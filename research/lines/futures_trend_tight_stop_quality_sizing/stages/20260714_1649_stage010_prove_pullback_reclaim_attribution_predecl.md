# Stage010 趋势证明-回踩-再确认紧止损归因预声明

- line_id：`futures_trend_tight_stop_quality_sizing`
- 当前模式：`research / day`
- 记录时间：`2026-07-14 16:49 CST`
- 阶段性质：机制完全不同于 Stage009 的分钟因果归因，不改变策略、不产生组合收益候选
- 是否重要突破：否
- 是否触发 A/B：否；只有 Stage010 统计门与独立复核均通过，才允许另行预声明唯一真实引擎阶段
- 正式实盘影响：无；不得修改正式策略、AI 月池、CTP、邮件或 launchd

## 前置结论与研究问题

- Stage009 已由独立 reviewer 以 `P0/P1/P2/P3=0/0/0/0` 闭环，直接开盘推进加小止损的固定结构 1R/2R target-first 仅 `45.21%/25.71%`，该分支关闭且禁止窗口或阈值救参。
- Stage010 不再问“开盘后是否继续追”，而是问：原日线方向先得到真实价格证明，随后回踩原计划入场位并重新收复时，是否形成跨品种、跨方向、跨年份的紧止损机会。
- 本阶段只做事件级归因；first-touch、母策略 PnL/R 和窗口收益均不得称作组合回测或可执行收益。

## 外部调研与判断

- Howard《Stop Distance, Exit Methodology, and Signal Preservation in Intraday Value Area Breakouts》使用一秒级 E-mini 数据，发现浅回踩优于深回踩，但十二种价格止损都可能损害原信号，且开盘前 30 分钟事件更差。
  - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6350238
- Hachemian / Tavernier / Van Royen《The Significance of Trading Frequency and Stop Loss in Trend Following Strategies》发现更高交易频率未显著改善同一趋势模型，止损只在防止极端损失时更明确，常规损失区间效果模糊。
  - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2349848
- `backtesting.py` 的公开引擎代码明确区分信号 bar 与下一 bar 开盘市价成交；其 breakout 讨论也暴露同 bar 同时触发入场/止损时仅靠 OHLC 无法还原真实路径。
  - https://github.com/kernc/backtesting.py/blob/master/backtesting/backtesting.py
  - https://github.com/kernc/backtesting.py/discussions/1295
- QuantDinger 的 GitHub 文档提供 breakout-retest 状态机示例，但包含大量可调窗口、buffer、均线和成交量阈值，只能参考状态机表达，不能作为收益证据或复制其参数。
  - https://github.com/brokermr810/QuantDinger/blob/main/docs/STRATEGY_DEV_GUIDE_CN.md
- 我的判断：浅回踩是可检验假设，不是已证明 alpha；价格止损本身很可能切断右尾。Stage010 必须固定单一状态机、下一分钟 open 执行和保守同 bar 顺序，先以负向检验为默认。

## 冻结母集与分段

1. 母集仍为 Stage008 当前正式版 `300` 个初次根开仓事件；stop retry、rollover 和加减仓不产生新机会样本。
2. 分钟数据只用 Stage000 完整入场会话 patch；历史 tick 沿用 Stage009 已修复规则：`lc.GFEX` 在 `2024-12-18` 交易日前为 `50`，当日起为 `20`。
3. `2020-2022` 为 discovery；`2023-2024` 为 historical locked validation；`2025-2026` 为 historical locked late evaluation。后两段不是真正未见 OOS。
4. 只允许落盘 discovery 的逐事件候选特征和结果；后段仅保存白名单候选特征 hash、行数、状态分布和覆盖，不落逐行结果。
5. 正式 AI 月池保持原路径，Stage010 新增 AI 特征数固定为 `0`，禁止按 AI rank/score 分组。

## 冻结状态机

对每个方向定义 `sign=+1/-1`，`E_actual` 为根开仓实际成交价，`R_actual` 为实际成交到原始初始止损的距离，`E_plan` 为信号时已知的原计划入场价。

1. **趋势证明与先失败**
   - 证明价：`E_actual + sign * 0.5 * R_actual`。
   - 先失败价：`E_actual - sign * 0.5 * R_actual`，与当前正式版开仓日实时 `0.5R` 止损尺度一致。
   - 从会话第一分钟开始逐 bar 检查；同 bar 同时触及证明价与先失败价，固定先失败，事件不再形成 Stage010 候选。
   - 不扫描 `0.25R/0.75R/1R`，也不在失败后使用 retry 事件救样本。
2. **首次回踩**
   - 证明 bar 完成后，最早从下一 bar 寻找首次触及 `E_plan` 的回踩；证明和回踩不能在同 bar 排序。
   - 多头用 `low <= E_plan`，空头用 `high >= E_plan`。
   - 若回踩前或回踩过程中先触及上述 `-0.5R` 失败价，同 bar 仍按失败优先，候选终止。
