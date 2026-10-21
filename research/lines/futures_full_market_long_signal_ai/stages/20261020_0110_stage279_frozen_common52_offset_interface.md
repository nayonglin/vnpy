# Stage279：冻结COMMON52加单项offset的实际接口闭包

- line_id=`futures_full_market_long_signal_ai`；2026-10-20 01:10 CST；只读盘点、非突破、非实施授权。新增fit/cash/选择/预测/SQL/网络/测试=0，累计439/238。只读小源码/AST/JSON并stat依赖，未import旧程序、未读CSV/NPZ/标签/native价格、未做大hash。仅新增本stage和[refs](./20261020_0110_stage279_frozen_common52_offset_interface_refs.json)，不改LINE/registry/旧source。

**原130六模型和前向全分数、157四控制、接受现金核均可直接复用。新增的必要面是训练残差计算、一个无截距scalar学习、完整新score重选及四本新候选现金薄封装；不能套用238/218模型，也不能仅过滤旧4365。** 本盘点不证明WASDE日级可知映射已完成。

| scope / cutoff | 原成熟训练行 | 前向child / 母行 |
| --- | ---: | ---: |
| main / 2020 | 247795 | 366634 / 71344 |
| main / 2023 | 445475 | 600106 / 89670 |
| holdout_0 / 2020 | 171712 | 138837 / 28392 |
| holdout_0 / 2023 | 297404 | 249829 / 35685 |
| holdout_1 / 2020 | 76083 | 227797 / 42952 |
| holdout_1 / 2023 | 148071 | 350277 / 53985 |

六折的准确路径/原SHA见refs：根为`outputs/stage130_contract_choice_fit/actual_run1/folds/{scope}/{2020-01-01或2023-01-01}/`，每折已有`portable_model.json`、`scaler.json`、`training_identity_weights.csv.gz`。本次逐个核portable/scaler小SHA，均匹配原130记录；每模型恰52coef+intercept，Ridge alpha1/有截距/cholesky。原mask为u可行动、`closed_complete_bar_model`、u及非空`label_known_date`严格早于cutoff、有限`net_R_stress`；held训练排除`sha256(family_id)%2`对应组，预测只该组。2020模型只预测2020≤u<2023，2023模型预测2023≤u≤2026-10-16。原权重为family-u持有区间并集uniqueness、组内均分动作、等u、总均值归一；**直接恢复原sample_weight，不重算、不将有源子集重新归一、不加D<K训练mask、不重标K目标**。依据`stage130_contract_choice_fit.py:29-75,144-169`。

训练逐行s52没有独立现成文件，normal equations不能恢复个体残差。最小读取为六份原training CSV共138791254压缩B（refs列12个必要身份/成熟/y/weight列）与129 `common26.npz`一次146877351B；COMMON为1552456×26，float64约322910848B，不必保存大52矩阵。17g导出权重宜按214:96-99从字符串直接`astype(float)`恢复，不经可能改舍入的`pd.to_numeric`。按sequence_index定位，原scaler有限值标准化、非有限值置0并附26个原missing，再与冻结coef点乘加原截距即可得到train s52。只需对非零offset设计行计算残差，其他行在无截距单scalar目标中仅贡献常数；所有原域/权重身份仍保留，不把它称为缩窄训练域。`model.joblib`、旧标签文件、129完整动作表、旧q、218/238support均非这一步依赖。

前向s52直接流读130 `child_scores.csv.gz`一次124127126B，已有全部14字段及main966740+held并集966740=1933480行；覆盖161014前向母行，含旧非正分，无须再算前向COMMON。新score=s52+γz，缺源/未映射z设计严格0，无新可学习missing/ID/截距。固定原权重时单scalar解为`γ=Σw z(y−s52)/(Σw z²+1)`；这只是Ridge1同一无截距目标的代数式，源变换/训练内缩放、支持门、fit计数与预算仍须收益前另冻，不能在此临时决定。

**已知硬限制：DCE.C family_group=1。** 若源只直接映射DCE.C，则holdout_1两折训练完全排除唯一有源family，必为unsupported/offset0，不得借main γ；holdout_0训练可有源，但其预测组没有DCE.C，直接项恒0。这套固定family-held不能证明此单品源的跨family增量泛化。main实际有效报告/变异尚未读，不作支持断言。

重选直接用`stage156_voluntary_choices.py:74 select_full_pool`：全scope母行+完整新分数→D<K先于argmax→逐exact product最高正分→原ordinary/F/family次序；缺child母行保留。该函数只接收main，held已有`stage205_local_curve_information_fit.py:308 choose_scope`私有main别名适配后恢复scope，不须改旧源或使用218/238模型。旧156 actual CLI固定旧协议/计数/130绑定，不作为新入口。

现金新候选须按**新choices全部selected ID**从129 `actions.csv.gz`（334909637B）一次流读`stage148_fx_cash.ACTION_FIELDS`16列，再用`stage157_voluntary_cash.py:91 make_voluntary_signals`重建所选信号/K边界→`stage131_contract_choice_cash.py:127 organize`（完整399252母行canonical）→`stage131_contract_choice_kernel.py:90 run_cash_account`。156输出的内部`VOLUNTARY_RESELECT`身份可作局部helper输入，外部记录须保留新候选身份。单纯改旧signals或用266.apply_policy将漏掉新正分机会。157原CLI硬绑旧156/131、`baseline_references`也读131，不能直接套跑。

四控制必须只读引用157 actual_run1的`NARROW_VOLUNTARY_RESELECT_{primary_2020或cold_2023}_{base或stress}`，不重放；准确summary/daily引用见refs。现金数据沿[263已核接口](./20261020_0018_stage263_cash_interface_inventory.md)：132缓存110273488B、5587日历、041经济快照、原070两份2000×窗口日数indices、100万/0.25N及全部预算/容量/成本规则不动。16个接受源码依赖在263 refs中；当前94个相关绑定存在/尺寸均匹配，原数据库stat亦匹配；大文件只stat，非新内容完整审计。未来实际restore_native_cache自带一次缓存读取/绑定核验，不另预hash或重开SQL。

调研复用272已核Ridge维护者原理及277 USDA/NBER原件结论，无重复网络：单项线性项可改变参与门，同产品各月份共用z时不能直接改变月排序。开始/结束新增收益调参过拟合**否**，本次没有金融结果；同史439fit/238cash后的选题适应性风险**是**。继续做有界接口盘点**有价值且已完成**；继续重复基准计算或声称held泛化**无价值**。参数/回测结果新增修改删除0；权益、收益、DD、Sharpe、滑点、交易数、胜率及CI均N/A；无新PIT、alpha、加注或金融资格。
