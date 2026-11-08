"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from dataclasses import dataclass

from enum import StrEnum

from .scenarios import ACTUAL_EVENTS

from .asof import ArtifactAvailability

from .scenarios import DurationComponent

from .enums import EventType

from .entities import FlightOccurrence

from .entities import FlightVersion

from .enums import HardCheck

from .scenarios import Trajectory

from .scenarios import TrajectorySample

from .entities import require_utc_seconds

from .scenarios import sample_trajectory

from .asof import visibility

class WaitLocation(StrEnum):
    """等待发生位置，按调用者给出的优先顺序选择可影响目标事件的位置。"""

    GATE = "GATE"
    TAXI_OUT = "TAXI_OUT"
    AIR = "AIR"
    TAXI_IN = "TAXI_IN"

@dataclass(frozen=True, slots=True)
class DurationComponents:
    """已知整秒时长；浮点分布样本须先验证为整秒再显式转换，不能截断。

    只有 BLOCK 时仅能解出 AOBT/AIBT。缺少分项不能反推起飞、落地，
    同时提供完整分项和 BLOCK 时必须一致，避免把总量叠加两次。
    """

    taxi_out_seconds: int | None = None
    air_seconds: int | None = None
    taxi_in_seconds: int | None = None
    block_seconds: int | None = None

    def __post_init__(self) -> None:
        values = (
            self.taxi_out_seconds,
            self.air_seconds,
            self.taxi_in_seconds,
            self.block_seconds,
        )
        for value in values:
            require_utc_seconds(value, "duration_seconds", nullable=True)
            if value is not None and value < 0:
                raise ValueError("时长不得为负")
        if (
            all(value is not None for value in values)
            and sum(values[:3]) != self.block_seconds
        ):
            raise ValueError("轮挡总量与三个完整分项不一致")
        if (
            self.block_seconds is not None
            and sum(value for value in values[:3] if value is not None)
            > self.block_seconds
        ):
            raise ValueError("已知分项合计超过轮挡总量")

@dataclass(frozen=True, slots=True)
class EventWindow:
    """单一机场、单一事件的许可窗口；None 表示端点或等待策略尚未确认。

    closure 必须显式给出 [)、[]、()、(]；无穷端由对应 bound=None 表示。
    allowed_wait_locations=() 明确禁止等待，None 表示业务口径未知。
    """

    constraint_ref: str
    airport: str
    event_type: EventType | None
    start_utc: int | None
    end_utc: int | None
    closure: str | None
    allowed_wait_locations: tuple[WaitLocation, ...] | None
    availability: ArtifactAvailability

    def __post_init__(self) -> None:
        if not self.constraint_ref or not self.airport:
            raise ValueError("事件窗必须指定约束引用和机场")
        if self.event_type is not None:
            object.__setattr__(self, "event_type", EventType(self.event_type))
            if self.event_type not in ACTUAL_EVENTS:
                raise ValueError("窗口只能约束实际四事件")
        for bound in (self.start_utc, self.end_utc):
            require_utc_seconds(bound, "window_bound", nullable=True)
        if (
            self.start_utc is not None
            and self.end_utc is not None
            and self.end_utc <= self.start_utc
        ):
            raise ValueError("窗口必须左早右晚")
        if self.closure is not None and self.closure not in {"[)", "[]", "()", "(]"}:
            raise ValueError("窗口闭合端点非法")
        if self.allowed_wait_locations is not None:
            object.__setattr__(
                self,
                "allowed_wait_locations",
                tuple(WaitLocation(x) for x in self.allowed_wait_locations),
            )

@dataclass(frozen=True, slots=True)
class WindowCheck:
    """具体事件的核验，不能用另一事件代替。"""

    constraint_ref: str
    event_type: EventType | None
    event_utc: int | None
    status: HardCheck
    reason_codes: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class EventSolution:
    """条件事件结果；PASS 只指提供的窗口，不代表全专业可行。"""

    aobt: int | None
    atot: int | None
    aldt: int | None
    aibt: int | None
    status: HardCheck
    reason_codes: tuple[str, ...]
    iterations: int
    window_checks: tuple[WindowCheck, ...] = ()
    exposures: tuple[TrajectorySample, ...] = ()
    wait_seconds: tuple[int, int, int, int] = (0, 0, 0, 0)

    def at(self, event_type: EventType) -> int | None:
        """按事件名称读取，计划事件不伪装为实际值。"""
        event_type = EventType(event_type)
        if event_type not in ACTUAL_EVENTS:
            raise ValueError("仅支持实际四事件")
        return (self.aobt, self.atot, self.aldt, self.aibt)[
            ACTUAL_EVENTS.index(event_type)
        ]

