# Stage189 补齐3月/4月AI池并重跑冷启动

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-09 14:50 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：准实盘影子盘口径审计 / 月度AI池缺口回填
- 是否重要突破：否
- 是否触发A/B：否。本阶段不修改策略参数，只补齐缺失的AI月度输入。

## 外部调研与判断

- 参考资料：
  - vn.py/VeighNa 文档和 portfolio strategy 资料确认组合策略回测支持多标的历史回放、初始资金、统计指标和可视化输出。
  - 本仓库第78 AI池切换逻辑以本地 `eval_date` eligibility 和策略代码为准。
- 我的判断：
  - 补齐 `2026-03-31` 池是时序一致性修复，不是策略优化。
  - 若影子盘使用月度AI池，缺一个月池会让整个月沿用过期池，足以改变开仓。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_stage189_ai_product_pool_backfill_multimonth.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `--eval-dates`：默认 `2026-03-31,2026-04-30`
  - `--source-prefix`：默认 `qmt_roll_stage183_ai_source_floor35`
- 修改参数：
  - 回放使用 Stage189 combined eligibility 作为 `ai_product_pool_eligibility_path`。
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - 指标预热：2025-01-01 至 2025-12-31
  - 交易分析：2026-01-01 至 2026-05-08
- 账户规模：300,000
- 成本口径：沿用 Stage78/Stage186 日线回测滑点与手续费口径
- 样本过滤：第78正式趋势策略，30万冷启动
- 策略/归因口径：
  - 固定 `official_stage78_defensive_v1`
  - 仅替换 AI eligibility 输入

## AI池回填结果

- `2026-03-31`
  - training_label_cutoff：2025-12-25
  - train_rows：1,278
  - train_months：71
  - selected_products：`SH.CZCE`, `jm.DCE`, `cu.SHFE`, `FG.CZCE`, `SA.CZCE`, `sp.SHFE`, `ru.SHFE`, `lh.DCE`, `fu.SHFE`
- `2026-04-30`
  - training_label_cutoff：2026-01-27
  - train_rows：1,296
  - train_months：72
  - selected_products：`SA.CZCE`, `SH.CZCE`, `FG.CZCE`, `si.GFEX`, `MA.CZCE`, `jm.DCE`, `rb.SHFE`, `AP.CZCE`, `fu.SHFE`
- combined eligibility：
  - min eval_date：2019-12-31
  - max eval_date：2026-04-30
  - unique eval_dates：53
  - 不覆盖正式 Stage78 eligibility

## 结果

- 期末权益：283,190
- 总收益：-5.6033%
- 最大回撤：-20.6840%
- Sharpe：-0.4147
- 总滑点：2,275
- 总交易次数：22
- 胜率：10.00%
- 其他关键指标：
  - 目标日：2026-05-08
  - 目标日信号数：1
  - 目标日信号：`si2609.GFEX` Long Open 1手，理论价 9,025
  - 目标日风险级别：`watch`
  - 触发原因：`drawdown_watch`
  - 是否允许影子盘记录：1
  - 是否允许真实新增开仓：1

## 对比

| 指标 | Stage186旧池 | Stage188只补4月池 | Stage189补3月+4月池 |
| --- | ---: | ---: | ---: |
| 期末权益 | 281,890 | 281,770 | 283,190 |
| 总收益 | -6.0367% | -6.0767% | -5.6033% |
| 最大回撤 | -21.0481% | -21.0817% | -20.6840% |
| Sharpe | -0.4476 | -0.4507 | -0.4147 |
| 总交易次数 | 23 | 24 | 22 |
| 目标日信号数 | 1 | 1 | 1 |

## 差异归因

- 补齐 `2026-03-31` 池后，4月不再沿用 `2026-02-27` 池。
- `2026-04-30` 的 `MA609.CZCE` Long Open 1手被 `ai_product_pool_blocked` 阻断。
- `2026-05-07` 的 `rb2610.SHFE` Long Open 1手仍然开仓。
- `2026-05-08` 的 `si2609.GFEX` Long Open 1手仍然开仓。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage189_ai_product_pool_backfill_multimonth_replay_review.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage189_ai_product_pool_backfill_multimonth_summary_stage189_ai_product_pool_backfill_multimonth_v1.json`
- pool：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage189_ai_product_pool_backfill_multimonth_pool_stage189_ai_product_pool_backfill_multimonth_v1.csv`
- eligibility：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage189_ai_product_pool_backfill_multimonth_combined_stage78_eligibility_stage189_ai_product_pool_backfill_multimonth_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage188_stage78_2026_30w_latest_ai_pool_20260101_30w_to_20260508_daily.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage188_stage78_2026_30w_latest_ai_pool_20260101_30w_to_20260508_professional_dashboard.html`

## 结论

- 本阶段结论：
  - 后续影子盘主口径应使用 Stage189 combined eligibility。
  - 补齐 3月池后，4月的 `MA609` 开仓被阻断，整体结果略好。
  - 5月8日目标日信号仍为 `si2609.GFEX` 开多1手。
- 是否进入下一步：是
- 下一步：
  - 将 Stage189 combined eligibility 纳入日度影子盘默认输入。
  - 继续做 T+1 开盘/日盘开盘代理成交价复核。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：
  - 本阶段按缺失月份补齐时序输入，没有根据收益挑选月份或参数。
  - 结果变好是输入口径修复后的自然结果，仍需在后续影子盘中固定使用，不可因短期好坏反复切换。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：
  - 月度AI池缺口会改变实际开仓，属于实盘前必须消除的工程风险。
  - 下一步 T+1 成交复核能继续降低回测到实盘之间的乐观偏差。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等 T+1 代理成交复核后一起整理。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是影子盘口径修复，不是正式策略升级。
