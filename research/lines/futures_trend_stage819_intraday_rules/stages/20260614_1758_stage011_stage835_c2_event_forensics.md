# Stage011 Stage835 C2/C4日内止损事件级法证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 17:58 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读事件级归因 + 分钟K视觉复盘；不改正式策略、不改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。它澄清了归因方向，但没有形成可晋级新策略。
- 是否触发A/B：否。没有新候选准备接入正式版，也没有与第78/Stage372做组合实验。

## 外部调研与判断

- 参考资料：
  - NinjaTrader `Managing Trade Risk Using Probabilities`：MAE 用于统计交易入场后典型逆向波动，帮助设定止损并避免过早止损或灾难亏损。
  - Trademetria `Understanding MAE and MFE Metrics`：MAE/MFE 应拆开看最大不利/最大有利路径，不能只看最终盈亏。
  - GitHub `python-backtesting-template`：仅作为通用回测结构参考，未复制策略代码。
- 我的判断：
  - 外部资料支持本阶段先做 MAE/MFE 事件级归因，而不是直接扫止损参数。
  - C2/C4 的 1R 日内止损不是问题本身；真正问题是止损释放资金后，组合层会重新生成更大的尾部暴露。
  - 因此下一步不应继续扫 `1R/0.8R/1.2R`、品种过滤或年份过滤，而应研究释放资金再使用纪律。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage835_stage827_c2_event_forensics.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无。本阶段只读取 Stage825/827/830 固定输出。
- 修改参数：无
- 删除参数：无
- 新增回测结果：无新完整组合回测；新增 C2/C4 事件级直接归因结果。
- 修改回测结果：无
- 删除回测结果：无

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-05-29`
- 账户规模：沿用 Stage819 候选 30w 口径；本阶段不重新模拟权益曲线。
- 成本口径：沿用 Stage827/Stage830 已生成 closed lots 的成本口径；本阶段不新增滑点模型。
- 样本过滤：
  - C2 事件：Stage827 `stage827_stage819_c2_engine`
  - C4 事件：Stage830 `stage830_stage819_c2_broker10_100_cap`
  - 基线匹配：Stage825 Stage819 closed-lot 分钟特征，按 `vt_symbol/direction/entry_date/entry_price_key` 聚合匹配。
- 策略/归因口径：
  - `event_stop_pnl`：C2/C4 实际触发日内止损后的 closed-lot PnL。
  - `baseline_pnl`：相同入场签名在原 Stage819 候选中的聚合 PnL。
  - `event_minus_baseline_pnl`：事件直接贡献，正值表示日内止损相对原候选减少亏损或提升收益。

## 结果

- 期末权益：不适用，本阶段不是完整组合回测。
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - C2_engine：事件 `51`，closed 匹配 `51`，baseline 匹配 `49`；事件止损 PnL 合计 `-9,436,886.6`，匹配基线 PnL `-14,630,055.0`，直接贡献 `+5,347,448.4`；正贡献事件 `33`，负贡献事件 `16`，中位直接贡献 `45,000`。
  - C4_broker10_cap：事件 `51`，closed 匹配 `51`，baseline 匹配 `48`；事件止损 PnL 合计 `-7,865,489.2`，匹配基线 PnL `-14,641,365.0`，直接贡献 `+6,871,695.8`；正贡献事件 `40`，负贡献事件 `8`，中位直接贡献 `89,370`。
  - 年度直接贡献：2021-2026 大多为正；2020 为负，C2 `-179,818.2`、C4 `-121,256.6`。
  - `stop_first` 桶：`91` 个匹配事件，直接贡献 `+12,179,364.2`，说明 C2 主要修的是先触及 1R 反向的失败单。
  - `morning_early` 桶：`39` 个事件，直接贡献 `+7,577,552.0`；`morning_late` 只有 `+91,195.2`，正负更混杂。
  - 负贡献集中线索：`ru.SHFE` `14` 个事件合计 `-1,002,858.0`，但这只是归因线索，不允许直接做品种过滤。
  - 未匹配 baseline：C2 有 `SM109.CZCE`、`jm2109.DCE` 两个事件；C4 多一个 `ru2009.SHFE`。closed 均匹配，说明事件本身完整，baseline 签名匹配有少量缺口。

## 视觉复盘

- 总览图确认 C2/C4 事件直接贡献为正，C4 因入口 broker10 cap 后手数/路径不同，直接贡献更高。
- Atlas 第一页显示：
  - `lh2201.DCE long 2021-11-01`、`si2310.GFEX long 2023-08-24`、`OI505.CZCE short 2025-01-21` 这类大正贡献，入场日出现快速逆向或先打 stop，原候选后续亏损更大，C2 止损是合理的。
  - `ru2601.SHFE long 2025-12-03` 是典型负贡献：C2 低位止损后，原候选基线虽然也亏但少亏，说明不能把所有 stop_first 都无脑视为好事件。
- 视觉判断：C2 止损的价格直觉是对的，但不能单独解决组合尾部；它把“坏单提前切掉”变成了“释放保证金和风险预算”，随后组合会在其他机会中重新承担风险。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage835_stage827_c2_event_forensics_report_stage835_stage827_c2_event_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage835_stage827_c2_event_forensics_summary_stage835_stage827_c2_event_forensics_v1.csv`
- event_match：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage835_stage827_c2_event_forensics_event_match_stage835_stage827_c2_event_forensics_v1.csv`
- bucket_stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage835_stage827_c2_event_forensics_bucket_stats_stage835_stage827_c2_event_forensics_v1.csv`
- yearly_stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage835_stage827_c2_event_forensics_yearly_stats_stage835_stage827_c2_event_forensics_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage835_stage827_c2_event_forensics_decision_stage835_stage827_c2_event_forensics_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage835_stage827_c2_event_forensics_event_delta_chart_stage835_stage827_c2_event_forensics_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage835_stage827_c2_event_forensics_atlas_manifest_stage835_stage827_c2_event_forensics_v1.csv`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage835_stage827_c2_event_forensics_atlas_page001_stage835_stage827_c2_event_forensics_v1.png` 到 `page010`

