# Stage007 已保存数据探针的限定独立复审

结论：已保存的345根分钟K及其完成证据、原CSV七字段一致性核验通过；原Stage007质量结论仍是`accepted=false`、worker为`completed_quality_rejected`，父进程exit1。确认1项原校验字段语义缺陷（P1），没有把rejected改为accepted，没有并入cache/overlay或修订执行合同。

审查仅离线读取本次raw/evidence/receipt、精确rb2010日线3行和本地源码；复核脚本没有导入TqSdk、读取凭证、连接网络、重下载、金融回放或改DB。原累计金融attempt仍4、完整结果仍1，C0无alpha结论，不授权C0_attempt3。

## 已确认的字段语义缺陷

`tools/stage007_tqsdk_stream_probe.py:134`把DB的`open_interest`映射为`close_oi`，并在135行把openOI设为unknown。原`examples/portfolio_backtesting/import_tqsdk_all_futures_daily_to_db.py:115`却明确把CSV的`row.open_oi`写入DB `open_interest`。该错位足以导致本次数据库比较出现假不一致，必须在任何新资格合同中明确修正；不能原地改写已失败历史。

| rb2010交易日 | DB open_interest | 原CSV open_oi | 原CSV close_oi |
| --- | --- | --- | --- |
| 2020-08-11 | 1,114,052 | 1,114,052 | 1,064,817 |
| 2020-08-12 | 1,064,817 | 1,064,817 | 1,053,986 |
| 2020-08-13 | 1,053,986 | 1,053,986 | 1,023,253 |

独立只读SQL的3行均唯一，OHLCV同时精确等CSV。目标分钟首OI=1,064,817、末OI=1,053,986；DB提供并验证的是本来源的openOI，没有提供另一份可独立校验的closeOI。该结论限定于这份导入合同及已抽查的rb2010三天，不能自动推断整个DB所有来源的字段语义。

## 已保存raw与完成证据

独立按rb夜盘120分钟、上午75+60分钟、下午90分钟枚举345网格，与CSV全部时间键有序逐值相同。键唯一，数值有限，OHLC合法，量仓非负。345条证据均有同键完成记录和至少一分钟后的严格后继；目标末分钟08-12 14:59的保存后继是同日21:00。

collector只接受serial非末行、并检查后继时间，回放终止本身不会把forming末行升级为完成。UTC纳秒→Asia/Shanghai转换源码正确，独立时钟哨点和跨夜网格一致。原提供商serial及SDK原始日志按协议不保留；完成结论依据保存的逐键后继表与执行代码，不能将其说成另有外部签名或原始stream复验。

自行聚合七字段为open3795/high3809/low3780/close3805/volume740132/openOI1064817/closeOI1053986，全部精确匹配原目标日CSV。原quality也正是CSV accepted、数据库只在`close_oi`一项拒绝。

## 正规通路、超时与订单边界

本机TqSdk 3.10.2的api/auth/backtest/tqsim/downloader五份源码同时匹配安装wheel RECORD及实际preflight SHA，支持未改写鉴权/授权检查的判断。工具直接使用正常`TqAuth`、`TqBacktest`和明确本地`TqSim`，worker无insert_order/cancel_order/TargetPosTask/资金账户调用；parent与worker receipt均记order/cancel=0。该依据是本工具调用图与保存receipt，不是额外读取券商账户流水。

父进程只启动一个worker、180秒deadline、超时及finally均kill进程组，不自动retry；实际38.220319秒退出。凭证只在进程内给TqAuth，子进程argv不包含账户值；SDK stdout/stderr/logging丢弃，允许字段receipt不保存凭证或SDK raw日志。复审没有读取私有配置。

Stage008可另行预声明字段感知资格：原CSV核七字段，已知来源DB核OHLCV+openOI，DB closeOI明确unknown。本审查未执行Stage008资格，也未授权并入任何缓存。单窗口成功只证明本次窗口在当时账号下可取且一致，不外推全市场权限、未来配额或全部历史质量。

过拟合判断：否，查的是已知缺口和固定源schema，没有收益选择或参数搜索。继续价值：是，明确区分合法数据能力与本地导入语义，避免无谓复连和把缺字段误写为通过。调研沿用Stage007预声明已记录的官方文档/GitHub与本机安装源码；本次只作本地证据核查，没有新增市场事实或额外网络调研。
