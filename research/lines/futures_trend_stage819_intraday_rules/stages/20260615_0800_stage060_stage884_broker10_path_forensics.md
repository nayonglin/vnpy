# Stage060 Stage884 Stage883 broker10 路径归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 08:00 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage883 固定 1 手 sleeve 的只读 broker10 路径归因和分钟K视觉复盘；不新增交易规则、不改官方正式版、不改官方候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。属于风险归因边界确认，不是正式候选突破。
- 是否触发正式 A/B：否。C17 已在 Stage059 判定不推广；本阶段只是解释风险来源，不进入正式候选、不写根目录 `back_log.md`。
- 决策：`stage884_broker10_has_exposure_signal_needs_readonly_followup`

## 外部调研与判断

- vn.py/VeighNa 官方项目定位支持多合约组合策略回测与实盘框架；本阶段继续用事件驱动组合路径解释保证金压力，而不是单笔代理收益。
- Turtle / 趋势跟随 pyramiding 资料强调 volatility-normalized sizing 与组合风险控制；顺势加仓的核心约束不是是否加在盈利后，而是组合总 heat 是否可生存。
- Backtrader order execution docs 强调回测必须尊重成交语义；因此本阶段只解释 Stage883 已生成的真实组合路径，不用事后最优价或未来收益标签造新规则。
- CFTC stop-loss 风险材料提示止损纪律不能消除滑点、缺口和流动性风险；所以 Stage883 的入场日实时止损成立，也不等于账户层 broker10 风险自动消失。
- 我的判断：Stage883 失败的本质不是 `+0.5R` 或 `1手` 这两个参数还需微调，而是新增右尾参与直接扩大持仓保证金分子；若继续救 sleeve 手数、R 倍数、品种或年份，就是过拟合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage884_stage883_broker10_path_forensics.py`
- 新增输出前缀：`qmt_roll_stage884_stage883_broker10_path_forensics_*`
- 新增交易规则：无。
- 新增参数：无交易参数；新增只读归因维度：
  - C17 top broker10 峰值分子/分母拆解。
  - C17 vs C9 broker10 delta 的 denominator effect 与 exposure effect。
  - 峰值日 active lot product-direction 归因。
  - focus date 前累计 realized PnL 缺口归因。
  - active lot 分钟K atlas。
- 修改参数：无官方配置修改；C4、C9、C17 均保持 Stage883 输出原样。
- 删除参数：无。

## 回测参数

- 数据区间：沿用 Stage883 / Stage847 / Stage863 全周期 `2018-01-01 -> 2026-05-29`。
- 上游候选：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 账户规模：`300000`
- 分钟数据：Stage861 full minute bars，加载 `1,479,592` 根、`216` 个合约。
- 对照：
  - C4：`stage830_stage819_c2_broker10_100_cap`
  - C9：`stage847_stage819_c4_05r_stop_retry_once`
  - C17：`stage883_stage819_c9_progress_pyramid_sleeve1_once`
- 本阶段未重跑新交易臂；只读取 Stage883 曲线、closed lots、entry risk、active lots 与分钟K做路径归因。
- 不扫描 progress R、sleeve 手数、止损位置、品种、方向、年份、broker 阈值或分钟窗口。

## 源结果复述

### C17 结果

- 期末权益：`51,683,814.65`
- 总收益：`17,127.9382%`
- 最大回撤：`-41.1625%`
- Sharpe：`1.6223`
- 总滑点：`3,921,000`
- 总交易次数：`1,051`
- 胜率：`53.4863%`
- max broker10 margin/equity：`127.4316%`
- p95 broker10 margin/equity：`63.7936%`

### 相对 C9

- 期末权益多：`+1,046,670.05`
- 最大回撤改善：`+1.4687pp`
- Sharpe 下降：`-0.0088`
- max broker10 恶化：`+13.0329pp`
- p95 broker10 恶化：`+2.2692pp`
- 结论：收益和回撤表面有改善，但风险峰值不通过。

## 新增归因结果

### Top10 broker10 机制

- C17 top10 broker10 峰值中，`10/10` 被归因为 `exposure_numerator_expansion`。
- 这与 Stage871/C13 不同：C13 的 broker10 恶化主要是前序右尾被砍后权益分母压缩；C17 则是直接新增或改变 active exposure，让保证金分子变大。

### C17 vs C9 分子/分母拆解

- `2020-10-15`：C17 broker10 `127.4316%`，C9 `78.3721%`，delta `+49.0595pp`；denominator effect `+6.5422pp`，exposure effect `+42.5172pp`。
- `2020-10-16`：C17 `113.0928%`，C9 `76.4447%`，delta `+36.6481pp`；denominator effect `-1.8488pp`，exposure effect `+38.4969pp`。
- `2020-11-23`：C17 `109.9356%`，C9 `114.3987%`，delta `-4.4631pp`；denominator effect `-25.8498pp`，exposure effect `+21.3866pp`。
- `2021-02-23`：C17 `100.6120%`，C9 `100.1638%`，delta `+0.4482pp`；denominator effect `-22.3238pp`，exposure effect `+22.7720pp`。
- `2022-02-16`：C17 `94.1665%`，C9 `92.6119%`，delta `+1.5547pp`；denominator effect `-18.4547pp`，exposure effect `+20.0093pp`。
- 判断：若 C17 总 broker10 delta 有时不比 C9 更差，是因为更高权益分母抵消了分子扩张；这不是 sleeve 安全，而是运气更好的权益路径暂时托住了风险比值。

### 峰值日 active exposure 归因

- `2020-10-15 jm.DCE long`：broker10 贡献 `+77.1943pp`，broker10 margin `496,256.508`，volume `19`。
- `2020-10-15 ru long`：`+57.3919pp`，broker10 margin `368,953.2`，volume `14`。
- `2020-10-15 CF.CZCE long`：`+55.1697pp`，broker10 margin `354,667.5`，volume `25`。
- `2020-11-20 AP.CZCE short`：`+64.8107pp`，broker10 margin `855,243.18`，volume `61`。
- `2020-11-20 rb.SHFE long`：`+59.7080pp`，broker10 margin `787,908`，volume `127`。
- `2020-11-23 AP.CZCE short`：`+73.6476pp`，broker10 margin `864,543.24`，volume `61`。
- 判断：压力不是单个品种名字本身，而是 C17 在若干趋势簇上扩大或保留了更大的 product-direction active exposure；不能写 `jm/AP/rb` 黑名单。

### 累计 PnL 缺口

- `2022-02-16 OI.CZCE long`：C17 vs C9 累计 realized PnL `-1,365,840`。
- `2022-02-16 ru.SHFE long`：`-878,987`。
- `2022-02-16 rb.SHFE long`：`-412,821`。
- `2022-02-16 lh.DCE long`：`-313,240`。
- `2022-02-16 cu.SHFE long`：`-276,770`。
- 判断：后期压力还叠加了 sleeve 分支自身的 product-direction 累计亏损缺口；它不是单纯“多赚后权益更高”的免费右尾。

## 视觉复核

- summary chart 非空：上图显示 C17 vs C9 的 broker10 delta 中，橙色 exposure effect 在 top10 峰值日持续为正；下图显示 C17 broker10 margin 通常高于 C9，只是部分日期被更高权益分母抵消。
- atlas page001 非空：`OI105.CZCE long`、`AP101.CZCE short` 等 active lot 分钟K显示，Stage884 复盘的是峰值日仍在场的真实 active lot，而不是事后挑选平仓后收益。
- atlas page002/page003 已生成：用于后续查看 C17 峰值日更多 product-direction active lot 的分钟路径。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage884_stage883_broker10_path_forensics_report_stage884_stage883_broker10_path_forensics_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage884_stage883_broker10_path_forensics_decision_stage884_stage883_broker10_path_forensics_v1.json`
- peak dates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage884_stage883_broker10_path_forensics_peak_dates_stage884_stage883_broker10_path_forensics_v1.csv`
- active lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage884_stage883_broker10_path_forensics_active_lots_stage884_stage883_broker10_path_forensics_v1.csv`
- product-direction attribution：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage884_stage883_broker10_path_forensics_product_direction_attribution_stage884_stage883_broker10_path_forensics_v1.csv`
- pair delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage884_stage883_broker10_path_forensics_pair_delta_stage884_stage883_broker10_path_forensics_v1.csv`
- denominator decomposition：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage884_stage883_broker10_path_forensics_denominator_decomposition_stage884_stage883_broker10_path_forensics_v1.csv`
- cumulative pnl delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage884_stage883_broker10_path_forensics_cumulative_pnl_delta_stage884_stage883_broker10_path_forensics_v1.csv`
- entry context：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage884_stage883_broker10_path_forensics_entry_context_stage884_stage883_broker10_path_forensics_v1.csv`
- summary chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage884_stage883_broker10_path_forensics_summary_chart_stage884_stage883_broker10_path_forensics_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage884_stage883_broker10_path_forensics_atlas_page001_stage884_stage883_broker10_path_forensics_v1.png` 至 `page003`

