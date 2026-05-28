# Stage136 - Stage103 商品偏度 overlay 自验证波动闸门审计

- 时间：2026-05-28 02:46 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 工作模式：`day`
- 阶段性质：固定路径 A/C 审计。A 仍是 Stage079 `50万C3下单 + 11.5万外部现金`，C0 是 Stage103，C1/C2 是 Stage135 商品低偏度 overlay 叠加 Stage101 同源自验证闸门。
- 是否重要突破：是。`stage103_plus_low_skew252_best1_vt10_mom63_round_half_guard` 在 Stage079 原始目标下全面通过，并且通过 Stage103 增量指标与绝对 broker10 保证金窗口；但相对 Stage103 的滚动收益胜率仍不强，因此晋级为主研究/工程候选，不直接关最终策略。
- 是否触发 A/B：是。C1/C2 是可能接入 Stage103 后继候选的固定结构，属于 A/B 评估。

## 外部调研与判断

- 调研方向：交易策略自适应风险分配、rolling/self-performance filter、managed futures 趋势策略的近期表现过滤、动量策略波动管理。
- 判断：公开资料普遍支持用自有历史表现、波动目标和风险闸门控制策略承载强度，但这类方法最容易滑向“用坏窗口修坏窗口”。本阶段不为 2026 或 start_2022 单独设补丁，而是复用 Stage101 已冻结的 `10%` 年化目标波动、`63` 日自有 PnL 动量和 `0.5` round-half 执行语义，所以不是新的小参数扫描。
- 专业判断：Stage135 的低偏度 overlay 有独立收益线索，但裸信号冷启动失败；给它加一个点时化 self-validation 闸门是合理的风险承载方式。如果该固定形状仍失败，就应停止救偏度路线，不继续扫偏度窗口、top_n、目标波动或 scale 阈值。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage436_skewness_vt_guard.py`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage436_skewness_vt_guard_summary_stage436_skewness_vt_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage436_skewness_vt_guard_horizon_stage436_skewness_vt_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage436_skewness_vt_guard_score_stage436_skewness_vt_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage436_skewness_vt_guard_fresh_start_stage436_skewness_vt_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage436_skewness_vt_guard_cost_stress_stage436_skewness_vt_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage436_skewness_vt_guard_margin_audit_stage436_skewness_vt_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage436_skewness_vt_guard_pairwise_rolling_stage436_skewness_vt_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage436_skewness_vt_guard_top_edge_day_ablation_stage436_skewness_vt_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage436_skewness_vt_guard_gate_stage436_skewness_vt_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage436_skewness_vt_guard_report_stage436_skewness_vt_guard_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage436_skewness_vt_guard_chart_stage436_skewness_vt_guard_v1.png`
- 修改正式策略：无。
- 修改 Stage079/C3/Stage103 参数：无。
- 删除参数：无。

## 新增参数

- 商品偏度窗口：`SKEW_LOOKBACK_DAYS=252`
- 再平衡频率：`REBALANCE_EVERY=20`
- 自验证波动窗口：`VOL_LOOKBACK_DAYS=63`
- 自验证目标波动：`TARGET_VOL=0.10`
- 执行阈值：`ROUND_HALF_THRESHOLD=0.5`
- 执行保证金闸门：沿用 Stage103 / Stage405 的 broker10 口径，即上一日权益下 `1.10x` 保证金不穿线。
- 候选：
  - `stage103_plus_low_skew252_best1_vt10_mom63_round_half_guard`
  - `stage103_plus_low_skew252_top3_vt10_mom63_round_half_guard`

## 核心结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 总滑点 | 总交易次数 | 日胜率 | 非零日胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 1,556,750 | 757 | 36.2924% | 48.3478% |
| Stage103 | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 1,569,265 | 1,217 | 43.0809% | 50.3432% |
| best1_vt | 32,120,290 | 5122.8114% | -27.5906% | 1.3918 | 13.9133 | 1,576,215 | 1,469 | 47.5196% | 50.7671% |
| top3_vt | 31,975,995 | 5099.3488% | -29.0249% | 1.3692 | 14.3685 | 1,584,075 | 1,737 | 44.2559% | 50.0739% |

## 3个月和6个月体验

| 版本 | 3个月分 | 6个月分 | 短持有综合分 | 90日改善项 | 180日改善项 | 90日5%收益分位 | 180日5%收益分位 | 90日DD20触发率 | 180日DD20触发率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 100.0000 | 100.0000 | 100.0000 | 0 | 0 | -11.4702% | -2.0393% | 18.5052% | 35.7109% |
| Stage103 | 121.2041 | 134.4513 | 128.4901 | 6 | 6 | -10.9102% | -0.6313% | 16.6141% | 35.7109% |
| best1_vt | 141.2265 | 144.5203 | 143.0381 | 7 | 8 | -10.5553% | -0.6977% | 12.3368% | 33.4115% |
| top3_vt | 119.4041 | 132.7779 | 126.7597 | 7 | 7 | -11.0727% | -0.9097% | 16.7942% | 35.7109% |

## 多起点和保证金

