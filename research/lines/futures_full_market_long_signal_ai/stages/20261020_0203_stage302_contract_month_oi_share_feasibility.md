# Stage302：真实成交月份池的滞后OI份额，条件GO的单一信息反证

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-20 02:03 CST。
- 性质：只读科学开题，非重要突破、非正式A/B；不授权实施或actual。
- 先核registry及本线078/084/089/127/129/143，随后只读相关源码小段和Stage266 README/小manifest。0采集、0 SQL、0全OI/标签/NPZ/结果大表读取、0训练、0现金、0实现；只新增本文，不改LINE/registry/旧source。
- 开始反思：新增按成绩调参数否，同史多轮择题风险是。继续查清信息差有价值；不能因为有新列就GO，也不能把所有可用参数都必须“唯一最优”作为开题门。

## 判断

**条件GO，仅保留一个窄命题：在原52背景与原全月动作域下，候选合约在前一完整源日、同产品accepted真实成交月份池中的OI份额，是否具有原代表合约净变化/V没有检验过的选月信息。** 只允许这一个量，不添加log、V分母、近远月、滚动窗、排序/阈值或OI方向口诀。这里GO指有一次有限可证伪研究的实质理由，不是当前actual授权或预测力结论。

**不支持更强版本**：“全交易所全部上市月份OI份额”“真实资金迁移”“净多买盘”。现有源不支持前者的完整分母，总OI也无法识别后两者。若必须回答这些强问题，应在此NO-GO，不以补源/补资格工程将本提案延长。

## 有界一手调研与经济先验

本次2个搜索query、2个独立原文URL；不再扩展检索、下载代码或采样数据。

