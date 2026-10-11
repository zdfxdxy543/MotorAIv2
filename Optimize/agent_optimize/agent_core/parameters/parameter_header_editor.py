"""
Lightweight tunable-parameter header editor for the GMP parameter iteration agent.

This module is designed for the simplified workflow where all agent-editable
control parameters are placed in one generated header file, for example:

    // Start Paras Define
    #define POS_KP 5.0f
    #define POS_KI 1.0f
    #define VEL_KP 5.0f
    #define VEL_KI 1.0f
    #define SPEED_LIMIT 1.0f
    #define SPEED_SLOPE_LIMIT 1.0f
    #define CUR_LIMIT 0.3f
    // End Paras Define

Design principle:
    - The header file is the source of truth for which parameters exist in the
      current control structure.
    - Different control structures may expose different parameter names.
    - The agent should first read available parameters, then only patch names
      returned by this module.
    - This module only replaces simple numeric literals. It never adds new
      parameters and never edits arbitrary C code.

Supported declarations inside the tunable block:
    1. Macro definitions:
        #define POS_KP 5.0f
        #define CUR_LIMIT 0.3f // comment

    2. Simple variable definitions:
        static float g_agent_speed_kp = 1.0f;
        const double MY_GAIN = 2.5;

Unsupported values are intentionally rejected, for example:
    #define POS_KP (BASE_GAIN * 2.0f)
    #define POS_KP get_default_gain()

Python: 3.10+
Dependencies: standard library only
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union
import math
import re
import shutil


NumericValue = Union[int, float]


DEFAULT_BEGIN_MARKERS: Tuple[str, ...] = (
    "// Start Paras Define",
    "// BEGIN_AGENT_TUNABLE_PARAMS",
    "// GMP_AGENT_TUNABLE_PARAMS_BEGIN",
    "/* BEGIN_AGENT_TUNABLE_PARAMS */",
    "/* GMP_AGENT_TUNABLE_PARAMS_BEGIN */",
)

DEFAULT_END_MARKERS: Tuple[str, ...] = (
    "// End Paras Define",
    "// END_AGENT_TUNABLE_PARAMS",
    "// GMP_AGENT_TUNABLE_PARAMS_END",
    "/* END_AGENT_TUNABLE_PARAMS */",
    "/* GMP_AGENT_TUNABLE_PARAMS_END */",
)

# Examples accepted:
#   1
#   -1
#   +1.0
#   .5
#   1e-3
#   1.0f
#   2.0F
_NUMBER_RE = r"[+-]?(?:(?:\d+\.\d*)|(?:\.\d+)|(?:\d+))(?:[eE][+-]?\d+)?[fF]?"
_IDENTIFIER_RE = r"[A-Za-z_][A-Za-z0-9_]*"

# #define POS_KP 5.0f // comment
_DEFINE_RE = re.compile(
    r"^(?P<prefix>\s*#\s*define\s+)"
    r"(?P<name>" + _IDENTIFIER_RE + r")"
    r"(?P<between>\s+)"
    r"(?P<value>" + _NUMBER_RE + r")"
    r"(?P<suffix>\s*(?://.*|/\*.*\*/\s*)?)$"
)

# static float g_agent_speed_kp = 1.0f;
# const double MY_GAIN = 2.5; // comment
_ASSIGNMENT_RE = re.compile(
    r"^(?P<prefix>\s*(?:(?:static|const|volatile|extern)\s+)*"
    r"(?:float|double|int|uint8_t|uint16_t|uint32_t|int8_t|int16_t|int32_t|long|short)"
    r"(?:\s+|\s*\*\s*)+)"
    r"(?P<name>" + _IDENTIFIER_RE + r")"
    r"(?P<between>\s*=\s*)"
    r"(?P<value>" + _NUMBER_RE + r")"
    r"(?P<suffix>\s*;\s*(?://.*|/\*.*\*/\s*)?)$"
)


class ParameterHeaderError(Exception):
    """Base exception for parameter header editor errors."""


class ParameterHeaderFileError(ParameterHeaderError):
    """Raised when the header file cannot be read, written, or backed up."""


class ParameterHeaderBlockError(ParameterHeaderError):
    """Raised when the tunable parameter block is missing or malformed."""


class ParameterHeaderParseError(ParameterHeaderError):
    """Raised when a tunable parameter line cannot be parsed safely."""


class ParameterHeaderUpdateError(ParameterHeaderError):
    """Raised when a requested update is invalid."""


class ParameterHeaderVerificationError(ParameterHeaderError):
    """Raised when post-patch verification fails."""


@dataclass(frozen=True)
class TunableParameter:
    """One tunable numeric parameter discovered in the header file."""

    name: str
    value: NumericValue
    raw_value: str
    declaration_kind: str
    line: int
    absolute_file: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "raw_value": self.raw_value,
            "declaration_kind": self.declaration_kind,
            "line": self.line,
            "absolute_file": self.absolute_file,
        }


@dataclass(frozen=True)
class HeaderPatchRecord:
    """Patch detail for one updated parameter."""

    name: str
    old_value: NumericValue
    new_value: NumericValue
    old_raw_value: str
    new_raw_value: str
    declaration_kind: str
    line: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "old_value": self.old_value,
            "new_value": self.new_value,
            "old_raw_value": self.old_raw_value,
            "new_raw_value": self.new_raw_value,
            "declaration_kind": self.declaration_kind,
            "line": self.line,
        }


@dataclass(frozen=True)
class _LineMatch:
    name: str
    value_text: str
    declaration_kind: str
    value_start: int
    value_end: int


@dataclass(frozen=True)
class _BlockRange:
    begin_line_index: int
    end_line_index: int


def read_tunable_parameters(
    header_path: Path | str,
    *,
    allowed_names: Optional[Iterable[str]] = None,
    require_markers: bool = True,
) -> Dict[str, NumericValue]:
    """
    Read current tunable parameter values from a generated header file.

    Args:
        header_path:
            Path to paras.generated.h or equivalent.

        allowed_names:
            Optional global allow-list. When omitted, all parameters discovered
            inside the tunable block are returned. This is the recommended mode
            for different control structures, because the current header file
            already tells the agent which parameters are available.

        require_markers:
            If True, only parse the block between Start/End markers. Keep True
            for normal agent use. If False, parse the whole file as a fallback.

    Returns:
        Mapping from parameter name to numeric value.
    """
    detailed = read_tunable_parameters_detailed(
        header_path,
        allowed_names=allowed_names,
        require_markers=require_markers,
    )
    return {name: item.value for name, item in detailed.items()}


def read_tunable_parameters_detailed(
    header_path: Path | str,
    *,
    allowed_names: Optional[Iterable[str]] = None,
    require_markers: bool = True,
) -> Dict[str, TunableParameter]:
    """Read tunable parameters with source line and raw literal details."""
    path = _resolve_header_path(header_path)
    text = _read_text(path)
    lines = text.splitlines(keepends=True)
    block = _find_tunable_block(lines, require_markers=require_markers)
    allowed = _normalize_allowed_names(allowed_names)

    result: Dict[str, TunableParameter] = {}
    for line_index in range(block.begin_line_index + 1, block.end_line_index):
        line = lines[line_index]
        stripped = line.strip()
        if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
            continue

        match = _match_tunable_line(line)
        if match is None:
            # Non-parameter lines are allowed in the block only when they are
            # harmless preprocessor/include guards or comments. Anything else
            # is rejected so the agent cannot accidentally patch ambiguous code.
            if _is_ignorable_block_line(stripped):
                continue
            raise ParameterHeaderParseError(
                f"Unsupported tunable parameter line at {path}:{line_index + 1}: {line.rstrip()}"
            )

        if allowed is not None and match.name not in allowed:
            continue

        if match.name in result:
            raise ParameterHeaderParseError(
                f"Duplicate tunable parameter name '{match.name}' in {path}."
            )

        value = parse_numeric_literal(match.value_text)
        result[match.name] = TunableParameter(
            name=match.name,
            value=value,
            raw_value=match.value_text,
            declaration_kind=match.declaration_kind,
            line=line_index + 1,
            absolute_file=str(path),
        )

    if not result:
        raise ParameterHeaderParseError(
            f"No tunable numeric parameters were found in header: {path}"
        )

    return result


def patch_tunable_parameters(
    header_path: Path | str,
    updates: Mapping[str, Any],
    *,
    backup: bool = True,
    backup_dir: Optional[Path | str] = None,
    allowed_names: Optional[Iterable[str]] = None,
    require_markers: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Patch existing numeric parameters in a generated header file.

    The function only changes parameters already discovered in the header. It
    rejects unknown names, non-finite values, and unsupported C expressions.

    Args:
        header_path:
            Path to paras.generated.h or equivalent.

        updates:
            Mapping from parameter name to new numeric value. Example:
                {"VEL_KP": 4.5, "CUR_LIMIT": 0.25}

        backup:
            If True, create a timestamped backup before writing.

        backup_dir:
            Optional backup directory. If omitted, backups are written beside
            the header file using a timestamped .bak file name.

        allowed_names:
            Optional global allow-list. Omit for dynamic per-control-structure
            discovery from the header file.

        require_markers:
            If True, only patch the Start/End marker block.

        dry_run:
            If True, return the planned patch without writing the file.

    Returns:
        A structured dict suitable for tool output and history logging.
    """
    path = _resolve_header_path(header_path)
    if not isinstance(updates, Mapping) or not updates:
        raise ParameterHeaderUpdateError("updates must be a non-empty mapping/dict.")

    text = _read_text(path)
    lines = text.splitlines(keepends=True)
    block = _find_tunable_block(lines, require_markers=require_markers)
    allowed = _normalize_allowed_names(allowed_names)

    current = read_tunable_parameters_detailed(
        path,
        allowed_names=allowed,
        require_markers=require_markers,
    )

    normalized_updates: Dict[str, NumericValue] = {}
    for raw_name, raw_value in updates.items():
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ParameterHeaderUpdateError("Each update key must be a non-empty parameter name string.")
        name = raw_name.strip()
        if name not in current:
            available = ", ".join(sorted(current.keys()))
            raise ParameterHeaderUpdateError(
                f"Unknown or unavailable tunable parameter '{name}'. Available parameters: {available}"
            )
        normalized_updates[name] = _normalize_numeric_update(raw_value, name)

    patch_records: Dict[str, HeaderPatchRecord] = {}
    changed = False

    for line_index in range(block.begin_line_index + 1, block.end_line_index):
        line = lines[line_index]
        match = _match_tunable_line(line)
        if match is None or match.name not in normalized_updates:
            continue

        old_param = current[match.name]
        new_value = normalized_updates[match.name]
        new_literal = format_numeric_literal(new_value, old_param.raw_value)

        if new_literal != match.value_text:
            lines[line_index] = line[: match.value_start] + new_literal + line[match.value_end :]
            changed = True

        patch_records[match.name] = HeaderPatchRecord(
            name=match.name,
            old_value=old_param.value,
            new_value=new_value,
            old_raw_value=old_param.raw_value,
            new_raw_value=new_literal,
            declaration_kind=old_param.declaration_kind,
            line=old_param.line,
        )

    missing = set(normalized_updates) - set(patch_records)
    if missing:
        raise ParameterHeaderUpdateError(
            "Internal patch error: failed to visit update names: " + ", ".join(sorted(missing))
        )

    backup_file: Optional[str] = None
    if changed and not dry_run:
        if backup:
            backup_file = str(_create_backup(path, backup_dir=backup_dir))
        _write_text(path, "".join(lines))
        _verify_updates(
            path,
            expected=normalized_updates,
            allowed_names=allowed,
            require_markers=require_markers,
        )

    return {
        "status": "ok",
        "dry_run": dry_run,
        "changed": changed,
        "header_path": str(path),
        "backup_file": backup_file,
        "available_parameters": sorted(current.keys()),
        "updated_parameters": {
            name: record.to_dict() for name, record in sorted(patch_records.items())
        },
    }


