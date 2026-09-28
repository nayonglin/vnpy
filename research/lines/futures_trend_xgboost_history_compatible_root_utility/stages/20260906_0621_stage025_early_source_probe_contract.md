# Stage025 早期来源与OI口径探针合同

- line_id：`futures_trend_xgboost_history_compatible_root_utility`；时间2026-09-06 06:21 CST。
- 类型：一次性有界来源实验，不新增通用功能，不做回测/训练。沿用用户研究与重建授权，不请求重复批准，不启动reviewer。
- 原完整目标、276事件、18品种、成本、账户规模和基准不变。Stage024目录缺13个原合约，原产物不改，不再调用该目录/指定元数据接口。

## 证据与判断

- 旧Stage195/196记录Tq早期目录缺口及Tushare历史补数，但Stage196只覆盖2015-2019，不能据此认定本次13个2020合约的数据库行都来自Tushare。
- `download_tqsdk_main_contract_bars.py`与`vnpy_tqsdk/tqsdk_datafeed.py`证明存在get_kline_serial直接导入路径，且用open_oi写入数据库open_interest。Tushare旧修复器使用fut_daily.oi。两个不同时间口径未经验证不能直接混称收盘持仓量。
- 本轮只读冻结A数据库rb2005于2019-11-01至2020-05-15的130行，OI和volume均正；这证明缓存存在，不是来源证明或全链完整证明。
- [Tushare合约接口](https://tushare.pro/document/2?doc_id=135)提供list_date/delist_date/d_month，要求至少2000积分；[官方HTTP协议](https://tushare.pro/document/1?doc_id=130)及[GitHub客户端](https://github.com/waditu/tushare/blob/master/tushare/pro/client.py)支持JSON POST到api.tushare.pro。本机客户端URL为api.waditu.com/dataapi，与核验的官方示例不同；不改安装包、不对该差异归因，只用官方主机的HTTPS路径。
- [TqSdk文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)区分open_oi/close_oi；一次元数据失败不能替代K线接口效果。以上仅支持来源核验，不支持alpha。

## 固定探针

1. Tushare：现有环境TUSHARE_TOKEN与SDK默认token相同，仅取现有环境值；一次HTTPS POST `https://api.tushare.pro`，api_name=fut_basic、exchange=SHFE、fut_type=1、fut_code=RB，fields=ts_code,symbol,exchange,fut_code,list_date,delist_date,d_month。30秒超时、无重试/重定向、不降级明文HTTP。不打印/保存请求token，保留响应或脱敏错误及请求步骤。失败即停止该来源，不替换其他凭证或绕过权限。
2. Tq：仅`SHFE.rb2005`，TqSim+TqBacktest固定2020-05-15一日，get_kline_serial duration86400、data_length1000，推进到BacktestFinished后复制。数据源窗口2019-11-01至2020-05-15，保留原始datetime/OHLC/volume/open_oi/close_oi；后界以基准缓存现有最后一天预先选定，不由新响应结果决定。180秒总超时、无策略/订单调用，不请求其他合约或元数据。
3. 若日线可得，按日期与冻结数据库rb2005逐值比对，只判断OHLC/volume/开端OI/结束OI的对应性，原库只读且执行前后SHA相同。不给标签/收益/回撤结论，不据比较更改A原始输入。
4. 只写本线`artifacts/stage025_early_source_probe/`，一次性驱动不保留为通用工具。记录输入哈希、开始/结束时间、步骤、异常类型与脱敏信息，修正上一探针仅记录异常类型的诊断不足，但不重跑上一请求。

## 反思

- 开始过拟合：否，无收益/标签或模型选择；长期研究选择偏差仍在。
- 开始继续价值：是，区分行情和合约服务的边界、厘清OI字段时间；没有可靠全链来源前不训练。
- 本阶段无新增/修改/删除回测结果；期末权益、总收益、最大回撤、Sharpe、滑点、交易次数与胜率不适用。生产/CTP/共享映射/其他研究线/registry/总账均不写。
