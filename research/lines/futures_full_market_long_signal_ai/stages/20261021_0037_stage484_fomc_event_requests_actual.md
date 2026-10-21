# Stage484：一次真实FOMC公告前精确请求身份投影

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 00:37 CST。
- 当前模式：Stage483固定协议下pure metadata请求投影；非重要突破；不触发策略A/B。
- 执行：root唯一actual，session `95219`，exit0；2026-10-21 00:34:53.405049—00:35:15.766119 CST，耗时22.361070秒；无自动重试。
- 本结果记录只复核新`actual_run1/summary.json`和`input_read_receipt.json`，不读旧大源、不修改代码、不再跑测试；待Stage485独立审查。

## 外部调研与判断

沿Stage483、Stage480已完成的作者原始FOMC、作者main/mypc、BoE1114和两个Fed官方夏冬锚点判断，本阶段新增网络0。America/New_York仍只是两锚支持的条件解释；UTC+25h覆盖已知测量窗约束，但不证明385事件全表时区、首发PIT或作者/供应商当时可取得。上海15:15及冻结源日历映射均为研究重建，不认证逐历史u的未来日历发布事实。

本次有价值的产物是精确待取字段身份。它没有取得公告前真实volume、现金乘数或settlement，不把u当日字段冒充公告前字段，也不把请求构造成功当作字段source coverage或alpha证明。原FF4经济正号及跨期口径边界继续未获认证。

## 版本与参数

沿用准备stage的单文件实现及四项新合成检查；本次代码新增/修改/删除0，策略、账户、止损、训练参数新增/修改/删除0。固定协议SHA256：
`b1d88000c22701a029a1735f80ecdba64bd91801ec035a4d93a83d285066d4ed`。

原研究区间2010-01-01—2026-10-16；范围六所98产品95family。u只按该区间内的日期资格决定；不按FF4/SP500值、标签、pre支持、子行动资格或未来路径筛选。每源事件保留原ordinal+timestamp身份。pre为公告前严格最后已完成15:15源日；u为UTC+25h后首个15:15源日；D为u后原日历下一源日。有限日历不夹取、不环绕。

## 真正结果

385事件全部保留状态：`before_source_calendar=197`、`u_before_study=47`、`eligible=141`，合计385。141事件对应141个不同u，展开`13,818=141×98`全母行与54,089子请求；唯一精确`(reference_epoch,pre_date)`raw键54,089，本次实际无跨子请求重复键。

以下身份均被保留，没有因缺支持或资格删除：

- nochild母6,406；全98 roster包含无子行动或无当前观测产品。
- `u_action_eligible=0`子行动26,114。
- `pre_observed_any_epoch=0`子行动4,029。此值只披露是否在完整元数据中存在同epoch、同pre_date观测，不是价格/成交量/标签可用性认证。
- ordinary/F产品别名、原母子链接、全局序号和u日期/索引逐行校验。

完整原始元数据身份未缩到事件子集：399,252母、1,552,456子行动，98产品95family。解析身份/计数digest为：

| 内容 | SHA256 |
| --- | --- |
| 全母7列身份 | `cc49c052f3303c792bca714a3504ca5a89466ae9aa42649cc205f1f4f13f5b43` |
| 全子12列身份 | `69541004970e01cf6428358ca40de38653938bf84c8907c4381dedf85f8f1f9f` |
| 全原母子计数 | `20daf68e237790104948501bb54000f1048490f0781a05972090c3cb81a52526` |
| 全产品/family roster | `58089151d903e6376839f3849268553c83dcac0979301c2814dfe7cfbe73f8f4` |
| 展开事件/子/母/raw键链接 | `0ac73436789abaadd1e55a5670526b332e998800fcdf1fa54019ef75eb12e5c6` |

## 预算与数据读取收据

收据确认227派生metadata12列一个完整流、470母7列一次、calendar/FOMC各一次，尝试和完成均各1；全部绑定源前后size/device/inode/mtime/ctime相同。四源SHA继承既有接受绑定，没有重新hash旧大源。

Y/exit、COMMON/score、价格/原市场字段、native/SQL、网络、fit、cash均0；没有执行回测、成交或账户收益计算。金融指标均N/A：期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率及成本/资金口径均不适用。新增/修改/删除回测结果0；累计481fit/258cash及1旧partial保持。

## 输出与绑定

目录：`outputs/stage484_fomc_event_requests/actual_run1/`；八项输出为full_event_clock_status、全事件母请求、全事件子请求、唯一epoch/pre_date请求、summary、input_read_receipt、manifest、terminal。

root已提供的终态文件绑定（本记录未另重读这两文件）：

- `manifest.json`：2,180B，SHA256 `4868445f5b1a21cd7b0537b7579e8489bedbc13f59747c597fcc15be2fe8b608`。
- `terminal.json`：657B，SHA256 `81ff0e48167d6996a7a2f5944a69b5aaeda42cfed9d00ee2a9201c295890ede4`。

## 裁决、反思与后续

当前仅完成一次真实请求身份投影，**待Stage485独立审查**；本记录不宣告独审通过、不认证价格字段覆盖、PIT或训练就绪。summary的`goal_complete=false`、`PIT_qualified=false`、`training_ready=false`保持；原全市场目标active且未完成。没有生成收益或宣称策略有效。

开始/结束新增按收益调参过拟合：否，没有读取收益/标签、训练或选择参数。长期历史择题风险：是，研究路线已有历史适应性，必须保持固定信息定义与一次执行纪律。开始/结束继续价值：有条件是，本次将必要字段请求落到54,089个精确身份，显式保留缺支持，为后继可证伪测量建立入口；重复扫描同一元数据或把工程成功当alpha没有价值。

后续先完成485独立新结果审查；若接受，只能另冻结一次真实字段投影及经济测量合同，按本次精确键核验公告前volume×现金乘数×settlement，区分字段缺失、口径未知与可观测暴露。不能自动训练、计算现金收益或事后换字段/符号/央行/频率救结果。原四前瞻、正式版本、生产、CTP、邮件和调度不变；本记录不修改LINE/registry/根总账。
