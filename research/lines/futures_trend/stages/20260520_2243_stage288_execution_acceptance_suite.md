# Stage288 SimNow执行安全验收总证据

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-20 23:42 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行安全验收 / Stage78-1实盘前门禁
- 是否重要突破：是，补齐1.6-1.9验收项并汇总开仓、平仓、撤单、断网证据
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：CTP `OnRspOrderInsert` 文档说明，`ReqOrderInsert` 后如果字段或柜台检查错误，会通过该回调返回报单错误；实盘仍需同时监听 `OnErrRtnOrderInsert`、`OnRtnOrder`。
- 我的判断：本阶段不是收益优化，也不挑交易结果；它验证执行安全层。普通 SimNow `9999/trading` 已能证明开平仓、撤单和断网回调；1.6/1.7/1.8/1.9 应作为实盘前提交闸门和回调展示层接入 Stage78-1，而不是为了截图故意向真实柜台发送错误单。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/ctp_execution_safety.py`
  - `examples/portfolio_backtesting/run_ctp_stage288_execution_acceptance_suite.py`
- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage250_phaseb_vnpy_order_request_builder.py`：接入 `ctp_execution_safety.validate_order_instruction`，使后续Phase B/实盘前 `OrderRequest` 构造复用同一套合约、tick、最大手数检查
  - `examples/portfolio_backtesting/run_ctp_stage288_execution_acceptance_suite.py`：生成外发友好版HTML，页面不展示本机文件路径，字段尽量中文化，不强调SimNow/Stage/资金口径，不嵌入截图，并把每个测试点拆成独立章节卡片；同时补回开仓、平仓、撤单、断网的脱敏交易细节和控制台关键打印/回调摘录
- 删除脚本：无
- 新增参数：
  - `ExecutionThresholdConfig.order_count_warn=3`
  - `ExecutionThresholdConfig.cancel_count_warn=1`
  - `ExecutionThresholdConfig.duplicate_intent_warn=1`
  - `PauseGateState.account_trading_allowed/strategy_enabled/session_logged_in`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：非回测；读取2026-05-20普通 SimNow `9999/trading` 实测订单、成交、撤单、断网证据
- 账户规模：Stage78-1当前执行口径 `500,000`
- 成本口径：不涉及收益成本
- 样本过滤：使用已生成的 Stage285/286/287 证据和最新 Stage174 订单/成交/合约快照
- 策略/归因口径：执行安全验收，不修改 Stage78-1 alpha

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 验收测试点：`16`
  - 通过：`16`
  - 失败：`0`
  - Stage288自身 `send_order_api_called_count=0`
  - Stage288自身 `cancel_order_api_called_count=0`
  - 实测证据纳入：开仓+平仓成交、撤单、断网回调
  - 交易细节纳入：委托号、成交号、合约、方向、开平、委托价、成交价、委托手数、已成交、最终状态
  - 控制台/回调摘录纳入：连接登录、行情/交易登录、授权、结算确认、发送委托、发送撤单、委托回报、成交回报、断线原因4097
  - 阈值预警：报单笔数 `4 >= 3`，撤单笔数 `2 >= 1`，重复意图 `1 >= 1`
  - 交易指令检查：错误合约、非最小tick价格、超单笔最大手数均本地拒绝，发单API调用为0
  - 错误提示：资金不足、持仓不足、市场状态不允许三类错误可归一化并展示
  - 暂停交易：账号权限限制、策略暂停、强制退出三类状态均阻断发单

## 输出文件

- report/html：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage288_execution_acceptance_suite_20260520_234200_stage288_execution_acceptance_suite_v1.html`
- screenshot：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage288_execution_acceptance_suite_20260520_234200_stage288_execution_acceptance_suite_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage288_execution_acceptance_suite_20260520_234200_stage288_execution_acceptance_suite_v1_summary.json`
- test_cases：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage288_execution_acceptance_suite_20260520_234200_stage288_execution_acceptance_suite_v1_test_cases.csv`
- threshold_warnings：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage288_execution_acceptance_suite_20260520_234200_stage288_execution_acceptance_suite_v1_threshold_warnings.csv`
- instruction_checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage288_execution_acceptance_suite_20260520_234200_stage288_execution_acceptance_suite_v1_instruction_checks.csv`
- error_prompts：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage288_execution_acceptance_suite_20260520_234200_stage288_execution_acceptance_suite_v1_error_prompts.csv`
- pause_checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage288_execution_acceptance_suite_20260520_234200_stage288_execution_acceptance_suite_v1_pause_checks.csv`
- 外发HTML隐私扫描：未发现 `/Users`、用户名、仓库路径、`file://`、`SimNow`、`Stage`、`50万`、`500000`、`PASS/FAIL`、旧输出文件列表、外部接口参考、隐私处理段落
- Chrome DevTools截图：已生成 `3456 x 12678` 全页PNG，可见开仓/平仓/撤单/断网的交易细节和控制台摘录

## 结论

- 本阶段结论：Stage78-1执行安全验收总证据通过。开平仓、撤单、断网属于普通 SimNow 真实回调；阈值预警、指令检查、错误提示和暂停交易属于实盘前通用门禁/展示层，可直接接入后续策略提交前流程。
- 是否进入下一步：是
- 下一步：
  - 把 `ctp_execution_safety.py` 接入后续 Stage78-1 SimNow/实盘提交前路径，使每日策略订单先过统一校验。
  - 若券商必须要求 `1010/41407/41415` 评测前置证据，则在该前置可稳定报单后复刻开平仓、撤单和断网测试。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有选择品种、没有调策略参数、没有按收益结果筛选规则；所有阈值是执行风控验收阈值，不参与历史收益优化。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：实盘前最容易出问题的是错误单、重复单、断线、暂停开关和柜台错误展示。Stage288补的是这些工程闸门，能直接降低真实发单风险。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：否，暂作为本线执行验收记录，不改变Stage78-1收益基准
