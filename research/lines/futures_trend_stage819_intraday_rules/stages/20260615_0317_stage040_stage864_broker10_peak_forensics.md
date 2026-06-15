# Stage040 Stage864 C9/C4 broker10峰值只读归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 03:18 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因与分钟K视觉复盘；不写新规则、不改正式版、不改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py GitHub：<https://github.com/vnpy/vnpy>
  - backtesting.py 逐 bar 回放文档：<https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html>
- 我的判断：外部资料只提供工程纪律参照，不能直接复制参数。Stage864 的核心是按真实组合路径解释保证金分子、权益分母和成交顺序；不能用事后 broker10 峰值日期、品种或方向直接写黑名单。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage864_stage863_broker10_peak_forensics.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无；本阶段只读 Stage863 固定输出与 Stage861 全量分钟K。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage863/Stage861 全周期输出；Stage864 实际加载相关分钟K `1,448,736` 根、`214` 个合约。
- 账户规模：沿用 Stage863 C4/C9/C10 口径。
- 成本口径：沿用 Stage863 固定成本与滑点口径；本阶段不生成新成交、不新增滑点。
- 样本过滤：只聚焦 C4/C9 broker10 top peak dates、active lots、entry sizing context、stop/retry 事件前窗口和对应分钟K视觉图册。
- 策略/归因口径：C4 为 `stage830_stage819_c2_broker10_100_cap`，C9 为 `stage847_stage819_c4_05r_stop_retry_once`；C10 在 Stage863 已与 C9 完全重合，因此 Stage864 只解释 C4 vs C9。

## 结果

- 期末权益：本阶段不新增回测；引用 Stage863 固定结果，C4 `46,015,805.0`，C9/C10 `50,637,144.6`。
- 总收益：本阶段不新增回测；引用 Stage863 固定结果，C4 `15,238.6017%`，C9/C10 `16,779.0482%`。
- 最大回撤：本阶段不新增回测；引用 Stage863 固定结果，C4 `-47.1915%`，C9/C10 `-42.6313%`。
- Sharpe：本阶段不新增回测；引用 Stage863 固定结果，C4 `1.5996`，C9/C10 `1.6312`。
- 总滑点：本阶段不新增回测；引用 Stage863 固定结果，C4 `3,023,410`，C9/C10 `3,607,030`。
- 总交易次数：本阶段不新增回测；引用 Stage863 固定结果，C4 `678`，C9/C10 `786`。
- 胜率：本阶段不新增回测；引用 Stage863 固定结果，C4 `53.0630%`，C9/C10 `53.5299%`。
- 其他关键指标：
  - C4 broker10 top peak：`2022-04-07`，账户权益 `15,642,213.8`，回撤 `-21.2054%`，broker10 `111.4255%`，当日净 PnL `-1,600,300`。
  - C9 broker10 top peak：`2020-11-23`，账户权益 `908,636.6`，回撤 `-14.8186%`，broker10 `114.3987%`，当日净 PnL `-117,930`。
  - `2020-11-23` C9 相比 C4 的主要 active lot 放大：`AP101.CZCE short` 手数 `+4`、broker10 pct `+3.4789pp`；`rb2101.SHFE long` 手数 `+8`、broker10 pct `+2.8846pp`；`OI101.CZCE long` 手数 `+1`。
  - `2020-11-26` C9-only `jm2101.DCE long` 贡献 broker10 pct `+40.6869pp`，同时 AP/rb/SM 等同路径继续比 C4 更大。
  - `2022-04-07` C9 绝对保证金仍略高于 C4，如 `CF205.CZCE long` 手数 `+4`、保证金 `+85,437`，但因 C9 权益更高，broker10 pct 低于 C4。
  - 入场 sizing context 显示 `AP101 short` C4/C9 分别选 `45/49` 手，估计权益 `1,562,116.6/1,712,611.6`；`rb2101 long` `96/104` 手；`OI101 long` `9/10` 手。核心不是换了入场点，而是同信号在更高权益/更少约束下自然放大。
  - 峰值日前 stop/retry 事件证明 C9 的路径差来自更早的资金曲线改变：`2020-11-23` 前 90 日有 `flat_no_reentry` 2 笔、`flat_retry_failed` 1 笔、`open_after_reentry` 1 笔；`2022-04-07` 前 90 日有 `flat_no_reentry` 3 笔、`flat_retry_failed` 1 笔、`open_after_reentry` 1 笔。
  - 视觉图册生成 `3` 页，覆盖 CF/jm/SM/AP/rb/OI 等关键合约；部分 rb2101 focus-day 分钟K为 `0`，已作为覆盖边界处理。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_report_stage864_stage863_broker10_peak_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_decision_stage864_stage863_broker10_peak_forensics_v1.json`
- orders：不适用，本阶段不生成订单。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_peak_dates_stage864_stage863_broker10_peak_forensics_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_active_lots_stage864_stage863_broker10_peak_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_product_direction_attribution_stage864_stage863_broker10_peak_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_pair_delta_stage864_stage863_broker10_peak_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_entry_sizing_context_stage864_stage863_broker10_peak_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_stop_retry_before_peak_stage864_stage863_broker10_peak_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_atlas_manifest_stage864_stage863_broker10_peak_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_atlas_page001_stage864_stage863_broker10_peak_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_atlas_page002_stage864_stage863_broker10_peak_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage864_stage863_broker10_peak_forensics_atlas_page003_stage864_stage863_broker10_peak_forensics_v1.png`

## 结论

- 本阶段结论：决策为 `stage864_peak_forensics_no_rule_yet`。C9 的 broker10 峰值风险不能归因为某个具体峰值品种、日期或方向，也不是 C10 同品种同方向加仓预算锁能拦住的路径。更本质的机制是：早期 stop/retry 改变权益和资金占用路径，后续相同或相近信号在更高权益、更少约束下获得更大 sizing；当权益分母回落时，broker10 峰值自然放大。
- 是否进入下一步：是，但只进入只读反事实，不进入候选、不触发 A/B。
- 下一步：Stage865 应设计一个实时可判定的账户层 sizing brake 代理，先只读检验其是否能在 broker10 峰值形成前触发，并且不大面积误伤右尾。禁止用 `2020-11-23`、`2022-04-07`、AP/rb/jm/CF 或方向做黑名单；也不继续做 C10 锁的小变体。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段目标是解释固定回放中的 broker10 峰值，不新增阈值和策略参数。
- 运行后判断：仍不是过拟合。
- 原因：脚本只读取 Stage863 固定 C4/C9/C10 输出和 Stage861 全量分钟K，按真实峰值日做归因与视觉复核；没有生成任何日期、品种、方向、R 倍数、时间窗或重试次数过滤。相反，本阶段明确否决按峰值样本写黑名单。

## 继续价值反思

- 运行前判断：有继续价值。Stage863 已证明 C9 在全量分钟K口径下相对 C4 增收、降回撤、升 Sharpe，但 broker10 峰值更高，必须先解释风险路径。
- 运行后判断：仍有继续价值，但价值不在继续救 C10，而在账户层 sizing brake 的低自由度只读反事实。
- 原因：Stage864 已把矛盾从“同品种 stop/retry 后加仓”推进到“权益路径改变后的组合级 sizing 放大”。这比按单品种或单日期修补更接近可穿越周期的风险治理问题；但还没有足够证据把它写成实盘规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage040 当前状态和下一步。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、跨线合并或重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段只读归因，不属于重要突破、路线废弃、正式候选或跨线合并。
