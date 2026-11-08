"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from collections.abc import Sequence

from dataclasses import dataclass

from statistics import median

import math

@dataclass(frozen=True)
class RobustFilterResult:
    values: tuple[float, ...]
    kept_indexes: tuple[int, ...]
    excluded_count: int
    center: float | None
    scale: float | None
    method: str

def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0 <= q <= 1:
        raise ValueError("q must be between 0 and 1")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

def weighted_percentile(
    values: Sequence[float],
    weights: Sequence[float],
    q: float,
) -> float:
    """Return a deterministic weighted nearest-rank percentile."""

    if not values:
        raise ValueError("weighted_percentile requires at least one value")
    if len(values) != len(weights):
        raise ValueError("values and weights must have the same length")
    if not 0 <= q <= 1:
        raise ValueError("q must be between 0 and 1")
    pairs = sorted(
        (float(value), max(0.0, float(weight)))
        for value, weight in zip(values, weights)
    )
    total = sum(weight for _value, weight in pairs)
    if total <= 0:
        pairs = [(value, 1.0) for value, _weight in pairs]
        total = float(len(pairs))
    else:
        pairs = [(value, weight) for value, weight in pairs if weight > 0]
    target = q * total
    cumulative = 0.0
    for value, weight in pairs:
        cumulative += weight
        if cumulative >= target:
            return value
    return pairs[-1][0]

def robust_filter(
    values: Sequence[float],
    *,
    minimum_samples: int,
    mad_limit: float,
    absolute_jitter: float,
    relative_jitter: float,
    minimum_retained: int,
    retention_fraction: float,
) -> RobustFilterResult:
    """Deterministically remove statistical extremes without assuming normality.

    The primary fence is median absolute deviation (MAD).  When rounded
    operational minutes make MAD zero, a conservative IQR/absolute fence is
    used.  Small cohorts are left untouched so a single legitimate operation
    is not silently discarded.
    """

    if type(minimum_samples) is not int or minimum_samples<1 or type(minimum_retained) is not int or minimum_retained<0:raise ValueError("样本门槛必须为有效整数")
    if any(not math.isfinite(x) or x<0 for x in (mad_limit,absolute_jitter,relative_jitter,retention_fraction)) or retention_fraction>1:raise ValueError("稳健筛选参数无效")
    finite = [
        (index, float(value))
        for index, value in enumerate(values)
        if math.isfinite(float(value))
    ]
    if not finite:
        return RobustFilterResult((), (), len(values), None, None, "empty")
    raw_values = [value for _, value in finite]
    center = float(median(raw_values))
    deviations = [abs(value - center) for value in raw_values]
    mad = float(median(deviations))
    if len(raw_values) < minimum_samples:
        return RobustFilterResult(
            tuple(raw_values),
            tuple(index for index, _ in finite),
            len(values) - len(raw_values),
            center,
            1.4826 * mad if mad else 0.0,
            "small_sample_no_statistical_exclusion",
        )

    if mad > 0:
        scale = 1.4826 * mad
        keep = [
            (index, value)
            for index, value in finite
            if abs(value - center) / scale <= mad_limit
        ]
        method = "mad"
    else:
        q1 = percentile(raw_values, 0.25)
        q3 = percentile(raw_values, 0.75)
        iqr = q3 - q1
        if iqr > 0:
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            scale = iqr / 1.349
        else:
            # Minute-rounded samples often share one value.  A five-minute or
            # ten-percent fence keeps normal operational jitter but removes a
            # lone maintenance/overnight extreme.
            tolerance = max(absolute_jitter, abs(center) * relative_jitter)
            lower = center - tolerance
            upper = center + tolerance
            scale = tolerance
        keep = [
            (index, value)
            for index, value in finite
            if lower <= value <= upper
        ]
        method = "iqr"

    # Never let the statistical pass collapse a cohort below half its rows.
    if len(keep) < max(minimum_retained, math.ceil(len(finite) * retention_fraction)):
        keep = finite
        method = "guarded_no_exclusion"
    return RobustFilterResult(
        tuple(value for _, value in keep),
        tuple(index for index, _ in keep),
        len(values) - len(keep),
        center,
        scale,
        method,
    )

def huber_location(
    values: Sequence[float],
    *,
    tuning: float = 1.345,
    max_iterations: int = 50,
    tolerance: float = 1e-6,
) -> float:
    """Return a robust intercept-only regression estimate (Huber IRLS)."""

    if not values:
        raise ValueError("huber_location requires at least one value")
    clean = [float(value) for value in values if math.isfinite(float(value))]
    if not clean:
        raise ValueError("huber_location requires a finite value")
    location = float(median(clean))
    mad = float(median(abs(value - location) for value in clean))
    scale = 1.4826 * mad
    if scale <= 1e-9:
        return location
    threshold = tuning * scale
    for _ in range(max_iterations):
        weights = []
        for value in clean:
            distance = abs(value - location)
            weights.append(1.0 if distance <= threshold else threshold / distance)
        denominator = sum(weights)
        updated = sum(
            weight * value for weight, value in zip(weights, clean)
        ) / denominator
        if abs(updated - location) <= tolerance:
            return updated
        location = updated
    return location

def weighted_huber_location(
    values: Sequence[float],
    weights: Sequence[float],
    *,
    tuning: float = 1.345,
    max_iterations: int = 50,
    tolerance: float = 1e-6,
) -> float:
    """返回带基础样本权重的稳健 Huber 中心。

    基础权重用于表达样本的新近程度或质量，Huber 权重用于抑制极端值。
    两类权重相乘后参与迭代，避免近期单个异常样本直接拉动中心。
    """

    if not values:
        raise ValueError("weighted_huber_location requires at least one value")
    if len(values) != len(weights):
        raise ValueError("values and weights must have the same length")
    clean = [
        (float(value), max(0.0, float(weight)))
        for value, weight in zip(values, weights)
        if math.isfinite(float(value)) and math.isfinite(float(weight))
    ]
    if not clean:
        raise ValueError("weighted_huber_location requires a finite value")
    clean_values = [value for value, _weight in clean]
    base_weights = [weight for _value, weight in clean]
    if not any(base_weights):
        base_weights = [1.0] * len(clean_values)

    location = weighted_percentile(clean_values, base_weights, 0.50)
    deviations = [abs(value - location) for value in clean_values]
    scale = 1.4826 * weighted_percentile(deviations, base_weights, 0.50)
    if scale <= 1e-9:
        return location

    threshold = tuning * scale
    for _ in range(max_iterations):
        effective_weights = []
        for value, base_weight in zip(clean_values, base_weights):
            distance = abs(value - location)
            robust_weight = (
                1.0 if distance <= threshold else threshold / distance
            )
            effective_weights.append(base_weight * robust_weight)
        denominator = sum(effective_weights)
        if denominator <= 0:
            return location
        updated = sum(
            weight * value
            for weight, value in zip(effective_weights, clean_values)
        ) / denominator
        if abs(updated - location) <= tolerance:
            return updated
        location = updated
    return location