- best1_vt 所有关键冷启动窗口均通过 30% 回撤闸门，并且 broker10 绝对口径无拒绝日：
  - `start_2020`：5122.8114% / -27.5906%，broker10 max margin/equity 97.3944%，拒绝 0 天
  - `start_2021`：4865.6545% / -27.0495%，broker10 max 97.0850%，拒绝 0 天
  - `start_2022`：665.6715% / -26.7753%，broker10 max 96.6279%，拒绝 0 天
  - `start_2024`：244.2447% / -28.1131%，broker10 max 93.8049%，拒绝 0 天
  - `start_2025`：212.4106% / -21.3537%，broker10 max 94.6583%，拒绝 0 天
  - `ytd_2026`：8.7138% / -20.1827%，broker10 max 50.1563%，拒绝 0 天
- top3_vt 在 `start_2022` 最大回撤为 `-32.4410%`，并且 `start_2020/start_2021/start_2022` 出现 broker10 拒绝，因此不晋级。

## 成本压力

best1_vt 在 `1x/2x/3x/5x` 滑点下最大回撤分别为：

- `1x`：-27.5906%，优于 Stage079 -29.7007%，优于 Stage103 -28.9792%
- `2x`：-29.0505%，优于 Stage079 -31.2917%，优于 Stage103 -30.4073%
- `3x`：-30.6173%，优于 Stage079 -33.0035%，优于 Stage103 -31.9135%
- `5x`：-39.1469%，不差于 Stage079 -40.1055%，不差于 Stage103 -39.1469%

## 贡献脆弱性与滚动胜率

- best1_vt 相对 Stage079 剔除最大 `20` 个正贡献日后，总收益仍为 `5033.6642%`，仍高 Stage079 `86.4041pp`，最大回撤 `-28.4838%`，Ulcer `14.3805`。
- best1_vt 相对 Stage103 剔除最大 `20` 个正贡献日后，总收益仍为 `5061.9252%`，仍略高 Stage103 `2.4268pp`，但最大回撤变成 `-29.9211%`，说明边际优势不是完全靠一两天，但厚度并不大。
- best1_vt 相对 Stage103 的滚动收益胜率不足压倒性：
  - 90日：48.1315%
  - 180日：38.4327%
  - 252日：34.3856%
  - 504日：34.4217%
- 但风险体验更稳定：相对 Stage103 的最大回撤不劣化率为 `95.3624%/95.4012%/96.5517%/100.0000%`，Ulcer 不劣化率为 `93.4264%/96.9029%/98.1544%/100.0000%`。

## 决策

- `stage103_plus_low_skew252_best1_vt10_mom63_round_half_guard` 按 Stage079 原始目标值得晋级：全周期收益、最大回撤、Sharpe、Ulcer、3个月/6个月体验、成本压力、多起点回撤、年度/季度/rolling252/rolling504 和 broker10 绝对保证金均通过。
- 但它不应被写成“最终替代 Stage103”：相对 Stage103 的多数滚动收益窗口并不占优，更多是用风险体验和左尾修复换取全周期净增益。若目标是“任何时候启动都更赚钱”，它还没有完全证明；若目标是“任何时候启动更少疼，同时不牺牲全周期收益”，它已经很强。
- `stage103_plus_low_skew252_top3_vt10_mom63_round_half_guard` 拒绝晋级：收益不错，但冷启动和 broker10 失败。
- 本阶段决策标签：`fixed_path_pass_but_robustness_gap_promote_to_engineering_paper_candidate`。

## 过拟合反思

- 运行前判断：不是直接过拟合。理由是本阶段先验来自商品偏度异常和 Stage101 已冻结 self-validation 规则，不为某个坏窗口单独设日期、品种或阈值。
- 运行后判断：仍不判定为过拟合，但不能放松警惕。它通过了多起点、成本、保证金和贡献日剔除，但相对 Stage103 滚动收益胜率偏弱，说明它更像“风险体验增强 + 小幅收益增强”，不是压倒性 alpha 升级。

## 继续价值反思

- 继续做有价值。best1_vt 是 Stage103 后第一个同时修掉 Stage135 裸偏度冷启动失败、又通过 Stage079 原始硬目标和绝对 broker10 的候选。
- 继续方式不应是扫参数；下一步只允许：
  - 固定 best1_vt 做 Stage137 严格鲁棒性与 OOS/贡献分布审计；
  - 做工程化复跑和 paper/影子盘准备；
  - 对比 Stage103 是否应以“收益优先”和“体验优先”两条候选并行。

## TODO

- 固定 best1_vt，不扫 `SKEW_LOOKBACK_DAYS`、`top_n`、`TARGET_VOL`、`VOL_LOOKBACK_DAYS`、`ROUND_HALF_THRESHOLD` 或 broker10 小数。
- Stage137 做严格晋级裁决：rolling return dominance、moving-block bootstrap、年度剔除、月份重排、真实成交成本上浮和最新增量 OOS 观察。
- 若 Stage137 仍通过，进入工程化 paper/影子盘候选；若失败，则降为研究经验并停止救偏度路线。
