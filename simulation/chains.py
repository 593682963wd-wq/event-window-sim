"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from typing import Any, Iterable, Optional

import datetime as dt

from .chain_models import AircraftChain

from .chain_models import ChainLeg

from .chain_models import FlightOccurrence

LOCAL_TZ = dt.timezone.utc

CONFLICT_REASON = "aircraft_position_conflict"

PLAN_ONLY_AIRCRAFT = "PLAN-ONLY"

def sort_time(occ: FlightOccurrence) -> Optional[dt.datetime]:
    """链排序时间：完整计划 datetime，缺失时回退实际节点（保持稳定排序）。"""
    for candidate in (occ.dep_official, occ.dep_plan,
                      occ.push_out, occ.dep_actual, occ.release_time):
        if candidate is not None:
            return candidate
    return None

def effective_position(occ: FlightOccurrence) -> str:
    """该航段结束后飞机所在机场。返航回始发；其余（含备降/调机）为到达机场。"""
    if occ.result_kind == "returned":
        return occ.origin
    return occ.destination

def _occ_key(occ: FlightOccurrence) -> str:
    return occ.flight_key

def build_aircraft_chain(
    business_date: str,
    aircraft_no: str,
    occurrences: Iterable[FlightOccurrence],
) -> tuple[list[AircraftChain], list[str]]:
    """构建单机当日链（可能因位置冲突拆成多条）。

    每条链内的段按时间升序且位置连续；断点写入前一条链的 broken 与 conflict 标记。
    返回 (chains, warnings)；全部段取消/机号缺失等导致无链时，warnings 仍上浮。
    """
    occs = sorted(
        [o for o in occurrences if o.business_date == business_date],
        key=lambda o: (sort_time(o) is None, sort_time(o) or dt.datetime.min.replace(tzinfo=LOCAL_TZ),
                       _occ_key(o)),
    )
    chains: list[AircraftChain] = []
    current: list[ChainLeg] = []
    broken: list[tuple[int, int, str]] = []
    warnings: list[str] = []

    for seq, occ in enumerate(occs, start=1):
        if not aircraft_no:
            warnings.append(f"{_occ_key(occ)} 机号缺失，未进入任何链")
            continue
        if occ.result_kind == "cancelled":
            warnings.append(f"{_occ_key(occ)} 取消，位置不转移，未进入链")
            continue
        conflict = False
        reason = ""
        if current:
            prev = current[-1]
            if effective_position(prev.occurrence) != occ.origin:
                conflict = True
                reason = CONFLICT_REASON
                broken.append((prev.sequence, seq, reason))
                warnings.append(
                    f"{_occ_key(prev.occurrence)} -> {_occ_key(occ)} 位置不连续"
                    f"（{effective_position(prev.occurrence)} != {occ.origin}），链断开")
        leg = ChainLeg(sequence=seq, occurrence=occ, flight_key=occ.flight_key,
                       position_conflict=conflict, note=reason)
        current.append(leg)

    if current:
        chain = AircraftChain(business_date=business_date, aircraft_no=aircraft_no,
                              legs=current, broken=broken,
                              conflict=bool(broken), warnings=warnings)
        chains.append(chain)
    return chains, warnings

def build_chains(occurrences: Iterable[FlightOccurrence]) -> tuple[list[AircraftChain], list[str]]:
    """按业务日期+机号分组构建全部链。

    - 有机号：真实飞机链（位置连续性检查）；
    - 机号缺失：按日期归入一条计划链（is_plan_only=True，低置信，不查位置）。
    返回 (chains, warnings)。
    """
    by_aircraft: dict[str, list[FlightOccurrence]] = {}
    plan_only: dict[str, list[FlightOccurrence]] = {}
    global_warnings: list[str] = []
    for occ in occurrences:
        if not occ.plane_no:
            global_warnings.append(f"{occ.flight_key} 机号缺失，只建计划链（低置信）")
            plan_only.setdefault(str(occ.business_date), []).append(occ)
            continue
        by_aircraft.setdefault(str(occ.plane_no), []).append(occ)

    chains: list[AircraftChain] = []
    for aircraft_no in sorted(by_aircraft):
        occs = by_aircraft[aircraft_no]
        dates = sorted({str(o.business_date) for o in occs})
        for business_date in dates:
            date_occs = [o for o in occs if str(o.business_date) == business_date]
            sub, sub_warnings = build_aircraft_chain(business_date, aircraft_no, date_occs)
            if sub:
                chains.extend(sub)
            global_warnings.extend(sub_warnings)

    for business_date in sorted(plan_only):
        occs = plan_only[business_date]
        chain = _build_plan_only_chain(business_date, occs)
        if chain is not None:
            chains.append(chain)
            global_warnings.extend(chain.warnings)
    return chains, global_warnings

def _build_plan_only_chain(business_date: str,
                           occurrences: Iterable[FlightOccurrence]) -> Optional[AircraftChain]:
    """计划链：机号缺失航段的低置信容器（无真实飞机归属，不做位置检查）。"""
    occs = sorted(
        occurrences,
        key=lambda o: (sort_time(o) is None, sort_time(o) or dt.datetime.min.replace(tzinfo=LOCAL_TZ),
                       _occ_key(o)),
    )
    legs: list[ChainLeg] = []
    warnings: list[str] = []
    for seq, occ in enumerate(occs, start=1):
        if occ.result_kind == "cancelled":
            warnings.append(f"{_occ_key(occ)} 取消，未进入计划链")
            continue
        legs.append(ChainLeg(sequence=seq, occurrence=occ, flight_key=occ.flight_key))
    if not legs:
        return None
    return AircraftChain(business_date=business_date, aircraft_no=PLAN_ONLY_AIRCRAFT,
                         legs=legs, warnings=warnings, is_plan_only=True)
