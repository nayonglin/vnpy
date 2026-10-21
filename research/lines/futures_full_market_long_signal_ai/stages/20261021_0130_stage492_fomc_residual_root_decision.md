# Stage492：匿名宏观信息包未达成收益与回撤同时改善

- line_id：`futures_full_market_long_signal_ai`；当前模式day；记录时间2026-10-21 01:21 CST。
- 工作区`/Users/mac/Desktop/fian`，沿`codex/ai-training-data-expansion`；阶段性质：固定新信息实验，非重要突破，非正式C9推广。本研究基线为全市场long-only A157自己四账。
- 当前状态（2026-10-21 01:30 CST）：来源/模型/8账与独立审查已完成；接受已核scope的研究算术，关闭固定FOMC/流动性残差包。完整目标active未完成。

## 外部调研及自己的判断

[英格兰银行WP1114](https://www.bankofengland.co.uk/-/media/boe/files/working-paper/2025/liquidity-monetary-policy-and-the-commodity-futures-market.pdf)提供公告前流动性影响海外商品冲击响应的先验；[固定作者GitHub](https://github.com/marekjarocinski/jkshocks_update_fed/tree/f788aef7d573f87f28b70ffc3763e73c4886a53f)提供原FF4/SP500数值。二者不提供中国全市场至少25h后可执行收益证明。以匿名数值避免未经核证的经济正号，仍不能解决跨年代口径/首发PIT。

判断：本次固定包未显示目标所需增量；不能凭压力成本下C比B略好挑选结论，因为两基础成本下C反而更差、四场景都输A。独立结果复核未发现已核scope实质计算错误；不据负结果翻符号/换央行/加窗口/加模型救参。

## 本次变更及参数

新增488精确源投影、489低维残差头与491薄现金入口；新增490一次审查器。原正式版及其他研究线源码未改。B显式常数与Lz共2参数，C另加FF4z/SP500z及其Lz交互共6参数，alpha1仅罚非恒项，交互不再次缩放。L先按所有事前可测候选等family/child中心化，成熟训练才计算各fold权重/scaler；同样本原52残差非crossfit。

2020/2023×main/held0/held1×B/C=12微型fit，原六个52模型不重训。pre域需双方raw有限、同epoch公告前V/S/M为正且source数值核验、原u资格和155 D<K；缺失、无事件或不在域，双方score逐值沿用原A。全部六所98历史产品/95family、完整161014前向母与966740主子保留；不按未来结果筛机会。

止损0.25N、20low、退出K、单family0.25%风险/总2%/25%缓冲保证金/1.10buffer、整数手、1%量容量、原基础/压力费用滑点全部不变，资金100万元。2020连续账户在2023更新头不清仓；2023冷启从空仓独立开始。8新现金，A157自身四账只读，绝不回放其131B baseline_refs。

新增/修改回测结果为本12微型fit及8本新账；没有删除或改写旧结果，也没有新增止损/本金/投注倍率。累计493实际fit/266完成cash及1旧partial。新观测和完整母体不代表95个独立市场样本。

## 来源实测、技术故障与实际计数

54,089 exact(epoch,pre_date)请求，原日线存在50,060、缺失4,029。源数值与成交额log通过50,005；48条结算价越native范围、7条source OHLC冲突保留未知，不修补或删母；规则/PIT未知与数值可见分开。V沿clean单边量，不二次折半；exact现金乘数为静态快照/CNY研究代理，不认证逐日法定单位。

首次source24896因root4096文件上限在9.727781秒真实exit1，已读4096CSV/87,318,923B、SQL1，H5/Y/COMMON/fit/cash0。该上界误沿代表母场景。收益前显式child协议仅改CSVcap为exact请求数54,089及累计读取/失败记录，科学字段逐键同原。恢复唯一84233 exit0/16.950146秒，4400CSV/88,373,421B、H5两打开/7112key访问；累计源SQL2，重复读取明确保留，不冒称缓存恢复。原协议和失败现场保留。

489唯一33689 exit0，76.879474秒、12/12fit、0SQL；2020主训练7213行/81宏观事件/67family，2023为13383/108/76。两个held共享81/108冲击，label留出且可见全市场事前X。主前向applied16242、共同mask fallback17948、非事件932550；原全score1933480一次流，原129动作/COMMON各一次，未重读原399252大母流。

491唯一96255 exit0，30.546106秒，8/8现金、0SQL/旧账重放/fit；每账数值完成先checkpoint再报告。实际数据区间截至2026-10-16，不等待今天新日线。只有原四前瞻账本依赖D21真实完成，二者独立。

## 完整金融结果

| 版本 | 起点/成本 | 期末权益(元) | 总收益 | 最大回撤 | Sharpe | 闭合交易/成交笔 | 净胜率 | 手续费(元) | 滑点归因(元) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A原模型 | 2020连续/基础 | 2,229,270.22 | 122.927022% | -15.627420% | 0.978453 | 1295/2592 | 12.2008% | 52,034.78 | 140,259.04 |
| A原模型 | 2020连续/压力 | 1,528,419.71 | 52.841971% | -11.359301% | 0.787447 | 952/1912 | 12.0798% | 68,710.29 | 167,960.05 |
| A原模型 | 2023冷启/基础 | 1,825,436.55 | 82.543655% | -9.902149% | 1.320956 | 494/990 | 12.9555% | 20,778.45 | 53,623.57 |
| A原模型 | 2023冷启/压力 | 1,526,645.82 | 52.664582% | -6.422761% | 1.223020 | 422/849 | 13.0332% | 36,269.18 | 83,952.08 |
| B流动性 | 2020连续/基础 | 2,128,925.79 | 112.892579% | -15.224931% | 0.922670 | 1498/2998 | 11.5487% | 53,724.21 | 144,550.77 |
| B流动性 | 2020连续/压力 | 1,497,453.42 | 49.745342% | -9.957200% | 0.785486 | 943/1894 | 12.4072% | 67,661.58 | 164,815.14 |
| B流动性 | 2023冷启/基础 | 1,731,133.09 | 73.113309% | -8.786800% | 1.268928 | 600/1202 | 12.5000% | 20,831.91 | 54,375.70 |
| B流动性 | 2023冷启/压力 | 1,498,763.59 | 49.876359% | -7.067230% | 1.243352 | 418/841 | 13.1579% | 35,746.41 | 82,908.88 |
| C宏观包 | 2020连续/基础 | 2,117,804.04 | 111.780404% | -15.322377% | 0.925555 | 1478/2958 | 11.4344% | 53,160.96 | 142,975.40 |
| C宏观包 | 2020连续/压力 | 1,517,536.90 | 51.753690% | -10.146421% | 0.810428 | 956/1920 | 12.6569% | 68,518.10 | 166,561.52 |
| C宏观包 | 2023冷启/基础 | 1,582,320.33 | 58.232033% | -8.518144% | 1.083049 | 568/1138 | 11.6197% | 19,759.67 | 51,874.85 |
| C宏观包 | 2023冷启/压力 | 1,516,887.22 | 51.688722% | -6.178197% | 1.281521 | 435/875 | 13.5632% | 36,717.78 | 85,281.09 |

净胜率以已闭合交易成本后PnL计算；成交笔数与闭合交易数分列。滑点归因已包含成交价格，不再次从权益扣除。所有账期末2个open；历史stale和执行容量未知沿原模型保留，不能把此研究DD当可实盘风险保证。

## 差异与置信度

| 比较 | 起点/成本 | 收益差(pp) | 回撤差(pp，正为较浅) | 日均log差 | 原配对95%CI |
| --- | --- | ---: | ---: | ---: | --- |
| B_minus_A | primary_2020/base | -10.034443 | 0.402489 | -2.80321035e-05 | [-8.01262451e-05, 1.62748701e-05] |
| B_minus_A | primary_2020/stress | -3.096629 | 1.402101 | -1.24579367e-05 | [-5.6164517e-05, 2.65326936e-05] |
| B_minus_A | cold_2023/base | -9.430346 | 1.115349 | -5.79704965e-05 | [-0.000176790092, 1.5895537e-05] |
| B_minus_A | cold_2023/stress | -2.788223 | -0.644469 | -2.01448741e-05 | [-6.51975983e-05, 1.12992797e-05] |
| C_minus_A | primary_2020/base | -11.146618 | 0.305043 | -3.12200584e-05 | [-7.72079394e-05, 6.74283475e-06] |
| C_minus_A | primary_2020/stress | -1.088281 | 1.212880 | -4.34922339e-06 | [-4.17463552e-05, 2.80089416e-05] |
| C_minus_A | cold_2023/base | -24.311623 | 1.384004 | -0.000156204191 | [-0.000351311421, -1.725582e-06] |
| C_minus_A | cold_2023/stress | -0.975860 | 0.244565 | -7.00841764e-06 | [-5.3668343e-05, 4.19833079e-05] |
| C_minus_B | primary_2020/base | -1.112176 | -0.097446 | -3.1879548e-06 | [-2.6482578e-05, 1.77381422e-05] |
| C_minus_B | primary_2020/stress | 2.008348 | -0.189221 | 8.10871331e-06 | [-6.28378106e-06, 2.41534838e-05] |
| C_minus_B | cold_2023/base | -14.881277 | 0.268655 | -9.82336943e-05 | [-0.00027517864, 3.83351378e-05] |
| C_minus_B | cold_2023/stress | 1.812363 | 0.889033 | 1.31364564e-05 | [-1.22875795e-05, 4.05560138e-05] |

C-A四收益差全负，四DD较浅；C-B仅两压力收益正，主压力DD反更深，四CI均跨0。C-A冷2023基础成本CI上端也负，但属于同史自适应与多比较条件证据，不能外推独立统计发现。其余C-A CI跨0。

同账截至2025年，C-A四收益仍全负（原账派生，不重置或新跑），不是单靠2026不完整年导致。main前向选中A4365、B6090、C6269；更多候选未转化为更高收益，不据此事后改阈值。

held C-A已知等u增量：holdout0=-0.0021484037R（9不同动作未知），holdout1=+0.0009355727R（11未知）；C-B=-0.0001703523R（8未知）/+0.0025145848R（7未知）。未知不填0，同动作相消不等于已知终值，未知边界没有证明。两个held不是不同宏观冲击集；252日/2000次同索引CI只条件于固定历史政策，非新盲OOS。

## 独立复核

490最终已完成来源、12头、完整main A身份、九张新choice、8资金账及12组×2000原配对CI核验。实际核13,826 fills/10,232 daily/17,374 positions/35,488 budgets，已核source/model/maincash material P0/P1/P2=0/0/0；审查器自有metric比较最大误差约2.33e-10，不冒称覆盖复用helper全部内部误差。

第一次审查88370在source_phase完成后被1.006e-16 raw小数解析差停止；续审83283已核12头/COMMON 1,406,314标量/完整1,933,480 score流/所有overlay及main A严格身份，仅在A保存score的4.44e-16串化误差停。最后tail1973真实exit0/67.368721秒，仅新产物选择/资金/CI尾审，采用分数1e-12容差，identity/eligibility/选择保持严格；不重复已验源和旧大流，0fit/策略回放。全部失败现场和读取计数保留，没有伪称第一次全审就通过。

累计审查原精确SQL/COMMON/130scores/156十列/nativecache各1；原129Y、CSV/H5大内容和399252母重扫0。source值的原CSV/H5 parser资格继承已审067桥接，不说逐原值二次认证。held非事件A历史绝对winner继承已审算法/原流守卫，未再次独立重数；事件选择独立由已核overlay重建、非event B/C对new A严格一致、held差异算术已核。故不签无边界all-scope独立0/0/0；所有held未知、PIT及泛化边界照旧。

[独立中文报告](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261021_0129_stage490_fomc_economic_final_independent_review.md)；[最终小闭环](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage490_fomc_economic_independent_review/final_small_closure.json)；[最终receipt](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage490_fomc_economic_independent_review/actual_review_tail1/review_receipt.json)。

## 裁决与反思

最终裁决unsupported：没有同时更高收益、更低回撤的证据，不晋级，不增加投注。独审已确认有限scope算术，关闭此固定FOMC/流动性残差包；不扫延迟/字段/经济符号/窗口/alpha/风险或删除弱年品种。

运行前新增按收益调参过拟合：否；运行后救参：否。长期同史多轮择题风险：是且高，不能称此次为全新盲测。首次source预算及审查器float问题是有记录的技术恢复，不修改科学规格，但也不隐藏额外读取。

继续本固定宏观包价值：否，收益门和held均未支持，未知资格也不完整。继续全市场高质量做多目标：是，有条件转向真正不同的机制/信息；完整目标未达成。极小标称止损不能限制跳空亏损，当前没有加大投注资格。

root已于2026-10-21 01:30 CST更新LINE/registry本行；非重要突破不追加根memory/back_log。生产/CTP/邮件/launchd/原四前瞻/Git分支和发布均未改变。

## 可复验产物

- [root决策](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage492_fomc_residual_root_decision/decision.json)，SHA256`20dbdbcebac5fd09407cc6d6035c50332c14dd5be20f1b86fc422f43edd0832b`。
- [12账户完整指标](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage491_fomc_cash/actual_run1/account_summaries.csv.gz)。
- [12组对比与CI](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage491_fomc_cash/actual_run1/comparisons.csv.gz)；[95family逐年含零归因](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage491_fomc_cash/actual_run1/family_year_including_zero.csv.gz)。
- [截至2025同账切片](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage491_fomc_cash/actual_run1/same_book_through_2025.csv.gz)；[held原未知与符号](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage489_fomc_residual_experiment/actual_run1/held_gate.json)。
- [现金manifest与8账路径](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage491_fomc_cash/actual_run1/manifest.json)；[原协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage487_fomc_residual_protocol/protocol.json)；[仅来源预算恢复child](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage487_fomc_residual_protocol/protocol_source_budget_recovery1.json)。
