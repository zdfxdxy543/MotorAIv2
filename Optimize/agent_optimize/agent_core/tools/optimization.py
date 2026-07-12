"""
optimization.py

Agent tool adapters for lightweight GMP parameter tuning orchestration.

This module is intentionally a *tool orchestration layer*, not an optimizer.
It connects already implemented deterministic modules:

1. automation tools: build/start exe/run Simulink closed loop
2. evaluation tools: processed.json + evaluation_config.json -> evaluation_result.json
3. parameter header editor: read and patch paras.generated.h
4. parameter history: append/read optimization_history.jsonl

Important design rule:
    Python does not decide PID/current/slope updates by itself.
    The agent should call run_one_tuning_iteration first, inspect the returned
    evaluation result/current parameters/history, decide parameter updates, then
    call apply_parameter_update_and_record.

Python version: 3.10+
Dependencies: standard library only
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from ..config import ProjectContext
from ..constants import DEFAULT_MAX_CHARS
from ..evaluation.result_writer import write_json_result
from ..parameters.parameter_header_editor import (
    ParameterHeaderError,
    patch_tunable_parameters as patch_header_parameters,
    read_tunable_parameters as read_header_parameters,
)
from ..parameters.parameter_history import (
    ParameterHistoryError,
    append_optimization_history,
    build_history_record,
    read_optimization_history,
    summarize_optimization_history,
)
from ..tool_registry import ToolRegistry
from ..utils import read_text_if_exists, truncate_text
from .automation import AutomationTools
from .evaluation import EvaluationTools


# LADRC signature parameter names. When both are present in the header, the
# agent is restricted to the LADRC allowlist so it cannot accidentally modify
# datasheet constants or safety limits that should stay fixed.
_LADRC_SIGNATURE = {"TARGET_WC", "TARGET_WO"}

# Parameters the agent is allowed to tune in LADRC mode.
_LADRC_TUNABLE: set[str] = {
    "TARGET_WC",
    "TARGET_WO",
    "CUR_LIMIT",
    "INERTIA",
    "TORQUE_CONST",
    "SPEED_SLOPE_LIMIT",
}

# SMC signature parameter names.
_SMC_SIGNATURE = {"TARGET_BW", "DIST_REJECT_TORQUE"}

# Parameters the agent is allowed to tune in SMC mode.
_SMC_TUNABLE: set[str] = {
    "TARGET_BW",
    "DIST_REJECT_TORQUE",
    "CUR_LIMIT",
    "INERTIA",
    "TORQUE_CONST",
}


def _detect_tunable_allowlist(all_params: dict[str, Any]) -> set[str] | None:
    """Return an allowlist based on controller type, or None to allow all.

    None means "allow all" — the caller should not filter.
    """
    names = {str(k).upper() for k in all_params}
    if _LADRC_SIGNATURE.issubset(names):
        return {n for n in _LADRC_TUNABLE if n in names}
    if _SMC_SIGNATURE.issubset(names):
        return {n for n in _SMC_TUNABLE if n in names}
    return None


def _get_effective_allowlist(
    ctx: Any,
    header_params: dict[str, Any],
) -> set[str] | None:
    """Merge controller-type allowlist with tuning_policy.allowed_parameters.

    Layered enforcement:
    1. Controller-type allowlist (LADRC / SMC) — always enforced when applicable.
    2. tuning_policy.allowed_parameters from the job JSON — enforced on top,
       including for PID where the controller allowlist is None.

    Returns:
        A set of allowed parameter names (upper-cased), or None to allow all.
    """
    controller_allowlist = _detect_tunable_allowlist(header_params)

    # ── read tuning_policy.allowed_parameters from context ──────────
    policy_names: list[str] | None = None
    try:
        auto = getattr(ctx, "automation", None)
        if callable(auto):
            policy_names = auto().get("_tuning_policy_allowed_names")
    except Exception:
        policy_names = None

    if not policy_names:
        # No tuning_policy configured — fall back to controller-only behaviour.
        return controller_allowlist

    policy_set = {str(n).upper() for n in policy_names}
    header_names = {str(k).upper() for k in header_params}
    policy_effective = policy_set & header_names  # only names that actually exist

    if controller_allowlist is None:
        # PID / unknown controller: tuning_policy is the only restriction.
        return policy_effective

    # LADRC / SMC: intersection of both restrictions.
    return controller_allowlist & policy_effective


def validate_tuning_policy_coverage(
    header_path: Path | str,
    ctx: Any,
) -> dict[str, Any]:
    """Compare header parameters against tuning_policy.allowed_parameters.

    Call this after the header file exists and tuning_policy has been injected
    into the context.  Returns a structured report that can be logged into
    tuning_result.json so operators can spot whitelist gaps without digging
    through agent transcripts.

    When no tuning_policy is configured the function returns a no-op result
    (backward-compatible).
    """
    header_params: dict[str, Any] = {}
    try:
        header_params = read_header_parameters(Path(header_path))
    except (ParameterHeaderError, OSError, TypeError, ValueError) as exc:
        return {
            "status": "skipped",
            "reason": f"cannot read header: {exc}",
            "is_coverage_complete": None,
        }

    header_names = {str(k).upper() for k in header_params}

    # ── resolve tuning_policy names from context ──────────────────────
    policy_names_raw: list[str] | None = None
    try:
        auto = getattr(ctx, "automation", None)
        if callable(auto):
            policy_names_raw = auto().get("_tuning_policy_allowed_names")
    except Exception:
        policy_names_raw = None

    if not policy_names_raw:
        return {
            "status": "no_policy",
            "reason": "tuning_policy.allowed_parameters not configured — all header parameters are tunable.",
            "header_param_count": len(header_names),
            "header_parameters": sorted(header_names),
            "is_coverage_complete": True,
        }

    policy_names = {str(n).upper() for n in policy_names_raw}
    untunable = header_names - policy_names
    nonexistent = policy_names - header_names

    return {
        "status": "validated",
        "header_param_count": len(header_names),
        "header_parameters": sorted(header_names),
        "policy_param_count": len(policy_names),
        "policy_parameters": sorted(policy_names),
        "untunable_parameters": sorted(untunable),
        "nonexistent_in_policy": sorted(nonexistent),
        "is_coverage_complete": len(untunable) == 0,
    }


class OptimizationTools:
    """LLM-callable tools for one-step tuning orchestration.

    The class is deliberately conservative. It provides:
        - run_one_tuning_iteration: build/sim/evaluate/read context
        - apply_parameter_update_and_record: patch header and append history
        - read_optimization_history_summary: inspect recent history

    It does not implement an autonomous numeric optimizer. That choice keeps
    parameter strategy inside the agent, while deterministic file operations
    stay inside Python.
    """

    HEADER_PATH_KEYS = (
        "parameter_header",
        "tunable_parameter_header",
        "tunable_params_header",
        "paras_header",
        "paras_generated_header",
    )

    HISTORY_PATH_KEYS = (
        "optimization_history",
        "optimization_history_path",
        "parameter_history",
        "tuning_history",
    )

    def __init__(self, ctx: ProjectContext) -> None:
        self.ctx = ctx
        self.automation_tools = AutomationTools(ctx)
        self.evaluation_tools = EvaluationTools(ctx)
        self._best_score: float | None = None
        self._best_parameters: dict[str, Any] | None = None

    def _automation(self) -> Dict[str, Any]:
        return self.ctx.automation()

    def _path_from_automation(self, key: str, default: str) -> Path:
        raw_path = self._automation().get(key, default)
        return self.ctx.resolve_config_path(str(raw_path))

    def _evaluation_result_path(self) -> Path:
        return self._path_from_automation("evaluation_result", "../log/evaluation_result.json")

    def _optimization_history_path(self, raw_path: Optional[str] = None) -> Path:
        if isinstance(raw_path, str) and raw_path.strip():
            return self.ctx.resolve_config_path(raw_path.strip())

        for key in self.HISTORY_PATH_KEYS:
            value = self._automation().get(key)
            if isinstance(value, str) and value.strip():
                return self.ctx.resolve_config_path(value.strip())

        resources = self.ctx.resources()
        for key in self.HISTORY_PATH_KEYS:
            item = resources.get(key)
            if isinstance(item, dict):
                value = item.get("path")
                if isinstance(value, str) and value.strip():
                    return Path(value).expanduser().resolve()

        return self.ctx.resolve_config_path("../log/optimization_history.jsonl")

    def _resolve_header_path(self, raw_path: Optional[str] = None) -> Path:
        if isinstance(raw_path, str) and raw_path.strip():
            return self.ctx.resolve_config_path(raw_path.strip())

        for key in self.HEADER_PATH_KEYS:
            value = self._automation().get(key)
            if isinstance(value, str) and value.strip():
                return self.ctx.resolve_config_path(value.strip())

        resources = self.ctx.resources()
        for key in self.HEADER_PATH_KEYS:
            item = resources.get(key)
            if isinstance(item, dict):
                value = item.get("path")
                if isinstance(value, str) and value.strip():
                    return Path(value).expanduser().resolve()

        accepted = ", ".join(self.HEADER_PATH_KEYS)
        raise ValueError(
            "Missing parameter header path. Provide 'header_path', or configure one of "
            f"these agent_project.json automation/resources keys: {accepted}."
        )

    @staticmethod
    def _json_dumps(data: Any) -> str:
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)

    @staticmethod
    def _load_json_file(path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        if not path.is_file():
            raise ValueError(f"path is not a file: {path}")
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"JSON root must be an object: {path}")
        return data

    @staticmethod
    def _is_error_text(text: str) -> bool:
        stripped = text.lstrip()
        return stripped.startswith("Error:") or stripped.startswith("Closed loop stopped")

    @staticmethod
    def _is_ok_text(text: str) -> bool:
        return text.lstrip().startswith("OK:")

    def run_one_tuning_iteration(
        self,
        *,
        header_path: Optional[str] = None,
        evaluation_config_path: Optional[str] = None,
        allow_unknown_metrics: bool = False,
        include_traceback: bool = False,
        history_path: Optional[str] = None,
        history_limit: int = 5,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> str:
        """Run build/simulation/evaluation and return tuning context.

        This tool does not patch parameters. After this call, the agent should
        inspect evaluation_result/current_parameters/recent_history, decide an
        update, then call apply_parameter_update_and_record.
        """
        try:
            resolved_header_path = self._resolve_header_path(header_path)
            resolved_history_path = self._optimization_history_path(history_path)
        except (OSError, ValueError) as exc:
            return f"Error: failed to resolve tuning paths. {type(exc).__name__}: {exc}"

        context: Dict[str, Any] = {
            "status": "unknown",
            "stage": "start",
            "header_path": str(resolved_header_path),
            "evaluation_config_path": str(Path(evaluation_config_path).expanduser().resolve()) if evaluation_config_path else None,
            "optimization_history_path": str(resolved_history_path),
            "closed_loop_success": False,
            "evaluation_success": False,
            "simulation_success": False,
        }

        # Read parameters before running, so even failed runs report current state.
        try:
            all_params = read_header_parameters(resolved_header_path)
            tunable_allowlist = _get_effective_allowlist(self.ctx, all_params)
            context["current_parameters_before_run"] = (
                {k: v for k, v in all_params.items() if tunable_allowlist is None or k in tunable_allowlist}
                if tunable_allowlist is not None
                else all_params
            )
            context["_tunable_allowlist"] = sorted(tunable_allowlist) if tunable_allowlist is not None else None
        except (ParameterHeaderError, OSError, TypeError, ValueError) as exc:
            return f"Error: failed to read current tunable parameters. {type(exc).__name__}: {exc}"

        closed_loop_result = self.automation_tools.run_closed_loop_once()
        context["stage"] = "closed_loop"
        context["closed_loop_result"] = truncate_text(closed_loop_result, max_chars)
        context["closed_loop_success"] = self._is_ok_text(closed_loop_result)
        context["simulation_success"] = context["closed_loop_success"]

        if not context["closed_loop_success"]:
            context["status"] = "closed_loop_failed"
            context["next_action"] = (
                "Do not patch parameters yet. Inspect build/simulation logs, fix the run, "
                "then call run_one_tuning_iteration again."
            )
            return self._json_dumps(context)

        evaluation_result_text = self.evaluation_tools.evaluate_simulation_result(
            evaluation_config_path=evaluation_config_path,
            allow_unknown_metrics=allow_unknown_metrics,
            include_traceback=include_traceback,
            summary_max_chars=min(max_chars, 8000),
        )
        context["stage"] = "evaluation"
        context["evaluation_tool_result"] = truncate_text(evaluation_result_text, max_chars)
        context["evaluation_success"] = not self._is_error_text(evaluation_result_text)

        evaluation_result_path = self._evaluation_result_path()
        context["evaluation_result_path"] = str(evaluation_result_path)

        try:
            evaluation_result = self._load_json_file(evaluation_result_path)
            context["evaluation_result"] = evaluation_result
            context["overall_score"] = evaluation_result.get("overall_score")
            context["metric_ok_count"] = evaluation_result.get("metric_ok_count")
            context["metric_error_count"] = evaluation_result.get("metric_error_count")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            context["evaluation_result_read_error"] = f"{type(exc).__name__}: {exc}"
            context["evaluation_result"] = {}

        # ── 最佳分数追踪 & 自动回退 ──────────────────────────────────────
        current_score = context.get("overall_score")
        if isinstance(current_score, (int, float)) and current_score is not None:
            if self._best_score is None or current_score > self._best_score:
                # 新的最佳：记录参数快照
                self._best_score = float(current_score)
                self._best_parameters = dict(all_params)
                context["best_score_so_far"] = self._best_score
                context["parameters_rolled_back"] = False
            elif current_score < self._best_score:
                # 评分退化：回退头文件到最佳参数
                context["best_score_so_far"] = self._best_score
                context["score_degraded"] = True
                context["score_delta_from_best"] = round(current_score - self._best_score, 4)
                if self._best_parameters is not None:
                    try:
                        patch_header_parameters(
                            resolved_header_path,
                            self._best_parameters,
                            backup=False,
                            dry_run=False,
                            allowed_names=None,
                        )
                    except Exception as exc:
                        context["rollback_error"] = f"{type(exc).__name__}: {exc}"
                        context["parameters_rolled_back"] = False
                    else:
                        context["parameters_rolled_back"] = True
                        context["rollback_warning"] = (
                            f"⚠️ 本轮评分 {current_score:.1f} 低于历史最佳 {self._best_score:.1f}"
                            f"（Δ = {current_score - self._best_score:.1f}），"
                            "参数已自动回退到最佳状态。\n"
                            "刚才的修改已记录在 recent_history 中，请注意：\n"
                            "  - 可能是方向正确但步子太大 → 尝试更小幅度的同方向调整\n"
                            "  - 也可能是方向本身有问题 → 尝试调整其他参数或换一个方向\n"
                            "请根据 history 中记录的 parameter_updates 判断属于哪种情况。"
                        )
            else:
                # 分数持平
                context["best_score_so_far"] = self._best_score
                context["parameters_rolled_back"] = False
        else:
            # 仿真失败或无有效分数：不更新最佳记录，也不回退
            context["best_score_so_far"] = self._best_score
            context["parameters_rolled_back"] = False

        try:
            all_after = read_header_parameters(resolved_header_path)
            tunable_allowlist = _get_effective_allowlist(self.ctx, all_after)
            context["current_parameters_after_run"] = (
                {k: v for k, v in all_after.items() if tunable_allowlist is None or k in tunable_allowlist}
                if tunable_allowlist is not None
                else all_after
            )
        except (ParameterHeaderError, OSError, TypeError, ValueError) as exc:
            context["parameter_read_after_run_error"] = f"{type(exc).__name__}: {exc}"

        try:
            context["recent_history"] = read_optimization_history(resolved_history_path, limit=history_limit)
            context["history_summary"] = summarize_optimization_history(resolved_history_path, limit=history_limit)
        except ParameterHistoryError as exc:
            context["history_read_error"] = f"{type(exc).__name__}: {exc}"

        context["status"] = "ok" if context["evaluation_success"] else "evaluation_failed"
        if context.get("parameters_rolled_back"):
            context["next_action"] = (
                "Parameters were rolled back because this iteration degraded the score. "
                "Inspect recent_history to see which update caused the regression. "
                "Consider: (1) same direction but smaller step, or (2) adjust a different "
                "parameter. Then call apply_parameter_update_and_record."
            )
        else:
            context["next_action"] = (
                "Analyze evaluation_result, current_parameters_after_run, and recent_history. "
                "If a parameter update is justified, call apply_parameter_update_and_record with "
                "the proposed numeric updates and a concise agent_reason."
            )
        return self._json_dumps(context)

    def apply_parameter_update_and_record(
        self,
        *,
        updates: Mapping[str, Any],
        agent_reason: str,
        header_path: Optional[str] = None,
        history_path: Optional[str] = None,
        simulation_success: bool = True,
        backup: bool = True,
        dry_run: bool = False,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> str:
        """Patch parameters according to agent decision and append history.

        This should be called after run_one_tuning_iteration. It reads the latest
        evaluation_result.json and records before/after parameters plus the
        agent's reason into optimization_history.jsonl.
        """
        if not isinstance(updates, Mapping):
            return (
                "Error: apply_parameter_update_and_record expects 'updates' to be an object/dict, "
                f"got {type(updates).__name__}."
            )
        if not updates:
            return "Error: updates must not be empty."
        if not isinstance(agent_reason, str) or not agent_reason.strip():
            return "Error: agent_reason must be a non-empty string."

        try:
            resolved_header_path = self._resolve_header_path(header_path)
            resolved_history_path = self._optimization_history_path(history_path)
            evaluation_result_path = self._evaluation_result_path()

            parameters_before = read_header_parameters(resolved_header_path)
            tunable_allowlist = _get_effective_allowlist(self.ctx, parameters_before)
            evaluation_result = self._load_json_file(evaluation_result_path)

            patch_result = patch_header_parameters(
                resolved_header_path,
                updates,
                backup=backup,
                dry_run=dry_run,
                allowed_names=tunable_allowlist,
            )

            parameters_after = read_header_parameters(resolved_header_path)

            record = build_history_record(
                parameters_before=parameters_before,
                parameters_after=parameters_after,
                evaluation_result=evaluation_result,
                agent_reason=agent_reason.strip(),
                simulation_success=bool(simulation_success),
                parameter_updates=dict(updates),
                extra={
                    "header_path": str(resolved_header_path),
                    "evaluation_result_path": str(evaluation_result_path),
                    "patch_result": patch_result,
                    "dry_run": bool(dry_run),
                },
            )

            if not dry_run:
                append_optimization_history(resolved_history_path, record)

            history_summary = summarize_optimization_history(resolved_history_path, limit=5)

        except (ParameterHeaderError, ParameterHistoryError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return f"Error: failed to apply parameter update. {type(exc).__name__}: {exc}"

        result = {
            "status": "ok",
            "dry_run": bool(dry_run),
            "history_written": not bool(dry_run),
            "header_path": str(resolved_header_path),
            "optimization_history_path": str(resolved_history_path),
            "evaluation_result_path": str(evaluation_result_path),
            "updated_parameter_names": sorted(dict(updates).keys()),
            "parameters_before_selected": {name: parameters_before.get(name) for name in updates.keys()},
            "parameters_after_selected": {name: parameters_after.get(name) for name in updates.keys()},
            "patch_result": patch_result,
            "history_record": record,
            "history_summary": history_summary,
            "next_action": (
                "Run run_one_tuning_iteration again to build, simulate, evaluate, and determine "
                "whether this update improved the objective."
            ),
        }
        return truncate_text(self._json_dumps(result), max_chars)

    def read_optimization_history_summary(
        self,
        *,
        history_path: Optional[str] = None,
        limit: int = 10,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> str:
        """Read recent tuning history and a compact summary."""
        try:
            resolved_history_path = self._optimization_history_path(history_path)
            records = read_optimization_history(resolved_history_path, limit=limit)
            summary = summarize_optimization_history(resolved_history_path, limit=limit)
        except (ParameterHistoryError, OSError, ValueError) as exc:
            return f"Error: failed to read optimization history. {type(exc).__name__}: {exc}"

        result = {
            "status": "ok",
            "optimization_history_path": str(resolved_history_path),
            "limit": limit,
            "summary": summary,
            "records": records,
        }
        return truncate_text(self._json_dumps(result), max_chars)

    def export_tuning_context_snapshot(
        self,
        *,
        output_path: Optional[str] = None,
        header_path: Optional[str] = None,
        history_path: Optional[str] = None,
        history_limit: int = 10,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> str:
        """Write a compact snapshot of current parameters/evaluation/history.

        This is optional but useful before asking the agent to reason about the
        next update. It does not run simulation or patch files.
        """
        try:
            resolved_header_path = self._resolve_header_path(header_path)
            resolved_history_path = self._optimization_history_path(history_path)
            evaluation_result_path = self._evaluation_result_path()
            if output_path:
                resolved_output_path = self.ctx.resolve_config_path(output_path)
            else:
                resolved_output_path = self.ctx.resolve_config_path("../log/tuning_context_snapshot.json")

            all_params = read_header_parameters(resolved_header_path)
            tunable_allowlist = _get_effective_allowlist(self.ctx, all_params)

            snapshot = {
                "status": "ok",
                "header_path": str(resolved_header_path),
                "evaluation_result_path": str(evaluation_result_path),
                "optimization_history_path": str(resolved_history_path),
                "current_parameters": (
                    {k: v for k, v in all_params.items() if tunable_allowlist is None or k in tunable_allowlist}
                    if tunable_allowlist is not None
                    else all_params
                ),
                "_tunable_allowlist": sorted(tunable_allowlist) if tunable_allowlist is not None else None,
                "evaluation_result": self._load_json_file(evaluation_result_path),
                "recent_history": read_optimization_history(resolved_history_path, limit=history_limit),
                "history_summary": summarize_optimization_history(resolved_history_path, limit=history_limit),
            }
            write_json_result(snapshot, resolved_output_path)
        except (ParameterHeaderError, ParameterHistoryError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            return f"Error: failed to export tuning context snapshot. {type(exc).__name__}: {exc}"

        return truncate_text(
            self._json_dumps(
                {
                    "status": "ok",
                    "snapshot_path": str(resolved_output_path),
                    "snapshot": snapshot,
                }
            ),
            max_chars,
        )


def register_optimization_tools(registry: ToolRegistry, ctx: ProjectContext) -> OptimizationTools:
    tool = OptimizationTools(ctx)

    registry.register(
        "run_one_tuning_iteration",
        {
            "type": "function",
            "function": {
                "name": "run_one_tuning_iteration",
                "description": (
                    "Run one closed-loop build/simulation, evaluate processed.json with evaluation_config.json, "
                    "then return latest evaluation_result, current tunable parameters, and recent optimization history. "
                    "This tool does not modify parameters; use it before deciding the next parameter update."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "header_path": {
                            "type": "string",
                            "description": "Optional path to paras.generated.h. If omitted, use agent_project.json automation/resources default.",
                        },
                        "evaluation_config_path": {
                            "type": "string",
                            "description": "Optional path to main/evaluation JSON. If omitted, use the configured automation.evaluation_config path.",
                        },
                        "allow_unknown_metrics": {
                            "type": "boolean",
                            "description": "Optional. Default false. Passed to evaluate_simulation_result.",
                        },
                        "include_traceback": {
                            "type": "boolean",
                            "description": "Optional. Default false. Include Python traceback in evaluation errors.",
                        },
                        "history_path": {
                            "type": "string",
                            "description": "Optional path to optimization_history.jsonl. Default ../log/optimization_history.jsonl.",
                        },
                        "history_limit": {
                            "type": "integer",
                            "description": "Optional. Number of recent history records to return. Default 5.",
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Optional. Maximum characters in returned JSON text. Default 20000.",
                        },
                    },
                },
            },
        },
        lambda args: tool.run_one_tuning_iteration(
            header_path=args.get("header_path"),
            evaluation_config_path=args.get("evaluation_config_path"),
            allow_unknown_metrics=bool(args.get("allow_unknown_metrics", False)),
            include_traceback=bool(args.get("include_traceback", False)),
            history_path=args.get("history_path"),
            history_limit=int(args.get("history_limit", 5)),
            max_chars=int(args.get("max_chars", DEFAULT_MAX_CHARS)),
        ),
    )

    registry.register(
        "apply_parameter_update_and_record",
        {
            "type": "function",
            "function": {
                "name": "apply_parameter_update_and_record",
                "description": (
                    "Patch numeric parameters in paras.generated.h according to the agent's decision, "
                    "then append one record to optimization_history.jsonl. Call this after analyzing "
                    "run_one_tuning_iteration output."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "updates": {
                            "type": "object",
                            "description": "Parameter updates, e.g. {\"VEL_KP\": 4.5, \"CUR_LIMIT\": 0.25}. Names must already exist in the header.",
                        },
                        "agent_reason": {
                            "type": "string",
                            "description": "Concise reason for this parameter update based on evaluation_result.",
                        },
                        "header_path": {
                            "type": "string",
                            "description": "Optional path to paras.generated.h. If omitted, use configured default.",
                        },
                        "history_path": {
                            "type": "string",
                            "description": "Optional path to optimization_history.jsonl. Default ../log/optimization_history.jsonl.",
                        },
                        "simulation_success": {
                            "type": "boolean",
                            "description": "Whether the preceding simulation succeeded. Default true.",
                        },
                        "backup": {
                            "type": "boolean",
                            "description": "Optional. Default true. Create header backup before patching.",
                        },
                        "dry_run": {
                            "type": "boolean",
                            "description": "Optional. Default false. If true, verify patch but do not write history.",
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Optional. Maximum characters returned. Default 20000.",
                        },
                    },
                    "required": ["updates", "agent_reason"],
                },
            },
        },
        lambda args: tool.apply_parameter_update_and_record(
            updates=args["updates"],
            agent_reason=args["agent_reason"],
            header_path=args.get("header_path"),
            history_path=args.get("history_path"),
            simulation_success=bool(args.get("simulation_success", True)),
            backup=bool(args.get("backup", True)),
            dry_run=bool(args.get("dry_run", False)),
            max_chars=int(args.get("max_chars", DEFAULT_MAX_CHARS)),
        ),
    )

    registry.register(
        "read_optimization_history_summary",
        {
            "type": "function",
            "function": {
                "name": "read_optimization_history_summary",
                "description": "Read recent records from optimization_history.jsonl and return a compact summary.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "history_path": {
                            "type": "string",
                            "description": "Optional path to optimization_history.jsonl. Default ../log/optimization_history.jsonl.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Optional. Number of recent records. Default 10.",
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Optional. Maximum characters returned. Default 20000.",
                        },
                    },
                },
            },
        },
        lambda args: tool.read_optimization_history_summary(
            history_path=args.get("history_path"),
            limit=int(args.get("limit", 10)),
            max_chars=int(args.get("max_chars", DEFAULT_MAX_CHARS)),
        ),
    )

    registry.register(
        "export_tuning_context_snapshot",
        {
            "type": "function",
            "function": {
                "name": "export_tuning_context_snapshot",
                "description": (
                    "Export current parameters, latest evaluation_result, and recent optimization history "
                    "to ../log/tuning_context_snapshot.json without running simulation or modifying parameters."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "output_path": {
                            "type": "string",
                            "description": "Optional output JSON path. Default ../log/tuning_context_snapshot.json.",
                        },
                        "header_path": {
                            "type": "string",
                            "description": "Optional path to paras.generated.h. If omitted, use configured default.",
                        },
                        "history_path": {
                            "type": "string",
                            "description": "Optional path to optimization_history.jsonl. Default ../log/optimization_history.jsonl.",
                        },
                        "history_limit": {
                            "type": "integer",
                            "description": "Optional. Number of recent history records to include. Default 10.",
                        },
                        "max_chars": {
                            "type": "integer",
                            "description": "Optional. Maximum characters returned. Default 20000.",
                        },
                    },
                },
            },
        },
        lambda args: tool.export_tuning_context_snapshot(
            output_path=args.get("output_path"),
            header_path=args.get("header_path"),
            history_path=args.get("history_path"),
            history_limit=int(args.get("history_limit", 10)),
            max_chars=int(args.get("max_chars", DEFAULT_MAX_CHARS)),
        ),
    )

    return tool


__all__ = [
    "OptimizationTools",
    "register_optimization_tools",
    "validate_tuning_policy_coverage",
    "_get_effective_allowlist",
]
