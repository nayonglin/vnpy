# Stage558：旧史PMI元数据有限批次实现就绪

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 05:01 CST；非突破；只实现557冻结的元数据请求，不是回测。
- root执行actual，作者本阶段只离线fixture。源码131行，stdlib，无安装、clone、测试套件、额外源/正文请求。

## 557设计和本次实现

557在收益前冻结官方已观察POST `https://api.so-gov.cn/query/s`，站点bm36000002/tab all/qt采购经理指数/sortdateDesc/**keyPlace1**/timeOption2。2010—2021共12个发布年，每年按page1—10顺序，2021止于11月14日以衔接552静态目录；其余12月31日。最多120POST、2个year并行、全局请求起点最小间隔0.3秒、timeout12秒，无自动重试/重定向，不传未经证实的pageSize/rows。

每年遇HTTP/API/schema/transport错误、空resultDocs或整响应ID集合与前页完全相同立即停止该年并留partial；page10止于cap，不绕过UI限制。page字段效果未被预先当作事实；第2页重复集合会提供明确的未成功分页证据。每次原raw、完整headers、参数、UTC、SHA、状态和停止原因写入独立文件，失败无响应写空bytes并保留异常，而不是伪造HTTP值。

保留所有resultDocs链接（包括社交/解读），再显式标候选；仅观测过的www.stats.gov.cn域http/https、PMI标题，排解读/统计师/图解/访谈/社交和非制造业单独报告。候选是后续正文核验入口，不等于原始首发已认证。标题带明确年+月才填report_month；“1月份...”保持null，不从查询年、目录日或时间戳补年。按URL生成去重视图时保留所有来源记录，冲突月份也保留多值。

只读552的59条小候选JSON，与本次候选合成2010-01—2026-09的201月coverage；不重读67raw目录，不GET任何正文。coverage的fields_qualified/availability_qualified均保持false，不把目录覆盖当可训练值。

## 有意义的离线验证

553和556已存search响应经新解析器运行：553为20个doc/20个唯一ID/1个原公告候选（2026-09）；556为16个doc/16个唯一ID/2个原公告候选（2021-09与10）。最终fixture exit0，网络0、fit0、cash0。

首次fixture的API断言误把site的code200套到search，实际search为ok=true/code=null；只纠正本地解析器，接受原观察的null/200成功码，非null失败仍停。另一断言原先误以为553全为噪声，实际有1个2026Sep候选，按原响应修正预期。两次技术断言失败均非HTTP重试/数据修订/金融失败；没有重新网络请求。初次就绪源码SHA `f206e1b2b9f2f5794f375c0878c67a3279ba30764c49620964445a8af3ab9ba3`（由下述559定向修正替代）。

实际入口已写source_ready.json中的cli，**actual尚未启动**；root后续只执行一次到actual_run1，观察超时不重启同一进程。

## 改动、指标与反思

新增源码/source_ready/本stage，无修改或删除策略参数；新增/修改/删除回测结果0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A；本阶段fit/cash/SQL/GET/POST均0，累计仍523fit/278完成cash及1旧partial。未改LINE、registry、Git和552/554输出。

开始与结束同史择题过拟合风险均**是且高**；当前只补独立调查对象原月索引，未看收益调字段/阈值。继续本次有限元数据批次价值**是**，因为556已出现真实旧月原公告、缺段可被直接验证；提高风险或训练模型的价值仍**未证明**。不因来源工程重新定义全市场高质量做多的完整目标，也不宣称PMI alpha。

证据：`outputs/stage558_pmi_old_catalog/source_ready.json`及`outputs/stage557_pmi_old_catalog_protocol/protocol.json`。

## 559启动前定向修正（05:02 CST）

root尚未启动actual。按559预审仅补两项旧标题兼容：plain加入Unicode NFKC正规化；候选正则由“采购经理指数”扩为`采购经理(?:人)?指数|\bPMI\b`。原请求窗口、协议、字段、预算、并发和停止条件均未改；两个既存小JSON fixture再次exit0，结果仍20/1与16/2，网络0。当前源码SHA `3cd6ea3bb4ad76f58831d21c3d298f09f66ca425a6e0527ecb1324f4cbe29410`，source_ready同步。此为来源标题合同纠正，不是收益选择或新研究scope。

## 唯一actual实际结果（2026-10-21 05:04 CST，独审待结）

root已执行唯一`actual_run1`，终态completed/exit0，耗时62.410405833秒；前述“尚未启动”是初始实现时点记录，不是当前状态。**实际57 POST，57个HTTP200，808条全量resultDocs元数据，171条旧史原公告候选行**；与552静态候选合并后230个不同URL。12个发布年全部以empty_resultDocs停止，未hitpage10 cap、整ID集合重复或HTTP/API/schema错误停止；请求少于120上限，不补满预算。

2010-01—2026-09共201月中，**172月具明确标题年月的候选URL，29月尚未按标题分配**；230 URL中53个标题未明确年月，维持unknown，不能从查询年或目录时刻补月。5个明确月有多个候选URL，保留来源待正文判定。29月是当前“标题显式年月覆盖缺口”，**不能解释成29份公告不存在或字段数据缺失**。缺口为2010全部12月、2011年2—12月，以及2015年6—11月。

每条链接仍只是候选，原正文、两分项、发布时间、首发版本和样本口径均未由本批核准。article_GET=0，fit/cash/SQL均0；累计仍**523fit/278完成cash及1旧partial**，期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A。无策略参数或金融结果改变，原全市场long目标仍未完成。

本次补记只读小`terminal.json`、`candidate_urls.json`、`coverage_201_months.json`，没有重读57raw、重新网络请求或改源码。559正在独立逐原响应审查，**本记录不预签独审通过**。过拟合风险开始/结束仍是且高；对旧史元数据本批的继续执行价值是（得到可反驳覆盖），现在无须重跑同批。下一步仅待独审裁决后冻结unknown及正文取得范围，不能由目录成功直接训练或加注。

实际证据：`outputs/stage558_pmi_old_catalog/actual_run1/terminal.json`、`candidate_urls.json`、`coverage_201_months.json`。
