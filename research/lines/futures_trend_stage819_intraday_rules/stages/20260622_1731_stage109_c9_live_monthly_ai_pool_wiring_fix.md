# Stage109 C9/15w 实盘月更 AI 池接线修复

- line_id：futures_trend_stage819_intraday_rules
- 当前模式：day
- 记录时间：2026-06-22 17:31 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：官方 C9/15w live shadow 执行配置修复；将实盘路径接回 Stage182 月度 AI 池。
- 是否重要突破：是，修复会改变 2026-06-22 目标日是否有 pending order。
- 是否触发A/B：否；这是执行接线修复，不是新策略版本或候选推广。

## 外部调研与判断

- 参考资料：
  - https://alphaarchitect.com/the-worlds-longest-trend-following-backtest/
  - https://arxiv.org/html/2602.11708v1
- 我的判断：公开资料只能支持 trend following / asset selection 应保持 point-in-time 和滚动/月度更新原则，不能回答本仓库实际实盘路径。本次结论以本地 SOP、配置代码和 Stage901 输出为准。

## 问题归因

- 设计原则：`futures-live-execution-sop` 明确写明当前 official live profile 应消费 Stage182 月度 AI 池；日度影子盘使用当前月池，不每日重训。
- 已存在的月更池：`OFFICIAL_LIVE_AI_ELIGIBILITY_PATH` 指向 `qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`，最新 `eval_date=2026-05-29`。
- 实际旧接线：`build_official_live_strategy_overrides()` 调用 Stage847-C9 candidate overrides，而 Stage847-C9 继承 Stage819/Stage777 的 frozen old-AI eligibility；Stage901 构造 live C9 profile 时只覆盖资金，没有合并 official live strategy overrides。
- 因此，修复前 C9/15w live shadow 实际使用 `qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_ai_top8_plus_fu_satellite_post_signal_eligibility.csv`，最新只到 `2026-02-27`。
- 口径边界：Stage777/813/819/C9 的历史候选回测记录多处明确写 `old_ai` / `旧正式 AI`，因此既有 C9 全周期、滚动窗口和候选指标不能直接声称已经是 Stage182 最新月更池口径。它们是“月度生效的旧 AI 文件”，不是“Stage182 最新 live inference 文件”。

## 本次变更

- 修改脚本：`examples/portfolio_backtesting/qmt_roll_official_live_config.py`
  - `build_official_live_strategy_overrides()` 新增 `ai_product_pool_eligibility_path=str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)`。
