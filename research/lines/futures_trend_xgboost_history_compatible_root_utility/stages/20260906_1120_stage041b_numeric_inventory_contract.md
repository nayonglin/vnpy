# Stage041B 成本数值身份适配

- 2026-09-06 11:20 CST；非重要突破；仅本线。Stage041的2583输入冻结保留，file contract efd9cfbf37466496c65ac9015d2295bee420cc0f055880c23c8eae269cbaf012。首批只启动首任务，11:18左右终止，新增退出意图/成交/有效标签均0；后两项未启动。原源码/测试/失败日志不改，不自动重跑旧目录。
- 已定位原engine.run_backtesting捕获Exception后return；Stage847._run_profile又令engine.output=lambda msg:None，所以原回调异常被吞，calculate_result最后只显示缺少2020-01-10日账本。当前失败audit没有观察或意图，符合退出前校验中断。
- 可复现实质差异：Stage040冻结首观察成本average_entry_price字符串为1203；Stage039原真实E动作记录为1203.0；二者Decimal精确相等，旧Stage041对整个book直接字符串比较会错误拒绝。此处不加容差、不修改价格；使用Decimal比较quantity和average_entry_price，source_trade_ids仍精确相同，快照/9特征/预算峰值仍精确相同。极小非零数值差、不同来源ID、非有限或非整数数量仍拒绝。
- 新stage041b_numeric_inventory_labels.py复用冻结Stage041调度/验收，只有数值身份比较、独立输出/合同路径和回调错误留存包装不同。包装保留原异常语义，finally恢复方法；若再失败，保存原始callback_failure，不能用最后一层KeyError猜测。
- 所有Stage041失败文件及原冻结清单纳入新输入，首三个canary身份、9特征、标签、月前60根、权重、模型、完整A/150000与截止日期均不变。3项新的有效回放通过才推进全1002；不以新旧绩效挑适配器。
- 新增/修改/删除策略参数无；新增诊断字段callback_failure；无新的绩效结果、历史fit/predict、reviewer。原550项全套通过与5项新增适配器RED均已观察，待GREEN与新冻结后执行。
- 开始是否过拟合：否，这是数值表示身份修复，未生成新标签前处理；整体历史选择偏差仍在。继续是否有价值：是，修复明确的执行前误拒绝，仍不保证XGBoost有效。生产不改、CTP/真实订单0、无跨线/总账/registry/commit/push。
