"""
round_feedback.py  —  Step 3: 汇总所有 candidate 的证据，生成轮次反馈。

设计原则：
    1. 纯程序化汇总，不依赖 LLM。
    2. 读取每个 candidate 的 evidence + manifest + tuning_result。
    3. 排名、统计失败指标、生成下一轮约束建议。
    4. 独立运行，不嵌入 generate/optimize 流程。

用法：
    python Competition/round_feedback.py <project_json> --round 1 --candidates all

输出位置：project/rounds/round_01/round_feedback.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

MOTORAI_ROOT = Path(__file__).resolve().parents[1]
if str(MOTORAI_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTORAI_ROOT))


# ── 辅助 ──────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _discover_candidate_dirs(project_root: Path, selectors: list[str]) -> list[Path]:
    candidates_root = project_root / "candidates"
    if not candidates_root.is_dir():
        return []

    selected = [s.strip() for s in selectors if s.strip()]
    if not selected or selected == ["all"]:
        return sorted(p for p in candidates_root.glob("candidate_*") if p.is_dir())

    result: list[Path] = []
    for item in selected:
        if item.isdigit():
            item = f"candidate_{int(item):02d}"
        path = candidates_root / item
        if path.is_dir():
            result.append(path)
    return result


# ── 读取单个 candidate 的关键数据 ─────────────────────────────────────────

def _read_candidate_data(candidate_dir: Path) -> dict[str, Any] | None:
    """读取一个 candidate 的 evidence + manifest + tuning_result。

    Returns None 如果关键文件缺失。
    """
    candidate_id = candidate_dir.name

    # 读取 evidence（Step 2 产物）
    evidence_path = candidate_dir / "log" / "optimize" / "candidate_evidence.json"
    evidence = _load_json(evidence_path)
    if not evidence:
        return None

    # 读取 manifest（Step 1 产物）
    manifest_path = candidate_dir / "log" / "generate" / "controller_manifest.json"
    manifest = _load_json(manifest_path)

    # 读取 tuning_result（原始 optimize 结果）
    tuning_path = candidate_dir / "log" / "optimize" / "tuning_result.json"
    tuning = _load_json(tuning_path)

    final_evaluation = evidence.get("final_evaluation")
    if not isinstance(final_evaluation, dict):
        final_evaluation = tuning.get("final_evaluation", {})

    overall_score = None
    try:
        overall_score = float(final_evaluation.get("overall_score"))
    except (TypeError, ValueError):
        pass

    return {
        "candidate_id": candidate_id,
        "overall_score": overall_score,
        "structure_manifest": {
            "structure_signature": manifest.get("structure_signature"),
            "loop_hierarchy": manifest.get("loop_hierarchy"),
            "control_methods": manifest.get("control_methods"),
        },
        "final_evaluation": final_evaluation,
        "failed_metrics": evidence.get("failed_metrics", []),
        "final_parameters": evidence.get("final_parameters", []),
        "parameter_history_summary": evidence.get("parameter_history_summary", {}),
        "tuning_diagnostics": evidence.get("tuning_diagnostics", {}),
        "source_files": evidence.get("source_files", {}),
    }


# ── 评分排序 ──────────────────────────────────────────────────────────────

def _build_scoreboard(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 overall_score 降序排列。"""
    scored = [c for c in candidates if c.get("overall_score") is not None]
    scored.sort(key=lambda c: c["overall_score"], reverse=True)  # type: ignore[arg-type, return-value]
    return [
        {"candidate_id": c["candidate_id"], "overall_score": c["overall_score"]}
        for c in scored
    ]


