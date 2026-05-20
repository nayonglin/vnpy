# Stage270 国金期货生产版 CTP API macOS 支持检查

- 记录时间：2026-05-19 14:48 CST
- 研究线：`futures_trend`
- 阶段性质：Stage78-1 CTP/broker-test 底层 API 版本兼容性补充排查
- 是否重要突破版本：否；不改变策略、参数、资金口径或发单逻辑

## 本次问题

券商技术追问：生产环境 API 是否有 macOS 版本。

为避免只基于评测包回答，本次补充检查国金官网外部接入页的生产版本 API 下载包。

## 下载与检查

- 官网外部接入页：
  - `https://www.gjqh.com.cn/ws-2003417-c0003-cn/list_5692.shtml`
- 生产版本 API 链接：
  - `https://www.gjqh.com.cn/downloadcommonfile.php?intStorePK=2003417&intModulePK=B0020&strFileGUID=b9cd24914c2f890adacc879f4cb3cee1&strName=v6.7.11_20250714_traderapi.zip`
- 本地下载路径：
  - `/private/tmp/gjqh_ctp_api/v6.7.11_20250714_traderapi.zip`
- SHA256：
  - `45b9a9a347a51e78418f062ed7e44516baa30f50a9f1994dc73b921695452d26`
- 包内容检查：
  - Linux x86_64：`thostmduserapi_se.so`、`thosttraderapi_se.so`
  - Windows 32/64：`thostmduserapi_se.dll/.lib`、`thosttraderapi_se.dll/.lib`
  - 未发现 macOS `.framework`、`.dylib`、`darwin`、`mac` 相关库目录

## 结论

1. 国金官网当前生产版本 API 包同样不是 macOS 可直接使用包。
2. 当前 Mac 能跑 CTP，是因为本机 `.py311` 的 `vnpy_ctp 6.7.2.1` 自带 macOS Mach-O universal framework。
3. 这个本机可用的 macOS CTP 库不是从国金官网生产版 API 包里取得的。
4. 因此对券商的准确答复应区分：
   - “贵司官网生产 API 包里我没有看到 macOS 版本”；
   - “我本机通过 vn.py/vnpy_ctp 自带的 macOS CTP 库可以连接你们 `41207/41215` 测试柜台”。

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

- 是否过拟合：否。本阶段只做 API 二进制平台检查，不涉及策略选择和收益拟合。
- 是否有价值继续：是，但继续点不在策略研究，而在券商确认是否提供 macOS 版生产/评测 API，或确认当前 `41207/41215` 测试柜台可继续用于虚拟盘。
