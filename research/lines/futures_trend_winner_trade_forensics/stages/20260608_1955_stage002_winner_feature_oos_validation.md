# Stage002 赢家特征跨年/OOS可靠性验证

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-08 19:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：基于 Stage719 正式版 closed-lot 逐笔法证表做只读跨年稳定性和时间顺序 OOS 验证。
- 是否重要突破：否；属于重要反证与特征可靠性筛查。
- 是否触发A/B：否。本阶段不改正式策略、不生成候选交易规则、不连接 CTP、不调用下单。

## 外部调研与判断

- 参考资料：
  - Walk-forward analysis：`https://tradingstrategy.ai/glossary/walk-forward-analysis`
  - 参数稳健性/OOS 验证：`https://quanthop.com/learn/backtesting-optimization/parameter-optimization`
  - R-multiple、MFE/MAE 交易复盘：`https://forexmechanics.com/traders-workshop/journal-metrics/`
  - Python MFE/MAE 几何分析参考：`https://pypi.org/project/trade-geometry-analyzer/0.1.0/`
- 我的判断：Stage719 的全样本赢家画像只能生成线索，不能证明可靠。Stage720 必须把“品种名”与“通用状态特征”隔离；如果允许品种名进入选择器，很容易把 FG/OI/jm 这类历史赢家品种包装成规律，属于品种过拟合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage720_winner_feature_oos_validation.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `MIN_SELECTOR_TRAIN_COUNT=12`
  - `MIN_SELECTOR_TRAIN_YEARS=2`
  - `MIN_SELECTOR_YEAR_POSITIVE_RATE=0.60`
  - `MIN_SELECTOR_AVG_R_EDGE=0.25`
  - `MAX_SELECTOR_TRAIN_CAPTURE=0.75`
  - `MAX_SELECTOR_FEATURES=6`
- 修改参数：无策略参数修改；仅分析口径里排除 `product` 作为时间顺序选择器特征，避免品种名过拟合。
- 删除参数：无。

## 回测/归因参数

- 数据来源：Stage719 输出 `closed_lots`。
- 原始 closed lots：`320`。
- 可用于 R 倍数验证的 closed lots：`313`。
- 剔除记录：`7` 笔，原因是没有可用 `r_multiple`/风险距离，不进入 Stage720 的 R 倍数统计。
- 正式版账户参考结果沿用 Stage719：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
- 本阶段自身不重跑账户权益曲线，只做逐笔 closed-lot 特征验证。

## 验证方法

- 预声明候选特征来自 Stage719：
  - 正向候选：`loss_streak_1_2`、`risk_normal`、`stop_1_2pct`、`active_0`、`long_rsi_60_70`、`rollover_reopen`
  - 压力候选：`long_case3`、`ai_rank_1_3`
  - 负向对照：`risk_floor_01`、`loss_streak_ge3`、`recovery`
- 逐年稳定性：看每个特征按 entry year 的 total R、avg R、胜率、年份正贡献、品种集中度。
- 时间顺序 OOS：每个目标年份只用此前年份训练，训练期选择满足样本数、年份正贡献、avg R 边际和右尾率的通用特征；目标年只评估被选特征 union，不使用目标年结果参与选择。
- 选择器特征列不包含 `product`，避免历史品种赢家泄漏为未来规则。

## 结果

- Stage720 决策：`positive_state_watch_negative_filter_confirmed_no_trade_rule_promotion`
- `loss_streak_1_2`：
  - 样本 `118`
  - avg R `1.8309`
  - total R `216.0465`
  - 胜率 `53.3898%`
  - big winner rate `13.5593%`
  - 年份正贡献 `6/7`
  - 覆盖 `17` 个品种，最大单品种占比 `10.1695%`
  - 分类：`relatively_reliable_positive_state`
- `risk_normal`：
  - 样本 `262`
  - avg R `0.7473`
  - total R `195.7890`
  - 年份正贡献 `6/7`
  - 分类：`broad_risk_baseline_not_quality_trigger`
  - 判断：它是正常风险环境，不是单独的高质量机会触发器。
- `risk_normal_any_stage719_positive`：
  - 样本 `213`
  - avg R `1.0757`
  - total R `229.1342`
  - 年份正贡献 `6/7`
  - 判断：全样本很好，但时间顺序选择器没有稳定通过，不能直接交易化。
- `rollover_reopen`：
  - 样本 `22`
  - avg R `1.0836`
  - 年份正贡献 `6/6`
  - 分类：`small_sample_positive_watch`
  - 判断：值得继续观察，但样本太小，不能当主规则。
- `stop_1_2pct`、`active_0`、`long_rsi_60_70`：
  - 均为 `positive_watch_needs_oos_gate`
  - 分别为 `106/83/67` 笔，年份正贡献均为 `5/7`
  - 判断：有正向倾向，但 2022/2024 这类弱年份并不能稳定保护。
