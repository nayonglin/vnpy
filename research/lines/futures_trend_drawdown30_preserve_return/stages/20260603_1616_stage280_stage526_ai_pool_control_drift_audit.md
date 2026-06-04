# Stage280 Stage526 AI产品池控制组漂移审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 16:16 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：控制组漂移审计与代码语义修复；不新增 alpha，不新增交易候选。
- 是否重要突破：是。修复了 Stage256 后引入的 AI 产品池 `eval_date` 同日生效回归，并恢复 Stage526 权威控制组。
- 是否触发A/B：否。本阶段是控制组复现/漂移审计，不是新策略候选。

## 外部调研与判断

- 参考方向：量化回测复现性、backtest drift、策略版本/数据版本审计；成熟流程要求先锁定同一数据、参数、成本和引擎语义，再比较候选收益。
- 本地判断：本次不是寻找更好曲线，而是修复控制组语义。若控制组漂移未先归零，任何后续候选比较都会失真。

## 本次变更

- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage580_stage526_ai_pool_control_drift_audit.py`
- 新增参数：无交易参数。
- 修改参数：无。
- 删除参数：无。
- 代码修复：`_ai_product_pool_snapshot` 从 `eval_index.searchsorted(normalized_date, side="right") - 1` 恢复为 `side="left" - 1`。
- 语义：`eval_date` 视为已完成信号快照，在 exact `eval_date` 当天继续使用上一期快照；新快照从之后的交易时点可用。若调用方需要下一交易日生效，应显式通过 `_ai_product_pool_entry_effective_date()` 平移有效日期。

## 根因

- Stage256 修复年度 top6 白名单时，把 AI 产品池快照查找改成了 `side="right"`。
- 这让月度 `eval_date` 快照在同一天就可用于交易，导致 Stage526 控制组在月末换池日提前使用未来完成快照。
- 典型差异：`2023-02-28/2023-03-01` 附近，污染版允许 `FG305.CZCE`，而旧权威语义仍使用上一期快照并保留 `ru2305.SHFE` 路径。

## 回测/审计参数

- 账户规模：Stage526 核心 `50万` + xsmom 组合账本口径，维持旧权威输出。
- 成本口径：正常 `1x`，并只用于控制组漂移比较。
- 对比对象：
  - old authority：`qmt_roll_stage526_productcap25_breadth_frontier`
  - prepatch：Stage577 同跑 A，含 `side="right"` 污染
  - repaired：Stage580 修复后重跑控制组

## 结果

- 旧权威 Stage526：
  - 期末权益 `23,369,505`
  - 总收益 `3699.9195%`
  - 最大回撤 `-36.2670%`
  - Sharpe `1.6385`
  - Ulcer `14.4691`
  - 总滑点 `1,342,190`
  - 总交易次数 `905`
  - 非零日胜率 `53.6330%`
- Stage577 污染版控制组：
  - 期末权益高出旧权威 `1,229,815`
  - 日度总 PnL 差异天数 `503`
  - 总滑点高出 `52,310`
- Stage580 修复后控制组：
  - 期末权益差 `0`
  - 总收益差 `0.0000pp`
  - 总滑点差 `0`
  - 日度总 PnL 差异天数 `0`
  - `exact_match_old_authority=true`

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage580_stage526_ai_pool_control_drift_audit_chart_stage580_stage526_ai_pool_control_drift_audit_v1.png`
- 左上权益图：旧权威蓝线与修复后绿线完全重合；污染版红线从 2023 后开始分叉并在 2025-2026 持续高于旧权威。
- 右上漂移图：污染版相对旧权威累计漂移上升到约 `122.98万`，修复线为零轴平线。
- 左下日 PnL 差异：污染版有多次尖峰，修复后为零差异。
- 右下指标柱：修复后 total return、max DD、slippage 均回到旧权威。

## 输出文件

- script：`examples/portfolio_backtesting/analyze_qmt_roll_stage580_stage526_ai_pool_control_drift_audit.py`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage580_stage526_ai_pool_control_drift_audit_decision_stage580_stage526_ai_pool_control_drift_audit_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage580_stage526_ai_pool_control_drift_audit_report_stage580_stage526_ai_pool_control_drift_audit_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage580_stage526_ai_pool_control_drift_audit_chart_stage580_stage526_ai_pool_control_drift_audit_v1.png`
- compare：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage580_stage526_ai_pool_control_drift_audit_summary_compare_stage580_stage526_ai_pool_control_drift_audit_v1.csv`
- daily diff：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage580_stage526_ai_pool_control_drift_audit_daily_diff_stage580_stage526_ai_pool_control_drift_audit_v1.csv`

## 结论

- 决策：`ai_pool_eval_date_regression_repaired`
- Stage526 权威控制组已恢复。
- Stage279 污染版 failure-memory 复验不能作为最终引用，必须用 Stage581 修复后结果替代。
- Stage256 年度 top6 下一交易日生效语义未被废弃：它应通过显式 effective date 平移处理，而不是全局改变快照查找语义。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：本阶段只修复 point-in-time 语义和控制组复现，不使用收益结果调整交易规则，也没有选择日期、品种或阈值。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值且必要。
- 原因：真实可成交策略结构必须先保证控制组不漂移。修复后可以继续做 Stage581 失败记忆复验和后续 selector/执行质量研究。

## TODO

- 用修复后的控制组重跑 Stage577 failure-memory 微仓位候选，输出 Stage581。
- 后续涉及 AI 产品池的所有历史回放，必须先确认 `eval_date` 生效语义是否符合 point-in-time。