def _window_reasons(window: EventWindow, cutoff_at: int) -> tuple[str, ...]:
    source = window.availability
    result = visibility(
        source.published_at,
        source.observed_at,
        cutoff_at,
        snapshot_ref=source.snapshot_ref,
    )
    reasons = list(result.reason_codes)
    if not source.reference:
        reasons.append("E_WINDOW_SOURCE_MISSING")
    if window.event_type is None:
        reasons.append("E_WINDOW_EVENT_UNKNOWN")
    if window.closure is None or (window.start_utc is None and window.end_utc is None):
        reasons.append("E_WINDOW_ENDPOINT_UNKNOWN")
    if window.allowed_wait_locations is None:
        reasons.append("E_WAIT_LOCATION_UNKNOWN")
    return tuple(reasons)

def check_event_window(
    window: EventWindow,
    *,
    airport: str,
    event_type: EventType,
    event_utc: int | None,
    cutoff_at: int,
) -> WindowCheck:
    """对调用方明确提供的机场和事件检查，不以挡轮替代落地。"""
    require_utc_seconds(event_utc, "event_utc", nullable=True)
    reasons = list(_window_reasons(window, cutoff_at))
    if window.airport != airport or window.event_type != event_type:
        reasons.append("E_WINDOW_EVENT_OR_AIRPORT_MISMATCH")
    if event_utc is None:
        reasons.append("E_REQUIRED_EVENT_UNKNOWN")
    if reasons:
        return WindowCheck(
            window.constraint_ref,
            window.event_type,
            event_utc,
            HardCheck.UNKNOWN,
            tuple(reasons),
        )
    left = window.start_utc is None or (
        event_utc >= window.start_utc
        if window.closure[0] == "["
        else event_utc > window.start_utc
    )
    right = window.end_utc is None or (
        event_utc <= window.end_utc
        if window.closure[1] == "]"
        else event_utc < window.end_utc
    )
    passed = left and right
    return WindowCheck(
        window.constraint_ref,
        window.event_type,
        event_utc,
        HardCheck.PASS if passed else HardCheck.FAIL,
        () if passed else ("E_EVENT_OUTSIDE_WINDOW",),
    )

def _timeline(
    earliest: int,
    durations: DurationComponents,
    extras: dict[DurationComponent, int],
    waits: list[int],
) -> tuple[int, int | None, int | None, int | None]:
    aobt = earliest + waits[0]
    taxi = (
        None
        if durations.taxi_out_seconds is None
        else durations.taxi_out_seconds + extras[DurationComponent.TAXI_OUT]
    )
    air = (
        None
        if durations.air_seconds is None
        else durations.air_seconds + extras[DurationComponent.AIR]
    )
    taxi_in = (
        None
        if durations.taxi_in_seconds is None
        else durations.taxi_in_seconds + extras[DurationComponent.TAXI_IN]
    )
    atot = None if taxi is None else aobt + taxi + waits[1]
    aldt = None if atot is None or air is None else atot + air + waits[2]
    if durations.block_seconds is not None:
        aibt = aobt + durations.block_seconds + sum(extras.values()) + sum(waits[1:])
    elif aldt is not None and taxi_in is not None:
        aibt = aldt + taxi_in + waits[3] + extras[DurationComponent.BLOCK]
    else:
        aibt = None
    if extras[DurationComponent.BLOCK]:
        # 总轮挡扰动没有分项落点证据，不能保留看似准确的起飞/落地。
        atot, aldt = None, None
    return aobt, atot, aldt, aibt

def _unknown(
    reasons: tuple[str, ...],
    iterations: int,
    exposures: tuple[TrajectorySample, ...] = (),
) -> EventSolution:
    return EventSolution(
        None,
        None,
        None,
        None,
        HardCheck.UNKNOWN,
        tuple(dict.fromkeys(reasons)),
        iterations,
        exposures=exposures,
    )

