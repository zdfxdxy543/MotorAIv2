"""History UI checks using only isolated projects and a simulated recycle bin."""
from pathlib import Path
from types import SimpleNamespace
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Generate/ui'))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtWidgets import QApplication, QMessageBox
from panels import history
from ui_main import MainWindow


class HistoryProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.storage = patch.object(history, 'HISTORY_FILE', self.root / 'history.json')
        self.storage.start()
        self.addCleanup(self.storage.stop)
        self.projects = []
        for name in ('first', 'second'):
            folder = self.root / name
            (folder / 'candidates').mkdir(parents=True)
            (folder / 'common').mkdir()
            project = folder / f'{name}.json'
            project.write_text(json.dumps({'workspace_mode': 'competition', 'project_name': name,
                'objective': f'{name} objective', 'candidate_count': 2}), encoding='utf-8')
            history.add_to_history(project)
            self.projects.append(project)
        self.panel = history.HistoryPanel()
        self.panel.refresh()
        self.panel.resize(300, 600)
        self.panel.show()
        self.app.processEvents()
        self.addCleanup(self.dispose_panel)

    def dispose_panel(self):
        self.panel.close()
        self.panel.deleteLater()
        self.app.processEvents()

    def menu_choose(self, index, label, check=None):
        def execute(menu, *args):
            actions = {action.text(): action for action in menu.actions() if not action.isSeparator()}
            self.assertEqual(set(actions), {'查看详情', '打开工程', '从历史移除', '删除工程…'})
            if check:
                check(actions)
            return actions.get(label)

        point = self.panel.project_list.visualItemRect(self.panel.project_list.item(index)).center()
        with patch.object(history.QMenu, 'exec_', execute):
            self.panel.project_list.customContextMenuRequested.emit(point)

    def test_context_menu_targets_clicked_row_and_shows_details_without_opening(self):
        opened = Mock()
        self.panel._on_project_opened = opened
        self.panel.project_list.setCurrentRow(0)
        self.menu_choose(1, '查看详情')
        self.assertEqual(self.panel.info_value_labels['objective'].text(), 'second objective')
        self.assertEqual(self.panel.project_list.currentItem().data(Qt.UserRole), str(self.projects[1]))
        opened.assert_not_called()
        self.menu_choose(1, '打开工程')
        opened.assert_called_once_with(self.projects[1])
        with patch.object(history.QMenu, 'exec_') as execute:
            self.panel._show_context_menu(QPoint(-1, -1))
            execute.assert_not_called()

    def test_remove_history_preserves_project_files_and_other_entries(self):
        self.menu_choose(0, '查看详情')
        self.menu_choose(0, '从历史移除')
        self.assertTrue(self.projects[0].exists())
        self.assertTrue(self.projects[1].exists())
        self.assertEqual([entry['path'] for entry in history.load_history()], [str(self.projects[1])])
        self.assertEqual(self.panel.project_list.count(), 1)
        self.assertTrue(self.panel.info_card.isHidden())

    def test_delete_cancel_or_recycle_failure_preserves_project_and_history(self):
        with patch.object(history.QMessageBox, 'question', return_value=QMessageBox.No), \
                patch.object(history.QFile, 'moveToTrash') as recycle:
            self.panel._delete_project(self.projects[0])
            recycle.assert_not_called()
        with patch.object(history.QMessageBox, 'question', return_value=QMessageBox.Yes), \
                patch.object(history.QFile, 'moveToTrash', return_value=(False, None)), \
                patch.object(history.QMessageBox, 'critical') as error:
            self.panel._delete_project(self.projects[0])
            error.assert_called_once()
        self.assertTrue(self.projects[0].exists())
        self.assertEqual(len(history.load_history()), 2)

    def test_delete_recycles_exact_folder_and_clears_loaded_project(self):
        calls = []
        network = Mock()
        window = SimpleNamespace(current_project_json_path=self.projects[0], action_network_config=network,
            get_current_project_json_path=lambda: window.current_project_json_path,
            _refresh_project_panels=lambda: calls.append('refresh'), _load_panel_data=lambda: calls.append('reload'))
        self.panel._on_project_deleted = lambda path: MainWindow._on_history_project_deleted(window, path)
        trash = self.root / 'recycle-bin'
        trash.mkdir()

        def recycle(raw):
            folder = Path(raw)
            destination = trash / folder.name
            self.assertEqual(folder, self.projects[0].parent.resolve())
            self.assertTrue(folder.is_relative_to(self.root.resolve()))
            self.assertTrue(destination.resolve().is_relative_to(self.root.resolve()))
            folder.rename(destination)
            return True, str(destination)

        with patch.object(history.QMessageBox, 'question', return_value=QMessageBox.Yes) as confirmation, \
                patch.object(history.QFile, 'moveToTrash', side_effect=recycle), \
                patch.object(history.QMessageBox, 'critical') as error:
            self.menu_choose(0, '删除工程…')
            error.assert_not_called()
            self.assertIn(str(self.projects[0].parent), confirmation.call_args.args[2])
        self.assertFalse(self.projects[0].parent.exists())
        self.assertTrue((trash / 'first/first.json').exists())
        self.assertTrue(self.projects[1].exists())
        self.assertEqual([entry['path'] for entry in history.load_history()], [str(self.projects[1])])
        self.assertIsNone(window.current_project_json_path)
        network.setEnabled.assert_called_once_with(False)
        self.assertEqual(calls, ['refresh', 'reload'])

    def test_running_project_cannot_be_deleted_and_other_project_is_allowed(self):
        panel = SimpleNamespace(_assistant_busy=lambda: True, _stopping=False)
        window = SimpleNamespace(get_current_project_json_path=lambda: self.projects[0],
            right_panel=lambda: SimpleNamespace(main_program_panel=panel))
        self.panel._can_delete_project = lambda path: MainWindow._can_delete_history_project(window, path)
        self.menu_choose(0, None, check=lambda actions: self.assertFalse(actions['删除工程…'].isEnabled()))
        self.assertTrue(self.panel._can_delete_project(self.projects[1]))
        with patch.object(history.QFile, 'moveToTrash') as recycle, \
                patch.object(history.QMessageBox, 'warning') as warning:
            self.panel._delete_project(self.projects[0])
            warning.assert_called_once()
            recycle.assert_not_called()

    def test_rejects_repository_root_unrecognized_json_and_linked_project(self):
        project = self.projects[0]
        with patch.object(history, 'MOTORAI_ROOT', project.parent):
            with self.assertRaises(ValueError):
                history.project_folder_for_deletion(project)
        (project.parent / '.git').mkdir()
        with self.assertRaises(ValueError):
            history.project_folder_for_deletion(project)
        with patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaises(ValueError):
                history.project_folder_for_deletion(self.projects[1])
        arbitrary = self.root / 'settings.json'
        arbitrary.write_text('{}', encoding='utf-8')
        with self.assertRaises(ValueError):
            history.project_folder_for_deletion(arbitrary)


if __name__ == '__main__':
    unittest.main()
