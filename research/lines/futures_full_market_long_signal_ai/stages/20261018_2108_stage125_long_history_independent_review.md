# Stage125：固定十二公历月历史信息独立全面审查

- line_id：`futures_full_market_long_signal_ai`；开始 2026-10-18 21:08 CST；当前仅最终代码核查与独审器准备，**actual 未授权、未启动**。重要突破：否。
- 本阶段只维护125工具、测试、输出与本唯一中文stage，不改121、122/123/124、LINE、registry及历史材料。

## 调研、判断与固定科学问题

读取 registry 与121冻结协议（SHA `c9a9538de0160266624c2bbfd8912964a44b2cfda97e639d1079fb1614bd7421`），沿已完成120的一手研究：[Moskowitz/Ooi/Pedersen原论文](https://spinup-000d1a-wp-offload-media.s3.amazonaws.com/faculty/wp-content/uploads/sites/3/2019/09/TimeSeriesMomentum.pdf)、[维护者实现](https://github.com/kieranjwood/trading-momentum-transformer/blob/master/mom_trans/data_prep.py)。论文动机仅支持检验长历史context，不证明本窄损long-only策略有优势，也不照搬月度多空仓位。

一次读取122/123/124最终源码与新fixture内容，静态 C/I/M=0；不重跑作者测试、旧suite或旧收益。122在每v固定prev(v)当时代表epoch，再用该同一真实epoch的(prev,v)两价，防今天主力回看一年、换月跨合约除价与未来主力身份。4074母表日历与5587原native索引区分；12公历月开下界b<v<=u，Feb29映前一年Feb28，任何窗口缺失整项missing，真零observed，原399252/98/95/6全集不删。q使用u收盘供下一D，不加外部报告的lag1。不是sign/volnorm/6月网格，也不接NFC。

123沿固定own-policy成熟标签、严格label_known_date<cutoff、family隔离与训练内scaler，shared missing与54头，两臂唯一scalar差异；预测不按未来closed筛选。124维持.25N/原20low/换月/生命周期/stale/gap uncapped、原预算/整数手/成本与主stress严格门，不因观察到结果而降门。

## 独审实现、测试与一次实际预算

新独审器 `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage125_long_history_review.py`：62634 B，SHA `d248afa6211c8bea9370caf1007b52496045f44be79b48d87cc46032b49a5814`；测试 4443 B，SHA `e62b183e82ed318a5560588fab501e271d31905f3feef749c79ee92eafdaabcb`。代码核查收据 `outputs/stage125_long_history_review/code_preflight.json`，完整CLI `audit_input_schema.json`；checker冻结 `checker_freeze.json`。

五个必要新语义fixture先RED（工具缺失）后GREEN；最终5项/0.251秒，覆盖前代表同epoch两价、母表紧邻日非native减一、闰日与开下界、窗口完整缺失与真0、非法全OHLC/经济身份、typed字符串/bool/null元数据比较与严格现金门。0真实数据/SQL/研究fit/cash，不重旧suite。上次114末端元数据被当数值的错误通过复用已有typed字段校验与新边界避免；未修改114任何产物。

实际只在root提供最终122/123/124 manifest+terminal六精确SHA后启动一次。独审单次只读SQL从accepted数据库完整重构全部1552456 native行；不全hash大库、不网络、不研究fit、不重放现金策略。独立用明确逐窗口math.fsum重算全部399252价格链scalar，对照作者prefix实现；全核模型12个正规方程、644056分数/动作、成熟train/weights/scaler、held已知域与unknown。全核八账本预算/费用/滑点不重复扣、逐笔native开盘与stop参考、全部持仓native mark与stale、全部95family/年度归因、既有252block/2000indices配对CI。有限first-hit分支另与同次SQL原bar逐项核，不产生替代策略路径。

每完成phase与每一账户都落checkpoint，另存已验scalar/mask、held/main signal，末端小checker问题不得自动重做已完成的源/模型/账本。失败原样保留，先报root，无自动修复重启。

## 反思、参数与尚未完成项

开始过拟合判断：本包**新增按结果调参否，历次同史择题风险是**。十二月是预冻结独立信息问题，不能把多轮CI当未见OOS，也不把2000bootstrap当2000独立市场。继续价值：**是，但只值得有限反证**；若失败停止固定12month/Ridge/NARROW包，若点估计正仍不能直接晋级/加注。

本次新增参数仅审计CLI与一次SQL预算；策略新增/修改/删除参数0，旧回测结果修改/删除0。actual未运行，因此期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。后续等待root精确终态授权后一次全面审查，保留历史选择、首发PIT、静态费用/保证金、日线窄损与尾端浮盈/集中度限制。正式/生产/加注资格均未达到，完整目标active且未完成。


## 21:12 actual 一次完成与独立结案

root提供最终122/123/124 manifest与terminal六精确SHA后，125于21:10:04 CST首次启动，21:10:58完成（54.225秒/exit0）。**完整审查1次、SQL1次、研究fit0、现金重跑0、原始下载0、大库hash0、旧suite0，自动retry0**。所有phase及逐账户checkpoint均保留，未发生checker错误，只有pandas未来行为弃用提示，未为小warning修改或重跑。

- receipt：89393 B SHA `f5e76729874e96dd2236e3dcd197741bc3812d6fbf0cec2e2ddf2ee2086994b3`；terminal：302 B SHA `281190f5f2201a3aefae9d5a1d8e88ac949098a295822739891bac57e08983d3`。路径均在 `outputs/stage125_long_history_review/actual_review1/`。
- 研究算术/接线剩余 **C=0/I=0/M=0**；固定科研包结论 **unsupported**，没有把负结果包装成通过。附加可读`decision_summary.json`不修改既有receipt。
- 同源独立一次只读SQL读取1,552,456行/9,520个epoch，前后stat/WAL/SHM一致，accepted大库SHA继承而未重hash。全399,252原代表身份、同epoch两bar及完整12月窗口独立重建；4074/5587时钟、98产品/95family/六所与全部缺失状态完整保留。factor observed208,817；q observed137,001（完整母表34.3144%），missing262,251；早期不足23,716，必要factor缺失238,535。未删未资格/无ref/新上市样本，真0语义fixture已验；实际真0数为0。
- 六训练cell均有正加权scalar方差，主2020成熟train81,903/finite63,721，主2023 train121,467/finite87,229；这仅可识别，不是样本独立性/充分性证明。12模型严格成熟train/weights/scaler/正规方程、644,056全部分数/动作、2held全预测与未知域均独立通过，无fit重跑、旧模型成绩或future-closed预测筛选。
- 八完整资金账本、u联合预算/D只减量/整数手/持仓/费用/滑点不双扣、所有3040个fill参考价格与9115条position mark对同次SQL核对；12个native首次分支case/1130bar另验。全部95family含零、年度表、4组2000既有同indices配对log CI、held/unknown/gap/>1R风险披露均核过。最大记录数值误差2.91e−11（初损浮点表示）。

### 真实资金结果（初始100万元）

| 账户 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点归因 | 完整平仓/Fill次数 | 已平仓净胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CONTROL_primary_2020_base | 1,069,527.0240 | 6.952702% | -13.179697% | 0.188150 | 22798.4576 | 296 / 594 | 12.5000% |
| CONTROL_primary_2020_stress | 1,056,759.9745 | 5.675997% | -11.686521% | 0.190441 | 43296.7366 | 257 / 516 | 12.8405% |
| CONTROL_cold_2023_base | 1,245,175.1230 | 24.517512% | -6.571577% | 1.032848 | 6495.3620 | 103 / 207 | 13.5922% |
| CONTROL_cold_2023_stress | 1,128,661.8495 | 12.866185% | -6.343284% | 0.734753 | 14130.5828 | 95 / 191 | 12.6316% |
| LONG_HISTORY_primary_2020_base | 1,117,626.0645 | 11.762606% | -12.614587% | 0.282657 | 23829.9535 | 310 / 622 | 12.5806% |
| LONG_HISTORY_primary_2020_stress | 1,069,334.7210 | 6.933472% | -11.057867% | 0.224428 | 42019.0660 | 253 / 508 | 13.0435% |
| LONG_HISTORY_cold_2023_base | 1,238,747.5360 | 23.874754% | -6.939159% | 0.975249 | 6523.1233 | 106 / 213 | 13.2075% |
| LONG_HISTORY_cold_2023_stress | 1,143,734.2315 | 14.373423% | -5.138073% | 0.815633 | 13716.1705 | 94 / 189 | 13.8298% |

滑点单位CNY，已在成交价中承载；表中只是归因汇总，不另扣。完整平仓数与买卖Fill数并列，不用一个含糊交易次数替代两个不同概念。各账户最后仍有未平仓，胜率不是所有信号价值。

| 相同mask下 LONG_HISTORY−CONTROL | 收益差 | 回撤改善 | 配对平均日log差95%CI |
| --- | ---: | ---: | --- |
| primary_2020/base | +4.809904 pp | +0.565110 pp | [-3.49338923822e-05, 0.000111446170534] |
| primary_2020/stress | +1.257475 pp | +0.628654 pp | [-1.76508305076e-06, 1.6686974427e-05] |
| cold_2023/base | -0.642759 pp | -0.367582 pp | [-3.15434911964e-05, 2.03397735623e-05] |
| cold_2023/stress | +1.507238 pp | +1.205211 pp | [-7.84092627492e-06, 4.43853526176e-05] |

**四CI均跨零；冷2023/base收益下降0.642759pp且回撤加深0.367582pp**。主2020/stress点改善1.257475pp、回撤改善0.628654pp不能覆盖预冻结门失败。该CONTROL含本包共享长历史缺失mask，和旧包CONTROL缺失列不同；严禁拿旧COMMON/NFC控制收益跨包直接排名或宣称新特征导致控制退化。

两个held已识别、u等权的净R增量分别为 **−0.0004252484R / −0.0001348520R**，名义均失败；held0未知差异0、held1为6，main未知差异1，未把未知收益当0、也未把未成交潜在标签未知冒充现金敞口。held只是机会诊断不是可交易资金收益。

### 盈利来源、尾部与置信度

主2020/stress LONG_HISTORY累计6.933472%包含末端未实现103,520元（FU97,100、stale WR6,420），实际现金965,814.721元低于初始本金；连续主样本2020/2021/2023年度均负（−0.865371%/−7.266212%/−0.783725%），2022仅+0.116606%，2024+7.124175%、2025+2.330241%、2026不完整年+6.824227%。不把连续账户年度切片称为独立冷启动。

主stress末端WR.202202一手自2021-12-31持有后缺价，stale1140天保留；WR零价场景期末1,018,904.721元，也仅是场景、非可保证下界。另一尾端FU浮盈右删失，尚未兑现。冷启动2023/stress现金1,046,634.2315元、浮盈97,100元，同样不能只报期末账面收益。2024/2025正family年度来源主要EC，2026主要FU；主stress EC/FU两family正贡献174,354.8675元，占全部正family贡献约78.10%，总净利润还受其他亏损抵消。并非全市场广泛高质量long已识别。

主stress存在12个gross loss>1R gap止损，最差gross loss3.557869R（2026-08-26 FU），窄.25N初损不保证实际损失有界；费用/滑点进一步影响真实net loss。保留全部原值，不加1R损失截断或利用后来结果调止损。

研究算术可信，但**稳定跨周期增量证据不足**。252日block/2000次bootstrap仅对此历史序列的抽样，非2000个独立市场，也不消除历史多轮择题、共同价格信息依赖、首发PIT、静态费用/保证金、日线窄损可成交性及未平仓估值问题。可否决的是本次固定12month/Ridge/NARROW包的资格，不能推出所有长历史context无效。

结束过拟合反思：**本次按观察结果调参否，反复使用同史择题风险仍是**；不扫6/12/24月、改sign/volnorm/方向/模型/stop/risk救参。继续本固定包价值：**否，应停止**；更广义全市场高质量做多目标仍有价值且未达成，后续必须有不同结构的问题与预声明证据。没有正式晋级、实盘/生产或加大投注依据。没有修改/删除任何旧回测结果，root在126做独立最终路线决策。
