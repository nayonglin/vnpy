# Stage290 CTP Mac直连官方采集函数接入修正

- line_id：`futures_trend`
- 当前模式：day
- 记录时间：2026-05-22 11:39 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行接入 / CTP穿透式监管上报格式修正
- 是否重要突破：否，属于阻塞项收敛和代码预埋
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 券商最新说明：MacOS/iOS直连模式下，登录接口 `ReqUserLogin` 需要传入由采集库函数 `CTP_GetSystemInfoUnAesEncode(result, length)` 得到的采集信息，才能完成穿透式监管上报。
  - 本地 Mac CP SDK 头文件：`ReqUserLogin(CThostFtdcReqUserLoginField*, int, TThostFtdcSystemInfoLenType, TThostFtdcClientSystemInfoType)`，`TThostFtdcClientSystemInfoType` 长度为 `273`。
  - 网络第三方资料也支持一个判断：直连模式的系统信息上报发生在 `ReqUserLogin` 阶段，且 `CTP_GetSystemInfoUnAesEncode` 是相关采集/编码函数。
- 我的判断：
  - 我们此前使用 `DataCollectforMacOS` 可执行文件打印出的 `CollectData` 文本，并把文本拷入 `ReqUserLogin` 的 `systemInfo` 参数；这只能证明“传了非空字节”，不能证明是券商后台认可的原始加密采集字节。
  - 券商最新说明基本解释了之前后台查不到上报的原因：正式路径应当是链接采集库并调用 `CTP_GetSystemInfoUnAesEncode`，而不是解析独立命令行工具的文本输出。
  - `RegisterUserSystemInfo` / `SubmitUserSystemInfo` 仍不应作为直连投资者正常路径。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/ctp_native_system_info.hpp`
- 修改脚本：
  - `examples/portfolio_backtesting/run_ctp_stage278_native_cpp_td_login_probe.cpp`
  - `examples/portfolio_backtesting/run_ctp_stage278_native_cpp_td_login_probe.sh`
  - `examples/portfolio_backtesting/run_ctp_stage281_native_cpp_smoke_order.cpp`
  - `examples/portfolio_backtesting/run_ctp_stage281_native_cpp_smoke_order.sh`
- 删除脚本：无
- 新增参数：
  - `CTP_SYSTEM_INFO_SOURCE=collector_api`：强制使用官方采集函数路径。
  - `CTP_SYSTEM_INFO_DYLIB`：可选，指定券商/CTP提供的 Mac 采集动态库路径。
  - `CTP_NATIVE_REQUIRE_SYSTEM_INFO=1`：要求必须取得采集信息，否则登录探针直接失败。
  - `CTP_USE_DATACOLLECT_TEXT_FALLBACK=1`：仅用于历史兼容，显式允许继续使用 DataCollect 文本输出。
- 修改参数：
  - DataCollect 文本解析不再默认启用，避免把历史诊断路径误当正式上报路径。
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：CTP 41407 原生 C++ 登录/报单探针的终端采集信息来源修正，不涉及 Stage78-1 alpha。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 两个原生 C++ 探针均已编译通过。
  - 当前本机已有的 `DataCollectforMacOS0719.zip` 只包含可执行文件，没有可链接的 Mac 动态库/头文件。
  - 该可执行文件内部可见私有符号 `CTP_GetRealSystemInfo(char*, int&)`，但不是可链接的正式库；因此还不能按券商说明直接完成 `CTP_GetSystemInfoUnAesEncode` 路径实测。

## 输出文件

- report：无
- summary：无
- orders：无
- daily：无
- quality：无

## 结论

- 本阶段结论：
  - 之前“C++ 直连能登录，但券商看不到监管上报”的最大概率原因，是我们使用了 DataCollect 命令行工具的文本输出，而不是官方采集库函数返回的原始加密采集字节。
  - 代码已预留官方函数动态调用路径；券商只要提供可链接的 Mac 采集库，就可以用 `CTP_SYSTEM_INFO_SOURCE=collector_api` 和 `CTP_NATIVE_REQUIRE_SYSTEM_INFO=1` 进行正式复测。
- 是否进入下一步：是
- 下一步：
  1. 请券商提供 Mac 版采集库/头文件，或确认 `CTP_GetSystemInfoUnAesEncode` 位于哪个 `.dylib/.framework`。
  2. 拿到库后，运行 41407 登录探针，向券商提供 `FrontID / SessionID / LoginTime / AppID` 让其后台确认上报。
  3. 后台确认后，再复刻报单/撤单 smoke test。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段完全不调整策略参数、不改变品种池、不看收益曲线，只是在修正 CTP 监管上报的字节来源。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：该问题直接决定 Mac 直连实盘/评测环境能否被券商验收；如果不闭环，即使策略信号正确也无法进入正式执行链路。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录最新上报路径判断。
- 是否更新 `research/registry.md`：否，当前线状态未发生正式候选级别变化。
- 是否追加根目录 `memory.md/back_log.md`：否，待券商确认后台收到上报后再追加重要里程碑。
