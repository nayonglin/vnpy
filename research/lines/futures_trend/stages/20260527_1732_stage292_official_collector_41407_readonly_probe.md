# Stage292 官方采集库 41407 只读登录验证

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-27 17:32 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：CTP/券商测试通路只读验证
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：券商提供的 `sfit_tst_1.0_20250325_7643_MacOS` 包内 `使用说明.txt`、`MacDataCollect.framework/Headers/DataCollect.h`、本仓库 Stage78-1 CTP/SimNow SOP。
- 我的判断：本次不是策略优化，也不是回测；核心是确认官方采集库能否作为 41407 直连登录的 `systemInfo` 来源。该包是 `tst` 测试密钥版，适合当前测试柜台验证；生产环境前仍需券商确认是否需要 `pro` 版。

## 本次变更

- 新增脚本：无。
- 修改脚本：`examples/portfolio_backtesting/ctp_native_system_info.hpp`
  - 增加真实 C++ dlsym 符号 `_Z28CTP_GetSystemInfoUnAesEncodePcRi` 和 `_Z21CTP_GetRealSystemInfoPcRi`。
  - 将官方采集函数签名按头文件修正为 `int (*)(char *, int&)`，并检查非零返回码。
  - buffer 最小长度从 `264` 调整为头文件要求的 `270`，调用前 `length=0`。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不适用。
- 账户规模：不适用；本阶段未运行策略、未下单。
- 成本口径：不适用。
- 样本过滤：不适用。
- 策略/归因口径：Stage78-1 执行通路只读验证；不涉及 alpha。

## 结果

- 官方采集库 smoke：
  - `MacDataCollect.framework` 为 Mach-O universal binary，支持 `x86_64` 和 `arm64`。
  - 导出符号包含 `CTP_GetSystemInfoUnAesEncode(char*, int&)`。
  - 不打印原始采集内容的 smoke test 成功：`source=collector_api:_Z28CTP_GetSystemInfoUnAesEncodePcRi len=264`。
- 41407 原生 C++ 只读登录：
  - 命令使用 `CTP_SYSTEM_INFO_SOURCE=collector_api`、`CTP_NATIVE_REQUIRE_SYSTEM_INFO=1`、券商测试版 `MacDataCollect.framework`。
  - 探针启动成功，API 版本：`v6.7.7_MacOS_CP_20240716 15:00:00`。
  - `CTP_SYSTEM_INFO_SOURCE=collector_api:_Z28CTP_GetSystemInfoUnAesEncodePcRi`。
  - `CTP_CLIENT_SYSTEM_INFO=set(len=264)`。
  - `CTP_NATIVE_REGISTER_USER_SYSTEM_INFO=0`，`CTP_NATIVE_SUBMIT_USER_SYSTEM_INFO=0`，符合直连投资者路径。
  - 75 秒等待后未收到交易前置连接回调：`front_connected=false auth_ok=false login_ok=false settlement_ok=false account_count=0 position_count=0`。
- 端口探测：
  - `182.140.218.46:41407` 超时。
  - `182.140.218.46:41415` 超时。
  - `182.140.218.46:41207` 超时。
  - `182.140.218.46:41215` 超时。
- 委托 API：未调用。
- 撤单 API：未调用。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：`0`
- 胜率：不适用。

## 输出文件

- report：无独立文件，控制台只读输出已在本阶段记录中摘要。
- summary：无独立文件。
- orders：无，未下单。
- daily：无。
- quality：无。

## 结论

- 本阶段结论：官方 Mac 采集库已经能在本机加载并生成 `264` 字节 `systemInfo`；本次 41407 只读登录失败不是采集库问题，而是当前本机到券商前置端口整体不可达，表现为 414xx 与 412xx 四个端口全部超时。
- 是否进入下一步：是，但应 fail-closed。
- 下一步：
  1. 让券商确认 2026-05-27 17:32 CST 前后 `182.140.218.46` 的 `41407/41415/41207/41215` 是否开放、是否限制 IP 白名单、当前是否处于服务时段。
  2. 等端口层恢复后，原样重跑本阶段只读命令。
  3. 若只读登录成功，再考虑恢复 1 手测试路径；在此之前不下单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段验证的是 CTP 执行依赖、系统信息采集和网络连通性，不涉及策略参数或历史样本拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：已经把问题从“是否有官方采集库/函数是否能调用”推进到“券商前置当前不可达”。这能减少和券商沟通时的歧义。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；这是一次未连通的只读验证，等端口恢复并登录成功后再合入主状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
