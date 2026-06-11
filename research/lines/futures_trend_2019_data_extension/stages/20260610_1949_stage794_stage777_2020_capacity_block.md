# Stage794 Stage777候选版2020容量约束归因

- line_id：`futures_trend_2019_data_extension`
- 当前模式：day
- 记录时间：2026-06-10 19:49
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：归因诊断
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段未新增外部资料；问题是本地候选版回测 `entry_candidate_snapshots` 的容量约束计数，不涉及新增策略思想。
- 我的判断：本次只统计既有候选版是否因为 `max_concurrent_positions=4` 被挡，不调参、不挑样本，因此过拟合风险低；但该统计只能说明容量约束触发频率，不能单独证明放宽到 5 个品种会提高收益。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 启动，沿用 Stage777 单路径回放口径至当前可用日线尾部
- 账户规模：50万候选版口径
- 成本口径：沿用 Stage777 / Stage772 `oi_restore_am40` 回放配置
- 样本过滤：统计 `entry_candidate_snapshots` 中 `skip_reason=concurrent_limit` 的候选信号
- 策略/归因口径：Stage777官方候选家族，`AM41`、基础等效风险 `0.40`、命中 `OI上升+价格沿方向` 恢复到 `0.80`、旧正式 AI 选品池、`max_concurrent_positions=4`

## 结果

- 期末权益：本阶段不重新报告，沿用候选版主回测结果
- 总收益：本阶段不重新报告
- 最大回撤：本阶段不重新报告
- Sharpe：本阶段不重新报告
- 总滑点：本阶段不重新报告
- 总交易次数：已开仓候选 `240` 笔
- 胜率：本阶段不统计
- 其他关键指标：
  - 候选快照总数：`818`
  - 成功开仓：`240`
  - 总跳过：`578`
  - 因达到 4 个品种/仓位上限跳过：`36`
  - `36/818 = 4.40%`，占全部候选快照比例较低
  - 进入开仓容量/手数阶段的候选约 `280` 笔，其中 `36/280 = 12.86%` 被 `maxpos4` 挡住
  - 被挡日期数：`28`
  - 被挡品种数：`14`
  - 被挡时 `active_positions_before=4` 且 `remaining_position_slots=0`：`36/36`
  - 年份分布：2020 年 `12`，2021 年 `16`，2022 年 `7`，2023 年 `1`
  - 方向分布：多头 `29`，空头 `7`
  - 信号分布：`long_case2=19`，`long_case1a=7`，`long_case3=3`，`short_case1a=7`
  - 品种分布：`SM.CZCE=5`，`jm.DCE=4`，`hc.SHFE=3`，`CF.CZCE=3`，`au.SHFE=3`，`rb.SHFE=3`，`SA.CZCE=3`，`sp.SHFE=2`，`MA.CZCE=2`，`OI.CZCE=2`，`FG.CZCE=2`，`AP.CZCE=2`，`fu.SHFE=1`，`lh.DCE=1`

## 输出文件

- report：无
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage794_stage777_2020_capacity_block_skip_reason_stage794_stage777_2020_capacity_block_v1.csv`
- orders：无
- daily：无
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage794_stage777_2020_capacity_block_entry_candidates_stage794_stage777_2020_capacity_block_v1.csv`

## 结论

- 本阶段结论：候选版 2020 启动全路径中，因为已经达到 4 个品种/仓位上限而没有开仓成功的候选信号是 `36` 笔。这个数量不是主导性过滤来源，远小于空头拒绝 `293`、AI品种池拦截 `162`、供需逆风拦截 `83`，但在真正进入开仓阶段的候选里占 `12.86%`，说明 `maxpos4` 有实际容量影响。
- 是否进入下一步：可选，不建议直接为了这 `36` 笔把正式候选改成 maxpos5。
- 下一步：如果要判断 maxpos4 是否过严，应对这 `36` 笔做“虚拟成交后验R倍数/是否与已有持仓同向高相关/是否抢占更好信号”的归因，而不是只看数量。

## 过拟合反思

- 运行前判断：否。本次是固定候选版、固定 2020 起点的事后容量计数，没有新增参数搜索。
- 运行后判断：否。统计结果没有用于挑选新阈值，只定位容量约束触发次数。
- 原因：`skip_reason=concurrent_limit` 是策略日志中的机械状态字段，不依赖收益标签。

## 继续价值反思

- 运行前判断：有价值。用户问题直接指向 maxpos4 是否错过机会。
- 运行后判断：有价值但不应扩展成盲目扫 maxpos。`36` 笔数量足够做逐笔后验归因，但不足以单独证明应该提高最大持仓。
- 原因：容量约束可能挡掉赢家，也可能挡掉低质量尾部机会；必须结合后验收益、相关性和已有持仓质量判断。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
