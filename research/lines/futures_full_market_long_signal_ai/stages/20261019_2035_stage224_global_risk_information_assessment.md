# Stage224：VIX/VIX3M 全球期权风险信息的来源与机制评估

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-19 20:35 CST；独立只读研究，非重要突破，不是实验协议或回测。
- 先读 `research/registry.md` 和本线 `LINE.md`，重点继承 Stage143–150、197、198、209、218–221。只新增本唯一 stage，不修改 LINE、registry、旧工具、其他线、正式版、生产或 Git。
- 新 fit / prediction / selection / cash / SQL / 标签 / 回测均 **0**；累计保持 **433 fit / 234 cash**。没有安装依赖、读取本地大表或批量下载历史。官方 CSV 仅读两个首部各 1,024B，共 2,048B；尾部 Range 未被服务器接受，未因此读取全文件。

## 结论

**当前否决把 VIX 水平或 VIX/VIX3M 比值作为下一项“新标量→COMMON52+Ridge→现金”实验。** 它们确实增加了国内价格与已试 FX 不能唯一恢复的期权观测；但“观测独立”只通过新意必要条件，没有通过本线所需的机制强度。当前公开一手研究支持的对象、期限和市场，与中国六所所有真实期货的短期做多、窄初损及共同 K 不一致。

本稿不推荐改 VIX 符号、阈值、窗口、交互、品种分组、模型、目标、权重或风险来补救。也不据此宣布所有期权信息无价值。没有一项新金融预算获得批准，不恢复 DOMAIN52、FX、曲率、数量/仓单/会员包、旧 regime 门或 Triple Screen。

## 官方来源实测：可访问，不等于历史首发资格

最小原始载体是以下两个 CBOE 公开日文件；日期为**美国指数观察日**，单位为年化波动率百分点，消费应限于 CLOSE，不能拿 OHLC 当 SPX 可成交价格。

