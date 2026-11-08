"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing import Any, Optional

import datetime as dt

@dataclass
class FlightOccurrence:
    flight_key: str
    business_date: str
    flight_no: str
    origin: str          # 归一化机场键（优先 ICAO）
    destination: str
    occurrence_index: int = 1   # 同航班号同日多发生实例序号（由调用方区分重复发生实例）
    plane_no: str = ""
    plane_type: str = ""
    status: str = ""
    abnormal_type: str = ""
    abnormal_reason: str = ""
    result_kind: str = "normal"   # normal/cancelled/returned/diverted/positioning
    raw: dict[str, Any] = field(default_factory=dict)
    # 计划节点（完整 datetime）
    dep_official: Optional[dt.datetime] = None
    arr_official: Optional[dt.datetime] = None
    dep_plan: Optional[dt.datetime] = None
    arr_plan: Optional[dt.datetime] = None
    # 流控/CDM
    tobt: Optional[dt.datetime] = None
    cobt: Optional[dt.datetime] = None
    ctot: Optional[dt.datetime] = None
    acars_eta: Optional[dt.datetime] = None
    # 实际节点
    push_out: Optional[dt.datetime] = None
    dep_actual: Optional[dt.datetime] = None
    arr_actual: Optional[dt.datetime] = None
    correct_slide_in: Optional[dt.datetime] = None
    slide_in: Optional[dt.datetime] = None
    # 保障节点
    release_time: Optional[dt.datetime] = None
    board_start: Optional[dt.datetime] = None
    close_pass_cabin: Optional[dt.datetime] = None
    close_cargo_cabin: Optional[dt.datetime] = None
    # 延误字段（只作核对）
    dep_airport_slide_min: Optional[float] = None
    arr_airport_slide_min: Optional[float] = None
    dep_delay_min: Optional[float] = None
    arr_delay_min: Optional[float] = None

    def scheduled_aobt(self) -> Optional[dt.datetime]:
        return self.dep_official or self.dep_plan

    def scheduled_aibt(self) -> Optional[dt.datetime]:
        return self.arr_official or self.arr_plan

    def status_machine(self) -> str:
        """粗粒度状态机：preflight / in_progress / completed / cancelled / irregular。"""
        if self.result_kind == "cancelled" or (self.status and any(k in self.status for k in ("取消", "cancel", "CANCELLED"))):
            return "cancelled"
        if self.result_kind != "normal":
            return "irregular"
        if self.arr_actual or self.correct_slide_in or self.slide_in:
            return "completed"
        if self.push_out or self.dep_actual or self.release_time or self.board_start:
            return "in_progress"
        return "preflight"

@dataclass
class ChainLeg:
    sequence: int
    occurrence: FlightOccurrence
    flight_key: str
    position_conflict: bool = False
    note: str = ""

@dataclass
class AircraftChain:
    business_date: str
    aircraft_no: str
    legs: list[ChainLeg] = field(default_factory=list)
    broken: list[tuple[int, int, str]] = field(default_factory=list)  # (from_seq,to_seq,reason)
    conflict: bool = False
    warnings: list[str] = field(default_factory=list)
    is_plan_only: bool = False      # 机号缺失时只有计划链

    @property
    def chain_id(self) -> str:
        return f"{self.business_date}|{self.aircraft_no}"

@dataclass(frozen=True)
class CandidateAobt:
    value: Optional[dt.datetime]
    source: str          # scheduled / aircraft_ready / TOBT / COBT / CTOT_implied / ETD
    reason: str
    valid: bool = True   # 过期候选仅审计记录，不进入硬计算
