# Stage019：生命周期修复与去数量上限独立预审

- 研究线：`futures_trend_full_market_noai_one_lot`。
- 时间：2026-10-18 20:37 CST；审查者：`/root/failed_run_review`。
- 新授权：修复到期卡死，取消最多4品种限制；100万、每产品最多1手、不加仓、无AI月池/pairwise、全部空头case、日线近似与供需停用口径保留。
- 本轮性质：执行合同/实现预审，不是金融结果审查或重要alpha突破。只读runtime及本地复用资产；审查者仅新写独占 `test_stage017_lifecycle_regressions.py` 与本记录，没有修改runtime/原金融输出、没有金融重跑。

## 结论

**当前未发现阻塞冻结新合同研究回放的P0/P1；本线独立重跑60 tests全部GREEN，其中生命周期/去数量上限19项全部通过。允许新run_id `run_20261018_lifecycle_unlimited_v1`按新冻结合同执行，不意味着其结果自动合格。**

新入口为Stage018，原Stage004与v4诊断证据保留。新生命周期与取消max4都会改变交易路径，因此这是新的研究执行版本；不能把新结果冒称为v4序列化恢复或无行为变化的复刻。

## 调研与独立判断

1. 本地仓库检索未发现可直接复用的完整六所期货到期交易实现；可复用的资产是独立交易日历、逐合约maturity/分类、native真实close队列、已有幂等平仓与实际持仓保证金下界、严格真实bar撮合和双账本。研究侧曾下载RQ数据，不代表本机已安装其完整生命周期模块。
2. vendor `futures_metadata.json` 的product字段是Index/Commodity/Government，而当前contract_metadata.product是IC/FB/T等代码，两者不可混淆。新policy使用明确的product_class并校验股指代码，未知分类/期限字段/日历覆盖直接失败。
3. 查阅[Backtrader官方换月说明](https://www.backtrader.com/docu/data-rollover/rolling-futures-over/)与[RQAlpha官方FuturePosition源码](https://github.com/ricequant/rqalpha/blob/master/rqalpha/mod/rqalpha_mod_sys_accounts/position_model.py)。判断：应借鉴独立日期/下一交易日/生命周期事件，而非后验从行情终点推到期日。RQAlpha源码包含到期时按内部last_price系统关闭的框架语义；本研究没有相应结算证据/合同，**不复制这种自动清仓作为普通市场成交**，也不把连续合约拼接当作跨实盘合约的免费换仓。

## 固定研究合同及参数变化

- 新增：股指Index且代码IF/IH/IC/IM，运营截止为maturity前1交易日；Commodity/Government非股指统一运营截止为“名义交割月首交易日前2交易日”和“maturity前10交易日”中较早者。EC、月均价F等非股指只归提前退出研究桶，不冒称其法律交割类型都相同。
- 新增：`exit_due(signal_day)`按独立日历next_session>=deadline判定，提前1交易日发真实平仓委托；信号预计fill>=deadline禁止新开，实际fillgate再次禁止，不能因重挂而跨截止开仓。
- 新增：截止当日完成真实撮合后仍持仓硬失败，并保存持仓/deadline快照；无真实正量报价不能制造平仓或择后续有价日放宽截止。
- 修改：native兼容max_concurrent_positions从4改为全宇宙自然容量93；effective_limit不再被环境权重压成更小数量。每产品1手且只有93产品，93是自然容量，不是另一次人为风险名额优化。实际total/cluster/broker保证金门保留。
- 删除：人为max4名额约束及其环境数量缩放；未删除资金、保证金与同产品总一手限制。
- 不变：100万初始资金、每产品最多一手、不加仓、无AI与全部空头case、其余日线信号/退出/风险门、已批准关闭的C2/C9分钟规则与缺冻结CSV供需过滤。

1/10/2交易日是事前声明的固定保守运营政策，**不是六所所有账户历史法定强平日的完整复刻**，本轮不扫描提前量或按收益选择数值。即使该政策不能避开更早的流动性消失，也必须如实硬失败；不能读取后验最后成交日、删除FB/IH/IC/ZC或伪造结算救回测。

## RED与修复过程的独立证据

1. 初始新增11 tests全部FAIL，除policy缺失外，3项是旧实现明确的真实行为RED：第5产品在保证金充足时被拒；env权重把旧max4缩为1；低保证金本应走actual_broker_margin_cap却先被actual_concurrency_limit挡住。并非仅用模块不存在宣称复现。
2. 与root最终固定10T/2T合同对齐后，13 tests仍全部RED，0 fixture import ERROR；非Index、Government、F家族、缺metadata、未知Index代码/分类等预期已声明。
3. 初次新实现出现2项fixture错误（新engine必需lifecycle_policy未绑定）；测试已使用真实metadata及覆盖到期的交易日历初始化，未要求runtime放宽安全校验。synthetic maturity由不在交易日历的周日5/15修正为5/16，非研究金融数据变更。
4. root额外识别取消pending OPEN后unsynced state可残留，独立新增两条RED实证：signal取消和actual deadline fillgate均已撤单/target0但还残留未同步layer。随后统一cancel_lifecycle_open实现了“只有实际pos=0、合约匹配且所有layer未同步时才清理意图”，两个回归GREEN；真实仓不被清空的对照也通过。

## 最终GREEN与代码审查

命令：`.py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test*.py' -v`。

独立运行结果：**Ran 60 tests in 2.857s，OK**；其中本次19项包括：

- Index截止/一交易日提前close；非Index月首2T/到期10T较早边界；Government与F家族；交易日历缺口按session而非自然日；改变后验last_bar_date不改变截止。
- 截止当日/之后禁新开，缺maturity/month/class或完整日历失败；已到截止仍有实际仓位硬失败，平仓后才可通过。
- 真正构造native close pending lot：连续强制退出幂等、实际仓位仍1且保证金仍占用；下一真实open105完成close后pos0；缺截止真实quote时无成交而明确硬失败。
- 超过4个不同真实产品，在足够保证金时第5个可开；不足保证金仍被actual broker门拒；环境权重不再缩数量。
- 取消截止OPEN时清理无真实仓的未同步意图/target/活动订单/pending产品；不清理真实持仓；actual-fill deadline gate在改pos前阻止并清理。

只读核对Stage016/018：日期来自metadata+独立source calendar，不读某合约未来bar；新FeeStrategy在普通信号处理前收敛到期target并屏蔽同产品/到期主力的新开，优先级覆盖5日rollover延迟；已有实际close队列继续走真实撮合和费用，实际未平前不释放仓与保证金；engine截止检查不能靠pos净额或冻结旧价蒙混。Stage018保留原账本对账、源hash、代码快照、残仓与缺bar披露。

## 置信度与后续

- 预审置信度：中高，关键时钟、实际委托、仓位/保证金和取消状态已有合成与原生集成测试；60项GREEN不等于所有金融路径已经覆盖。
- 新金融回放可能仍因截止前实际价格消失而失败；该结果应记录数据/模型边界，不能继续移动截止或品种黑名单。此时保留失败前缀成交与deadline证据，再独立审查。
- 实际回放完成后，必须重算逐笔费用/日PnL、源bar与signal时钟、deadline前退出、超4品种后的保证金门、真实93品种覆盖和残仓；新的真实结果审查JSON顶层绑定冻结run/manifest.json的source_manifest_sha256并给独立结论，不能从本预审自动盖PASS。
- 不产生本轮期末权益/总收益/DD/Sharpe/滑点/交易数/胜率；它们在未运行的新版本上均不适用。

开始/结束过拟合判断：否，本轮没有金融寻优、后验末bar或删品种；固定提前10T会改变行为，须透明披露其运营而非alpha含义。继续价值：是，先关闭过期仓死锁和人为名额约束，才能评估用户目标；但不能把解除死锁后的收益上升当作自然过拟合检验已通过。

同名JSON记录预审门、代码hash和RED/GREEN身份。source_manifest_sha256为null是因为新金融run尚未执行，本预审不得被当作真实结果审查。
