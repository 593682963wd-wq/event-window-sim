"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""
from __future__ import annotations
from itertools import pairwise
from dataclasses import dataclass

@dataclass(frozen=True)
class FlightLeg:
    scheduled_departure: dt.datetime | None
    scheduled_arrival: dt.datetime | None

def propagated_delays(legs: list[FlightLeg], initial_delay: int, *, minimum_turnaround_minutes: int) -> list[int]:
    """用计划过站裕度吸收前序延误，形成可解释的滚动传播近似。"""
    if type(initial_delay) is not int or initial_delay < 0 or type(minimum_turnaround_minutes) is not int or (minimum_turnaround_minutes < 0):
        raise ValueError('延误与最少间隔须为非负整数')
    if not legs:
        return []
    delays = [max(0, int(initial_delay))]
    for previous, current in pairwise(legs):
        previous_arrival = previous.scheduled_arrival
        current_departure = current.scheduled_departure
        if previous_arrival is None or current_departure is None:
            delays.append(delays[-1])
            continue
        ground_minutes = int((current_departure - previous_arrival).total_seconds() / 60)
        absorbable = max(0, ground_minutes - minimum_turnaround_minutes)
        delays.append(max(0, delays[-1] - absorbable))
    return delays

def turnaround_buffers(legs: list[FlightLeg], *, minimum_turnaround_minutes: int) -> list[int]:
    """计算相邻航段之间可用于吸收延误的小幅调时裕度。"""
    if type(minimum_turnaround_minutes) is not int or minimum_turnaround_minutes < 0:
        raise ValueError('最少间隔须为非负整数')
    buffers: list[int] = []
    for previous, current in pairwise(legs):
        previous_arrival = previous.scheduled_arrival
        current_departure = current.scheduled_departure
        if previous_arrival is None or current_departure is None:
            buffers.append(0)
            continue
        ground_minutes = int((current_departure - previous_arrival).total_seconds() / 60)
        buffers.append(max(0, ground_minutes - minimum_turnaround_minutes))
    return buffers
