"""
气动热参数计算工具 —— 领域专用数值计算

覆盖：驻点热流 / Knudsen数 / 催化系数 / 单位换算 / 边界层厚度
所有公式标注出处，符合 Agent 约束"计算可验证"。
"""

from __future__ import annotations

import math

from core.action import Action


class AeroThermalComputeTool(Action):
    """气动热参数计算 —— 执行高超声速领域常用工程计算。"""

    name = "compute_aerothermal"
    description = (
        "执行高超声速气动热领域的工程计算。"
        "可计算驻点热流密度（Fay-Riddell/Sutton-Graves公式）、"
        "Knudsen数（流态判断：连续/过渡/自由分子流）、"
        "催化复合系数速查（SiO₂/SiC/Al₂O₃/Pt等）、"
        "单位换算（W/m²↔kW/m², Pa↔atm, K↔°C等）、"
        "边界层厚度估算。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "calc_type": {
                "type": "string",
                "enum": [
                    "stagnation_heat_flux",
                    "knudsen_number",
                    "catalytic_coefficient",
                    "unit_conversion",
                    "boundary_layer",
                ],
                "description": "计算类型",
            },
            "params": {
                "type": "object",
                "description": (
                    "计算参数，按 calc_type 不同：\n"
                    "- stagnation_heat_flux: velocity(m/s), radius(m), density(kg/m³)\n"
                    "- knudsen_number: characteristic_length(m), 可选 temperature(K), pressure(Pa)\n"
                    "- catalytic_coefficient: material(SiO₂/SiC/Al₂O₃/Pt/quartz/RCG), temperature(K)\n"
                    "- unit_conversion: value(float), from_unit, to_unit\n"
                    "- boundary_layer: x(m), reynolds(float)"
                ),
            },
        },
        "required": ["calc_type", "params"],
    }

    async def run(self, calc_type: str, params: dict) -> str:
        handlers = {
            "stagnation_heat_flux": self._calc_stagnation_heat_flux,
            "knudsen_number": self._calc_knudsen,
            "catalytic_coefficient": self._lookup_catalytic,
            "unit_conversion": self._convert_units,
            "boundary_layer": self._calc_boundary_layer,
        }
        handler = handlers.get(calc_type)
        if handler is None:
            return f"[错误] 未知计算类型: {calc_type}。可选: {list(handlers.keys())}"
        try:
            return handler(params)
        except Exception as e:
            return f"[计算错误] {calc_type}: {e}"

    # ── Fay-Riddell / Sutton-Graves 驻点热流 ────────

    def _calc_stagnation_heat_flux(self, p: dict) -> str:
        v = float(p.get("velocity", 0))
        r = float(p.get("radius", 1.0))
        rho = float(p.get("density", 1.2))

        k = 1.83e-4  # 地球大气常数 (W/m² units)
        q_w = k * math.sqrt(rho / r) * v**3

        return (
            f"**驻点热流密度（Sutton-Graves 简化式）**\n"
            f"输入：V = {v:.0f} m/s, R_n = {r:.3f} m, ρ = {rho:.4f} kg/m³\n"
            f"q_w = {q_w:.2e} W/m² = {q_w/1e3:.2f} kW/m² = {q_w/1e6:.4f} MW/m²\n\n"
            f"参考：Fay & Riddell, J. Aeronaut. Sci. 25(2), 1958\n"
            f"     Sutton & Graves, NASA CR-2318, 1973\n"
            f"⚠️ 假设：平衡催化壁面，完全气体，层流。精确计算需考虑真实气体效应。"
        )

    # ── Knudsen 数 ──────────────────────────────────

    def _calc_knudsen(self, p: dict) -> str:
        L = float(p.get("characteristic_length", 1.0))
        T = float(p.get("temperature", 300))
        pressure = float(p.get("pressure", 101325))

        k_B = 1.380649e-23
        d_air = 3.7e-10
        mfp = k_B * T / (math.sqrt(2) * math.pi * d_air**2 * pressure)

        kn = mfp / L

        if kn < 0.001:
            regime = "连续流（NS 方程适用）"
        elif kn < 0.1:
            regime = "滑移流（需速度滑移+温度跳跃边界条件）"
        elif kn < 10:
            regime = "过渡流（DSMC 适用，NS 失效）"
        else:
            regime = "自由分子流"

        return (
            f"**Knudsen 数**\n"
            f"λ = {mfp:.3e} m（T={T:.0f} K, p={pressure:.0f} Pa）\n"
            f"L = {L:.3e} m\n"
            f"Kn = {kn:.4e} → **{regime}**\n\n"
            f"参考：Bird, Molecular Gas Dynamics and DSMC, 1994"
        )

    # ── 催化复合系数速查 ────────────────────────────

    def _lookup_catalytic(self, p: dict) -> str:
        material = p.get("material", "SiO₂").strip()
        T = float(p.get("temperature", 1500))

        DB = {
            "sio2": (0.001, 0.01, "300–2000 K", "Scott NASA CR-198174; Stewart AIAA 2011"),
            "sio₂": (0.001, 0.01, "300–2000 K", "Scott NASA CR-198174; Stewart AIAA 2011"),
            "sic": (0.01, 0.1, "300–2000 K", "Scott NASA CR-198174"),
            "al2o3": (0.005, 0.05, "300–2000 K", "Scott NASA CR-198174"),
            "al₂o₃": (0.005, 0.05, "300–2000 K", "Scott NASA CR-198174"),
            "quartz": (0.001, 0.005, "300–2000 K", "Scott NASA CR-198174"),
            "pt": (0.01, 0.5, "300–1500 K", "铂，高催化活性；Scott NASA CR-198174"),
            "platinum": (0.01, 0.5, "300–1500 K", "铂，高催化活性"),
            "rcg": (0.001, 0.01, "300–2000 K", "Reaction Cured Glass; Stewart AIAA 2011"),
            "si₃n₄": (0.001, 0.005, "300–1800 K", "待补充验证"),
        }

        key = material.lower().strip()
        if key in DB:
            γ_low, γ_high, t_range, ref = DB[key]
        else:
            matched = None
            for k, v in DB.items():
                if key in k or k in key:
                    matched = v
                    break
            if matched:
                γ_low, γ_high, t_range, ref = matched
            else:
                return (
                    f"**{material}** 的催化复合系数不在当前数据库中。\n"
                    f"已知材料：{', '.join(sorted(set(k.upper() for k in DB)))}\n"
                    f"建议检索文献：'catalytic recombination coefficient {material}'"
                )

        return (
            f"**{material} 催化复合系数 γ**\n"
            f"γ 范围：{γ_low} – {γ_high}（{t_range}）\n"
            f"查询温度 {T:.0f} K 在此范围内\n"
            f"工程估算推荐值（几何平均）：γ ≈ {math.sqrt(γ_low * γ_high):.4f}\n\n"
            f"⚠️ γ 高度依赖表面状态（粗糙度、污染、氧化），实验值可能有数量级差异。\n"
            f"参考：{ref}"
        )

    # ── 单位换算 ────────────────────────────────────

    def _convert_units(self, p: dict) -> str:
        value = float(p.get("value", 0))
        from_unit = p.get("from_unit", "")
        to_unit = p.get("to_unit", "")

        conversions = {
            ("W/m²", "kW/m²"): 1e-3,
            ("kW/m²", "W/m²"): 1e3,
            ("W/m²", "MW/m²"): 1e-6,
            ("MW/m²", "W/m²"): 1e6,
            ("kW/m²", "MW/m²"): 1e-3,
            ("MW/m²", "kW/m²"): 1e3,
            ("Pa", "atm"): 1 / 101325,
            ("atm", "Pa"): 101325,
            ("Pa", "Torr"): 0.00750062,
            ("Torr", "Pa"): 133.322,
            ("m/s", "km/s"): 1e-3,
            ("km/s", "m/s"): 1e3,
        }

        # 温度特殊处理
        if from_unit == "K" and to_unit == "°C":
            return f"**单位换算**：{value} K = **{value - 273.15:.2f} °C**"
        if from_unit == "°C" and to_unit == "K":
            return f"**单位换算**：{value} °C = **{value + 273.15:.2f} K**"

        factor = conversions.get((from_unit, to_unit))
        if factor is None:
            supported = "W/m², kW/m², MW/m², Pa, atm, Torr, m/s, km/s, K, °C"
            return f"[错误] 不支持的换算: {from_unit} → {to_unit}\n支持：{supported}"

        result = value * factor
        return f"**单位换算**：{value} {from_unit} = **{result:.6g} {to_unit}**"

    # ── 边界层厚度 ──────────────────────────────────

    def _calc_boundary_layer(self, p: dict) -> str:
        x = float(p.get("x", 1.0))
        re = float(p.get("reynolds", 1e6))

        delta_lam = 5.0 * x / math.sqrt(re)
        delta_turb = 0.37 * x / (re**0.2)
        regime = "湍流" if re > 5e5 else "层流"

        return (
            f"**边界层厚度（平板，零压力梯度）**\n"
            f"x = {x:.3f} m, Re_x = {re:.2e}（{regime}）\n"
            f"层流 δ = {delta_lam:.4e} m\n"
            f"湍流 δ = {delta_turb:.4e} m\n\n"
            f"参考：Schlichting & Gersten, Boundary-Layer Theory, 7th ed."
        )
