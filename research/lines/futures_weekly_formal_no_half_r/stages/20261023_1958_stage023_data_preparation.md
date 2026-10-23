# Stage023 历史数据规范副本准备（2026-10-23 19:58）

本阶段不是重要突破版本，也不产出金融绩效。准备器已在看 N/P 收益前冻结，代码 `08a3eb8ff134ff2d4c129de826977e4b1beb707bc30738f7a812f0298d64a79a`，36 项纯数据测试通过；独立金融审查由其他 agent 负责。本次是否过拟合：否，未搜索策略参数、未按收益择源；继续有价值，因为先消除数量口径和物理代身份歧义才能解释长窗。

最终目录为 `/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage023_history_data_approved`。`data_ready=true`、`data_ready_for_bounded_replay=true`，但 `historical_main_reconstruction_complete=false`：这是保留冻结主力映射缺陷的受限回放数据，并非完整重建历史主力。来源、原始证据、审批与产物由 1,774 文件 SHA 闭包固定。

新增数据标准为原19品种、2014-01-01—2026-10-23真实合约日线，主源 clean accepted 全字段、单边 volume、当日 close_oi；补充 95 条近期主力、40 条近期非主力、455 条独立准入的真实 Tq 日线。合计 **392,065 条正量 bar**，无源冲突或重复覆盖。Stage278 的259条旧补丁仅留证据，不重复叠加。策略参数与成本没有变；旧M行情、旧绩效、风险metadata原样保留。

原主力正量缺口591，明确分为 **573 原始RQ真实零量、18 结构性无效/不可用冻结映射、unknown 0**。573中539在clean inclusive生命周期内，34旧FU1905只作旧180分类标签，不能绑定新380。18中7个FU1805晚于真实退市日2018-04-27，11个FU1905处于官方终止至2018-07-16重挂空窗；没有伪造零量、价格或替代主力。这两类均不入DB、physical_epoch_daily、周指标或撮合。后续金融必须继续拒绝实际持仓/成交日非正量，并核18无候选、订单、持仓、周源消费。

两次数据准备失败原样保留且都无金融：首次错误拒绝合法199907世纪metadata；第二次错误按worktree解析主仓相对raw归档路径。对应失败receipt、当时源码及红测均保留。另对raw OHLCV/closeOI逐字段NaN/Inf补了先红后绿的显式finite拒绝；零量/结构分类另有独立红绿与backup集成验证。最终版本冻结后未改工具。

新副本隔离旧原19的326,549行后重建，共同旧/新312,762键OHLC差0；volume差14,570键，closeOI差250,665键，故 N 与旧 M 的差不能只归于延窗，应结合固定新副本 P2020 桥接解释。旧 M 库 SHA 前后均 `b439081d0408eeafd2e8596a6948db49c2e64220416c1973b354f03c7b1214b0`，metadata逐字节相同，DB与epoch_daily逐键逐值一致。

2014预热映射仍缺228日，hc1505首2015目标只有13个完整观察周，不能笼统称起点21周ready。真实日K物理身份已覆盖，6个未来代完整生命周期仍未知并显式标记；同native跨代共145对、观察间隔均>366天，未把观察首末伪当上市/到期。历史信息非PIT，数据准备通过不代表执行容量、跨周期有效或生产资格。

关键SHA：receipt `bc285973f73fb656846a7b44d78af9f75ebefaa14f64453fd704d3b1271d3f37`；source_manifest `8a4a02fbf89029d2471e3785b6ddb5d806e29bcd2fcc281fb05cca4c2329e4b6`；新DB `f27a0af7604d8df4ed07a5d69573467ae8ca77f947d3717220d4869cd24ebb7a`。完整键表和失败证据见同名JSON。

旧交付Stage015/016/017/019/021逐SHA复核：分别172/24/10/88/93条声明，去重含5份manifest共300文件，**0变化**。本记录不更新LINE、registry或旧交付，不参与N/P最终金融独审。后续TODO只剩固定N/P的结果与消费证据独立验收，不能从本阶段推导收益或晋级。