def _choose_winner(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    scored = [c for c in candidates if c.get("overall_score") is not None]
    if not scored:
        return None
    winner = max(scored, key=lambda c: c["overall_score"])  # type: ignore[arg-type, return-value]
    return {
        "candidate_id": winner["candidate_id"],
        "overall_score": winner["overall_score"],
        "final_evaluation": winner.get("final_evaluation", {}),
    }


# ── 失败指标汇总 ──────────────────────────────────────────────────────────

def _summarize_failed_metrics(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """统计哪些指标在多个 candidate 上失败。"""
    metric_candidates: dict[str, list[str]] = {}
    for c in candidates:
        for m in c.get("failed_metrics", []):
            name = m.get("name") or m.get("note", "unknown")
            if name not in metric_candidates:
                metric_candidates[name] = []
            metric_candidates[name].append(c["candidate_id"])

    return [
        {"metric": name, "failed_in": sorted(cids), "failed_count": len(cids)}
        for name, cids in sorted(metric_candidates.items(), key=lambda x: -len(x[1]))
    ]


# ── 下一轮约束 ────────────────────────────────────────────────────────────

def _build_next_round_constraints(
    winner: dict[str, Any] | None,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """基于本轮的 winner 和普遍失败指标，生成下一轮的探索建议。

    规则：
        preserve：winner 的结构签名
        avoid：如果有 candidate 分数明显低于其他同结构 candidate
        explore：针对普遍失败的指标，建议替换方向
    """
    preserve: list[str] = []
    avoid: list[str] = []
    explore: list[str] = []

    if winner:
        cid = winner.get("candidate_id", "")
        for c in candidates:
            if c["candidate_id"] == cid:
                sig = c.get("structure_manifest", {}).get("structure_signature", "")
                if sig:
                    preserve.append(sig)
                break

    # 统计失败指标，生成探索建议
    failed_summary = _summarize_failed_metrics(candidates)
    metric_explore_hints = {
        "overshoot": "尝试加入前馈补偿、抗饱和逻辑或降低外环增益",
        "speed_overshoot": "尝试加入斜坡限幅或低通滤波",
        "settling_time": "尝试提高外环增益或加入前馈通道",
        "rise_time": "尝试提高外环 KP 或加入前馈",
        "steady_state_error": "尝试提高外环 KI 或加入积分分离",
        "ripple": "尝试加入低通滤波或降低电流环增益",
        "oscillation_score": "尝试降低外环增益或增加阻尼",
    }
    for item in failed_summary[:3]:
        metric = item["metric"]
        hint = ""
        for key, value in metric_explore_hints.items():
            if key in metric.lower():
                hint = value
                break
        if not hint:
            hint = f"针对 {metric} 探索替代控制结构或参数范围"
        explore.append(hint)

    return {"preserve": preserve, "avoid": avoid, "explore": explore}


# ── 主函数 ────────────────────────────────────────────────────────────────

def generate_round_feedback(
    project_json: str | Path,
    round_number: int = 1,
    selectors: list[str] | None = None,
) -> Path:
    """汇总所有 candidate 的数据，生成 round_feedback.json。

    Args:
        project_json: 项目 JSON 文件路径。
        round_number: 轮次编号。
        selectors: candidate 选择器列表，默认 ["all"]。

    Returns:
        写入的 round_feedback.json 路径。
    """
    project_json = Path(project_json).expanduser().resolve()
    project_root = project_json.parent
    if selectors is None:
        selectors = ["all"]

    candidate_dirs = _discover_candidate_dirs(project_root, selectors)
    if not candidate_dirs:
        raise FileNotFoundError(f"未找到任何 candidate 目录：{project_root / 'candidates'}")

    # 读取所有 candidate 数据
    candidates: list[dict[str, Any]] = []
    for cdir in candidate_dirs:
        data = _read_candidate_data(cdir)
        if data:
            candidates.append(data)

    if not candidates:
        raise RuntimeError("所有 candidate 都缺少 candidate_evidence.json。请先运行 optimize。")

    # 确定是否满足停止条件
    stop_conditions = _load_json(project_json).get("stop_conditions") or {}
    winner = _choose_winner(candidates)
    requirement_satisfied = _check_stop_conditions(winner, stop_conditions)

    feedback: dict[str, Any] = {
        "schema_version": 1,
        "round": round_number,
        "requirement_satisfied": requirement_satisfied,
        "stop_conditions": stop_conditions,
        "winner": winner,
        "scoreboard": _build_scoreboard(candidates),
        "candidates": candidates,
        "failed_metrics_summary": _summarize_failed_metrics(candidates),
        "next_round_constraints": _build_next_round_constraints(winner, candidates),
    }

    output_path = project_root / "rounds" / f"round_{round_number:02d}" / "round_feedback.json"
    _write_json(output_path, feedback)
    return output_path


def _check_stop_conditions(winner: dict[str, Any] | None, stop_conditions: dict[str, Any]) -> bool:
    """检查 winner 是否满足停止条件。"""
    if not winner or not stop_conditions:
        return False

    score = winner.get("overall_score")
    if score is None:
        return False

    if "overall_score_min" in stop_conditions:
        try:
            if float(score) < float(stop_conditions["overall_score_min"]):
                return False
        except (TypeError, ValueError):
            return False

    if "metric_score_min" in stop_conditions:
        try:
            min_required = float(stop_conditions["metric_score_min"])
        except (TypeError, ValueError):
            return False
        final_eval = winner.get("final_evaluation")
        if isinstance(final_eval, dict):
            actual_min = final_eval.get("min_metric_score")
        else:
            actual_min = None
        if actual_min is None:
            return False
        try:
            if float(actual_min) < min_required:
                return False
        except (TypeError, ValueError):
            return False

    return True


# ── CLI ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成轮次反馈：汇总所有 candidate 的优化证据。")
    parser.add_argument("project_json", type=Path, help="项目 JSON 文件路径")
    parser.add_argument("--round", type=int, default=1, help="轮次编号，默认 1")
    parser.add_argument("--candidates", nargs="*", default=["all"], help="candidate 选择器，默认 all")
    args = parser.parse_args(argv)

    try:
        output_path = generate_round_feedback(
            args.project_json,
            round_number=args.round,
            selectors=args.candidates,
        )
        print(f"round_feedback written: {output_path}")
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
