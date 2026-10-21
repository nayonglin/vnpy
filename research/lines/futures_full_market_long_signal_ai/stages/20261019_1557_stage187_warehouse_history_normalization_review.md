# Stage187：全历史仓单规范化与固定投影独立审查

时间：2026-10-19 15:57 CST；line_id=`futures_full_market_long_signal_ai`。先读 registry、183 design、184 ruling、185 decision，继承181已接受的归档闭包。本阶段只改自己的187工具、测试、输出与本唯一stage；不改LINE/registry、186/188作者代码、overlay、原文、模型或金融参数。非重要alpha突破。

**规范化与投影两阶段独审均接受，C/I/M各为0/0/0，errors均为空。** 接受的是固定条件声明scope的表示、解析、算术、缺失、映射与身份投影；物理单位、代码类型、货物相互独立、历史首次公开及训练/金融资格仍未认证。完整目标未完成。

## 事前静审与有限修正

完整静读186冻结源、已有9个本次fixture及63项精确overlay，不重跑作者suite。absent/null/empty/blank/literal均分别保留；三JSON行keyset、HTML物理table及header/span原身份分别保留；不倒填VARID/WHTYPE，不因后来的HTML显式单位反推旧WGHTUNIT。

scope须具备唯一原plain total、完整非重复源leaf、有限非负数量和精确leaf-total相等。每个坏组仍required；同一数量rowspan原点只计一次且覆盖包含全部地点context；多个或缺失普通总计不挑第一/最后，不按数值凑组。区域/税类汇总不作为leaf重复加总；此源行条件不认证税别叶分配、物理货物partition或厂库码释义。覆盖hash不含数量、日期、行序号或结果；mapping是完整原label逐字、限定格式/时期的独立overlay，原字段不被映射覆盖。report未归属scope及坏required scope按冻结规则阻止相应完整product资格，未以坏组剔除后平均提高覆盖。

另静检最终writer依赖的185/180/178小schema：`plan.input_metadata.calendar`真实存在并为052完整5587日日历binding；186的`calender`是明确API拼写，188已沿用。未重复root已做的五字段action域预检。

188实际前发现一个确定接口阻断：两处读取`row['date']`，186真实载体是`request_date`。一次反馈root/作者后，仅将两loop改为真实字段，无fallback、不改186或科学规则；作者fixture改真实schema，先7个KeyError RED，修后原9个GREEN（0.241s）。这里只核最小diff及新SHA，未再重复整份静审或运行该suite。最终188只有一次actual。

187自己的两个phase各增加1个有界故障反例：规范化审查器拒绝把`0.100000000000000005`篡改为`0.1`；投影审查器以真实`request_date`和既定日历验证D−1/D−2报告及D+1预定入场。分别先观察缺实现FAIL，再GREEN；不是把作者同一9项再跑一次。无旧suite/wholebranch/回测。

## 规范化唯一独审

186根唯一actual：session29885，completed/exit0，110.936738s；subject manifest为6021B、SHA `6883b09d949c4a8d4c8679f6f181d67d6b6e83a1c1d18617318b5021b9879f3d`。root发终态后，187唯一session45887实际exit0，receipt计时**90.953637500s**，无失败、重试或重规范化。

187对四个新gzip各一次流读，在同一压缩字节流计算SHA/bytes；每个报告内独立复建全部原字段状态、严格Decimal、HTML grid/origin、角色、scope、叶数量去重与和、coverage hash、映射、required membership、98产品日状态及summary。未import186或173作者计算函数。

事前固定6份机械raw锚点：**20140519、20231117、20240321、20251124、20251205、20260724**，分别取181已识别的三JSON row-keyset和三新HTML header结构组首日；名单不依据数量、可用率或收益。六body各读一次并核SHA/bytes，JSON逐原对象、HTML用独立stdlib parser逐物理table/tr/cell与规范输出比对。其余3,012份body本次不打开、不做全raw二扫；其字节完整性继承accepted181，原文提取正确性由冻结源码/有限fixture及六锚点约束。全输出行上的保真字段及算术均独立重算，抽样原文不能升级成未抽样原文字段的第二次全量逐字核验。

| 核验项目 | 结果 |
| --- | ---: |
| 完整原报告 | 3,018：2,798 JSON＋220 HTML |
| 原物理行 | 1,033,479 |
| 数量及官方delta字段 | 2,066,958 |
| 原scope | 63,417 |
| 条件源scope / unknown scope | 49,414 / 14,003 |
| 完整98×3018产品日状态 | 295,764 |
| 原leaf / subtotal / tax_total / plain_total行 | 779,160 / 171,865 / 14,070 / 53,314 |
| intro / column_header / section_header行 | 440 / 7,315 / 7,315 |
| raw锚点 / 其余raw读取 | 6 / 0 |

