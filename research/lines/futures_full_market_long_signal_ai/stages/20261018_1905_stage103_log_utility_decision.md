# Stage103 固定风险效用目标结案：没有收益与回撤改善

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 19:05 CST；现分支/checkout，未创建工作树或分支。
- 重要突破：否。G四组收益均低于L，两个2023冷启动组合亏损，回撤两组改善、两组更深，四CI跨0。接受独立复核算术，停止这一固定log代理，不扫描风险或效用参数。
- 完整目标仍是全市场全品种高质量做多、成本后更高收益更低回撤，并最终验证极小止损与增加投注；尚未达成，goal active。

## 科学依据、变更与参数

098审查[Kelly原文记录](https://onlinelibrary.wiley.com/doi/abs/10.1002/j.1538-7305.1956.tb03809.x)、[风险约束Kelly作者论文](https://web.stanford.edu/~boyd/papers/kelly.html)、[作者代码](https://github.com/cvxgrp/kelly_code)及SPO原论文/代码。判断：log曲率改变条件均值的偏好，但log本身不保证峰值最大回撤；单事件效用也不是重叠组合财富log。没有复制作者优化器、模拟盈利或GPL代码。

原式log1p(f*y)/f被否决，因为070按含成本风险预留。新有限对照只隔离曲率：y=当前NARROW stress净R；c=接受COMMON的stress_u_cost_R，a=1/(1+8c)，z=a*y。L学z，G学log1p(.0025*z)/.0025。f取既定单family风险，未选择新风险小数。a*y不是新信息，L仅为必要同单位控制，不能趁G失败挑L晋级，也不将083独立单位变换的否决翻成发现。

两目标同COMMON26+26missing共52项+intercept，无RFF/外部缺失位/外部标量。Ridge alpha1/intercept/cholesky。两main cutoff2020/2023，共4fit；严格自身成熟闭合标签、family区间唯一性→u等质量→均值1权重、训练内尺度与缺失填补。与旧不同背景COMMON不能直接跨包归因。没有family留出，不宣称全品种泛化。

训练域任何无效c/a/y、非正财富因子或非有限log均整候选fail-stop，不删行/clip/epsilon。前向322028完整分数先保存，之后才检查已知闭合OOS域；未成熟/open/cancel/unknown保持原null状态，无未来域动作门。

实际两个训练域分别81903、121467行，前向已闭合已知101940行，域反证0。全399252身份/每臂161014预测保留。历史有限值不证明总体尾部可积或未来不会突破财富边界。

交易参数新增/修改/删除均0：100w，单family0.25%/总2%，buffered margin25%/1.10；.25 Wilder20N初损/因果20low/noPT、u预留D只减不回收、原070 gap/roll/缺价/费用/破产与整数手，均未变。不用080/OI/RFF、无加注。目标只是孤立u连续计划风险代理，不写入未来q或equity。

## 实际与独立复核

100由root唯一27.175秒/4attempt=4complete/322028分数/0SQL；101由root唯一18.062秒/8start=8complete/1共享native SQL。0新label/下载/旧金融重跑/大库hash。

102独立agent唯一23.930秒完整复核，4个52模型/全分数/399252域投影/全部训练与OOS目标域、8账本、四CI与门，C/I/M0，最大比较差2.91e-11；0新SQL/模型重拟合/现金重放。当前累计361研究fit/94现金账户，这些是重叠历史研究而非独立市场经验。

## 全部回测指标

| 目标 | 区间 | 成本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 闭合交易 | 净胜率 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| L | 2020至今持续 | base | 1,228,549.38 | 22.854938% | -5.583249% | 0.639584 | 142 | 16.1972% |
| L | 2020至今持续 | stress | 1,061,109.78 | 6.110978% | -5.579406% | 0.280798 | 141 | 14.8936% |
| L | 2023独立冷启 | base | 1,170,245.54 | 17.024554% | -3.920594% | 1.029868 | 65 | 15.3846% |
| L | 2023独立冷启 | stress | 1,069,543.82 | 6.954382% | -4.799666% | 0.655341 | 63 | 14.2857% |
| G | 2020至今持续 | base | 1,163,387.23 | 16.338723% | -4.557618% | 0.507147 | 115 | 15.6522% |
| G | 2020至今持续 | stress | 1,034,686.03 | 3.468603% | -6.185406% | 0.168898 | 112 | 14.2857% |
| G | 2023独立冷启 | base | 984,708.83 | -1.529117% | -4.481547% | -0.183901 | 54 | 11.1111% |
| G | 2023独立冷启 | stress | 981,371.34 | -1.862866% | -4.649122% | -0.234251 | 53 | 11.3208% |

胜率按闭合经济根净CNY>0计算。下表滑点已进成交价，归因不重复扣除；fills不等于闭合交易数。

| 目标 | 区间/成本 | fills | 手续费CNY | 滑点归因CNY |
| --- | --- | ---: | ---: | ---: |
| L | primary_2020/base | 284 | 4,025.62 | 10,168.24 |
| L | primary_2020/stress | 284 | 9,615.22 | 21,544.59 |
| L | cold_2023/base | 130 | 1,704.46 | 2,932.61 |
| L | cold_2023/stress | 126 | 4,571.18 | 7,034.44 |
| G | primary_2020/base | 230 | 3,012.77 | 7,462.15 |
| G | primary_2020/stress | 224 | 7,473.97 | 16,439.01 |
| G | cold_2023/base | 108 | 1,266.17 | 2,142.02 |
| G | cold_2023/stress | 106 | 3,668.66 | 5,605.17 |

## G减L冻结门

| 区间/成本 | 收益差pp | 回撤差pp | 日均log差95%CI |
| --- | ---: | ---: | --- |
| primary_2020/base | -6.516215 | +1.025631 | [-0.0001357920228, 2.783144353e-05] |
| primary_2020/stress | -2.642374 | -0.606000 | [-0.0001603842817, 9.074498993e-05] |
| cold_2023/base | -18.553670 | -0.560954 | [-0.0004503860393, 5.571735571e-07] |
| cold_2023/stress | -8.817248 | +0.150544 | [-0.0002932081682, 2.74724548e-05] |

回撤差负表示G更深。主stress收益正增量/回撤不恶化/CI low>0均未满足；G自身四收益>0也为假。域有效和账本财富为正不能补救现金门。结论是unsupported，非仅unknown。CI沿固定252日块/2000次/seed20261018与同indices，单位为日均log差；全部跨零，也未校正整条研究的多轮择题，不当新盲OOS。

## 年度与风险

| 主stress连续年度切片 | L收益 | G收益 |
| --- | ---: | ---: |
| 2020 | -0.241388% | -0.241388% |
| 2021 | -4.535892% | -1.064497% |
| 2022 | +4.119264% | +7.018676% |
| 2023 | -0.157816% | -0.386403% |
| 2024 | +6.187498% | -2.440786% |
| 2025 | +0.620836% | +1.034575% |
| 2026（至10-16） | +0.314411% | -0.232402% |

这些是持续账户年度切片，不是逐年独立冷启动；两起点/两成本也不独立。2020—2025完整年G仅2/6为正，2026不完整年负，不能称穿越周期。全部年度与95family含零贡献CSV保留。

八账户期末均flat、无stale，未发生研究账本破产；四个主窗各有1个历史stale源日，冷启无stale。合计55个gap止损fills、39个损失>1R，跨账户重复事件不当独立经验。极窄初损不是实际损失上界；静态规格/费用/保证金、日线收盘估值与成交模型限制仍在。

主模型未知动作分歧0、已知不参与分歧1；原unknown/open/取消未变0标签。潜在未成交标签未知与真实cash缺价分别报告。历史重建不冒充首发PIT或真实broker成交。

## 决定、反思与下一步

- 固定log曲率代理停止；不继续f、效用族、阈值、N floor、模型或风险小数救参。压缩巨大R赢家并未在这个包中产生所需组合改善；不据此否定所有风险偏好方法。
- 新增按本包成绩调参：否。历史反复试验、目标选择和同史复用的过拟合风险：是，普通bootstrap不能消除。
- 继续这个固定log包：否。继续全市场高质量做多完整目标：是，优先有独立经济依据的信息假设，避免继续换标签冒充新信息；当前没有下一包actual授权。
- 未达到高质量可泛化、极窄损安全、加大投注、更高收益且更低回撤的目标；不晋级正式或生产，不执行Git/CTP/订单操作。

## 精确证据

- protocol：`outputs/stage099_log_utility_protocol/protocol.json`，5339B，SHA `0d51abfc6e466ccda0c293b23dad71928e06b0f5929e395150e90812e6f3582e`。
- science：`stages/20261018_1841_stage098_risk_objective_feasibility.md`，15530B，SHA `3c9ef265f8007e9c09c2adc4da6598c51500a9fb612fc4490974f6fb59b55793`。
- fit_manifest：`outputs/stage100_log_utility_fit/experiment/manifest.json`，17823B，SHA `3f3537caa7e211b6b9a29f791a81678d3d67c0d871130e3ccfef13e7fcb9d53f`。
- fit_terminal：`outputs/stage100_log_utility_fit/experiment/actual_terminal.json`，478B，SHA `e955989d7b12914fe073c0b5e1a8e2c0d51b7be1a09cd65b76c18c4d79a03326`。
- domain_report：`outputs/stage100_log_utility_fit/experiment/domain_report.json`，3093B，SHA `7022ef263199bef05f6a9f016d73bfbeab08d3467d57714d18717d386c07be2f`。
- cash_manifest：`outputs/stage101_log_utility_cash/cash/manifest.json`，44712B，SHA `f543b0d1060e3f2e606811c6bda140337e31c10e2c2b9480cfda8be4bb42ddd2`。
- cash_terminal：`outputs/stage101_log_utility_cash/cash/actual_terminal.json`，518B，SHA `a91530f992e610423704d5f2cfa28a1d8561912b5711fb3b000a2595d60f0e6d`。
- review_receipt：`outputs/stage102_log_utility_review/actual_review1/review_receipt.json`，45916B，SHA `9cd850b3e23ade879e6fa7f8ae310d97284bba2d203aa6fe6b6bf1240e782712`。
- review_terminal：`outputs/stage102_log_utility_review/actual_review1/actual_terminal.json`，303B，SHA `c02801a41d6b3d43f4b957a181f3f0391314481ae5209589630303ce4cc812a4`。
