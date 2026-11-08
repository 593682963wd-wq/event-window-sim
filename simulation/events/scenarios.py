"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from dataclasses import dataclass

from enum import StrEnum

from itertools import pairwise

from .asof import ArtifactAvailability

from .enums import EventType

from .enums import HardCheck

from .entities import ScenarioSet

from .asof import effective_at

from .entities import require_utc_seconds

from .asof import visibility

ACTUAL_EVENTS = (EventType.AOBT, EventType.ATOT, EventType.ALDT, EventType.AIBT)

class DurationComponent(StrEnum):
    """扰动所增加的时长分项；轮挡总量不能再次叠加分项总量。"""

    TAXI_OUT = "TAXI_OUT"
    AIR = "AIR"
    TAXI_IN = "TAXI_IN"
    BLOCK = "BLOCK"

@dataclass(frozen=True, slots=True)
class TrajectoryInterval:
    """显式闭合端点的绝对时间片；空增量仍表示未知。"""

    start_utc: int
    end_utc: int
    closure: str
    extra_seconds: int | None

    def __post_init__(self) -> None:
        require_utc_seconds(self.start_utc, "start_utc")
        require_utc_seconds(self.end_utc, "end_utc")
        if self.end_utc <= self.start_utc or self.closure not in {
            "[)",
            "[]",
            "()",
            "(]",
        }:
            raise ValueError("轨迹区间或闭合端点非法")
        require_utc_seconds(self.extra_seconds, "extra_seconds", nullable=True)
        if self.extra_seconds is not None and self.extra_seconds < 0:
            raise ValueError("外生附加时长不得为负")

@dataclass(frozen=True, slots=True)
class Trajectory:
    """与计划无关的机场场；来源可见性在调用时按显式截止核验。"""

    trajectory_ref: str
    scenario_id: str
    airport: str
    exposure_event: EventType
    component: DurationComponent
    intervals: tuple[TrajectoryInterval, ...]
    availability: ArtifactAvailability

    def __post_init__(self) -> None:
        for value in (self.trajectory_ref, self.scenario_id, self.airport):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("轨迹、情景和机场引用不得为空")
        object.__setattr__(self, "exposure_event", EventType(self.exposure_event))
        object.__setattr__(self, "component", DurationComponent(self.component))
        if self.exposure_event not in ACTUAL_EVENTS:
            raise ValueError("暴露必须对应实际四事件")
        intervals = tuple(sorted(self.intervals, key=lambda row: row.start_utc))
        if not intervals:
            raise ValueError("轨迹至少提供一个有明确端点的时间片")
        for left, right in pairwise(intervals):
            if left.end_utc > right.start_utc or (
                left.end_utc == right.start_utc
                and left.closure[1] == "]"
                and right.closure[0] == "["
            ):
                raise ValueError("轨迹时间片重叠，不能任意选择其中一条")
        object.__setattr__(self, "intervals", intervals)

@dataclass(frozen=True, slots=True)
class TrajectorySample:
    """一次真实事件时刻上的取样证据；未覆盖不能补零。"""

    trajectory_ref: str
    event_utc: int | None
    extra_seconds: int | None
    status: HardCheck
    reason_codes: tuple[str, ...]

def sample_trajectory(
    trajectory: Trajectory, *, event_utc: int | None, cutoff_at: int
) -> TrajectorySample:
    """仅按机场场自身的绝对时间取值；每次改时须再次调用。"""
    require_utc_seconds(event_utc, "event_utc", nullable=True)
    source = trajectory.availability
    visible = visibility(
        source.published_at,
        source.observed_at,
        cutoff_at,
        snapshot_ref=source.snapshot_ref,
    )
    reasons = list(visible.reason_codes)
    if not source.reference:
        reasons.append("E_TRAJECTORY_SOURCE_MISSING")
    if event_utc is None:
        reasons.append("E_EXPOSURE_EVENT_UNKNOWN")
    if reasons:
        return TrajectorySample(
            trajectory.trajectory_ref,
            event_utc,
            None,
            HardCheck.UNKNOWN,
            tuple(reasons),
        )
    matches = [
        interval
        for interval in trajectory.intervals
        if effective_at(
            interval.start_utc, interval.end_utc, event_utc, closure=interval.closure
        )
    ]
    if not matches or matches[0].extra_seconds is None:
        reason = (
            "E_TRAJECTORY_NOT_COVERED" if not matches else "E_TRAJECTORY_VALUE_UNKNOWN"
        )
        return TrajectorySample(
            trajectory.trajectory_ref, event_utc, None, HardCheck.UNKNOWN, (reason,)
        )
    return TrajectorySample(
        trajectory.trajectory_ref,
        event_utc,
        matches[0].extra_seconds,
        HardCheck.PASS,
        (),
    )

def select_scenario_trajectories(
    *, scenario_set: ScenarioSet, scenario_id: str, trajectories: tuple[Trajectory, ...]
) -> tuple[Trajectory, ...]:
    """显式匹配冻结目录，不查询最新情景，也不默默漏掉引用。"""
    if scenario_id not in scenario_set.scenario_ids:
        raise ValueError("情景不在指定情景集")
    refs = [item.trajectory_ref for item in trajectories]
    if len(refs) != len(set(refs)) or set(refs) != set(scenario_set.trajectory_refs):
        raise ValueError("轨迹目录与冻结引用不一致或存在重复")
    if any(item.scenario_id not in scenario_set.scenario_ids for item in trajectories):
        raise ValueError("轨迹归属未知情景")
    return tuple(item for item in trajectories if item.scenario_id == scenario_id)
