# Stage024 真实组合资金与保证金约束验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-25 22:00 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage023 低相关卫星研究候选的真实资金、整数手数、保证金约束复验
- 是否重要突破：否；但属于重要反证
- 是否触发A/B：是；该候选有潜在合入价值，因此按 A/B 思路隔离验证，但本阶段不进入正式 A/B

## 外部调研与判断

- 参考资料：
  - AQR《Demystifying Managed Futures》：时间序列动量/趋势跟踪能够解释管理期货收益，并讨论风险分配、成本和实现问题。
  - SSRN《Trend Following, Risk Parity and Momentum in Commodity Futures》：商品期货趋势跟踪相对简单风险平价调权更关键，风险平价类组合权重调整并不能替代真实策略收益源。
- 我的判断：
  - 组合层低相关收益源是合理方向，但不能只看净值层小数权重。
  - 对 50 万账户而言，整数手数、最小合约规模、保证金占用会改变策略真实暴露；所以 Stage023 必须落到真实资金拆分后再判断。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage324_true_combo_capital_margin.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `TOTAL_CAPITAL=500_000`
  - `C3_CAPITAL=400_000`
  - `SATELLITE_CAPITAL=100_000`
  - 保证金 `watch=60%`、`review=80%`、`reject=100%`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 到 `2026-04-30`，并补 `since_2022/since_2023/since_2024/phase_2024_2025/ytd_2026`
- 账户规模：总资金 `500,000`；C3 独立资金 `400,000`；卫星独立资金 `100,000`
- 成本口径：沿用各自策略默认滑点和回测成本口径
- 样本过滤：不做单品种黑名单，不做事后窗口筛选
- 策略/归因口径：
  - C3：`C_pressure040_supply_headwind`
  - 卫星：`range_reversion_v8_two_stage_stop`
  - 组合：只叠加两条真实资金回测的日盈亏，不做小数手数缩放
  - 保证金：两条腿绝对保证金保守相加，暂不做跨策略同合约净额抵消

## 结果

- 期末权益：全样本组合约 `12,941,335`
- 总收益：全样本组合 `2488.2670%`
- 最大回撤：全样本组合 `-33.7156%`
- Sharpe：全样本组合 `1.4125`
- 总滑点：组合层没有直接重算总滑点；C3 和卫星分别由各自回测引擎输出
- 总交易次数：组合层没有直接重算总交易次数；C3 和卫星分别由各自回测引擎输出
- 胜率：组合层不适用
- 其他关键指标：
  - C3 40 万全样本总收益 `3109.5338%`、最大回撤 `-35.7575%`
  - 卫星 10 万全样本总收益 `3.2000%`、最大回撤 `-3.7566%`
  - 组合相对 C3 收益保留 `80.0206%`
  - 全样本最大保证金/权益 `93.4733%`
  - 全样本 `review` 天数 `11`，`reject` 天数 `0`
  - `since_2022` 组合最大回撤 `-29.9979%`，但最大保证金/权益 `80.4745%`
  - `since_2023` 组合总收益 `410.1490%`、最大回撤 `-28.1254%`
  - `since_2024` 组合总收益 `212.5950%`、最大回撤 `-25.4261%`
  - `ytd_2026` 组合总收益 `-4.6440%`、最大回撤 `-17.0428%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage324_true_combo_capital_margin_report_stage324_true_combo_capital_margin_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage324_true_combo_capital_margin_summary_stage324_true_combo_capital_margin_v1.csv`
- orders：无组合层订单输出；各腿订单由独立回测输出
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage324_true_combo_capital_margin_combo_daily_stage324_true_combo_capital_margin_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage324_true_combo_capital_margin_decision_stage324_true_combo_capital_margin_v1.json`

## 结论

- 本阶段结论：
  - Stage023 的净值层组合不能升级为真实 50 万资金候选。
  - 主要原因不是卫星带来大亏损，而是 10 万资金下卫星几乎无法形成足够有效暴露；同时 C3 从 50 万压到 40 万后，整数手数和资金约束导致自身收益下降、回撤变深。
  - 所以 `80% C3 + 20%卫星` 在净值层过线，但在真实资金拆分下全样本最大回撤仍为 `-33.7156%`，未通过 30% 闸门。
- 是否进入下一步：进入，但不是继续微调 `80/20` 权重。
- 下一步：
  - 停止围绕 `80/20`、`85/15` 继续做小数权重救结果。
  - 若继续组合层方向，应寻找 10 万资金也能有效交易、低相关、低保证金离散度的卫星腿。
  - 或者回到 C3 内部，研究更本质的 2021 旧样本相关暴露状态识别，但不得做黑名单和年份补丁。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合；它是对上一阶段候选的真实约束复验。
- 原因：
  - 本阶段没有新增 alpha 参数，也没有通过微调权重寻找最好结果。
  - 失败后如果继续围绕 `0.19/0.21`、`0.18/0.22` 扫权重，才会变成过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有价值，但 Stage023 当前形状价值下降。
- 原因：
  - 该实验直接说明净值层组合不等于实盘可执行组合，避免了错误晋级。
  - 后续价值在于寻找“资金离散度更低的低相关腿”，而不是继续救这个具体 80/20 组合。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage023 被真实资金约束反证。
- 是否更新 `research/registry.md`：是，更新最新关键阶段和下一步。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要反证，防止后续误判。
