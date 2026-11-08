"""作者：Wangyuan；日期：2026-10-29。离线通用核心，输入由调用方显式提供。"""

from __future__ import annotations

from collections.abc import Mapping

from dataclasses import dataclass, fields, is_dataclass

from datetime import date

from enum import Enum

from types import MappingProxyType, UnionType

from typing import get_args, get_origin, get_type_hints

import math

from .enums import DataQuality

ENTITY_FIELDS = {'FlightOccurrence': ('flight_id', 'source_namespace', 'source_identity_ref', 'carrier', 'flight_number', 'business_date', 'origin', 'destination', 'leg_sequence'), 'FlightVersion': ('flight_version_id', 'flight_id', 'plan_version_id', 'sobt_utc', 'sibt_utc', 'origin_tz', 'destination_tz', 'aircraft_type', 'assignment_ref', 'payload_digest', 'timezone_db_version'), 'ScenarioSet': ('scenario_set_id', 'version', 'scenario_ids', 'weights', 'probability_basis', 'trajectory_refs', 'exposure_rule', 'event_windows', 'rng_algorithm', 'seed')}

from .enums import EventType

_UTC_FIELDS = frozenset({
    "target_from", "target_to", "created_at", "effective_from", "sobt_utc", "sibt_utc",
    "value_utc", "published_at", "observed_at", "extracted_at", "start_utc", "end_utc",
    "valid_from", "valid_to", "cutoff_at", "due_at", "effective_at", "maturity_at", "at",
})

_NULLABLE_UTC_FIELDS = frozenset({
    "effective_from", "value_utc", "published_at", "observed_at", "valid_to",
    "due_at", "effective_at", "maturity_at",
})

_COUNT_FIELDS = frozenset({
    "leg_sequence", "revision", "sample_count", "expected_count", "not_applicable_count",
    "valid_count", "unknown_count", "seed", "expected_revision",
})

_UNITS = frozenset({
    "seconds", "minutes", "hours", "count", "flights", "ratio", "probability",
    "percent", "currency", "flight_minutes", "minutes_per_connection",
    "passenger_minutes", "person_minutes", "aircraft_minutes", "demand_units", "capacity_units",
})

_ENUM_FIELDS = {
    "event_type": EventType,
    "qualification": DataQuality,
    "completeness": DataQuality,
}

_MAPPING_FIELDS = frozenset({"scope", "scope_conditions", "event_windows", "page_manifest", "window"})

_SEQUENCE_FIELDS = frozenset({
    "mapping_evidence", "scenario_ids", "weights", "trajectory_refs", "snapshot_refs",
    "evidence_refs", "subject_refs", "conditions", "execution_refs",
})

_REQUIRED_IDS = frozenset({
    "plan_version_id", "flight_id", "flight_version_id", "execution_id", "source_record_id",
    "resource_id", "connection_id", "rule_id", "scenario_set_id", "run_id", "metric_id",
    "reference_id", "outcome_id", "snapshot_id", "trace_id", "id",
})

