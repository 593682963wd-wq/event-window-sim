"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from dataclasses import dataclass

import math

from fractions import Fraction

@dataclass(frozen=True)
class ScenarioSet:
    """调用方明确给出情景目录与概率，None 表示仅作压力情景比较。"""
    scenario_ids: tuple[str, ...]
    weights: tuple[float, ...] | None


PROBABILITY_TOLERANCE = Fraction(1, 10**12)

STATISTICS_VERSION = "rational-inverse-cdf-boundary-tail-v1"

def _number(value: float, label: str) -> Fraction:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label}必须为有限数值")
    return Fraction(str(value))

def _weighted(
    values: Sequence[float], probabilities: Sequence[float]
) -> tuple[tuple[Fraction, Fraction], ...]:
    if not values or len(values) != len(probabilities):
        raise ValueError("数值与概率必须等长且非空")
    numbers = tuple(_number(value, "观测值") for value in values)
    masses = tuple(_number(p, "概率") for p in probabilities)
    total = sum(masses)
    if any(p < 0 for p in masses) or abs(total - 1) > PROBABILITY_TOLERANCE:
        raise ValueError("概率必须非负且已归一化为1")
    # 仅消除冻结容差内的十进制表示误差，不校准未经归一化的权重。
    return tuple(
        sorted(
            (value, mass / total)
            for value, mass in zip(numbers, masses, strict=True)
            if mass > 0
        )
    )

def inverse_cdf(
    values: Sequence[float], probabilities: Sequence[float], probability: float
) -> float:
    """取 inf{x:F(x)≥p}；以有理数累加并使用固定比较容差。"""
    p = _number(probability, "分位概率")
    if not 0 <= p <= 1:
        raise ValueError("分位概率必须位于[0,1]")
    pairs = _weighted(values, probabilities)
    cumulative = Fraction(0)
    for value, mass in pairs:
        cumulative += mass
        if cumulative + PROBABILITY_TOLERANCE >= p:
            return float(value)
    return float(pairs[-1][0])

def worst_tail_mean(
    values: Sequence[float], probabilities: Sequence[float], tail_probability: float
) -> float:
    """按最差的指定概率质量求均值，边界原子只取所需质量。"""
    tail = _number(tail_probability, "尾部质量")
    if not 0 < tail <= 1:
        raise ValueError("尾部质量必须位于(0,1]")
    remaining, numerator = tail, Fraction(0)
    for value, mass in reversed(_weighted(values, probabilities)):
        take = min(remaining, mass)
        numerator += value * take
        remaining -= take
        if remaining == 0:
            break
    return float(numerator / tail)

@dataclass(frozen=True, slots=True)
class RiskSummary:
    """标量情景结果，单位由调用方声明；完整性和概率资格互相独立。"""

    mode: str
    expected_value: float | None
    quantile: float | None
    tail_mean: float | None
    minimum: float | None
    maximum: float | None
    expected_count: int
    valid_count: int
    quantile_probability: float
    tail_probability: float
    reason_codes: tuple[str, ...]
    statistics_version: str = STATISTICS_VERSION

def summarize_risk(
    outcomes: Mapping[str, float | None],
    *,
    scenario_set: ScenarioSet,
    quantile_probability: float = 0.9,
    tail_probability: float = 0.1,
) -> RiskSummary:
    """按情景ID匹配冻结权重；部分未知时保留计数而不改分母算期望。"""
    ids = scenario_set.scenario_ids
    if not ids or len(set(ids)) != len(ids) or set(outcomes) != set(ids):
        raise ValueError("结果须与非空、唯一的冻结情景目录完全匹配")
    q, tail = (
        _number(quantile_probability, "分位概率"),
        _number(tail_probability, "尾部质量"),
    )
    if not 0 <= q <= 1 or not 0 < tail <= 1:
        raise ValueError("分位概率或尾部质量非法")
    values = tuple(outcomes[key] for key in ids)
    for value in values:
        if value is not None:
            _number(value, "观测值")
    valid = sum(value is not None for value in values)
    weights = scenario_set.weights
    mode = "PRESSURE" if weights is None else "PROBABILISTIC"
    reasons = []
    if weights is not None:
        _weighted([0] * len(ids), weights)
    else:
        reasons.append("E_PROBABILITY_UNAVAILABLE")
    if valid != len(ids):
        reasons.append("E_SCENARIO_OUTCOME_UNKNOWN")
    expected = quantile = tail_mean = minimum = maximum = None
    if valid == len(ids):
        minimum, maximum = min(values), max(values)
        if weights is not None:
            expected = float(
                sum(value * mass for value, mass in _weighted(values, weights))
            )
            quantile = inverse_cdf(values, weights, quantile_probability)
            tail_mean = worst_tail_mean(values, weights, tail_probability)
    return RiskSummary(
        mode,
        expected,
        quantile,
        tail_mean,
        minimum,
        maximum,
        len(ids),
        valid,
        quantile_probability,
        tail_probability,
        tuple(reasons),
    )

def correlated_totals(
    outcomes: Mapping[str, Mapping[str, float | None]],
) -> dict[str, float | None]:
    """先在同情景内合计对象，拒绝对象集合漂移，不能把边际分位数相加。"""
    if not outcomes:
        raise ValueError("同情景聚合不能为空")
    targets = set(next(iter(outcomes.values())))
    if not targets or any(set(row) != targets for row in outcomes.values()):
        raise ValueError("各情景必须覆盖同一个非空对象集合")
    totals = {}
    for identity, row in sorted(outcomes.items()):
        known = [
            _number(row[key], "观测值")
            for key in sorted(targets)
            if row[key] is not None
        ]
        totals[identity] = float(sum(known)) if len(known) == len(targets) else None
    return totals
