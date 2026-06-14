# futures_trend_stage819_intraday_rules - Stage819候选分钟级规则研究线

## 定位

- 资产：商品期货。
- 上游版本：当前 primary official candidate `official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`。
- 研究目标：基于 Stage819 候选版本的全周期逐笔交易，结合数据分析和分钟K线视觉复盘，挖掘能否用规则类、非AI的日内入场/出场机制提高收益或降低左尾。
- 独立性：本线只做 Stage819 候选的只读法证、规则设计和后续独立 A/C 验证；不得修改当前官方正式版 Stage372/20w，不得连接 CTP，不得调用下单。

## 研究假设

- Stage819 候选的主要价值来自更强右尾和更高进攻性，但问题是回撤尾部不稳。
- 分钟级规则如果有价值，应体现在“确认后入场、错了实时止损、允许有限多次尝试、让顺畅趋势继续运行”，而不是在日线级别死扛。
- 日内规则必须是可解释的价格/波动/成交量/OI规则，不使用 AI、机器学习、未来收益标签或事后最优点。

## 反过拟合约束

- 不按某一年、某品种、某方向、某几笔大赢家或大亏损反推专属规则。
- 不扫分钟窗口、小数阈值、ATR倍数或重试次数来救结果。
- 首阶段只允许固定少数通用规则形状：开盘区间突破、失败快速止损、有限重试、日内追踪止损、收盘前强制退出。
- 所有规则必须能在分钟K逐根推进时实时判定，不能用当日收盘后才知道的信息。
- 图谱和逐笔法证只能产生候选假设；进入策略前必须做冻结规则的真实引擎 A/C 和成本压力验证。

## 当前状态

