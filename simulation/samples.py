"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""
from __future__ import annotations
from collections import Counter
from statistics import mean
from typing import Iterable
import datetime as dt
import math
from .sample_models import SegmentSample
from .sample_models import WindowStatistics

def window_ranges(day: dt.date, season_start: dt.date) -> dict[str, tuple[dt.date, dt.date]]:
    end = day - dt.timedelta(days=1)
    if season_start is not None and season_start > end:
        raise ValueError('航季开始日不能晚于查询日前一日。')
    return {'rolling_30': (day - dt.timedelta(days=30), end), 'season_to_date': (season_start, end)}

def confidence_for(count: int, *, formal: int, review: int, high: int) -> str:
    if count >= high:
        return 'high'
    if count >= formal:
        return 'medium'
    if count >= review:
        return 'low'
    return 'insufficient'

def aggregate_window(window: str, start: dt.date, end: dt.date, samples: Iterable[SegmentSample], current_planned_seconds: int, *, formal: int, review: int, high: int) -> WindowStatistics:
    if start > end or current_planned_seconds < 0:
        raise ValueError('日期范围或计划秒数无效')
    if not 0 <= review <= formal <= high:
        raise ValueError('样本数门槛须按升序非负')
    included: list[SegmentSample] = []
    exclusions: Counter[str] = Counter()
    for sample in samples:
        try:
            sample_date = dt.date.fromisoformat(sample.business_date)
        except ValueError:
            exclusions['invalid_business_date'] += 1
            continue
        if not start <= sample_date <= end:
            continue
        if sample.quality_status != 'valid':
            exclusions[sample.exclusion_reason or sample.quality_status] += 1
            continue
        if any((type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (sample.actual_block_seconds, sample.planned_block_seconds))):
            exclusions['invalid_duration'] += 1
            continue
        included.append(sample)
    if not included:
        return WindowStatistics(window=window, start_date=start.isoformat(), end_date=end.isoformat(), excluded_count=sum(exclusions.values()), excluded_reasons=dict(exclusions), warnings=('no_valid_samples',))
    actual = [item.actual_block_seconds for item in included]
    planned = [item.planned_block_seconds for item in included]
    paired = [item.actual_block_seconds - item.planned_block_seconds for item in included]
    avg_actual = round(mean(actual))
    return WindowStatistics(window=window, start_date=start.isoformat(), end_date=end.isoformat(), sample_count=len(included), excluded_count=sum(exclusions.values()), average_actual_seconds=avg_actual, average_planned_seconds=round(mean(planned)), average_paired_gap_seconds=round(mean(paired)), current_plan_gap_seconds=avg_actual - current_planned_seconds, p50_actual_seconds=_percentile(actual, 0.5), p80_actual_seconds=_percentile(actual, 0.8), min_actual_seconds=min(actual), max_actual_seconds=max(actual), confidence=confidence_for(len(included), formal=formal, review=review, high=high), coverage_dates=tuple(sorted({item.business_date for item in included})), excluded_reasons=dict(exclusions))

def _percentile(values: list[int], quantile: float) -> int:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower))
