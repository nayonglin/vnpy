# Stage134：选月复用盘点

2026-10-18 22:24 CST；只读盘点。SQL/label/fit/cash/下载0，旧工具/LINE/registry未改。

129 actions含`u_volume,gross_capacity_qty,entry_capacity_qty,multiplier,round_lot,tick_size`及u费滑/风险、N/low20/close/lifecycle；完整经济取041 projection。actions、130 scores、132缓存无OI，跳过OI，不读库。

复用130原scope/cutoff/score。固定B已selected的family-u及exactproduct，池为该母行`u_action_eligible=1,score>0`。最大量用u_volume；随机预冻minhash盐/seed，不择优；近月=epoch末段YYYYMM。并列epoch/action_id。它识别正分池内排序，未独立识别无AI正分门的动作扩张。

完整choices沿母序、无child保留。21列=071七列IDENTITY加：

`proposed_action_id,proposed_epoch,proposed_score,chosen_action_id,chosen_action_sequence_index,chosen_epoch,anchor_epoch,score,selected,selection_state,scope,cutoff,arm,policy`。

reference/anchor不改，赢家只挂自身母行；空chosen用`''/-1/NaN/selected0`，四种selection_state保留。score为所选AI分数。chosen_action_id连129原`label_state,participation_state,net_R_stress,label_known_date`；不按未来closed筛选。held先family-u后等u：异动作unknown不填0，同动作增量0仍披露共同unknown；非现金。

131不调execute（硬编1SQL+8A/B）。复用`make_signals→organize→kernel.run_cash_account(prepared=...)`：只传selected choices及对应actions/mothers子集，其函数不要求完整母体；控制局部映B，另存control_id。organize仍传全mothers保canonical schedule。volume+20minhash共84新cash，旧B4引用。

132 cash_only1缓存110MB；restore_native_cache返回NativeBars。薄桥bar(epoch,k)：locate且valid后返回OHLCV；indicator→N/run_length/low20，缺/invalid返NaN/0；无high55需求。不能直接当Market或重算指标。日期/经济/bootstrap沿128，stop/risk/anchor/容量不变。

独审复用132最终cached_cash1的拒绝等价/预算/原生容量检查及102 review_account，设helper/positions；只核新增选择/9表账本及原indices。源标签/6模型/旧账户不重扫；拒绝表沿最终dtype/全空列等价规则，不造checker。

沿128调研，月份为经济动作；不重复联网。开始/结束按收益调参：否；同史择题风险：是。有限归因有价值，不改133 unsupported/加注资格。指标N/A。
