# Stage212 Stage208坏窗口逐笔/账本复盘

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-01 18:27 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读坏窗口复盘；不新增规则、不调参数、不做收益筛选。
- 是否重要突破：否。重要结论是解释 Stage208 主候选脆弱来源，并拒绝直接上 ATR/K线补丁。
- 是否触发A/B：否。没有新候选版本。

## 外部调研与判断

- 参考资料：
  - 趋势跟随的主要风险是长水下与 whipsaw，而非单日止损能完全解决；ATR/Chandelier 属于常见工具，但需要非常谨慎验证，不能因为单个坏窗口就调倍数。
  - 本仓库已有盈利锁/ATR/Chandelier 退出线反证记录：`futures_trend_profit_lock_exit` Stage007-009。
  - 本线已有 Stage029/030/032/039/054 反证：早期 ATR/MAE 早停、已有仓位释放、分层锁盈 sizing、单笔风险上限都不能在保收益前提下稳定解决主回撤。
- 我的判断：
  - Stage211 已显示主候选贴线但有价值；Stage212 的任务是判断是否出现低自由度、可解释的坏窗口结构。
  - 如果坏窗口只是“xsmom 空档 + C3 路径承压”，那不是 ATR/K线形态能稳健解决的问题；继续要么做更完整的持仓日度归因，要么在部署层选择 `risk060 + true xsmom` 作为保守口径。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage511_stage208_bad_window_postmortem.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；新增峰谷、最差日、xsmom活动、C3成交 usage 近似已实现盈亏归因。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：复核 Stage208/211 的坏窗口，核心峰谷为 `2021-09-16` 至 `2022-02-11`。
- 账户规模：沿用 Stage208 `615,000` 账户口径。
- 成本口径：沿用 Stage208/Stage506 成交 ledger；本阶段不新增成本假设。
- 样本过滤：无。
- 策略/归因口径：
  - 主候选：`risk070_clean + true-carried Stage103 xsmom`。
  - 订单归因：根据 Stage506 C3 `trade_usage` 还原近似已实现 gross PnL；不含未平仓持仓逐日盯市损益，因此只作产品暴露线索，不作完整产品 PnL。

## 结果

- 主候选期末权益：沿用 Stage208 `21,210,535`
- 主候选总收益：沿用 Stage208 `3348.8675%`
- 主候选最大回撤：沿用 Stage208 `-38.5861%`
- 主候选 Sharpe：沿用 Stage208 `1.1674`
- 总滑点：本阶段无新增。
- 总交易次数：本阶段无新增。
- 胜率：本阶段无新增逐笔胜率。
- 其他关键指标：
  - 最差90日峰谷：`2021-11-18` 到 `2022-02-11`，回撤 `-32.6713%`，xsmom 活跃天数 `0`、PnL `0`。
  - 最差180/252/504日峰谷实际都落在 `2021-09-16` 到 `2022-02-11`，回撤 `-38.5861%`，xsmom 活跃天数 `0`、PnL `0`。
  - 180日完整窗口中 xsmom 在峰谷前有 `20` 个活跃日、PnL `93,840`；但真正峰到谷阶段 xsmom 不参与，说明它是抬升窗口两端而不是直接保护最大下跌段。
  - 峰谷最差日均由 clean C3 贡献，xsmom PnL 为 `0`。
  - 近似已实现亏损产品线索：180日峰谷内 `ru.SHFE -595,200`、`lh.DCE -532,320`、`sp.SHFE -102,620`、`rb.SHFE -55,920`、`au.SHFE -40,780`；但该表不含持仓盯市，禁止据此做品种黑名单。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage511_stage208_bad_window_postmortem_report_stage511_stage208_bad_window_postmortem_v1.md`
- summary：无独立 summary；使用 peak_trough / product_summary。
- orders：沿用 Stage506 trade usage。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage511_stage208_bad_window_postmortem_top_loss_days_stage511_stage208_bad_window_postmortem_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage511_stage208_bad_window_postmortem_peak_trough_stage511_stage208_bad_window_postmortem_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage511_stage208_bad_window_postmortem_trade_product_summary_stage511_stage208_bad_window_postmortem_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage511_stage208_bad_window_postmortem_xsmom_activity_stage511_stage208_bad_window_postmortem_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage511_stage208_bad_window_postmortem_chart_stage511_stage208_bad_window_postmortem_v1.png`
- decision：`bad_windows_are_c3_path_and_xsmom_activation_gap_no_direct_rule_change`

## 图表视觉复盘

- `2021-09` 至 `2022-02` 红色峰谷区域里，主候选与 clean C3 基本重合，说明 true xsmom 在真正下跌段没有保护。
- 主候选在 `2022-02-11` 触及最深水下，随后反弹；这是典型路径承压，不是单日异常。
- 最差90日 top loss days 全部为 C3 PnL，xsmom PnL 为 `0`。

## 结论

- 本阶段结论：`bad_windows_are_c3_path_and_xsmom_activation_gap_no_direct_rule_change`。
- 是否进入下一步：是，但下一步不是新增 ATR/K线策略。
- 下一步：
  1. 若要继续研究策略本体，先补完整 C3 持仓日度产品归因，弄清峰谷期间的未实现盯市损益。
  2. 同时把 `risk060 + true xsmom` 作为保守部署口径，与 `risk070 + true xsmom` 做真实保证金对照。
  3. 禁止根据 `ru/lh/sp/rb/au` 已实现亏损直接做黑名单；禁止直接扫 ATR 倍数、K线阈值或 xsmom 激活窗口。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只解释固定坏窗口，没有修改规则。若继续用这些日期或产品去定制过滤器，就会过拟合。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但方向更明确。
- 原因：Stage208 仍有价值；但如果目标是实盘可执行，下一步应该优先选择部署口径或补完整持仓归因，不应快速堆策略补丁。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为是否继续策略本体优化的重要边界。
