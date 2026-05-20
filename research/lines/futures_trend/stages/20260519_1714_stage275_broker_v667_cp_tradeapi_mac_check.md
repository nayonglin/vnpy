# Stage275：券商新给 v6.6.7_CP_tradeapi 包的 Mac 可用性检查

- 时间：2026-05-19 17:14 CST
- 研究线：`futures_trend`
- 类型：Stage78-1 CTP/券商测试柜台 API 包兼容性检查，不涉及 alpha 优化
- 是否重要突破版本：否，属于连接链路诊断
- 是否过拟合：否。本阶段没有改策略、没有调参、没有根据收益挑选版本，只检查券商给的新 API 包能否在 Mac/vn.py 环境加载。
- 是否仍有继续价值：是。它能明确 `41407` 交易前置问题是否可以通过更换券商给的新 API 包解决。

## 输入文件

- 本地文件：`/Users/bytedance/Downloads/v6.6.7_CP_tradeapi.zip`
- 文件大小：约 `8.0M`
- MD5：`4832dff0132150ffaf8ac32f7b58db00`
- SHA256：`8cfadf8d9ee983e07985f732f6485b87930b76c4a2d0903d355f125ffd4dff1a`

## 检查方法

1. 使用 `unzip -l` 查看包内容。
2. 解压到 `/private/tmp/ctp_v667_cp_tradeapi`，不覆盖当前 `.py311`。
3. 使用 `file` 检查 `thosttraderapi_se` / `thostmduserapi_se` 的平台类型。

## 检查结果

包内包含：

- Linux x86_64：
  - `thosttraderapi_se.so`
  - `thostmduserapi_se.so`
- Windows 32/64 位：
  - `thosttraderapi_se.dll`
  - `thosttraderapi_se.lib`
  - `thostmduserapi_se.dll`
  - `thostmduserapi_se.lib`
- 头文件：
  - `ThostFtdcTraderApi.h`
  - `ThostFtdcMdApi.h`
  - `ThostFtdcUserApiDataType.h`
  - `ThostFtdcUserApiStruct.h`

包内未发现：

- macOS `.framework`
- macOS `.dylib`
- Mach-O 动态库

`file` 结果确认：

- Linux 库是 `ELF 64-bit LSB shared object, x86-64`
- Windows 库是 `PE32/PE32+ executable (DLL)`
- 没有可供当前 macOS Python/vn.py 进程加载的二进制。

## 判断

- 这个 `v6.6.7_CP_tradeapi.zip` 不能直接在当前 Mac 上用于 vn.py/`vnpy_ctp` 测试。
- 因为它不是 Mac API 包，不能替换 `DYLD_FRAMEWORK_PATH` 所需的 `thosttraderapi_se.framework`。
- 因此本次无法用它继续测试 `41407` 交易前置。
- 若券商希望我们在 Mac 上测试 `v6.6.7_CP`，需要提供 macOS 版：
  - `thosttraderapi_se.framework` / `thostmduserapi_se.framework`，或
  - `.dylib` 版本，且需要与 Python/vn.py 封装 ABI 匹配。

## 对券商建议话术

```text
这个 v6.6.7_CP_tradeapi.zip 我们检查了，包内只有 Linux .so 和 Windows .dll/.lib，没有 macOS 的 framework 或 dylib。

我们当前是在 Mac 上用 vn.py / Python 测试，所以这个包无法直接加载，也无法用来验证 41407 交易前置。

麻烦提供 v6.6.7_CP 的 macOS 版本：
thosttraderapi_se.framework / thostmduserapi_se.framework
或者可用于 macOS 的 dylib，并确认是否有适配 Python/vn.py 的封装。
```

## 回测指标

本阶段未做回测，以下指标不适用：

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A

## 后续 TODO

1. 向券商确认是否有 v6.6.7_CP 的 Mac 包或 vn.py/Python 封装。
2. 如果只能提供 Linux/Windows 包，则 Mac 实盘路线不能用该包解决；需要继续使用已能加载的 SimNow Mac CP SDK 或回到 `41207/41215` 稳定路线。
3. 若后续拿到 Mac 包，再用 Stage273 TD-only 探针复测 `41407`。
