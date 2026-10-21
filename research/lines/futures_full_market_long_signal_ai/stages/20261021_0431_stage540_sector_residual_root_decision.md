# Stage540：固定行业校准未获跨品种支持，关闭本规格

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 04:31 CST；day模式；非重要突破。
- 工作区 `/Users/mac/Desktop/fian`，分支 `codex/ai-training-data-expansion`；六所98产品/95family全市场long，独立于正式C9月度池。
- 上一goal轮为进展：537已完成输入盘点；本轮完成536协议、538一次actual与539独立全量新cache审查。没有等待今日日线。

**裁决：不采用这套固定行业残差截距，不进入资金回测，不增加投注。主模型有很小的平均改善，但一个完整留族组变差，且输给固定任意分组；预声明的两个留族组同向门未通过。** 这是该规格的失败，不是所有行业信息或所有AI的否定。完整高收益、低回撤、超高质量做多、极窄止损和加注目标仍未达成，goal保持active。

## 外部调研与独立判断

本轮实际核原作者[JMLR 2005论文摘要](https://www.jmlr.org/papers/v6/evgeniou05a.html)、[MTL-TSMOM固定GitHub原码](https://raw.githubusercontent.com/joelowj/mtl-tsmom/b07fa1d0a3c71bef3d3614e0d8f4233477e42df1/core/model.py)与[RBA原始研究](https://www.rba.gov.au/publications/bulletin/2016/mar/7.html)。共同学习在统计上有依据；GitHub实际是共享LSTM加辅助网络，不能冒充行业截距验证；RBA说明商品风险溢价在期限/商品/时期上不同，也不保证静态行业均值可迁移。我的判断：可以有限检验收益以外的经济标签，但必须由跨品种/跨期实际结果裁决。本次数据不支持其稳定优势。未下载或运行第三方代码。

## 版本、参数与实际执行

A=原130六个COMMON52冻结头加155/156 voluntary-reselect日历门；B=A加一次固定任意family分组校准；C=A加研究前269八类行业校准。原26值/26missing、scaler、52系数/截距、成熟标签、逐foldunion/day权重、当时全产品机会、月份/普通F优先、退出及成本均未改。新增只包括两份固定group mapping、sumw1/lambda1无zscore无新global参数的小残差头；旧参数修改/删除0。不是原52重训或正式C9发布。

536在新结果前冻结精确公式/真实与随机映射/seed/门。B按原hash留族两侧分别置乱同标签多重集合，全局单族产业EC保留，S未知不置乱。未知或训练无该组精确offset0。sumw1、lambda1强收缩，C实际新增有效df范围0.626267—0.684207，每fold低于1。一般unknown有训练质量时sumwZ不必0；此次实际unknown训练行0、q≈1，未将无显式全局参数偷换成任意unknown情形全域均值为0。

唯一actual_run1 exit0，182.728989秒，12/12个新offset fit，0原52 fit、0新资金账、0SQL、0行情下载；四类旧大输入actions/COMMON/mothers/fullscores各一次内容读取并校SHA。六fold原训练统计、scaler及52充分方程均匹配（lhs最大差0）；无读取六张旧大训练表。全母体399252行保留，2020-01-01—2026-10-16每臂主/留族各161014母机会，主+held旧score1933480行均覆盖，旧非正分同样进入候选。

## 实际结果

以下单位是压力成本下已选择动作的 **R增量：先family-u、再等u日均值**，不是账户收益率，不能乘本金或当作组合权益。无交易与已知不参与为0；异动作未知保持NaN；同动作增量0同时披露原收益未决。

| 范围 | C−A真实行业减原模型 | C−B真实行业减任意分组 | C−A异动作未知 | C−B异动作未知 |
| --- | ---: | ---: | ---: | ---: |
| 主模型 | +0.000292331272 | +0.000429956785 | 1 | 1 |
| 留族0 | +0.000114203498 | +0.000555341684 | 1 | 1 |
| 留族1 | -0.001096434136 | -0.001097507354 | 2 | 5 |

留族0略正，但留族1的C−A和C−B均负，故名义现金前门为false。失败并非只因未知状态；即便按已知支持的原诊断，方向门也失败。主模型A/B/C入选分别4365/4397/4404次，是入选机会数，不是资金账户成交笔数。完整different/added/removed细分本轮没有另行输出，不能由净入选差伪造，也不为这项非核心统计重扫全cache。

### 年度分解

| 年份 | 主模型C−A | 留族0 C−A | 留族1 C−A |
| --- | ---: | ---: | ---: |
| 2020 | +0.001248310784 | -0.000734356525 | -0.000936742774 |
| 2021 | +0.001402341721 | +0.003807607671 | +0.003060119312 |
| 2022 | -0.000080065850 | -0.001726672250 | -0.004503010746 |
| 2023 | -0.000265813387 | -0.000959561856 | -0.004715602681 |
| 2024 | -0.000038670806 | +0.000910625595 | -0.000818240492 |
| 2025 | -0.000135084141 | -0.000131610111 | +0.000617560258 |
| 2026（截至10-16） | -0.000201711286 | -0.000518538114 | -0.000205161061 |

主模型全周期小正来自2020/2021，2022—2026截至样本末全部负，两个held各只有2/7年为正。2026不是完整年度，亦不是今天的未收盘数据。数据不支持穿越周期的行业平均优势；不挑2021/行业赢家重分组。

## 独立review与置信度

539在actual结束后由独立agent唯一执行，exit0，43.186809秒，C/I/M=0/0/0。其计算不import538/130/156实现：独算六fold区间union/等日权重、冻结52 Ahat、12小头、1933480 forward修正、966084个三臂主/留族选择、所有daily/annual/现金前门；选择ID精确一致。最大权重差9.95e-14、原base差3.55e-15、head差1.55e-14、forward offset差1.47e-16、选择分数差1.78e-15、诊断均值差2.72e-20，均属浮点误差。复算是审计而非新候选搜索fit，新增candidate计数仍12。

被接受的是新实现与已继承输入合同下的算术/身份/时钟/权重/完整域，未因此认证交易所原始价格全库、可成交性、未来收益或生产。原静态taxonomy只覆盖94/95family（97/98产品），S完整保留；EC在两cutoff无成熟同行业训练，回原52，不能计为行业迁移成功。部分组只有少量训练peer，固定随机分组的成熟权重/有效df不可能逐点相同。一个固定placebo没有给出排列检验p值；同一历史已511次fit后的本次523累计，同史适应性选择使这些held不是未触及最终OOS。异动作未知数量见表，没有填0或给出不存在的无条件置信界。

## 财务指标、记录与后续

新期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：**全部N/A**。原因是预声明模型门失败后0新资金回测；不是已算收益差而隐去，也不是把机会R累加为现金。旧157 OWN四本控制仅绑定待复用，本轮未重跑；没有新资金盈亏/回撤结论。

新增：536协议/映射、537精确input inventory、538实现与8个意义明确的小fixture、539独审工具和本次540决策/报告；修改原策略代码/配置0，删除0；本轮新增12fit/0cash，累计**523fit/278完成cash及1旧partial**，旧结果不覆盖。独立review新增candidate fit0。root只更新本线LINE/registry，不追加根memory/back_log，不提交/推送/改生产、CTP、邮件或定时任务。

运行前/后过拟合判断均**是且高**；固定低df/一个种子只限制新增自由度，不能清除同史择题。运行前一次证伪价值**是**，运行后继续此固定行业截距路线价值**否**：跨品种/年度门没有支持。继续完整目标研究价值**是**，但须先找经济上不同、决策时可见、能影响绝对做多时点的信息或不同动作，再排重/冻设计；不扫分类、惩罚、seed、斜率交互、目标或风险来补救此失败。

Polanyi式经验判断在本轮被压为可反驳问题：从同产业其他品种积累的平均误差，离开原品种后能否迁移？本次答案在此规格下不稳定，不能用交易直觉覆盖反证。

证据：

- [冻结协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage536_sector_residual_protocol/protocol.json)
- [actual终态](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage538_sector_residual_fit/actual_run1/actual_terminal.json)
- [完整诊断](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage538_sector_residual_fit/actual_run1/held_diagnostic.json)
- [独立审查](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage539_sector_residual_independent_review/actual_review1/review.json)
- [机器决策](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage540_sector_residual_root_decision/decision.json)