def solve_events(
    *,
    flight: FlightVersion,
    occurrence: FlightOccurrence,
    earliest_aobt: int,
    durations: DurationComponents,
    trajectories: tuple[Trajectory, ...] = (),
    constraints: tuple[EventWindow, ...] = (),
    cutoff_at: int,
    max_iterations: int = 32,
) -> EventSolution:
    """有界固定点重算四事件及外生暴露；未收敛不返回最后一轮候选时刻。

    earliest_aobt 已含前机/保障/人员等外部就绪要求，本函数再取计划撤轮下限。
    输入仅包含一个情景；允许传入其他机场的全局轨迹和窗口，会按机场角色筛选。
    只能求解显式等待策略的条件固定点，不宣称离散非单调轨迹的全局最早解。
    """
    require_utc_seconds(earliest_aobt, "earliest_aobt")
    require_utc_seconds(cutoff_at, "cutoff_at")
    if type(max_iterations) is not int or not 1 <= max_iterations <= 10_000:
        raise ValueError("迭代次数必须为1至10000的整数")
    if flight.flight_id != occurrence.flight_id:
        raise ValueError("计划版本与逻辑航段不匹配")
    if len({row.trajectory_ref for row in trajectories}) != len(trajectories):
        raise ValueError("轨迹重复会叠加扰动")
    if len({row.scenario_id for row in trajectories}) > 1:
        raise ValueError("一次求解不能混合多个外生情景")
    if len({row.constraint_ref for row in constraints}) != len(constraints):
        raise ValueError("窗口引用重复")
    airports = (
        occurrence.origin,
        occurrence.origin,
        occurrence.destination,
        occurrence.destination,
    )
    active_trajectories = tuple(
        row
        for row in trajectories
        if row.airport == airports[ACTUAL_EVENTS.index(row.exposure_event)]
    )
    active_windows = tuple(
        row
        for row in constraints
        if row.airport in {occurrence.origin, occurrence.destination}
        and (
            row.event_type is None
            or row.airport == airports[ACTUAL_EVENTS.index(row.event_type)]
        )
    )
    for window in active_windows:
        reasons = _window_reasons(window, cutoff_at)
        if reasons:
            return _unknown(reasons, 0)
    # 撤轮等待会平移后续全部事件，必须先求上游下限，避免按输入行序重复补等待。
    # 同事件按有效下限和稳定引用排序；调用者传入顺序不构成运行策略。
    active_windows = tuple(
        sorted(
            active_windows,
            key=lambda row: (
                ACTUAL_EVENTS.index(row.event_type),
                -1
                if row.start_utc is None
                else row.start_utc + (row.closure[0] == "("),
                row.constraint_ref,
            ),
        )
    )
    if len({row.component for row in active_trajectories}) != len(active_trajectories):
        return _unknown(("E_EXPOSURE_COMPOSITION_UNCONFIRMED",), 0)
    if any(
        row.component == DurationComponent.BLOCK for row in active_trajectories
    ) and any(row.component != DurationComponent.BLOCK for row in active_trajectories):
        return _unknown(("E_TOTAL_AND_COMPONENT_EXPOSURE_CONFLICT",), 0)
    earliest = max(flight.sobt_utc, earliest_aobt)
    zero_extras = {component: 0 for component in DurationComponent}
    candidate = _timeline(earliest, durations, zero_extras, [0, 0, 0, 0])
    seen = {candidate}
    for iteration in range(1, max_iterations + 1):
        samples = tuple(
            sample_trajectory(
                row,
                event_utc=candidate[ACTUAL_EVENTS.index(row.exposure_event)],
                cutoff_at=cutoff_at,
            )
            for row in active_trajectories
        )
        failures = tuple(
            reason
            for sample in samples
            if sample.status != HardCheck.PASS
            for reason in sample.reason_codes
        )
        if failures:
            return _unknown(failures, iteration, samples)
        extras = dict(zero_extras)
        for trajectory, sample in zip(active_trajectories, samples, strict=True):
            extras[trajectory.component] += sample.extra_seconds
        waits = [0, 0, 0, 0]
        for window in active_windows:
            index = ACTUAL_EVENTS.index(window.event_type)
            value = _timeline(earliest, durations, extras, waits)[index]
            if value is None:
                return _unknown(("E_REQUIRED_EVENT_UNKNOWN",), iteration, samples)
            lower = window.start_utc
            if lower is not None:
                lower += window.closure[0] == "("
                if value < lower:
                    positions = [
                        list(WaitLocation).index(place)
                        for place in window.allowed_wait_locations
                        if list(WaitLocation).index(place) <= index
                    ]
                    if positions:
                        waits[positions[0]] += lower - value
        updated = _timeline(earliest, durations, extras, waits)
        if updated == candidate:
            checks = tuple(
                check_event_window(
                    window,
                    airport=airports[ACTUAL_EVENTS.index(window.event_type)],
                    event_type=window.event_type,
                    event_utc=updated[ACTUAL_EVENTS.index(window.event_type)],
                    cutoff_at=cutoff_at,
                )
                for window in active_windows
            )
            status = (
                HardCheck.FAIL
                if any(check.status == HardCheck.FAIL for check in checks)
                else HardCheck.PASS
            )
            reasons = tuple(
                dict.fromkeys(
                    reason for check in checks for reason in check.reason_codes
                )
            )
            if updated[3] is None and not checks:
                status, reasons = HardCheck.UNKNOWN, ("E_ARRIVAL_DURATION_UNKNOWN",)
            elif any(value is None for value in updated):
                reasons += ("EVENT_SUBSET_ONLY",)
            return EventSolution(
                *updated, status, reasons, iteration, checks, samples, tuple(waits)
            )
        if updated in seen:
            return _unknown(("E_EVENT_ITERATION_CYCLE",), iteration, samples)
        seen.add(updated)
        candidate = updated
    return _unknown(("E_EVENT_ITERATION_LIMIT",), max_iterations)
