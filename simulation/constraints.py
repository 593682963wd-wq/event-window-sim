"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional
import datetime as dt
from .chain_models import CandidateAobt

@dataclass(frozen=True)
class CtotWindow:
    ctot: dt.datetime
    window_start: dt.datetime
    window_end: dt.datetime
    early_tolerance_min: float
    late_tolerance_min: float

    def contains(self, value: dt.datetime) -> bool:
        return self.window_start <= value <= self.window_end

def ctot_window(ctot: dt.datetime, early_tolerance_min: float, late_tolerance_min: float) -> CtotWindow:
    """CTOT 容差窗口。"""
    if any((type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in (early_tolerance_min, late_tolerance_min))):
        raise ValueError('窗口容差须有限非负')
    return CtotWindow(ctot=ctot, window_start=ctot - dt.timedelta(minutes=early_tolerance_min), window_end=ctot + dt.timedelta(minutes=late_tolerance_min), early_tolerance_min=early_tolerance_min, late_tolerance_min=late_tolerance_min)

def ctot_implied_aobt(ctot: Optional[dt.datetime], taxi_out_min: Optional[float]) -> Optional[dt.datetime]:
    """CTOT 反推撤轮挡参考：CTOT - 预计滑出。"""
    if ctot is None or taxi_out_min is None:
        return None
    return ctot - dt.timedelta(minutes=taxi_out_min)

def max_constraint_aobt(candidates: list[CandidateAobt], *, include_expired: bool=False) -> tuple[Optional[dt.datetime], list[CandidateAobt], list[str]]:
    """可审计最大约束规则：predicted_AOBT = max(有效候选)。

    返回 (最终值, 达到最大值的候选列表, 全部候选的逐条理由)。
    include_expired=True 时（仅用于证据核对）过期候选也参与求值。
    """
    reasons = [f'{c.source}={c.value:%H:%M}' if c.value else f'{c.source}=无值' for c in candidates]
    reasons.append('规则：predicted_AOBT = max(有效候选)，取最大值作为可审计最大约束')
    if include_expired:
        usable = [c for c in candidates if c.value is not None]
    else:
        usable = [c for c in candidates if c.value is not None and c.valid]
    if not usable:
        return (None, [], reasons)
    peak = max(usable, key=lambda c: c.value)
    winners = [c for c in usable if c.value == peak.value]
    return (peak.value, winners, reasons)
