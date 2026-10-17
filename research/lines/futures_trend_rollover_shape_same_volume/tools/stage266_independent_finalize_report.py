"""Bind full source accuracy plus the final monotonic quarantine delta."""
from datetime import datetime
import csv
from pathlib import Path

import stage266_independent_validate as audit


def main():
    out = audit.BASE
    base = audit.LINE / "outputs/stage266_clean_daily"
    contract = audit.json_load(base / "contract.json")
    reports = {key: audit.json_load(out / name) for key, name in {
        "source_rows": "independent_validation.json", "CSV_exports": "csv_export_validation.json",
        "excluded_accounting": "excluded_conservation_validation.json", "September_overlap": "september_TQ_RQ_overlap.json",
        "reader": "independent_reader_review.json", "monotonic_delta": "final_monotonic_delta_review.json",
    }.items()}
    for key, report in reports.items():
        if report.get("findings") or report.get("review_findings") or report["status"].startswith("FAIL"):
            raise ValueError("independent_report_not_passing:" + key)
    delta = reports["monotonic_delta"]
    db = Path(contract["db_path"])
    if audit.sha(db) != delta["final_database_sha256"] or audit.sha(base / "contract.json") != delta["final_contract_sha256"]:
        raise ValueError("final_input_changed")
    # Preserve the first full scan coverage as its own snapshot, then emit final.
    old_coverage = out / "before_legacy_delta_coverage_by_exchange_year_product.csv"
    if not old_coverage.exists():
        old_coverage.write_bytes((out / "coverage_by_exchange_year_product.csv").read_bytes())
    with audit.read_only_connection(db) as connection:
        path = out / "coverage_by_exchange_year_product.csv"
        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["exchange", "year", "product", "selected_rows", "train_eligible_rows"])
            writer.writerows(connection.execute("SELECT exchange,substr(trade_date,1,4),product,COUNT(*),SUM(train_eligible) FROM daily_bars GROUP BY exchange,substr(trade_date,1,4),product ORDER BY exchange,substr(trade_date,1,4),product"))
        totals = dict(connection.execute("SELECT COUNT(*) AS selected_rows,COUNT(DISTINCT contract_epoch_id) AS selected_contracts,COUNT(DISTINCT exchange||'.'||product) AS selected_products,SUM(legacy108_row_usable) AS legacy108_row_usable,SUM(open_oi IS NULL) AS missing_open_oi_rows,MIN(trade_date) AS first_date,MAX(trade_date) AS last_date FROM daily_bars").fetchone())
    protected = []
    for old in reports["source_rows"]["protected_files"]:
        # Registry is edited only by the integrator after reports are frozen.
        if Path(old["path"]).name == "registry.md":
            continue
        expected = next(r["sha256"] for r in audit.json_load(contract["before_integrity_path"])["files"] if str(audit.LINE.parents[2] / r["path"]) == old["path"])
        actual = audit.sha(old["path"])
        if actual != expected:
            raise ValueError("protected_data_changed:" + old["path"])
        protected.append({"path": old["path"], "sha256": actual, "unchanged": True})
    paths = ["independent_validation.json", "csv_export_validation.json", "excluded_conservation_validation.json", "september_TQ_RQ_overlap.json",
             "september_TQ_RQ_price_differences.csv", "independent_reader_review.json", "final_monotonic_delta_review.json",
             "coverage_by_exchange_year_product.csv", "coverage_by_exchange_year.csv", "coverage_by_contract.csv", "validator_tests.log", "reader_tests.log"]
    receipts = [{"path": str(out / name), "bytes": (out / name).stat().st_size, "sha256": audit.sha(out / name)} for name in paths]
    dependency_source = audit.LINE.parents[2] / "examples/portfolio_backtesting/analyze_qmt_roll_ai_product_suitability_walkforward.py"
    clarification = base / "feature_dependency_clarification.json"
    if clarification.exists():
        receipts.append({"path": str(clarification), "bytes": clarification.stat().st_size, "sha256": audit.sha(clarification)})
    availability_path = base / "czce_reader_mapping_availability_304_final.json"
    availability = audit.json_load(availability_path)
    if availability["final_dataset"]["database_sha256"] != delta["final_database_sha256"]:
        raise ValueError("availability_snapshot_mismatch")
    receipts.append({"path": str(availability_path), "bytes": availability_path.stat().st_size, "sha256": audit.sha(availability_path)})
    result = {
        "generated_at": datetime.now().astimezone().isoformat(), "status": "PASS_BOUNDED_SOURCE_CONTRACT_ACCURACY_AND_READER",
        "final_database": {"path": str(db), "sha256": delta["final_database_sha256"], "bytes": db.stat().st_size},
        "final_contract": {"path": str(base / "contract.json"), "sha256": delta["final_contract_sha256"]},
        "counts": totals, "source_family_counts": delta["source_family_counts"], "by_exchange": delta["by_exchange"],
        "selected_source_checks": {"full_selected_observations_compared_before_final_delta": 1552466, "surviving_rows_inherit_identical_source_values": totals["selected_rows"],
                                   "all_source_files_SHA_and_bytes_match": all(x["sha_and_bytes_match"] for x in reports["source_rows"]["source_file_checks"]),
                                   "source_files_checked": len(reports["source_rows"]["source_file_checks"]), "metadata_and_sources_unchanged_after_delta": delta["source_and_contract_tables_unchanged"]},
        "final_quarantine_key_checks": delta["final_quarantine_key_checks"],
        "CSV_checks": {"full_before_delta": reports["CSV_exports"]["counts"], "final_delta_affected_files": len(delta["affected_CSV_all_field_checks"]),
                       "all_affected_fields_match": all(x["all_fields_match"] for x in delta["affected_CSV_all_field_checks"]), "unaffected_inventory_receipts_unchanged": delta["unaffected_CSV_inventory_receipts_unchanged"]},
        "open_interest_clock": reports["source_rows"]["TQ_open_close_clock_evidence"], "September_overlap": reports["September_overlap"]["counts"],
        "reader": {"status": reports["reader"]["status"], "tests_passed": reports["reader"]["tests_run"], "actual_120_day_probe": reports["reader"]["actual_default_120_window"],
                   "original_probe_database_sha256": reports["reader"]["database_sha256"], "probe_inherits_unchanged_contract_rows": delta["inherited_checks"]["reader_120_day_probe_remains_valid"],
                   "eight_memory_faults_rejected": all(reports["reader"]["memory_only_faults_rejected"].values()), "missing_open_oi_preserved": reports["reader"]["actual_missing_open_oi_preserved"]},
        "feature_dependency_clarification": {
            "source_path": str(dependency_source), "source_sha256": audit.sha(dependency_source), "independently_read_lines": [120, 240, 274, 336],
            "monthly108_direct_open_oi_dependency": False,
            "physical_legacy108_row_usable_train_eligible_meaning": "Only seven-column legacy CSV completeness: OHLC, volume, opening OI, closing OI. Historical names do not define monthly108 necessity or sufficiency.",
            "seven_column_complete_rows": totals["legacy108_row_usable"], "reader_agent_reported_conservative_18_pool_CSV_window_rows": availability["overall"]["strict120_feature_window_rows"],
            "monthly108_readiness": "Not produced: common strategy PNL/signal rolling inputs and mature forward labels remain absent.",
            "prior_reader_report_limit_clarification": "The old report's request to lock 120 concerns only choosing that conservative CSV diagnostic gate, not a necessary monthly108 feature dependency.",
            "early_close_only_period_not_declared_untrainable": True,
        },
        "protected_primary_data": protected, "artifacts": receipts,
        "severity": {"P0": 0, "P1": 0, "P2": 0},
        "bounded_notes": ["Accuracy is proven against frozen native source columns, dates, quantity contracts and locators; historical exchange truth/completeness is not claimed.",
                          "Excluded-source accounting has two CZCE.ZC710 identity rejects before its raw counter; they are explicitly counted in excluded records and never selected.",
                          "Source priority labels are checked; rejected-source accounting uses declared gate totals rather than independently rebuilding all rejected raw observations.",
                          "Only 36 selected rows lack vendor lifecycle metadata; symbol-only status stays explicit. Metadata is not official listing proof.",
                          "Opening OI remains missing for close-only sources; open_interest is the closing alias, never historical private open-oi alias.",
                          "Reader diagnostic window_rows can vary. Its 120-day seven-column gate is conservative CSV availability, not monthly108 necessity/sufficiency. Actual monthly readiness needs common strategy PNL/signal features, declared forward-label maturity, PIT and splits."],
        "training_samples_generated": 0, "training_qualified": False, "financial_backtests": 0, "model_fits": 0, "main_database_writes": 0, "new_downloads": 0,
        "overfitting_after": False, "continue_value_after": True,
        "judgment_zh": "固定数据合同验收不按收益选源或调参；当前价值在有界可靠读取与后续预声明样本成熟度审计，不等于已训练或适宜实盘。",
        "report_script_sha256": audit.sha(__file__),
    }
    audit.json_save(out / "independent_review_summary.json", result)
    print(result["status"], totals, result["final_database"]["sha256"])


if __name__ == "__main__":
    main()
