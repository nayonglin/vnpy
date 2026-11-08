# Stage001 GitHub 期货基本面 Skill、数据适配器与 Agent 框架调研

- line_id：`futures_fundamental_data_sources`
- 当前模式：只读外部调研；未安装、未运行第三方代码、未取用凭证、未跑回测
- 记录时间：2026-11-08 15:14（Asia/Shanghai）
- 工作区：`/Users/mac/Desktop/fian`
- 阶段性质：来源与复用性核验；供主报告综合和独立复核
- 是否重要突破：否；找到贴合的现成研究流程，但未证明完整历史数据能力
- 是否触发 A/B：否；没有策略候选或收益结论

## 外部调研与判断

**结论：有真实的中国商品期货基本面 Skill 可参考，不能说没有现成 Skill；但本次检索未找到已经核实同时满足“稳定授权数据、2015 年起产业基本面与历史新闻、明确可复现的看多/看空证据链”的完整现成方案。** 最值得借鉴的是 `zynthium/finresearcher` 的研究纪律，以及 QuantSkills 的数据契约、同日对齐和事实/推断分离。它们都不能替代数据供应商的历史覆盖验收。

本次先使用已连接 GitHub 插件的仓库搜索、文件搜索、README/代码读取和 REST 元数据读取，再用 Web 搜索补齐检索召回和 Tushare 官方文档。搜索词包含“期货 基本面 skill”“期货 基本面 SKILL.md”“commodity fundamental agent”“SKILL.md commodity futures”。星数没有进入取舍依据。

核验等级：下文“已核验”指实际读到 GitHub 当前默认分支文件；不等于完成安装、真实 API 调用、服务 SLA 或全仓安全审计。`pushed_at` 仅为 GitHub 元数据时间，不能证明供应商服务可用性或数据质量。

## 八个优先参考仓库

### 1. finresearcher：最贴合的中文基本面研究工作流