def restore_header_backup(
    header_path: Path | str,
    *,
    backup_file: Optional[Path | str] = None,
    backup_dir: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Restore a header file from a backup.

    If backup_file is omitted, the latest matching backup is selected. This is
    useful for a later tool such as restore_tunable_parameters_backup.
    """
    path = _resolve_header_path(header_path)
    if backup_file is None:
        backup_path = _find_latest_backup(path, backup_dir=backup_dir)
    else:
        backup_path = Path(backup_file).expanduser().resolve()

    if not backup_path.exists() or not backup_path.is_file():
        raise ParameterHeaderFileError(f"Backup file does not exist: {backup_path}")

    try:
        shutil.copy2(backup_path, path)
    except OSError as exc:
        raise ParameterHeaderFileError(
            f"Failed to restore header from backup {backup_path} to {path}: {exc}"
        ) from exc

    return {
        "status": "ok",
        "header_path": str(path),
        "restored_from": str(backup_path),
        "parameters_after_restore": read_tunable_parameters(path),
    }


def parse_numeric_literal(raw: str) -> NumericValue:
    """Parse a simple C numeric literal into int or float."""
    if not isinstance(raw, str) or not raw.strip():
        raise ParameterHeaderParseError("Numeric literal must be a non-empty string.")

    text = raw.strip()
    if not re.fullmatch(_NUMBER_RE, text):
        raise ParameterHeaderParseError(f"Unsupported numeric literal: {raw!r}")

    no_suffix = text[:-1] if text[-1:] in {"f", "F"} else text
    try:
        if re.fullmatch(r"[+-]?\d+", no_suffix):
            value: NumericValue = int(no_suffix)
        else:
            value = float(no_suffix)
    except ValueError as exc:
        raise ParameterHeaderParseError(f"Failed to parse numeric literal: {raw!r}") from exc

    if isinstance(value, float) and not math.isfinite(value):
        raise ParameterHeaderParseError(f"Numeric literal is not finite: {raw!r}")
    return value


def format_numeric_literal(value: NumericValue, previous_literal: str) -> str:
    """
    Format a Python numeric value as a C numeric literal.

    The previous literal controls whether an f/F suffix is preserved.
    """
    value = _normalize_numeric_update(value, "value")
    previous = previous_literal.strip()
    suffix = ""
    if previous.endswith("f"):
        suffix = "f"
    elif previous.endswith("F"):
        suffix = "F"

    previous_without_suffix = previous[:-1] if suffix else previous
    previous_looks_float = any(ch in previous_without_suffix for ch in ".eE")

    if isinstance(value, int) and not suffix and not previous_looks_float:
        return str(value)

    number = float(value)
    # .10g keeps the file readable while avoiding excessive floating noise.
    body = format(number, ".10g")

    # If the old literal was a float literal and the new formatted value looks
    # integral, keep a decimal point to preserve the code style: 5.0f not 5f.
    if (suffix or previous_looks_float) and all(ch not in body for ch in ".eE"):
        body = body + ".0"

    return body + suffix


def _resolve_header_path(header_path: Path | str) -> Path:
    path = Path(header_path).expanduser().resolve()
    if not path.exists():
        raise ParameterHeaderFileError(f"Header file does not exist: {path}")
    if not path.is_file():
        raise ParameterHeaderFileError(f"Header path is not a file: {path}")
    return path


def _read_text(path: Path) -> str:
    """Read a C header robustly across common Windows/editor encodings.

    Windows PowerShell 5.x `Out-File` and some editors may create UTF-16
    files. Such files can look normal in an editor but fail marker matching if
    decoded as a single-byte encoding. Try UTF-16 before GBK.
    """
    encodings = ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gbk")
    last_unicode_error: Optional[UnicodeDecodeError] = None

    for encoding in encodings:
        try:
            text = path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_unicode_error = exc
            continue
        except OSError as exc:
            raise ParameterHeaderFileError(f"Failed to read header file {path}: {exc}") from exc

        # Reject obvious wrong decodes, especially UTF-16 bytes decoded as GBK
        # or UTF-16-LE decoded with the wrong endian variant.
        if "\x00" in text:
            continue
        return text

    if last_unicode_error is not None:
        raise ParameterHeaderFileError(
            f"Failed to decode header file {path}. Tried encodings: {', '.join(encodings)}."
        ) from last_unicode_error
    raise ParameterHeaderFileError(f"Failed to decode header file {path}.")


def _write_text(path: Path, text: str) -> None:
    try:
        temporary = path.with_name(path.name + '.tmp')
        temporary.write_text(text, encoding="utf-8", newline="")
        temporary.replace(path)
    except OSError as exc:
        raise ParameterHeaderFileError(f"Failed to write header file {path}: {exc}") from exc


def _find_tunable_block(lines: Sequence[str], *, require_markers: bool) -> _BlockRange:
    begin_index: Optional[int] = None
    end_index: Optional[int] = None

    for index, line in enumerate(lines):
        if begin_index is None and _line_has_marker(line, DEFAULT_BEGIN_MARKERS):
            begin_index = index
            continue
        if begin_index is not None and _line_has_marker(line, DEFAULT_END_MARKERS):
            end_index = index
            break

    if begin_index is None or end_index is None:
        if not require_markers:
            return _BlockRange(begin_line_index=-1, end_line_index=len(lines))
        raise ParameterHeaderBlockError(
            "Could not find tunable parameter block markers. Expected a begin marker "
            f"like {DEFAULT_BEGIN_MARKERS[0]!r} and an end marker like {DEFAULT_END_MARKERS[0]!r}."
        )

    if end_index <= begin_index:
        raise ParameterHeaderBlockError("Tunable parameter block end marker appears before begin marker.")

    # Reject multiple blocks to avoid patching an unintended section.
    for later_line in lines[end_index + 1 :]:
        if _line_has_marker(later_line, DEFAULT_BEGIN_MARKERS) or _line_has_marker(later_line, DEFAULT_END_MARKERS):
            raise ParameterHeaderBlockError("Multiple tunable parameter block markers were found.")

    return _BlockRange(begin_line_index=begin_index, end_line_index=end_index)


def _line_has_marker(line: str, markers: Sequence[str]) -> bool:
    # Be tolerant of BOM/NUL artifacts and extra spaces around marker comments.
    stripped = line.replace("\ufeff", "").replace("\x00", "").strip()
    compact = re.sub(r"\s+", " ", stripped)
    return any(marker in compact for marker in markers)


def _normalize_allowed_names(allowed_names: Optional[Iterable[str]]) -> Optional[set[str]]:
    if allowed_names is None:
        return None
    result: set[str] = set()
    for item in allowed_names:
        if not isinstance(item, str) or not item.strip():
            raise ParameterHeaderUpdateError("allowed_names must contain only non-empty strings.")
        result.add(item.strip())
    return result


def _match_tunable_line(line: str) -> Optional[_LineMatch]:
    for declaration_kind, regex in (("macro", _DEFINE_RE), ("variable", _ASSIGNMENT_RE)):
        match = regex.match(line.rstrip("\r\n"))
        if match is None:
            continue
        value_start, value_end = match.span("value")
        return _LineMatch(
            name=match.group("name"),
            value_text=match.group("value"),
            declaration_kind=declaration_kind,
            value_start=value_start,
            value_end=value_end,
        )
    return None


def _is_ignorable_block_line(stripped: str) -> bool:
    if not stripped:
        return True
    if stripped.startswith("//") or stripped.startswith("/*") or stripped.endswith("*/"):
        return True
    if stripped.startswith("#ifndef") or stripped.startswith("#define _"):
        return True
    if stripped.startswith("#endif"):
        return True
    return False


def _normalize_numeric_update(raw_value: Any, name: str) -> NumericValue:
    if isinstance(raw_value, bool):
        raise ParameterHeaderUpdateError(f"Update value for {name} must be numeric, not bool.")

    if isinstance(raw_value, int):
        return raw_value

    if isinstance(raw_value, float):
        if not math.isfinite(raw_value):
            raise ParameterHeaderUpdateError(f"Update value for {name} must be finite.")
        return raw_value

    if isinstance(raw_value, str):
        value = parse_numeric_literal(raw_value)
        if isinstance(value, float) and not math.isfinite(value):
            raise ParameterHeaderUpdateError(f"Update value for {name} must be finite.")
        return value

    raise ParameterHeaderUpdateError(
        f"Update value for {name} must be int, float, or simple numeric literal string."
    )


def _create_backup(path: Path, *, backup_dir: Optional[Path | str]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if backup_dir is None:
        backup_path = path.with_name(f"{path.name}.{timestamp}.bak")
    else:
        root = Path(backup_dir).expanduser().resolve()
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ParameterHeaderFileError(f"Failed to create backup directory {root}: {exc}") from exc
        backup_path = root / f"{path.name}.{timestamp}.bak"

    try:
        shutil.copy2(path, backup_path)
    except OSError as exc:
        raise ParameterHeaderFileError(f"Failed to create backup {backup_path}: {exc}") from exc
    return backup_path


def _find_latest_backup(path: Path, *, backup_dir: Optional[Path | str]) -> Path:
    if backup_dir is None:
        root = path.parent
    else:
        root = Path(backup_dir).expanduser().resolve()

    pattern = f"{path.name}.*.bak"
    backups = sorted(root.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    if not backups:
        raise ParameterHeaderFileError(f"No backup files found for {path} in {root}")
    return backups[0]


def _verify_updates(
    header_path: Path,
    *,
    expected: Mapping[str, NumericValue],
    allowed_names: Optional[set[str]],
    require_markers: bool,
) -> None:
    actual = read_tunable_parameters(
        header_path,
        allowed_names=allowed_names,
        require_markers=require_markers,
    )
    failures: List[str] = []
    for name, expected_value in expected.items():
        actual_value = actual.get(name)
        if actual_value is None:
            failures.append(f"{name}: missing after patch")
            continue
        if not _numeric_equal(actual_value, expected_value):
            failures.append(f"{name}: expected {expected_value!r}, got {actual_value!r}")
    if failures:
        raise ParameterHeaderVerificationError("Post-patch verification failed: " + "; ".join(failures))


def _numeric_equal(left: NumericValue, right: NumericValue) -> bool:
    if isinstance(left, int) and isinstance(right, int):
        return left == right
    return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-12)


__all__ = [
    "NumericValue",
    "TunableParameter",
    "HeaderPatchRecord",
    "ParameterHeaderError",
    "ParameterHeaderFileError",
    "ParameterHeaderBlockError",
    "ParameterHeaderParseError",
    "ParameterHeaderUpdateError",
    "ParameterHeaderVerificationError",
    "read_tunable_parameters",
    "read_tunable_parameters_detailed",
    "patch_tunable_parameters",
    "restore_header_backup",
    "parse_numeric_literal",
    "format_numeric_literal",
]
