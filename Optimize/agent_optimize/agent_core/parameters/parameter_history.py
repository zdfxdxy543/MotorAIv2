"""Optimization history utilities for the GMP parameter tuning agent.

This module stores one optimization iteration per JSON Lines record.
It is intentionally lightweight and independent from LLM/tool code.

Typical output file:
    tools/agent/log/optimization_history.jsonl

Public API:
    append_optimization_history(path, record) -> None
    read_optimization_history(path, limit=10) -> list[dict]

Optional helpers are provided for convenience, but callers may ignore them.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

PathLike = Union[str, Path]
Record = Dict[str, Any]


class ParameterHistoryError(Exception):
    """Base exception for optimization history errors."""


class InvalidHistoryRecordError(ParameterHistoryError):
    """Raised when a history record cannot be validated or serialized."""


def _as_path(path: PathLike) -> Path:
    if isinstance(path, Path):
        return path
    if isinstance(path, str) and path.strip():
        return Path(path)
    raise ParameterHistoryError("history path must be a non-empty str or pathlib.Path")


def _now_iso() -> str:
    # Keep local timezone information if the host has it configured.
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _safe_float(value: Any) -> Optional[float]:
    """Convert value to finite float when possible, otherwise return None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
        return number if math.isfinite(number) else None
    return None


def extract_overall_score(evaluation_result: Any) -> Optional[float]:
    """Extract an overall score from common evaluation_result shapes.

    Supported examples:
        {"overall_score": 86.5}
        {"overall_score": {"value": 86.5}}
        {"summary": {"overall_score": 86.5}}
        {"scoring": {"overall_score": 86.5}}
        {"score": 86.5}

    Returns None when no finite score is found.
    """
    if not isinstance(evaluation_result, dict):
        return None

    direct_keys = ("overall_score", "score")
    for key in direct_keys:
        if key in evaluation_result:
            value = evaluation_result[key]
            if isinstance(value, dict):
                score = _safe_float(value.get("value"))
            else:
                score = _safe_float(value)
            if score is not None:
                return score

    nested_keys = ("summary", "scoring", "score_summary", "evaluation_summary")
    for key in nested_keys:
        nested = evaluation_result.get(key)
        if isinstance(nested, dict):
            score = extract_overall_score(nested)
            if score is not None:
                return score

    return None


def _validate_optional_dict(record: Record, key: str) -> None:
    if key in record and record[key] is not None and not isinstance(record[key], dict):
        raise InvalidHistoryRecordError(f"record['{key}'] must be a dict when provided")


def _validate_record(record: Record) -> None:
    if not isinstance(record, dict):
        raise InvalidHistoryRecordError("history record must be a dict")

    _validate_optional_dict(record, "parameters_before")
    _validate_optional_dict(record, "parameters_after")
    _validate_optional_dict(record, "evaluation_result")
    _validate_optional_dict(record, "parameter_updates")

    if "iteration" in record:
        iteration = record["iteration"]
        if isinstance(iteration, bool) or not isinstance(iteration, int) or iteration < 1:
            raise InvalidHistoryRecordError("record['iteration'] must be a positive integer")

    if "agent_reason" in record and record["agent_reason"] is not None:
        if not isinstance(record["agent_reason"], str):
            raise InvalidHistoryRecordError("record['agent_reason'] must be a string when provided")

    if "simulation_success" in record and record["simulation_success"] is not None:
        if not isinstance(record["simulation_success"], bool):
            raise InvalidHistoryRecordError("record['simulation_success'] must be a bool when provided")


def _load_all_records(path: Path) -> List[Record]:
    if not path.exists():
        return []
    if not path.is_file():
        raise ParameterHistoryError(f"history path is not a file: {path}")

    records: List[Record] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ParameterHistoryError(
                    f"invalid JSON in history file {path} at line {line_no}: {exc}"
                ) from exc
            if not isinstance(value, dict):
                raise ParameterHistoryError(
                    f"invalid history record at line {line_no}: expected JSON object"
                )
            records.append(value)
    return records


def get_next_iteration(path: PathLike) -> int:
    """Return the next iteration number for a history file."""
    history_path = _as_path(path)
    records = _load_all_records(history_path)
    max_iteration = 0
    for item in records:
        iteration = item.get("iteration")
        if isinstance(iteration, int) and not isinstance(iteration, bool):
            max_iteration = max(max_iteration, iteration)
    return max_iteration + 1


def _find_previous_score(records: Iterable[Record]) -> Optional[float]:
    for item in reversed(list(records)):
        if "overall_score" in item:
            score = _safe_float(item.get("overall_score"))
            if score is not None:
                return score
        score = extract_overall_score(item.get("evaluation_result"))
        if score is not None:
            return score
    return None


def _find_best_score(records: Iterable[Record]) -> Optional[float]:
    """Return the best (highest) overall_score across all history records.

    This is used as the correct baseline for determining whether the current
    iteration truly improved the objective, as opposed to _find_previous_score
    which returns the last record's score (which may be a rolled-back failure).
    """
    best: Optional[float] = None
    for item in records:
        score: Optional[float] = None
        if "overall_score" in item:
            score = _safe_float(item.get("overall_score"))
        if score is None:
            score = extract_overall_score(item.get("evaluation_result"))
        if score is not None:
            if best is None or score > best:
                best = score
    return best


