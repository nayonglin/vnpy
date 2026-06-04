# Stage275 Stage526硬容量残余成交证据审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 02:22 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读成交/容量证据审计；不修改交易策略，不新增交易版本，不重算收益曲线。
- 是否重要突破：否；但进一步收窄 Stage269 的真实可成交证据缺口。
- 是否触发A/B：否。本阶段没有形成可接入正式版本的新策略。

## 外部调研与判断

- 参考资料：
  - 郑商所英文站显示交易时间为 `9:00-11:30`、`13:30-15:00` 北京时间。
  - 上期所英文交易时间页面列出下午日盘为 `1:30-3:00 PM`。
- 我的判断：
  - Stage269 使用 `14:30-15:00` 作为收盘执行窗口是合理的保守审计窗口。
  - 日线成交量能证明合约当天不是死合约，但不能等同于“收盘窗口一定可按回测 close 成交”；两类证据必须分开记录。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit.py`
- 修改策略脚本：无。
- 删除脚本：无。
- 新增输出：
  - `qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit_hard_event_detail_stage573_stage526_hard_capacity_residual_evidence_audit_v1.csv`
  - `qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit_minute_candidates_stage573_stage526_hard_capacity_residual_evidence_audit_v1.csv`
  - `qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit_gates_stage573_stage526_hard_capacity_residual_evidence_audit_v1.csv`
  - `qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit_summary_stage573_stage526_hard_capacity_residual_evidence_audit_v1.csv`
  - `qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit_decision_stage573_stage526_hard_capacity_residual_evidence_audit_v1.json`
  - `qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit_report_stage573_stage526_hard_capacity_residual_evidence_audit_v1.md`
  - `qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit_chart_stage573_stage526_hard_capacity_residual_evidence_audit_v1.png`

## 参数与口径

- 输入：
  - Stage567 硬容量事件 `5` 笔。
  - Stage567 同日换月配对上下文。
  - 本地 TqSdk 日线 `tqsdk_daily_2010_2026_04`。
  - 本地所有同合约分钟文件，包括 `minute_backtest` 与 `completed_minute_backtest`。
- 窗口：
  - 目标日收盘窗口：`14:30-15:00`。
  - 日线硬容量阈值：订单量 / 日成交量 `1%`。
  - 日线软容量阈值：订单量 / 日成交量 `0.5%`。
- 注意：
  - 目标日分钟证据优先于日线证据。
  - 最近前序交易日收盘窗口只作为数据源质量旁证，不作为关账证据。

## 结果

- 决策：`daily_capacity_improved_close_window_still_not_closed`
- 闸门：`2/5` 通过。
- 硬容量事件：`5`
- 日线成交量为正：`5/5`
- 日线订单量不超过 `1%`：`4/5`
- 目标日收盘窗口分钟成交量为正：`2/5`
- 残余收盘窗口缺口：`3`
- 同日换月配对事件：`2`
- 同日换月配对合约日线成交量为正：`2/2`
- 最大订单量/日成交量：`1.0381%`
- 最大订单量/目标日收盘窗口成交量：`5.1261%`

### 硬事件明细

| 事件 | 日线成交量 | 订单/日成交量 | 目标日收盘窗口成交量 | 状态 |
| --- | ---: | ---: | ---: | --- |
| `SM501.CZCE 2024-12-05` | `77,572` | `0.5762%` | `8,720` | 收盘窗口已关账 |
| `SM505.CZCE 2024-12-19` | `84,405` | `0.5924%` | `11,380` | 收盘窗口已关账 |
| `AP505.CZCE 2025-04-18` | `32,241` | `0.8654%` | `0` | 日线容量为正，但目标日收盘窗口缺失 |
| `lc2505.GFEX 2025-04-21` | `39,047` | `0.8887%` | `0` | 同日 `lc2507` 成交量 `196,466`，但旧合约目标日收盘窗口缺失 |
| `fu2509.SHFE 2025-08-21` | `48,163` | `1.0381%` | `0` | 同日 `fu2510` 成交量 `348,236`，但旧合约目标日收盘窗口缺失且略超 `1%` |

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit_chart_stage573_stage526_hard_capacity_residual_evidence_audit_v1.png`
- 左上：5 笔硬事件的日线成交量都明显大于订单量，说明这些不是完全死合约；但该图不能单独证明收盘窗口可成交。
- 右上：真正的关键图。`SM501/SM505` 有绿色收盘窗口成交量，`AP505/lc2505/fu2509` 为 0，说明 Stage269 的残余缺口仍存在。
- 左下：`fu2509` 是唯一超过 `1%` 日成交量红线的事件，且只超过约 `0.0381pp`；其余 `AP505/lc2505` 在 `0.86%-0.89%`，属于日线容量边界但未过硬线。
- 右下：`lc2507/fu2510` 两个同日换月配对合约流动性显著强于旧合约，支持后续实盘加入提前换月/拆单监控，而不是简单删除 `lc/fu` 产品。

## 结论

- Stage526 的硬容量证据比 Stage269 时更清楚：5/5 硬事件当天都有日线成交量，且 4/5 订单量不超过日成交量 `1%`。
- 但 Stage526 仍不能宣称“真实交易不存在偏差”：`AP505/lc2505/fu2509` 三笔缺少目标日 `14:30-15:00` 正成交量分钟证据。
- `fu2509` 是唯一真实硬边界事件：订单 `500` 手占旧合约日成交量 `1.0381%`，但同日新合约 `fu2510` 成交量 `348,236`、配对开仓参与率 `0.1436%`，说明更合理的实盘控制是提前换月或拆单，而不是删除产品。
- 本阶段不产生交易规则；它只把执行缺口从“缺少证据”细分为：
  - 日线容量已缓解；
  - 收盘窗口证据未关；
  - 换月配对支持提前换月/拆单监控。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段只验证成交证据，不用收益表现筛事件，不改变参数。
- 运行后判断：不是过拟合。结果没有删除难看的 `fu2509`，反而把它保留为唯一超过 `1%` 的硬边界事件。
- 风险：如果后续直接因为 `fu2509` 这一笔把 `fu` 永久剔除，就是过拟合；正确方向是交易执行层提前换月、拆单和真实成交采样。

## 继续价值反思

- 运行前判断：有价值。真实可成交目标必须逐笔证明回测成交价附近可落地。
- 运行后判断：有价值，但不能继续靠本地历史分钟源单方面关账。
- 下一步：
  - 将 `AP505/lc2505/fu2509` 写入 live execution template 的 P0 监控项。
  - 实盘/SimNow/券商测试时优先采样旧合约临近换月的 signal/submit/fill/VWAP/participation/shortfall。
  - 对 `lc/fu` 换月类事件优先研究“提前换月或拆单监控”，而不是产品黑名单。

## 验证

- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit.py`：通过。
- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage573_stage526_hard_capacity_residual_evidence_audit.py`：通过。
- `.py311/bin/python -m json.tool ...decision...json`：通过。
- 图表已视觉检查。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。本阶段不是新候选或正式突破。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是执行证据细化，不是路线合并或正式候选。
