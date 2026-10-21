# Stage561：230 个原公告精确 URL 正文批次就绪，尚未 actual

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 05:11 CST；day；非重要突破。
- Stage560 已收益前冻结完整批次；本阶段实现与 source-ready 不是抓取完成，不是金融回测，root 唯一启动 actual。
- 开始/结束过拟合风险：**是且高**（同历史持续择题），没有用新收益选字段、符号、阈值或年份。继续来源补齐价值：**是**（已有真正目录和早期字段不规则实证），是否提供盈利优势仍未知。

## 560 冻结设计与来源判断

559 已独立接受 558 中 230 个 exact candidate URL：172 个标题月、53 个标题月未知需正文确认，保留多 URL 版本、不按标题或查询年补值。560 的 candidate binding 为 73017 B / `cd9042087c9a7fd170450e52198f590f32db2d0827913f035660cae7f8111a6a`；协议为 5608 B / `8ec117a6a7c39c36a5122d5f5e9133e91887c419d4e2b40e26857efb3deb1df1`。

本批只使用这230个已经观察到的 URL，精确保留 HTTP/HTTPS 和路径；命中545的两条 exact URL 才复用缓存，其余最多228 GET，2 worker，global 请求起点至少间隔0.3秒，timeout12秒、每响应最多2MiB+1保留并标超限、不redirect/retry/fallback，host只准 `www.stats.gov.cn`。所有错误响应/异常receipt保留。没有为元数据再探测其他URL，也不读取旧金融表。

调研结论沿用 543 的原始NBS/经济文献及AKShare维护者源码、548/558真实目录、549早期正文锚点：PMI两分项是企业调查扩散指数，原公告有真覆盖也有不规则缺项，第三方headline接口和未来滚动重印都不能替代原月信息集。本批取得正文是检验经济问题的基础，**不证明订单库存差值、全市场做多方向或极窄损加注alpha**。

## 新脚本与抽取边界

新增 `tools/stage561_pmi_original_articles.py`，188行标准库，复用545 `TextAndTables/NoRedirect`，旧源未改。最终 source **16393 B / `5a529d21a3abaadbcb388dcec02f50a72fa52cb16235b769f4383209cec88902`**；共享545 parser **6331 B / `12eaa57208895ac041f69cfaa628d94c430ed8ec77f7d3eeead57fc388f25e14`**。

1. 原HTML title/h1/h2明确报告月，或 firsttable 前真实正文 `YYYY年M月…中国/全国制造业` lead；不从目录日、queryyear、URL路径、发布年月或附注“自2013年1月”补reference_month。多身份冲突/nonmonthly保留state。
2. 制造业main表先有生产/新订单/原材料库存/从业/配送签名，aux表先有新出口订单/采购量/产成品库存签名，非制造业商务活动/投入品价格表不混。header按实际多行标签合并（PMI rowspan），只取精确当月行；旧vertical表取首行当月列。不按7列猜表类或固定FG列号。
3. 严格制造业正文范围内 `新订单指数为/是X%`、`产成品库存指数为/是X%` 只作明值补充，遇“二、中国非制造业”终止；问卷名、库存压力或无数字提法不造值。桌面/手机相同候选去重，冲突保留全部evidence且value=null，不平均。
4. clock分别 `publication_minute / publication_date / document_date_proxy / unknown`；header分钟在真实正文lead前取，只有显式发布时间/发布日期支持仅日，成文日保持proxy。时区来自国家发布者中国上下文，非网页打印后缀。所有availability/first-vintage资格仍false，不在此加入日线或训练输入。
5. GB/sample/行业数只记录附注明确制造业候选；820扩至3000只取明确后值，否则ambiguous候选/unknown，不拿非制造业4000/4300当制造业样本。多个URL同月保留独立版本，并报告跨版本/版本内冲突，不增加独立宏观月数。

缺值状态为 `unparsed_or_not_reported`，是当前抽取器未取得数值，**不笼统声称原文不存在**。输出每URL原body、headers、SHA、receipt/extract，汇总 `article_extracts.json` 与201月coverage、unknown/nonmonthly、字段/clock/口径版本。不会把来自不同版本的零散两值拼成一条已合格原发布。

