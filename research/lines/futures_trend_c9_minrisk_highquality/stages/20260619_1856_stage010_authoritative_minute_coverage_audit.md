# Stage010 权威分钟覆盖审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 18:56 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据覆盖审计 + 官方资金曲线/覆盖图/分钟 atlas 视觉复盘
- 是否重要突破：是，数据前提层面重要；不是交易规则突破
- 是否触发A/B：否，没有新策略版本或可接正式版候选

## 外部调研与判断

- 参考资料：
  - Freqtrade lookahead-analysis：`https://www.freqtrade.io/en/stable/lookahead-analysis/`
  - pysystemtrade：`https://github.com/pst-group/pysystemtrade`
  - pysystemtrade futures data docs：`https://github.com/pst-group/pysystemtrade/blob/develop/docs/data.md`
  - Concretum backtesting data quality：`https://concretumgroup.com/backtesting-data-quality-can-your-data-provider-be-trusted/`
- 我的判断：
  - 分钟规则的第一性前提是 entry-day 分钟数据可审计、时间顺序不泄漏、缺口不被插值伪造。
  - Stage008/009 连续证明入场后硬退出/降仓会伤右尾，继续调参数没有价值；更高价值的是确认 Stage007 的 missing/no-follow 统计是不是旧分钟源造成的覆盖偏差。
  - 外部资料均支持先把数据层作为独立资产治理，避免在错误或缺失分钟数据上做规则优化。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage010_authoritative_minute_coverage_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；审计窗口固定 `FIRST_N_BARS=30`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-06-15`
- 账户规模：`150,000`
- 成本口径：官方正常成本；本阶段不生成 C 候选
- 样本过滤：不按品种、方向、年份、月份过滤；官方 C9/15w closed lots 全量审计
- 策略/归因口径：
  - 复跑官方正式 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - 对每笔 official closed lot 同时检查旧分钟源 `s825._load_minute_bars` 和 Stage861 full minute 源 `s928._load_stage861_full_minute_bars`
  - 只生成覆盖账本、贡献曲线和分钟 atlas，不新增交易规则

## 结果

- 官方路径期末权益：`39,176,437.60`
- 官方路径总收益：`26017.6251%`
- 官方路径最大回撤：`-45.0827%`
- 官方路径 Sharpe：`1.6331`
- 官方路径总滑点：`2,730,130`
- 官方路径总交易次数：`787`
- 官方路径胜率：`53.2560%`
- 官方路径 broker10 峰值：`111.7365%`
- official closed lots：`399`
- 旧分钟源 entry-day 覆盖：`260/399 = 65.1629%`
- Stage861 full minute entry-day 覆盖：`398/399 = 99.7494%`
- Stage861 相对旧源修复：`138` 笔，净 PnL `5,316,294.60`
- Stage861 仍缺失：`1` 笔，`OI609.CZCE` `2026-06-02` long，净 PnL `420,000`
- Stage861 修复样本中包含大右尾：
  - `ru2501.SHFE` `2024-09-12` long，PnL `3,549,200`
  - `rb2210.SHFE` `2022-07-07` short，PnL `2,135,000`
  - `hc2210.SHFE` `2022-07-07` short，PnL `2,085,000`
  - `OI605.CZCE` `2026-03-05` long，PnL `1,270,060`
- 决策：`stage010_stage861_improves_coverage_but_missing_tail_remains`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_report_stage010_authoritative_minute_coverage_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_stage010_authoritative_minute_coverage_audit_v1.csv`
- daily/curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_stage010_authoritative_minute_coverage_audit_v1.csv`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_coverage_features_stage010_authoritative_minute_coverage_audit_v1.csv`
- coverage stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_coverage_stats_stage010_authoritative_minute_coverage_audit_v1.csv`
- official path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_path_chart_stage010_authoritative_minute_coverage_audit_v1.png`
- coverage chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_coverage_chart_stage010_authoritative_minute_coverage_audit_v1.png`
- contribution chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_coverage_contribution_chart_stage010_authoritative_minute_coverage_audit_v1.png`
- minute atlas：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_atlas_page001_stage010_authoritative_minute_coverage_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_atlas_page002_stage010_authoritative_minute_coverage_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_atlas_page003_stage010_authoritative_minute_coverage_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage010_authoritative_minute_coverage_audit/qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_atlas_page004_stage010_authoritative_minute_coverage_audit_v1.png`

## 视觉分析

- 官方资金曲线与 Stage001/008/009 的 A 口径一致，说明 Stage010 没有改变交易路径，只是重放官方路径并绑定分钟覆盖。
- 覆盖年度图显示：旧源在 `2018/2019` entry-day 覆盖为 `0`，Stage861 全部补齐；`2020-2026` 也补了多个关键 entry-day。
- 贡献曲线显示：`repaired_by_stage861_full` 不是边缘样本，累计净 PnL 约 `+531.63万`，其中包含 `ru2501/rb2210/hc2210/OI605` 等此前 Stage007 视为 missing 的大右尾。
- atlas page001 明确显示上述修复样本的 entry-day 分钟K已经可画图，且很多是趋势右尾早期结构；这会显著改变 Stage006/007 的 clean/no-follow/missing 分布。
- 仍缺 `OI609.CZCE 2026-06-02`，该笔是 `+420,000` 右尾；任何未来分钟交易规则必须把该笔保持官方路径，不能插值或用未来最近分钟K补证据。

## 结论

- 本阶段结论：`stage010_stage861_improves_coverage_but_missing_tail_remains`
- 是否进入下一步：进入，但只作为数据源前提推进，不是策略晋级
- 下一步：
  - 后续所有 entry-day 分钟规则默认使用 Stage861 full minute 源，而不是旧 `s825._load_minute_bars` 源。
  - Stage006/007 基于旧源的 missing/no-follow 结论应降级为旧源法证，不能作为后续交易规则基础；需要用 Stage861 full 源重算高质量/低质量分钟标签。
  - 对 `OI609.CZCE 2026-06-02` 保持 hard missing；未来规则不得对该笔做分钟退出/降仓/恢复判断。
  - 下一阶段优先做 Stage861 full 源下的只读信号质量再归因，特别是入场前/入场当刻可见结构，而不是继续入场后硬退出。

## 过拟合反思

- 运行前判断：否。Stage010 不设计交易规则，只审计数据覆盖。
- 运行后判断：否。输出是覆盖账本、官方资金曲线和 atlas，没有按品种、年份、方向或结果改交易。
- 原因：本阶段服务于数据前提，而不是寻找最优参数。

## 继续价值反思

- 运行前判断：有。Stage007 的 missing 样本含大右尾，若数据源已经修复，后续分钟研究必须先重建标签。
- 运行后判断：有。Stage861 覆盖从 `65.1629%` 提升到 `99.7494%`，足以支撑下一步重算分钟质量标签；但仍不能直接交易。
- 原因：这一步把“数据缺口”从大面积阻塞变成单笔 hard missing，同时避免继续在旧源偏差上过拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage861 成为后续分钟默认源和单笔 hard missing。
- 是否更新 `research/registry.md`：否，本线仍未形成正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是本线数据前提突破，但不是正式候选、跨线合并或实盘配置变化。
