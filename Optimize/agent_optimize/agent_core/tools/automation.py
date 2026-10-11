import subprocess
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import ProjectContext
from ..constants import DEFAULT_MAX_CHARS
from ..process_runner import run_bat_sync_in_new_console, start_bat_async, stop_process_tree
from ..tool_registry import ToolRegistry
from ..utils import file_updated_after, read_text_if_exists

# agent.py can be launched directly from Optimize/agent_optimize.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from agent_silhelper.sil_session import run_matlab_job, validate_contract, write_contract
from agent_silhelper.remote_sil_client import prepare_remote_simulation


class AutomationTools:
    def __init__(self, ctx: ProjectContext) -> None:
        self.ctx = ctx
        self.active_exe_process: Optional[subprocess.Popen] = None
        self.active_exe_started_at: float = 0.0
        self.active_exe_bat_path: Optional[Path] = None
        self.prepared_contract: Optional[Dict[str, Any]] = None

    def prepare_simulation(self) -> str:
        model = self._path_from_automation("sim_model_path")
        if model is None:
            return "Error: automation.sim_model_path is required for SIL preparation."
        try:
            print("[stage] 正在准备 MATLAB 模型和 SIL 接口。", flush=True)
            backend = self._simulation_backend()
            mode = str(backend.get("mode") or "local").lower()
            if mode == "remote":
                contract = prepare_remote_simulation(self.ctx.project_config_path)
            elif mode == "local":
                scope_map = self._path_from_automation("scope_map", "../log/simulation/scope_channel_map.json")
                names = list(json.loads(scope_map.read_text(encoding="utf-8-sig"))) if scope_map and scope_map.is_file() else []
                result = run_matlab_job(model, gmp_root=self._automation().get("gmp_root"),
                                        scope_vars=names,
                                        timeout_sec=int(self._automation().get("sim_timeout_sec", 1800)))
                contract = result["network_config"]
            else:
                return f"Error: unsupported simulation backend: {mode}"
            write_contract(model.parent / "network.json", contract)
            self.prepared_contract = contract
            return f"OK: SIL model prepared. connection_id={contract['connection_id']}"
        except Exception as exc:
            self.prepared_contract = None
            return f"Error: SIL preparation failed: {exc}"

    def _automation(self) -> Dict[str, Any]:
        return self.ctx.automation()

    def _path_from_automation(self, key: str, default: Optional[str] = None) -> Optional[Path]:
        value = self._automation().get(key, default)
        if not value:
            return None
        return self.ctx.resolve_config_path(str(value))

    def _simulation_backend(self) -> Dict[str, Any]:
        backend = self._automation().get("simulation_backend")
        if isinstance(backend, dict):
            return backend
        return {"mode": "local"}

    def build_solution(self) -> str:
        """Run build_sln.bat synchronously. With the split-bat design, this bat must only build and exit."""
        automation = self._automation()
        bat_path = self._path_from_automation("build_bat_path")
        if bat_path is None:
            return "Error: automation.build_bat_path is not configured in agent_project.json."

        timeout_sec = int(automation.get("build_timeout_sec", 900))
        build_log = self._path_from_automation("build_agent_log", "../log/build.log")
        started_at = time.time()

        print("[stage] 正在编译控制程序。", flush=True)

        result = run_bat_sync_in_new_console(
            bat_path=bat_path,
            args=[],
            timeout_sec=timeout_sec,
        )

        log_status = ""
        if build_log is not None:
            if file_updated_after(build_log, started_at, slack_sec=2.0):
                log_status = f"build.log was updated: {build_log}"
            elif build_log.exists():
                log_status = f"build.log exists but timestamp does not look newer than this run: {build_log}"
            else:
                log_status = f"build.log does not exist: {build_log}"

        if result.startswith("Error"):
            return (
                "Error: build_sln.bat failed.\n\n"
                f"[bat_result]\n{result}\n\n"
                f"[build_log_status]\n{log_status}\n\n"
                f"[build.log]\n{read_text_if_exists(build_log, DEFAULT_MAX_CHARS) if build_log else '[not configured]'}"
            )

        return (
            "OK: build stage finished successfully.\n\n"
            f"[bat_result]\n{result}\n\n"
            f"[build_log_status]\n{log_status}\n\n"
            f"[build.log]\n{read_text_if_exists(build_log, 4000) if build_log else '[not configured]'}"
        )

    def start_exe(self) -> str:
        """Start start_exe.bat asynchronously. The exe may block while waiting for Simulink."""
        automation = self._automation()
        bat_path = self._path_from_automation("start_exe_bat_path")
        if bat_path is None:
            return "Error: automation.start_exe_bat_path is not configured in agent_project.json."

        if self.active_exe_process is not None and self.active_exe_process.poll() is None:
            return (
                "Error: an exe/start_exe process is already running. "
                f"pid={self.active_exe_process.pid}. Wait for it to finish before starting another run."
            )

        preparation = self.prepare_simulation()
        if preparation.startswith("Error:"):
            return preparation

        run_exe_log = self._path_from_automation("run_exe_log", "../log/run_exe.log")
        timeout_sec = int(automation.get("exe_start_timeout_sec", 120))

        started_at = time.time()
        print("[stage] 正在启动控制器，等待 SIL 接口就绪。", flush=True)
        proc, msg = start_bat_async(bat_path=bat_path, args=[], new_console=True)
        if proc is None:
            return msg

        self.active_exe_process = proc
        self.active_exe_started_at = started_at
        self.active_exe_bat_path = bat_path

        # Wait for run_exe.log to update. This confirms start_exe.bat reached the exe-launch stage.
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if (proc.poll() is None and run_exe_log is not None
                    and file_updated_after(run_exe_log, started_at, slack_sec=1.0)
                    and "GMP SIL controller is waiting" in read_text_if_exists(run_exe_log, 4000)):
                return (
                    f"{msg}\n"
                    "OK: controller reported that it is waiting for Simulink.\n\n"
                    f"[run_exe.log]\n{read_text_if_exists(run_exe_log, 4000)}"
                )

            returncode = proc.poll()
            if returncode is not None:
                return (
                    f"Error: start_exe.bat exited before exe launch. returncode={returncode}\n\n"
                    f"[run_exe.log]\n{read_text_if_exists(run_exe_log, DEFAULT_MAX_CHARS) if run_exe_log else '[not configured]'}"
                )
            time.sleep(0.5)

        stop_process_tree(proc)
        return (
            f"Error: timed out while waiting for run_exe.log update after {timeout_sec} seconds.\n"
            f"pid={proc.pid}, bat={bat_path}\n\n"
            f"[run_exe.log]\n{read_text_if_exists(run_exe_log, DEFAULT_MAX_CHARS) if run_exe_log else '[not configured]'}"
        )

    def run_simulation_bat(self) -> str:
        """Run the configured simulation backend and wait until processed.json is fully written."""
        automation = self._automation()
        backend = self._simulation_backend()
        mode = str(backend.get("mode", "local") or "local").strip().lower()
        if mode == "remote":
            bat_path = self._path_from_automation("remote_sim_bat_path", "run_remote_simulation.bat")
        elif mode == "local":
            bat_path = self._path_from_automation("sim_bat_path")
        else:
            return f"Error: unsupported automation.simulation_backend.mode: {mode}"

        if bat_path is None:
            return "Error: simulation bat path is not configured in agent_project.json."
        if self.active_exe_process is None or self.active_exe_process.poll() is not None:
            return "Error: controller is not running; prepare and start it before simulation."

        timeout_sec = int(backend.get("timeout_sec") or automation.get("sim_timeout_sec", 1800))
        result_json = self._path_from_automation("simulation_result", "../log/processed.json")
        run_exe_log = self._path_from_automation("run_exe_log", "../log/run_exe.log")

        args = []
        model = self._path_from_automation("sim_model_path")
        try:
            contract = validate_contract(json.loads((model.parent / "network.json").read_text(encoding="utf-8-sig")))
            if not self.prepared_contract or contract["connection_id"] != self.prepared_contract["connection_id"]:
                return "Error: SIL contract changed or was not prepared; restart the controller."
        except Exception as exc:
            return f"Error: invalid SIL contract: {exc}"
        model_path = self._path_from_automation("sim_model_path") if mode == "local" else None
        if mode == "local" and model_path is not None:
            args.extend([str(model_path), str(self._automation().get("gmp_root") or ""), contract["connection_id"]])

        if result_json is not None:
            try:
                result_json.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                return f"Error: failed to remove stale processed.json before simulation: {result_json}\n{exc}"

        sim_started_at = time.time()
        print(f"[stage] 正在运行闭环仿真（{mode}，超时上限 {timeout_sec} 秒）；单次可能需要数分钟。", flush=True)
        sim_result = run_bat_sync_in_new_console(
            bat_path=bat_path,
            args=args,
            timeout_sec=timeout_sec,
        )

        result_status = ""
        result_ready = False
        if result_json is not None:
            if file_updated_after(result_json, sim_started_at, slack_sec=3.0):
                result_status = f"processed.json was updated: {result_json}"
                result_ready = True
            elif result_json.exists():
                result_status = f"processed.json exists but timestamp does not look newer than this run: {result_json}"
            else:
                result_status = f"processed.json does not exist: {result_json}"

        if sim_result.lstrip().startswith("Error:"):
            return "\n".join(
                [
                    sim_result,
                    result_status,
                    "",
                    f"[run_exe.log]\n{read_text_if_exists(run_exe_log, 4000) if run_exe_log else '[not configured]'}",
                ]
            )

        if result_json is not None and not result_ready:
            return "\n".join(
                [
                    "Error: simulation backend finished but processed.json was not updated.",
                    f"backend_mode={mode}",
                    result_status,
                    f"[bat_result]\n{sim_result}",
                    "",
                    f"[run_exe.log]\n{read_text_if_exists(run_exe_log, 4000) if run_exe_log else '[not configured]'}",
                ]
            )

        if result_json is not None:
            data = json.loads(result_json.read_text(encoding="utf-8-sig"))
            if data.get("status") != "done" or data.get("scope_mapping_errors"):
                return f"Error: simulation output is invalid: {data.get('diagnostics', {})}"

        print("[stage] 仿真完成，输出数据已验证。", flush=True)

        parts = [
            f"OK: simulation backend finished. backend_mode={mode}",
            sim_result,
            result_status,
            "",
            f"[run_exe.log]\n{read_text_if_exists(run_exe_log, 4000) if run_exe_log else '[not configured]'}",
        ]
        return "\n".join(parts)

    def wait_for_exe_exit(self, timeout_sec: int = 120) -> str:
        if self.active_exe_process is None:
            return "OK: no active exe/start_exe process is tracked."

        try:
            code = self.active_exe_process.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            stop_process_tree(self.active_exe_process)
            return (
                "Error: start_exe.bat/exe did not exit within "
                f"{timeout_sec} seconds. pid={self.active_exe_process.pid}. "
                "Check whether the exe is still waiting or stuck."
            )

        pid = self.active_exe_process.pid
        self.active_exe_process = None
        return f"{'OK' if code == 0 else 'Error'}: start_exe.bat/exe exited. pid={pid}, returncode={code}."

    def run_closed_loop_once(self) -> str:
        """One complete split-bat orchestration."""
        build_result = self.build_solution()
        if build_result.lstrip().startswith("Error:"):
            return "Error: closed loop stopped at build stage.\n\n" + build_result

        exe_result = self.start_exe()
        if exe_result.lstrip().startswith("Error:"):
            return (
                "Error: closed loop stopped at exe-start stage.\n\n"
                f"[build_result]\n{build_result}\n\n"
                f"[exe_result]\n{exe_result}"
            )

        sim_result = self.run_simulation_bat()
        if sim_result.lstrip().startswith("Error:"):
            wait_result = self.wait_for_exe_exit(timeout_sec=30)
            return (
                "Error: closed loop stopped at simulation stage.\n\n"
                f"[build_result]\n{build_result}\n\n"
                f"[exe_result]\n{exe_result}\n\n"
                f"[simulation_result]\n{sim_result}\n\n"
                f"[wait_for_exe_exit]\n{wait_result}"
            )

        wait_result = self.wait_for_exe_exit(timeout_sec=120)
        if wait_result.startswith("Error:"):
            return "Error: closed-loop controller failed.\n" + wait_result

        result_json = self._path_from_automation("simulation_result", "../log/processed.json")
        run_exe_log = self._path_from_automation("run_exe_log", "../log/run_exe.log")

        return (
            "OK: closed-loop run finished.\n\n"
            f"[build_result]\n{build_result}\n\n"
            f"[exe_result]\n{exe_result}\n\n"
            f"[simulation_result]\n{sim_result}\n\n"
            f"[wait_for_exe_exit]\n{wait_result}\n\n"
            f"[processed.json]\n{read_text_if_exists(result_json, 4000) if result_json else '[not configured]'}\n\n"
            f"[run_exe.log]\n{read_text_if_exists(run_exe_log, 4000) if run_exe_log else '[not configured]'}"
        )


