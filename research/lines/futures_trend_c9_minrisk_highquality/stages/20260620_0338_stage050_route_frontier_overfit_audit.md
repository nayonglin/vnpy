# Stage050 route frontier overfit audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 03:38 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：既有路线前沿审计和过拟合风险审计；不是新交易规则，不是真实组合引擎，不是 A/B 候选，不是实盘规则。
- 是否重要突破：否。它是收束和封存审计，不是候选突破。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - Bailey / Lopez de Prado, `The Probability of Backtest Overfitting`：多策略、多参数反复试验会提高回测过拟合概率，应用 CSCV/PBO 思想审视历史试错前沿。
  - AQR / Hurst, Ooi, Pedersen, `A Century of Evidence on Trend-Following Investing`：趋势跟踪能穿越周期的基础在于简单、长期、分散、跨环境有效，而不是针对局部样本做补丁。
  - Rob Carver / `pysystemtrade` 与 systematic trading 资料：稳健系统应先设计、后验证，规则必须可算法化复现，避免把历史表现差异反推成复杂过滤。
- 我的判断：本线前 49 阶段已经覆盖了分钟削仓、硬退出、默认最小风险恢复、账户层 floor/tranche、相关拥挤、波动参与度、期限结构、供需、会员持仓、stop/retry 语义和产品趋势 t-stat 等路线。继续在这些失败形状上切产品、年份、方向、窗口、R 倍数或阈值，本质上是在增加多重试验次数，而不是提高普世性。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage050_route_frontier_overfit_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `TARGET_RETURN_RETENTION = 80.0`
  - `TARGET_DD_IMPROVEMENT = 5.0`
  - `strict_candidate_pass = return_retention >= 80% + max_dd_improvement >= 5pp + broker10不恶化 + Sharpe不显著下降 + evidence_type == true_engine`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：复用本线 Stage002/003/004/008/009/013/017/018/019/020/021/046/048/049 已生成的正式 C9/15w 输出。
- 账户规模：官方正式 `150,000`。
- 成本口径：沿用各阶段既有官方 C9/15w 口径；官方主口径总滑点 `2,730,130`。
- 样本过滤：不筛年份、不筛品种、不筛方向；按既有路线记录合并为 `true_engine`、`proxy`、`upper_bound` 三类证据。
- 策略/归因口径：把每条已测试路线投影到同一个收益保留 / 最大回撤改善前沿图；代理和乐观上限只能作为解释证据，不能算 deployable 候选。

## 结果

- 官方期末权益：`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：约 `1.633`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方胜率：`53.2560%`
- 其他关键指标：
  - 合并 tested records：`21`
  - strict deployable candidate pass count：`0`
  - best true-engine drawdown repair：Stage009 / `C_stage009_opening_range_adverse_exit`，最大回撤改善 `6.8986pp`，但收益保留仅 `40.2072%`，Sharpe 下降。
  - nearest record：Stage018 / `no_follow_30m_low_quality_80`，收益保留 `102.3680%`，最大回撤改善 `4.5666pp`，但 broker10 恶化到 `112.6528%`，且只是 proxy，后续 Stage019 真引擎已反证。
  - Stage020 profit tranche 最大回撤改善 `10.5748pp`，但收益保留仅 `43.4992%`，且是账户层 proxy。
  - Stage048 upper bound 收益保留 `104.5272%`，但最大回撤只改善 `0.1631pp`。
  - Stage049 upper bound 收益保留 `93.2863%`，但最大回撤恶化 `13.4003pp`。
  - 决策：`stage050_no_existing_route_candidate_continue_only_new_predeclared_or_data_engineering`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage050_route_frontier_overfit_audit/qmt_roll_stage050_c9_minrisk_route_frontier_overfit_audit_report_stage050_route_frontier_overfit_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage050_route_frontier_overfit_audit/qmt_roll_stage050_c9_minrisk_route_frontier_overfit_audit_frontier_metrics_stage050_route_frontier_overfit_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage050_route_frontier_overfit_audit/qmt_roll_stage050_c9_minrisk_route_frontier_overfit_audit_next_route_decision_stage050_route_frontier_overfit_audit_v1.json`
- route summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage050_route_frontier_overfit_audit/qmt_roll_stage050_c9_minrisk_route_frontier_overfit_audit_route_family_summary_stage050_route_frontier_overfit_audit_v1.csv`
- quality / visuals：
  - `qmt_roll_stage050_c9_minrisk_route_frontier_overfit_audit_return_drawdown_frontier_stage050_route_frontier_overfit_audit_v1.png`
  - `qmt_roll_stage050_c9_minrisk_route_frontier_overfit_audit_representative_path_chart_stage050_route_frontier_overfit_audit_v1.png`
  - `qmt_roll_stage050_c9_minrisk_route_frontier_overfit_audit_failure_reason_chart_stage050_route_frontier_overfit_audit_v1.png`

## 视觉观察

- return/drawdown frontier 图显示，绿色目标区只标记 `return_retention >= 80%` 且 `dd_improvement >= 5pp` 的交集；其中没有任何 `true_engine` 点，也没有 deployable 候选。
- representative path chart 显示，Stage009 这类真实硬退出能让部分回撤段变浅，但从 `2021` 后系统性低于官方，属于砍右尾换平滑；Stage020 profit tranche 也在 `2021` 后压制复利；Stage048/049 上限线要么贴近官方、要么在 `2022-2023` 明显低于官方。
- failure reason chart 显示主要失败原因是 `dd_improvement_lt5pp`，其次是 `broker10_worse`、`proxy_not_deployable`、`return_retention_lt80` 和 `sharpe_lower`；这说明失败不是某一条规则差一点，而是路线族普遍存在收益/回撤/可部署性三角矛盾。

## 结论

- 本阶段结论：既有 12 个路线族没有一个达到“收益保留 80%+、最大回撤改善 5pp+、broker10 不恶化、Sharpe 不显著下降、且为真引擎”的 deployable 标准。
- 是否进入下一步：继续本研究目标，但不得继续沿既有失败路线切阈值或拆样本。
- 下一步：
  1. 数据工程路线：先补齐并点时化外生数据覆盖，再用固定 spec 重跑，不得边补边调。
  2. 新候选路线：只允许基于 Stage045 已同步的 `timestamp_ready=1` 分钟 replay 子集，先预声明一个第一性规则；`fallback/no-proxy` 样本保持官方路径或先补数据。

## 过拟合反思

- 运行前判断：否。Stage050 是把既有冻结结果归一审计，不新增阈值、不筛样本、不寻找更好参数。
- 运行后判断：审计本身不是过拟合；但若继续在 blocked routes 内做产品、年份、方向、窗口、R 倍数、阈值附近搜索，就是明显过拟合。
- 原因：21 条记录已经显示统一前沿形态，真引擎降回撤通常牺牲右尾，保留收益的代理又不能真引擎落地或回撤改善不足。

## 继续价值反思

- 运行前判断：有价值。路线前沿审计可以防止我们把“还差一点”的错觉误当成继续深挖价值。
- 运行后判断：本研究线仍有价值，但价值只在两个方向：补齐点时外生数据，或提出一个新的、预声明的、可 replay 的分钟执行候选。
- 原因：当前目标还没有达成；但继续价值不在旧路线救参，而在减少自由度、提高点时数据质量和候选可证伪性。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage050 归纳结论和后续硬边界。
- 是否更新 `research/registry.md`：否，非正式候选、非跨线合并；本线仍在推进。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是本线内路线前沿审计，不是正式候选、重要突破或整条路线废弃。
