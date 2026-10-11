from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

try:
    import matlab.engine
except ImportError:
    matlab = None

try:
    from .sil_session import run_matlab_job
except ImportError:
    from sil_session import run_matlab_job

class LocalSimulinkRunner:
    """Run a local Simulink model and collect diagnostics plus scope signals."""

    def __init__(self, matlab_session_name: Optional[str] = None, *, force_batch: bool = False):
        self.eng = None
        self.session_name = "batch"
        if force_batch:
            return
        sessions = matlab.engine.find_matlab() if matlab is not None else []
        if not sessions and not matlab_session_name:
            return

        if matlab_session_name:
            if matlab_session_name not in sessions:
                raise RuntimeError(
                    f"Requested MATLAB session '{matlab_session_name}' not found. Available: {sessions}"
                )
            target_session = matlab_session_name
        else:
            target_session = sessions[0]

        self.session_name = target_session
        self.eng = matlab.engine.connect_matlab(target_session)

    def run_model(
        self,
        model_path: str,
        scope_channel_map: Dict[str, List[str]],
        scope_vars: Optional[List[str]] = None,
        open_model_ui: bool = True,
        gmp_root: Optional[str] = None,
        network_config: Optional[Dict[str, Any]] = None,
        expected_connection_id: Optional[str] = None,
        timeout_sec: int = 1800,
    ) -> Dict[str, Any]:
        result = run_matlab_job(
            model_path, action="run", gmp_root=gmp_root, network=network_config,
            scope_vars=list(scope_vars or scope_channel_map),
            expected_connection_id=expected_connection_id, timeout_sec=timeout_sec,
            engine=self.eng,
            open_model_ui=open_model_ui,
        )
        raw_scopes = result.get("raw_scopes", {})
        for payload in raw_scopes.values():
            if isinstance(payload, dict) and "error" in payload:
                payload["_error"] = payload["error"]
        signals, errors = self._merge_scope_signals(raw_scopes, scope_channel_map)
        result.update(signals=signals, scope_mapping_errors=errors)
        result["diagnostics"]["matlab_session"] = self.session_name
        return result

    def _merge_scope_signals(
        self,
        raw_scopes: Dict[str, Any],
        scope_channel_map: Dict[str, List[str]],
    ) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
        merged: Dict[str, Dict[str, Any]] = {}
        errors: List[str] = []

        for scope_name, scope_obj in raw_scopes.items():
            if isinstance(scope_obj, dict) and scope_obj.get("_error"):
                errors.append(f"{scope_name}: {scope_obj['_error']}")
                continue

            channels = self._extract_channels(scope_obj)
            if not channels:
                errors.append(f"{scope_name}: no channel data found")
                continue

            semantic_names = scope_channel_map.get(scope_name, [])
            for idx, channel in enumerate(channels):
                if idx < len(semantic_names) and semantic_names[idx]:
                    signal_name = semantic_names[idx]
                else:
                    signal_name = f"{scope_name}.ch{idx + 1}"

                signal_name = self._dedupe_key(merged, signal_name)
                merged[signal_name] = {
                    "time": channel["time"],
                    "values": channel["values"],
                    "source_scope": scope_name,
                    "source_channel": channel["label"],
                }

        return merged, errors

    def _extract_channels(self, scope_obj: Any) -> List[Dict[str, Any]]:
        if not isinstance(scope_obj, dict):
            return []

        time_axis = self._to_1d(scope_obj.get("time", []))
        signals = scope_obj.get("signals")

        if signals is None:
            value_matrix = self._to_2d(scope_obj.get("value", []))
            return self._columns_to_channels(value_matrix, time_axis, "CH")

        if isinstance(signals, dict):
            signals = [signals]
        if not isinstance(signals, list):
            return []

        channels: List[Dict[str, Any]] = []
        for item in signals:
            if not isinstance(item, dict):
                continue

            label = str(item.get("label") or item.get("blockName") or "CH")
            value_matrix = self._to_2d(item.get("values", []))
            if not value_matrix:
                continue

            # Common Scope shape: one signal entry with Nx2 values.
            if len(signals) == 1 and len(value_matrix[0]) > 1:
                channels.extend(self._columns_to_channels(value_matrix, time_axis, label))
            elif len(value_matrix[0]) > 1:
                channels.extend(self._columns_to_channels(value_matrix, time_axis, label))
            else:
                values = [row[0] for row in value_matrix]
                channels.append({"label": label, "time": time_axis, "values": values})

        return channels

    @staticmethod
    def _columns_to_channels(
        matrix: List[List[float]], time_axis: List[float], label_prefix: str
    ) -> List[Dict[str, Any]]:
        if not matrix:
            return []

        cols = len(matrix[0])
        channels: List[Dict[str, Any]] = []
        for c in range(cols):
            values = [row[c] for row in matrix]
            channels.append(
                {
                    "label": f"{label_prefix}{c + 1}",
                    "time": time_axis,
                    "values": values,
                }
            )
        return channels

    @staticmethod
    def _to_1d(data: Any) -> List[float]:
        if data is None:
            return []
        if isinstance(data, list):
            if data and isinstance(data[0], list):
                return [LocalSimulinkRunner._to_float(row[0]) for row in data if row]
            return [LocalSimulinkRunner._to_float(v) for v in data]
        return [LocalSimulinkRunner._to_float(data)]

    @staticmethod
    def _to_2d(data: Any) -> List[List[float]]:
        if data is None:
            return []
        if isinstance(data, list):
            if not data:
                return []
            if isinstance(data[0], list):
                return [[LocalSimulinkRunner._to_float(v) for v in row] for row in data]
            return [[LocalSimulinkRunner._to_float(v)] for v in data]
        return [[LocalSimulinkRunner._to_float(data)]]

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except Exception:
            return 0.0

    @staticmethod
    def _dedupe_key(container: Dict[str, Any], base: str) -> str:
        if base not in container:
            return base
        idx = 2
        while f"{base}_{idx}" in container:
            idx += 1
        return f"{base}_{idx}"

    @staticmethod
    def _trim_text(text: Any, max_len: int = 20000) -> str:
        if text is None:
            return ""
        text = str(text)
        if len(text) <= max_len:
            return text
        return text[:max_len] + "\n...<truncated>..."
