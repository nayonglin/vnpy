# Stage218：固定训练行动域loss干预实现就绪

- line_id：`futures_full_market_long_signal_ai`；记录时间 2026-10-19 20:17 CST。非重要突破；root唯一actual尚未执行。
- 已读216决策及冻结217协议（SHA `b86c21d02b70e55181b7324efc1ebb6b363ee9d842738efe0f2baedfc3747b53`）。沿用217先完成的原出版页与作者GitHub调研；判断为模型错定下的经验loss域干预值得一次反证，不把12.47%—14.04%被排除质量当坏样本或金融优势。

## 本次改动与固定参数

- 新增`tools/stage218_training_domain_loss_fit.py`与3个定向合成fixture，复用205的IO、17g缓存parser和156选择纯函数，复用130原COMMON52设计及214 gate；没有调用旧q拟合流程或修改任何旧源码。
- 唯一策略改动是原130成熟训练完整身份核对后，仅保留156同K日历门A=D<K的动作；candidate weight=old weight×W/W_A。保留原相对权重、Y、六scaler、52维、Ridge(alpha1/intercept/cholesky)、cutoff2020/2023和家族留出；不重算uniqueness、不重标、不新增特征或mask。
- 全六preflight先于首fit，逐折核原身份、214 counts与math.fsum质量、A非空/无unknown、原Y/设计与变换权重有限。任一失败0fit。support NPZ保存全旧seq、A、old/new weight；normal equations含52系数与intercept，全6拟合完成后才完整前向。
- 完整candidate前向1933480子模型行，main/held各161014母体；旧156main与205 control_held_K直接读存档，不重算旧模型/预测/选择。held保持原完整target域和未知披露。
- 主选择chosen_action_id/sequence/epoch/selected及完整anchor身份全部相同时，normal completed但cash_eligible=false/reason no_action_change，停止新账本；score数值幅度不触发现金重放。
- 若动作变化，219最多4本自有现金路径仍用100万/初损0.25N/单family0.25%/总2%/buffered margin25%/buffer1.1/participation1%与原成本/K退出。该现金actual尚未授权或执行。

## 新验证与输出契约

- 新3fixture一次3 passed/1.015秒，0物理fit/旧大输入读：W/W_A及相对质量、任一六折失败阻止所有fit、同动作不同score仍停止现金。仅在其后增加一处小metadata lineage核对，未重复旧suite。
- root精确授权schema `stage217_exact_root_fit_authorization_v1`；manifest schema `stage218_training_domain_loss_fit_v1`，全source_bundle和217 input_bindings。固定roles包括choices_main、boundaries、held_diagnostic、choices_holdout、selection_identity，所有调用/完成计数及cash_eligible明确供219消费。
- 就绪receipt：`outputs/stage218_training_domain_loss_fit/implementation_receipt.json`，含冻结源码/fixtures SHA、CLI与字段；无自动重试。模型逐个保存后再报告，旧大输入仅继承SHA与前后stat。

## 金融结果及反思

新增fit/cash/labels/prediction/selection/SQL均0，累计427fit/230cash。新增/修改/删除回测结果0；权益、收益、回撤、Sharpe、滑点、交易、胜率全部N/A。不把代码通过当alpha。

开始/结束过拟合风险：是，同史多轮择题仍有，事前冻结并未消除历史选择风险；不按本包新成绩换门、权重、模型、Y、阈值、止损或风险。继续本单点实验有价值，因结构干预明确且有支持；无真实盲OOS或可加注证据。TODO：220关键源码/新语义预审后root唯一actual，再一次独立全新模型/前向/选择/held审查；无动作变化即0cash关闭。完整goal active，正式版/生产/Git发布均未触及。

## root唯一actual终态（2026-10-19 20:22 CST）

