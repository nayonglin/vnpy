# Stage282 41407 看穿式终端信息上报路径复核

- line_id：`futures_trend`
- 当前模式：day
- 记录时间：2026-05-20 16:11 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：CTP/SimNow Mac CP SDK 看穿式终端采集与上报路径审计；只读连接验证
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 本地 SimNow Mac CP SDK：`/private/tmp/simnow_mac_cp_sdk/TraderapiMduserapi_6.7.7_CP_MacOS`
  - 本地 SDK 头文件：`ThostFtdcTraderApi.h`、`ThostFtdcUserApiStruct.h`、`ThostFtdcUserApiDataType.h`
  - 本地 SDK PDF：`合规使用说明_看穿式终端采集库.pdf`
  - CTP API 文档：`CTP-GetSystemInfo`、`RegisterUserSystemInfo`、`SubmitUserSystemInfo`
- 我的判断：
  1. `RegisterUserSystemInfo` 是“中继服务器多连接模式”，要求认证成功后、登录前调用。
  2. `SubmitUserSystemInfo` 是“中继服务器操作员登录模式”，要求操作员登录后上报不同客户信息。
  3. 直连模式文档说明交易 API 登录时自动采集/上报，或在当前 Mac CP 头文件中通过扩展版 `ReqUserLogin(..., length, systemInfo)` 传入终端信息。
  4. 我们当前路线并不是完全没上报：已把 `DataCollectforMacOS` 输出作为 `ReqUserLogin` 的 `systemInfo` 参数传入；但登录成功本身不能证明上报成功，因为本次对照发现 `system_info_len=0` 也能登录成功。
  5. 更大的疑点在于：`DataCollectforMacOS0719.zip` 只有可执行工具，没有 `DataCollect.h` 或可链接库；而 CTP 文档强调采集信息不是 C 字符串，应该按原始数组 `memcpy`。我们现在把工具打印出的 `CollectData` 经环境变量传入，可能不是券商后台期望的原始采集字节格式。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/run_ctp_stage278_native_cpp_td_login_probe.cpp`
- 删除脚本：无
- 新增参数：
  - `CTP_NATIVE_SUBMIT_USER_SYSTEM_INFO=1`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不涉及行情回测
- 账户规模：Stage78-1 正式执行口径仍为 `500000`；本阶段只做 CTP 只读登录/上报路径审计
- 成本口径：不涉及
- 样本过滤：只测试券商评测/CP 交易前置 `tcp://182.140.218.46:41407`
- 策略/归因口径：不报单；复核 `ReqUserLogin(systemInfo)`、`RegisterUserSystemInfo`、`SubmitUserSystemInfo` 三种路径

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - API 版本：`v6.7.7_MacOS_CP_20240716 15:00:00`
  - 本地 `ThostFtdcTraderApi.h` 明确包含：
    - `RegisterUserSystemInfo(CThostFtdcUserSystemInfoField*)`
    - `SubmitUserSystemInfo(CThostFtdcUserSystemInfoField*)`
    - `ReqUserLogin(CThostFtdcReqUserLoginField*, int, TThostFtdcSystemInfoLenType, TThostFtdcClientSystemInfoType)`
  - `DataCollectforMacOS` 输出 `CollectData`，脱敏统计：`len=100`，可打印 ASCII，非纯 hex，非标准 base64。
  - 显式 `RegisterUserSystemInfo` 测试：
    - `CTP_NATIVE_REGISTER_USER_SYSTEM_INFO=1`
    - `RegisterUserSystemInfo client_system_info_len=100 ret=-6`
    - 随后 `ReqUserLogin system_info_len=100 ret=0`
    - `OnRspUserLogin ErrorID=0`，`SessionID=1816074420`，`LoginTime=16:09:38`
    - 账户/持仓查询成功，未报单
  - 显式 `SubmitUserSystemInfo` 测试：
    - `CTP_NATIVE_SUBMIT_USER_SYSTEM_INFO=1`
    - `ReqUserLogin system_info_len=100 ret=0`
    - `OnRspUserLogin ErrorID=0`，`SessionID=1820006595`，`LoginTime=16:10:37`
    - `SubmitUserSystemInfo client_system_info_len=100 ret=-6`
    - 账户/持仓查询成功，未报单
  - 空 `systemInfo` 对照测试：
    - 禁用 `DataCollectforMacOS` 自动采集
    - `ReqUserLogin system_info_len=0 ret=0`
    - `OnRspUserLogin ErrorID=0`，`SessionID=1822628046`，`LoginTime=16:11:17`
    - 账户/持仓查询成功，未报单
  - `-6` 按 CTP 文档为“采集结果字段错误”。

## 输出文件

- report：本 stage 文件
- summary：终端原生 C++ 只读探针输出
- orders：无，未调用报单或撤单接口
- daily：不适用
- quality：不适用

## 结论

- 本阶段结论：用户怀疑“当前方式可能绕过或没有满足券商需要的上报”是合理的。严格说，当前代码使用了 `ReqUserLogin(..., systemInfo)`，不等于完全没传终端信息；但登录成功不能证明上报成功，因为 `system_info_len=0` 也能登录成功。显式 `RegisterUserSystemInfo` 和 `SubmitUserSystemInfo` 均返回 `-6`，说明用 `DataCollectforMacOS` 打印出来的 `CollectData` 直接填入 `CThostFtdcUserSystemInfoField.ClientSystemInfo` 至少不被这两条上报接口接受。后续需要券商确认 Mac 直连模式到底应使用“扩展登录参数”还是“链接采集库获取原始字节再上报”。
- 是否进入下一步：是
- 下一步：
  1. 向券商确认 `client_hermanna_1.0` 的 AppType 是直连投资者、投资者中继，还是操作员中继。
  2. 向券商确认 Mac CP `v6.7.7` 直连场景中，`DataCollectforMacOS` 打印的 `CollectData` 是否可以原样传给 `ReqUserLogin(..., length, systemInfo)`；还是必须提供 `DataCollect.h`/动态库，调用 `CTP_GetSystemInfo` 得到原始字节。
  3. 请券商分别查询三个只读会话：`1816074420`、`1820006595`、`1822628046`，看后台是否有终端采集记录差异。
  4. 在确认采集上报格式前，不继续把 `414xx/CP` 作为正式执行 adapter。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：这是 CTP 接入协议和上报路径审计，不涉及策略收益、参数、品种池或回测窗口选择。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：本阶段把“登录成功但券商后台查不到”的问题进一步收敛到终端信息上报模式和采集数据格式，而不是泛泛怀疑网络、账号或策略代码。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；这是执行链路线内阶段记录。
