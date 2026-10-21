# Stage053 精确C2首阻塞需求独立审查

- line_id=futures_ai_monthly_pool_generalization；2026-10-20 22:20 CST记录，实际独审22:18完成；独立review，非alpha/收益突破。不改052作者代码/产物、LINE或registry。
- 从046b仅asof/成熟/首unknown字段独立固定2209窗/85product。052全量2209映射原key/date/reason完全保留，去重910 exactepoch×source_trade_date/910state。63364检查0fail，未解决P0/P1/P2=0/0/0；9作者单测另通过。
- 全量核requirement/state ID、group/window复用、episode fresh日与layer signal日、signed R/guard/effectivefilltick、物理与自然日/资格False和完整前夜语义。34 held≠target、63roll确认，不能由050代表hint替代确切持仓。
- 3640精确SQL键核全910当日OHLC/entry.open、signal日Stage804字面stop、metadata configured tick及LC历史effective tick，fresh R另算。固定43分层独立SQL case→039 trace（原12均匀+exchange/year/roll/held差异），不调用042 builder或052 extractor/aggregation；state/entry/stop/qty/实际reference open腿/原episode R/两个signal clock全部吻合。
- 首unknown C2发生在本日daily age更新前，state.bars_since_entry0不等于缺日；原episode fresh signal用于来源/R，roll新layer signal用于age，不能混用。trade_date是source交易标签，可能需前一自然夜盘，不能拿它直接裁自然日minute；T00逻辑参考不冒充09:00实体open。
- source/产物SHA前后不变。broker/native/physical资格仍False；metadata_order_book_id与042 LC tick lookup字符串是提示，CZCE别名不可机械拼接。完整首blockerminute即使补齐也不保证60日后续全known；910事件复用2209窗不算2209独立新增样本。
- 输出outputs/stage053_independent_c2_demand_review/{baseline.json,independent_expected_month_windows.csv,review.py,review.json,independent_replay.py,independent_trace_samples.csv,README.md}。054已同步可用exact需求后按provider/session/OHLC资格审查，不转授旧receipt。
- 新增/修改/删除alpha参数与金融回测结果无；minute fills、训练标签、model fit、下载、订单、生产修改0。期末权益/收益/回撤/Sharpe/总滑点/真实交易次数/胜率N/A。
- 调研判断继承Stage010/021官方vn.py/GitHub与冻结执行合同并由本SQL/trace证据核：来源需求必须跟实际held和交易日状态走。开始/结束新增收益选参过拟合否，无收益排序；继续价值是，精确资料定位可减少监督未知并防止错约补数，但未证明模型预测或收益改善。
