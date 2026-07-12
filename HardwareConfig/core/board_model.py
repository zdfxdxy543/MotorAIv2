"""
Driver board parameter data model.

Based on MONKEY_BOARD.h structure: nameplate, physical limits,
sensing topology, and sensing circuit parameters.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union


class BoardParamCategory(Enum):
    NAMEPLATE = "nameplate"
    LIMITS = "limits"
    TOPOLOGY = "topology"
    CIRCUIT = "circuit"

    @property
    def label(self) -> str:
        return {
            "nameplate": "铭牌信息",
            "limits": "物理极限",
            "topology": "传感拓扑",
            "circuit": "传感电路参数",
        }[self.value]


class ParamKind(Enum):
    FLOAT = "float"
    INT = "int"
    STRING = "string"


@dataclass
class BoardParamDef:
    macro: str
    label: str
    symbol: str
    unit: str
    category: BoardParamCategory
    kind: ParamKind = ParamKind.FLOAT
    decimals: int = 3
    min_val: float = 0.0
    max_val: float = 1e6
    # Sub-category label for circuit params
    sub_label: str = ""


# ---------------------------------------------------------------------------
# Complete parameter set from MONKEY_BOARD.h
# ---------------------------------------------------------------------------

BOARD_PARAM_DEFS: list[BoardParamDef] = [
    # ---- Nameplate (string) ----
    BoardParamDef("MY_BOARD_NAME",                 "板卡名称",       "Name",           "",
                  BoardParamCategory.NAMEPLATE, kind=ParamKind.STRING),
    BoardParamDef("MY_BOARD_GATE_DRIVER_IC",       "栅极驱动IC",     "Gate Driver",    "",
                  BoardParamCategory.NAMEPLATE, kind=ParamKind.STRING),
    BoardParamDef("MY_BOARD_MOSFET_PART_NUMBER",   "MOSFET型号",     "MOSFET",         "",
                  BoardParamCategory.NAMEPLATE, kind=ParamKind.STRING),
    BoardParamDef("MY_BOARD_CURRENT_SENSOR_MODEL", "电流传感器型号", "Current Sensor", "",
                  BoardParamCategory.NAMEPLATE, kind=ParamKind.STRING),
    BoardParamDef("MY_BOARD_THERMAL_SENSOR_MODEL", "温度传感器型号", "Thermal Sensor", "",
                  BoardParamCategory.NAMEPLATE, kind=ParamKind.STRING),

    # ---- Physical Limits (float) ----
    BoardParamDef("MY_BOARD_VBUS_MIN_V",         "母线电压下限",   "Vbus_min",   "V",
                  BoardParamCategory.LIMITS, decimals=1, min_val=0, max_val=1000),
    BoardParamDef("MY_BOARD_VBUS_MAX_V",         "母线电压上限",   "Vbus_max",   "V",
                  BoardParamCategory.LIMITS, decimals=1, min_val=0, max_val=1000),
    BoardParamDef("MY_BOARD_CURRENT_MAX_RMS_A",  "最大相电流RMS",  "Iph_rms_max","A",
                  BoardParamCategory.LIMITS, decimals=1, min_val=0, max_val=500),
    BoardParamDef("MY_BOARD_CURRENT_MAX_PEAK_A", "最大相电流峰值", "Iph_peak_max","A",
                  BoardParamCategory.LIMITS, decimals=1, min_val=0, max_val=500),
    BoardParamDef("MY_BOARD_TEMP_MAX_C",         "最高工作温度",   "T_max",      "°C",
                  BoardParamCategory.LIMITS, decimals=1, min_val=0, max_val=200),

    # ---- Sensing Topology (int) ----
    BoardParamDef("MY_BOARD_PH_CURRENT_SENSE_TYPE",     "相电流传感类型",   "PH_CS_Type",
                  "", BoardParamCategory.TOPOLOGY, kind=ParamKind.INT, decimals=0, min_val=0, max_val=3),
    BoardParamDef("MY_BOARD_PH_CURRENT_SENSE_TOPOLOGY", "相电流传感拓扑",   "PH_CS_Topo",
                  "", BoardParamCategory.TOPOLOGY, kind=ParamKind.INT, decimals=0, min_val=0, max_val=3),
    BoardParamDef("MY_BOARD_PH_VOLTAGE_SENSE_TYPE",     "相电压传感类型",   "PH_VS_Type",
                  "", BoardParamCategory.TOPOLOGY, kind=ParamKind.INT, decimals=0, min_val=0, max_val=2),
    BoardParamDef("MY_BOARD_DCBUS_VOLTAGE_SENSE_TYPE",  "母线电压传感类型", "DC_VS_Type",
                  "", BoardParamCategory.TOPOLOGY, kind=ParamKind.INT, decimals=0, min_val=0, max_val=2),
    BoardParamDef("MY_BOARD_DCBUS_CURRENT_SENSE_TYPE",  "母线电流传感类型", "DC_CS_Type",
                  "", BoardParamCategory.TOPOLOGY, kind=ParamKind.INT, decimals=0, min_val=0, max_val=2),
    BoardParamDef("MY_BOARD_THERMAL_SENSE_TYPE",        "温度传感类型",     "Therm_Type",
                  "", BoardParamCategory.TOPOLOGY, kind=ParamKind.INT, decimals=0, min_val=0, max_val=3),

    # ---- Sensing Circuit: Phase Current (float) ----
    BoardParamDef("MY_BOARD_PH_SHUNT_RESISTANCE_OHM",  "采样电阻",       "R_shunt",
                  "Ω", BoardParamCategory.CIRCUIT, decimals=4, min_val=0.0001, max_val=100,
                  sub_label="相电流 — Shunt"),
    BoardParamDef("MY_BOARD_PH_CSA_GAIN_V_V",          "电流放大器增益", "CSA_Gain",
                  "V/V", BoardParamCategory.CIRCUIT, decimals=1, min_val=0.1, max_val=1000,
                  sub_label="相电流 — Shunt"),
    BoardParamDef("MY_BOARD_PH_CSA_BIAS_V",            "放大器偏置电压", "CSA_Bias",
                  "V", BoardParamCategory.CIRCUIT, decimals=2, min_val=0, max_val=5,
                  sub_label="相电流 — Shunt"),
    BoardParamDef("MY_BOARD_PH_CURRENT_SENSITIVITY_MV_A","传感器灵敏度",  "CS_Sens",
                  "mV/A", BoardParamCategory.CIRCUIT, decimals=1, min_val=0.1, max_val=10000,
                  sub_label="相电流 — Hall"),
    BoardParamDef("MY_BOARD_PH_CURRENT_ZERO_BIAS_V",   "零电流偏置电压", "CS_Zero",
                  "V", BoardParamCategory.CIRCUIT, decimals=2, min_val=0, max_val=5,
                  sub_label="相电流 — Hall"),
    BoardParamDef("MY_BOARD_PH_CURRENT_SENSE_POLE_HZ", "信号带宽",       "CS_BW",
                  "Hz", BoardParamCategory.CIRCUIT, decimals=1, min_val=1, max_val=1e7,
                  sub_label="相电流"),

    # ---- Sensing Circuit: Phase Voltage (float) ----
    BoardParamDef("MY_BOARD_PH_VOLTAGE_SENSE_GAIN",   "分压增益",       "VS_Gain",
                  "V/V", BoardParamCategory.CIRCUIT, decimals=5, min_val=0.00001, max_val=1,
                  sub_label="相电压"),
    BoardParamDef("MY_BOARD_PH_VOLTAGE_SENSE_BIAS_V", "偏置电压",       "VS_Bias",
                  "V", BoardParamCategory.CIRCUIT, decimals=2, min_val=0, max_val=5,
                  sub_label="相电压"),
    BoardParamDef("MY_BOARD_PH_VOLTAGE_SENSE_POLE_HZ","信号带宽",       "VS_BW",
                  "Hz", BoardParamCategory.CIRCUIT, decimals=1, min_val=1, max_val=1e7,
                  sub_label="相电压"),

    # ---- Sensing Circuit: DC Bus Voltage (float) ----
    BoardParamDef("MY_BOARD_DCBUS_VOLTAGE_SENSE_GAIN",   "分压增益",    "DC_VS_Gain",
                  "V/V", BoardParamCategory.CIRCUIT, decimals=5, min_val=0.00001, max_val=1,
                  sub_label="母线电压"),
    BoardParamDef("MY_BOARD_DCBUS_VOLTAGE_SENSE_BIAS_V", "偏置电压",    "DC_VS_Bias",
                  "V", BoardParamCategory.CIRCUIT, decimals=2, min_val=0, max_val=5,
                  sub_label="母线电压"),
    BoardParamDef("MY_BOARD_DCBUS_VOLTAGE_SENSE_POLE_HZ","信号带宽",    "DC_VS_BW",
                  "Hz", BoardParamCategory.CIRCUIT, decimals=2, min_val=1, max_val=1e7,
                  sub_label="母线电压"),

    # ---- Sensing Circuit: DC Bus Current (float) ----
    BoardParamDef("MY_BOARD_DCBUS_SHUNT_RESISTANCE_OHM",  "采样电阻",   "DC_R_shunt",
                  "Ω", BoardParamCategory.CIRCUIT, decimals=4, min_val=0.0001, max_val=100,
                  sub_label="母线电流 — Shunt"),
    BoardParamDef("MY_BOARD_DCBUS_CSA_GAIN_V_V",          "放大器增益", "DC_CSA_Gain",
                  "V/V", BoardParamCategory.CIRCUIT, decimals=1, min_val=0.1, max_val=1000,
                  sub_label="母线电流 — Shunt"),
    BoardParamDef("MY_BOARD_DCBUS_CSA_BIAS_V",            "偏置电压",   "DC_CSA_Bias",
                  "V", BoardParamCategory.CIRCUIT, decimals=2, min_val=0, max_val=5,
                  sub_label="母线电流 — Shunt"),
    BoardParamDef("MY_BOARD_DCBUS_CURRENT_SENSITIVITY_MV_A","传感器灵敏度","DC_CS_Sens",
                  "mV/A", BoardParamCategory.CIRCUIT, decimals=1, min_val=0.1, max_val=10000,
                  sub_label="母线电流 — Hall"),
    BoardParamDef("MY_BOARD_DCBUS_CURRENT_ZERO_BIAS_V",   "零电流偏置", "DC_CS_Zero",
                  "V", BoardParamCategory.CIRCUIT, decimals=2, min_val=0, max_val=5,
                  sub_label="母线电流 — Hall"),
    BoardParamDef("MY_BOARD_DCBUS_CURRENT_SENSE_POLE_HZ", "信号带宽",    "DC_CS_BW",
                  "Hz", BoardParamCategory.CIRCUIT, decimals=1, min_val=1, max_val=1e7,
                  sub_label="母线电流"),
    BoardParamDef("MY_BOARD_DCBUS_CURRENT_SENSE_GAIN",    "传感增益",    "DC_CS_Gain",
                  "-", BoardParamCategory.CIRCUIT, decimals=1, min_val=0, max_val=1e6,
                  sub_label="母线电流 — 其他"),
    BoardParamDef("MY_BOARD_DCBUS_CURRENT_SENSE_BIAS_V",  "传感偏置",    "DC_CS_Bias",
                  "V", BoardParamCategory.CIRCUIT, decimals=2, min_val=0, max_val=5,
                  sub_label="母线电流 — 其他"),

    # ---- Sensing Circuit: Thermal (float) ----
    BoardParamDef("MY_BOARD_THERMAL_PULLUP_RESISTANCE_OHM","上拉电阻",   "NTC_R_pullup",
                  "Ω", BoardParamCategory.CIRCUIT, decimals=1, min_val=100, max_val=1e6,
                  sub_label="温度 — NTC"),
    BoardParamDef("MY_BOARD_THERMAL_NTC_BETA_VALUE",       "NTC Beta值", "NTC_Beta",
                  "K", BoardParamCategory.CIRCUIT, decimals=1, min_val=100, max_val=10000,
                  sub_label="温度 — NTC"),
    BoardParamDef("MY_BOARD_THERMAL_NTC_NOMINAL_R_OHM",    "NTC标称电阻","NTC_R_nom",
                  "Ω", BoardParamCategory.CIRCUIT, decimals=1, min_val=100, max_val=1e6,
                  sub_label="温度 — NTC"),
    BoardParamDef("MY_BOARD_THERMAL_NTC_NOMINAL_TEMP_C",   "NTC标称温度","NTC_T_nom",
                  "°C", BoardParamCategory.CIRCUIT, decimals=1, min_val=0, max_val=150,
                  sub_label="温度 — NTC"),
    BoardParamDef("MY_BOARD_THERMAL_IC_SENSITIVITY_MV_C",  "IC灵敏度",   "IC_Sens",
                  "mV/°C", BoardParamCategory.CIRCUIT, decimals=1, min_val=0.1, max_val=100,
                  sub_label="温度 — IC"),
    BoardParamDef("MY_BOARD_THERMAL_IC_OFFSET_V",          "IC零偏电压", "IC_Offset",
                  "V", BoardParamCategory.CIRCUIT, decimals=2, min_val=0, max_val=5,
                  sub_label="温度 — IC"),
]

BOARD_BY_MACRO: dict[str, BoardParamDef] = {p.macro: p for p in BOARD_PARAM_DEFS}
BOARD_BY_CATEGORY: dict[BoardParamCategory, list[BoardParamDef]] = {}
for p in BOARD_PARAM_DEFS:
    BOARD_BY_CATEGORY.setdefault(p.category, []).append(p)

BOARD_CATEGORY_ORDER = [
    BoardParamCategory.NAMEPLATE,
    BoardParamCategory.LIMITS,
    BoardParamCategory.TOPOLOGY,
    BoardParamCategory.CIRCUIT,
]
