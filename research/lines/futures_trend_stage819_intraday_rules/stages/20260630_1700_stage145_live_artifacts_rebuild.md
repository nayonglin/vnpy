# Stage145 实盘依赖可复算产物重建

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-30 17:00 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘依赖产物重建 / 只读恢复 / 非策略优化
- 是否重要突破：否，但属于实盘链路恢复事项
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：已检查当前 Git 远端 `origin/master`、本地其他 worktree、`.codex_backups`、Trash 与 APFS/Time Machine 快照；关键 `backtest_outputs` 产物未在 Git 历史或可用本地备份中找到。
- 我的判断：无法做到原始文件字节级 1:1 恢复；只能按当前代码、当前本地数据库和 TQSDK 数据源重建功能等价产物，并用行数、hash、官方配置导入和 Stage935 校验确认下游可用。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：
  - 基础 `qmt_roll`：2020-01-01 至 2026-04-30。
  - 旧 floor35 静态源：2020-01-01 至 2026-04-30。
  - 当前 Stage183 live source：2020-01-01 至 2026-06-30。
- 账户规模：
  - Stage183 source refresh：200,000。
  - 当前官方实盘配置校验：15w C9 口径。
- 成本口径：沿用各脚本默认滑点/手续费口径；无实盘下单、无 CTP 报单。
- 样本过滤：沿用 `CORR20_06_08_FLOOR35_OVERRIDES`、full-market structural prefilter、Stage182 monthly live inference 默认规则。
- 策略/归因口径：只恢复官方配置与月度 AI 池依赖的 CSV/JSON/joblib/html 产物，不改变正式策略参数。

## 结果

- 期末权益：
  - 旧 floor35 静态源：2,742,710。
  - 当前 Stage183 live source：2,570,930。
  - full-market floor35 formal：125,950。
- 总收益：
  - 旧 floor35 静态源：1271.355%。
  - 当前 Stage183 live source：1185.465%。
  - full-market floor35 formal：-37.025%。
- 最大回撤：
  - 旧 floor35 静态源：-33.0434%。
  - 当前 Stage183 live source：-33.0434%。
  - full-market floor35 formal：-80.8664%。
- Sharpe：
  - 旧 floor35 静态源：0.99697。
  - 当前 Stage183 live source：0.95195。
  - full-market floor35 formal：-0.14056。
- 总滑点：
  - 旧 floor35 静态源：350,790。
  - 当前 Stage183 live source：360,730。
  - full-market floor35 formal：115,540。
- 总交易次数：
  - 旧 floor35 静态源：1165。
  - 当前 Stage183 live source：1187。
  - full-market floor35 formal：1983。
- 胜率：
  - 旧 floor35 静态源：40.4399%。
  - 当前 Stage183 live source：40.0332%。
  - full-market floor35 formal：36.9261%。
- 其他关键指标：
  - Stage173 数据更新：`max_saved_date=2026-06-30`，`failed_count=0`，`empty_count=0`，`mapping_combined_max_date=2026-06-30`。
  - Stage182 live inference：`eval_date=2026-05-29`，`source_max_date=2026-06-30`，`training_label_cutoff=2026-03-02`。
  - Stage182 Top9：`SA.CZCE, MA.CZCE, OI.CZCE, si.GFEX, AP.CZCE, FG.CZCE, SM.CZCE, jm.DCE, fu.SHFE`。
  - Stage935：`automation_status=monthly_ai_pool_updated`，`post_stage182_validation=valid`，`order_api_called_count=0`，`cancel_order_api_called_count=0`，`real_order_enabled=false`，`email_status=skipped_by_policy`。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage935_official_live_monthly_ai_pool_update_latest_report.txt`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_report_stage182_ai_product_pool_live_inference_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage183_ai_product_pool_source_refresh_report_stage183_ai_product_pool_source_refresh_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage935_official_live_monthly_ai_pool_update_latest_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_summary_stage182_ai_product_pool_live_inference_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage183_ai_product_pool_source_refresh_summary_stage183_ai_product_pool_source_refresh_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage173_forward_main_contract_data_update_summary_stage173_forward_main_contract_data_update_v1.json`
- orders：无；本次未调用任何下单/撤单 API。
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage183_ai_source_floor35_daily.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_formal_floor35_daily.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_full_market_floor35_formal_daily.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_latest_pool_stage182_ai_product_pool_live_inference_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_ai_top8_plus_fu_satellite_post_signal_eligibility.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_structural_prefilter_eligible_full_market_structural_prefilter_v1.csv`

## 结论

- 本阶段结论：关键实盘依赖的可复算产物已恢复，官方 live config 能解析到重建后的 universe 与 Stage182 combined eligibility；但这不是历史原文件字节级恢复。
- 是否进入下一步：是。
- 下一步：继续观察日常 Stage907/929/930/931/934 只读或执行前 gate；如后续再次清理磁盘，应把 `backtest_outputs` 里的正式依赖产物列为保护清单。

## 过拟合反思

- 运行前判断：否。本次目标是恢复误删产物，不新增策略思想、不扫描参数、不根据结果改规则。
- 运行后判断：否。Stage935 与 Stage182 只按完整月份和既有模型重建月度 AI 池；full-market formal 表现很差也没有被用于 promotion。
- 原因：所有命令均沿用既有脚本与固定规则，输出用于接线和安全校验，不参与反向挑参。

## 继续价值反思

- 运行前判断：是。缺失产物会影响官方配置导入、月度 AI 池和日常报告链路。
- 运行后判断：是。Stage935 已证明可把 stale/missing AI 池自动修复到 `eval_date=2026-05-29`，对后续实盘链路稳定性有直接价值。
- 原因：恢复后的产物让当前 C9/15w 官方配置重新具备完整路径依赖；后续重点应是监控产物存在性和定时任务健康，而不是继续优化这些重建结果。

## 合入建议

- 是否更新本线 `LINE.md`：暂不需要；这是恢复事件，不改变路线状态。
- 是否更新 `research/registry.md`：不需要。
- 是否追加根目录 `memory.md/back_log.md`：不需要；若后续形成磁盘清理保护清单，再考虑追加到流程级记录。
