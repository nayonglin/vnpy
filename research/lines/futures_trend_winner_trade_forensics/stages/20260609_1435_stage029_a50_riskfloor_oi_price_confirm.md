# Stage029 正式版50万0.1风控交易 OI+价格确认逐笔归因

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：2026-06-09 14:35 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因 / 逐笔法证
- 是否重要突破：否，属于强线索复核，不是可直接交易化规则
- 是否触发A/B：否，本阶段未修改策略规则，仅复盘正式版50万口径的已成交交易

## 外部调研与判断

- 参考资料：
  - Britannica Money: futures volume/open interest 中提到价格与 OI 同向增加可用于确认趋势强度。
  - NexusFi: open interest matrix 把上涨+OI上升视作多头趋势确认，下跌+OI上升视作空头趋势确认。
- 我的判断：OI 上升 + 价格沿交易方向，是有期货微观结构含义的“新资金沿趋势进入”特征，比单纯 OI 上升更接近第一性原理；但它仍然不是普世 alpha，必须在正式策略的实际 0.1 风控成交上验证，并警惕少数大赢家贡献过高。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage755_a50_riskfloor_oi_confirm.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；脚本内部只读过滤 `risk_multiplier <= 0.100001`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用正式 Stage372/Stage750 50万口径全周期，`2020-01` 至本地当前数据末端
- 账户规模：`500,000`
- 成本口径：沿用正式版手续费、滑点、合约乘数、保证金口径
- 样本过滤：
  - 全部 closed lots：`343`
  - 仅保留正式版实际成交且 `risk_multiplier=0.1` 的 lot：`57`
  - 其中 OI 数据可用：`44`
  - OI 缺失：`13`
- 策略/归因口径：
  - 正式版50万 `official_stage372_500k_stage750`
  - 连败机制打开；实际 `0.1` 风控交易由 `risk_multiplier=0.1` 和 `loss_streak>=3` 识别
  - 特征定义：`entry_oi_price_confirm = entry_oi_gt_prev1 AND entry_price_direction_aligned`
  - 多头价格沿方向：开仓日 close 大于前一交易日 close
  - 空头价格沿方向：开仓日 close 小于前一交易日 close

## 结果

- 期末权益：本阶段不以权益为目标，未单独统计权益曲线
- 总收益：本阶段不以权益为目标，未单独统计
- 最大回撤：本阶段不以权益为目标，未单独统计
- Sharpe：本阶段不以权益为目标，未单独统计
- 总滑点：沿用正式回测成本，未在本阶段单独汇总
- 总交易次数：closed lots `343`；0.1 风控 lots `57`
- 胜率：
  - 全部 0.1 风控 lot：盈利 `16`、亏损 `41`，胜率 `28.0702%`
  - OI 可用的 0.1 风控 lot：盈利 `13`、亏损 `31`，胜率 `29.5455%`
  - 命中 `OI上升+价格沿方向`：`10` 笔，盈利 `6`、亏损 `4`，胜率 `60.0000%`
  - OI 可用但未命中：`34` 笔，盈利 `7`、亏损 `27`，胜率 `20.5882%`
- 其他关键指标：
  - 命中组总 realized PnL：`+724,180`
  - 命中组平均 realized PnL：`+72,418`
  - 命中组平均理论方向收益率：`+1.5281%`
  - 命中组平均 R：`+8.5311`
  - OI 可用未命中组总 realized PnL：`-626,220`
  - OI 可用未命中组平均 realized PnL：`-18,418.2353`
  - OI 可用未命中组平均理论方向收益率：`-1.6595%`
  - OI 可用未命中组平均 R：`-0.8504`
  - 若把 OI 缺失也归入非命中/不可用，非命中组 `47` 笔，盈利 `10`、亏损 `37`，胜率 `21.2766%`，总 realized PnL `-956,305`

## 逐笔命中清单

