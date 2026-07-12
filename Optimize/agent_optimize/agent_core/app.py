from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .config import ProjectContext, load_project_context
from .llm import LLMClient
from .prompts import SYSTEM_PROMPT
from .tool_registry import ToolRegistry
from .tools import (
    register_automation_tools,
    register_resource_tools,
    register_evaluation_tools,
    register_parameter_edit_tools,
    register_optimization_tools,
)
from .tools.optimization import validate_tuning_policy_coverage
from .parameters.parameter_header_editor import ParameterHeaderError, read_tunable_parameters


def _infer_parameter_range(name: str, current_value: float) -> dict[str, Any]:
    """为自动补全的参数推断合理的 min/max 范围。

    规则按参数名后缀分类，与 parameter_seeder.classify_parameter() 的分类逻辑
    保持一致。兜底用 [current*0.1, current*10]。
    """
    name_upper = str(name).upper()
    abs_val = abs(current_value) if current_value != 0.0 else 1.0

    # ── 斜率 / 爬坡限制（必须在 _LIMIT 之前，否则 SPEED_SLOPE_LIMIT
    #     会被优先命中 _LIMIT 分支）────────────────────────────────
    if "_SLOPE" in name_upper:
        return {"min": 0.01, "max": round(max(abs_val * 5.0, 1.0), 4),
                "description": "自动补全：斜率/爬坡参数"}

    # ── 限幅参数（SPEED_LIMIT, CUR_LIMIT, …）─────────────────────
    if name_upper.endswith("_LIMIT") or name_upper.endswith("_MAX"):
        return {"min": 0.05, "max": round(max(abs_val * 5.0, 10.0), 4),
                "description": "自动补全：限幅参数"}

    # ── PID 增益 ─────────────────────────────────────────────────
    if name_upper.endswith("_KP"):
        return {"min": 0.1, "max": round(max(abs_val * 5.0, 20.0), 4),
                "description": "自动补全：比例增益"}
    if name_upper.endswith("_KI"):
        return {"min": 0.0, "max": round(max(abs_val * 10.0, 5.0), 4),
                "description": "自动补全：积分增益"}
    if name_upper.endswith("_KD"):
        return {"min": 0.0, "max": round(max(abs_val * 5.0, 5.0), 4),
                "description": "自动补全：微分增益"}

    # ── 带宽参数（LADRC / SMC）───────────────────────────────────
    if any(name_upper.endswith(s) for s in ("_WC", "_WO", "_BW")):
        return {"min": 1.0, "max": round(max(abs_val * 5.0, 500.0), 4),
                "description": "自动补全：带宽参数"}

    # ── 物理常数 ─────────────────────────────────────────────────
    if name_upper in ("INERTIA", "TORQUE_CONST") \
            or name_upper.endswith("_INERTIA") \
            or name_upper.endswith("_TORQUE_CONST"):
        return {"min": round(abs_val * 0.5, 6), "max": round(abs_val * 2.0, 6),
                "description": "自动补全：物理常数"}

    # ── 兜底 ─────────────────────────────────────────────────────
    return {"min": round(abs_val * 0.1, 6), "max": round(abs_val * 10.0, 4),
            "description": "自动补全：未分类参数"}


DEFAULT_HEADLESS_MAX_TOOL_ROUNDS = 12


def build_registry(ctx) -> ToolRegistry:
    registry = ToolRegistry()
    register_resource_tools(registry, ctx)
    register_automation_tools(registry, ctx)
    register_evaluation_tools(registry, ctx)
    register_parameter_edit_tools(registry, ctx)
    register_optimization_tools(registry, ctx)
    return registry


def _message_to_dict(message: Any) -> Dict[str, Any]:
    """Keep OpenAI-compatible message objects usable in the local conversation list."""
    # The OpenAI SDK message object already works in many cases, but dict conversion is more robust
    # when appending it back into the messages list.
    if hasattr(message, "model_dump"):
        return message.model_dump(exclude_none=True)
    if isinstance(message, dict):
        return message
    return {
        "role": getattr(message, "role", "assistant"),
        "content": getattr(message, "content", None),
        "tool_calls": getattr(message, "tool_calls", None),
    }


