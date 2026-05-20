# Stage280 新测试账号 DataCollect 接入 41407 原生 C++ 登录

- line_id：`futures_trend`
- 当前模式：day
- 记录时间：2026-05-20 15:44 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：CTP/券商测试柜台新账号链路归因；只读连接验证
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：券商要求使用新测试账号重新登录，并继续使用 `DataCollectforMacOS0719.zip` 采集工具。
- 我的判断：更换新账号后仍要保持同一条 41407 原生 C++ + DataCollect 路线，才能让券商后台按新账号、会话号和终端采集信息查日志。该阶段不涉及策略收益，不应改变 Stage78-1 交易逻辑。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：本地 `ctp_broker_test.local.env` 已由用户更新为券商新测试账号/密码；研究记录只记录长度，不记录明文
- 删除参数：无

## 回测/归因参数

- 数据区间：不涉及行情回测
- 账户规模：Stage78-1 正式执行口径仍为 `500000`；本阶段只读 CTP 链路验证不使用策略资金参数
- 成本口径：不涉及
- 样本过滤：只测试券商评测/CP 交易前置 `tcp://182.140.218.46:41407`
- 策略/归因口径：不发单，只做 DataCollect 采集、认证、登录、结算确认、账户查询、持仓查询

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 新账号长度：`CTP_USERID=set(len=6)`；密码长度：`CTP_PASSWORD=set(len=8)`
  - 交易前置：`tcp://182.140.218.46:41407`
  - DataCollect 已接入：`CTP_CLIENT_SYSTEM_INFO=set(len=100)`
  - 原生 C++ API 版本：`v6.7.7_MacOS_CP_20240716 15:00:00`
  - `OnFrontConnected`：成功
  - `ReqAuthenticate ret=0`，`OnRspAuthenticate ErrorID=0`
  - `ReqUserLogin system_info_len=100 ret=0`
  - `OnRspUserLogin ErrorID=0`，`FrontID=15`，`SessionID=1715607367`，`TradingDay=20260520`，`LoginTime=15:44:05`
  - `ReqSettlementInfoConfirm ret=0`，`OnRspSettlementInfoConfirm ErrorID=0`
  - `ReqQryTradingAccount ret=0`，账户快照收到 `account_count=1`
  - `ReqQryInvestorPosition ret=0`，持仓快照收到 `position_count=4`
  - 汇总：`front_connected=true auth_ok=true login_ok=true settlement_ok=true account_count=1 position_count=4`
  - 委托/撤单 API 调用次数：`0`
  - CTP 返回的 `ErrorMsg=��ȷ` 是 GBK 字符串未转码显示；以 `ErrorID=0` 为准，语义为成功。

## 输出文件

- report：本 stage 文件
- summary：终端原生 C++ 探针输出
- evidence：
  - `examples/portfolio_backtesting/backtest_outputs/ctp_evidence/stage280_41407_new_account_datacollect_login_evidence_sanitized.txt`
  - `examples/portfolio_backtesting/backtest_outputs/ctp_evidence/stage280_41407_new_account_datacollect_login_evidence_sanitized.png`
- orders：无，未调用报单或撤单接口
- daily：不适用
- quality：不适用

## 结论

- 本阶段结论：券商新测试账号在 `41407` 原生 C++ + DataCollect 路线上完整通过认证、登录、结算确认、账户和持仓查询；且 `ReqUserLogin` 已传入 `system_info_len=100` 的终端采集信息。若券商后台仍查不到，应按 `SessionID=1715607367 / FrontID=15 / LoginTime=15:44:05 / AppID=client_hermanna_1.0 / BrokerID=1010 / 新测试账号` 查交易前置登录流水和终端采集记录。
- 是否进入下一步：是
- 下一步：
  1. 将脱敏截图或会话字段发给券商确认后台记录。
  2. 若券商仍不可见，再按其要求显式开启 `CTP_NATIVE_REGISTER_USER_SYSTEM_INFO=1` 复测；当前仍不默认启用。
  3. 继续保持 fail-closed：本阶段只读，无任何策略发单含义。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：这是 CTP 新账号与终端采集登录链路验证，不涉及策略参数、品种池、收益窗口或历史回测结果选择。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：新账号复测成功后，券商可以排除旧账号后台查询口径问题；如果仍查不到，就能把问题进一步收敛到券商后台日志筛选或 `RegisterUserSystemInfo` 是否必须显式调用。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；这是执行链路线内阶段记录。
