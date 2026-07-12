from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


sys.dont_write_bytecode = True

MOTORAI_ROOT = Path(__file__).resolve().parents[1]
GENERATE_SCRIPT = MOTORAI_ROOT / "Generate" / "run_llm_to_program.py"
OPTIMIZE_ROOT = MOTORAI_ROOT / "Optimize"
AGENT_OPTIMIZE_DIR = OPTIMIZE_ROOT / "agent_optimize"
AGENT_OPTIMIZE_EXAMPLE_DIR = AGENT_OPTIMIZE_DIR / "Example"
AGENT_SILHELPER_DIR = OPTIMIZE_ROOT / "agent_silhelper"
SETTINGS_PATH = MOTORAI_ROOT / "motorai_settings.json"
SIMULINK_MODEL_CANDIDATES = (
    "MCS_STD_PMSM_MODEL.slx",
    "MCS_STD_PMSM_MODEL_2022b.slx",
)

if str(MOTORAI_ROOT) not in sys.path:
    sys.path.insert(0, str(MOTORAI_ROOT))

from Optimize.config_project import (  # noqa: E402
    modify_gmp_compiler_include_summaries,
    modify_simulink_vcxproj,
    resolve_gmp_root,
    rewrite_bat_variables,
)


COMMON_PROJECT_FIELDS = [
    "objective_text",
    "task_type",
    "max_iterations",
    "objective",
    "available_signals",
    "signals",
    "targets",
    "events",
    "metrics",
    "stop_conditions",
]

COMMON_REQUIREMENT_JSON_NAME = "user_requirement.json"


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


@dataclass(frozen=True)
class CandidatePaths:
    candidate_id: str
    root: Path
    src: Path
    simulate: Path
    log: Path
    log_generate: Path
    log_optimize: Path
    candidate_json: Path


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def preferred_simulink_model_path(simulate_dir: Path) -> Path:
    simulate_dir = simulate_dir.expanduser().resolve()
    for file_name in SIMULINK_MODEL_CANDIDATES:
        candidate = simulate_dir / file_name
        if candidate.exists():
            return candidate
    return simulate_dir / SIMULINK_MODEL_CANDIDATES[0]


def normalize_candidate_simulink_model_path(candidate: dict[str, Any]) -> bool:
    workspace = candidate.get("workspace") if isinstance(candidate.get("workspace"), dict) else {}
    simulate_raw = workspace.get("simulate")
    if simulate_raw:
        simulate_dir = Path(str(simulate_raw)).expanduser().resolve()
    elif candidate.get("sln_path"):
        simulate_dir = Path(str(candidate["sln_path"])).expanduser().resolve().parent
    elif candidate.get("candidate_root"):
        simulate_dir = Path(str(candidate["candidate_root"])).expanduser().resolve() / "project" / "simulate"
    else:
        return False

    preferred = preferred_simulink_model_path(simulate_dir)
    current_raw = candidate.get("simulink_model_path")
    current = Path(str(current_raw)).expanduser().resolve() if current_raw else None
    if current == preferred:
        return False

    candidate["simulink_model_path"] = str(preferred)
    return True


def common_requirement_path(project_json: Path) -> Path:
    return project_json.expanduser().resolve().parent / "common" / COMMON_REQUIREMENT_JSON_NAME


def write_common_requirement_snapshot(project_json: Path, project: dict[str, Any] | None = None) -> Path:
    project_json = project_json.expanduser().resolve()
    if project is None:
        project = load_json_object(project_json)

    payload = {
        "schema_version": 1,
        "source_project_json": str(project_json),
        "description": "Shared user requirement, metric, target, and stop-condition source for all candidates.",
        "scoring_rule": {
            "implementation": "Optimize/agent_optimize/agent_core/evaluation/scoring.py",
            "winner_selection": "winner = max(candidates, key=overall_score)",
            "llm_score_allowed": False,
        },
    }
    for field in COMMON_PROJECT_FIELDS:
        if field in project:
            payload[field] = project[field]

    path = common_requirement_path(project_json)
    write_json(path, payload)
    return path


def sync_candidate_common_fields(candidate_json: Path) -> dict[str, Any]:
    candidate_json = candidate_json.expanduser().resolve()
    candidate = load_json_object(candidate_json)
    parent_raw = candidate.get("parent_project_json")
    if not parent_raw:
        return candidate

    parent_path = Path(str(parent_raw)).expanduser()
    if not parent_path.is_absolute():
        parent_path = candidate_json.parent / parent_path
    parent_path = parent_path.resolve()
    if not parent_path.exists():
        return candidate

    parent = load_json_object(parent_path)
    shared_requirement = write_common_requirement_snapshot(parent_path, parent)
    changed = False
    for field in COMMON_PROJECT_FIELDS:
        if field in parent:
            candidate[field] = parent[field]
            changed = True
    candidate["shared_requirement_json"] = str(shared_requirement)
    changed = True
    if changed:
        write_json(candidate_json, candidate)
    return candidate


def candidate_id(index: int) -> str:
    return f"candidate_{index:02d}"


def candidate_design_profile(index: int) -> dict[str, Any]:
    profiles = [
        {
            "name": "稳健低超调方案",
            "llm_temperature": 0.15,
            "temperature": 0.15,
            "design_axis": "structure_generation",
            "structure_bias": "稳健型，优先低超调和稳定裕度。",
            "prompt": "本候选方案优先选择稳健、低超调、易调参的控制结构。若需求允许，机械环优先使用 PID，避免过度复杂结构。",
            "implementation_bias": "代码生成阶段可优先使用保守限幅、低通滤波和低超调逻辑；参数迭代阶段不因此改变评分规则。",
            "preferred_control_methods": ["pid", "gain_scheduling"],
            "generation_strategy": {
                "stage": "generate",
                "current_mode": "template_merge_v1",
                "current_scope": "当前稳定生成器主要选择 current_loop + mech_loop 及 pid/mit/smc 方法标记，再由模板合并生成 ctl_main.c。",
                "future_modes": ["full_controller_generation", "gain_scheduling"],
            },
            "optimize_policy": "shared_metrics_shared_scoring",
        },
        {
            "name": "快速响应方案",
            "llm_temperature": 0.35,
            "temperature": 0.35,
            "design_axis": "structure_generation",
            "structure_bias": "快速响应型，优先调节时间和上升时间。",
            "prompt": "本候选方案优先提高动态响应速度、缩短上升时间和调节时间，在稳定约束内允许更积极的环路配置。",
            "implementation_bias": "代码生成阶段可优先使用更积极的前馈、较快外环响应和动态限幅策略；参数迭代阶段不因此改变评分规则。",
            "preferred_control_methods": ["pid", "feedforward", "mit"],
            "generation_strategy": {
                "stage": "generate",
                "current_mode": "template_merge_v1",
                "current_scope": "当前稳定生成器主要选择 current_loop + mech_loop 及 pid/mit/smc 方法标记，再由模板合并生成 ctl_main.c。",
                "future_modes": ["full_controller_generation", "feedforward", "mit"],
            },
            "optimize_policy": "shared_metrics_shared_scoring",
        },
        {
            "name": "抗扰恢复方案",
            "llm_temperature": 0.45,
            "temperature": 0.45,
            "design_axis": "structure_generation",
            "structure_bias": "抗扰型，优先负载扰动恢复。",
            "prompt": "本候选方案优先增强负载扰动下的恢复能力和速度保持能力，关注外环抗扰和电流限幅配合。",
            "implementation_bias": "代码生成阶段可优先加入扰动观测、转矩前馈或抗饱和逻辑；参数迭代阶段不因此改变评分规则。",
            "preferred_control_methods": ["pid", "disturbance_observer", "smc"],
            "generation_strategy": {
                "stage": "generate",
                "current_mode": "template_merge_v1",
                "current_scope": "当前稳定生成器主要选择 current_loop + mech_loop 及 pid/mit/smc 方法标记，再由模板合并生成 ctl_main.c。",
                "future_modes": ["full_controller_generation", "disturbance_observer", "smc"],
            },
            "optimize_policy": "shared_metrics_shared_scoring",
        },
        {
            "name": "平滑低纹波方案",
            "llm_temperature": 0.25,
            "temperature": 0.25,
            "design_axis": "structure_generation",
            "structure_bias": "平滑型，优先电流波动、速度波动和稳定裕度。",
            "prompt": "本候选方案优先降低电流纹波、速度波动和机械噪声，控制结构应偏平滑、保守、低振荡。",
            "implementation_bias": "代码生成阶段可优先加入滤波、斜坡限制和电流平滑策略；参数迭代阶段不因此改变评分规则。",
            "preferred_control_methods": ["pid", "filtering", "ramp_limit"],
            "generation_strategy": {
                "stage": "generate",
                "current_mode": "template_merge_v1",
                "current_scope": "当前稳定生成器主要选择 current_loop + mech_loop 及 pid/mit/smc 方法标记，再由模板合并生成 ctl_main.c。",
                "future_modes": ["full_controller_generation", "filtering", "ramp_limit"],
            },
            "optimize_policy": "shared_metrics_shared_scoring",
        },
    ]
    profile = dict(profiles[(index - 1) % len(profiles)])
    profile["candidate_id"] = candidate_id(index)
    return profile


