"""
next_round_strategy.py  —  Step 4: 基于第一轮实验报告，用 LLM 生成第二轮方案。

输入：
    rounds/round_01/round_feedback.json  第一轮实验报告
    common/user_requirement.json         用户原始需求
    common/candidate_profiles.json       第一轮方案定义

输出：
    rounds/round_02/input_feedback.json   第二轮 agent 的决策上下文
    rounds/round_02/candidate_profiles.json  第二轮每个 candidate 的策略定义

用法：
    python Competition/next_round_strategy.py <project_json> --from-round 1 --to-round 2 --candidates 4
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

from motorai_config import get_llm_settings, load_settings
from openai import OpenAI
from Competition.competition_workspace import detect_controller_method


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


# ── 构建 LLM 提示词 ──────────────────────────────────────────────────────

def _detect_user_method_constraint(requirement: str) -> str:
    """从用户原始需求中检测明确指定的控制方法。

    只匹配肯定句式（如"采用PID控制器"、"速度环使用PI"），
    不匹配备选/未来/参考性提及（如"可考虑SMC"、"如果使用滑模"）。

    如果用户没有明确指定方法，返回空字符串。
    """
    method = detect_controller_method(requirement)
    labels = {
        "pid": "PID",
        "ladrc": "LADRC（自抗扰）",
        "smc": "SMC（滑模）",
    }
    return labels.get(method, "")


def _build_system_prompt() -> str:
    return """你是一个电机控制系统的结构迭代策略师。你的任务是根据上一轮多候选方案竞争的结果，为下一轮设计新的候选方案策略。

你需要分析：
1. 哪个候选方案赢了、为什么（结构、参数方向）
2. 哪些指标普遍失败（可能是结构层面的问题）
3. 哪些结构方向值得保留、哪些需要改进
4. 参数如何从上一轮继承或重新初始化

每个候选方案必须包含：
- name：方案名称（简洁，体现本轮改进意图）
- structure_bias：结构生成偏置描述（一句话）
- preferred_control_methods：优先探索的控制方法列表（只能选 pid/smc/ladrc）
- reference_candidates：参考上一轮哪个候选方案（最多两个）
- parameter_seed_policy：参数初始化策略（这是重点，必须认真填写）：
  - mode："inherit" / "inherit_then_perturb" / "fresh"
  - source_candidate：继承来源（mode 非 fresh 时必填）
  - perturbation_direction：扰动方向和幅度描述（mode=inherit_then_perturb 时必填）
- expected_improvement：本轮预期改善
  - target_failed_metrics：本轮要解决的失败指标列表

参数策略的核心原则：
- 与 winner 同结构的 exploit 方案：用 inherit_then_perturb 模式，在 winner 参数基础上小幅调整
- 结构相近的方案：用 inherit 模式，继承同名参数
- 结构完全不同的 explore 方案（如 pid→smc）：用 fresh 模式，不继承
- 通用参数（CUR_LIMIT、SPEED_LIMIT 等）通常可以从 winner 继承，即使结构不同

重要规则：
- 至少保留一个接近 winner 结构的方向（exploit），同时至少有一个尝试不同策略方向（explore）。
  策略差异可以在参数偏置、性能取舍、限幅/滤波策略上体现，不一定要更换控制方法。
- 如果用户没有指定控制方法，winner 的实际控制方法应占下一轮多数 candidate，
  同时至少保留一个 PID/LADRC 中另一方法的 challenger。两类方案都需要继续调参。
- 用户提示中给出的 candidate 控制方法和角色分配是固定约束。name、structure_bias、
  preferred_control_methods 和 parameter_seed_policy 必须与该分配一致，不得自行换成其他控制方法。
- **如果用户原始需求中已经明确指定了控制方法（如"速度环采用PID控制器"），
  则所有 candidate 的 preferred_control_methods 必须包含该方法，不得替换为用户未指定的方法。**
  在这种情况下，explore 方案应聚焦于参数策略差异、响应速度 vs 稳定性的权衡等方向。