1. [Hong、Yogo，2012，What Does Futures Market Interest Tell Us about the Macroeconomy and Asset Prices? 原文版本](https://www.nber.org/system/files/working_papers/w16712/revisions/w16712.rev1.pdf)。检索核到原作者、JFE发表信息与摘要；PDF入口及定位未取得可核方法段，故不假称全文复核。其聚合OI与经济活动/资产回报的动机，不等于单产品选月或日级long方向证据。
2. [Harrison Hong，2001，Stochastic Convenience Yield, Optimal Hedging and the Term Structure of Open Interest and Futures Prices，作者原文](https://www.columbia.edu/~hh2679/hong-futures.pdf)，36页，已读标题、摘要、引言及关键命题段。便利收益风险和套保期限可以改变OI在各月份的分布；近月/远月同时持仓也可用于对冲基差风险。它为“分布包含不同经济状态”提供先验，没有推出高份额月份的long收益更高或回撤更小。

因此，这一假说的依据是**不同交付期承接的存续风险与套保需求不完全相同**，不是“增仓即买盘”。每张未平仓合约同时有多方和空方；OI份额是匹配合约存量的相对分布，不是资金金额、主动买入、参与者身份或净多头。即使份额变化，纯平仓、到期、跨期spread、对手方替换及新开都可能造成相似结果，不能从日终横截面识别谁把资金从一月移到另一月。本轮不选择迁移量或近远月定义。

全98中金融期货和不同商品机制并不相同，不能由商品便利收益模型保证统一符号或全域有效。仍保留全域和family held，让训练外结果证伪泛化；不因先验较弱而只挑某类商品试。

## 历史去重：旧实验实际覆盖到哪里

| 证据 | 实际消费/动作 | 对本命题的约束 |
| --- | --- | --- |
| [078](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261018_1712_stage078_open_interest_information_feasibility.md)、[084](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261018_1739_stage084_oi_information_protocol.md) | 原004代表epoch e，`[OI(e,u−1)−OI(e,u−2)]/V(e,u−1)`；不预设符号 | 同一delta/V换窗口、分母或对子月重算，不因此成为新观测 |
| [085实际源接口](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage085_oi_projection.py:198) | SQL虽扫全期，205行needed只含每个母行原代表e的两lag键，212行丢弃其余；只消费该标量及共同missing | “曾扫描全OI”不等于模型使用过全月份分布；不能用SQL范围扩大旧金融结论 |
| [089结案](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261018_1806_stage089_oi_information_cash_decision.md) | 固定日级OI/54槽Ridge/NARROW包，12fit/8cash，未支持增量并关闭 | 停止条款保留，不复活价格×OI确认、阈值、加注或旧delta/V包 |
| [127选月开题](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261018_2116_stage127_contract_action_space_science.md)、[129](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage129_contract_choice_dataset.py:162) | 允许原母事件下的真实候选月份；不是只交易代表，anchor仍固定u canonical | 当前决策是初开买哪一真实月份；不改自由续持、动态换月或母域 |
| [143范围结案](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261018_2338_stage143_scope_and_oi_dedup_decision.md) | 明确保留“旧代表实验未检验全子月OI排序”边界，但不凭扩域自动授权 | 新理由必须是跨月份**存量分布**与选月对象的结合，不能仅说新母体或当前52没列 |

这是既有OI源的一种此前未消费的联合观测，**不是新下载源，也不是全新OI通道**。旧负证据降低先验，并没有实际否决这一具体份额信息。该结论是本次指定范围的有界去重，不声称穷尽仓库全部历史策略。

## 信息差与代数反例

[129 COMMON定义](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage129_contract_choice_dataset.py:28)为自身价量11项、期限**价格**13项、成本/止损距离2项，130再加相应26 missing。没有OI水平、总OI或跨月份额。原代表曾用OI作成交量相同的tie-break，不能因此恢复整条OI向量；固定最大V唯一的例子可排除这个间接选择因素。

纯代数例（不是读取真实数据）：两个月份A/B的价格、V、期限COMMON和身份完全相同；前后两源日OI分别恒为 `(100,100)` 或恒为 `(100,900)`。A的旧delta/V在两种世界均为0，A自身两lag OI也相同，但其同池份额分别1/2与1/10。两者都可保持A为唯一最大V代表。故旧代表标量、其有限投影、当前52和OHLCV缓存不能唯一重构新量。即使旧delta/V曾扩到所有月份，两个恒定水平世界的delta仍均为0。

反例只证明观测不可恢复，**不证明统计独立、可预测或增益为正**。份额可能主要反映已被V/期限价格间接表达的流动性、到期周期或机械换月，也可能只是噪声；这些正是一次有限比较要承担的失败风险。即使成功，也不能归因为已识别套保需求或因果资金流。

## 唯一量与实际源分母

对原129动作 `(product p, query epoch e, u)`，令v为原冻结source-calendar的 `u_index−1`，不是自然日前一天。冻结：

```text
P(p,v) = clean中产品精确为p、交易日精确为v、quality_status=accepted且finite volume>0的月份行集合
T(p,v) = sum(close_oi(j,v) for j in P(p,v))
q(e,u) = close_oi(e,v) / T(p,v)
```

- `p`含交易所和精确普通/F产品身份，epoch保留完整YYYYMM；不把普通/F合并为份额池，family只沿原预算共享。不能按当前或未来主力筛月份。
- P包含该日源中全部accepted真实成交月份，不以当前u动作资格、20ready、容量、经济是否可交易、D有价或最终标签闭合作分母筛选；也不只取将来被选月份。池只有一个月不另设排除阈值。
- [Stage266 README](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/README.md)明确其记录为真实成交日线，零成交填充、争议和非法源记录被排除。因此P不是“所有上市合约”，池外未观察月份OI状态未知，**不得当OI0、不得carry补入、不得声称得到交易所总OI**。本次接受这一较窄估计对象，不补零成交月或全上市生命周期目录。
- P内任一行OI非有限/负数、单位或来源不获既有合同接受，**整组(p,v)的q unknown**；不得将坏行置0或只drop坏行后缩分母。P为空或T≤0同样unknown。该规则不依据收益，也不要求补源才能继续。
- query e在v不属于P，则其q unknown，即使u新出现或其它月份可见，也不将它填0。e有真实OI0且T>0，q=0合法；这与missing不同。无额外log、截尾、归一排名或窗口。
- 同日跨月可来自不同已接受来源，但必须各自满足同一canonical单边单位合同；不能因source不同再除二，也不能猜未知factor。只继承固定Stage266转换和隔离结果，不重建旧raw资格、拼列或撤销隔离。

以上只冻结数量语义，不通过本阶段读取全OI证明每组覆盖。本次未做SQL，不能报q可用率、新缺失计数或后验挑覆盖好的family。

## 时点、输入依赖与有限比较边界

lag1继承084对日终发布的保守研究约定，不使用u当天尚未发布的收盘OI；日期沿原source-calendar，不跨代表/合约差分，不等待下一条存在的bar代替v。归档源缺首次发布/修订链，滞后一天也不能变成严格PIT证明；该限制沿旧研究保留，不为这个小量另铺时钟工程，更不授生产资格。

旧缓存不足以直接产出q：[132读取](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage132_contract_choice_review.py:185)的values明确是OHLCV五列，[缓存持久化](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage132_contract_choice_review.py:735)没有OI。085旧投影只保留canonical两lag needed键。accepted SQLite schema则已有`contract_epoch_id/exchange/trade_date/close_oi/volume/source_id/oi_factor/volume_factor/quality_status`，sources提供来源family，完整p可由epoch恢复；无需新下载或labels。

**若root以后授权**，最小增量是一次必要OI窄字段源流生成按原action_sequence_index对齐的q/available，随后原130六scope×cutoff各自最多一项scalar残差解。不能把本阶段当成那次读取或拟合的授权。所有旧52系数/intercept、各fold旧scaler、原成熟行与权重/Y、alpha1均冻结；只在该fold训练内对finite q标准化并拟合残差的一维线性系数，不加新intercept或learned missing。无q的external z=0，严格回到该fold旧52分数；已观察q=0按合法观测处理。

对照为原130纯COMMON52的同全域选择/现金接受产物，不能拿已失败084、DOMAIN52或K_TARGET52作为可挑较弱基准。六fold的系数方向各自由训练决定，文献不提供统一正负方向；不因方向不合口号改q、只留某折或扩大模型。该低容量设计只检验加性线性增量，失败不证明一切OI分布机制无效，但关闭这一固定份额包。

完整98目录产品、399252母域与全部129子动作身份保持；全1,933,480前向scope分数仍部署到原2020/2023区间，主161014和原held两个family组都保留。q unknown不是删预测/拒绝交易门。原156先D<K再positive与选月、anchor/容量/费滑/0.25N/资金核全部不变，不限旧已选集合。

最多6个scalar fit、候选自身最多4cash的完整经济反证可在以后另冻协议；不重训旧52或重跑旧控制。全域动作身份相同可等价停；动作变化时，held原语义诊断与现金应分别报告，原first-exit R不能替代共同K资金收益/DD。不同动作payoff unknown保留unknown，同动作未决的共享增量0另列；family-u后equal-u，不能只取已知交易交集。失败不扫窗、变分母、补近远月/迁移量、加missing或换模型救参；不因高份额能筛薄月而宣称窄损安全或加注。

## 记录与结束反思

- 已见registry当前线的结案摘要，不能称完全收益盲；本次未打开296/297模型、分数、账本或新金融产物，也未以该轮成绩选择OI公式。旧089结案只为范围去重，不复制为本次结果。
- 新增参数实施/策略/数据/回测结果均0；期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率N/A。无新回测，无本阶段金融独审运行；以后若actual须由独立agent核源、数学、全域/held和现金，不把本开题当独审接受。
- 结束过拟合判断：历史适应性选择风险是，本阶段按新成绩调参数否。旧OI失败给低先验；不可恢复的新增分布观测仅够一次窄反证，不能预许成功。
- 结束继续价值：**上述受限份额信息问题有；全上市OI/净多资金/迁移强解释或旧delta/V重试没有。** 完整用户目标仍active，未证明穿越周期、窄损封顶、低DD或增加投注资格。本文无actual授权、不更新LINE/registry。
