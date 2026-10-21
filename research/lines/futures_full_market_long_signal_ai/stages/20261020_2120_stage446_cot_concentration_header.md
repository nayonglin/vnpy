# Stage446：已有 COT 集中度精确字段与存储边界核验

- line_id：`futures_full_market_long_signal_ai`；执行时间 `2026-10-20 21:19 CST`，本文整理于21:20。开始前读取registry、LINE头部及Stage444范围。非重要alpha突破，只是已有来源与存储结构核验。
- Stage444 scope：`outputs/stage444_cot_concentration_scope/scope.json`，4,599 B，SHA256 `b275a60e0210f62520687f39db501418bb1bebd334272f2f9213a3db6c5db64e`。本次不另开假说，不建立解析工程，不修改原档、旧阶段、LINE、registry、模型或账户。
- 开始过拟合判断：没有本次收益择参；长期历史复用与自适应择题风险仍高，发现新列不能重置试验次数。继续价值：有限是，用低成本核验区分“原档有字段”与“当前标准输出已持有数值”，避免给旧信息改名重训。

## 实际一次运行与原档绑定

小型一次probe `tools/stage446_cot_concentration_header_once.py`，9,998 B、SHA256 `d125cd18e7ef487e3d44425c83c65bb997f93fabfa32ec0a63cb8c8f3732470a`，使用 `.py311/bin/python` 实际执行一次，exit0。没有测试suite、安装依赖或导入下载器。

仅scope绑定的 `fut_disagg_txt_2010.zip` 使用一次 `Path.read_bytes()`，以同一份bytes计算实际大小 `1,004,704 B`、SHA256 `fef4827fbaa1a2a72ad3fe7ef0ca659ee4c85bc6857fdc096f4320b8a096322b`，与scope及407的2010 schema绑定一致。`ZipFile(BytesIO(...))` 只打开唯一TXT/CSV成员 `f_year.txt`，只调用一次 `readline()`；返回5,669 B的第一行header，共191列，header SHA256 `0c6e69fe6cf2fc2d0ee4607d8850174d6e71a61cff46aa0d1f1fbf3564774c6b`。使用已绑定407 schema记录的cp1252解码，完整header与该元数据完全一致；完整原文、列数组与索引存入receipt。

本次没有消费EOF，因此**没有重新验证整成员CRC**；407已验CRC只作为旧元数据引用。压缩库内部缓冲不等于研究者读取数据行，本次没有请求或解析第二行、任何原数据行或集中度数值。

probe操作计数：原ZIP读取1、BytesIO ZipFile1、member open1、readline1、原数据行解析0、其他原ZIP读取0、mapped/canonical数据行读取0。读取绑定元数据JSON20份（scope、407三个小清单/summary、16个schema），既存parser/aggregate源码2份，probe自绑定源码1份。网络/新下载/市场API/SQL/price/Y/score/q/fit/cash/未来D/test suite均0。收据计数范围为这一次probe调用；前置只读允许的文本/代码/schema元数据，后置只读receipt及13年schema元数据解释日期列差异，均没有再次访问原ZIP或任何数值行。

## 24个精确集中度列

实际header中的列名如下，不做猜测别名、大小写转换或归一化替代。每个原始合约分组标签 `All`、`Old`、`Other` 都有8列，共 `2 gross/net × 2 最大4/8交易者 × 2 long/short × 3分组 = 24` 列。

