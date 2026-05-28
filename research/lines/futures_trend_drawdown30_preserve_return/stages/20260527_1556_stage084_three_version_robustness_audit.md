# Stage084 三版本鲁棒性与路径压力审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 15:56 CST
- 阶段性质：只读深度审计；不修改 `78-1`、`Stage079`、`C3` 的信号、品种、AI池、仓位或成交路径
- 是否重要突破：否，重要复核。补充 Stage083 没有覆盖的路径依赖、bootstrap、月份顺序扰动和现金需求边界。
- 是否触发A/B：否。本阶段没有新策略版本，只做候选排序审计。

## 外部调研与判断

- 参考资料：
  - TradingStrategy.ai backtesting / research methodology：强调单条历史曲线不足以证明稳健性，需要 walk-forward/rolling、成本、鲁棒性和过拟合控制一起看。
  - Ulcer Index / PerformanceAnalytics：强调回撤深度和持续时间，而不只看最大回撤单点。
- 我的判断：
  - 本阶段不能继续调资金小数或策略阈值，只能固定评估维度做只读审计。
  - `Stage079`、`纯C3`、`78-1`不是完全同类：`Stage079` 是账户部署结构，`纯C3` 是更高收益底座，`78-1` 是正式基准。
  - 结论必须区分“当前目标下哪个更好”和“纯 alpha 哪个更强”。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage384_three_version_robustness_audit.py`
- 修改策略脚本：无
- 删除脚本：无
- 新增输出：
  - `qmt_roll_stage384_three_version_robustness_audit_summary_stage384_three_version_robustness_audit_v1.csv`
  - `qmt_roll_stage384_three_version_robustness_audit_rolling_distribution_stage384_three_version_robustness_audit_v1.csv`
  - `qmt_roll_stage384_three_version_robustness_audit_tail_dependency_stage384_three_version_robustness_audit_v1.csv`
  - `qmt_roll_stage384_three_version_robustness_audit_block_bootstrap_stage384_three_version_robustness_audit_v1.csv`
  - `qmt_roll_stage384_three_version_robustness_audit_month_permutation_stage384_three_version_robustness_audit_v1.csv`
  - `qmt_roll_stage384_three_version_robustness_audit_cash_requirement_stage384_three_version_robustness_audit_v1.csv`
  - `qmt_roll_stage384_three_version_robustness_audit_score_stage384_three_version_robustness_audit_v1.csv`
  - `qmt_roll_stage384_three_version_robustness_audit_decision_stage384_three_version_robustness_audit_v1.json`
  - `qmt_roll_stage384_three_version_robustness_audit_report_stage384_three_version_robustness_audit_v1.md`
  - `qmt_roll_stage384_three_version_robustness_audit_dashboard_stage384_three_version_robustness_audit_v1.html`

## 参数

- 新增参数：
  - `BOOTSTRAP_SIMS=3000`
  - `MONTH_PERMUTATION_SIMS=3000`
  - block bootstrap 长度：`20/60` 日
  - 尾部依赖：移除最强正收益日 `1/3/5/10/20`
  - 成本压力：`1x/2x/3x/5x`
  - 目标最大回撤：`-30%`
  - 相对 C3 收益保留闸门：`80%`
- 修改参数：无
- 删除参数：无

## 数据与口径

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 三版本：
  - `78-1`：正式基准
  - `纯C3`：50万 C3 裸策略
  - `Stage079`：`50万C3下单 + 11.5万外部现金`
- 本阶段先重跑 Stage083，再读取 Stage083 当前日度权益输出。
- 成本现金需求只保留从当前全周期 `net_pnl/slippage` 可严谨重构的结果；不输出无法等同真实引擎冷启动的现金估算。

## 全周期结果

| 版本 | 总收益 | 最大回撤 | Sharpe | Ulcer | 日收益5%尾部均值 | 最长水下 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `78-1` | `5170.7870%` | `-40.1659%` | `1.1645` | `20.7798` | `-6.4741%` | `403` 天 |
| `纯C3` | `6085.1300%` | `-31.0767%` | `1.3143` | `16.2072` | `-5.3783%` | `369` 天 |
| `Stage079` | `4947.2602%` | `-29.7007%` | `1.3182` | `15.0931` | `-5.0266%` | `369` 天 |

## 滚动窗口结果

- 252日滚动：
  - `Stage079`：回撤30以内通过率 `100.0000%`，5%分位收益 `-1.6710%`
  - `纯C3`：回撤30以内通过率 `84.9029%`，5%分位收益 `-1.6915%`
  - `78-1`：回撤30以内通过率 `47.5243%`，5%分位收益 `-15.7971%`
- 504日滚动：
  - `Stage079`：回撤30以内通过率 `100.0000%`，5%分位收益 `55.4206%`
  - `纯C3`：回撤30以内通过率 `54.9226%`，5%分位收益 `56.6168%`
  - `78-1`：回撤30以内通过率 `22.5664%`，5%分位收益 `24.5282%`

## Tail / 路径依赖

- 移除最强 `10` 个正收益日后：
  - `Stage079`：总收益 `898.1018%`，最大回撤 `-32.5210%`
  - `纯C3`：总收益 `1015.9151%`，最大回撤 `-34.2862%`
  - `78-1`：总收益 `748.3505%`，最大回撤 `-56.9477%`
- 判断：
  - 三者都依赖少数趋势日，这是趋势策略基本属性，不是 Stage079 独有问题。
  - Stage079 在移除极端正收益日后也会破30，说明它的安全垫不厚。

## Bootstrap 与月份顺序扰动

- block bootstrap `20` 日：
  - `Stage079`：破30回撤概率 `89.0000%`，5%分位最大回撤 `-53.1980%`
  - `纯C3`：破30回撤概率 `94.9333%`，5%分位最大回撤 `-56.9118%`
  - `78-1`：破30回撤概率 `99.6667%`，5%分位最大回撤 `-69.6257%`
- block bootstrap `60` 日：
  - `Stage079`：破30回撤概率 `86.4333%`
  - `纯C3`：破30回撤概率 `94.1333%`
  - `78-1`：破30回撤概率 `99.7667%`
- 月份顺序扰动：
  - `Stage079`：破30回撤概率 `86.4333%`，中位最大回撤 `-35.2558%`
  - `纯C3`：破30回撤概率 `95.2667%`，中位最大回撤 `-37.7840%`
  - `78-1`：破30回撤概率 `100.0000%`，中位最大回撤 `-47.3209%`
- 判断：
  - Stage079 仍是三者里最稳，但经不起把历史收益顺序打乱后的严格统计压力。
  - 所以它应被称为“当前历史路径与正常成本下的部署候选”，不能被称为厚安全垫版本。

## 成本现金需求

| 版本 | 1x压到30所需现金 | 2x压到30所需现金 | 3x压到30所需现金 | 5x压到30所需现金 |
| --- | ---: | ---: | ---: | ---: |
| `78-1` | `3,237,350` | `5,308,060` | `7,378,770` | `11,520,190` |
| `纯C3` | `66,043.33` | `318,850` | `571,656.67` | `3,340,748.33` |
| `Stage079` 追加现金 | `0` | `203,850` | `456,656.67` | `3,225,748.33` |

## 综合评分

| 版本 | 当前目标分 | alpha分 | 结论 |
| --- | ---: | ---: | --- |
| `Stage079` | `70.7421` | `68.7149` | 当前目标综合第一 |
| `纯C3` | `42.9009` | `74.5246` | 纯 alpha 第一，但回撤目标不达标 |
| `78-1` | `30.1195` | `59.9849` | 正式基准，但本线目标下不占优 |

## 结论

- 当前目标“回撤30以内 + 收益不显著降低 + 曲线更平滑”：`Stage079` 最好。
- 纯 alpha 收益最大：`纯C3` 最好。
- 正式基准身份：`78-1` 保留，但不应作为本线最优候选。
- `Stage079` 胜出不是因为信号比 C3 强，而是因为 `50万C3下单 + 11.5万现金` 的账户部署结构更匹配回撤目标。
- 高滑点结论不变：`Stage079` 在 `2x/3x/5x` 下仍需新增现金才可压进30，不能宣称为高成本稳健版本。

## 过拟合反思

- 运行前判断：不是过拟合。固定比较对象与指标，不新增交易规则或参数搜索。
- 运行后判断：不是过拟合。Stage079 的胜出来自部署现金边界，报告明确区分了账户口径和 alpha 强弱，没有把加现金误判为信号提升。

## 继续价值反思

- 运行前判断：有价值。Stage083 给出排序，但还需要知道该排序是否经得住路径压力和成本现金边界。
- 运行后判断：继续有价值，但不是继续调这三个版本。正常成本下推进 Stage079 的 forward/影子盘审计；高滑点目标则另找独立收益源或低费用承载工具。

## 后续规划

- 若接受正常成本和 `61.5万` 账户口径：推进 Stage079 的 forward / 影子盘部署边界审计。
- 若要求高滑点也压到30以内：不要继续扫 `11.5万` 附近小数，必须寻找新的低相关收益源或费用敏感度更低的承载工具。
- 若只追求策略收益率：保留 `纯C3` 为 alpha 底座，但它不是回撤30以内版本。

