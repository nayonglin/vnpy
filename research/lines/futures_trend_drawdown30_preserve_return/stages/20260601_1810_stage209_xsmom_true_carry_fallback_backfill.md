# Stage209 xsmom真实承载成交窗口补数

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-06-01 18:10 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：成交数据补齐；只补 Stage208 xsmom fallback 订单所需分钟窗口。
- 是否重要突破：是。虽然 Stage509 自身覆盖判定因同时要求夜盘和日盘两个窗口而显示 partial，但重跑 Stage208 后实际成交 fallback 已清零。
- 是否触发A/B：否。补数据阶段，不新增策略版本。

## 外部调研与判断

- 参考资料：回测执行模型资料均强调不能用缺失成交价或同bar幻觉替代真实可成交窗口；本阶段遵循这一原则。
- 我的判断：Stage208 指标通过但 fallback=93 时不能晋级，必须先补成交窗口；补数比调参更符合真实可执行目标。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage509_xsmom_true_carry_fallback_backfill.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：`RAW_ROOT=tqsdk_stage509_xsmom_true_carry_fallback_backfill`、`WINDOW_PADDING_MINUTES=10`、`MAX_SECONDS_PER_SYMBOL=240`。
- 修改参数：无。
- 删除参数：无。

## 补数参数

- 数据窗口：每笔 Stage208 fallback 同时请求 `signal_date 21:00-21:05` 和 `fill_date 09:00-09:05`。
- 目标合约：Stage208 fallback 合约 `76` 个。
- 目标窗口：`186` 个。
- 成交语义：重跑 Stage208 时优先夜盘 first open；无夜盘则用日盘 first open。

## 结果

- Stage509 状态：`xsmom_backfill_partial`。
- Stage509 严格窗口覆盖：`42/76` 合约通过；未通过 `34` 个合约。
- 关键解释：Stage509 的 `covered_after_extract` 要求每个缺口合约的夜盘和日盘窗口都覆盖；但 Stage508 真正执行只需要可用的下一真实窗口之一。
- 重跑 Stage208 后实际 xsmom 成交 fallback：`0`。
- 重跑 Stage208 后最佳候选：`risk070_clean + true xsmom`，`21,210,535/3348.8675%/-38.5861%/Sharpe1.1674/Ulcer16.5824`。

## 输出文件

- windows：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage509_xsmom_true_carry_fallback_backfill_windows_stage509_xsmom_true_carry_fallback_backfill_v1.csv`
- status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage509_xsmom_true_carry_fallback_backfill_status_stage509_xsmom_true_carry_fallback_backfill_v1.csv`
- raw：`examples/portfolio_backtesting/downloaded_futures/tqsdk_stage509_xsmom_true_carry_fallback_backfill/`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage509_xsmom_true_carry_fallback_backfill_decision_stage509_xsmom_true_carry_fallback_backfill_v1.json`

## 结论

- 本阶段结论：Stage208 的候选资格不再被成交 fallback 阻塞。
- 是否进入下一步：是。
- 下一步：以 Stage208 final replay 为准进入多窗口/保证金/成本/逐段复盘；Stage509 自身不再作为策略优化方向。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：补数只提高执行数据真实性，不使用收益结果调参。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：补数后 Stage208 fallback 清零，候选从诊断进入工程复核阶段。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：合并到 Stage208 重要候选摘要即可。
