# Stage005 外生日线特征审计：directional_edge60 初筛候选

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-08 20:49 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：0.1 风险档高质量豁免外生日线特征只读审计
- 是否重要突破：否，得到一个初筛候选但未验证为可靠特征
- 是否触发A/B：否，本阶段只读；后续 Stage006 触发 A/C 策略回放

## 外部调研与判断

- 参考资料：
  - Donchian/区间突破类趋势过滤资料普遍把“突破后是否仍站在顺方向区间边缘”作为动量持续质量证据。
  - Triple barrier / meta-labeling 资料强调：高质量机会识别必须用入场当时可得特征、后续固定标签、walk-forward 或多窗口验证，不能用最终收益倒推。
  - GitHub 可参考 `triple_barrier` 标注框架：`https://github.com/mchiuminatto/triple_barrier`
  - 趋势和突破过滤参考：`https://www.40in20out.com/`、`https://www.tradingview.com/script/DJSQzde0-Breakout-Evidence-Board-TradeDots/`
- 我的判断：`directional_edge60` 有第一性原理，即趋势恢复机会如果是高质量的，价格应仍贴近顺方向 60 日区间边缘；但它来自历史 73 个 0.1 档样本，必须进入真实策略 A/C 回放，不能直接晋级。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage723_throttle_external_bar_features.py`
- 修改脚本：同脚本后续修正口径，把 `promoted` 改为 `initial_gate_candidate`，避免误读为已找到可靠特征。
- 删除脚本：无。
- 新增参数/门槛：
  - `MIN_RELIABLE_ROWS=30`
  - `MIN_RELIABLE_YEARS=4`
  - `MIN_RELIABLE_PRODUCTS=6`
  - `MAX_DOMINANT_PRODUCT_SHARE=35%`
  - `MIN_GOOD_LIFT_PP=10`
  - `MAX_BAD_RATE_PCT=60`
  - `directional_edge60`: long `close_pos60 >= 0.80`，short `close_pos60 <= 0.20`

## 数据和结果

- 输入：Stage716 H40 可标注 0.1 档 actionable candidates。
- 样本：
  - candidate rows：`73`
  - product bar rows：`68`
  - contract fallback rows：`5`
  - missing bar rows：`0`
  - product bar coverage：`93.1507%`
  - any bar coverage：`100.0000%`
- 初筛候选：
  - `product_directional_edge60_bucket=directional_edge`
  - 样本 `33`
  - H40 +2R first-hit good rate `42.4242%`
  - H40 -1R first-hit bad rate `57.5758%`
  - good lift `+12.2873pp`
  - avg path score `10.4346R`
  - 年份覆盖 `7`
  - good >= baseline 年份 `6`
  - 产品覆盖 `15`
  - 最大单品种占比 `18.1818%`
- 明确负项：
  - OI confirmation 本身无效：`product_directional_oi_confirm20=oi_confirm` good rate `30.3030%`，bad `69.6970%`。
  - volume/OI 叠加后的 `edge_with_volume_oi` 样本仅 `14`，不足以作为规则。

## 输出文件

- enriched candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage723_throttle_external_bar_features_enriched_candidates_stage723_throttle_external_bar_features_v1.csv`
- feature metrics：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage723_throttle_external_bar_features_feature_metrics_stage723_throttle_external_bar_features_v1.csv`
- year detail：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage723_throttle_external_bar_features_year_detail_stage723_throttle_external_bar_features_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage723_throttle_external_bar_features_decision_stage723_throttle_external_bar_features_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage723_throttle_external_bar_features_report_stage723_throttle_external_bar_features_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage723_throttle_external_bar_features_chart_stage723_throttle_external_bar_features_v1.png`

## 结论

- 决策：`external_bar_initial_gate_candidate_requires_strategy_ab_validation`
- 这不是可靠特征，只是一个值得 A/C 验证的低自由度候选。
- 下一步：Stage006 将把它接成默认关闭的策略参数，验证“通过 directional_edge60 后恢复正常风险 sizing”是否能穿越多窗口。

## 过拟合反思

- 运行前判断：有过拟合风险。样本只有 `73`，且目标直接来自历史 0.1 档机会。
- 运行后判断：不是正式过拟合结论，但风险仍高。Stage005 没有拼多条件，也没有按品种/年份/红框筛选；但初筛候选必须经真实策略回放，不能直接交易化。

## 继续价值反思

- 运行前判断：有价值。它把研究从现有内部字段组合转向外生日线结构。
- 运行后判断：有价值进入一次 A/C 验证，但不值得继续叠加 volume/OI/roll 条件救参。
- 原因：单一 `directional_edge60` 有解释力；volume/OI 等辅助条件样本不足或指标无效。
