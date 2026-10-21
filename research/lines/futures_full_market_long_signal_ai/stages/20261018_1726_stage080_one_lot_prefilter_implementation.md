# Stage080 固定NARROW/COMMON的一手可达预过滤实现

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 17:26 CST；沿当前checkout/分支。
- 重要突破：否，当前只实现与合成，目标active未达成；实际新增fit/cash/label/SQL/download/整DB-H5 hash全部0。既有累计333fit/66cash不变。
- 079协议SHA固定`421722dd73ba0b4c43656b9439766afcf80c723b095160ace4742114050afce3`；不改070任何源码/输出、LINE/registry、他线或正式版。

已实际浏览[SPO原论文摘要](https://arxiv.org/abs/1710.08005)及[Cvxportfolio维护方策略源码](https://raw.githubusercontent.com/cvxgrp/cvxportfolio/master/cvxportfolio/policies.py)。判断：预测与可行决策应区分，但外部研究并不证明本一手预过滤会提高收益。075—077已证明预算存在合法空间，单一规则值得做一次固定模型的资金机制反证；不据外部收益或新回放选择阈值、排序或分配轮次。

唯一新算法在local reserve_batch：原family/经济/期限/持仓/超额与破产规则完成后，以当时u的E/已有冻结风险/缓冲保证金检验L*r<=.0025E、L*r<=剩余.02E、L*m<=剩余.25E。不可达者全保留，并存raw_target_qty_unscaled=S/r、prefilter_eligible/reasons、各资源限额和一lot资源；joint_input_qty_unscaled/兼容target_qty_unscaled、prefloor、风险/保证金/费配额、qty cap均0，不进入共同scale分母。可达集合仍用原实数目标、共同scale和lot floor，无二次余量分配、score排序、加一手或新参数。

单文件stage080_one_lot_prefilter.py隔离复制070 run_cash_account定义，源码正文逐字相同，函数在本模块解析新reserve，不全局monkeypatch旧module。quote/ledger/市场/风险缩减/退出/未知/同family/quote取消/原D.open止损/因果20low、D配额只减与不回收均沿已接受070纯定义。保存joint_scale_original_same_u和qty_cap_original_same_u作同当前状态纯算术对照；它不是原现金账户的历史状态或额外回测。

未来实际仅NARROW/COMMON固定161014前向分数与完整399252母体，两起点×两成本4cash共享一次native，0fit/新label/下载/整大库hash。只读取079绑定的原四daily/summary与既有bootstrap indices，不重跑基线、不读原reservation作逐event旧D比较。导出新完整fills/reservations/rejections/daily/positions/closed/open、四新四原指标与配对log CI、年度与全部family含零、prefilter日/候选/同u cap变化、实际aggregate total_filled_qty差、成本/未决/零价、科学继续门。资金路径会内生分歧，报告明确区分两种对照。

同次必要native arrays中，确定性保存首次三类prefilter/new-u qty cap gain及entry-day/later/gap/旧epoch/lifecycle/missing/deferred有限路径，含连续Wilder暖机到决定日、缺日、reference schedule、经济与u批次配额，不按PnL选择。沿070纯collector，不新增SQL或全native复制；schema沿stage070_finite_first_native_cases_v1，存入本080输出finite_native_cases.json.gz。

TDD先观察缺实现6项红，再实现并验收6项全部绿：单family/剩余风险/剩余保证金一lot不可达、只可达集合共同scale且全行保留、无剔除时每个旧reserve字段相同、D数量只减。只运行test_stage080_one_lot_prefilter.py，不跑旧suite。源码/测试/命令和精确SHA见outputs/stage080_one_lot_prefilter/implementation_receipt.json；root另交081独立预审。CLI需固定079 SHA、root exact source bundle与freshdir授权，失败保留且无自动重试；本实现和拟命令均不是实际授权。

新增/修改/删除交易参数0；旧金融结果改删0；未来最多4新cash与1SQL尚未执行。期末权益、收益、DD、Sharpe、总滑点、交易次数、胜率当前均N/A。

开始/结束是否新增按成绩调参过拟合：否，当前只实现已冻单一机制且0金融新结果；研究者看过旧收益，择题风险仍在，不能称全盲。继续有价值：是，限一次固定模型/固定退出/固定预算下的4cash直接证伪；有动作空间不等于能提升收益与回撤。若079门不支持则停止此规则，不救参数，目标仍active。

17:29 一次实际结果：root在081预审C/I0与fresh source/protocol核对后签精确授权，由owner唯一运行至fresh experiment/，16.530865秒exit0。实际4started/4completed共享native SQL1；新增fit0/label0/基线重跑0/下载0/整DB-H5 hash0，无修复重试。科学合同、源码、原070结果均未改。累计仍333fit，现金由66增至70；无正式/生产/CTP/邮件/订单操作。

| 新账户 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点CNY | 总费用CNY | fills条数 | 闭合root数 | 闭合净胜率 | 双边成交合约手数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| NARROW_COMMON_primary_2020_base | 1,482,007.3595 | 48.20073595% | -19.03124958% | 0.58374592 | 54,897.7979 | 26,597.6405 | 1085 | 541 | 17.74491682% | 7186 |
| NARROW_COMMON_primary_2020_stress | 1,217,733.8440 | 21.77338440% | -11.83839162% | 0.48845629 | 83,926.5543 | 44,946.1560 | 997 | 492 | 17.88617886% | 3778 |
| NARROW_COMMON_cold_2023_base | 1,645,097.6170 | 64.50976170% | -19.26365058% | 1.07767473 | 43,873.7096 | 23,012.3830 | 757 | 377 | 19.89389920% | 6994 |
| NARROW_COMMON_cold_2023_stress | 1,192,915.0415 | 19.29150415% | -11.87029932% | 0.74992289 | 54,860.0336 | 31,839.9585 | 655 | 324 | 20.67901235% | 3121 |

交易次数明确区分：fills是逐笔买/卖成交记录条数；closed是完全退出的root次数；total_filled_qty是买卖双边成交合约手数合计，不能将正差称为新增开仓次数或新增信号。

| 对应账户 | 原收益 | 原DD | 新−原收益pp | 新−原DD pp | 配对日log CI95 | 双边成交手数新−原 |
|---|---:|---:|---:|---:|---|---:|
| NARROW_COMMON_primary_2020_base | 48.36785860% | -18.72447902% | -0.16712265 | -0.30677055 | [-1.380866623e-05, 1.447822849e-05] | +100 |
| NARROW_COMMON_primary_2020_stress | 22.44352890% | -11.91382590% | -0.67014450 | +0.07543427 | [-3.276940706e-05, 1.709109769e-05] | +98 |
| NARROW_COMMON_cold_2023_base | 64.87658025% | -19.09036867% | -0.36681855 | -0.17328191 | [-7.551798861e-06, 8.063562197e-07] | +66 |
| NARROW_COMMON_cold_2023_stress | 19.37163390% | -12.02385946% | -0.08012975 | +0.15356014 | [-5.65835798e-06, 4.154034426e-06] | +90 |

四组合收益全低于已接受070，CI均跨0；主2020stress收益下降0.67014450pp，虽然DD浅0.07543427pp，未通过主收益/CI门；base两起点DD更深。079 nominal continuation gate为unsupported，继续本可达预过滤方案无支持，停止，不调qty/阈值/score排序/模型/止损救参。075—077的合法动作空间证书保留：预算存在空间与替代分配赚钱是不同命题。

本次新路径3486候选记录中972条被prefilter，742个账户u有prefilter（两窗口重叠、两成本分别计，不当独立日期样本），同当前u纯算术qty cap合计增加295。这些数字来自新账户内生权益/持仓状态，不能直接与075的317个单family不可达证书对比，也不是原历史现金路径的逐event增量；历史原现金只读既有daily/summary，实际数量比较仅用双边成交合约手数aggregate差。未额外读取原reservation、没有基线回放。

完整4账户新账本、四新四原汇总、年度切片、全family含零贡献、prefilter逐u/全部候选与raw target/三约束、费用/换手/未决/零价及确定首次原因finite native slices均在experiment manifest内。主比较未识别差异historical stale，zero-price仍为情景而非有限普遍损失下界，所有账户期末保留1或3个正常开放root，未终点强平。原始触价/排队/盘内gap限制仍在。root已绑定final manifest并授权081唯一全面实际复核；作者数字汇总不是独立复核证据。

- manifest.json：23957 bytes，SHA `4050b45b208f74ed33f57427d4f3961907e03c9653f70ebe735e7cbc30600d5f`
- actual_terminal.json：500 bytes，SHA `6993594897f2a2febcae0bda8508c86033ef555559cef5b933a7cf0bc6eef6e6`
- continuation_gate.json：354 bytes，SHA `275b184518a4797b73b823e6794f0083b4ef82470fea1729d385b4458a92c313`
- finite_native_cases.json.gz：29876 bytes，SHA `43a1ba1bdb2c15d1e738f51d33bc0d826ff53f81297b6102297fe7c946ac83e3`

结束是否新增按成绩调参过拟合：否，冻结单点规则仅实际一次，失败后未继续搜索；研究题目来自已见旧历史，研究选择风险不能被一次CI消除。继续救此固定规则有价值：否，四收益均更低、主CI不支持且base DD更深。完成独立审计与保存仍有价值：是，以确认预算算术、真实交易、成本和置信度；全市场高质量做多/更高收益更低回撤总目标仍active未达成。
