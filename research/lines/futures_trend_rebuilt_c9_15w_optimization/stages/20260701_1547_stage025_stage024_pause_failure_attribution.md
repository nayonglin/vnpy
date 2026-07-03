# Stage025 Stage024 暂停规则失败归因与下一步边界

- 时间：`2026-07-01 15:47 CST`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 阶段性质：只读归因，不是新策略版本，不改官方线上 C9/15w，不连接 CTP，不调用下单，不触发 A/B。
- 目标：解释 Stage024 因果 `high_vol_high_eff` 暂停新 `flat_entry` 为什么仍未达成“任意起点、任意大于一年周期正收益”的目标，并决定下一步是否应继续做真实引擎。

## 外部调研与判断

- Return Stacked 的 managed futures 综述强调，趋势跟随的长期价值来自跨市场趋势延续、分散化和低相关右尾，而不同实现之间年度表现分散很大。判断：不能为了压局部回撤，用粗糙 hard gate 把右尾趋势切掉。
  - 参考：https://www.returnstacked.com/managed-futures-trend-following/
- Man Group 对 trend following drawdown 的讨论指出，趋势跟随常见路径是小亏损后出现大收益，whipsaw 期需要耐心，过早退出可能错过后续趋势。判断：Stage024 的暂停逻辑必须检查是否砍掉恢复段。
  - 参考：https://www.man.com/insights/is-this-time-different
- Alpha Architect 的 fast/slow trend timing 研究提示，高波动 regime 下不是简单空仓，而可能需要切换到更快信号；neutral 比例过高会错过收益。判断：如果继续做 regime，应考虑“信号形态切换/风险释放节奏”，而不是继续调暂停阈值。
  - 参考：https://alphaarchitect.com/trend-following-timing-fast-and-slow-trends/
- PyTrendFollow 和 ReSolve 复制 trend-following 的开源/研究资料都把 vol scaling、滚动数据质量、组合层权重作为基础，而不是单一市场状态硬禁开。判断：下一阶段若引入外生源，应先做可因果、可复验、低自由度的 exposure 分层，而不是扩大规则集合。
  - 参考：https://github.com/chrism2671/PyTrendFollow
  - 参考：https://investresolve.com/how-to-replicate-trend-following-managed-futures/

## 本地证据

使用现有产物：

- Stage013 曲线：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage013_account_state_pilot_gate_engine/rebuilt_c9_stage013_account_state_pilot_gate_engine_curves_stage013_account_state_pilot_gate_engine_v1.csv`
- Stage024 曲线：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage024_causal_high_vol_pause_engine/rebuilt_c9_stage024_causal_high_vol_pause_engine_curves_stage024_causal_high_vol_pause_engine_v1.csv`
- Stage024 pause events：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage024_causal_high_vol_pause_engine/rebuilt_c9_stage024_causal_high_vol_pause_engine_pause_events_stage024_causal_high_vol_pause_engine_v1.csv`
- Stage013/024 worst-window files。

## Stage024 相对 Stage013 的窗口转移

- Stage024 新增负窗口：`39,043`
- Stage024 消除 Stage013 负窗口：`71,978`
- 净减少负窗口：`32,935`
- 两者都为负窗口：`258,969`

分 source 看：

| source_start_month | Stage024 新增负窗口 | Stage024 消除负窗口 | 净变化 | Stage024 最差收益 | 同窗口 Stage013 收益 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2019-01` | `1,171` | `12,890` | `-11,719` | `-29.1246%` | `-32.7491%` |
| `2020-07` | `2,236` | `10,179` | `-7,943` | `-29.4701%` | `-30.7466%` |
| `2018-01` | `2,151` | `9,818` | `-7,667` | `-29.6395%` | `-31.4724%` |
| `2018-07` | `2,123` | `9,619` | `-7,496` | `-29.7042%` | `-32.1377%` |
| `2020-01` | `2,434` | `9,576` | `-7,142` | `-29.3914%` | `-31.5220%` |
| `2021-01` | `18,802` | `3,969` | `+14,833` | `-35.7025%` | `-28.8167%` |
| `2022-07` | `3,371` | `1` | `+3,370` | `-44.0955%` | `-43.7940%` |

结论：Stage024 不是完全无效，它确实减少了早期账户的负窗口；但它明显伤害 `2021-01` 和 `2022-07` 生命周期。目标要求所有起点都稳，所以不能晋级。

## 暂停事件归因

Stage024 暂停事件：

