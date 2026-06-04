# Stage308 只读 Tick 快照探针合同审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 04:30 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：dry-run / code contract 审计；不重放收益、不连接 CTP、不订阅行情、不调用 `send_order`。
- 是否重要突破：否。它补齐 Stage307 暴露出的 tick 捕获代码缺口，但还没有真实 fresh tick 证据。
- 是否触发A/B：否。本阶段不是策略候选，不产生收益曲线、交易白名单或 submit 动作。

## 外部调研与判断

- 参考资料：
  - vn.py MainEngine/OmsEngine cache APIs：`https://deepwiki.com/vnpy/vnpy/2.2-main-engine`
  - vn.py EVENT_TICK/EVENT_ORDER/EVENT_TRADE architecture：`https://deepwiki.com/vnpy/vnpy/2.1-main-engine-and-event-system`
  - vn.py gateway callback contract：`https://deepwiki.com/vnpy/vnpy/7.2-creating-custom-gateways`
- 我的判断：
  - vn.py 支持我们需要的只读数据路径：`EVENT_TICK` 将 tick 写入 OMS cache，随后可通过 `MainEngine.get_tick` 或事件回调持久化。
  - Stage174 旧只读探针能收 contract/account/position/order/trade/log，但没有目标合约订阅，也没有 ticks CSV；这正是 Stage307 中 `ticks=0` 的结构性原因。
  - Stage608 的正确边界是先补 read-only tick capture 工具，不进入 submit；只有显式 `--connect` 且环境确认后，才允许做 read-only connect/subscribe。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.py`
  - `examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.sh`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage608_readonly_tick_probe_contract_audit.py`
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_live_context_adapter.py`
    - 新增通用 `load_readonly_snapshot_files()`，保留 `load_stage174_readonly_snapshot()` 兼容入口。
- 删除脚本：无。
- 新增参数：
  - `MODEL_TAG = stage608_readonly_tick_snapshot_probe_v1`
  - `wait_seconds = 20`
  - `pre_subscribe_wait_seconds = 5`
  - `submit_plan = Stage591 submit_plan`
  - `target_symbols = Stage591 vt_symbol 去重列表`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：无收益回测；只读 Stage591 submit plan，用于生成目标订阅合约。
- 账户规模：不适用；本阶段只检查执行上下文采集工具。
- 成本口径：不适用；无成交、无滑点。
- 执行口径：
  - 本次实际运行为 dry-run：`connect_requested=false`
  - `send_order_api_called_count=0`
  - `cancel_order_api_called_count=0`
  - `subscribe_api_called_count=0`
- 样本过滤：
  - 目标合约 `5` 个：`fu2509.SHFE/lc2505.GFEX/AP505.CZCE/SM501.CZCE/SM505.CZCE`
- 策略/归因口径：
  - 不改 Stage079、Stage526 或 78-1 策略逻辑。
  - 不把历史 reference price 当 live tick。
  - 不把 dry-run 的空 tick 当通过证据。

## 结果

- 新增交易回测：无。
- 决策：`readonly_tick_probe_code_ready_dry_run_no_live_ticks_yet`
- 是否允许晋级：否。
- 是否允许声明真实交易无偏差：否。
- 期末权益：不适用；无收益回测。
- 总收益：不适用；无收益回测。
- 最大回撤：不适用；无收益回测。
- Sharpe：不适用；无收益回测。
- 总滑点：不适用；无成交回放。
- 总交易次数：不适用；无成交回放。
- 胜率：不适用；无成交回放。
- 其他关键指标：
  - target_symbol_count：`5`
  - capabilities implemented：`9/9`
  - hard gates：`8/9`
  - tick rows：`0`
  - send_order API calls：`0`
  - subscribe API calls：`0`
  - wrapper dry-run 后 `vnpy_ctp_import_available=true`
  - missing required env：`CTP_USERID/CTP_PASSWORD/CTP_BROKERID/CTP_TD_ADDRESS/CTP_MD_ADDRESS/CTP_APPID/CTP_AUTH_CODE`

## 能力矩阵

| capability | result | 说明 |
| --- | ---: | --- |
| `dry_run_default_no_connect` | `1` | 默认不连接 CTP |
| `target_symbols_from_submit_plan` | `1` | 从 Stage591 submit plan 读取 5 个目标合约 |
| `dyld_wrapper_available` | `1` | macOS 下通过 shell wrapper 设置 `DYLD_FRAMEWORK_PATH` |
| `event_tick_registered` | `1` | 注册 `EVENT_TICK` 回调 |
| `subscribe_request_supported` | `1` | 支持 `SubscribeRequest + main_engine.subscribe` |
| `ticks_csv_output_declared` | `1` | 输出 ticks CSV，供 Stage606/607 validator 读取 |
| `cache_snapshot_after_wait` | `1` | 等待后调用 `collect_snapshot_from_main_engine` 持久化 cache |
| `send_order_path_absent` | `1` | 没有 `send_order` 调用路径 |
| `cancel_order_path_absent` | `1` | 没有 `cancel_order` 调用路径 |

## 失败闸门

| 闸门 | 观测值 | 要求 | 判断 |
| --- | ---: | --- | --- |
| `fresh_tick_snapshot_not_yet_received` | `0` | explicit `--connect` 后 `>0` | dry-run 下预期失败，说明仍缺真实 tick 证据 |

## 输出文件

- probe summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage608_readonly_tick_snapshot_probe_summary_stage608_readonly_tick_snapshot_probe_v1.json`
- probe target symbols：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage608_readonly_tick_snapshot_probe_target_symbols_stage608_readonly_tick_snapshot_probe_v1.csv`
- probe ticks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage608_readonly_tick_snapshot_probe_ticks_stage608_readonly_tick_snapshot_probe_v1.csv`
- audit report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage608_readonly_tick_probe_contract_audit_report_stage608_readonly_tick_probe_contract_audit_v1.md`
- audit decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage608_readonly_tick_probe_contract_audit_decision_stage608_readonly_tick_probe_contract_audit_v1.json`
- audit capability：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage608_readonly_tick_probe_contract_audit_capability_stage608_readonly_tick_probe_contract_audit_v1.csv`
- audit gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage608_readonly_tick_probe_contract_audit_gates_stage608_readonly_tick_probe_contract_audit_v1.csv`
- audit chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage608_readonly_tick_probe_contract_audit_chart_stage608_readonly_tick_probe_contract_audit_v1.png`

## 图表视觉复盘

- 图表已视觉检查两次，第一次发现失败项红条不可见，已修复为失败也显示完整红条；第二次视觉检查通过。
- 左上能力矩阵 `9/9` 全绿：说明 EVENT_TICK、SubscribeRequest、ticks CSV、cache snapshot、无 send/cancel 路径、macOS 动态库 wrapper 都已具备。
- 右上 dry-run snapshot rows 只有 `target_symbols=5`，contracts/accounts/positions/ticks 均为 `0`；这符合 dry-run 不连接的边界。
- 左下 gate results 只有 `fresh_tick_snapshot_not_yet_received` 一条红色失败，说明剩余缺口集中，不是策略本体或历史收益问题。
- 右下 execution no-bias ladder 只有 `dry-run contract` 为绿，`explicit read-only connect/tick rows/validator live context/vt_orderid writer` 全红；这清楚说明还没有到 submit 阶段。

## 结论

- Stage608 补齐了 Stage307 后的工具缺口：未来可以对目标 submit plan 合约做 read-only tick capture，并把 ticks CSV 输入 Stage606/607 validator。
- 当前仍不能声明真实交易无偏差，因为本阶段没有连接、没有真实 tick rows、没有 validator live context 全绿，更没有 `vt_orderid`。
- 下一步不是收益回测，也不是扩池；下一步是用户明确确认测试环境和 read-only 动作后，用 wrapper 跑显式 `--connect`，捕获目标合约 tick，再把 Stage608 snapshot 输入 validator。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段只补执行证据采集代码，不改策略规则、产品池、收益窗口或风险参数。
  - dry-run 下仍保留红灯，不用空 tick 或历史价硬凑通过。
  - 图表修复是为了更准确表达失败闸门，不是改善指标。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - Stage307 的结构缺口是旧探针没有 tick capture；Stage608 已把这个缺口推进成可运行工具。
  - 未来只差 read-only connect/subscribe 真实采样，不需要再猜为什么 tick 为零。
  - 这比继续做收益优化更直接服务目标中的“真实交易不存在偏差”。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_live_context_adapter.py examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.py examples/portfolio_backtesting/analyze_qmt_roll_stage608_readonly_tick_probe_contract_audit.py`：通过。
- `examples/portfolio_backtesting/run_ctp_stage608_readonly_tick_snapshot_probe.sh`：dry-run 通过，`connect_requested=false`、`send_order_api_called_count=0`、`subscribe_api_called_count=0`、`vnpy_ctp_import_available=true`。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage608_readonly_tick_probe_contract_audit.py`：通过。
- Stage608 decision/report/gates/capability 已复读。
- Stage608 chart 已视觉检查并修复后复查。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新最新状态和下一步。
- 是否更新 `research/registry.md`：是，更新当前线最新阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否。没有正式候选、重要突破或路线废弃。
