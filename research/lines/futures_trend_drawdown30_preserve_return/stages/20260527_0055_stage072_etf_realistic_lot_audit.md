# Stage072 ETF真实整手承载复核

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 00:55 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage071候选真实性复核；路线降级
- 是否重要突破：否，重要反证
- 是否触发A/B：是。Stage071 ETF腿可能接入正式候选，本阶段按A/C纪律复核真实承载。

## 外部调研与判断

- 参考资料：
  - 上海证券交易所 ETF 问答：ETF买卖最低为1手，即100份基金份额；最小价格变动单位为0.001元。
  - 深圳证券交易所基金交易问答：基金份额买入申报数量为100份或整数倍；卖出不足100份的余额可以一次性卖出。
- 我的判断：
  - ETF比个股更适合小资金承载，但 Stage071 的优势只有约22.9个百分点总收益，必须用真实整手、最低佣金、换手和多起点现金对照复核。
  - 真实承载复核不是调参；如果复核后主要优势只来自早期样本或低费用假设，就不能升级。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage372_etf_realistic_lot_audit.py`
- 修改脚本：无正式策略脚本修改；仅新增独立审计入口。
- 删除脚本：无。
- 新增参数：
  - ETF腿资金：`25,000`
  - ETF整手：`100` 份
  - 主审计费用：`lot100_fee10bp_min5`，即单向10bp、每笔5元最低佣金
  - 压力费用：`lot100_fee20bp_min5`
  - 无最低佣金对照：`lot100_fee10bp_min0`
- 修改参数：无。
- 删除参数：无。

## A/B/C口径

- A：`C3 100%`
- B：Stage071 ETF核心流动Connors独立腿，重新按25,000元、100份整手、费用和现金约束撮合
- C：`95%C3 + 5%真实ETF整手腿`
- 现金对照：`95%C3 + 5%现金`

## 回测/审计参数

- 数据区间：公共样本 `2020-01-02` 至 `2026-04-28`
- 账户规模：组合口径50万；ETF腿25,000元
- 成本口径：
  - C3沿用 Stage336 日账本，C3总滑点 `1,556,750`
  - ETF腿主口径总费用 `2,915`
  - ETF腿主口径总成交 `583`
- 策略/归因口径：
  - 不改78-1、C3、ETF信号、ETF候选列表、Connors参数或权重。
  - 每个ETF信号日按下一ETF交易日收盘调仓，目标权重按100份整手向下取整，现金不足时降手数。

## 结果

- C3基准：期末权益 `30,285,100`，总收益 `5957.0200%`，最大回撤 `-31.0767%`，Sharpe `1.3094`，总滑点 `1,556,750`，总交易次数 `757`。
- 现金对照 `95%C3+5%现金`：期末权益 `25,516,398.54`，总收益 `5003.2797%`，最大回撤 `-29.7155%`，Sharpe `1.3094`，Ulcer `15.4303`。
- Stage071连续权重纸面组合：期末权益 `25,630,990.88`，总收益 `5026.1982%`，最大回撤 `-29.7079%`，Sharpe `1.3109`，Ulcer `15.4141`。
- 主口径 `95%C3+5%真实ETF整手`：期末权益 `25,544,613.93`，总收益 `5008.9228%`，最大回撤 `-29.7121%`，Sharpe `1.3098`，Ulcer `15.4229`，日收益正率 `25.6388%`。
- ETF独立腿主口径：期末权益 `25,611.10`，总收益 `2.4444%`，最大回撤 `-6.6905%`，总换手 `1,200,408.30`，费用 `2,915.00`，成交 `583`。
- 无最低佣金ETF独立腿：总收益 `7.5217%`；5元最低佣金把ETF独立腿收益压到 `1.9534%` 到 `2.4444%` 区间。
- 承载情况：目标事件 `881`，实际可买整手事件 `881`，未成交/买不到一手事件 `0`。

## 多窗口现金对照

- `full_common`：真实ETF组合 `5008.9228%/-29.7121%`，略优于现金 `5003.2797%/-29.7155%`。
- `start_2021`：真实ETF组合 `3973.3605%/-29.7121%`，低于现金 `3976.9428%/-29.7155%`。
- `start_2022`：真实ETF组合 `1470.6916%/-29.0421%`，低于现金 `1472.7113%/-29.0421%`。
- `start_2023`：真实ETF组合 `671.4605%/-18.3648%`，低于现金 `672.3086%/-18.3795%`。
- `start_2024`：真实ETF组合 `276.7222%/-18.3648%`，低于现金 `277.1150%/-18.3795%`。
- `ytd_2026`：真实ETF组合 `7.5419%/-10.8236%`，低于现金 `7.5582%/-10.8277%`，且 Ulcer 略差。

## 决策

- 决策：`fail_etf_realistic_lot_not_robust_vs_cash_windows`
- 原因：
  - 真实整手口径全周期只比现金对照多约 `5.64` 个百分点总收益，优势极小。
  - 多个核心起点窗口收益低于同权重现金，说明优势主要来自早期样本，不能证明可推广。
  - 5元最低佣金对25,000元ETF腿影响很大，费用占初始ETF腿 `11.66%`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage372_etf_realistic_lot_audit_report_stage372_etf_realistic_lot_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage372_etf_realistic_lot_audit_summary_stage372_etf_realistic_lot_audit_v1.csv`
- window_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage372_etf_realistic_lot_audit_window_summary_stage372_etf_realistic_lot_audit_v1.csv`
- annual_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage372_etf_realistic_lot_audit_annual_summary_stage372_etf_realistic_lot_audit_v1.csv`
- execution_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage372_etf_realistic_lot_audit_execution_summary_stage372_etf_realistic_lot_audit_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage372_etf_realistic_lot_audit_daily_stage372_etf_realistic_lot_audit_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage372_etf_realistic_lot_audit_trades_stage372_etf_realistic_lot_audit_v1.csv`
- HTML：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage372_etf_realistic_lot_audit_equity_drawdown_stage372_etf_realistic_lot_audit_v1.html`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage372_etf_realistic_lot_audit_decision_stage372_etf_realistic_lot_audit_v1.json`

## 结论

- Stage071 ETF小资金承载候选不能升级为当前正式路线。
- ETF腿技术上能按25,000元和100份整手承载，不存在股票腿那种大量买不到一手问题；但经济上不够强，真实最低佣金和多起点现金对照后，优势不足以支撑“不过拟合”的升级。
- 当前目标仍未完成；最低过拟合可执行边界仍是 Stage055/067 的正常成本部署层现金方案，或者继续寻找新的独立收益源/新承载结构。

## 过拟合反思

- 运行前判断：不是过拟合。只复核真实交易单位、费用和现金约束，没有新增收益参数。
- 运行后判断：不把该ETF候选升级，正是为了避免过拟合。全周期略赢现金但多起点输现金，继续扫ETF权重、单一ETF或Connors参数会转为过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage071只有边际优势，必须确认真实承载。
- 运行后判断：当前ETF小腿路线继续价值低；总目标仍有价值。
- 下一步：停止当前ETF `5%` 小腿救援；若继续跨资产承载，只能寻找更强且费用敏感度低的独立收益源，或重新评估 `30万+` 独立股票账户组合层方案；否则回到正常成本下 `50万C3下单+11.5万外部现金` 部署边界。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为ETF小腿真实性复核反证。
