# Stage147 当前重建线上版本 2018 起逐半年冷启动到 2026-06-29

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-30 18:31 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：当前重建线上版本多起点冷启动回测与曲线可视化
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：vn.py 官方回测/CTA Backtester 文档与 GitHub 示例用于确认“历史回测+结果分析”仍应走本仓库既有 vn.py 回放链路。
- 我的判断：本次不是寻找新策略，也不是引入新框架；C9 当前线上版本带有路径依赖的资金、AI 池、分钟止损/重试和 broker10 限制，最小偏差做法是继续复用 `Stage901` live wrapper 独立冷启动重跑。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage938_c9_live_15w_halfyear_starts_to_20260629.py`
  - `examples/portfolio_backtesting/visualize_qmt_roll_stage938_c9_live_15w_halfyear_starts_to_20260629.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：固定起点 `2018-01-01`，每年 `1月1日/7月1日`；固定结束日 `2026-06-29`；资金 `150000`
- 修改参数：无策略参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：每个起点独立从对应实际交易日跑到 `2026-06-29`
- 账户规模：`150000`
- 成本口径：沿用当前 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage901` live wrapper
- 样本过滤：`2018-01` 到 `2026-01`，逐半年起点，共 `17` 个样本
- 策略/归因口径：当前重建线上版本 C9/Stage847 15w，AI 池读取当前 Stage182 combined eligibility，即当前最新池 `SA/MA/OI/si/AP/FG/SM/jm/fu`

## 结果

- 期末权益：最低 `152,011.60`，中位 `455,463.70`，最高 `14,870,482.00`
- 总收益：最低 `1.3411%`，中位 `203.6425%`，最高 `9813.6547%`
- 最大回撤：最差 `-56.2069%`，来自 `2018-01`；中位 `-47.2779%`
- Sharpe：最低 `0.2450`，中位 `1.1945`，最高 `1.4784`
- 总滑点：所有窗口合计 `7,870,830`
- 总交易次数：所有窗口合计 `6,696`
- 胜率：非零日胜率中位 `52.2752%`
- 其他关键指标：
  - 正收益窗口 `17/17`
  - 最差收益起点 `2026-01`，收益 `1.3411%`，主要因持有期最短
  - 最好收益起点 `2018-07`，收益 `9813.6547%`
  - DD30/DD40/DD50 失败窗口分别为 `10/9/8`
  - peak broker10 margin/equity `96.6295%`，broker100 失败 `0`
  - 订单 API：`send_order_api_called_count=0`，`cancel_order_api_called_count=0`，`ctp_connected=false`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage938_c9_live_15w_halfyear_starts_to_20260629_report_stage938_c9_live_15w_halfyear_starts_to_20260629_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage938_c9_live_15w_halfyear_starts_to_20260629_summary_stage938_c9_live_15w_halfyear_starts_to_20260629_v1.csv`
- stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage938_c9_live_15w_halfyear_starts_to_20260629_stats_stage938_c9_live_15w_halfyear_starts_to_20260629_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage938_c9_live_15w_halfyear_starts_to_20260629_curves_stage938_c9_live_15w_halfyear_starts_to_20260629_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage938_c9_live_15w_halfyear_starts_to_20260629_decision_stage938_c9_live_15w_halfyear_starts_to_20260629_v1.json`
- dashboard：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage938_c9_live_15w_halfyear_starts_to_20260629_dashboard_stage938_c9_live_15w_halfyear_starts_to_20260629_v1.png`

## 结论

- 本阶段结论：当前重建线上版本在 `2018-01` 起逐半年冷启动、统一持有到 `2026-06-29` 口径下，所有 `17` 个窗口最终正收益；但左尾回撤仍深，早期长窗口最差回撤达到 `-56.2069%`，说明该版本的长期右尾仍伴随高回撤承受要求。
- 是否进入下一步：进入只读审计下一步，不进入调参。
- 下一步：固定 Stage182 AI 池和 Stage861/Stage449 等关键派生产物 hash；若继续看实盘风险，应做当前池与旧池的同口径 A/B 只读对照，而不是改 C9 参数。

## 过拟合反思

- 运行前判断：否。起点、结束日、资金和当前 live override 都由用户请求固定。
- 运行后判断：否。本次没有按结果调任何阈值、品种、方向、月份或 AI 池。
- 原因：这只是当前版本路径审计；不能用 `2018-07` 的高收益或 `2018-01` 的深回撤反向救参。

## 继续价值反思

- 运行前判断：是。统一结束日多起点曲线能观察不同冷启动时点到当前的路径差异。
- 运行后判断：是。结果提供了当前重建版本的路径基准和心理预期，但后续价值在冻结产物与对照审计，不在继续扫参。
- 原因：当前差异核心仍是重建产物与旧冻结产物不一致，继续优化策略会混淆“版本复原问题”和“alpha 改进问题”。

## 合入建议

- 是否更新本线 `LINE.md`：是，本次作为 Stage146 后的当前重建版本曲线补充。
- 是否更新 `research/registry.md`：否，未改变研究线状态或默认实盘版本。
- 是否追加根目录 `memory.md/back_log.md`：否，非重大突破、非正式候选变更。
