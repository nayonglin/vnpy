# Stage197：现成 COMMON52 与共同 K 基准有界盘点

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-19 18:31 CST。只读元数据盘点，非重要突破，不触发新A/B。仅新增本唯一stage和小inventory，不改LINE、registry、195/196、根总账或其他研究线。
- 目的：避免下一步重复训练或现金，固定可比基准身份；不评估新alpha或收益，不按收益挑选旧基准。实际新增fit/cash/预测/选择/标签/SQL/下载均0，累计 **421 fit / 226 cash**。

## 结论

**已有准确可比的“不含后添登记/会员来源missing的COMMON52”模型及完整冻结分数，不需要再训练。已有共同155 K下的main choices与4本现金，也不需要为建立这一旧基准重复现金。** COMMON自身仍含原26列missing，且原COMMON26内也有期限缺失状态字段；不能称为无缺失、无代理或无PIT风险的模型。

1. Stage130实际完成6个纯52模型（main/held0/held1 × 2020/2023），portable_model/scaler及完整child_scores/原A/B choices均存在，已接受132算术独审C/I/M=0/0/0。A/B共享模型；A限canonical，B从所有原u合格月取最高正分，再作原ordinary/F family优先。
2. Stage156 **直接消费130同一child_scores SHA** `e94b4d3d…dbae8457`，完整main966740个child先D<K再原排序重选，未重训、未重新预测、未改原129目标。choices_main SHA `cce87a00…6fd9ddd`；完整161014父行保留，2020/2023段分别71344/89670。K后选择数2613/1752只用于核身份，不是收益表现。
3. Stage157 manifest明确绑定同一156 choices、156 manifest及130 fit manifest，实际4本分别为2020连续/2023独立冷启动 × base/stress，fit=0；metadata continuation新现金0、原金融输出不变、financial_recalculations=0。158已精确绑定此157 manifest与156 manifest，completed/research_arithmetic_accepted=true、C/I/M=0/0/0。本阶段未读账本或重算收益。
4. 限定链路中，**纯52的held-K choices未发现现成文件**：130有完整held分数与无K choices；156只作main K；167/190有held-K choices但它们各含后添来源missing。这里不补选择、模型或现金。

## 六折语义核对

130、167、190的dataset/actions/common/mothers四项binding完全一致，指向同一成熟129数据。三者使用同一冻结130 `fold_slices` / `training_weights`；相关当前小源码与manifest绑定匹配。原u可行动、标签closed_complete、u及label_known_date严格早于cutoff、net_R_stress有限；held按sha256(family_id)模2分组并从训练剔除对应组。权重仍是family-u区间并集的concurrency/uniqueness、动作均分、等u；目标仍为原first-exit stress R，未按K重标。

| scope | cutoff | 成熟训练动作 | family | family-u组 | 前向child | 前向母行 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| main | 2020-01-01 | 247795 | 69 | 82929 | 366634 | 71344 |
| main | 2023-01-01 | 445475 | 77 | 125955 | 600106 | 89670 |
| holdout_0 | 2020-01-01 | 171712 | 44 | 55688 | 138837 | 28392 |
| holdout_0 | 2023-01-01 | 297404 | 47 | 82519 | 249829 | 35685 |
| holdout_1 | 2020-01-01 | 76083 | 25 | 27241 | 227797 | 42952 |
| holdout_1 | 2023-01-01 | 148071 | 30 | 43436 | 350277 | 53985 |

三阶段以上六折训练/预测元数据一致；各折COMMON scaler的columns、mean、var、scale、finite_count **逐值完全相等**。130每模型系数和feature_names都恰为52，Ridge alpha=1、intercept=true、cholesky。2020模型只预测2020≤u<2023，2023模型预测2023≤u≤2026-10-16。130原52=COMMON26标准化＋26原nonfinite标志，无新增会员/登记来源槽。

`weight_groups.csv.gz`等压缩文件的跨阶段SHA不同；本阶段不读其内容，不断言文件字节相同或SHA差异的原因。语义核对依托同一已接受源binding、冻结函数、相同六折身份摘要与全部COMMON统计，不冒充新一轮大表逐行审计。

## 不能混用的控制

- 167 CONTROL54为COMMON52＋member_concentration_missing＋恒0末列；190 CONTROL54为COMMON52＋registration_missing＋恒0末列。各自missing可学习，main2020对应系数约0.152106和0.177589，非纯常数扩展。两者不能作为统一纯52分数基准，也不能只将冻结54的missing输入或系数归零就声称得到原52训练解。
- 原COMMON中`q_missing`等是既有期限控制字段，名称不代表后添会员/登记missing；本盘点没有删除原COMMON中的missing。
- 130原choices及131现金没有155 K；共同K已经由156选择和157四本实现。K是合约月前一月首个源日历交易日，全池先过滤再argmax；现金还应用K退出，原模型与标签不变。K仍是not_certified自愿政策，不是历史法律/券商截止认证。
- 最接近链路未发现另名CONTROL52或只追加常数0的单独模型；130已有纯52，无须为名字或冗余常数重训。固定旧基准不依赖收益择优，既有失败结论不被抹掉。

## 小binding与验证范围

[小inventory](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage197_common52_baseline_inventory/inventory.json)保存130/156/157/167/190 manifest、六折模型/scaler的完整path/bytes/SHA、已接受132/158 receipts、共同数据binding、冻结源码核对与157四户目录。大分数/choices只沿原manifest引用并检查存在/尺寸，不读内容、不重新hash。130 manifest SHA `7798d9a3…cd6e1fc`；156 manifest `131bdcfb…0dbef12`；157 manifest `0c27edef…e34c7a4`；完整值见inventory。

本次只在JSON元数据和必要源码片段中核对模型维度、成熟边界、权重函数、共同scaler及K输入链；未扫描全库、读取行情/价格/大CSV/收益、hash大文件、训练或重跑选择/现金。新增/修改/删除参数0；新增/修改/删除回测结果0；权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率本阶段均N/A，没有新金融结果。原132/158/169/192接受不自动变成晋级或目标完成。

## 调研、反思与继续价值

外部资料复用本轮root已完成的官方与GitHub调研，以及190记录的[scikit-learn加权Ridge官方定义](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.ridge_regression.html)和[维护者源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/linear_model/_ridge.py)，没有重复检索或据此新建方案。判断：同一成熟训练域/学习器可复用现成52，增加可学习missing会改变控制语义；删冻结54某个直接项不等同重新训练纯52，Stage195的分数拆解也不是收益因果归因。

开始/结束本阶段是否过拟合：**否**，只锁定旧身份，不看收益选基准、不改变模型/来源/K；历史同史择题、COMMON自身代理及PIT风险仍为**是**，未消除。继续这次盘点的价值：**是**，已找到模型、全域分数、main K选择及四本现金，避免重复成本；为建立这个相同旧基准继续训练/现金的价值：**否**。本阶段已完成有界盘点，后续研究由root决定；不创建新实验、不补held-K、不晋级或加注。
