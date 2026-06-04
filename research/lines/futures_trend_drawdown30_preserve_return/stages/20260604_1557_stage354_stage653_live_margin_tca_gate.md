# Stage354 Stage653 实盘保证金/TCA闸门

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 15:57 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘前工程闸门 / 保证金口径 / TCA证据链
- 是否重要突破：是，修正实盘保证金触发源，打通本机 CTP Mac framework import
- 是否触发A/B：是，Stage653 `force95->80` 作为高风险进攻候选进入实盘前证据闸门；本阶段不做新收益回测

## 外部调研与判断

- 参考资料：
  - 本地 `vnpy/trader/object.py`：`AccountData` 仅有 `balance/frozen/available`。
  - 本地 `.py311/lib/python3.11/site-packages/vnpy_ctp/gateway/ctp_gateway.py`：CTP `onRspQryTradingAccount` 映射中 `frozen=data["FrozenMargin"] + data["FrozenCash"] + data["FrozenCommission"]`，`available=data["Available"]`。
  - GitHub `vnpy/vnpy`：`AccountData` 公开结构同样只表达 `balance/frozen/available`。
  - GitHub/社区 `vnpy_ctp` 资料显示 CTP 网关的 `frozen` 来自冻结保证金、冻结现金和冻结手续费之和。
- 我的判断：
  - Stage653 的强制保证金减仓不能用 vn.py 通用 `AccountData.frozen` 当成当前持仓保证金。
  - 实盘触发源必须来自券商/CTP 原始账户字段中的显式当前保证金，例如 `CurrMargin/current_margin/margin/occupied_margin`，否则应 fail-closed。
  - 当前继续调 `95/80` 小数没有价值；真实瓶颈是只读账户保证金快照、精确 `vt_orderid` 映射和 P0 TCA 样本。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage654_stage653_live_margin_tca_gate.py`
  - `examples/portfolio_backtesting/run_ctp_stage655_readonly_account_margin_probe.py`
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_live_context_adapter.py`
- 删除脚本：无
- 新增参数：
  - 策略 alpha 无新增参数。
  - 实盘适配层新增 `ACCOUNT_MARGIN_FIELD_CANDIDATES`，只接受 `margin/curr_margin/CurrMargin/current_margin/CurrentMargin/position_margin/PositionMargin/occupied_margin/OccupiedMargin/use_margin/UseMargin` 等显式保证金字段。
- 修改参数：
  - 无收益或交易规则参数修改。
- 删除参数：
  - 无。
- 环境处理：
  - 将 `/Users/bytedance/Downloads/TraderapiMduserapi_6.7.7_MacOS_CP.zip` 中的 `thostmduserapi_se.framework` 与 `thosttraderapi_se.framework` 复制到 `.py311/lib/`。
  - 清除 quarantine 并本地签名后，`.py311/bin/python` 可成功 `from vnpy_ctp.api import TdApi, MdApi`。

## 回测/归因参数

- 数据区间：本阶段无新回测；引用 Stage653 20万 all-in 强制减仓结果。
- 账户规模：`200,000`
- 成本口径：引用 Stage653 正常成本、2x/3x 成本压力。
- 样本过滤：Stage654 只读已有 Stage653/Stage613/Stage655 输出和当前代码合同。
- 策略/归因口径：Stage653 `stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4` 固定候选，不继续扫阈值。

## 结果

- 期末权益：引用 Stage653 `10,415,070`
- 总收益：引用 Stage653 `5107.5350%`
- 最大回撤：引用 Stage653 `-38.8730%`
- Sharpe：引用 Stage653 `1.6384`
- 总滑点：引用 Stage653 `597,710`
- 总交易次数：引用 Stage653 `655`
- 胜率：引用 Stage653 `52.3156%`
- 其他关键指标：
  - 年化收益率：`86.8222%`
  - 收益保留：`89.9664%`
  - broker10 保证金峰值：`83.3212%`
  - 超过100%保证金天数：`0`
  - 强制减仓：`6` 次 / `317` 手
  - 2x/3x 成本最大回撤：`-41.3142% / -43.9072%`
  - Stage654 hard gates：`5/10`
  - live margin contract：通过，代码已禁止用 `AccountData.frozen` 误当保证金。
  - Stage655 TDAPI import：通过，`tdapi_import_available=True`。
  - Stage655 状态：`dry_run_not_connected`，缺少 `CTP_USERID/CTP_PASSWORD/CTP_BROKERID/CTP_TD_ADDRESS/CTP_APPID/CTP_AUTH_CODE`。
  - 当前真实账户显式保证金快照：失败，`account_rows=0`。
  - 精确 `vt_orderid` 映射：失败，`0`。
  - P0 TCA 样本：失败，`0/9`。
  - Stage613 TCA closeout：失败，`3/9`。
  - CTP 连接：未尝试。
  - 下单 API：未调用，`send_order_api_called_count=0`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage654_stage653_live_margin_tca_gate_report_stage654_stage653_live_margin_tca_gate_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage654_stage653_live_margin_tca_gate_decision_stage654_stage653_live_margin_tca_gate_v1.json`
- orders：无，本阶段不下单。
- daily：无，本阶段不做新回测。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage654_stage653_live_margin_tca_gate_gates_stage654_stage653_live_margin_tca_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage654_stage653_live_margin_tca_gate_evidence_stage654_stage653_live_margin_tca_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage654_stage653_live_margin_tca_gate_chart_stage654_stage653_live_margin_tca_gate_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_summary_stage655_readonly_account_margin_probe_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_accounts_stage655_readonly_account_margin_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_positions_stage655_readonly_account_margin_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage655_readonly_account_margin_probe_logs_stage655_readonly_account_margin_probe_v1.csv`

## 结论

- 本阶段结论：
  - `force95->80` 仍是 Stage653 中最符合用户偏好的高收益进攻候选，但不是实盘批准版本。
  - 实盘保证金触发口径已修正为显式当前保证金字段或 CTP raw `CurrMargin`；若只拿到 vn.py 通用 `AccountData.frozen`，系统应阻断。
  - 本机 CTP Mac framework import 已修通，下一步可在用户明确授权并配置环境变量后运行只读账户探针。
- 是否进入下一步：
  - 是，但下一步只能是只读保证金快照和 TCA 证据补齐，不是继续调收益参数。
- 下一步：
  - 配置 `CTP_USERID/CTP_PASSWORD/CTP_BROKERID/CTP_TD_ADDRESS/CTP_APPID/CTP_AUTH_CODE` 后，由用户明确授权运行 `run_ctp_stage655_readonly_account_margin_probe.py --connect`。
  - 捕获 raw `CurrMargin` 后重跑 Stage654/Stage612/Stage613。
  - 未补齐当前账户显式保证金、精确 `vt_orderid` 映射和 P0 `9/9` TCA 样本前，不允许实盘下单，也不能宣称执行无偏差。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有调交易信号、品种、风险倍率、止盈止损或 `95/80` 小数。
  - 反而因为证据不足阻止晋级，避免用错误保证金字段把历史收益误翻译成实盘安全。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值限定在实盘证据链。
- 原因：
  - 高收益候选已经足够清楚，继续优化历史回测会快速进入过拟合区。
  - 真实价值在于确认券商账户 `CurrMargin`、委托返回 `vt_orderid`、成交 TCA 和 fail-closed 行为是否可靠。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等 Stage655 真实只读账户快照和 Stage613 closeout 再整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段属于实盘前重要口径修正和环境突破。