- 事件数：`156`
- 减少手数：`13,576`
- 年份分布：`2021` 年 `37` 个、减少 `841` 手；`2022` 年 `119` 个、减少 `12,735` 手。
- 产品减少手数前列：`hc.SHFE 2,887`、`fu.SHFE 2,460`、`SM.CZCE 1,995`、`MA.CZCE 1,497`、`rb.SHFE 1,400`、`SA.CZCE 1,188`。

按 `source + date` 聚合为暂停 episode 后：

- episode 数：`113`
- `252` 交易日后 equity-delta 变动总和：`+24,949,883.6`
- `252` 交易日后正贡献率：`81.42%`
- 中位 `252` 交易日贡献：`+110,065.0`

这说明暂停在多数 episode 上方向是对的。但最差 episode 也很关键：

| source | date | products | reduced | 252d delta |
| --- | --- | --- | ---: | ---: |
| `2018-07` | `2021-02-28` | `MA.CZCE` | `23` | `-207,245.8` |
| `2021-01` | `2022-08-30` | `SA.CZCE` | `51` | `-147,590.0` |
| `2021-01` | `2022-03-28` | `fu.SHFE,hc.SHFE,jm.DCE` | `118` | `-97,150.0` |
| `2019-07` | `2022-03-28` | `fu.SHFE,hc.SHFE,jm.DCE` | `359` | `-74,280.0` |
| `2021-01` | `2022-03-23` | `fu.SHFE` | `55` | `-65,190.0` |

最强正贡献 episode：

| source | date | products | reduced | 252d delta |
| --- | --- | --- | ---: | ---: |
| `2019-01` | `2021-10-13` | `cu.SHFE` | `12` | `+1,541,565.6` |
| `2019-01` | `2021-10-28` | `lh.DCE` | `39` | `+1,410,495.6` |
| `2018-07` | `2021-10-13` | `cu.SHFE` | `13` | `+1,261,588.0` |
| `2018-01` | `2021-10-13` | `cu.SHFE` | `10` | `+1,187,965.6` |
| `2018-07` | `2021-10-28` | `lh.DCE` | `43` | `+1,107,128.0` |

结论：`high_vol_high_eff` 内部混合了两类完全不同的东西：

1. 应该躲的高波动假趋势/回撤延续；
2. 必须保留的恢复段右尾交易。

所以 Stage024 失败不是“暂停不够强”，而是单一 regime hard gate 无法区分这两类环境。

## 对目标的影响

- 任意结束日严格 `>1` 年负窗口仍为 `298,012`，目标失败。
- 最差收益 `-44.0955%`，目标失败。
- `17/17` 全周期收益保留通过，但这只能说明右尾没有被大面积砍掉，不能证明目标达成。
- 目标最难部分仍是 `2022-03/2022-07 -> 2023-07/2023-10` 的 1-2 年恢复段。

## 下一步候选边界

不建议继续做：

- `high_vol_high_eff` / `high_vol_low_eff` 分位阈值扫描；
- 暂停手数从 `0` 改成 `1/2/半仓` 的手数扫描；
- 按 `2022-03-28`、`2022-08-30`、品种、方向、source 定制补丁；
- 把 Stage020/021 高质量加风险当成左尾修复器。

更合理的 Stage026 方向：

1. **只读：恢复段右尾识别器**  
   专门比较 `2021-10` 正贡献 episode 与 `2022-03/2022-08` 负贡献 episode，在入场前可见数据中找差异。若差异只来自未来收益，则停止。

2. **只读：坏窗口持仓路径再拆解**  
   对 Stage024 仍失败的 top worst windows 做 positions/holding_pnl 归因，确认最大损失是否仍由新增仓位、已有仓位、或错过恢复交易造成。

3. **隔离：收益增强模块**  
   Stage020/021 的高质量信号可保留为收益增强研究，但必须独立于左尾风控，不用它来声称“任意一年正收益”。

## 过拟合反思

- 开始前：否。Stage025 是只读归因，不引入新参数、不筛选新候选。
- 结束后：否。本阶段没有根据结果反调规则；反而关闭了继续扫同类 regime gate 的方向。

## 继续价值反思

- 继续本阶段形状：价值有限。hard regime gate 已经暴露本质缺陷。
- 继续整体目标：仍有价值，但下一步应转向“入场前可见的恢复段右尾识别”和“剩余 worst window 的 holding_pnl 根因”，而不是继续做暂停阈值或手数参数。

## 决策

- 决策：`stage025_readonly_attribution_no_promotion`
- 不晋级、不触发 A/B、不改线上。
- 下一步若继续，应先做 Stage026 只读恢复段右尾识别器，只有找到可因果、跨 source 不崩的差异，才考虑写真实引擎。
