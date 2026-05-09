# Stage188 Stage78冷启动接入最新月度AI池回放

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-09 13:59 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：准实盘影子盘口径审计 / 月度AI池接入对照
- 是否重要突破：否
- 是否触发A/B：否。本阶段不修改Stage78策略参数，只替换回放输入的AI eligibility文件。

## 外部调研与判断

- 参考资料：
  - vn.py/VeighNa 回测资料显示组合回测支持多标的参数、初始资金、日度盈亏和统计指标输出。
  - vnpy_portfoliostrategy 资料显示组合策略模块用于跨多合约协同回测和执行。
- 我的判断：
  - 外部资料只能确认回测框架能力；AI池按 `eval_date` 切换是本仓库策略逻辑，应以本仓库代码和候选快照为准。
  - 把 Stage182 生成的 combined eligibility 接入 Stage188 是时序输入修正，不是调参。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage188_stage78_2026_30w_cold_start_latest_ai_pool.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `--ai-eligibility-path`：默认指向 Stage182 生成的 combined Stage78 eligibility。
- 修改参数：
  - 本阶段回放将 `ai_product_pool_eligibility_path` 从 Stage78 正式旧文件覆盖为 Stage182 combined 文件。
  - `trade_start_date=2026-01-01`，保持 Stage186 冷启动口径。
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - 指标预热：2025-01-01 至 2025-12-31
  - 交易分析：2026-01-01 至 2026-05-08
- 账户规模：300,000
- 成本口径：沿用 Stage78/Stage186 日线回测滑点与手续费口径
- 样本过滤：第78正式趋势策略，30万冷启动
- 策略/归因口径：
  - 固定 `official_stage78_defensive_v1`
  - 不修改趋势策略参数
  - 不接入震荡策略

## AI池审计

- 文件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
- 最早 `eval_date`：2019-12-31
- 最新 `eval_date`：2026-04-30
- `eval_date` 数量：52
- 最新池品种：
  - `SA.CZCE`
  - `SH.CZCE`
  - `FG.CZCE`
  - `si.GFEX`
  - `MA.CZCE`
  - `jm.DCE`
  - `rb.SHFE`
  - `AP.CZCE`
  - `fu.SHFE`
- 注意：
  - combined 文件从 2026-02-27 直接跳到 2026-04-30，中间没有 2026-03-31 池。
  - 因此 3月、4月仍使用 2026-02-27 池；5月交易开始使用 2026-04-30 池。

## 结果

- 期末权益：281,770
- 总收益：-6.0767%
- 最大回撤：-21.0817%
- Sharpe：-0.4507
- 总滑点：2,295
- 总交易次数：24
- 胜率：9.0909%
- 其他关键指标：
  - 目标日：2026-05-08
  - 目标日信号数：1
  - 目标日信号：`si2609.GFEX` Long Open 1手，理论价 9,025
  - 目标日风险级别：`watch`
  - 触发原因：`drawdown_watch`
  - 是否允许影子盘记录：1
  - 是否允许真实新增开仓：1

## 对比Stage186旧池

| 指标 | Stage186旧池 | Stage188最新池 | 差异 |
| --- | ---: | ---: | ---: |
| 期末权益 | 281,890 | 281,770 | -120 |
| 总收益 | -6.0367% | -6.0767% | -0.0400 pct |
| 最大回撤 | -21.0481% | -21.0817% | -0.0336 pct |
| Sharpe | -0.4476 | -0.4507 | -0.0031 |
| 总滑点 | 2,285 | 2,295 | +10 |
| 总交易次数 | 23 | 24 | +1 |
| 目标日信号数 | 1 | 1 | 0 |

## 差异归因

- Stage186 旧池在 2026-05-07 阻断 `rb.SHFE`。
- Stage188 最新池中 `rb.SHFE` 出现在 2026-04-30 池第7名，因此 2026-05-07 新增 `rb2610.SHFE` Long Open 1手。
- 2026-05-08 的 `si2609.GFEX` Long Open 1手信号不变，但其 AI 池信号日期从 2026-02-27 更新为 2026-04-30，排名从第3变为第4。
- 新增 `rb2610.SHFE` 持仓导致截至 2026-05-08 期末权益比 Stage186 少 120 元。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage188_stage78_2026_30w_latest_ai_pool_report_stage188_stage78_2026_30w_latest_ai_pool_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage188_stage78_2026_30w_latest_ai_pool_summary_stage188_stage78_2026_30w_latest_ai_pool_v1.json`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage188_stage78_2026_30w_latest_ai_pool_comparison_vs_stage186_stage188_stage78_2026_30w_latest_ai_pool_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage188_stage78_2026_30w_latest_ai_pool_20260101_30w_to_20260508_trades_2020_2026_04.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage188_stage78_2026_30w_latest_ai_pool_20260101_30w_to_20260508_daily.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage188_stage78_2026_30w_latest_ai_pool_daily_report_stage188_stage78_2026_30w_latest_ai_pool_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage188_stage78_2026_30w_latest_ai_pool_signal_plan_stage188_stage78_2026_30w_latest_ai_pool_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage188_stage78_2026_30w_latest_ai_pool_20260101_30w_to_20260508_professional_dashboard.html`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage188_stage78_2026_30w_latest_ai_pool_20260101_30w_to_20260508_trade_review.html`

## 结论

- 本阶段结论：
  - 接入最新月度AI池后，2026-05-08目标日主信号仍是 `si2609.GFEX` 开多1手。
  - 主要变化是 2026-05-07 多开 `rb2610.SHFE` 1手，导致权益小幅降低 120 元。
  - 最新AI池接入没有推翻 Stage186 的总体判断：30万冷启动仍处于亏损与 `watch` 状态，但低于用户设定的 40%最大可接受回撤。
- 是否进入下一步：是
- 下一步：
  - 后续影子盘默认应使用 Stage188 最新AI池口径，而不是 Stage186 旧池口径。
  - 补齐 2026-03-31 月度池缺口，确认 4月信号是否本应不同。
  - 继续做 T+1 开盘/日盘开盘代理成交价，降低同日收盘成交口径的乐观性。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：
  - 本阶段没有根据回测结果选择池或修改参数，只接入按 SOP 生成的最新月度AI池。
  - 结果略差也保留并记录，说明不是为了调好收益。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：
  - 影子盘必须保证AI月度池时序和日线数据同步。
  - 本阶段发现 3月池缺口，以及 5月新池会改变 `rb.SHFE` 开仓，这是实盘前必须知道的执行差异。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，待补齐 2026-03-31 池缺口和 T+1 代理成交后再更新。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是影子盘口径审计，不是正式策略升级。
