# Stage100：0.25%无周门v1实际失败独立审查

- line_id：futures_trend_full_market_noai_one_lot；当前模式：day／只读独审。
- 记录时间：2026-10-20 01:57 CST；工作树：full-market-noai-one-lot/fian；分支：codex/full-market-noai-one-lot。
- 不是重要alpha突破；没有修改金融实现、参数、输入、截止或旧结果，没有金融重跑、下载、生产、CTP、订单API。审查者未参与090—093实现。
- 唯一审查源：outputs/run_20261020_risk025_no_weekly_v1；金融源码9feb5784d7757ee81cbab007a610a0d64da64ca6。

## 结论与资格

**FAIL_INCOMPLETE_LIFECYCLE／FAIL，remaining P0=0、P1=1（完整回测合同未满足）。financial_metrics_valid=false、source_manifest_sha256=null。** 2019-06-27硬停止时JR201907.CZCE仍真实持有12手，违反已预登记的生命周期截止。没有最终manifest/summary；本输出不能被当成2015—2026全期结果，不能算全期收益、回撤、Sharpe、胜率、盈亏比、年度表或正式复盘。P1代表完整性失败，不是把已通过的0.0025金额算式认作代码错。独立读者所有可验证检查errors=0，并不等于金融运行PASS。

## 本次合同与真实证据

100万本金，每笔原signal总权益×0.0025（初始2500）、整手向下，不足1手不开、无一手/4品种帽、不加仓、无AI、全市场、全部空头case；此次完全关闭新增周多头门。原周JSON在JR preserve事件确为null。周期原计划2015-01-05—2026-10-16，固定N数据和日线近似，C2/C9与缺CSV供需按原授权关闭。

1. 2019-06-19，JR long_case2原receipt NoWeeklyFeeStrategy:JR201907.CZCE:long:1117：总权益1,063,530.6437024872，原预算2,658.826609256218，stop2905，signal每手风险40，授权12手；native保守数量/资金约束能低于预算整数上限，不是强制取满。
2. 6/20真实日量9<12，原意向真实延期且preserve保留同一receipt；6/21真实开盘2915、日量12，实际OPEN12。按全部前缀真成交独算，该单前因果开盘权益扣已发生fill成本为1,088,479.9164297632；当前权益预算2,721.199791074408，和原预算取小仍2,658.826609256218。实际总stop风险|2915−2905|×20×12=2400≤2658.826609256218。**没有发现本单0.25%风险金额错误。**
3. 由冻结交易历与到期2019-07-12独算，deadline=6/27，生命周期exit signal=6/26。failed_lifecycle_events在6/26、6/27均有close_target_zero12。失败日真实pos12、target0、pending_close_lots12，state层已空，当前reissue CLOSE order1936仍是12。未把计划平仓当成交、未假释放实际持仓。
4. 冻结accepted-clean真行情：6/24量6、6/25量9、6/26量6、6/27量7。CleanExecution要求一张委托的完整数量≤该日真实量，6/27量7因此不能执行CLOSE12。6/28量49在已冻结截止后，不能拿来补过闸。既有expiry与quantity-consensus两层overlay在6/19—6/27均无该JR记录，没有本地遗漏已合格报价证据。

## 原始CLOSE时点与部分成交边界

当前失败物料只导出已成交前缀、最后snapshot和有限事件，没导出完整未成交订单史、deferred_orders或trade_event_diagnostics。pending_close_lot的provisional_exit_price2915同时匹配6/25与6/26；当前order1936的6/27是重发日期。**无法唯一确定首次native CLOSE是6/25还是6/26，也不能把“已证明6/26生命周期发出”误说成“证明此前从无CLOSE”。** 这是诊断可见性限制。

若最早实际CLOSE意图仅6/26，允许真实部分平仓时，deadline日最多按日量7平掉7手，仍剩5；所以“只增加部分CLOSE”不能被当前证据证明足以完成本案。若更早有合法意图，跨6/26与6/27的日量合计可能充足，但本失败导出不足以据此认领成功。不得前移本笔信号、使用未来成交量、伪造部分成交或假结算。

## 独立前缀复算与完整性边界

- 全1492实际fills按冻结真开盘价、整手、日量≥原整单、无actual加仓、一产品一真实合约重算；截至失败日真实仓位与snapshot六合约完全一致。
- 静态费表独算手续费35,212.04557023609、滑点142,525；每日MTM逐真fill独算失败snapshot账面权益1,099,807.9544297631，与snapshot差3.4924596548080444e-09，实际保证金491,551完全相同。这些数字**仅用于失败前缀对账，绝非全期绩效**。
- protocol、全部start金融代码与代码快照、source_inputs/output_files、生命周期物料及N五张冻结表hash逐一核对，无漂移。protocol SHA=fcb1176e51cf4bedd56879e4db2367ea16a0d7144fd4e6eb6f9574427af52914；failure_snapshot SHA=bbb1459983f309d50b9e9ea84db72b9d157a262438a89babf5f8c9b619638550。
- 失败导出缺全量opening receipt/open_budget与daily account表，故仅JR这张已保留receipt能做原预算+实际开盘预算双核，不能把它外推为1492 fills全量预算通过。也不能确认全部fill周JSON为空；代码MRO/预审和本事件null是不同层级证据。
- 已预备完整成功源专用的三份独立读者，仅留档，**没有对本次未完成源执行成功审查或宣称PASS**。另有只读父0.5v3资金读者准备校验，2027原意向/2026终止、2862 EOD资金最大差5.82e-11、实际cluster PnL差0；明确不是新0.25结果。

## 最小诚实后续选项

- 保持当前完整数量/日线执行/固定生命周期合同：保留失败归因，不发布无周门完整绩效。
- 若用户要求改政策：先给两臂共同、统一、因果的提前退出或流动性仓位政策建立新合同，再检验。不得按JR、本次亏损/截止或后验成交量挑开仓/拒单，也不得只补无周门一臂。
- 统一部分CLOSE属于共同执行政策改动，必须保留数量、费用、pending CLOSE和真实资金守恒；本案仅在deadline日拆单仍剩5，不能承诺它单独解决。任何真实报价数据补齐也须有独立合格证据，当前未发现遗漏。

## 外部方法、反思与后续

沿用Stage098已核[CME风险金额/止损距离仓位](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)与[vn.py官方组合文档](https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md)；本判断来自冻结实际仓位/报价/生命周期，不复制外部收益结论。单笔stop风险约束不保证未来市场有足够退出流动性，二者不能混为一条预算算式。

过拟合：运行前后均存在在看过旧风险比例结果后改参数的后验选择风险；本次失败独审不寻优，尤其不能针对JR救参。继续价值：记录失败有价值，但同合同不应重复跑到碰巧通过；若改统一政策必须先明确新对照合同。本阶段不改LINE/registry/root总账、不提交Git；后续由root决定与用户沟通。日线近似、非PIT费用保证金、真实盘口容量和停用规则限制仍保留。

所有实际审计代码、完整日志、结果和准备读者原字节在同名_audit_code目录，SHA索引见同名JSON；失败源原字节保持不变。
