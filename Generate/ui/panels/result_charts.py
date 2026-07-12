"""
result_charts.py — 仿真结束后在右侧面板展示的可视化图表。

四张图：
  1. 速度响应波形 — 各 candidate 的 rotor_speed_rad_s 时域曲线
  2. 评分对比柱状图 — scoreboard 排名
  3. 参数调优变化量 — winner 各参数 delta_pct
  4. 转角位置波形 — 各 candidate 的 rotor_angle_rad 时域曲线

数据来源：rounds/round_NN/round_feedback.json + simulation/processed.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PyQt5.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PyQt5.QtCore import Qt

import core.paths  # noqa: F401 — ensures repository roots are on sys.path

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from styles.fonts import configure_matplotlib_fonts
from styles.theme import current_theme

# ── 中文字体配置 ──────────────────────────────────────────────────────
configure_matplotlib_fonts(matplotlib)

# ── 候选方案配色 ──────────────────────────────────────────────────────
CANDIDATE_COLORS: dict[str, str] = {
    "candidate_01": "#5470c6",
    "candidate_02": "#91cc75",
    "candidate_03": "#fac858",
    "candidate_04": "#ee6666",
    "candidate_05": "#73c0de",
    "candidate_06": "#3ba272",
    "candidate_07": "#fc8452",
    "candidate_08": "#9a60b4",
}


def _candidate_color(cid: str) -> str:
    if cid in CANDIDATE_COLORS:
        return CANDIDATE_COLORS[cid]
    keys = list(CANDIDATE_COLORS.keys())
    import re
    m = re.search(r"(\d+)", cid)
    idx = (int(m.group(1)) - 1) if m else (hash(cid) % len(keys))
    return CANDIDATE_COLORS[keys[idx % len(keys)]]


# ══════════════════════════════════════════════════════════════════════
# 单图 Canvas 基类
# ══════════════════════════════════════════════════════════════════════

class _BaseChart(FigureCanvas):
    """matplotlib FigureCanvas 封装，统一尺寸和主题适配。"""

    def __init__(self, parent=None, figsize=(6, 3)):
        self._fig = Figure(figsize=figsize, dpi=100, tight_layout=True)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(160)
        self._apply_theme()

    def _apply_theme(self):
        t = current_theme()
        bg = getattr(t, "surface", "#ffffff")
        fg = getattr(t, "text", "#1e293b")
        grid_c = getattr(t, "border_light", "#e2e8f0")
        self._fig.patch.set_facecolor(bg)
        for ax in self._fig.axes:
            ax.set_facecolor(bg)
            ax.tick_params(colors=fg)
            ax.xaxis.label.set_color(fg)
            ax.yaxis.label.set_color(fg)
            ax.title.set_color(fg)
            for spine in ax.spines.values():
                spine.set_color(grid_c)

    @property
    def fig(self):
        return self._fig

    @property
    def ax(self):
        if not self._fig.axes:
            self._fig.add_subplot(111)
        return self._fig.axes[0]

    def clear(self):
        self._fig.clf()
        self.draw_idle()

    def show_empty(self, message: str = "暂无数据"):
        self.clear()
        self.ax.text(
            0.5, 0.5, message,
            transform=self.ax.transAxes,
            ha="center", va="center",
            fontsize=14, color="#94a3b8",
        )
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.draw_idle()


# ══════════════════════════════════════════════════════════════════════
# 图 1：速度响应波形
# ══════════════════════════════════════════════════════════════════════

class SpeedWaveformChart(_BaseChart):
    def plot(self, candidates_data: list[dict[str, Any]], target_value: float | None):
        self.clear()
        ax = self.ax
        t = current_theme()

        for cd in candidates_data:
            time = cd.get("time", [])
            values = cd.get("values", [])
            cid = cd.get("candidate_id", "?")
            if not time or not values:
                continue
            color = _candidate_color(cid)
            ax.plot(time, values, linewidth=1.4, color=color, label=cid, alpha=0.88)

        if target_value is not None:
            ax.axhline(
                y=target_value, color="#ef4444", linestyle="--",
                linewidth=1.2, alpha=0.7, label=f"目标 {target_value:.1f} rad/s"
            )

        ax.set_xlabel("时间 (s)", color=t.text)
        ax.set_ylabel("转速 (rad/s)", color=t.text)
        ax.set_title("速度响应波形", fontsize=13, fontweight="bold", color=t.text)
        ax.legend(loc="lower right", fontsize=8, framealpha=0.6)
        ax.grid(True, alpha=0.25, color=t.border)
        self._apply_theme()
        self.draw_idle()


# ══════════════════════════════════════════════════════════════════════
# 图 2：评分对比柱状图
# ══════════════════════════════════════════════════════════════════════

class ScoreBarChart(_BaseChart):
    def plot(self, scoreboard: list[dict[str, Any]], winner_id: str = ""):
        self.clear()
        ax = self.ax
        t = current_theme()

        if not scoreboard:
            self.show_empty("暂无评分数据")
            return

        # 按分数升序排列（横条图从下往上）
        sorted_sb = sorted(scoreboard, key=lambda x: x.get("overall_score", 0) or 0)
        labels = [s.get("candidate_id", "?") for s in sorted_sb]
        scores = [s.get("overall_score") or 0 for s in sorted_sb]
        colors = [_candidate_color(l) for l in labels]
        edge_colors = [
            "#f59e0b" if l == winner_id else "none" for l in labels
        ]
        edge_widths = [3 if l == winner_id else 0 for l in labels]

        bars = ax.barh(labels, scores, color=colors, edgecolor=edge_colors,
                       linewidth=edge_widths, height=0.55, alpha=0.88)

        for bar, score in zip(bars, scores):
            ax.text(
                bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{score:.2f}", va="center", fontsize=9, color=t.text,
            )

        if winner_id:
            ax.set_title(f"评分对比  ★ {winner_id}", fontsize=13, fontweight="bold", color=t.text)
        else:
            ax.set_title("评分对比", fontsize=13, fontweight="bold", color=t.text)

        ax.set_xlabel("Overall Score", color=t.text)
        ax.grid(True, axis="x", alpha=0.25, color=t.border)
        ax.set_xlim(0, max(scores) * 1.15 if max(scores) > 0 else 100)
        self._apply_theme()
        self.draw_idle()


# ══════════════════════════════════════════════════════════════════════
# 图 3：参数调优变化量
# ══════════════════════════════════════════════════════════════════════

class ParamDeltaChart(_BaseChart):
    def plot(self, final_parameters: list[dict[str, Any]], candidate_id: str = ""):
        self.clear()
        ax = self.ax
        t = current_theme()

        if not final_parameters:
            self.show_empty("暂无参数数据")
            return

        # 过滤：只显示有变化的参数，按 delta_pct 排序
        params_with_delta = [
            p for p in final_parameters
            if p.get("delta_pct") is not None and abs(p["delta_pct"]) > 0.05
        ]
        if not params_with_delta:
            self.show_empty("参数无显著变化")
            return

        params_with_delta.sort(key=lambda x: x.get("delta_pct", 0) or 0)
        labels = [_param_short(p["name"]) for p in params_with_delta]
        deltas = [p.get("delta_pct") or 0 for p in params_with_delta]
        bar_colors = [
            "#ef4444" if d >= 0 else "#3b82f6" for d in deltas
        ]

        bars = ax.barh(labels, deltas, color=bar_colors, height=0.55, alpha=0.82)

        for bar, d in zip(bars, deltas):
            x_pos = bar.get_width()
            offset = 1.0 if x_pos >= 0 else -1.0
            ha = "left" if x_pos >= 0 else "right"
            ax.text(
                x_pos + offset, bar.get_y() + bar.get_height() / 2,
                f"{d:+.1f}%", va="center", ha=ha, fontsize=8, color=t.text,
            )

        title = f"参数调优变化量  —  {candidate_id}" if candidate_id else "参数调优变化量"
        ax.set_title(title, fontsize=13, fontweight="bold", color=t.text)
        ax.axvline(x=0, color=t.border_strong, linewidth=1.0, alpha=0.6)
        ax.set_xlabel("变化 (%)", color=t.text)
        ax.grid(True, axis="x", alpha=0.25, color=t.border)
        self._apply_theme()
        self.draw_idle()


# ══════════════════════════════════════════════════════════════════════
# 图 4：转角位置波形
# ══════════════════════════════════════════════════════════════════════

class AngleWaveformChart(_BaseChart):
    def plot(self, candidates_data: list[dict[str, Any]]):
        self.clear()
        ax = self.ax
        t = current_theme()

        for cd in candidates_data:
            time = cd.get("time", [])
            values = cd.get("values", [])
            cid = cd.get("candidate_id", "?")
            if not time or not values:
                continue
            color = _candidate_color(cid)
            ax.plot(time, values, linewidth=1.4, color=color, label=cid, alpha=0.88)

        ax.set_xlabel("时间 (s)", color=t.text)
        ax.set_ylabel("转角 (rad)", color=t.text)
        ax.set_title("电机转角位置", fontsize=13, fontweight="bold", color=t.text)
        ax.legend(loc="lower right", fontsize=8, framealpha=0.6)
        ax.grid(True, alpha=0.25, color=t.border)
        self._apply_theme()
        self.draw_idle()


# ══════════════════════════════════════════════════════════════════════
# 组合面板
# ══════════════════════════════════════════════════════════════════════

def _param_short(name: str) -> str:
    """去掉 MOTORAI_ / MOTOR_ 前缀。"""
    for prefix in ("MOTORAI_", "MOTOR_"):
        if name.upper().startswith(prefix):
            return name[len(prefix):]
    return name


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _latest_round(project_root: Path) -> int:
    """找到已完成的最大轮次编号。"""
    rounds_dir = project_root / "rounds"
    if not rounds_dir.is_dir():
        return 0
    best = 0
    for d in rounds_dir.glob("round_*"):
        if d.is_dir():
            try:
                best = max(best, int(d.name.replace("round_", "")))
            except ValueError:
                pass
    return best


def _all_rounds(project_root: Path) -> list[int]:
    """返回所有可用轮次编号（升序）。"""
    rounds_dir = project_root / "rounds"
    if not rounds_dir.is_dir():
        return []
    result: list[int] = []
    for d in rounds_dir.glob("round_*"):
        if d.is_dir():
            try:
                result.append(int(d.name.replace("round_", "")))
            except ValueError:
                pass
    return sorted(result)


def _latest_round(project_root: Path) -> int:
    """找到已完成的最大轮次编号。"""
    all_r = _all_rounds(project_root)
    return all_r[-1] if all_r else 0


def _find_processed_json(project_root: Path, candidate_id: str, round_number: int | None = None) -> Path | None:
    """为指定 candidate 查找 simulation/processed.json。

    当 round_number 为 None 或等于 latest 时，使用 candidates/ 当前数据；
    否则从 rounds/round_NN/ 备份中读取。
    """
    latest = _latest_round(project_root)
    if round_number is None or round_number == latest:
        # 最新一轮：用 candidates/ 当前数据
        direct = project_root / "candidates" / candidate_id / "log" / "optimize" / "simulation" / "processed.json"
        if direct.exists():
            return direct
    # 指定历史轮次或 candidates/ 不存在：走 rounds 备份
    if round_number is not None and round_number != latest:
        proc = project_root / "rounds" / f"round_{round_number:02d}" / "candidates" / candidate_id / "log" / "optimize" / "simulation" / "processed.json"
        if proc.exists():
            return proc
    # 兜底：逐轮回退
    rounds_dir = project_root / "rounds"
    if rounds_dir.is_dir():
        for rd in sorted(rounds_dir.glob("round_*"), reverse=True):
            proc = rd / "candidates" / candidate_id / "log" / "optimize" / "simulation" / "processed.json"
            if proc.exists():
                return proc
    return None


def _load_speed_signals(project_root: Path, candidate_dirs: list[Path], round_number: int | None = None) -> list[dict[str, Any]]:
    """提取各 candidate 的转子速度波形。"""
    result: list[dict[str, Any]] = []
    for cdir in candidate_dirs:
        proc = _find_processed_json(project_root, cdir.name, round_number)
        if proc is None:
            continue
        data = _read_json(proc)
        sig = data.get("signals", {}).get("rotor_speed_rad_s", {})
        if sig:
            result.append({
                "candidate_id": cdir.name,
                "time": sig.get("time", []),
                "values": sig.get("values", []),
            })
    return result


def _load_angle_signals(project_root: Path, candidate_dirs: list[Path], round_number: int | None = None) -> list[dict[str, Any]]:
    """提取各 candidate 的转角波形。"""
    result: list[dict[str, Any]] = []
    for cdir in candidate_dirs:
        proc = _find_processed_json(project_root, cdir.name, round_number)
        if proc is None:
            continue
        data = _read_json(proc)
        sig = data.get("signals", {}).get("rotor_angle_rad", {})
        if sig:
            result.append({
                "candidate_id": cdir.name,
                "time": sig.get("time", []),
                "values": sig.get("values", []),
            })
    return result


def _extract_target_speed(project_json: Path) -> float | None:
    """从 user_requirement.json 或 candidate.json 的 targets/metrics 中提取目标转速(rad/s)。"""
    # 先试 user_requirement.json
    common_req = project_json.parent / "common" / "user_requirement.json"
    req = _read_json(common_req)

    def _find_in(obj: dict[str, Any]) -> float | None:
        # targets section
        targets = obj.get("targets")
        if isinstance(targets, dict):
            for spec in targets.values():
                if isinstance(spec, dict):
                    tv = spec.get("target_value")
                    if isinstance(tv, (int, float)) and tv > 0:
                        return float(tv)
        # metrics section — 找第一个 speed 相关指标的 target_value
        metrics = obj.get("metrics")
        if isinstance(metrics, list):
            for m in metrics:
                if not isinstance(m, dict):
                    continue
                sig = str(m.get("signal", "")).lower()
                if "speed" in sig:
                    tv = m.get("target_value")
                    if isinstance(tv, (int, float)) and tv > 0:
                        return float(tv)
        return None

    tv = _find_in(req) or _find_in(_read_json(project_json))
    return tv


class ResultChartsPanel(QWidget):
    """仿真结果可视化面板 — 包含四张图，放入右侧抽屉。"""

    def __init__(self, project_json_getter=None, parent=None):
        super().__init__(parent)
        self._project_json_getter = project_json_getter
        self._current_round: int = 0
        self._project_root: Path | None = None
        self.setObjectName("resultChartsPanel")

        # ── 布局 ──────────────────────────────────────────────────────
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # 标题行：标题 + 轮次下拉框
        header = QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 4)
        header.setSpacing(8)

        self._title_label = QLabel("仿真结果图表")
        self._title_label.setObjectName("chartPanelTitle")
        self._title_label.setStyleSheet(
            f"QLabel#chartPanelTitle{{"
            f"font-size:14px;font-weight:600;"
            f"color:{current_theme().muted};"
            f"background:{current_theme().panel};border:none;}}"
        )
        header.addWidget(self._title_label)

        header.addStretch()

        self._round_combo = QComboBox()
        self._round_combo.setFixedHeight(28)
        self._round_combo.setMinimumWidth(160)
        self._round_combo.setStyleSheet(
            f"QComboBox{{"
            f"font-size:13px;padding:2px 8px;"
            f"color:{current_theme().text};"
            f"background:{current_theme().surface};"
            f"border:1px solid {current_theme().border};"
            f"border-radius:4px;}}"
            f"QComboBox:hover{{border-color:{current_theme().border_strong};}}"
            f"QComboBox QAbstractItemView{{"
            f"color:{current_theme().text};"
            f"background:{current_theme().surface};"
            f"selection-background-color:{current_theme().selection};}}"
        )
        self._round_combo.currentIndexChanged.connect(self._on_round_changed)
        header.addWidget(self._round_combo)

        header_widget = QWidget()
        header_widget.setLayout(header)
        outer_layout.addWidget(header_widget)

        # ── 2×2 网格布局 ────────────────────────────────────────────
        grid = QGridLayout()
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setSpacing(10)

        self.speed_chart = SpeedWaveformChart(self)
        self.score_chart = ScoreBarChart(self)
        self.param_chart = ParamDeltaChart(self)
        self.angle_chart = AngleWaveformChart(self)

        for chart in [self.speed_chart, self.score_chart, self.param_chart, self.angle_chart]:
            chart.setMinimumHeight(160)
            chart.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        grid.addWidget(self.speed_chart, 0, 0)
        grid.addWidget(self.score_chart, 0, 1)
        grid.addWidget(self.param_chart, 1, 0)
        grid.addWidget(self.angle_chart, 1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        outer_layout.addLayout(grid)

        # 默认显示空状态
        self._show_empty_all()

    def _show_empty_all(self):
        msg = "请先打开项目并运行仿真"
        for chart in [self.speed_chart, self.score_chart, self.param_chart, self.angle_chart]:
            chart.show_empty(msg)

    def show_running(self, round_number: int = 1):
        """仿真正在运行中——显示占位提示，保留标题栏轮次信息。"""
        self._title_label.setText(f"仿真结果图表  —  Round {round_number}  ● 运行中")
        msg = f"第 {round_number} 轮仿真正在运行..."
        for chart in [self.speed_chart, self.score_chart, self.param_chart, self.angle_chart]:
            chart.show_empty(msg)

    def _rebuild_round_combo(self, project_root: Path, latest: int):
        """根据可用轮次重建下拉框选项。"""
        self._round_combo.blockSignals(True)
        try:
            self._round_combo.clear()
            all_r = _all_rounds(project_root)
            # 当前（最新轮次）始终排在第一位
            self._round_combo.addItem(f"当前 (Round {latest})", latest)
            for r in sorted(all_r, reverse=True):
                if r != latest:
                    self._round_combo.addItem(f"Round {r} (历史)", r)
        finally:
            self._round_combo.blockSignals(False)

    def _on_round_changed(self, index: int):
        if index < 0 or self._project_root is None:
            return
        selected_round = self._round_combo.currentData()
        if selected_round is not None and selected_round != self._current_round:
            self._current_round = selected_round
            self._reload_charts()

    def reload_for_project(self):
        """读取项目数据并刷新全部图表。"""
        getter = self._project_json_getter
        project_json = getter() if callable(getter) else None
        if not project_json:
            self._show_empty_all()
            return

        project_json = Path(project_json)
        if not project_json.exists():
            self._show_empty_all()
            return

        project_root = project_json.parent
        self._project_root = project_root
        latest = _latest_round(project_root)
        if latest <= 0:
            self._show_empty_all()
            return

        # ── 重建下拉框 ───────────────────────────────────────────────
        self._rebuild_round_combo(project_root, latest)
        self._current_round = latest

        # ── 收集 candidate 目录 ──────────────────────────────────────
        candidates_root = project_root / "candidates"
        self._candidate_dirs = sorted(
            [d for d in candidates_root.glob("candidate_*") if d.is_dir()]
        )

        # ── 刷新图表 ─────────────────────────────────────────────────
        self._reload_charts()

    def _reload_charts(self):
        """根据当前选中的轮次刷新全部图表。"""
        project_root = self._project_root
        if project_root is None:
            return
        rn = self._current_round
        candidate_dirs = getattr(self, "_candidate_dirs", [])
        if not candidate_dirs:
            return

        # ── 读取对应轮次的 feedback ──────────────────────────────────
        fb_path = project_root / "rounds" / f"round_{rn:02d}" / "round_feedback.json"
        feedback = _read_json(fb_path)
        if not feedback:
            self._show_empty_all()
            return

        # ── 更新标题 ─────────────────────────────────────────────────
        latest = _latest_round(project_root)
        if rn == latest:
            self._title_label.setText(f"仿真结果图表  —  Round {rn} (当前)")
        else:
            self._title_label.setText(f"仿真结果图表  —  Round {rn} (历史)")

        # ── 获取项目 JSON 路径 ───────────────────────────────────────
        getter = self._project_json_getter
        project_json = Path(getter()) if callable(getter) else None

        # ── 图 1：速度波形 ───────────────────────────────────────────
        speed_data = _load_speed_signals(project_root, candidate_dirs, rn)
        target = _extract_target_speed(project_json) if project_json else None
        self.speed_chart.plot(speed_data, target)

        # ── 图 2：评分对比 ───────────────────────────────────────────
        scoreboard = feedback.get("scoreboard", [])
        winner = feedback.get("winner", {})
        winner_id = str(winner.get("candidate_id", "")) if isinstance(winner, dict) else ""
        self.score_chart.plot(scoreboard, winner_id)

        # ── 图 3：参数调优变化量 ─────────────────────────────────────
        candidates_fb = feedback.get("candidates", [])
        winner_params: list[dict[str, Any]] = []
        for c in candidates_fb:
            if isinstance(c, dict) and str(c.get("candidate_id", "")) == winner_id:
                winner_params = c.get("final_parameters", [])
                break
        self.param_chart.plot(winner_params, winner_id)

        # ── 图 4：转角波形 ───────────────────────────────────────────
        angle_data = _load_angle_signals(project_root, candidate_dirs, rn)
        self.angle_chart.plot(angle_data)