| lot_id | 合约 | 方向 | 开仓 | 平仓 | 盈亏 | 结果 | 理论收益率 | R | 信号 | 退出 | 连败数 | OI变化 |
| ---: | --- | --- | --- | --- | ---: | --- | ---: | ---: | --- | --- | ---: | ---: |
| 27 | `hc2010.SHFE` | long | 2020-06-02 | 2020-06-04 | -300 | loss | -0.8451% | -0.4227 | long_case1a | long_prev2day_stop | 3 | +0.0799% |
| 113 | `jm2109.DCE` | long | 2021-06-23 | 2021-06-29 | +120 | profit | +0.1012% | +0.0312 | long_case2 | long_prev2day_stop | 4 | +6.7163% |
| 152 | `jm2205.DCE` | long | 2021-12-17 | 2021-12-28 | +2,970 | profit | +2.3131% | +0.4142 | long_case2 | long_prev2day_stop | 4 | +4.0877% |
| 156 | `SM205.CZCE` | long | 2022-01-12 | 2022-01-18 | -15,300 | loss | -4.0009% | -2.0157 | long_case1a | long_prev2day_stop | 3 | +8.3792% |
| 162 | `CF205.CZCE` | long | 2022-01-12 | 2022-02-07 | +13,000 | profit | +3.0689% | +1.5392 | long_case2 | long_prev2day_stop | 3 | +0.7771% |
| 182 | `lh2209.DCE` | long | 2022-04-25 | 2022-05-18 | +7,520 | profit | +2.5405% | +1.1059 | long_case2 | long_prev2day_stop | 4 | +0.4466% |
| 190 | `hc2210.SHFE` | short | 2022-07-07 | 2022-07-21 | +675,540 | profit | +9.8395% | +83.4000 | short_case1a | short_prev2day_stop | 3 | +0.8521% |
| 224 | `CF309.CZCE` | long | 2023-07-12 | 2023-07-18 | -3,450 | loss | -0.6739% | -0.2110 | long_case2 | long_prev2day_stop | 3 | +1.0671% |
| 236 | `cu2310.SHFE` | long | 2023-08-31 | 2023-09-06 | -2,400 | loss | -0.2300% | -0.1153 | long_case2 | long_prev2day_stop | 3 | +1.5596% |
| 294 | `lh2505.DCE` | long | 2025-03-07 | 2025-03-21 | +46,480 | profit | +3.1679% | +1.5852 | long_case2 | long_prev2day_stop | 3 | +1.3468% |

## 输出文件

- report：无图表，本阶段为 CSV/终端归因
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage755_a50_riskfloor_oi_confirm_summary_stage755_a50_riskfloor_oi_confirm_v1.csv`
- orders：无单独 orders 输出
- daily：无单独 daily 输出
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage755_a50_riskfloor_oi_confirm_riskfloor_lots_stage755_a50_riskfloor_oi_confirm_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage755_a50_riskfloor_oi_confirm_group_stats_stage755_a50_riskfloor_oi_confirm_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage755_a50_riskfloor_oi_confirm_closed_lots_stage755_a50_riskfloor_oi_confirm_v1.csv`

## 结论

- 本阶段结论：在正式版50万、连败机制打开、实际触发 `0.1` 风控的交易里，`OI上升+价格沿交易方向` 的命中组明显优于非命中组。命中组 `10` 笔中盈利 `6` 笔、亏损 `4` 笔，胜率 `60.0000%`；OI 可用未命中组胜率只有 `20.5882%`。
- 是否进入下一步：可以进入更严格的只读验证，但不能直接改正式版扩大风险。
- 下一步：先做命中组贡献拆解，尤其剔除 `hc2210.SHFE` 这笔 `+675,540/+83.4R` 后重算；再做年份/品种/方向分层、冷启动样本和候选日前可见性检查。若剔除单笔巨额右尾后仍保持优势，才考虑预声明 A/C，而不是直接上正式版。

## 过拟合反思

- 运行前判断：有过拟合风险。用户提出的视觉/OI观察有第一性原理基础，但目标样本是正式版低风险档交易，样本天然较小。
- 运行后判断：仍有过拟合风险，但不是无效线索。
- 原因：命中组胜率和平均 R 很强，但 `10` 笔样本过小，且 PnL/R 被 `hc2210.SHFE` 单笔大赢家显著拉高；不过非命中组在 OI 可用样本里表现显著差，这说明它至少是一个有解释力的质量标签。

## 继续价值反思

- 运行前判断：有价值继续。OI 与价格同向是期货趋势确认里的经典结构，不是纯数据挖掘特征。
- 运行后判断：有价值继续，但只适合做“候选质量标签/风险恢复前置观察”，不能直接作为放大仓位规则。
- 原因：特征命中后胜率从 OI 可用整体 `29.5455%` 提到 `60.0000%`，非命中仅 `20.5882%`；但样本数和单笔右尾集中度不足以支撑直接交易化。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage029 摘要
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段只读归因，不属于正式候选或重要合入
