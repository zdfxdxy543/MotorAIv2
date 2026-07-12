"""
evaluator.py

Evaluation executor for the GMP parameter-iteration agent.

Responsibilities:
1. Read evaluation_config.json and processed.json.
2. Use schemas.py, signal_loader.py, and metrics.py.
3. Dispatch each MetricConfig.metric_name to the corresponding deterministic
   metric function.
4. Support target_value and target_signal.
5. Support derived_signals. First version supports only numerical_derivative.
6. Record per-metric failures without aborting the whole evaluation.
7. Return a plain JSON-serializable dict. No LLM or agent logic is included.

Python version: 3.12+
Dependencies: standard library only
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
import json
import traceback

try:  # Package usage: agent_core.evaluation.evaluator
    from .schemas import (
        EvaluationConfig,
        EvaluationConfigError,
        MetricConfig,
        SUPPORTED_METRIC_NAMES,
        load_evaluation_config_from_json,
        validate_evaluation_config,
    )
    from .signal_loader import (
        SignalSeries,
        SignalLoaderError,
        SignalNotFoundError,
        load_mapped_signals,
    )
    from . import metrics
    from .scoring import add_scores_to_evaluation_result, ScoringError
except ImportError:  # Direct local debugging usage from this directory.
    from schemas import (  # type: ignore[no-redef]
        EvaluationConfig,
        EvaluationConfigError,
        MetricConfig,
        SUPPORTED_METRIC_NAMES,
        load_evaluation_config_from_json,
        validate_evaluation_config,
    )
    from signal_loader import (  # type: ignore[no-redef]
        SignalSeries,
        SignalLoaderError,
        SignalNotFoundError,
        load_mapped_signals,
    )
    import metrics  # type: ignore[no-redef]
    from scoring import add_scores_to_evaluation_result, ScoringError  # type: ignore[no-redef]


class EvaluatorError(Exception):
    """Base exception for evaluator-level errors."""


class DerivedSignalError(EvaluatorError):
    """Raised when a derived signal cannot be created."""


# Metric names that are directly implemented in metrics.py and return scalar
# values. numerical_derivative is handled separately because it returns a signal.
_BASE_METRIC_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "final_value": metrics.final_value,
    "peak_value": metrics.peak_value,
    "min_value": metrics.min_value,
    "peak_to_peak": metrics.peak_to_peak,
    "mean_absolute_error": metrics.mean_absolute_error,
    "rms_error": metrics.rms_error,
    "steady_state_error": metrics.steady_state_error,
    "overshoot": metrics.overshoot,
    "rise_time": metrics.rise_time,
    "settling_time": metrics.settling_time,
    "ripple": metrics.ripple,
    "zero_crossing_count": metrics.zero_crossing_count,
    "linear_fit_r2": metrics.linear_fit_r2,
    "response_delay": metrics.response_delay,
    "stability": metrics.stability,
    "numerical_derivative": metrics.numerical_derivative,
}

# Semantic aliases make agent-generated configs easier to read while keeping
# metrics.py small and deterministic.
_METRIC_ALIASES: dict[str, str] = {
    "final_speed_error": "steady_state_error",
    "final_position_error": "steady_state_error",
    "speed_overshoot": "overshoot",
    "iq_response_overshoot": "overshoot",
    "id_deviation": "mean_absolute_error",
    "oscillation_score": "zero_crossing_count",
    "acceleration_tracking_error": "rms_error",
    "velocity_curve_linearity": "linear_fit_r2",
    "current_smoothness": "ripple",
    "current_cost": "rms_error",
    "energy_or_current_cost": "rms_error",
}

_ALLOWED_CONFIG_METRIC_NAMES: set[str] = (
    set(SUPPORTED_METRIC_NAMES)
    | set(_BASE_METRIC_FUNCTIONS.keys())
    | set(_METRIC_ALIASES.keys())
)

# Units are intentionally simple. They describe the metric output, not the
# signal's physical unit.
_METRIC_UNITS: dict[str, str] = {
    "final_value": "value",
    "peak_value": "value",
    "min_value": "value",
    "peak_to_peak": "value",
    "mean_absolute_error": "value",
    "rms_error": "value",
    "steady_state_error": "value",
    "overshoot": "ratio",
    "rise_time": "s",
    "settling_time": "s",
    "ripple": "value",
    "zero_crossing_count": "count",
    "linear_fit_r2": "ratio",
    "response_delay": "s",
    "stability": "value",
    "numerical_derivative": "signal",
}

# Some semantic aliases are normally interpreted relative to zero when the
# config does not explicitly provide target_value or target_signal.
_ZERO_TARGET_ALIASES: set[str] = {
    "final_speed_error",
    "id_deviation",
    "oscillation_score",
    "current_cost",
    "energy_or_current_cost",
}


_TARGET_REQUIRED_METRICS: set[str] = {
    "mean_absolute_error",
    "rms_error",
    "steady_state_error",
    "response_delay",
}


_WINDOW_METRICS: set[str] = {
    "steady_state_error",
    "ripple",
    "stability",
}


_TOLERANCE_METRICS: set[str] = {
    "settling_time",
    "response_delay",
}


_REFERENCE_METRICS: set[str] = {
    "zero_crossing_count",
}


_RATIO_EXTRA_FIELDS: dict[str, tuple[str, ...]] = {
    "rise_time": ("lower_ratio", "upper_ratio"),
    "settling_time": ("tolerance_ratio",),
    "steady_state_error": ("window_ratio",),
    "ripple": ("window_ratio",),
    "response_delay": ("threshold_ratio",),
    "stability": ("window_ratio",),
}


_WINDOW_EXTRA_FIELDS: tuple[str, ...] = ("window_size",)


def evaluate_simulation(
    processed_json_path: str | Path,
    evaluation_config_path: str | Path,
    *,
    strict_metric_names: bool = True,
    include_traceback: bool = False,
) -> dict[str, Any]:
    """
    Evaluate one simulation run and return a JSON-serializable result dict.

    Args:
        processed_json_path:
            Path to processed.json produced by the simulation pipeline.

        evaluation_config_path:
            Path to evaluation_config.json generated by the agent or by a user.

        strict_metric_names:
            Passed to validate_evaluation_config(). In normal use this should
            stay True.

        include_traceback:
            If True, include Python tracebacks in error entries. This is useful
            for debugging but should usually be False in agent-facing output.

    Returns:
        Dict containing status, metric results, warnings, and errors.

    Notes:
        Config loading, config validation, and signal loading errors are treated
        as global failures because no reliable metric evaluation can proceed.
        Individual metric failures are recorded per metric and do not stop later
        metrics from running.
    """
    processed_path = Path(processed_json_path)
    config_path = Path(evaluation_config_path)

    result: dict[str, Any] = _new_result(processed_path, config_path)

    try:
        config = load_evaluation_config_from_json(config_path)
        validate_evaluation_config(
            config,
            allowed_metric_names=_ALLOWED_CONFIG_METRIC_NAMES,
            strict_metric_names=strict_metric_names,
        )
        mapped_signals = load_mapped_signals(processed_path, config)
    except (EvaluationConfigError, SignalLoaderError, OSError, ValueError) as exc:
        result["status"] = "failed"
        result["errors"].append(_error_entry("global", exc, include_traceback=include_traceback))
        return result

    result["task_type"] = config.task_type
    result["objective"] = config.objective
    result["configured_signal_count"] = len(config.signals)
    result["configured_metric_count"] = len(config.metrics)
    result["signals"] = _summarize_signals(mapped_signals)

    _apply_derived_signals(
        config=config,
        signals=mapped_signals,
        result=result,
        include_traceback=include_traceback,
    )

    used_result_keys: set[str] = set()
    for index, metric_config in enumerate(config.metrics):
        metric_result = _evaluate_one_metric(
            metric_config=metric_config,
            index=index,
            signals=mapped_signals,
            include_traceback=include_traceback,
        )
        key = _metric_result_key(metric_config, index=index, used_keys=used_result_keys)
        result["metrics"][key] = metric_result
        if metric_result.get("status") == "error":
            result["errors"].append(
                {
                    "stage": "metric",
                    "metric_key": key,
                    "metric_name": metric_config.metric_name,
                    "message": metric_result.get("error", "metric evaluation failed"),
                }
            )

    result["metric_ok_count"] = sum(
        1 for item in result["metrics"].values() if item.get("status") == "ok"
    )
    result["metric_error_count"] = sum(
        1 for item in result["metrics"].values() if item.get("status") == "error"
    )

    if result["errors"]:
        result["status"] = "partial" if result["metric_ok_count"] > 0 else "failed"
    else:
        result["status"] = "ok"

    return _add_scores_safely(result)


def evaluate_simulation_from_config(
    processed_json_path: str | Path,
    config: EvaluationConfig,
    *,
    strict_metric_names: bool = True,
    include_traceback: bool = False,
) -> dict[str, Any]:
    """
    Evaluate using an already loaded EvaluationConfig object.

    This helper is useful for unit tests and for future agent tools that have
    just generated a config in memory. It has the same behavior as
    evaluate_simulation(), except that no config file is read.
    """
    processed_path = Path(processed_json_path)
    result = _new_result(processed_path, evaluation_config_path=None)

    try:
        validate_evaluation_config(
            config,
            allowed_metric_names=_ALLOWED_CONFIG_METRIC_NAMES,
            strict_metric_names=strict_metric_names,
        )
        mapped_signals = load_mapped_signals(processed_path, config)
    except (EvaluationConfigError, SignalLoaderError, OSError, ValueError) as exc:
        result["status"] = "failed"
        result["errors"].append(_error_entry("global", exc, include_traceback=include_traceback))
        return result

    result["task_type"] = config.task_type
    result["objective"] = config.objective
    result["configured_signal_count"] = len(config.signals)
    result["configured_metric_count"] = len(config.metrics)
    result["signals"] = _summarize_signals(mapped_signals)

    _apply_derived_signals(
        config=config,
        signals=mapped_signals,
        result=result,
        include_traceback=include_traceback,
    )

    used_result_keys: set[str] = set()
    for index, metric_config in enumerate(config.metrics):
        metric_result = _evaluate_one_metric(
            metric_config=metric_config,
            index=index,
            signals=mapped_signals,
            include_traceback=include_traceback,
        )
        key = _metric_result_key(metric_config, index=index, used_keys=used_result_keys)
        result["metrics"][key] = metric_result
        if metric_result.get("status") == "error":
            result["errors"].append(
                {
                    "stage": "metric",
                    "metric_key": key,
                    "metric_name": metric_config.metric_name,
                    "message": metric_result.get("error", "metric evaluation failed"),
                }
            )

    result["metric_ok_count"] = sum(
        1 for item in result["metrics"].values() if item.get("status") == "ok"
    )
    result["metric_error_count"] = sum(
        1 for item in result["metrics"].values() if item.get("status") == "error"
    )
    result["status"] = "partial" if result["errors"] else "ok"
    if result["errors"] and result["metric_ok_count"] == 0:
        result["status"] = "failed"
    return _add_scores_safely(result)


def write_evaluation_result(result: Mapping[str, Any], output_path: str | Path) -> None:
    """Write an evaluation result dict as UTF-8 JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")




