"""
Parse driver board .h files to extract MY_BOARD_* macro values.

Handles:
  - String values:   "MONKEY TREASURE"
  - Float values:    (18.0f)
  - Int/enum values: (1) or (SENSOR_TYPE_SHUNT)
"""

import re
import os
from typing import Optional, Union

# Match: #define MY_BOARD_XXX value  (value is either "string" or (numeric))
_RE_DEFINE = re.compile(
    r'^\s*#define\s+(MY_BOARD_\w+)\s+(.+?)(?:\s*//.*)?$',
    re.MULTILINE,
)

# Numeric value inside parentheses: (18.0f), (1), (SENSOR_NONE)
_RE_NUMERIC = re.compile(r'^\((.+)\)$')

# Enum name like SENSOR_TYPE_SHUNT → resolve to int if known
_ENUM_MAP = {
    "SENSOR_NONE": 0,
    "SENSOR_TYPE_SHUNT": 1,
    "SENSOR_TYPE_HALL": 2,
    "SENSOR_TYPE_DIRECT": 3,
    "CS_TOPOLOGY_LOW_SIDE": 1,
    "CS_TOPOLOGY_HIGH_SIDE": 2,
    "CS_TOPOLOGY_INLINE": 3,
    "VS_TYPE_NONE": 0,
    "VS_TYPE_PHASE_GND": 1,
    "VS_TYPE_LINE_LINE": 2,
    "THERMAL_SENSOR_NTC": 1,
    "THERMAL_SENSOR_PTC": 2,
    "THERMAL_SENSOR_IC": 3,
}

_RE_FLOAT_SUFFIX = re.compile(r'(\d+\.?\d*(?:[eE][+-]?\d+)?)f')


def _strip_f(expr: str) -> str:
    return _RE_FLOAT_SUFFIX.sub(r'\1', expr)


def _try_eval_numeric(expr: str) -> Optional[float]:
    """Evaluate a simple numeric expression like `0.4 / 2.0`."""
    try:
        cleaned = _strip_f(expr)
        if not re.match(r'^[\d\s\+\-\*\/\.\(\)eE]+$', cleaned):
            return None
        return float(eval(cleaned, {"__builtins__": {}}, {}))
    except Exception:
        return None


def parse_board_header(filepath: str) -> dict[str, Optional[Union[float, str]]]:
    """
    Parse a driver board .h file.

    Returns
    -------
    dict
        macro_name → float/int value, string, or None if unparseable.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Board preset not found: {filepath}")

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    # Join continuation lines
    content = re.sub(r'\\\s*\n\s*', ' ', content)

    params: dict[str, Optional[Union[float, str]]] = {}

    for match in _RE_DEFINE.finditer(content):
        macro = match.group(1)
        raw_value = match.group(2).strip()

        # String value: "something"
        if raw_value.startswith('"') and raw_value.endswith('"'):
            params[macro] = raw_value[1:-1]  # strip quotes
            continue

        # Numeric value: (something)
        m = _RE_NUMERIC.match(raw_value)
        if m:
            inner = m.group(1).strip()
            # Check if it's an enum name
            if inner in _ENUM_MAP:
                params[macro] = _ENUM_MAP[inner]
                continue
            # Try to evaluate as number
            val = _try_eval_numeric(inner)
            if val is not None:
                # If decimals == 0 after stripping, it's an int
                params[macro] = val
            else:
                params[macro] = None
            continue

        params[macro] = None

    return params


def extract_board_brief(params: dict) -> str:
    """One-line summary for the board preset list."""
    parts = []
    name = params.get("MY_BOARD_NAME")
    if name and isinstance(name, str):
        parts.append(str(name))
    driver = params.get("MY_BOARD_GATE_DRIVER_IC")
    if driver and isinstance(driver, str):
        parts.append(str(driver))
    vmax = params.get("MY_BOARD_VBUS_MAX_V")
    if vmax is not None:
        parts.append(f"{float(vmax):.0f}V")
    return " | ".join(parts) if parts else ""