def candidate_index_from_name(name: str) -> int:
    try:
        return int(str(name).rsplit("_", 1)[-1])
    except (TypeError, ValueError):
        return 1


def candidate_paths(project_root: Path, index: int) -> CandidatePaths:
    cid = candidate_id(index)
    root = project_root / "candidates" / cid
    return CandidatePaths(
        candidate_id=cid,
        root=root,
        src=root / "src",
        simulate=root / "project" / "simulate",
        log=root / "log",
        log_generate=root / "log" / "generate",
        log_optimize=root / "log" / "optimize",
        candidate_json=root / "candidate.json",
    )


def ensure_safe_candidate_root(project_root: Path, candidate_root: Path) -> None:
    project_root = project_root.resolve()
    candidate_root = candidate_root.resolve()
    candidates_root = (project_root / "candidates").resolve()
    if not candidate_root.is_relative_to(candidates_root):
        raise ValueError(f"candidate root is outside candidates directory: {candidate_root}")


def copy_required_directory(src: Path, dst: Path, *, force: bool, project_root: Path) -> None:
    if not src.exists() or not src.is_dir():
        raise FileNotFoundError(f"required directory does not exist: {src}")

    if dst.exists():
        if not force:
            raise FileExistsError(
                f"destination already exists: {dst}. Re-run with --force to recreate candidates."
            )
        ensure_safe_candidate_root(project_root, dst)
        shutil.rmtree(dst)

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


def copy_optional_file(src: Path, dst: Path) -> None:
    if src.exists() and src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def copy_shared_context_json_files(project_root: Path, project_json: Path, template_root: Path | None = None) -> list[str]:
    """Copy common JSON context files to project_root/common once and return their paths."""
    common_name_prefixes = ("chronos_", "GMP_Tunable")
    common_dir = project_root / "common"
    common_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    roots = []
    if template_root is not None:
        roots.append(template_root)
    roots.append(project_root)

    seen_names = set()
    for root in roots:
        if not root.exists():
            continue
        for src in sorted(root.glob("*.json")):
            if src.name == project_json.name or src.name in seen_names:
                continue
            if not src.name.startswith(common_name_prefixes):
                continue
            dst = common_dir / src.name
            copy_optional_file(src, dst)
            copied.append(str(dst.resolve()))
            seen_names.add(src.name)

    return copied


def candidate_llm_temperature(profile: dict[str, Any] | None) -> float | None:
    if not isinstance(profile, dict):
        return None
    for key in ("llm_temperature", "temperature"):
        if profile.get(key) is None:
            continue
        try:
            return float(profile[key])
        except (TypeError, ValueError):
            continue
    return None


def build_candidate_generation_requirement(base_requirement: str, profile: dict[str, Any] | None) -> str:
    base_requirement = str(base_requirement or "").strip()
    if not isinstance(profile, dict) or not profile:
        return base_requirement

    name = str(profile.get("name", "") or "").strip()
    structure_bias = str(profile.get("structure_bias", "") or "").strip()
    prompt = str(profile.get("prompt", "") or "").strip()
    implementation_bias = str(profile.get("implementation_bias", "") or "").strip()
    methods = profile.get("preferred_control_methods") or profile.get("future_methods") or []
    if isinstance(methods, list):
        methods_text = ", ".join(str(item) for item in methods if str(item).strip())
    else:
        methods_text = str(methods or "").strip()

    generation_strategy = profile.get("generation_strategy")
    current_mode = ""
    current_scope = ""
    future_modes = ""
    if isinstance(generation_strategy, dict):
        current_mode = str(generation_strategy.get("current_mode", "") or "").strip()
        current_scope = str(generation_strategy.get("current_scope", "") or "").strip()
        modes = generation_strategy.get("future_modes") or []
        if isinstance(modes, list):
            future_modes = ", ".join(str(item) for item in modes if str(item).strip())
        else:
            future_modes = str(modes or "").strip()

    parts = [
        base_requirement,
        "",
        "候选方案生成策略（只影响 generate 阶段，不改变 optimize 的用户指标、参数调优目标和评分规则）：",
    ]
    if name:
        parts.append(f"- 策略名称：{name}")
    if structure_bias:
        parts.append(f"- 结构生成偏置：{structure_bias}")
    if prompt:
        parts.append(f"- 生成提示：{prompt}")
    if implementation_bias:
        parts.append(f"- 代码逻辑偏置：{implementation_bias}")
    if methods_text:
        # 第二轮以后（有 parameter_seed_policy 的 profile）才强制方法，
        # 第一轮 profile 的 preferred_control_methods 只是建议。
        seed_policy = profile.get("parameter_seed_policy") if isinstance(profile, dict) else None
        if seed_policy:
            parts.append(f"- 必须使用的控制方法（只能从以下方法中选择，不得使用未列出的方法）：{methods_text}")
        else:
            parts.append(f"- 优先探索控制方法：{methods_text}")
    if current_mode:
        parts.append(f"- 当前生成模式：{current_mode}")
    if current_scope:
        parts.append(f"- 当前生成能力边界：{current_scope}")
    if future_modes:
        parts.append(f"- 预留扩展方向：{future_modes}")
    parts.append("- 若当前生成器暂不支持某高级结构，请在已支持的 loop/method 表达范围内生成最接近方案，并把扩展意图保留在 candidate metadata 中。")
    return "\n".join(parts).strip()


def write_candidate_generation_context(
    candidate_json: Path,
    base_requirement: str,
    generation_requirement: str,
    profile: dict[str, Any] | None,
) -> Path:
    candidate_json = candidate_json.expanduser().resolve()
    candidate_dir = candidate_json.parent
    context_path = candidate_dir / "log" / "generate" / "design_strategy.json"
    write_json(
        context_path,
        {
            "schema_version": 1,
            "candidate_id": candidate_dir.name,
            "base_requirement": base_requirement,
            "generation_requirement": generation_requirement,
            "design_profile": profile or {},
            "note": "This file is for controller-structure/code generation only. Optimize uses shared metrics and scoring.",
        },
    )
    return context_path