| 文件 | 当前实际访问网址 | 亲读首行 | 尾覆盖与快照状态 |
| --- | --- | --- | --- |
| VIX | [VIX_History.csv](https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv) | `DATE,OPEN,HIGH,LOW,CLOSE`；1990-01-02，CLOSE=17.240000 | **尾行未核，不认证末日或连续无缺**；Last-Modified=`2026-10-17 01:11:02 GMT` |
| VIX3M | [VIX3M_History.csv](https://cdn-api.cboe.com/api/global/us_indices/daily_prices/VIX3M_History.csv) | 同五列；2009-09-18，CLOSE=26.540000 | **尾行未核，不认证末日或连续无缺**；Last-Modified=`2026-10-16 21:31:06 GMT` |

原始请求使用 `https://cdn.cboe.com/api/global/us_indices/daily_prices/{ticker}_History.csv`，均重定向上述 `cdn-api`。2026-10-19 20:34 CST 对每个文件各发一次 `bytes=0-1023` 和一次 `bytes=-1024`；四个逻辑请求均返回 200、没有 Content-Range。首部读取上限严格为 1,024B，suffix 返回 200 后 body 读取 0B 并停止。沙箱内此前四个逻辑请求仅 DNS 失败，0B；随后受控公网只读访问成功。网页工具直接打开 CSV 返回 Internal Error，未把错误页当成数据。

这是有意保留的覆盖未知：Last-Modified 只说明当前对象修改时间，不能证明末行日期、行级首次发布时间或某历史日 08:00 已经可得。不能把“2026-10-16 是最近美国交易日”当成已读到该尾行，也不能用旧 VXV 的 2007 起点冒充当前 VIX3M 文件。当前 [CBOE 历史页](https://www.cboe.com/tradable_products/vix/vix_historical_data)明确将 VIX 文件列为每日更新；[2026 年期限指数方法](https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Selected_SPX_Target_Expected_Volatility_Term_Indices.pdf)第 7 节同样记 VIX3M first value 为 2009 年 9 月。未核得整段连续性与末尾，不签源数据验收。

## 定义、时钟与泄漏边界

[CBOE VIX 方法](https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf)将 VIX 定义为 SPX/SPXW 期权报价形成的未来 30 天美国股票波动率；上述期限指数方法规定 VIX3M 为 93 天，使用另一到期区间的 SPX/SPXW 期权。两者均是风险中性隐含波动的指标；VIX/VIX3M 是两个隐含期限的相对形状，**不是**隐含风险中性方差减去物理期望方差，也不等于方差风险溢价。

现行方法文件分别修订于 2026-02-26 / 2026-03-04，其 RTH 传播表均列终点 **16:15 America/New_York**。美国日 d 的该时刻对应上海次日夏令时 **04:15**、冬令时 **05:15**。旧 [2021 DataShop 通知](https://datashop.cboe.com/new-product-launch-high-level-option-sentiment-10222021)曾写 16:16，属于特定产品/版本历史，不能倒替当前方法，也不能解释为日 CSV 的统一上传 SLA。

本线将来若单独做来源资格，最低保守合同应是：用真实 America/New_York 时区转换；在上海次日 **08:00** 之后且**该快照确已收到**时，才允许使用完整美国收盘。08:00 是研究的保守候选门，不是本文已经证明的 CBOE 发布保证。历史归档没有行级 received_at 时，只能标记“最终归档＋滞后假设”，不能晋级 strict PIT。节假日用最后真正收到的美国源日，并保留源日及年龄；缺数据不填 0，不因美国休市删除中国母体。

例如中国 2026-10-19 15:00 的原信息集，至多使用已收到的美国 2026-10-16 收盘；美国 10-19 收盘要到中国 10-20 凌晨才形成。不能按相同日期 join，也不能因中国交易日 D 的夜盘在前一自然日晚 21:00 开始，就把 D 当日上午才收到的美国收盘回灌到夜盘起点。现有事件若在 u 日 15:00 冻结，之后收到的数据不可借“下一个 D 日开盘”提前进入该事件；不为 VIX 更改原决策时钟。

## 已有字段、信息新意与模型可表达的对象

只读核对 `tools/stage129_contract_choice_dataset.py` 的 OWN/MATURITY/COMMON、`stage130_contract_choice_fit.py` 的 52 维 FEATURE_NAMES 和加性 Ridge 预测，以及 `stage009_day_proxy_dataset.py` 的 market lag 构造，路径均相对本线。

| 已有对象 | 与本候选的关系 |
| --- | --- |
| COMMON52 | 26 个国内自身 OHLCV/期限/成本距离值及其 26 个 missing；没有 SPX 期权价格、VIX、VIX3M 或物理美国方差预期 |
| 旧 market4lag/regime | 国内排自身 family 的滞后收益中位数、正收益广度、IQR、missing；Stage013 固定包关闭。不是期权观测，但公共环境门的经济用途有重合 |
| Stage146–150 FX | ECB 公开汇率变动观测，固定包未通过；汇率水平/变动不决定 SPX 期权保护价格，不能从 FX 失败推出 VIX 已测失败 |

固定全部上述国内 OHLCV、期限和 FX 路径，SPX 期权报价仍可因全球尾部保险需求、预期方差、交易商风险承载变化而不同，因此 VIX 不能被这些输入**唯一代数恢复**。国内市场也可能已经共同计入这些变化；不可恢复性不证明剩余可预测收益，更不证明它在中国开盘之后仍未计价。

相同决策 cutoff 下，VIX 或期限比值是所有 action 共享的 q(t)。在一个给定加性头内：`s(i,t)=a+β·X(i,t)+b·q(t)`，故同 cutoff 的 `s(i,t)−s(j,t)=β·[X(i,t)−X(j,t)]`，新增 q 直接项抵消。它直接提供公共时点偏移与正分准入影响，不能直接表达相同风险冲击下不同 family 的异号反应或 query 月份特有价值。**如果重新拟合，β 本身可能变化，故不能声称新旧模型排名一定相同**；但这种重估变化也不等于已经识别出 VIX 的异质传导。为了让它表达异质性而再加 sector 交互、暴露估计或阈值，已经是新的多轴设计，本文不推荐。

## 原始研究与 GitHub 核证后的取舍

- [Bollerslev、Tauchen、Zhou，2009 原论文摘要](https://academic.oup.com/rfs/article-abstract/22/11/4463/1565787?login=false)研究隐含与实现方差之差，对美国股票季度附近收益较强；[Fed 的早期作者稿](https://www.federalreserve.gov/pubs/feds/2007/200711/)可读。支持的是 VRP 的特定收益预测，不能把 VIX 高低或 VIX/VIX3M 当成同一变量。期刊正文抓取失败，未声称重读全文。
- [BIS Working Paper 619 作者原文](https://www.bis.org/publications/working-paper-619-volatility-risk-premia-and-future-commodities-returns.pdf)，印刷页 2–6：商品货币 VRP 的证据有危机后时期限制，黄金 VRP 加控制后主要限于贵金属，油相关结果对控制敏感。其预期物理波动代理另有测量误差；作者明示全样本 HAR 参数有 look-ahead，不能把该实现原样当历史 PIT。论文没有证明 VIX 比值对中国所有期货同号有效。
- [BIS 的概念说明](https://www.bis.org/publications/volatility-concepts-and-risk-premium)进一步要求比较相同期限的隐含波动与实现波动预测，才能分离风险补偿。VIX 上升既可能代表更高物理不确定性，也可能代表保险更贵，两者对后续收益与短期路径的含义不同。
- 核读 [datasets/finance-vix 的 Makefile](https://github.com/datasets/finance-vix/blob/main/Makefile)和[维护者 process.py](https://github.com/datasets/finance-vix/blob/main/scripts/process.py)：前者直接取 CBOE 日 CSV，后者主要转换日期并派生月末。它们证实简洁来源链，**没有**美国收盘到中国含夜盘事件的 received_at、历史 vintage 或中国 long alpha 资格。
- 核读 [vix_utils 维护者说明](https://github.com/dougransom/vix_utils)：来源是 CBOE cash/futures 历史，文档承认少量缺日并建议 fill/skip。这种通用建议不符合本线的完整母体与未知保留纪律；未安装、复制或运行代码。

经济判断：短期保险需求集中可能先压低风险资产现价，而更高风险补偿又可能对应较高的中期预期收益；由“恐慌高”直接推“禁做多”或“应抄底”均缺时间尺度。中国工业品、贵金属、农产品、股指和国债对需求、供给、利率、人民币及避险冲击的暴露不同；这里是机制上的反例，不是本稿新估计的相关系数。一个全球风险标量没有为全 family 给出统一 long 符号。把它定位为尾部风险背景或监测信息有解释价值，但不能因此进入本线 alpha、加注或公共禁入门。

## 最小 probe 与明确停止标准

**当前建议停在本评估，不跑新增金融，也不因尾行未知扩大历史采集。** 若后续有与交易研究分离的数据服务需求，唯一可以事前另签的小 probe 是：未来固定连续 7 个 CBOE 交易日，在上海次日 08:00 保存两指数的实际接收时间、源日、末行与内容摘要；覆盖一个美国节假日/夏冬令时的机械时钟 fixture，禁止读 Y、选事件、训练、现金或调规则。它只回答小样本发布可得性，不能认证全部历史；不自动创建监控或调度。

停止条件预先固定：

1. 源日/期限/正值语义或实际 received_at 不能核清，立即不接入；用 Last-Modified、日历推定或延迟假设冒充首发资格，立即拒绝。
2. 经济假说仍只是“VIX 高/低适合全市场 long”或“比值超过某阈值禁入”，没有独立于已见收益的异质暴露与明确时间尺度，停止于机制；本轮已经触及此停止条件。
3. 只有换标量符号、百分位、窗口、family/年份、交互/模型、D/K、target、weight、止损或风险后才有故事，关闭本提案，不从中另挑赢家。
4. 7 日来源 probe 即使全部准时，也不获得 fit/cash 权限；若唯一新增价值只是公共环境门或原 COMMON 系数重估，不能把它包装成已证明的新高质量信号。

本稿不从“否决 VIX 简单包”转列一串其他全球指标。真正 VRP 需要匹配物理预期、期限与时钟，是另一研究对象；目前不提出其数据工程或金融实验。

## 结果、反思与合入

- 新增/修改/删除代码、模型、交易参数及回测结果均 0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部 **N/A**，不复制旧结果冒充本阶段成绩。
- 开始/结束新增按结果调参过拟合：**否**，只读来源与机制，没有新收益筛选；多轮同一历史选题与事后叙事选择风险：**是**。收益前冻结不能消除这项累积风险。
- 开始继续价值：**是**，小范围核证能区分“新观测”和“强机制”，避免再次弱标量续包。
- 结束继续本 VIX/VIX3M 金融方向：**否**，机制和表达方式不足；继续扩展本报告/历史采集：**否**。完整全市场高质量做多目标仍有条件值得继续，但本稿未提供新的可交易候选，未完成整体目标，也未获得晋级/加注资格。
- 本阶段无回测，因而不新触发回测后金融复审；本文件本身是独立于 root 的来源/逻辑评估。合入者可记录“期权观测在 COMMON/FX 外，但简单 VIX/期限比值包被设计阶段否决；官方源首部已核，尾覆盖及历史首发仍未知”。不写成“VIX 被历史回测证伪”或“已取得全球风险 alpha”。
