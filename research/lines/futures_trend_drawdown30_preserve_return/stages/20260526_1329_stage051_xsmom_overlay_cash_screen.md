# Stage051 C3 + 横截面动量Overlay + 外部现金筛查

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 13:29 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage049 反证后的换承载方式筛查
- 是否重要突破：阶段性线索，不是正式突破
- 是否触发A/B：否。当前仍是筛查，未达到可接正式版本的真实引擎验证级别。

## 外部调研与判断

- 参考资料：沿用本线此前对商品趋势/动量、波动缩放和尾部风险文献的调研；核心判断是横截面动量可能是独立收益源，但必须受真实保证金、整数手数、滑点和多起点约束检验。
- 我的判断：Stage048/049 已反证 `35万C3 + 15万xsmom` 拆分；本阶段不再救该拆分，而是保留 C3 50万原路径，把既有 xsmom 整数手数结果作为保证金 overlay，并用外部现金吸收组合层最大回撤和保证金峰值。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage351_xsmom_overlay_cash_screen.py`
- 修改脚本：清理 pandas 前向填充旧写法，不改变计算逻辑。
- 删除脚本：无。
- 新增参数：
  - overlay 承载方式：`floor_margin_per_leg_37p5k`、`min1_cheapest_within_37p5k`、`min1_all_no_cap`
  - 外部现金：`0/30000/50000/67000/100000/115000`
  - 切片窗口：全样本、2021全年、2024-2025、2026YTD
  - 滑点压力：`1x/2x/3x`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020至今；另含切片窗口。
- 账户规模：C3 交易路径仍按50万；本阶段叠加外部现金做账户口径评价。
- 成本口径：使用既有 C3 与 Stage346 xsmom 日损益/滑点口径；滑点压力为 1x/2x/3x。
- 样本过滤：不新增品种过滤，不调整 AI 池，不调整 C3 入场/出场。
- 策略/归因口径：C3 50万原路径 + Stage346 xsmom 整数手数日收益 overlay + 外部现金边界。

## 结果

- 最佳全样本候选：`min1_all_no_cap + 30000` 外部现金。
- 期末权益：`31,824,920`
- 总收益：`5904.7019%`
- 最大回撤：`-29.8729%`
- Sharpe：`1.6848`
- 总滑点：`1,566,700`
- 总交易次数：约 `1,207`（C3 `757` + xsmom `450` 合约成交口径）
- 胜率：本阶段为日收益/保证金筛查，未重新统计交易回合胜率。
- 其他关键指标：
  - 相对 C3 收益保留：`97.0349%`
  - 最大保证金/权益：`99.6410%`
  - review days：`5`
  - reject days：`0`
  - 解析所需现金：回撤30约 `21,726.67`，保证金100约 `28,265.80`
  - `2x`滑点下若要回撤和保证金同时过线，约需 `151,000` 外部现金，但收益保留降至 `79.0911%`
  - `3x`滑点下约需 `334,000` 外部现金，收益保留降至 `61.8165%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage351_xsmom_overlay_cash_screen_report_stage351_xsmom_overlay_cash_screen_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage351_xsmom_overlay_cash_screen_summary_stage351_xsmom_overlay_cash_screen_v1.csv`
- orders：无
- daily：无独立输出，复用输入日级路径。
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage351_xsmom_overlay_cash_screen_decision_stage351_xsmom_overlay_cash_screen_v1.json`

## 结论

- 本阶段结论：`overlay_cash_screen_candidate_requires_real_engine`。`min1_all_no_cap + 3万外部现金` 是阶段性线索：正常成本下比纯外部现金缓冲更省现金，且收益保留更高。
- 是否进入下一步：进入固定候选复验，不进入正式候选。
- 下一步：构造 Stage052，固定 `C3 50万原路径 + xsmom min1_all_no_cap overlay + 3万外部现金`，做真实引擎/多起点复验、保证金拒单检查、弱窗口与滑点压力；若多起点或滑点失败，则停止该承载方式。

## 过拟合反思

- 运行前判断：否。没有调品种、没有调入场、没有调 C3 参数，只是测试既有独立收益源和现金边界。
- 运行后判断：本阶段不是过拟合，但不能晋级。
- 原因：候选来自粗现金边界和既有 xsmom 口径；但切片不是完整重启真实引擎，且 2x/3x 滑点下现金需求显著上升，继续围绕 `3万/2.9万/3.1万` 或 overlay 细节救结果会过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage049 指向资金拆分失败，但横截面动量本身仍可能作为独立收益源。
- 运行后判断：有价值，但只限固定候选真实引擎反证。
- 原因：全样本 `5904.7019%/-29.8729%` 且收益保留 `97.0349%` 明显优于纯粹加 11.5万现金的收益口径；不过高滑点压力和非真实引擎切片仍是重大风险。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为阶段性线索记录。