- 仓库：[zynthium/finresearcher](https://github.com/zynthium/finresearcher)。真实入口：[skills/futures-fundamental-research/SKILL.md](https://github.com/zynthium/finresearcher/blob/main/skills/futures-fundamental-research/SKILL.md)。仓库没有根 README；实际阅读内部 [采集脚本 README](https://github.com/zynthium/finresearcher/blob/main/skills/futures-fundamental-research/scripts/fetch/README.md)、[来源分层](https://github.com/zynthium/finresearcher/blob/main/skills/futures-fundamental-research/references/data-sources.md)、`source_registry.py`、`futures_history.py` 和 `market_cli.py`。
- 可借鉴：供给—需求—库存—边际变化—利润—期限结构—交割风险—外盘锚定—反证；允许偏多、偏空、中性、观望、只看结构。要求来源评级、最新可验证日、主要证据缺口；没有反证路径不下方向；授权版和公开代理版分开。
- 不能直接复用为数据平台：脚本 README 明确当前只是原始归档层，尚无付费产业库接入、完整数据库/调度或复杂多交易所适配。[source_registry.py](https://github.com/zynthium/finresearcher/blob/main/skills/futures-fundamental-research/scripts/fetch/source_registry.py) 中部分入口只是交易所首页；历史行情脚本调用新浪，提供盘面历史，不是供需或新闻档案。
- 2015：没有随仓提供已验收的 2015 产业库或新闻库；不能把工作流里的“历史”“可追溯”当成数据覆盖证明。
- 维护/许可证/依赖：创建和最后推送均为 2026-04-11；可见树未发现 LICENSE，不能因公开可读就认定允许复制分发。采集模块自称只用 Python 标准库，仍需独立验证页面和字段。建议学习流程后自行实现，或先向作者明确许可。

### 2. Futures Investment Council：有计算代码，但技术权重明显、库存历史不满足 2015

- 仓库与主文档：[quantskills/skill-futures-investment-council](https://github.com/quantskills/skill-futures-investment-council)。已读 [README](https://github.com/quantskills/skill-futures-investment-council/blob/main/README.md)、[SKILL.md](https://github.com/quantskills/skill-futures-investment-council/blob/main/SKILL.md)、数据 provider、基本面适配代码、配置与 pyproject。
- 可借鉴：确定性指标和文字解释分开；证据重复引用不能当成独立票；披露共识/分歧/反方/失效条件；数据缺失用 `unknown`；`confidence` 明确不是上涨概率。PandaData 失效不得悄悄换离线 CSV，这个约束合理。
- 不能当作纯基本面分析器：扫描器主要依赖 MA、ADX、突破和 RSI，README 也承认这是趋势排序；当前 [fundamentals.py](https://github.com/quantskills/skill-futures-investment-council/blob/main/scripts/skill_futures_investment_council/api/fundamentals.py) 的 AKShare 补充主要是 `futures_spot_price_daily` 与 `futures_inventory_em`，并非完整产量/开工/需求平衡表。
- 代码级待修风险：该文件 `_DEFAULT_SPOT_SYMBOLS` 把 `OI` 写成“豆油”，而其库存映射是“菜油”，存在品种错配风险。尚未执行验证，不应直接作为可信底座。
- 2015：库存适配依赖的当前 AKShare `futures_inventory_em` 在源码请求中限制 `TRADE_DATE >= 2020-10-28`，并仅取第一页 500 行；扩大上层 `start_date` 无法得到 2015 库存。仓库也没有提供 2015 新闻档案接口。
- 维护/许可证/依赖：最后推送 2026-08-16；[LICENSE](https://github.com/quantskills/skill-futures-investment-council/blob/main/LICENSE) 为 GPL-3.0-only（GitHub 自动元数据显示 NOASSERTION，实际文件优先）；Python>=3.10，akshare/numpy/pandas/PyYAML，默认实时数据另依赖 PandaData SDK、账号和网络；仓库带 vendor wheel，本轮没有安装或审计二进制。适合参考，不建议直接接入现有环境。

### 3. Futures DeepView Analyst：结构、库存和利润接口规划最直接，但依赖商业数据契约

- 仓库：[quantskills/skill-futures-deepview-analyst](https://github.com/quantskills/skill-futures-deepview-analyst)。已读 [README](https://github.com/quantskills/skill-futures-deepview-analyst/blob/main/README.md) 和真实 [SKILL.md](https://github.com/quantskills/skill-futures-deepview-analyst/blob/main/SKILL.md)。
- 可借鉴：基差、期限结构、仓单、库存、现货利润、席位与资金流的方法地图；先核对 API 契约、单品种单日试调、再按同一 trade_date 对齐；事实和方向推断分开；席位仅前排名披露，不能解释为全市场“主力”。
- 不能直接拿来保证数据或方向：该仓只有 Skill/参考文档/平台适配文件，真实调用依赖姊妹 `skill-pandadata-api` 与 PandaData 权限。席位、仓单和利润仍不是完整产业供需。README 对接口数量写法有 35/38 两种，不宜机械照抄宣传数。
- 2015：已读文件没有逐接口起点、历史新闻回补或 2015 样本；本轮未验证该商业接口服务、报价和授权。指定过去分析日期不等于各数据域都存有那个日期。
- 维护/许可证/依赖：最后推送 2026-07-16；GPL-3.0；依赖 `pandadata-api`，需要另行核实 SDK、接口文档和账号权限。值得向供应商索取样本验证后再评价数据层。

### 4. AKShare：开源适配器，可补数据，不能承诺档案和 SLA

- 仓库：[akfamily/akshare](https://github.com/akfamily/akshare)。已读 [README](https://github.com/akfamily/akshare/blob/main/README.md)、[新闻源码](https://github.com/akfamily/akshare/blob/main/akshare/futures/futures_news_shmet.py)、[库存源码](https://github.com/akfamily/akshare/blob/main/akshare/futures/futures_inventory_em.py)。它是 Python 库，不是期货基本面判断 Skill。README 另列 AKTools 可提供 MCP，但本轮没有安装或测试该伴随项目。
- 可借鉴：接口命名和结构化 pandas 返回，适合建立来源适配层、公开源交叉检查和小样本验证。MIT；README 当前要求 64 位 Python>=3.11；仓库最后推送 2026-11-06，维护活跃。
- 2015/新闻关键限制：`futures_news_shmet(symbol)` 没有日期参数；源码只请求第 1 页，“全部”100条、品类2000条，不能代表2015新闻档案。`futures_inventory_em` 请求硬编码2020-10-28起、500条且无翻页，不能代表完整库存史。
- 稳定性：README 明示外部不可控因素可能导致接口移除；开源代码活跃不等于上游公共网页/API稳定，也不自动取得付费内容或商用再分发权限。适合辅助源，不宜作为所有品类基本面的唯一主源。

### 5. Tushare：适合作为有权限的结构数据候选，新闻不应承诺覆盖2015

- SDK 仓库：[waditu/tushare](https://github.com/waditu/tushare)。已读 [README](https://github.com/waditu/tushare/blob/master/README.md) 和 [Pro client](https://github.com/waditu/tushare/blob/master/tushare/pro/client.py)。它是数据适配器，不是基本面判断 Skill；动态 API 方法名不会在 SDK 逐个列出。
- 可借鉴：统一 REST/表格接口，合约、日行情、仓单与持仓排名可做底座。BSD-3-Clause；GitHub 最后推送 2024-03-13，但不能据此推论2026服务停更，当前[官方变更页](https://tushare.pro/document/1?doc_id=9)仍有2026接口更新。
- 官方明确的范围：[fut_daily 文档](https://tushare.pro/document/2?doc_id=138)写起点1995-04-17、2000积分、单次2000条；这只证明行情文档范围，不证明基本面。旧[权限总表](https://tushare.pro/document/1?doc_id=108)给仓单2006年起、持仓排名2002年起，应按细接口与实际品种再验收。
- 新闻：[官方权限表](https://tushare.pro/document/1?doc_id=290)当前仅标“3年以上”，列单独1000元，不构成2015档案承诺；期限、权限和使用授权仍须供应商确认。本轮没有调用私人 token。
- 不能直接复用旧 SDK 安全假设：本次读到的 `client.py` 默认 endpoint 是 `http://api.tushare.pro`，鉴权 token 放 JSON 请求体；若未来接入，应先核实现用受支持版本和 HTTPS 契约，不能把当前公开旧文件直接装进生产环境。

### 6. Claude Trading Skills：真实 Skill 集，适合新闻方法论和海外锚定

- 仓库：[tradermonty/claude-trading-skills](https://github.com/tradermonty/claude-trading-skills)。已读主 README、[market-news-analyst/SKILL.md](https://github.com/tradermonty/claude-trading-skills/blob/main/skills/market-news-analyst/SKILL.md) 与 [cot-contrarian-detector/SKILL.md](https://github.com/tradermonty/claude-trading-skills/blob/main/skills/cot-contrarian-detector/SKILL.md)。MIT；最后推送2026-11-08。
- 可借鉴：新闻按来源、意外程度、传播链和相关/因果区分整理；COT 数据需承认披露滞后，拥挤度不能单独变成方向/入场信号；缺历史的市场进入 skipped，记录原因。
- 不匹配：主定位是长期投资、ETF/分红股和美股波段；新闻 Skill 默认“过去10天”、英文、WebSearch/WebFetch，不提供2015新闻档案。COT 是 CFTC 披露市场，不能直接替代国内交易所席位和中国商品供需。
- 依赖：新闻路径不需独立API key但需联网搜索；COT 路径需 FMP Premium+ 和 requests。可取其新闻证据链与海外驱动模块，不应整套照搬为国内品种基本面评分器。

### 7. TradingAgents：多空讨论框架，需重写基本面和数据层

- 仓库：[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)。已读主 README、[fundamentals_analyst.py](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/agents/analysts/fundamentals_analyst.py)、[Yahoo新闻代码](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/dataflows/vendors/yahoo/news.py)、[AlphaVantage新闻代码](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/dataflows/vendors/alpha_vantage/news.py) 和 pyproject。
- 可借鉴：不同角色分工、bull/bear反证、运行配置留痕、历史窗口过滤和 coverage-gap 提示，后者避免把接口无覆盖误写为“当时没有新闻”。
- 不匹配：基本面角色明确研究公司财报、资产负债表、现金流和内幕交易；README市场例子主要股票与加密，非中国商品供需。它是 LangGraph 框架，不是可直接装入的中国期货 Skill。
- 2015：Yahoo路径先取当前新闻feed/搜索样本再按日期过滤，不是完整历史档案；AlphaVantage能传 time_from/time_to，仍未证明中国商品和2015新闻覆盖。声明支持历史日期不能代替供应商验收。
- 维护/许可/依赖：Apache-2.0；最后推送2026-11-04；Python>=3.11，LangChain/LangGraph/pandas/yfinance等依赖较多，LLM和可选数据API独立收费。当前仅为架构参考，不建议为一个品种的基本面问答先引入完整交易框架。

### 8. FinRobot：可参考可追溯计算与报告，当前重点仍是股票估值

- 仓库：[AI4Finance-Foundation/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot)。已读主 README 与 [news_aggregator.py](https://github.com/AI4Finance-Foundation/FinRobot/blob/master/finrobot_desktop/finrobot/engine/data/providers/news_aggregator.py)，并核对默认分支树中 Skill 清单。Apache-2.0；最后推送2026-10-24。
- 可借鉴：确定性计算与LLM叙述分开、数据来源追踪、多源失败应显式报错、无日期新闻保持unknown而不是伪造“刚刚发布”。
- 不匹配：当前V2是equity research，DCF/DDM/LBO/comps、公司财报和股票IC报告，Skill目录也主要股票/投行/财富管理；它不是中国商品期货现成基本面方案。
- 2015/依赖：所读新闻聚合器调用Yahoo当前新闻与AlphaVantage，AV调用不带历史日期；没有证明2015国内商品新闻。新桌面栈为PydanticAI/FastAPI/React/Tauri等，另需LLM与FMP/Finnhub等数据权限，引入成本较高。

## 另核验但不列为优先复用方案

### canqihe/futures-data-skill：历史价格与历史新闻的宣传必须拆开

已读 [README](https://github.com/canqihe/futures-data-skill/blob/main/README.md)、[小写skill.md](https://github.com/canqihe/futures-data-skill/blob/main/skill.md)、[collector.py](https://github.com/canqihe/futures-data-skill/blob/main/backend/collector.py)、requirements及目录树。最后推送2026-03-24，未发现LICENSE。其README声称2005-2026 OHLCV和上万新闻，但数据库明确未随仓提供；不能验证该统计，更不能将OHLCV起点移植为新闻起点。

实际代码价格调用新浪连续行情，新闻调用AKShare上海金属网，`fetch_news`再 `head(100)`，不支持历史日期回补；还有按publisher的全局最新时间过滤，各品类增量是否误跳需要另审。依赖主要akshare/pandas，但skill强制原机器 `/usr/local/bin/python3.14`，与当前仓库`.py311/bin/python`冲突；README与skill品种/新闻数也不一致。可借SQLite归档思路，不宜采信“完整数据库”或安装后即有2015新闻。

### QUANTAXIS：数据/回测基础设施，非本次核心缺口

核验的是目前可访问的 [yutiansut/QUANTAXIS](https://github.com/yutiansut/QUANTAXIS)，不是误拼的组织地址；已读README和 [QAFetch文档](https://github.com/yutiansut/QUANTAXIS/blob/master/doc/api-reference/qafetch.md)。MIT，最后推送2026-09-18。其期货接口围绕日线/分钟/实时和本地存储；多数据源和统一结构可参考，但没有读到满足2015供需和新闻的现成Skill。MongoDB/ClickHouse、pytdx等引入范围超过当前问题，已有vn.py体系不宜为此整体替换。

### 华尔街见闻新闻Skill：近期摘要入口，不等于历史新闻合同

已读 [wallstreetinsights/skills 的 wallstreetcn-news.md](https://github.com/wallstreetinsights/skills/blob/main/wallstreetcn-news.md)。仓库自述“华尔街见闻官方skills”，MIT，只有该文件和LICENSE，无根README与标准命名的SKILL.md目录；最后推送2026-04-23。本轮未找到华尔街见闻主站反向链接GitHub仓库的证据，因此官方身份最多写“仓库自称官方”，不可仅靠名称认证。

内容是无需key的最新/头条/热文/关键词搜索四个公开API和摘要版式；没有2015起点、全量翻页、原文授权或SLA条款。可参考近期新闻接入，不能把 `content_short` 当全文、关键词搜索当完整2015档案。其他媒体转载谈“跨时段回溯”也不是连续完整性的证明。

## 本次变更、回测和输出

- 新增：本调研stage文件。
- 修改/删除脚本：无。
- 新增/修改/删除策略参数：无。
- 回测参数与财务结果：未回测；期末权益、收益、最大回撤、Sharpe、总滑点、交易次数和胜率均不适用，没有新增或删除任何既有回测结果。
- 安装、依赖变更、凭证读取、外部写入、下单和定时任务：均无。

## 结论与后续建议

1. 优先“借鉴研究契约 + 验收授权数据”，不要先被多Agent角色数量或预测措辞吸引。基本面方向应是可证伪的条件判断，不能把多数模型同意当成独立证据。
2. 若接受商业源，向PandaData及产业供应商逐品种索取2015、2020、近一年的样本，核验字段、频率、单位、样本口径、发布时间、修订、授权和故障处理；“接口支持start_date”不等于那时确实有数据。
3. 至少拆开验收：真实合约行情/期限结构、仓单与库存、产量/开工/需求/利润、新闻原文与最早公开时间。2015行情通过不能替代后三者验收。
4. 若未来做历史方向验证，必须保存原始载荷和获取时间，同时记录当时公开时间与修订版本；LLM已知后来事件，历史新闻过滤也不足以单独消除知识泄漏。

## 反思

- 运行前过拟合：否。本轮只研究信息来源和事实契约，不选择收益最好的信号、权重或阈值。
- 运行后过拟合：否。没有依据价格结果挑框架；仍需防止未来把技术指标包装成基本面、按行情事后挑新闻或把专家叙述调到“看起来正确”。
- 运行前继续价值：是。先弄清数据与Skill边界，可以避免后续无效安装和错误历史验证。
- 运行后继续价值：是，限于最小品种的来源验收。完整2015产业/新闻覆盖仍无现成证据，继续扩大角色或安装框架的边际价值低，应先解决数据。

## 合入建议

- 由主agent综合后更新本线LINE.md与registry；本子任务不修改它们。
- 不追加根目录memory.md/back_log.md；尚无策略突破、路线正式废弃或候选晋级。
- 本stage需要主agent独立交叉阅读，不能作为已经运行成功或供应商数据认证的证明。
