# Stage002 截止日完整日K数据源修复与覆盖审计

- 决策：`stage002_endofday_source_rebuild_coverage_pass_allow_new_model_preregistration_only`。
- 唯一实现修复：整批订阅后推进到 `BacktestFinished`，再复制截止日日K。
- 目录、主力映射、采集计划、54个月、资格阈值和覆盖核心均与Stage001完全相同。
- 日线：`894144`行；未来行=`0`。
- 覆盖行/合格行/池外挑战行：`3836/2900/1989`。
- 每月合格品种最小/中位/最大：`50` / `53.0` / `60`。
- A-rank10合格月/动作就绪月：`48` / `48`；合格月池外挑战者最小值=`34`。
- source gates：`{"bar_future_rows_zero": true, "catalog_asof_exact_cutoff": true, "fetch_failed_zero": true, "fetch_status_complete": true, "label_values_read_zero": true, "mapping_contracts_in_catalog": true, "mapping_future_rows_zero": true, "model_fit_zero": true, "normalised_bar_duplicates_zero": true, "production_writes_zero": true, "raw_rows_after_cutoff_dropped_zero": true, "strategy_backtest_zero": true}`。
- coverage gates：`{"challenger_breadth_on_each_eligible_baseline_month": true, "coverage_duplicates_zero": true, "cxffex_eligible_rows_zero": true, "eligible_breadth_each_month": true, "fallback_rows_zero": true, "formal_replacement_eligible_months": true, "future_bar_rows_used_zero": true, "future_mapping_rows_used_zero": true, "label_rows_read_zero": true, "monthly_row_count_exact": true}`。
- 未读取收益标签，未fit/predict，未运行策略回测，未连接CTP，未调用订单API，未写生产文件。
- 通过仅证明数据资格，仍不证明XGBoost能提高收益或降低回撤。