- 如果多个候选方案都失败了同一个指标，说明可能是结构层面的瓶颈，下一轮应考虑替代结构
- 方案名称和 structure_bias 要用中文
- 输出的 JSON 必须是合法的 JSON 对象，包含 "profiles" 数组"""


def _build_user_prompt(
    user_requirement: dict[str, Any],
    round_feedback: dict[str, Any],
    prev_profiles: list[dict[str, Any]],
    candidate_count: int,
    controller_allocation: dict[str, Any] | None = None,
) -> str:
    """构建包含完整上下文信息的提示词。"""
    parts: list[str] = []

    # 用户需求
    objective = user_requirement.get("objective_text") or user_requirement.get("objective", "未指定")
    parts.append(f"## 用户原始需求\n\n{objective}\n")

    # ── 从用户需求中检测控制方法约束 ─────────────────────────────────
    user_method_hint = _detect_user_method_constraint(objective)
    if user_method_hint:
        parts.append(f"## ⚠️ 用户已指定控制方法\n\n")
        parts.append(f"用户的原始需求中明确提到了以下控制方法：**{user_method_hint}**。\n")
        parts.append("所有候选方案的 preferred_control_methods 必须包含用户已指定的方法，")
        parts.append("不得替换为用户未提及的控制方法。")
        parts.append("explore 方向应聚焦于参数偏置、响应速度 vs 稳定性权衡、限幅/滤波策略等方面的差异化，")
        parts.append("而不是换掉用户已经选定的控制方法。\n")

    # 停止条件
    stop = round_feedback.get("stop_conditions", {})
    if stop:
        parts.append(f"## 停止条件\n```json\n{json.dumps(stop, ensure_ascii=False, indent=2)}\n```\n")
    parts.append(f"需求已满足：{'是' if round_feedback.get('requirement_satisfied') else '否'}\n")

    # 上一轮结果摘要
    winner = round_feedback.get("winner", {})
    scoreboard = round_feedback.get("scoreboard", [])
    parts.append(f"## 上一轮结果\n\n**Winner**: {winner.get('candidate_id', 'N/A')} (score: {winner.get('overall_score', 'N/A')})\n")
    parts.append(f"\n**排名**：\n")
    for item in scoreboard:
        parts.append(f"- {item['candidate_id']}: {item['overall_score']}\n")

    # 失败指标汇总
    failed = round_feedback.get("failed_metrics_summary", [])
    if failed:
        parts.append("\n**普遍失败的指标**：\n")
        for item in failed:
            parts.append(f"- {item['metric']}: 失败于 {item['failed_in']}\n")

    # 每个候选方案的详细信息
    candidates = round_feedback.get("candidates", [])
    parts.append(f"\n## 上一轮候选方案详情\n")
    for c in candidates:
        cid = c.get("candidate_id", "?")
        score = c.get("overall_score", "N/A")
        structure = c.get("structure_manifest", {})
        sig = structure.get("structure_signature", "?")
        methods = structure.get("control_methods", [])
        failed_metrics = [m.get("name", "?") for m in c.get("failed_metrics", [])]
        ph = c.get("parameter_history_summary", {})
        most_adj = ph.get("most_adjusted", [])
        barely = ph.get("barely_moved", [])
        convergence = ph.get("convergence", "unknown")

        # 提取关键参数的变化信息
        param_changes: list[str] = []
        for p in c.get("final_parameters", []):
            name = p.get("name", "")
            delta = p.get("delta_pct")
            if delta is not None and abs(delta) > 0.5:
                direction = "↑" if delta > 0 else "↓"
                param_changes.append(f"{name} {direction}{abs(delta):.1f}%")

        parts.append(
            f"**{cid}** | score={score} | 结构={sig} | 方法={methods}\n"
            f"  失败指标：{failed_metrics if failed_metrics else '无'}\n"
            f"  收敛趋势：{convergence}\n"
            f"  大幅调整的参数：{most_adj if most_adj else '无'}  |  几乎未变的参数：{barely if barely else '无'}\n"
            f"  参数变化：{', '.join(param_changes) if param_changes else '所有参数变化 < 0.5%'}\n"
        )

    # 可用结构空间
    parts.append(f"\n## 当前已实现的控制结构\n")
    parts.append("- **pid**：标准 PID 控制（默认，外环 mech_loop 使用）\n")
    parts.append("- **smc**：滑模控制（替换外环 PID，模板已就绪）\n")
    parts.append("- **ladrc**：线性自抗扰控制（替换外环 PID，支持速度和位置模式，模板已就绪）\n")
    parts.append("\n**注意**：preferred_control_methods 只能从上述三种中选择。")
    parts.append("feedforward、disturbance_observer、gain_scheduling、filtering 等功能尚未实现，")
    parts.append("不得出现在第二轮方案的 preferred_control_methods 中。\n")

    # 参数初始化策略说明
    parts.append(f"\n## 参数初始化策略\n")
    parts.append("每个候选方案必须明确参数初始化方式：\n")
    parts.append("**mode 取值**：\n")
    parts.append("- `inherit`：同名参数从 source_candidate 的最终值继承。适用于与上一轮结构相同的 exploit 方案。\n")
    parts.append("- `inherit_then_perturb`：先继承同名参数，再根据 perturbation_direction 施加小幅偏移。\n")
    parts.append("  适用于与上一轮结构相同但想尝试不同偏置方向的 exploit 方案。\n")
    parts.append("- `fresh`：使用生成器默认值，不继承任何参数。适用于与上一轮结构完全不同（如 pid→smc）的 explore 方案。\n")
    parts.append("\n**perturbation_direction 写法**（仅 mode=inherit_then_perturb 时需要）：\n")
    parts.append("- 方向词必须从以下选择：提高、增加、加大、升高、上调、降低、减少、减小、下调\n")
    parts.append("- 百分比必须为纯数字（如 5%、10%），禁止使用 ± 前缀（如 \"±5%\" 应拆为 \"提高 5%\" 或 \"降低 5%\"）\n")
    parts.append("- 禁止使用模糊动词如 \"做\"、\"调整\"、\"修改\"、\"扰动\" —— 必须指明具体方向\n")
    parts.append("- 示例：\"提高 VEL_KP 和 POS_KP 约 20%，降低 CUR_LIMIT 约 10%\"\n")
    parts.append("- 基于上一轮的参数值方向，明确指出哪些参数该调大、哪些该调小\n")
    parts.append("\n**参数继承时注意**：\n")
    parts.append("- 如果 source_candidate 的结构与当前候选方案不同（如 pid→smc），")
    parts.append("  只有同名通用参数（如 CUR_LIMIT、SPEED_LIMIT）可以继承，结构特定参数应使用 fresh\n")
    parts.append("- 如果上一轮某参数 delta_pct 接近 0，说明该参数对优化不敏感，可以直接继承\n")
    parts.append("- 如果上一轮 most_adjusted 中的参数，说明该参数对性能影响大，值得在新的 exploit 方案中重点调整\n")

    # 上一轮的方案策略
    if prev_profiles:
        parts.append(f"\n## 上一轮方案策略（供参考）\n```json\n{json.dumps(prev_profiles, ensure_ascii=False, indent=2)}\n```\n")

    assignments = controller_allocation.get("assignments") if isinstance(controller_allocation, dict) else []
    if isinstance(assignments, list) and assignments:
        parts.append("\n## 固定 candidate 控制方法分配（不可更改）\n")
        for assignment in assignments:
            if not isinstance(assignment, dict):
                continue
            source = assignment.get("source_candidate") or "无"
            parts.append(
                f"- {assignment.get('candidate_id')}：方法={assignment.get('method')}，"
                f"角色={assignment.get('role')}，参数来源={source}\n"
            )
        parts.append(
            "每个方案的名称和 structure_bias 必须明确服从其分配方法，"
            "不得描述或暗示使用其他控制方法。\n"
        )

    # 任务
    parts.append(f"\n## 任务\n")
    parts.append(f"请为第下一轮生成 {candidate_count} 个候选方案策略。")
    if user_method_hint:
        parts.append(f"注意：用户已指定控制方法为 {user_method_hint}，所有方案的控制方法必须保持一致。")
        parts.append("差异化应体现在参数偏置方向、性能指标侧重点（如一个偏快速响应、一个偏稳态精度）等方面。")
    else:
        parts.append("确保至少有一个 exploit（基于 winner 方向改进）和一个 explore（尝试不同结构方向）。")
    parts.append("以 JSON 格式输出：{\"profiles\": [...]}")

    return "\n".join(parts)


# ── 调用 LLM ──────────────────────────────────────────────────────────────

def _call_llm(prompt: str, system_prompt: str) -> dict[str, Any]:
    """调用 LLM 生成下一轮候选方案。"""
    settings = get_llm_settings(load_settings())
    api_key = str(settings.get("api_key", "") or "").strip()
    if not api_key:
        raise RuntimeError("未配置 LLM API key。请检查 motorai_settings.json。")

    model = str(settings.get("model", "deepseek-v4-flash")).strip()
    base_url = str(settings.get("base_url", "https://api.deepseek.com")).strip()
    temperature = float(settings.get("temperature", 0.3))

    client = OpenAI(api_key=api_key, base_url=base_url)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("LLM 返回了空响应")

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        # 尝试从 markdown 代码块中提取 JSON
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if match:
            result = json.loads(match.group(1))
        else:
            raise RuntimeError(f"LLM 返回的内容不是合法 JSON: {content[:500]}")

    return result


# ── 校验 ──────────────────────────────────────────────────────────────────

def _validate_profiles(profiles: list[dict[str, Any]], candidate_count: int) -> list[dict[str, Any]]:
    """校验并补全 LLM 输出的 profiles。"""
    result: list[dict[str, Any]] = []
    valid_modes = {"inherit", "inherit_then_perturb", "fresh"}
    for i in range(candidate_count):
        raw = profiles[i] if i < len(profiles) else {}
        seed_policy = raw.get("parameter_seed_policy") if isinstance(raw.get("parameter_seed_policy"), dict) else {}
        mode = str(seed_policy.get("mode", "") or "").strip()
        if mode not in valid_modes:
            mode = "fresh"
        profile: dict[str, Any] = {
            "candidate_id": f"candidate_{i + 1:02d}",
            "name": str(raw.get("name", "") or f"候选方案 {i + 1}").strip(),
            "structure_bias": str(raw.get("structure_bias", "") or "").strip(),
            "preferred_control_methods": _ensure_list(raw.get("preferred_control_methods"), ["pid"]),
            "reference_candidates": _ensure_list(raw.get("reference_candidates"), []),
            "parameter_seed_policy": {
                "mode": mode,
                "source_candidate": str(seed_policy.get("source_candidate", "") or "").strip(),
                "perturbation_direction": str(seed_policy.get("perturbation_direction", "") or "").strip() if mode == "inherit_then_perturb" else "",
            },
            "expected_improvement": {
                "target_failed_metrics": _ensure_list(
                    raw.get("expected_improvement", {}).get("target_failed_metrics"), []
                ),
            },
        }
        result.append(profile)
    return result


def _ensure_list(value: Any, default: list[str]) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return default


def _ensure_elite_preservation(
    profiles: list[dict[str, Any]],
    feedback: dict[str, Any],
) -> list[dict[str, Any]]:
    """精英保留 + 去重：保证多样性，防止两个 candidate 参数一模一样。

    规则：
    1. 至少有一个 candidate 纯 inherit winner（精英保留）
    2. 不允许两个 candidate 同为纯 inherit 且来源相同（浪费仿真资源）
       违者将后出现的转为 inherit_then_perturb + 默认微扰动
    """
    winner = feedback.get("winner")
    if not isinstance(winner, dict):
        return _deduplicate_inherit(profiles)

    winner_id = str(winner.get("candidate_id", "") or "").strip()
    if not winner_id:
        return _deduplicate_inherit(profiles)

    # ── 规则 1：精英保留 ──────────────────────────────────────────────
    has_elite = False
    for p in profiles:
        seed = p.get("parameter_seed_policy") if isinstance(p.get("parameter_seed_policy"), dict) else {}
        mode = str(seed.get("mode", "") or "").strip()
        refs = p.get("reference_candidates") or []
        source = str(seed.get("source_candidate", "") or "").strip()
        if mode == "inherit" and (winner_id in refs or source == winner_id):
            has_elite = True
            break

    if not has_elite:
        # 提取 winner 的控制方法
        candidates = feedback.get("candidates") or []
        winner_methods: list[str] = ["pid"]
        for c in candidates:
            if c.get("candidate_id") == winner_id:
                manifest = c.get("structure_manifest") if isinstance(c.get("structure_manifest"), dict) else {}
                methods = manifest.get("control_methods") or []
                if isinstance(methods, list) and methods:
                    winner_methods = [str(m).strip().lower() for m in methods if str(m).strip()]
                break

        last_index = len(profiles) - 1
        preserve: dict[str, Any] = {
            "candidate_id": f"candidate_{last_index + 1:02d}",
            "name": f"精英保留（继承 {winner_id}）",
            "structure_bias": f"与 {winner_id} 保持一致的控制结构，继承其最终参数作为起点",
            "preferred_control_methods": winner_methods,
            "reference_candidates": [winner_id],
            "parameter_seed_policy": {
                "mode": "inherit",
                "source_candidate": winner_id,
                "perturbation_direction": "",
            },
            "expected_improvement": {"target_failed_metrics": []},
        }
        profiles[-1] = preserve

    # ── 规则 2：去重 ──────────────────────────────────────────────────
    return _deduplicate_inherit(profiles)


def _deduplicate_inherit(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """若多个 candidate 同为纯 inherit 且来源相同，将冗余者转为微扰动模式。"""
    seen_sources: dict[str, int] = {}  # source_id -> first profile index
    for i, p in enumerate(profiles):
        seed = p.get("parameter_seed_policy") if isinstance(p.get("parameter_seed_policy"), dict) else {}
        mode = str(seed.get("mode", "") or "").strip()
        source = str(seed.get("source_candidate", "") or "").strip()
        if mode != "inherit" or not source:
            continue
        if source in seen_sources:
            # 重复了，转为 inherit_then_perturb
            dup = profiles[i]
            dup_name = dup.get("name", "")
            dup["parameter_seed_policy"] = {
                "mode": "inherit_then_perturb",
                "source_candidate": source,
                "perturbation_direction": "提高 VEL_KP 约 3%，提高 VEL_KI 约 3%，提高 CUR_KP 约 3%，提高 CUR_KI 约 3%",
            }
            dup["name"] = dup_name + "（微调）" if dup_name else f"继承 {source}（微调）"
        else:
            seen_sources[source] = i
    return profiles


def _candidate_controller_methods(feedback: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for candidate in feedback.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("candidate_id", "") or "").strip()
        manifest = candidate.get("structure_manifest")
        methods = manifest.get("control_methods") if isinstance(manifest, dict) else []
        if not isinstance(methods, list):
            methods = [methods]
        normalized = [str(method).strip().lower() for method in methods]
        method = next((item for item in normalized if item in {"pid", "ladrc", "smc"}), "")
        if candidate_id and method:
            result[candidate_id] = method
    return result


def _best_candidate_for_method(
    feedback: dict[str, Any],
    method: str,
    candidate_methods: dict[str, str],
) -> str:
    ranked: list[tuple[float, str]] = []
    for candidate in feedback.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("candidate_id", "") or "").strip()
        if candidate_methods.get(candidate_id) != method:
            continue
        try:
            score = float(candidate.get("overall_score"))
        except (TypeError, ValueError):
            continue
        ranked.append((score, candidate_id))
    return max(ranked, default=(float("-inf"), ""))[1]


def _build_controller_allocation_plan(
    feedback: dict[str, Any],
    requirement_text: str,
    profile_count: int,
) -> dict[str, Any]:
    explicit_method = detect_controller_method(requirement_text)
    winner = feedback.get("winner")
    winner_id = str(winner.get("candidate_id", "") or "").strip() if isinstance(winner, dict) else ""

    if explicit_method:
        return {
            "mode": "user_constraint",
            "winner_method": explicit_method,
            "winner_slots": profile_count,
            "challenger_method": None,
            "challenger_slots": 0,
            "assignments": [
                {
                    "candidate_id": f"candidate_{index + 1:02d}",
                    "method": explicit_method,
                    "role": "user_constraint",
                    "source_candidate": "",
                }
                for index in range(profile_count)
            ],
        }

    candidate_methods = _candidate_controller_methods(feedback)
    winner_method = candidate_methods.get(winner_id, "")
    if not winner_method or profile_count < 1:
        return {"mode": "llm_fallback", "winner_method": None, "assignments": []}

    challenger_method = "ladrc" if winner_method == "pid" else "pid"
    winner_slots = profile_count if profile_count == 1 else min(
        profile_count - 1,
        max(1, int(profile_count * 0.75)),
    )
    challenger_source = _best_candidate_for_method(feedback, challenger_method, candidate_methods)
    assignments: list[dict[str, Any]] = []
    for index in range(profile_count):
        if index == 0:
            method = winner_method
            role = "elite"
            source = winner_id
        elif index < winner_slots:
            method = winner_method
            role = "exploit"
            source = winner_id
        else:
            method = challenger_method
            role = "challenger"
            source = challenger_source
        assignments.append(
            {
                "candidate_id": f"candidate_{index + 1:02d}",
                "method": method,
                "role": role,
                "source_candidate": source,
            }
        )

    return {
        "mode": "winner_guided_exploit_explore",
        "winner_candidate": winner_id,
        "winner_method": winner_method,
        "winner_slots": winner_slots,
        "challenger_method": challenger_method,
        "challenger_slots": profile_count - winner_slots,
        "challenger_source": challenger_source or None,
        "assignments": assignments,
    }


def _mentioned_controller_methods(text: str) -> set[str]:
    lowered = str(text or "").lower()
    keywords = {
        "pid": ("pid", "比例积分"),
        "ladrc": ("ladrc", "adrc", "自抗扰"),
        "smc": ("smc", "滑模"),
    }
    return {
        method
        for method, terms in keywords.items()
        if any(term in lowered for term in terms)
    }


def _normalize_conflicting_strategy_text(
    profile: dict[str, Any],
    method: str,
    role: str,
    winner_id: str,
) -> None:
    strategy_text = f"{profile.get('name', '')} {profile.get('structure_bias', '')}"
    if not (_mentioned_controller_methods(strategy_text) - {method}):
        return

    label = {"pid": "PID", "ladrc": "LADRC", "smc": "SMC"}.get(method, method.upper())
    if role == "elite":
        name = f"{label}精英保留"
        bias = f"保持上一轮 winner {winner_id} 的 {label} 控制结构和最优参数。"
    elif role == "challenger":
        name = f"{label}挑战优化"
        bias = f"采用 {label} 控制结构，继承该方法上一轮最佳参数并继续调优。"
    elif role == "user_constraint":
        name = f"{label}参数策略"
        bias = f"保持用户指定的 {label} 控制结构，在该方法内探索参数和性能取舍。"
    else:
        name = f"{label}参数优化"
        bias = f"采用 {label} 控制结构，围绕上一轮 winner 参数继续优化。"
    profile["name"] = name
    profile["structure_bias"] = bias
    profile["strategy_text_normalized"] = True


def _apply_controller_method_allocation(
    profiles: list[dict[str, Any]],
    feedback: dict[str, Any],
    requirement_text: str,
    allocation_plan: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply deterministic controller allocation after validating the LLM output."""
    plan = allocation_plan or _build_controller_allocation_plan(
        feedback,
        requirement_text,
        len(profiles),
    )
    assignments = plan.get("assignments") if isinstance(plan, dict) else []
    if not isinstance(assignments, list) or not assignments:
        return profiles, plan

    winner_id = str(plan.get("winner_candidate", "") or "")
    candidate_methods = _candidate_controller_methods(feedback)
    assignment_by_id = {
        str(item.get("candidate_id")): item
        for item in assignments
        if isinstance(item, dict) and item.get("candidate_id")
    }
    for profile in profiles:
        assignment = assignment_by_id.get(str(profile.get("candidate_id", "")))
        if not assignment:
            continue
        method = str(assignment.get("method", "") or "").lower()
        role = str(assignment.get("role", "") or "")
        source = str(assignment.get("source_candidate", "") or "")
        seed = profile.get("parameter_seed_policy")
        seed = dict(seed) if isinstance(seed, dict) else {}

        if role == "elite":
            profile["reference_candidates"] = [source] if source else []
            profile["parameter_seed_policy"] = {
                "mode": "inherit" if source else "fresh",
                "source_candidate": source,
                "perturbation_direction": "",
            }
        elif role == "exploit":
            profile["reference_candidates"] = [source] if source else []
            profile["parameter_seed_policy"] = {
                "mode": "inherit_then_perturb" if source else "fresh",
                "source_candidate": source,
                "perturbation_direction": str(seed.get("perturbation_direction", "") or "")
                or ("围绕 winner 参数小幅扰动，并针对失败指标继续调优" if source else ""),
            }
        elif role == "challenger":
            profile["reference_candidates"] = [source] if source else []
            profile["parameter_seed_policy"] = {
                "mode": "inherit_then_perturb" if source else "fresh",
                "source_candidate": source,
                "perturbation_direction": (
                    "围绕该控制方法上一轮最佳参数小幅扰动，并针对失败指标继续调优"
                    if source
                    else ""
                ),
            }
        elif role == "user_constraint":
            source = str(seed.get("source_candidate", "") or "")
            if source and candidate_methods.get(source) != method:
                profile["reference_candidates"] = []
                profile["parameter_seed_policy"] = {
                    "mode": "fresh",
                    "source_candidate": "",
                    "perturbation_direction": "",
                }

        profile["preferred_control_methods"] = [method]
        profile["controller_method_constraint"] = method
        profile["controller_assignment"] = {
            "method": method,
            "source": "user_requirement" if role == "user_constraint" else "winner_guided_allocation",
            "role": role,
            "winner_candidate": winner_id,
        }
        _normalize_conflicting_strategy_text(profile, method, role, winner_id)

    return _deduplicate_inherit(profiles), plan


