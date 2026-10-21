# Stage111 类别持仓唯一gross比例投影：实现冻结，0actual

- line_id：futures_full_market_long_signal_ai；2026-10-18 19:49 CST；重要突破：否。当前目标为六所全市场全部品种long-only质量、窄损与成本后收益/回撤改善；不涉及正式版、CTP或其他线。
- 已读取registry/LINE确认本线，因而已见登记的旧停止结论和109运行状态；也已知此前研究上下文，不能称全盲。本实现未poll 109 session、读取其新增来源数值或金融成绩。
- 新增actual projection/SQL/fit/cash/label/download均0；累计沿110前361研究fit/94现金。111/112实施已授权，actual另等root精确绑定。

## 合同与来源判断

只落实110已冻结的官方SHFE来源与类别语义；没有重新探源、下载、调用原生SQL或检查大库。109在做独立单遍来源获取，只有其终态和root源接受均到位才允许111 actual。官方历史归档加完整source日lag仅为研究假设，不证明历史首发、无修订PIT、全部月份覆盖或固定参与者人群。

唯一scalar为`(LN−SN)/(LN+SN+LF+SF)`；107 own-ratio未实测，本次不实现、不预留第二臂或结果后替换路径。四量必须来自同表同scope、两类两侧平衡；不使用外部OI，不推断聪明资金方向，也不把类别净额解释为市场净需求。

## 新实现

新增`tools/stage111_member_category_projection.py`与对应6项合成fixture。源脚本只pure import已接受071序列化/身份工具，不运行旧actual。真实执行四参数为output、protocol-sha256、authorization、authorization-sha256；固定110 SHA与1560B implementation_clarifications SHA均硬绑定。每phase要求新目录，不自动重试。

111实际将读取109 date_manifest精确指向的本地raw archive或13份精确复用原响应，核原字节binding后恢复完整o_cursor。不能从仅保留类别行的normalized猜测整份报告披露的真实contract全集。新日期须HTTP200、未截断、无transport error；HTML/缺日/未请求等状态保留missing；报告日期有值必须等于请求日，旧无报告日期单独标识。

精确识别110两套ABBR三列一致的label pair与FC=-1/NFC=0；保存原文、strip后文、rank、四量原值/type/null/精确整数与population_version。不因普通正排名会员名字含“期货公司”而误判类别。成交量/变化列只属来源QA，缺失不抹除合法四L/S。

每product/day存在all时，必须唯一且完整两类all；只使用all，其他contract保留QA而不重计。all残缺不回退。无all时，对整份报告披露的该product全部真实contract逐个核完整类别对；任一缺对、冲突或不平衡，整体missing，不用剩余子集。先sum四原量，再算一个比例。真实gross0给observed=1/scalar0；缺量不能变0。

对399252完整母体保序保原7身份。v为4074个唯一母体u_date有序日历的紧前日；原u_index仅身份，不假定native v_index=u_index−1。不取u表、不找最近可得日、不ffill。只映射精确`SHFE.<原表字母代码大写>`；跨所同名、普通_F、其他范围均不猜。来源只覆盖SHFE不缩母体，也不按reference_epoch或ready状态筛源。

输出完整`member_category_projection.csv.gz`、3588日期的`source_day_audit.csv.gz`、带原始scope/四量/类别版本/contract全集的`product_scope_audit.csv.gz`，并以manifest绑定109终态、date_manifest、root接受、clarification、母体和所有源码。projection使用真实`observed_archive_member_categories_lag1`，没有借用同epoch OI资格。source缺失、未知类别和null保持独立状态。

## 验证和交接

111六项新fixture先RED（源缺失）后GREEN。与112两项合并最终命令：`.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p 'test_stage11[12]_member_category*.py'`；8 tests、0.788s、OK。仅内存合成表，不读109实际数据，不跑旧suite或任何金融。覆盖完整旧contract与缺对、唯一all优先与残缺不回退、真0与missing、两套label/未知label/rank/日期、严格lag缺日报与精确SHFE映射。

精确SHA、auth形状、终态/manifest schema与CLI见`outputs/stage111_member_category_projection/implementation_receipt.json`。root唯一actual runner；本作者只交付冻结实现。111 completed仅表明投影进程完结且母体完整，绝不暗示来源日期/品种齐全、可训练、可交易或盈利。

新增/修改/删除交易参数均0；新增/修改/删除回测结果均无。期末权益、总收益、最大回撤、Sharpe、滑点、交易数、胜率均N/A。无Git、LINE/registry、其他线或正式材料改动。

## 反思

新增按本包金融结果选参：否，0actual且分母/范围/lag已先冻结。历史选择和来源可得性偏差风险：是；必须披露类别版本、所覆盖scope和未知，不能以来源获取成功声称经济增益。继续价值：有，限一次检验此前COMMON之外的真实类别数量信息；来源工程本身不是目标完成，不能加注。若固定包不支持，不再扫分母、方向、窗口或缺失门救参。
