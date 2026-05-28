# Stage140 - 非机械目标口径晋级裁决

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 03:20 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读晋级裁决；承接用户“如果值得晋级，可以不按目标来”的判断要求。
- 是否重要突破：是。突破不是新收益，而是把当前候选的执行优先级正式裁清。
- 是否触发A/B：是，属于候选晋级判断；本阶段没有新增回测，只复用 Stage138/139 固定审计输出。

## 外部调研与判断

- 参考资料：
  - Bailey、Lopez de Prado，《The Deflated Sharpe Ratio》：https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
  - Bailey、Borwein、Lopez de Prado、Zhu，《The Probability of Backtest Overfitting》：https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
  - Lopez de Prado，《A Data Science Solution to the Multiple-Testing Crisis in Financial Research》：https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3299597_code434076.pdf?abstractid=3177057
- 我的判断：多候选研究后，晋级不应该等同于“全样本最高分”或“刚好补齐某个短持有指标”。更可靠的候选应满足低自由度、整数手可执行、保证金路径干净、成本压力不脆弱、贡献不过度集中、且失败项不是靠继续救参才能解释。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 修改正式策略：无。

## 回测/归因参数

- 数据区间：沿用 Stage138/139 全周期 `2020-2026` 与任意启动/多起点/年度/季度/滚动窗口审计。
- 账户规模：Stage079 baseline 为 `50万C3下单 + 11.5万外部现金`，总资金 `61.5万`。
- 成本口径：正常成本 `1x`，并参考 Stage138/139 中已完成的 `2x/3x/5x` 成本压力与 broker10 保证金审计。
- 样本过滤：无新增过滤。
- 策略/归因口径：
  - A：Stage079 baseline。
  - C1：Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`。
  - C2：Stage115 `stage103_plus_cffex_index_best1_tsmom60_guard`，仅 paper。
  - C3：Stage136 `stage103_plus_low_skew252_best1_vt10_mom63_round_half_guard`，仅 paper。

## 结果

| 版本 | 裁决 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 总滑点 | 总交易次数 | 非零日胜率 | 3个月分 | 6个月分 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | baseline | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 1,556,750 | 757 | 48.3478% | 100.0000 | 100.0000 |
| Stage103 | 主执行相对候选，晋级 | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 1,569,265 | 1,217 | 50.3432% | 121.2041 | 134.4513 |
| Stage115 | 高分 paper，不主晋级 | 33,607,695 | 5364.6659% | -23.5184% | 1.4810 | 12.0786 | 1,594,705 | 1,719 | 53.8102% | 183.4601 | 210.3930 |
| Stage136 | paper/体验观察，不主晋级 | 32,120,290 | 5122.8114% | -27.5906% | 1.3918 | 13.9133 | 1,576,215 | 1,469 | 50.7671% | 141.2265 | 144.5203 |

其他关键指标：

- Stage103 严格完整目标仍未全过：3个月失败 `return_p05/return_median/positive_rate/below_5_rate/dd20_rate/ulcer_p95/uw_p95`，6个月失败 `return_p05/positive_rate/below_5_rate/dd20_rate/ulcer_p95/uw_p95`。
- Stage103 仍值得晋级，因为它相对 Stage079 同时改善总收益、最大回撤、Sharpe、Ulcer、3/6个月综合分，且 Stage138/139 没有发现必须降级的贡献集中、保证金或成本压力缺陷。
- Stage115 分数最高，但相对 Stage103 的 `90/180/252/504` 日收益胜率只有 `46.0153%/41.3890%/38.4653%/33.5916%`，剔除最大 `1` 个相对贡献日后收益差转为 `-13.4058pp`，且绝对 broker10 仍需额外现金约 `7,137.64`，因此只能 paper。
- Stage136 通过 Stage079 原始目标，但相对 Stage103 的 `90/180/252/504` 日收益胜率只有 `34.3539%/28.2966%/27.3919%/34.4217%`，剔除最大 `1` 个相对贡献日后收益差 `-55.0864pp`，留一年度最差相对 Stage079 收益差 `-262.4845pp`，因此只能 paper。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_report_stage438_independent_promotion_dashboard_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_summary_stage438_independent_promotion_dashboard_v1.csv`
- gap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage439_active_goal_gap_audit_gap_stage439_active_goal_gap_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_decision_stage438_independent_promotion_dashboard_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage438_independent_promotion_dashboard_chart_stage438_independent_promotion_dashboard_v1.png`

## 结论

- 本阶段结论：我判断 Stage103 值得晋级为当前主执行相对候选，即使它没有满足所有严格 3个月/6个月目标。这个晋级是工程/影子盘/执行候选晋级，不是替代 Stage079 baseline，也不是宣称完整目标已经完成。
- 是否进入下一步：是。
- 下一步：
  - 固定 Stage103 做工程化复跑、paper/影子盘、真实券商保证金和订单级对账。
  - Stage115 作为高分 paper 对照，不进入主候选。
  - Stage136 作为体验 paper 观察，不进入主候选。
  - 继续主动研究时，只允许全新低自由度风险源；不救 Stage115、Stage136、OI/value 或连续失败信号的小参数。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段是晋级裁决，不新增规则、不调参数。
- 运行后判断：不是过拟合。反而是把高分但脆弱的 Stage115/136 降级，避免被漂亮曲线诱导。
- 原因：晋级依据来自多周期、任意启动、贡献剔除、成本、保证金和后续降级审计，而不是某个单窗口表现。

## 继续价值反思

- 运行前判断：继续有价值，但价值不在救旧参数，而在执行验证或新风险源。
- 运行后判断：继续有价值。
- 原因：完整严格目标尚未完成；Stage103 已足够进入影子盘/执行验证，同时还可保留极少量新风险源探索。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage140 裁决。
- 是否更新 `research/registry.md`：是，这是正式候选层级变化摘要。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；暂不追加 `memory.md`。