3. **再确认**
   - 从首次回踩 bar 起，找到第一根 close 重新位于 `E_plan` 有利侧的 bar；回踩 bar 自身可以完成再确认，但只在该 bar 完成后决策。
   - 决策时必须已经完成会话最初 `30` 根一分钟 K；不足 30 分钟的早期再确认只记状态，不允许延迟等到第 30 分钟后自动转候选。
   - 最早反事实成交为再确认 bar 的下一根真实一分钟 K 的 open。
   - 下一根 open 若不再位于 `E_plan` 有利侧，或已越过结构止损，不成交、不可用后续 bar 补救。
4. **结构止损与紧风险门**
   - 多头止损为首次回踩至再确认期间最低 low 减 `1` 个历史有效 tick；空头为最高 high 加 `1 tick`。
   - 反事实风险为下一根 open 到结构止损的距离，必须 `>=1 tick` 且 `<=0.5 * R_actual`。
   - 不扫描 tick buffer、风险比例或回踩深度阈值；超过 `0.5R` 直接记为结构不够紧。

## 冻结特征与标签

候选白名单特征只来自当时已完成分钟 K、方向和信号时已知几何：

- `proof_bar_index/time`、`proof_excursion_actual_r`
- `retest_bar_index/time`、`retest_depth_actual_r`
- `reclaim_bar_index/time`、`retest_duration_bars`
- `reclaim_close_distance_actual_r`、`reclaim_directional_body_actual_r`、`reclaim_close_location`
- `counterfactual_entry_time/price`
- `structural_stop_price`、`micro_stop_distance`、`micro_stop_actual_risk_ratio`
- `completed_minutes_before_decision`
- 状态枚举：`prior_half_r_stop/no_proof/no_retest/no_reclaim/early_reclaim/no_next_bar/next_open_lost_reclaim/gap_beyond_stop/micro_stop_too_wide/candidate`

结果标签：

- `micro_first_touch_1r/2r`：从反事实成交 bar 开始比较结构止损 `-1R` 与 `+1R/+2R`；同 bar 止损优先。
- `return_5m/15m/60m_micro_r`：按窗口末根 close 计算，不足窗口记缺失，不跨会话补值。
- `baseline_realized_pnl/r_multiple`：只看候选是否保留母策略右尾，不等于反事实策略收益。
- 每个候选汇总事件数、品种数、方向数、年份数、1R/2R 命中、Wilson 区间、母策略总 R/中位 R和年度分解。

## 硬门与停止规则

1. discovery 候选必须 `>=30`、覆盖 `>=3` 年、两个方向且至少 `8` 个品种，否则直接关闭，不放宽 30 分钟、0.5R、回踩锚点或 stop ratio。
2. 三个 discovery 年份都必须有候选；不得删除亏损年、品种或方向。
3. 进入真实引擎的 first-touch 门固定为：整体 2R target-first 点估计 `>33.33%`，且 Wilson 95% 下界也 `>33.33%`；2020/2021/2022 三个年度点估计都必须 `>33.33%`。这是无成本 `-1R/+2R` 的最低盈亏平衡门，不因样本小而放宽。
4. 候选对应的母策略 baseline total R 必须在 2020/2021/2022 三年分别为正，防止小止损机会集中在原策略左尾而丢失趋势右尾。
5. 1R/2R first-touch、年度稳定性和母策略右尾只用于判断是否值得进入真实引擎，不按结果搜索组合条件。
6. Stage010 只允许这一个状态机；失败后不尝试 `20/45/60` 分钟、不改 proof R、不使用 EMA/RSI/成交量/品种补丁救参。
7. 即使归因通过，也只允许预声明一个真实引擎；真实引擎仍必须满足四锚点收益保留 `>=70%` 与回撤门，并计入滑点、手续费、整数手、保证金、broker10 和当前 `0.5R` retry 交互。

## 完整性与独立复核

- 先写单元测试覆盖 long/short、proof 与 stop 同 bar、proof/retest 不同 bar、同 bar retest+reclaim、30 分钟边界、下一 bar open、历史 LC tick、gap 越止损、1R/2R 同 bar stop-first。
- 母集守恒、分钟覆盖、因果时间、分段隔离、后段 feature seal 和 manifest 均 fail-close。
- 跑完数据必须拉一个新的独立 agent 复算状态机、标签、年度统计、seal、manifest 和结论；所有影响结果问题修复后按同一预声明原口径重跑。

## 运行前反思

- 过拟合：是，高。Stage010 是在看到 Stage009 失败后选择的第二个分钟结构，历史复用无法消除；通过唯一状态机、固定 0.5R、30 分钟、下一 bar open 和禁止失败后救参限制自由度。
- 继续价值：是，但仅限一次归因。机制与 Stage009 的立即追价不同，符合“方向先证明、回踩降低止损距离、再确认”的第一性原理；同时外部证据警告紧止损可能毁掉趋势右尾，因此失败应立即停止整个分钟紧止损方向。