## 结论

- 本阶段结论：`stage835_c2_direct_events_positive_but_path_risk_unresolved`。
- 是否进入下一步：进入，但不是继续改止损阈值。
- 下一步：
  - 设计 Stage836：C2 止损后的释放资金再使用纪律，只允许低自由度账户级规则，例如“止损释放资金进入冷却桶，当日/次日不立即放大同方向或同产品簇风险”。
  - 先做只读归因：统计 C2/C4 止损后 N 日内新增/放大的风险预算具体贡献，确认尾部来自哪里。
  - 若再进入引擎，规则必须不引用 A 路径、不引用未来收益、不按 `ru/2020` 做过滤。

## 过拟合反思

- 运行前判断：否。Stage835 只读取已经冻结的 C2/C4 事件，不调 R、不调时间窗口、不筛品种。
- 运行后判断：否，但下一步风险升高。
- 原因：事件级归因本身是解释，不是优化；如果把 `ru.SHFE`、`2020`、`morning_late` 等桶直接变成过滤器，就是典型事后过拟合。

## 继续价值反思

- 运行前判断：有价值。它能拆清 C2/C4 是止损本身错，还是释放资金后的组合联动错。
- 运行后判断：有价值，但方向要收窄。
- 原因：C2/C4 直接事件贡献分别为 `+5.35M` 和 `+6.87M`，证明日内止损不是伪改善；但完整路径仍有 DD/broker 风险，下一步必须研究风险预算再使用，而不是救参。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage011 结论和 Stage012 方向。
- 是否更新 `research/registry.md`：否。不是正式候选、重要突破或路线迁移。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选或重要合入摘要。
