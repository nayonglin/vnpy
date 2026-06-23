# Stage012 risk_or_feature_invalid 修复归因

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 19:22 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读风险字段修复审计 + 官方资金曲线/贡献曲线/修复分布/分钟 atlas 视觉复盘
- 是否重要突破：否，属于下一阶段真实引擎前的数据会计前提，不是交易规则突破
- 是否触发A/B：否，没有新策略版本或可接正式版候选

## 外部调研与判断

- 参考资料：
  - QuantStart backtesting considerations：`https://www.quantstart.com/articles/backtesting-systematic-trading-strategies-in-python-considerations-and-open-source-frameworks/`
  - pysystemtrade：`https://github.com/pst-group/pysystemtrade`
  - NautilusTrader backtesting：`https://nautilustrader.io/docs/latest/concepts/backtesting/`
  - Freqtrade lookahead-analysis：`https://www.freqtrade.io/en/stable/lookahead-analysis/`
- 我的判断：
  - 风险金额、止损距离、仓位规模属于执行层核心账本，不能把字段缺失直接解释成信号质量。
  - 修复只能使用成交日前已经存在的 official entry_risk plan-day 记录，不能用未来 MFE/MAE、最终盈亏或日终结果补证据。
  - Stage011 的 `risk_or_feature_invalid` 必须先拆清，否则下一阶段最小风险真实引擎会把会计缺口误当作不可交易样本。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage012_risk_invalid_repair_forensics.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；只读匹配约束为 official `entry_risk` plan-day 不晚于成交日、最大滞后 `10` 个自然日、按合约/方向/手数/价格接近度匹配
