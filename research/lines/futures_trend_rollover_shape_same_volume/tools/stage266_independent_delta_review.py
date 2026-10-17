"""Prove the final legacy-price quarantine is a strict 10-row subset.

Only compares frozen SQLite states and affected CSV exports. Never reloads a
market source or the private legacy database. Run after the parent freezes delta.
"""
import argparse
from datetime import datetime
import csv
import json
from pathlib import Path

import stage266_independent_validate as audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delta", type=Path, required=True)
    args = parser.parse_args()
    out = audit.BASE
    before_path = out / "before_legacy_delta.sqlite"
    base = audit.LINE / "outputs/stage266_clean_daily"
    contract = audit.json_load(base / "contract.json")
    db_path = Path(contract["db_path"])
    original = audit.json_load(out / "independent_validation.json")
    if audit.sha(before_path) != original["inputs"]["database"]["sha256"]:
        raise ValueError("before_snapshot_does_not_match_full_independent_validation")
    with args.delta.open(encoding="utf-8-sig", newline="") as f:
        expected = {(r["contract_epoch_id"], r["trade_date"]) for r in csv.DictReader(f)}
    if len(expected) != 10:
        raise ValueError("expected_exactly_ten_delta_keys")
    before_sha = audit.sha(before_path)
    new_sha = audit.sha(db_path)
    if new_sha != contract["final_database_sha256"]:
        raise ValueError("final_database_sha_mismatch")
    problems = []
    with audit.read_only_connection(before_path) as db:
        db.execute("ATTACH DATABASE ? AS final", (db_path.resolve().as_uri() + "?mode=ro",))
        fields = [r["name"] for r in db.execute("PRAGMA table_info(daily_bars)")]
        new_fields = [r["name"] for r in db.execute("PRAGMA final.table_info(daily_bars)")]
        if fields != new_fields:
            raise ValueError("delta_changed_daily_schema")
        join = "o.contract_epoch_id=n.contract_epoch_id AND o.trade_date=n.trade_date"
        added = db.execute("SELECT COUNT(*) FROM final.daily_bars n LEFT JOIN main.daily_bars o ON " + join + " WHERE o.contract_epoch_id IS NULL").fetchone()[0]
        changed = db.execute("SELECT COUNT(*) FROM main.daily_bars o JOIN final.daily_bars n ON " + join + " WHERE " + " OR ".join(f'o."{x}" IS NOT n."{x}"' for x in fields)).fetchone()[0]
        removed = [dict(r) for r in db.execute("SELECT o.* FROM main.daily_bars o LEFT JOIN final.daily_bars n ON " + join + " WHERE n.contract_epoch_id IS NULL ORDER BY o.contract_epoch_id,o.trade_date")]
        removed_keys = {(r["contract_epoch_id"], r["trade_date"]) for r in removed}
        if removed_keys != expected or added or changed:
            problems.append("delta_not_exact_ten_row_deletion_only")
        tables_unchanged = {}
        for table in ("sources", "contracts"):
            unequal = db.execute(f"SELECT COUNT(*) FROM (SELECT * FROM main.{table} EXCEPT SELECT * FROM final.{table})").fetchone()[0]
            reverse = db.execute(f"SELECT COUNT(*) FROM (SELECT * FROM final.{table} EXCEPT SELECT * FROM main.{table})").fetchone()[0]
            tables_unchanged[table] = unequal == reverse == 0
        if not all(tables_unchanged.values()):
            problems.append("source_or_contract_metadata_changed")
        old_count = db.execute("SELECT COUNT(*) FROM main.daily_bars").fetchone()[0]
        final_count = db.execute("SELECT COUNT(*) FROM final.daily_bars").fetchone()[0]
        final_legacy = db.execute("SELECT SUM(legacy108_row_usable) FROM final.daily_bars").fetchone()[0]
        final_families = {r[0]: r[1] for r in db.execute("SELECT s.family,COUNT(*) FROM final.daily_bars b JOIN final.sources s USING(source_id) GROUP BY s.family")}
        if any(r["legacy108_row_usable"] or r["train_eligible"] or r["open_oi"] is not None or r["source_id"] != "rqalpha" for r in removed):
            problems.append("delta_removed_other_than_close_only_RQ_rows")
    old_inventory = {x["contract_epoch_id"]: x for x in audit.json_load(out / "before_legacy_delta_csv_inventory.json")}
    inventory = {x["contract_epoch_id"]: x for x in audit.json_load(base / "csv_inventory.json")}
    affected = {key[0] for key in expected}
    if set(inventory) != set(old_inventory):
        problems.append("delta_changed_CSV_epoch_set")
    unaffected_receipts_same = all(inventory[k] == v for k, v in old_inventory.items() if k not in affected)
    if not unaffected_receipts_same:
        problems.append("delta_changed_unaffected_CSV_receipt")
    csv_checks = []
    quarantine_checks = {}
    with audit.read_only_connection(db_path) as db:
        units = audit.json_load(contract["unit_contract_path"])
        for label, path, expected_sha in (
            ("quantity", units["quarantine"]["path"], units["quarantine"]["sha256"]),
            ("price", contract["price_conflict_path"], contract["price_conflict_sha256"]),
        ):
            if audit.sha(path) != expected_sha:
                problems.append(label + "_quarantine_SHA_mismatch")
            with Path(path).open(encoding="utf-8-sig", newline="") as f:
                keys = {(r["contract_epoch_id"], r["trade_date"]) for r in csv.DictReader(f)}
            leaks = sum(db.execute("SELECT COUNT(*) FROM daily_bars WHERE contract_epoch_id=? AND trade_date=?", key).fetchone()[0] for key in keys)
            quarantine_checks[label] = {"keys": len(keys), "leaks": leaks, "sha256": expected_sha}
            if leaks:
                problems.append(label + "_quarantine_key_leaked")
        if quarantine_checks["quantity"]["keys"] != 2294 or quarantine_checks["price"]["keys"] != 304:
            problems.append("final_quarantine_count_mismatch")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            problems.append("final_database_integrity_failure")
        for epoch in sorted(affected):
            item = inventory[epoch]
            path = base / item["path"]
            if audit.sha(path) != item["sha256"]:
                problems.append("delta_CSV_SHA_mismatch:" + epoch)
            with path.open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            native = [dict(r) for r in db.execute("SELECT * FROM daily_bars WHERE contract_epoch_id=? ORDER BY trade_date", (epoch,))]
            matches = len(rows) == len(native) == item["rows"]
            for row, raw in zip(rows, native):
                for field, value in row.items():
                    if field == "datetime":
                        same = value == raw["trade_date"] + " 00:00:00+08:00"
                    elif raw.get(field) is None:
                        same = value == ""
                    elif isinstance(raw[field], (int, float)):
                        same = audit.equal(value, raw[field])
                    else:
                        same = value == str(raw[field])
                    matches &= same
            if not matches:
                problems.append("delta_CSV_field_mismatch:" + epoch)
            removed_here = sum(k[0] == epoch for k in expected)
            if old_inventory[epoch]["rows"] - item["rows"] != removed_here or item["legacy108_rows"] != old_inventory[epoch]["legacy108_rows"]:
                problems.append("delta_CSV_count_change_mismatch:" + epoch)
            csv_checks.append({"contract_epoch_id": epoch, "rows": len(rows), "all_fields_match": matches, "sha256": item["sha256"]})
    original_reader = audit.json_load(out / "independent_reader_review.json")
    coverage_paths = {}
    with audit.read_only_connection(db_path) as db:
        for name, fields, query in (
            ("coverage_by_exchange_year.csv", ["exchange", "year", "products", "contracts", "rows", "legacy108_rows", "first_date", "last_date"],
             "SELECT exchange,substr(trade_date,1,4),COUNT(DISTINCT product),COUNT(DISTINCT contract_epoch_id),COUNT(*),SUM(legacy108_row_usable),MIN(trade_date),MAX(trade_date) FROM daily_bars GROUP BY exchange,substr(trade_date,1,4) ORDER BY exchange,substr(trade_date,1,4)"),
            ("coverage_by_contract.csv", ["contract_epoch_id", "exchange", "product", "contract_yyyymm", "rows", "legacy108_rows", "first_date", "last_date"],
             "SELECT contract_epoch_id,exchange,product,contract_yyyymm,COUNT(*),SUM(legacy108_row_usable),MIN(trade_date),MAX(trade_date) FROM daily_bars GROUP BY contract_epoch_id ORDER BY contract_epoch_id"),
        ):
            path = out / name
            with path.open("w", newline="") as f:
                writer = csv.writer(f); writer.writerow(fields); writer.writerows(db.execute(query))
            coverage_paths[name] = audit.sha(path)
        selected_by_exchange = [dict(r) for r in db.execute("SELECT exchange,COUNT(*) AS rows,COUNT(DISTINCT contract_epoch_id) AS contracts,SUM(legacy108_row_usable) AS legacy108_rows,MIN(trade_date) AS first_date,MAX(trade_date) AS last_date FROM daily_bars GROUP BY exchange")]
    if audit.sha(db_path) != new_sha:
        problems.append("database_changed_during_delta_review")
    report = {"generated_at": datetime.now().astimezone().isoformat(), "status": "PASS_MONOTONIC_DELETION_SUBSET" if not problems else "FAIL",
              "review_script_sha256": audit.sha(__file__), "prior_full_independent_report_sha256": audit.sha(out / "independent_validation.json"),
              "prior_full_database_sha256": before_sha, "final_database_sha256": new_sha, "final_contract_sha256": audit.sha(base / "contract.json"),
              "delta_path": str(args.delta), "delta_sha256": audit.sha(args.delta), "old_rows": old_count, "final_rows": final_count,
              "added_rows": added, "modified_existing_rows": changed, "deleted_rows": len(removed), "deleted_keys_exactly_declared": removed_keys == expected,
              "deleted_row_evidence": removed, "legacy108_rows": final_legacy, "source_family_counts": final_families,
              "source_and_contract_tables_unchanged": tables_unchanged, "unaffected_CSV_inventory_receipts_unchanged": unaffected_receipts_same,
              "final_quarantine_key_checks": quarantine_checks,
              "affected_CSV_all_field_checks": csv_checks, "final_coverage_receipts": coverage_paths, "by_exchange": selected_by_exchange,
              "inherited_checks": {"prior_selected_native_comparisons": original["counts"]["raw_source_rows_compared"], "final_selected_native_accuracy_safe_subset": final_count,
                                   "legacy108_eligibility_inherited_unchanged": final_legacy == original["counts"]["legacy108_row_usable_rows"],
                                   "reader_120_day_probe_remains_valid": original_reader["actual_default_120_window"]["contract_epoch_id"] not in affected},
              "findings": problems, "new_market_sources_read": 0, "private_legacy_database_reread": False, "main_database_writes": 0,
              "boundary": "Every surviving selected row is byte-value identical to a previously exhaustively validated row. This proves a monotonic safe subset; it does not choose which legacy/RQ price was true."}
    audit.json_save(out / "final_monotonic_delta_review.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in {"deleted_row_evidence", "affected_CSV_all_field_checks", "by_exchange"}}, ensure_ascii=False))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
