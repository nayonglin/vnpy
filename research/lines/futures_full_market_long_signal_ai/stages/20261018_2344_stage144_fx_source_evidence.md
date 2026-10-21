# Stage144：ECB 汇率来源与决策时点证据

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-18 23:44 CST。
- 范围：已读 registry、本线 LINE 和 Stage143。仅核来源资格，不设计或运行收益实验；非重要突破，不触发 A/B，不改 LINE、registry 或其他线。
- 当前结论：root 已完整取得官网历史 ZIP 并通过载体检查，可作当前归档；历史首发 vintage 尚未证明。直达 CSV 已有内容反例，不能凭域名和 HTTP 200 接受。**尚无 strict PIT 或训练资格。**

## 官方口径与载体

[ECB 官方入口](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)明确欧元为共同基准，提供 USD、CNY，列出 Time series 的 [CSV ZIP](https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip) 和 XML；当页可读 2026-10-16 两币数值。[2015 年公告](https://www.ecb.europa.eu/press/pr/date/2015/html/pr151207.en.html)确认自 1999 年 1 月每日发布参考汇率，但这不替代本机对两币完整起止、缺失和重复日的验收。

若同日同版本的两列单位分别是 CNY/EUR、USD/EUR，则交叉比值为 `CNY_per_USD = CNY_per_EUR / USD_per_EUR`。这只是从两个欧元参考价派生的量，不是中国中间价、离岸 CNH、美元指数或可执行 USD/CNY 成交价。两腿必须同 observation date、同载体版本、均为正数；不可把一腿前值与另一腿新值混算。

维护者 [alexprengere/currencyconverter](https://github.com/alexprengere/currencyconverter) 的 README 指向同一官方 ZIP，并说明默认内嵌数据可能陈旧，缺失可选择线性插值或 last-known。可借鉴下载与解析入口，不能照搬插值、越界回退或默认内嵌表，更不能用第三方镜像替代官方资格。未安装、执行或复制其代码。

## 实际访问记录与否定证据

本 agent 对两个地址各做一次沙箱 HEAD，均为 DNS exit 6；授权网络后各一次 HEAD：ZIP 返回 HTTP/2 200、`application/zip`、Last-Modified `2026-10-16 13:56:49 GMT`；直达 [CSV 地址](https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.csv)返回 HTTP/2 200、`text/csv`，Last-Modified 却为 `2020-06-18 11:46:09 GMT`。只取得头，不据此声称正文、ZIP CRC 或全历史完整。web 打开两下载地址均报 Internal Error，属于工具读取失败，不能写成站点 404。直接 framework PDF 一度超时，带官方搜索结果参数的同一 PDF 后可读。两次含 Data Portal 的组合请求连接失败，未冒称取得其历史元数据。

root 另行报告：直达 CSV 请求超时，已收 622,592 字节，失败码 28；片段首行为周日 `2010-02-14`，`USD=2`、`CNY=1.3`，另有整齐的 1、2、2.1、2.2 等数值。此反例与参考汇率发布语义不符。**该直 CSV 未通过资格，片段不可当完整历史、不可按值修补或输入训练。** 不推测异常原因。原 partial 为 `outputs/stage144_fx_source/raw/eurofxref-hist.timeout_partial.csv`，对应头为 `ecb_headers_network.txt`；ZIP 头为 `ecb_zip_headers.txt`，均由 root 保留。

终态补充：本 agent 实读小型 [content_receipt.json](../outputs/stage144_fx_source/content_receipt.json)。root 单次有界 ZIP 请求最终 exit 0，原 ZIP 641,332 字节、SHA256 `8e925cef1572f8df5c8743229a761b029180f3b5cd4aa2213592192964ebd793`；单一 CSV 成员 1,927,337 字节、CRC 通过。归档 7,116 行，1999-01-04 至 2026-10-16，无重复日期或周末行。**归档起点不等于 CNY 起点**：1999—2004 的 CNY 全缺；2005 双币195行、缺62行；2006起各年度双币无缺。2020—2026-10-16共1,741行双币完整，只证明该归档支持研究区间，不证明首发 PIT。root 已生成 `outputs/stage144_fx_source/ecb_usdcny_archive_values.csv`，收据明确 training/strict_pit/financial 三资格均 false。本 agent 未重复取 body、读全表或重做全文件 hash。

## 2020 年后的发布时钟与更正边界

2015 公告明确自 **2016-07-01** 将发布时间从约 14:30 改为约 16:00 CET，当时采样为 14:15。[2016-02-18 官方会议摘要第1页](https://www.ecb.europa.eu/paym/groups/pdf/fxcg/2016/0218/2016-02-18_summary.pdf)进一步明确 CET/CEST 随季节适用。因此欧洲夏令时约为中国 22:00，冬令时约 23:00。当前入口和 [2026-06-23 framework 第2页](https://www.ecb.europa.eu/stats/pdf/exchange/Frameworkfortheeuroforeignexchangereferencerates.en.pdf?3e6954e3231bfd495fe0030c2b992af8=)则写约 14:10 确定、16:00 发布；不能把当前采样分钟机械追溯为全历史规则。`around` 也不是逐日准时送达保证。

同 framework 第7页允许内部核查或公众反馈触发修订、重发；同币下一 TARGET 营业日汇率发布后不再修订；更正记录至少保留五年。**记录留存不等于公开提供逐时 vintage。** 本次未取得 2020 年当时版本的完整规则沿革、逐次公告和首发快照；现有历史下载应称“当前归档重建”，不能自动叫 strict PIT。

对本线中国 `u` 日收盘决策，ECB 同日值尚未发布，21:00 夜盘通常也早于该发布。最少须取完整日滞后，若沿用既有 source 日契约，还要满足观测日不晚于母体紧前完整 source 日 `v`；不得擅改 `u_index`、混淆自然日与交易日。仅 `t≤u−1` 仍不解决归档修订：周一的值可以在周二欧洲发布前更正，周二中国15:00还不能把事后最终值当已知。

在当前更正规则可适用的条件下，保守历史方案还应要求：`t` 的下一次同币 ECB 营业日发布已在决策前完成，并留固定送达余量。正常中国周一15:00即不能直接采用上周五的最终归档值，因为其更正窗可能延至周一欧洲发布；可退至周四。此为依据规则的保守研究假设，历史规则沿革和实际 vintage 未补齐前仍不签 strict PIT。前向数据应保存真实抓取时点、原文、头、hash、版本和失败，而非只记日历日期；HTTP Last-Modified 不是逐观测首发时刻。

## 缺失、运行与判断

ECB 以 TARGET 营业日发布，国内交易所日历不同。周末、TARGET 休市、币种缺值和取数失败必须分开；不插值，不把休市填成“汇率无变化”，不以未来最近有效值倒填。若以后允许保持旧值，须先固定 age/missing 状态和最大陈旧规则；本轮不授权该特征实现。ZIP 载体和上述覆盖检查现已通过，历史发布/修订沿革及与本线决策的时间绑定仍未通过，不能把解压成功写成全部来源资格。

新增/修改/删除策略参数均0；新增/修改/删除回测结果均0。本 agent 新增汇率数据正文下载0、SQL/fit/cash/标签/行情扫描均0；root 的有界载体探针按其收据另计。累计391 fit/202 cash 不变。期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率均 N/A；无金融回测，不追加金融结果独审。

开始及结束过拟合判断：新增拟合过拟合为否，因本轮未看收益选参数；同史多轮择题风险仍是。继续价值判断：有限来源验收为是，它排除了错误 CSV 和发布时间泄漏；继续延长工程或立刻拟合为否，vintage/时点与新机制门槛尚未通过。ZIP 当前归档合格只推进载体资格，不授权收益实验、窄损、加注或正式接入。
