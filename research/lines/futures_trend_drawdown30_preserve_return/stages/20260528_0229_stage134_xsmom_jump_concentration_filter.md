# Stage134 xsmom反跳跃集中度过滤审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 02:29 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：固定结构 A/B/C 只读审计；不改 Stage079/C3，不改 Stage103，不扫小数阈值。
- 是否重要突破：否。重要结论是反证边界：反跳跃集中度过滤能改善 Stage079，但不支配 Stage103。
- 是否触发A/B：是。A=`Stage079`；C0=`Stage103 broker10_guard`；C1=`jump63_drop_worst1`；C2=`jump63_lowhalf`。

## 外部调研与判断

- 参考资料：
  - `Frog in the Pan: Continuous Information and Momentum`：连续、非跳跃式信息扩散可增强动量质量，离散大跳跃后的动量更容易反转。
  - GitHub `Momentum-Investing`：公开实现里也把 FIP、skewness filter、TSMOM/CSMOM 组合用于动量质量过滤，但其股票长仓框架不能直接迁移到中国期货整数手和保证金约束。
  - 商品期货 momentum / trend-following 文献与代码样例：支持动量质量与趋势形态审计，但也反复提示数据挖掘和样本设计风险。
- 我的判断：
  - Stage104 显示短持有坏窗口更多来自趋势暴涨后的反转，所以“去掉单根跳跃贡献过高的 xsmom 信号”有合理经济含义。
  - 但该方向必须低自由度。若本阶段失败，不应继续调 `jump_share` 阈值、窗口或 Top比例。
  - 本阶段只测试两个离散结构：去掉跳跃集中度最高1个信号、保留跳跃集中度最低半数。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage434_xsmom_jump_concentration_filter.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `jump_share63 = rolling63 max(abs(return)) / rolling63 sum(abs(return))`，并整体 shift 1 日，避免未来函数。
  - `xsmom_jump63_drop_worst1_broker10_guard`：同日 xsmom 期望信号数大于等于2时，去掉 `jump_share63` 最高的1个信号。
  - `xsmom_jump63_lowhalf_broker10_guard`：同日保留 `jump_share63` 最低半数信号。
  - `BROKER10_MULTIPLIER=1.10`：沿用 Stage103 执行闸门。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：当前权威日度路径 `2020-01-02` 起至 2026 数据末端；多起点含 `start_2020/start_2021/start_2022/start_2023/start_2024/start_2025/phase_2024_2025/weak_2021_full/ytd_2026`。
- 账户规模：`615,000` 账户口径；Stage079 为 `50万C3下单 + 11.5万外部现金`。
- 成本口径：正常成本，并复验 `1x/2x/3x/5x` 滑点压力。
- 样本过滤：无日期、月份、品种补丁；只用交易日前已知的 63日跳跃集中度。
- 策略/归因口径：Stage103 的 xsmom 承载结构上加跳跃质量排序；C3 主体不变。

## 结果

### 全周期核心结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 3个月分 | 6个月分 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Stage079 | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 100.0000 | 100.0000 |
| Stage103 broker10_guard | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 121.2041 | 134.4513 |
| jump63_drop_worst1 | 31,526,015 | 5026.1813% | -29.6304% | 1.3532 | 14.5308 | 116.6370 | 122.4306 |
| jump63_lowhalf | 31,478,140 | 5018.3967% | -28.9814% | 1.3428 | 14.6311 | 114.1135 | 119.1450 |

### 交易与胜率

| 版本 | 总滑点 | 总交易次数 | 日胜率 | 非零日胜率 |
|---|---:|---:|---:|---:|
| Stage079 | 1,556,750 | 757 | 36.2924% | 48.3478% |
| Stage103 broker10_guard | 1,569,265 | 1,217 | 43.0809% | 50.3432% |
| jump63_drop_worst1 | 1,569,930 | 1,231 | 42.8851% | 50.1144% |
| jump63_lowhalf | 1,571,360 | 1,239 | 42.4935% | 49.6568% |

### 3个月/6个月任意启动体验

- `jump63_drop_worst1`：
  - 3个月 p05 收益 `-10.9102%`，正收益率 `74.5160%`，低增长率 `28.3656%`，DD20 触发率 `17.2895%`，Ulcer P95 `16.7812`。
  - 6个月 p05 收益 `-1.1835%`，正收益率 `94.2281%`，低增长率 `9.0568%`，DD20 触发率 `35.7109%`，Ulcer P95 `19.2305`。
- `jump63_lowhalf`：
  - 3个月 p05 收益 `-10.9331%`，正收益率 `74.0657%`，低增长率 `28.6808%`，DD20 触发率 `17.2445%`，Ulcer P95 `16.9137`。
  - 6个月 p05 收益 `-1.1853%`，正收益率 `93.9934%`，低增长率 `9.1037%`，DD20 触发率 `35.7109%`，Ulcer P95 `19.2156`。
- Stage103 仍更强：3个月/6个月分 `121.2041/134.4513`，高于两个跳跃过滤版本。

### 保证金与成本压力

- `jump63_drop_worst1` 通过 Stage079 硬指标、3/6个月目标、execution-relative 闸门；但 `start_2020/start_2021` 仍不是绝对 1.10x 部署口径。
- `jump63_lowhalf` 通过 Stage079 硬指标和3/6个月目标，但 `phase_2024_2025/start_2024` 的 1.10x 保证金口径相对 Stage079 变差，不通过 execution-relative。
- `1x/2x/3x/5x` 滑点压力下，两个跳跃过滤版本最大回撤均不差于 Stage079；但均不优于 Stage103 的综合质量。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage434_xsmom_jump_concentration_filter_report_stage434_xsmom_jump_concentration_filter_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage434_xsmom_jump_concentration_filter_chart_stage434_xsmom_jump_concentration_filter_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage434_xsmom_jump_concentration_filter_summary_stage434_xsmom_jump_concentration_filter_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage434_xsmom_jump_concentration_filter_daily_stage434_xsmom_jump_concentration_filter_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage434_xsmom_jump_concentration_filter_quality_panel_stage434_xsmom_jump_concentration_filter_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage434_xsmom_jump_concentration_filter_decision_stage434_xsmom_jump_concentration_filter_v1.json`

## 结论

- 本阶段结论：`jump63_drop_worst1` 是 Stage079 目标下的合格 paper 备选，但不是主晋级版本；`jump63_lowhalf` 更弱。
- 是否进入下一步：不进入主晋级。当前主执行相对候选仍是 Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`。
- 下一步：
  1. 不继续调 `jump_share63` 阈值、窗口或 Top比例。
  2. Stage134 只保留为“反跳跃集中度有风险含义”的研究经验和 paper 对照。
  3. 如果继续研究，应优先 Stage103 工程化复跑、paper/影子盘和真实券商保证金接入；主动优化只允许全新、低自由度、保证金更轻、样本更充分的新风险源。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本阶段不是过拟合；若继续救跳跃窗口或阈值，就会转向过拟合。
- 原因：本阶段没有用坏窗口挑日期/品种，也没有扫 `25%/30%`、`20/126日`、Top比例等相邻参数；失败后直接停止，而不是围绕结果救参。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：Stage134 子路线继续主动优化价值低；总目标仍有价值，但路径应回到 Stage103 落地或新风险源。
- 原因：反跳跃集中度验证了一个正确风险直觉，但收益、Sharpe、Ulcer、3/6个月体验都被 Stage103 支配；继续打磨只会增加复杂度而缺少新信息。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage134 约束和阶段文件。
- 是否更新 `research/registry.md`：否，未形成新的正式主候选。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 简要摘要；不更新 `memory.md`。
