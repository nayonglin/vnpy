# Stage008 三均线原19池只读预审

- 审查时间：2026-10-23 14:56 CST；line_id=futures_weekly_formal_no_half_r。范围为stage008_three_ma.py、stage008_signal_anchor_plan.py、run_stage008_three_ma.py、stage008_execution_audit.py及20261023_1446冻结合同。未修改工具/行情、未执行金融回放、未观察或选择G收益。
- 预审结论：`PASS_PRE_REVIEW_PENDING_RUN_EVIDENCE`；当前未发现必须修复的P0/P1/P2。仅表明静态实现和边界回归符合冻结语义，不是G结果接受或生产资格。

## 核查结论

1. 三处MA40决策消费均替换：普通信号删除MA40 finite门、20/40交叉、四线排列；简单趋势和换月延续均只计算5/10/20。MACD方向/交叉分支、非MA entry filter、量仓风险模式仍在。工厂明确拒绝未知_generate_signal MRO，避免绕开另一层信号过滤；ma_extra_long=40仅兼容遗留字段。
2. ThreeMaWeeklyArrayManager强制inner.size=41，inited独立count>=21；仍由原完整真实周聚合器推进，不引入第二层聚合。历史按min(count,storage)截出真实已观察尾部；普通信号要求21根，RSI6直接对真实close计算，不调用前置0的am.rsi。>=41根时MACD/RSI和保留的MA数值与原实现相同。
3. 观察历史21—30根时，继承30周期量价层按原规则insufficient_history/倍率1.0，31根起正常生效；不是永久关闭该层。MA20止损、RSI95半平及其他持仓/价格风险方法继续继承。日级执行、日极值风控、5交易日换月未改成周执行。
4. 两个真实作用已合同明示：_is_simple_ma_trend默认需25观察周（旧公式需45而缓存41，原分支恒False），三线化后可生效；换月形态helper需20根，原调用路径可能未到普通信号21ready就调用，不应声称所有续仓至少21周。本次不另加全局21门改变冻结语义。
5. data-only planner精确原19集合与E9 preflight交叉核对、同窗2020-01-01—2026-10-22、资本150000、MA5/10/20、storage41及半R/C2/AI False硬闸；完整setting与E9.setting逐键精确相等。调用实际G信号类，通过无构造器pure reader扫描真实日线，禁止账户、持仓、订单/资金路径；扫描结果仅用于次日canonical锚预取，不作为引擎准入。
6. runner保持原19、独立SQLite实际PRAGMA绑定、完成数据manifest文件SHA、原始日线SHA、proof及旧来源冻结、pre/post SHA；实际运行后半R/C2/AI与AI加载/盘中事件检查保留。持仓成交日真实日线缺口和volume<=0拒绝。
7. 执行接受层在原账本回放后逐实际clock fill精确timestamp唯一/price=raw open/quantity>0/finite正分钟volume核验；零量或非法量最终否决，不跳信号、改成交价、换分钟或偷偷修资金路径。容量比率含同symbol/minute聚合，并明确正量不证明盘口/容量。F016真实零量失效案例已有回归，不把它当可补缺口。
8. 原19时段网格、缺锚先停后真实补数、旧key优先/冲突拒绝均保留。最终G仍须独立核actual trades与clock完整对应、raw/proof来源闭包、父proof和输入SHA；不能用静态接受函数代替最终独审。

## 纯边界回归与局限

- 独立执行既有test_stage008_three_ma、test_stage008_execution_audit、test_stage008_signal_anchor_plan：30项通过，耗时18.441秒；无金融回放。覆盖20/21ready、41storage、观察RSI、>=41数值等价、无20/40单独触发、长短三线、非MA过滤、同周不重复、24/25简单趋势、30/31量价风险、19/20换月、MA40毒化、未知MRO、保留退出方法、缺周/末周/合约epoch重置、零量/NaN/重复/错价接受否决等。
- 初次直接unittest命令因默认vn.py日志写入受限而未开始测试；随后先禁用日志并显式设置本机依赖路径，30项正常通过。没有因此放宽策略或数据检查。
- 尚未取得G完整金融输出，故不确认会计、交易数量、实际正分钟量、完整消费数据SHA、收益风险、所有AI禁用证据和实际预热覆盖。完成后另做全面独审；结果差/零量等硬闸失败均保留，不为挽救成绩改参数或价格。
- 过拟合判断：本轮是用户预设三均线消融，没有根据G成绩寻优；同窗反复研究与非PIT偏差仍在。继续价值：在冻结语义下完成一次G及独审有价值，不扩MA数值搜索，不因单窗改善晋级。

## 本次读取版本SHA256

- tools/stage008_three_ma.py: `5f5554eb35033912658a2db6182b97418eafa5253ede88cf27caf09c47dc3061`
- tools/stage008_signal_anchor_plan.py: `64618b516ebc95589106f3b2131c01f4e546ccdc832073a97d1c9643f0353307`
- tools/run_stage008_three_ma.py: `d02c21220c3ac328a3532adf02695ff13390452bf0df714dc5ed91ca85652df6`
- tools/stage008_execution_audit.py: `78f89cfef93312bf9e4016046c6cb92c4ad69648f0ba508d678f9c61ed93939a`
- stages/20261023_1446_stage008_three_ma_19_contract.md: `958d33951bc47598e52626a5135a3f6c6719780f5d549a3c1c11234a6a003fde`