def register_automation_tools(registry: ToolRegistry, ctx: ProjectContext) -> AutomationTools:
    tool = AutomationTools(ctx)

    registry.register(
        "build_solution",
        {
            "type": "function",
            "function": {
                "name": "build_solution",
                "description": "Synchronously call build_sln.bat to build the Visual Studio solution. Split-bat version: this bat must only build and exit.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        lambda args: tool.build_solution(),
    )

    registry.register(
        "start_exe",
        {
            "type": "function",
            "function": {
                "name": "start_exe",
                "description": "Asynchronously call start_exe.bat to start the generated exe. The exe may wait for Simulink.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        lambda args: tool.start_exe(),
    )

    registry.register(
        "run_simulation_bat",
        {
            "type": "function",
            "function": {
                "name": "run_simulation_bat",
                "description": "Synchronously call the configured local or remote Simulink backend and generate processed.json.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        lambda args: tool.run_simulation_bat(),
    )

    registry.register(
        "wait_for_exe_exit",
        {
            "type": "function",
            "function": {
                "name": "wait_for_exe_exit",
                "description": "Wait for the active start_exe.bat/exe process to exit.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timeout_sec": {"type": "integer", "description": "Seconds to wait. Default is 120."}
                    },
                },
            },
        },
        lambda args: tool.wait_for_exe_exit(timeout_sec=args.get("timeout_sec", 120)),
    )

    registry.register(
        "run_closed_loop_once",
        {
            "type": "function",
            "function": {
                "name": "run_closed_loop_once",
                "description": "Run one complete split-bat closed loop: build_sln.bat, start_exe.bat, simulation backend, wait for exe exit, then report processed.json and run_exe.log.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        lambda args: tool.run_closed_loop_once(),
    )

    return tool