def _add_scores_safely(result: dict[str, Any]) -> dict[str, Any]:
    """Attach overall_score when scoring.py can score the metric results.

    Scoring is intentionally best-effort: invalid or missing thresholds should
    not invalidate the deterministic metric results produced by evaluator.py.
    """
    try:
        return add_scores_to_evaluation_result(result)
    except ScoringError as exc:
        result.setdefault("warnings", []).append(f"scoring skipped: {type(exc).__name__}: {exc}")
        result.setdefault("overall_score", None)
        result.setdefault("min_metric_score", None)
        result.setdefault("scoring_summary", {
            "overall_score": None,
            "min_metric_score": None,
            "scored_metric_count": 0,
            "skipped_metric_count": 0,
            "total_score_weight": 0.0,
            "error": f"{type(exc).__name__}: {exc}",
        })
        return result

def _new_result(
    processed_json_path: Path,
    evaluation_config_path: Path | None,
) -> dict[str, Any]:
    return {
        "status": "not_run",
        "task_type": None,
        "objective": None,
        "processed_json_path": str(processed_json_path),
        "evaluation_config_path": str(evaluation_config_path) if evaluation_config_path is not None else None,
        "configured_signal_count": 0,
        "configured_metric_count": 0,
        "signals": {},
        "derived_signals": {},
        "metrics": {},
        "metric_ok_count": 0,
        "metric_error_count": 0,
        "warnings": [],
        "errors": [],
    }


