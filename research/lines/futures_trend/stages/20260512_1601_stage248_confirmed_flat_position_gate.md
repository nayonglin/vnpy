# Stage248 CTP 空持仓确认与 Phase B 最终闸门复验

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-12 16:01`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：CTP 持仓快照语义修正 + Phase B 最终安全闸门复验
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py 官方 GitHub：`https://github.com/vnpy/vnpy`
  - vnpy_ctp 官方 GitHub：`https://github.com/vnpy/vnpy_ctp`
  - 本地源码：`vnpy/trader/engine.py`、`.py311/lib/python3.11/site-packages/vnpy_ctp/gateway/ctp_gateway.py`
- 我的判断：
  - vn.py 的 OMS 通过事件缓存持仓，`EVENT_POSITION` 到来后才会进入 `get_all_positions()`。
  - vnpy_ctp 的 `onRspQryInvestorPosition` 在 `data` 为空时直接 `return`，因此“没有 `EVENT_POSITION`”不能天然等价为“已确认空仓”。
  - 安全做法是捕获 CTP 原始持仓查询回调里的 `last=True`。只有“收到 last 回调、无持仓 payload、无错误”时，才把空持仓标记为 `confirmed_flat`。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage245_phaseb_duplicate_and_target_checks.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 代码修正：
  - Stage174 增加 CTP 原始持仓查询回调审计文件 `position_query_callbacks`。
  - Stage174 新增 `broker_snapshot.position_snapshot_state`：
    - `confirmed_flat`
    - `positions_received`
    - `position_query_not_completed`
    - `position_query_error`
    - `position_payload_without_position_rows`
  - Stage245 只在 `position_snapshot_state=confirmed_flat` 时把空持仓视作 0 仓位。
  - Stage245 只处理 `approved_waiting_precheck` 意图，并修复 `NaN can_submit` 的安全转换。
  - 清理一次并行复跑造成的 approval ledger 半行污染。

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
  - SimNow 只读探针状态：`readonly_snapshots_received`
  - `real_order_enabled=false`
  - `order_api_called=false`
  - `position_snapshot_state=confirmed_flat`
  - 持仓行数：`0`
  - 持仓查询回调行数：`22`
  - 持仓查询 data 回调行数：`0`
  - 持仓查询 `last=True`：`true`
  - 持仓查询错误行数：`0`
  - Stage244：`passed / can_submit=1`
  - Stage245：`duplicate_check_status=passed`
  - Stage245：`target_position_check_status=passed`
  - Stage245：`final_can_submit=1`

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage245_phaseb_duplicate_target_report_20260430_stage245_phaseb_duplicate_and_target_checks_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage245_phaseb_duplicate_target_summary_20260430_stage245_phaseb_duplicate_and_target_checks_v1.json`
- orders：不适用
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_position_query_callbacks_stage174_ctp_vnpy_readonly_probe_v1.csv`

## 结论

- 本阶段结论：SimNow 只读环境已经可以确认空仓，Phase B 样例委托已通过账户、挂单、重复委托、目标持仓四道提交前闸门。
- 是否进入下一步：是
- 下一步：仍不直接真实下单；下一步应实现 `submit_order` 的 dry-run/adapter 层和“真实提交默认关闭”的最后保险，确保即使 `final_can_submit=1` 也必须显式打开真实提交开关。

## 过拟合反思

- 运行前判断：否。本阶段只处理实盘执行状态语义，不碰第78-1信号、AI池、参数或资金规则。
- 运行后判断：否。`confirmed_flat` 只提升真实账户状态识别准确性，不改变历史收益。
- 原因：这是执行可靠性改进，无法通过历史数据优化收益曲线。

## 继续价值反思

- 运行前判断：是。没有空仓确认，系统会永远卡在持仓快照缺失；贸然放行又可能重复开仓。
- 运行后判断：是。Phase B 提交前闸门已经跑通，下一步可以进入真实下单 adapter 的最后保险层。
- 原因：当前系统已经从“无法确认账户状态”推进到“能确认账户状态但仍不真实下单”，这是实盘前必要台阶。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加，等真实 submit adapter 完成后作为 Phase B 重要合入摘要记录
