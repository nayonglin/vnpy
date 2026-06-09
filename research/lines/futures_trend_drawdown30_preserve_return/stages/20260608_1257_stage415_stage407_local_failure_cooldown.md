# Stage415 Stage407 全局连败替换为局部品种方向冷却反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 12:57 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：机制归因 + 固定单点反证
- 是否重要突破：否，但属于关键负结论
- 是否触发A/B：否，未通过晋级条件

## 外部调研与判断

- 参考资料：
  - AQR `Trend Following` 研究：趋势跟踪的核心是多市场、低相关、可重复的趋势暴露，而不是事后挑单一市场或单一窗口。
  - Hurst/Ooi/Pedersen `A Century of Evidence on Trend-Following Investing`：趋势跟踪长期有效来自跨资产分散和规则化风险控制，弱化了单品种曲线拟合的可信度。
  - Man Group 关于 trend following market mix 的研究：扩市场有价值，但新增市场必须提升组合层机会集，不能破坏原核心右尾路径。
- 我的判断：把“全局账户连败 0.1”替换为“同品种同方向失败冷却”有机制合理性，因为一个品种的假突破不应直接压低所有无关品种仓位；但固定结果显示该替换会破坏正式版全周期收益和回撤，不能作为当前答案。红框增长消失的主因仍是 AI rerank top9 改写入池路径并挤掉核心右尾，连败风控只是后续放大器。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage702_stage407_local_failure_cooldown.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `product_direction_failure_cooldown_enabled=True`
  - `product_direction_failure_cooldown_lookback_days=252`
  - `product_direction_failure_cooldown_min_consecutive_failures=3`
  - `product_direction_failure_cooldown_days=90`
  - `product_direction_failure_cooldown_entry_contexts=flat_entry`
- 修改参数：
  - D/C 候选运行期 `streak_risk_multipliers 1.0,1.0,1.0,0.1 -> 1.0,1.0,1.0,1.0`
  - C 继续保持 `jd.DCE` 参与原 AI 池 rerank top9，`max_concurrent_positions=5`
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用当前 Stage372/Stage407 全周期，红框重点窗口 `2025-04-16` 至 `2025-07-25`
- 账户规模：`200,000`
- 成本口径：正常成本，另保留 2x/3x 成本压力输出
- 样本过滤：无未来数据；AI eligibility 按原 Stage407 点时月度池
- 策略/归因口径：
  - A：正式 Stage372/20w `maxpos4` 原版
  - D：正式版关闭全局连败降风险，替换为同品种同方向 `3 losses / 252d / 90d` flat-entry 冷却
  - B：Stage407 原 AI 池 + `jd.DCE` 参与 AI rerank top9 + `maxpos5`
  - C：B 关闭全局连败降风险，替换为同品种同方向冷却

## 结果

- A 正式版：
  - 期末权益：`8,728,285`
  - 总收益：`4264.1425%`
  - 最大回撤：`-38.6713%`
  - Sharpe：`1.6279`
  - 总滑点：`506,220`
  - 总交易次数：`633`
  - 胜率：`52.2586%`
- D 正式版局部冷却：
  - 期末权益：`3,026,025`
  - 总收益：`1413.0125%`
  - 最大回撤：`-48.7981%`
  - Sharpe：`1.1655`
  - 总滑点：`287,280`
  - 总交易次数：`663`
  - 胜率：`52.2904%`
- B Stage407 原版：
  - 期末权益：`3,284,935`
  - 总收益：`1542.4675%`
  - 最大回撤：`-33.2821%`
  - Sharpe：`1.3858`
  - 总滑点：`298,030`
  - 总交易次数：`688`
  - 胜率：`51.7181%`
- C Stage407 局部冷却：
  - 期末权益：`3,182,730`
  - 总收益：`1491.3650%`
  - 最大回撤：`-54.4892%`
  - Sharpe：`1.1731`
  - 总滑点：`315,740`
  - 总交易次数：`703`
  - 胜率：`52.4823%`
- 红框窗口：
  - A：`+5,605,230`
  - D：`+2,090,740`
  - B：`+90,830`
  - C：`+1,797,090`
  - C 相对 B 修复 `+1,706,260`，但仍比 A 少 `3,808,140`
