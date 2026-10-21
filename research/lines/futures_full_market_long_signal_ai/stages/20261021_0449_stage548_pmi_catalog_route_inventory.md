# Stage548：PMI公告静态目录的真实可达范围

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 04:49 CST；非重要突破；来源发现，不是金融实验。
- 任务：以有界小探查找2010-01—2026-09共201个原月PMI公告的批量目录入口；不下载批量正文、不训练、不做资金回测、不读行情或label大表。

**结论：官方67页静态目录入口真实可用，但已观察首尾只横跨2021-11—2026-10，不能覆盖2010—2021-10。接受这条分段发现路径，拒绝声称已经找到201个月完整URL。** root随后可一次冻结67页的剩余65目录请求；本阶段没有执行该批任务。

## 真实目录与分页

官方首页 [index.html](https://www.stats.gov.cn/sj/zxfb/index.html) 真200、72,872 B；原源码内联 `createPageHTML(67, 0, "index", "html")`。首页15个发布条目，目录展示日期2026-10-20到2026-09-30；同一条目有桌面/中屏/手机三条anchor，按`pc_1600`一次读取或按URL去重。首页含2026年9月PMI原公告链接，但这里只认证href存在，未GET该href正文，不能替代545已存的另一栏目原页核验。

同一官方函数明确生成第1—66索引的`index_{i}.html`，不是猜测目录号。最后一页 [index_66.html](https://www.stats.gov.cn/sj/zxfb/index_66.html) 真200、69,196 B；10个发布条目，日期2021-11-27到2021-11-15；内联 `createPageHTML(67,66,"index","html")`。**中间65页未下载；观察首尾不能证明期间月份无缺。** 源码还出现`sCount='4229'`，它与本次声明页数/每页展示数不一致，不能据此越过66盲扫、不能把4229当完整可达条目数。

规范字段目前只有目录`title/href/display_date`，目录日期不当原发布分钟、不当所属报告月、不提取特征值。优先真实标题与正文报告月份匹配，排除“解读”和统计师评述；早期原文题目如“8月份中国制造业采购经理指数有所回升”，不统一为“运行情况”。URL中202302/202303可能是迁移，不据此判断原发布年。

## 官方搜索源码与GitHub判断

545已存的官方原页内联源码直接显示`/search/s?qt=`。本次真实GET搜索壳46,906 B、200，但没有正文结果清单；它引用公开so-gov脚本，声明站点`bm36000002`和`api.basic=https://api.so-gov.cn/`。小脚本原值显示`POST query/s`，可见搜索params结构含`siteCode/tab/qt/sort/keyplace/ie`，另combin列表函数有`page/pageSize`但未认证主搜索分页；**没有发API检索请求，因此返回字段、最大pageSize、分页边界和覆盖均未验证。** 收到root“尾页后收口、不再扩so-gov”指令后停止，没有为动态搜索做额外工程。

GitHub检索`stats.gov.cn/search`主要命中无关国家数据查询示例；`so-gov.cn api search`命中[保存的统计局动态搜索壳](https://github.com/brother0952/cursor_assist/blob/8cea62d41d05e66b19b79cef791c72f9f83037f6/data_analyze/stats_search_base.html)。它是作者保存页面，不能当稳定归档爬虫或PMI201条清单。判断：本次官方已存内联规则比社区猜URL更可靠；可先使用静态分段目录，早期缺段另设计，不安装、clone或复制未经验证的下载程序。

## 请求与证据边界

本阶段新增6个真200：官方首页/搜索壳/发布脚本/尾页/搜索api.js/query.js，原body总203,023 B，逐文件SHA在`catalog_route.json`及两份receipt中。此前一次普通沙箱DNS失败无响应，提权对不同的尾斜杠目录请求一次reset，均无HTTP body；改为明确`index.html`后成功。没有自动重试，没有公告批量正文，没有后台下载进程遗留。web工具另有两次观察失败且无原响应，不能计作验源成功。

可复用已存首页、尾页，不再重GET它们；若root批准目录批，剩余65页足够完成“声明67页”枚举，然后按实际覆盖缺段决定下一步，不擅自扫`index_67+`或201次搜索。当前25条目录记录仅发现证据、不是25个月数据；完整目标201报告月仍未就绪。

## 改动、指标与反思

新增548静态目录原响应、receipt、25条目录小记录和route JSON。新增/修改/删除策略参数0；新增/修改/删除回测结果0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A。新增fit/cash/SQL均0；累计仍523 fit /278完成cash及1旧partial。

开始与结束对同史择题过拟合风险判断均**是且高**，本阶段未查看收益选择数据或调参。继续完整原月来源盘点价值**是**：发现可复用官方分段索引且明确早期缺口；现在进行模型或加注的价值**未证明**。本阶段不把宏观直觉或来源取得等同超高质量long证据，不修改正式C9、LINE、registry、Git或生产。

证据目录：`research/lines/futures_full_market_long_signal_ai/outputs/stage548_pmi_catalog_route/`；核心`catalog_route.json`。
