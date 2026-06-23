# Stage011 Stage861 full minute 质量标签重算

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 19:10 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读标签重算 + 官方资金曲线/贡献曲线/年度图/分钟 atlas 视觉复盘
- 是否重要突破：否，属于数据覆盖修复后的关键归因，不是交易规则突破
- 是否触发A/B：否，没有新策略版本或可接正式版候选

## 外部调研与判断

- 参考资料：
  - Market Intraday Momentum：`https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/ee7dac49-530b-4950-b5d0-e0b5eee08f2e.pdf`
  - Intraday Time Series Momentum 国际证据：`https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf`
  - pysystemtrade 数据文档：`https://github.com/pst-group/pysystemtrade/blob/develop/docs/data.md`
  - NautilusTrader backtesting：`https://nautilustrader.io/docs/latest/concepts/backtesting/`
  - Freqtrade lookahead-analysis：`https://www.freqtrade.io/en/stable/lookahead-analysis/`
- 我的判断：
  - 开盘/入场后早段分钟路径有研究价值，但文献只能支持“观察早段信息消化”，不能支持扫 `15/30/60` 或按单窗口救参。
  - Stage006/007 的旧源标签必须降级为旧源法证；Stage011 用 Stage861 full minute 重算后再判断 clean/no-follow 是否仍有结构意义。
  - 任何使用 30m 标签的真实引擎都必须承认这是入场后信息，不是入场前信息；未来只能讨论“保持最小风险/不恢复风险”这类执行纪律，不能直接删除、半仓或硬退出。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage011_stage861_quality_relabel_readonly.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；只读标签沿用 Stage006 冻结形状 `first_30m_directional_r > 0 and first_30m_mae_r <= 0.5R`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-06-15`
- 账户规模：`150,000`
- 成本口径：官方 C9/15w 正常成本；本阶段不生成 C 候选
- 样本过滤：官方 closed lots 全量 `399` 笔，不按品种、方向、年份、月份过滤
- 策略/归因口径：
  - 读取 Stage010 复跑出的官方 C9/15w 资金曲线和 closed-lot coverage features
  - 使用 Stage861 full minute 源重算 `clean_continuation_30m`、`no_follow_30m`、`adverse_heat_30m`、`risk_or_feature_invalid`、`missing_stage861_30m`
  - 额外计算第一根分钟K描述标签 `first_bar_follow_close/flat/adverse`，仅作视觉描述，不作为交易规则

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
- Stage861 covered lots：`398`
- hard missing lots：`1`，仍为 `OI609.CZCE 2026-06-02`
- `clean_continuation_30m`：`176` 笔，净 PnL `39,333,478.10`，正收益覆盖 `74.3322%`，负收益绝对覆盖 `44.4077%`
- `no_follow_30m`：`145` 笔，净 PnL `-6,100,118.10`，正收益覆盖 `7.7115%`，负收益绝对覆盖 `46.1692%`，正收益年份 `2`
- `adverse_heat_30m`：`12` 笔，净 PnL `6,480,115.60`，说明逆行热度不是坏信号充分条件
- `risk_or_feature_invalid`：`65` 笔，净 PnL `2,921,137.00`
- `first_bar_follow_close`：`130` 笔，净 PnL `25,526,918.70`
- `first_bar_adverse_close`：`120` 笔，净 PnL `9,544,718.90`
- 决策：`stage011_stage861_no_follow_still_promising_but_readonly`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage011_stage861_quality_relabel_readonly/qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_report_stage011_stage861_quality_relabel_readonly_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage011_stage861_quality_relabel_readonly/qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_summary_stage011_stage861_quality_relabel_readonly_v1.csv`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage011_stage861_quality_relabel_readonly/qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_features_stage011_stage861_quality_relabel_readonly_v1.csv`
- bucket stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage011_stage861_quality_relabel_readonly/qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_quality_bucket_stats_stage011_stage861_quality_relabel_readonly_v1.csv`
- first-bar stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage011_stage861_quality_relabel_readonly/qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_first_bar_bucket_stats_stage011_stage861_quality_relabel_readonly_v1.csv`
- contribution curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage011_stage861_quality_relabel_readonly/qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_contribution_curve_stage011_stage861_quality_relabel_readonly_v1.csv`
- official path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage011_stage861_quality_relabel_readonly/qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_official_path_chart_stage011_stage861_quality_relabel_readonly_v1.png`
- contribution chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage011_stage861_quality_relabel_readonly/qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_contribution_chart_stage011_stage861_quality_relabel_readonly_v1.png`
- year quality chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage011_stage861_quality_relabel_readonly/qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_year_quality_chart_stage011_stage861_quality_relabel_readonly_v1.png`
- minute atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage011_stage861_quality_relabel_readonly/qmt_roll_stage011_c9_minrisk_stage861_quality_relabel_readonly_atlas_page001_stage011_stage861_quality_relabel_readonly_v1.png` 至 `page006`

