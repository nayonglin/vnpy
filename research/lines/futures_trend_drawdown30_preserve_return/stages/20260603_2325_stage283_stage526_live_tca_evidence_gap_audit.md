# Stage283 Stage526 live TCA 证据缺口审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-03 23:25 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读执行证据审计；不改策略；不做收益回测；不新增交易候选。
- 是否重要突破：否，但属于实盘可成交性关账前置边界。
- 是否触发A/B：否。没有新增可晋级交易版本。

## 外部调研与判断

- 参考资料：
  - CME Transaction Cost Analysis for Futures：https://www.cmegroup.com/education/files/TCA-4.pdf
  - tcapy open-source TCA library：https://github.com/cuemacro/tcapy
  - Optimality of VWAP Execution Strategies under General Shaped Market Impact Functions：https://arxiv.org/abs/1605.03683
  - Execution and block trade pricing with optimal constant rate of participation：https://arxiv.org/abs/1210.7608
- 我的判断：
  - 真实成交偏差不能只靠回测滑点或分钟代理关账。
  - 正确的 TCA 证据至少要合并 order/fill 与行情，并同时看 arrival price、VWAP、implementation shortfall、participation、unfilled/reject。
  - 当前 Stage568/575 已经有模板，但模板不是实盘证据；必须扫描实际 fill/ledger 后按 P0 close condition 计数。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage583_stage526_live_tca_evidence_gap_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `REQUIRED_VALID_SAMPLES_PER_P0=3`
  - `MAX_VWAP_COST_BPS=50.0`
  - `MAX_IMPLEMENTATION_SHORTFALL_BPS=75.0`
  - `MAX_PARTICIPATION_PCT=25.0`
  - required fields：`signal_generated_at/signal_price/order_submit_at/order_submit_price/order_type/fill_first_at/fill_last_at/avg_fill_price/filled_volume/unfilled_volume/actual_implementation_shortfall_bps/actual_vs_window_vwap_bps`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage575 P0 watchlist 与当前 `backtest_outputs` 中所有 `live/evidence/execution/fill/ledger/shadow/simnow/ctp` CSV 候选文件。
- 账户规模：不适用。
- 成本口径：不适用；本阶段不是收益回测。
- 样本过滤：
  - P0 只认 Stage575 的 `fu2509.SHFE/lc2505.GFEX/AP505.CZCE`。
  - 证据文件扫描 `585` 个 CSV，其中 `12` 个文件匹配 P0 行。
  - 只有同时满足完整 fill、VWAP、implementation shortfall、participation、unfilled=0、无 broker reject/filter 的行才计入有效 TCA 样本。
- 策略/归因口径：
  - 不改 Stage526。
  - 不把历史代理、模板、分钟候选当作 live fill。
  - 不把扫描到 P0 行当作关账证据。

## 结果

- 期末权益：不适用；本阶段无收益回测。Stage526 参考口径仍为 `23,369,505`。
- 总收益：不适用。Stage526 参考口径仍为 `3699.9195%`。
- 最大回撤：不适用。Stage526 参考口径仍为 `-36.2670%`。
- Sharpe：不适用。Stage526 参考口径仍为 `1.6385`。
- 总滑点：不适用。Stage526 参考口径仍为 `1,342,190`。
- 总交易次数：不适用。Stage526 参考口径仍为 `905`。
- 胜率：不适用。Stage526 参考口径仍为 `53.6330%`。
- 其他关键指标：
  - 决策：`live_tca_evidence_gap_not_closed`
  - 闸门通过：`2/6`
  - P0：`fu2509.SHFE/lc2505.GFEX/AP505.CZCE`
  - 有效 live TCA 样本：`0/9`
  - P0 close gate：`0/3`
  - evidence files scanned：`585`
  - with P0 rows：`12`
  - zero execution bias claim：`not allowed`

## 图表视觉复盘

- 左上图：三个 P0 的有效样本都是 `0/3`，红色剩余柱完整保留，说明每个 P0 都还缺 `3` 个有效样本。
- 右上图：required TCA field value coverage 全红；Stage568/575 虽然有列，但 P0 行没有真实 submit/fill/avg_fill/VWAP/shortfall 值。
- 左下图：匹配到 P0 的主要是 Stage568/575 模板、Stage573 分钟候选和历史代理文件；valid live samples 均为 `0`，没有发现能关账的真实 fill 文件。
- 右下图：只通过 `p0_watchlist_loaded` 和 `evidence_files_scanned`，真实成交字段、有效样本、P0 close、zero-bias claim 全失败。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage583_stage526_live_tca_evidence_gap_audit_report_stage583_stage526_live_tca_evidence_gap_audit_v1.md`
- evidence inventory：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage583_stage526_live_tca_evidence_gap_audit_evidence_inventory_stage583_stage526_live_tca_evidence_gap_audit_v1.csv`
- p0 close gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage583_stage526_live_tca_evidence_gap_audit_p0_close_gates_stage583_stage526_live_tca_evidence_gap_audit_v1.csv`
- field completeness：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage583_stage526_live_tca_evidence_gap_audit_field_completeness_stage583_stage526_live_tca_evidence_gap_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage583_stage526_live_tca_evidence_gap_audit_gates_stage583_stage526_live_tca_evidence_gap_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage583_stage526_live_tca_evidence_gap_audit_decision_stage583_stage526_live_tca_evidence_gap_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage583_stage526_live_tca_evidence_gap_audit_chart_stage583_stage526_live_tca_evidence_gap_audit_v1.png`

## 结论

- 本阶段结论：`live_tca_evidence_gap_not_closed`
- 是否进入下一步：进入真实成交/独立分钟证据收集，不进入交易候选变更。
- 下一步：
  - 对 `fu2509.SHFE/lc2505.GFEX/AP505.CZCE` 分别累计 `3` 个可比 live fill 或独立全日分钟证据。
  - 每个样本必须满足：filled=100%、unfilled=0、actual_vs_window_vwap_bps <= `50`、implementation shortfall <= `75`、participation <= `25%`、无 broker reject/filter。
  - 把 SimNow/CTP/券商测试回报写入 Stage575 live evidence template 或同结构账本。
  - 未完成前，Stage526 只能说“正常成本主候选”，不能说“真实交易不存在偏差”。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段只审计执行证据，不改策略、品种、参数、入场、出场或 sizing。
  - 扫描规则和 P0 close condition 在看到结果前固定。
  - 结果没有被用来优化收益，只用来约束可成交性声明。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - 目标要求“真实交易不存在偏差”，当前证据明确不足，且缺口可操作。
  - 下一步必须来自真实 SimNow/CTP/券商成交回报或独立全日分钟源，而不是继续回测调参。
  - 若真实成交长期证明短缺或劣化，Stage526 的实盘声明必须降级。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，当前线最新阶段需要刷新。
- 是否追加根目录 `memory.md/back_log.md`：是。该阶段直接影响“真实交易不存在偏差”的目标边界。
