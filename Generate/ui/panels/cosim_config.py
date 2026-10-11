from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
    QVBoxLayout,
)

import core.paths  # keeps repository roots on sys.path
from Competition.candidate_network_config import (
    list_candidate_network_configs,
    save_candidate_network_config,
)


class CandidateNetworkPanel(QWidget):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.project_json_getter = project_json_getter
        self._rows: list[dict] = []
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("网络配置")
        title.setStyleSheet("font-size:13pt;font-weight:700;")
        layout.addWidget(title)

        hint = QLabel("读取项目后可为每个 candidate 选择本地或外地 Simulink，并写入对应 project/simulate/network.json。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.candidate_combo = QComboBox()
        self.candidate_combo.currentIndexChanged.connect(self._on_candidate_changed)
        form.addRow("Candidate", self.candidate_combo)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("本地 Simulink 模型", "local")
        self.mode_combo.addItem("外地 Simulink 模型", "remote")
        self.mode_combo.addItem("自动调度 (Scheduler)", "scheduled")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        form.addRow("模型位置", self.mode_combo)

        self.worker_url_edit = QLineEdit()
        self.worker_url_edit.setPlaceholderText("例如 http://192.168.1.23:8787")
        form.addRow("SILWorker 地址", self.worker_url_edit)

        self.scheduler_url_edit = QLineEdit()
        self.scheduler_url_edit.setPlaceholderText("例如 http://192.168.1.1:8786")
        form.addRow("Scheduler 地址", self.scheduler_url_edit)

        self.remote_model_path_edit = QLineEdit()
        self.remote_model_path_edit.setPlaceholderText("远程机器上的 .slx 路径")
        form.addRow("远程模型路径", self.remote_model_path_edit)

        self.target_address_edit = QLineEdit()
        self.target_address_edit.setPlaceholderText("例如 127.0.0.1 或主控机局域网 IP")
        form.addRow("target_address", self.target_address_edit)

        self.receive_port_spin = self._make_port_spin()
        form.addRow("receive_port", self.receive_port_spin)

        self.transmit_port_spin = self._make_port_spin()
        form.addRow("transmit_port", self.transmit_port_spin)

        self.transport_combo = QComboBox()
        self.transport_combo.addItem("UDP", "udp")
        self.transport_combo.addItem("TCP", "tcp")
        form.addRow("传输协议", self.transport_combo)

        layout.addLayout(form)

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        self.reload_btn = QPushButton("重新读取")
        self.reload_btn.clicked.connect(self.reload_for_project)
        self.save_btn = QPushButton("保存配置")
        self.save_btn.setObjectName("secondaryActionButton")
        self.save_btn.clicked.connect(self.save_current)
        button_layout.addWidget(self.reload_btn)
        button_layout.addWidget(self.save_btn)
        layout.addWidget(button_row)

        self.status_label = QLabel("请先读取项目。")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color:#666;")
        layout.addWidget(self.status_label)
        layout.addStretch()

        self.setEnabled(False)

    @staticmethod
    def _make_port_spin() -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, 65535)
        return spin

    def _project_json_path(self) -> Path | None:
        if callable(self.project_json_getter):
            path = self.project_json_getter()
            if path:
                return Path(path)
        return None

    def has_project(self) -> bool:
        project_json = self._project_json_path()
        return bool(project_json and project_json.exists())

    def reload_for_project(self):
        project_json = self._project_json_path()
        if not project_json or not project_json.exists():
            self.setEnabled(False)
            self._rows = []
            self.candidate_combo.clear()
            self.status_label.setText("请先读取项目。")
            return

        try:
            self._rows = list_candidate_network_configs(project_json)
        except Exception as exc:
            self.setEnabled(False)
            self.status_label.setText(f"读取 candidate 配置失败：{exc}")
            return

        self._loading = True
        try:
            self.candidate_combo.clear()
            for row in self._rows:
                self.candidate_combo.addItem(row["candidate_id"], row["candidate_id"])
        finally:
            self._loading = False

        self.setEnabled(bool(self._rows))
        if not self._rows:
            self.status_label.setText("当前项目没有 candidate 工作区。")
            return
        self._render_row(self._rows[0])
        self.status_label.setText(f"已读取 {len(self._rows)} 个 candidate。")

    def _on_candidate_changed(self, index: int):
        if self._loading or index < 0 or index >= len(self._rows):
            return
        self._render_row(self._rows[index])

    def _render_row(self, row: dict):
        self._loading = True
        try:
            mode = str(row.get("mode") or "local").lower()
            mode_index = self.mode_combo.findData(mode if mode in ("remote", "scheduled") else "local")
            self.mode_combo.setCurrentIndex(max(0, mode_index))
            self.worker_url_edit.setText(str(row.get("worker_url") or ""))
            self.scheduler_url_edit.setText(str(row.get("scheduler_url") or ""))
            self.remote_model_path_edit.setText(str(row.get("remote_model_path") or ""))

            network = row.get("network") if isinstance(row.get("network"), dict) else {}
            self.target_address_edit.setText(str(network.get("target_address") or "127.0.0.1"))
            self.receive_port_spin.setValue(int(network.get("receive_port") or 12500))
            self.transmit_port_spin.setValue(int(network.get("transmit_port") or 12501))
            self.transport_combo.setCurrentIndex(max(0, self.transport_combo.findData(str(network.get("transport") or "udp"))))
        finally:
            self._loading = False
        self._on_mode_changed()

    def _on_mode_changed(self, *_args):
        mode = self.mode_combo.currentData() or "local"
        remote_enabled = mode == "remote"
        scheduled_enabled = mode == "scheduled"

        self.worker_url_edit.setEnabled(remote_enabled)
        self.scheduler_url_edit.setEnabled(scheduled_enabled)

        for widget in (
            self.remote_model_path_edit,
            self.target_address_edit,
            self.receive_port_spin,
            self.transmit_port_spin,
            self.transport_combo,
        ):
            widget.setEnabled(True)

    def save_current(self):
        project_json = self._project_json_path()
        if not project_json or not project_json.exists():
            QMessageBox.warning(self, "提示", "请先读取项目。")
            return
        candidate_id = self.candidate_combo.currentData()
        if not candidate_id:
            QMessageBox.warning(self, "提示", "请选择 candidate。")
            return

        mode = self.mode_combo.currentData() or "local"
        if mode == "remote" and not self.worker_url_edit.text().strip():
            QMessageBox.warning(self, "提示", "外地 Simulink 模型需要填写 SILWorker 地址。")
            return

        try:
            result = save_candidate_network_config(
                project_json,
                str(candidate_id),
                mode=str(mode),
                worker_url=self.worker_url_edit.text().strip(),
                scheduler_url=self.scheduler_url_edit.text().strip(),
                remote_model_path=self.remote_model_path_edit.text().strip(),
                target_address=self.target_address_edit.text().strip() or "127.0.0.1",
                receive_port=int(self.receive_port_spin.value()),
                transmit_port=int(self.transmit_port_spin.value()),
                transport=str(self.transport_combo.currentData() or "udp"),
            )
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"保存失败：{exc}")
            return

        self.reload_for_project()
        self.status_label.setText(
            f"已保存 {result['candidate_id']}：{result['network_json']}"
        )
        QMessageBox.information(self, "完成", f"已写入：\n{result['network_json']}")
