# Stage281 41407 原生 C++ 报单 API smoke order

- line_id：`futures_trend`
- 当前模式：day
- 记录时间：2026-05-20 15:58 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：CTP/券商测试柜台 41407 原生 C++ 报单 API 链路验证
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：沿用前序已核对的 SimNow Mac CP SDK `v6.7.7_MacOS_CP_20240716 15:00:00`、券商提供的 `DataCollectforMacOS0719.zip` 工具和券商新测试账号。当前动作是执行链路 smoke test，不新增策略 alpha 或回测研究。
- 我的判断：既然 41407 原生 C++ 已完成认证、登录、结算、账户和持仓查询，下一步可以在测试环境内以 1 手、低价、显式开关的方式调用 `ReqOrderInsert`，用来确认“报单 API 是否真的能被调用”。该验证不能被解释为策略实盘开关，也不能用于正常 Stage78-1 手数。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_ctp_stage281_native_cpp_smoke_order.cpp`
  - `examples/portfolio_backtesting/run_ctp_stage281_native_cpp_smoke_order.sh`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `CTP_NATIVE_SMOKE_MODE`
  - `CTP_NATIVE_SMOKE_ORDER_ENABLED`
  - `CTP_NATIVE_SMOKE_CONFIRM`
  - `CTP_NATIVE_SMOKE_INSTRUMENT`
  - `CTP_NATIVE_SMOKE_EXCHANGE`
  - `CTP_NATIVE_SMOKE_DIRECTION`
  - `CTP_NATIVE_SMOKE_PRICE`
  - `CTP_NATIVE_SMOKE_VOLUME`
  - `CTP_NATIVE_SMOKE_WAIT_SECONDS`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不涉及行情回测
- 账户规模：Stage78-1 正式执行口径仍为 `500000`；本阶段只做 1 手测试报单，不使用策略资金参数
- 成本口径：不涉及
- 样本过滤：只测试券商评测/CP 交易前置 `tcp://182.140.218.46:41407`
- 策略/归因口径：先 dry-run，再 fresh read-only snapshot，最后在用户已确认测试环境前提下，显式调用 1 手 `MA609.CZCE` 买开 `ReqOrderInsert`

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 报单测试时间：`2026-05-20 15:57:36 CST`
  - 交易前置：`tcp://182.140.218.46:41407`
  - 路线：原生 C++ 直连 CTP，不经过 vn.py / `vnpy_ctp`
  - `CTP_CLIENT_SYSTEM_INFO=set(len=100)`
  - API 版本：`v6.7.7_MacOS_CP_20240716 15:00:00`
  - 测试委托：`instrument=MA609`，`exchange=CZCE`，`direction=buy`，`offset=open`，`price=1.0000`，`volume=1`
  - `ReqAuthenticate ret=0`，`OnRspAuthenticate ErrorID=0`
  - `ReqUserLogin system_info_len=100 ret=0`
  - `OnRspUserLogin ErrorID=0`，`FrontID=15`，`SessionID=1768626185`，`TradingDay=20260520`，`LoginTime=15:57:36`
  - `ReqSettlementInfoConfirm ret=0`，`OnRspSettlementInfoConfirm ErrorID=0`
  - `ReqOrderInsert OrderRef=779263855588 ret=0`
  - `OnRspOrderInsert ErrorID=21 OrderRef=779263855588`
  - `send_order_api_called_count=1`
  - `cancel_order_api_called_count=0`
  - `rtn_order_count=0`
  - `rtn_trade_count=0`
  - 事后账户/持仓复核：`2026-05-20 15:58:42` 账户和持仓查询成功，`account_count=1`，`position_count=4`
  - 稳定结论：报单 API 确实被调用；CTP 随后以 `OnRspOrderInsert ErrorID=21` 拒绝，未出现委托回报、成交回报或活动委托，所以没有成交，也没有可撤委托。

## 输出文件

- report：本 stage 文件
- summary：终端原生 C++ smoke-order 输出
- evidence：
  - `examples/portfolio_backtesting/backtest_outputs/ctp_evidence/stage281_41407_native_cpp_smoke_order_evidence_sanitized.txt`
  - `examples/portfolio_backtesting/backtest_outputs/ctp_evidence/stage281_41407_native_cpp_smoke_order_evidence_sanitized.png`
- orders：`ReqOrderInsert` 已调用但被 CTP 拒绝；无 `OnRtnOrder`，无 `OnRtnTrade`
- daily：不适用
- quality：不适用

## 结论

- 本阶段结论：41407 原生 C++ + DataCollect 路线已经证实可以走到报单 API 层。`ReqOrderInsert ret=0` 表示本地 API 请求已发出，但柜台/CTP 以 `OnRspOrderInsert ErrorID=21` 拒绝该委托；本次没有形成交易所委托、没有成交、没有残留活动委托。给券商排查时应提供 `SessionID=1768626185 / FrontID=15 / LoginTime=15:57:36 / OrderRef=779263855588 / ErrorID=21`。
- 是否进入下一步：是
- 下一步：
  1. 请券商按上述会话字段和 `OrderRef` 查询 `ErrorID=21` 的柜台侧中文原因。
  2. 若原因只是价格、合约状态、权限或时段规则，可按券商建议再做一次更合规的 1 手测试；仍需 fresh snapshot、dry-run、显式开关和确认文本。
  3. 在 `414xx/CP` 路线进入日常虚拟盘前，需要把原生 C++ 桥接层做成稳定 broker adapter，并补齐订单/成交/撤单状态机；不能直接让 Stage78-1 正常手数调用该 smoke 脚本。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：这是 CTP 报单通路验证，没有选择收益窗口、没有调参、没有改变品种池或交易逻辑；它只回答“接口是否能调用、柜台如何响应”。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：现在已经从“券商后台看不到登录”推进到“有明确登录会话和报单响应错误码”。这能让券商按确定字段查后台，也能帮助我们判断后续 Mac 原生执行桥是否值得继续工程化。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；这是执行链路线内阶段记录。