quantity状态：numeric 578,145、numeric_zero 440,264、missing_field 440、parse_failure 14,630；official_delta分别193,355、825,054、440、14,630。每field的14,630 parse_failure来自7,315列标题＋7,315单位/品名section元数据，未把这些填成0；所有原行均保留。

scope原因计数：`nonunique_plain_total`及`leaf_total_arithmetic_unknown`各10,103，`research_mapping_unknown`为4,107；原因可以在同一scope重叠，不能相加当作unknown scope总数。不唯一包括缺失或多个普通总计，未为可用率修词典、拆scope或重跑。

全产品日/年状态summary独核一致：2016—2019及2026没有任何`conditional_all_required_scopes_qualified`。其余年份的条件产品日数为2014 1,550、2015 550、2020 1,012、2021 3,645、2022 3,745、2023 3,971、2024 4,356、2025 3,662。原行存在不等于product可构成完整比较；不由归档齐全推断每年均有可用仓单特征。

规范化小收据schema=`stage187_registration_normalization_review_v1`，`accepted=true`、C/I/M均0，`normalization_manifest`完整绑定同一186实际manifest；该接口已被root接受并供188实际准入，不是root布尔值替代独审。

## 投影唯一独审

188根唯一actual：session87042，completed/exit0，80.188311s；最终源码仅有上述实际前接口修正。manifest12249B，SHA `800f0b1a884b3968756d9a5c4e4cbe878af7794e09bd5523418bcf8c72b718b8`。root终态后，187唯一session37934实际exit0，**58.027988833s**，无重投影、raw读取或金融计算。

独立复算每个scope的`(Qv−Qw)/(Qv+Qw)`；仅双明确0取0，有限非负原量用Decimal50位上下文，所有required scope相同且每个比较对合格，才等权平均。任一scope缺失/坏/覆盖或表示变化使整个product missing；不取交集、不回看最近成功、不前填、不合单位原量、不以官方delta替代Qv/Qw。全分量及F字符串精确一致，无放宽容差。

完整052绑定5587日日历：原129的u_date/u_index保持原身份，解释为D决策；预定entry为D+1，v=D−1、w=D−2。逐行核索引/日期，不把延期实际成交用作特征时钟，不跨JSON/HTML/表示版本连接。

| 全域核验 | 结果 |
| --- | ---: |
| 原母行 / 原action行 | 399,252 / 1,552,456 |
| 2020+原母行 | 161,014 |
| product / family / 交易所 | 98 / 95 / 6 |
| 无action母行保留 | 186,400 |
| product pair / scope component行 | 399,350 / 26,121 |
| known母行 / known action行 | 22,270 / 230,490 |
| 普通/F alias、raw读取、旧大CSV通用hash | 0 / 0 / 0 |

原129只流读明确identity列；不读取标签或价格列、不重新hash旧334MB大CSV，继承精确root授权/accepted129输入闭包并核其size/stat未变。新投影全母/子identity、F、feature_state、原anchor及父子关系逐行对照；完整无子母体、普通/F原身份、所有scope pair、完整含零product/year coverage及mother/action closure表均核，不缩成有源小宇宙。新输出SHA在同一次流读内核对。source、完整identity/F、pair math均有durable checkpoint，无自动retry。

母identity SHA为`cdbab5e86de77f68167a546256b589ec7607ec2299cf54eec2af9fb01cf27f2c`；action identity SHA为`eeb545eeb1527351f4a5f8e16fdbd6ed47b9094e06139b898a99ed048df656b0`。

product pair状态全核：known22,270；unknown_no_product_status103,684；unknown_incomplete_scope_membership267,304；unknown_bad_required_scope5,900；unknown_required_scope_pair157；unknown_required_scope_set_changed_or_empty35。缺失不等于数量0或not_applicable；无新推断NA清单。

按原D年份，known母行：2014 1,519、2015 558、2020 976、2021 3,616、2022 3,729、2023 3,921、2024 4,296、2025 3,655；**2010—2013、2016—2019及2026均为0**，原母行仍完整保留。2020+ known母共20,193。报告日norm状态与决策日F计数因固定lag、相邻对及覆盖条件不同，不要求相同。多个合约child共享product-D信息，230,490 known action不是同数独立经济观察。

投影小收据schema=`stage187_registration_projection_review_v1`，accepted及C/I/M同义；精确绑定`projection_manifest`、`normalization_manifest`、`normalization_review`，给后续准入提供同一输入闭包。它没有签发fit/cash授权，也不证明未来六fold训练支持或盈利。

## 交付及哈希

下表路径均相对于本研究线，SHA256为完整值；两张accepted receipt在签发后不再改。

