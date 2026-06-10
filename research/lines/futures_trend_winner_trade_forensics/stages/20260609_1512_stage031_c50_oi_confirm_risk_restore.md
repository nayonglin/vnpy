# Stage031 C50 OI确认后恢复0.8风险资金

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：2026-06-09 15:12 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：A/C 策略回测，基于 Stage748 C50 半风险关闭连败版本增加 OI+价格确认风险恢复规则
- 是否重要突破：否，收益显著提高但风险闸门失败
- 是否触发A/B：是，已按 `skills/version-ab-experiment/SKILL.md` 作为正式候选相关风险 sizing 规则验证

## 外部调研与判断

- 参考资料：
  - CME Open Interest 教育资料：https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest.html
  - NexusFi Open Interest Analysis：https://nexusfi.com/a/concepts/open-interest-analysis
  - GrizzlyParrot Futures Open Interest Explained：https://grizzlyparrottrading.com/futures-basics/futures-open-interest-explained.html
- 我的判断：OI 上升叠加价格沿交易方向，可以解释为“新资金沿趋势进入”，适合作为趋势机会质量的确认信息；但公开资料也更倾向把它作为确认/解释工具，而不是单独预测信号。GitHub/开源资料没有找到能直接复用到本仓库商品组合的成熟实现，因此本阶段只采用低自由度规则，并严格使用入场前最新已完成日线，避免开仓日收盘 OI 的事后信息泄漏。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无
- 新增参数：
  - `enable_oi_price_confirm_risk_restore`
  - `oi_price_confirm_risk_restore_multiplier`
  - `oi_price_confirm_risk_restore_entry_contexts`
- 修改参数：
  - A 基准为 Stage748：`stage526_500k_force95_to80_r040_pc25_maxpos4_no_streak_no_recovery_stage748`
  - C 候选为 Stage757：`stage526_500k_force95_to80_r040_oi_confirm_r080_no_streak_no_recovery_stage757`
  - Stage748 全局 `risk_multiplier=0.40` 仍烙在基础 `risk_ratio` 中；为了让命中后风险资金恢复到正式版 `0.80`，策略内部恢复乘数设为 `2.00`，即 `0.40 * 2.00 = 0.80`
  - 关闭连败缩放：`streak_risk_multipliers=1.0,1.0,1.0,1.0`
  - 关闭 `enable_streak_entry_structure_risk_recovery`
  - 关闭 `enable_recovery_sleeve`
  - 启用 `enable_oi_price_confirm_risk_restore=True`
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：基础成本、2x 成本、3x 成本压力
- 样本过滤：全周期日线，OI 恢复规则只使用入场前最新两根已完成合约日线的 `close` 与 `open_interest`
- 策略/归因口径：
  - 做多：最新已完成日线 `close > prev_close` 且 `OI > prev_OI`
  - 做空：最新已完成日线 `close < prev_close` 且 `OI > prev_OI`
  - 命中后仅提升本次入场 sizing 风险乘数，不改信号、不改 AI 池、不改品种池、不改退出
  - 同时保留只读对照：开仓日 OI+价格确认属于事后口径，仅用于解释，不用于交易 sizing

## 结果

- C Stage757 期末权益：`9,571,060`
- C Stage757 总收益：`1814.2120%`
- C Stage757 最大回撤：`-41.6458%`
- C Stage757 Sharpe：`1.4510`
- C Stage757 总滑点：`877,910`
- C Stage757 总交易次数：`685`
- C Stage757 胜率：非零交易日胜率 `52.6678%`
- A Stage748 期末权益：`5,565,350`
- A Stage748 总收益：`1013.0700%`
- A Stage748 最大回撤：`-39.7082%`
- A Stage748 Sharpe：`1.3285`
- A Stage748 总滑点：`470,250`
- A Stage748 总交易次数：`686`
- A Stage748 胜率：非零交易日胜率 `52.7165%`
- C-A：
  - 期末权益 `+4,005,710`
  - 总收益 `+801.142pp`
  - 最大回撤恶化 `-1.9377pp`
  - Sharpe `+0.1225`
  - 滑点 `+407,660`
  - 交易次数 `-1`
  - 强制减仓次数 `3 -> 6`
- 成本压力：
  - 1x 成本：`9,571,060 / 1814.2120% / -41.6458% / Sharpe 1.4510`
  - 2x 成本：`8,693,150 / 1638.6300% / -44.8728% / Sharpe 1.3547`
  - 3x 成本：`7,815,240 / 1463.0480% / -48.2707% / Sharpe 1.2584`
