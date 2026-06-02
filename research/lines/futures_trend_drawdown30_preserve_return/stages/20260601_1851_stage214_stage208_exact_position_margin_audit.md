# Stage214 Stage208精确持仓保证金审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-06-01 18:51 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读部署约束审计；用真实 C3 逐日持仓重建保证金，不新增策略信号，不修改入场/出场，不扫参数。
- 是否重要突破：是。Stage213 的保证金代理显著低估 `risk060` 实际持仓保证金，Stage214 改变部署判断。
- 是否触发A/B：否。当前是固定候选风险审计，不是新候选接入。

## 外部调研与判断

- 参考资料：
  - SHFE Clearing / daily mark-to-market and margin: https://www.shfe.com.cn/eng/services/investor/Investor_clearing/
  - SHFE General Exchange Rules / margin definition and daily mark-to-market: https://www.shfe.cn/eng/services/Rules/SHFERules/202107/t20210721_826974.html
  - CFFEX rules / margin, forced liquidation, risk alert: https://www.cffex.com.cn/en_new/fzhygz/
  - vn.py GitHub：`https://github.com/vnpy/vnpy`
- 我的判断：期货真实部署首先被逐日持仓保证金、券商加收和强平风险约束，而不是只被最大回撤约束。GitHub/开源实现层面没有比本地 vn.py 回测引擎的持仓账本更可靠的替代证据；本阶段应以本地 `build_positions_df(engine)` 重建的逐日持仓作为比 Stage213 代理口径更强的审计证据。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage513_stage208_exact_position_margin_audit.py`
- 修改脚本：
  - 同上。修正报告结论与 decision next_step，确保 `not_ready` 标签、图表解读和结论一致。
- 删除脚本：无。
- 新增参数：无策略参数。审计口径固定为 `risk060_clean/risk070_clean + true-carried Stage103 xsmom`，成本压力 `1x/2x/3x`，margin cap `100/95/90`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-05-25，沿用 Stage208/209 日度权益与 xsmom 真成交账本。
- 账户规模：Stage208 原账户权益路径；额外现金只在部署资金口径中计算，不改变交易路径。
- 成本口径：基础真实成交成本 + `1x/2x/3x` 成本压力。
- 样本过滤：无日期、品种、坏窗口过滤。
- 策略/归因口径：
  - C3 部分重跑固定 `stage079_next_real_risk060_clean` 和 `stage079_next_real_risk070_clean`，只为抽取每日 `end_pos/close_price/contract_size/margin_ratio`。
  - C3 精确保证金：`abs(end_pos) * close_price * contract_size * margin_ratio`。
  - 组合保证金：C3 精确保证金 + Stage208 xsmom true margin，再乘 broker10 加收倍数。

## 结果

- `risk060 + true xsmom`：
  - 期末权益：`20,682,740`
  - 总收益：`3263.0472%`
  - 最大回撤：`-36.2870%`
  - Sharpe：`1.2291`
  - 总滑点：`1,231,020`
  - 总交易次数：`1,220`
  - 胜率：非零日胜率 `52.8614%`
  - 其他关键指标：1x 精确 broker10 最大保证金/权益 `138.9327%`，穿 `100%` 共 `17` 天，穿 `90%` 共 `31` 天；2x 成本最大回撤 `-38.9342%`。
- `risk070 + true xsmom`：
  - 期末权益：`21,210,535`
  - 总收益：`3348.8675%`
  - 最大回撤：`-38.5861%`
  - Sharpe：`1.1674`
  - 总滑点：`1,228,400`
  - 总交易次数：`1,215`
  - 胜率：非零日胜率 `52.4887%`
  - 其他关键指标：1x 精确 broker10 最大保证金/权益 `140.3161%`，穿 `100%` 共 `25` 天，穿 `90%` 共 `36` 天；2x 成本最大回撤 `-41.4962%`，DD40 失败。
- 部署现金口径：
  - `risk060` 若要求 broker10<=100% 且 DD40，需要额外现金约 `2,700,105`，部署收益 `605.3426%`，相对 Stage079 部署收益保留 `12.2359%`。
  - `risk060` 若要求 broker10<=90% 且 DD40，需要额外现金约 `3,770,706`，部署收益 `457.5715%`，相对 Stage079 部署收益保留 `9.2490%`。
  - `risk070` 若要求 broker10<=90% 且 DD40，需要额外现金约 `3,571,190`，部署收益 `491.9876%`，相对 Stage079 部署收益保留 `9.9446%`。
- 代理口径差异：
  - Stage213 `risk060` 代理最大 broker10 保证金/权益为 `96.4348%`、穿100% `0` 天；Stage214 精确持仓为 `138.9327%`、穿100% `17` 天，最大差 `42.4980pp`。
  - Stage213 `risk070` 代理为 `122.7492%`、穿100% `8` 天；Stage214 精确持仓为 `140.3161%`、穿100% `25` 天。
- 峰值归因：
  - `risk060` 最大保证金日为 `2025-01-06`：账户权益 `6,935,305`，C3 精确保证金 `8,603,052`，xsmom 保证金 `156,411`，broker10 总保证金 `9,635,410`，保证金/权益 `138.9327%`。
  - 当日 C3 保证金主要来自 `cu.SHFE 2,561,280`、`fu.SHFE 2,509,500`、`lc.GFEX 1,211,496`、`SA.CZCE 1,090,886`、`SM.CZCE 633,499`、`FG.CZCE 596,390`。

## 图表视觉复盘

- 左上保证金/权益曲线显示 `risk060/risk070` 都多次穿越 `100%`，2025 年初尖峰最明显；这不是单个极端点，而是多段名义持仓拥挤。
- 左下回撤曲线显示 `risk060` 回撤仍守 DD40，`risk070` 则在成本压力下更脆；所以本阶段的问题不是 alpha 消失，而是资金约束不通过。
- 右上组件图显示 `risk060` 保证金几乎全部来自 C3 主体，xsmom 只是边际叠加；继续调 xsmom 参数不能解决核心保证金问题。
- 右下现金图显示压到 broker10<=90% 需要数百万额外现金，部署资金收益率被摊薄到当前目标不可接受的水平。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage513_stage208_exact_position_margin_audit_report_stage513_stage208_exact_position_margin_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage513_stage208_exact_position_margin_audit_decision_stage513_stage208_exact_position_margin_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage513_stage208_exact_position_margin_audit_chart_stage513_stage208_exact_position_margin_audit_v1.png`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage513_stage208_exact_position_margin_audit_margin_daily_stage513_stage208_exact_position_margin_audit_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage513_stage208_exact_position_margin_audit_c3_positions_stage513_stage208_exact_position_margin_audit_v1.csv`
- deployment matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage513_stage208_exact_position_margin_audit_deployment_matrix_stage513_stage208_exact_position_margin_audit_v1.csv`
- event days：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage513_stage208_exact_position_margin_audit_event_days_stage513_stage208_exact_position_margin_audit_v1.csv`
- product days：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage513_stage208_exact_position_margin_audit_top_margin_product_days_stage513_stage208_exact_position_margin_audit_v1.csv`
- validation：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage513_stage208_exact_position_margin_audit_validation_stage513_stage208_exact_position_margin_audit_v1.csv`

## 结论

- 本阶段结论：`risk060 + true xsmom` 不能晋级部署候选。它在收益和 DD40 上仍有价值，但精确逐日持仓保证金穿透真实资金约束；Stage213 的代理保证金结论需要作废。
- 是否进入下一步：进入下一步，但不是继续把 `risk060` 当候选精修。
- 下一步：先复盘 exact-vs-proxy 保证金差异来源，确认合约乘数、metadata margin_ratio、持仓账本和 broker10 加收是否一致；若确认无误，转向更低名义持仓/保证金感知结构，而不是扫 `risk=0.61/0.62`、ATR/K线阈值、xsmom 参数或坏品种过滤。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有改交易规则、信号、品种池、日期或参数；只是把 Stage213 的代理保证金替换为固定候选的逐日持仓保证金回放。负向结果也被保留并更新结论，没有救参。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但方向改变。
- 原因：当前目标仍未完成；继续价值在“真实资金约束下找可部署结构”，而不是在已失败的代理口径上继续做收益优化。Stage214 说明如果保证金数据无误，当前 `risk060/risk070 + true xsmom` 都不满足“保留大部分收益且真实部署无偏差”的目标。

## 合入建议

- 是否更新本线 `LINE.md`：是，Stage213 的 `risk060` 部署优先结论需要被 Stage214 覆盖。
- 是否更新 `research/registry.md`：是，当前研究线最新关键阶段应改为 Stage214。
- 是否追加根目录 `memory.md/back_log.md`：是。该阶段是重要负向突破，会影响后续所有实盘部署判断。
