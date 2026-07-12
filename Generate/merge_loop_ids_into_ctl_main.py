"""Merge generated loop-ids into Example C/H/paras templates.

Behavior by mech property:
- mech + pid: C uses Example1 style, H uses Example2 style, paras uses Example3 style.
- mech + smc: C/H/paras use Example4 style.
- pid and smc are treated as mutually exclusive.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List


def replace_section(text: str, start_marker: str, end_marker: str, insert_lines: List[str]) -> str:
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker, start_idx + len(start_marker))
    if start_idx == -1 or end_idx == -1:
        raise RuntimeError(f"markers not found: {start_marker} .. {end_marker}")
    before = text[: start_idx + len(start_marker)]
    after = text[end_idx:]
    return before + "\n" + "".join(insert_lines) + after


def activate_commented_section(text: str, start_marker: str, end_marker: str) -> str:
    """Remove //-comment prefixes from every line between start_marker and end_marker.

    The markers themselves are kept in place.  Only the lines *between* the
    markers are un-commented.  Handles indented comments correctly.
    """
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker, start_idx + len(start_marker))
    if start_idx == -1 or end_idx == -1:
        return text  # markers absent → nothing to activate, leave as-is

    before = text[: start_idx + len(start_marker)]
    after = text[end_idx:]
    section = text[start_idx + len(start_marker) : end_idx]

    activated_lines: List[str] = []
    for line in section.split("\n"):
        idx = line.find("//")
        if idx >= 0:
            # Keep whatever is before the // (e.g. indentation), drop the // and
            # the optional space that follows it.
            after_comment = line[idx + 2:]
            if after_comment.startswith(" "):
                activated_lines.append(line[:idx] + after_comment[1:])
            else:
                activated_lines.append(line[:idx] + after_comment)
        else:
            activated_lines.append(line)

    return before + "\n".join(activated_lines) + after


def activate_ladrc_in_c(ctext: str, mech_mode: str) -> str:
    """Activate the LADRC speed or position blocks in the generated C file."""
    if mech_mode == "ladrc_spd":
        ctext = activate_commented_section(ctext, "// Start LADRC Speed Var", "// End LADRC Speed Var")
        ctext = activate_commented_section(ctext, "// Start LADRC Speed Func Decl", "// End LADRC Speed Func Decl")
        ctext = activate_commented_section(ctext, "// Start LADRC Speed Clear", "// End LADRC Speed Clear")
        ctext = activate_commented_section(ctext, "// Start LADRC Speed Setup", "// End LADRC Speed Setup")
    elif mech_mode == "ladrc_pos":
        ctext = activate_commented_section(ctext, "// Start LADRC Position Var", "// End LADRC Position Var")
        ctext = activate_commented_section(ctext, "// Start LADRC Position Func Decl", "// End LADRC Position Func Decl")
        ctext = activate_commented_section(ctext, "// Start LADRC Position Clear", "// End LADRC Position Clear")
        ctext = activate_commented_section(ctext, "// Start LADRC Position Setup", "// End LADRC Position Setup")
    return ctext


def activate_ladrc_in_h(htext: str, mech_mode: str) -> str:
    """Activate the LADRC extern declarations in the generated header file."""
    if mech_mode == "ladrc_spd":
        htext = activate_commented_section(htext, "// Start LADRC Speed Extern", "// End LADRC Speed Extern")
    elif mech_mode == "ladrc_pos":
        htext = activate_commented_section(htext, "// Start LADRC Position Extern", "// End LADRC Position Extern")
    return htext


def activate_pid_in_c(ctext: str, mech_mode: str) -> str:
    """Activate the PID mechanical blocks in the generated C file."""
    if mech_mode != "pid":
        return ctext
    ctext = activate_commented_section(ctext, "// Start PID Mech Var", "// End PID Mech Var")
    ctext = activate_commented_section(ctext, "// Start PID Mech Func Decl", "// End PID Mech Func Decl")
    ctext = activate_commented_section(ctext, "// Start PID Mech Clear", "// End PID Mech Clear")
    ctext = activate_commented_section(ctext, "// Start PID Mech Setup", "// End PID Mech Setup")
    return ctext


def activate_pid_in_h(htext: str, mech_mode: str) -> str:
    """Activate the PID extern declaration in the generated header file."""
    if mech_mode != "pid":
        return htext
    htext = activate_commented_section(htext, "// Start PID Mech Extern", "// End PID Mech Extern")
    return htext


def activate_smc_in_c(ctext: str, mech_mode: str) -> str:
    """Activate the SMC mechanical blocks in the generated C file."""
    if mech_mode != "smc":
        return ctext
    ctext = activate_commented_section(ctext, "// Start SMC Mech Var", "// End SMC Mech Var")
    ctext = activate_commented_section(ctext, "// Start SMC Mech Func Decl", "// End SMC Mech Func Decl")
    ctext = activate_commented_section(ctext, "// Start SMC Mech Clear", "// End SMC Mech Clear")
    ctext = activate_commented_section(ctext, "// Start SMC Mech Setup", "// End SMC Mech Setup")
    return ctext


def activate_smc_in_h(htext: str, mech_mode: str) -> str:
    """Activate the SMC extern declaration in the generated header file."""
    if mech_mode != "smc":
        return htext
    htext = activate_commented_section(htext, "// Start SMC Mech Extern", "// End SMC Mech Extern")
    return htext


def ensure_include_line(text: str, include_line: str, after_include: str) -> str:
    if include_line in text:
        return text
    anchor = after_include + "\n"
    idx = text.find(anchor)
    if idx == -1:
        return include_line + "\n" + text
    insert_pos = idx + len(anchor)
    return text[:insert_pos] + include_line + "\n" + text[insert_pos:]


def add_unique(lines: List[str], value: str) -> None:
    if value not in lines:
        lines.append(value)


def loop_name(item: dict) -> str:
    return str(item.get("name") or "").lower()


def loop_id(item: dict) -> str:
    return str(item.get("id") or "").lower()


def loop_props(item: dict) -> List[str]:
    return [str(p).lower() for p in (item.get("properties") or []) if str(p).strip()]


def has_mech(loop_items: List[dict]) -> bool:
    return any("mech" in loop_name(item) or "mech" in loop_id(item) for item in loop_items)


def has_current(loop_items: List[dict]) -> bool:
    return any("current" in loop_name(item) or "current" in loop_id(item) for item in loop_items)


def current_input_kind(loop_items: List[dict]) -> str:
    """Return 'simulate_speed' when the current loop should use rg.enc, otherwise 'real_speed'."""
    for item in loop_items:
        if not ("current" in loop_name(item) or "current" in loop_id(item)):
            continue
        props = loop_props(item)
        if any("simulate_speed" in p for p in props):
            return "simulate_speed"
    return "real_speed"


def detect_mech_mode(loop_items: List[dict]) -> str:
    """Return 'smc', 'pid', 'ladrc_spd', 'ladrc_pos', or 'none'."""
    # LADRC takes priority — check it first so ladrc isn't caught by the pid fallback
    for item in loop_items:
        if not ("mech" in loop_name(item) or "mech" in loop_id(item)):
            continue
        props = loop_props(item)
        if any("ladrc" in p for p in props):
            if any("position" in p for p in props):
                return "ladrc_pos"
            return "ladrc_spd"
    for item in loop_items:
        if not ("mech" in loop_name(item) or "mech" in loop_id(item)):
            continue
        props = loop_props(item)
        if any("smc" in p for p in props):
            return "smc"
    for item in loop_items:
        if not ("mech" in loop_name(item) or "mech" in loop_id(item)):
            continue
        props = loop_props(item)
        if any("pid" in p for p in props):
            return "pid"
    return "none"


def mech_control_kind(loop_items: List[dict]) -> str:
    """Pick velocity/position mode for Example1 mech enable line."""
    for item in loop_items:
        if not ("mech" in loop_name(item) or "mech" in loop_id(item)):
            continue
        props = loop_props(item)
        if "position" in props:
            return "position"
        if "speed" in props:
            return "speed"
    return "position"


def apply_pid_macros_to_c(text: str) -> str:
    replacements = {
        "    mech_init.pos_kp = 5.0f;\n": "    mech_init.pos_kp = POS_KP;\n",
        "    mech_init.pos_ki = 1.0f;\n": "    mech_init.pos_ki = POS_KI;\n",
        "    mech_init.vel_kp = 5.0f;\n": "    mech_init.vel_kp = VEL_KP;\n",
        "    mech_init.vel_ki = 1.0f;\n": "    mech_init.vel_ki = VEL_KI;\n",
        "    mech_init.speed_limit = 1.0f;\n": "    mech_init.speed_limit = SPEED_LIMIT;\n",
        "    mech_init.speed_slope_limit = 1.0f;\n": "    mech_init.speed_slope_limit = SPEED_SLOPE_LIMIT;\n",
        "    mech_init.cur_limit = 0.3f;\n": "    mech_init.cur_limit = CUR_LIMIT;\n",
        "    mech_init.pos_kp = pos_kp;\n": "    mech_init.pos_kp = POS_KP;\n",
        "    mech_init.pos_ki = pos_ki;\n": "    mech_init.pos_ki = POS_KI;\n",
        "    mech_init.vel_kp = vel_kp;\n": "    mech_init.vel_kp = VEL_KP;\n",
        "    mech_init.vel_ki = vel_ki;\n": "    mech_init.vel_ki = VEL_KI;\n",
        "    mech_init.speed_limit = speed_limit;\n": "    mech_init.speed_limit = SPEED_LIMIT;\n",
        "    mech_init.speed_slope_limit = speed_slope_limit;\n": "    mech_init.speed_slope_limit = SPEED_SLOPE_LIMIT;\n",
        "    mech_init.cur_limit = cur_limit;\n": "    mech_init.cur_limit = CUR_LIMIT;\n",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def replace_define_motion_controller(text: str, lines: List[str]) -> str:
    return replace_section(text, "// Start Define Motion Controller", "// End Define Motion Controller", lines)


def build_c_sections(loop_items: List[dict], mech_mode: str) -> tuple[List[str], List[str], List[str]]:
    init_lines: List[str] = []
    bind_lines: List[str] = []
    enable_lines: List[str] = []

    # current loop from Example1
    for item in loop_items:
        name = loop_name(item)
        props = loop_props(item)
        if "current" not in name and "current" not in loop_id(item):
            continue
        add_unique(init_lines, "    Setup_Motor_Current();\n")
        if current_input_kind(loop_items) == "simulate_speed":
            add_unique(
                bind_lines,
                "    ctl_attach_foc_core_port(&mtr_ctrl, &iuvw.control_port, &udc.control_port, &rg.enc, &spd_enc.encif);\n",
            )
        else:
            add_unique(
                bind_lines,
                "    ctl_attach_foc_core_port(&mtr_ctrl, &iuvw.control_port, &udc.control_port, &pos_enc.encif, &spd_enc.encif);\n",
            )
        add_unique(enable_lines, "    ctl_enable_foc_core_current_ctrl(&mtr_ctrl);\n")

    # mech loop by mode
    if has_mech(loop_items):
        if mech_mode == "smc":
            add_unique(init_lines, "    Setup_SMC_Mechanical_Controller();\n")
            add_unique(bind_lines, "    ctl_attach_smc_mech_ctrl(&smc_ctrl, &pos_enc.encif, &spd_enc.encif);\n")
            add_unique(enable_lines, "    ctl_enable_smc_mech_ctrl(&smc_ctrl);\n")
        elif mech_mode == "ladrc_spd":
            add_unique(init_lines, "    Setup_LADRC_Speed_Controller();\n")
            add_unique(bind_lines, "    ctl_attach_ladrc_spd_ctrl(&ladrc_spd_ctrl, &spd_enc.encif);\n")
            add_unique(enable_lines, "    ctl_set_ladrc_spd_mode(&ladrc_spd_ctrl, LADRC_SPD_MODE_ENABLE, float2ctrl(0.0f));\n")
            add_unique(enable_lines, "    ctl_set_ladrc_target_velocity(&ladrc_spd_ctrl, 0.1);\n")
        elif mech_mode == "ladrc_pos":
            add_unique(init_lines, "    Setup_LADRC_Position_Controller();\n")
            add_unique(bind_lines, "    ctl_attach_ladrc_pos_ctrl(&ladrc_pos_ctrl, &pos_enc.encif);\n")
            add_unique(enable_lines, "    ctl_enable_ladrc_pos_ctrl(&ladrc_pos_ctrl, float2ctrl(0.0f));\n")
        else:
            add_unique(init_lines, "    Setup_Mechanical_Controller();\n")
            add_unique(bind_lines, "    ctl_attach_mech_ctrl(&mech_ctrl, &pos_enc.encif, &spd_enc.encif);\n")
            if mech_control_kind(loop_items) == "speed":
                add_unique(enable_lines, "    ctl_set_mech_ctrl_mode(&mech_ctrl, MECH_MODE_VELOCITY);\n")
                add_unique(enable_lines, "    ctl_set_mech_target_velocity(&mech_ctrl, 0.1);\n")
            else:
                add_unique(enable_lines, "    ctl_set_mech_ctrl_mode(&mech_ctrl, MECH_MODE_POSITION);\n")

    return init_lines, bind_lines, enable_lines


def generate_header(template_text: str, loop_items: List[dict], mech_mode: str) -> str:
    htext = template_text

    # Switch mech header include by mode.
    if mech_mode == "smc":
        htext = htext.replace(
            "#include <ctl/component/motor_control/mechanical_loop/basic_mech_ctrl.h>",
            "#include <ctl/component/motor_control/mechanical_loop/smc_mech_ctrl.h>",
        )
    elif mech_mode == "ladrc_spd":
        htext = htext.replace(
            "#include <ctl/component/motor_control/mechanical_loop/basic_mech_ctrl.h>",
            "#include <ctl/component/motor_control/mechanical_loop/ladrc_spd_ctrl.h>",
        )
    elif mech_mode == "ladrc_pos":
        htext = htext.replace(
            "#include <ctl/component/motor_control/mechanical_loop/basic_mech_ctrl.h>",
            "#include <ctl/component/motor_control/mechanical_loop/ladrc_pos_ctrl.h>",
        )
    else:
        htext = htext.replace(
            "#include <ctl/component/motor_control/mechanical_loop/smc_mech_ctrl.h>",
            "#include <ctl/component/motor_control/mechanical_loop/basic_mech_ctrl.h>",
        )

    # Motor Control section: finish mech checks first, then current
    lines: List[str] = []
    indent = "        "
    if has_mech(loop_items):
        if mech_mode == "smc":
            lines.append(f"{indent}ctl_step_smc_mech_ctrl(&smc_ctrl, smc_target_revs, smc_target_angle_pu, smc_vel_ref_pu, smc_acc_ref_pu);\n")
            lines.append("\n")
            lines.append(f"{indent}ctl_set_foc_core_idq_ref(&mtr_ctrl, 0, ctl_get_smc_mech_cmd(&smc_ctrl));\n")
            lines.append("\n")
        elif mech_mode == "ladrc_spd":
            lines.append(f"{indent}ctl_step_ladrc_spd_ctrl(&ladrc_spd_ctrl);\n")
            lines.append("\n")
            lines.append(f"{indent}ctl_set_foc_core_idq_ref(&mtr_ctrl, 0, ctl_get_ladrc_spd_cmd(&ladrc_spd_ctrl));\n")
            lines.append("\n")
        elif mech_mode == "ladrc_pos":
            lines.append(f"{indent}ctl_step_ladrc_pos_ctrl(&ladrc_pos_ctrl, 0, float2ctrl(0.0f), float2ctrl(0.0f), float2ctrl(0.0f));\n")
            lines.append("\n")
            lines.append(f"{indent}ctl_set_foc_core_idq_ref(&mtr_ctrl, 0, ctl_get_ladrc_pos_cmd(&ladrc_pos_ctrl));\n")
            lines.append("\n")
        else:
            lines.append(f"{indent}ctl_step_mech_ctrl(&mech_ctrl);\n")
            lines.append("\n")
            lines.append(f"{indent}ctl_set_foc_core_idq_ref(&mtr_ctrl, 0, ctl_get_mech_cmd(&mech_ctrl));\n")
            lines.append("\n")

    if has_current(loop_items):
        lines.append(f"{indent}ctl_step_foc_core(&mtr_ctrl);\n")
        lines.append("\n")

    if not lines:
        lines.append(f"{indent}// controller body disabled by generated architecture\n")

    htext = replace_section(htext, "        // Start Motor Control", "        // End Motor Control", lines)
    return htext


def generate_paras(template_text: str, mech_mode: str) -> str:
    """Generate paras.h content for the given control mode.

    Only tunable parameters (gains, bandwidths, limits) are placed inside the
    ``// Start Paras Define`` block.  Physical constants (INERTIA,
    TORQUE_CONST, OMEGA_BASE, I_BASE) are written directly into
    ctl_main.c via the controller setup functions — they never appear in
    paras.h and are therefore invisible to the tuning agent.
    """
    insert_lines: List[str] = []

    if mech_mode == "smc":
        insert_lines = [
            "// SMC tuning targets\n",
            "#define TARGET_BW 30.0f\n",
            "#define DIST_REJECT_TORQUE 2.0f\n",
            "\n",
            "// Current loop PI gains\n",
            "#define CUR_KP 1.0f\n",
            "#define CUR_KI 1200.0f\n",
            "\n",
            "// Limits\n",
            "#define CUR_LIMIT 1.0f\n",
        ]
    elif mech_mode in ("ladrc_spd", "ladrc_pos"):
        insert_lines = [
            "// LADRC tuning targets\n",
            "#define TARGET_WC 5.0f\n",
            "#define TARGET_WO 50.0f\n",
            "\n",
            "// Current loop PI gains\n",
            "#define CUR_KP 1.0f\n",
            "#define CUR_KI 1200.0f\n",
            "\n",
            "// Limits\n",
            "#define SPEED_LIMIT 1.0f\n",
            "#define SPEED_SLOPE_LIMIT 0.1f\n",
            "#define CUR_LIMIT 0.3f\n",
        ]
    elif mech_mode == "pid":
        insert_lines = [
            "#define POS_KP 5.0f\n",
            "#define POS_KI 1.0f\n",
            "\n",
            "#define VEL_KP 5.0f\n",
            "#define VEL_KI 0.0f\n",
            "\n",
            "#define CUR_KP 1.0f\n",
            "#define CUR_KI 1200.0f\n",
            "\n",
            "#define SPEED_LIMIT 1.0f\n",
            "#define SPEED_SLOPE_LIMIT 1.0f\n",
            "#define CUR_LIMIT 0.3f\n",
        ]

    return replace_section(template_text, "// Start Paras Define", "// End Paras Define", insert_lines)


def main(
    loop_ids_path: Path,
    template_path: Path,
    output_path: Path,
    core_path: Path | None = None,
    header_template_path: Path | None = None,
    header_output_path: Path | None = None,
    paras_template_path: Path | None = None,
    paras_output_path: Path | None = None,
) -> int:
    if not loop_ids_path.exists():
        print(f"missing loop ids: {loop_ids_path}")
        return 2
    if not template_path.exists():
        print(f"missing template: {template_path}")
        return 2
    if header_template_path is not None and not header_template_path.exists():
        print(f"missing header template: {header_template_path}")
        return 2
    if paras_template_path is not None and not paras_template_path.exists():
        print(f"missing paras template: {paras_template_path}")
        return 2

    payload = json.loads(loop_ids_path.read_text(encoding="utf-8-sig"))
    loops = payload.get("selected_loops") or []
    mech_mode = detect_mech_mode(loops)

    # C generation
    ctext = template_path.read_text(encoding="utf-8")

    # Activate mode-specific blocks (un-comment them) before section replacements.
    ctext = activate_pid_in_c(ctext, mech_mode)
    ctext = activate_smc_in_c(ctext, mech_mode)
    ctext = activate_ladrc_in_c(ctext, mech_mode)

    init_lines, bind_lines, enable_lines = build_c_sections(loops, mech_mode)
    ctext = replace_section(ctext, "    // Start Controller Init", "    // End Controller Init", init_lines)
    ctext = replace_section(ctext, "    // Start Encoder Binding", "    // End Encoder Binding", bind_lines)
    ctext = replace_section(ctext, "    // Start Enable", "    // End Enable", enable_lines)

    if paras_output_path is not None:
        paras_include = f'#include "{paras_output_path.name}"'
        ctext = ensure_include_line(ctext, paras_include, '#include "ctl_main.h"')
    if mech_mode == "pid":
        ctext = apply_pid_macros_to_c(ctext)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ctext, encoding="utf-8")
    print(f"Wrote {output_path}")

    # H generation
    if header_template_path and header_output_path:
        htpl = header_template_path.read_text(encoding="utf-8")
        hout = generate_header(htpl, loops, mech_mode)
        hout = activate_pid_in_h(hout, mech_mode)
        hout = activate_smc_in_h(hout, mech_mode)
        hout = activate_ladrc_in_h(hout, mech_mode)
        header_output_path.parent.mkdir(parents=True, exist_ok=True)
        header_output_path.write_text(hout, encoding="utf-8")
        print(f"Wrote {header_output_path}")

    # paras generation
    if paras_template_path and paras_output_path:
        ptpl = paras_template_path.read_text(encoding="utf-8")
        pout = generate_paras(ptpl, mech_mode)
        paras_output_path.parent.mkdir(parents=True, exist_ok=True)
        paras_output_path.write_text(pout, encoding="utf-8")
        print(f"Wrote {paras_output_path}")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge loop-ids into ctl_main template.")
    parser.add_argument("--loop-ids", type=Path, default=Path(__file__).with_name("controller_loop_ids_generated.json"))
    parser.add_argument("--core-structure", type=Path, default=Path(__file__).with_name("controller_core_structure.json"))
    parser.add_argument("--template", type=Path, default=Path(__file__).with_name("Example").joinpath("ctl_main.c"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("ctl_main.generated.c"))
    parser.add_argument("--header-template", type=Path, default=Path(__file__).with_name("Example").joinpath("ctl_main.h"))
    parser.add_argument("--header-output", type=Path, default=Path(__file__).with_name("ctl_main.generated.h"))
    parser.add_argument("--paras-template", type=Path, default=Path(__file__).with_name("Example").joinpath("paras.h"))
    parser.add_argument("--paras-output", type=Path, default=Path(__file__).with_name("paras.generated.h"))
    args = parser.parse_args()
    raise SystemExit(
        main(
            args.loop_ids,
            args.template,
            args.output,
            core_path=args.core_structure,
            header_template_path=args.header_template,
            header_output_path=args.header_output,
            paras_template_path=args.paras_template,
            paras_output_path=args.paras_output,
        )
    )
