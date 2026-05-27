# Stage078 Stage075组合多起点与滚动窗口审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 02:30 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读稳健性审计；不修改78-1、C3、股票账户参数或组合权重
- 是否重要突破：否。该阶段确认组合候选仍为黄灯paper对象，不能正式晋级
- 是否触发A/B：否。按 A/B skill，本阶段是 monitor/audit，不是新增策略版本或正式合入候选

## 外部调研与判断

- 参考资料：
  - GitHub walk-forward-analysis 主题和相关实现强调应检查多起点/滚动窗口，而非只看单条全周期曲线。
  - QuantStats GitHub 组合分析工具包含滚动收益、回撤、风险指标等组合绩效审计思路。
  - Walk-forward/forward testing 的核心是固定规则后持续观察，而不是用弱窗口反向调参。
- 我的判断：
  - Stage075/077 已经证明全周期相对78-1更平滑，但还需要季度冷启动和滚动窗口审计。
  - 本阶段如果发现相对现金不稳，只能限制候选状态，不能调股票权重或股票参数救窗口。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage378_stage075_combo_multistart_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；只新增审计闸门
  - 年度/季度冷启动最短样本：`252` 日
  - 回撤硬闸门：组合最大回撤 `>= -30%`
  - 相对现金回撤容忍：`-0.75pp`
  - 252/504 日滚动窗口审计
- 修改参数：无
- 删除参数：无

## 回测/审计参数

- 数据来源：Stage377 daily monitor 固定曲线
- 样本区间：`2020-01-02` 至 `2026-04-27`
- 账户口径：`50万C3 + 30万股票账户`，总资金 `80万`
- 对照：
  - `50万C3 + 30万现金`
  - `78-1 + 30万现金`
  - `50万C3期货账户`
- 成本口径：不新增成交回测，沿用上游既有曲线成本
- 交易逻辑：无新增交易逻辑；只重切既有净值

## 结果

- 组合全周期期末权益：约 `30,193,682.12`
- 组合全周期总收益：`3674.2103%`
- 组合全周期最大回撤：`-28.0463%`
- 组合全周期 Sharpe：沿用 Stage077 `1.3187`
- 组合全周期 Ulcer：`13.5280`
- 总滑点：无新增回测，沿用上游既有曲线
- 总交易次数：无新增回测，沿用上游既有曲线
- 胜率：无新增回测，沿用上游既有曲线

## 多起点与滚动窗口审计

- 审计状态：`yellow`
- 红灯原因：无
- 黄灯原因：
  - 季度冷启动相对现金/78-1综合闸门通过率不足75%
  - 252日滚动窗口相对现金曾落后超过5pp
  - 252日滚动窗口存在负收益，但504日窗口仍为正
  - 年度冷启动相对现金收益通过率不足80%
- 年度冷启动：
  - 符合样本：`6`
  - 回撤30以内通过率：`100.00%`
  - 综合通过率：`16.67%`
- 季度冷启动：
  - 符合样本：`23`
  - 回撤30以内通过率：`100.00%`
  - 综合通过率：`4.35%`
- 252日滚动：
  - 窗口数：`2057`
  - 最差收益：`-13.2918%`
  - 最差相对现金：`-7.2739pp`
- 504日滚动：
  - 窗口数：`1805`
  - 最差收益：`24.7959%`
  - 最差相对现金：`-10.4926pp`

## 关键解释

- 该组合确实显著平滑78-1：年度和季度冷启动的组合最大回撤全部进入 `30%` 以内，且多数窗口相对78-1回撤和Ulcer都有改善。
- 该组合不能证明股票腿稳定优于现金：年度冷启动只有 `1/6` 综合通过，季度冷启动只有 `1/23` 综合通过。
- 这意味着 Stage075 更接近“用独立股票账户改善路径体验”的 paper 候选，不是可以直接替代78-1或C3的正式策略版本。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage378_stage075_combo_multistart_audit_report_stage378_stage075_combo_multistart_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage378_stage075_combo_multistart_audit_decision_stage378_stage075_combo_multistart_audit_v1.json`
- annual_start：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage378_stage075_combo_multistart_audit_annual_start_stage378_stage075_combo_multistart_audit_v1.csv`
- quarter_start：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage378_stage075_combo_multistart_audit_quarter_start_stage378_stage075_combo_multistart_audit_v1.csv`
- rolling_paired：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage378_stage075_combo_multistart_audit_rolling_paired_stage378_stage075_combo_multistart_audit_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage378_stage075_combo_multistart_audit_aggregate_stage378_stage075_combo_multistart_audit_v1.csv`
- html：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage378_stage075_combo_multistart_audit_dashboard_stage378_stage075_combo_multistart_audit_v1.html`

## 结论

- 本阶段结论：Stage075组合可以继续作为黄灯forward paper对象；不能正式晋级，也不能认为股票腿稳定打败现金。
- 是否进入下一步：是，但只能是只读paper和对账，不允许参数救援。
- 下一步：
  - 继续日更 Stage077/078 paper 监控。
  - 对相对现金落后的季度/252日窗口做只读归因。
  - 若要继续追求正式候选，需要寻找更强独立收益源或更低费用敏感度承载工具，而不是调股票权重。

## 过拟合反思

- 运行前判断：不是过拟合。只重切固定曲线，不修改规则。
- 运行后判断：不是过拟合。结果暴露了相对现金不稳这一弱点，没有据此调参。
- 原因：本阶段没有新增可搜索交易参数，没有挑选窗口合入，只把全样本候选放到多起点下验真。

## 继续价值反思

- 运行前判断：有价值。用户目标包含“曲线更平滑”，多起点审计是必要验证。
- 运行后判断：仍有价值，但价值变窄。
- 原因：组合在最大回撤和平滑度上非常稳定地优于78-1，但相对现金收益不稳，所以只适合作为paper观察对象，而不是正式策略版本。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或路线废弃，只是候选状态约束。