| 文件 | bytes | SHA256 |
| --- | ---: | --- |
| tools/stage186_warehouse_history_normalize.py | 29,692 | 45525e8500449f2b087dd94d227760bf94b344ab47303257a9adf2fe87cbfa02 |
| tools/test_stage186_warehouse_history_normalize.py | 11,955 | ae38d66cd3dabd4b00d84f2bade47e8926cf27ca3fe04219048ba645442cf5f6 |
| outputs/stage186_warehouse_history_normalize/product_overlay.json | 50,599 | 4728d646bd949bee21f5a4f8f48e9e898bc25070a0065c628b390304d31c4676 |
| tools/stage187_warehouse_history_normalization_review.py | 32,253 | 3cb977f2d831b082200012beb9a4a14ea8827bcbc9308abcce222b9296623b3b |
| tools/test_stage187_warehouse_history_normalization_review.py | 1,123 | 3a76e6a4faa25f2bcff7602280d8d82a175c5841d93622d22f09f8a2dfaccd79 |
| outputs/stage187_warehouse_history_normalization_review/normalization/receipt.json | 5,863 | 82297d194aebab490ea8254d03d5a18e49b1425b0be51a5030a34c72cd5f6802 |
| normalization/input_closure_checkpoint.json（同上187输出根） | 998 | 8f62d17bd648dd4f0b922bfb24c09f0acdaa9081fa8f7077c2b01e5c0fcc0890 |
| normalization/output_rows_checkpoint.json（同上） | 3,697 | 230d7c2bd4ada66548fc2c94266a6fe9d9e1572929d5d46e514c373df20500e1 |
| tools/stage188_registration_projection.py | 27,063 | bd3da6e25b4d4b445b4b3ecb7ca78eb03411d0cebe6a86c993b3c0de50593d71 |
| tools/test_stage188_registration_projection.py | 11,997 | 3fbebe9019cf6eba4feb60fcb15bd99f68d146ec1a2dd7d66ec061e8148d413e |
| tools/stage187_registration_projection_review.py | 20,711 | 9655ab3807487d131b808f80d430710b1f8f09dc369e0d1bb6daa58f56b18f1b |
| tools/test_stage187_registration_projection_review.py | 1,533 | b11b69e5ef5bdfc053a81eb1ed8baf63c50a1ba0a6f3ec54728f474f7d53624c |
| outputs/stage187_warehouse_history_normalization_review/projection/receipt.json | 16,208 | d8f0fe974662f85de34975e197e4531b472f9ab12fee0aa72a7a8ad1cdc5cc82 |
| projection/source_closure_checkpoint.json（同上187输出根） | 3,236 | 97d8b911f11a8b1a715558e9adf2da477569f206dee2aa3dd6ec5fc304a0a90e |
| projection/identity_F_checkpoint.json（同上） | 300 | bdb2d37dd3e75a982807ffc2a02006847e850371fcc1edc5ebb24b129a4740f3 |
| projection/pair_math_checkpoint.json（同上） | 681 | 0a37eccec501ab23ff2dedbba6bf9a80005f33e580466f299b6266d73f5e2587 |

两次actual的完整CLI载体由上面工具的`--manifest`、`--manifest-sha256`、`--output`三参数唯一确定：186 subject指向其actual_run1 manifest/6883…，输出187/normalization；188 subject指向其actual_run1 manifest/800f…，输出187/projection。根已分别在终态后授权，不重新执行这些命令。

## 科学边界与反思

来源调研继承183/185及已读官方入口/维护者实现，本轮按固定权限0网络，不重复旧码字典工程。不采用维护者静默numeric coercion、固定合计位置或今日近似名称拼scope。旧WGHTUNIT/WHTYPE token及未披露状态保真；同token、源行不重叠和算术吻合仍不能证明十年同一物理规格/尺度、不同标签货物独立或首次发布未修订。metadata/overlay是回顾研究身份依据，不能倒签原VARID披露。

条件标量只表示各声明登记口径相对变化的等权pooling，非总物理库存变化、社会供需、最终客户持仓或聪明钱。报告发布/修订假设仍须诚实标strictPIT=false，不能靠增加lag伪装认证。本次接受不绕过后续全六fold成熟支持预检；若不支持，保持0fit/0cash并如实no-go，不为覆盖率修overlay、分scope/品种/年份救参。全六所母域保留不代表全六所均有此信息。

开始及结束新增结果调参过拟合判断均为**否**：没有读取新金融结果或优化标量、方向、窗口、模型、K、止损、风险和参数；原长期择题、部分覆盖及归档修订风险仍在。继续**按已固定门做有限信息增量判别有价值**，重抓已齐源、全raw再审、旧字典漫游或为可用率拼组无价值；是否有alpha由后续独立实验反证，不由C/I/M为0代替。

本阶段新增/修改/删除策略参数与金融结果均无；新增fit/cash/SQL/network/价格/标签为0，累计仍409fit/218cash。期末权益、总收益、最大回撤、Sharpe、滑点、交易数、胜率均N/A，不能填0或旧成绩。未修改正式版、生产、资金或委托；完整目标和加注/晋级资格未达成。
