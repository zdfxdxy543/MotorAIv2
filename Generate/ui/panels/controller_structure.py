from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen, QPolygonF
import json
from pathlib import Path

from styles.theme import current_theme


class ControllerStructureCanvas(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.setFrameShape(QFrame.NoFrame)
        self.setObjectName('CurveCanvas')
        self.setObjectName('ControllerStructureCanvas')
        t = current_theme()
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f'QFrame#ControllerStructureCanvas{{background:{t.panel};border:none;}}')
        self._model = {
            'items': [],
            'mech_props': [],
            'source': '',
        }

    def set_model(self, model: dict):
        self._model = model or {'items': [], 'mech_props': [], 'source': ''}
        self.update()

    @staticmethod
    def _arrow_head(end_x, end_y, direction='down'):
        size = 16
        if direction == 'down':
            return [QPointF(end_x, end_y), QPointF(end_x - size, end_y - size * 1.4), QPointF(end_x + size, end_y - size * 1.4)]
        return [QPointF(end_x, end_y), QPointF(end_x - size * 1.4, end_y - size), QPointF(end_x - size * 1.4, end_y + size)]

    def _draw_arrow(self, painter: QPainter, start: QPointF, end: QPointF):
        t = current_theme()
        painter.setPen(QPen(QColor(t.canvas_arrow), 3.2))
        painter.drawLine(start, end)
        if end.y() >= start.y():
            head = self._arrow_head(end.x(), end.y(), 'down')
        else:
            head = self._arrow_head(end.x(), end.y(), 'right')
        painter.setBrush(QColor(t.canvas_arrow))
        painter.drawPolygon(QPolygonF(head))

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        t = current_theme()

        rect = self.rect().adjusted(20, 20, -20, -20)
        painter.fillRect(rect, QColor(t.panel))

        painter.setPen(QColor(t.canvas_title))
        painter.drawText(QRectF(rect.left(), rect.top(), rect.width(), 36), Qt.AlignCenter, '控制器结构框图')

        items = self._model.get('items') or []
        if not items:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            ps = t.canvas_placeholder_start
            pe = t.canvas_placeholder_end
            gradient.setColorAt(0, QColor(*ps))
            gradient.setColorAt(1, QColor(*pe))
            painter.fillRect(rect, gradient)

            painter.setPen(QPen(QColor(t.muted), 1))
            painter.drawRect(rect)

            painter.setPen(QPen(QColor(t.muted), 2, Qt.DashLine))
            painter.drawLine(rect.topLeft(), rect.bottomRight())
            painter.drawLine(rect.topRight(), rect.bottomLeft())

            painter.setPen(QColor(t.muted))
            painter.drawText(rect, Qt.AlignCenter, '暂无控制器结构\n请先在”主程序生成”中生成并保存 loop-ids 结果')
            return

        box_w = 352
        box_h = 104
        gap = 52
        
        label_font_size = int(painter.font().pointSize() * 1.5)
        prop_font_size = int(painter.font().pointSize() * 0.8)
        
        max_prop_width = 0
        for item in items:
            props = item.get('properties') or []
            display_props = '，'.join(props) if props else '-'
            prop_text = f'属性参数：{display_props}'
            prop_font = QFont(painter.font().family(), prop_font_size)
            fm = QFontMetrics(prop_font)
            max_prop_width = max(max_prop_width, fm.width(prop_text))
        
        text_padding = 28
        total_width = box_w + text_padding + max_prop_width + 40
        total_height = 84 + box_h + (gap + 8 if next((item for item in items if item['kind'] == 'current_loop'), None) else 0) + len([item for item in items if item['kind'] in {'speed_loop', 'position_loop'}]) * (box_h + gap)
        
        start_x = rect.left() + (rect.width() - total_width) / 2
        start_y = rect.top() + (rect.height() - total_height) / 2
        
        if start_x < rect.left():
            start_x = rect.left()
        if start_y < rect.top():
            start_y = rect.top()

        x = start_x + 20
        y = start_y + 42

        # Build layout positions.
        positions = []
        current_item = next((item for item in items if item['kind'] == 'current_loop'), None)
        inner_items = [item for item in items if item['kind'] in {'speed_loop', 'position_loop'}]

        box_pen_colors = {
            'current_loop': QColor('#0f62fe'),
            'speed_loop': QColor('#0f7b3a'),
            'position_loop': QColor('#a05a00'),
        }
        fill_colors = {
            'current_loop': QColor('#eef4ff'),
            'speed_loop': QColor('#effaf3'),
            'position_loop': QColor('#fff4e6'),
        }

        if current_item:
            positions.append((current_item, QRectF(x, y, box_w, box_h)))
            y += box_h + gap + 16

        for inner in inner_items:
            positions.append((inner, QRectF(x, y, box_w, box_h)))
            y += box_h + gap

        # draw arrows between consecutive visible nodes
        for idx in range(len(positions) - 1):
            _, prev_rect = positions[idx]
            _, next_rect = positions[idx + 1]
            start = QPointF(prev_rect.center().x(), prev_rect.bottom())
            end = QPointF(next_rect.center().x(), next_rect.top())
            self._draw_arrow(painter, start, end)

        # mechanical wrapper around speed/position nodes
        if inner_items:
            first_rect = positions[1 if current_item else 0][1]
            last_rect = positions[-1][1]
            wrapper = QRectF(
                first_rect.left() - 20,
                first_rect.top() - 28,
                first_rect.width() + 40,
                (last_rect.bottom() - first_rect.top()) + 56,
            )
            painter.setPen(QPen(QColor(t.muted), 3.2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(wrapper, 20, 20)
            painter.setPen(QColor(t.subtle))
            mech_props = self._model.get('mech_props') or []
            mech_text = '机械环'
            if mech_props:
                mech_text += f"  ({', '.join(mech_props)})"
            painter.drawText(QRectF(wrapper.left() + 16, wrapper.top() - 24, wrapper.width() - 32, 32), Qt.AlignLeft | Qt.AlignVCenter, mech_text)

        # draw node boxes and property labels
        for item, box in positions:
            kind = item['kind']
            label = item['label']
            props = item.get('properties') or []
            display_props = '，'.join(props) if props else '-'

            painter.setPen(QPen(box_pen_colors.get(kind, QColor('#4d4d4d')), 3.6))
            painter.setBrush(fill_colors.get(kind, QColor('#f2f2f2')))
            painter.drawRoundedRect(box, 16, 16)
            
            label_font = QFont(painter.font().family(), int(painter.font().pointSize() * 1.5))
            painter.setFont(label_font)
            painter.setPen(QColor(t.text_strong))
            painter.drawText(box.adjusted(20, 0, -20, 0), Qt.AlignCenter, label)

            prop_font = QFont(painter.font().family(), int(painter.font().pointSize() * 0.8))
            painter.setFont(prop_font)
            painter.setPen(QColor(t.muted))
            text_x = box.right() + 28
            prop_rect = QRectF(text_x, box.top() + 20, rect.right() - text_x, box.height() - 40)
            painter.drawText(prop_rect, Qt.AlignLeft | Qt.AlignVCenter, f'属性参数：{display_props}')


class ControllerStructurePanel(QWidget):
    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self.project_json_getter = project_json_getter
        t = current_theme()
        self.setObjectName('controllerStructurePanel')
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f'QWidget#controllerStructurePanel{{background:{t.panel};border:none;}}')
        self.canvas = ControllerStructureCanvas()
        self.source_label = QLabel('来源：未加载项目')
        self.source_label.setStyleSheet(f'color:{t.subtle};background:{t.panel};border:none;')
        self.source_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_row = QWidget()
        title_row.setAttribute(Qt.WA_StyledBackground, True)
        title_row.setStyleSheet(f'background:{t.panel};border:none;')
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(QLabel('控制器结构'))
        title_layout.addStretch()
        refresh_btn = QPushButton('刷新框图')
        refresh_btn.clicked.connect(self.refresh_from_project)
        title_layout.addWidget(refresh_btn)

        layout.addWidget(title_row)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.source_label)
        self.refresh_from_project()

    def _project_json_path(self):
        if callable(self.project_json_getter):
            return self.project_json_getter()
        return None

    def _load_payload(self):
        project_json = self._project_json_path()
        if not project_json:
            return None, None

        candidates = [project_json]
        candidates.append(project_json.parent / 'candidates' / 'candidate_01' / 'log' / 'generate' / 'controller_loop_ids_generated.json')
        candidates.append(project_json.parent / 'controller_loop_ids_generated.json')

        for path in candidates:
            try:
                if not path.exists():
                    continue
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    selected = data.get('selected_loops') or data.get('structured_requirement', {}).get('selected_loops')
                    if isinstance(selected, list) and selected:
                        return data, path
            except Exception:
                continue
        return None, None

    @staticmethod
    def _loop_label(kind: str) -> str:
        return {
            'current_loop': '电流环',
            'speed_loop': '速度环',
            'position_loop': '位置环',
        }.get(kind, kind)

    def _build_model(self, payload: dict | None):
        if not payload:
            return {'items': [], 'mech_props': [], 'source': ''}

        loops = payload.get('selected_loops') or payload.get('structured_requirement', {}).get('selected_loops') or []
        by_name = {str(loop.get('name') or '').strip().lower(): loop for loop in loops if isinstance(loop, dict)}

        mech_loop = by_name.get('mech_loop')
        mech_props = list(mech_loop.get('properties') or []) if mech_loop else []
        mech_target = mech_props[0] if mech_props else ''

        items = []
        current = by_name.get('current_loop')
        if current:
            items.append({
                'kind': 'current_loop',
                'label': self._loop_label('current_loop'),
                'properties': current.get('properties') or [],
            })

        speed = by_name.get('speed_loop')
        position = by_name.get('position_loop')

        if not speed and mech_target == 'speed':
            speed = {'properties': mech_props}
        if not position and mech_target == 'position':
            position = {'properties': mech_props}

        if speed:
            items.append({
                'kind': 'speed_loop',
                'label': self._loop_label('speed_loop'),
                'properties': speed.get('properties') or [],
            })
        if position:
            items.append({
                'kind': 'position_loop',
                'label': self._loop_label('position_loop'),
                'properties': position.get('properties') or [],
            })

        return {
            'items': items,
            'mech_props': mech_props,
            'source': payload.get('_source_path', ''),
        }

    def refresh_from_project(self):
        payload, source_path = self._load_payload()
        if payload and source_path:
            payload = dict(payload)
            payload['_source_path'] = str(source_path)
        model = self._build_model(payload)
        self.canvas.set_model(model)
        if source_path:
            self.source_label.setText(f'来源：{source_path}')
        else:
            self.source_label.setText('来源：未找到 controller_loop_ids_generated.json 或当前项目 JSON 中的 selected_loops')
