# Stage032 A50连败状态下OI确认豁免恢复原始仓位

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：2026-06-09 15:43 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：A/C 策略回测，基于 Stage750 50万正式逻辑增加 OI+价格确认后豁免连败缩放
- 是否重要突破：否，明确反证
- 是否触发A/B：是，属于可能影响正式风险 sizing 的候选规则

## 外部调研与判断

- 参考资料：
  - CME Open Interest：https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest.html
  - Britannica Volume & Open Interest：https://www.britannica.com/money/futures-volume-open-interest
  - NexusFi Open Interest Analysis：https://nexusfi.com/a/concepts/open-interest-analysis
- 我的判断：价格沿方向 + OI 上升可以解释为趋势确认和新资金进入，但资料倾向把它作为确认/解释工具，而不是单独交易信号。本阶段不改变 alpha，只测试它能否在连败防守状态下作为外生质量确认，临时豁免 `0.1` 连败缩放。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage758_a50_streak_oi_confirm_exemption.py`
- 修改脚本：无，本阶段复用 Stage031 已新增的默认关闭 OI 恢复参数
- 删除脚本：无
- 新增参数：无
- 修改参数：
  - A：`stage526_500k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_stage750`
  - C：`stage526_500k_force95_to80_oi_confirm_streak_exempt_r080_pc25_maxpos4_stage758`
  - 账户资金 `500,000`
  - 全局正式风险资金保持 `risk_multiplier=0.80`
  - 连败机制打开：`streak_risk_multipliers=1.0,1.0,1.0,0.1`
  - `enable_streak_entry_structure_risk_recovery=True`
  - `enable_recovery_sleeve=True`
  - `enable_oi_price_confirm_risk_restore=True`
  - `oi_price_confirm_risk_restore_multiplier=1.00`
  - `oi_price_confirm_risk_restore_entry_contexts=flat_entry,reverse_entry,rollover_reopen`
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：基础成本、2x 成本、3x 成本压力
- 样本过滤：全周期日线；OI 豁免只使用入场前最新两根已完成合约日线的 `close` 和 `open_interest`
- 策略/归因口径：
  - 做多：最新已完成日线 `close > prev_close` 且 `OI > prev_OI`
  - 做空：最新已完成日线 `close < prev_close` 且 `OI > prev_OI`
  - 命中后只把内部连败风险乘数恢复到 `1.0`，有效正式风险仍为 `0.80`
  - 不额外放大正常非连败仓位，不改 AI 池、不改品种池、不改入场/退出、不关闭 recovery sleeve

## 结果

- A Stage750 期末权益：`21,371,670`
- A Stage750 总收益：`4174.3340%`
- A Stage750 最大回撤：`-39.7236%`
- A Stage750 Sharpe：`1.6218`
- A Stage750 总滑点：`1,161,790`
- A Stage750 总交易次数：`677`
- A Stage750 胜率：非零交易日胜率 `52.8954%`
- C Stage758 期末权益：`11,752,705`
- C Stage758 总收益：`2250.5410%`
- C Stage758 最大回撤：`-45.6934%`
- C Stage758 Sharpe：`1.4034`
- C Stage758 总滑点：`936,630`
- C Stage758 总交易次数：`678`
- C Stage758 胜率：非零交易日胜率 `52.5952%`
- C-A：
  - 期末权益 `-9,618,965`
  - 总收益 `-1923.793pp`
  - 最大回撤恶化 `-5.9698pp`
  - Sharpe `-0.2184`
  - 滑点 `-225,160`
  - 交易次数 `+1`
  - 强制减仓次数 `7 -> 8`
- 成本压力：
  - 1x 成本：`11,752,705 / 2250.5410% / -45.6934% / Sharpe 1.4034`
  - 2x 成本：`10,816,075 / 2063.2150% / -49.0643% / Sharpe 1.3205`
  - 3x 成本：`9,879,445 / 1875.8890% / -52.7016% / Sharpe 1.2384`
- 其他关键指标：
  - 决策：`a50_streak_oi_confirm_exemption_not_promoted`
  - 硬失败：`candidate_full_dd40_fail`、`candidate_dd_worse_more_than_3pp`、`candidate_sharpe_worse_more_than_0_15`、`candidate_no_full_return_improvement`、`candidate_cost2_deployable_fail`
  - watch 失败：`restore_sample_lt30`、`restore_trade_winrate_lt50`
  - 可交易 OI 豁免实际应用：`25` 笔，`15` 个品种，`7` 年，盈利 `8`、亏损 `16`，胜率 `32.0000%`，总 realized PnL `-1,410,365`，平均 R `2.8306`，中位 R `-0.4227`
  - 未应用：`318` 笔，胜率 `48.4277%`，总 realized PnL `+13,427,740`
  - 事后开仓日 OI 确认命中：`121` 笔，胜率 `66.1157%`，总 realized PnL `+13,566,720`，但不可用于开仓 sizing
  - 年度可交易豁免：`2020 +10,485`、`2021 -103,860`、`2022 +134,650`、`2023 -94,570`、`2024 -204,350`、`2025 +793,440`、`2026 -1,946,160`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage758_a50_streak_oi_confirm_exemption_decision_stage758_a50_streak_oi_confirm_exemption_v1.json`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage758_a50_streak_oi_confirm_exemption_summary_stage758_a50_streak_oi_confirm_exemption_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage758_a50_streak_oi_confirm_exemption_trades_stage758_a50_streak_oi_confirm_exemption_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage758_a50_streak_oi_confirm_exemption_curve_stage758_a50_streak_oi_confirm_exemption_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage758_a50_streak_oi_confirm_exemption_restore_group_stats_stage758_a50_streak_oi_confirm_exemption_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage758_a50_streak_oi_confirm_exemption_restore_lots_stage758_a50_streak_oi_confirm_exemption_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage758_a50_streak_oi_confirm_exemption_year_stats_stage758_a50_streak_oi_confirm_exemption_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage758_a50_streak_oi_confirm_exemption_entry_risk_stage758_a50_streak_oi_confirm_exemption_v1.csv`

## 结论

- 本阶段结论：正式 50万连败机制打开时，`OI 上升 + 价格沿方向` 不能作为连败豁免条件。它没有救回被 `0.1` 错杀的右尾，反而把防守区的坏单放大：实际豁免 `25` 笔中胜率只有 `32%`，总 PnL `-141.04万`，并把全周期权益从 `2137.17万` 打到 `1175.27万`，最大回撤从 `-39.72%` 恶化到 `-45.69%`。
- 是否进入下一步：不进入；该规则不能接正式版，也不应继续单因子交易化。
- 下一步：停止 OI 单因子连败豁免。若继续高质量机会识别，只能把 OI 放进多因子 watch，并优先研究为什么事后开仓日 OI 有效但入场前可交易 OI 失效；禁止扫 OI 天数、恢复倍率、品种、年份、方向或加关 recovery sleeve 救参。

## 过拟合反思

- 运行前判断：有中等过拟合风险，因为 OI 特征来自历史赢家/亏损图册与法证观察。
- 运行后判断：单独把 OI 确认作为连败豁免属于过拟合倾向，不能穿越正式 50万连败状态。
- 原因：事后开仓日 OI 确认仍然很强，但可交易因果口径只有 `25` 笔且胜率 `32%`，说明可用信息在开仓前不足；继续改窗口或倍率是在追历史展开后的信息。

## 继续价值反思

- 运行前判断：有价值。它直接检验“连败 0.1 是否过度防守，能否用外生 OI 确认豁免”。
- 运行后判断：该具体规则没有继续价值。
- 原因：它同时伤害收益、回撤、Sharpe 和成本压力，是明确反证；继续价值只剩只读解释，即研究 OI 的信息时点和泄漏边界。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage032 结论
- 是否更新 `research/registry.md`：否，研究线已存在
- 是否追加根目录 `memory.md/back_log.md`：是，追加重要 A/C 失败结论
