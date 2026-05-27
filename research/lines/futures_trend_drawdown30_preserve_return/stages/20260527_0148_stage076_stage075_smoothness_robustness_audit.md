# Stage076 Stage075平滑度与弱窗口审计

- 研究线：`futures_trend_drawdown30_preserve_return`
- 时间：2026-05-27 01:48 CST
- 基准版本：`official_stage78_1_defensive_50w_no_sizing_cap`
- 阶段性质：只读审计；不修改78-1、C3或股票账户参数。
- 是否重要突破：否，但确认 Stage075 是组合层 forward paper 候选。

## 开始前反思

- 是否过拟合：否。
- 原因：本阶段只比较既有曲线，指标预先固定为最大回撤、Ulcer、最长水下期、滚动一年/两年收益、现金对照和2024弱窗口归因，没有调权重、阈值或股票版本。
- 是否有价值继续：是。
- 原因：Stage075 已经显示 `50万C3+30万股票账户` 优于同资金现金对照，但需要确认它是否真比78-1平滑，以及是否只是现金稀释。

## 外部调研结论

- 平滑度不能只看单点最大回撤，还要看回撤深度和持续时间。Ulcer Index 的核心用途就是衡量回撤深度与持续时间，因此本阶段加入 Ulcer、最长水下期、滚动252/504日收益。
- 组合层候选必须与同资金现金对照比较，否则很容易把“多放现金导致的稀释”误判成有效低相关收益源。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage376_stage075_smoothness_robustness_audit.py`
- 新增输出：
  - `qmt_roll_stage376_stage075_smoothness_robustness_audit_summary_stage376_stage075_smoothness_robustness_audit_v1.csv`
  - `qmt_roll_stage376_stage075_smoothness_robustness_audit_annual_stage376_stage075_smoothness_robustness_audit_v1.csv`
  - `qmt_roll_stage376_stage075_smoothness_robustness_audit_relative_stage376_stage075_smoothness_robustness_audit_v1.csv`
  - `qmt_roll_stage376_stage075_smoothness_robustness_audit_tail_stage376_stage075_smoothness_robustness_audit_v1.json`
  - `qmt_roll_stage376_stage075_smoothness_robustness_audit_weak_2024_stage376_stage075_smoothness_robustness_audit_v1.csv`
  - `qmt_roll_stage376_stage075_smoothness_robustness_audit_decision_stage376_stage075_smoothness_robustness_audit_v1.json`
  - `qmt_roll_stage376_stage075_smoothness_robustness_audit_report_stage376_stage075_smoothness_robustness_audit_v1.md`
  - `qmt_roll_stage376_stage075_smoothness_robustness_audit_curves_stage376_stage075_smoothness_robustness_audit_v1.html`
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 核心结果

公共样本区间：`2020-01-02` 至 `2026-04-27`。

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 最长水下 | 最差252日收益 | 最差504日收益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 78-1正式基准50万 | 25,309,885.00 | 4961.9770% | -40.1659% | 1.1559 | 20.7931 | 403天 | -35.5420% | -7.2903% |
| C3期货账户50万 | 29,691,800.00 | 5838.3600% | -31.0767% | 1.3044 | 16.2075 | 369天 | -18.6645% | 28.7784% |
| 50万C3 + 30万现金 | 29,991,800.00 | 3648.9750% | -28.6217% | 1.3051 | 13.8887 | 369天 | -14.9384% | 27.6498% |
| 50万C3 + 30万股票账户 | 30,193,682.12 | 3674.2103% | -28.0463% | 1.3187 | 13.5280 | 369天 | -14.2593% | 28.5960% |
| 30万股票整手账户 | 501,882.12 | 67.2940% | -12.3781% | 0.6454 | 3.9827 | 427天 | -8.5525% | -6.1459% |

补充口径：

- C3期货腿总滑点沿用 Stage075/Stage359 口径：`1,556,750`。
- C3期货腿总交易次数：`757`。
- C3期货腿胜率：`45.3826%`。
- Stage076本身是只读审计，没有新增真实委托、成交或胜率。

## 相对改善

- 相对78-1，Stage075组合收益低 `1287.7667pp`，但最大回撤改善 `12.1196pp`，Ulcer 改善 `34.94%`，最差252日收益改善 `21.2827pp`，最差504日收益改善 `35.8863pp`。
- 相对单独C3，Stage075组合最大回撤改善 `3.0304pp`，Ulcer 改善 `16.5322%`，但总收益低 `2164.1497pp`。
- 相对 `50万C3+30万现金`，Stage075组合总收益高 `25.2353pp`，最大回撤改善 `0.5755pp`，Ulcer 改善 `2.5973%`。

## C3与股票腿左尾关系

- C3与股票腿日收益相关系数：`0.0106`。
- C3最差5%交易日里，股票腿平均日收益：`-0.000161`。
- C3最差5%交易日里，股票腿上涨比例：`50.8621%`。

判断：股票腿不是强负相关对冲，但接近低相关；它对平滑度的贡献小幅优于现金，不是强alpha级别的保护腿。

## 2024弱窗口归因

- Stage075组合最大回撤窗口：`2024-04-02` 至 `2024-08-27`，回撤 `-15.3097%`。
- 现金对照最大回撤：`-13.8783%`。
- 组合相对现金回撤差：`-1.4314pp`。
- 同一窗口中，C3期货腿亏损 `-142,537`，股票腿亏损 `-24,290.8`；股票腿没有对冲，反而叠加亏损，这是 start_2024 不完全通过的原因。

## 决策

- 决策：`stage075_combo_smoother_than_78_but_forward_paper_required`
- 结论：Stage075 相对78-1明显更平滑，也小幅优于同资金现金对照；但它牺牲了大量C3收益，且2024弱窗口中股票腿和C3同亏，因此只能进入组合层 forward paper，不能直接晋级正式实盘。
- `strategy_change_allowed=false`：本阶段不允许把股票账户组合写入78-1正式策略。

## 结束后反思

- 是否过拟合：否。
- 原因：审计发现2024窗口仍有缺口，但没有据此调股票权重或改股票规则；只把候选限制为 forward paper。
- 是否有价值继续：是。
- 原因：Stage075已经满足“明显比78-1平滑”的观察标准，并且略优于现金对照；下一步价值在真实执行和OOS监控，而不是继续扫参数。

## 后续规划和TODO

- 不升级正式策略；先做组合层 forward paper。
- 对2024弱窗口继续只读归因，不做股票权重或参数救援。
- 后续每日paper需要同时输出 C3、股票腿、现金对照、组合层权益和回撤。
- 若 forward paper 持续优于现金对照，再进入实盘前双账户部署评估。
