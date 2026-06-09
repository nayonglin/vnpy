# Stage020 入场后确认仓 Overlay 权益代理

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：day
- 记录时间：2026-06-08 22:55 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：组合 overlay 代理；用官方 Stage719 日级权益叠加 Stage019 确认仓每日盯市增量。
- 是否重要突破：是，出现首个不依赖 0.1 豁免、且更接近组合路径的高质量机会强候选。
- 是否触发A/B：是；当前结论是“值得真实策略 A/C 设计”，不是直接推广。

## 外部调研与判断

- 参考资料：[Pyramid trading](https://en.wikipedia.org/wiki/Pyramid_trading)、[Trend following](https://en.wikipedia.org/wiki/Trend_following)、[Purged cross-validation](https://en.wikipedia.org/wiki/Purged_cross-validation)、GitHub [How-To-Backtest-Correctly](https://github.com/Neyt/How-To-Backtest-Correctly)。
- 我的判断：overlay 代理比单笔代理更接近真实目标，因为它至少检查了权益曲线和回撤。但它仍没有处理整数手、保证金、maxpos、强制减仓、额外滑点和新增仓位对后续交易资格的反身影响，所以只能作为真实 A/C 入口。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage737_postentry_addon_overlay_equity.py`
- 修改脚本：同脚本修正 `main()` 调用，改为读取 Stage736 addon lots 的 `_load_sources()`。
- 删除脚本：无
- 新增参数：`INITIAL_CAPITAL=200000.0`；候选判断为 `end_equity_delta>0` 且 `max_drawdown_delta_pp>=-5.0`。
- 修改参数：无正式策略参数修改。
- 删除参数：无

## 回测/归因参数

- 数据区间：正式 Stage719 positions 日级权益，全周期 `2020-01-01` 至本地数据末端。
- 账户规模：`200,000`。
- 成本口径：官方权益沿用 Stage719 成本；确认仓 overlay 未额外加入滑点/手续费，也未处理真实仓位约束。
- 样本过滤：Stage019 通过代理闸门的 `9` 个特征。
- 策略/归因口径：在每笔候选的 observation close 后按 `volume * size * 0.5` 构造确认仓，每日用合约 close 盯市，退出日按原交易 exit price 结算，再叠加到官方 daily equity。

## 结果

- 期末权益：最佳 overlay `11,830,067.5`；正式参考 `8,728,285`
- 总收益：最佳 overlay `5815.0338%`；正式参考 `4264.1425%`
- 最大回撤：最佳 overlay `-38.2652%`；正式参考 `-38.6713%`
- Sharpe：最佳 overlay `1.6855`；正式参考 `1.6289`
- 总滑点：overlay 未重估；正式参考 `506,220`
- 总交易次数：overlay 未重估；正式参考 `633`
- 胜率：overlay 未重估；正式参考 `52.2586%`
- 其他关键指标：候选 `9` 个均满足 `end_equity_delta>0` 且回撤恶化不超过 `5pp`。
  - `post1_avg_directional_close_strength_ge60`：rows `136`、addon PnL `3,101,782.5`、end equity `11,830,067.5`、DD `-38.2652%`、DD delta `+0.4061pp`、Sharpe `1.6855`。
  - `post1_body60_ratio_ge50`：addon PnL `2,715,290.0`、end equity `11,443,575.0`、DD `-40.0781%`、DD delta `-1.4068pp`、Sharpe `1.6660`。
  - `post1_smooth_directional_combo`：addon PnL `2,290,085.0`、end equity `11,018,370.0`、DD `-40.4769%`、DD delta `-1.8056pp`、Sharpe `1.6383`。
  - `post5_long60_ratio_le20`：addon PnL `618,922.5`、end equity `9,347,207.5`、DD delta `-0.1174pp`、Sharpe `1.6844`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage737_postentry_addon_overlay_equity_report_stage737_postentry_addon_overlay_equity_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage737_postentry_addon_overlay_equity_summary_stage737_postentry_addon_overlay_equity_v1.csv`
- orders：不适用
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage737_postentry_addon_overlay_equity_daily_equity_stage737_postentry_addon_overlay_equity_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage737_postentry_addon_overlay_equity_decision_stage737_postentry_addon_overlay_equity_v1.json`

## 结论

- 本阶段结论：入场后早期顺畅 K 线是目前最有价值的新方向；它不试图推翻三连败 `0.1`，而是在所有交易里识别“已经证明自己”的机会并考虑确认仓。
- 是否进入下一步：是，但只能进入真实策略 A/C 设计。
- 下一步：优先做一个低自由度 C 版本：官方 Stage372/20万不变，只在 `post1_body60_ratio_ge50` 或 `post1_avg_directional_close_strength_ge60` 满足后尝试 `0.5x` 确认仓；真实 A/C 必须处理整数手、保证金、maxpos、强制减仓、滑点、同一 lot 多特征去重和加仓后止损/退出。

## 过拟合反思

- 运行前判断：有风险，但值得验证。
- 运行后判断：仍有过拟合风险，不能直接上线。
- 原因：结果很强，但 overlay 代理没有真实组合约束；若下一步开始扫 `post1/post2/post5`、倍数、阈值或取 top 特征组合，就会变成历史右尾拟合。低过拟合做法是只选一个结构最宽、解释最自然的 post1 特征进入真实 A/C。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：它回答了用户观察的本质：优质趋势不是“入场前无影线”，而是“入场后市场迅速给出方向确认且不利影线/弱收盘少”。这比继续挖 0.1 豁免更贴近趋势跟随第一性原理。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是
