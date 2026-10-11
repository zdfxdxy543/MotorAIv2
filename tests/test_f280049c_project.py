"""Candidate simulation and CCS targets use one set of control parameters."""
from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from Competition.f280049c_project import (MOTORAI_ROOT, TEMPLATE, SYSCONFIG_SCRIPT,
                                          SYSCONFIG_TOOL, copy_f280049c_project)
from Competition.competition_workspace import init_candidates
from Competition.competition_runner import ensure_candidates
from Optimize.agent_optimize.agent_core.parameters.parameter_header_editor import patch_tunable_parameters

GMP = MOTORAI_ROOT.parents[1] / 'gmp_pro'


def prepare_candidate(root):
    shutil.copytree(TEMPLATE / 'src', root / 'src')
    return copy_f280049c_project(root, gmp_root=GMP)


class F280049cProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(dir=MOTORAI_ROOT / 'Output')
        cls.candidate = Path(cls.temporary.name) / 'candidate_01'
        cls.hardware = prepare_candidate(cls.candidate)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_project_has_complete_ccs_build_inputs(self):
        root = self.hardware
        for name in ('../../src/ctl_main.c', '../../src/user_main.c', '../../src', 'xplt', 'syscfg',
                     'device_cmd/28004x_generic_flash_lnk.cmd', 'device_cmd/f28004x_headers_nonbios.cmd'):
            path = (root / name).resolve()
            self.assertTrue(path.is_relative_to(self.candidate.resolve()), name)
            self.assertTrue(path.exists(), name)
        self.assertEqual(len(list(root.rglob('*codestartbranch.asm'))), 1)
        self.assertEqual(root, self.candidate / 'project/f280049c')
        self.assertFalse((root / 'user/ctl_main.c').exists())
        self.assertFalse((root / 'build_manifest.json').exists())
        self.assertFalse((root / 'build.ps1').exists())
        self.assertEqual((root / 'xplt/xplt.peripheral.c').read_bytes(),
                         (TEMPLATE / 'project/f280049c/xplt/xplt.peripheral.c').read_bytes())
        project = ET.parse(root / '.project').getroot()
        links = [link for link in project.findall('linkedResources/link')
                 if link.findtext('locationURI').startswith('GMP_ROOT/')]
        self.assertGreater(len(links), 0)
        self.assertTrue(all(link.findtext('name').startswith('gmp_library/') for link in links))
        self.assertTrue(all((GMP / link.findtext('locationURI').removeprefix('GMP_ROOT/')).is_file()
                            for link in links))
        ccs = (root / '.cproject').read_text(encoding='utf-8')
        self.assertIn('<?fileVersion 4.0.0?>', ccs.split('<cproject', 1)[0])
        self.assertNotIn('/implement/', ccs)
        self.assertIn('COM_TI_C2000WARE_INSTALL_DIR', ccs)
        self.assertIn('COM_TI_COM_GMP_CORE_C28X_SDK__GMP_PRO_ROOT', ccs)
        self.assertIn('${PROJECT_LOC}/../../src', ccs)
        packages = json.loads((GMP / '.metadata/.tirex/package.tirex.json').read_text(encoding='utf-8-sig'))
        version = next(p['version'] for p in packages if p['id'] == 'GMP-Core-C28x')
        self.assertIn(f'PRODUCTS=GMP-Core-C28x:{version};C2000WARE:5.4.0.00;', ccs)
        self.assertEqual(project.findtext('linkedResources/link/locationURI'),
                         'PARENT-2-PROJECT_LOC/src/ctl_main.c')
        self.assertFalse((root / 'gmp_src_mgr/gmp_inc').exists())
        self.assertFalse((root / 'gmp_src_mgr/gmp_src').exists())
        self.assertFalse((root / 'driverlib').exists())
        for configuration in ET.fromstring(ccs).findall('.//configuration'):
            self.assertIsNotNone(configuration.find('sourceEntries'))
            self.assertTrue(any(v.get('value') == '_FLASH' for v in configuration.findall('.//listOptionValue')))
            tool = configuration.find(f'.//tool[@superClass="{SYSCONFIG_TOOL}"]')
            self.assertIsNotNone(tool)
            self.assertEqual(tool.find(f'option[@superClass="{SYSCONFIG_TOOL}.INPUT_SCRIPT"]').get('value'),
                             '${PROJECT_LOC}/' + SYSCONFIG_SCRIPT)
            self.assertEqual(tool.find(f'option[@superClass="{SYSCONFIG_TOOL}.PRODUCTS"]/listOptionValue').get('value'),
                             '${COM_TI_C2000WARE_INSTALL_DIR}/.metadata/sdk.json')
            self.assertEqual(tool.find(f'option[@superClass="{SYSCONFIG_TOOL}.DEVICE"]').get('value'),
                             'TMS320F280049C')
            excluded = configuration.find('sourceEntries/entry').get('excluding').split('|')
            self.assertNotIn(SYSCONFIG_SCRIPT, excluded)
            self.assertIn('syscfg', excluded)
            self.assertTrue(any(v.get('value') == '${PROJECT_LOC}/${ConfigName}/syscfg'
                                for v in configuration.findall('.//listOptionValue')))
        script = (root / SYSCONFIG_SCRIPT).read_text(encoding='utf-8')
        self.assertNotIn('gmp_pro@1.00.00.05', script)
        self.assertIn('useStandardCodeStartBranch = false', script)

    def test_copy_is_independent_and_preserves_existing_hardware_edits(self):
        with tempfile.TemporaryDirectory(dir=MOTORAI_ROOT / 'Output') as temporary:
            project = Path(temporary) / '独立工程 with spaces'
            hardware = prepare_candidate(project)
            self.assertEqual(hardware, project / 'project/f280049c')
            self.assertFalse((hardware / 'build').exists())
            self.assertNotEqual(ET.parse(hardware / '.project').findtext('name'),
                                ET.parse(self.hardware / '.project').findtext('name'))
            source = hardware / 'xplt/xplt.peripheral.c'
            source.write_text('/* user hardware edits */', encoding='utf-8')
            self.assertEqual(copy_f280049c_project(project), hardware)
            self.assertEqual(source.read_text(), '/* user hardware edits */')
            self.assertNotEqual(source.read_bytes(),
                                (TEMPLATE / 'project/f280049c/xplt/xplt.peripheral.c').read_bytes())
            with self.assertRaises(FileNotFoundError):
                copy_f280049c_project(Path(temporary) / 'missing', Path(temporary) / 'no_template')

    def test_existing_unrelated_folder_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(dir=MOTORAI_ROOT / 'Output') as temporary:
            project = Path(temporary)
            hardware = project / 'project/f280049c'
            hardware.mkdir(parents=True)
            note = hardware / 'note.txt'
            note.write_text('keep', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                copy_f280049c_project(project)
            self.assertEqual(note.read_text(), 'keep')

    def test_copy_recovers_from_a_transient_windows_directory_lock(self):
        with tempfile.TemporaryDirectory(dir=MOTORAI_ROOT / 'Output') as temporary:
            original = Path.rename
            attempts = []
            def rename(source, destination):
                attempts.append(source)
                if len(attempts) == 1:
                    raise PermissionError('Windows directory temporarily in use')
                return original(source, destination)
            with patch.object(Path, 'rename', rename):
                hardware = prepare_candidate(Path(temporary) / 'candidate_01')
            self.assertEqual(len(attempts), 2)
            self.assertTrue((hardware / '.cproject').is_file())

    def test_existing_metadata_repair_preserves_control_sources_and_ccs_settings(self):
        with tempfile.TemporaryDirectory(dir=MOTORAI_ROOT / 'Output') as temporary:
            candidate = Path(temporary) / 'candidate_01'
            hardware = prepare_candidate(candidate)
            metadata = hardware / '.cproject'
            original = metadata.read_bytes()
            metadata.write_bytes(original.replace(b'\n<?fileVersion 4.0.0?>', b'', 1))
            before = {path: path.read_bytes() for path in
                      (candidate / 'src/ctl_main.c', hardware / 'xplt/ctrl_settings.h',
                       hardware / '.project', hardware / '.ccsproject')}
            self.assertEqual(copy_f280049c_project(candidate), hardware)
            self.assertEqual(metadata.read_bytes(), original)
            modified = metadata.stat().st_mtime_ns
            copy_f280049c_project(candidate)
            self.assertEqual(metadata.stat().st_mtime_ns, modified)
            for path, data in before.items():
                self.assertEqual(path.read_bytes(), data)

    def test_legacy_sysconfig_repair_preserves_manual_settings_and_frozen_build(self):
        with tempfile.TemporaryDirectory(dir=MOTORAI_ROOT / 'Output') as temporary:
            candidate = Path(temporary) / 'candidate_01'
            hardware = prepare_candidate(candidate)
            metadata = hardware / '.cproject'
            tree = ET.parse(metadata)
            for configuration in tree.findall('.//configuration'):
                chain = configuration.find('folderInfo/toolChain')
                chain.remove(chain.find(f'tool[@superClass="{SYSCONFIG_TOOL}"]'))
                if configuration.get('name') == 'Release':
                    tool = ET.SubElement(chain, 'tool', id=SYSCONFIG_TOOL + '.Release',
                                         name='SysConfig', superClass=SYSCONFIG_TOOL)
                    option = ET.SubElement(tool, 'option', id=SYSCONFIG_TOOL + '.OTHER_FLAGS.Release',
                                           superClass=SYSCONFIG_TOOL + '.OTHER_FLAGS', valueType='stringList')
                    ET.SubElement(option, 'listOptionValue', builtIn='false', value='--treatWarningsAsErrors')
                compiler = next(t for t in chain.findall('tool') if '.compiler' in t.get('superClass', ''))
                option = compiler.find('option[@valueType="includePath"]')
                for child in list(option):
                    if child.get('value') == '${PROJECT_LOC}/${ConfigName}/syscfg':
                        option.remove(child)
                ET.SubElement(option, 'listOptionValue', builtIn='false', value='${PROJECT_LOC}/custom_headers')
                entry = configuration.find('sourceEntries/entry')
                entry.set('excluding', SYSCONFIG_SCRIPT + '|build|Debug|Release|manual_excluded.c')
            tree.write(metadata, encoding='UTF-8', xml_declaration=True)
            script = hardware / SYSCONFIG_SCRIPT
            script_before = script.read_bytes() + b'\n// manual peripheral edits\n'
            script.write_bytes(script_before.replace(b' --product "C2000WARE@',
                b' --product "gmp_pro@1.00.00.05" --product "C2000WARE@'))
            preserved = {p: p.read_bytes() for p in
                         (candidate / 'src/ctl_main.c', candidate / 'src/paras.generated.h',
                          hardware / 'syscfg/board.c', hardware / 'xplt/xplt.peripheral.c',
                          hardware / '.project', hardware / '.ccsproject') if p.is_file()}
            copy_f280049c_project(candidate)
            self.assertEqual(script.read_bytes(), script_before)
            for configuration in ET.parse(metadata).findall('.//configuration'):
                tool = configuration.find(f'.//tool[@superClass="{SYSCONFIG_TOOL}"]')
                self.assertIsNotNone(tool)
                self.assertEqual(tool.find(f'option[@superClass="{SYSCONFIG_TOOL}.INPUT_SCRIPT"]').get('value'),
                                 '${PROJECT_LOC}/' + SYSCONFIG_SCRIPT)
                if configuration.get('name') == 'Release':
                    self.assertEqual(tool.find(f'option[@superClass="{SYSCONFIG_TOOL}.OTHER_FLAGS"]/listOptionValue').get('value'),
                                     '--treatWarningsAsErrors')
                self.assertEqual(configuration.find('sourceEntries/entry').get('excluding'),
                                 SYSCONFIG_SCRIPT + '|build|Debug|Release|manual_excluded.c')
                self.assertTrue(any(v.get('value') == '${PROJECT_LOC}/custom_headers'
                                    for v in configuration.findall('.//listOptionValue')))
            for path, content in preserved.items():
                self.assertEqual(path.read_bytes(), content)
            timestamps = [p.stat().st_mtime_ns for p in (metadata, script)]
            copy_f280049c_project(candidate)
            self.assertEqual([p.stat().st_mtime_ns for p in (metadata, script)], timestamps)

    def test_iterations_use_shared_parameters_without_overwriting_board_settings(self):
        with tempfile.TemporaryDirectory(dir=MOTORAI_ROOT / 'Output') as temporary:
            candidate = Path(temporary) / 'candidate_01'
            hardware = prepare_candidate(candidate)
            header = candidate / 'src/paras.generated.h'
            header.write_text('// Start Paras Define\n#define CUR_KP 1.0f\n// End Paras Define\n', encoding='utf-8')
            settings = hardware / 'xplt/ctrl_settings.h'
            board_before = settings.read_bytes()
            for gain in (2.0, 3.0):
                patch_tunable_parameters(header, {'CUR_KP': gain}, backup=False)
                include = hardware / '../../src/paras.generated.h'
                self.assertEqual(include.resolve(), header.resolve())
                self.assertIn(f'#define CUR_KP {gain}', include.read_text())
                self.assertEqual(copy_f280049c_project(candidate), hardware)
                self.assertEqual(settings.read_bytes(), board_before)
            self.assertFalse((hardware / 'paras.generated.h').exists())

    def test_new_and_existing_workspaces_have_one_hardware_target_per_candidate(self):
        with tempfile.TemporaryDirectory(dir=MOTORAI_ROOT / 'Output') as temporary:
            root = Path(temporary)
            project = root / 'project.json'
            project.write_text(json.dumps({'gmp_path': str(GMP),
                'template_project_path': str(TEMPLATE), 'max_iterations': 1}), encoding='utf-8')
            manifest = init_candidates(project, 2)
            self.assertNotIn('hardware_project', manifest)
            self.assertFalse((root / 'F280049c').exists())
            for candidate in manifest['candidates']:
                hardware = Path(candidate['f280049c'])
                self.assertEqual(hardware.parent, Path(candidate['simulate']).parent)
                self.assertTrue((hardware / '.project').is_file())
            old = root / 'candidates/candidate_02'
            hardware = old / 'project/f280049c'
            hardware.rename(old / 'saved_hardware')
            parameters = old / 'src/paras.generated.h'
            parameters.write_text('/* existing tuned parameters */', encoding='utf-8')
            ensure_candidates(project, 2, force_init=False)
            self.assertTrue((hardware / '.project').is_file())
            self.assertEqual(parameters.read_text(), '/* existing tuned parameters */')


if __name__ == '__main__':
    unittest.main()
