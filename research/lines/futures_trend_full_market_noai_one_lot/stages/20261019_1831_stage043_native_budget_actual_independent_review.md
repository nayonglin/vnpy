# Stage043：原生风险预算cap1完整实际结果独立审查

审查时间：2026-10-19 18:31（Asia/Shanghai）。所属研究线：`futures_trend_full_market_noai_one_lot`。源：`outputs/run_20261019_native_budget_one_lot_v1`。重要突破：不是alpha突破，是恢复用户预算合同后的完整研究账本。

**结论：PASS WITH LIMITS，仅限本次日线近似研究。** 全账本、原信号预算、真实开盘预算、1手上限与生命周期核验通过。仍有5个继承的孤儿target重挂尝试，已由当前授权闸门在成交前全部拒绝，作为P2缺陷披露；没有把它们当正常有效授权，也不改冻结结果掩盖。不是完整C9、实盘或正式晋级资格认证。本代理没有金融重跑，没有修改源run/代码/LINE。

JSON顶层source_manifest_sha256精确绑定：`a8696e2b73b25399251d1efc46e47dfd49f89d23bfc80f6bc1f33bfdbe5237c3`。这是实际独立verdict，未因源summary自称performance_certifiable而自动盖章。

## 独立重算的完整结果

| 指标 | 独立核验值 |
|---|---:|
| 起始资金 | 1,000,000 |
| 期末权益 | 1,832,070.63 |
| 净收益 | 832,070.63（83.2071%） |
| 最大回撤 | -226,771.77（-18.3470%） |
| Sharpe（240交易日、日对数收益、样本标准差） | 0.405520 |
| 自然日期CAGR | 约5.2698% |
| 手续费 / 滑点 | 45,474.37 / 148,490.00 |
| 总成本 | 193,964.37 |
| 成交 | 6,130（开3,071 / 平3,059） |
| 完整平仓episode / 净胜率 | 3,059 / 33.3442% |

分析边界2015-01-01至2026-10-16，实际2862个日账户边界为2015-01-05至2026-10-16。源annual_return=6.9775%是按240交易日线性折算，并非自然日期CAGR。期末权益也由初始资金+已平净807,065.830098+未平浮动25,315−其入场成本310.19842独立重建。

独立逐笔按静态开/平/平今费率核费，最大误差2.85e-14；滑点误差0；3059个episode配对净收益误差不超过2.92e-11。逐日从真实收盘与实际成交重建holding/trading/net PNL，最大误差约1.46e-11/3.64e-12/7.28e-12；权益与快照误差约3.3e-9，全部每日持仓一致。源账户PASS现在还补上了预算资格逐笔检查，旧fixed_size诊断结果不能改名认领本轮。

## 每笔开仓的原预算及开盘复核

协议fixed_size=0，min=max_position_size=1；AI pool、pairwise、加仓关闭。真实3071笔OPEN全部有唯一冻结SignalRiskBudgetSnapshot，原始contract/product/side/signal/date与trade一致，实际entry_risk均sizing_method=risk_budget，target_risk_amount等于冻结原授权，filled_entry_price与实际风险同步正确。包括3014次flat_entry与57次rollover_reopen，没有换月绕过预算。

逐审计行独立重算原预算：`clamp(signal limited_balance×risk_ratio, monetary min,max)×final effective_multiplier×overheat×directional30d`；再按审计时的开盘权益、冻结sizing上限/usage及当前reserved重算同一货币预算，取与原授权的min。全部公式匹配。risk使用真实open到有效stop×size，至少一tick价值；全部实际OPEN满足 `risk≤current budget≤signal budget`，最大risk/current budget约0.995657。

独立按前日真实仓位到今日open的holding leg和已真实发生成本重建每次审计的opening_equity，最大误差约3.3e-9。当前reserved不低于逐笔实际持仓的真实open保证金底线；其它pending额外预留介于数值舍入0与385,243.20。private pending-layer逐项组成没有输出，故不能声称对此部分逐项独立重建；该合计进入预算的算式完整核验，具体预留代码及合成集成已独立审查。

3238次OPEN填单审计中3071成交、167拒绝。拒绝分解：157次开盘已越有效stop、5次一手风险超预算、5次无当前绑定授权。拒绝order_id没有任何actual fill，未记成交费用；不能把167次都说成“风险金额超预算”。账户实际仓位没有任何拒单假仓。

## 5次无授权拒单：继承缺陷及限度

| 真实拒绝日 | 合约 | 原始意图日 | 原意图 |
|---|---|---|---|
| 2020-06-19 | m202009.DCE | 2020-06-11 | long_case2 |
| 2021-09-09 | pg202110.DCE | 2021-09-06 | long_case2 |
| 2021-11-10 | b202201.DCE | 2021-11-05 | short rollover_reopen |
| 2023-06-19 | RS202309.CZCE | 2023-06-14 | long_case2 |
| 2024-04-15 | fb202406.DCE | 2024-04-10 | long_case2 |

五案都直接可见：原信号有entry_risk授权但未filled；下一交易日无accepted正量bar而defer；随后主力映射切到其它合约；旧合约bar回归后，新order尝试时signal_snapshot={}、effective stop缺失。当前闸门以unbound_signal_risk_budget拒绝，拒绝日期实际该合约仓位为0、没有相应成交。

