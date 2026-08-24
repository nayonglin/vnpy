# Stage017 多头三倍放大与半量缩减风险全周期结果

- line_id：`futures_trend_rollover_shape_same_volume`
- 结果时间：2026-08-24 19:09 CST
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 最终结果前冻结提交：`ebe805b8625e50f623353c1b34839ac7654cf5be`
- 复用来源提交：`9554adf7e9d02979af90557387a790ff7e46815e`
- 是否重要突破：否
- 最终决策：`stop_long_triple_volume_with_low_volume_discount_after_full_period`

## 外部调研与判断

- CME 支持把期货成交量解释为参与度、流动性和换月迁移信息，但明确成交量本身不能识别买卖方向：<https://www.cmegroup.com/education/courses/introduction-to-futures/what-is-volume>。
- `pysystemtrade` 将信号、position sizing、portfolio 与 accounting 分层，支持把低量规则限制在风险仓位层：<https://github.com/robcarver17/pysystemtrade/blob/develop/docs/backtesting.md>。
- 判断：M 的回撤和 Sharpe 改善来自4个极端缩量多头的路径重分配；样本太少，且相对 A/C 仍未覆盖成本门，不能解释为稳定独立 alpha。

## 本次版本变更

- 新增研究臂 M：基于换月 C，多头30日同向且最近10日量严格大于再前10日 `3.0` 倍时风险 `×1.5`；多头最近10日量严格小于再前10日 `0.5` 倍时风险 `×0.5`，低量判断不要求30日同向；其他多头 `×1.0`；全部空头 `×1.0`。
- 恰好 `0.5` 倍不减、恰好 `3.0` 倍不加；价格或成交量历史不足/无效保持 `×1.0`。
- 覆盖全部 risk-budget flat、reverse、rollover reopen 与三类 add；fixed-size 不变，倍率后仍向下取整并通过既有硬门。
- 新增参数：`enable_directional_30d_low_volume_risk_discount=true`、`directional_30d_low_volume_ratio_threshold=0.5`、`directional_30d_low_volume_risk_multiplier=0.5`。
- 修改实验参数：无；删除参数：无。
- A/C/L 从 Stage015 原始 summary/curve 精确复用，各 `2,037` 行资金曲线逐值一致；仅 M 新跑一次完整周期真引擎。
- 正式配置、正式物料、master、production、CTP和订单路径均未修改；订单/撤单 API `0/0`，`ctp_connected=false`。

## 完整周期结果

区间 `2018-01-01 -> 2026-05-29`，初始资金 `150,000`。

|臂|期末权益|总收益|最大回撤|Sharpe|总滑点|交易|胜率|broker10峰值|超100%天数|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|A 正式|13,071,214.10|8614.1427%|-56.2069%|1.362230|1,525,590|808|52.5841%|91.4950%|0|
|C 换月|13,338,365.80|8792.2439%|-56.9876%|1.362669|1,517,200|825|52.6812%|100.4112%|1|
|L 多头三倍量1.5|14,442,341.80|9528.2279%|-56.5393%|1.374306|1,684,490|827|52.5326%|98.8823%|0|
|M 多头三倍量1.5/半量0.5|14,293,257.00|9428.8380%|-54.2470%|1.406198|1,634,290|826|52.7496%|91.0591%|0|

## 双基线差异与门槛

- M 相对正式 A：期末权益 `+1,222,042.90`、收益 `+814.6953pp`、最大回撤改善 `1.9599pp`、Sharpe `+0.043967`、broker10峰值改善 `0.4359pp`；但滑点为 A 的 `107.1251%`，超过 `105%` 上限，`A_vs_M` 失败。
- M 相对换月 C：期末权益 `+954,891.20`、收益 `+636.5941pp`、最大回撤改善 `2.7406pp`、Sharpe `+0.043529`、broker100 从1天改善为0天；但滑点为 C 的 `107.7175%`，超过 `105%`，`C_vs_M` 失败。
- M 相对 L：期末权益 `-149,084.80`、收益 `-99.3899pp`，但最大回撤改善 `2.2923pp`、Sharpe `+0.031891`、滑点降至 `97.0199%`、broker10峰值改善 `7.8232pp`。M 用少量收益换取更好风险路径，但 L 本身已失败，不能替代 A/C 双门。
- `A_vs_M`、`C_vs_M` 均仅成本门失败，`escalate_to_multicycle=false`；按预声明规则不进入多周期。

## 风险合同与实际成交

- 最终风险诊断 `376` 条：多头高量 `17×1.5`、多头低量 `4×0.5`、其他多头 `281×1.0`、空头旁路 `74×1.0`。
- 多头低量4条均为 flat entry：`au2006.SHFE`、`ru2101.SHFE`、`jm2201.DCE`、`hc2205.SHFE`；最近/此前10日量比最大 `0.4987701`，全部严格低于 `0.5`，风险金额逐行精确减半。
- 规则不要求30日方向同向，但本次4条自然命中样本恰好全部30日同向；因此本回测没有提供“方向不一致但极端缩量”的真实样本证据。
- 4条低量诊断全部形成后续初始 OPEN；前三条最终成交为 `2/4/9` 手，`hc2205.SHFE` 从诊断300手经下游硬门缩至120手成交，证明低量倍率不会绕过既有容量约束。
- 总 OPEN `404`，其中 Stage847 retry `30`，实际初始 OPEN `374`；风险上下边界、long-only、空头旁路、倍率和目标风险金额合同全部通过。

## 输出与独立复算

- `artifacts/stage017/stage017_aclm_summary.csv`
- `stage017_aclm_comparison.csv`
- `stage017_aclm_curve.csv`
- `stage017_full_m_entry_risk.csv`
- `stage017_full_m_trades.csv`
- `stage017_full_m_trade_events.csv`
- `stage017_full_m_risk_split_contract_summary.csv`
- `stage017_decision.json`
- `stage017_full_period_equity_aclm.png`
- summary 的期末权益、收益、最大回撤、Sharpe、滑点、交易数从curve独立重算，最大绝对误差 `1.82e-12`；A/C/L 与 Stage015 各 `2,037` 点资金曲线最大差 `0`。
- 独立 reviewer 首轮 `P0=0/P1=1/P2=0/P3=0`，唯一P1为结果记录尚未落盘；本文件补齐后复核为 `P0=0/P1=0/P2=0/P3=0`，规则、复用身份、数字、晋级门、未来数据和生产隔离均通过。

## 结果反思与后续

- 运行后是否过拟合：是，高风险。低量分支只命中4条，路径改善由极小样本决定；精确 `0.5` 阈值和 `0.5` 倍率不能据此宣称可穿越周期。
- 运行后是否值得继续：否，按当前历史优化路线无继续价值。M 虽改善回撤、Sharpe和broker暴露，但 A/C 成本门均失败；不因“只差成本门”扫描阈值、倍率或强行跑多周期。
- 决策：`stop_long_triple_volume_with_low_volume_discount_after_full_period`；不晋升、不发布正式物料、不改 master/production/CTP。
- 未来只有新增、未参与设计的 forward OOS 极端缩量样本形成足够覆盖，才允许重新评估这一防守标签。
