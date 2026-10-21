# Stage170a 固定q对照实际选择差异的有限只读归因

时间：2026-10-19 02:35 CST；line_id `futures_full_market_long_signal_ai`。先读registry/LINE；本轮仅解释已完成167/168，不是补跑、救参或169独审替代。唯一新输出 `outputs/stage170_choice_effect/choice_effect_summary.json`（75361 B）及本stage；不改LINE、registry、root170、源码或旧数据。新增fit/cash/SQL/download/predict/tests均0；累计 **409 fit / 218 cash**。不是重要突破，不签accepted、泛化或加注。

## 完整母域的选择变化

只对167 `choices_main.csv.gz` 做一次必要列读取：sequence/event/product/family/u/reference、chosen_action/epoch、selected、selection_state、arm；没有读取child_scores、raw、COMMON、labels或价格。完整322028行按event_id一对一匹配为161014对，各arm原身份一致，未按q可得、选中或盈亏过滤。chosen是决策动作，**不是已证明实际成交**。

- CONTROL54选中4901，CONCENTRATION54选中4894。
- selected二元状态不同 **9** 对；原selection_state原因文本不同 **15** 对；chosen_action_id不同 **13** 对（约完整父域0.0081%）。三者含义不同，不能相加。
- 13对为 **新增1、删除8、换合约月4**，同合约不同action为0；双方都空156112对、同一非空action4889对，合计与全部161014对闭合。

| 年份 | 全父数 | CONTROL选中 | q臂选中 | selected改变 | chosen改变 | 新增/删除/换月 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2020 | 23814 | 282 | 282 | 2 | 2 | 1 / 1 / 0 |
| 2021 | 23814 | 1212 | 1210 | 2 | 2 | 0 / 2 / 0 |
| 2022 | 23716 | 1459 | 1455 | 4 | 6 | 0 / 4 / 2 |
| 2023 | 23716 | 253 | 253 | 0 | 0 | 0 / 0 / 0 |
| 2024 | 23716 | 358 | 358 | 0 | 0 | 0 / 0 / 0 |
| 2025 | 23814 | 241 | 241 | 0 | 0 | 0 / 0 / 0 |
| 2026 | 18424 | 1096 | 1095 | 1 | 3 | 0 / 1 / 2 |

chosen改变分布为SHFE7、INE1、DCE3、CZCE1、CFFEX1、GFEX0；完整六所及98代码含零变化计数都在JSON。后四所发生选择变化不能称其新增了会员来源：实际q源观察仍仅SHFE/INE；两臂重新估计共同模型的其他系数、missing系数与截距，最终选择变化不限于q可见父行。这里只观察选择，不从这些父行的PnL倒算账户差额。

## 全部12模型的q格与共同missing系数

从fit_records指定的12小portable和6个共享scaler读取，不调用模型。位置52为 `member_concentration_missing`、位置53为 `member_concentration_standardized`；下表每行含该scope/cutoff两模型，完整精度及原binding/训练q均值尺度在JSON。

| scope / cutoff | CONTROL q系数 | CONTROL missing系数 | q臂q系数 | q臂missing系数 |
| --- | ---: | ---: | ---: | ---: |
| main / 2020 | 0 | 0.152105855564 | −0.020790499509 | 0.152305272978 |
| main / 2023 | 0 | 0.131360232728 | −0.011927406338 | 0.131411115273 |
| holdout_0 / 2020 | 0 | 0.196074721677 | −0.013122040646 | 0.195912810045 |
| holdout_0 / 2023 | 0 | 0.181183021856 | −0.014369144479 | 0.180989005411 |
| holdout_1 / 2020 | 0 | 0.071897847830 | −0.014640296076 | 0.072378205868 |
| holdout_1 / 2023 | 0 | 0.051871873372 | −0.002308773236 | 0.051917798856 |

CONTROL最后格系数全部精确0，与恒0设计一致；集中度臂六个训练内条件斜率均负。这是各fold线性Ridge对原stress first-exit目标的条件拟合，不是因果效应、聪明钱证据或q的独立完整score贡献。q使用本fold成熟训练有限观测加权中心/尺度，missing另有共同格；共同系数也会随重估变化。**不能据负号换sign、lag、归一或阈值，不据正missing系数解释“缺源更好”。**

## 现金差异直接引用四个完整账户pair

只读168四行 `comparisons.csv.gz` 和8个小summary。以下差额都是CONCENTRATION54减CONTROL54；DD差为正表示更浅；CI单位是日log收益均值差，不能与收益百分点混用。

| 账户pair | 总收益差pp | DD改善pp | 日log差CI95 |
| --- | ---: | ---: | --- |
| 2020 base | +1.672676550 | +0.006167987123 | [−0.000018902237655, +0.000032326154774] |
| 2020 stress | +0.019787800 | +0.013896945713 | [−0.000002546605938, +0.000002789794311] |
| 2023 base | 0 | 0 | [0, 0] |
| 2023 stress | +0.005187500 | 0 | [−0.000000002680736, +0.000000118182711] |

三组非退化CI含0，一组配对区间为[0,0]；没有重读daily或据此另证两臂逐日完全一致。此处不据单笔净PnL累加“贡献”，也不把仅13个决策变化等同于13笔账户差异，实际账户预算/持仓递推可传播影响。8个账户summary仍全部 **execution_unknown=true**；完整账户摘要、四pair全部字段及source路径存JSON。首发PIT与可兑现执行资格没有因本归因获得认证。

复现入口：167 `actual_run1/choices_main.csv.gz` 以上12列；`fit_records.json` 的portable_model/scaler引用；168 `actual_run1/comparisons.csv.gz` 及 `NARROW_<arm>_<window>_<cost>/summary.json`。分类按双方chosen是否空、是否同ID、不同ID时是否同epoch，完整事件全集配对；未选中行保留，未读任何结果列筛母体。输出JSON另列年/所/全代码分母和selection_state转换，非抽样例子。

开始/结束新增过拟合：**否，本轮是固定结果的全域观察，0新金融、不依成绩变参**；同史多轮择题风险不消失。继续本次归因的价值：**已完成其有界解释目的**；不能从系数或局部正差再开救参。本记录不替代169完整复审，也不提前替root170下研究支持结论，原目标仍未证明达成。