def _apply_derived_signals(
    *,
    config: EvaluationConfig,
    signals: dict[str, Any],
    result: dict[str, Any],
    include_traceback: bool,
) -> None:
    for index, spec in enumerate(config.derived_signals):
        try:
            derived_signal = _build_derived_signal(spec, signals=signals, index=index)
            signals[derived_signal.name] = derived_signal
            result["derived_signals"][derived_signal.name] = _summarize_signal(derived_signal)
        except Exception as exc:  # Deliberately keep later metrics running.
            error = _error_entry(
                stage=f"derived_signals[{index}]",
                exc=exc,
                include_traceback=include_traceback,
            )
            result["errors"].append(error)
            result["warnings"].append(
                f"failed to build derived signal at index {index}: {error['message']}"
            )


def _build_derived_signal(
    spec: Mapping[str, Any],
    *,
    signals: Mapping[str, Any],
    index: int,
) -> Any:
    if not isinstance(spec, Mapping):
        raise DerivedSignalError(f"derived_signals[{index}] must be an object/dict.")

    name = _get_non_empty_string(spec, "name", f"derived_signals[{index}]")
    method = _get_non_empty_string(spec, "method", f"derived_signals[{index}]")

    # Accept several common source-field names to make configs less brittle.
    source_name = (
        spec.get("from")
        or spec.get("source")
        or spec.get("source_signal")
        or spec.get("input_signal")
    )
    if not isinstance(source_name, str) or not source_name.strip():
        raise DerivedSignalError(
            f"derived_signals[{index}] must define a non-empty source field: "
            "'from', 'source', 'source_signal', or 'input_signal'."
        )
    source_name = source_name.strip()

    if source_name not in signals:
        available = ", ".join(sorted(signals.keys()))
        raise DerivedSignalError(
            f"derived signal {name!r} depends on missing signal {source_name!r}. "
            f"Available signals: [{available}]"
        )

    if method != "numerical_derivative":
        raise DerivedSignalError(
            f"derived signal {name!r} uses unsupported method {method!r}. "
            "First version supports only 'numerical_derivative'."
        )

    return metrics.numerical_derivative(signals[source_name], name=name)