## 视觉分析

- official path chart 显示本阶段没有改变官方 C9/15w 资金路径；标记线只是把 Stage861 标签投到官方权益、回撤、broker10 曲线上。
- contribution chart 显示 `no_follow_30m` 红线自 `2021` 后长期为负，最终约 `-610万`；`all_except_no_follow` 曲线长期高于全样本参考，说明 no-follow 在 Stage861 修复后仍是负质量集合。
- 但同一张图也显示 `first_bar_adverse_close` 仍有约 `+954万` 正贡献，不能把第一根分钟K逆向作为硬坏信号。
- year quality chart 显示 clean 贡献主要来自 `2021/2023/2025`，no-follow 在 `2022/2023/2025/2026` 明显拖累，但 `2024` 为正；因此如果只为躲 `2022/2026` 做规则，很容易过拟合弱窗口。
- atlas page001 显示 `ru2501` 等 clean 大赢家并不都要求第一根分钟K顺向，部分先轻微逆向后进入趋势。
- atlas page003 显示 `SH405/au2412/CF205/SM505` 等 no-follow 反例最终贡献正收益；page004 显示 `SH607/AP210/cu2307/lh2411` 等 no-follow 亏损样本确实有早段不跟随或假突破形态。
- 视觉结论：no-follow 值得继续作为“是否继续保持最小风险”的候选前提，但不能作为删除、半仓或固定 30m 硬退出规则。

## 结论

- 本阶段结论：`stage011_stage861_no_follow_still_promising_but_readonly`
- 是否进入下一步：进入，但只允许设计冻结的真实引擎前置假设，不允许扫参数
- 下一步：
  - 不再做 `no_follow_30m_reduce_to_half` 形状救参，Stage008 已反证。
  - 下一阶段若做真实引擎，应探索“默认最小风险，只有 Stage861 30m 质量通过才恢复官方风险”的相反执行结构，而不是开满后机械砍仓。
  - 真实引擎必须保留官方 C9 `0.5R stop/retry` 优先级，`risk_or_feature_invalid` 和 `missing_stage861_30m` 保持官方路径，不能插值或用未来信息。
  - 在写引擎前还应先把 `risk_or_feature_invalid` 的 65 笔拆清，确认是多 layer/风险字段缺失还是可用实时风险预算字段，避免把会计缺口当作信号质量。

## 过拟合反思

- 运行前判断：否。Stage011 只把 Stage006 冻结标签迁移到 Stage861 full minute 源，不新增交易参数。
- 运行后判断：否。没有按品种、年份、方向、月份、R 倍数或窗口选择交易；输出为标签账本、官方资金曲线、贡献曲线和 atlas。
- 原因：本阶段只做归因，不改变任何交易路径。

## 继续价值反思

- 运行前判断：有。Stage010 已证明旧源 missing 偏差很大，重算标签是后续分钟研究的必要前提。
- 运行后判断：有。no-follow 在 Stage861 full 源下仍净亏约 `610万`，且正收益年份只有 `2`，说明它不是旧源偏差；但反例仍强，下一步必须换成“不恢复风险”的纪律，而不是删除/砍仓。
- 原因：这条线索能服务“高质量信号时用最小风险搏最大收益”的核心目标，但还未证明真实资金路径能达到收益保留 `80%+` 且降低回撤。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage011 的 Stage861 重算结论和下一步边界。
- 是否更新 `research/registry.md`：否，本线未形成正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、重要合入或路线废弃。
