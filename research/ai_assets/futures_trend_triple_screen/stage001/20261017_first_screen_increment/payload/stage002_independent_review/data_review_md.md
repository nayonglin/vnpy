# Stage002 追加分钟数据与A0路径等价：独立审查

- 时间：2026-10-17 23:00 CST。
- 结论：**接受attempt2追加数据及A0已访问路径等价证明。数据门可支持固定C0_attempt2，仍须consumer冻结预检通过；不等于C0金融结果通过。**
- 范围仅为新增分钟、来源/会话/日线交叉、旧键保留和A0真实读集合；没有金融引擎运行、A0全账重跑或周缓存重算。

## 来源和新增数据

134份Stage491 completed CSV共135,604,532字节，路径和SHA均与旧A_final3 input_manifest一致。对应日线来源和主力映射SHA同样匹配旧接受输入。Stage448的零量forming快照不在这134源中，没有按候选PnL挑选源或日期。

原数据build因首AP005原日线CSV缺失中止，其失败目录完整保留。新attempt2仅对精确CSV不存在的16个合同使用原同SHA SQLite，只读按symbol/exchange/interval=d及研究日期提取原合约日线，openOI保留unknown；有CSV的118个合同仍优先原CSV并逐SHA校验。审查源码确认数据库没有改写，也没有由分钟聚合反向伪造日线。事实上16份SQLite来源的502个候选session全部隔离，**本次全部新增分钟来自CSV日线核验的117个合同**，没有任何SQLite fallback会话进入overlay。

总4390个候选session中接受3509、隔离881（425不完整、454日线聚合不符、2处原base重叠冲突）。140个接受session没有新增键，独立审查不重复核验其旧数据。其余3369个实际添键session均由独立会话网格构造复核，合并原base重叠片段后的完整grid、唯一键及OHLCVOI合法性通过；7字段日线聚合最大绝差0。1,078,530行overlay逐行通过source_id、原CSV物理行号和7个值绑定，无合成/填充价格。

2处重叠冲突为`fu2209.SHFE`的2022-05-31和2022-06-01，整session隔离；881个隔离session与overlay的session集合交集0，保守隔离没有被合并器悄悄补入。

目标`rb2010.SHFE / 2020-05-18`完整345分钟，物理范围2020-05-15 21:00至2020-05-18 14:59，base原0行、overlay添345行。日线开高低收为3469/3544/3455/3528，量1,869,234，首OI1,568,331、尾OI1,473,769，7字段精确一致。

## 原base保留与A0等价

独立验证原base共1,411,116键，SHA仍`5c06124f…9189`。overlay键唯一，与base键交集0，所有新增仅为原缺失键。原loader返回值的已有列和值不被赋新值；排序/时间规范化沿既有读取语义进行。

独立按真实calendar和已冻结会话合同重建A0_attempt2全部535个canonical anchor及501次实际扫描后缀，得到106,731个不同读取键。所有键都在原base中，新增分钟与anchor、扫描集合交集分别0/0。扫描期望/实际count与原记录一致；因此原A0在这些确定性消费者下看见的价格、时序与完整度均不变，可复用其已验收金融结果，**该结论是路径等价证明，不冒称A0在新数据集重新回放**。

原s901 canonical开盘anchor和entry_session扫描只从相应合同及确切会话分钟取价格。临时research wrapper仅追加到原loader结果，拒绝任何原key重叠，离开scope恢复loader及s901三个缓存；原`_run_live_c9`的finally恢复s827分钟全局。该调用链没有新增价格来源优先级、阈值或策略规则。

## 冻结时序和限制

构建时协议原字节以`protocol_used.md`保留，SHA`a28e2493…64c8`与summary/source_manifest相同。SQLite来源说明是在构建后追加到当前协议，amendment_receipt明确标注after_build并保留当前SHA，没有倒签。原数据、模型和builder期间未变；此文档澄清不作为alpha结果证据。

独立数据检查文件SHA为`2c57a48e5d0dd4d44d885af4da87266a3c7b5bc389360bcd31a942d000911e27`。下一步consumer预检应记录该审查、summary、overlay、source_manifest、builder及实际runner SHA，严格分钟门继续保留。此次覆盖不保证所有C0潜在session齐全，后续若再缺数据，应按合同停止逐缺口循环，不输出未完成业绩。

过拟合判断：本次未按收益选价格或规则，新增选参型过拟合为否；既有源覆盖的选择性和历史研究偏差仍在。继续价值：有，已证明新增数据不会改变固定A0，可以对同一C0假说再做合同内唯一一次严格尝试；没有理由扫参数或放宽数据门。生产资格仍false。

机器证据见`overlay_independent_checks.json`；复核工具为本线`tools/stage001_independent_review.py --overlay .../stage002_local_minute_overlay/attempt2`。本次按根明确限定不联网，依据已接受本地源及前轮官方文档/源码调研继续核验。