def write_candidate_profiles(project_root: Path, candidate_count: int) -> list[dict[str, Any]]:
    profiles = [candidate_design_profile(index) for index in range(1, candidate_count + 1)]
    payload = {
        "schema_version": 1,
        "description": "Candidate generation profiles. Users may edit llm_temperature, prompt, structure_bias, and preferred_control_methods before generation. These fields affect generate only; optimize still uses shared metrics and scoring.",
        "profiles": profiles,
    }
    write_json(project_root / "common" / "candidate_profiles.json", payload)
    return profiles


def load_candidate_profiles(project_root: Path) -> list[dict[str, Any]]:
    profiles_path = project_root / "common" / "candidate_profiles.json"
    if not profiles_path.exists():
        return []
    try:
        payload = load_json_object(profiles_path)
    except Exception:
        return []
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        return []
    return [profile for profile in profiles if isinstance(profile, dict)]


def sync_candidate_profiles_from_common(project_json: Path, candidate_dirs: Iterable[Path]) -> None:
    project_root = project_json.expanduser().resolve().parent
    profiles = load_candidate_profiles(project_root)
    if not profiles:
        return
    profiles_by_id = {
        str(profile.get("candidate_id")): profile
        for profile in profiles
        if str(profile.get("candidate_id", "")).strip()
    }

    for index, candidate_dir in enumerate(candidate_dirs, start=1):
        profile = profiles_by_id.get(candidate_dir.name)
        if profile is None and index <= len(profiles):
            profile = profiles[index - 1]
        if profile is None:
            continue
        candidate_json = candidate_dir / "candidate.json"
        if not candidate_json.exists():
            continue
        try:
            candidate = load_json_object(candidate_json)
            candidate["design_profile"] = profile
            write_json(candidate_json, candidate)
        except Exception:
            continue


def _candidate_index_from_profile_line(line: str) -> int | None:
    match = re.search(r"candidate[\s_\-]*(\d{1,2})", line, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"候选(?:方案|工作区)?\s*(\d{1,2})", line)
    if match:
        return int(match.group(1))
    return None


def _append_unique(values: list[Any], value: str) -> None:
    if value not in values:
        values.append(value)


def _apply_profile_override_line(profile: dict[str, Any], line: str) -> bool:
    changed = False
    lower = line.lower()

    temp_match = re.search(
        r"(?:llm_temperature|temperature|生成温度|模型温度|agent温度|温度)\s*[:=：]?\s*(0(?:\.\d+)?|1(?:\.0+)?)",
        line,
        flags=re.IGNORECASE,
    )
    temp_value: float | None = None
    if temp_match:
        temp_value = max(0.0, min(1.0, float(temp_match.group(1))))
    elif any(token in line for token in ("高生成温度", "生成温度高", "高模型温度", "模型温度高", "高随机性", "更发散")):
        temp_value = 0.55
    elif any(token in line for token in ("低生成温度", "生成温度低", "低模型温度", "模型温度低", "低随机性", "更保守")):
        temp_value = 0.1
    if temp_value is not None:
        profile["llm_temperature"] = temp_value
        profile["temperature"] = temp_value
        changed = True

    method_keywords = [
        ("滑模", "smc"),
        ("smc", "smc"),
        ("扰动观测", "disturbance_observer"),
        ("observer", "disturbance_observer"),
        ("前馈", "feedforward"),
        ("feedforward", "feedforward"),
        ("增益调度", "gain_scheduling"),
        ("gain scheduling", "gain_scheduling"),
        ("滤波", "filtering"),
        ("斜坡", "ramp_limit"),
        ("pid", "pid"),
    ]
    methods = profile.get("preferred_control_methods")
    if not isinstance(methods, list):
        methods = []
    for keyword, method in method_keywords:
        if keyword in lower or keyword in line:
            _append_unique(methods, method)
            changed = True
    if changed:
        profile["preferred_control_methods"] = methods
        notes = profile.get("user_notes")
        if not isinstance(notes, list):
            notes = []
        _append_unique(notes, line.strip())
        profile["user_notes"] = notes
        generation_strategy = profile.get("generation_strategy")
        if isinstance(generation_strategy, dict):
            modes = generation_strategy.get("future_modes")
            if not isinstance(modes, list):
                modes = []
            for method in methods:
                _append_unique(modes, str(method))
            generation_strategy["future_modes"] = modes
            profile["generation_strategy"] = generation_strategy
    return changed


def apply_candidate_profile_overrides(project_json: Path, text: str) -> dict[str, Any]:
    """Parse simple user candidate hints and update common/candidate profile JSON.

    Only lines that explicitly mention a candidate id are parsed, so physical
    temperature or plant-condition text is not mistaken for LLM temperature.
    """
    project_json = project_json.expanduser().resolve()
    project_root = project_json.parent
    project_data = load_json_object(project_json)
    candidate_count = int(project_data.get("candidate_count") or 4)
    profiles = load_candidate_profiles(project_root)
    if not profiles:
        profiles = [candidate_design_profile(index) for index in range(1, candidate_count + 1)]

    updated: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        index = _candidate_index_from_profile_line(line)
        if index is None or index < 1 or index > len(profiles):
            continue
        profile = dict(profiles[index - 1])
        if _apply_profile_override_line(profile, line):
            profile["candidate_id"] = candidate_id(index)
            profiles[index - 1] = profile
            updated.append(candidate_id(index))

    if not updated:
        return {"updated": []}

    payload = {
        "schema_version": 1,
        "description": "Candidate generation profiles. Users may edit llm_temperature, prompt, structure_bias, and preferred_control_methods before generation. These fields affect generate only; optimize still uses shared metrics and scoring.",
        "profiles": profiles,
    }
    write_json(project_root / "common" / "candidate_profiles.json", payload)
    sync_candidate_profiles_from_common(project_json, discover_candidate_dirs(project_json, ["all"]))
    return {"updated": sorted(set(updated)), "profiles_path": str((project_root / "common" / "candidate_profiles.json").resolve())}


def build_candidate_json(
    base_project: dict[str, Any],
    project_json: Path,
    project_root: Path,
    paths: CandidatePaths,
    index: int,
    shared_context_files: list[str] | None = None,
) -> dict[str, Any]:
    candidate = dict(base_project)
    candidate["schema_version"] = candidate.get("schema_version", 1)
    candidate["candidate_id"] = paths.candidate_id
    candidate["candidate_index"] = index
    candidate["design_profile"] = candidate_design_profile(index)
    candidate["parent_project_json"] = str(project_json.resolve())
    candidate["candidate_root"] = str(paths.root.resolve())

    candidate["src_folder_path"] = str(paths.src.resolve())
    candidate["sln_path"] = str((paths.simulate / "GMP_Motor_Control_simulink.sln").resolve())
    candidate["simulink_model_path"] = str(preferred_simulink_model_path(paths.simulate))
    candidate["simulation_backend"] = select_candidate_simulation_backend(
        base_project,
        paths.candidate_id,
        index,
    )
    candidate["iteration_parameter_header_path"] = str((paths.src / "paras.generated.h").resolve())
    candidate["generated_loop_ids_path"] = str(
        (paths.log_generate / "controller_loop_ids_generated.json").resolve()
    )

    job_paths = candidate.get("paths") if isinstance(candidate.get("paths"), dict) else {}
    job_paths = dict(job_paths)
    job_paths.update(
        {
            "header_path": "src/paras.generated.h",
            "result_file": "log/optimize/tuning_result.json",
            "generated_loop_ids_path": "log/generate/controller_loop_ids_generated.json",
            "evaluation_config": "log/optimize/evaluation_config.json",
            "evaluation_result": "log/optimize/evaluation_result.json",
            "evaluation_summary": "log/optimize/evaluation_summary.txt",
            "optimization_history": "log/optimize/optimization_history.jsonl",
            "simulation_result": "log/optimize/simulation/processed.json",
            "agent_project": "log/optimize/agent_project.json",
        }
    )
    candidate["paths"] = job_paths

    candidate["workspace"] = {
        "project_root": str(project_root.resolve()),
        "candidate_root": str(paths.root.resolve()),
        "src": str(paths.src.resolve()),
        "simulate": str(paths.simulate.resolve()),
        "log": str(paths.log.resolve()),
        "log_generate": str(paths.log_generate.resolve()),
        "log_optimize": str(paths.log_optimize.resolve()),
    }
    candidate["shared_context_files"] = list(shared_context_files or [])
    candidate["generate_outputs"] = {
        "loop_ids": str((paths.log_generate / "controller_loop_ids_generated.json").resolve()),
        "ctl_main_c": str((paths.src / "ctl_main.c").resolve()),
        "ctl_main_h": str((paths.src / "ctl_main.h").resolve()),
        "paras_header": str((paths.src / "paras.generated.h").resolve()),
    }
    return candidate


