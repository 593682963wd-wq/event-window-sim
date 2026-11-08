"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from dataclasses import dataclass

import math

_TOLERANCE = 1e-12

@dataclass(frozen=True, slots=True)
class DurationDistribution:
    """校准后的非负秒值与对应概率；同值合并后按秒数升序保存。"""

    seconds: tuple[float, ...]
    probabilities: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.seconds or len(self.seconds) != len(self.probabilities):
            raise ValueError("分布需要等长且非空的秒值和概率")
        if any(
            type(x) not in (int, float) or not math.isfinite(x) or x < 0
            for x in self.seconds
        ):
            raise ValueError("时长必须为有限非负秒数")
        if any(
            type(p) not in (int, float) or not math.isfinite(p) or p < 0
            for p in self.probabilities
        ):
            raise ValueError("概率必须为有限非负数")
        total = math.fsum(self.probabilities)
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=_TOLERANCE):
            raise ValueError("概率必须已校准并归一化为1")
        merged: dict[float, float] = {}
        for value, probability in zip(self.seconds, self.probabilities, strict=True):
            merged[float(value)] = merged.get(float(value), 0.0) + float(probability)
        pairs = [
            (value, probability)
            for value, probability in sorted(merged.items())
            if probability > 0
        ]
        if not pairs:
            raise ValueError("分布需要正概率质量")
        norm = math.fsum(probability for _, probability in pairs)
        object.__setattr__(self, "seconds", tuple(value for value, _ in pairs))
        object.__setattr__(
            self, "probabilities", tuple(probability / norm for _, probability in pairs)
        )

    def exceed_probability(self, threshold_seconds: float) -> float:
        """返回严格超过阈值的概率 P(X>threshold)。"""
        _require_finite(threshold_seconds, "阈值")
        return math.fsum(
            p
            for x, p in zip(self.seconds, self.probabilities, strict=True)
            if x > threshold_seconds
        )

    def quantile(self, probability: float) -> float:
        """按逆经验 CDF 取 inf{x:F(x)≥p}，边界用固定容差。"""
        _require_finite(probability, "分位概率")
        if not 0 <= probability <= 1:
            raise ValueError("分位概率必须位于[0,1]")
        cumulative = 0.0
        for x, mass in zip(self.seconds, self.probabilities, strict=True):
            cumulative = math.fsum((cumulative, mass))
            if cumulative + _TOLERANCE >= probability:
                return x
        return self.seconds[-1]

    def expected_positive_gap(self, threshold_seconds: float) -> float:
        """返回 E[(X-threshold)+]，单位为秒。"""
        _require_finite(threshold_seconds, "阈值")
        return math.fsum(
            max(x - threshold_seconds, 0.0) * p
            for x, p in zip(self.seconds, self.probabilities, strict=True)
        )

    def plan_buffer(self, scheduled_seconds: float) -> float:
        """返回 max(计划秒数-Q50,0)，仅可用于有分布的轮挡时长。"""
        _require_finite(scheduled_seconds, "计划时长")
        if scheduled_seconds < 0:
            raise ValueError("计划时长不得为负")
        return max(scheduled_seconds - self.quantile(0.5), 0.0)

def _require_finite(value: float, name: str) -> None:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name}必须为有限数值")
