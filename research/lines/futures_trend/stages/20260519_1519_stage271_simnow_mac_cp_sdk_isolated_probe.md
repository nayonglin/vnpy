# Stage271 SimNow Mac CP SDK 隔离加载与 414xx 只读探针

- 记录时间：2026-05-19 15:19 CST
- 研究线：`futures_trend`
- 阶段性质：Stage78-1 CTP/broker-test 底层 SDK 隔离验证
- 是否重要突破版本：否；不改变策略 alpha、参数、资金口径或发单逻辑

## 背景

券商技术提供 SimNow 官方 API 下载页，用户手动下载 Mac 评测版 SDK：

- `/Users/bytedance/Downloads/TraderapiMduserapi_6.7.7_MacOS_CP.zip`

目标：在不覆盖当前已打通的 `.py311/vnpy_ctp` 环境前提下，单独验证该 Mac CP SDK 是否能解决 `414xx` 评测前置的握手失败问题。

## SDK 检查

- 文件大小：约 `6.1M`
- MD5：`bbb85d8789008ee81094aca87b2c9715`
- SHA256：`0fd120e911234a6c260d158519a76a6ffd00b7f93a6bb412de20dc50236911b3`
- 解压路径：
  - `/private/tmp/simnow_mac_cp_sdk/TraderapiMduserapi_6.7.7_CP_MacOS/TraderapiMduserapi_6.7.7_CP_MacOS测评版`
- SDK 内容：
  - `thostmduserapi_se.framework`
  - `thosttraderapi_se.framework`
- 架构：
  - Mach-O universal binary
  - 支持 `x86_64` 与 `arm64`
- 版本字符串：
  - `v6.7.7_MacOS_CP_20240716 15:00:00`
- 代码签名：
  - `codesign --verify` 通过

## 本次改动

- 新增隔离 wrapper：
  - `examples/portfolio_backtesting/run_ctp_stage271_broker_cp_mac_sdk_readonly_probe.sh`
- 更新 SOP：
  - `skills/stage78-simnow-shadow-sop/SKILL.md`

wrapper 特点：

- 不覆盖 `.py311/lib/python3.11/site-packages/vnpy_ctp/api/libs`
- 从本机 `ctp_broker_test.local.env` 读取账号信息
- 支持命令行环境变量覆盖 `CTP_BROKERID/CTP_TD_ADDRESS/CTP_MD_ADDRESS`
- 通过 `CTP_MAC_CP_SDK_DIR` 和 `DYLD_FRAMEWORK_PATH` 临时加载 Mac CP SDK
- 只跑 Stage174 只读探针，不发单

## 隔离加载验证

命令通过 `DYLD_PRINT_LIBRARIES=1` 验证 Python/vnpy_ctp 实际加载的是 `/private/tmp` 中的 CP SDK：

- `thostmduserapi_se.framework`
- `thosttraderapi_se.framework`

第一次加载时 macOS 因下载隔离标记阻止加载：

- `library load disallowed by system policy`

只对 `/private/tmp` 解压副本执行：

- `xattr -dr com.apple.quarantine <sdk_dir>`

之后导入 `vnpy_ctp.CtpGateway` 成功。

## 414xx 只读连接结果

命令：

```bash
CTP_BROKERID=1010 \
CTP_TD_ADDRESS=tcp://182.140.218.46:41415 \
CTP_MD_ADDRESS=tcp://182.140.218.46:41407 \
bash examples/portfolio_backtesting/run_ctp_stage271_broker_cp_mac_sdk_readonly_probe.sh --connect --wait-seconds 25
```

结果：

- 行情服务器连接成功
- 行情服务器登录失败：
  - 代码：`64`
  - 信息：`CTP:客户端未认证`
- 本次未调用任何发单接口

关键变化：

- 之前用当前 `vnpy_ctp 6.7.2.1` 自带库连接 `414xx` 时是握手层错误：
  - `CTP:API Front shake hand err: decode err`
  - `Decrypt handshake data failed`
  - `4097`
- 换成 SimNow Mac CP SDK 后，`decode err / 4097` 消失，说明 CP SDK 与 `414xx` 前置的握手协议匹配。
- 现在阻塞转移到认证层：`客户端未认证`。

## 412xx 对照

用同一套 Mac CP SDK 连接已打通的 `41207/41215`，出现 `decode err`，说明：

- `41207/41215` 更适配当前 `.py311` 中的 `v6.7.2_MacOS_20231016` 库；
- `41415/41407` 更适配 SimNow `v6.7.7_MacOS_CP_20240716` 库。

## 结论

1. 用户下载的 SimNow Mac CP SDK 是正确包，MD5 与页面一致。
2. 该 SDK 可以在 Mac 上被当前 vn.py/vnpy_ctp 扩展隔离加载。
3. 该 SDK 确实解决了 `414xx` 的握手失败问题。
4. 当前 `414xx` 不能继续登录的原因不是 SDK 不匹配，而是客户端认证未通过，需券商确认该账号在 `414xx` 评测前置上的 AppID/AuthCode/权限是否已登记。
5. 当前 Stage78-1 日常虚拟盘仍应继续使用已打通的 `41207/41215` 路线；`414xx` 暂作为 CP 评测隔离路线。

## 参数和结果变更

- 新增参数：`CTP_MAC_CP_SDK_DIR`
- 修改参数：无
- 删除参数：无
- 新增回测结果：无
- 修改回测结果：无
- 删除回测结果：无
- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 过拟合与继续价值反思

- 是否过拟合：否。本阶段只验证 CTP SDK 与前置协议/认证链路，不涉及策略参数、收益评估或品种选择。
- 是否有价值继续：是，但继续点不在策略。下一步应让券商确认 `414xx` 评测前置对应的 AppID/AuthCode、BrokerID、账号权限是否已经登记；拿到正确认证后复跑 Stage271。

## TODO

1. 把 `代码64：CTP:客户端未认证` 发给券商技术，确认 414xx 的 AppID/AuthCode 是否正确且已登记。
2. 询问券商：`41207/41215` 和 `41415/41407` 分别对应什么柜台/API版本，是否可以继续使用 412xx 做虚拟盘。
3. 若券商给出新的 AppID/AuthCode，只更新本机 `ctp_broker_test.local.env` 或临时环境变量，不能写入聊天或公开文件。
