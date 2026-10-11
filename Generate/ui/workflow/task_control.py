"""Stop only a process tree launched by this UI, without blocking Qt."""
import subprocess
import json
import urllib.request
from pathlib import Path
from PyQt5.QtCore import QThread


class StopProcessWorker(QThread):
    error = ''

    def __init__(self, pid, parent=None, remote_markers=(), remote_marker_root=None):
        super().__init__(parent)
        self.pid = int(pid)
        self.remote_markers = list(remote_markers)
        self.remote_marker_root = Path(remote_marker_root) if remote_marker_root else None
        if self.pid < 0 or (not self.pid and not self.remote_markers):
            raise ValueError('Invalid task PID')

    def run(self):
        try:
            if self.pid:
                result = subprocess.run(['taskkill', '/PID', str(self.pid), '/T', '/F'],
                                        capture_output=True, timeout=20,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if result.returncode:
                    self.error = (result.stderr or result.stdout).decode(errors='replace')
            if self.remote_marker_root is not None:
                # Snapshot after killing the local callers: a job marker may
                # have been created between the click and taskkill completion.
                markers = self.remote_marker_root.glob('candidates/*/log/optimize/simulation/remote_active.json')
                self.remote_markers = list(dict.fromkeys(self.remote_markers + list(markers)))
            for marker in self.remote_markers:
                marker = Path(marker)
                if not marker.exists():
                    continue
                job = json.loads(marker.read_text(encoding='utf-8'))
                request = urllib.request.Request(job['worker_url'].rstrip('/') + '/cancel_simulation',
                    data=json.dumps({'job_id': job['job_id'], 'cancel_token': job['cancel_token']}).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}, method='POST')
                with urllib.request.urlopen(request, timeout=25) as response:
                    result = json.loads(response.read())
                if not result.get('ok'):
                    raise RuntimeError('远端任务停止未确认：' + str(result))
                marker.unlink(missing_ok=True)
        except Exception as exc:
            self.error = str(exc)
