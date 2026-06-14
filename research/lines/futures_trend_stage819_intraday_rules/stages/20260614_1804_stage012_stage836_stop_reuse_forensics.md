# Stage012 Stage836 止损后释放资金再使用归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 18:04 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因 + 增量开仓分钟K图谱；不改正式策略、不改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。它排除了 blanket cooldown 方向，但没有形成可晋级新策略。
- 是否触发A/B：否。没有新候选准备接入正式版，也没有与第78/Stage372做组合实验。

## 外部调研与判断

- 参考资料：
  - Investopedia `Stop-Loss Orders: Protect Your Investments From Losses`：强调止损后的 re-entry risk，重新进场可能被短期反弹误导，形成止损、追入、再止损循环。
  - Semantic Scholar 收录的 Klement 2013 `Assessing Stop-Loss and Re-Entry Strategies` 摘要：止损策略的价值必须与再入场规则一起评估。
  - QuantStart `Backtesting Systematic Trading Strategies in Python`：强调 backtesting 与 trading simulator 对 bar-by-bar 执行和真实部署差异的检验价值。
- 我的判断：
  - Stage011 证明 C2/C4 直接止损事件总体正贡献后，下一步不能孤立讨论“止损好不好”，必须看止损后释放的风险预算如何再使用。
  - 外部资料支持这个判断：止损的风险不只在出场价，也在出场后的再暴露。
  - 本阶段结果反证 blanket cooldown：C2/C4 止损后 10 日内新增/放大 C 暴露总体为正贡献；简单把止损后资金冻结，很可能砍掉跨品种右尾。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage836_stage827_stop_reuse_forensics.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定观察窗口 `1/3/5/10` 个交易日。
  - `nearest-stop` 口径：每个 C-vs-A 增量开仓只归因给最近的前序日内止损，避免重复计数。
  - `event-window` 口径：以每个止损事件为锚点，允许窗口重叠，仅作环境参考。
