# Stage065 平滑度前沿横向审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-26 20:51 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：既有候选权益曲线横向审计；不新增交易规则
- 是否重要突破：否，但修正目标解释
- 是否触发A/B：否。本阶段只审计已有 A/C/B 候选路径，不创建新策略候选。

## 外部调研与判断

- 参考资料：
  - Ulcer Index 口径：同时衡量回撤深度和持续时间，比单一最大回撤更贴近持有痛感。
  - Calmar 口径：用年化收益除以最大回撤，适合辅助判断收益是否足够补偿回撤。
- 我的判断：
  - 用户新增目标包含“全周期曲线更平滑”和“两年几乎没增长”，不能只看最大回撤。
  - 本阶段采用最大回撤、Ulcer Index、最长水下交易日、最差 504 日滚动收益和 504 日非正收益占比一起审计。
  - 审计指标只用于排序和归因，不允许把净值层或已反证候选直接晋级。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage365_smoothness_frontier_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 硬回撤目标：`-30%`
  - 严格收益保留：相对 C3 `80%+`
  - 可研究收益保留：相对 C3 `65%+`
  - 平滑度指标：Ulcer Index 降低 `10%+` 或最长水下交易日降低 `10%+`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：读取各候选既有 `2020-01-01` 至 `2026-04-30` 日权益曲线。
- 账户规模：按各候选既有口径；C3与净值层候选为 `500,000`，xsmom overlay 为 `530,000`，部署现金边界为 `615,000`。
- 成本口径：沿用各阶段既有曲线成本，不重新计算成交。
- 样本过滤：只纳入已有代表性候选：
  - 正式78-1：`A_official78_1_50w`
  - 当前研究基准：`B_c3_current_50w`
  - 部署边界：`D_c3_50w_plus_115k_external_cash`
  - xsmom 净值层/overlay、Carry、季节性、同源时间尺度分散候选
- 策略/归因口径：只做横向路径质量审计。

## 结果

- 正式78-1：
  - 总收益：`5170.7870%`
  - 最大回撤：`-40.1659%`
  - Ulcer Index：`20.8635%`
  - 最长水下交易日：`268`
  - 最差 504 日滚动收益：`38.9409%`
  - Sharpe：`1.4316`
- 当前 C3 研究基准：
  - 总收益：`6085.1300%`
  - 最大回撤：`-31.0767%`
  - Ulcer Index：`16.2653%`
  - 最长水下交易日：`242`
  - 最差 504 日滚动收益：`95.6774%`
  - Sharpe：`1.6164`
- 全样本严格通过但需拆状态的候选：
  - `R_xsmom_overlay_3w_cash`：总收益 `5904.7019%`，收益保留 `97.0349%`，最大回撤 `-29.8729%`，Ulcer `14.7401%`，但 Stage052 已因多周期/滑点压力反证。
  - `D_c3_50w_plus_115k_external_cash`：总收益 `4947.2602%`，收益保留 `81.3008%`，最大回撤 `-29.7007%`，Ulcer `15.1510%`；这是部署层正常成本边界，不是策略 alpha 改善。
  - `c3_92p5_xsmom_mom_12m_skip1m_7p5_cost20bps`：总收益 `4880.7988%`，收益保留 `80.2086%`，最大回撤 `-29.5427%`，Ulcer `14.8948%`，但 Stage046 已显示 3.75万期货腿不可直接承载。
  - `c3_95_xsmom_mom_6m_skip1m_5_cost20bps`：总收益 `5097.8011%`，收益保留 `83.7747%`，最大回撤 `-29.9390%`，Ulcer `15.4135%`；同属净值层动量，不可直接晋级。
  - `T_timescale_base80_slow20`：总收益 `4889.0285%`，收益保留 `80.3439%`，最大回撤 `-29.8115%`，Ulcer `15.4646%`，但 Stage056 已多窗口反证。
- 更平滑但收益下降的候选：
  - `c3_90_carry_10_cost20bps`：总收益 `4123.5917%`，收益保留 `67.7651%`，最大回撤 `-28.4959%`，Ulcer `14.5897%`。它确实比 C3 更平滑，但 Carry 独立腿已反证，组合主要靠稀释，不是可晋级收益源。
- 关于“两年几乎没增长”：
  - 正式78-1 最差 504 日滚动收益为 `38.9409%`。
  - C3 最差 504 日滚动收益为 `95.6774%`。
  - 本次纳入候选的 504 日滚动收益非正占比均为 `0%`。
  - 因此，从当前日权益口径看，不支持“C3 有两年不增长”的判断；更像是主观体感来自阶段性回撤/横盘，而不是完整 504 交易日非正收益。
- 决策：`smoothness_candidates_found_but_require_status_split`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage365_smoothness_frontier_audit_report_stage365_smoothness_frontier_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage365_smoothness_frontier_audit_summary_stage365_smoothness_frontier_audit_v1.csv`
- annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage365_smoothness_frontier_audit_annual_returns_stage365_smoothness_frontier_audit_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage365_smoothness_frontier_audit_rolling_windows_stage365_smoothness_frontier_audit_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage365_smoothness_frontier_audit_curves_stage365_smoothness_frontier_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage365_smoothness_frontier_audit_decision_stage365_smoothness_frontier_audit_v1.json`

## 结论

- 本阶段结论：相对正式78-1，C3 已经显著改善路径质量；相对 C3，确实存在全样本更平滑的候选，但可直接部署/可晋级状态不同。
- 当前最稳妥可执行边界仍是 `50万C3下单 + 11.5万外部现金`，正常成本下满足回撤30以内和80%收益保留，但它不是 alpha 改善，也不通过高滑点收益保留。
- xsmom 净值层最有研究价值，但直接期货小资金腿不可承载；如果继续，应研究新的承载结构，而不是调 `7.5%` 权重。
- Carry/季节性/同源慢周期可让曲线更平滑，但主要来自稀释或负收益腿，不满足“收益不显著降低”的正式目标。
- 是否进入下一步：进入。下一步应专门研究 xsmom 净值层的可承载结构，或把 Stage055 作为部署边界对外说明；不继续救已反证卫星权重。

## 过拟合反思

- 运行前判断：不是过拟合。原因是本阶段只审计既有曲线，不新增规则、不搜索阈值。
- 运行后判断：不是过拟合。原因是排序只用于路径质量判断，并且主动把已反证/不可承载候选标出来。
- 风险提示：如果把 `Carry 10%`、`季节性 10%` 或 `xsmom 7.5%` 当成“最佳参数”继续扫小数，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。原因是目标已经扩展为收益、回撤、平滑度三维，需要统一审计现有候选。
- 运行后判断：有价值，但下一步必须缩小到“承载结构”而不是继续找小数参数。
- 原因：本阶段已经证明平滑度可以改善；真正难点是找到不牺牲太多收益且可真实下单的独立收益源。

## 合入建议

- 是否更新本线 `LINE.md`：是，加入 Stage064/065。
- 是否更新 `research/registry.md`：是，最新阶段改为 Stage065。
- 是否追加根目录 `memory.md/back_log.md`：是，作为目标解释修正和后续禁区。
