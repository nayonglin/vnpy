# Stage555：统计局搜索参数的官方脚本纠偏

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 04:55 CST；非突破；仅参数来源核验。
- 已读553已留site配置，不重新GET；只对548搜索壳已直接引用的util.js执行1次小GET，原body/receipt留存，未POST、未扫描或请求其他脚本。未触碰552/554输出。

**结论：公开客户端实际发送的标题位置字段是`keyPlace=1`，大小写应与源码一致。此前请求的`keyplace=1`不能视为标题筛选已生效。** 但尚未用新请求验证服务端结果，不能断言修这个拼写就解决全部宏观/微信混入。

## 准确字段证据

[官方util.js](https://p.so-gov.cn/web/api/util.js) 真200、22,446 B，SHA`ec81939017a9d9b05ea3732b87d48e612bf8aaedb6cf54ea9c4855f70c433c7b`。源码97—106行的`getData`调用`$(this).data()`，不是将input的name直接序列化；139—168行`toolParams`合并所选data。538—545行更直接使用`toolbar_radio('keyPlace',...)`和`toolbar_selected('keyPlace',...)`，这提供大小写的独立内部证据。

548已存search.body 258—259行给出`data-key-place="0"`全文、`data-key-place="1"`标题。底部radio虽有name="keyplace"，实际采集不是该name，不能据此继续发送小写p。

- 排序：`sort=dateDesc`（或`relevance`），548壳242—243行原值；不改成自行猜的uppercase枚举。
- 自定义日期：`timeOption=2`、`startDateStr`、`endDateStr`，日期格式`yyyy-mm-dd`。util573—603行注释和`.data('startDateStr', start)`/`.data('endDateStr', end)`直接确认；548壳305—311行input以data-time-option和data-start/end-date-str承载同名字段。
- 高级搜索函数114—136行另加入`adv=1`及`qt=advKeyWord()`。普通工具栏不必擅自增加adv。
- **util没有`pageSize`或`rows`，没有主结果分页参数的新增证据**。548 query.js的combin函数有page/pageSize，不可移植为主搜索DTO。当前不继续抓其他JS、不尝试100/20/rows参数网格。

553原site响应仍说明all为默认tab、maxPage10、defaultKeyPlace0、toolsType0、unionSearchConf.status=true。autoJson.pageSize10属于自动结果配置，不认证主结果页长；联查配置也不能证明553异常标题的唯一来源。2010—2021缺段的下一次真实请求范围由root另冻，不在本阶段发送。

## 改动与边界

新增原util.js、receipt、parameter_evidence.json及本stage；修改/删除策略参数0，新增/修改/删除金融结果0。本轮fit/cash/SQL均0，期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。未改LINE、registry、Git、正式材料或生产。

开始与结束对同史择题过拟合风险均**是且高**；本阶段没有收益筛参。继续修正公开检索的可复验字段有价值**是**，因为服务端忽略字段会制造伪缺失；无限搜索API工程的价值**否**，所以一次原脚本后停止，等待固定元数据获取预算。来源字段纠偏不提供PMI alpha、更高收益或可加注证据。

证据：`research/lines/futures_full_market_long_signal_ai/outputs/stage555_pmi_search_parameter_source/parameter_evidence.json`。