- Stage018 已完成：做 Stage842 止损后结构破坏 taxonomy。结论 `stage842_s3_positive_gross_but_stage841_negative_not_promoted_engine_watch`：Stage825 全量 `341` 笔 closed lots 中入场日分钟K覆盖 `227` 笔，`0.5R` 逆向触发 `101` 笔，触发后仍有恢复形态 `62` 笔。最佳只读形状 S3 `two_stop_side_closes_before_reclaim` 触发 `88` 笔，全量 gross delta `+4,103,675`，其中亏损修复 `+9,865,085`、赢家误伤 `-5,726,410`；Stage841 可匹配事件 `24/25`，S3 在该子集触发 `19` 笔，触发 `killed_c4_winner` `6` 笔、`saved_c4_loser` `8` 笔，子集 delta `-3,643,210`。结论为正线索但不晋级，不进入官方候选，不触发 A/B。
- Stage017 已完成：做 Stage841 C7 fail-fast 事件误伤法证。结论 `stage841_diagnostic_only_c7_failfast_hurts_by_killing_recoverable_entries`：C7 fail-fast `25` 个事件全部匹配到 C4 同入口 lots；匹配事件中 C4 总 PnL `+1,417,025.0`，C7 总 PnL `-2,059,431.3`，C7 相对 C4 净损 `-3,476,456.3`。其中 `killed_c4_winner` `10` 个造成 `-4,413,255.2`，大于 `saved_c4_loser` `10` 个带来的 `+1,084,639.7`；止损后当日重新站回入场 `6` 个，到达 `+0.5R` `3` 个，到达 `+1R` `2` 个。分钟K atlas 显示 C7 常把趋势初期可恢复抖动当成错误入场，解释了 Stage840 的真实引擎失败。
- Stage016 已完成：验证 Stage840 C7 `C4 + 120m 0.5R fail-fast no-retry` 真实组合引擎。结论 `stage840_c7_not_promoted_stop_failfast_timewindow_route`：C7 触发 fail-fast `25` 次，C2 事件 `52` 次，cap 事件 `32` 次；C7 期末权益 `26,118,143.3`、总收益 `8606.0478%`、最大回撤 `-52.6280%`、Sharpe `1.3351`、总滑点 `1,993,300`、交易 `682`、胜率 `52.7928%`、broker10 峰值 `132.7826%`。相对 C4，C7 少赚 `4,405,767.5`，最大回撤恶化 `1.8380pp`，Sharpe 降 `0.1168`，broker10 峰值恶化 `17.3814pp`。Stage839 的 H3 lot-level gross 线索穿不过真实资金联动，停止 fail-fast 时间窗路线。
- Stage015 已完成：做 Stage839 C2 未覆盖失败交易分钟K法证。结论 `stage839_uncovered_failure_no_single_clean_rule_yet`：Stage819 baseline `341` 笔 closed lots，总 PnL `28,171,880`；亏损 `179` 笔、亏损合计 `-32,489,020`。C2 `stop_first` 可覆盖亏损 `43` 笔、`-14,784,145`；未覆盖亏损仍有 `136` 笔、`-17,704,875`，其中有分钟证据 `70` 笔、`-11,725,485`，缺分钟 `66` 笔、`-5,979,390`。H1 `target_first` 后保本保护 gross delta `-1,000,420`，否决；H2 `neither + 入场日收盘逆向退出` gross delta `+737,350`，误伤赢家 `-3,694,495`，暂不进引擎；H3 `120m 0.5R fail-fast no-retry` gross delta `+3,461,542.4`，但误伤赢家 `-5,032,679.2`，且真正未覆盖亏损只覆盖 `13` 笔，只能作为一次冻结真实引擎验证线索。
- Stage014 已完成：验证 Stage838 C6 `C4 + 持仓后 concentration-aware survival` 压力起点。结论 `stage838_c6_cluster_survival_not_enough`：C6 对 A 收益胜 `4/4`，但回撤胜仅 `1/4`；对 C4 回撤胜 `3/4`，但收益中位差 `-24.1263pp`。A broker100 失败 `0/4`，C4 `4/4`，C6 仍为 `4/4`；C6 最大 broker10 `124.9520%`，DD50 失败仍 `3/4`。cluster 事件 `7` 次、减仓 `173` 手，但主要打在 `2021-02-19/2022-03-29` 的 CF long 簇，没有命中关键 `2022-07` 黑色/燃油 short 压力簇。C6 不进入年度全样本，不进入正式候选，不进入官方 A/B。
- Stage013 已完成：做 Stage837 C4 持仓后全路径压力法证。结论 `stage837_holding_pressure_cluster_rule_shape_supported`：broker 锚点 `8` 个，top3 产品方向簇高集中率 `100%`，short 方向集中率 `87.5%`，equity denominator 正贡献比例 `50%`。`2022-07` broker100 多数来自黑色/燃油 short 集群，top3 share 约 `78.9%` 至 `81.6%`、short share `100%`；`2019-01 2021-12-22` 是 long 集群例外，top3 share `100%`。但关键 `2022-07` 压力合约分钟K基本缺失，不能宣称分钟级实时止损已被证明。
- Stage012 已完成：做 Stage836 止损后释放资金再使用归因。主口径为 `nearest-stop`，每个 C-vs-A 增量开仓只归因给最近的前序日内止损；辅助口径为允许重叠的 event-window。结果反证 blanket cooldown：C2 10日 incremental C exposure PnL `+3,532,434.4`，C4 10日 incremental C exposure PnL `+2,267,950.0`。C2 `C_only` 为负 `-594,960.0`，但 `C_larger` 为强正 `+4,127,394.4`；C4 `C_larger` 也为强正 `+2,420,390.0`，且 C4 10日总 risk delta 为 `-1,308,353.2`，说明 broker cap 已压缩总体暴露。决策 `stage836_reuse_incremental_positive_no_blanket_cooldown`，不做止损后全局冷却或同品种冷却。
- Stage011 已完成：对 Stage827 C2 与 Stage830 C4 的日内止损触发事件做只读事件级归因和分钟K图谱。C2 `51` 个事件 closed 全匹配、baseline 匹配 `49`，直接贡献 `+5,347,448.4`；C4 `51` 个事件 closed 全匹配、baseline 匹配 `48`，直接贡献 `+6,871,695.8`。`stop_first` 桶 `91` 个匹配事件贡献 `+12,179,364.2`，说明 C2 止损本身大多是在修失败单；但 2020 年为负、`ru.SHFE` 为负，且完整 C2/C4 路径仍有 DD/broker 尾部风险。决策 `stage835_c2_direct_events_positive_but_path_risk_unresolved`，不推广为新策略。
- Stage010 已完成：验证“入场日 OR15 确认/假突破规避”只读 lot-level overlay。C6 `OR15 close confirm + retry2` covered-lot 净差 `-3,200,100`；C7 `OR15 hold5 confirm + retry2` covered-lot 净差 `-2,463,770`。二者虽然能过滤 `stop_first` 左尾（C6 `+10,369,355`，C7 `+11,302,320`），但严重伤害 `target_first` 快速走顺右尾（C6 `-14,395,710`，C7 `-14,591,315`），决策 `stage834_or15_confirmation_not_promoted`。OR15 形状不进入真实组合引擎 A/C。
- Stage009 已完成：在 C4 基础上叠加持仓后 `forced_margin_deleverage` 生存线，固定 `trigger=100%/target=100%/broker_multiplier=1.65/priority=largest_margin`，只跑 Stage832 压力起点。C5 收益仍强，4个起点对 A 收益胜 `4/4`，但 broker100 失败仍为 `4/4`，max broker10 从 C4 最高 `115.40%` 恶化到 C5 `125.53%`；DD50 失败仍 `3/4`，且 `2019-01` 回撤从 C4 `-50.7898%` 恶化到 C5 `-59.5303%`。forced 事件 `11` 次、关闭 `109` 手，主要集中 `CF.CZCE short`，未命中 Stage832 的 `2022-07` 黑色/燃油压力簇。决策 `stage833_c5_stress_survival_not_enough`，C5 不进入全年度验证。
- Stage008 已完成：对 Stage831 中 C4 的 broker100/DD50 压力起点做只读归因。压力起点为 `2018-01/2019-01/2020-01/2021-01`；C4 在四个起点收益和 Sharpe 仍强于 A，但 broker100 天数分别为 `2/3/2/2`，DD50 天数为 `13/13/13/0`，max broker10 到 `115.40%/104.98%/114.47%/108.12%`。入口 cap 事件显示开仓前投影最高 `1.2375 -> 1.2713`，开仓后均压到约 `1.0`，说明入口 cap 按设计生效；真正压力来自持仓后盯市、权益分母塌缩和黑色/燃油短仓集群保证金分子。决策 `read_only_forensics_no_promotion`。
- Stage001 已完成：建立 Stage819 2018起点全周期 closed lots、分钟K覆盖率、逐笔入场日分钟特征、规则候选分桶和全量图谱。
- Stage002 已完成：冻结 C1 `30分钟0.5R fail-fast + 最多2次重试` 与 C2 `1R止损先于1R确认则退出`，做 Stage819 候选内部 lot-level minute overlay A/C。
- Stage003 已完成：将 C2 放入隔离 subclass + 自定义 engine 组合路径验证；A 精确复现 Stage819，C2 触发 51 次。
- Stage004 已完成：只读归因 C2 回撤恶化机制；C2 直接止损事件在 2022 年合计正贡献 `+605,911`，但释放资金后同一批机会的手数和风险预算被放大，2022-03-09 至 2022-06-29 窗口 C-A 净损益差 `-774,050`，最大保证金/权益差 `+45.7703pp`。
- Stage005 已完成：做 C2 + A opened volume cap 反事实。C3 期末权益 `29,771,186.8`，高于 A `3,448,456.8`，但最大回撤 `-59.23%` 仍比 A `-54.75%` 差；相对裸 C2，回撤从 `-62.77%` 修到 `-59.23%`，证明账户层预算方向有效但不充分。
- Stage006 已完成：做 C2 + broker10 保证金/权益 `100%` 入口闸门。C4 期末权益 `30,523,910.8`，高于 A `4,201,180.8`；最大回撤 `-50.79%`，好于 A `-54.75%` 且显著好于裸 C2 `-62.77%`；Sharpe `1.452`，总滑点 `2,079,430`，交易次数 `677`，胜率 `53.63%`。
- Stage007 已完成：冻结 Stage006 参数做年度起点稳健性。成熟起点 `2018-01` 到 `2025-01` 共 `8` 个，C4 收益胜 `8/8`、Sharpe 胜 `8/8`、回撤胜 `5/8`、收益+回撤双胜 `5/8`；但 DD50 失败 `3` vs A `1`，broker100 失败 `4` vs A `0`，决策 `stage831_c4_not_robust_enough`。
- 当前结论：C2 裸规则不晋级；C4 也不能晋级。C4 证明日内止损释放资金有进攻价值，但 `2019/2020/2021` 起点回撤和 broker10 路径恶化，说明入口保证金闸门不是完整生存线。
- 当前结论补充：Stage018 显示“连续两根止损侧收盘”比固定时间 fail-fast 更有结构含义，能修复一批 `no_same_day_recovery` 左尾；但它仍误杀 `18` 个赢家，且在 Stage841 C7 失败事件子集为负。不能把全量 gross `+4,103,675` 当成策略成立。若继续，只允许一个冻结真实引擎 C8 做反证；不得扫描连续根数、OR长度、R倍数、品种、方向或年份。
- 当前结论补充：Stage017 解释了 Stage016/Stage840 的失败机制。C7 不是因为事件匹配错误而失败，而是固定 `120m 0.5R` fail-fast 的语义太粗：它确实救下部分 C4 亏损，但更大规模误杀可恢复的趋势右尾，尤其 OI/lh/sp/fu 等事件。下一步不能继续救 `120m/0.5R/retry`，只能转向“止损后结构破坏”这类低自由度、可实时判定的只读 taxonomy。
- 当前结论补充：Stage016 反证 `120m 0.5R fail-fast no-retry`。问题不是 `120m` 或 `0.5R` 需要继续微调，而是初期小逆向经常会误伤后续右尾、改变 C4 的复利路径，并把 broker10 压力推到更差的后续路径。停止 fail-fast 时间窗、R 倍数和重试次数扫描。
- 当前结论补充：Stage015 显示 C2 未覆盖左尾没有单一干净形状。`target_first` 桶虽然包含后续亏损，但总 PnL `36,237,740`、赢家 PnL `39,262,010`，不能做简单保本/追踪保护；`neither` 桶总 PnL仍为正，不能全砍。唯一可继续的 H3 `120m 0.5R fail-fast` 也只是一次冻结引擎验证线索，不允许继续扫时间窗或 R 倍数。
- 当前结论补充：Stage014 反证 concentration-aware holding survival 作为 C4 的补丁。问题不是 `trigger/target/broker_multiplier/top3_share/direction_share` 需要继续微调，而是 runtime 生存线会过早改变 long 集群路径，却没有命中后续 exact broker10 的关键 short 压力簇，且会让 broker100 与 `2019-01` 回撤更差。停止 C4 survival branch 的阈值救援。
- 当前结论补充：Stage013 支持一个账户/持仓层的 broad rule shape：当 broker10 压力与 top3 产品方向簇集中、方向集中同时出现时，组合进入持仓后集中度风险状态。但这不是产品过滤或年份过滤证据，也不是分钟级出场已成立的证据；DD50 仍多是权益路径问题，broker100 才是持仓保证金/集中度问题。
- 当前结论补充：Stage012 反证“止损后冻结资金/同品种冷却”的粗规则。止损后新增/放大 C 暴露在 10 日窗口总体正贡献，负贡献也多为跨品种、跨多日，不是同品种马上复仇开仓。下一步应转向持仓后保证金集中、产品簇集中和权益分母压力，而不是继续研究 cooldown。
- 当前结论补充：Stage011 显示 C2/C4 的直接止损事件总体是正贡献，问题不在“1R 止损本身完全错误”，而在止损后释放的保证金和风险预算如何被组合重新使用。下一步禁止继续扫止损倍数、年份、品种或日内时段过滤，应转向释放资金再使用纪律。
- 当前结论补充：Stage008 显示 DD50 与 broker100 不是同一个问题。`2022-06` DD50 很多日期 C4 已空仓或低保证金，是相对自身高水位的权益路径回撤；`2022-07-07` broker100 是持仓后黑色/燃油短仓集群的保证金压力，部分起点由权益分母塌缩主导，部分由 C4 更大持仓保证金分子主导。下一步只能研究 full-path holding margin survival 或释放资金再使用纪律。
- 当前结论补充：Stage009 反证简单持仓后强制减仓生存线。原因不是“100% 阈值需要微调”，而是 runtime margin survival 未命中 exact broker10 压力簇，且改变路径后会释放新风险。停止沿 `trigger/target/broker_multiplier` 小数扫描救 C4。
- 当前结论补充：A opened volume cap 是反事实归因，不是 live-feasible 规则；不能把 C3 包装成正式候选。
- 当前结论补充：C4 仍不是官方正式候选替代。Stage006 full-path max broker10 margin/equity 到 `115.40%`；Stage007 跨起点显示 C4 broker100 失败 `4` 次而 A 为 `0`，且 DD50 失败更多。不能因收益和 Sharpe 胜出就忽略尾部路径风险。
- C1 也改善收益和回撤，但新增 `58` 次交易、滑点增加 `199,920`，且重试组为负贡献；暂不作为主线。
- 主要限制：入场日分钟K覆盖 227/341，覆盖率 66.57%；2018/2019 和部分合约缺少分钟K，不能把图谱证据误读成全量分钟策略证明。
- Stage004 进一步限制：窗口内最大负贡献是 `fu.SHFE long`，但全样本最差 C2-vs-A 相对回撤差出现在 2020-10/11；不得按 2022、单品种、方向或 R 倍数做补丁式救参。