def _evaluate_one_metric(
    *,
    metric_config: MetricConfig,
    index: int,
    signals: Mapping[str, Any],
    include_traceback: bool,
) -> dict[str, Any]:
    original_metric_name = metric_config.metric_name
    resolved_metric_name = _resolve_metric_name(original_metric_name)

    base_result: dict[str, Any] = {
        "status": "not_run",
        "metric_name": original_metric_name,
        "resolved_metric_name": resolved_metric_name,
        "metric_index": index,
        "signal": metric_config.signal,
        "target_signal": metric_config.target_signal,
        "target_value": metric_config.target_value,
        "weight": metric_config.weight,
        "optimization_direction": metric_config.optimization_direction,
        "unit": _METRIC_UNITS.get(resolved_metric_name, "value"),
        "extra": dict(metric_config.extra),
    }

    try:
        if resolved_metric_name not in _BASE_METRIC_FUNCTIONS:
            raise EvaluatorError(f"unsupported metric_name: {original_metric_name!r}")

        if metric_config.signal not in signals:
            available = ", ".join(sorted(signals.keys()))
            raise SignalNotFoundError(
                f"metric {original_metric_name!r} requires signal {metric_config.signal!r}, "
                f"but it is not available. Available signals: [{available}]"
            )

        signal = signals[metric_config.signal]
        target = _resolve_target(metric_config, resolved_metric_name, original_metric_name, signal, signals)
        kwargs = _metric_kwargs(metric_config, resolved_metric_name, target)
        value = _BASE_METRIC_FUNCTIONS[resolved_metric_name](signal, **kwargs)

        base_result["status"] = "ok"
        base_result["value"] = _json_safe_value(value)
        if target is not _NO_TARGET:
            base_result["target_summary"] = _target_summary(target)
        return base_result

    except Exception as exc:
        base_result["status"] = "error"
        base_result["error"] = f"{type(exc).__name__}: {exc}"
        if include_traceback:
            base_result["traceback"] = traceback.format_exc()
        return base_result


