# Stage051 Stage875 C9 重试后日内进展持仓审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 06:16 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读事件法证；不改官方正式版、不改官方候选配置、不接真实引擎、不连接 CTP、不调用下单。
- 是否重要突破：否；这是一个候选分支反证。
- 是否触发A/B：否；未形成有价值的新策略版本。

## 外部调研与判断

- 参考资料：
  - Turtle 规则原文强调被止损后可用固定规则重新入场，但核心仍是保留趋势右尾，不能按单日无进展的后验印象平仓：https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf
  - Backtrader `StopTrail` 与 stop-loss 示例说明止损/追踪止损要在逐根 bar 的执行语义里落地，不能只看最终标签：https://www.backtrader.com/docu/order-creation-execution/trail/stoptrail/
  - Backtrader stop-loss sample 可作为订单语义参考，但不能直接复制到当前组合资金路径：https://github.com/mementum/backtrader/blob/master/samples/stop-trading/stop-loss-approaches.py
  - vn.py CTA engine 参考说明实盘规则必须可在 runtime 逐事件判定：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/engine.py
  - Rob Carver 对动态止损的讨论提示，按持仓中途路径频繁改退出通常会损伤右尾和 Sharpe：https://qoppac.blogspot.com/2020/02/what-is-right-way-to-set-stop-losses.html
