# Stage250 Phase B vn.py OrderRequest 构造与 real 阻断测试

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-12 16:13`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Phase B 真实提交前的标准订单请求构造层
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py `OrderRequest` / `MainEngine.send_order` 相关资料与源码
  - DeepWiki vn.py 网页索引中对 order submission flow 的说明：先校验合约，再构造 `OrderRequest`，最后 `main_engine.send_order`
  - 本地源码：`vnpy/trader/object.py`、`vnpy/trader/constant.py`、`vnpy/trader/ui/widget.py`
- 我的判断：真实 submit 前，应该先把 Phase B 意图映射成标准 vn.py `OrderRequest`，并显式校验合约、方向、开平、限价、手数、tick、gateway。构造层仍不应该导入 CTP gateway 或调用 `send_order`。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage250_phaseb_vnpy_order_request_builder.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `--mode dry-run|real`
  - `--confirm-real-submit`
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
  - dry-run：`request_ready_count=1 / blocked_count=0 / order_api_called_count=0`
  - real 阻断测试：`request_ready_count=0 / blocked_count=1 / order_api_called_count=0`
  - real 阻断原因：`phaseb_real_order_env_disabled;real_submit_confirmation_missing;stage250_never_calls_send_order`
  - 构造出的请求字段：
    - `symbol=MA609`
    - `exchange=CZCE`
    - `direction=Long`
    - `offset=Open`
    - `type=Limit`
    - `volume=16`
    - `price=3010`
    - `vt_symbol=MA609.CZCE`
    - `gateway_name=CTP`

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage250_phaseb_vnpy_order_request_builder_dry_run_report_20260430_stage250_phaseb_vnpy_order_request_builder_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage250_phaseb_vnpy_order_request_builder_real_report_20260430_stage250_phaseb_vnpy_order_request_builder_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage250_phaseb_vnpy_order_request_builder_dry_run_summary_20260430_stage250_phaseb_vnpy_order_request_builder_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage250_phaseb_vnpy_order_request_builder_real_summary_20260430_stage250_phaseb_vnpy_order_request_builder_v1.json`
- orders：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage250_phaseb_vnpy_order_request_builder_dry_run_results_20260430_stage250_phaseb_vnpy_order_request_builder_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage250_phaseb_vnpy_order_request_builder_real_results_20260430_stage250_phaseb_vnpy_order_request_builder_v1.csv`
- daily：不适用
- quality：不适用

## 结论

- 本阶段结论：Phase B 样例委托已经可以被映射为标准 vn.py `OrderRequest`，dry-run 校验通过；real 模式默认被阻断，且 `order_api_called_count=0`。
- 是否进入下一步：是
- 下一步：实现最小真实 submit adapter 前，还应补一个“提交前即时再探针”流程，真实提交必须使用最新账户/持仓/活动委托状态，而不是复用历史快照。

## 过拟合反思

- 运行前判断：否。OrderRequest 构造只验证执行字段，不改策略信号、AI池或参数。
- 运行后判断：否。本阶段不影响历史收益曲线，也不会优化回测指标。
- 原因：这是实盘执行工程层的 deterministic mapping。

## 继续价值反思

- 运行前判断：是。真实 submit 前必须先证明字段映射正确，否则容易出现方向、开平、交易所或 tick 错误。
- 运行后判断：是。请求构造已通过，但真实提交仍需要即时账户状态复查。
- 原因：现在已经能把“策略意图”安全转成“交易系统请求”，下一步应确保提交时状态仍然新鲜。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加，待真实 submit adapter 和即时复查闭环后再记录重要合入摘要
