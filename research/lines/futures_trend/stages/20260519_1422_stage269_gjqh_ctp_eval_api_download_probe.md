# Stage269 国金期货评测版 CTP API 下载与 Mac 兼容性验证

- 记录时间：2026-05-19 14:22 CST
- 研究线：`futures_trend`
- 阶段性质：Stage78-1 CTP/broker-test 底层 API 版本兼容性排查
- 是否重要突破版本：否；这是执行链路排障，不改变策略 alpha、参数或资金口径

## 本次问题

用户提供国金期货外部接入页面：

- `https://www.gjqh.com.cn/ws-2003417-c0003-cn/list_5692.shtml`

券商技术反馈：评测版本 API 按该网站下载。

## 下载与文件检查

- 页面中的评测版 API 链接：
  - `https://www.gjqh.com.cn/downloadcommonfile.php?intStorePK=2003417&intModulePK=B0020&strFileGUID=74aae7bc92185f8600dd3b38675bf342&strName=v6.7.10_CP_20250415_traderapi.zip`
- 本地下载路径：
  - `/private/tmp/gjqh_ctp_api/v6.7.10_CP_20250415_traderapi.zip`
- SHA256：
  - `4a4057374d19e8a66e0b11cb7a3b60328a10b03da760f424adfa91ef4ba8ffdb`
- 包内容：
  - Linux 64 位：`thostmduserapi_se.so`、`thosttraderapi_se.so`
  - Windows 32/64 位：`thostmduserapi_se.dll/.lib`、`thosttraderapi_se.dll/.lib`
  - 未发现 macOS 可直接使用的 `.framework` 或 `.dylib`

## 当前本机 CTP 环境

- Python：`.py311/bin/python`
- `vnpy_ctp`：`6.7.2.1`
- 当前本机已安装 macOS CTP 库：
  - `.py311/lib/python3.11/site-packages/vnpy_ctp/api/libs/thostmduserapi_se.framework`
  - `.py311/lib/python3.11/site-packages/vnpy_ctp/api/libs/thosttraderapi_se.framework`
- 文件类型为 Mach-O universal binary，包含 `x86_64` 和 `arm64`

## 连接验证

用当前 Mac `vnpy_ctp 6.7.2.1` 只读测试评测前置，未发单：

1. 页面文字顺序口径：
   - TD：`tcp://182.140.218.46:41415`
   - MD：`tcp://182.140.218.46:41407`
   - 结果：失败
   - 关键错误：`CTP:API Front shake hand err: decode err`、`Decrypt handshake data failed`、`交易服务器连接断开，原因4097`

2. 前次沟通顺序口径：
   - TD：`tcp://182.140.218.46:41407`
   - MD：`tcp://182.140.218.46:41415`
   - 结果：失败
   - 关键错误同上：`decode err / 4097`

3. 已打通的券商测试柜台对照：
   - TD：`tcp://182.140.218.46:41207`
   - MD：`tcp://182.140.218.46:41215`
   - 结果：成功
   - 状态：`readonly_snapshots_received`
   - 行情登录、交易授权、交易登录、结算确认、合约查询、账户/持仓快照均成功
   - 本次仍未发单：`real_order_enabled=false / order_api_called=false`

## 结论

1. 国金页面的评测版 API 包确实能下载，版本为 `v6.7.10_CP_20250415_traderapi`。
2. 该包不是 Mac 可直接替换包；它只包含 Linux x86_64 和 Windows 库。
3. 当前 Mac 上不能把该包直接装进 `.py311` 的 `vnpy_ctp`，否则会因为二进制格式不匹配而不可用。
4. 414xx 评测前置在两种端口顺序下都出现握手解密失败，说明不是简单的 TD/MD 端口写反，更像是评测前置与当前 Mac CTP API 版本/认证链路不匹配。
5. 41207/41215 券商测试柜台已经能被当前 Mac `vnpy_ctp 6.7.2.1` 稳定只读连接，因此 Stage78-1 当前虚拟盘执行链路不应切到 414xx，除非券商提供 macOS 版评测 API 或明确要求用 Linux/Windows 运行。

## 参数和结果变更

- 新增参数：无
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

- 是否过拟合：否。本阶段只验证底层 API 包、二进制平台和连接错误，不调整策略、不选择参数、不评价收益。
- 是否有价值继续：是，但方向应收敛。继续追 414xx 的前提是券商提供 macOS 版 `v6.7.10_CP` API，或我们切到 Linux/Windows 环境测试；Stage78-1 当前日常虚拟盘继续使用已通过的 41207/41215。

## TODO

1. 向券商确认是否有 macOS 版 `v6.7.10_CP_20250415` 的 `.framework` 或 `.dylib`。
2. 向券商确认 41207/41215 是否就是当前可用于测试下单的柜台；若是，Stage78-1 broker-test 继续沿用该柜台。
3. 若必须使用 414xx 评测前置，则准备 Linux/Windows CTP 连接机或 Docker/远端环境，避免破坏当前 Mac 可用链路。
