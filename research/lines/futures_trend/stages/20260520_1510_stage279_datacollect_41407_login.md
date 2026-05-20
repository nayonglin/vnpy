# Stage279 DataCollectforMacOS 接入 41407 原生 C++ 登录

- line_id：`futures_trend`
- 当前模式：day
- 记录时间：2026-05-20 15:10 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：CTP/券商测试柜台终端采集链路归因；只读连接验证
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：券商提供的 `/Users/bytedance/Downloads/DataCollectforMacOS0719.zip`。
- 文件校验：
  - zip SHA256：`708543eb8587f9f63ae9b471091de59765a7e280be2ded99ca23bf1a6fe877c4`
  - 解包后 `DataCollectforMacOS` SHA256：`155d482635e3e034f2cb002db6a8c950171414a2372c69d52d1ac6038d491efb`
  - 二进制类型：macOS Mach-O universal binary，支持 `x86_64` 和 `arm64`
  - 版本输出：`datacollect_1.0 for MacOS version 1.0_20231016_4926_MacOS`
- 我的判断：该工具本身只采集本机终端信息并输出 `CollectData`，不直接连接券商前置。若券商后台要看到采集信息，应把 `CollectData` 填入 CTP 登录请求的 `systemInfo` 参数。本阶段已按这个思路接入原生 C++ 登录探针。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/run_ctp_stage278_native_cpp_td_login_probe.sh`
  - `examples/portfolio_backtesting/run_ctp_stage278_native_cpp_td_login_probe.cpp`
- 删除脚本：无
- 新增参数：
  - `CTP_DATA_COLLECT_TOOL`：DataCollect 工具路径，默认 `/private/tmp/stage279_data_collect_mac/DataCollectforMacOS`
  - `CTP_CLIENT_SYSTEM_INFO`：显式传入 CTP 登录的终端采集信息；默认由 DataCollect 自动生成
  - `CTP_NATIVE_REGISTER_USER_SYSTEM_INFO`：是否额外调用 `RegisterUserSystemInfo`，默认 `0`
- 修改参数：`ReqUserLogin` 从空 `systemInfoLen=0` 改为在 DataCollect 可用时传入非空 `systemInfo`
- 删除参数：无

## 回测/归因参数

- 数据区间：不涉及行情回测
- 账户规模：Stage78-1 正式执行口径仍为 `500000`；本阶段只读 CTP 链路验证不使用策略资金参数
- 成本口径：不涉及
- 样本过滤：只测试券商评测/CP 交易前置 `tcp://182.140.218.46:41407`
- 策略/归因口径：不发单，只做采集工具输出、认证、登录、结算确认、账户查询、持仓查询

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - DataCollect 工具可运行，输出 `CollectData`；为避免泄露本机 MAC/序列号等信息，研究记录只保留长度
  - `CTP_CLIENT_SYSTEM_INFO=set(len=100)`
  - 原生 C++ API 版本：`v6.7.7_MacOS_CP_20240716 15:00:00`
  - 交易前置：`tcp://182.140.218.46:41407`
  - `OnFrontConnected`：成功
  - `ReqAuthenticate ret=0`，`OnRspAuthenticate ErrorID=0`
  - `ReqUserLogin system_info_len=100 ret=0`
  - `OnRspUserLogin ErrorID=0`，`FrontID=15`，`SessionID=1581585766`，`TradingDay=20260520`，`LoginTime=15:09:59`
  - `ReqSettlementInfoConfirm ret=0`，`OnRspSettlementInfoConfirm ErrorID=0`
  - `ReqQryTradingAccount ret=0`，账户快照收到 `account_count=1`
  - `ReqQryInvestorPosition ret=0`，持仓快照收到 `position_count=32`
  - 汇总：`front_connected=true auth_ok=true login_ok=true settlement_ok=true account_count=1 position_count=32`
  - 委托/撤单 API 调用次数：`0`
  - CTP 返回的 `ErrorMsg=��ȷ` 是 GBK 字符串未转码显示；以 `ErrorID=0` 为准，语义为成功。

## 输出文件

- report：本 stage 文件
- summary：终端原生 C++ 探针输出
- orders：无，未调用报单或撤单接口
- daily：不适用
- quality：不适用

## 结论

- 本阶段结论：券商提供的 `DataCollectforMacOS0719.zip` 已能在本机采集终端信息，且采集结果已作为非空 `systemInfo` 传入 `ReqUserLogin`。`41407` 原生 C++ 链路在带 `system_info_len=100` 的情况下，仍完整通过认证、登录、结算确认、账户和持仓查询。若券商后台仍查不到，应让券商按 `SessionID=1581585766 / FrontID=15 / LoginTime=15:09:59 / AppID=client_hermanna_1.0 / BrokerID=1010 / 测试账号` 查交易前置登录流水和终端采集记录。
- 是否进入下一步：是
- 下一步：
  1. 把本次会话字段发给券商确认后台是否可见。
  2. 若仍不可见，可按券商确认后再显式开启 `CTP_NATIVE_REGISTER_USER_SYSTEM_INFO=1` 复测；当前默认不启用，因为券商前面已回复 `RegisterUserSystemInfo / SubmitUserSystemInfo` 不用调用。
  3. Stage78-1 日常虚拟盘仍按 SOP 使用已验证的默认路线，不因本次采集测试改变策略或发单规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：这是 CTP 终端采集/登录链路补齐，不涉及任何策略参数、品种池、收益指标筛选或回测窗口选择。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：本阶段从“交易登录成功但券商看不到记录”推进到“带 DataCollect 终端采集信息的登录也成功”，能让券商用更精确的会话字段排查后台记录。若后台确认可见，该链路可收尾；若仍不可见，再只针对 `RegisterUserSystemInfo` 做一次窄范围复测。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；这是执行链路线内阶段记录。
