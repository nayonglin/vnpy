# Stage001 独立全面审查

- line_id：futures_weekly_short_ma_slope_gate；审查日期：2026-10-29 Asia/Shanghai。
- 审查员：独立agent independent_review；未实现策略、未修改作者代码/数据/产物，金融回放0次。
- 结论：**PASS_WITH_LIMITATIONS，P0/P1/P2=0/0/0**，仅指已冻结研究模型的规则、来源一致性和会计复算。策略综合结论仍为 **MIXED_OR_FAIL_NO_RESCUE_TUNING / NO_PROMOTION**。
- 有效金融产物：outputs/stage001_A_attempt003、stage001_C_attempt003；不得引用001/002为有效成绩。

## 审查范围和证据

1. 数据预审：独立153项检查通过。78个直接源绑定全部匹配，旧SQLite 1,345,729行全字段EXCEPT保全，仅追加28行；旧392,169条批准日K全部字段和CSV前缀保全，新计392,197。原mapping字节前缀保全，仅追加19条10/29主力。28条新增raw日K与CSV/SQLite六字段逐值一致，使用close_oi，duration=86400，epoch对应，无10/30形成bar准入。metadata/physical_epochs字节不变，无44池/stage040行情输入。独立重跑8项门控测试通过。
2. 新规则：同一合约最新两个已接受完整周的SMA5/SMA10差，严格>0、OR；0斜率允许，不引入回归/视觉角度参数。count限制真实观察尾，最新11个周源收盘逐值核验，单一physical epoch，未完成10/26—29周不参与。普通新开空的sizing返回完整原结果后只将正量候选归零，并以_open_position最终guard防旁路。多头、退出、每日资金风控和换月原路保持。
3. A独立全量251,973项检查、C独立全量250,994项检查，分别覆盖464/435笔实际fill，3,421/3,340个金融持仓日，全部1,652个交易日，25,295/25,295条完整周bar；独立重建逐合约现金/盯市/成本、净仓、完整flat-to-flat周期与期末未平MTM。每个fill均同约真实日open、严格下一交易日，所有持仓/周源日正量，所有实际持仓日存在性由fill再推导。
4. 最终跨臂6,778项检查：完整settings、effective parameters和data identity逐值相同；每个实际空开订单按anchor的signal_date、contract识别新信号或换月。A实际空开为58笔新信号+6笔换月，C为43+6，均有唯一上下文。C所有实际新开空均对应非正MA5/10决策，17条归零候选无实际新开。
5. C有65次short_case1a sizing记录，21次MA任一向上，其中17次原sizing为正被归零；不是17笔确定可成交反事实。4次原规则已归零者不算新增有效阻止。总成交减少29也不能解读成只删除29笔旧交易，完整路径和手数会反馈。
6. 原版身份：A003截至10/28的daily（1,651日）、trades（464笔）、clock、candidates、weekly、anchors、internal equity及全部金融持仓与原Stage032 A逐值等价（仅移除scope/profile标签后比较）。这是2020同一起点身份核对，未将2015子曲线冒称2020独立回测。
7. 源和报告：两组各2,929个input binding、全部attempt产物哈希复验通过，结果在审查中未变；comparison源文件和输出文件SHA全部匹配，summary权益、DD、Sharpe、完整周期胜率/均盈亏/PF/未平MTM与独立复算一致。

## 独立复算结果

两臂均150,000元/空仓、原19池、2020-01-02—2026-10-29；零手续费、原滑点、静态交易所保证金×1.65。

| 指标 | A未改基准 | C空头MA斜率门 |
|---|---:|---:|
| 期末权益 | 1,304,010 | 1,690,065 |
| 总收益 | 769.34% | 1026.71% |
| 最大回撤 | -55.042917% | -56.606513% |
| Sharpe | 0.9664999 | 1.0363204 |
| 总滑点 | 81,020 | 85,160 |
| 实际成交笔数 | 464 | 435 |
| 已平完整周期 | 228 | 214 |
| 胜率 | 47.807018% | 45.794393% |
| 平均盈利 | 23,003.8532 | 31,141.7857 |
| 平均亏损绝对值 | 15,427.9661 | 18,137.1930 |
| 平均盈亏比 | 1.491049 | 1.717012 |
| Profit Factor | 1.377325 | 1.476028 |
| 已平完整周期净利润 | 686,920 | 984,255 |
| 未平周期净MTM | 467,090 | 555,810 |
| 配置保证金/权益峰值 | 104.751881% | 105.862691% |

C期末多386,055元、收益多257.37个百分点、Sharpe提高约0.06982，但最大回撤恶化约1.56360个百分点；预声明的权益/DD/Sharpe三门只通过两门。因此不能称全面升级，也不符合本次固定门槛。交易数下降但总滑点增加，是动态手数与资金路径效应，不能据少交易直接推断成本更低。

## 失败运行及环境适配

- 001缺Git忽略的structural universe运行资产，配置前中止，金融结果不成立。
- 002完整引擎计算后被settings路径验收拒绝，terminal=failed/nondeclared_settings_changed，主daily/trades账本尚未导出；不能给有效收益。仅保存周止损/初始止损/拒绝诊断和MA门控诊断可与003逐字节比较，已全部相等。
- 两份补入运行CSV新旧SHA精确相等。normalize只允许相同相对路径的checkout前缀迁移、已声明mapping/start，以及固定basename在本线empty_signals的隔离路径；空信号两侧文件都不存在。
- **供需headwind flag在新旧实际配置均True，并未关闭**；loader遇不存在文件直接return，空signals令matched0/weight1/reason=no_signal。只迁移无信号源路径，不改阈值/weight/max_age/flag。不得写成供需模块disabled。
- 独立身份检查脚本初版误期待002没有导出的daily.csv而中止，改为只比较实际保存的诊断后通过；这是审查工具修正，未改策略/结果。

## 置信度与边界

对冻结数据下规则执行、会计闭合、原版身份、实际门控和报告数值的置信度较高；这不证明交易所真值、全历史PIT/OOS、真实逐日券商保证金、盘口深度/容量或实盘可成交。继承原历史主力重建缺陷、生命周期未知、暖机覆盖限制，不能由程序检查通过改写成全部数据准确。配置保证金峰值仍超过100%，不能声称不会追保。末未平仓利润不是已平盈利，也未计入完整周期胜率。

## 反思与建议

- 本轮没有结果后扫窗口/角度阈值/品种/年份、删交易或改成本，未新增调参过拟合；但重复历史内开发的选择偏差仍存在，不是新OOS。
- 此固定实验有检验结构假设的价值且已完成。结果是收益/Sharpe改善与更深回撤并存，不支持直接晋级；不建议据结果救参。若用户以后继续，应另冻验证合同做独立起点/成本压力，不能自动追加实验。
- 未发现剩余可执行P0/P1/P2；正式物料、production、CTP、订单和调度未变，独立审查无交易API调用。

## 机器证据

- stages/stage001_independent_preflight.json
- stages/stage001_independent_A_results.json
- stages/stage001_independent_C_results.json
- stages/stage001_independent_baseline_identity.json
- stages/stage001_independent_final.json
- 对应工具均位于tools/stage001_independent_*.py。