## 后续规划

- Stage001：只读逐笔法证与分钟K图谱。
- Stage002：冻结 1-2 个低自由度日内规则候选，做分钟级可执行语义设计，不接正式版。
- Stage003：优先把 C2 写进完整组合引擎开关，在 Stage819 候选上做真实 A/C 回测，检验收益、回撤、滑点、交易次数、资金联动和保证金路径。
- Stage004：已完成，不调参，确认 C2 回撤恶化主因是释放资金后的同机会规模/风险预算放大，不是 C2 直接止损事件本身。
- Stage005：已完成，C2 + A opened volume cap 缓和回撤但不可实盘，且仍未修回 A 的回撤水平。
- Stage006：已完成，broker10 `100%` 入口闸门是 live-feasible 账户层规则，不引用 A 路径、不引用未来结果；全周期优于 A 的收益和回撤，但 full-path broker10 仍超过 100%，暂不升级为正式候选。
- Stage007：已完成，冻结参数年度起点显示收益/Sharpe 稳定增强但 DD50 和 broker100 尾部失败更多，C4 不晋级。
- Stage008：已完成 C4 broker100/DD50 超限日归因。结论是入口 cap 工作正常，但持仓后盯市、权益分母和产品集中暴露仍会重新生成风险；禁止扫描 `1R`、保证金阈值、broker multiplier、冷却天数、品种过滤或年份过滤。
- Stage009：已完成 C4 + forced margin survival 压力起点验证，C5 不晋级，不进入全年度起点。禁止继续扫 `forced trigger/target/broker multiplier`。
- Stage010：已完成 OR15 入场确认/假突破规避只读验证。结论为不推广，不进入真实引擎；停止 OR 长度、hold bars、重试次数和 OR 反侧止损扫描。
- Stage011：已完成 C2/C4 真实止损事件级法证。结论为直接事件正贡献但路径风险未解，不进入正式候选。
- Stage012：已完成止损后释放资金再使用归因。结论为 10日 incremental C exposure 总体正贡献，不进入 cooldown 规则。
- Stage013：已完成持仓后全路径压力法证。结论是 broker100 压力存在产品方向簇集中形状，但 DD50 与 broker100 不同源，且分钟K覆盖不足，不进入正式候选。
- Stage014：已完成冻结低自由度 concentration-aware holding pressure engine 试验。结论为 C6 不晋级；停止 C4 持仓后 survival 阈值扫描。
- Stage015：已完成 C2 未覆盖失败交易分钟K法证。结论为未覆盖左尾没有单一干净规则；H1 否决，H2 暂停，H3 仅保留一次冻结真实引擎验证线索。
- Stage016：已完成 C7 `C4 + 120m 0.5R fail-fast no-retry` 真实引擎验证，结论为不晋级并停止 fail-fast 时间窗路线。
- Stage017：已完成 C7 fail-fast 事件误伤法证。结论为 C7 失败主要来自误杀可恢复趋势右尾，不进入真实引擎、不进入官方候选、不进入 A/B。
- Stage018：已完成“止损后结构破坏”只读 taxonomy。S3 `two_stop_side_closes_before_reclaim` 全量只读 gross 为正，但 Stage841 子集为负且误伤右尾，不晋级。
- Stage019：若继续，只允许冻结一个 C8 真实组合引擎：`C4 + S3_two_stop_side_closes_before_reclaim`。验证全周期权益、回撤、Sharpe、滑点、交易次数、胜率、broker10、年度起点压力；不得并行扫描连续根数、OR长度、R倍数、品种、方向或年份。