def normalize_history_record(path: PathLike, record: Record) -> Record:
    """Return a validated copy of *record* with useful fields completed.

    Added when missing:
        - iteration
        - timestamp
        - overall_score
        - previous_overall_score
        - overall_score_delta
        - overall_score_improved
        - best_score_so_far

    * overall_score_improved compares against the **best** score across all
      existing records (not just the immediately preceding record), so that
      a post-rollback attempt is correctly judged against the all-time best.
    * previous_overall_score still records the immediate predecessor, which
      is useful for trend analysis even when rollback occurred.

    The input record is not mutated.
    """
    history_path = _as_path(path)
    normalized = deepcopy(record)
    _validate_record(normalized)

    existing_records = _load_all_records(history_path)

    if "iteration" not in normalized:
        normalized["iteration"] = get_next_iteration(history_path)

    if not normalized.get("timestamp"):
        normalized["timestamp"] = _now_iso()

    current_score = normalized.get("overall_score")
    current_score_float = _safe_float(current_score)
    if current_score_float is None:
        current_score_float = extract_overall_score(normalized.get("evaluation_result"))

    previous_score = _find_previous_score(existing_records)
    best_score = _find_best_score(existing_records)

    if current_score_float is not None:
        normalized["overall_score"] = current_score_float

    if previous_score is not None:
        normalized["previous_overall_score"] = previous_score

    # ── 评分改善判断：与历史最佳分比较，而非仅与上一条记录 ──────
    # 这样可以防止"回退后下次尝试比烂分好就误判为进步"的问题。
    if current_score_float is not None and best_score is not None:
        normalized["best_score_so_far"] = best_score
        normalized["overall_score_improved"] = current_score_float > best_score
        # delta 仍相对于上一条记录，方便 trace 趋势
        if previous_score is not None:
            normalized["overall_score_delta"] = current_score_float - previous_score
    elif current_score_float is not None and previous_score is not None:
        # 第一条有分数的记录：没有 best_score，回退到跟 previous 比
        normalized["best_score_so_far"] = current_score_float
        normalized["overall_score_delta"] = current_score_float - previous_score
        normalized["overall_score_improved"] = current_score_float > previous_score
    elif "overall_score_improved" not in normalized:
        normalized["overall_score_improved"] = None
        if current_score_float is not None:
            # 第一个记录：自身就是最佳
            normalized["best_score_so_far"] = current_score_float

    return normalized


def append_optimization_history(path: PathLike, record: Record) -> None:
    """Append one optimization iteration record to a JSONL history file.

    Args:
        path: Target JSONL path, usually tools/agent/log/optimization_history.jsonl.
        record: JSON-serializable dict. Common fields:
            - iteration: optional positive int; auto-filled when missing.
            - parameters_before: dict
            - parameters_after: dict
            - evaluation_result: dict
            - agent_reason: str
            - simulation_success: bool
            - timestamp: optional; auto-filled when missing.

    Raises:
        ParameterHistoryError / InvalidHistoryRecordError on invalid input.
    """
    history_path = _as_path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    normalized = normalize_history_record(history_path, record)

    try:
        line = json.dumps(normalized, ensure_ascii=False, default=_json_default)
    except (TypeError, ValueError) as exc:
        raise InvalidHistoryRecordError(f"history record is not JSON serializable: {exc}") from exc

    with history_path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(line)
        f.write("\n")


def read_optimization_history(path: PathLike, limit: int = 10) -> List[Record]:
    """Read optimization history records.

    Args:
        path: JSONL history file path.
        limit: Number of latest records to return. Use limit <= 0 to return all records.

    Returns:
        A list of dict records in chronological order.
        Missing file returns an empty list.
    """
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ParameterHistoryError("limit must be an integer")

    history_path = _as_path(path)
    records = _load_all_records(history_path)
    if limit <= 0:
        return records
    return records[-limit:]


def get_latest_history_record(path: PathLike) -> Optional[Record]:
    """Return the latest record, or None if history does not exist."""
    records = read_optimization_history(path, limit=1)
    return records[0] if records else None


def build_history_record(
    *,
    parameters_before: Optional[Dict[str, Any]] = None,
    parameters_after: Optional[Dict[str, Any]] = None,
    evaluation_result: Optional[Dict[str, Any]] = None,
    agent_reason: str = "",
    simulation_success: Optional[bool] = None,
    parameter_updates: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Record:
    """Build a standard history record dict for callers/tools.

    This helper does not write anything; pass the returned dict to
    append_optimization_history().
    """
    record: Record = {
        "parameters_before": parameters_before or {},
        "parameters_after": parameters_after or {},
        "evaluation_result": evaluation_result or {},
        "agent_reason": agent_reason,
    }
    if simulation_success is not None:
        record["simulation_success"] = simulation_success
    if parameter_updates is not None:
        record["parameter_updates"] = parameter_updates
    if extra:
        record.update(extra)
    return record


def summarize_optimization_history(path: PathLike, limit: int = 10) -> Dict[str, Any]:
    """Return a small summary of recent optimization history."""
    records = read_optimization_history(path, limit=limit)
    scores: List[float] = []
    for item in records:
        score = _safe_float(item.get("overall_score"))
        if score is None:
            score = extract_overall_score(item.get("evaluation_result"))
        if score is not None:
            scores.append(score)

    return {
        "record_count": len(records),
        "first_iteration": records[0].get("iteration") if records else None,
        "latest_iteration": records[-1].get("iteration") if records else None,
        "latest_record": records[-1] if records else None,
        "scores": scores,
        "best_score": max(scores) if scores else None,
        "latest_score": scores[-1] if scores else None,
        "latest_score_delta": records[-1].get("overall_score_delta") if records else None,
        "latest_score_improved": records[-1].get("overall_score_improved") if records else None,
    }


__all__ = [
    "ParameterHistoryError",
    "InvalidHistoryRecordError",
    "append_optimization_history",
    "read_optimization_history",
    "get_latest_history_record",
    "get_next_iteration",
    "extract_overall_score",
    "normalize_history_record",
    "build_history_record",
    "summarize_optimization_history",
]
