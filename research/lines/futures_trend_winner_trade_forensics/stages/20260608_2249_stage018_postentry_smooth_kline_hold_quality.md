# Stage018 入场后早期顺畅K线质量审计

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：day
- 记录时间：2026-06-08 22:49 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读法证；判断用户“前一段时间影线短”的视觉观察是否更像入场后趋势展开初段，而不是入场前信号。
- 是否重要突破：阶段性强线索，但不是可直接上线版本。
- 是否触发A/B：触发 `skills/version-ab-experiment/SKILL.md` 的前置判断；本阶段未进入真实 A/C，只做特征审计。

## 外部调研与判断

- 参考资料：[Trend following](https://en.wikipedia.org/wiki/Trend_following)、[Pyramid trading](https://en.wikipedia.org/wiki/Pyramid_trading)、[Purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation)、GitHub [How-To-Backtest-Correctly](https://github.com/Neyt/How-To-Backtest-Correctly)、GitHub [trend-following-backtesting-strategies](https://github.com/trustdan/trend-following-backtesting-strategies)。
- 我的判断：趋势系统的右尾来自“让已经证明自己的仓位继续工作”，短影线/强实体更适合作为持仓确认或加仓观察，而不是入场前一次性放大初始风险。开源/资料支持 pyramiding/add-to-winners 的思想，但同时强调验证泄漏、过拟合和组合风险；不能直接复制成正式策略。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage735_postentry_smooth_kline_hold_quality.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：观察窗口 `post1/post2/post3/post5`；入场后残余 R 代理 `residual_r_proxy = final_r - early_move_r_proxy`；可靠性闸门要求样本、年份、品种、方向、dominant product share、residual R lift、positive residual years 等。
- 修改参数：无正式策略参数修改。
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage719 当前正式版 closed lots，全周期 `2020-01-01` 至本地数据末端。
- 账户规模：正式参考 `200,000`。
- 成本口径：复用 Stage719 已实现 closed lots；本阶段不是重新回测，不新增滑点。
- 样本过滤：closed lots `320`；各 post 窗口需有足够入场后日线。
- 策略/归因口径：只使用入场后已发生且早于退出的 K 线，判断是否可用于持仓管理/确认加仓；不用于入场前初始风险放大。

## 结果

- 期末权益：不适用；正式版参考 `8,728,285`
- 总收益：不适用；正式版参考 `4264.1425%`
- 最大回撤：不适用；正式版参考 `-38.6713%`
- Sharpe：不适用；正式版参考 `1.6279`
- 总滑点：不适用；正式版参考 `506,220`
- 总交易次数：不适用；正式版参考 `633`
- 胜率：不适用；正式版参考 `52.2586%`
- 其他关键指标：通过完整可靠性闸门特征 `9` 个。baseline `post1` 有效 `313` 笔、final avg R `0.4971`、final big winner rate `8.9457%`、residual avg R `0.3759`。最强质量特征包括：
  - `post5_smooth_directional_combo`：`34` 笔、`7` 年、`17` 品种、final avg R `5.0375`、big winner rate `44.1176%`、residual avg R `2.2510`、residual lift `+1.7789`。
  - `post2_clean_shadow_combo`：`43` 笔、final avg R `4.2690`、big winner rate `30.2326%`、residual avg R `1.8613`。
  - `post1_body60_ratio_ge50`：`92` 笔、`7` 年、`19` 品种、residual avg R `0.9058`、bad rate `10.8696%`。
  - `post1_avg_directional_close_strength_ge60`：`136` 笔、`7` 年、`19` 品种、residual avg R `0.6703`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage735_postentry_smooth_kline_hold_quality_report_stage735_postentry_smooth_kline_hold_quality_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage735_postentry_smooth_kline_hold_quality_feature_metrics_stage735_postentry_smooth_kline_hold_quality_v1.csv`
- orders：不适用
- daily：不适用
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage735_postentry_smooth_kline_hold_quality_enriched_lots_stage735_postentry_smooth_kline_hold_quality_v1.csv`

## 结论

- 本阶段结论：用户观察到的“影线短/走势顺畅”更像入场后趋势展开质量，而不是入场前所有交易初始风险放大特征。
- 是否进入下一步：是，进入固定 0.5x 确认仓代理测算。
- 下一步：只用通过闸门的特征做固定风险确认仓代理，不扫窗口、不扫倍数。

## 过拟合反思

- 运行前判断：有过拟合风险，因为这是从历史大赢家视觉印象出发。
- 运行后判断：暂时可控，但仍不能正式化。
- 原因：本阶段没有调品种/年份/红框，且用了覆盖、年份、品种、方向和残余收益闸门；但特征仍来自历史路径观察，必须进入真实 A/C 前继续压力测试。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值转向“确认后加仓/持仓管理”，不是初始加仓。
- 原因：入场前短影线两轮失败，入场后顺畅 K 线出现跨年跨品种残余收益信号。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要研究边界变化