def select_candidate_simulation_backend(
    project: dict[str, Any],
    candidate_name: str,
    index: int,
) -> dict[str, Any]:
    """Return per-candidate simulation backend config, defaulting to local."""
    default_backend: dict[str, Any] = {"mode": "local"}

    global_backend = project.get("simulation_backend")
    if isinstance(global_backend, dict):
        default_backend = dict(global_backend)

    backends = project.get("candidate_simulation_backends") or project.get("simulation_backends")
    selected: Any = None
    if isinstance(backends, dict):
        key_candidates = (
            candidate_name,
            candidate_name.lower(),
            str(index),
            f"candidate_{index}",
            f"candidate_{index:02d}",
        )
        for key in key_candidates:
            if key in backends:
                selected = backends[key]
                break
        if selected is None:
            selected = backends.get("default")
    elif isinstance(backends, list) and 0 <= index - 1 < len(backends):
        selected = backends[index - 1]

    if isinstance(selected, dict):
        backend = dict(default_backend)
        backend.update(selected)
    else:
        backend = dict(default_backend)

    backend["mode"] = str(backend.get("mode") or "local").strip().lower() or "local"
    return backend


def resolve_candidate_simulation_backend(candidate_json: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    backend = candidate.get("simulation_backend")
    if isinstance(backend, dict):
        resolved = dict(backend)
        resolved["mode"] = str(resolved.get("mode") or "local").strip().lower() or "local"
        return resolved

    parent_raw = candidate.get("parent_project_json")
    if parent_raw:
        parent_path = Path(str(parent_raw)).expanduser()
        if not parent_path.is_absolute():
            parent_path = candidate_json.parent / parent_path
        parent_path = parent_path.resolve()
        if parent_path.exists():
            try:
                parent = load_json_object(parent_path)
                return select_candidate_simulation_backend(
                    parent,
                    str(candidate.get("candidate_id") or candidate_json.parent.name),
                    int(candidate.get("candidate_index") or candidate_index_from_name(candidate_json.parent.name)),
                )
            except Exception:
                pass

    return {"mode": "local"}


def init_candidates(
    project_json: Path,
    candidate_count: int,
    *,
    force: bool = False,
    template_root: Path | None = None,
) -> dict[str, Any]:
    project_json = project_json.expanduser().resolve()
    project_root = project_json.parent
    base_project = load_json_object(project_json)
    if template_root is None and base_project.get("template_project_path"):
        template_root = Path(str(base_project["template_project_path"]))
    template_root = template_root.expanduser().resolve() if template_root is not None else None
    source_root = template_root or project_root
    source_src = source_root / "src"
    source_simulate = source_root / "project" / "simulate"

    if candidate_count < 1:
        raise ValueError("candidate_count must be >= 1")

    write_common_requirement_snapshot(project_json, base_project)
    shared_context_files = copy_shared_context_json_files(project_root, project_json, template_root)
    candidate_profiles = write_candidate_profiles(project_root, candidate_count)
    candidates: list[dict[str, Any]] = []
    for index in range(1, candidate_count + 1):
        paths = candidate_paths(project_root, index)
        if paths.root.exists() and not force:
            raise FileExistsError(
                f"candidate already exists: {paths.root}. Re-run with --force to recreate candidates."
            )
        if paths.root.exists() and force:
            ensure_safe_candidate_root(project_root, paths.root)
            shutil.rmtree(paths.root)

        copy_required_directory(source_src, paths.src, force=force, project_root=project_root)
        copy_required_directory(source_simulate, paths.simulate, force=force, project_root=project_root)

        for log_dir in (
            paths.log_generate,
            paths.log_optimize,
            paths.log_optimize / "simulation",
            paths.log_optimize / "build",
        ):
            log_dir.mkdir(parents=True, exist_ok=True)

        candidate = build_candidate_json(
            base_project,
            project_json,
            project_root,
            paths,
            index,
            shared_context_files=shared_context_files,
        )
        candidate["design_profile"] = candidate_profiles[index - 1]
        write_json(paths.candidate_json, candidate)
        optimize_config = configure_candidate_optimize(paths.candidate_json)

        candidates.append(
            {
                "candidate_id": paths.candidate_id,
                "candidate_root": str(paths.root.resolve()),
                "candidate_json": str(paths.candidate_json.resolve()),
                "src": str(paths.src.resolve()),
                "simulate": str(paths.simulate.resolve()),
                "log": str(paths.log.resolve()),
                "optimize": optimize_config,
            }
        )

    manifest = {
        "schema_version": 1,
        "project_json": str(project_json),
        "project_root": str(project_root.resolve()),
        "common_dir": str((project_root / "common").resolve()),
        "shared_context_files": shared_context_files,
        "candidate_count": candidate_count,
        "candidates": candidates,
    }
    write_json(project_root / "competition.json", manifest)
    return manifest


def candidate_optimize_paths(candidate_dir: Path) -> dict[str, Path]:
    candidate_dir = candidate_dir.expanduser().resolve()
    log_optimize = candidate_dir / "log" / "optimize"
    return {
        "agent_project": log_optimize / "agent_project.json",
        "build_bat": log_optimize / "build_sln.bat",
        "start_exe_bat": log_optimize / "start_exe.bat",
        "sim_bat": log_optimize / "run_local_quick.bat",
        "remote_sim_bat": log_optimize / "run_remote_simulation.bat",
        "scope_map": log_optimize / "simulation" / "scope_channel_map.json",
        "raw_simulation": log_optimize / "simulation" / "raw.json",
        "processed_simulation": log_optimize / "simulation" / "processed.json",
    }


def _relative_to_config(path: str) -> str:
    return path.replace("\\", "/")


def build_candidate_agent_project(candidate_json: Path) -> dict[str, Any]:
    candidate = load_json_object(candidate_json)
    candidate_root = Path(candidate["candidate_root"]).expanduser().resolve()
    src_dir = Path(candidate["src_folder_path"]).expanduser().resolve()
    parameter_header = Path(candidate["iteration_parameter_header_path"]).expanduser().resolve()
    sim_model = Path(candidate["simulink_model_path"]).expanduser().resolve()
    simulation_backend = resolve_candidate_simulation_backend(candidate_json, candidate)

    template_path = AGENT_OPTIMIZE_EXAMPLE_DIR / "agent_project.json"
    agent_project = load_json_object(template_path)
    agent_project["project_name"] = f"{candidate.get('candidate_id', candidate_root.name)}_optimize"

    resources = agent_project.setdefault("resources", {})
    resources["agent_log"] = {
        "type": "directory",
        "path": ".",
        "description": "Candidate-local optimize log directory.",
        "allowed_extensions": [".log", ".txt", ".json", ".jsonl"],
    }
    resources["simulation_result"] = {
        "type": "file",
        "path": "simulation/processed.json",
        "description": "Candidate-local processed simulation result JSON.",
    }
    resources["expected_metrics"] = {
        "type": "file",
        "path": "expected_metrics.txt",
        "description": "Candidate-local expected metrics text file.",
    }
    resources["project_src"] = {
        "type": "directory",
        "path": str(src_dir),
        "description": "Candidate-local engineering source directory.",
        "allowed_extensions": [
            "",
            ".c",
            ".h",
            ".cpp",
            ".hpp",
            ".cc",
            ".hh",
            ".txt",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".ini",
            ".cfg",
            ".conf",
            ".md",
            ".log",
        ],
    }

    automation = agent_project.setdefault("automation", {})
    automation.update(
        {
            "build_bat_path": "build_sln.bat",
            "start_exe_bat_path": "start_exe.bat",
            "sim_bat_path": "run_local_quick.bat",
            "remote_sim_bat_path": "run_remote_simulation.bat",
            "parameter_header": str(parameter_header),
            "optimization_history": "optimization_history.jsonl",
            "sim_model_path": str(sim_model),
            "scope_map": "simulation/scope_channel_map.json",
            "build_agent_log": "build/build.log",
            "run_exe_log": "build/run_exe.log",
            "simulation_result": "simulation/processed.json",
            "evaluation_config": "evaluation_config.json",
            "evaluation_result": "evaluation_result.json",
            "evaluation_summary": "evaluation_summary.txt",
            "build_timeout_sec": int(automation.get("build_timeout_sec", 900)),
            "sim_timeout_sec": int(automation.get("sim_timeout_sec", 1800)),
            "simulation_backend": simulation_backend,
        }
    )
    return agent_project


def write_candidate_run_local_quick_bat(candidate_json: Path, bat_path: Path) -> None:
    candidate = load_json_object(candidate_json)
    sim_model = Path(candidate["simulink_model_path"]).expanduser().resolve()
    run_local_job = (AGENT_SILHELPER_DIR / "run_local_job.py").resolve()
    raw_output = "simulation\\raw.json"
    processed_output = "simulation\\processed.json"
    content = f"""@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "MODEL_PATH={sim_model}"

if not "%~1"=="" (
    set "MODEL_PATH=%~1"
)

set "SCOPE_MAP=%SCRIPT_DIR%simulation\\scope_channel_map.json"
if not exist "%SCRIPT_DIR%simulation" mkdir "%SCRIPT_DIR%simulation"
if not exist "%SCOPE_MAP%" echo {{}}>"%SCOPE_MAP%"

python "{run_local_job}" --model-path "%MODEL_PATH%" --scope-map "%SCOPE_MAP%" --raw-output "%SCRIPT_DIR%{raw_output}" --processed-output "%SCRIPT_DIR%{processed_output}"
exit /b %ERRORLEVEL%
"""
    bat_path.parent.mkdir(parents=True, exist_ok=True)
    bat_path.write_text(content, encoding="utf-8")


def write_candidate_run_remote_simulation_bat(candidate_json: Path, bat_path: Path) -> None:
    remote_client = (AGENT_SILHELPER_DIR / "remote_sil_client.py").resolve()
    content = f"""@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
if not exist "%SCRIPT_DIR%simulation" mkdir "%SCRIPT_DIR%simulation"

python "{remote_client}" --agent-project "%SCRIPT_DIR%agent_project.json" > "%SCRIPT_DIR%simulation\\remote_client_stdout.txt" 2> "%SCRIPT_DIR%simulation\\remote_client_stderr.txt"
exit /b %ERRORLEVEL%
"""
    bat_path.parent.mkdir(parents=True, exist_ok=True)
    bat_path.write_text(content, encoding="utf-8")


def _normalize_metric_thresholds(metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """自动校准 metric 的 good_threshold / bad_threshold。

    防止两种常见问题：
    1. good == bad（评分函数会抛异常跳过该指标）
    2. bad 值来自模板默认值，与当前 target_value 不匹配（如 62.832 是 3000rpm
       模板的残留值，用于 500rpm 目标会导致评分几乎无区分度）

    规则（对 minimize 指标）：
    - good >= bad         → bad = good * 2
    - bad > target * 0.3  → bad = good * 5（bad 是旧模板残留值，按 good 等比缩放）
    - bad > good * 10     → bad = good * 5（兜底，压制模板残留的极端值）
    """
    if not isinstance(metrics, list):
        return metrics

    for m in metrics:
        if not isinstance(m, dict):
            continue
        good = m.get("good_threshold")
        bad = m.get("bad_threshold")
        if not isinstance(good, (int, float)) or not isinstance(bad, (int, float)):
            continue
        target = m.get("target_value")
        direction = str(m.get("optimization_direction", "minimize")).strip().lower()

        if direction == "minimize":
            if good >= bad:
                m["bad_threshold"] = good * 2.0
                bad = m["bad_threshold"]
            # bad 超过目标值 30%，说明是旧模板残留的绝对值
            if isinstance(target, (int, float)) and target > 0 and bad > target * 0.3:
                m["bad_threshold"] = good * 5.0
                bad = m["bad_threshold"]
            # 兜底：bad 仍超过 good 的 10 倍
            if bad > good * 10:
                m["bad_threshold"] = good * 5.0
        elif direction == "maximize":
            if good <= bad:
                m["bad_threshold"] = good * 0.5

    return metrics


def _write_candidate_evaluation_config(candidate: dict[str, Any], optimize_dir: Path, *, candidate_json: Path | None = None) -> Path:
    """从 candidate.json 提取评估配置字段，写入 evaluation_config.json。

    同时将校准后的阈值回写到 candidate.json，确保无论 evaluator
    走 direct-evaluation 模式（读 candidate.json）还是默认路径
    （读 evaluation_config.json）都拿到一致的阈值。
    """
    # 深拷贝 metrics，避免校准时污染 candidate dict 中的原始对象
    raw_metrics = candidate.get("metrics")
    metrics_copy = [dict(m) for m in raw_metrics] if isinstance(raw_metrics, list) else []
    calibrated = _normalize_metric_thresholds(metrics_copy)

    config: dict[str, Any] = {}
    for field in ("task_type", "objective", "signals"):
        value = candidate.get(field)
        if value is not None:
            config[field] = value
    config["metrics"] = calibrated

    output = optimize_dir / "evaluation_config.json"
    write_json(output, config)

    # 同步回写 candidate.json，防止 generate 阶段冲掉后 evaluator 读到旧值
    if candidate_json is not None:
        candidate["metrics"] = calibrated
        write_json(candidate_json, candidate)

    return output


def _sync_calibrated_metrics_to_parent(candidate: dict[str, Any], candidate_json: Path) -> None:
    """将校准后的 metrics 阈值回写到父项目 JSON。

    _write_candidate_evaluation_config 已将校准后的阈值写入 candidate.json，
    但父项目 JSON（如 FinalFifth.json）中的原始值未更新。若用户后续使用
    --force-init 重建 candidate，旧值会被 sync_candidate_common_fields 拷回，
    导致校准失效。此函数消除该风险。

    仅当 candidate["metrics"] 与父项目 JSON 的 metrics 结构一致（逐项
    metric_name + signal 匹配）时才执行回写；不匹配则跳过，避免误写。
    """
    parent_raw = candidate.get("parent_project_json")
    if not parent_raw:
        return
    parent_path = Path(str(parent_raw)).expanduser()
    if not parent_path.is_absolute():
        parent_path = candidate_json.parent / parent_path
    parent_path = parent_path.resolve()
    if not parent_path.exists():
        return

    calibrated_metrics = candidate.get("metrics")
    if not isinstance(calibrated_metrics, list) or not calibrated_metrics:
        return

    try:
        parent = load_json_object(parent_path)
    except Exception:
        return

    parent_metrics = parent.get("metrics")
    if not isinstance(parent_metrics, list) or len(parent_metrics) != len(calibrated_metrics):
        return

    # 逐项匹配：仅当 metric_name + signal 一致时才覆盖阈值
    updated = False
    for pm, cm in zip(parent_metrics, calibrated_metrics):
        if not isinstance(pm, dict) or not isinstance(cm, dict):
            return
        if pm.get("metric_name") != cm.get("metric_name"):
            return
        if pm.get("signal") != cm.get("signal"):
            return
        for key in ("good_threshold", "bad_threshold"):
            if key in cm and pm.get(key) != cm.get(key):
                pm[key] = cm[key]
                updated = True

    if updated:
        write_json(parent_path, parent)


def sync_tuning_policy_with_header(candidate_json: Path) -> dict[str, Any]:
    """Auto-complete tuning_policy.allowed_parameters from paras.generated.h.

    Reads the actual tunable parameters from the generated header, compares them
    with the user-configured whitelist, and adds any missing parameters with
    sensible min/max ranges inferred from the parameter name and current value.

    Call after code generation, so paras.generated.h reflects the actual control
    structure.  The updated whitelist is written back to candidate.json on disk.

    Returns:
        A summary dict with ``auto_added``, ``nonexistent``, and ``updated`` keys.
    """
    from Optimize.agent_optimize.agent_core.parameters.parameter_header_editor import (
        read_tunable_parameters,
        ParameterHeaderError,
    )
    from Optimize.agent_optimize.agent_core.app import _infer_parameter_range

    candidate_json = Path(candidate_json).expanduser().resolve()
    candidate = load_json_object(candidate_json)

    # ── read current whitelist ──────────────────────────────────────
    tuning_policy = candidate.get("tuning_policy")
    if not isinstance(tuning_policy, dict):
        return {"updated": False, "reason": "no tuning_policy in candidate.json"}
    allowed_params = tuning_policy.get("allowed_parameters")
    if not isinstance(allowed_params, dict):
        allowed_params = {}

    # ── read header ─────────────────────────────────────────────────
    header_path_raw = candidate.get("iteration_parameter_header_path")
    if not header_path_raw:
        header_path_raw = candidate.get("paths", {}).get("header_path")
    if not header_path_raw:
        src_dir = Path(str(candidate.get("src_folder_path") or "")).expanduser().resolve()
        header_path_raw = str(src_dir / "paras.generated.h")
    header_path = Path(str(header_path_raw)).expanduser()
    if not header_path.is_absolute():
        header_path = candidate_json.parent / header_path
    header_path = header_path.resolve()

    if not header_path.exists():
        return {"updated": False, "reason": f"header not found: {header_path}"}

    try:
        header_params = read_tunable_parameters(header_path)
    except (ParameterHeaderError, OSError, TypeError, ValueError) as exc:
        return {"updated": False, "reason": f"cannot read header: {exc}"}

    if not header_params:
        return {"updated": False, "reason": "no parameters in header"}

    # ── diff ────────────────────────────────────────────────────────
    header_names = {str(k).upper() for k in header_params}
    policy_names = {str(k).upper() for k in allowed_params}
    missing = header_names - policy_names
    nonexistent = policy_names - header_names

    if not missing and not nonexistent:
        return {"updated": False, "reason": "coverage already complete", "header_param_count": len(header_names)}

    # ── auto-add missing ────────────────────────────────────────────
    # SPEED_LIMIT 等保护参数不加入白名单，防止 agent 误调
    _FIXED_TUNABLE = {"SPEED_LIMIT"}
    auto_added: list[str] = []
    for name in sorted(missing):
        if name.upper() in _FIXED_TUNABLE:
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

    # ── remove nonexistent: 删除 policy 中 header 已不存在的参数 ──
    removed: list[str] = []
    if nonexistent:
        for name in sorted(nonexistent):
            for ak in list(allowed_params.keys()):
                if str(ak).upper() == name:
                    del allowed_params[ak]
                    removed.append(str(ak))
                    break

    # ── persist back to candidate.json ──────────────────────────────
    if tuning_policy is not candidate.get("tuning_policy"):
        candidate["tuning_policy"] = dict(candidate.get("tuning_policy", {}))
    candidate["tuning_policy"]["allowed_parameters"] = allowed_params
    write_json(candidate_json, candidate)

    # ── also update the parent project JSON (the source of truth) ────
    parent_updated = False
    parent_raw = candidate.get("parent_project_json")
    if parent_raw:
        parent_path = Path(str(parent_raw)).expanduser()
        if not parent_path.is_absolute():
            parent_path = candidate_json.parent / parent_path
        parent_path = parent_path.resolve()
        if parent_path.exists():
            try:
                parent = load_json_object(parent_path)
                parent_tp = parent.get("tuning_policy")
                if not isinstance(parent_tp, dict):
                    parent["tuning_policy"] = {}
                parent_ap = parent["tuning_policy"].get("allowed_parameters")
                if not isinstance(parent_ap, dict):
                    parent_ap = {}
                # merge: keep user-configured entries, add auto-inferred ones
                parent_ap.update(
                    {name: allowed_params[name] for name in auto_added}
                )
                # remove entries that no longer exist in header
                for name in removed:
                    for pk in list(parent_ap.keys()):
                        if str(pk).upper() == name.upper():
                            del parent_ap[pk]
                            break
                parent["tuning_policy"]["allowed_parameters"] = parent_ap
                write_json(parent_path, parent)
                parent_updated = True
            except Exception:
                pass

    summary = {
        "updated": True,
        "parent_updated": parent_updated,
        "header_param_count": len(header_names),
        "policy_param_before": len(policy_names),
        "policy_param_after": len(allowed_params),
        "auto_added": auto_added,
        "removed": removed,
        "nonexistent_in_policy": sorted(nonexistent) if nonexistent else [],
    }

    if auto_added:
        print(
            f"  [tuning_policy] auto-completed {len(auto_added)} parameter(s): "
            f"{', '.join(auto_added)}"
        )
    if removed:
        print(
            f"  [tuning_policy] removed {len(removed)} obsolete parameter(s) "
            f"not found in header: {', '.join(removed)}"
        )

    return summary


# Default motor max speed in RPM, used to convert rad/s target to per-unit.
_DEFAULT_MAX_SPEED_RPM = 3000.0


def _extract_target_speed_pu_from_candidate(candidate: dict[str, Any]) -> float | None:
    """Extract target speed in per-unit from a candidate dict's targets/metrics.

    Looks for a speed-related target (signal name containing 'speed') and
    converts its target_value from rad/s to per-unit.
    Returns None when no suitable target is found.
    """
    # ── try the targets section first ──────────────────────────────────
    targets = candidate.get("targets")
    if isinstance(targets, dict):
        for signal_name, spec in targets.items():
            if not isinstance(spec, dict):
                continue
            if "speed" not in signal_name.lower():
                continue
            tv = spec.get("target_value")
            if isinstance(tv, (int, float)) and tv > 0:
                return float(tv) * 60.0 / (_DEFAULT_MAX_SPEED_RPM * 2.0 * math.pi)

    # ── fall back to the first metric with a target_value ──────────────
    metrics = candidate.get("metrics")
    if isinstance(metrics, list):
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            signal = str(metric.get("signal", "") or "").lower()
            if "speed" not in signal:
                continue
            tv = metric.get("target_value")
            if isinstance(tv, (int, float)) and tv > 0:
                return float(tv) * 60.0 / (_DEFAULT_MAX_SPEED_RPM * 2.0 * math.pi)

    return None


def _sync_target_velocity_to_ctl_main(candidate: dict[str, Any], ctl_main_path: Path) -> bool:
    """Rewrite the target-velocity literal in ctl_main.c from candidate.json.

    After generate, ctl_main.c contains a hardcoded placeholder (0.1).  This
    function computes the correct per-unit value from the user-configured
    target_value (rad/s) and replaces it in-place via regex.
    """
    target_pu = _extract_target_speed_pu_from_candidate(candidate)
    if target_pu is None:
        print("  [target] no speed target found in candidate config, skipping ctl_main.c rewrite")
        return False

    if not ctl_main_path.exists():
        print(f"  [target] ctl_main.c not found: {ctl_main_path}, skipping rewrite")
        return False

    text = ctl_main_path.read_text(encoding="utf-8")

    # Match both PID and LADRC target-velocity calls.
    pattern = re.compile(
        r'(ctl_set_(?:mech|ladrc)_target_velocity\s*\(\s*&(?:\w+)\s*,\s*)[\d]+(?:\.[\d]*)?(?:f)?'
    )
    new_literal = f"{target_pu:.6f}f"
    new_text, count = pattern.subn(rf'\g<1>{new_literal}', text)

    if count == 0:
        print("  [target] warning: no target-velocity call found in ctl_main.c, nothing rewritten")
        return False

    ctl_main_path.write_text(new_text, encoding="utf-8")
    rad_s = candidate.get("targets", {}).get("rotor_speed_rad_s", {}).get("target_value", "?")
    print(f"  [target] ctl_main.c: {count} call(s) rewritten to {new_literal}  ({rad_s} rad/s)")
    return True


def configure_candidate_optimize(candidate_json: Path) -> dict[str, Any]:
    candidate_json = candidate_json.expanduser().resolve()
    candidate = sync_candidate_common_fields(candidate_json)
    normalize_candidate_simulink_model_path(candidate)
    candidate["simulation_backend"] = resolve_candidate_simulation_backend(candidate_json, candidate)
    write_json(candidate_json, candidate)
    candidate_root = Path(candidate["candidate_root"]).expanduser().resolve()
    src_dir = Path(candidate["src_folder_path"]).expanduser().resolve()
    sln_path = Path(candidate["sln_path"]).expanduser().resolve()
    sln_dir = sln_path.parent
    optimize_paths = candidate_optimize_paths(candidate_root)
    log_optimize = candidate_root / "log" / "optimize"
    log_optimize.mkdir(parents=True, exist_ok=True)
    (log_optimize / "build").mkdir(parents=True, exist_ok=True)
    (log_optimize / "simulation").mkdir(parents=True, exist_ok=True)

    gmp_root = resolve_gmp_root(candidate, str(sln_dir))

    shutil.copy2(AGENT_OPTIMIZE_EXAMPLE_DIR / "build_sln.bat", optimize_paths["build_bat"])
    shutil.copy2(AGENT_OPTIMIZE_EXAMPLE_DIR / "start_exe.bat", optimize_paths["start_exe_bat"])

    rewrite_bat_variables(
        optimize_paths["build_bat"],
        {
            "SLN_PATH": str(sln_path),
            "SLN_DIR": str(sln_dir),
            "GMP_PRO_LOCATION": gmp_root,
            "LOG_DIR": "%SCRIPT_DIR%build",
        },
        repo_root=gmp_root,
    )
    rewrite_bat_variables(
        optimize_paths["start_exe_bat"],
        {
            "SLN_DIR": str(sln_dir),
            "LOG_DIR": "%SCRIPT_DIR%build",
        },
        repo_root=gmp_root,
    )
    write_candidate_run_local_quick_bat(candidate_json, optimize_paths["sim_bat"])
    write_candidate_run_remote_simulation_bat(candidate_json, optimize_paths["remote_sim_bat"])

    if not optimize_paths["scope_map"].exists():
        default_scope_map = OPTIMIZE_ROOT / "log" / "simulation" / "scope_channel_map.json"
        if default_scope_map.exists():
            copy_optional_file(default_scope_map, optimize_paths["scope_map"])
        else:
            write_json(optimize_paths["scope_map"], {})

    agent_project = build_candidate_agent_project(candidate_json)
    write_json(optimize_paths["agent_project"], agent_project)

    # ── 生成 evaluation_config.json ─────────────────────────────────────
    # candidate.json 已通过 sync_candidate_common_fields() 拿到最新的
    # task_type / objective / signals / metrics，直接落盘为 evaluation_config.json。
    # 这样 evaluator 无论走 direct-evaluation override 还是读默认路径，
    # 都能拿到正确的评估配置，不依赖 LLM 的行为。
    _write_candidate_evaluation_config(candidate, log_optimize, candidate_json=candidate_json)

    # ── 回写校准后的指标阈值到父项目 JSON ───────────────────────────
    # candidate["metrics"] 已被 _write_candidate_evaluation_config 原地更新为
    # 校准后的值，同步回 FinalFifth.json 防止 --force-init 时旧值被拷回。
    try:
        _sync_calibrated_metrics_to_parent(candidate, candidate_json)
    except Exception:
        pass  # 回写失败不阻塞 configure 流程

    modify_simulink_vcxproj(str(sln_dir), gmp_root)
    modify_gmp_compiler_include_summaries(candidate_root, gmp_root)

    candidate["paths"] = dict(candidate.get("paths") if isinstance(candidate.get("paths"), dict) else {})
    candidate["paths"]["agent_project"] = _relative_to_config("log/optimize/agent_project.json")
    candidate["optimize_outputs"] = {
        "agent_project": str(optimize_paths["agent_project"].resolve()),
        "build_bat": str(optimize_paths["build_bat"].resolve()),
        "start_exe_bat": str(optimize_paths["start_exe_bat"].resolve()),
        "sim_bat": str(optimize_paths["sim_bat"].resolve()),
        "remote_sim_bat": str(optimize_paths["remote_sim_bat"].resolve()),
        "evaluation_config": str((log_optimize / "evaluation_config.json").resolve()),
        "evaluation_result": str((log_optimize / "evaluation_result.json").resolve()),
        "simulation_result": str((log_optimize / "simulation" / "processed.json").resolve()),
        "optimization_history": str((log_optimize / "optimization_history.jsonl").resolve()),
        "tuning_result": str((log_optimize / "tuning_result.json").resolve()),
        "simulation_backend": candidate["simulation_backend"],
    }
    write_json(candidate_json, candidate)

    return {
        "candidate_id": candidate.get("candidate_id", candidate_root.name),
        "candidate_json": str(candidate_json),
        "agent_project": str(optimize_paths["agent_project"].resolve()),
        "project_src": str(src_dir),
        "parameter_header": str(Path(candidate["iteration_parameter_header_path"]).expanduser().resolve()),
        "evaluation_config": str((log_optimize / "evaluation_config.json").resolve()),
        "evaluation_result": str((log_optimize / "evaluation_result.json").resolve()),
        "simulation_result": str((log_optimize / "simulation" / "processed.json").resolve()),
        "optimization_history": str((log_optimize / "optimization_history.jsonl").resolve()),
        "simulation_backend": candidate["simulation_backend"],
    }


def configure_optimize_for_candidates(project_json: Path, selectors: Iterable[str]) -> dict[str, Any]:
    candidate_dirs = discover_candidate_dirs(project_json, selectors)
    if not candidate_dirs:
        raise FileNotFoundError("no candidate directories found; run the init command first")
    results = [
        configure_candidate_optimize(candidate_dir / "candidate.json")
        for candidate_dir in candidate_dirs
    ]
    summary = {
        "schema_version": 1,
        "project_json": str(project_json.expanduser().resolve()),
        "results": results,
    }
    write_json(project_json.expanduser().resolve().parent / "candidates" / "optimize_config_result.json", summary)
    return summary


def requirement_from_candidate(candidate_json: Path) -> str:
    data = sync_candidate_common_fields(candidate_json)
    for key in ("objective_text", "requirement", "objective"):
        value = str(data.get(key, "") or "").strip()
        if value:
            profile = data.get("design_profile")
            if not isinstance(profile, dict):
                profile = candidate_design_profile(candidate_index_from_name(str(data.get("candidate_id", ""))))
            return build_candidate_generation_requirement(value, profile)
    raise ValueError(f"candidate has no objective_text, requirement, or objective: {candidate_json}")


def discover_candidate_dirs(project_json: Path, selectors: Iterable[str]) -> list[Path]:
    project_root = project_json.expanduser().resolve().parent
    selected = [item.strip() for item in selectors if str(item).strip()]
    if "all" in selected and len(selected) > 1:
        selected = [item for item in selected if item != "all"]
    if not selected or selected == ["all"]:
        return sorted(path for path in (project_root / "candidates").glob("candidate_*") if path.is_dir())

    result: list[Path] = []
    for item in selected:
        normalized = item.strip()
        if normalized.isdigit():
            normalized = candidate_id(int(normalized))
        path = project_root / "candidates" / normalized
        if not path.is_dir():
            raise FileNotFoundError(f"candidate directory does not exist: {path}")
        result.append(path)
    return result


def build_generate_command(candidate_dir: Path, requirement: str) -> list[str]:
    candidate_json = candidate_dir / "candidate.json"
    temperature = None
    if candidate_json.exists():
        try:
            candidate = load_json_object(candidate_json)
            profile = candidate.get("design_profile")
            temperature = candidate_llm_temperature(profile if isinstance(profile, dict) else None)
        except Exception:
            temperature = None
    command = [
        sys.executable,
        str(GENERATE_SCRIPT),
        requirement,
        "--candidate-dir",
        str(candidate_dir.resolve()),
        "--llm-config",
        str(SETTINGS_PATH),
    ]
    if temperature is not None:
        command.extend(["--temperature", str(temperature)])
    return command


def generate_outputs(candidate_dir: Path) -> dict[str, str]:
    candidate_dir = candidate_dir.resolve()
    return {
        "loop_ids": str((candidate_dir / "log" / "generate" / "controller_loop_ids_generated.json").resolve()),
        "ctl_main_c": str((candidate_dir / "src" / "ctl_main.c").resolve()),
        "ctl_main_h": str((candidate_dir / "src" / "ctl_main.h").resolve()),
        "paras_header": str((candidate_dir / "src" / "paras.generated.h").resolve()),
        "user_main_c": str((candidate_dir / "src" / "user_main.c").resolve()),
    }


def run_generate_for_candidate(candidate_dir: Path, *, dry_run: bool) -> dict[str, Any]:
    candidate_json = candidate_dir / "candidate.json"
    candidate_data = sync_candidate_common_fields(candidate_json)
    profile = candidate_data.get("design_profile")
    if not isinstance(profile, dict):
        profile = candidate_design_profile(candidate_index_from_name(candidate_dir.name))
    base_requirement = ""
    for key in ("objective_text", "requirement", "objective"):
        base_requirement = str(candidate_data.get(key, "") or "").strip()
        if base_requirement:
            break
    requirement = requirement_from_candidate(candidate_json)
    strategy_context = write_candidate_generation_context(
        candidate_json,
        base_requirement,
        requirement,
        profile,
    )
    command = build_generate_command(candidate_dir, requirement)
    outputs = generate_outputs(candidate_dir)
    outputs["design_strategy"] = str(strategy_context.resolve())

    if dry_run:
        return {
            "candidate_id": candidate_dir.name,
            "status": "dry_run",
            "command": command,
            "outputs": outputs,
        }

    log_dir = candidate_dir / "log" / "generate"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "run_generate_stdout.txt"
    stderr_path = log_dir / "run_generate_stderr.txt"

    result = subprocess.run(
        command,
        cwd=str(MOTORAI_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")

    # ── generate 成功后立即同步 tuning_policy ─────────────────────────
    # paras.generated.h 刚刚生成完毕，用它的实际参数列表自动补全
    # tuning_policy.allowed_parameters，同时写回 candidate.json 和父级
    # project.json（如 MergeTest.json）。这样 generate 完成的那一刻，
    # 白名单就已经是完整的，后续 optimize 不会漏参数。
    if result.returncode == 0:
        try:
            sync_result = sync_tuning_policy_with_header(candidate_json)
            outputs["tuning_policy_sync"] = sync_result
        except Exception as exc:
            print(
                f"  [tuning_policy] sync failed for {candidate_dir.name}: {exc}",
                file=sys.stderr,
            )

    return {
        "candidate_id": candidate_dir.name,
        "status": "completed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout": str(stdout_path.resolve()),
        "stderr": str(stderr_path.resolve()),
        "outputs": outputs,
    }


def generate_candidates(project_json: Path, selectors: Iterable[str], *, parallel: int, dry_run: bool) -> dict[str, Any]:
    candidate_dirs = discover_candidate_dirs(project_json, selectors)
    if not candidate_dirs:
        raise FileNotFoundError("no candidate directories found; run the init command first")
    if parallel < 1:
        raise ValueError("parallel must be >= 1")
    sync_candidate_profiles_from_common(project_json, candidate_dirs)

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=parallel) as executor:
        futures = {
            executor.submit(run_generate_for_candidate, candidate_dir, dry_run=dry_run): candidate_dir
            for candidate_dir in candidate_dirs
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item.get("candidate_id", ""))
    summary = {
        "schema_version": 1,
        "project_json": str(project_json.expanduser().resolve()),
        "dry_run": dry_run,
        "parallel": parallel,
        "results": results,
    }

    project_root = project_json.expanduser().resolve().parent
    output_name = "generate_dry_run_result.json" if dry_run else "generate_result.json"
    write_json(project_root / "candidates" / output_name, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage MotorAI competition candidate workspaces.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create isolated candidate workspaces.")
    init_parser.add_argument("project_json", type=Path)
    init_parser.add_argument("--candidate-count", type=int, default=4)
    init_parser.add_argument("--template-root", type=Path)
    init_parser.add_argument("--force", action="store_true")

    gen_parser = subparsers.add_parser("generate", help="Run Generate for candidate workspaces.")
    gen_parser.add_argument("project_json", type=Path)
    gen_parser.add_argument("--candidate", action="append", default=["all"])
    gen_parser.add_argument("--parallel", type=int, default=1)
    gen_parser.add_argument("--dry-run", action="store_true")

    opt_parser = subparsers.add_parser("configure-optimize", help="Create candidate-local Optimize configs.")
    opt_parser.add_argument("project_json", type=Path)
    opt_parser.add_argument("--candidate", action="append", default=["all"])

    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            result = init_candidates(
                args.project_json,
                args.candidate_count,
                force=args.force,
                template_root=args.template_root,
            )
        elif args.command == "generate":
            result = generate_candidates(
                args.project_json,
                args.candidate,
                parallel=args.parallel,
                dry_run=args.dry_run,
            )
        elif args.command == "configure-optimize":
            result = configure_optimize_for_candidates(args.project_json, args.candidate)
        else:
            parser.error(f"unknown command: {args.command}")
            return 2
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    configure_stdio()
    raise SystemExit(main())
