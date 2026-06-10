# Stage035 Stage757 增加5日OI合计2倍过滤

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-09 19:36 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 策略回测，基于 Stage757 增加 OI 恢复的强过滤条件
- 是否重要突破：否
- 是否触发A/B：是，风险放大规则可能被误认为可接正式或进入下一验证

## 外部调研与判断

- 参考资料：
  - CME Open Interest：`https://www.cmegroup.com/education/lessons/open-interest`
  - Britannica Volume & Open Interest：`https://www.britannica.com/money/futures-volume-open-interest`
  - StoneX Volume and Open Interest：`https://futures.stonex.com/technical-analysis-learning-center/volume-and-open-interest`
- 我的判断：公开资料支持“价格同向 + OI 上升”作为趋势确认，但没有资料支持“最近5日 OI 合计必须是前5日 2倍”是普世阈值。本阶段只作为用户指定的强过滤单点验证，不继续扫 `1.5/1.8/2.5`。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage761_c50_oi_confirm_recent_sum2x.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无
- 新增参数：
  - `oi_price_confirm_risk_restore_require_recent_sum_ratio`
  - `oi_price_confirm_risk_restore_recent_sum_days`
  - `oi_price_confirm_risk_restore_recent_sum_min_ratio`
- 修改参数：
  - Stage761 在 Stage757 基础上设置 `oi_price_confirm_risk_restore_require_recent_sum_ratio=True`
  - `oi_price_confirm_risk_restore_recent_sum_days=5`
  - `oi_price_confirm_risk_restore_recent_sum_min_ratio=2.0`
  - 保持 `risk_multiplier=0.40`、命中恢复到等效 `0.80`、关闭连败缩放和 recovery sleeve
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：基础成本、2x 成本、3x 成本压力
- 样本过滤：全周期日线；OI 合计条件使用策略内同一 `history["open_interest"]` 字段，取最新 `5` 根已完成日线合计与再前 `5` 根合计比较
- 策略/归因口径：
  - 先满足 Stage757 原 OI 条件：价格沿交易方向且 OI 上升
  - 再要求 `recent_5_oi_sum >= prior_5_oi_sum * 2.0`
  - 只有两者同时满足才把风险从等效 `0.40` 恢复到 `0.80`
  - 不改信号、不改 AI 池、不改品种池、不改退出

## 结果

- 期末权益：`5,565,350`
- 总收益：`1013.0700%`
- 最大回撤：`-39.7082%`
- Sharpe：`1.3285`
- 总滑点：`470,250`
- 总交易次数：`686`
- 胜率：非零交易日胜率 `52.7165%`
- 其他关键指标：
  - Stage761 与 Stage748 C50 完全一致：期末权益差 `0`、收益差约 `0pp`、回撤差 `0pp`、Sharpe 差 `0`
  - 相对 Stage757：期末权益少 `4,005,710`，收益少 `801.142pp`，回撤改善 `1.9377pp`，Sharpe 少 `0.1225`
  - Stage757 原 OI 同向确认候选：`124` 行
  - 新增 `5日合计>=前5日2倍` 后实际恢复仓位：`0` 行
  - 原 OI 同向确认候选中，`recent_5_sum / prior_5_sum`：中位数 `1.0201`，p95 `1.5067`，p99 `1.7829`，最大 `1.8100`
  - 2x 成本压力：`5,095,100/919.0200%/-42.9625%/Sharpe1.2352`
  - 3x 成本压力：`4,624,850/824.9700%/-46.4274%/Sharpe1.1425`
  - 决策：`c50_oi_confirm_recent_sum2x_not_promoted`
  - hard fail：`no_oi_restore_trades_after_recent_sum_filter`、`candidate_cost2_deployable_fail`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage761_c50_oi_confirm_recent_sum2x_report_stage761_c50_oi_confirm_recent_sum2x_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage761_c50_oi_confirm_recent_sum2x_summary_stage761_c50_oi_confirm_recent_sum2x_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage761_c50_oi_confirm_recent_sum2x_trades_stage761_c50_oi_confirm_recent_sum2x_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage761_c50_oi_confirm_recent_sum2x_curve_stage761_c50_oi_confirm_recent_sum2x_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage761_c50_oi_confirm_recent_sum2x_closed_lots_stage761_c50_oi_confirm_recent_sum2x_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage761_c50_oi_confirm_recent_sum2x_restore_group_stats_stage761_c50_oi_confirm_recent_sum2x_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage761_c50_oi_confirm_recent_sum2x_recent_sum_reason_stats_stage761_c50_oi_confirm_recent_sum2x_v1.csv`

## 结论

- 本阶段结论：`5日OI合计 >= 前5日OI合计 * 2.0` 过强，导致 Stage757 的 OI 恢复机制实际触发次数为 `0`。这不是更稳的高质量过滤器，而是把 OI 放大机制完全关闭，退化回 Stage748。
- 是否进入下一步：不进入下一步交易化验证
- 下一步：停止围绕 `2倍` 附近做阈值救参；如果继续 OI 方向，应改为先做只读分布/分位数研究，找“连续性或相对分位”是否有解释力，而不是继续硬倍数。

## 过拟合反思

- 运行前判断：有中等过拟合风险，因为 `2倍` 是强阈值且来自人工直觉，不是已验证的跨周期规则。
- 运行后判断：本次结果不是过拟合成功，而是条件完全不触发；继续扫相邻倍数会转为救参过拟合。
- 原因：原 OI 同向确认样本的最大5日合计比只有 `1.8100`，说明 `2倍` 在当前可交易 OI 口径下不是可用阈值。

## 继续价值反思

- 运行前判断：有价值，因为它检验“只在持仓量快速扩张时放大”是否能降低 Stage757 左尾。
- 运行后判断：该具体条件无继续价值。
- 原因：实际恢复次数为 `0`，没有形成可评估的策略差异；只留下一个分布信息：5日合计比可作为只读变量，但不能用 `2倍`。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：是，追加失败结论和停止扫描建议