def freeze_value(value: object) -> object:
    """递归冻结嵌套容器，避免冻结实体仍被外部列表或字典改写。"""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) or not key for key in value):
            raise ValueError("映射键必须为非空字符串")
        return MappingProxyType({key: freeze_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze_value(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("嵌套数值必须有限")
    if value is None or isinstance(value, (str, bool, int, float, bytes)):
        return value
    if is_dataclass(value) and value.__dataclass_params__.frozen:
        if not type(value).__module__.startswith("simulation.events."):
            raise TypeError("不信任外部冻结对象的嵌套可变性")
        return value
    raise TypeError(f"不支持可变或未知嵌套类型: {type(value).__name__}")

def require_utc_seconds(value: object, name: str, *, nullable: bool = False) -> int | None:
    """UTC 时间仅接受整数秒；布尔值不能冒充整数。"""
    if value is None and nullable:
        return None
    if type(value) is not int:
        raise ValueError(f"{name} 必须为 UTC 整数秒")
    return value

def require_finite_number(value: object, name: str, *, nullable: bool = False) -> float | int | None:
    """拒绝 bool、NaN 和无穷值；保留缺数 None。"""
    if value is None and nullable:
        return None
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} 必须为有限数值")
    return value

def _validate_entity(instance: object) -> None:
    expected = ENTITY_FIELDS.get(type(instance).__name__)
    if expected is None or not set(expected).issubset({field.name for field in fields(instance)}):
        raise TypeError("实体字段不符合冻结合同")
    annotations = get_type_hints(type(instance))
    for field in fields(instance):
        name = field.name
        value = getattr(instance, name)
        if name in _MAPPING_FIELDS and not isinstance(value, Mapping):
            raise ValueError(f"{name} 必须为映射")
        if name in _SEQUENCE_FIELDS and value is not None and not isinstance(value, (tuple, list)):
            raise ValueError(f"{name} 必须为序列或 None")
        if name in _UTC_FIELDS:
            require_utc_seconds(value, name, nullable=name in _NULLABLE_UTC_FIELDS)
        elif name in _COUNT_FIELDS and value is not None:
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} 必须为非负整数")
        elif name in {"gap_seconds", "point_seconds", "threshold", "numerator", "denominator", "value", "coverage", "amount", "lead_time"} and value is not None:
            require_finite_number(value, name)
        if name in _REQUIRED_IDS and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{name} 必须为非空不透明字符串")
        if name.endswith(("_id", "_ref")) and value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{name} 必须为非空不透明字符串或 None")
        if name in ("unit", "denominator_unit") and value is not None and value not in _UNITS:
            raise ValueError(f"{name} 非法: {value}")
        enum_type = _ENUM_FIELDS.get(name)
        if enum_type and value is not None:
            try:
                enum_type(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} 非法: {value}") from exc
        _validate_annotation(value, annotations[name], name)
        if isinstance(value, (Mapping, list, tuple, set, frozenset)):
            object.__setattr__(instance, name, freeze_value(value))
    business_date = getattr(instance, "business_date", None)
    if business_date is not None:
        if not isinstance(business_date, str):
            raise ValueError("business_date 必须为 YYYY-MM-DD 业务标识")
        try:
            if date.fromisoformat(business_date).isoformat() != business_date:
                raise ValueError
        except ValueError as exc:
            raise ValueError("business_date 必须为 YYYY-MM-DD 业务标识") from exc

def _validate_annotation(value: object, annotation: object, name: str) -> None:
    """运行时拒绝标注不允许的可变替代物；不能只依赖静态类型提示。"""
    if annotation is object:
        return
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is UnionType:
        for alternative in args:
            try:
                _validate_annotation(value, alternative, name)
                return
            except ValueError:
                pass
        raise ValueError(f"{name} 的类型与冻结合同不符")
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"{name} 必须为序列")
        for item in value:
            _validate_annotation(item, args[0], name)
        return
    if origin is not None:
        if not isinstance(value, origin):
            raise ValueError(f"{name} 类型非法")
        return
    if annotation is int:
        if type(value) is not int:
            raise ValueError(f"{name} 必须为整数")
    elif annotation is float:
        require_finite_number(value, name)
    elif isinstance(annotation, type) and issubclass(annotation, Enum):
        try:
            annotation(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} 枚举非法") from exc
    elif not isinstance(value, annotation):
        raise ValueError(f"{name} 类型非法")

class FrozenEntity:
    """冻结字段的共享验证钩子，不承担业务决策。"""

    def __post_init__(self) -> None:
        _validate_entity(self)

@dataclass(frozen=True, slots=True)
class FlightOccurrence(FrozenEntity):
    """跨计划版本稳定的逻辑航段身份。"""

    flight_id: str
    source_namespace: str
    source_identity_ref: str | None
    carrier: str
    flight_number: str
    business_date: str
    origin: str
    destination: str
    leg_sequence: int

@dataclass(frozen=True, slots=True)
class FlightVersion(FrozenEntity):
    """属于具体计划版本的航段时刻。"""

    flight_version_id: str
    flight_id: str
    plan_version_id: str
    sobt_utc: int
    sibt_utc: int
    origin_tz: str | None
    destination_tz: str | None
    aircraft_type: str | None
    assignment_ref: str | None
    payload_digest: str
    timezone_db_version: str | None = None  # 内部建议扩展：复现显示转换。

    def __post_init__(self) -> None:
        FrozenEntity.__post_init__(self)
        if self.sibt_utc <= self.sobt_utc:
            raise ValueError("计划到挡须晚于计划撤轮")

@dataclass(frozen=True, slots=True)
class ScenarioSet(FrozenEntity):
    """冻结情景、可选概率与随机算法。"""

    scenario_set_id: str
    version: str
    scenario_ids: tuple[str, ...]
    weights: tuple[float, ...] | None
    probability_basis: str | None
    trajectory_refs: tuple[str, ...]
    exposure_rule: str | None
    event_windows: Mapping[str, object]
    rng_algorithm: str
    seed: int

    def __post_init__(self) -> None:
        FrozenEntity.__post_init__(self)
        if self.weights is not None:
            if not self.probability_basis:
                raise ValueError("有情景权重须有概率依据")
            if len(self.weights) != len(self.scenario_ids) or any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in self.weights):
                raise ValueError("情景权重数量或数值非法")
            if not math.isclose(sum(self.weights), 1.0, abs_tol=1e-9):
                raise ValueError("有概率的情景权重须合计为1")
        elif self.probability_basis is not None:
            raise ValueError("无权重情景不能声明概率依据")
