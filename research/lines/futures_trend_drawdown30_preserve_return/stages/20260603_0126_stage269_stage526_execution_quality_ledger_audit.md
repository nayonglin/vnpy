# Stage269 Stage526真实成交质量账本审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 01:26 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读执行质量/TCA账本审计；不改策略、不改入场/出场、不生成新交易候选。
- 是否重要突破：否，但属于实盘可执行性关键基础设施。
- 是否触发A/B：否。本阶段不形成新策略版本。

## 外部调研与判断

- 参考资料：
  - CFA Institute `Trading Costs and Electronic Markets`：交易成本需要拆成显性成本、隐性成本、VWAP 成本估计与 implementation shortfall。
  - CFA Institute Research Foundation `Trading and Electronic Markets`：交易成本估计和 VWAP/implementation shortfall 都要求保留订单与成交的详细记录。
- 我的判断：
  - Stage526 当前不应通过继续调策略参数来解释执行风险；真实可成交目标需要逐笔账本，把回测参考价、真实成交均价、窗口 VWAP、参与率、未成交/撤单和实际滑点放在一张表里。
  - 本阶段只建立账本和历史分钟代理，不把任何偏差事件转成交易过滤规则，因此不是过拟合。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage568_stage526_execution_quality_ledger_audit.py`
- 修改策略脚本：无。
- 删除脚本：无。
- 新增参数/字段：
  - 实盘成交字段 `20` 个：`signal_generated_at`、`signal_price`、`order_submit_at`、`order_submit_price`、`order_type`、`limit_price`、`fill_first_at`、`fill_last_at`、`avg_fill_price`、`filled_volume`、`cancelled_volume`、`unfilled_volume`、`commission_cash`、`actual_slippage_cash`、`actual_implementation_shortfall_bps`、`actual_vs_window_vwap_bps`、`account_equity_before`、`broker_margin_before`、`broker_margin_rate_note`、`operator_note`。
  - 分钟代理质量：`full_like_positive_volume`、`partial_positive_volume`、`full_like_zero_volume`、`partial_zero_volume`、`missing`。
  - 收盘执行窗口：last5/last15/last30 优先限定为日盘 `14:30-15:00`，避免把同一自然日夜盘误当成收盘窗口。
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据来源：Stage565 交易容量事件、Stage566 缺口回填结果、Stage567 硬容量事件、本地 TqSdk 分钟数据。
- 账户/策略口径：Stage526 `r080_pc25_maxpos4`，沿用正常成本与真实下一窗口研究链路。
- 成本口径：本阶段不重算收益，只审计回测参考价相对分钟 VWAP 与执行窗口成交量的偏差。
- 价格偏差闸门：回测成交价相对收盘 last5 VWAP 的 95 分位偏差不超过 `50bps`。
- 窗口参与率闸门：订单量 / 收盘 last15 分钟成交量 95 分位不超过 `25%`。

## 结果

- 决策：`execution_quality_ledger_ready_with_window_participation_monitor`
- Gates：`6/7`
- 期末权益：`23,369,505`
- 总收益：`3699.9195%`
- 最大回撤：`-36.2670%`
- Sharpe：`1.6385`
- 总滑点：`1,342,190`
- 总交易次数：`905`
- 胜率：非零日胜率 `53.6330%`

### 关键指标

| 指标 | 数值 |
| --- | ---: |
| Stage526 交易事件数 | `687` |
| 分钟代理覆盖 | `680/687 = 98.9811%` |
| 完整近似日且正成交量覆盖 | `614/687 = 89.3741%` |
| 硬容量事件 | `5` |
| 硬容量事件有任意分钟代理 | `5/5` |
| 硬容量事件有收盘 last15 正成交量 | `2/5` |
| 回测价 vs 收盘 last5 VWAP p50 | `3.8660 bps` |
| 回测价 vs 收盘 last5 VWAP p95 | `19.7420 bps` |
| 回测价 vs 收盘 last5 VWAP max | `47.4718 bps` |
| 订单 / 收盘 last15 成交量 p50 | `0.2788%` |
| 订单 / 收盘 last15 成交量 p95 | `2.9121%` |
| 订单 / 收盘 last15 成交量 max | `10.1768%` |
| 窗口参与率 >25% 事件 | `0` |
| 价格偏差 >50bps 事件 | `28` |

### 失败闸门

- `hard_capacity_events_have_last15_volume` 未通过：`2/5`。
- 细节：
  - `SM501.CZCE 2024-12-05`：收盘窗口 `14:30-14:59`，last15 成交量 `5650`，订单参与率 `7.9115%`。
  - `SM505.CZCE 2024-12-19`：收盘窗口 `14:30-14:59`，last15 成交量 `7807`，订单参与率 `6.4045%`。
  - `lc2505.GFEX 2025-04-21`、`AP505.CZCE 2025-04-18`、`fu2509.SHFE 2025-08-21` 只有 `09:00-09:15` 零成交片段，不能证明收盘窗口可成交，必须补真实成交回报或真实日线/分钟源。

## 图表视觉复盘

- 图表：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage568_stage526_execution_quality_ledger_audit_chart_stage568_stage526_execution_quality_ledger_audit_v1.png`
- 左上图：`614` 个事件有完整近似日且正成交量分钟代理，历史代理覆盖足够高；但 `59` 个 partial zero、`7` 个 full-like zero、`7` 个 missing 不能被当成实盘可成交证据。
- 右上图：修正为 `14:30-15:00` 收盘窗口后，价格偏差点整体收敛到 `50bps` 以内，说明 Stage526 回测 close 与收盘窗口 VWAP 大体一致；但这仍只是历史代理，不替代真实成交回报。
- 左下图：最高收盘窗口参与率为 `SH409.CZCE 2024-07-03` 的 `10.1768%`，没有事件超过 `25%` 警戒线，说明当前主要不是“收盘窗口吃不下单”的普遍问题。
- 右下图：硬容量事件中 `SM501/SM505` 的窗口成交量可观测，`lc/AP/fu` 三笔红柱为 `0` 是证据缺失，不是已证明低风险。