- 修改脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py`
  - 导入 `OFFICIAL_LIVE_AI_ELIGIBILITY_PATH` 与 `build_official_live_strategy_overrides()`。
  - Stage901 `_run_live_c9()` 在 C9 profile 上合并 official live strategy overrides，不再只覆盖资金。
  - Stage901 decision/report 新增 AI 池审计：路径、最新 eval date、最新品种、实际 strategy override AI 路径。
- 新增脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：实盘 live strategy override 的 AI eligibility 路径从旧文件修正为 Stage182 月更文件。

## 回测/归因参数

- 数据区间：`2026-06-16` 至 `2026-06-22`。
- 目标日：`2026-06-22`。
- 账户规模：C9/15w live default，`150000`。
- AI 池：Stage182 月更池，最新 `eval_date=2026-05-29`。
- 最新池内品种：`SA.CZCE`、`si.GFEX`、`FG.CZCE`、`MA.CZCE`、`OI.CZCE`、`jm.DCE`、`AP.CZCE`、`rb.SHFE`、`fu.SHFE`。
- 执行口径：只读 shadow + dry-run，不连接 CTP，不调用下单。

## 验证结果

- `py_compile`：通过。
- 静态验证：`build_official_live_strategy_overrides()["ai_product_pool_eligibility_path"]` 与 `OFFICIAL_LIVE_AI_ELIGIBILITY_PATH` 一致，`matches=True`。
- Stage901 重跑：
  - `ai_pool_audit.max_eval_date=2026-05-29`
  - `strategy_ai_product_pool_eligibility_path` 指向 Stage182 月更池
  - `pending_order_count=1`
  - pending order：`rb2610.SHFE Short Open volume=11 price=3126.0`
  - `send_order_api_called_count=0`
  - `cancel_order_api_called_count=0`
- Stage260 execution gate：
  - `pending_order_count=1`
  - `execution_candidate_count=1`
  - `blocked_count=1`
  - `executable_count=0`
  - 阻断原因：只读账户快照 `snapshot_age_seconds=3280.582`，超过 `300` 秒新鲜度要求；fail-closed。
  - `order_api_called_count=0`
- Stage905 executor dry-run：
  - `intent_count=1`
  - `ready_count=0`
  - `blocked_count=1`
  - `executor_status=executor_dry_run_blocked`
  - `send_order_api_called_count=0`
  - `cancel_order_api_called_count=0`
- Stage929 timed-cycle report：
  - 使用 `--shadow-refresh-mode plan-only --readonly-refresh-mode plan-only`，只重建报告，不连接 CTP。
  - `wrapper_exit_code=0`
  - `pending_order_count=1`
  - `stage905_ready_count=0`
  - `order_api_called_count=0`
  - 邮件通知已发送，severity `warning`，主题为 `[C9/15w 官方报告][warning] 2026-06-22 待处理=1 可提交=0 下单API=0`。

## 结果

- 期末权益：本阶段只跑 2026-06-16 后 live shadow，当前未成交，`150000.0`。
- 总收益：`0.0%`。
- 最大回撤：`0.0%`。
- Sharpe：N/A。
- 总滑点：`0.0`。
- 总交易次数：shadow 成交 `0`；pending order `1`。
- 胜率：N/A。
- 其他关键指标：风险层级 `normal`，允许 shadow record，理论上允许新开仓；但执行 gate 因 broker 快照过期而阻断。

## 输出文件

- Stage901 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_report_stage901_stage847_c9_2026_ytd_live_shadow_v1.md`
- Stage901 decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_decision_stage901_stage847_c9_2026_ytd_live_shadow_v1.json`
- Stage901 pending orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_pending_orders_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
- Stage260 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage260_official_live_daily_execution_gate_summary_20260622_stage260_official_live_daily_execution_gate_v1.json`
- Stage905 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage905_official_live_executor_dry_run_summary_20260622_stage905_official_live_executor_dry_run_v1.json`
- Stage929 latest report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_15w_timed_cycle_latest_report.md`

## 结论

- 本阶段结论：用户判断正确，C9/15w 实盘路径应该接 Stage182 月更 AI 池；之前“无交易”是 C9 live shadow 没合并 official live AI override 的接线错误。
- 修复后，2026-06-22 目标日出现 `rb2610.SHFE` 空头开仓 pending order。
- 当前不能直接下单：Stage260 因 broker 只读快照过期阻断，Stage905 dry-run 也 blocked，订单 API 仍为 `0`。
- 是否进入下一步：是。
- 下一步：若今晚要按修复后口径处理该 `rb` 候选，必须先刷新生产只读账户/持仓/合约/tick 快照，再重跑 Stage260/Stage905/Stage927。只有 fresh gate 全过且用户明确允许真实提交时，才能讨论进入 Stage931；否则保持 fail-closed。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次不是根据结果调参数，而是让 official live shadow 使用 SOP 已定义的 Stage182 月度 AI 池；没有修改 AI 排名逻辑、C9 信号规则、R 倍数、重试次数、品种打分或历史样本。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：该接线直接决定 2026-06-22 是否有 `rb` pending order，属于实盘执行一致性问题；修复后还暴露了下一步真正阻断在 broker 快照新鲜度，而不是策略信号。

## 合入建议

- 是否更新本线 `LINE.md`：是，补充当前 live default 已接 Stage182 月更池，且今晚 `rb` 候选因 broker 快照过期 fail-closed。
- 是否更新 `research/registry.md`：暂不更新，等待今晚执行链路或人工确认后再统一更新。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；当前工作区已有较多无关变更，且本阶段还需完成 fresh broker gate 后才适合作为跨线合入摘要。
