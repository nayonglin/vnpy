# Stage091 独立审查089全793大文件流式intake

2026-10-20 23:56，非重要突破版本；数据输入审查，不运行策略/source/模型。技术审查30,051 checks、0fail；当前未解决P0/P1/P2均0。接受两条条件reference输入，未认证生产、物理session/PIT或完整60日标签。

事前按083完整793请求、原055支持15/其余778待policy锁scope。preflight发现qualify_snapshot覆盖minute_source可能把混source洗为声明source的generic P2；真实producer尚未读payload。作者TDD红→绿修复为只正规化空值，保留原provider交055拒绝；旧e17源码/test/PLAN/header原样保留。修后源码974e514417c31af0c9d9467a8afe6e2dd9b5b23c63cbf9ec157d101119eaa80d，67项独立合成挑战核跨chunk重复/空source/字面NA/Unicode逗号换行provider、NaT/UTC、坏CSV异常、短readinto和hash、endpoints/flags以及793/15范围和grid SHA。

Producer唯一full payload pass：221,112,973 bytes、1,411,116 CSV records、15 chunks；raw SHA5c06124fac52ff37a19d1abe89f6f6a80d36b8ece874eb647286377317289189，stat前后不变。当前089另有3×110 bytes header-only预读，旧freeze receipt明确保留，不能混作full pass。

091用标准库csv逐原始byte行独立流式解析，复算同一rawSHA、records、全native/provider计数、全部匹配source_record_index和原始价格/time/identity字段。24event/32snapshots/7,169原始记录一一一致；raw tq_symbol与exact vendor/native无矛盾，未去重或拼provider。全部110组件独立重建一致：78无目标broad行、16缺格、13有行但待历史policy、2条件输入通过、1日OHLC冲突。原793当前clean exact OHLC/entryopen另只读SQL逐项核验，数据库身份/统计未变。

两通过均stage249_completed_trading_day_fragment独立来源：SHFE.HC.202205@2022-03-04、SHFE.AU.202202@2022-01-17；均完整full055 grid、首open和current clean OHLC吻合。全部778继续未资格，13有行也只coverage；无0→known。旧119 manifest、4767已知source矩阵、1374 robust矩阵及core SHA前后不变。

独立review实际full raw读取2次：首次已核rawSHA/记录/snapshots后，在我自建15grid oracle碰到087非pilotAU202206/2022-05-10展示counter错误（夜盘午夜按自然日误分day），随后追加087原样保留勘误，并按总grid减day225改手写oracle，第二次完成全部复核。原055 grid555/hash及四锁pilot一直正确，089不受影响。生产者仍只有1次full pass；不能将review两次抹成全流程一次。勘误在087/night_count_erratum.json及两份*_night_count_corrected.csv。

标准化研究并集gate为research_union_acceptance.json，accepts_stage089_inputs=True；精确manifest SHA8949b55777f1f2a760ff5f71b51b6c7c1fdd0c98f266bb4d37c217c71414474a，unresolved_P0/P1/P2=0并绑定原review.json SHA。首次093因字段命名P*与unresolved_P*不一致在任何输出/源运行前fail-closed；新标准receipt独立保存，原review不改，无须改093或重读raw。此gate只供root另行授权的研究union，不能当source结果或生产批准。

调研参考[Python3.11 io](https://docs.python.org/3.11/library/io.html)、[CPython3.11原实现](https://raw.githubusercontent.com/python/cpython/3.11/Lib/_pyio.py)与[pandas read_csv](https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html)。判断：二进制原byte hash与解析分块是不同层，chunk边界不构成交易session或provider边界，重复/缺失必须跨chunk整体保留。

开始与结束过拟合判断否：全793与当前15规则事先固定，不按R/胜负/通过结果择样。继续价值是：之前未扫的大原始文件确实增加两条完整条件输入，但能恢复多少整窗、是否有更晚未知必须另验。0C2结果、0source replay/injection、0fit、0label变更、0网络下载/订单/正式操作；不购买/试用或用TqBacktest绕tq_dl=false。参数增改删0，权益/收益/回撤/Sharpe/滑点/交易次数/胜率N/A。

产物：outputs/stage091_independent_large_stream_intake_review/；不改LINE/registry。
