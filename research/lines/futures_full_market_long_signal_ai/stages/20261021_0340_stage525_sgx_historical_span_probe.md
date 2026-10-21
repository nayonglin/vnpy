# Stage525：SGX四个固定历史锚的官方归档跨度探针

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 03:40 CST。
- 本轮只做来源跨度/原件内日期与章节存在性检查，不是金融实验、训练特征生产或重要突破。先读registry和本线LINE，再读Stage521及其小probe_plan；不读旧行情、129/actions/Y、COMMON、模型或现金大表。
- 开始反思：本轮没有收益选样或调参，新增按成绩过拟合为否；长期同史择题风险仍是且高。继续价值有条件是：四个收益前固定锚可以让“存在历史路径”从推测变成有限事实，不能替代连续覆盖、PIT、稳定同定义或alpha。

## 收益前冻结与实际预算

先保存[protocol.json](../outputs/stage525_sgx_historical_span_probe/protocol.json)，创建时间UTC `2026-10-20T19:38:33.299253+00:00`。唯一URL模板来自521原计划，保留完整`iron_dsp` / `Iron_Ore_DSP_(T%2B1_Volume_and_Open_Interest).html`文件名，只替换年、月份目录和日期；所有存在性在请求前均未知。

日期固定为2013-01-09、2016-01-13、2019-01-09、2026-01-14，按第一周以后周三选取，未看行情或收益后更改。预算最多4GET、并发最多2、每次timeout15秒、响应体上限2MiB、禁止重定向与retry；失败不换日期、域名或端点。一次性[runner.py](../outputs/stage525_sgx_historical_span_probe/runner.py)只写本525输出目录，HTTP错误体也完整封存。

唯一实际进程：**session46723**，开始UTC19:38:41，最后响应结束UTC19:38:46；tool `write_stdin` 的终态chunk为`758a4a`，**真实exit_code=0**。过程预写started记录，收完即保存raw及HTTP元数据；完成后不重启、不重抓。脚本正常完成不代表4个URL全部成功。

## 四个固定原件的真实结果

| 事前固定日期 | HTTP | 完整raw字节 | 页面自称日期/时点 | 原TSI62章与固定Feb标签 |
| --- | --- | ---: | --- | --- |
| 2013-01-09 | 404 | 118 | 错误体`404 Not Found`，没有报告日期 | 无TSI62章、无Feb-13；这是此精确URL失败，不能外推当年无任何数据 |
| 2016-01-13 | 404 | 118 | 同上 | 无TSI62章、无Feb-16；不换旧命名或其他端点重试 |
| 2019-01-09 | 200 | 643,506 | `As at Wednesday, January 09, 2019, 8pm SG Time` | 有`SGX TSI IRON ORE 62% DERIVATIVES`章和`Feb-19`字面标签 |
| 2026-01-14 | 200 | 415,749 | `DSPs as at Wednesday, January 14, 2026, 3.00pm (Rebar), 5.30pm (Iron Ore), 8pm (All others), SG Time` | 有`Feb-26`；旧字面TSI62章不在，表头为IODEX，不能当原定义的无缝延续 |

合计**4GET /2HTTP200 /2HTTP404 /0retry /0redirect /0异常**；4个响应体均完整、没有触及2MiB上限，总1,059,491B。两404同一118B内容及SHA，不当两个独立市场观测。

| 日期 | raw SHA256 |
| --- | --- |
| 2013-01-09、2016-01-13各自错误体 | `b0b0fadb436530e81236a3d97058fc501d732eb24768845c5e97ac8ac3c32176` |
| 2019-01-09 | `75f79f799a8c87364a8955e98d81d82fbd1ac775fd5110ed22f310341069c610` |
| 2026-01-14 | `579afa6cb7d5117bbeb98e04ae31de19d7ca8f17b1742b3ba5ff2ac17af3b39d` |

当前HTTP Last-Modified分别为2019-01-09 23:00:21 GMT及2026-01-14 23:00:28 GMT，即北京时间次日07:00:21/07:00:28；这是本次服务器返回的文件元数据，**不是历史首发时刻证明**。2019页首整体`8pm`也不能进一步解释为所有DSP计算/免费发布均20:00；本轮没有单独历史定价规则。因此521在2020/2023原件发现的17:30不能机械倒套2019。

