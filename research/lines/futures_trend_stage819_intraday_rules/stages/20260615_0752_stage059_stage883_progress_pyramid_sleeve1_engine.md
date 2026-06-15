# Stage059 Stage883 1手顺势加仓 sleeve 真实引擎审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 07:52 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage819 候选分钟级规则研究；冻结真实组合引擎 A/C，不改官方正式版、不改官方候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。属于 Stage882 同手数加仓失败后的账户级右尾参与预算验证。
- 是否触发正式 A/B：否。C17 未通过 C9 闸门，不进入正式候选、不写根目录 `back_log.md`。
- 决策：`stage883_progress_pyramid_sleeve1_engine_not_promoted`

## 外部调研与判断

- vn.py/VeighNa 官方项目定位支持多合约组合策略回测与实盘框架；本阶段必须落到事件驱动真实组合引擎，而不能只看代理收益。
- CME 对 open interest 的说明支持把 OI/参与度作为趋势确认维度，但不支持把单一 OI 或价格触发当作无风险加仓理由。
- Turtle / 趋势跟随 pyramiding 资料的第一性原则是：只给已经盈利的仓位加仓，并对新增风险设置独立止损。
- CFTC stop-loss 风险材料提示止损只能控制纪律，不能保证成交质量或消除滑点，因此新增仓必须小、可解释、可实时退出。
- 我的判断：Stage882 同手数加仓证明右尾真实存在，但账户不可生存；Stage883 用固定 1 手 sleeve 是低自由度的右尾参与预算，不是参数救援。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine.py`
- 新增输出前缀：`qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_*`
- 新增规则臂：`stage883_stage819_c9_progress_pyramid_sleeve1_once`
- 新增参数：
  - `PYRAMID_PROGRESS_R = 0.5`
  - `PYRAMID_MAX_ADD_VOLUME = 1`
  - `enable_stage883_progress_pyramid_once = True`
  - `stage883_pyramid_max_add_volume = 1`
- 修改参数：无官方配置修改；C9、C4、Stage819 候选配置均保持原样。
- 删除参数：无官方配置删除；本阶段不沿用 Stage882 的同手数 `add_volume_multiplier` 作为可调参数。
- 规则定义：C9 保持不变；若入场日先触达 `+0.5R` progress 且没有先触达 `-0.5R` adverse，则在 `+0.5R` 合成最多 `1` 手 add-on sleeve；新增仓止损为原始入场价，入场日回打即合成平仓，否则作为普通仓位进入后续日线退出路径。

## 回测参数

- 数据区间：沿用 Stage847/Stage863 全周期 `2018-01-01 -> 2026-05-29`。
- 上游候选：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
- 账户规模：`300000`
- 分钟数据：Stage861 full minute bars，加载 `1,479,592` 根、`216` 个合约。
- 对照：
  - C4：`stage830_stage819_c2_broker10_100_cap`
  - C9：`stage847_stage819_c4_05r_stop_retry_once`
  - C17：`stage883_stage819_c9_progress_pyramid_sleeve1_once`
- 成本：沿用当前组合回测默认手续费/滑点；本阶段未进入 2x/3x 成本压力。
- 不扫描 progress R、add volume、止损位置、品种、方向、年份或分钟窗口。

## 新增回测结果

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
- 总滑点增加：`+313,970`
- 总交易次数增加：`+265`
- max broker10 恶化：`+13.0329pp`
- p95 broker10 恶化：`+2.2692pp`

### 事件统计

- add-on sleeve 事件：`175`
- 入场日未止损：`99`
- 入场日止损：`76`
- add 总手数：`175`
- 合成开仓成交：`175`
- 合成 closed lots：`174`
- 合成 lot realized PnL：`220,620.15`
- 年度 stopped 估计亏损：
  - 2018：`-820.4`
  - 2019：`-3,004.7`
  - 2020：`-4,850.0`
  - 2021：`-7,301.5`
  - 2022：`-7,378.7`
  - 2023：`-2,441.3`
  - 2024：`-4,739.8`
  - 2025：`-3,000.6`
  - 2026：`-190.0`

## 视觉复核

- 路径图非空：C17 权益长期略高于 C9，2022 峰谷回撤略好，但 broker10 峰值明显高于 C9，验证了“不通过”的主要原因。
- atlas page001 非空：展示 add 后未在入场日回打原入场价的样本；绿线为 `+0.5R add`，蓝线为原始入场价/新增仓止损。
- atlas page004 非空：展示入场日止损样本；绿线 add 后红线在回打原入场价时平掉 add-on，符合“错了不能死扛”的实时止损定义。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_report_stage883_stage882_progress_pyramid_sleeve1_engine_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_decision_stage883_stage882_progress_pyramid_sleeve1_engine_v1.json`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_comparison_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_curve_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_trades_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv`
- closed lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_closed_lots_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv`
- pyramid events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_pyramid_events_stage883_stage882_progress_pyramid_sleeve1_engine_v1.csv`
- path chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_path_chart_stage883_stage882_progress_pyramid_sleeve1_engine_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine_atlas_page001_stage883_stage882_progress_pyramid_sleeve1_engine_v1.png` 至 `page004`

## 结论

- C17 有数据价值：固定 1 手 sleeve 保留了一部分 Stage882 的右尾，且相对 C9 多赚 `104.67` 万、最大回撤也改善 `1.47pp`。
- C17 不能推广：Sharpe 低于 C9，max broker10 从 C9 的 `114.3987%` 恶化到 `127.4316%`，说明新增右尾不是免费的，风险峰值仍在账户层重新出现。
- 停止本 sleeve 分支：不做 `2手/3手`、`0.25R/0.75R`、止损位置、品种、方向或年份救参；不进入滚动起点、成本压力、正式候选或 A/B。
- 第一性判断：分钟级“确认后小额参与”比同手数加仓更像可执行纪律，但在当前候选版资金路径里仍无法穿越保证金生存线。收益不是问题，账户压力才是问题。

## 过拟合反思

- 运行前判断：否。本阶段不是根据局部样本扫参，而是把 Stage882 的右尾参与降为固定 1 手账户预算。
- 运行后判断：否，但继续救该形状会变成过拟合。`1` 手 sleeve 已经是最保守的正整数参与方式，若继续扫 `2/3` 手、R 阈值或按品种过滤，就是在用历史峰值救参。

## 继续价值反思

- 运行前判断：有价值。Stage882 说明右尾真实，必须验证更小账户预算是否可行。
- 运行后判断：本 sleeve 分支没有继续价值；整条分钟规则线仍有复盘价值，但下一步不应再围绕 pyramiding 变体。
- 后续规划：回到目标本质，优先做“新增日内入场/出场是否能降低账户压力而不是增加账户压力”的只读复盘，例如对 C9/C17 的 broker10 峰值日做逐笔持仓层视觉归因，或暂停本线等待新的低自由度信息源。
