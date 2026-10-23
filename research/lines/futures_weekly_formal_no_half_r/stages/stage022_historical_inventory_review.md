# Stage022 2015长窗历史行情库存独立审查

- 时间：2026-10-23T19:32:10.543103+08:00；line_id=futures_weekly_formal_no_half_r；重要突破：否。
- 结论：**库存审查完成，完整数据资格仍待建立**。仅只读SQLite/源码、字段和SHA核验，没有金融回放、下载、旧文件修改或N/P绩效结论。
- 可执行路线：新accepted-clean规范副本＋真实缺口补源＋物理epoch/target安全＋同新库P桥接及N长窗，保持旧M不变。旧正式分钟失败不适用于本次声明日Kopen，但真实日线/持仓/周源闸不能降低。

## 可复用真实源

- 当前M DB：`/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage005_data/daily.sqlite`；daily interval=d的全库1257339行，2015-01-05—2026-10-22；原19真实逐合约326549日键，另有25499个continuous行，后者不进入逐合约补源。
- accepted clean：`/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/clean_daily.sqlite`；2010-01-04—2026-10-16，1552456行，物理contract_epoch_id/contract_yyyymm、source/locator/hash及单边volume/当日close_oi。DB SHA a63f92ce…58711与manifest重验一致。
- Stage278最终DB：`/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage278_daily_2015_20261022/daily_snapshot.sqlite`；SHA881c2f29…bff8重验一致；mapping_snapshot与本线原19历史映射可复用。旧259补丁SHA4578e5f5…2816也一致，但259全部已在M，不能称新补259。
- Stage278259对accepted clean：257已存在，OHLC全同；另2条hc1905/2019-05-15、AP001/2020-01-13均volume0，仅留不可交易证据。259与456正量未认证、448quarantine交集均0；ru1601上期所官方26条全部已被clean覆盖。

## 数量/OI语义是实质数据差异

- 全体M/clean重叠312199个真实合约日，OHLC逐项精确相同。2015的2644重叠日volume全部M=2×clean；2019同时存在1×、2×及OI字段时点差，不能只按日期猜factor。
- 2019新缺键overlay17281行中17153个volume1×、128个2×；原键7407行volume4210为1×、2983为2×。例AP901/2019-01-02 Mvol316/OI282为clean1×；AP905同日Mvol358784/OI230326为clean2×。
- 2020重叠30365，volume全1×，旧M OI当日close精确5296，但前日clean close精确26612；2021前日精确36623/36934、2022为36963/37162、2023为41258/41481、2024为45708/45951。这说明统一当日closeOI会改变2020+价量风险路径，须用新同库P桥接，不能把新N与M差只称延窗。
- 旧M会计和已声明原数据冻结仍成立；本次不改旧输出。新副本以accepted clean全部字段为确定性规范源；未覆盖行必须有已验证真实单边V/closeOI，不混入未知旧OI。

## 缺口与最小补源

- M原19逐合约326549日键：312199匹配accepted clean，14350未匹配。clean截止内14236：13780为非正/非法量价（多为零量），456为正量合法OHLC但无accepted行；截止后10/19—22共114行（112正量）。旧库continuous的25499行另行排除，不能当可交易缺口。
- 456正量未认证涵盖239合约，152合约日落2015+主力mapping（43合约）；其中74价格冲突quarantine、374数量冲突quarantine，另8存在生命周期/来源异常，必须保留隔离理由。逐合同日期范围和全部逐键main标记在JSON。
- **不能把456当普通“没下载”并用原值兜底。** 最小补源先152个mapped-main，再对实际周源/持仓/成交所需尾段补真实源；源优先级、冲突与单位转换须在金融运行前冻结。Stage278旧路径2785个held/traded已通过，不证明新周线无AI路径全部可用。
- root已报告新Tq27份10/19—23正量；本审查没有读取这些新原始文件，N/P接受前仍需纳入新manifest逐值/时间/单边/closeOI与主力覆盖核验。

## 2014预热

- 旧Stage278“2014无数据”只指当时原vnpy DB，不能沿用到本次：clean原19在2014有16245条accepted真日线、207物理epochs，12个产品有记录，全部正量。原19不是在2014全上市，不造不存在品种的历史。
- 2014原19映射2497非空日键，2269可匹配accepted日线；缺228均MA，Tq旧代码与历史ME存在别名风险，不应把ME历史随意改名成新MA规格。2015首主力MA506自身有136个真日/28完整周可预热。
- 2015首日11个有映射主力，静态2014证据中10个达到21完整周；hc1505仅13周。实际ready还需引擎按完整交易日历/lifecycle导出，不声称元旦全部19已ready。41存储不改，周边界按完整日历而非公历年截断。

## CZCE跨十年与接受闸

- Stage278实际源中41个CZCE native名字被不同年代合约复用。SM505物理201505上市2014-08-08/到期2015-05-15，202505上市2024-05-20/到期2025-05-19；native同名不能当同一持仓/目标/订单身份。
- weekly AM已在>366日gap重置inner，防指标拼接；但completed proof保留两代，独审必须按物理epoch分段后取41。单靠AM reset不足以防孤儿target：Stage278已真实出现SM505无state归属OPEN失败，并以通用clear_unowned_targets解决。新入口应预先冻结同类目标归属安全与epoch开仓/订单/持仓闸，旧M不修改。
- stage008/weekly_adapter readiness日志写死>=2020；新历史入口需覆盖2014预热及2015+全部ready记录，否则审计证据缺段。源数据、动作、状态均须无跨epoch错配；真实持仓或成交bar缺失、零量、非法close、订单跨生命周期均拒绝，不给部分曲线绩效。

## 反思

- 本轮是用户指定延窗及数据正确性核查，没有扫描alpha或按回报选源；有价值，因已发现数量/OI和物理身份的实质风险。同历史反复研究与静态规格/零佣金/非PIT/无容量资格仍限制外推。
- 下一步只在新规范数据资格完成后跑固定P/N，并分别全面独审会计、因果周、执行、结果与SHA；本文件不预写接受或晋级结论。

机器文件：`/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/stages/stage022_historical_inventory_review.json`；SHA256 `3ca4d991b8ef6668d39a391520f42797c462f55212fe4f4771ef72d1aa8211e5`。源SHA、456逐键/合同日期范围、2014预热表、全部年度数量对照、只读脚本完整内嵌JSON。
