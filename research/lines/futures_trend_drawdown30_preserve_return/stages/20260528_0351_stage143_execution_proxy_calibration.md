# Stage143 执行代理价校准审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 03:51 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行模型审计；不修改 Stage079/C3/Stage103 交易规则。
- 是否重要突破：否，但属于重要风险闸门。它限制 Stage103 直接进入真实 paper/影子盘。
- 是否触发A/B：否。本阶段没有提出新策略候选，只校准成交代理。

## 外部调研与判断

- 参考资料：
  - SHFE Trading Hours：https://www.shfe.com.cn/eng/reports/CalendarHolidays/TradingHours/
  - DCE 官方交易时间资料：https://www.dce.com.cn/dceg/file/2025-05-29/1748480876704ff80808197162e7128701971994e0a01313.pdf
  - ZCE CF 合约细则夜盘时间示例：https://english.zce.cn/en/Rulebook/DetailedRules/webinfo/2024/02/1708568086296612.htm
  - 南华期货交易时间汇总：https://www.nanhua.net/cmsbigfile/2024/11/c7be3f53-3ee2-4e9d-a55f-c074f5165c5b/Trading%20Hours%202024.11.18.pdf
- 我的判断：国内商品期货有夜盘和日盘分段，日线 `next bar open` 对有夜盘品种更接近“收盘后生成信号、下一交易日夜盘开盘/集合竞价执行”的代理，对无夜盘品种更接近次日 09:00 执行代理；`same-day close` 只有在盘中提前生成稳定信号、或有合规收盘价交易机制时才可视为可执行。当前本地没有完整分钟线/盘口级 `20:55/21:00/09:00` 可成交价，因此 Stage143 只能给出日线代理风险边界，不能宣称完成真实成交校准。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage443_execution_proxy_calibration.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：执行代理 `same_day_close`、`t1_next_open`、`t1_next_close`；订单缺口按夜盘/日盘或未确认会话分桶。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：`615,000`，即 Stage079 `50万C3下单 + 11.5万外部现金`。
- 成本口径：当前真实引擎默认成本，未额外放大滑点。
- 样本过滤：无坏日期、无坏品种过滤。
- 策略/归因口径：
  - C3 主体分别用同日收盘、T+1 next open、T+1 next close 三个引擎重跑。
  - Stage103 的 xsmom 腿沿用 Stage403 冻结日度路径，目的是隔离 C3 执行代理风险。
  - 订单级缺口使用同日成交订单，检查同一订单若移动到下一交易日 open/close 的不利现金冲击。

## 结果

- Stage079 同日收盘口径：
  - 期末权益 `31,040,650`
  - 总收益 `4947.2602%`
  - 最大回撤 `-29.7007%`
  - Sharpe `1.6226`
  - Ulcer `15.1468`
  - 总滑点 `1,556,750`
  - 总交易次数 `757`
- Stage079 `T+1 next open`：
  - 期末权益 `32,778,250`
  - 总收益 `5229.7967%`
  - 最大回撤 `-52.7518%`
  - Sharpe `1.4928`
  - Ulcer `19.2452`
  - rolling252/504 破30回撤率 `39.5785% / 59.6696%`
  - 年度/季度 DD30 通过率 `60.0000% / 52.3810%`
  - 3个月/6个月体验分 `44.8515 / -67.7624`
  - 总滑点 `2,003,820`
  - 总交易次数 `781`
- Stage079 `T+1 next close`：
  - 期末权益 `34,817,080`
  - 总收益 `5561.3138%`
  - 最大回撤 `-53.8822%`
  - Sharpe `1.4638`
  - Ulcer `17.7253`
  - rolling252/504 破30回撤率 `59.7970% / 88.7269%`
  - 年度/季度 DD30 通过率 `0.0000% / 4.7619%`
  - 3个月/6个月体验分 `-15.7349 / -257.5107`
