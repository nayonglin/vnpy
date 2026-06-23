# Stage261 账户外层治理边界审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 时间：`2026-06-22 16:41`
- 工作模式：`day`
- 阶段性质：只读账户/资金分层边界审计；不创建交易规则，不运行 true engine，不触发 A/B，不改正式配置，不连接 CTP/SimNow，不调用订单 API。
- 是否重要突破版本：否。它是本地可继续路线的边界封口，不是策略候选。
- decision：`stage261_pure_outside_account_transfer_invariant_no_alpha_no_candidate`

## 外部调研与判断

- CPPI/TIPP 类组合保险强调通过动态调整风险资产暴露保护 floor，但这本质会改变持仓风险，不属于“不改变正式持仓路径”的账户外层治理：https://quantpedia.com/introduction-to-cppi-constant-proportion-portfolio-insurance/
- AXA IM 对 CPPI/TIPP 的介绍同样把它定义为在低风险和高风险资产之间动态调配，以保护初始资本或高水位 floor：https://core.axa-im.com/investment-strategies/multi-asset/insights/understanding-portfolio-insurance-management-cppitipp
- CME 的 2% 风险规则属于头寸风险预算管理，会改变每笔风险暴露，不是纯外部账户转账：https://www.cmegroup.com/education/courses/trade-and-risk-management/the-2-percent-rule
- Schwab 的 bucket approach 是资产账户分桶与提款规划思想，可用于现金流治理，但若交易持仓和 PnL 路径不变，合并总财富曲线不会因为内部转账而降低真实回撤：https://www.schwab.com/learn/story/phasing-retirement-with-bucket-drawdown-strategy
- 我的判断：外层账户分桶只有两种真实状态：第一，纯内部转账且不改变持仓/PnL，则合并总财富等于官方权益曲线，不能降低真实最大回撤；第二，真实出金降低生产账户权益，则会改变保证金/生存性，不能再声称“不改变正式持仓路径”。因此它不能作为本线“高质量信号最小风险”策略 alpha。

## 本次版本改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage261_outside_account_governance_boundary_audit.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_outside_account_governance_boundary_audit/`
- 读取输入：
  - Stage017 CPPI/TIPP 历史反证
  - Stage020 月末出金锁盈历史反证
  - Stage251 官方 A 臂资金曲线
  - Stage259 下一步队列
  - Stage260 执行回放缺口
- 固定审计 5 个账户转账边界策略：
  - `A_official_no_transfer`
  - `B_monthly_5m_half_lock60_reserve40_transfer_only`
  - `C_monthly_new_hwm_10pct_lockbox`
  - `D_quarter_end_profit_20pct_reserve`
  - `E_year_end_profit_30pct_lockbox`
- 新增参数：
  - `CAPITAL=150,000`
  - `TRADING_DAYS_PER_YEAR=252`
  - `EPS=1e-6`
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无，未运行 true engine；只重放官方日级 PnL 并做账户转账不变性审计。
- 修改回测结果：无。
- 删除回测结果：无。

## 关键结果

- 官方 A 臂不变：
  - 期末权益：`39,176,437.60`
  - 总收益：`26017.6251%`
  - 最大回撤：`-45.0827%`
  - Sharpe：`1.6331`
  - 总滑点：`2,730,130`
  - 总交易次数：`787`
  - 胜率：`53.2560%`
- Stage261 审计结果：
  - policy_count：`5`
  - candidate_ready_count：`0`
  - best non-official return retention：`1.0000`
  - best non-official total DD improvement：`0.0000pp`
  - max total wealth invariant abs diff：`0.0000000149`
  - pure transfer total DD changed count：`0`
  - gate：`2/6`
- Gate 结论：
  - 通过：无正式配置/订单副作用、收益保留 >=80%。
  - 失败：合并总财富回撤改善 5pp、非官方转账后生产账户安全不恶化、策略 alpha/信号质量、Stage259/260 本地路线重启。

## 视觉输出

