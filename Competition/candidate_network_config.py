from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

MOTORAI_ROOT = Path(__file__).resolve().parents[1]
if str(MOTORAI_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTORAI_ROOT))

from Competition.competition_workspace import discover_candidate_dirs, load_json_object, write_json
from Optimize.agent_silhelper.sil_session import network_options


DEFAULT_NETWORK_CONFIG = {
    "target_address": "127.0.0.1",
    "receive_port": 12500,
    "transmit_port": 12501,
    "transport": "udp",
}


def _candidate_sort_key(path: Path) -> tuple[int, str]:
    try:
        return int(path.name.rsplit("_", 1)[-1]), path.name
    except (TypeError, ValueError):
        return 9999, path.name


def _candidate_index(path: Path) -> int:
    try:
        return int(path.name.rsplit("_", 1)[-1])
    except (TypeError, ValueError):
        return 1


def default_network_config_for_candidate(candidate_dir: Path) -> dict[str, Any]:
    config = dict(DEFAULT_NETWORK_CONFIG)
    index = _candidate_index(candidate_dir)
    config["receive_port"] = 12500 + (index - 1) * 100
    config["transmit_port"] = 12501 + (index - 1) * 100
    return config


def _normalize_network_config(
    *, candidate_dir: Path, target_address: str | None = None,
    receive_port: int | str | None = None, transmit_port: int | str | None = None,
    transport: str = "udp",
) -> dict[str, Any]:
    config = default_network_config_for_candidate(candidate_dir)
    config["transport"] = transport
    for key, value in (("target_address", target_address),
                       ("receive_port", receive_port), ("transmit_port", transmit_port)):
        if value is not None and str(value).strip():
            config[key] = value
    return network_options(config)


def _candidate_json_path(candidate_dir: Path) -> Path:
    return candidate_dir / "candidate.json"


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return load_json_object(path)
    except Exception:
        return {}


def _remote_model_default(candidate_dir: Path, candidate_data: dict[str, Any]) -> str:
    raw = candidate_data.get("remote_model_path")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    backend = candidate_data.get("simulation_backend")
    if isinstance(backend, dict):
        raw = backend.get("remote_model_path") or backend.get("model_path")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    raw = candidate_data.get("simulink_model_path")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return str((candidate_dir / "project" / "simulate" / "MCS_STD_PMSM_MODEL.slx").resolve())


def _build_backend(
    *,
    mode: str,
    candidate_dir: Path,
    candidate_data: dict[str, Any],
    worker_url: str = "",
    remote_model_path: str = "",
    network_config: dict[str, Any],
) -> dict[str, Any]:
    mode = (mode or "local").strip().lower()
    if mode not in ("local", "remote"):
        raise ValueError(f"Unsupported SIL backend: {mode}")
    if mode != "remote":
        return {"mode": "local"}

    model_path = remote_model_path.strip() or _remote_model_default(candidate_dir, candidate_data)
    backend = {
        "mode": "remote",
        "worker_url": worker_url.strip(),
        "remote_model_path": model_path,
        "target_address": network_config["target_address"],
        "receive_port": int(network_config["receive_port"]),
        "transmit_port": int(network_config["transmit_port"]),
        "transport": network_config["transport"],
    }
    return backend


def list_candidate_network_configs(project_json: Path) -> list[dict[str, Any]]:
    project_json = project_json.expanduser().resolve()
    candidate_dirs = sorted(discover_candidate_dirs(project_json, ["all"]), key=_candidate_sort_key)
    rows: list[dict[str, Any]] = []
    for candidate_dir in candidate_dirs:
        candidate_data = _load_json_if_exists(_candidate_json_path(candidate_dir))
        backend = candidate_data.get("simulation_backend")
        if not isinstance(backend, dict):
            backend = {}
        network_path = candidate_dir / "project" / "simulate" / "network.json"
        network = _load_json_if_exists(network_path)
        if not network:
            network = candidate_data.get("network_config") if isinstance(candidate_data.get("network_config"), dict) else {}
        if not network:
            network = default_network_config_for_candidate(candidate_dir)

        rows.append(
            {
                "candidate_id": candidate_dir.name,
                "candidate_dir": str(candidate_dir),
                "mode": str(backend.get("mode") or "local").lower(),
                "worker_url": str(backend.get("worker_url") or ""),
                "remote_model_path": _remote_model_default(candidate_dir, candidate_data),
                "network": _normalize_network_config(
                    candidate_dir=candidate_dir,
                    target_address=network.get("target_address"),
                    receive_port=network.get("receive_port"),
                    transmit_port=network.get("transmit_port"),
                    transport=str(network.get("transport") or "udp"),
                ),
                "network_json": str(network_path),
            }
        )
    return rows


