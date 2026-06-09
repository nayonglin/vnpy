# Stage440 现金备用桶逐月启动验证

- line_id：`futures_trend_cash_reserve_bucket`
- 当前模式：`day`
- 记录时间：`2026-06-09 12:13 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：资金管理 A/B 研究、逐月独立启动验证
- 是否重要突破：否，属于反证但保留经验
- 是否触发A/B：是，遵循 `skills/version-ab-experiment/SKILL.md`

## 外部调研与判断

- 参考资料：
  - Fixed fractional sizing 的基本定义：按当前账户权益固定比例承担风险，权益下跌会自动降仓。参考 `https://journalplus.co/learn/glossary/fixed-fractional`
  - 期货手数 sizing 资料也强调按账户权益、风险比例、止损距离和合约点值计算手数，整数手会放大小账户颗粒度。参考 `https://nexusfi.com/a/risk-management/position-sizing`
  - GitHub walk-forward 主题和相关项目说明多起点/滚动验证是降低单一路径误判的常用方法。参考 `https://github.com/topics/walk-forward-analysis`
- 我的判断：备用桶有理论基础，因为正式版按权益计算风险预算，早期亏损会降低后续手数；但它不是 alpha，必须用逐月启动验证是否穿越周期。结果显示它能修复 `2022-05`，但系统性牺牲 2020 强路径复利底座，不能接正式版。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage751_cash_reserve_bucket_monthly_start.py`
- 修改脚本：无正式策略文件修改；仅研究脚本内新增 `CashReserveBucketStrategy` 子类
- 删除脚本：无
- 新增参数：
  - `enable_cash_reserve_bucket=True`
  - `cash_reserve_bucket_trading_target=400000`
  - `cash_reserve_bucket_initial_reserve=100000`
  - `cash_reserve_bucket_only_after_trade_start=True`
- 修改参数：
  - C 的 `account_capital=500000`
  - C 的 `c3_capital=400000`
  - `risk_multiplier=0.80`、正式连败缩放、recovery sleeve、AI 池、品种池、`maxpos4`、broker10 `95%->80%` 均不变
- 删除参数：无

## 回测/归因参数

- 数据区间：逐月独立启动 `2020-01` 至 `2026-04`，统一结束 `2026-04-30`
- 账户规模：总资金 `500,000`；C 的交易桶 `400,000`，备用桶 `100,000`
- 成本口径：沿用 Stage750/正式成本和 broker10 精确保保证金审计
- 样本过滤：全体 `76` 个起点；成熟样本 `>=252` 交易日为 `64` 个
- 策略/归因口径：
  - A50：Stage750 A50 正式逻辑，`account_capital/c3_capital=500000`
  - C：正式逻辑不变，仅把策略内部权益拆成交易桶和备用桶；备用桶补款发生在策略 `_refresh_risk_state` 里，早于组合回撤、风险预算和手数计算

## 结果

- C 全周期 `2020-01`：
  - 期末权益：`9,656,610`
  - 总收益：`1831.322%`
  - 最大回撤：`-39.0439%`
  - Sharpe：`1.3532`
  - 总滑点：`829,730`
  - 总交易次数：`674`
  - 胜率：`52.3851%`
  - broker10 最高保证金/权益：`75.7592%`
  - 备用桶使用：`90,950`，补款 `15` 次
- A50 全周期 `2020-01`：
  - 期末权益：`21,371,670`
  - 总收益：`4174.334%`
  - 最大回撤：`-39.7236%`
  - Sharpe：`1.6218`
  - 总滑点：`1,161,790`
  - 总交易次数：`677`
  - 胜率：`52.8954%`
- 全体 `76` 个起点：
  - C 收益胜出：`20/76`
  - C 回撤胜出：`68/76`
  - 中位收益差：`-55.6745pp`
  - 中位收益保留：`82.7515%`
  - C DD40 失败：`0/76`
  - A50 DD40 失败：`2/76`
  - 备用桶使用：`55/76`
- 成熟 `>=252` 起点：
  - C 收益胜出：`16/64`
  - C 回撤胜出：`57/64`
  - 中位收益差：`-70.7835pp`
  - 中位收益保留：`82.7515%`
  - C DD40 失败：`0/64`
  - A50 DD40 失败：`2/64`
- 重点 `2022-05`：
  - A50：`1,037,895/107.579%/-29.9920%/Sharpe0.7818`
  - C：`1,909,280/281.856%/-27.6160%/Sharpe1.1854`
  - C 备用桶 `2` 次补满 `100,000`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage751_cash_reserve_bucket_monthly_start_report_stage751_cash_reserve_bucket_monthly_start_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage751_cash_reserve_bucket_monthly_start_summary_stage751_cash_reserve_bucket_monthly_start_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage751_cash_reserve_bucket_monthly_start_comparison_stage751_cash_reserve_bucket_monthly_start_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage751_cash_reserve_bucket_monthly_start_curves_stage751_cash_reserve_bucket_monthly_start_v1.csv`
- reserve_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage751_cash_reserve_bucket_monthly_start_reserve_events_stage751_cash_reserve_bucket_monthly_start_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage751_cash_reserve_bucket_monthly_start_chart_stage751_cash_reserve_bucket_monthly_start_v1.png`
- heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage751_cash_reserve_bucket_monthly_start_heatmap_stage751_cash_reserve_bucket_monthly_start_v1.png`
- focus：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage751_cash_reserve_bucket_monthly_start_focus_202205_stage751_cash_reserve_bucket_monthly_start_v1.png`

## 结论

- 本阶段结论：`cash_reserve_bucket_not_promoted`。备用桶能改善回撤和个别冷启动路径，尤其 `2022-05`，但成熟样本收益胜率只有 `16/64`，中位收益差为负，且 2020 强路径损失很大。
- 是否进入下一步：不作为正式主策略增强继续推进。
- 下一步：如果继续账户层研究，优先考虑不降低初始交易桶的“外层备用金/出金锁盈/生存线”框架，而不是继续扫 `40w+10w` 附近比例。

## 过拟合反思

- 运行前判断：过拟合风险低，因为只验证一个预声明资金结构，不扫参数。
- 运行后判断：不是参数过拟合导致失败，而是结构性 trade-off 暴露；C 把强路径初始交易能力从 50 万降到 40 万，天然损失复利底座。
- 原因：这个结构确实修复 `2022-05`，但不能普适增强收益；若继续按月份或比例救参，就会进入过拟合。

## 继续价值反思

- 运行前判断：有价值，因为它直接回答冷启动亏损压低后续仓位的问题。
- 运行后判断：本形态不值得作为正式增强继续做；作为账户体验和生存线思想仍有参考价值。
- 原因：回撤改善很明显，但收益胜率和成熟样本中位收益差不过关。下一步应换结构，而不是围绕备用比例微调。

## 合入建议

- 是否更新本线 `LINE.md`：是，已更新。
- 是否更新 `research/registry.md`：建议更新，新增该线并标记反证。
- 是否追加根目录 `memory.md/back_log.md`：建议只追加 `back_log.md`，作为重要反证摘要；不追加 `memory.md`。
