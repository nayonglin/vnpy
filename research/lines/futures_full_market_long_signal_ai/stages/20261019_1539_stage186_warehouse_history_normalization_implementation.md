# Stage186 全历史仓单离线规范化实现准备

时间：2026-10-19 15:39 CST；line_id=`futures_full_market_long_signal_ai`。先读registry、183设计、184 ruling、185 root决策；rg限定本线tools找到173，仅复用其已冻结的严格Decimal/HTML span纯helper，不修改173。新增本stage、186工具/测试及独立overlay，未改LINE/registry、178—185、原文或金融代码。**本agent未启动全历史actual、下载、scalar、投影、训练或现金**；累计409 fit / 218 cash，权益/收益/DD/Sharpe/滑点/交易次数/胜率均N/A，非重要突破。

已接受的180/181事实由185继承：3018报告=3009新+9复用、完整2014-05-19—2026-10-16，combined原body234169817 B；这不是186规范化结果。185决策SHA `40787dfd0b4a8bfebe257fbcc9ea397ba982ea76ff9f60305caaab5ba7fbc017`。本轮不重复联网/GitHub调研，沿183/185已读主源与条件scope裁决；不执行维护者脚本、补字典、重下180或重审全raw。

## 有界认识与独立映射

只由180 date_manifest定位root指定的20140519、20231117、20240321、20251118、20260724五份代表原文，读取结构/字段/角色/表头，不扫描其余raw、不计算scalar或金融结果。JSON分别为11/13/10字段keyset；ROWSTATUS的0/1/2与显式明细/合计/普通及税类总计文本相配，不用排序数值恢复类型。HTML保持物理table、每次header、rowspan/colspan和数量cell原点；后期厂库/地区可倒序，SC使用交割仓库/本日数量，不能套固定列号或把缺官方增减补0。

另仅读accepted154的小epoch目录identity与已绑定metadata身份/名字，形成 **独立 `outputs/stage186_warehouse_history_normalize/product_overlay.json`**。保存全部98研究product身份、63个逐字列举的完整JSON双语label/HTML原label映射、适用格式日期段、独立目录/metadata依据、具体身份记录和研究解释限制。lookup不拆名、strip、大小写折叠、模糊匹配或去_F；raw字段不被映射覆盖。metadata是后见研究身份依据，非当时发布、旧VARID披露或物理语义恒定证明。厂库文字只作为原label，不合成WHTYPE。

没有额外可靠独立名字依据的AD/OP等例子明确留missing，不为覆盖率补泛字典。当期已披露VARID若能唯一指向既有研究identity，仅作该product存在坏required scope的阻断依据，不绕过literal overlay恢复quantity；完全无法归属、不能排除与有源product重叠的data scope才列report级unresolved。导言/表头/单位标题不是unresolved data组。未显式认证任何not_applicable产品清单，不能事后据CFFEX/EC或普通/F分类猜NA。

## 固定规范与scope资格

所有原JSON行、HTML物理tr均保留，含header/intro/section/未知/坏行；JSON保存raw_fields与原字段类型，HTML保存原cell/raw_text/attrs/grid/origin，数量和官方delta分别保留。absent/null/空串/空白/literal分开；原VARNAME完整值、WGHTUNIT、已披露VARID/WHTYPE及各presence进入原scope，缺字段NOT_DISCLOSED不冒充默认仓库/所有类型。JSON三keyset为不同representation，HTML另按完整ordered header-regime signature与原table_index保留表身份，绝不跨JSON/HTML或schema比较。

JSON原数字先用Decimal读取，避免float损失；原JSON小数在raw_fields序列化为精确十进制字符串，同时raw_field_types=`json_decimal_number`说明其原数字类型，不能误认成原字符串。quantity也保存同一raw_type标记；原整数字段保持int。原body绑定仍保留字节真值。严格解析区分missing/null/blank/0/placeholder/parse_failure，负数量unknown，官方负增减可保留，失败不填0。

原scope只有**唯一原普通总计**、所有源明细角色可识别、完整不重复leaf coverage、原量有限非负且所有leaf精确和等于该总计时，才可给`conditional_source_qualified`；原码/物理单位/类型资格仍false。税类合计、区域小计与父总计不加进leaf；多个普通总计不取第一/最后、不拆方便组、不用数值凑覆盖。HTML重复header仍属于同一原table的scope，两个无法唯一归属的总计整体unknown。quantity rowspan的同一原cell只计一次，覆盖指纹包含其全部提货/地点上下文；不同原点重复leaf身份unknown。

