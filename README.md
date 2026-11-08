# 分布统计与条件事件模拟

版本 0.1.0。本项目源码采用 MIT 许可证，见 LICENSE；第三方依赖仍适用各自上游许可。

这是从已有实现筛选出的通用算法和必要离线适配，保留实用计算路径；并非任何原应用的完整迁移。未包含原始业务数据、既有文档模板、账号、网络适配、模型权重或历史仓库。来源追溯保存在独立的私有审查材料中。

## 运行

Python 3.13 已实测；源码使用 Python 3.11+ 语法，其他运行时尚未验证。在本目录执行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python demo.py
.venv/bin/python -m unittest discover -s tests -v
```

`demo.py` 是可直接运行的库使用示例，输入完全新造且明显标注为合成。`python demo.py --help` 查看说明。演示生成的文件/数据库都放临时目录并清理；需要处理自己的数据时，参照示例显式调用下面模块，不存在自动发现本机目录或登录操作。

## 能力与边界

时长分布以秒为单位；事件求解仅接受整数UTC秒，显式提供来源发布/观察/截止时刻和等待位置。只有BLOCK时不反推缺失四事件分项；输入来源不可见/冲突/不收敛保留未知。求得PASS仅指给定条件窗口，不代表运行可行。航链位置冲突保留冲突标记，未执行完整恢复调度/换机/取消优化。robust_filter所有筛选门槛由调用方给出；未包含训练样本或预测效果证明。

仅离线合成测试和文件回读已验证。没有真实业务数据验收、当前法规适用性验证、生产部署或外部发送测试。读取自己的文件不等于可以公开其内容；输出和使用参数仍由调用方审核。

## 模块接口

接口参数以源码类型标注和测试用例为准。下表包含实现接口，带下划线的函数是保留的内部辅助接口。

| 模块 | 主要符号 |
| --- | --- |
| `simulation/chain_models.py` | `FlightOccurrence`, `ChainLeg`, `AircraftChain`, `CandidateAobt` |
| `simulation/chains.py` | `sort_time`, `effective_position`, `_occ_key`, `build_aircraft_chain`, `build_chains`, `_build_plan_only_chain` |
| `simulation/constraints.py` | `CtotWindow`, `ctot_window`, `ctot_implied_aobt`, `max_constraint_aobt` |
| `simulation/distribution.py` | `DurationDistribution`, `_require_finite` |
| `simulation/events/asof.py` | `SnapshotMode`, `VisibilityDecision`, `visibility`, `effective_at`, `ArtifactAvailability` |
| `simulation/events/entities.py` | `freeze_value`, `require_utc_seconds`, `require_finite_number`, `_validate_entity`, `_validate_annotation`, `FrozenEntity`, `FlightOccurrence`, `FlightVersion`, `ScenarioSet` |
| `simulation/events/enums.py` | `JobStatus`, `OpinionStatus`, `ActionStatus`, `DataQuality`, `HardCheck`, `EventType` |
| `simulation/events/scenarios.py` | `DurationComponent`, `TrajectoryInterval`, `Trajectory`, `TrajectorySample`, `sample_trajectory`, `select_scenario_trajectories` |
| `simulation/events/solver.py` | `WaitLocation`, `DurationComponents`, `EventWindow`, `WindowCheck`, `EventSolution`, `_window_reasons`, `check_event_window`, `_timeline`, `_unknown`, `solve_events` |
| `simulation/recovery_math.py` | `FlightLeg`, `propagated_delays`, `turnaround_buffers` |
| `simulation/risk.py` | `ScenarioSet`, `_number`, `_weighted`, `inverse_cdf`, `worst_tail_mean`, `RiskSummary`, `summarize_risk`, `correlated_totals` |
| `simulation/robust.py` | `RobustFilterResult`, `percentile`, `weighted_percentile`, `robust_filter`, `huber_location`, `weighted_huber_location` |
| `simulation/sample_models.py` | `SegmentSample`, `WindowStatistics` |
| `simulation/samples.py` | `window_ranges`, `confidence_for`, `aggregate_window`, `_percentile` |

## 2026-11-08 协作修订

- 取消结果保持cancelled状态。
- 正总权重时，零权重样本不参与q=0分位值。

集合根目录 `verify_release.py --project domain-distribution-simulation` 可复跑合成测试和首次使用示例；本轮以集合验证报告为准。
