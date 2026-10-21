# Stage602：既存WASDE美国玉米Production同作物年修订的有界源内容核查

- 时间：2026-10-21 07:56（Asia/Shanghai）；line_id `futures_full_market_long_signal_ai`。先读registry，仍为独立全市场98/95研究线，不修改正式C9、LINE或registry。
- 重要突破：否。完成有限源内容可行性，尚未完成训练、日历连接或金融验证。累计仍547fit/286完成cash及1旧partial。
- 结论：**官方版本语义＋160个排除已知V2的同MY相邻月双Proj配对，足以支持下一次单项、收益前冻结的科学协议设计；本轮不授权fit/cash。** 不能因ZIP后来打包而把全部历史永久否决，也不能把160pair视为160个独立同分布样本或获利证据。

## 已定位文件和一次读取边界

58件实际是273的2汇总ZIP＋45月CSV，以及281的11月CSV；278无成功件。不是58份逐期TXT/PDF。两个raw目录为 `outputs/stage273_wasde_raw_source/actual_run1/raw/` 和 `outputs/stage281_original_host_wasde_source/actual_run1/raw/`。每件精确原路径、URL、字节、原下载SHA、Last-Modified/ETag、ZIP成员见 `source_inventory.json`。原下载SHA沿既存manifest引用，**没有重新hash全部raw**，也未认证当时HTTP首见。

一次临时只读脚本 `/private/tmp/stage602_observe_existing_wasde.py` 对58个CSV/member流各扫一次，2.181887秒，898541原数据行；只留549个目标Production原单元格及小报告/配对观察。随后补充统计仅读本轮观察JSON，不重读raw。不安装依赖、不新增长期提取器、不写可训练输入；0网络/SQL/native缓存/COMMON/动作大表读取、0fit/0cash。

精确实体是 `U.S. Feed Grain and Corn Supply and Use` / `Corn` / `United States` / `Production` / `Annual` / ReliabilityProjection空。549格单位全为Million Bushels；每份3个MY，183格Proj.、183格Est.、183格空flag。只用ForecastYear/Month等于该份明确ReleaseDate年月的当前列，不拿当份旧月回顾列冒充上期。183个不同WASDE报告/发布月，跨度2010-04-09—2026-10-09；0坏值/NA/重复目标格/单位冲突。

原16字段、Value列11和完整原单元位置保存在 `us_corn_production_cells.json`，ZIP成员/1起数据行号/含表头物理行末均保留。CSV观察视图内evidence列空白只是没有嵌套JSON；精确定位以该JSON及 `calendar_month_pair_observations.json` 为准，不为排版重扫源。

## 配对与真实支持

2010Apr—2026Oct共199月槽：162个相邻自然月、最新共同MY且双方均Proj的内容pair；16个当月原源未见、4个前月源未见后的首回归月、1个起始月；另16个5月新MY首现时旧MY转Est，不能拼接。NA/不明值0。缺源只描述58件内观察，不自动声称当月报告不存在：例如2013Oct旧280已核为官方取消，其他缺源原因仍依旧证据，不跨月借值。

- 162内容pair：零70、正45、负47，17个MY（2010/11—2026/27）。
- 2026May/Jun原文件显式V2而更正known_at未知，影响Jun/Jul两个pair；May本来就是MY换年无pair。排除后**160个条件配对：零69、正44、负47；非零91，仍17MY**。
- 截至2020之前：102pair（排V2仍102），零43/正24/负35，10MY。
- 2020—22：33pair（仍33），零15/正9/负9，4MY。
- 2023至今：27内容pair，排V225；零11/正11/负3，仅14非零，5MY。2025全年0pair；不能宣称后段覆盖完整或用2026替代2025。
- 按当前发布自然月Jan—Dec，内容/排V2数量：13/13、13/13、15/15、15/15、0/0、16/15、16/15、16/16、16/16、15/15、13/13、14/14。5月为事前双Proj规则导致结构性无pair，不修成0；已配对的零修订才是真0。

|发布年|内容pair|排V2条件pair|
|---|---:|---:|
|2010|7|7|
|2011|11|11|
|2012|11|11|
|2013|9|9|
|2014|11|11|
|2015|11|11|
|2016|11|11|
|2017|11|11|
|2018|11|11|
|2019|9|9|
|2020|11|11|
|2021|11|11|
|2022|11|11|
|2023|9|9|
|2024|9|9|
|2025|0|0|
|2026|9|7|

逐MY/逐年/逐月方向及完整月份状态见 `support_observations.json` 与199月grid。相邻pair共享一份报告，且同MY连续预测高度相关；17MY比每日/每合约复制行数更接近独立支持边界。上列时间片按当前release年，只是源覆盖诊断，尚无决策u年或训练fold统计。

## 原格锚点和版本判断

- 2010Apr：2009/10 Proj Production 13131.00，首ZIP成员 `oce-wasde-report-data-2010-04-to-2015-12.csv` 数据row747/物理line748/Value列11；2010May旧MY变Est13110.00，新2010/11 Proj13370.00，故不把两者配为一个预测修订。2010Jun同2010/11 Proj13370.00与May内容可配，真实零修订。
- 2016Jan：2015/16 Proj13601.00，第二ZIP成员数据row822/line823/列11。
- 2021Jan：2020/21 Proj14182，月CSV数据row543/line544/列11。
- 2026Sep/Oct：2026/27 Proj15800.00/16034.00，两个独立月CSV各数据row813/line814/列11；与601已实读的两份原TXT数值一致。只是固定末段双锚点吻合，不扩称所有历史原出版物已逐份核过。

Root本轮实际读[USDA历史数据页](https://www.usda.gov/historical-wasde-report-data-3)Note to Users（root定位391—394行）：官方说明档案保存各份报告当时的数据，不混其后底层序列修订，且单份出版物为官方记录。故后出汇总ZIP可以支持**条件vintage重建**，不能仅因2021 Last-Modified就全判未来回填。此官方语义记录见 `external_vintage_semantics.json`；602未重复请求。

相应边界仍在：档案hash/无V2后缀不独自证明每份历史v1首发字节未改；明确V2更正时刻未知就不用；原Report/Release年月和Forecast当前列仍须核。summary的PITcertified=0仅指历史首发字节未逐份证，不是160条件支持=0，更不是永久金融NO_GO。当前financial_ready=false主要因为尚无新科学协议、DCE.C限定作用范围与因果日历连接授权；不能据此新建全市场宏观门禁。沿601已有时钟草案仍为真实发布日+2自然日纽约00时（DST），未构造join或偷偷使用公告前夜盘。

## 变更、判断和下一步

新增只有本唯一阶段和本轮源观察JSON/CSV；新增/修改/删除策略参数0，新增/修改/删除历史金融结果0；权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率、CI均N/A。没有修源、补洞、carry或选择方向。

调研判断沿601真实官方归档/维护者源码核验，并补入root本轮官方Note to Users；不重复下载。新对象是已固定US Corn Production同MY原预测修订，区别已关闭World Corn库存/消费level包；修订仍非相对市场共识surprise，不证明独立因果或alpha。

开始/结束新增收益调参过拟合：否，字段、MY/双Proj/相邻月规则均先定，0收益回看；长期同史547/286适应性择题风险仍高。继续价值：**值得一次单项协议设计**，160条件pair/17MY且有91非零支持，但2023+只有14非零、政策传导及共因仍需反证。不值得扩作物/改NA/借Est/扫lag/放大系数救分；不能因本源内容通过而直接开训练或加仓。由root决定下一冻结实验，全98/95缺失原A fallback原则保持。
