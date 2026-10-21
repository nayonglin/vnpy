# Stage087 新资料试取范围与固定四样本协议

2026-10-20 23:41；非重要突破版本。本步只生成离线计划，未连接Tq API/行情、读取凭据或下载；未算C2、回放source、fit或改参数/标签。原4767条件已知与1374 robust文件SHA前后不变；793请求/1926首C2窗完整保留，不以未来资料可得性改变N或eligibility。

原055冻结SHA9736b1b0a362e4a12b2c7839db067c59e0a3b430be0c65c384f2a4433ba9d8c2逐一判断：当前技术范围15请求/37阻塞窗，其余778=375日期早于2020+403不在冻结产品表，全部在all793_reference_scope.csv保留，不扩helper。没有套2020规则为778补资格。

选择规则先固定为四个exchange各取(source_trade_date,contract_epoch_id,requirement_id)最早1条，exchange排序，最多4。四所代表这一事前覆盖约束下恰为最小4条；规则不用R、胜负、未来标签、windowcount、价格匹配、下载成功率或旧provider结果。序列逆序及价格/windowcount扰动不改变选择，失败不替换样本。

| exact epoch / source trade date | 拟用Tq symbol | previous共同day | 原055 grid |
|---|---|---|---|
| CZCE.CF.202005 / 2020-01-02 | CZCE.CF005 | 2019-12-31 | day225 |
| DCE.JM.202609 / 2026-06-03 | DCE.jm2609 | 2026-06-02 | night120+day225 |
| GFEX.LC.202605 / 2026-01-26 | GFEX.lc2605 | 2026-01-23 | day225 |
| SHFE.AU.202202 / 2022-01-17 | SHFE.au2202 | 2022-01-14 | night330+day225 |

pilot_plan.json含每项exact vendor orderbook/native、YYYYMM/lifetime、目标OHLC/entryopen、完整055 grid SHA和拟用symbol；pilot_reference_grids/存完整序列。上述symbol只是官方格式+本地vendor binding的拟定，未认证Tq服务器交割年月/历史资料/账号权限。CZCE三位码不得自动换成其他年代；服务端identity或返回日期/价格冲突保留unknown，不能改epoch救数据。LC day225只是原helper研究假设，不是实际时段认证，若下载见夜盘不得删夜盘凑日盘。

自然guard请求统一previous共同source工作日20:59→D15:01，均为明确+08 timezone-aware datetime；包括CF跨元旦、AU/LC跨周末。guard是较宽取数边界，不是交易session，也不缩短原055 grid。本机TqSdk3.10.2源码及纯datetime AST验证显示datetime右边界可能含end，focus定位也不保证严格左界；所以不谎称半开API，原始返回全部保留并记实际首尾。guard内非grid分钟/端点、缺格、timestamp秒/tz矛盾、非法价格、OHLC/entryopen/identity/provider冲突均拒绝或unknown，不floor/shift/ffill/拼接providers。请求外额外上下文另列，不默删原raw。

后续取数若另行开展：只单exact合约/dur60/adjNone，保存raw原文件SHA/bytes/stat、SDK版本与任务error/timeout，核human datetime和datetime_nano同一instant；按原exact metadata年月/生命周期匹配，并独立来源核完整grid、current clean日OHLC和首open。is_finished或100%只说明任务状态，不能代替非空、完整或成功资格。每次失败及空结果仍保留对应原N；取得这些分钟也不保证60日窗完全known。root已另告知tq_dl=false；本计划不授权购买、试用或以TqBacktest绕过历史导出功能门槛。

官方调研结论见sources.json：[DataDownloader文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html)和[维护者downloader源码](https://raw.githubusercontent.com/shinnytech/tqsdk-python/master/tqsdk/tools/downloader.py)用于下载边界；[datetime源码](https://raw.githubusercontent.com/shinnytech/tqsdk-python/master/tqsdk/datetime.py)用于明确date/datetime差异；[合约代码规范](https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html)用于大小写/三位码。文档当前3.10.3，本机3.10.2另锁本地SHA；不把当前SDK/服务端元数据当历史PIT或交易所session原文。

90项离线检查0fail，初跑AST harness漏typing.Union注解依赖，补标准库类型名后通过，未import Tq API。源码、输入、calendar、055、metadata和4767/1374矩阵审后SHA不变。pilot_plan SHA dbe872de107ba88fdcde46112ecfae6e5b5e2ee86d520507b3a0e996d9445543。计数network_connections仅指Tq行情/API连接；本步确实按要求浏览了公开官方文档，说明见counter_scope_receipt.json。

开始与结束过拟合判断否：固定分层和时序取样，没有收益择参。继续价值是：真正新资料尝试前确定日期、身份和拒绝规则；取得权限/资料前不能提高模型置信。新增/修改/删除策略模型参数均0，权益/收益/回撤/Sharpe/滑点/交易数/胜率N/A。

产物：outputs/stage087_reference_intake_pilot_plan/；不改LINE/registry。
