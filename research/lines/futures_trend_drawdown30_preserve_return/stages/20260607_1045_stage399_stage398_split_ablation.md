# Stage399 Stage398 拆变量消融：MA20 only vs no-prev2day only

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-07 10:45 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：拆变量归因 / 候选筛选
- 是否重要突破：否；MA20 only 是强线索，但尚未做冷启动和弱窗口复验
- 是否触发A/B：已遵循 `skills/version-ab-experiment/SKILL.md`；本阶段是 Stage398 的最小拆变量消融，不进入正式 A/B

## 外部调研与判断

- 参考资料：在线检索 `trend following position sizing initial stop moving average stop loss GitHub`、`position sizing stop distance risk per trade trend following futures`、`Turtle Trading position sizing stop distance risk per trade`。
- 我的判断：趋势跟踪通用原则支持“按止损距离控制单笔风险”；本阶段拆分验证表明，Stage398 的主要低回撤贡献不是简单去掉二日止损，而是 MA20 初始止损把手数距离拉回更稳的结构。单独关闭 prev2day 会放大持仓波动和成本压力，不具备推广价值。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage686_stage398_split_ablation.py`
- 修改脚本：无正式策略脚本修改；只新增研究 wrapper
- 删除脚本：无
- 新增参数：
  - Arm A `ma20_only`：`use_ma20_stop=True`、`enable_prev2day_stop=True`
  - Arm B `no_prev2day_only`：`use_ma20_stop=False`、`enable_prev2day_stop=False`
- 修改参数：两个 arm 均保留 `risk_ratio_*=0.01`、plus25/PVC、no-AI、`short_case1a/2/3`、`maxpos25`、`streak_risk_multipliers=1.0,1.0,1.0,1.0`
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：原始滑点成本，并追加 `2x/3x` 成本压力
- 样本过滤：plus25 含 `ni.SHFE/ag.SHFE/sc.INE/p.DCE/jd.DCE/v.DCE`，关闭 AI product pool filter，允许 `short_case1a/short_case2/short_case3`
- 策略/归因口径：基于 Stage397 `risk_ratio_*=0.01 + no-loss-streak + maxpos25`，分别只改一个变量

## 结果

### Arm A：MA20 only，保留 prev2day

- 期末权益：`712,790`
- 总收益：`42.5580%`
- 最大回撤：`-24.1030%`
- Sharpe：`0.4472`
- 总滑点：`85,290`
- 总交易次数：`1,689`
- 胜率：`51.4686%`
- broker10 资金占用：峰值 `59.3668%`，p95 `29.3602%`，`>90%/>100%` 天数 `0/0`
- 成本压力：2x `627,500/25.5000%/-27.6610%/Sharpe0.3065`；3x `542,210/8.4420%/-31.5259%/Sharpe0.1641`
- 候选：`opened=808`，`sizing_zero_volume=424`，`supply_demand=169`
- 初始止损距离：中位 stop distance `134.7`，中位 risk_per_contract `1,390.0`，中位 selected_volume `2`
- 年度：2020 `+102,385`，2021 `-33,865`，2022 `+9,415`，2023 `+2,755`，2024 `+37,010`，2025 `+97,765`，2026截至4月 `-2,675`

### Arm B：no-prev2day only，保留原初始止损

- 期末权益：`690,620`
- 总收益：`38.1240%`
- 最大回撤：`-46.0285%`
- Sharpe：`0.3479`
- 总滑点：`114,690`
- 总交易次数：`1,759`
- 胜率：`51.0905%`
- broker10 资金占用：峰值 `64.7123%`，p95 `38.2340%`，`>90%/>100%` 天数 `0/0`
- 成本压力：2x `575,930/15.1860%/-53.2970%/Sharpe0.2179`；3x `461,240/-7.7520%/-62.1152%/Sharpe0.0947`
- 强制保证金减仓：`15` 次，减仓 `143` 手
- 候选：`opened=816`，`sizing_zero_volume=378`，`supply_demand=165`
- 初始止损距离：中位 stop distance `68.0`，中位 risk_per_contract `735.5`，中位 selected_volume `3`
- 年度：2020 `+182,080`，2021 `-59,265`，2022 `-113,135`，2023 `-77,325`，2024 `+44,000`，2025 `+247,115`，2026截至4月 `-32,850`

## 对照结论

- 相对 Stage397 原 `0.01`，MA20 only：
  - 期末权益多 `98,930`
  - 收益多 `19.786pp`
  - 最大回撤改善 `16.0868pp`
  - Sharpe 多 `0.1780`
  - 滑点少 `19,560`
  - 2x/3x 成本 DD 改善 `20.8493pp/26.5047pp`
- 相对 Stage397 原 `0.01`，no-prev2day only：
  - 期末权益多 `76,760`
  - 收益多 `15.352pp`
  - 最大回撤恶化 `5.8387pp`
  - 滑点多 `9,840`
  - 资金占用 p95 多 `6.7037pp`
  - 2x/3x 成本 DD 恶化 `4.7866pp/4.0845pp`
- 相对 Stage398 组合版，MA20 only 少 `60,435` 期末权益、回撤深 `0.9760pp`，说明关闭 prev2day 对收益有补充，但主要安全贡献来自 MA20 手数距离。
- no-prev2day only 证明：不换初始止损就去掉 prev2day，会把短止损手数放大，导致 2022/2023 长水下和成本压力恶化。

## 品种归因

- MA20 only 主要盈利：`au +127,440`、`fg +93,420`、`ap +29,270`、`v +27,100`、`sh +25,380`、`sp +25,020`、`jm +24,300`、`lc +23,460`
- MA20 only 主要拖累：`hc -51,400`、`jd -32,460`、`sm -32,350`、`p -25,000`、`rb -21,790`、`ma -19,240`
- no-prev2day only 主要盈利集中在 `fg +144,840`、`lh +86,800`、`oi +68,750`、`si +60,650`、`sh +55,350`、2025 右尾很强
- no-prev2day only 主要拖累：`ma -61,370`、`cf -53,550`、`sm -52,830`、`ag -47,460`、`ru -42,750`、`v -30,550`，2022/2023 路径明显变坏

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage686_stage398_split_ablation_report_stage686_stage398_split_ablation_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage686_stage398_split_ablation_summary_stage686_stage398_split_ablation_v1.csv`
- cost stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage686_stage398_split_ablation_cost_stress_stage686_stage398_split_ablation_v1.csv`
- curves/chart：已输出同图对照曲线

## 结论

- 本阶段结论：Stage398 的核心贡献来自 `MA20 初始止损手数计算`。单独关闭 prev2day 不是合格方向，它增加右尾但显著放大左尾、资金占用和成本压力。
- 是否进入下一步：MA20 only 进入下一步稳健性复验；no-prev2day only 停止。
- 下一步：
  - 固定 MA20 only，不扫窗口，做冷启动、弱窗口和成本压力复验。
  - 若要保留 Stage398 组合版，需要额外证明关闭 prev2day 的收益补充不是 2025 单窗右尾，并且不会伤害 2022/2023。

## 过拟合反思

- 运行前判断：否，这次是拆变量归因，不是在结果后补丁。
- 运行后判断：MA20 only 暂不判定为过拟合；no-prev2day only 有明显窗口依赖和尾部放大问题，继续救它会过拟合。
- 原因：MA20 only 的改善同时体现在正常成本、2x/3x 成本和资金占用 p95；no-prev2day only 主要靠 2025 右尾拉收益，但 2021-2023 连续伤害路径。

## 继续价值反思

- 运行前判断：有价值；这是 Stage398 晋级前必须做的最小归因。
- 运行后判断：有价值，但方向收窄到 MA20 sizing。
- 原因：它解释了 Stage398 不是“去掉二日止损就好”，而是“原初始止损太近导致手数和风险路径不稳”；下一步应验证 MA20 sizing 是否穿越多窗口。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage399 摘要。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，作为 Stage398 归因结论追加。