- 其他关键指标：
  - 决策：`c50_oi_confirm_risk_restore_not_promoted`
  - 硬失败：`candidate_full_dd40_fail`、`candidate_cost2_deployable_fail`
  - watch 失败：`restore_trade_winrate_lt50`
  - 可交易因果 OI 恢复实际应用：`125` 笔 closed lots，`18` 个品种，`7` 年，盈利 `60`、亏损 `65`，胜率 `48.0000%`，总实现盈亏 `+3,950,340`，平均 R `1.8435`，中位 R `-0.1153`
  - 未应用：`222` 笔，胜率 `46.8468%`，总实现盈亏 `+5,861,350`，平均 R `0.2445`
  - 事后开仓日 OI 确认命中：`121` 笔，胜率 `66.1157%`，总实现盈亏 `+10,787,410`
  - 事后开仓日 OI 确认未命中：`180` 笔，胜率 `36.6667%`，总实现盈亏 `-444,645`
  - 年度拆分显示可交易规则在 `2020/2021/2025` 明显贡献，但 `2024` 为 `-195,040`，`2026` 仅 `5` 笔即亏 `-1,606,830`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage757_c50_oi_confirm_risk_restore_decision_stage757_c50_oi_confirm_risk_restore_v1.json`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage757_c50_oi_confirm_risk_restore_summary_stage757_c50_oi_confirm_risk_restore_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage757_c50_oi_confirm_risk_restore_trades_stage757_c50_oi_confirm_risk_restore_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage757_c50_oi_confirm_risk_restore_curve_stage757_c50_oi_confirm_risk_restore_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage757_c50_oi_confirm_risk_restore_restore_group_stats_stage757_c50_oi_confirm_risk_restore_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage757_c50_oi_confirm_risk_restore_restore_lots_stage757_c50_oi_confirm_risk_restore_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage757_c50_oi_confirm_risk_restore_year_stats_stage757_c50_oi_confirm_risk_restore_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage757_c50_oi_confirm_risk_restore_entry_risk_stage757_c50_oi_confirm_risk_restore_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage757_c50_oi_confirm_risk_restore_entry_candidates_stage757_c50_oi_confirm_risk_restore_v1.csv`

## 结论

- 本阶段结论：OI 上升 + 价格沿方向是有解释力的右尾放大标签，但单独作为“恢复 0.8 风险资金”的交易规则不晋级。它把 Stage748 C50 的全周期收益从 `1013.0700%` 提高到 `1814.2120%`，Sharpe 也提高，但最大回撤破 `DD40`，2x 成本压力更差，且可交易因果口径命中交易胜率只有 `48.0000%`。本质上它不是稳定过滤劣质机会，而是在部分年份放大右尾，同时在 `2024/2026` 放大左尾。
- 是否进入下一步：不作为当前正式候选晋级；可以保留为多因子质量特征的 watch。
- 下一步：若继续，只允许低自由度地把 OI 确认与更上游结构条件组合，例如慢趋势一致性、账户状态、开仓后早期确认或流动性/合约切换状态；禁止直接扫 `0.6/0.7/0.9` 风险恢复倍率、OI 天数、价格阈值、年份、品种或方向补丁。

## 过拟合反思

- 运行前判断：有中等过拟合风险。原因是 OI+价格确认来自 Stage754/756 对历史赢家和亏损的观察，尤其开仓日 OI 确认存在事后信息泄漏风险。
- 运行后判断：本次可交易实现本身不算数据泄漏，因为只用了入场前已完成日线；但把它单独当风险恢复规则会过拟合到 `2020/2021/2025` 的右尾路径。
- 原因：事后开仓日确认命中胜率 `66.1157%`，但可交易因果确认只有 `48.0000%`，说明强信号很大一部分来自开仓当天市场已经展开后的信息。交易规则虽然赚更多，但 DD40 和 2x 成本失败，且 `2026` 少数大亏证明它缺少过滤反向失败的第二层结构。

## 继续价值反思

- 运行前判断：有价值。它是外生市场结构变量，不是单纯账户路径或品种年份补丁，可以回答“能不能识别高质量机会后恢复风险资金”。
- 运行后判断：仍有研究价值，但不应继续单因子交易化。
- 原因：可交易因果口径的平均 R 明显更高，说明 OI 确认抓到了一部分趋势右尾；但胜率和年度稳定性不够，必须转成多因子质量评分或 forward watch，而不是直接放大风险。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage031 结论
- 是否更新 `research/registry.md`：否，研究线已存在
- 是否追加根目录 `memory.md/back_log.md`：是，追加重要 A/C 结果和长期记忆摘要
