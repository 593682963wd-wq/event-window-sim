"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from enum import StrEnum

class JobStatus(StrEnum):
    """评价作业状态。"""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED_UNCERTAIN = "INTERRUPTED_UNCERTAIN"

class OpinionStatus(StrEnum):
    """意见草稿的有效性。"""

    DRAFT = "DRAFT"
    VALID = "VALID"
    STALE = "STALE"
    WITHDRAWN = "WITHDRAWN"

class ActionStatus(StrEnum):
    """条件行动的准备状态。"""

    PROPOSED = "PROPOSED"
    CONDITION_PENDING = "CONDITION_PENDING"
    READY_FOR_OFFICIAL_PROCESS = "READY_FOR_OFFICIAL_PROCESS"
    CLOSED_WITH_EVIDENCE = "CLOSED_WITH_EVIDENCE"

class DataQuality(StrEnum):
    """数据适用和可信状态。"""

    VALID = "VALID"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class HardCheck(StrEnum):
    """硬约束判定；未知不得视为通过。"""

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class EventType(StrEnum):
    """计划和实际运行事件，不能互相代替。"""

    AOBT = "AOBT"
    ATOT = "ATOT"
    ALDT = "ALDT"
    AIBT = "AIBT"
    SOBT = "SOBT"
    SIBT = "SIBT"