def save_candidate_network_config(
    project_json: Path,
    candidate_id: str,
    *,
    mode: str,
    worker_url: str = "",
    remote_model_path: str = "",
    target_address: str = "127.0.0.1",
    receive_port: int = 12500,
    transmit_port: int = 12501,
    transport: str = "udp",
    scheduler_url: str = "",
) -> dict[str, Any]:
    project_json = project_json.expanduser().resolve()
    candidate_dirs = {path.name: path for path in discover_candidate_dirs(project_json, ["all"])}
    if candidate_id not in candidate_dirs:
        raise FileNotFoundError(f"candidate not found: {candidate_id}")

    candidate_dir = candidate_dirs[candidate_id]
    candidate_json = _candidate_json_path(candidate_dir)
    candidate_data = _load_json_if_exists(candidate_json)
    if not candidate_data:
        candidate_data = {"candidate_id": candidate_id, "candidate_root": str(candidate_dir)}

    network_config = _normalize_network_config(
        candidate_dir=candidate_dir,
        target_address=target_address,
        receive_port=receive_port,
        transmit_port=transmit_port,
        transport=transport,
    )
    backend = _build_backend(
        mode=mode, candidate_dir=candidate_dir, candidate_data=candidate_data,
        worker_url=worker_url, remote_model_path=remote_model_path, network_config=network_config,
    )
    network_path = candidate_dir / "project" / "simulate" / "network.json"
    previous = _load_json_if_exists(network_path)
    # Keep the model-owned identity only while all connection settings stay unchanged.
    try:
        unchanged = bool(previous) and network_options(previous) == network_config
    except ValueError:
        unchanged = False
    if unchanged:
        published = {**previous, **network_config}
        published.pop("command_recv_port", None)
        published.pop("command_trans_port", None)
    else:
        published = network_config
    write_json(network_path, published)

    candidate_data["network_config"] = network_config
    candidate_data["simulation_backend"] = backend
    write_json(candidate_json, candidate_data)

    _update_project_backend(project_json, candidate_id, backend)
    _ensure_remote_simulation_bat(candidate_dir)
    _update_agent_project(candidate_dir, backend)

    return {
        "candidate_id": candidate_id,
        "mode": backend["mode"],
        "candidate_json": str(candidate_json),
        "network_json": str(network_path),
        "simulation_backend": backend,
        "network_config": network_config,
    }


def _update_project_backend(project_json: Path, candidate_id: str, backend: dict[str, Any]) -> None:
    project_data = _load_json_if_exists(project_json)
    if not project_data:
        return
    backends = project_data.get("candidate_simulation_backends")
    if not isinstance(backends, dict):
        backends = {}
    backends[candidate_id] = backend
    project_data["candidate_simulation_backends"] = backends
    write_json(project_json, project_data)


def _update_agent_project(candidate_dir: Path, backend: dict[str, Any]) -> None:
    agent_project = candidate_dir / "log" / "optimize" / "agent_project.json"
    data = _load_json_if_exists(agent_project)
    if not data:
        return
    automation = data.get("automation")
    if not isinstance(automation, dict):
        automation = {}
        data["automation"] = automation
    automation["simulation_backend"] = backend
    automation.setdefault("scope_map", "simulation/scope_channel_map.json")
    automation.setdefault("remote_sim_bat_path", "run_remote_simulation.bat")
    write_json(agent_project, data)


def _ensure_remote_simulation_bat(candidate_dir: Path) -> None:
    log_optimize = candidate_dir / "log" / "optimize"
    remote_bat = log_optimize / "run_remote_simulation.bat"
    remote_client = Path(__file__).resolve().parents[1] / "Optimize" / "agent_silhelper" / "remote_sil_client.py"
    content = f"""@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
if not exist "%SCRIPT_DIR%simulation" mkdir "%SCRIPT_DIR%simulation"

python "{remote_client}" --agent-project "%SCRIPT_DIR%agent_project.json" > "%SCRIPT_DIR%simulation\\remote_client_stdout.txt" 2> "%SCRIPT_DIR%simulation\\remote_client_stderr.txt"
exit /b %ERRORLEVEL%
"""
    remote_bat.parent.mkdir(parents=True, exist_ok=True)
    remote_bat.write_text(content, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write MotorAI candidate co-simulation network config")
    parser.add_argument("project_json", type=Path)
    parser.add_argument("candidate_id")
    parser.add_argument("--mode", choices=["local", "remote"], default="local")
    parser.add_argument("--worker-url", default="")
    parser.add_argument("--remote-model-path", default="")
    parser.add_argument("--target-address", default="127.0.0.1")
    parser.add_argument("--receive-port", type=int, default=12500)
    parser.add_argument("--transmit-port", type=int, default=12501)
    parser.add_argument("--transport", choices=["udp", "tcp"], default="udp")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = save_candidate_network_config(
        args.project_json,
        args.candidate_id,
        mode=args.mode,
        worker_url=args.worker_url,
        remote_model_path=args.remote_model_path,
        target_address=args.target_address,
        receive_port=args.receive_port,
        transmit_port=args.transmit_port,
        transport=args.transport,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
