# Stage001 全市场PIT数据源重建与覆盖审计

- 决策：`stage001_source_rebuild_coverage_fail_close_no_model`。
- 截止日目录：`4603`个合约、`80`个商品品种。
- 映射：`105440`行、`80`个品种、`2191`个具体主力合约。
- 日线：`894144`行；截止日之后丢弃行=`0`。
- 覆盖行/合格行/池外挑战行：`3836/2840/1947`。
- 每月合格品种最小/中位/最大：`0` / `52.5` / `59`。
- A-rank10合格月/动作就绪月：`47` / `47`；合格月池外挑战者最小值=`34`。
- source gates：`{"bar_future_rows_zero": true, "catalog_asof_exact_cutoff": true, "fetch_failed_zero": true, "fetch_status_complete": true, "label_values_read_zero": true, "mapping_contracts_in_catalog": true, "mapping_future_rows_zero": true, "model_fit_zero": true, "normalised_bar_duplicates_zero": true, "production_writes_zero": true, "raw_rows_after_cutoff_dropped_zero": true, "strategy_backtest_zero": true}`。
- coverage gates：`{"challenger_breadth_on_each_eligible_baseline_month": true, "coverage_duplicates_zero": true, "cxffex_eligible_rows_zero": true, "eligible_breadth_each_month": false, "fallback_rows_zero": true, "formal_replacement_eligible_months": true, "future_bar_rows_used_zero": true, "future_mapping_rows_used_zero": true, "label_rows_read_zero": true, "monthly_row_count_exact": true}`。
- 未读取收益标签，未fit/predict，未运行策略回测，未连接CTP，未调用订单API，未写生产文件。
- 即使通过，也只允许另立模型预注册，不自动授权XGBoost、真实引擎或上线。