- 我的判断：
  - “重试后当天没有马上触达 `+0.5R progress`，收盘退出”看起来像纪律，但它直接挑战 C9 的右尾来源。
  - 只有当 no-progress-after-reentry 样本的真实后续贡献为负，才值得写真实引擎；如果这些样本仍贡献正 PnL，就必须停止该分支。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage875_stage863_reentry_progress_hold_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE = "Stage875"`
  - `MODEL_TAG = "stage875_stage863_reentry_progress_hold_audit_v1"`
  - 审计阈值沿用 C9 事件语义的 `+0.5R progress`，只作为分组，不作为新策略参数。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage861 全量分钟K覆盖与 Stage863 C9 全周期事件输出，覆盖 `2018-01` 起点至 `2026-05-29`。
- 账户规模：沿用 Stage863 C9 口径；本阶段不新增账户规模。
- 成本口径：沿用 Stage863 C9 已生成 closed lots / trades / stop-retry events；本阶段只做事件审计，不新增成交成本模型。
- 样本过滤：
  - 只取 Stage863 C9 `open_after_reentry` 事件。
  - 将原始 stop/retry event 的 `trade_id` 映射到原始 `order_id`，再匹配合成重试开仓 `order_id + ".stage847_c9.2"`。
  - 成功匹配重试 closed lots 的样本数为 `26/26`。
- 策略/归因口径：
  - 对重试后同日分钟K逐根扫描是否触达入场方向 `+0.5R progress`。
  - 若未触达，则计算一个只读反事实：按重试日 EOD 盯市退出，与实际后续持仓 PnL 对比。
  - 该口径只是代理审计，不是可交易引擎。

## 结果

- 期末权益：未新增；沿用 Stage863 C9 `50,637,144.6`。
- 总收益：未新增；沿用 Stage863 C9 `16,779.0482%`。
- 最大回撤：未新增；沿用 Stage863 C9 `-42.6313%`。
- Sharpe：未新增；沿用 Stage863 C9 `1.6312`。
- 总滑点：未新增；沿用 Stage863 C9 `3,607,030`。
- 总交易次数：未新增；沿用 Stage863 C9 `786`。
- 胜率：未新增；沿用 Stage863 C9 `53.5299%`。
- 其他关键指标：
  - C9 `open_after_reentry`：`26` 笔，全部匹配重试后 closed lots。
  - `no_progress_after_reentry`：`12` 笔；实际重试后 PnL `+1,783,150`；EOD 盯市代理 PnL `+138,400`；若 EOD 退出 delta `-1,644,750`；median MFE after reentry `0.406349R`；median close after reentry `-0.018995R`。
  - `progress_after_reentry`：`14` 笔；实际重试后 PnL `+4,754,180`；EOD 盯市代理 PnL `+3,371,830`；若 EOD 退出 delta `-1,382,350`；median MFE after reentry `3.95162R`；median close after reentry `3.00891R`。
  - 全部 `open_after_reentry`：`26` 笔；实际重试后 PnL `+6,537,330`；EOD 盯市代理 PnL `+3,510,230`；若 EOD 退出 delta `-3,027,100`。
  - 最大误伤样本：`OI201.CZCE` long，`2021-09-24` 重试后当天未触达 `+0.5R progress`，EOD 代理 `-31,920`，实际后续 `+2,090,000`，单笔少赚 `2,121,920`。
  - 确实有 EOD 退出会改善的个例，如 `SM505.CZCE`、`AP110.CZCE`、`rb2201.SHFE`，但净效果被右尾误伤压倒。

## 视觉复核

- summary chart 显示 no-progress 组和 progress 组的实际持有 PnL 都高于 EOD 盯市代理。
- atlas page001/page002 重点补入 no-progress 样本：
  - `OI201.CZCE` 证明“当天无进展”并不是趋势失败充分条件，真实持有后来贡献大右尾。
  - `SM505.CZCE`、`AP110.CZCE`、`rb2201.SHFE` 证明该规则确实能救个别左尾，但样本内净值不够。
  - `jm2101.DCE`、`MA909.CZCE` 进一步显示无进展样本里仍有正贡献。
- 视觉判断：这个规则的经验直觉太像“想把持仓变干净”，但真正趋势交易需要忍受一部分入场日没有立刻展开的持仓。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage875_stage863_reentry_progress_hold_audit_report_stage875_stage863_reentry_progress_hold_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage875_stage863_reentry_progress_hold_audit_summary_stage875_stage863_reentry_progress_hold_audit_v1.csv`
- event_audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage875_stage863_reentry_progress_hold_audit_event_audit_stage875_stage863_reentry_progress_hold_audit_v1.csv`
- yearly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage875_stage863_reentry_progress_hold_audit_yearly_stage875_stage863_reentry_progress_hold_audit_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage875_stage863_reentry_progress_hold_audit_summary_chart_stage875_stage863_reentry_progress_hold_audit_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage875_stage863_reentry_progress_hold_audit_atlas_manifest_stage875_stage863_reentry_progress_hold_audit_v1.csv`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage875_stage863_reentry_progress_hold_audit_atlas_page001_stage875_stage863_reentry_progress_hold_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage875_stage863_reentry_progress_hold_audit_atlas_page002_stage875_stage863_reentry_progress_hold_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage875_stage863_reentry_progress_hold_audit_atlas_page003_stage875_stage863_reentry_progress_hold_audit_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage875_stage863_reentry_progress_hold_audit_decision_stage875_stage863_reentry_progress_hold_audit_v1.json`

## 结论

- 本阶段结论：`stage875_reentry_no_progress_eod_exit_rejected_no_engine`。
- 是否进入下一步：否，不接“重试后未进展 EOD 退出”真实引擎。
- 下一步：
  - 停止围绕 `open_after_reentry` 的 progress 阈值、等待窗口、EOD 平仓、品种、方向、年份扫描。
  - 如果继续本研究线，应回到不直接截断右尾、也不增加 whipsaw 成本的账户层/持仓层生存问题；否则暂停等待新的低自由度外生特征。

## 过拟合反思

- 运行前判断：否。本阶段只审计 C9 已发生的 `open_after_reentry` 事件，并固定一个自然语义：重试后当天是否触达原方向 `+0.5R progress`。
- 运行后判断：否，但继续救这个分支会变成过拟合。
- 原因：
  - 这次没有扫描阈值、分钟窗口、品种、方向或年份，只验证一个单一规则直觉。
  - 结果已经被 `OI201.CZCE` 等右尾样本强反证；如果继续把 `0.5R` 改成 `0.3R/0.8R`、把 EOD 改成等待若干分钟，本质就是对少数事件救参。

## 继续价值反思

- 运行前判断：有有限价值。它检验的是 C9 重试分支最后一个自然直觉：重试后如果当天没有马上展开，是否应该退出。
- 运行后判断：该具体分支没有继续价值。
- 原因：
  - no-progress 组实际后续仍净赚 `+1,783,150`，EOD 退出会少赚 `1,644,750`。
  - 全部 open-after-reentry 若按 EOD 代理退出会少赚 `3,027,100`，说明这不是一个能提高收益或保护回撤的低自由度规则。
  - 继续应转向更本质的账户/持仓层风险承载，而不是继续在重试事件内部切小片。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage051 反证和停止该分支。
- 是否更新 `research/registry.md`：否，本线状态未发生路线级变化。
- 是否追加根目录 `memory.md/back_log.md`：否，不是重要突破、路线废弃、正式候选、跨线合并或记录体系迁移。
