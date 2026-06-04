# Stage266 Stage526流动性/容量/扩池品种可承载性审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-06-03 00:53 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读容量审计；不改策略、不改参数、不生成交易候选。
- 是否重要突破：否，但属于真实可成交边界的重要证据。
- 是否触发A/B：否。本阶段没有新策略版本进入正式候选，也不修改 Stage526/079。

## 外部调研与判断

- 参考资料：
  - Hurst/Ooi/Pedersen, *A Century of Evidence on Trend-Following Investing*：https://research.cbs.dk/en/publications/a-century-of-evidence-on-trend-following-investing/
  - Chevalier/Darolles, *Futures Market Liquidity and the Trading Cost of Trend Following Strategies*：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3523005
  - `pysystemtrade` backtesting/cost/buffer 文档：https://github.com/robcarver17/pysystemtrade/blob/develop/docs/backtesting.md
- 我的判断：
  - 趋势策略要穿越周期，扩品种池和低相关分散是合理方向，但必须同时审计成本、换手、成交容量和真实可交易性。
  - 本阶段不把成交量/OI占比做成 alpha，也不据此调参；只回答 Stage526 和 Stage541 扩池候选是否存在“纸面成交”风险。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage565_stage526_liquidity_capacity_product_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `STRESS_ORDER_VOLUME_PCT=0.50`
  - `SOFT_ORDER_VOLUME_PCT=0.25`
  - `STRESS_POSITION_OI_PCT=1.00`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage526/Stage541 既有输出，主区间覆盖 2020-01-02 至 2026-05-25。
- 账户规模：Stage526 `61.5万账户权益口径`，Stage541 单品种 `11.5万 sleeve`。
- 成本口径：不重算权益；读取 Stage526/Stage541 已有 `slippage/net_pnl/trade_count`。
- 样本过滤：
  - Stage526：`variant=r080_pc25_maxpos4`，交易事件定义为 `abs(pos_change)>0` 或 `trade_count>0`。
  - Stage541：读取单品种机会图 positions，按产品聚合容量质量。
- 策略/归因口径：
  - `order_volume_to_day_volume_pct = abs(pos_change) / TqSdk daily volume * 100`
  - `peak_position_to_oi_pct = max(abs(start_pos), abs(end_pos)) / TqSdk close_oi * 100`
  - 数据缺口与真实容量压力分开：缺成交量/OI只记为 `data_gap`，不直接等同硬容量压力。

## 结果