冻结native `_reconcile_state_with_position` 在actual0时reset layers，却未同步清旧target；native rebalance在旧合约bar重新出现后会按残留target重发OPEN。这个“旧目标生命周期清理不完整”是继承的实现缺陷，不能只归因缺行情或把空snapshot当正常有效receipt。其因果序列由源gap/defer/mapping记录与冻结源码强支持；运行未逐日输出private targets/state，具体reset/reissue时点属于代码路径推断，JSON逐案保留证据与限度。

P2判定依据是本轮所有这些无授权请求都在actual mutation之前被正确拦截，成交/费用/持仓/预算账本无违约，拒单清理合成回归也通过。本审查不声称未来修好上游目标清理后收益必然不变，不为此重跑或修改本轮冻结账本。未来可单独修target清理与回归；当前结果须保留这5次被安全收容的缺陷披露。

## 全市场、实际持仓与到期

研究范围六所93历史产品、4328合约epoch；实际92产品成交，唯一无成交为l_F.DCE。全部6130笔1手、逐产品跨合约gross最大1，无重复开/加仓；实际并发最高21，1894个日末持仓超过4产品。移除原4品种限制已实际生效，但资金风控仍在。

全部4328个deadline从原始日历独立重算一致；没有截止当日或之后OPEN，没有任何日末超deadline持仓。每笔开仓的actual broker保证金/开盘权益独立重建，最大约0.820075，小于原1.0 cap。最大日末保证金611,336.60，最大保证金/权益49.5741%；最大名义gross6,699,170，gross/权益峰值5.18921倍。保证金是资金承载约束，不是亏损上限。

期末12个正常未平仓均尚未到deadline/maturity，全部有2026-10-16新鲜报价、stale天数0，日末保证金249,260.10、名义gross2,690,330。残余浮盈不应称作已实现现金。2023年以来2389笔成交、净损益+603,077.76，末次成交2026-10-16，没有旧版过期卡仓后的长期停摆。

## 2024及旧三笔的本轮实际路径

2024实际242日、636笔成交，年初权益1,235,999.158236，年末1,274,880.098051，净收益 **+38,880.939815元（+3.145709%）**。这不是把旧三笔亏损从旧账户算术删除；本轮账户、预算和后续路径已经改变。

9/30三合约仍实际出现long_case2候选：IC一手计划风险23,556>原预算18,933.917961，native selected0；IM23,078.4>18,933.917961，native selected0。IF计划风险25,005.6≤原预算28,400.876942，通过原生定仓形成一手意图；其预算包含原策略30d方向倍率1.5，不能简化成一律1.8%资金。

10/8 IF真实open4549到stop4084.248的一手风险139,425.6，开盘资金预算28,064.807942，比原授权更小，因此拒绝；IC/IM已经在信号定仓层拒绝，没有实际fillgate记录。三合约在该原信号窗口均无实际成交。没有换掉品种、阈值或回放完整版C9来得出此结论，也不据此宣称完整版C9原本必免亏。

## 数据、因果时钟及代码绑定

全部成交有真实正成交量bar，price=open且位于当日高低区间。所有原始OPEN信号/重挂日期早于fill，原signal bar无execution-only，逐一与signal日因果主力映射匹配。主力observation日期严格早于生效日、OI匹配，未用退出报价作选主力数据。

4笔quantity-conflict报价成交均为CLOSE，合约日期与上一轮一致，成交ID为2735/2834/3011/4651（BACKTESTING前缀），原始多源open与evidence一致；没有execution-only OPEN。669条新层与133条旧expiry层、原始clean/metadata/calendar等hash均延续已审绑定，不改变训练或信号资格。

独立校验最终manifest列举22源文件、17当前代码hash、18个起始源码/快照以及源输入输出hash；新增039/040/041与预审版本一致，继承native/engine的MRO代码也在起始冻结中。日志无异常。生产资格false、无订单API/行情下载；日内C2/C9和供需过滤仍按授权停用。

另保留此前P2日期hook维护风险：生命周期close intent先于native current_bar_date刷新，但失败冷却与failure-memory两功能本轮仍关闭，首guard在读日期前return，对本轮无行为影响；启用前须先修复。

## 置信度与后续

对当前冻结真实成交、预算算式、会计、数据绑定、1手和生命周期约束置信度高。对private pending逐项组成、真实反事实开盘流动性、逐历史日PIT规格费用/元数据发布时间和完整C9盘中顺序有明确限制。stop-distance是计划风险，不保证未来跳空、涨跌停或next-open退出的实际最大损失。整体表现也不构成正式晋级证据。

本审查没有新增/修改/删除运行参数或金融结果。开始与结束反思：恢复用户原预算合同和通用开盘拒绝规则，不按2024收益调阈值/删品种，未见过拟合操作；但已使用同一历史样本诊断，不能称样本外。继续有价值，可作为符合预算cap1合同的研究基准。下一步只绑定独立审查交付规范HTML/整体曲线；任何新修改或正式接入另走对应验证，不能把旧fixed_size诊断曲线当同口径基准。