coverage fingerprint仅由源context、quantity列身份及共享原点的完整上下文结构生成，不含数量、收益、日期或原行序号。全部原点/源行引用另存便于独审。每个原scope，包括坏组和未映射组，required=true且完整输出；每product当日若任一required组坏、membership未证实，则整个product状态unknown，不能只平均好scope。本轮不计算183的比例、等权均值或lag特征，也不作成熟训练支持声明。

## 输出API、绑定及一次实际入口

预定fresh实际目录：`outputs/stage186_warehouse_history_normalize/actual_run1`；已有目录拒绝覆盖，失败保存terminal，不自动retry。实际仅按185已接受180 manifest/date_manifest、179/178绑定遍历3018完整有序记录；每份body只读一次并在同一内存核bytes/hash/解析，旧9份不复制、不重抓；gzip按报告流写，不把全历史原行同时装内存。只绑定新输出一次，不读129/标签/行情/数据库。

- `normalized_rows.jsonl.gz`：完整物理行、raw/presence、数量/官方delta/角色、mapping和原scope身份、origin与原表/活动header，所有坏行仍在。
- `scope_observations.jsonl.gz`：每(date,scope_id)一行，schema=`stage186_scope_observation_v1`；scope_identity/representation_version、原label、映射状态、全部源行/普通总计、原quantity_value/official_delta_value（Decimal字符串/null）、leaf_measurements、leaf_sum_quantity、quantity_arithmetic_status、leaf_coverage_fingerprint及reasons。合格coverage_state唯一为`complete_nonduplicated_source_rows`，否则unknown；status为`conditional_source_qualified`或unknown。
- `product_scope_status.jsonl.gz`：完整 **98×3018** 身份状态，product字段为`mapped_research_product_id`；required_scope_ids全部含坏组、bad_scope_ids、scope_membership_complete、unresolved_report_scope_ids。status为`conditional_all_required_scopes_qualified`、unknown、unknown_no_source_scope；没有源不当0或NA。188已确认此API，只消费规范结果，后续单scalar/全母域投影另签。
- `report_schema.jsonl.gz`：逐报告原metadata、全部表/header版本、source URL/body/response binding及归档日期状态。
- `started/summary/terminal/manifest.json`：manifest schema=`stage186_warehouse_history_normalization_manifest_v1`，顶层绑定上述4gzip、product_overlay、继承178/052的`calender`（保持既有拼写、此轮不再读calendar）、source_bundle/185/180/179/178；summary只数源状态/缺失及年/product支持，不含scalar/收益。strictPIT、物理货物独立、金融资格均false。

root唯一实际CLI（本agent未执行）：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage186_warehouse_history_normalize.py --output research/lines/futures_full_market_long_signal_ai/outputs/stage186_warehouse_history_normalize/actual_run1 --overlay research/lines/futures_full_market_long_signal_ai/outputs/stage186_warehouse_history_normalize/product_overlay.json`。root保存实际源/overlay授权，187先静审，随后root唯一actual与187独审。若未来6折没有支持，只能报告源/表示准入no-go且0fit/cash，不是金融已反证本scalar。

## 有限测试与候选冻结

9个本次合成fixture先观察RED后GREEN；高精度JSON小数另在同一Decimal case追加 `0.100000000000000005` 反例，先RED再补Decimal读取/显式原类型保存。最终专属命令 `.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p test_stage186_warehouse_history_normalize.py -v`：**9/9通过，0.004秒**，未跑旧suite或全历史规范化。

覆盖presence/三schema断点；普通总计与税/父子不重加；多总计保留unknown；重复leaf/未知角色/混单位坏组不丢；严格缺失/零/负数与小数保真；HTML多header不拆方便scope；rowspan一次计量及完整context指纹；精确overlay/适用段/无_F alias和unresolved阻断；SC特殊列与缺官方delta/原物理行保留。

最终候选：source **29692 B**，SHA256 `45525e8500449f2b087dd94d227760bf94b344ab47303257a9adf2fe87cbfa02`；test **11955 B**，SHA `ae38d66cd3dabd4b00d84f2bade47e8926cf27ca3fe04219048ba645442cf5f6`；overlay **50599 B**，SHA `4728d646bd949bee21f5a4f8f48e9e898bc25070a0065c628b390304d31c4676`。173 helper SHA `350d74fb8373aaa9bd2b980db7c0051efedfd0754225194ff5671ac2972e1db2` 不变，作为source_bundle依赖绑定。187/root已收到候选和API，源码停止修改，等待必要静审反馈/根唯一actual。

开始/结束新增过拟合：**否，此轮只忠实实现事前冻结源/表示条件，未按数量变化、scalar可得率或金融成绩调定义**；长期择题/后见目录与归档修订风险仍在。继续价值：**有，限一次全域离线规范化和独审**；unknown不能靠字典/填码/拼scope消除。未改模型、K、止损、风险、资金或正式版；完整long目标和加注资格未达成。
