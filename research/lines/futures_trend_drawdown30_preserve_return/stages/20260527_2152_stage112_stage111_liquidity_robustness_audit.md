# Stage112 Stage111 流动性与鲁棒性审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 21:52 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读反证/降级审计；不修改 Stage079、Stage103、股票策略参数或股票池。
- 是否重要突破：否；但这是重要纠偏，避免把 Stage111 错升部署候选。
- 是否触发A/B：是。A 为 Stage079，C0 为 Stage103，C1 为 Stage111 修正后最强候选 `Stage103 + 5万股票整手 + 6.5万现金年化2%`。

## 外部调研与判断

- 参考资料：
  - walk-forward analysis / rolling validation：单一路径全周期胜出不足以证明策略稳健。
  - block bootstrap robustness：对交易策略应检查块重采样下收益、回撤和 Ulcer 是否仍稳定。
  - GitHub walk-forward/backtesting 相关实现：通用做法是将候选放到多窗口和重采样路径下检验，而不是只看总收益。
- 我的判断：
  - Stage111 边际改善很小，必须用 rolling window 和 bootstrap 验证“任何时候启动”的体验是否真的改善。
  - 股票槽位替换现金槽位后，股票市值不能默认作为期货账户可用保证金，因此必须单独做流动性口径审计。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage412_stage111_liquidity_robustness_audit.py`
- 修改脚本：同步修正 Stage411 股票公共起点归一化，避免隐含带入 2018-2020 股票历史收益。
- 删除脚本：无。
- 新增参数：
  - rolling 窗口：`21/63/90/126/180/252/504` 自然日。
  - block bootstrap 块长：`20/60/120` 日，各 `2000` 次。
  - 流动性保证金倍率：`1.00/1.02/1.05/1.10`。
  - 顶部相对贡献日剔除：`0/1/3/5/10/20/40/80/120` 日。
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 账户规模：总账户 `615,000` 元，不增加资金占用。
- 成本口径：沿用 Stage411 / Stage403 成本；流动性审计使用 Stage352 C3 保证金和 Stage403 xsmom 卫星保证金。
- 样本过滤：`start_2020` 公共样本；股票腿按公共起点重新归一化。
- 策略/归因口径：只审计 Stage111 修正后最强候选 `stage103_stock_lot_50000_cash_65000_yield2`。

## 结果

- Stage111 修正后最强候选：
  - 期末权益：`31,746,022.93`
  - 总收益：`5061.9549%`
  - 最大回撤：`-28.9631%`
  - Sharpe：`1.3695`
  - Ulcer：`14.2690`
  - 3个月/6个月体验分：`122.2976 / 135.9356`
- 相对 Stage103 的 rolling 任意启动胜率：
  - 90日收益胜率：`48.3566%`
  - 180日收益胜率：`40.7321%`
  - 252日收益胜率：`40.5537%`
  - 504日收益胜率：`30.6032%`
  - 90日最大回撤不劣化率：`91.2652%`
  - 180日最大回撤不劣化率：`96.3867%`
  - 90日 Ulcer 不劣化率：`93.4714%`
  - 180日 Ulcer 不劣化率：`93.5711%`
- 相对 Stage079 的 rolling 任意启动胜率：
  - 90日收益胜率：`50.1126%`
  - 180日收益胜率：`47.5364%`
  - 252日收益胜率：`43.7105%`
  - 504日收益胜率：`32.1527%`
- block bootstrap 相对 Stage103：
  - 20日块收益胜率：`53.75%`
  - 60日块收益胜率：`57.15%`
  - 120日块收益胜率：`48.30%`
  - 60日块收益差中位数：`+2.9771pp`
  - 60日块收益差5%分位：`-168.5125pp`
- 流动性保证金审计：
  - 正常 `1.00x`：扣除 5万股票不可用保证金后，最大保证金/流动期货权益 `95.2562%`，无拒单。
  - `1.05x`：最大保证金/流动期货权益 `100.0190%`，出现 `1` 天流动性穿线，额外现金需求 `95.83` 元。
  - `1.10x`：最大保证金/流动期货权益 `104.7818%`，出现 `3` 天流动性穿线，额外现金需求 `60,353.82` 元。
  - 对照 Stage103 `1.10x` 已有 `1` 天穿线、额外现金 `13,665.70` 元；Stage111 股票槽位显著放大了保证金可用性问题。
- 顶部相对贡献日剔除：
  - 不剔除时，Stage111 相对 Stage103 收益只高 `+2.4591pp`。
  - 剔除最大 `1` 个相对贡献日后，Stage111 已低于 Stage103 `-10.8755pp`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage412_stage111_liquidity_robustness_audit_report_stage412_stage111_liquidity_robustness_audit_v1.md`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage412_stage111_liquidity_robustness_audit_rolling_stage412_stage111_liquidity_robustness_audit_v1.csv`
- pairwise：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage412_stage111_liquidity_robustness_audit_pairwise_stage412_stage111_liquidity_robustness_audit_v1.csv`
- bootstrap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage412_stage111_liquidity_robustness_audit_block_bootstrap_stage412_stage111_liquidity_robustness_audit_v1.csv`
- liquidity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage412_stage111_liquidity_robustness_audit_liquidity_margin_stage412_stage111_liquidity_robustness_audit_v1.csv`
- topday：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage412_stage111_liquidity_robustness_audit_top_edge_day_ablation_stage412_stage111_liquidity_robustness_audit_v1.csv`
- yearly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage412_stage111_liquidity_robustness_audit_yearly_stage412_stage111_liquidity_robustness_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage412_stage111_liquidity_robustness_audit_decision_stage412_stage111_liquidity_robustness_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage412_stage111_liquidity_robustness_audit_chart_stage412_stage111_liquidity_robustness_audit_v1.png`

## 结论

- 本阶段结论：Stage111 修正后保留为 paper/研究候选，但拒绝部署晋级。
- 是否进入下一步：不进入正式部署；可保留为组合层 paper 观察。
- 下一步：
  - Stage103 仍是主执行相对候选。
  - 若要低风险增强，`Stage103 + 11.5万现金年化2%` 比股票槽位更干净。
  - 不再围绕股票槽位 `2.5/5/10万` 附近小数、现金收益率或股票策略参数继续救援。
  - 若继续追目标，需要新低相关收益源，且必须先满足流动性保证金口径。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合；这次是对既有候选做反证，发现公共起点和流动性边界。
- 原因：没有新增交易规则，也没有调参数；rolling、bootstrap、贡献日剔除和流动性审计都在拆解稳健性。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：Stage111 子路线继续主动优化价值低；总目标仍有价值。
- 原因：Stage111 相对 Stage103 的收益优势太薄，任意启动收益胜率不足，而且使用股票槽位会削弱期货保证金可用性。

## 合入建议

- 是否更新本线 `LINE.md`：是，Stage111 降为 paper/研究候选。
- 是否更新 `research/registry.md`：是，最新关键阶段更新到 Stage112。
- 是否追加根目录 `memory.md/back_log.md`：是，记录公共起点修正和部署晋级拒绝。
