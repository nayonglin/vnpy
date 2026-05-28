# Stage114 独立晋级判断审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 22:15 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：决策审计；不新增交易规则，不按原理想目标硬凑结论，而是判断哪些版本值得进入下一层流程。
- 是否重要突破：是，明确 Stage103 可晋级到工程化复跑 / paper影子盘，但仍不能升为正式替代或绝对部署版本。
- 是否触发A/B：否，本阶段整合既有 A/B 审计输出，不产生新交易版本。

## 外部调研与判断

- 参考资料：
  - walk-forward / rolling window 资料与 GitHub 实现：强调不要用单条全周期权益曲线证明策略，应看任意启动、滚动窗口和样本扰动。
  - 2026年5月国内货币基金收益资料：现金管理收益接近 1% 附近，2% 不应作为默认可得假设。
- 我的判断：如果不强行追求所有 3/6 个月理想项，Stage103 已经值得晋级到工程化复跑和 paper 影子盘；但它的收益端任意窗口胜率不足，不能直接宣布正式替代 Stage079。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage414_independent_promotion_judgement.py`
- 修改脚本：无策略脚本修改。
- 删除脚本：无
- 新增参数：
  - 晋级对象：Stage103、Stage103+现金年化1.2%、Stage103+现金年化2%、Stage103+5万股票整手+6.5万现金年化2%
  - 任意启动滚动窗口：`63/90/126/180/252/504` 自然日
  - 晋级层级：`promote_engineering_paper`、`operational_overlay`、`paper_cash_assumption`、`paper_only_reject_deployment`
- 修改参数：无交易参数修改。
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：61.5万
- 成本口径：复用 Stage403 / Stage411 / Stage412 / Stage413 的统一成本和保证金输出。
- 样本过滤：全周期公共样本；任意启动滚动窗口。
- 策略/归因口径：只读整合既有候选，不改变 C3、xsmom、股票策略或现金收益假设。

## 结果

- Stage103：总收益 `5059.4984%`，最大回撤 `-28.9792%`，Sharpe `1.3681`，Ulcer `14.3132`，3个月/6个月体验分 `121.2041/134.4513`，晋级分 `82`。
- Stage103 + 现金年化1.2%：总收益 `5060.9647%`，最大回撤 `-28.9426%`，Sharpe `1.3692`，Ulcer `14.2878`，3个月/6个月体验分 `121.9939/134.8679`，晋级分 `78`，只作为执行细节。
- Stage103 + 现金年化2%：总收益 `5061.9951%`，最大回撤 `-28.9181%`，Sharpe `1.3700`，Ulcer `14.2707`，3个月/6个月体验分 `122.5050/134.9949`，晋级分 `70`，只作 paper 假设，不作为现实默认。
- Stage103 + 5万股票整手 + 6.5万现金年化2%：总收益 `5061.9549%`，最大回撤 `-28.9631%`，Sharpe `1.3695`，Ulcer `14.2690`，3个月/6个月体验分 `122.2976/135.9356`，晋级分 `55`，paper 保留，拒绝部署。
- 任意启动收益胜率相对 Stage079：
  - Stage103：90/180/252日为 `42.8443%/44.3715%/43.6408%`。
  - 现金1.2%：90/180/252日为 `49.8200%/47.7017%/43.4951%`。
  - 股票槽位：90/180/252日为 `49.9100%/47.6079%/43.7379%`。
- 风险体验：Stage103 的 90/180日 Ulcer 不劣化率为 `91.7642%/96.7636%`；现金1.2%为 `92.2142%/97.4203%`；风险优势稳定，但收益胜率不是压倒性。
- Stage409 样本扰动：Stage103 block bootstrap 收益胜率约 `55.2%`，不是绝对收益优势。
- Stage112 流动性：股票槽位在 `1.10x` 流动期货权益口径有 `3` 天穿线，需额外约 `60,353.82` 现金。
- 总滑点/总交易次数/胜率：Stage114 未新增交易，不重新计算成交级胜率；Stage103 沿用 Stage403/109 口径，总滑点约 `1,569,265`，总交易次数约 `1217`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage414_independent_promotion_judgement_report_stage414_independent_promotion_judgement_v1.md`
- matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage414_independent_promotion_judgement_matrix_stage414_independent_promotion_judgement_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage414_independent_promotion_judgement_rolling_pairwise_stage414_independent_promotion_judgement_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage414_independent_promotion_judgement_decision_stage414_independent_promotion_judgement_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage414_independent_promotion_judgement_chart_stage414_independent_promotion_judgement_v1.png`

## 结论

- 本阶段结论：`promote_stage103_to_engineering_paper_not_absolute_deployment`。
- 是否进入下一步：是，但只进入工程化复跑 / paper影子盘 / 真实券商保证金接入。
- 下一步：固定 Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`，不再调 `0.5/10%/63日/broker10`；现金1.2%作为可选现金管理细节；股票槽位只保留 paper；若继续追理想 3/6 个月目标，必须另找真正不同的收益源。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：本阶段没有新增规则或小参数，只把既有审计结果用更严格的晋级层级归档；同时明确不把 2% 现金和股票槽位当现实部署假设。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但方向改变。
- 原因：继续救 Stage103 小参数或现金收益率价值低；Stage103 工程化和真实保证金验证有价值，理想短持有体验若继续追，需要新收益源。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是
