# Stage407：取得2010—2025 CFTC原年包，保留全市场身份与固定八通道

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 15:04 CST汇总。开始前读registry及root冻结protocol，SHA256 `da7b46f3956ba6e571ae281f51bcd08cdf8406aa89ada83694fbba82c3e781bd`。
- **16个官方Disaggregated Futures Only Text年ZIP全部取得，160,607条原历史身份、601个原代码均保留。固定八通道835个持仓asof日×8=6,680行H/MM已抽取。** 本阶段只source/data stats，不读取Y、不训练、不跑资金，不能把持仓asof日当已确认发布事件。
- 本次是有限来源准备，非重要alpha突破；原母域98产品/95家族、其他90个unmapped产品、模型与账户均保持。

## 唯一有界批次与真实来源

[CFTC官方历史压缩索引](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm)只GET一次，实际200、81,667 B、SHA256 `c3c75556dc4e55a783798b9505cb90beaa3d3f769078ab1516c15f63ffc12d57`。原HTML表summary明确为 `Disaggregated Futures Only Reports`，Text锚点逐一给出 `fut_disagg_txt_YYYY.zip`，不从URL模板猜出未观察到的路径，不混入Legacy/TFF/Combined或Excel。

索引实际session `52776` exit0；后继单年包worker `27226`复用索引，14:57:09—14:58:48 CST执行，实际exit0。按事前year order `2010,2025,2011,…,2024`，单worker并发1、30秒、0retry/0duplicate。没有扫描整台机器或重hash旧大历史；root/406已查的已知cache状态直接沿用。408发布时钟由独立worker处理，本407没有取ReleaseSchedule/Announcements。

- 共17 GET（1索引+16ZIP）全部HTTP200，失败0；实际网络正文28,443,093 B。
- 单ZIP最大2,420,076 B，低于8MiB；source worker总量低于120MiB。每年解压声明及实际stream均在128MiB限额内，不extractall、不装SDK。
- 若403/429本应立即停止本worker新请求；实际未触发，没有代理、换host、路径阶梯或自动重试。
- 官方ZIP整份保留所有历史市场、名称、原行，不按今天存在的合约/品种过滤。所有原件/headers/status/hash在 `outputs/stage407_cot_source_years/actual_run1/raw_years/`；观察到的索引锚点独立保存在 `observed_year_anchors.json`。

## 实际字段和一次本地读取

首2010真实member为 `f_year.txt`、191列。实际header虽写 `Report_Date_as_MM_DD_YYYY`，原单元却为ISO `2010-12-28`；代码和YYMMDD带空格，如原code `001602 `、原asof `101228 `。解析保留原字符串与member/行号，只在规范副本strip，按实际明确日期值解析，不根据header名字强行换月日或要求每周二。

计算字段逐一绑定实际CSV列：

| 量 | 原列 |
| --- | --- |
| 原市场身份 | `CFTC_Contract_Market_Code`、`Market_and_Exchange_Names`及额外原identity字段 |
| 原持仓日期 | `As_of_Date_In_Form_YYMMDD`、`Report_Date_as_MM_DD_YYYY`（保留实际值格式） |
| OI | `Open_Interest_All` |
| PMPU long / short | `Prod_Merc_Positions_Long_All` / `Prod_Merc_Positions_Short_All` |
| MM long / short | `M_Money_Positions_Long_All` / `M_Money_Positions_Short_All` |

固定映射只用root事前八通道：AU088691、AG084691、CU085692、M026603、Y007601、C002602、CF033661、SR080732；代码是字符串，原alphanumeric代码和前导0均未强转整数。H=`(PMPUshort−PMPUlong)/OI`，MM=`(MMlong−MMshort)/OI`。合法已报0保留；缺失、负持仓、非正OI、日期冲突或冲突重复为unknown，不填0或隐式clip。

每年原成员仅一次完整stream解析并检查CRC；16年全通过，原ZIP不重抓。首包额外小型header观察不消费额外网络，也不冒充又一次完整解析。原各年输出保留全历史identity行及code/name/date/member/line/原tokens hash/sourceZIP；固定八通道另保留计算相关原数值token、分子、OI、H/MM和unknown原因。没有把全部191列重复抄进另一份巨型可编辑真相，完整原行仍可从原ZIP复验。

新增407 source、parser与轻量跨年aggregate工具；parser只有一个小合成ZIP检查，验证非Tuesday、合法0、负持仓/OI0/冲突重复unknown、CRC和不按生存市场筛选，不跑旧suite/旧天气/金融实验。source脚本11,509 B，SHA256 `66c4785fdd9dd5d045a918b007308ce1d3f78187006e79f5ec33defc9b950007`；parser16,737 B，SHA256 `50dfc3b465a93b08e0dbcf0238f519595290a15c80aeceb80354e18eea0464f1`。

## 原数据统计、非周二事实与跨年去重

