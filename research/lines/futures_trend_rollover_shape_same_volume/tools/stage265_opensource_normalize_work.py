"""Read preserved Work CSV samples; exact epoch/date joins, no imputation/DB write.

The third-party repository has GPLv3 text, but vendor-data redistribution rights
are not asserted. This is an isolated provenance/coverage/quality sample only.
"""
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from zoneinfo import ZoneInfo

from stage264_build_daily_manifest import contract_identity
from stage264_normalize_shfe_years import compare_existing, contract_report

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
BASE = LINE / "outputs/stage265_deep_daily/opensource"
MANIFEST = LINE / "outputs/stage264_pre_main_daily/manifest_contracts.csv"
MAIN_DATES = MANIFEST.with_name("manifest_main_dates.csv")
COMMIT = "e8dd9a55b9a30b1e3033fe838724c23fcdd87ad1"
FIELDS = {"open": "open", "high": "high", "low": "low", "close": "cl", "volume": "vol", "open_interest": "oi"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vendor_identity(vendor, day):
    match = re.fullmatch(r"([A-Za-z]+)([0-9]{3,4})\.CZC", vendor)
    if not match:
        raise ValueError("not_real_czce_vendor_contract")
    product, digits = match.groups()
    identity = contract_identity(f"{product.upper()}{digits}.CZCE", day)
    delivery = identity["contract_yyyymm"]
    if day[:7].replace("-", "") > delivery:
        raise ValueError("after_delivery_month")
    canonical = f"{product.upper()}{int(delivery[:4]) % 10}{delivery[-2:]}.CZCE"
    return f"{canonical}@{delivery}", canonical, f"{product.upper()}.CZCE"


def read_wide(path):
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig", newline="")))
    cells = {}
    duplicates = 0
    for row_number, row in enumerate(rows, 2):
        day = row[""]
        date.fromisoformat(day)
        for vendor, value in row.items():
            if not vendor or value is None or not value.strip() or value.lower() == "nan":
                continue
            key = (day, vendor)
            if key in cells:
                duplicates += 1
                raise ValueError(f"duplicate_wide_day_vendor:{path.name}:{key}")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"nonfinite_wide_cell:{path.name}:{key}")
            cells[key] = (number, row_number)
    return cells, {"file": path.name, "sha256": sha(path), "rows": len(rows), "first_date": rows[0][""] if rows else None,
                   "last_date": rows[-1][""] if rows else None, "nonmissing_cells": len(cells),
                   "vendor_contracts_with_values": len({vendor for day, vendor in cells}), "duplicate_keys": duplicates}


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    manifests = [row for row in csv.DictReader(MANIFEST.open(encoding="utf-8-sig")) if row["product"] == "SM.CZCE"]
    by_epoch = {row["contract_epoch_id"]: row for row in manifests}
    tree = json.loads((BASE / "ildhj_work_tree.raw").read_bytes())
    blobs = {item["path"]: item["sha"] for item in tree["tree"] if item["type"] == "blob"}
    field_cells, field_info, mismatches, canonical_collisions = {}, [], [], []
    for field, suffix in FIELDS.items():
        path = BASE / f"work_SM_data_{suffix}.raw"
        payload = path.read_bytes()
        git_blob = hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()
        if git_blob != blobs[f"Futures_Data/data_{suffix}/SM.csv"]:
            raise RuntimeError("sample_does_not_match_pinned_git_blob")
        cells, info = read_wide(path)
        info["verified_git_blob_sha1"] = git_blob
        field_info.append(info)
        resolved = {}
        for (day, vendor), (value, row_number) in cells.items():
            try:
                epoch, vt, product = vendor_identity(vendor, day)
            except ValueError:
                continue
            if epoch not in by_epoch:
                continue
            key = (epoch, day)
            if key in resolved:
                canonical_collisions.append({"field": field, "contract_epoch_id": epoch, "date": day, "vendor": vendor})
                raise RuntimeError("canonical_alias_collision_requires_review")
            resolved[key] = (value, vendor, row_number)
        field_cells[field] = resolved
    all_keys = set.union(*(set(cells) for cells in field_cells.values()))
    accepted, rejected = [], []
    for epoch, day in sorted(all_keys):
        missing = [field for field in FIELDS if (epoch, day) not in field_cells[field]]
        if missing:
            rejected.append({"contract_epoch_id": epoch, "date": day, "reason": "missing_required_fields", "missing_fields": ",".join(missing)})
            continue
        values = {field: field_cells[field][(epoch, day)][0] for field in FIELDS}
        op, hi, lo, cl = (values[field] for field in ("open", "high", "low", "close"))
        if min(op, hi, lo, cl) <= 0 or not lo <= min(op, cl) <= max(op, cl) <= hi or values["volume"] < 0 or values["open_interest"] < 0:
            rejected.append({"contract_epoch_id": epoch, "date": day, "reason": "invalid_ohlc_or_negative_units", "missing_fields": ""})
            continue
        item = by_epoch[epoch]
        accepted.append({"contract_epoch_id": epoch, "vt_symbol": item["vt_symbol"], "product": item["product"], "date": day, **values,
                         "source": "ildhj0116/Work", "source_commit": COMMIT,
                         "vendor_contract": field_cells["open"][(epoch, day)][1],
                         "source_field_rows": json.dumps({field: field_cells[field][(epoch, day)][2] for field in FIELDS}),
                         "volume_units": "raw_vendor_units_pending_comparison", "oi_clock": "pending_comparison"})
    existing = defaultdict(list)
    connection = sqlite3.connect((ROOT / ".vntrader/database.db").resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    try:
        for manifest in manifests:
            for row in connection.execute("SELECT datetime,open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata WHERE symbol=? AND exchange='CZCE' AND interval='d' ORDER BY datetime",
                                          (manifest["vt_symbol"].split(".")[0],)):
                day = row["datetime"][:10]
                try:
                    identity = contract_identity(manifest["vt_symbol"], day)
                except ValueError:
                    continue
                if identity["contract_epoch_id"] != manifest["contract_epoch_id"]:
                    continue
                existing[manifest["contract_epoch_id"]].append({"contract_epoch_id": manifest["contract_epoch_id"], "date": day,
                    "existing_datetime": row["datetime"], **{field: row[field+"_price"] if field in ("open", "high", "low", "close") else row[field] for field in FIELDS}})
    finally:
        connection.close()
    grouped = defaultdict(list)
    for row in accepted:
        grouped[row["contract_epoch_id"]].append(row)
    main_dates, missing_main = defaultdict(set), set()
    for row in csv.DictReader(MAIN_DATES.open(encoding="utf-8-sig")):
        if row["product"] == "SM.CZCE":
            main_dates[row["contract_epoch_id"]].add(row["date"])
            if row["coverage_ok"].lower() != "true":
                missing_main.add((row["contract_epoch_id"], row["date"]))
    annotated, differences, reports = [], [], []
    for item in manifests:
        epoch = item["contract_epoch_id"]
        actual, diffs, _ = compare_existing(grouped[epoch], existing[epoch])
        annotated.extend(actual)
        differences.extend(diffs)
        reports.append(contract_report(item, grouped[epoch], existing[epoch], main_dates[epoch]))
    accepted_keys = {(row["contract_epoch_id"], row["date"]) for row in accepted}
    covered_gaps = sorted(missing_main & accepted_keys)
    out_fields = ["contract_epoch_id", "vt_symbol", "product", "date", *FIELDS, "source", "source_commit", "vendor_contract", "source_field_rows",
                  "volume_units", "oi_clock", "overlap_status", "matches_existing_ohlc", "matches_existing_volume", "matches_existing_open_interest", "matches_existing_all"]
    write_csv(BASE / "work_SM_normalized_bars.csv", annotated, out_fields)
    write_csv(BASE / "work_SM_rejected_rows.csv", rejected, ["contract_epoch_id", "date", "reason", "missing_fields"])
    diff_fields = ["contract_epoch_id", "vt_symbol", "date", "existing_datetime", "different_fields", *(name for field in FIELDS for name in ("official_"+field,"existing_"+field))]
    write_csv(BASE / "work_SM_overlap_differences.csv", differences, diff_fields)
    report = {"generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "source_commit": COMMIT,
              "source_commit_date": "2018-04-26", "status": "isolated_sparse_third_party_sample_pending_independent_review",
              "field_coverage": field_info, "contracts": reports,
              "summary": {"target_epochs": len(manifests), "valid_complete_rows": len(accepted), "rejected_rows": len(rejected),
                  "rejected_reasons": dict(Counter(row["reason"] for row in rejected)), "SM_original_missing_main_days": len(missing_main),
                  "SM_missing_main_days_sample_covers": len(covered_gaps), "SM_missing_main_days_still_missing": len(missing_main - accepted_keys),
                  "new_unique_days": sum(row["official_new_unique_days"] for row in reports),
                  "new_pre_main_days": sum(row["official_new_pre_main_days"] for row in reports),
                  "overlap_days": sum(row["overlap_days"] for row in reports),
                  "different_field_counts": {field:sum(row["different_field_counts"][field] for row in reports) for field in FIELDS}},
              "covered_SM_missing_main_dates": [{"contract_epoch_id": epoch,"date":day} for epoch,day in covered_gaps],
              "remaining_SM_missing_main_dates": [{"contract_epoch_id": epoch,"date":day} for epoch,day in sorted(missing_main-accepted_keys)],
              "limitations": ["high/low begin 2015-01-05 while other fields begin 2014; no 2014 full OHLC is inferred",
                  "Sparse quoted/traded contract wide tables; missing cells never imputed",
                  "Only GPLv3 repository license seen; vendor-data redistribution rights not established",
                  "2018-04-26 snapshot cannot cover 2019 or SA listings; no merge/main database write"],
              "output_sha256": {name:sha(BASE/name) for name in ("work_SM_normalized_bars.csv", "work_SM_rejected_rows.csv", "work_SM_overlap_differences.csv")}}
    (BASE / "work_SM_quality_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report["summary"],ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