def _resolve_metric_name(metric_name: str) -> str:
    return _METRIC_ALIASES.get(metric_name, metric_name)


_NO_TARGET = object()


def _resolve_target(
    metric_config: MetricConfig,
    resolved_metric_name: str,
    original_metric_name: str,
    signal: Any,
    signals: Mapping[str, Any],
) -> Any:
    if metric_config.target_signal is not None:
        if metric_config.target_signal not in signals:
            available = ", ".join(sorted(signals.keys()))
            raise SignalNotFoundError(
                f"target_signal {metric_config.target_signal!r} is not available. "
                f"Available signals: [{available}]"
            )
        return signals[metric_config.target_signal]

    if metric_config.target_value is not None:
        return metric_config.target_value

    # Semantic defaults. These only apply when the agent used a semantic alias.
    if original_metric_name in _ZERO_TARGET_ALIASES:
        return 0.0

    if original_metric_name == "final_position_error":
        values = getattr(signal, "values", None)
        if not values:
            raise EvaluatorError(
                "final_position_error has no explicit target and the signal has no initial sample."
            )
        return values[0]

    if resolved_metric_name in _TARGET_REQUIRED_METRICS:
        raise EvaluatorError(
            f"metric {original_metric_name!r} requires either target_value or target_signal."
        )

    return _NO_TARGET


def _metric_kwargs(metric_config: MetricConfig, resolved_metric_name: str, target: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}

    if target is not _NO_TARGET:
        if resolved_metric_name in _REFERENCE_METRICS:
            kwargs["reference"] = target
        else:
            kwargs["target"] = target

    if resolved_metric_name in _TOLERANCE_METRICS and metric_config.tolerance is not None:
        kwargs["tolerance"] = metric_config.tolerance

    if resolved_metric_name in _WINDOW_METRICS:
        if metric_config.window is not None:
            if isinstance(metric_config.window, int):
                kwargs["window_size"] = metric_config.window
            elif isinstance(metric_config.window, float):
                kwargs["window_ratio"] = metric_config.window
            else:
                raise EvaluatorError(
                    f"metric {metric_config.metric_name!r} has unsupported window value "
                    f"{metric_config.window!r}; expected int window_size or float window_ratio."
                )

    extra = dict(metric_config.extra)
    for field_name in _RATIO_EXTRA_FIELDS.get(resolved_metric_name, ()):  # lower_ratio, etc.
        if field_name in extra:
            kwargs[field_name] = extra[field_name]

    for field_name in _WINDOW_EXTRA_FIELDS:
        if field_name in extra and resolved_metric_name in _WINDOW_METRICS:
            kwargs[field_name] = extra[field_name]

    if resolved_metric_name == "overshoot" and "normalize" in extra:
        kwargs["normalize"] = extra["normalize"]

    if resolved_metric_name == "stability":
        if "include_bias" in extra:
            kwargs["include_bias"] = extra["include_bias"]
        if "normalize" in extra:
            kwargs["normalize"] = extra["normalize"]

    return kwargs


def _metric_result_key(
    metric_config: MetricConfig,
    *,
    index: int,
    used_keys: set[str],
) -> str:
    explicit = metric_config.extra.get("result_name") if isinstance(metric_config.extra, dict) else None
    base = explicit if isinstance(explicit, str) and explicit.strip() else metric_config.metric_name
    base = base.strip()

    key = base
    if key not in used_keys:
        used_keys.add(key)
        return key

    suffix = 2
    while f"{base}#{suffix}" in used_keys:
        suffix += 1
    key = f"{base}#{suffix}"
    used_keys.add(key)
    return key


