# Stage102：固定预算log目标的独立审查

- line_id：`futures_full_market_long_signal_ai`；首次记录：2026-10-18 18:52 CST。
- 本轮范围：099固定科学合同、100目标与模型、101原070现金接线；只写102自有文件，不修改LINE、registry、作者源码或历史结果。
- 最终状态：科学/代码预审C/I=0；唯一actual_review1已于2026-10-18 19:02 CST完整退出0，C/I/M=0。研究算术可信，固定log目标不支持继续；重要突破：否。

## 一手调研与科学判断

已先读registry确认本线，读098/099协议及计划，并实读[Boyd作者论文页](https://web.stanford.edu/~boyd/papers/kelly.html)、作者[kelly_code](https://github.com/cvxgrp/kelly_code) README，以及[SPO原论文摘要](https://arxiv.org/abs/1710.08005)。调研支持财富log偏好与算术收益均值不同；Boyd论文另加明确风险约束，不能据log目标保证峰值最大回撤更低。SPO使用下游优化结构，本轮只改Ridge目标、保留score>0与原070分配，不能声称已经实现SPO或联合组合log优化。

预算单位校正成立：原COMMON的成本c以2NM为分母，窄损d=.25NM，故a=d/(d+cu)=1/(1+8c)。L学z=a*y，G学log1p(.0025*z)/.0025，在同52槽、成熟母体、权重、缩放和执行下隔离曲率；L是同单位必要控制，无新信息含义。逐事件变换同号不意味着条件均值或有限Ridge投影同号。

科学C/I=0的边界是：任一成熟训练目标的c/a/y或log域无效必须整候选停止，不删行/clip/epsilon；全部预测完成后才检查OOS闭合且known<=end的域反证，反证只停cash，不回填交易或预测mask。未成熟/open/cancel/unknown目标null。实际共同预算、整手、margin、D减量使兑现风险随路径变化，因此z仅是孤立u计划连续预算效用代理，不是实际组合复利、Kelly概率校准或生存保证。

## 本轮检查与预算

科学预审：`outputs/stage102_log_utility_review/protocol_preflight.json`；精确绑定099协议/计划/098科学文件。5个必要新独审fixture先RED后GREEN（新增无效y仍保留已定义a、a溢出时z保持null的边界，属独审器准备修正，未启动actual），仅验证成本单位、log曲率与精确域边界、未评估未来目标null、52槽缺失处理；0真实输入/fit/cash/SQL。未重跑作者tests或旧套件。

100/101最终审及实际总审详见后文；本轮遵守root精确最终绑定后冻结checker、一次fresh审查。预设训练/OOS域失败分支只核已生成模型与数据，不强迫8cash；本次实际域通过。审查器无实际失败/修复/重启。

## 过拟合与继续价值

开始判断：**有实质历史多轮选题/目标选择风险**。本轮不以新成绩调f、删行或换模型，但固定历史前向拼接也不是新盲OOS。**有条件值得有限继续**：只用一次最多4fit/8cash对照反证固定曲率代理，不能失败后追加f/效用/阈值/N-floor扫描。

预审时只有数学与静态合同支持；本次实际完成后没有alpha或现金增量优势，详见后文。完整全市场高质量long、更高净收益与更低回撤、极窄初损与未来加注目标均未完成。无正式晋升/生产或加注授权。

## 参数与结果记录

本阶段新增独审目标数学/边界fixture与102独立保存现金核适配；研究参数新增/修改/删除均0，历史回测结果修改/删除均0。f=.0025、a=1/(1+8c)、Ridge52维及所有预算沿099，不调参。本独审没有新增金融实验；作者100/101各唯一actual及本独审终态与指标列于后文，不修改任何历史结果。

## 18:58最终代码预审

一次完整静态审100 final `f759aede4ddf57bd8825296fd7950fd3c5f94f93b53983eeb1b08c826409b029`及101 final `3cd20421faf99950292e06679aac99d805a0bb76825b6b8756f0588d625bef89`，读取作者保存7+6新fixtures证明，不重跑作者或旧suite。C/I=0；收据`code_preflight.json`4503B SHA`050ce4eb57a3b2b50026342bae82d002aa11379db14dce2ad3da497e09b58983`。root已完成模型/现金各一次并发送精确final绑定；102将在冻结自有checker后启动唯一actual_review1。

## 19:02实际审查终态与精确闭包

root明确授权后按final输入一次执行，session45678/PID24245，2026-10-18 19:02:29—19:02:53 CST，23.929585秒，1启动/1完整，exit0。没有第二次actual审查，也没有研究拟合/现金重跑。目标数学准备阶段新增无效y/a溢出边界先RED后GREEN，首次准备draft保留于`preparation_snapshot/`；另在actual启动前将原R经CSV再次导出的浮点末位比较容差设为1e−10+2e−11相对（实际最大误差1.42e−14），并使域失败摘要仅汇总有限数，未改变研究数据或算法。

| 文件 | bytes | SHA256 |
| --- | ---: | --- |
| 100 final manifest | 17823 | `3f3537caa7e211b6b9a29f791a81678d3d67c0d871130e3ccfef13e7fcb9d53f` |
| 100 actual terminal | 478 | `e955989d7b12914fe073c0b5e1a8e2c0d51b7be1a09cd65b76c18c4d79a03326` |
| 101 final manifest | 44712 | `f543b0d1060e3f2e606811c6bda140337e31c10e2c2b9480cfda8be4bb42ddd2` |
| 101 actual terminal | 518 | `a91530f992e610423704d5f2cfa28a1d8561912b5711fb3b000a2595d60f0e6d` |
| 102 checker freeze | 4956 | `34f8156eae1531fc9a251044e16e4336c5bda3e24e13079783b7bd6a6d70c5c5` |
| 102 review receipt | 45916 | `9cd850b3e23ade879e6fa7f8ae310d97284bba2d203aa6fe6b6bf1240e782712` |
| 102 actual terminal | 303 | `c02801a41d6b3d43f4b957a181f3f0391314481ae5209589630303ce4cc812a4` |
| 102 process terminal | 1943 | `75bb463fa41785c22ded3819debdefbf27c960411d2dc1f37fc3cc47b88559d5` |

全部绑定的source/test/auth/protocol/artifacts按各自真实schema核闭包，不假定历史071/094的manifest同形。100正常completed与科学domain_failure、执行failed三种终态明确区分。自有8文件快照存actual_review1/checker_snapshot，最终源码与开始时一致。唯一命令（stdout另存同目录的actual_review1_stdout.txt）：

```text
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage102_independent_review.py --fit-manifest research/lines/futures_full_market_long_signal_ai/outputs/stage100_log_utility_fit/experiment/manifest.json --fit-sha256 3f3537caa7e211b6b9a29f791a81678d3d67c0d871130e3ccfef13e7fcb9d53f --fit-terminal-sha256 e955989d7b12914fe073c0b5e1a8e2c0d51b7be1a09cd65b76c18c4d79a03326 --cash-manifest research/lines/futures_full_market_long_signal_ai/outputs/stage101_log_utility_cash/cash/manifest.json --cash-sha256 f543b0d1060e3f2e606811c6bda140337e31c10e2c2b9480cfda8be4bb42ddd2 --cash-terminal-sha256 a91530f992e610423704d5f2cfa28a1d8561912b5711fb3b000a2595d60f0e6d --output research/lines/futures_full_market_long_signal_ai/outputs/stage102_log_utility_review/actual_review1
```

本独审实际预算：0新SQL、0fit、0研究现金/完整native策略重放、0新标签、0下载、0旧suite、0旧模型重核、0整库/H5 hash。作者本轮真实预算为100四fit/27.175445秒/0SQL，以及101八cash/18.062491秒/共享1SQL。继承已接受COMMON与标签来源；没有重新清洗或认证旧全库。仅重构当前目标与模型、已保存现金恒等式及有限native案例。

## 目标、成熟与四模型

399252母体ID、COMMON26和事件顺序一致；52项仅COMMON标准化26+未缩放缺失指示26，无RFF/OI/外部缺失/held槽。每cutoff只用本政策closed且u与非空known_date均严格小于cutoff；family闭区间并发唯一性→每u同权→mean1权重、train-only有限均值/总体方差/scaler独立重算。L/G逐行共享ID、权重、scaler与X；仅目标z与log1p(.0025*z)/.0025不同。没有因未来closed、finite效用、实际filled或D拒绝筛预测。

| cutoff | own mature训练 | 每臂完整预测 | L selected | G selected | 动作分歧 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2020-01-01 | 81903 | 71344 | 260 | 222 | 38 |
| 2023-01-01 | 121467 | 89670 | 244 | 224 | 20 |

共4个52系数+截距模型的53×53正规方程独立核验，最大残差9.9863e−10；lhs/rhs与独立重构差0。全部322028分数由保存portable系数与独立重建X计算，最大差2.22e−16；合并预测的全部身份/score/selected/readiness/cutoff与逐fold保存相同，2020/2023拼接不重不漏。未import作者模型core或重新fit。

训练81903及121467行全部有效；完成全部前向预测后，101940个OOS闭合且known<=2026-10-16机会逐行c/a/z/L/G/wealth/domain重构有效，invalid=0。完整399252域投影中，其余297312行的新目标列保持null与原状态；没有用域作交易mask。OOS参考wealth factor范围[0.96696535,1.26735200]，a范围[0.05065670,0.96913042]。这只是有限历史域成立，不证明未来正财富、负log尾可积或实际组合生存。候选domain_failure分支本次没有触发，其保证来自静态流程审读与必要边界fixture，不冒称真实失败分支已实际运行。

G较L主cutoff少38个selected、后cutoff少20个，动作分歧分别38/20；全部四对现金fill签名不同。该收缩不等于oracle集合包含定理，也没有新增信息含义。主预测161014/臂仍保留7类原标签状态；动作分歧中未知未闭合0、已知取消1，取消不伪装成负标签。未selected的原未知仍在全母体中。

## 八个现金账本及固定门

逐笔独立核1492 fills、2586 position-days、10232 daily、745 closed roots、0期末open、2839 reservations。核所有selected意图/拒绝保留、u时点联合原070预留/共同scale/floor、D只减量、费用、Decimal不利滑点、冻结持有risk、margin、现金/未实现盈亏/权益、Sharpe/DD、胜率、年度与全部95family含0格归因。无080预过滤或额外再分配。12个确定性首分支保存native案例由完整Wilder暖机重算N/20low/.25N初损/first-hit及open退出，覆盖两臂entry-day stop/later-boundary/epoch换约/gap/deferred/missing。不是全库native独立重放；其余执行核继承已接受070固定纯核。

| 账户 | 期末权益CNY | 总收益 | 最大回撤 | Sharpe | 总滑点CNY | closed次数 | 净胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| L_primary_2020_base | 1,228,549.38 | 22.854938% | -5.583249% | 0.639584 | 10,168.24 | 142 | 16.1972% |
| L_primary_2020_stress | 1,061,109.78 | 6.110978% | -5.579406% | 0.280798 | 21,544.59 | 141 | 14.8936% |
| L_cold_2023_base | 1,170,245.54 | 17.024554% | -3.920594% | 1.029868 | 2,932.61 | 65 | 15.3846% |
| L_cold_2023_stress | 1,069,543.82 | 6.954382% | -4.799666% | 0.655341 | 7,034.44 | 63 | 14.2857% |
| G_primary_2020_base | 1,163,387.23 | 16.338723% | -4.557618% | 0.507147 | 7,462.15 | 115 | 15.6522% |
| G_primary_2020_stress | 1,034,686.03 | 3.468603% | -6.185406% | 0.168898 | 16,439.01 | 112 | 14.2857% |
| G_cold_2023_base | 984,708.83 | -1.529117% | -4.481547% | -0.183901 | 2,142.02 | 54 | 11.1111% |
| G_cold_2023_stress | 981,371.34 | -1.862866% | -4.649122% | -0.234251 | 5,605.17 | 53 | 11.3208% |

固定252源日块/2000次/seed20261018的原indices逐项绑定，未重新抽样；四组CI分布由八本日log权益差独立重算。CI单位是平均日log差，收益与DD差单位是百分点；它们不是2000个独立市场。

| 窗口/成本 | G−L收益pp | G−L DD pp（正为更浅） | CI95低 | CI95高 |
| --- | ---: | ---: | ---: | ---: |
| primary_2020/base | -6.51621525 | 1.02563098 | -0.0001357920228 | 2.783144353e-05 |
| primary_2020/stress | -2.64237425 | -0.60600009 | -0.0001603842817 | 9.074498993e-05 |
| cold_2023/base | -18.55367025 | -0.56095376 | -0.0004503860393 | 5.571735571e-07 |
| cold_2023/stress | -8.81724815 | 0.15054397 | -0.0002932081682 | 2.74724548e-05 |

主stress G收益3.4686034%低于L的6.11097765%，最大回撤−6.18540561%深于L的−5.57940553%；四组收益差全负，四组CI均跨0，G两个cold账户收益为负。因此固定门nominal unsupported，已有明确反证，无需靠unknown或尾部假设才能拒绝。

八本实际财富路径均正，期末均无open。四本primary各有1个历史stale日，四本cold为0；`financial_unknown=true`保留，不能因最终平仓删除当时估值未知。unfilled信号标签未知与实际现金未知分开；正常open的既定研究mark及零价情景不自动当普遍损失界。原unknown/stale未建立能排除翻转差异的普遍界，不能给强生存结论。

## 最终判断、局限与TODO

**计算/数据/逻辑/数值/置信披露/bug独审：C/I/M=0，原作者本轮研究算术可信。研究效应：固定log曲率相对同单位L无增量优势，关闭此包。完整目标：未达到。** L本身不是相对旧y的新alpha证明，本轮没有旧y控制、family留出、新盲OOS或正式多起点资格；不能据L正收益单独复活083，不能把G的目标偏好解释为新市场信息或强Kelly/生存。

结束过拟合判断：**存在实质历史多轮选择风险**，本轮没有按结果再调f、threshold、N-floor、效用或模型；本次拒绝不授权追加CARA/CRRA/CVaR或风险倍率扫描。普通bootstrap不校正多轮择题，也不创造新的时间样本。现有成熟样本条件于已闭合，未知可能非随机，long-only、窄止损及样本内wealth正均不提供普适损失上界。Polanyi式经验直觉可警觉尾部与成本错配，但不能替代这些反证。

结束继续价值：**固定log包：否，应停止；全市场高质量long、更高净收益与更低回撤的目标：仍有价值。** 极窄初损普适性、右尾捕获、未来加注与穿越周期能力仍未证。本阶段不提出或启动另一轮试验，不修改已冻协议/源码/参数/账本，不晋升正式或生产。后续只交root据此做路线决策与本地记录；资产全清单见`outputs/stage102_log_utility_review/artifact_inventory.json`，本独审至此冻结。