- root session `15791` 唯一实际执行，exit0，`87.448280125` 秒；六fold全部preflight通过后实际fit attempted=completed=6，实际model fit=6，无自动重试。manifest `42803B / SHA c75dff54a0fa2b8fa0c0672314a2c98dc87487d5c00b64d7a5ff8c6b93fb47a8`（root提供身份）。本agent只读small fitrecords/preflight/held/selection/terminal追加，不重读大输入。
- 原成熟Y、六old scaler和COMMON52/alpha1/intercept/cholesky未变；只在A内将old weight乘c=W/W_A。**transformed weight与原weight不同**；counter `training_weights_recomputed=0`指原uniqueness/day权重未重算，绝不表示最终拟合权重不变。

| scope | cutoff | 原行数 | retained / excluded行数 | retained / excluded原质量 | c=W/W_A | ESS原全域 → retained重标后 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| main | 2020-01-01 | 247795 | 216443 / 31352 | 215906.400102634 / 31888.599897366 | 1.147696408639 | 92089.420205 → 80171.627951 |
| main | 2023-01-01 | 445475 | 390340 / 55135 | 387066.072069423 / 58408.927930577 | 1.150901699078 | 138666.813959 → 120749.253354 |
| holdout_0 | 2020-01-01 | 171712 | 150511 / 21201 | 150301.098958206 / 21410.901041794 | 1.142453389830 | 64632.214415 → 56370.415541 |
| holdout_0 | 2023-01-01 | 297404 | 261338 / 36066 | 260263.851144881 / 37140.148855119 | 1.142701910741 | 96665.325692 → 84323.692328 |
| holdout_1 | 2020-01-01 | 76083 | 65932 / 10151 | 65804.595839046 / 10278.404160954 | 1.156195840578 | 31509.714439 → 27274.405146 |
| holdout_1 | 2023-01-01 | 148071 | 129002 / 19069 | 127274.582133657 / 20796.417866343 | 1.163398044745 | 47634.511091 → 41168.664002 |

- 六fold gate unknown全0；c为统一质量归一，retained旧相对权重不变，candidate总loss质量回到原W（最大浮点残差5.820766091346741e-11）。统一乘c不恢复样本多样性，ESS下降；原权重支持、A/old/new全seq NPZ已保存。normal equation作者最大残差 `1.57742761075e-08`，独立核验尚在进行。
- 新6次前向完整`1933480`子模型行，main与held各161014母体；candidate选择3次，原156main及205 control_held_K只读2个已存选择表，旧预测/旧main选择/旧held选择均0。主选择身份变化`1758`母体（selected标志变化1386），anchor/event/family/product/u身份差异全0，因此cash_eligible=true，只代表值得实际兑现4本新账本，并非金融或生产资格。
- actions/mothers/COMMON各1读、六training cache各1读、calendar1读；q/source投影/新标签/旧fit/旧cash/控制score/SQL/下载/大输入hash均0。累计实际433fit/230cash；219现金在跑，其结果不计入本阶段。

| held组 | 已知family-u后equal-u均值增量R | distinct unknown | 同动作未决披露 | selected COMMON52 → DOMAIN52 | 门 |
| --- | ---: | ---: | ---: | ---: | --- |
| holdout_0 | 0.001294936754 | 16 | 22 | 2111 → 2900 | false / unknown |
| holdout_1 | 0.001070648940 | 7 | 31 | 3766 → 4190 | false / unknown |

- 两held已知均值小正，但distinct differential unknown分别16/7，故217的unknown=0门均失败；不填0、不删未知，也不把原firstexit-R诊断替代同K/资金现金收益。不能据此宣称稳定泛化或训练域剔除有效。
- 220模型/完整前向/选择/held独审actual运行中；219新cash运行中。此处不预告独审通过、最终收益/DD或资格；原217门不因已知小正而放宽。
- 本阶段新fit6、现金回测0；权益/收益/最大回撤/Sharpe/总滑点/交易/胜率仍N/A，待219原账本终态。开始/结束过拟合风险仍是历史择题，未按本结果调参数；继续完成已冻结现金与独审有价值，救参、加注或接正式版没有依据。完整goal保持active。
