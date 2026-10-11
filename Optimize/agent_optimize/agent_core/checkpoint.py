"""Match saved iterations to the requirements they actually evaluated."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


def write_result_json(result_file, result):
    """Atomically save UTF-8 JSON, tolerating short-lived Windows read locks."""
    result_file = Path(result_file).expanduser().resolve()
    payload = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    result_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                dir=result_file.parent, prefix='.' + result_file.name + '.',
                suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
        # Readers can briefly deny replacement on Windows. Keep the old file intact.
        for attempt in range(21):
            try:
                os.replace(temporary, result_file)
                return
            except PermissionError:
                if attempt == 20:
                    raise
                time.sleep(0.1)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def job_signature(job):
    keys = ('task_type', 'objective', 'objective_text', 'structured_requirement',
            'signals', 'metrics', 'targets', 'events', 'selected_loops',
            'stop_conditions', 'max_iterations', 'tuning_policy',
            '_optimization_run_id')
    payload = {key: job.get(key) for key in keys}
    payload['max_iterations'] = int(job.get('max_iterations', 1))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     default=str).encode('utf-8')).hexdigest()


def load_checkpoint(result_file, job_file, job):
    try:
        saved = json.loads(Path(result_file).read_text(encoding='utf-8-sig'))
        if (Path(saved['job_file']).resolve() == Path(job_file).resolve()
                and saved.get('job_signature') == job_signature(job)
                and isinstance(saved.get('rounds'), list)
                and int(saved.get('iterations_completed', -1)) == len(saved['rounds'])
                and 0 <= len(saved['rounds']) <= int(job.get('max_iterations', 1))):
            return saved
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {}