## 输出文件

- ledger：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage568_stage526_execution_quality_ledger_audit_execution_quality_ledger_stage568_stage526_execution_quality_ledger_audit_v1.csv`
- live template：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage568_stage526_execution_quality_ledger_audit_live_execution_ledger_template_stage568_stage526_execution_quality_ledger_audit_v1.csv`
- minute proxy：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage568_stage526_execution_quality_ledger_audit_minute_proxy_by_event_stage568_stage526_execution_quality_ledger_audit_v1.csv`
- top window：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage568_stage526_execution_quality_ledger_audit_top_window_participation_stage568_stage526_execution_quality_ledger_audit_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage568_stage526_execution_quality_ledger_audit_summary_stage568_stage526_execution_quality_ledger_audit_v1.csv`
- gates：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage568_stage526_execution_quality_ledger_audit_gates_stage568_stage526_execution_quality_ledger_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage568_stage526_execution_quality_ledger_audit_decision_stage568_stage526_execution_quality_ledger_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage568_stage526_execution_quality_ledger_audit_report_stage568_stage526_execution_quality_ledger_audit_v1.md`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage568_stage526_execution_quality_ledger_audit_chart_stage568_stage526_execution_quality_ledger_audit_v1.png`

## 结论

- 本阶段结论：真实成交质量账本已经可用，可以作为 Stage526/079 后续影子盘与实盘执行偏差采样模板。
- 但这不等于 Stage526 已经“真实交易不存在偏差”；当前只能说明历史分钟代理下，普通事件的收盘窗口参与率和 close-vs-VWAP 偏差大体可控。
- 未关账项：`lc2505/AP505/fu2509` 三个硬容量事件缺少收盘窗口正成交量证据；未来必须通过真实成交回报、券商成交明细或独立日线/分钟源补证。
- 下一步：把 SimNow/CTP/券商测试的每笔真实成交回报写入 live template，同步记录 signal/submit/fill/VWAP/participation/shortfall，形成日常执行偏差监控。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：本阶段没有改变交易规则，也没有删除失败事件；所有缺口和偏差都进入账本，只用于执行监控优先级。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：目标要求真实可成交且不存在偏差，必须把“回测价是否能成交”变成逐笔可审计字段；该账本已经把抽象滑点倍率落成可持续采样结构。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是执行监控基础设施，不是正式候选或重大收益突破。
