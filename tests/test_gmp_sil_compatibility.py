"""Run with: python -m unittest discover -s tests -p test_gmp_sil_compatibility.py"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from Competition.candidate_network_config import save_candidate_network_config
from Optimize.agent_silhelper.sil_session import network_options, validate_contract
from Optimize.agent_silhelper.remote_sil_client import _build_payload
from Optimize.agent_optimize.agent_core.config import ProjectContext
from Optimize.agent_optimize.agent_core.tools.automation import AutomationTools


def contract():
    return {**network_options(), 'schema_version': 1, 'protocol_version': 1,
            'role': 'server', 'connection_id': 'a' * 32,
            'simulink_to_controller_bytes': 264, 'controller_to_simulink_bytes': 200}


class SILCompatibilityTests(unittest.TestCase):
    def test_rejects_legacy_and_bad_abi(self):
        for data in [network_options(), {**contract(), 'simulink_to_controller_bytes': 260},
                     {**contract(), 'connection_id': 'fake'}, {**contract(), 'protocol_version': 2}]:
            with self.assertRaises(ValueError):
                validate_contract(data)
        self.assertEqual(validate_contract(contract()), contract())
        with self.assertRaises(ValueError):
            network_options({'receive_port': 12500, 'transmit_port': 12500})
        self.assertEqual(network_options({'transport': 'tcp'})['transport'], 'tcp')
        self.assertEqual(network_options({'target_address': 'localhost'})['target_address'], '127.0.0.1')

    def test_saving_options_preserves_or_invalidates_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / 'candidate_1'
            network = candidate / 'project/simulate/network.json'
            network.parent.mkdir(parents=True)
            network.write_text(json.dumps(contract()), encoding='utf-8')
            project = root / 'project.json'
            project.write_text('{}', encoding='utf-8')
            with patch('Competition.candidate_network_config.discover_candidate_dirs', return_value=[candidate]):
                save_candidate_network_config(project, 'candidate_1', mode='local')
                self.assertEqual(json.loads(network.read_text())['connection_id'], 'a' * 32)
                save_candidate_network_config(project, 'candidate_1', mode='local', transport='tcp')
                self.assertNotIn('connection_id', json.loads(network.read_text()))

    def test_remote_uses_model_identity_and_two_ports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'network.json').write_text(json.dumps(contract()), encoding='utf-8')
            project = {'automation': {'sim_model_path': str(root / 'model.slx')}}
            payload = _build_payload(agent_project=project, agent_project_path=root / 'agent.json',
                                     backend={'remote_model_path': 'remote.slx', **network_options()}, scope_map={})
            self.assertEqual(payload['expected_connection_id'], 'a' * 32)
            self.assertEqual(set(payload['network_config']), set(network_options()))

    def test_prepare_failure_never_launches_controller(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cfg = {'automation': {'sim_model_path': str(root / 'model.slx'), 'start_exe_bat_path': 'start.bat'}}
            ctx = ProjectContext(root, root / 'agent.json', root, cfg)
            tool = AutomationTools(ctx)
            with patch.object(tool, 'prepare_simulation', return_value='Error: bad model'), \
                 patch('Optimize.agent_optimize.agent_core.tools.automation.start_bat_async') as launch:
                self.assertTrue(tool.start_exe().startswith('Error:'))
                launch.assert_not_called()
            with patch.object(tool, 'build_solution', return_value='Error: build failed'):
                self.assertTrue(tool.run_closed_loop_once().startswith('Error:'))

    def test_standalone_worker_helpers_match(self):
        for name in ['sil_session.py', 'local_sil_runner.py', 'run_local_job.py', 'motorai_sil_job.m']:
            self.assertEqual((ROOT / 'Optimize/agent_silhelper' / name).read_bytes(),
                             (ROOT / 'silworker/agent_silhelper' / name).read_bytes(), name)


if __name__ == '__main__':
    unittest.main()
