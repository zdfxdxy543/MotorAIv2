from __future__ import annotations

import argparse
import json
import hmac
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from agent_silhelper.sil_session import network_options, run_matlab_job, validate_contract


WORKER_DIR = Path(__file__).resolve().parent
HELPER_SCRIPT = WORKER_DIR / "agent_silhelper" / "run_local_job.py"
DEFAULT_CONFIG = {
    "worker_id": "silworker",
    "job_root": "jobs",
    "default_matlab_session_name": None,
    "allow_model_roots": [],
    "default_timeout_sec": 1800,
    "max_request_bytes": 5 * 1024 * 1024,
    "python_executable": sys.executable,
}


def _merge_config(config_path: Path | None) -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)
    if config_path is None:
        return config

    config_path = config_path.expanduser()
    if not config_path.is_absolute():
        config_path = WORKER_DIR / config_path
    config_path = config_path.resolve()

    if not config_path.exists():
        raise FileNotFoundError(f"config file does not exist: {config_path}")

    data = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"config JSON root must be an object: {config_path}")
    config.update(data)
    return config


def _resolve_worker_path(raw_path: str | Path) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = WORKER_DIR / path
    return path.resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _tail(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


class SilWorkerState:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.lock = threading.Lock()
        self.active_lock = threading.Lock()
        self.active_job = None
        self.cancelled_jobs = {}
        self.worker_id = str(config.get("worker_id") or "silworker")
        self.job_root = _resolve_worker_path(str(config.get("job_root") or "jobs"))
        self.job_root.mkdir(parents=True, exist_ok=True)

    def validate_model_path(self, raw_path: Any) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("request must provide remote_model_path or model_path")

        model_path = Path(raw_path).expanduser().resolve()
        if not model_path.exists():
            raise FileNotFoundError(f"Simulink model does not exist: {model_path}")
        if model_path.suffix.lower() != ".slx":
            raise ValueError(f"Only .slx models are supported: {model_path}")

        allowed_roots = self.config.get("allow_model_roots") or []
        if allowed_roots:
            roots = [Path(str(root)).expanduser().resolve() for root in allowed_roots]
            if not any(_is_relative_to(model_path, root) for root in roots):
                allowed_text = ", ".join(str(root) for root in roots)
                raise PermissionError(
                    f"model_path is outside allow_model_roots: {model_path}; allowed={allowed_text}"
                )

        return model_path

    def prepare_simulation(self, request: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        return self.run_simulation({**request, "_prepare_only": True})

    def run_simulation(self, request: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if not HELPER_SCRIPT.exists():
            return 500, {
                "ok": False,
                "error": f"helper script not found: {HELPER_SCRIPT}",
            }

        if not self.lock.acquire(blocking=False):
            return 409, {
                "ok": False,
                "error": "worker is busy running another simulation",
                "worker_id": self.worker_id,
            }

        started_at = time.time()
        job = {'job_id': str(request.get('job_id') or uuid.uuid4().hex),
               'cancel_token': str(request.get('cancel_token') or ''),
               'cancelled': threading.Event(), 'done': threading.Event(), 'process': None}
        with self.active_lock:
            now = time.monotonic()
            self.cancelled_jobs = {key: expiry for key, expiry in self.cancelled_jobs.items() if expiry > now}
            if (job['job_id'], job['cancel_token']) in self.cancelled_jobs:
                self.lock.release()
                return 409, {'ok': False, 'error': 'job was cancelled before it started'}
            self.active_job = job
        try:
            return self._run_simulation_locked({**request, 'job_id': job['job_id']}, started_at)
        finally:
            with self.active_lock:
                self.active_job = None
                job['done'].set()
            self.lock.release()

    @staticmethod
    def _stop_process(process):
        if process is not None and process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, timeout=20,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            process.wait(timeout=20)

    def _track_process(self, process):
        with self.active_lock:
            job = self.active_job
            job['process'] = process
            cancelled = job['cancelled'].is_set()
        if cancelled:
            self._stop_process(process)

    def cancel_simulation(self, request):
        with self.active_lock:
            job = self.active_job
            if job is None:
                # The cancellation HTTP handler may run before the original
                # handler has registered its job. Remember this exact request.
                job_id = str(request.get('job_id') or '')
                token = str(request.get('cancel_token') or '')
                if job_id and token:
                    self.cancelled_jobs[(job_id, token)] = time.monotonic() + 300
                return 200, {'ok': True, 'status': 'already_finished'}
            token = str(request.get('cancel_token') or '')
            if (str(request.get('job_id') or '') != job['job_id'] or not job['cancel_token']
                    or not hmac.compare_digest(token, job['cancel_token'])):
                return 409, {'ok': False, 'error': 'cancel request does not match the active job'}
            job['cancelled'].set()
            process = job['process']
        self._stop_process(process)
        if not job['done'].wait(timeout=20):
            return 504, {'ok': False, 'error': 'remote job has not stopped yet'}
        return 200, {'ok': True, 'status': 'cancelled', 'job_id': job['job_id']}

    def _run_simulation_locked(
        self,
        request: dict[str, Any],
        started_at: float,
    ) -> tuple[int, dict[str, Any]]:
        job_id = str(request.get("job_id") or f"job_{uuid.uuid4().hex[:12]}")
        candidate_id = str(request.get("candidate_id") or "")
        model_path = self.validate_model_path(
            request.get("remote_model_path") or request.get("model_path")
        )
        network_config = self._network_config_from_request(request)
        if request.get("_prepare_only"):
            result = run_matlab_job(model_path, gmp_root=self.config.get("gmp_root"),
                                    network=network_config,
                                    scope_vars=request.get("scope_vars") or list(request.get("scope_map") or {}),
                                    process_started=self._track_process,
                                    timeout_sec=int(request.get("timeout_sec") or self.config.get("default_timeout_sec") or 1800))
            return 200, {"ok": True, "worker_id": self.worker_id,
                         "network_config": result["network_config"]}

        network_path = model_path.parent / "network.json"
        contract = validate_contract(json.loads(network_path.read_text(encoding="utf-8-sig")))
        if not request.get("expected_connection_id") or contract["connection_id"] != request["expected_connection_id"]:
            return 409, {"ok": False, "error": "SIL model changed; prepare it and restart the controller"}
        if network_options(contract) != network_config:
            return 409, {"ok": False, "error": "SIL network options changed since preparation"}

        scope_map = request.get("scope_map")
        if scope_map is None:
            scope_map = {}
        if not isinstance(scope_map, dict):
            raise ValueError("scope_map must be a JSON object")

        timeout_sec = int(request.get("timeout_sec") or self.config.get("default_timeout_sec") or 1800)
        if timeout_sec <= 0:
            raise ValueError("timeout_sec must be positive")

        session_name = request.get("session_name")
        if not isinstance(session_name, str) or not session_name.strip():
            session_name = self.config.get("default_matlab_session_name")
        session_name = str(session_name).strip() if session_name else ""

        no_open_ui = bool(request.get("no_open_ui", False))
        scope_vars = request.get("scope_vars")
        if scope_vars is not None:
            if not isinstance(scope_vars, list) or not all(isinstance(item, str) for item in scope_vars):
                raise ValueError("scope_vars must be a list of strings")

        request_path = self.job_root / "request.json"
        scope_map_path = self.job_root / "scope_channel_map.json"
        raw_output = self.job_root / "raw.json"
        processed_output = self.job_root / "processed.json"
        stdout_path = self.job_root / "run_local_job_stdout.txt"
        stderr_path = self.job_root / "run_local_job_stderr.txt"

        for stale_path in (raw_output, processed_output, stdout_path, stderr_path):
            try:
                stale_path.unlink()
            except FileNotFoundError:
                pass

        request_record = {
            "received_at_unix": started_at,
            "worker_id": self.worker_id,
            "job_id": job_id,
            "candidate_id": candidate_id,
            "network_config": network_config,
            "request": request,
        }
        request_path.write_text(
            json.dumps(request_record, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        scope_map_path.write_text(
            json.dumps(scope_map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        python_executable = str(self.config.get("python_executable") or sys.executable)
        command = [
            python_executable,
            str(HELPER_SCRIPT),
            "--model-path",
            str(model_path),
            "--scope-map",
            str(scope_map_path),
            "--raw-output",
            str(raw_output),
            "--processed-output",
            str(processed_output),
            "--expected-connection-id", contract["connection_id"],
            "--timeout-sec", str(timeout_sec),
        ]
        if self.config.get("gmp_root"):
            command.extend(["--gmp-root", str(self.config["gmp_root"])])
        if request.get('cancel_token'):
            command.append('--batch')
        elif session_name:
            command.extend(["--session-name", session_name])
        if no_open_ui:
            command.append("--no-open-ui")
        if scope_vars:
            command.extend(["--scope-vars", *scope_vars])

        try:
            process = subprocess.Popen(
                command,
                cwd=str(WORKER_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._track_process(process)
            stdout, stderr = process.communicate(timeout=timeout_sec + 60)
            completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        except subprocess.TimeoutExpired as exc:
            self._stop_process(process)
            process.communicate()
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            stdout_path.write_text(str(stdout), encoding="utf-8")
            stderr_path.write_text(str(stderr), encoding="utf-8")
            return 504, {
                "ok": False,
                "worker_id": self.worker_id,
                "job_id": job_id,
                "candidate_id": candidate_id,
                "error": f"simulation timed out after {timeout_sec} seconds",
                "stdout_tail": _tail(str(stdout)),
                "stderr_tail": _tail(str(stderr)),
                "elapsed_sec": round(time.time() - started_at, 3),
            }

        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")

        if completed.returncode != 0:
            return 500, {
                "ok": False,
                "worker_id": self.worker_id,
                "job_id": job_id,
                "candidate_id": candidate_id,
                "returncode": completed.returncode,
                "error": "run_local_job.py failed",
                "stdout_tail": _tail(completed.stdout or ""),
                "stderr_tail": _tail(completed.stderr or ""),
                "elapsed_sec": round(time.time() - started_at, 3),
            }

        if not processed_output.exists():
            return 500, {
                "ok": False,
                "worker_id": self.worker_id,
                "job_id": job_id,
                "candidate_id": candidate_id,
                "error": f"processed.json was not created: {processed_output}",
                "stdout_tail": _tail(completed.stdout or ""),
                "stderr_tail": _tail(completed.stderr or ""),
                "elapsed_sec": round(time.time() - started_at, 3),
            }

        processed_json = json.loads(processed_output.read_text(encoding="utf-8-sig"))
        return 200, {
            "ok": True,
            "worker_id": self.worker_id,
            "job_id": job_id,
            "candidate_id": candidate_id,
            "processed_json": processed_json,
            "elapsed_sec": round(time.time() - started_at, 3),
            "worker_files": {
                "request": str(request_path),
                "scope_map": str(scope_map_path),
                "network": str(network_path),
                "raw": str(raw_output),
                "processed": str(processed_output),
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
            },
        }

    @staticmethod
    def _network_config_from_request(request: dict[str, Any]) -> dict[str, Any]:
        network = request.get("network_config")
        if not isinstance(network, dict):
            network = {}
        return network_options({**request, **network})


def make_handler(state: SilWorkerState) -> type[BaseHTTPRequestHandler]:
    class SilWorkerHandler(BaseHTTPRequestHandler):
        server_version = "MotorAI-SILWorker/1.0"

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write(
                "%s - - [%s] %s\n"
                % (self.client_address[0], self.log_date_time_string(), format % args)
            )

        def do_GET(self) -> None:
            if self.path.rstrip("/") == "/health":
                self._json_response(
                    200,
                    {
                        "ok": True,
                        "worker_id": state.worker_id,
                        "busy": state.lock.locked(),
                        "job_root": str(state.job_root),
                    },
                )
                return
            self._json_response(404, {"ok": False, "error": "not found"})

        def do_POST(self) -> None:
            if self.path.rstrip("/") not in ("/run_simulation", "/prepare_simulation", "/cancel_simulation"):
                self._json_response(404, {"ok": False, "error": "not found"})
                return

            try:
                request = self._read_json_body()
                operation = {'/prepare_simulation': state.prepare_simulation,
                             '/run_simulation': state.run_simulation,
                             '/cancel_simulation': state.cancel_simulation}[self.path.rstrip('/')]
                status_code, payload = operation(request)
                self._json_response(status_code, payload)
            except PermissionError as exc:
                self._json_response(403, {"ok": False, "error": str(exc)})
            except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
                self._json_response(400, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            except Exception as exc:
                self._json_response(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})

        def _read_json_body(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            max_bytes = int(state.config.get("max_request_bytes") or DEFAULT_CONFIG["max_request_bytes"])
            if content_length <= 0:
                raise ValueError("empty request body")
            if content_length > max_bytes:
                raise ValueError(f"request body is too large: {content_length} > {max_bytes}")

            raw = self.rfile.read(content_length)
            body = json.loads(raw.decode("utf-8-sig"))
            if not isinstance(body, dict):
                raise ValueError("request JSON root must be an object")
            return body

        def _json_response(self, status_code: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return SilWorkerHandler


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lightweight MotorAI remote Simulink worker")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--config", type=Path, default=WORKER_DIR / "silworker_config.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = _merge_config(args.config)
    state = SilWorkerState(config)
    handler_cls = make_handler(state)
    server = ThreadingHTTPServer((args.host, args.port), handler_cls)

    print(f"[silworker] worker_id={state.worker_id}")
    print(f"[silworker] job_root={state.job_root}")
    print(f"[silworker] listening on http://{args.host}:{args.port}")
    print("[silworker] health endpoint: /health")
    print("[silworker] run endpoint: POST /run_simulation")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[silworker] stopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
