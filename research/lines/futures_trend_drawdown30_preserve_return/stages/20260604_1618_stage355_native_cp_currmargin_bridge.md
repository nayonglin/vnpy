# Stage355 Native CP CurrMargin 桥接

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 16:18 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘前只读账户保证金取证 / CP SDK 路线桥接
- 是否重要突破：是，首次用券商 CP Mac SDK + 官方 MacDataCollect function 路线拿到 raw CTP `CurrMargin`
- 是否触发A/B：否，本阶段不做收益回测，也不改变策略 alpha；属于 Stage653 高风险进攻候选的执行证据链

## 外部调研与判断

- 参考资料：
  - GitHub `vnpy/vnpy` 与本地 `vnpy/trader/object.py`：`AccountData` 只表达 `balance/frozen/available`。
  - GitHub/社区 `vnpy_ctp` 与本地 `ctp_gateway.py`：`AccountData.frozen` 来自 `FrozenMargin + FrozenCash + FrozenCommission`，不是当前持仓保证金占用。
  - 本机券商文件 `/Users/bytedance/Downloads/sfit_tst_1.0_20250325_7643_MacOS/.../MacDataCollect.framework` 暴露 `CTP_GetSystemInfoUnAesEncode` 符号。
  - CP SDK `v6.7.7_MacOS_CP_20240716 15:00:00` 是 `41407/41415` CP 前置可用 SDK。
- 我的判断：
  - `41407/41415` 不是普通 vnpy_ctp framework 的可用路径；普通 vn.py gateway read-only 返回 `decode err / 4097`，属于 SDK/front 不匹配。
  - Python `vnpy_ctp.api.TdApi` TD-only 路径在本环境中可 import，但对 CP 前置没有收到 `OnFrontConnected`，不能作为当前 CurrMargin 取证主路径。
  - Native C++ + CP SDK + `MacDataCollect.framework` 官方采集函数是当前最可信的只读账户保证金取证路径。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_ctp_stage655_readonly_account_margin_probe.sh`
  - `examples/portfolio_backtesting/parse_ctp_stage656_native_cp_account_margin_probe.py`
  - `examples/portfolio_backtesting/run_ctp_stage656_native_cp_account_margin_probe.sh`
- 修改脚本：
  - `examples/portfolio_backtesting/run_ctp_stage655_readonly_account_margin_probe.py`
  - `examples/portfolio_backtesting/run_ctp_stage278_native_cpp_td_login_probe.cpp`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage654_stage653_live_margin_tca_gate.py`
- 删除脚本：无
- 新增参数：
  - 策略 alpha 无新增参数。
  - Stage656 wrapper 环境默认：`CTP_MAC_CP_SDK_DIR=.py311/lib`、`CTP_SYSTEM_INFO_SOURCE=collector_api`、`CTP_NATIVE_REQUIRE_SYSTEM_INFO=1`、`CTP_NATIVE_TD_WAIT_SECONDS=35`。
- 修改参数：
  - 无交易参数修改。
- 删除参数：
  - 无。

## 回测/归因参数

- 数据区间：无新回测；只读连接当前券商测试 CP 前置。
- 账户规模：引用 Stage653 20万候选，不新增资金口径。
- 成本口径：引用 Stage653 正常成本与 2x/3x 压力。
- 样本过滤：Stage656 只解析 native C++ 只读 TD 日志，输出账户/持仓/日志 CSV。
- 策略/归因口径：Stage653 `force95->80` 固定候选；本阶段只验证实盘保证金字段来源。

## 结果

- 期末权益：引用 Stage653 `10,415,070`
- 总收益：引用 Stage653 `5107.5350%`
- 最大回撤：引用 Stage653 `-38.8730%`
- Sharpe：引用 Stage653 `1.6384`
- 总滑点：引用 Stage653 `597,710`
- 总交易次数：引用 Stage653 `655`
- 胜率：引用 Stage653 `52.3156%`
- 其他关键指标：
  - Stage655 Python TD-only：本地 env 已齐，TCP 可达，但 `front_connected=False`，`account_rows=0`；退出路径已修成稳定 `EXIT_CODE=4`，不再被 native wrapper `139` 掩盖。
  - Stage267/vn.py gateway read-only：`decode err / 4097`，无账户/持仓快照；证明普通 vnpy_ctp framework 不适合当前 CP 前置。
  - Stage656 native CP read-only：`front_connected/auth_ok/login_ok/settlement_ok=True`，`account_rows=1`、`position_rows=2`、`explicit_margin_rows=1`，raw `CurrMargin` 已捕获。
  - Stage656 使用官方 collector function：`system_info_source=collector_api:_Z28CTP_GetSystemInfoUnAesEncodePcRi`，`system_info_len=264`。
  - 下单 API：未调用，`send_order_api_called_count=0`、`cancel_order_api_called_count=0`。
  - Stage654 复跑：hard gates 从 `5/10` 提升到 `6/10`；`account_snapshot_margin_ok=True`。
  - Stage654 仍不允许实盘：剩余失败为成本压力、精确 `vt_orderid`、P0 TCA `0/9`、Stage613 closeout 未全绿。

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_report_stage656_native_cp_account_margin_probe_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage654_stage653_live_margin_tca_gate_report_stage654_stage653_live_margin_tca_gate_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_summary_stage656_native_cp_account_margin_probe_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage654_stage653_live_margin_tca_gate_decision_stage654_stage653_live_margin_tca_gate_v1.json`
- orders：无，本阶段不下单。
- daily：无，本阶段不做新回测。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_accounts_stage656_native_cp_account_margin_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_positions_stage656_native_cp_account_margin_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_logs_stage656_native_cp_account_margin_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage656_native_cp_account_margin_probe_raw_stage656_native_cp_account_margin_probe_v1.log`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage654_stage653_live_margin_tca_gate_gates_stage654_stage653_live_margin_tca_gate_v1.csv`

## 结论

- 本阶段结论：
  - Stage653 `force95->80` 的实盘保证金口径关键缺口已经补上：可以通过 Stage656 native CP 只读路径拿到 raw `CurrMargin`。
  - 当前 CP 前置正确路径不是普通 vn.py/vnpy_ctp gateway，也不是 Python TD-only，而是 native C++ + CP SDK + 官方 MacDataCollect function。
  - 这只解决“账户保证金字段”闸门，不解决真实委托 `vt_orderid` 与成交 TCA。
- 是否进入下一步：
  - 是，但下一步不能直接实盘下单。
- 下一步：
  - 在用户明确确认“测试环境 + 允许发送 1 手测试单”前，只能继续做 dry-run adapter 和 TCA reducer 准备。
  - 若要补 `vt_orderid` 与 P0 TCA，必须走 native CP submit-cancel smoke order 的显式确认闸门，且只允许 1 手测试单。
  - Stage654 剩余硬缺口：精确 `bridge_signal_id -> vt_orderid`、P0 有效 TCA `9/9`、以及 Stage653 2x/3x 成本压力的策略决策。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有新增收益规则、没有调阈值、没有选择品种、没有回看收益改策略。
  - 它只把实盘执行字段从“错误/缺失”推进到“可验证 raw CurrMargin”。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但下一步价值边界很清楚。
- 原因：
  - 当前已经证明 CP 只读账户保证金可获取，继续重复连接价值不高。
  - 后续真正缺口是订单生命周期证据；没有用户显式测试下单确认前，不能继续推进到真实 `vt_orderid`。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等 `vt_orderid/TCA` 阶段再整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段是实盘前关键执行链路突破。