## 有限离线核验和一次定向独审

三份既有545缓存：2010Aug正确53.1/FGnull且分钟署时；2019Jan49.6/47.1且分钟；2020Jan51.4/46.0且仅成文proxy。全程0GET，不新增来源fixture或大测试框架。

preactual自查发现旧完整YYYY标题可能被当成正文lead，导致header分钟被错误截去；562定向review另指出“全国制造业”前缀需要支持。两处在actual之前一次修复：记录firsttable前h1/h2/title结束offset，lead只在其后真实正文寻找，headerprefix/scope随此定位；允许中国/全国前缀，不扩大至历史表或附注。旧 `source_check/source_ready.json` 保留为被最终版本取代的preactual证据，最终三缓存必要复核通过在 **`source_check_final/source_ready.json`**；没有真实抓取重跑。562已定向核6处并同意冻结新SHA进入唯一actual，不要求额外fixture；其全面230-body独审只能在真实actual后做，当前不预签结论。

## root 唯一实际 CLI 与指标

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage561_pmi_original_articles.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage560_pmi_original_articles_protocol/protocol.json --output research/lines/futures_full_market_long_signal_ai/outputs/stage561_pmi_original_articles/actual_run1
```

当前 actual_started=false；新GET/fit/cash/SQL均0，累计仍523fit/278完成cash与1旧partial。策略参数与回测结果的新增/修改/删除均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部 **N/A**。实际后只由小terminal/summary补录本记录，原始230body由562独立读一次核验；不为小元数据重复下载。

只改本线脚本/输出/唯一561stage，不改LINE/registry、正式/生产、CTP、scheduler、Git提交推送。完整全98产品/95family高质量做多、高收益低DD、极窄损加注目标仍未完成，不能以源下载替代目标或缩域。

## 05:22 CST 追加：root 唯一 actual_run1 已 terminal，独审待完成

root 唯一实际进程 session8276 已退出 **exit0**；本 agent 仅读 `actual_run1/terminal.json` 与201月coverage的小摘要核对，未重读230正文、未重新GET或执行抽取。terminal为 **completed**，耗时518.413538500秒（约8分38秒），**228新GET +2 exact-URL缓存，共230 URL版本**；其中228个URL receipt为HTTP200，另2个非200，transport/parser异常0。没有因观察等待超时重启实际。

当前作者抽取结果为：

- 201月grid中 **199月确认原文报告年月，164月具有同一URL版本内NO/FG双值**；2010-04、2010-05尚无已确认原月身份，不能回填，也不据此宣称原公告永久不存在。
- 37月没有已抽取完整pair，集中在2010—2013早期不规则披露；其中包括上述2月无身份。缺值保持 `unparsed_or_not_reported`，不把当前parser未取得值当成原文绝对无值。
- 28个URL unresolved，仍保留非月报/身份不明/非200各自receipt/extract，等待562全面归因；2个月有多个URL版本，不扩大独立宏观月数。
- 跨URL版本冲突月0，**同一版本内部冲突月1：2011-10**。不能把“0跨版本冲突”说成全部值无冲突；该月不平均、不悄悄选值，已经通知562特别核因。
- 作者当前199个已确认月的clock_kind均是 `publication_minute`，publication_date/proxy/unknown计数均0。该统计只描述本批已抽取版本，不推翻既有2020Jan govinfo副本仅成文日的事实，不证明这些分钟为当年最早公开、更不认证first-vintage。545 govinfo副本与本批精确URL不同，不能混同。

164pair月和199身份月均为作者当前结果，**562独立230-body数值、逻辑、时钟、冲突与置信度审查尚未完成**。保持 `full_history_qualified=false / goal_complete=false`；不在审前自动做dailyjoin、模型/资金回测，也不以缺值月份缩全98/95母域。

实际新增fit/cash/SQL仍0，累计 **523fit/278完成cash及1旧partial**；策略参数和回测结果新增/修改/删除仍0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部 **N/A**。开始和结束过拟合风险仍是且高；此轮真实取得原页及暴露缺口/冲突有继续来源审查价值，alpha与加注价值尚未证明。下一步仅562独审及root统一来源裁决，不为小元数据重抓本批。