- Stage103 同日收盘口径：
  - 期末权益 `31,730,915`
  - 总收益 `5059.4984%`
  - 最大回撤 `-28.9792%`
  - Sharpe `1.6835`
  - Ulcer `14.3669`
  - 总滑点 `1,569,265`
  - 总交易次数 `1,217`
  - 3个月/6个月体验分 `121.0947 / 124.5738`
- Stage103 `C3 T+1 next open + xsmom冻结路径`：
  - 期末权益 `33,468,515`
  - 总收益 `5342.0350%`
  - 最大回撤 `-49.6765%`
  - Sharpe `1.5455`
  - Ulcer `18.2071`
  - rolling252/504 破30回撤率 `47.9313% / 59.6696%`
  - 年度/季度 DD30 通过率 `60.0000% / 52.3810%`
  - 3个月/6个月体验分 `58.9674 / -28.5166`
- Stage103 `C3 T+1 next close + xsmom冻结路径`：
  - 期末权益 `35,507,345`
  - 总收益 `5673.5520%`
  - 最大回撤 `-48.8675%`
  - Sharpe `1.5314`
  - Ulcer `16.5726`
  - rolling252/504 破30回撤率 `59.5628% / 88.5326%`
  - 年度/季度 DD30 通过率 `0.0000% / 4.7619%`
  - 3个月/6个月体验分 `15.0415 / -176.6144`
- 订单级缺口：
  - 同日订单数 `757`
  - next-open 可用率 `100%`
  - next-open 总不利现金冲击 `469,010`
  - next-close 总不利现金冲击 `9,161,385`
  - next-open 不利现金均值 `619.56`
  - next-open 不利 tick 中位数 `-1.0`
  - next-open 绝对不利 tick P95 `168.0`
  - next-open 不利订单占比 `46.4993%`
  - 最大单日 next-open 不利冲击 `1,434,120`
  - 最小单日 next-open 不利冲击 `-2,335,000`
  - 开仓订单 next-open 总不利冲击 `7,725,630`
  - 平仓订单 next-open 总不利冲击 `-7,256,620`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage443_execution_proxy_calibration_report_stage443_execution_proxy_calibration_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage443_execution_proxy_calibration_summary_stage443_execution_proxy_calibration_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage443_execution_proxy_calibration_horizon_stage443_execution_proxy_calibration_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage443_execution_proxy_calibration_score_stage443_execution_proxy_calibration_v1.csv`
- execution_matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage443_execution_proxy_calibration_execution_matrix_stage443_execution_proxy_calibration_v1.csv`
- trade_gap_ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage443_execution_proxy_calibration_trade_gap_ledger_stage443_execution_proxy_calibration_v1.csv`
- trade_gap_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage443_execution_proxy_calibration_trade_gap_summary_stage443_execution_proxy_calibration_v1.csv`
- worst_dates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage443_execution_proxy_calibration_worst_gap_dates_stage443_execution_proxy_calibration_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage443_execution_proxy_calibration_decision_stage443_execution_proxy_calibration_v1.json`

## 结论

- 本阶段结论：`same_day_close_not_deployment_safe_next_open_requires_intraday_calibration`。
- 是否进入下一步：是，但不是继续调 alpha；应先补真实执行代理。
- 下一步：
  - 暂缓把 Stage103 直接推进真实 paper/影子盘。
  - 先补 `20:55/21:00/09:00` 分钟线或 QMT 行情采样，确认真实可执行代理价。
  - 若无法取得分钟线，则 Stage103 只能保留为同日收盘研究候选，不能把同日收盘结果当作真实可执行体验。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做执行代理校准，没有按坏日期、坏品种、坏窗口筛规则；订单缺口显示 next-open 冲击并非单向不利，不能被用来构造黑名单。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但方向要切换。
- 原因：严格目标仍未完成，Stage103 同日口径仍是主候选；但在真实执行代理前继续优化 3个月/6个月指标会放大成交假设风险。下一步最有价值的是执行数据校准，而不是继续救旧参数。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新 Stage143 执行约束。
- 是否更新 `research/registry.md`：是，这是本线当前优先级变化。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`。
