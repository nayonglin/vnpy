# Stage053 现有卫星池粗权重净值层筛查

- 研究线：`futures_trend_drawdown30_preserve_return`。
- 记录时间：`2026-05-26 14:16 CST`。
- 当前模式：`day`。
- 阶段性质：Stage052 反证后的现有卫星池排查；只做净值层粗筛，不生成正式候选。
- 重要突破：重要反证。

## 本次动机

Stage052 已经反证 `C3原路径 + xsmom overlay + 3万外部现金` 路线。为避免在旧候选里凭感觉继续打转，本阶段把已有研究产物中的卫星曲线统一拉到同一套粗权重框架下，先判断是否存在值得进入真实资金/保证金/整数手数复验的净值层候选。

## 调研和判断

- 外部研究继续支持商品趋势组合可用动量、Carry、价值、偏态/尾部风险和多策略分散改善路径回撤。
- 但本线本地实验已经反证当前 Carry 实现、xsmom 小资金腿、xsmom overlay、旧震荡卫星真实资金拆分等多种形状。
- 因此本阶段不新增精细参数，也不训练新模型；只把已有卫星以粗权重做方向筛查。若净值层都不过关，就不值得进入更昂贵的真实资金复验。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage353_existing_satellite_pool_frontier.py`。
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage353_existing_satellite_pool_frontier_summary_stage353_existing_satellite_pool_frontier_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage353_existing_satellite_pool_frontier_window_stage353_existing_satellite_pool_frontier_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage353_existing_satellite_pool_frontier_decision_stage353_existing_satellite_pool_frontier_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage353_existing_satellite_pool_frontier_report_stage353_existing_satellite_pool_frontier_v1.md`
- 不修改第78-1、C3、AI池、品种池、开平仓逻辑或真实执行模块。

## 参数

- C3权重粗档：`70%/75%/80%/85%/90%/92.5%/95%`。
- 卫星池：
  - `range_v8_two_stage_stop`
  - `range_v9_short_soft_floor`
  - `range_v7_intraday_stop`
  - `boll_v5_rsi_extreme`
  - `no_lower_weekly_pullback_ignition`
  - `no_upper_twosignalhigh_short`
  - `pairwise_range150_fast`
  - `carry_cost20bps`
- 窗口：复用 Stage352 的 `full/start_2020/start_2021/start_2022/start_2023/start_2024/start_2025/ytd_2026/weak_2021_full/phase_2024_2025`。
- 闸门：组合最大回撤 `>= -30%`；正收益窗口收益保留 `>= 80%`。
- 修改参数：无。
- 删除参数：无。

## 基准口径

- C3 全周期总收益：`6085.1300%`。
- C3 全周期最大回撤：`-31.0767%`。
- C3 期末权益：`30,925,650`。
- C3 Sharpe：约 `1.6173`。
- C3 总交易次数：`757`。
- 本阶段是净值层筛查，不重新计算真实撮合滑点、保证金或胜率。

## 核心结果

- 决策：`no_existing_satellite_netvalue_candidate`。
- 原因：没有任何现有卫星在粗权重净值层通过全部窗口。

### 最接近但失败的组合

| 卫星 | C3权重 | 卫星权重 | 全周期收益 | 全周期最大回撤 | 收益保留 | 通过窗口 | 正收益窗口通过 | 最差回撤 | 正收益窗口最低收益保留 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `range_v8_two_stage_stop` | `80%` | `20%` | `4869.2570%` | `-29.6198%` | `80.0189%` | `8/9` | `7/8` | `-29.6198%` | `79.9631%` |
| `range_v9_short_soft_floor` | `80%` | `20%` | `4869.0530%` | `-29.6238%` | `80.0156%` | `8/9` | `7/8` | `-29.6238%` | `79.9047%` |
| `carry_cost20bps` | `85%` | `15%` | `5167.5691%` | `-29.8821%` | `84.9213%` | `8/9` | `7/8` | `-30.5640%` | `83.4037%` |

## 结论

- 现有卫星池不能直接拼出“最大回撤30以内且收益不显著降低”的净值层候选。
- `range_v8_two_stage_stop` 的 `80/20` 只差 `weak_2021_full` 收益保留 `79.9631%` 这类边界，但它在 Stage024/026 真实资金、保证金和滑点链路里已经被反证，不能因为净值层接近就重新推广。
- 当前旧卫星池继续调小数权重的收益很低，过拟合风险很高。
- 下一步应停止旧卫星拼接路线，转向真正新的低相关收益源/承载结构，或回到 `11.5万外部现金` 的正常成本部署边界。

## 过拟合反思

- 运行前判断：不是过拟合，因为只用已有卫星、粗权重、固定窗口和预声明闸门做排查。
- 运行后判断：本阶段不是过拟合；但若继续把 `80/20` 调成 `80.05/19.95` 这类小数救边界，就是明显过拟合。

## 继续价值反思

- 运行前判断：有价值，因为 Stage052 后需要确认旧候选是否还有低成本复用空间。
- 运行后判断：本阶段有排除价值；旧卫星池方向继续价值低，总研究线仍有价值，但必须换结构。

## TODO

- 不进入真实资金复验。
- 不继续扫现有卫星权重小数。
- 下一阶段优先二选一：
  - 重新寻找真正低相关、可承载、弱窗口互补的新收益源。
  - 把 `11.5万外部现金` 作为正常成本部署边界做实盘前资金约束解释，而不是继续把它包装成 alpha 改进。
