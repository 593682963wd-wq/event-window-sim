"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from typing import Any

@dataclass(frozen=True)
class SegmentSample:
    sample_key: str
    flight_key: str
    segment_key: str
    business_date: str
    aircraft_type: str
    planned_block_seconds: int
    actual_block_seconds: int
    taxi_out_seconds: int | None
    airborne_seconds: int | None
    taxi_in_seconds: int | None
    calculation_method: str
    quality_status: str = "valid"
    exclusion_reason: str = ""
    source_mode: str = "user_input"
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class WindowStatistics:
    window: str
    start_date: str
    end_date: str
    sample_count: int = 0
    excluded_count: int = 0
    average_actual_seconds: int | None = None
    average_planned_seconds: int | None = None
    average_paired_gap_seconds: int | None = None
    current_plan_gap_seconds: int | None = None
    p50_actual_seconds: int | None = None
    p80_actual_seconds: int | None = None
    min_actual_seconds: int | None = None
    max_actual_seconds: int | None = None
    confidence: str = "insufficient"
    coverage_dates: tuple[str, ...] = ()
    excluded_reasons: dict[str, int] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        return self.sample_count > 0 and self.current_plan_gap_seconds is not None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