- 期末权益：`23,369,505`
- 总收益：`3699.9195%`
- 最大回撤：`-36.2670%`
- Sharpe：`1.6385`
- 总滑点：`1,342,190`
- 总交易次数：`905`
- 胜率：`53.6330%`（非零日胜率）
- 其他关键指标：
  - decision：`liquidity_capacity_caution_selector_not_ready`
  - gates：`6/9`
  - Stage526交易事件：`687`
  - Stage526正成交量覆盖率：`86.0262%`
  - Stage526正持仓量覆盖率：`86.0262%`
  - Stage526 p95订单量/日成交量：`0.1873%`
  - Stage526 max订单量/日成交量：`1.0381%`
  - Stage526硬容量压力事件占比：`0.7278%`
  - Stage526持仓/OI压力事件占比：`0.2911%`
  - 硬容量压力交易日PnL占绝对交易日PnL：`0.2715%`
  - 材料性非核心候选：`6`
  - 材料性非核心容量绿灯：`5`，为 `lu.INE/v.DCE/y.DCE/ao.SHFE/c.DCE`
  - 材料性非核心容量红灯：`0`
  - `al.SHFE` 为黄色，不是订单过大，而是单品种历史容量覆盖率 `85.7143%`，需要补数复核。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage565_stage526_liquidity_capacity_product_audit_report_stage565_stage526_liquidity_capacity_product_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage565_stage526_liquidity_capacity_product_audit_summary_stage565_stage526_liquidity_capacity_product_audit_v1.csv`
- orders/events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage565_stage526_liquidity_capacity_product_audit_stage526_trade_liquidity_events_stage565_stage526_liquidity_capacity_product_audit_v1.csv`
- product quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage565_stage526_liquidity_capacity_product_audit_stage526_product_liquidity_stage565_stage526_liquidity_capacity_product_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage565_stage526_liquidity_capacity_product_audit_single_product_liquidity_stage565_stage526_liquidity_capacity_product_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage565_stage526_liquidity_capacity_product_audit_combined_product_capacity_stage565_stage526_liquidity_capacity_product_audit_v1.csv`
- daily/annual：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage565_stage526_liquidity_capacity_product_audit_annual_liquidity_stage565_stage526_liquidity_capacity_product_audit_v1.csv`
- quality/gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage565_stage526_liquidity_capacity_product_audit_gates_stage565_stage526_liquidity_capacity_product_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage565_stage526_liquidity_capacity_product_audit_decision_stage565_stage526_liquidity_capacity_product_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage565_stage526_liquidity_capacity_product_audit_chart_stage565_stage526_liquidity_capacity_product_audit_v1.png`

## 图表视觉复盘

- 左上图：灰色叉号集中在 2020 和 2026，说明主要是 TqSdk 日成交量/OI覆盖缺口；真实红色容量压力只集中在 2024-2025 少数大单，尤其 `fu2509.SHFE`、`lc2505.GFEX`、`AP505.CZCE`、`SM501/505.CZCE`。
- 右上图：材料性非核心候选整体贴近左侧低容量压力区，`lu/v/y/ao/c` 都是容量绿灯；`al` 是黄色，原因是覆盖率不足，不是已匹配事件容量过大。
- 左下图：扩池单品种里存在明显不可承载尾部，`fb.DCE` 最大订单量/日成交量约 `142%`，说明“扩池”不能无差别放开，必须有容量闸门。
- 右下图：2021-2023 覆盖率为 `100%` 且容量压力很低；2024-2025 出现少量真实容量压力；2026覆盖率骤降到 `15.7895%`，当前不能用 2026 的日成交量/OI审计作强结论。

## 结论

- 本阶段结论：
  - Stage526 当前 50万级别订单量大体可承载：p95订单/日成交量仅 `0.1873%`，硬容量压力事件仅 `0.7278%`，且不是主要亏损来源。
  - 但 Stage526 还不能在容量审计上关账：成交量/OI覆盖率只有 `86.0262%`，且有一次 `fu2509.SHFE` 达到 `1.0381%` 日成交量的边界事件。
  - 低风险扩池不是被流动性直接否决：6个材料性非核心候选里 5个容量绿灯、0个红灯；真正瓶颈仍是 Stage264/263 的选品器与 forward 外生/舆情数据。
  - 不能无差别扩池：非材料性扩池产品存在 `fb.DCE` 这类容量红灯，必须有容量闸门和产品资格审计。
- 是否进入下一步：进入，但不作为新交易规则晋级。
- 下一步：
  - 补 2020/2026 TqSdk 日成交量/OI缺口，特别是 2026 当前持仓/交易品种。
  - 建真实成交滑点采样账本：记录信号价、理论窗口价、submit时间、fill时间、成交价、订单量、当时窗口成交量/OI、实际滑点。
  - 品种选择方向继续按 Stage261/263 累计 `20` 个合格 forward 外生样本和真实舆情/新闻账本，未达标前不做选品收益回测。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有调交易参数，没有选历史盈利品种进入策略，只用独立日成交量/OI审计既有 Stage526/Stage541 事件是否可承载。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但方向要明确。
- 原因：容量审计把“可成交”和“选品alpha”拆开了。现在的证据显示容量不是 Stage526 的主要否决项，但数据覆盖和真实滑点监控仍是实盘前必补项；扩池方向继续有价值，但不能靠宽池本身晋级。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段是 Stage526 真实可成交边界的重要证据。