- official vs total wealth path：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_outside_account_governance_boundary_audit/qmt_roll_stage261_c9_minrisk_outside_account_governance_boundary_audit_official_vs_total_wealth_path_stage261_outside_account_governance_boundary_audit_v1.png`
- bucket layer chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_outside_account_governance_boundary_audit/qmt_roll_stage261_c9_minrisk_outside_account_governance_boundary_audit_bucket_layer_chart_stage261_outside_account_governance_boundary_audit_v1.png`
- drawdown invariance chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_outside_account_governance_boundary_audit/qmt_roll_stage261_c9_minrisk_outside_account_governance_boundary_audit_drawdown_invariance_chart_stage261_outside_account_governance_boundary_audit_v1.png`
- return drawdown frontier：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_outside_account_governance_boundary_audit/qmt_roll_stage261_c9_minrisk_outside_account_governance_boundary_audit_return_drawdown_frontier_stage261_outside_account_governance_boundary_audit_v1.png`
- invariant gate chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage261_outside_account_governance_boundary_audit/qmt_roll_stage261_c9_minrisk_outside_account_governance_boundary_audit_invariant_gate_chart_stage261_outside_account_governance_boundary_audit_v1.png`
- 图像检查：5 张 PNG 尺寸正常、非空，像素标准差约 `28.6411` 到 `105.9804`。

## 第一性结论

如果官方持仓和每日 PnL 不变，生产账户、锁盈账户、备用账户之间的转账只是内部资产搬家：

`consolidated_wealth = production_equity + locked_equity + reserve_equity = official_equity`

因此真实合并总财富最大回撤不能变小。Stage261 的 4 个非官方转账策略全部满足收益保留 `1.0`，但合并总财富最大回撤改善都是 `0.0pp`。同时，只要把现金真实移出生产账户，生产账户权益变薄，`broker10` 压力相对生产账户会恶化，例如：

- `B_monthly_5m_half_lock60_reserve40_transfer_only`：生产账户最大回撤 `-91.6633%`，max broker10/production `338.2200%`
- `C_monthly_new_hwm_10pct_lockbox`：生产账户最大回撤 `-50.9382%`，max broker10/production `120.6860%`
- `D_quarter_end_profit_20pct_reserve`：生产账户最大回撤 `-57.7133%`，max broker10/production `143.7589%`
- `E_year_end_profit_30pct_lockbox`：生产账户最大回撤 `-55.8255%`，max broker10/production `157.1092%`

这说明账户外层治理可以做现金流/心理账户/提款规划，但不能算作本目标里的“降低策略真实最大回撤且保留 80% 收益”的 alpha。

## 结论

Stage261 封闭了 Stage259 中唯一无需外部状态的本地路线：`outside_account_capital_governance_only`。它不应继续扩展为正式候选、A/B、true engine 或持仓路径变更；也不得用分桶后的局部账户回撤替代合并总财富回撤。

从当前证据看，继续靠近原目标只剩两条有效路线：

1. 导入 broker/production 同源执行回放；
2. 获取授权 orderflow/depth/MBO/MBP10，或等价的外部高信息源。

没有这些数据时，继续本地 OHLCV/OI、出金比例、CPPI/TIPP、账户分桶、smoke/read-only 文件救参，都会偏离“普世、不过拟合、穿越周期”的目标。

## 开始与结束反思

- 开始前是否过拟合：否。本阶段没有扫品种、年份、方向、分钟阈值或交易参数，只做账户转账数学不变性审计。
- 结束后是否过拟合：否。结论是否定账户分桶作为 alpha，没有从样本里提炼新规则。
- 开始前是否还有价值继续：有。Stage259/260 已把本地策略信息路线收束，只剩账户外层治理这一条无需外部状态的路线需要边界审计。
- 结束后是否还有价值继续：有，但价值不在本地账户分桶；价值只在外部/同源高信息数据导入，或把账户分桶降级为非策略的现金流治理说明。

## 后续 TODO

- 不再继续账户分桶、出金比例、CPPI/TIPP 或 DD floor 扫参。
- 若要继续本目标，优先准备 broker/production execution replay intake 或授权 orderflow/depth 数据合同。
- 若没有新数据，只能做数据采购/forward capture 验收，不进入 true engine、A/B 或正式候选。