# ── 主函数 ────────────────────────────────────────────────────────────────

def generate_next_round_strategy(
    project_json: str | Path,
    from_round: int = 1,
    to_round: int = 2,
    candidate_count: int = 0,
) -> dict[str, Any]:
    """生成下一轮的候选方案策略。

    Returns:
        {"input_feedback": Path, "candidate_profiles": Path, "profiles": [...]}
    """
    project_json = Path(project_json).expanduser().resolve()
    project_root = project_json.parent

    # 1. 读取输入
    feedback = _load_json(project_root / "rounds" / f"round_{from_round:02d}" / "round_feedback.json")
    if not feedback:
        raise FileNotFoundError(f"未找到 round_{from_round:02d} 的 round_feedback.json，请先运行 optimize。")

    project_data = _load_json(project_json)
    requirement = _load_json(project_root / "common" / "user_requirement.json")
    profiles_data = _load_json(project_root / "common" / "candidate_profiles.json")
    prev_profiles = profiles_data.get("profiles", []) if isinstance(profiles_data.get("profiles"), list) else []

    # candidate_count 优先从项目 JSON 读取
    if candidate_count <= 0:
        candidate_count = int(project_data.get("candidate_count") or len(prev_profiles) or 4)

    objective = str(
        requirement.get("objective_text")
        or requirement.get("requirement")
        or requirement.get("objective")
        or ""
    )
    controller_allocation = _build_controller_allocation_plan(
        feedback,
        objective,
        candidate_count,
    )

    # 2. 构建 prompt 并调用 LLM
    system = _build_system_prompt()
    user = _build_user_prompt(
        requirement,
        feedback,
        prev_profiles,
        candidate_count,
        controller_allocation,
    )

    print("正在调用 LLM 分析第一轮实验报告，生成第二轮方案策略...")
    llm_result = _call_llm(user, system)

    raw_profiles = llm_result.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise RuntimeError(f"LLM 返回的 profiles 不是有效数组: {json.dumps(llm_result, ensure_ascii=False)[:500]}")

    profiles = _validate_profiles(raw_profiles, candidate_count)

    if controller_allocation.get("mode") == "llm_fallback":
        profiles = _ensure_elite_preservation(profiles, feedback)
    profiles, controller_allocation = _apply_controller_method_allocation(
        profiles,
        feedback,
        objective,
        controller_allocation,
    )

    # 3. 写入输出
    round_dir = project_root / "rounds" / f"round_{to_round:02d}"
    round_dir.mkdir(parents=True, exist_ok=True)

    # input_feedback.json：给下一轮 agent 的决策上下文
    input_feedback: dict[str, Any] = {
        "schema_version": 1,
        "from_round": from_round,
        "to_round": to_round,
        "requirement_satisfied": feedback.get("requirement_satisfied", False),
        "winner": feedback.get("winner"),
        "scoreboard": feedback.get("scoreboard", []),
        "failed_metrics_summary": feedback.get("failed_metrics_summary", []),
        "controller_allocation": controller_allocation,
        "prev_candidates_summary": [
            {
                "candidate_id": c.get("candidate_id"),
                "overall_score": c.get("overall_score"),
                "structure_signature": c.get("structure_manifest", {}).get("structure_signature"),
                "failed_metrics": [m.get("name") for m in c.get("failed_metrics", [])],
                "convergence": c.get("parameter_history_summary", {}).get("convergence"),
            }
            for c in feedback.get("candidates", [])
        ],
    }
    _write_json(round_dir / "input_feedback.json", input_feedback)

    # candidate_profiles.json：下一轮的方案策略
    profiles_output: dict[str, Any] = {
        "schema_version": 1,
        "round": to_round,
        "from_round": from_round,
        "description": (
            f"第 {to_round} 轮候选方案策略，由 LLM 基于第 {from_round} 轮实验报告生成。"
            "这些策略只影响 generate 阶段的控制结构选择和参数种子方向。"
        ),
        "controller_allocation": controller_allocation,
        "profiles": profiles,
    }
    _write_json(round_dir / "candidate_profiles.json", profiles_output)

    print(f"已生成: {round_dir / 'input_feedback.json'}")
    print(f"已生成: {round_dir / 'candidate_profiles.json'}")

    return {
        "input_feedback": str((round_dir / "input_feedback.json").resolve()),
        "candidate_profiles": str((round_dir / "candidate_profiles.json").resolve()),
        "controller_allocation": controller_allocation,
        "profiles": profiles,
    }


# ── CLI ────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成下一轮候选方案策略（需要 LLM）。")
    parser.add_argument("project_json", type=Path, help="项目 JSON 文件路径")
    parser.add_argument("--from-round", type=int, default=1, help="来源轮次，默认 1")
    parser.add_argument("--to-round", type=int, default=2, help="目标轮次，默认 2")
    parser.add_argument("--candidates", type=int, default=0, help="下一轮候选方案数量，默认从项目 JSON 读取")
    args = parser.parse_args(argv)

    try:
        result = generate_next_round_strategy(
            args.project_json,
            from_round=args.from_round,
            to_round=args.to_round,
            candidate_count=args.candidates,
        )
        print(f"\n生成 {len(result['profiles'])} 个候选方案：")
        for p in result["profiles"]:
            print(f"  {p['candidate_id']}: {p['name']}")
            print(f"    偏置: {p['structure_bias']}")
            print(f"    方法: {p['preferred_control_methods']}")
            print(f"    参考: {p['reference_candidates']}")
            print(f"    参数策略: {p['parameter_seed_policy']['mode']} <- {p['parameter_seed_policy']['source_candidate']}")
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
