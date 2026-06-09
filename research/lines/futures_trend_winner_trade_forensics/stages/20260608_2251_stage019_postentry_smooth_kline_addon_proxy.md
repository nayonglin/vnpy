# Stage019 入场后顺畅K线确认仓单笔代理

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：day
- 记录时间：2026-06-08 22:51 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：代理测算；只对 Stage018 通过特征模拟观察完成后增加固定 `0.5x` 原交易风险确认仓。
- 是否重要突破：阶段性强线索，但仍不是正式回测。
- 是否触发A/B：触发前置 A/C 判断；本阶段仍为单笔代理，不改正式版。

## 外部调研与判断

- 参考资料：[Pyramid trading](https://en.wikipedia.org/wiki/Pyramid_trading)、GitHub [trend-following-backtesting-strategies](https://github.com/trustdan/trend-following-backtesting-strategies)、[Purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation)。
- 我的判断：如果做加仓，低过拟合版本应是“趋势已证明后，用固定小确认仓参与右尾”，而不是继续扫 `0.3/0.5/0.8`、`1/2/3/5` 窗口或特征组合。本阶段固定 `0.5x` 只是压力前测。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage736_postentry_smooth_kline_addon_proxy.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`ADDON_RISK_FRACTION=0.50`；代理 PnL `addon_residual_r_proxy * original_risk_amount * 0.5`。
- 修改参数：无正式策略参数修改。
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage018 enriched lots，全周期。
- 账户规模：正式参考 `200,000`。
- 成本口径：代理测算不额外加入滑点/手续费，不处理真实保证金、整数手、排队、maxpos 和组合强制减仓。
- 样本过滤：只使用 Stage018 `passes_reliable_gate=True` 的 `9` 个特征。
- 策略/归因口径：观察窗口结束后，假设增加原交易风险 `0.5x` 的确认仓，只赚取观察点到实际退出之间的残余路径。

## 结果

- 期末权益：不适用；正式版参考 `8,728,285`
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：通过代理闸门特征 `9` 个；最佳总代理增量 `3,101,782.5`。
  - `post1_avg_directional_close_strength_ge60`：`136` 笔、`7` 年、`19` 品种、total proxy `3,101,782.5`、avg residual R `0.6703`、positive years `7`、worst year `+37,447.5`。
  - `post1_body60_ratio_ge50`：`92` 笔、total proxy `2,715,290.0`、avg residual R `0.9058`、positive years `7`、bad rate `10.8696%`。
  - `post1_smooth_directional_combo`：`56` 笔、total proxy `2,290,085.0`、avg residual R `1.0891`、positive years `7`。
  - `post5_smooth_directional_combo`：`34` 笔、avg residual R `2.2510`、final big winner rate `44.1176%`，但 worst year 为 `-103,500.0`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage736_postentry_smooth_kline_addon_proxy_report_stage736_postentry_smooth_kline_addon_proxy_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage736_postentry_smooth_kline_addon_proxy_addon_metrics_stage736_postentry_smooth_kline_addon_proxy_v1.csv`
- orders：不适用
- daily：不适用
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage736_postentry_smooth_kline_addon_proxy_addon_lots_stage736_postentry_smooth_kline_addon_proxy_v1.csv`

## 结论

- 本阶段结论：入场后顺畅 K 线特征在单笔代理上明显优于入场前短影线，值得进入组合 overlay 验证。
- 是否进入下一步：是。
- 下一步：把确认仓每日 PnL 叠加到官方日级权益，检查期末权益、回撤和 Sharpe，而不是只看单笔总收益。

## 过拟合反思

- 运行前判断：有风险。
- 运行后判断：风险仍在，但比入场前规则更合理。
- 原因：固定 `0.5x`、只用 Stage018 已通过特征，没有继续扫倍数；但代理没有处理组合层约束，不能作为上线证据。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：多个跨年跨品种特征在残余收益上为正，且 `post1` 类特征不需要等到持仓很后期才确认，具备真实策略可操作性。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是