- 修改参数：无
- 删除参数：无
- 新增回测结果：无新完整组合回测；新增止损后再使用归因结果。
- 修改回测结果：无
- 删除回测结果：无

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-05-29`
- 账户规模：沿用 Stage819 候选 30w 口径；本阶段不重新模拟权益曲线。
- 成本口径：沿用 Stage827/Stage830 已生成 closed lots 的成本口径；本阶段不新增滑点模型。
- 样本过滤：
  - A：Stage827 `stage827_stage819_baseline`
  - C2：Stage827 `stage827_stage819_c2_engine`
  - C4：Stage830 `stage830_stage819_c2_broker10_100_cap`
  - 止损锚点：Stage827/830 intraday_events 中的 C2 1R stop 触发事件。
- 策略/归因口径：
  - 按 `entry_date/vt_symbol/direction/signal/entry_context/layer_kind/entry_price_key` 聚合开仓。
  - 将 C 相对 A 的开仓差异分为 `C_only`、`C_larger`、`C_smaller`、`A_only`、`both_equal`。
  - `incremental C exposure` 只包括 `C_only` 与 `C_larger`。
  - 主判断使用 `nearest-stop`，因为它避免一个增量开仓被多个止损窗口重复计数。

## 结果

- 期末权益：不适用，本阶段不是完整组合回测。
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - C2 nearest-stop 10日：`99` 行差异，incremental `52` 行，reduced `25` 行；增量风险 `+1,830,317.2`，增量 PnL `+3,532,434.4`；增量正/负行数 `26/26`。
  - C4 nearest-stop 10日：`99` 行差异，incremental `16` 行，reduced `68` 行；增量风险 `+412,739.2`，增量 PnL `+2,267,950.0`；增量正/负行数 `7/9`。
  - C2 1日 incremental PnL 为 `-341,540.0`，3日转正 `+1,043,380.0`，10日显著转正，说明“刚止损后立刻新增风险”弱，但跨几日的再使用有右尾。
  - C4 1日 incremental PnL 为 `-309,050.0`，3日转正 `+895,990.0`，10日 `+2,267,950.0`；同时 C4 10日总 volume delta 为 `-1,821`、risk delta 为 `-1,308,353.2`，说明 broker cap 已经显著压缩总体暴露。
  - Exposure bucket：
    - C2 `C_only`：`10` 行，PnL `-594,960.0`；C2 `C_larger`：`42` 行，PnL `+4,127,394.4`。
    - C4 `C_only`：`9` 行，PnL `-152,440.0`；C4 `C_larger`：`7` 行，PnL `+2,420,390.0`。
  - 产品桶只作线索：C2 `rb.SHFE long` 负贡献 `-510,940.0`，`au.SHFE long` `-249,880.0`；但 C2 `OI.CZCE long` 正贡献 `+1,001,400.0`，`sp.SHFE long` `+310,674.4`。不得按产品过滤救参。
  - 最差增量开仓多为跨品种：例如 `rb2205.SHFE long 2022-01-14` 距最近 `jm.DCE long` 止损 6 个交易日，PnL delta `-390,000`；`cu2502.SHFE short 2025-01-03` 距最近 `lc.GFEX short` 止损 1 个交易日，PnL delta `-350,300`。同品种止损后再开不是主因。

## 视觉复盘

- `reuse_chart` 显示 C2/C4 的 10日 incremental C exposure PnL 都明显为正；C4 的 incremental risk 明显低于 C2，符合 broker cap 压缩总体暴露的作用。
- 最差增量开仓 atlas 显示：
  - `rb2205.SHFE long 2022-01-14` 入场日价格大部分时间在 entry 上方，但最终退出差，属于后续路径恶化，不是入场分钟立即失败。
  - `cu2502.SHFE short 2025-01-03` 入场日波动较大，价格先顺后反，且不是最近止损同品种重入。
  - `au2112.SHFE long 2021-11-11` 入场日没有明显的同品种止损后复仇形态，更像跨品种释放风险后的趋势机会失败。
- 视觉判断：blanket 同品种冷却或所有资金冷却都不贴合事实。负贡献不是一类干净的“止损后马上同品种再进”的分钟K形状。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage836_stage827_stop_reuse_forensics_report_stage836_stage827_stop_reuse_forensics_v1.md`
- nearest_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage836_stage827_stop_reuse_forensics_nearest_summary_stage836_stage827_stop_reuse_forensics_v1.csv`
- nearest_attribution：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage836_stage827_stop_reuse_forensics_nearest_stop_attribution_stage836_stage827_stop_reuse_forensics_v1.csv`
- event_window_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage836_stage827_stop_reuse_forensics_event_window_summary_stage836_stage827_stop_reuse_forensics_v1.csv`
- event_window_attribution：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage836_stage827_stop_reuse_forensics_event_window_attribution_stage836_stage827_stop_reuse_forensics_v1.csv`
- exposure_bucket：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage836_stage827_stop_reuse_forensics_exposure_bucket_stage836_stage827_stop_reuse_forensics_v1.csv`
- product_bucket：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage836_stage827_stop_reuse_forensics_product_bucket_stage836_stage827_stop_reuse_forensics_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage836_stage827_stop_reuse_forensics_decision_stage836_stage827_stop_reuse_forensics_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage836_stage827_stop_reuse_forensics_reuse_chart_stage836_stage827_stop_reuse_forensics_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage836_stage827_stop_reuse_forensics_atlas_manifest_stage836_stage827_stop_reuse_forensics_v1.csv`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage836_stage827_stop_reuse_forensics_atlas_page001_stage836_stage827_stop_reuse_forensics_v1.png` 到 `page003`

## 结论

- 本阶段结论：`stage836_reuse_incremental_positive_no_blanket_cooldown`。
- 是否进入下一步：进入，但不做 blanket cooldown，也不做同品种冷却。
- 下一步：
  - 转向 Stage837：持仓后全路径保证金集中与权益分母风险归因，重点看 broker100/DD50 压力日之前的持仓簇、产品簇、方向簇和分钟级不利运动，而不是止损后再开仓本身。
  - 如果后续要设计规则，只能是更贴近事实的账户层/持仓层规则，例如“高保证金压力 + 产品簇集中 + 持仓中分钟级不利运动”触发减风险；不能按 `rb/au/2020` 过滤。

## 过拟合反思

- 运行前判断：否。Stage836 用固定 `1/3/5/10` 交易日窗口和 frozen C2/C4 止损事件，不按产品、年份或时段筛选。
- 运行后判断：否，但产品桶有明显诱惑。
- 原因：C2 的 `rb.SHFE long`、`au.SHFE long` 负贡献看起来可过滤，但样本很小且同时存在 `OI.CZCE long` 等大正贡献；把这些桶变成规则会过拟合。

## 继续价值反思

- 运行前判断：有价值。它能验证“释放资金再使用”是否真是 C2/C4 尾部恶化主因。
- 运行后判断：有价值，但方向需要调整。
- 原因：止损后 10日 incremental C exposure 是正贡献，说明 blanket 冷却不是正确方向；尾部风险更可能来自持仓后保证金/权益路径和产品簇集中，值得继续只读拆解。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage012 结论和 Stage013 方向。
- 是否更新 `research/registry.md`：否。不是正式候选、重要突破或路线迁移。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选或重要合入摘要。
