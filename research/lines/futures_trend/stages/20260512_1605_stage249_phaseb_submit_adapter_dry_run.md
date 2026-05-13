# Stage249 Phase B 提交适配器 Dry-run 保险层

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-12 16:05`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Phase B submit adapter 最后一层保险
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py 官方 GitHub：`https://github.com/vnpy/vnpy`
  - vnpy_ctp 官方 GitHub：`https://github.com/vnpy/vnpy_ctp`
  - 本地执行链路：Stage242/243/244/245/248 输出
- 我的判断：即使 Stage245 已经 `final_can_submit=1`，也不能直接把真实 submit 接上去。正确顺序是先加 submit adapter dry-run 层，证明“系统会在什么条件下准备提交”，同时默认保持 `submit_api_called=0`。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage249_phaseb_submit_adapter.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `--mode dry-run|real`
  - `--confirm-real-submit`
  - 环境变量开关：`PHASEB_REAL_ORDER_ENABLED`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：Phase B 样例委托 `2026-04-30` / `PHASEB-20260430-001`

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 请求模式：`dry-run`
  - `phaseb_real_order_env_enabled=false`
  - `checked_intent_count=1`
  - `dry_run_ready_count=1`
  - `blocked_count=0`
  - `submit_api_called_count=0`
  - 样例：`PHASEB-20260430-001 / MA609.CZCE / Long Open / 16手 / 3010`

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage249_phaseb_submit_adapter_report_20260430_stage249_phaseb_submit_adapter_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage249_phaseb_submit_adapter_summary_20260430_stage249_phaseb_submit_adapter_v1.json`
- orders：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage249_phaseb_submit_adapter_results_20260430_stage249_phaseb_submit_adapter_v1.csv`
- daily：不适用
- quality：不适用

## 结论

- 本阶段结论：Phase B 现在已经走到“系统认为可以提交，但 dry-run 明确没有调用真实下单 API”的状态。
- 是否进入下一步：是
- 下一步：真实 submit adapter 仍未实现。若要继续，应实现真实 broker adapter，但保留三重保险：环境变量开关、命令行确认文本、提交前再次读取账户/持仓/挂单快照。

## 过拟合反思

- 运行前判断：否。提交适配器不改策略信号和历史表现。
- 运行后判断：否。`dry_run_ready` 只是执行状态，不影响回测曲线。
- 原因：这是工程安全层，不是收益优化层。

## 继续价值反思

- 运行前判断：是。没有 dry-run 保险层，`final_can_submit=1` 后容易误接真实下单。
- 运行后判断：是。现在可以安全讨论真实 adapter 实现，而不会误触发订单。
- 原因：系统已经有“可提交”和“真实提交”之间的明确隔离。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：建议等真实 adapter 完成并完成一次 dry-run + blocked-real 双路径测试后再追加
