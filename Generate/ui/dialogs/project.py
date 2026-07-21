from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
    QVBoxLayout,
)
import json
import subprocess
import sys
from pathlib import Path

from core.paths import MOTORAI_ROOT
from motorai_config import (
    get_gmp_root,
    get_llm_settings,
    get_output_root,
    load_settings,
    normalize_optimize_config,
    resolve_motorai_path,
    save_settings,
)
from Competition.competition_workspace import init_candidates


def sync_optimize_project_from_settings(project_json_path: Path) -> tuple[bool, str]:
    optimize_config = normalize_optimize_config(load_settings())
    config_project = Path(optimize_config['config_project'])
    if not config_project.exists():
        return False, f'未找到 Optimize 配置脚本：{config_project}'

    result = subprocess.run(
        [sys.executable, str(config_project), str(project_json_path)],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip()
        return False, detail or f'Optimize 配置脚本退出码：{result.returncode}'
    return True, (result.stdout or '').strip()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('设置')
        self.resize(560, 220)
        self.setObjectName('SettingsDialog')

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        gmp_root_row = QWidget()
        gmp_root_layout = QHBoxLayout(gmp_root_row)
        gmp_root_layout.setContentsMargins(0, 0, 0, 0)
        gmp_root_layout.setSpacing(6)
        self.gmp_root_edit = QLineEdit()
        self.gmp_root_edit.setPlaceholderText('请选择或输入 GMP 根目录')
        self.browse_btn = QPushButton('浏览...')
        self.browse_btn.clicked.connect(self.choose_gmp_root)
        gmp_root_layout.addWidget(self.gmp_root_edit)
        gmp_root_layout.addWidget(self.browse_btn)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText('请输入 API Key')
        self.api_key_edit.setEchoMode(QLineEdit.Password)

        self.model_name_edit = QLineEdit()
        self.model_name_edit.setPlaceholderText('请输入大模型名称')

        self.model_url_edit = QLineEdit()
        self.model_url_edit.setPlaceholderText('请输入大模型网址')

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(['浅色', '深色'])

        form_layout.addRow('GMP根目录', gmp_root_row)
        form_layout.addRow('界面主题', self.theme_combo)
        form_layout.addRow('api-key', self.api_key_edit)
        form_layout.addRow('大模型名称', self.model_name_edit)
        form_layout.addRow('大模型网址', self.model_url_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.on_accept)
        buttons.rejected.connect(self.reject)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(buttons)

        self._settings_path = MOTORAI_ROOT / 'motorai_settings.json'
        self.load_settings()

    def choose_gmp_root(self):
        folder = QFileDialog.getExistingDirectory(self, '选择 GMP 根目录')
        if folder:
            self.gmp_root_edit.setText(folder)

    def on_accept(self):
        if self.save_settings():
            self.accept()

    def load_settings(self):
        try:
            settings = load_settings(self._settings_path)
            llm_data = get_llm_settings(settings)

            self.gmp_root_edit.setText(get_gmp_root(settings))

            ui_cfg = settings.get('ui') if isinstance(settings.get('ui'), dict) else {}
            theme = str(ui_cfg.get('theme', 'light')).lower()
            self.theme_combo.setCurrentIndex(0 if theme == 'light' else 1)

            self.api_key_edit.setText(llm_data.get('api_key', ''))
            self.model_name_edit.setText(llm_data.get('model', ''))
            self.model_url_edit.setText(llm_data.get('base_url', ''))
        except Exception:
            pass

    def save_settings(self):
        api_key = self.api_key_edit.text().strip()
        model_name = self.model_name_edit.text().strip()
        model_url = self.model_url_edit.text().strip()

        try:
            settings = load_settings(self._settings_path)
            paths = settings.setdefault('paths', {})
            paths['gmp_root'] = self.gmp_root_edit.text().strip()

            ui_cfg = settings.setdefault('ui', {})
            ui_cfg['theme'] = 'light' if self.theme_combo.currentIndex() == 0 else 'dark'

            llm_data = settings.setdefault('llm', {})
            llm_data['api_key'] = api_key
            llm_data['model'] = model_name
            llm_data['base_url'] = model_url
            save_settings(settings, self._settings_path)
            return True
        except Exception as exc:
            QMessageBox.warning(self, '设置保存失败', f'保存配置失败：{exc}')
            return False


class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('新建项目')
        self.resize(640, 240)
        self.setObjectName('NewProjectDialog')

        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        project_parent_row = QWidget()
        project_parent_layout = QHBoxLayout(project_parent_row)
        project_parent_layout.setContentsMargins(0, 0, 0, 0)
        project_parent_layout.setSpacing(6)
        self.project_parent_edit = QLineEdit()
        self.project_parent_edit.setPlaceholderText('请选择或输入项目保存路径')
        self.project_parent_edit.setText(str(self._get_project_parent_path()))
        self.project_parent_btn = QPushButton('浏览...')
        self.project_parent_btn.clicked.connect(self.choose_project_parent)
        project_parent_layout.addWidget(self.project_parent_edit)
        project_parent_layout.addWidget(self.project_parent_btn)

        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText('请输入项目名')

        self.max_iter_spin = QSpinBox()
        self.max_iter_spin.setRange(1, 9999)
        self.max_iter_spin.setValue(4)

        self.candidate_count_spin = QSpinBox()
        self.candidate_count_spin.setRange(1, 16)
        self.candidate_count_spin.setValue(2)

        self.max_rounds_spin = QSpinBox()
        self.max_rounds_spin.setRange(1, 50)
        self.max_rounds_spin.setValue(2)
        self.max_rounds_spin.setToolTip('多轮迭代的最大轮次上限，达到后即使未满足停止条件也会停止')

        form_layout.addRow('项目保存路径', project_parent_row)
        form_layout.addRow('项目名', self.project_name_edit)
        form_layout.addRow('单轮最大调优次数', self.max_iter_spin)
        form_layout.addRow('候选工作区数量', self.candidate_count_spin)
        form_layout.addRow('最大迭代轮数', self.max_rounds_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.on_accept)
        buttons.rejected.connect(self.reject)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(buttons)

        self.project_root = None
        self.project_json_path = None

    def _read_gmp_root(self):
        return get_gmp_root(load_settings())

    def _get_project_parent_path(self):
        if hasattr(self, 'project_parent_edit'):
            raw_path = self.project_parent_edit.text().strip()
            if raw_path:
                return resolve_motorai_path(raw_path, raw_path)
        return get_output_root(load_settings())

    def choose_project_parent(self):
        current_path = str(self._get_project_parent_path())
        folder = QFileDialog.getExistingDirectory(self, '选择项目保存路径', current_path)
        if folder:
            self.project_parent_edit.setText(folder)

    def _get_template_project_path(self):
        return MOTORAI_ROOT / 'Generate' / 'Example' / 'mcs_pmsm_nt'

    def _save_output_root(self, project_parent: Path):
        settings = load_settings()
        paths = settings.setdefault('paths', {})
        paths['output_root'] = str(project_parent.resolve())
        save_settings(settings)

    def _build_project_data(self, project_root, template_root: Path, candidate_count: int):
        return {
            'schema_version': 1,
            'workspace_mode': 'competition',
            'candidate_count': int(candidate_count),
            'max_rounds': int(self.max_rounds_spin.value()),
            'template_project_path': str(template_root),
            'gmp_path': self._read_gmp_root(),
            'paths': {
                'candidates_dir': 'candidates',
                'common_dir': 'common',
                'record_file': 'record.json',
                'competition_file': 'competition.json',
            },
            'objective_text': '',
            'task_type': '',
            'max_iterations': int(self.max_iter_spin.value()),
            'objective': '',
            'available_signals': [],
            'signals': {},
            'targets': {},
            'events': {},
            'metrics': [],
            'tuning_policy': {},
            'stop_conditions': {},
            'selected_loops': [],
        }

    def on_accept(self):
        project_name = self.project_name_edit.text().strip()

        if not project_name:
            QMessageBox.warning(self, '提示', '请先填写项目名。')
            return

        gmp_root = self._read_gmp_root()
        if not gmp_root:
            QMessageBox.warning(self, '提示', '请先在“设置”中配置 GMP 根目录。')
            return

        project_parent = self._get_project_parent_path()
        if project_parent is None:
            QMessageBox.warning(self, '提示', '无法确定项目保存路径。')
            return
        project_parent = project_parent.expanduser()

        project_root = project_parent / project_name
        if project_root.exists():
            QMessageBox.warning(self, '提示', f'项目目录已存在：{project_root}')
            return

        template_root = self._get_template_project_path()
        if template_root is None or not template_root.exists():
            QMessageBox.warning(
                self,
                '提示',
                f'模板文件夹不存在：{template_root}',
            )
            return

        try:
            project_parent.mkdir(parents=True, exist_ok=True)
            project_root.mkdir(parents=True, exist_ok=False)
            self._save_output_root(project_parent)

            candidate_count = int(self.candidate_count_spin.value())
            project_data = self._build_project_data(project_root, template_root, candidate_count)
            self.project_json_path = project_root / f'{project_name}.json'
            with open(self.project_json_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)

            self.project_root = project_root
            competition_manifest = init_candidates(
                self.project_json_path,
                candidate_count,
                force=False,
                template_root=template_root,
            )
            QMessageBox.information(
                self,
                '完成',
                (
                    f'项目已创建：{self.project_json_path}\n'
                    f'候选工作区：{competition_manifest.get("candidate_count", candidate_count)} 个\n'
                    f'候选策略文件：{project_root / "common" / "candidate_profiles.json"}'
                ),
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, '错误', f'创建项目失败：{exc}')