| 统计形态 | All | Old | Other |
| --- | --- | --- | --- |
| Gross / 4 / Long | `Conc_Gross_LE_4_TDR_Long_All` | `Conc_Gross_LE_4_TDR_Long_Old` | `Conc_Gross_LE_4_TDR_Long_Other` |
| Gross / 4 / Short | `Conc_Gross_LE_4_TDR_Short_All` | `Conc_Gross_LE_4_TDR_Short_Old` | `Conc_Gross_LE_4_TDR_Short_Other` |
| Gross / 8 / Long | `Conc_Gross_LE_8_TDR_Long_All` | `Conc_Gross_LE_8_TDR_Long_Old` | `Conc_Gross_LE_8_TDR_Long_Other` |
| Gross / 8 / Short | `Conc_Gross_LE_8_TDR_Short_All` | `Conc_Gross_LE_8_TDR_Short_Old` | `Conc_Gross_LE_8_TDR_Short_Other` |
| Net / 4 / Long | `Conc_Net_LE_4_TDR_Long_All` | `Conc_Net_LE_4_TDR_Long_Old` | `Conc_Net_LE_4_TDR_Long_Other` |
| Net / 4 / Short | `Conc_Net_LE_4_TDR_Short_All` | `Conc_Net_LE_4_TDR_Short_Old` | `Conc_Net_LE_4_TDR_Short_Other` |
| Net / 8 / Long | `Conc_Net_LE_8_TDR_Long_All` | `Conc_Net_LE_8_TDR_Long_Old` | `Conc_Net_LE_8_TDR_Long_Other` |
| Net / 8 / Short | `Conc_Net_LE_8_TDR_Short_All` | `Conc_Net_LE_8_TDR_Short_Old` | `Conc_Net_LE_8_TDR_Short_Other` |

2010—2025的16份407既存schema均逐份核实际SHA/大小及source绑定，**16/16都各含上述24个精确列名一次，目标字段一致**。这不是重新打开16个原ZIP，也不证明16年数值非缺失。

完整191列header不能称字节/逐列全同：2010—2012第3列（zero-based index2）为 `Report_Date_as_MM_DD_YYYY`；2013—2025为 `Report_Date_as_YYYY-MM-DD`。后置只读对应schema，确认差异仅此日期列名，24个集中度字段没有差异；本次不读取日期或其他数据值。

## 当前407输出没有存这些数值

通过绑定源码静态核验，不打开mapped/canonical的任何数据行：

- `tools/stage407_cot_parse_year.py` SHA256 `50dfc3b465a93b08e0dbcf0238f519595290a15c80aeceb80354e18eea0464f1`。`FIELDS`仅选择身份、日期、PMPU long/short、MM long/short、OI；`numbers`只包含五个数值角色 `pmpu_long/pmpu_short/mm_long/mm_short/open_interest`。`mapped.append`（第235行）存这五个原数值token/值、H/MM、分子、OI和identity/hash，没有存全行token或集中度值。identity保留列数、原行token SHA与原ZIP/member/行号，可以回溯原件，hash不等于保留了全部数值。
- `tools/stage407_cot_source_aggregate.py` SHA256 `1567500826b18f878abc0ee05837561328100a827262e33915d36a098b964de1`。第73行 `row = dict(original[0])` 从mapped复制并增加来源/重复状态，不重新提取原ZIP字段，因此 `eight_mapped_channels_2010_2025.jsonl` canonical也未存集中度值。
- 407 schema保存完整header列名，原ZIP保存原始数据行；“列名在schema中”和“值已进入mapped/canonical”明确不同。407 summary中6,680个known H/MM值的资格不能转借给集中度。

## 外部调研、未知与结束判断

本446外部定义沿用root在Stage444先行核验的[CFTC说明](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm)与[维护者源码入口](https://github.com/NDelventhal/cot_reports)，没有再联网或调用其包。结合本次原header的判断：这是跨交易者类别的最大4/8可报告交易者集中比率，不能当作Managed Money类别、交易者身份或实时资金流。`All/Old/Other`是原始合约分组，不能把三个集中比率相加，也不能以All字段存在推断Old/Other对每个市场有效。

本次**未知且不推断**：数值非缺失、按市场/日期可用率、发布与首次可见时钟、strict PIT/vintage、与旧MM/PMPU等输入的独立信息、任何long alpha、金融或生产资格。字段精确存在仅推进到“来源header存在/已有存储边界明确”，不启动q、训练、现金或加注。

金融参数及回测结果新增/修改/删除均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。正式版/生产/CTP/订单/邮件/调度/Git均未操作。

结束过拟合判断：本次没有按新收益选字段、方向或参数，直接结果救参否；长期自适应择题风险仍在。继续价值：本次有限来源与存储核验有价值，已完成；是否读取数值或做新经济假说由root结合445血缘与机制另行裁决，不能由24列存在自动获得许可。

终态receipt：`outputs/stage446_cot_concentration_header/actual_run1/receipt.json`，54,007 B，SHA256 `5c518a54b0d79ae86afbf8e7c13bf159cd2bec496063e113a9bf82861f04dcb1`。
