# Stage008 当前正式版严格基准与日线突破质量归因结果

- line_id：`futures_trend_tight_stop_quality_sizing`
- 当前模式：`research / day`
- 记录时间：`2026-07-14 16:13 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：当前正式版历史路径基准重建、会计/R/AI/执行完整性审计和只读归因
- 是否重要突破：是，属于证据口径修复与可信基准里程碑，不是策略收益突破
- 是否触发A/B：否；策略与正式实盘均未改变

## 外部调研与判断

- AQR 长历史趋势研究支持趋势跟随作为跨周期母策略，但不能证明本仓库的具体加仓条件。
- 时间序列动量与波动状态研究支持把趋势位置和波动状态作为解释变量；`pysystemtrade` 和 Donchian 参考实现支持保留真实执行语义并排除当前 bar。
- 我的判断：Stage008 的价值是建立可复算母本，不是从同一历史继续找最优参数。独立终审确认全期基准结果已持久化，因此 `2023-2026` 不能再称为真正未见 OOS。

## 本次变更

- 新增脚本：`tools/stage008_fresh_baseline_breakout_quality_attribution.py`。
- 修改脚本：`tools/stage001_baseline_technical_attribution.py`，补实际成交价到初始止损的风险/R口径和 planned/actual 分离。
- 新增测试：Stage008 因果 source、实际风险、未来特征白名单 hash、forced event 唯一消费、账户/AI/特征门。
- 新增参数：无交易参数；新增 `2020-2022 discovery`、日线突破/路径效率/波动状态只读特征。
- 修改参数：无交易参数。
- 删除参数：无。
- 新增结果：严格基准、年度路径、回撤阶段、发现段分箱、完整输入输出 manifest 和图表。
- 修改结果：R 从计划成交风险改为实际成交风险；日线 `stop_atr14` 保持信号时 planned entry 到 initial stop，避免次日成交信息泄漏。
- 删除结果：删除会暴露后段逐行特征与结果联表的旧 private event 文件；保留全期基准结果并明确其不是 OOS。

## 回测参数

- 正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 数据区间：`2020-01-01 -> 2026-06-30`，实际首日 `2020-01-02`。
- 账户规模：`150,000`。
- 成本口径：正式滑点，commission `0`；总滑点 `1,712,120`。
- 策略口径：正式 AI 月池、broker10、增量保证金、正式 `0.5R` 开仓日实时止损和最多一次重试。
- AI 新特征：`0`。
- 样本：闭合根事件 `300`，closed lots `404`，终点未平仓 `rb2610.SHFE short 500`。

## 回测结果

- 期末权益：`5,167,871.60`。
- 总收益：`3345.247733%`。
- 最大回撤：`-65.350816%`。
- Sharpe：`1.260107`。
- 总滑点：`1,712,120`。
- 总交易次数：`793`。
- 事件胜率：`36.3333%`，`109/300`；closed-lot 胜率 `32.4257%`。
- 最长水下：`503` 个交易日；`2022-03-30 -> 2023-07-05` 谷底，`2024-04-29` 修复。
- 最大回撤区间：`-65.350816%`。
- 当前未修复回撤：`2025-07-25 -> 2026-06-24` 谷底约 `-52.4092%`。
- 已实现毛利：`6,534,991.60`；终点未实现：`195,000`；daily gross：`6,729,991.60`，误差 `0`。

## 严格审计

- 实际风险：`389/389` 个 open 由实际成交价、initial stop、size、volume 和 pricetick floor 重算；缺失 `0`。
- source 手数差异：`4/4` 均由唯一、同日期/合约/方向/手数的 forced margin deleverage event 解释；重复 exact event 和重复消费均 fail-close。
- 根开仓：`311/311` 等于严格交易会话首分钟 open。
- AI：月审计 `78/78 PASS`；候选 `842`、allowed `516`、blocked `212`，成员和数值 mismatch 均为 `0`。
- 实时止损重试：`131` 个 `0.5R` 事件、`78` 次重试；最多一次重试和手数守恒均通过。
- manifest：input `111/111`、output `27/27`；数据库 SHA 前后不变。
- 测试：整线 `65 passed`；Stage009 加入后整线最新为 `72 passed`。

## 独立复核

- 多轮阻断修复 reviewer：`019f5f44-a4bc-77e3-9518-b8b7cf6154fd`、`019f5f62-dea3-7a91-8751-f3808dcce1f4`、`019f5f79-036a-76e1-b33b-d62f7205359f`、`019f5f8a-fac0-7081-aa55-86d6ab7bf716`。
- 最终 reviewer：`Pascal / 019f5fa3-687a-7420-8ae2-9c3db74866f5`。
- 首轮终审发现：全期结果已持久化，错误的“未见 holdout”声明为治理 P0；forced event 重复 exact 为 P2。
- 修复后 closure：`P0/P1/P2/P3 = 0/0/0/1`，数值可信度 `99.9%`、closure 置信度 `99.8%`；P3 仅为 `LINE.md/registry.md` 待同步。
- 不可恢复边界：历史盲态不能恢复；已修复的是错误 OOS 声明，不是伪造新的盲态。

## 输出文件

- report：`outputs/stage008_fresh_baseline_breakout_quality_attribution/tight_stop_quality_stage008_report_stage008_fresh_baseline_breakout_quality_attribution_v1.md`
- summary：`outputs/stage008_fresh_baseline_breakout_quality_attribution/tight_stop_quality_stage008_summary_stage008_fresh_baseline_breakout_quality_attribution_v1.csv`
- daily：`outputs/stage008_fresh_baseline_breakout_quality_attribution/tight_stop_quality_stage008_daily_stage008_fresh_baseline_breakout_quality_attribution_v1.csv.gz`
- chart：`outputs/stage008_fresh_baseline_breakout_quality_attribution/tight_stop_quality_stage008_baseline_path_stage008_fresh_baseline_breakout_quality_attribution_v1.png`
- decision：`outputs/stage008_fresh_baseline_breakout_quality_attribution/tight_stop_quality_stage008_decision_stage008_fresh_baseline_breakout_quality_attribution_v1.json`

## 结论

- Stage008 可以关闭为可信的正式版历史路径基准；不改变正式版和实盘。
- 日线发现段中，前20日突破上四分位有较强右尾线索，但“紧止损”本身不是质量信号；用户目标已进一步收紧到分钟 K，因此不把日线规则直接推进真实引擎。
- 允许 Stage009 做分钟新特征的历史锁定评估；任何后段结论都必须标注不是真正 OOS。

## 过拟合反思

- 运行前判断：是，中高；相同历史已经被多次观察。
- 运行后判断：是，高；全期基准结果已见，后段不能提供真正独立样本外证据。
- 原因：特征定义虽在读取关系前冻结，但策略收益路径本身已知；只能降低调参自由度，不能恢复盲态。

## 继续价值反思

- 运行前判断：是；需要可信母本才能判断分钟级优化是否真实。
- 运行后判断：是，但证据等级受限；Stage009/010 历史结果只用于淘汰和形成 shadow 候选，最终仍需 `2026-06-30` 后 forward 数据。

## 合入建议

- 更新本线 `LINE.md`：是，随 Stage009 复核结果一并更新。
- 更新 `research/registry.md`：是，随 Stage009 复核结果一并更新。
- 追加根目录 `memory.md/back_log.md`：暂不追加；当前是重要证据修复，但尚无策略晋级或路线关闭。
