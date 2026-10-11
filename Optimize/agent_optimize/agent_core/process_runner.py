import os
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


def validate_bat_path(bat_path: Path) -> Optional[str]:
    if os.name != "nt":
        return "Error: .bat execution requires Windows. This tool must be run on the engineering PC."
    if not bat_path.exists():
        return f"Error: bat file does not exist: {bat_path}"
    if bat_path.suffix.lower() != ".bat":
        return f"Error: configured automation target is not a .bat file: {bat_path}"
    return None


def start_bat_async(
    bat_path: Path,
    args: Optional[List[str]] = None,
    new_console: bool = True,
) -> Tuple[Optional[subprocess.Popen], str]:
    """Start a whitelisted .bat asynchronously. No arbitrary command strings."""
    err = validate_bat_path(bat_path)
    if err:
        return None, err

    command = ["cmd.exe", "/d", "/c", str(bat_path)]
    if args:
        command.extend(str(arg) for arg in args)

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    try:
        console_log = bat_path.with_name(bat_path.stem + "_console.log")
        with console_log.open("wb") as console:
            proc = subprocess.Popen(
                command, cwd=str(bat_path.parent), creationflags=creationflags,
                stdout=console, stderr=subprocess.STDOUT,
            )
    except OSError as exc:
        return None, f"Error: failed to start bat file: {bat_path}\n{exc}"

    return proc, f"OK: started bat asynchronously. pid={proc.pid}, bat={bat_path}, console_log={console_log}"


def run_bat_sync_in_new_console(
    bat_path: Path,
    args: Optional[List[str]] = None,
    timeout_sec: int = 600,
) -> str:
    """Start a whitelisted .bat in a new console and wait for it."""
    proc, msg = start_bat_async(bat_path=bat_path, args=args, new_console=True)
    if proc is None:
        return msg

    try:
        returncode = proc.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        stop_process_tree(proc)
        return f"Error: bat timed out after {timeout_sec} seconds. pid={proc.pid}, bat={bat_path}"

    if returncode != 0:
        log = bat_path.with_name(bat_path.stem + "_console.log")
        detail = log.read_text(encoding="utf-8", errors="replace")[-12000:] if log.is_file() else ""
        return f"Error: bat failed. returncode={returncode}, pid={proc.pid}, bat={bat_path}\n{detail}"

    return f"OK: bat finished successfully. returncode=0, pid={proc.pid}, bat={bat_path}"


def stop_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                   capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    proc.wait(timeout=10)
