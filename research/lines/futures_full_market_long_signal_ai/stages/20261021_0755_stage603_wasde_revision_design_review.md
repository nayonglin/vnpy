# Stage603：US Corn同作物年Production修订独立设计审查

- line_id：`futures_full_market_long_signal_ai`；2026-10-21 07:55 CST。先读registry，实读本线601及274/275/284/289五份小stage、275提取源码；不扫其它旧研究，不重复597。
- **结论：新观测成立；只支持完成已授权的相邻报告配对源诊断，不建议现在直接再做2个scalar fit。当前金融NO_GO，源诊断后默认收口，不自动晋级。** 非重要突破；新增fit/cash/SQL/行情或历史WASDE大下载全部0；原累计547fit/286完成cash＋1旧partial不变。

## 区别是真的，但不是收益证据

旧289关闭的是World Corn当前Proj的Ending Stocks/Domestic Total水平及其固定单scalar offset；两个cutoff系数后完整执行身份不变、Corn分数全负且0参与，原4cash跳过。US Corn Production的跨独立发布、同MY修订是新的供给预测更新，不能由旧单时点S/U唯一恢复。它不等同于把旧比值差分、改符号或有效期救分；也不能仅因“修订”名字新就重开旧level包。

本次真实浏览[USDA ERS原作者2021总结](https://ers.usda.gov/amber-waves/2021/december/usda-s-corn-output-projections-inform-futures-price-movements)：其美国玉米期货研究涉及1999–2017，生产预测信息效应因月份而异，May为新作预测起点。该证据支持研究对象有经济内容，不能证明两日后DCE.C窄损long净收益。[USDA原始中国进口研究](https://ers.usda.gov/publications/104540)强调国内外价格受非关税措施等阻隔；此处仅据此判断传导有条件，不引用旧年价差作为当下数值。Production上修也不是相对市场共识的surprise；天气/价格/NASS等信息可能已经反映，供给冲击到中国价格的方向与时点不能当恒等式。

映射仅DCE.C保留了经济边界，却限制了全98/95目标的潜在增量。原Corn全负不是“任何新信息必无效”的证明；它说明若最终仍无新参与即可按完整身份等价免现金，不能放大gamma、降低原门或改两日lag硬造交易。现有证据不值得为了凑新fit直接再拟合。

## 58是容器数，尚不是新pair月数

289的58个原件包含2个历史汇总ZIP；其旧合并报告183、旧quantity eligible172。275前47个容器已包含172报告。因此“最多58个月报告”不是目前可证事实；US Production的新有效pair数本603保持unknown，等待602一次源投影。两次独立发布记录可以在同一官方ZIP中，不能机械要求每月单独物理文件而重下载全部档案。

真实信息单元是唯一release pair，不是DCE.C的日、候选期限或重复合约行。相邻修订共享一个端点；同一MY内的天气/预测更新相关，因此pair计数也不完全独立。需列每年、MY、公告公历月、零/非零及缺失原因。不以零修订充新增信息，也不丢掉合法0。若最后确实只有约58个pair且集中少数MY，一条斜率数学可解不等于跨周期功效足够；只适合一次严格有限的反证，不能称稳定优势。没有一个脱离MY覆盖、非零变化和成熟标签支持的普适“满N即合格”月数门，本603不补造阈值。

## 最小源合同的必要澄清

唯一对象仍为US Corn / Production /同单位Million Bushels；`x=(P_r−P_prev)/P_prev`。**先选当前报告最高目标MY，再要求前一自然月同MY且双方均精确Proj**；不能从“最新共同MY”回退旧作物年填新作首次缺口。当前最高MY为Est、上一月未出现该MY、缺相邻月、单位/字段有冲突、分母非正均unknown；不能跨季强接或补0。MY不是DCE合约到期年。每个值的ForecastYear/Month必须对应各自release，不能拿当前报告的上月回顾列当上份原值。

May新作首次预测和Proj/Est轮换会形成可预知的季节缺失；后续生产多月不变仍是合法0。这种机制性可用域不能被解释为随机缺失。只诊断公告公历月×MY的覆盖和非零分布即可，本轮不铺12个月交互模型、不同阶段参数或新窗口。若将来另批金融，一条known域常数只控制“有资料月份”的平均差，不能单独证明排除了known域内部的季节混杂；应披露按公告月/作物年聚合的效果与是否单年集中，不把该限制隐藏成已识别的供给因果。

## 官方vintage足以做条件历史重建，不能等同首发字节

本次实读[USDA Historical WASDE Report Data官方说明](https://www.usda.gov/historical-wasde-report-data-3)：数据保存各报告发布时所见信息、排除之后底层系列修订；单份publication仍是official record。故不能把后出的汇总ZIP一概叫最新回填PSD，也不能因为缺逐字节first-print证明就永久堵住历史研究。显式release/Forecast年月/Proj/MY及源trace可支持**条件历史vintage重建**，不授历史first-seen/PIT首发认证。

[官方errata](https://www.usda.gov/historical-changes-revisions)确有报告重贴。已知晚更正影响本Production字段且更正时点未知，阻断对应pair；相关范围也无法区分则保留unknown。官方明确只改其它作物或讨论文本、目标数值未变时，不应自动废掉整份US Production。当前无V2后缀也不能独自证明没有修改。后更正不得回写成早期alpha；也不为此铺20年bit级首发工程。

## 时钟与唯一值得做的下一步

[官方发布页](https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/commodity-markets/wasde-report)当前列12:00 ET及汇总CSV翌日更新，但历史时刻并非一直相同。冻结的release date＋2自然日、America/New_York 00:00可作为条件历史的主动延迟界，使用IANA/DST而非固定EST。仅边界后完成的原中国u可消费，再到其后D；不把公告信息回贴u之前，不预测紧接公告的夜盘。它足够支持这个延迟日级问题的保守时序假设，救不了错误release日或未知晚更正，也不证明两日后仍有可交易信息。

本603仅建议602交一张有限pair表及支持摘要：唯一release/version/MY、两端原值/单位/原trace、当前Forecast年月、合法0/非0、逐年/MY/公历月计数、缺失原因、两日延迟界与能否落入原u。**不读取收益矩阵、标签或行情就能完成，0fit/cash。** 不另下载报告、扩其它作物/国家或再修原包。若无法恢复两次独立发布、存在目标相关未知时点更正、实体/单位冲突不可解、无有效pair或训练可用量全相同，则在源层停止相应pair或整条候选。来源通过仅表示可构造；不自动开启新head。

维护者[wasdeparser源码](https://raw.githubusercontent.com/fdfoneill/wasdeparser/master/wasdeparser/parser.py)已实读，月份回落月首及硬编码页格不能用于公告日期或vintage认证；本603不安装/运行。官方档案目录也只作小页面核，不新抓原报告。

## 记录与反思

新增/修改/删除策略参数、模型和金融结果均0；权益/总收益/最大回撤/Sharpe/总滑点/交易数/胜率全部N/A。机器结论见`outputs/stage603_wasde_revision_design_review/decision.json`。只写本唯一stage和603自身输出，不改LINE/registry/正式或其它agent文件。

开始/结束是否按新收益过拟合：否，没有新收益或拟合；长期同史择题风险仍是。是否有价值继续：**只完成已经授权的一次源配对诊断有价值，立刻再训练无优先价值。** 新观测物理可行不等于值得不断消费同史；全市场高质量long目标仍active，未授正式/生产/增加注额资格。


## 2026-10-21 07:57 CST：602小输出有限独审及样本判断更新

root通知602终态后，本603对其summary、report/cells、JSON/CSV pair、support及inventory共7个小输出各一次读取并存603派生缓存；未读58原件、行情、标签或大缓存。随后在派生数据独立核6318断言，critical=0、important=0。首次审查器只认ISO日期遇到已文档支持的US日期literal停止；仅适配两种显式格式后从603派生缓存继续，未重读602或原件、未更改来源。

确认183独立release/月、549个明确US Corn Production当前Forecast年月cell，均同Million Bushels/Annual/空ReliabilityProjection；每份恰1个Proj且其MY是本份最高MY。独立按**当前最高MY先选、再匹配上一自然月同MY**重建，得到162个内容pair，与602的latest-common计数完全相同；未来必须固定不回退，不能据本次巧合省略合同。所有pair两端WasdeNumber不同，逐份Forecast年月各对应自身release；没有拿当前回顾列冒充上一份发布。

计数：199月grid=162内容pair＋16 current report缺失＋4前自然月缺失＋16 MY/Proj轮换＋1首月。162中合法0为70、负47、正45；剔除可见V2影响后160、0为69/负47/正44，覆盖17个MY。发布日分段条件源pair：2020前102、2020—2022为33、2023起25；这是source支持，**未经过原训练成熟/标签/实际DCE.C映射，不能称102/135训练样本**。相邻pair共端点、多个发布落同MY，162也不是162个独立经济周期。

校验两端完整JSON证据均能对应549cells及report，继承source path/hash/member/CSV数据行/物理结束行/Value列（第11列），无空值冒充数值。pair CSV的两个evidence列在有效pair中共324格为空；完整calendar JSON中324个端点对象已逐一对应原cells。这是交付表示限制，不能引用空CSV格当原行证据；源证据在JSON，本轮无需为此修作者输出或重扫raw。原件SHA继承下载manifest，本603没有重新逐值认证58raw。

可见2026May/June V2不等于已证明Corn字段被改。官方May更正明确为Wheat by-Class，不能称Corn真实矛盾；June V2范围/时刻仍unknown，使June及July两pair暂unknown，因此仍保留160条件支持，不需要重扫其它errata来救两格。162都不是bit级PIT认证，此限制不否定官方as-reported语义。

**新的样本结论**：不是最多58个月，而是有160条件pair/17MY，足以讨论一次低容量、按唯一报告对及作物年分组的反证设计；本603不再以样本只有少数年份否决该对象。并未证明值得立刻训练：现存2/3/4/12月pair的Production变更全部为0，May因新MY首次出现无pair，June多为0，其余非零集中某些生长/估产阶段，季节/缺失混杂实质存在。不能把日/合约重复行做新N，也不能只给known域常数便宣称隔离了具体月份效应。root若继续，应先冻结报告/MY分组和季节/缺失域对照的单项增量设计，不预授fit、不得改gamma/threshold/lag救Corn参与；完整98/95母体与unknown不缩。

本轮最小源诊断已完成，接受**条件源可构造**；直接重复原2scalar日复制头仍不建议。US Corn修订对象不永久关闭，金融暂缓亦非生产审批要求。新fit/cash/SQL/大原件/行情读取均0。最终机器结论更新在decision.json及602_small_output_review.json；只补本唯一603记录，由root604决定后续设计。