- 负向对照：
  - `risk_floor_01`：`51` 笔，avg R `-0.7885`，年份正贡献 `1/7`
  - `loss_streak_ge3`：`64` 笔，avg R `-1.3237`，年份正贡献 `1/7`
  - `recovery`：`13` 笔，avg R `-3.4233`，年份正贡献 `1/5`
  - 判断：负向特征比正向特征更稳定，支持 `>=3` 连败后低风险档的防守意义。
- 时间顺序 OOS 选择器：
  - 可验证目标年 `5` 个：`2022~2026`
  - 被选特征 union 跑赢全体：`2/5`
  - 被选特征 union total R 为正：`3/5`
  - 2022：selected avg R `-0.3243`，all avg R `-0.2315`，未跑赢
  - 2023：selected avg R `0.4795`，all avg R `0.4901`，未跑赢
  - 2024：selected avg R `-0.7716`，all avg R `-0.7226`，未跑赢
  - 2025：selected avg R `3.5209`，all avg R `2.5965`，跑赢
  - 2026：selected avg R `0.2070`，all avg R `0.1025`，跑赢

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage720_winner_feature_oos_validation_report_stage720_winner_feature_oos_validation_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage720_winner_feature_oos_validation_chart_stage720_winner_feature_oos_validation_v1.png`
- feature reliability：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage720_winner_feature_oos_validation_feature_reliability_stage720_winner_feature_oos_validation_v1.csv`
- feature year：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage720_winner_feature_oos_validation_feature_year_stage720_winner_feature_oos_validation_v1.csv`
- suite summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage720_winner_feature_oos_validation_suite_summary_stage720_winner_feature_oos_validation_v1.csv`
- suite year：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage720_winner_feature_oos_validation_suite_year_stage720_winner_feature_oos_validation_v1.csv`
- selector features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage720_winner_feature_oos_validation_selector_features_stage720_winner_feature_oos_validation_v1.csv`
- selector year：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage720_winner_feature_oos_validation_selector_year_stage720_winner_feature_oos_validation_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage720_winner_feature_oos_validation_decision_stage720_winner_feature_oos_validation_v1.json`

## 结论

- 本阶段结论：能称为“相对可靠”的正向特征目前只有一个，即 `loss_streak_1_2`：连续亏损 `1~2` 笔但尚未进入 `0.1` 风险档的状态。它不像单品种或单年份右尾，覆盖品种较分散，年份正贡献 `6/7`，avg R 明显高于全体。
- 但它仍不能单独交易化。原因是通用正向特征选择器只在 `2/5` 个 OOS 年份跑赢全体，说明“正向特征组合”尚不能稳定识别未来赢家。
- 更稳的结论反而是负向：`loss_streak_ge3`、`risk_floor_01`、`recovery` 明显不是赢家来源。这支持现有连败 `>=3` 后低风险档的底层逻辑：它不是为了赚钱，而是为了少在坏状态里暴露。

## 过拟合反思

- 运行前判断：过拟合风险高。Stage719 的候选来自全样本画像，天然有赢家倒推风险。
- 运行后判断：正向特征仍有过拟合风险，不能推广成规则；负向特征过拟合风险较低。
- 原因：`loss_streak_1_2` 经跨年和品种分散性检查较稳，但时间顺序选择器整体未通过；而 `loss_streak_ge3/risk_floor_01/recovery` 在绝大多数年份都差，是更像机制而不是拟合的证据。

## 继续价值反思

- 运行前判断：有价值。它直接回答“历史赢家到底有什么相对可靠特征”。
- 运行后判断：有价值继续，但不该继续扩大特征组合或扫阈值。
- 原因：目前可以把 `loss_streak_1_2` 当成高质量机会豁免机制里的一个必要组件或加分项，把 `loss_streak_ge3/risk_floor/recovery` 当成 veto/低风险状态；下一步若交易化，必须另开 A/B 或 A/C，用预声明规则验证“连败后默认 0.1，但 `loss_streak_1_2` 等质量状态允许不降档/半降档”的净效果。

## 后续 TODO

- 不使用品种名作为交易规则。
- 不直接使用完整正向 selector 交易化。
- 若继续质量豁免，候选只允许从 `loss_streak_1_2` 出发，最多叠加一个非结果型条件，例如 `risk_normal` 或 `stop_1_2pct`，并先走独立 A/B。
- 继续补充逐笔路径层复盘：`loss_streak_1_2` 的大赢家是否先经历较大 MAE、是否依赖 2025 右尾、是否有退出效率问题。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：可选；本次不是正式合入，但建议把本线最新阶段从 Stage001 更新为 Stage002。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选合入。
