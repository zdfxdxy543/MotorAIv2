"""Prepare the model-owned GMP SIL contract before launching a controller."""
from __future__ import annotations

import ipaddress
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any


def network_options(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data or {}
    address = str(data.get('target_address') or '127.0.0.1').strip()
    if address.lower() == 'localhost':
        address = '127.0.0.1'
    ipaddress.IPv4Address(address)
    transport = str(data.get('transport') or 'udp').lower()
    if transport not in ('udp', 'tcp'):
        raise ValueError('SIL transport must be udp or tcp')
    result = {'transport': transport, 'target_address': address}
    for key, default in [('receive_port', 12500), ('transmit_port', 12501)]:
        value = int(data.get(key, default))
        if not 1 <= value <= 65535:
            raise ValueError(f'{key} must be in [1, 65535]')
        result[key] = value
    if transport == 'udp' and result['receive_port'] == result['transmit_port']:
        raise ValueError('UDP controller and model must use different ports')
    return result


def validate_contract(data: dict[str, Any]) -> dict[str, Any]:
    if data.get('schema_version') != 1 or data.get('role') != 'server':
        raise ValueError('Expected a GMP SIL schema_version=1 server contract')
    if data.get('protocol_version') != 1:
        raise ValueError('Expected GMP SIL protocol_version=1')
    if not re.fullmatch(r'[0-9a-fA-F]{32}', str(data.get('connection_id', ''))):
        raise ValueError('Missing or invalid model-generated connection_id; prepare the model first')
    network_options(data)
    # MotorAI's xplt.config.h selects the packed dp_sil buffers.
    for key, expected in [('simulink_to_controller_bytes', 264), ('controller_to_simulink_bytes', 200)]:
        if data.get(key) != expected:
            raise ValueError(f'{key} must be {expected} for the MotorAI dp_sil ABI')
    return dict(data)


def write_contract(path: Path, contract: dict[str, Any]) -> None:
    validate_contract(contract)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def matlab_executable() -> str:
    configured = os.environ.get('GMP_MATLAB_EXECUTABLE', '').strip()
    if configured:
        if not Path(configured).is_file():
            raise FileNotFoundError(f'GMP_MATLAB_EXECUTABLE does not exist: {configured}')
        return configured
    available = shutil.which('matlab')
    if available:
        return available
    if os.name == 'nt':
        directory = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'MATLAB'
        releases = sorted(p for p in directory.glob('R20[0-9][0-9][ab]')
                          if 'R2022b' <= p.name <= 'R2025b' and (p/'bin/matlab.exe').is_file())
        if releases:
            return str(releases[-1]/'bin/matlab.exe')
    raise FileNotFoundError('MATLAB was not found; set GMP_MATLAB_EXECUTABLE to a supported MATLAB executable')


def resolve_gmp_root(root: str | Path | None = None) -> Path:
    value = root or os.environ.get('GMP_PRO_LOCATION')
    if not value:
        settings = Path(__file__).resolve().parents[2] / 'motorai_settings.json'
        if settings.is_file():
            value = json.loads(settings.read_text(encoding='utf-8-sig')).get('paths', {}).get('gmp_root')
    if not value:
        raise ValueError('GMP root is required for SIL preparation')
    result = Path(value).expanduser().resolve()
    if not (result/'tools/gmp_sil/sil_helper/gmp_sil_helper.hpp').is_file():
        raise ValueError(f'Configured platform does not provide the new GMP SIL protocol: {result}')
    return result


def run_matlab_job(model_path: str | Path, *, action: str = 'prepare',
                   gmp_root: str | Path | None = None, network: dict[str, Any] | None = None,
                   scope_vars: list[str] | None = None, timeout_sec: int = 1800,
                   expected_connection_id: str | None = None, engine=None,
                   open_model_ui: bool = False, process_started=None) -> dict[str, Any]:
    model = Path(model_path).expanduser().resolve()
    if not model.is_file() or model.suffix.lower() != '.slx':
        raise FileNotFoundError(f'Simulink model does not exist: {model}')
    if action not in ('prepare', 'run'):
        raise ValueError(f'Unsupported SIL action: {action}')
    root = resolve_gmp_root(gmp_root)
    if network is None:
        path = model.parent/'network.json'
        network = json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {}
    helper_directory = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix='motorai_sil_') as temporary:
        directory = Path(temporary)
        request = {'model_path': str(model), 'action': action, 'gmp_root': str(root),
                   'network': network_options(network), 'scope_vars': scope_vars or [],
                   'result_path': str(directory/'result.json'),
                   'expected_connection_id': expected_connection_id or ''}
        request['open_model_ui'] = bool(open_model_ui and engine is not None)
        request_path = directory/'request.json'
        request_path.write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8')
        quote = lambda path: str(path).replace("'", "''")
        expression = f"addpath('{quote(helper_directory)}'); motorai_sil_job('{quote(request_path)}');"
        if engine is None:
            command = [matlab_executable(), '-batch', expression]
            if os.name == 'nt':
                command.insert(1, '-wait')
            process = subprocess.Popen(command, cwd=model.parent, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, encoding='utf-8', errors='replace',
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if process_started is not None:
                process_started(process)
            try:
                stdout, stderr = process.communicate(timeout=timeout_sec)
            except subprocess.TimeoutExpired:
                # MATLAB's Windows executable launches a child process; stop the entire job.
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                else:
                    process.kill()
                process.communicate()
                raise TimeoutError(f'MATLAB SIL {action} timed out after {timeout_sec} seconds')
            console = stdout + stderr
            returncode = process.returncode
        else:
            output = io.StringIO()
            engine.addpath(str(helper_directory), nargout=0)
            engine.motorai_sil_job(str(request_path), nargout=0, stdout=output, stderr=output)
            console, returncode = output.getvalue(), 0
        if not (directory/'result.json').is_file():
            raise RuntimeError(f'MATLAB SIL {action} did not produce a result (exit {returncode}):\n{console[-12000:]}')
        result = json.loads((directory/'result.json').read_text(encoding='utf-8-sig'))
        result.setdefault('diagnostics', {})['matlab_console'] = console[-20000:]
        if returncode or result.get('status') == 'failed':
            raise RuntimeError(result.get('diagnostics', {}).get('error_msg') or console[-12000:])
        validate_contract(result['network_config'])
        return result
