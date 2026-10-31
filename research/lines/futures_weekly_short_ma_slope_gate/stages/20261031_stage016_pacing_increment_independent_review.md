# Stage016 查询节拍修复增量独审

时间：2026-10-31T20:27:44.592081+08:00。line_id=futures_weekly_short_ma_slope_gate。PASS_OFFLINE_INCREMENT_WITH_LIMITATIONS；实际来源、最终statement和production资格仍false。旧整链独审JSON 99bf6d1f…逐字不改，本记录只增量绑定当前931源码及查询等待边界；不是新的金融回放。

## 观察、确定发现与原因界限

root首轮完整CI的88套件2254项为2252通过/2失败，critical281项前后无漂移；不是全绿。两个失败分别为seal的final_order_query_pacing_timeout，以及历史C9 AI fixture未显式绑定旧身份触发weekly disabled。后者只补测试中的C9 profile和历史AI material，正式weekly guard和配置未放宽。作者此前精准重跑/加probe的seal曾通过，原始失败没有逐次monotonic轨迹，因此不能确定宣称原CI失败由本竞态造成；仅可说行为时序相容。

作者先对order/position/common三处用scripted clock确认双读跨next_allowed误超时。独审继续发现trade和position-detail两处遗漏：last=.1、next1.2、clock .2→1.199999→1.200001、budget8秒，仍在0 API时报pacing_timeout。独审attempt001为3测试2失败1通过。扩展attempt002又确认trade首次poll跨过允许点和deadline后仍发1次FakeApi查询：clock .2→1.200001，budget.5即deadline.7；4测试3失败1通过。两次失败时931 SHA均为e3fc8a10427f387195d0c0f8ed4f7c28ec47fdb43ed1971943620963e548597a，实际测试前后相同。原脚本/日志/JSON全部保留。

当前作者修复五个family循环，每轮用同一now判断允许时刻及remaining，保留1.1秒默认节拍、至少1秒门、原预算和sender/授权；trade新增post-pacing真实deadline门，在reqid/API之前阻断已经逾期的新查询。

## 独立复验与哈希

- 原独立v2反例4例全绿，旧trade/detail误超时及晚查询均关闭。
- 新独立五helper时钟测试7例全绿：四类查询跨允许时刻、直接跨过deadline、等待过程中deadline先到、order/position的min1s和harddeadline、common helper的节拍及真实超时。
- 精确运行作者9个新增回归和首次失败的seal case，10例20.413秒全绿，0跳过，源码前后无漂移。

本增量共21次成功调用，不是全局去重总数，不与旧97或作者137相加冒称完整CI通过。root修复后完整88套件重跑结果由root另行封存，本记录不声称其已通过。

当前整931 SHA为ac3176c8752fd49c8527953deed6a2bef8ff1e9305327dfe86b33136f4e06c10。五helper AST已精确绑定；此前七个quota/native/deferred关键函数AST逐一完全相同。旧独审源map中除931之外全部实际文件哈希仍相同。没有原13604整931字节快照，不声称已独立证明全文件在五函数之外逐字不变，也不借用旧V6整文件身份。新source需要当前完整CI/正式source qualification另验。

## 保留边界

本轮scope内P0/P1/P2未修复数为0，但真实capture authority、最终cash-day-close解析、自动TransferSerial producer、真实CTP/银行/SMTP/订单验证、不可变release/activation/master及生产安装仍未建立。native partial fill领先旧四查询的剩余child仍需真实source reconciliation；不承诺同batch自动继续。所有测试为本地FakeApi/合成callback epoch，查询计数只是fixture计数，绝不当真实provider资格。

本次不调alpha或风控参数，不构成新过拟合；继续价值在消除可确定复现的误超时和越deadline只读查询。原Stage014经济NO_PROMOTION及研究局限保留。无新增回测结果，金融指标N/A。未修改作者实现、旧审查、Git/index、生产，未连接任何外部服务。
