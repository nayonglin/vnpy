# Stage014 数据：原19品种截至2026-10-30已完成交易日

- line_id：futures_weekly_short_ma_slope_gate；数据准备及自检，不运行金融、不提交Git。
- 记录时间：2026-10-30T22:50:44.064653+08:00；是否重要突破：否。只写本研究线Stage014命名的工具/输出/证据，旧快照和44品种/正式/生产均未改。
- 需求：15万交易本金+15万场外备用金原C，每年五起点到最新共同已完成日；月份不影响本次一天数据延伸。

## 调研与判断

沿既有stage001_data_prepare与上游stage032_latest_data已审Tq日线适配，使用真实86400秒日K的close_oi，不用当前quote替代历史日K。查询Tq连续主力calendar与raw daily；当前2026-10-30夜盘属于11/2形成中的日K，明确排除。资料/代码依据为原冻结适配和供应商raw；这不是交易所终值仲裁，也不是独立供应商共识。

数据准备本身是否调参过拟合：否，固定最新完成日10/30、只追加，不以收益选数据；整体多起点研究仍有同历史/重叠样本偏差。运行前继续价值：是，满足所有59候选同一最新终点；运行后继续价值：是，供独立数据准入和实际回放因果/逐笔审核，不能将数据自检当策略验证。

## 新增、修改和删除

新增tools/stage014_data_prepare.py、test_stage014_data_prepare.py、stage014_data_verify.py、stage014_data_reachability.py及Stage014数据/证据。新增目标TARGET=2026-10-30、PREVIOUS=2026-10-29、NEXT=2026-11-02，合约数预算220、只读数据预算300秒；无新增交易参数。旧数据/策略参数/回测结果修改与删除均无。

先查本线没有已完成10/30独立raw，因此按原同源方式读取本机既有Tq auth，仅只读拉行情；凭证未输出/保存到证据。TqApi insert_order/cancel_order显式拦截，调用计数0，CTP未连接。189必要/可能合约30根日K订阅完成，未因PnL挑选。

## 覆盖和准入

原physical_epochs2813项，按既有listed/delisted以及交割月明确分类；189个截至目标仍可能存在的原19品种epoch全部纳入，另并入旧snapshot10/29 tail和23原C末日持仓/挂单、新30主力，最终并集仍189。旧交割月但未知精确生命周期仅标记“不为本次延伸选择”，没有用最后观察日推定精确退市。完整逐epoch选择/排除理由存raw/epoch_selection.json。

189个请求均获得10/30真实日观测；185个正量OHLCV/OI准入，4个SM远月（SM704/706/707/708）为零/无效，仅分类，不生成bar。143条11/2形成中/未来raw行排除。10/30主力19条完整、必需key缺失0；10/29主力重叠和28个旧tail共同字段数值无修订；全部<=29原权威保留。

4个零/无效合约并非“没有历史”：旧physical/SQLite别名行数98/74/57/37，对应2027epoch96/72/56/28，最近正量日均2026-10-16，volume/OI分别5/70、24/83、42/177、9/38。但在旧mapping全历史（含大小写无关查询）和新10/30主力中出现次数均0。数据证据stages/stage014_zero_daily_reachability.json仅证明从未主力；新59冷启动从空仓、所有建仓/换月路径必须主力的源码可达性还须独立agent确认。若发现任一非主力建仓路径，则fail-closed，不以旧23无持仓或0填价替代证明。

## 字节、行与原始字段自检

原SQLite1345757行完整保留，目标1345942行（+185），EXCEPT旧行缺失0、integrity_check=ok、新185行价格/volume/close_oi逐字段一致。原physical392197行完整CSV字节前缀保留，新392382（+185）；mapping仅追加19行且旧字节前缀保留。metadata.csv、physical_epochs.csv原SHA不变。新数据无日期/价格fallback，无未来批准bar。四项新增边界测试RED→GREEN；独立实现风格的只读自检37项全部通过，status=PASS_BOUNDED_DATA_ONLY，失败[]；真正独立reviewer另行审核。

数据地址：/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/data_stage014_20261030/data_approved

|identity|SHA256|
|---|---|
|daily.sqlite|fbeff64d137f8cd244844850501dd0384cfb072740bbd0bd515821e20ecf2ce4|
|mapping.csv|2dd16b914b6e89ba41798b3c8ca8ed0f91b16097b3ac3504c55d3846b97fc204|
|physical_epoch_daily.csv|130a3439736c191676d732a3013e2a18c25ebcce297a67e9240e4aba25d7ff24|
|receipt.json|5eef032a27409555d77957c253c2bdbbaf70adc6079867c9050d59a7c07e3cd1|
|source_manifest.json|0303e201312090a900bb39ac46b43193d98f4c27875e05a6ee6d6844afa7cc84|
|probe_receipt.json|ec22cd66cf5a13730d28cdb85ed8165f2ba77f9e97c857f4803c30d9025f4244|
|contract_coverage.json|abeffdb1eec17a9a8fe54759b8466514e23349649bfe7f09a0aa00ea23a2a7f1|

Source manifest保留旧snapshot/source manifest、所有23 C端仓/挂单及其冻结SHA、辅助适配源码和所有新raw/批准文件。prepare源码与snapshot从成功后不再修改。实际完成时间2026-10-30T22:44:05.539913+08:00，next_trading_date=2026-11-02，latest_day_is_completed_week=True。

## 边界、后续和TODO

本阶段金融回放次数0，期末权益/收益/回撤/Sharpe/滑点/成交/胜率均不适用；没有推导绩效。下一步由独立reviewer审核上述185条准入及四零量不可达性；然后冻结数据用于59个独立账户。仍继承非完整历史主力重建、2014少数预热缺口、生命周期/PIT未知、静态元数据及容量限制；每个实际持仓/成交/周源和已完成周使用时点仍须回放闸门，不用本次数据ready覆盖它们。NO_PROMOTION。