## 必须保留的定义变化

2026原件`IMPORTANT NOTES`明确列出：

- 合约名称变化以`1 Sep 2025`为界，旧TSI Iron Ore CFR China 62%名称改为IODEX名称。
- `Reference Index for FSP`以**合约到期月份**划界：`expiry prior to Jan 2026`为TSI 62% Fe CFR China；`expiry from Jan 2026 onwards`为IODEX CFR China 61% Fe。不能误写成整个市场在某民用日统一更换所有历史基准，也不能仅改章名后拼接同一62%序列。

限定摘录位于[definition_notes.json](../outputs/stage525_sgx_historical_span_probe/definition_notes.json)。本轮只登记原文定义、时钟和标签，不把DSP/PrevDSP/量仓数值解析成特征、不选择新月份、不计算grade-premium或交易收益。原HTTP检查中预先固定的`09 Jan 2019`等简写字符串未命中，是日期打印格式不同；后续[content_review.json](../outputs/stage525_sgx_historical_span_probe/content_review.json)保留实际长格式上下文，**不删除原false或重新GET来修结果**。

## 本轮调研与判断结论

外部调研沿用刚读Stage521的一手SGX报告、交易时钟资料与维护者GitHub边界；本轮网上实际只访问协议中四个官方archive URL，不追加泛搜或其他端点。维护者抓取示例和日期模板本身不证明历史存在，这次真实GET只新增2019与2026两个锚事实。

**跨度探针完成，不能直接转为批量历史或金融GO。** 加上521原2020/2023，两阶段目前仅四个成功日期；2013/2016固定路径404，旧时期覆盖仍未知；2026还出现显式参考定义变化。没有证明2010—2026连续历史、可训练样本数、首版与后版一致、当年21:00前可得或延迟入场后的信息增量。完整六所98产品/95family母域未修改，也没有将铁矿历史锚包装成全市场支持。

因此不自动补缺、不修改已有525日期、不因404另找第二套模板，不重开旧365/521同晚首开题，不启动fit/cash/SQL。若root以后继续，只能基于这些真实失败和定义边界另作明确裁决；本525没有新actual授权。

## 输出、金融指标与结束反思

- 主清单：[manifest.json](../outputs/stage525_sgx_historical_span_probe/manifest.json)；它包含各URL、请求/完成UTC、完整headers、状态、raw路径/bytes/SHA/异常及预算计数。
- 四份`YYYY-MM-DD.raw.bin`、各自`.http.json`和`.started.json`完整保留；[process_exit_receipt.json](../outputs/stage525_sgx_historical_span_probe/process_exit_receipt.json)记录实际session/exit/tool终态证据。新四raw SHA与manifest绑定均核对一致；不重hash旧大源。
- 新增仅本stage及525输出目录的一次性脚本/协议/原件/元数据；新增/修改/删除策略参数与金融结果均0。新fit/cash/SQL、旧金融重放、分钟数据、生产/CTP/订单/凭证/Git操作均0。LINE、registry、根memory/back_log、其他线、正式版、邮件与launchd未改。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率及金融参数全部**N/A**；不是把未测写成0。本轮无回测，不冒称完成金融结果独审。
- 结束过拟合：新增按收益调参否；同史自适应择题风险是且高。结束继续价值：本次四锚核查价值已实现，继续同预算探针否；未来是否有更大来源研究价值仍未决，不能以两个200自动推进。完整高质量long/更高净收益更低回撤/窄损加注目标active未完成，无生产或加注资格。

## 附录：报告日期与到期月份的区别

root已对525新2026原件独立读取一次，并要求保留以下解释边界；本agent没有为此再次读取raw或请求网络：FSP参考指数界线是**合约到期月份Jan2026起**，不是“从2026报告日期起所有价格都改成61%”。2025年的同一份报告可能同时列出两类expiry，须逐合约保留定义，不能按报告年份整页切换。2026旧`TSI62`字面章名未出现，也不等于页面没有铁矿价格；本次已观察IODEX表头与固定Feb-26标签。2019仅有整体8pm页首证据；打印日期的简写字符串不匹配也只反映格式，不触发任何补抓或换日期。本525到此停止。
