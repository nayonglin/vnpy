# Stage329 P2 公开源 Monitor Run 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 08:02 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：公开源 forward monitor 运行审计；不重放策略、不改交易规则、不生成 selector/paper/交易白名单、不连接 CTP。
- 是否重要突破：否。它让 `ag/CY/SR` 的公开源证据链可重复运行，但不产生可交易候选。
- 是否触发A/B：否。没有 selector、paper 或交易候选，且 PIT 样本、episode、预测力和 TCA 均未达标。

## 外部调研与判断

- 参考资料：
  - SHFE Daily Data：`https://www.shfe.cn/eng/reports/StatisticalData/DailyData/`
  - ESMIS API Documentation：`https://esmis.nal.usda.gov/api-documentation`
  - NASS Crop Progress methodology：`https://www.nass.usda.gov/Surveys/Guide_to_NASS_Surveys/Crop_Progress_and_Condition/index.php`
  - ESMIS Crop Progress release：`https://esmis.nal.usda.gov/publication/crop-progress/2026-06-01`
  - ESMIS WASDE release：`https://esmis.nal.usda.gov/publication/world-agricultural-supply-and-demand-estimates/2026-05-12-0`
  - USDA ERS Cotton and Wool Outlook：`https://ers.usda.gov/publications/pub-details?pubid=114047`
- 我的判断：
  - 公开源 monitor 的价值在于建立 point-in-time 证据链，而不是直接提升 alpha。
  - 每条 source row 必须保留 `received_at/source_url/final_url/raw_hash/status/bytes`，成功和失败都要留痕，避免未来把回填数据误当成当时可得数据。
  - CZCE 已知 `412/404` 路由应进入 blocked catalog，不应继续作为 active monitor 计入 selector 证据；`CY/SR` 当前更适合用 USDA/ESMIS/ERS 公共源累计事件与供需 episode。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage629_p2_public_source_monitor_run.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增公开源 monitor run 合同、blocked route catalog、PIT 样本锁定闸门。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：本阶段不做收益回测，只做当前公开源页面抓取与阶段级 ledger 输出。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - active monitor：`ag.SHFE`、`CY.CZCE`、`SR.CZCE` 的 SHFE/USDA/ESMIS/ERS 公共源。
  - blocked catalog：Stage626 已确认的 CZCE `412/404` 路由。
- 策略/归因口径：forward monitor 证据采集；禁止将 monitor row 写入 history selector。

## 结果

- 期末权益：不适用，本阶段不重算收益。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`p2_public_source_monitor_run_collected_selector_locked`
  - active rows：`6`
  - active monitor ok rows：`6`
  - active products covered：`3`
  - event monitor products：`2`
  - selector rows：`0`
  - paper/whitelist rows：`0`
  - hard gates：`7/7`
  - `ag.SHFE`：monitor rows `1.0`，event monitor `0.0`，raw hash rows `1`，PIT dates `1`。
  - `CY.CZCE`：monitor rows `3.5`，event monitor `3.0`，raw hash rows `4`，PIT dates `1`。
  - `SR.CZCE`：monitor rows `1.5`，event monitor `1.0`，raw hash rows `2`，PIT dates `1`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage629_p2_public_source_monitor_run_report_stage629_p2_public_source_monitor_run_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage629_p2_public_source_monitor_run_decision_stage629_p2_public_source_monitor_run_v1.json`
- run ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage629_p2_public_source_monitor_run_run_ledger_stage629_p2_public_source_monitor_run_v1.csv`
- product status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage629_p2_public_source_monitor_run_product_status_stage629_p2_public_source_monitor_run_v1.csv`
- route status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage629_p2_public_source_monitor_run_route_status_stage629_p2_public_source_monitor_run_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage629_p2_public_source_monitor_run_gates_stage629_p2_public_source_monitor_run_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage629_p2_public_source_monitor_run_chart_stage629_p2_public_source_monitor_run_v1.png`

## 图表视觉复盘

- 左上图显示：`CY.CZCE` 的 monitor/event 行最充分，`SR.CZCE` 次之；`ag.SHFE` 只有交易所日度公开页证据，event monitor 仍为 `0`。
- 右上图显示：active monitor `6` 行全部成功；CZCE blocked catalog 中 `412` 两行、`404` 一行被清楚分离，没有把阻塞路由误计为可用源。
- 左下图显示：所有 active source 均有 hash 标记，SHFE Daily Data、NASS guide、WASDE、Crop Progress 为主要字节来源；没有出现“有页面但无 hash”的静默证据缺口。
- 右下图显示：所有 gate 为绿色，但其中包含 fail-closed lock：`pit_dates_still_below_selector_threshold` 只是确认 `1 < 20` 时 selector 继续锁定，不是晋级通过。

## 运行与验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage629_p2_public_source_monitor_run.py`：通过。
- 首次沙箱内运行因 DNS/network sandbox 返回 `gaierror`，不计为外部源失败。
- 使用联网权限重跑 `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage629_p2_public_source_monitor_run.py`：通过，6/6 active monitor rows 成功。
- `python -m json.tool ...decision_stage629_p2_public_source_monitor_run_v1.json`：通过。
- 输出文件存在：通过。
- 图表视觉检查：通过，四个面板结论与 CSV/decision 一致。

## 结论

- 本阶段结论：P2 公开源 monitor run 已可采集 `ag/CY/SR` 的 raw-hash 证据，但当前仍只是 PIT 证据起点，不是选品 alpha。
- 是否进入下一步：进入，但只能继续按日期追加 monitor 证据和 episode ledger。
- 下一步：
  1. 将 run ledger 按 append gate 累计为 master PIT ledger，要求至少 `20` 个 received_at 日期和 `12` 个月跨度。
  2. 对 `CY/SR` 记录 USDA/ESMIS/ERS 事件 episode；对 `ag` 补事件型公开源或授权源。
  3. 只有满足 episode、purged walk-forward、63/126日左尾和 live TCA 后，才允许申请 P1 review。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段不回测收益、不挑历史赢家、不调风险小数、不生成交易名单，只固定公开源 monitor 证据格式，并把 selector/paper/whitelist 锁住。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值在长期证据累计，不在当日交易。
- 原因：`soft_agri` 和 `precious_metals` 是低单笔风险扩池的潜在新风险槽；公开源可重复抓取是晋级的必要条件，但远不足以构成充分条件。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage329 摘要。
- 是否更新 `research/registry.md`：是，推进最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破、路线废弃或跨线合并。
