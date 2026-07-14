# Stage001 当前主策略基准可视化与纯规则技术归因预声明

- line_id：`futures_trend_tight_stop_quality_sizing`
- 当前模式：`research / day`
- 预声明时间：`2026-07-13 22:45 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：当前主策略全新运行、可视化、只读技术归因
- 是否重要突破：否
- 是否触发A/B：否；不改策略

## 外部调研与判断

- 趋势信号强度文献支持按趋势质量配置暴露，但波动率缩放文献同时提示收益可能只是杠杆效应。
- TA-Lib 与 Backtrader 的开源实现说明 ATR/ADX、stop 与仓位必须有透明、可复算的定义。
- 我的判断：Stage001 不能把“止损小所以手数多”误称为高质量。必须先证明小止损与后续方向性收益、损失捕获和跨年稳定性有关。

## 冻结输入

- 当前主策略入口：`analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow._run_live_c9`。
- 当前正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 起止：`2020-01-01 -> 2026-06-30`；初始资金 `150,000`。
- 当前数据库、主力映射、分钟补数与正式 AI 月池按运行时实际状态读取；AI 只维持主策略原路径，本线规则不读取 AI 字段。
- closed lots 从本次新跑的 trades、entry_risk、entry_candidates 重新 FIFO 构造，不读取任何旧研究产物。

## 时点合同

- 每个开仓事件的技术特征截止日是该合约 `entry_date` 之前最后一个完整交易日，严格 `< entry_date`。
- 入场日及之后的 OHLCVOI 不得进入技术特征。
- 原始止损距离使用本次主策略在开仓前已生成的 `stop_distance`；ATR/ADX/K线来自严格前一日及以前。
- 同一 `open_trade_id` 的分批平仓先聚合为一个开仓事件，PnL 与风险金额分别求和后再计算 R。

## 冻结技术特征

- 止损：`stop_pct`、`stop_atr14`。
- 趋势：方向化 `return20/60`、`efficiency20/60`、`range_position20/60`、`ma_stack_5_20_60`。
- 指标：Wilder `atr14`、`adx14`、方向化 `di_spread14`、`atr_pct`。
- K线：`directional_clv`、`body_ratio`、`adverse_wick_ratio`、`support_wick_ratio`、`nr7`、`inside_bar`、`compression7_atr`。
- 禁止：AI 分数/排名/概率、账户结果状态、未来 MFE/MAE、品种/年份黑名单。

## 冻结时间切分

- `discovery`：2020-01-01 至 2022-12-31。
- `validation`：2023-01-01 至 2024-12-31。
- `holdout`：2025-01-01 至 2026-06-30。
- 所有四分位阈值只由 discovery 计算；后两段不得反向改变阈值。

## 预声明复合规则族

“极小止损”固定为 discovery `stop_atr14` 的最低四分位，不搜索其他止损小数。只审计以下四个规则族：

1. `tight_directional_efficiency`：极小止损，且 `efficiency20>0`、`efficiency60>0`。
2. `tight_range_position`：极小止损，且方向化 `range_position20` 位于 discovery 最高四分位。
3. `tight_ma_adx`：极小止损、5/20/60均线顺向排列、方向化 DI 差为正、ADX14不低于 discovery 中位。
4. `tight_strong_close`：极小止损、方向收盘位置位于 discovery 最高四分位、实体占比不低于 discovery 中位。

Stage001 只做 outcome 资格审计。若多个通过，按上述顺序选择第一个，不按收益最高选择。

## 资格门

- 技术特征核心覆盖率 `>=90%`。
- 候选至少 `40` 个事件、`5` 个产品、两个方向、`5` 个自然年。
- discovery、validation、holdout 合计 R 均为正。
- 正 R 年份至少 `5` 个，负 R 年份不超过 `1` 个。
- 候选收益捕获占比高于损失捕获占比；至少 `5` 个年份保持该方向。
- 单一年份正 R 贡献不超过全部正 R 的 `60%`。
- 只有独立 agent 确认无影响结果问题，才允许进入 Stage002。

## 预期输出

- 主策略 fresh baseline daily、summary、trades、entry risk、entry candidates、closed lots。
- 资金/回撤/水下/年度贡献图。
- 止损效率、趋势位置、K线结构分布与热力图。
- drawdown episode 与开仓事件贡献表。
- discovery 阈值、单特征四分位、复合规则、年份/分段统计、feature usage audit、manifest、decision、report。

## 运行前反思

- 过拟合：中高，但受控。四个规则族、顺序、周期和时间切分已经在结果可见前冻结。
- 继续价值：有。即使所有规则失败，也能明确“小止损加仓”是否是当前主策略的真实优势还是噪声放大。
