# Stage285 SimNow 1手开仓和平仓成交证明

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-20 21:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：CTP/SimNow 测试环境执行链路证明
- 是否重要突破：是，普通 SimNow `9999/trading` 前置完成 1 手开仓成交 + 1 手平仓成交
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：仓库内 `skills/futures-live-execution-sop/SKILL.md`、Stage174 只读快照、Stage258 smoke-order 保险层。
- 我的判断：
  - 用户需要给期货商证明“程序能正常下达开仓和平仓指令”，这属于执行链路证明，不属于 alpha 优化。
  - 当前券商评测 `1010/41407/41415` 从 Mac 侧网络探针超时，原生 C++ 也未收到 `OnFrontConnected`，因此不能用该通道构造当下成交证据。
  - 普通 SimNow `9999/trading` 前置在夜盘时段可登录、可订阅实时 `MA609` tick，适合构造最小 1 手开/平成交证据；若券商要求必须用 `1010/41407` 账号，则本阶段只能证明普通 SimNow/vn.py/CTP 执行栈能力，不能替代评测前置验收。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_ctp_stage285_simnow_open_close_proof.py`
  - `examples/portfolio_backtesting/run_ctp_stage285_simnow_open_close_proof.sh`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `--mode dry-run|submit-open-close`
  - `--vt-symbol`
  - `--aggressive-ticks`
  - `--max-tick-age-seconds`
  - `--confirm-submit I_UNDERSTAND_THIS_SENDS_CTP_TEST_ORDERS`
- 修改参数：无
- 删除参数：无
- 安全闸门：
  - 只允许 `volume=1`
  - 需要新鲜 Stage174 只读快照
  - 需要 `CTP_SMOKE_ORDER_ENABLED=1`
  - 需要精确确认文本
  - 默认 dry-run，不调用 `send_order`

## 回测/归因参数

- 数据区间：不适用
- 账户规模：SimNow 测试账户，不作为策略资金口径
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：非策略信号，纯 CTP 执行链路证明
- 测试前置：`SIMNOW_FRONT=trading`
- 交易前置：`tcp://182.254.243.31:30001`
- 行情前置：`tcp://182.254.243.31:30011`
- 测试合约：`MA609.CZCE`
- 测试手数：`1`

## 结果

- 状态：`open_close_all_traded`
- 开仓：
  - 委托：`CTP.1_-1160514772_1`
  - 方向/开平：`Long / Open`
  - 委托价：`2973.0`
  - 成交价：`2970.0`
  - 成交手数：`1`
  - 成交编号：`2026052100040894`
  - 委托状态：`All Traded`
- 平仓：
  - 委托：`CTP.1_-1160514772_2`
  - 方向/开平：`Short / Close`
  - 委托价：`2965.0`
  - 成交价：`2968.0`
  - 成交手数：`1`
  - 成交编号：`2026052100041181`
  - 委托状态：`All Traded`
- `send_order_api_called_count=2`
- `cancel_order_api_called_count=0`
- 后验只读持仓快照：
  - 状态：`readonly_snapshots_received`
  - 持仓语义：`confirmed_flat`
  - 非零持仓行：`0`
- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：本阶段实际测试成交 `2`
- 胜率：不适用

## 输出文件

- evidence_html：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage285_simnow_open_close_proof_evidence_20260520_214451.html`
- evidence_png：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage285_simnow_open_close_proof_evidence_20260520_214451.png`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage285_simnow_open_close_proof_report_20260520_214451_stage285_simnow_open_close_proof_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage285_simnow_open_close_proof_summary_20260520_214451_stage285_simnow_open_close_proof_v1.json`
- console：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage285_simnow_open_close_proof_console_20260520_214451_stage285_simnow_open_close_proof_v1.txt`
- orders：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage285_simnow_open_close_proof_orders_20260520_214451_stage285_simnow_open_close_proof_v1.csv`
- trades：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage285_simnow_open_close_proof_trades_20260520_214451_stage285_simnow_open_close_proof_v1.csv`
- positions：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage285_simnow_open_close_proof_positions_20260520_214451_stage285_simnow_open_close_proof_v1.csv`
- accounts：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage285_simnow_open_close_proof_accounts_20260520_214451_stage285_simnow_open_close_proof_v1.csv`

## 结论

- 本阶段结论：普通 SimNow `9999/trading` 通道已经完整证明程序能发出开仓委托、收到开仓成交、再发出平仓委托、收到平仓成交，并在后验只读快照中回到空仓。
- 是否进入下一步：是，但只进入“给券商确认/截图佐证”或“等待券商评测前置恢复后复刻”的下一步，不进入策略正常手数交易。
- 下一步：
  - 如果券商接受普通 SimNow 证明，则发送 evidence PNG/HTML/console。
  - 如果券商要求 `1010/41407/41415` 评测前置证明，则等该前置从 Mac 网络恢复后，用同样 Stage285 逻辑或原生 C++ 版本复刻。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只验证执行通道的开平仓能力，不修改 Stage78-1 策略参数、不改变 AI 池、不参与收益评估。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：开仓成交和平仓成交是进入虚拟盘/半自动执行的基本工程闸门；有了原始 order/trade/console 证据，可以让券商更快判断 API、AppID、账号权限和程序调用方式是否正常。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage285 普通 SimNow 开平仓证明已完成。
- 是否更新 `research/registry.md`：可更新为最新执行链路里程碑。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不改变策略收益与正式候选结论。