| 年包 | 全历史身份行 | 八通道原行 | 八通道原asof日 |
| --- | ---: | ---: | ---: |
| 2010 | 5,547 | 416 | 52 |
| 2011 | 5,486 | 416 | 52 |
| 2012 | 5,938 | 424 | 53 |
| 2013 | 8,270 | 416 | 52 |
| 2014 | 10,271 | 416 | 52 |
| 2015 | 9,762 | 416 | 52 |
| 2016 | 10,520 | 416 | 52 |
| 2017 | 10,204 | 416 | 52 |
| 2018 | 10,874 | 424 | 53 |
| 2019 | 10,954 | 416 | 52 |
| 2020 | 10,786 | 416 | 52 |
| 2021 | 10,704 | 416 | 52 |
| 2022 | 11,526 | 416 | 52 |
| 2023 | 12,534 | 416 | 52 |
| 2024 | 13,601 | 424 | 53 |
| 2025 | 13,630 | 416 | 52 |

- 全身份160,607行、601个原市场code、1,061个code/name历史组合，原rename/delisted身份均保留。原asof为Monday的行有1,558，Tuesday159,049；没有把Monday改成Tuesday，也没有硬定每年52周。
- 映射日期跨度2010-01-05至2025-12-30，共835个实际持仓asof日；6,680固定通道行均有明确H/MM，缺code0、未知asof0、冲突重复0。映射原 `FutOnly_or_Combined` token6,680行均为`FutOnly`。
- 轻量aggregate只读本407的16个schema及小型mapped JSONL各一次，不重读旧大history。key为原asof+固定channel；同key多原行若原row hash不同则H/MM unknown，相同也保留所有source origins，不重复制造事件。本轮年内及跨年重复/冲突组均0。
- canonical只在实际观察到的mapped asof日期×固定8channel构造；若某code缺失会保留None而不虚构日期。本轮没有此类缺失。原年度输出不修改，另外90产品unmapped保留未知，不删出原98/95母域。

**835是持仓日期数，不是835个已证可见publication events；6,680也不是独立周数。** 2023/24/25 asof52/53/52不直接宣告held每年35可见事件门通过。实际发布、延迟、补发合并、已知修订及历史可得时钟仍由408准备、root有限裁决后才能计数，不能自动Friday+4天或根据周二反推。

## 终态物料、独审与价值边界

关键物料均在 `outputs/stage407_cot_source_years/actual_run1/`：

| 物料 | 字节 | SHA256 |
| --- | ---: | --- |
| `source_manifest.json` | 35,699 | `5aee8d98444196b7b5d7c113f6f1967a6554ae036c8b206ecda751fb20220282` |
| `parsed_years_manifest.json` | 26,379 | `36cff3496d1fc0b42f282314ebe77ffde49b8c01da76f995f13fc03c7b3d65cb` |
| `aggregate_source_summary.json` | 32,294 | `13629636dcf3b1c2bcd24ede46f489fcdeb9c319f5cc2a9b6467a2a5b14b0de2` |
| `eight_mapped_channels_2010_2025.jsonl` | 17,952,927 | `f3cceea48da6594741406511dc508d3bfc1db94e29e0ef2fe392858659babad2` |
| `all_historical_identity_index.json` | 174,622 | `536dc3851169abd42251075b1bf17f06598ddc520d51469daf1e9d3c33320e7f` |

原年份ZIP是当前从官方取回的文件，可能已含历史修订，**不是本机当年留存的strict first-seen/vintage证明**。日期和下载时间原样保留，没有强求不可得的无限首见证明，也没有因为ZIP下载成功就自动金融化。PMPU此前已在旧048计算过，本次不把旧字段重新命名成新发现；若后继有价值，只能验证其在同COMMON52+MM共同对照外的条件增量。

所有407数值/source文件已经终态，交root指定410独立一次流核16原ZIP、全identity/八通道值与边界；作者不代替独审结论。本阶段不取408发布资料、不读Y、不预判可靠周数、不开金融。若真实共同可见事件不满足407 protocol的400周及held2023/24/25各35门，按原规则0fit/0cash停止本规格，不换COT类别或扫窗口救参。

参数/结果账本：只新增407工具、输出与本文，LINE/registry/其他线/旧源/策略/模型/账户/原360-361前瞻安排均未改；Y读取0、fit0、cash0、金融partial0、行情API0、SQL0、GRIB0，CTP/订单/邮件/调度/Git0。金融参数和回测结果新增/修改/删除0；期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率N/A。

开始/结束过拟合判断：既有COT探索反馈偏差高；本次没有新收益择年/通道/字段，完整source人口取数与实际语义校验不是alpha验证。继续价值：有限是，已补齐16年原数值源并保留原身份/未知，为发布例外与条件增量资格裁决提供实物；不是因为天气规格停止就认为COT必有优势。成本后高收益、低回撤、极小止损及加注资格均未证明，完整目标未完成。