def _summarize_signals(signals: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {name: _summarize_signal(signal) for name, signal in signals.items()}


def _summarize_signal(signal: Any) -> dict[str, Any]:
    time_values = list(getattr(signal, "time", []) or [])
    values = list(getattr(signal, "values", []) or [])
    summary: dict[str, Any] = {
        "name": getattr(signal, "name", None),
        "source_name": getattr(signal, "source_name", None),
        "sample_count": len(values),
        "source_scope": getattr(signal, "source_scope", None),
        "source_channel": getattr(signal, "source_channel", None),
    }
    if time_values:
        summary["time_start"] = time_values[0]
        summary["time_end"] = time_values[-1]
    if values:
        summary["value_first"] = values[0]
        summary["value_last"] = values[-1]
        summary["value_min"] = min(values)
        summary["value_max"] = max(values)
    return summary


def _target_summary(target: Any) -> dict[str, Any]:
    if target is _NO_TARGET:
        return {"type": "none"}
    if isinstance(target, (int, float)) and not isinstance(target, bool):
        return {"type": "scalar", "value": float(target)}
    if hasattr(target, "values"):
        return {
            "type": "signal",
            "name": getattr(target, "name", None),
            "source_name": getattr(target, "source_name", None),
            "sample_count": len(getattr(target, "values", []) or []),
        }
    if isinstance(target, list):
        return {"type": "list", "length": len(target)}
    return {"type": type(target).__name__, "repr": repr(target)}


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _compact_signal_dict(value.to_dict())
    if is_dataclass(value):
        return _json_safe_value(asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _json_safe_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(v) for v in value]
    return repr(value)


def _compact_signal_dict(signal_dict: Mapping[str, Any]) -> dict[str, Any]:
    # Do not dump long derived-signal arrays into metric value by default.
    time_values = list(signal_dict.get("time") or [])
    values = list(signal_dict.get("values") or [])
    compact: dict[str, Any] = {
        "name": signal_dict.get("name"),
        "source_name": signal_dict.get("source_name"),
        "sample_count": len(values),
        "source_scope": signal_dict.get("source_scope"),
        "source_channel": signal_dict.get("source_channel"),
    }
    if time_values:
        compact["time_start"] = time_values[0]
        compact["time_end"] = time_values[-1]
    if values:
        compact["value_first"] = values[0]
        compact["value_last"] = values[-1]
        compact["value_min"] = min(values)
        compact["value_max"] = max(values)
    return compact


def _get_non_empty_string(spec: Mapping[str, Any], key: str, prefix: str) -> str:
    value = spec.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DerivedSignalError(f"{prefix}.{key} must be a non-empty string.")
    return value.strip()


def _error_entry(stage: str, exc: Exception, *, include_traceback: bool) -> dict[str, Any]:
    entry = {
        "stage": stage,
        "type": type(exc).__name__,
        "message": str(exc),
    }
    if include_traceback:
        entry["traceback"] = traceback.format_exc()
    return entry


def _main() -> int:
    """Command-line evaluator for manual debugging.

    Example:
        python -m agent_core.evaluation.evaluator \
          --processed-json ../log/processed.json \
          --evaluation-config ../log/evaluation_config.json \
          --output ../log/evaluation_result.json
    """
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate GMP simulation metrics.")
    parser.add_argument("--processed-json", required=True, help="Path to processed.json")
    parser.add_argument("--evaluation-config", required=True, help="Path to evaluation_config.json")
    parser.add_argument("--output", help="Optional path to write evaluation_result.json")
    parser.add_argument(
        "--allow-unknown-metrics",
        action="store_true",
        help="Disable strict metric-name validation. Unknown metrics still fail during dispatch.",
    )
    parser.add_argument(
        "--traceback",
        action="store_true",
        help="Include Python tracebacks in error entries.",
    )
    args = parser.parse_args()

    result = evaluate_simulation(
        processed_json_path=args.processed_json,
        evaluation_config_path=args.evaluation_config,
        strict_metric_names=not args.allow_unknown_metrics,
        include_traceback=args.traceback,
    )

    if args.output:
        write_evaluation_result(result, args.output)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result.get("status") in {"ok", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = [
    "EvaluatorError",
    "DerivedSignalError",
    "evaluate_simulation",
    "evaluate_simulation_from_config",
    "write_evaluation_result",
]
