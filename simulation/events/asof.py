"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from dataclasses import dataclass

from enum import StrEnum

from .entities import require_utc_seconds

class SnapshotMode(StrEnum):
    """历史重建允许晚观测记录，但永远不证明前瞻能力。"""

    STRICT = "STRICT"
    HISTORICAL_RECONSTRUCTED = "HISTORICAL_RECONSTRUCTED"

@dataclass(frozen=True, slots=True)
class VisibilityDecision:
    """可见性结论及不可提升的证据边界。"""

    eligible: bool
    reason_codes: tuple[str, ...]
    mode: SnapshotMode
    proves_prospective: bool = False

def visibility(published_at: int | None, observed_at: int | None, cutoff_at: int, *,
               snapshot_ref: str | None, mode: SnapshotMode = SnapshotMode.STRICT) -> VisibilityDecision:
    """以来源发布和真实留存时间判定；不会使用事件日期替代任何一项。"""
    mode = SnapshotMode(mode)
    for name, value in (("published_at", published_at), ("observed_at", observed_at)):
        require_utc_seconds(value, name, nullable=True)
    require_utc_seconds(cutoff_at, "cutoff_at")
    reasons = []
    if published_at is None:
        reasons.append("E_PUBLISHED_AT_MISSING")
    elif published_at > cutoff_at:
        reasons.append("E_FUTURE_PUBLISHED")
    if observed_at is None:
        reasons.append("E_OBSERVED_AT_MISSING")
    elif observed_at > cutoff_at and mode == SnapshotMode.STRICT:
        reasons.append("E_LATE_OBSERVED")
    if not isinstance(snapshot_ref, str) or not snapshot_ref.strip():
        reasons.append("E_SNAPSHOT_MISSING")
    if reasons:
        return VisibilityDecision(False, tuple(reasons), mode)
    # 输入可见不等于模型、输出当时均留存，更不等于真实前瞻验证。
    return VisibilityDecision(True, ("HISTORICAL_RECONSTRUCTION_ONLY",)
                              if mode == SnapshotMode.HISTORICAL_RECONSTRUCTED else (), mode)

def effective_at(valid_from: int, valid_to: int | None, target_at: int, *, closure: str) -> bool:
    """生效性按目标事件判断，端点来自合同，不能暗设一律半开区间。"""
    for name, value in (("valid_from", valid_from), ("target_at", target_at)):
        require_utc_seconds(value, name)
    require_utc_seconds(valid_to, "valid_to", nullable=True)
    if valid_to is not None and valid_to <= valid_from:
        raise ValueError("生效区间必须左早右晚")
    if closure not in {"[)", "[]", "()", "(]"}:
        raise ValueError("窗口端点未确认")
    return (target_at >= valid_from if closure[0] == "[" else target_at > valid_from) and (
        valid_to is None or (target_at <= valid_to if closure[1] == "]" else target_at < valid_to))

@dataclass(frozen=True, slots=True)
class ArtifactAvailability:
    """制品、校准、阈值或标签的当时可用性证据；标签另保留成熟时刻。"""

    reference: str
    published_at: int | None
    observed_at: int | None
    snapshot_ref: str | None
    matured_at: int | None = None