def _tool_call_parts(tool_call: Any, tool_round: int, index: int) -> Tuple[str, str, str]:
    """Extract function name, raw JSON arguments, and tool-call id from SDK or dict objects."""
    if isinstance(tool_call, dict):
        function = tool_call.get("function", {})
        if isinstance(function, dict):
            function_name = function.get("name") or ""
            raw_arguments = function.get("arguments") or "{}"
        else:
            function_name = getattr(function, "name", "") or ""
            raw_arguments = getattr(function, "arguments", None) or "{}"
        tool_call_id = tool_call.get("id") or f"tool_call_{tool_round}_{index}"
        return function_name, raw_arguments, tool_call_id

    function = getattr(tool_call, "function", None)
    function_name = getattr(function, "name", "") or ""
    raw_arguments = getattr(function, "arguments", None) or "{}"
    tool_call_id = getattr(tool_call, "id", None) or f"tool_call_{tool_round}_{index}"
    return function_name, raw_arguments, tool_call_id


def run_agent_turn(
    llm: LLMClient,
    registry: ToolRegistry,
    messages: List[Dict[str, Any]],
    *,
    max_tool_rounds: int = DEFAULT_HEADLESS_MAX_TOOL_ROUNDS,
    echo_tools: bool = False,
    allowed_tool_names: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Run one assistant turn, including any tool-call loops requested by the model.

    The caller owns the conversation list. This function appends assistant and tool
    messages to that list until the assistant returns a final message without
    tool_calls, then returns that final assistant message.

    allowed_tool_names:
        None means all registered tools are exposed.
        Otherwise, only listed tools are exposed to the LLM and executable.
    """
    if max_tool_rounds < 1:
        raise ValueError("max_tool_rounds must be >= 1")

    allowed_tool_set = set(allowed_tool_names) if allowed_tool_names is not None else None

    all_schemas = registry.schemas()

    if allowed_tool_set is None:
        tool_schemas = all_schemas
    else:
        available_tool_names = {
            (schema.get("function") or {}).get("name")
            for schema in all_schemas
            if isinstance(schema, dict)
        }

        missing_tools = allowed_tool_set - available_tool_names
        if missing_tools:
            raise ValueError(
                "allowed_tool_names contains tools that are not registered: "
                + ", ".join(sorted(missing_tools))
            )

        tool_schemas = [
            schema
            for schema in all_schemas
            if (schema.get("function") or {}).get("name") in allowed_tool_set
        ]

    for tool_round in range(1, max_tool_rounds + 1):
        assistant_message = llm.ask(messages, tool_schemas)
        assistant_dict = _message_to_dict(assistant_message)
        messages.append(assistant_dict)

        tool_calls = assistant_dict.get("tool_calls") or []
        if not tool_calls:
            return assistant_dict

        for index, tool_call in enumerate(tool_calls, start=1):
            function_name, raw_arguments, tool_call_id = _tool_call_parts(
                tool_call,
                tool_round,
                index,
            )

            if not function_name:
                tool_result = "Error: missing tool function name."

            elif allowed_tool_set is not None and function_name not in allowed_tool_set:
                tool_result = (
                    f"Error: tool '{function_name}' is not allowed in this stage. "
                    f"Allowed tools: {sorted(allowed_tool_set)}"
                )

            else:
                try:
                    function_args = json.loads(raw_arguments)
                    if not isinstance(function_args, dict):
                        raise ValueError("tool arguments JSON root must be an object")
                except (json.JSONDecodeError, ValueError) as exc:
                    tool_result = (
                        f"Error: invalid tool arguments JSON: {exc}\n"
                        f"raw_arguments={raw_arguments}"
                    )
                else:
                    if echo_tools:
                        print(f"\n[tool call] {function_name}({function_args})")
                    tool_result = registry.run(function_name, function_args)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": str(tool_result),
                }
            )

    raise RuntimeError(
        "Assistant exceeded max_tool_rounds="
        f"{max_tool_rounds}. Increase options.max_tool_rounds_per_turn or narrow the task."
    )



def _is_direct_evaluation_job(job: Dict[str, Any]) -> bool:
    """Return True when the job JSON can be used directly as an evaluation config.

    Direct-evaluation jobs are top-level JSON files that contain the fields the
    evaluator already expects: task_type, objective, signals, and metrics. In
    this mode the job file itself is used as the evaluation_config source.
    """
    return (
        isinstance(job.get("task_type"), str)
        and bool(job.get("task_type", "").strip())
        and isinstance(job.get("objective"), str)
        and bool(job.get("objective", "").strip())
        and isinstance(job.get("signals"), dict)
        and bool(job.get("signals"))
        and isinstance(job.get("metrics"), list)
        and bool(job.get("metrics"))
    )


def _ensure_automation_config(ctx: ProjectContext) -> Dict[str, Any]:
    """Return a mutable automation config object on the project context."""
    automation = ctx.config.get("automation")
    if not isinstance(automation, dict):
        automation = {}
        ctx.config["automation"] = automation
    return automation

def load_job_json(job_file: Path) -> Dict[str, Any]:
    """Load and minimally validate a headless tuning job JSON file."""
    job_file = job_file.expanduser().resolve()
    if not job_file.exists():
        raise FileNotFoundError(f"job file does not exist: {job_file}")
    if not job_file.is_file():
        raise ValueError(f"job path is not a file: {job_file}")

    try:
        job = json.loads(job_file.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in job file: {job_file}\n{exc}") from exc

    if not isinstance(job, dict):
        raise ValueError("job JSON root must be an object")

    max_iterations = job.get("max_iterations", 1)
    try:
        max_iterations_int = int(max_iterations)
    except (TypeError, ValueError) as exc:
        raise ValueError("job.max_iterations must be an integer") from exc
    if max_iterations_int < 1:
        raise ValueError("job.max_iterations must be >= 1")
    job["max_iterations"] = max_iterations_int

    has_legacy_job_payload = any(
        key in job for key in ("objective_text", "structured_requirement", "evaluation_config")
    )
    has_direct_evaluation_payload = _is_direct_evaluation_job(job)
    if not has_legacy_job_payload and not has_direct_evaluation_payload:
        raise ValueError(
            "job must contain at least one legacy input field "
            "(objective_text, structured_requirement, evaluation_config), "
            "or be a direct evaluation config with non-empty "
            "task_type, objective, signals, and metrics"
        )

    if "paths" in job and not isinstance(job["paths"], dict):
        raise ValueError("job.paths must be an object when provided")
    if "options" in job and not isinstance(job["options"], dict):
        raise ValueError("job.options must be an object when provided")
    if "stop_conditions" in job and not isinstance(job["stop_conditions"], dict):
        raise ValueError("job.stop_conditions must be an object when provided")

    return job


def write_result_json(result_file: Path, result: Dict[str, Any]) -> None:
    """Write tuning_result.json with stable UTF-8 formatting."""
    result_file = result_file.expanduser().resolve()
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def stop_condition_met(evaluation_result: Dict[str, Any], stop_conditions: Dict[str, Any]) -> bool:
    """Return True when all explicitly configured stop conditions are satisfied.

    Supported keys:
      - overall_score_min
      - metric_error_count_max or max_metric_error_count
      - metric_ok_count_min
      - status_equals
    If no supported stop condition is supplied, this returns False so the job
    runs until max_iterations.
    """
    if not isinstance(evaluation_result, dict) or not evaluation_result:
        return False
    if not isinstance(stop_conditions, dict) or not stop_conditions:
        return False

    checked_any = False

    if "overall_score_min" in stop_conditions:
        checked_any = True
        try:
            actual_score = float(evaluation_result.get("overall_score"))
            required_score = float(stop_conditions["overall_score_min"])
        except (TypeError, ValueError):
            return False
        if actual_score < required_score:
            return False

    error_limit_key = None
    if "metric_error_count_max" in stop_conditions:
        error_limit_key = "metric_error_count_max"
    elif "max_metric_error_count" in stop_conditions:
        error_limit_key = "max_metric_error_count"
    if error_limit_key is not None:
        checked_any = True
        try:
            actual_error_count = int(evaluation_result.get("metric_error_count"))
            allowed_error_count = int(stop_conditions[error_limit_key])
        except (TypeError, ValueError):
            return False
        if actual_error_count > allowed_error_count:
            return False

    if "metric_ok_count_min" in stop_conditions:
        checked_any = True
        try:
            actual_ok_count = int(evaluation_result.get("metric_ok_count"))
            required_ok_count = int(stop_conditions["metric_ok_count_min"])
        except (TypeError, ValueError):
            return False
        if actual_ok_count < required_ok_count:
            return False

    if "status_equals" in stop_conditions:
        checked_any = True
        expected_status = str(stop_conditions["status_equals"])
        actual_status = str(evaluation_result.get("status"))
        if actual_status != expected_status:
            return False

    return checked_any


def _resolve_job_relative_path(job_file: Path, raw_path: Optional[str]) -> Optional[Path]:
    if not raw_path:
        return None
    path = Path(str(raw_path)).expanduser()
    if not path.is_absolute():
        path = job_file.parent / path
    return path.resolve()


def _optional_job_path_as_str(job_file: Path, raw_path: Optional[str]) -> Optional[str]:
    path = _resolve_job_relative_path(job_file, raw_path)
    return str(path) if path is not None else None


def _default_result_file(job_file: Path, job: Dict[str, Any]) -> Path:
    paths = job.get("paths") or {}
    configured = paths.get("result_file") if isinstance(paths, dict) else None
    return _resolve_job_relative_path(job_file, configured) or (job_file.parent / "tuning_result.json").resolve()


def _automation_path(ctx: ProjectContext, key: str, default: str) -> Path:
    raw_path = ctx.automation().get(key, default)
    return ctx.resolve_config_path(str(raw_path))


def _read_json_file_if_exists(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_latest_evaluation_result(ctx: ProjectContext) -> Dict[str, Any]:
    return _read_json_file_if_exists(
        _automation_path(ctx, "evaluation_result", "../log/evaluation_result.json")
    )


def _result_files(ctx: ProjectContext) -> Dict[str, str]:
    return {
        "evaluation_config": str(_automation_path(ctx, "evaluation_config", "../log/evaluation_config.json")),
        "evaluation_result": str(_automation_path(ctx, "evaluation_result", "../log/evaluation_result.json")),
        "evaluation_summary": str(_automation_path(ctx, "evaluation_summary", "../log/evaluation_summary.txt")),
        "optimization_history": str(_automation_path(ctx, "optimization_history", "../log/optimization_history.jsonl")),
        "simulation_result": str(_automation_path(ctx, "simulation_result", "../log/simulation/processed.json")),
    }


def _compact_evaluation_summary(evaluation_result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(evaluation_result, dict) or not evaluation_result:
        return {}
    keys = [
        "status",
        "task_type",
        "overall_score",
        "metric_ok_count",
        "metric_error_count",
        "warning_count",
        "error_count",
    ]
    return {key: evaluation_result.get(key) for key in keys if key in evaluation_result}


def _build_setup_prompt(job: Dict[str, Any], job_file: Path) -> str:
    options = job.get("options") or {}
    allow_unknown_metrics = bool(options.get("allow_unknown_metrics", False))
    evaluation_config = job.get("evaluation_config")

    setup_constraints = (
        "Setup-stage constraints:\n"
        "- Do not call list_project_resources.\n"
        "- Do not call list_directory.\n"
        "- Do not call read_project_file.\n"
        "- Do not call read_evaluation_result.\n"
        "- Use only the job payload below as the source of truth.\n"
        "- Call write_evaluation_config exactly once.\n"
        "- After write_evaluation_config succeeds, finish this setup step.\n"
    )

    if isinstance(evaluation_config, dict):
        instruction = (
            "The job already includes evaluation_config. Do not infer or inspect files. "
            "Call write_evaluation_config exactly once using job.evaluation_config."
        )
    else:
        instruction = (
            "The job does not include evaluation_config. Infer a valid evaluation_config from "
            "objective_text and structured_requirement, then call write_evaluation_config. "
            "Do not inspect project files, logs, directories, source code, or previous results. "
            "Do not run build, exe, Simulink, or parameter patching in this setup step."
        )

    payload = {
        "job_file": str(job_file),
        "allow_unknown_metrics": allow_unknown_metrics,
        "job": job,
    }

    return (
        f"Prepare this headless tuning job. {instruction}\n\n"
        f"{setup_constraints}\n"
        "When calling write_evaluation_config, pass allow_unknown_metrics from this payload.\n"
        f"Payload:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _get_max_params_per_update(job: Dict[str, Any]) -> int:
    """根据 candidate design_profile 的激进程度决定每轮最多可修改的参数数量。

    温度越高 → 策略越激进 → 允许一次改更多参数。
    """
    profile = job.get("design_profile")
    if isinstance(profile, dict):
        temp = profile.get("llm_temperature")
        if temp is None:
            temp = profile.get("temperature")
        if isinstance(temp, (int, float)):
            if temp <= 0.20:
                return 5    # 稳健低超调
            elif temp <= 0.30:
                return 8    # 平滑低纹波
            elif temp <= 0.40:
                return 10   # 快速响应
            else:
                return 12   # 抗扰恢复
    return 8  # 默认


def _build_iteration_prompt(
    job: Dict[str, Any],
    job_file: Path,
    iteration: int,
    max_iterations: int,
) -> str:
    paths = job.get("paths") or {}
    options = job.get("options") or {}
    stop_conditions = job.get("stop_conditions") or {}

    header_path = _optional_job_path_as_str(job_file, paths.get("header_path"))
    history_path = _optional_job_path_as_str(job_file, paths.get("history_path"))
    max_params = _get_max_params_per_update(job)

    payload = {
        "iteration": iteration,
        "max_iterations": max_iterations,
        "stop_conditions": stop_conditions,
        "tool_options": {
            "header_path": header_path,
            "history_path": history_path,
            "allow_unknown_metrics": bool(options.get("allow_unknown_metrics", False)),
            "include_traceback": bool(options.get("include_traceback", False)),
            "dry_run": bool(options.get("dry_run", False)),
            "history_limit": int(options.get("history_limit", 5)),
        },
        "job": job,
    }

    return (
        f"Run headless tuning iteration {iteration}/{max_iterations}.\n"
        "Required behavior:\n"
        "1. Call run_one_tuning_iteration exactly once. Pass header_path, history_path, "
        "allow_unknown_metrics, include_traceback, and history_limit from tool_options when present.\n"
        "2. Inspect the returned tuning context: closed_loop_success, evaluation_success, "
        "evaluation_result, current_parameters_after_run, best_score_so_far, and recent_history.\n"
        "3. If the returned evaluation already satisfies stop_conditions, do not patch parameters. Summarize why.\n"
        "4. If build/simulation/evaluation failed, do not patch parameters. Summarize the failure and next action.\n"
        "5. If parameters_rolled_back is true, the system auto-reverted to best-so-far parameters because "
        "the last update degraded the score. Study recent_history to understand which update caused the "
        "regression, then decide: same direction with smaller step, or a different approach entirely.\n"
        f"6. Otherwise, decide a batch of parameter updates. You may update up to {max_params} parameters "
        "in a single iteration. When multiple parameters share a common root cause (e.g. zero integral "
        "gain requires both KI and KP adjustment for stability), update the related set together. "
        "Do NOT limit yourself to one parameter unless the problem is truly isolated. "
        "Prioritise parameters affecting failed or low-scoring metrics first. "
        "Call apply_parameter_update_and_record. Pass dry_run, header_path, and history_path from tool_options.\n"
        "7. Finish with a concise JSON-like summary in plain text. Do not ask the user questions.\n\n"
        f"Payload:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def run_headless_job(
    job_file: Path,
    llm: LLMClient,
    registry: ToolRegistry,
    ctx: ProjectContext,
) -> int:
    """Run a tuning job JSON without interactive input and write tuning_result.json."""
    job_file = job_file.expanduser().resolve()
    job = load_job_json(job_file)
    result_file = _default_result_file(job_file, job)
    paths = job.get("paths") or {}
    options = job.get("options") or {}
    stop_conditions = job.get("stop_conditions") or {}
    max_iterations = int(job.get("max_iterations", 1))
    max_tool_rounds = int(options.get("max_tool_rounds_per_turn", DEFAULT_HEADLESS_MAX_TOOL_ROUNDS))

    use_job_file_as_evaluation_config = _is_direct_evaluation_job(job)
    if use_job_file_as_evaluation_config:
        # Direct-evaluation mode: the command-line job JSON is the evaluation config.
        # This overrides the static agent_project.json automation.evaluation_config path
        # for this run without changing the project config file on disk.
        _ensure_automation_config(ctx)["evaluation_config"] = str(job_file)

    result: Dict[str, Any] = {
        "schema_version": 1,
        "job_id": job.get("job_id"),
        "job_file": str(job_file),
        "evaluation_config_source": "job_file" if use_job_file_as_evaluation_config else "generated_or_configured",
        "status": "running",
        "stop_reason": None,
        "iterations_requested": max_iterations,
        "iterations_completed": 0,
        "result_files": _result_files(ctx),
        "rounds": [],
        "final_evaluation": {},
        "errors": [],
        "assumptions": [],
    }
    write_result_json(result_file, result)

    # ── 注入 tuning_policy.allowed_parameters 到工具层（含自动补全） ──
    # 1）从 job JSON 读取用户显式配置的白名单；
    # 2）与 paras.generated.h 中的实际参数做差集；
    # 3）缺失的参数自动补全，推断合理的 min/max 范围；
    # 4）同步注入 context.automation（工具层硬约束）和 job dict（LLM prompt）。
    tuning_policy = job.get("tuning_policy")
    if isinstance(tuning_policy, dict):
        allowed_params = tuning_policy.get("allowed_parameters")
        if isinstance(allowed_params, dict):
            allowed_params = dict(allowed_params)  # 浅拷贝，避免污染原始 job
        else:
            allowed_params = {}
    else:
        allowed_params = {}

    header_path = _resolve_job_relative_path(
        job_file,
        (paths.get("header_path") or "src/paras.generated.h"),
    )
    header_params: dict[str, Any] = {}
    if header_path and header_path.exists():
        try:
            header_params = read_tunable_parameters(header_path)
        except (ParameterHeaderError, OSError, TypeError, ValueError):
            header_params = {}

    if header_params:
        header_names = {str(k).upper() for k in header_params}
        policy_names = {str(k).upper() for k in allowed_params}
        missing = header_names - policy_names
        nonexistent = policy_names - header_names

        # ── 自动补全缺失参数 ──────────────────────────────────────
        # SPEED_LIMIT 等保护参数不加入白名单，防止 agent 误调
        _FIXED_TUNABLE = {"SPEED_LIMIT"}
        auto_added: list[str] = []
        for name in sorted(missing):
            if name in _FIXED_TUNABLE:
                continue
            original_name = name
            for hk in header_params:
                if str(hk).upper() == name:
                    original_name = str(hk)
                    break
            current_val = float(header_params.get(original_name, 1.0))
            inferred = _infer_parameter_range(original_name, current_val)
            allowed_params[original_name] = inferred
            auto_added.append(original_name)

        # ── 删除 header 中已不存在的参数 ──────────────────────────
        removed: list[str] = []
        if nonexistent:
            for name in sorted(nonexistent):
                for ak in list(allowed_params.keys()):
                    if str(ak).upper() == name:
                        del allowed_params[ak]
                        removed.append(str(ak))
                        break

        if auto_added:
            print(
                f"[headless] ⚡ auto-completed {len(auto_added)} missing tuning_policy "
                f"parameter(s): {', '.join(auto_added)}"
            )
        if removed:
            print(
                f"[headless] 🗑 removed {len(removed)} obsolete tuning_policy "
                f"parameter(s) not found in header: {', '.join(removed)}"
            )

        # 回写 job dict（LLM prompt 会看到补全后的白名单）
        if tuning_policy is not job.get("tuning_policy"):
            job["tuning_policy"] = dict(job.get("tuning_policy", {}))
        job["tuning_policy"]["allowed_parameters"] = allowed_params

        # 注入 context（工具层硬约束）
        _ensure_automation_config(ctx)["_tuning_policy_allowed_names"] = sorted(allowed_params.keys())

        # 校验结果写入 tuning_result.json
        result["tuning_policy_validation"] = {
            "status": "validated",
            "header_param_count": len(header_names),
            "header_parameters": sorted(header_names),
            "policy_param_count": len(allowed_params),
            "policy_parameters": sorted(allowed_params.keys()),
            "auto_added": auto_added,
            "removed": removed,
            "nonexistent_in_policy": sorted(nonexistent),
            "is_coverage_complete": (len(missing) == 0 or len(auto_added) == len(missing)) and len(removed) == len(nonexistent),
        }
        write_result_json(result_file, result)

    elif allowed_params:
        # header 不存在但有白名单：仍然注入，不做补全
        _ensure_automation_config(ctx)["_tuning_policy_allowed_names"] = sorted(allowed_params.keys())

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": (
                "You are running in headless automation mode. Do not ask the user questions. "
                "Use the job JSON as the complete task input. If information is missing, make the safest "
                "reasonable assumption, record the assumption in your summary, and continue if possible. "
                "Python controls the number of iterations; you control the tool decisions inside each turn."
            ),
        },
    ]

    try:
        if use_job_file_as_evaluation_config:
            result["setup_summary"] = (
                "Skipped evaluation_config setup because the job file itself contains "
                "task_type, objective, signals, and metrics. The job file is used "
                "directly as the evaluation config."
            )
            write_result_json(result_file, result)
        elif not bool(options.get("skip_evaluation_config_setup", False)):
            print("[headless] preparing evaluation_config")
            messages.append({"role": "user", "content": _build_setup_prompt(job, job_file)})
            setup_message = run_agent_turn(
                llm,
                registry,
                messages,
                max_tool_rounds=max_tool_rounds,
                echo_tools=True,
                allowed_tool_names=["write_evaluation_config"],
            )
            result["setup_summary"] = setup_message.get("content")
            write_result_json(result_file, result)

        for iteration in range(1, max_iterations + 1):
            print(f"[headless] starting iteration {iteration}/{max_iterations}")
            messages.append(
                {
                    "role": "user",
                    "content": _build_iteration_prompt(job, job_file, iteration, max_iterations),
                }
            )
            # 最后一轮迭代不允许修改参数——改了也没机会验证，坏参数会被继承
            iteration_tools = ["run_one_tuning_iteration"]
            if iteration < max_iterations:
                iteration_tools.append("apply_parameter_update_and_record")

            final_message = run_agent_turn(
                llm,
                registry,
                messages,
                max_tool_rounds=max_tool_rounds,
                echo_tools=True,
                allowed_tool_names=iteration_tools,
            )

            latest_evaluation = _load_latest_evaluation_result(ctx)
            compact_evaluation = _compact_evaluation_summary(latest_evaluation)
            round_record = {
                "iteration": iteration,
                "assistant_summary": final_message.get("content"),
                "evaluation": compact_evaluation,
            }
            result["rounds"].append(round_record)
            result["iterations_completed"] = iteration
            result["final_evaluation"] = compact_evaluation

            if stop_condition_met(latest_evaluation, stop_conditions):
                result["status"] = "stopped_by_success"
                result["stop_reason"] = "stop_conditions_met"
                write_result_json(result_file, result)
                print(f"[headless] stop conditions met after iteration {iteration}")
                return 0

            write_result_json(result_file, result)

        result["status"] = "completed"
        result["stop_reason"] = "max_iterations_reached"
        result["final_evaluation"] = _compact_evaluation_summary(_load_latest_evaluation_result(ctx))
        write_result_json(result_file, result)
        print(f"[headless] completed {max_iterations} iteration(s). result={result_file}")
        return 0

    except Exception as exc:
        result["status"] = "failed"
        result["stop_reason"] = "exception"
        result["errors"].append(
            {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        try:
            result["final_evaluation"] = _compact_evaluation_summary(_load_latest_evaluation_result(ctx))
            write_result_json(result_file, result)
        except Exception:
            pass
        print(f"[headless] failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


def interactive_loop(llm: LLMClient, registry: ToolRegistry) -> None:
    print("Motor Agent started. Type exit to quit.")
    print("Try: list available project resources")
    print("Try: run one closed-loop build and simulation")
    print("Try: read simulation_result and summarize its JSON structure")
    print("Try: build solution")
    print("Try: start exe")
    print("Try: run simulink simulation")
    print("Try: list project_src")

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    while True:
        user_input = input("\nUser> ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Agent exited.")
            break
        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            assistant_dict = run_agent_turn(
                llm,
                registry,
                messages,
                max_tool_rounds=DEFAULT_HEADLESS_MAX_TOOL_ROUNDS,
                echo_tools=True,
            )
        except Exception as exc:
            print(f"\nAgent> Error: {type(exc).__name__}: {exc}")
            continue

        print(f"\nAgent> {assistant_dict.get('content')}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Motor tuning agent")
    parser.add_argument(
        "--job-file",
        help="Path to tuning_job.json. When provided, run in headless automation mode.",
    )
    args = parser.parse_args(argv)

    try:
        ctx = load_project_context()
        llm = LLMClient(ctx)
        registry = build_registry(ctx)

        if args.job_file:
            return run_headless_job(
                job_file=Path(args.job_file),
                llm=llm,
                registry=registry,
                ctx=ctx,
            )

        interactive_loop(llm, registry)
        return 0
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
