"""Normalize official annual SHFE XLS ZIPs into an isolated candidate dataset.

No downloads, database writes, model fitting or replay. All original prices and
pre-2020 two-sided volume/open interest units are retained. A normalized source
is not an accepted merged dataset; old-database differences remain quarantined.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import date, datetime
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from zipfile import ZipFile
from zoneinfo import ZoneInfo

import xlrd

from stage264_build_daily_manifest import contract_identity


LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
BASE = LINE / "outputs/stage264_pre_main_daily"
OUTPUT = BASE / "shfe_official"
DATABASE = ROOT / ".vntrader/database.db"
YEARS = tuple(range(2014, 2020))
PRODUCT_COUNTS = {"au.SHFE": 12, "cu.SHFE": 60, "hc.SHFE": 16, "rb.SHFE": 16, "ru.SHFE": 16, "sp.SHFE": 4}
NUMERIC = ("open", "high", "low", "close", "volume", "open_interest")
PRICE = NUMERIC[:4]
BASE_FIELDS = ("contract_epoch_id", "vt_symbol", "product", "date", *NUMERIC,
               "source_year", "raw_member", "row", "raw_sheet")
FLAGS = ("overlap_status", "matches_existing_ohlc", "matches_existing_volume", "matches_existing_open_interest", "matches_existing_all")
HEADER = {"instrument": "合约", "date": "日期", "open": "开盘价", "high": "最高价",
          "low": "最低价", "close": "收盘价", "volume": "成交量", "open_interest": "持仓量"}


def stamp() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_value(value) -> str:
    if isinstance(value, (float, int)) and math.isfinite(value) and value == int(value):
        return str(int(value))
    return str(value).strip()


def sheet_records(rows) -> tuple[list[dict], dict]:
    """Decode actual annual-report grouping; footer cannot lend a contract code."""
    actual, columns, current = [], None, None
    info = {"header_row": None, "skipped_non_data_rows": 0, "group_blank_contract_rows": 0}
    for row_number, values in enumerate(rows, 1):
        labels = [text_value(value) for value in values]
        if all(label in labels for label in HEADER.values()):
            columns = {key: labels.index(label) for key, label in HEADER.items()}
            info["header_row"] = row_number
            current = None
            continue
        if columns is None:
            continue
        if len(values) <= max(columns.values()):
            values = list(values) + [""] * (max(columns.values()) + 1 - len(values))
        instrument = text_value(values[columns["instrument"]])
        day = text_value(values[columns["date"]])
        if instrument and not re.fullmatch(r"[A-Za-z]+[0-9]+", instrument):
            current = None
            info["skipped_non_data_rows"] += 1
            # Annual footnotes are after the entire report, not new trade rows.
            if "注" in instrument:
                break
            continue
        if instrument:
            current = instrument
        if not current or not day:
            info["skipped_non_data_rows"] += 1
            continue
        if not instrument:
            info["group_blank_contract_rows"] += 1
        item = {key: values[index] for key, index in columns.items()}
        item.update(instrument=current, date=day, row=row_number)
        actual.append(item)
    if columns is None:
        raise ValueError("annual_xls_header_not_found")
    info["extracted_trade_rows"] = len(actual)
    return actual, info


def parse_day(value) -> date:
    raw = text_value(value)
    if re.fullmatch(r"[0-9]{8}", raw):
        raw = f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    try:
        return date.fromisoformat(raw)
    except ValueError as error:
        raise ValueError("invalid_date") from error


def validate_numeric(row: dict) -> None:
    if not all(math.isfinite(row[field]) for field in NUMERIC):
        raise ValueError("nonfinite_numeric")
    if row["volume"] < 0 or row["open_interest"] < 0:
        raise ValueError("negative_volume_or_open_interest")
    if all(row[field] == 0 for field in PRICE) and row["volume"] == 0:
        raise ValueError("zero_price_no_trade_placeholder")
    if any(row[field] <= 0 for field in PRICE):
        raise ValueError("nonpositive_ohlc")
    op, hi, lo, cl = (row[field] for field in PRICE)
    if not lo <= min(op, cl) <= max(op, cl) <= hi:
        raise ValueError("inconsistent_ohlc")


def normalize_record(raw: dict, source_year: int, raw_member: str, epochs: dict) -> dict:
    instrument = text_value(raw["instrument"]).lower()
    if not re.fullmatch(r"[a-z]+[0-9]{4}", instrument):
        raise ValueError("not_real_contract")
    vt = f"{instrument}.SHFE"
    if vt not in epochs:
        raise ValueError("outside_manifest")
    manifest = epochs[vt]
    day = parse_day(raw["date"])
    if day.year != source_year:
        raise ValueError("source_year_mismatch")
    try:
        identity = contract_identity(vt, day.isoformat())
    except ValueError as error:
        raise ValueError("delivery_epoch_mismatch") from error
    if identity["contract_epoch_id"] != manifest["contract_epoch_id"]:
        raise ValueError("delivery_epoch_mismatch")
    delivery = manifest["contract_yyyymm"]
    if (day.year, day.month) > (int(delivery[:4]), int(delivery[4:])):
        raise ValueError("after_delivery_month")
    try:
        no_trade = float(raw["volume"]) == 0
    except (ValueError, TypeError, KeyError):
        no_trade = False
    if no_trade and any(text_value(raw[key]) in ("", "-", "--") for key in PRICE):
        raise ValueError("no_trade_missing_ohlc_placeholder")
    try:
        numbers = {key: float(str(raw[key]).replace(",", "").strip()) for key in NUMERIC}
    except (ValueError, TypeError, KeyError) as error:
        raise ValueError("invalid_numeric") from error
    validate_numeric(numbers)
    return {"contract_epoch_id": manifest["contract_epoch_id"], "vt_symbol": vt,
            "product": manifest["product"], "date": day.isoformat(), **numbers,
            "source_year": source_year, "raw_member": raw_member, "row": raw.get("row", ""),
            "raw_sheet": raw.get("raw_sheet", "")}


def resolve_duplicates(records: list[dict]) -> tuple[list[dict], list[dict], dict]:
    groups = defaultdict(list)
    for row in records:
        groups[(row["contract_epoch_id"], row["date"])].append(row)
    accepted, rejected = [], []
    info = {"identical_duplicate_extra_rows": 0, "conflicting_duplicate_keys": 0, "conflicting_duplicate_rows": 0}
    for key in sorted(groups):
        group = groups[key]
        versions = {tuple(row[field] for field in NUMERIC) for row in group}
        if len(versions) == 1:
            accepted.append(group[0])
            info["identical_duplicate_extra_rows"] += len(group) - 1
        else:
            info["conflicting_duplicate_keys"] += 1
            info["conflicting_duplicate_rows"] += len(group)
            rejected.extend({**row, "reason": "conflicting_duplicate"} for row in group)
    return accepted, rejected, info


def compare_existing(official: list[dict], existing: list[dict]) -> tuple[list[dict], list[dict], dict]:
    groups = defaultdict(list)
    for row in existing:
        groups[(row["contract_epoch_id"], row["date"])].append(row)
    annotated, differences = [], []
    info = {"overlap_days": 0, "exact_match_days": 0, "different_days": 0, "existing_duplicate_overlap_days": 0,
            "different_field_counts": {key: 0 for key in NUMERIC}, "max_abs_field_difference": {key: 0.0 for key in NUMERIC}}
    for row in official:
        key = (row["contract_epoch_id"], row["date"])
        old = groups.get(key, [])
        item = dict(row)
        item.update(overlap_status="new_date", matches_existing_ohlc="not_applicable",
                    matches_existing_volume="not_applicable", matches_existing_open_interest="not_applicable", matches_existing_all="not_applicable")
        if old:
            info["overlap_days"] += 1
            duplicate = len(old) != 1
            info["existing_duplicate_overlap_days"] += duplicate
            all_same = True
            for previous in old:
                unequal = [field for field in NUMERIC if previous[field] is None or
                           not math.isfinite(float(previous[field])) or abs(row[field] - previous[field]) > 1e-8]
                for field in NUMERIC:
                    if previous[field] is not None and math.isfinite(float(previous[field])):
                        info["max_abs_field_difference"][field] = max(info["max_abs_field_difference"][field], abs(row[field] - previous[field]))
                if unequal or duplicate:
                    all_same = False
                    for field in unequal:
                        info["different_field_counts"][field] += 1
                    entry = {"contract_epoch_id": row["contract_epoch_id"], "vt_symbol": row["vt_symbol"], "date": row["date"],
                             "different_fields": ",".join(unequal) if unequal else "existing_duplicate_day",
                             "existing_datetime": previous.get("existing_datetime", previous["date"])}
                    for field in NUMERIC:
                        entry[f"official_{field}"] = row[field]
                        entry[f"existing_{field}"] = previous[field]
                    differences.append(entry)
            if duplicate:
                item.update(overlap_status="duplicate_existing", matches_existing_ohlc=False,
                            matches_existing_volume=False, matches_existing_open_interest=False, matches_existing_all=False)
            else:
                previous = old[0]
                equal = {field: previous[field] is not None and math.isfinite(float(previous[field])) and
                         abs(row[field] - previous[field]) <= 1e-8 for field in NUMERIC}
                item.update(overlap_status="exact_match" if all_same else "different_existing",
                            matches_existing_ohlc=all(equal[field] for field in PRICE),
                            matches_existing_volume=equal["volume"], matches_existing_open_interest=equal["open_interest"],
                            matches_existing_all=all_same)
            info["exact_match_days"] += all_same
            info["different_days"] += not all_same
        annotated.append(item)
    return annotated, differences, info


def unit_diagnostics(official: list[dict], differences: list[dict]) -> dict:
    """Describe source-unit and OI-clock identities; do not transform any row."""
    groups = defaultdict(list)
    for row in official:
        groups[row["contract_epoch_id"]].append(row)
    previous = {}
    for epoch, rows in groups.items():
        ordered = sorted(rows, key=lambda row: row["date"])
        for earlier, current in zip(ordered, ordered[1:]):
            previous[(epoch, current["date"])] = earlier

    def ratio(numerator, denominator):
        if numerator is None or denominator is None:
            return "missing"
        if not all(math.isfinite(float(value)) for value in (numerator, denominator)):
            return "nonfinite"
        if denominator == 0:
            return "both_zero" if numerator == 0 else "existing_zero"
        return str(Fraction(str(numerator)) / Fraction(str(denominator)))

    by_group = {}
    exact_groups = Counter()
    classes, exceptions, evidence = Counter(), [], []
    for row in differences:
        earlier = previous.get((row["contract_epoch_id"], row["date"]))
        volume_ratio = ratio(row["official_volume"], row["existing_volume"])
        oi_ratio = ratio(row["official_open_interest"], row["existing_open_interest"])
        lag_ratio = ratio(earlier["open_interest"], row["existing_open_interest"]) if earlier else "no_previous_official_row"
        identity = volume_ratio == "2" and lag_ratio == "2"
        label = "volume_2x_and_previous_close_oi_2x_existing" if identity else "other_difference"
        classes[label] += 1
        product = row["vt_symbol"].split(".", 1)[0].rstrip("0123456789") + ".SHFE"
        group_key = (row["date"][:4], product)
        item = by_group.setdefault(group_key, {"year": group_key[0], "product": product, "difference_days": 0,
                                               "volume_ratio_counts": Counter(), "same_day_oi_ratio_counts": Counter(),
                                               "previous_close_oi_ratio_counts": Counter(), "classification_counts": Counter()})
        item["difference_days"] += 1
        item["volume_ratio_counts"][volume_ratio] += 1
        item["same_day_oi_ratio_counts"][oi_ratio] += 1
        item["previous_close_oi_ratio_counts"][lag_ratio] += 1
        item["classification_counts"][label] += 1
        exact_groups[(*group_key, volume_ratio, oi_ratio, lag_ratio, label)] += 1
        example = {"contract_epoch_id": row["contract_epoch_id"], "date": row["date"], "classification": label,
                   "official_volume": row["official_volume"], "existing_volume": row["existing_volume"],
                   "official_close_oi": row["official_open_interest"], "existing_oi": row["existing_open_interest"],
                   "previous_official_date": earlier["date"] if earlier else None,
                   "previous_official_close_oi": earlier["open_interest"] if earlier else None}
        if identity and len(evidence) < 12:
            evidence.append(example)
        if not identity:
            exceptions.append(example)
    return {
        "classification_counts": dict(classes), "difference_days": len(differences),
        "by_year_product": [{key: dict(value) if isinstance(value, Counter) else value for key, value in by_group[k].items()}
                            for k in sorted(by_group)],
        "by_year_product_exact_ratios": [dict(year=key[0], product=key[1], volume_ratio=key[2], same_day_oi_ratio=key[3],
                                              previous_official_close_oi_to_existing_oi_ratio=key[4], classification=key[5], count=count)
                                        for key, count in sorted(exact_groups.items())],
        "coupled_identity_examples": evidence, "unexplained_difference_rows": exceptions,
        "interpretation": "The coupled identity is evidence consistent with one-sided volume and beginning-of-day OI in the existing rows; the ingest-field choice itself has not been proved. Same-day OI cannot be fixed by a constant scale.",
        "transforms_applied": False, "integration_decision": "retain raw units; preserve both values; await explicit semantics contract and independent review",
    }


def valid_existing_dates(existing: list[dict]) -> set[str]:
    groups = defaultdict(list)
    for row in existing:
        groups[row["date"]].append(row)
    valid = set()
    for day, rows in groups.items():
        if len(rows) != 1:
            continue
        try:
            validate_numeric(rows[0])
            valid.add(day)
        except (ValueError, TypeError):
            pass
    return valid


def contract_report(manifest: dict, official: list[dict], existing: list[dict], main_dates: set[str]) -> dict:
    annotated, _, overlap = compare_existing(official, existing)
    existing_dates, official_dates = valid_existing_dates(existing), {row["date"] for row in official}
    shared_conflicts = {row["date"] for row in annotated if row["overlap_status"] in ("different_existing", "duplicate_existing")}
    union = existing_dates | official_dates
    conservative = union - shared_conflicts
    first = manifest["first_main_date"]
    scope_first = manifest["first_main_date_in_scope"]
    before = lambda dates: sum(day < first for day in dates)
    through = lambda dates: sum(day <= first for day in dates)
    scope_through = lambda dates: sum("2015-01-01" <= day <= scope_first for day in dates)
    return {
        "contract_epoch_id": manifest["contract_epoch_id"], "vt_symbol": manifest["vt_symbol"], "product": manifest["product"],
        "delivery_yyyymm": manifest["contract_yyyymm"], "list_date": "unknown", "delist_date": "unknown",
        "full_lifetime_coverage_claim": False, "first_main_date": first, "first_main_date_in_scope": scope_first,
        "existing_raw_rows": len(existing), "existing_valid_unique_days": len(existing_dates),
        "official_valid_unique_days": len(official_dates), "official_first_date": min(official_dates) if official_dates else None,
        "official_last_date": max(official_dates) if official_dates else None,
        "existing_valid_pre_main_days": before(existing_dates), "existing_valid_through_first_main_days": through(existing_dates),
        "official_pre_main_days": before(official_dates), "official_new_pre_main_days": before(official_dates - existing_dates),
        "official_new_unique_days": len(official_dates - existing_dates), "union_valid_pre_main_days": before(union),
        "union_valid_through_first_main_days": through(union), "AM120_ready_before": through(existing_dates) >= 120,
        "AM120_coverage_ready_after": through(union) >= 120,
        "union_nonconflicting_through_first_main_days": through(conservative), "AM120_nonconflicting_ready_after": through(conservative) >= 120,
        "source_scope_AM120_ready_before": scope_through(existing_dates) >= 120,
        "source_scope_AM120_coverage_ready_after": scope_through(union) >= 120,
        "source_scope_AM120_nonconflicting_ready_after": scope_through(conservative) >= 120,
        "existing_scope_through_first_main_days": scope_through(existing_dates), "union_scope_through_first_main_days": scope_through(union),
        "quarantined_overlap_dates": sorted(shared_conflicts), "main_days_in_scope_expected": len(main_dates),
        "main_days_in_scope_existing_covered": len(main_dates & existing_dates), "main_days_in_scope_official_covered": len(main_dates & official_dates),
        "main_days_in_scope_union_covered": len(main_dates & union), "main_days_in_scope_nonconflicting_covered": len(main_dates & conservative),
        "main_days_in_scope_missing_before": sorted(main_dates - existing_dates), "main_days_in_scope_missing_after": sorted(main_dates - union),
        "main_days_in_scope_quarantined_after": sorted(main_dates & shared_conflicts), **overlap,
    }


def read_existing(database: Path, manifests: list[dict]) -> tuple[dict, dict]:
    """Only same date-bound real epoch rows from a read-only SQLite snapshot."""
    groups, info = {}, {"out_of_epoch_or_invalid_date_rows_excluded": 0, "read_only": True, "query_only": True}
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    connection.execute("BEGIN")
    try:
        for manifest in manifests:
            symbol = manifest["vt_symbol"].rsplit(".", 1)[0]
            records = []
            for row in connection.execute(
                "SELECT datetime,open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata "
                "WHERE symbol=? AND exchange='SHFE' AND interval='d' ORDER BY datetime", (symbol,)):
                day = row["datetime"][:10]
                try:
                    identity = contract_identity(manifest["vt_symbol"], day)
                    if identity["contract_epoch_id"] != manifest["contract_epoch_id"]:
                        raise ValueError("different_epoch")
                    if day[:7].replace("-", "") > manifest["contract_yyyymm"]:
                        raise ValueError("after_delivery_month")
                except ValueError:
                    info["out_of_epoch_or_invalid_date_rows_excluded"] += 1
                    continue
                records.append({"contract_epoch_id": manifest["contract_epoch_id"], "vt_symbol": manifest["vt_symbol"],
                                "product": manifest["product"], "date": day, "existing_datetime": row["datetime"],
                                **{field: row[f"{field}_price"] if field in PRICE else row[field] for field in NUMERIC}})
            groups[manifest["contract_epoch_id"]] = records
    finally:
        connection.close()
    return groups, info


def write_csv(path: Path, rows: list[dict], fields) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    manifests_all = list(csv.DictReader((BASE / "manifest_contracts.csv").open(encoding="utf-8-sig", newline="")))
    manifests = [row for row in manifests_all if row["exchange"] == "SHFE"]
    if dict(Counter(row["product"] for row in manifests)) != PRODUCT_COUNTS:
        raise RuntimeError("SHFE_manifest_scope_changed_review_required")
    epochs = {row["vt_symbol"]: row for row in manifests}
    if len(epochs) != len(manifests):
        raise RuntimeError("same_symbol_multiple_epochs_need_explicit_resolution")
    archives = [OUTPUT / "raw_years" / f"shfe_futures_{year}.zip" for year in YEARS]
    missing = [str(path) for path in archives if not path.exists()]
    if missing:
        raise RuntimeError(f"annual_archives_not_ready:{missing}")
    source_inputs = [BASE / "manifest_contracts.csv", BASE / "manifest_main_dates.csv", BASE / "shfe_archive_index_selection.json",
                     OUTPUT / "year_download_status.json", Path(__file__).resolve(), Path(__file__).with_name("test_stage264_normalize_shfe_years.py")]
    inputs_before = {str(path.relative_to(ROOT)): file_sha(path) for path in source_inputs}
    database_before = DATABASE.stat()
    records, rejected, source_reports = [], [], []
    outside = 0
    for year, path in zip(YEARS, archives):
        source = {"source_year": year, "archive": str(path.relative_to(LINE)), "bytes": path.stat().st_size,
                  "sha256": file_sha(path), "members": []}
        with ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError(f"archive_crc_failed:{path.name}")
            if len([member for member in archive.infolist() if not member.is_dir()]) != (12 if year == 2019 else 1):
                raise RuntimeError(f"annual_member_count_changed:{year}")
            for member in archive.infolist():
                if member.is_dir():
                    continue
                if not member.filename.lower().endswith(".xls"):
                    raise RuntimeError(f"unexpected_archive_member:{path.name}:{member.filename}")
                payload = archive.read(member)
                book = xlrd.open_workbook(file_contents=payload, on_demand=True)
                member_info = {"raw_member": member.filename, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                               "sheets": [], "xls_datemode": book.datemode}
                try:
                    for sheet in book.sheets():
                        raw_rows, details = sheet_records(sheet.row_values(index) for index in range(sheet.nrows))
                        notes = []
                        for index in range(max(0, sheet.nrows-16), sheet.nrows):
                            note = " ".join(text_value(value) for value in sheet.row_values(index) if text_value(value))
                            if any(word in note for word in ("单边", "双边", "two-sided", "single-sided")):
                                notes.append({"row": index+1, "text": note})
                        member_info["sheets"].append({"name": sheet.name, "rows": sheet.nrows, "cols": sheet.ncols,
                                                       "unit_footnotes": notes, **details})
                        for raw in raw_rows:
                            raw["raw_sheet"] = sheet.name
                            vt = f'{text_value(raw["instrument"]).lower()}.SHFE'
                            if vt not in epochs:
                                outside += 1
                                continue
                            try:
                                records.append(normalize_record(raw, year, member.filename, epochs))
                            except ValueError as error:
                                rejected.append({"contract_epoch_id": epochs[vt]["contract_epoch_id"], "vt_symbol": vt,
                                                 "product": epochs[vt]["product"], "source_year": year,
                                                 "raw_member": member.filename, "raw_sheet": sheet.name, "row": raw["row"],
                                                 "date": raw["date"], "reason": str(error),
                                                 "raw_record_json": json.dumps(raw, ensure_ascii=False, allow_nan=True)})
                finally:
                    book.release_resources()
                source["members"].append(member_info)
        source_reports.append(source)
        print(json.dumps({"year": year, "valid_candidate_rows_cumulative": len(records), "rejected_rows_cumulative": len(rejected)}, ensure_ascii=False), flush=True)
    accepted, duplicate_rejections, duplicate_info = resolve_duplicates(records)
    rejected.extend({**row, "raw_record_json": json.dumps(row, ensure_ascii=False)} for row in duplicate_rejections)
    existing_groups, database_info = read_existing(DATABASE, manifests)
    official_groups, main_dates = defaultdict(list), defaultdict(set)
    for row in accepted:
        official_groups[row["contract_epoch_id"]].append(row)
    with (BASE / "manifest_main_dates.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row["contract_epoch_id"] in existing_groups:
                main_dates[row["contract_epoch_id"]].add(row["date"])
    contracts, normalized, differences = [], [], []
    for manifest in manifests:
        epoch = manifest["contract_epoch_id"]
        official = official_groups[epoch]
        existing = existing_groups[epoch]
        annotated, diffs, _ = compare_existing(official, existing)
        normalized.extend(annotated)
        differences.extend(diffs)
        contracts.append(contract_report(manifest, official, existing, main_dates[epoch]))
    inputs_after = {str(path.relative_to(ROOT)): file_sha(path) for path in source_inputs}
    database_after = DATABASE.stat()
    if inputs_before != inputs_after or (database_before.st_size, database_before.st_mtime_ns) != (database_after.st_size, database_after.st_mtime_ns):
        raise RuntimeError("source_inputs_changed_during_normalization")
    for source, path in zip(source_reports, archives):
        if file_sha(path) != source["sha256"]:
            raise RuntimeError("raw_archive_changed_during_normalization")
    downloads = json.loads((OUTPUT / "year_download_status.json").read_text())
    for source in source_reports:
        download = next(item for item in downloads["years"] if item["year"] == source["source_year"])
        if download["status"] != "downloaded" or download["sha256"] != source["sha256"]:
            raise RuntimeError("raw_archive_does_not_match_download_receipt")
    normalized.sort(key=lambda row: (row["contract_epoch_id"], row["date"]))
    differences.sort(key=lambda row: (row["contract_epoch_id"], row["date"], row["existing_datetime"]))
    write_csv(OUTPUT / "normalized_bars.csv", normalized, (*BASE_FIELDS, *FLAGS))
    reject_fields = ("contract_epoch_id", "vt_symbol", "product", "date", "source_year", "raw_member", "raw_sheet", "row", "reason", "raw_record_json")
    write_csv(OUTPUT / "rejected_rows.csv", rejected, reject_fields)
    difference_fields = ("contract_epoch_id", "vt_symbol", "date", "existing_datetime", "different_fields",
                         *(field for key in NUMERIC for field in (f"official_{key}", f"existing_{key}")))
    write_csv(OUTPUT / "overlap_differences.csv", differences, difference_fields)
    unit_audit = unit_diagnostics(normalized, differences)
    unit_audit.update(generated_at=stamp(), source_footnotes=[
        {"year": source["source_year"], "raw_member": member["raw_member"], "sheet": sheet["name"], "footnotes": sheet["unit_footnotes"]}
        for source in source_reports for member in source["members"] for sheet in member["sheets"]])
    (OUTPUT / "unit_semantics_audit.json").write_text(json.dumps(unit_audit, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    ready_before = sum(row["AM120_ready_before"] for row in contracts)
    summary = {
        "contract_epochs": len(manifests), "products": PRODUCT_COUNTS, "source_valid_rows_before_deduplication": len(records),
        "normalized_valid_unique_rows": len(normalized), "rejected_raw_rows": len(rejected),
        "rejection_reasons": dict(Counter(row["reason"] for row in rejected)), "outside_manifest_rows_ignored": outside,
        **duplicate_info, "overlap_days": sum(row["overlap_days"] for row in contracts),
        "exact_match_days": sum(row["exact_match_days"] for row in contracts), "different_days": sum(row["different_days"] for row in contracts),
        "different_field_counts": {key: sum(row["different_field_counts"][key] for row in contracts) for key in NUMERIC},
        "official_new_unique_days": sum(row["official_new_unique_days"] for row in contracts),
        "official_new_pre_main_days": sum(row["official_new_pre_main_days"] for row in contracts),
        "AM120_ready_before": ready_before, "AM120_coverage_ready_after": sum(row["AM120_coverage_ready_after"] for row in contracts),
        "AM120_nonconflicting_ready_after": sum(row["AM120_nonconflicting_ready_after"] for row in contracts),
        "source_scope_AM120_ready_before": sum(row["source_scope_AM120_ready_before"] for row in contracts),
        "source_scope_AM120_coverage_ready_after": sum(row["source_scope_AM120_coverage_ready_after"] for row in contracts),
        "source_scope_AM120_nonconflicting_ready_after": sum(row["source_scope_AM120_nonconflicting_ready_after"] for row in contracts),
        "main_days_in_scope_expected": sum(row["main_days_in_scope_expected"] for row in contracts),
        "main_days_in_scope_existing_covered": sum(row["main_days_in_scope_existing_covered"] for row in contracts),
        "main_days_in_scope_union_covered": sum(row["main_days_in_scope_union_covered"] for row in contracts),
        "main_days_in_scope_nonconflicting_covered": sum(row["main_days_in_scope_nonconflicting_covered"] for row in contracts),
        "unknown_listing_dates": len(manifests), "all_lifetime_metadata_unknown": True,
    }
    report = {
        "generated_at": stamp(), "line_id": "futures_trend_rollover_shape_same_volume", "stage": "Stage264",
        "status": "isolated_official_candidate_with_quarantined_differences" if differences else "isolated_official_candidate_pending_independent_review",
        "official_dataset_status": "normalized_source_quality_checks_pass_pending_independent_review",
        "existing_database_comparison_status": "2019_subset_differs_in_volume_units_and_OI_clock_plus_two_small_quantity_discrepancies",
        "source": "SHFE official annual futures XLS archives", "source_years": list(YEARS), "xlrd_version": xlrd.__version__,
        "source_index": str((BASE / "shfe_archive_index_selection.json").relative_to(LINE)),
        "scope": "Only manifest-bound SHFE real contract epochs; annual 2014-2019 data; no continuous contracts",
        "price_comparison_absolute_tolerance": 1e-8,
        "units": {"volume": "hands; pre-2020 source footnote states two-sided; unconverted",
                  "open_interest": "end-of-day held positions (持仓量/OPENINTEREST), hands, two-sided; not daily change; unconverted"},
        "coverage_semantics": "strict pre-main and through-first-main-close counts are separate; later bars never warm earlier dates; scoped counters preload 2015-01-01",
        "pit_limit": "Official annual packages are ex-post archives linked under 202401 and may contain revisions; date cutoffs do not prove contemporaneous 2014-2019 as-of publication bytes.",
        "conflict_policy": "conflicting source duplicates reject every version; official-vs-database discrepancies retain both values, flag candidate rows and quarantine dates in conservative coverage",
        "normalization_is_not_accepted_integration": True, "independent_review_status": "pending_other_agent",
        "inputs_sha256": inputs_before, "source_archives": source_reports, "database_read": database_info,
        "summary": summary, "contracts": contracts, "unit_diagnostics": {key: value for key, value in unit_audit.items() if key not in ("by_year_product_exact_ratios", "source_footnotes")},
        "safety": {"network_requests": 0, "database_writes": False, "model_training_runs": 0, "backtest_runs": 0,
                   "official_source_changes": False, "prior_stage_outputs_overwritten": False, "listing_dates_invented": False},
    }
    report["output_files"] = {name: {"sha256": file_sha(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size}
                              for name in ("normalized_bars.csv", "rejected_rows.csv", "overlap_differences.csv", "unit_semantics_audit.json")}
    (OUTPUT / "quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
