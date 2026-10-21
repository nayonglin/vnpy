# Stage173 仓单七日报离线规范化实现

时间：2026-10-19 03:03 CST；line_id `futures_full_market_long_signal_ai`。先读registry/LINE、171与172冻结协议。仅新增本stage、`tools/stage173_warehouse_normalize.py`、专属test；不改LINE、registry、172、原文或金融资产。当前只实现/合成fixture，**未启动全七日离线actual**；0新fit/cash/SQL/标签/价格/网络/依赖安装，累计409 fit / 218 cash，金融指标均N/A，非重要突破。

源沿172唯一公开取源：七日20251113/14/17/18/19/20/21，前3JSON、后4HTML。172 protocol SHA `7359cd6fbd9d1bbf65d30dd89b8b4b2d7da4d49463de2018d737814a39b17b00`；root通知取源完成7/7 HTTP200、845130 B，manifest5362 B、SHA `1460d64762d6e90822aeb7bca3a96299574df3e149721c6548debc08b8c7f545`。本实现硬绑二者，只沿其七个原文件和response绑定读取，不glob补源、重试或联网。

## 有限schema认识及实现边界

本执行者仅看11/13JSON前2600＋末1100 B、11/18HTML前12500 B，共两个日期有限片段；没有先全七日解析一遍。174独立原文审查补充了厂库/地区列反转、黄金合并地点、厂库提货地rowspan及SC特殊列名等结构认识，不冒称173实际全表结果。

旧JSON每个o_cursor原行完整保留，含双语 `VARNAME/REGNAME/WHABBRNAME`、VARID、WGHTUNIT、WHTYPE、ROWSTATUS、WHROWS、WRTWGHTS/WRTCHANGE及其他原key。WGHTUNIT 1/2/3、WHTYPE 1/2不是缺字段，但**无codebook、无显式物理单位映射**，保存code_unmapped；不从新HTML吨/千克/桶、惯例或合约乘数倒填。产品名明确“厂库”可作文本观察，代码本身不被强签语义。原中文显示值只是保留双语raw之外的display，不强行合并产品/类型。

HTML仅标准库HTMLParser，不执行脚本/AKShare。每table每物理tr/td/th、原text/attrs/rowspan/colspan/源位置及展开grid都保留；以真实header名字定位，能处理地区/厂库交换。q显式列alias仅 `期货/本日数量`，地点仅 `厂库/仓库/交割仓库`，并保留quantity_field_name/location_field_name/delta_field_name。SC没有增减列就missing_field，不用“本日−上日”替官方增减。

合并region/location保留merged unknown；region跨度只传上下文。quantity/delta各存origin，继承的同一原数值cell不计成多个leaf数量，提货地点物理行仍都保留。不同数值原点却完全重复leaf身份会标unknown_duplicate_leaf，不删行修数。所有header/intro/section/unknown行也保留，不把它们当交易样本。

Decimal严格区分missing_field/null/blank/placeholder(--等)/numeric_zero/numeric/parse_failure；只接受严格十进制或严格千分组格式，原值/类型/解析方法和值字符串同时保留，不round、不silent coercion、失败不填0。数量与官方delta分开，delta可为负。原合计/小计/总计/保税/完税行单独分层；不把汇总加进leaf，也不强求每产品必须有plain总计。

保税/完税逐leaf口径并未由名称穷尽：未写“保税”不自动判完税。分税总计本身保留未知leaf覆盖；若有显式保税+完税+plain总计，可另做汇总等式诊断。FU保税总计与总计不叠加作leaf。

## 输出API与算术资格

root指定fresh输出目录 `outputs/stage173_warehouse_normalize/<run>/`，预定：

- `normalized_rows.jsonl.gz`：逐原JSONrow/HTML物理tr，source_row为report内0-based，table_index/table_row；request_date、source_format、product raw/display/code、storage type raw/code状态/文本kind、unit raw/value/state、region/warehouse、rowstatus/row_level/aggregate_label、context。quantity/official_delta嵌套含raw/raw_type/state/value(精确Decimal字符串或null)/method；真实列名及origin/inherited标记。JSON raw_fields全存，HTML raw_cells/logical_grid含全部span与来源。实际CLI再加report_date_state/source_url/version。
- `report_schema.json`：每日报告request与正文日期状态、JSON全部top metadata或HTML全部headers/intro/table信息，以及raw/response binding和完整HTTP/获取元数据。archive update/print、HTTP与当时首次公开分开，first-publication PIT=false。
- `intra_checks.jsonl.gz`：每显式aggregate按quantity/official_delta核leaf唯一原数值cell之和，subtotal限定地区，plain总计与分税汇总独立。status为资格状态，arithmetic_status单列纯数值match/mismatch/unknown；old code组basis=`raw_code_only_not_physical_unit_certification`，即使算术闭合，primary仍unknown_unit，不认证物理单位/类型。
- `adjacent_checks.jsonl.gz`：只相邻冻结源日、同scope、完整leaf context覆盖不变时核当前官方delta与原量差。格式/单位raw/type/scope或覆盖变化unknown_coverage；无明确单位primary unknown，允许单独raw-code算术诊断。官方delta原值永不替换，缺前日/缺列不fill0。
- `summary.json/started.json/terminal.json/manifest.json`：完整行/品种/表/数值/单位/层级/检查状态、输入与源码身份、0金融预算及失败终态。无自动retry、无新增金融资格。

scope_key为canonical `[format,product_raw,product_code_raw,storage_type_raw,unit_raw]`；不跨格式强制物理join。新增格式/口径未识别仍以原行和unknown保留，不扩历史规则库或新URL。174已收到具体字段API，后续只独立核全新输出，不由本stage签accepted。

## 有限验证与交root冻结

初始6个fixture先RED后GREEN；root指出SC显式别名未覆盖，新增三列SC fixture先RED（原0 leaf），最小alias修后GREEN。最终专属命令 `.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p test_stage173_warehouse_normalize.py -v`：**7/7通过，0.002秒**，未跑旧suite或真实7日。

七项保护：Decimal缺失/0/横杠/非法分型；反转header及数量rowspan不重复；JSON代码unknown/原行/日期分开；subtotal与保税/完税不叠加leaf；相邻单位/coverage不明保持unknown；重复leaf与不强制总计；SC本日数量/交割仓库显式alias及缺增减不补0。

交root静读字节：实现25747 B、SHA256 `350d74fb8373aaa9bd2b980db7c0051efedfd0754225194ff5671ac2972e1db2`；测试7273 B、SHA `6a4b31b8542b349e82acd1818160df6c13e3c39fd73ac761c500faebed87360e`。根唯一离线CLI（本agent尚未执行）：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage173_warehouse_normalize.py --raw-manifest research/lines/futures_full_market_long_signal_ai/outputs/stage172_warehouse_pilot_raw/actual_run1/manifest.json --output research/lines/futures_full_market_long_signal_ai/outputs/stage173_warehouse_normalize/actual_run1`。已有目录拒绝覆盖，失败留终态；等待root锁源/启动，不自行全七日解析或重跑。

开始/结束新增收益后调参过拟合：**否，本轮只做事前固定source pilot规范化，未看收益选品种/日期/单位**；长期同史择题风险仍有。继续价值：**是，限root一次全七日解析及174独审**；单位代码、类型、coverage与首发时钟缺口不因算术相等消失。没有新特征/标签/模型/现金或大历史下载，完整long目标尚未达成，不加注。