## 结论

- Stage884 确认 Stage883/C17 的 broker10 问题主要来自持仓保证金分子扩大，而不是权益分母被削弱。
- C17 的收益和回撤改善不能掩盖账户压力：它把 right-tail sleeve 的收益换成了更高的 product-direction active exposure，top10 峰值日全部呈现 exposure numerator expansion。
- 停止 sleeve / pyramiding 分支的结论进一步加固：不做 `2手/3手`、progress R、止损位置、品种、方向、年份或 broker10 日期黑名单。
- 若继续本线，只能转到持仓层压力治理或新的低自由度外生信息源；但持仓层治理也必须避免按峰值日期/品种补丁化，先做只读压力状态定义，不能直接写规则。

## 过拟合反思

- 运行前判断：否。本阶段是解释 Stage883 失败来源，不用局部样本选择新阈值，也不新增交易规则。
- 运行后判断：否，但继续围绕 sleeve 参数救援会过拟合。`10/10` top broker10 峰值显示分子扩张是系统性结果，不是一个可通过小数阈值修掉的偶然点。

## 继续价值反思

- 运行前判断：有价值。Stage883 同时多赚和改善回撤，却恶化 broker10，必须拆清楚是分子问题还是分母问题，否则下一步会走错方向。
- 运行后判断：Stage884 作为归因有价值，但 sleeve/pyramiding 本身没有继续价值。整条研究线若继续，只能做账户/持仓层生存问题的只读抽象，或暂停等待新的低自由度信息源。
- 后续规划：不再做 pyramiding/sleeve 的手数、R、止损、品种、方向、年份扫描；若继续，下一阶段最多做 C9/C17 峰值日的 holding-level pressure state 只读定义，确认是否存在不依赖品种名和日期的实时压力状态。