- 红框开仓/仓位归因：
  - A 红框 opened `7` 行，开仓手数合计 `1,378`，已开仓中位 `target_risk_amount=156,515`
  - B 红框 opened `6` 行，开仓手数合计 `295`，已开仓中位 `target_risk_amount=12,913`
  - C 红框 opened `6` 行，开仓手数合计 `404`，已开仓中位 `target_risk_amount=63,819`
  - B 中 `fu.SHFE` 在 `2025-06-11` 被 `ai_product_pool_blocked`，而 A 同日开 `281` 手
  - B 中 `2025-07-08/09` 的 `jm/FG/si` 分别只开 `9/24/10` 手，A 分别开 `142/359/179` 手
- AI 审计：
  - `jd.DCE` 在 51 个 eval_date 中选中 `46` 次，平均 rank `6.1304`
  - 红框附近 `2025-04-30` 鸡蛋 rank `1`，`2025-05-30` rank `4`，`2025-06-30` rank `9`，`2025-07-31` rank `8`
  - 鸡蛋不是偶发进入，而是长期占用 top9 名额并改变原池排序
- 冷却机制自身：
  - C 全周期 `product_direction_failure_cooldown_blocked_rows=23`
  - C 红框 `blocked_rows=1`，说明红框主要不是被新冷却挡掉，而是 AI 入池与全局连败路径问题

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage702_stage407_local_failure_cooldown_report_stage702_stage407_local_failure_cooldown_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage702_stage407_local_failure_cooldown_summary_stage702_stage407_local_failure_cooldown_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage702_stage407_local_failure_cooldown_daily_stage702_stage407_local_failure_cooldown_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage702_stage407_local_failure_cooldown_entry_candidates_stage702_stage407_local_failure_cooldown_v1.csv`
- entry_risk_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage702_stage407_local_failure_cooldown_entry_risk_summary_stage702_stage407_local_failure_cooldown_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage702_stage407_local_failure_cooldown_chart_stage702_stage407_local_failure_cooldown_v1.png`
- equity_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage702_stage407_local_failure_cooldown_equity_only_stage702_stage407_local_failure_cooldown_v1.png`

## 结论

- 本阶段结论：`stage407_no_global_streak_local_cooldown_not_promoted`。红框增长消失不是因为鸡蛋自己亏钱，也不是保证金不够，而是“AI rerank top9 改写原核心池 -> `fu/jm/si/FG/lc` 等右尾机会缺失或小仓 -> 全局连败 0.1 进一步把后续仓位压小”的路径效应。
- 是否进入下一步：本机制不进入下一步，不接正式版，不做 A/B。
- 下一步：
  - 停止在主账户上继续扫连败倍率、冷却天数、lookback、小数阈值。
  - 若还研究鸡蛋，优先做非挤占式独立 sleeve / 独立风险预算，或只读 forward 监控。
  - 若还研究 AI，必须先重训/重定义 selector 目标，使其不挤掉正式版核心右尾，而不是在原概率 topN 上调 `top8/top9/top10`。

## 过拟合反思

- 运行前判断：不是典型过拟合，因为只跑一个有机制含义的固定替代方案，未按窗口、品种或年份扫参。
- 运行后判断：若继续沿 `252/90/3`、冷却天数、连败倍率或 topN 调参，会快速过拟合。
- 原因：该机制在红框上有局部修复，但正式版全周期从 `8,728,285` 降到 `3,026,025`，Stage407 也从 `3,284,935` 降到 `3,182,730` 且回撤恶化到 `-54.4892%`；局部修复不能覆盖全周期路径破坏。

## 继续价值反思

- 运行前判断：有价值，因为它验证“全局连败是否误伤无关品种趋势”的机制边界。
- 运行后判断：这条机制本身无继续价值，但归因结论有价值。
- 原因：它证明全局连败确实是红框放大器，却也证明简单局部冷却无法替代正式风控；真正要解决鸡蛋问题，不能继续救共享 top9 主池，应转向非挤占式 sleeve 或重建账户级 AI selector。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage415 当前状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，追加关键负结论和后续禁区。