- 修改参数：无
- 删除参数：无
- 新增回测/归因结果：65 笔旧 `risk_or_feature_invalid` 全部修复为可计算 30m R 口径
- 修改回测结果：无，官方资金路径不变
- 删除回测结果：无

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-06-15`
- 当前官方正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
- 账户规模：`150,000`
- 成本口径：官方 C9/15w 正常成本；本阶段不生成 C 候选
- 样本过滤：官方 closed lots 全量 `399` 笔，不按品种、方向、年份、月份过滤
- 策略/归因口径：
  - 读取 Stage011 的 Stage861 full minute 标签账本
  - 读取 Stage010 复跑出的官方 C9/15w 资金曲线和 official `entry_risk` 账本
  - 仅对 Stage011 的 65 笔旧 `risk_or_feature_invalid` 进行 plan-day risk 修复
  - 使用 plan-day `stop_distance` 和成交日 Stage861 分钟K重算 first 30m directional R / MAE R
  - 修复后重新归入 `clean_continuation_30m`、`no_follow_30m`、`adverse_heat_30m` 或 `missing_stage861_30m`

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
- 旧 `risk_or_feature_invalid`：`65` 笔
- entry_risk 修复：`65` 笔
- entry_risk 未修复：`0` 笔
- 修复到 `clean_continuation_30m`：`12` 笔，旧 invalid 内净 PnL `421,810.00`
- 修复到 `adverse_heat_30m`：`7` 笔，旧 invalid 内净 PnL `850,740.00`
- 修复到 `no_follow_30m`：`46` 笔，旧 invalid 内净 PnL `1,648,587.00`
- 旧 invalid 合计净 PnL：`2,921,137.00`
- 全样本修复后 `clean_continuation_30m`：`188` 笔，净 PnL `39,755,288.10`
- 全样本修复后 `no_follow_30m`：`191` 笔，净 PnL `-4,451,531.10`，正收益年份 `3`
- 修复后仍 missing/invalid：`1` 笔，仍为 Stage861 hard missing `OI609.CZCE 2026-06-02`
- 决策：`stage012_risk_invalid_all_repaired_as_plan_day_risk_no_trade_rule`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage012_risk_invalid_repair_forensics/qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_report_stage012_risk_invalid_repair_forensics_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage012_risk_invalid_repair_forensics/qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_summary_stage012_risk_invalid_repair_forensics_v1.csv`
- repair ledger：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage012_risk_invalid_repair_forensics/qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_repair_ledger_stage012_risk_invalid_repair_forensics_v1.csv`
- repaired features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage012_risk_invalid_repair_forensics/qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_features_repaired_quality_stage012_risk_invalid_repair_forensics_v1.csv`
- repair bucket stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage012_risk_invalid_repair_forensics/qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_repair_bucket_stats_stage012_risk_invalid_repair_forensics_v1.csv`
- full repaired quality stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage012_risk_invalid_repair_forensics/qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_quality_before_after_stats_stage012_risk_invalid_repair_forensics_v1.csv`
- year repaired quality stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage012_risk_invalid_repair_forensics/qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_year_repaired_quality_stats_stage012_risk_invalid_repair_forensics_v1.csv`
- official path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage012_risk_invalid_repair_forensics/qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_official_path_chart_stage012_risk_invalid_repair_forensics_v1.png`
- contribution chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage012_risk_invalid_repair_forensics/qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_contribution_chart_stage012_risk_invalid_repair_forensics_v1.png`
- repair chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage012_risk_invalid_repair_forensics/qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_repair_chart_stage012_risk_invalid_repair_forensics_v1.png`
- minute atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage012_risk_invalid_repair_forensics/qmt_roll_stage012_c9_minrisk_risk_invalid_repair_forensics_atlas_page001_stage012_risk_invalid_repair_forensics_v1.png` 至 `page006`

## 视觉分析

- official path chart 显示本阶段仍不改变官方 C9/15w 资金路径，只把旧 invalid 样本按修复后标签投到权益、回撤和 broker10 曲线上。
- contribution chart 显示修复后 `no_follow_30m` 仍为负，但从 Stage011 的约 `-610万` 收窄到约 `-445万`；说明 no-follow 线索仍有价值，但旧 invalid 中存在正贡献 no-follow，不能把它粗暴当作坏样本集合。
- repair chart 显示旧 invalid 样本跨多年、跨品种分布，被修复为 clean/adverse/no-follow 三类，不是单一品种、年份或行情阶段导致的独立信号集合。
- atlas page001 显示旧 invalid -> no-follow 的样本里既有亏损也有大额正收益，且部分存在 plan-day risk 与成交日开盘 gap；真实引擎以后必须明确 R 口径，不能在 plan-day stop_distance 与成交价到 stop_price 的实际距离之间事后混用。

## 结论

- 本阶段结论：`stage012_risk_invalid_all_repaired_as_plan_day_risk_no_trade_rule`
- 是否进入下一步：进入，但只允许进入冻结真实引擎设计，不允许扫窗口、比例、R 倍数、品种、方向、年份或月份
- 下一步：
  - 未来分钟 R 决策可以使用 official entry_risk plan-day `stop_distance` 作为账本口径。
  - 若 plan-day risk 不可得，必须保持官方路径或保守跳过分钟 R 决策，不能编造风险字段。
  - 下一阶段如写真实引擎，应冻结为“默认最小风险，官方 C9 `0.5R stop/retry` 优先，只有 Stage861 30m clean 质量确认后才允许恢复官方风险”的单一版本。
  - `no_follow_30m` 只能作为“不恢复风险/继续最小风险”的负向前提，不能再做直接删除、半仓或固定 30m 硬退出。

## 过拟合反思

- 运行前判断：否。Stage012 只修复 official 风险账本字段，不引入交易分支，也不按品种、年份、方向、月份选样本。
- 运行后判断：否。65 笔修复全部来自成交日前 official `entry_risk` plan-day 记录，属于会计修复，不是按最终盈亏调参。
- 原因：没有改变任何交易路径，只把下一阶段真实引擎所需的 R 分母从缺失字段恢复为可审计账本。

## 继续价值反思

- 运行前判断：有。Stage011 的 65 笔 invalid 如果不拆清，会污染“最小风险/恢复风险”的真实引擎输入。
- 运行后判断：有。65 笔全部可修复，且修复后 no-follow 仍为负贡献，说明继续沿“默认最小风险，质量通过才恢复风险”的方向有研究价值。
- 原因：这不是救参数，而是在减少错误归因；下一步仍需真实组合引擎验证能否降低回撤并保留官方收益 `80%+`。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage012 的风险账本修复结论和下一步边界。
- 是否更新 `research/registry.md`：否，本线未形成正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、重要合入或路线废弃。
