"""Independent, read-only Stage266 daily-data validation.

Never imports the cleaner. Source/calendar/quantity checks are bounded by the
frozen contract, not a claim that every exchange-published historical row is true.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import time


EXCHANGES = {"CFFEX", "CZCE", "DCE", "GFEX", "INE", "SHFE"}
PRICES = ("open", "high", "low", "close")
LINE = Path(__file__).resolve().parents[1]
BASE = LINE / "outputs/stage266_independent_validation"


def finite_number(value):
    if value is None or str(value).strip().lower() in {"", "null", "none", "nan", "-", "--"}:
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) else None


def equal(a, b):
    a, b = finite_number(a), finite_number(b)
    return a is not None and b is not None and math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-8)


def semantic_violations(row, *, cutoff):
    """Check selected rows without reproducing the cleaner's selection code."""
    errors = []
    day = str(row.get("trade_date", ""))
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            raise ValueError("not_iso_day")
        parsed = date.fromisoformat(day)
        if parsed > date.fromisoformat(cutoff):
            errors.append("after_cutoff")
    except ValueError:
        errors.append("invalid_trade_date")
    if row.get("exchange") not in EXCHANGES:
        errors.append("unknown_exchange")
    canonical = f"{row.get('exchange')}.{row.get('product')}.{row.get('contract_yyyymm')}"
    if row.get("contract_epoch_id") != canonical:
        errors.append("contract_epoch_not_canonical_identity")
    delivery = str(row.get("contract_yyyymm", ""))
    native_symbol = str(row.get("source_symbol", ""))
    if "." in native_symbol:
        prefix, native_symbol = native_symbol.split(".", 1)
        if prefix != row.get("exchange"):
            errors.append("source_symbol_exchange_mismatch")
    match = re.fullmatch(r"([A-Za-z]+)(\d{3,4})(F?)", native_symbol)
    if not re.fullmatch(r"\d{6}", delivery) or not 1 <= int(delivery[-2:] or 0) <= 12:
        errors.append("invalid_contract_month")
    elif not match or match.group(2) != delivery[-len(match.group(2)):]:
        errors.append("symbol_delivery_month_mismatch")
    elif match.group(1).upper() != str(row.get("product", "")).upper().removesuffix("_F") or bool(match.group(3)) != str(row.get("product", "")).upper().endswith("_F"):
        errors.append("symbol_product_or_F_mismatch")
    nums = {k: finite_number(row.get(k)) for k in (*PRICES, "volume", "close_oi", "open_interest")}
    if any(nums[k] is None or nums[k] <= 0 for k in PRICES):
        errors.append("nonpositive_or_nonfinite_ohlc")
    elif not nums["low"] <= min(nums["open"], nums["close"]) <= max(nums["open"], nums["close"]) <= nums["high"]:
        errors.append("invalid_ohlc_geometry")
    if nums["volume"] is None or nums["volume"] <= 0:
        errors.append("nonpositive_volume_in_accepted")
    if nums["close_oi"] is None or nums["close_oi"] < 0:
        errors.append("invalid_close_oi")
    if not equal(nums["open_interest"], nums["close_oi"]):
        errors.append("open_interest_not_close_alias")
    for actual, native, factor_name in (("volume", "native_volume", "volume_factor"), ("close_oi", "native_close_oi", "oi_factor")):
        raw, factor = finite_number(row.get(native)), finite_number(row.get(factor_name))
        if raw is None or raw < 0 or factor is None or factor <= 0 or not equal(row.get(actual), raw * factor):
            errors.append("volume_factor_mismatch" if actual == "volume" else "close_oi_factor_mismatch")
    opening, native_opening = finite_number(row.get("open_oi")), finite_number(row.get("native_open_oi"))
    status = row.get("open_oi_status")
    if status == "missing_not_imputed":
        if row.get("open_oi") is not None or row.get("native_open_oi") is not None:
            errors.append("missing_open_oi_was_imputed")
    elif status == "source_observed":
        if native_opening is None:
            errors.append("observed_open_oi_missing_native")
        factor = finite_number(row.get("oi_factor"))
        if opening is None or native_opening is None or min(opening, native_opening) < 0 or factor is None or not equal(opening, native_opening * factor):
            errors.append("open_oi_factor_mismatch")
    else:
        errors.append("unknown_open_oi_status")
    if row.get("quality_status") != "accepted":
        errors.append("selected_nonaccepted_quality")
    for flag in ("train_eligible", "legacy108_row_usable"):
        if row.get(flag) not in (0, 1, False, True):
            errors.append("invalid_" + flag + "_flag")
    return errors


def source_violations(row, raw, *, family, close_field, open_field=None):
    errors = []
    if close_field == "open_oi":
        errors.append("forbidden_open_oi_as_close_source")
    if "tq" in str(family).lower() and close_field != "close_oi":
        errors.append("TQ_close_oi_field_must_be_explicit_close_oi")
    for field in PRICES:
        if not equal(row.get(field), raw.get(field)):
            errors.append("source_" + field + "_mismatch")
    if not equal(row.get("native_volume"), raw.get("volume")):
        errors.append("source_native_volume_mismatch")
    if not equal(row.get("native_close_oi"), raw.get(close_field)):
        errors.append("source_native_close_oi_mismatch")
    actual_open = row.get("native_open_oi")
    source_open = finite_number(raw.get(open_field)) if open_field else None
    if source_open is None:
        if actual_open is not None or row.get("open_oi_status") != "missing_not_imputed":
            errors.append("source_missing_open_oi_imputed")
    elif not equal(actual_open, source_open) or row.get("open_oi_status") != "source_observed":
        errors.append("source_native_open_oi_mismatch")
    return errors


def expected_factors(units, family, exchange, day, raw):
    if family == "rqalpha":
        rules = [r for r in units["rqalpha"]["rules"] if exchange in r["exchanges"] and r["start"] <= day <= r["end"]]
        if len(rules) != 1:
            raise ValueError("no_unique_RQ_unit_rule")
        return float(rules[0]["volume_factor"]), float(rules[0]["close_oi_factor"])
    if family == "official":
        factor = units["official"]["accepted_regime_factors"].get(raw.get("unit_regime"))
        if factor is None:
            raise ValueError("unknown_official_unit_regime")
        return float(factor), float(factor)
    if family in ("old_tq", "recent_tq"):
        return float(units[family]["volume_factor"]), float(units[family]["close_oi_factor"])
    raise ValueError("unknown_source_family")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_load(path):
    return json.loads(Path(path).read_text())


def json_save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_only_connection(path):
    connection = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


class Findings:
    def __init__(self):
        self.counts = Counter()
        self.examples = defaultdict(list)

    def add(self, reason, context):
        self.counts[reason] += 1
        if len(self.examples[reason]) < 8:
            self.examples[reason].append(context)


class NativeReader:
    """Only source locators and raw columns, never cleaner functions."""
    def __init__(self):
        self.csv_source = None
        self.csv_rows = []
        self.h5_path = None
        self.h5 = None
        self.h5_key = None
        self.h5_rows = None

    def get(self, source, locator):
        path = Path(source["path"])
        if source["family"] == "rqalpha":
            if self.h5_path != str(path):
                import h5py
                if self.h5:
                    self.h5.close()
                self.h5 = h5py.File(path, "r")
                self.h5_path = str(path)
                self.h5_key = None
            key = locator["key"]
            if self.h5_key != key:
                self.h5_rows = self.h5[key][:]
                self.h5_key = key
            record = self.h5_rows[int(locator["row"])]
            raw = {k: float(record[k]) for k in record.dtype.names}
            raw["datetime"] = int(record["datetime"])
            raw["source_key"] = key
            return raw
        if self.csv_source != source["source_id"]:
            opener = gzip.open if path.suffix == ".gz" else Path.open
            with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
                self.csv_rows = list(csv.DictReader(f))
            self.csv_source = source["source_id"]
        index = int(locator["row"]) - 2
        if index < 0:
            raise ValueError("CSV_locator_before_first_data_row")
        return self.csv_rows[index]

    def close(self):
        if self.h5:
            self.h5.close()


def rq_identity(meta):
    symbol = meta["order_book_id"]
    match = re.fullmatch(r"[A-Za-z]+(\d{4})(F?)", symbol)
    if not match or not 1 <= int(match.group(1)[2:]) <= 12:
        raise ValueError("not_real_delivery_contract")
    reference_year = int(meta["maturity_date"][:4])
    yy = int(match.group(1)[:2])
    year = reference_year // 100 * 100 + yy
    if year < reference_year - 50:
        year += 100
    elif year > reference_year + 50:
        year -= 100
    return f"{meta['exchange']}.{meta['underlying_symbol'].upper()}.{year}{match.group(1)[2:]}"


def raw_day(raw, family):
    if family == "rqalpha":
        value = str(int(raw["datetime"]))
        if len(value) != 14 or value[8:] != "000000":
            raise ValueError("RQ_daily_nonmidnight_or_invalid_datetime")
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    value = str(raw.get("trade_date", raw.get("date", "")))
    return value[:10]


def csv_source_identity_violations(row, raw, family):
    errors = []
    if family == "official":
        for field in ("exchange", "product", "contract_yyyymm", "source_symbol"):
            if str(raw.get(field, "")).upper() != str(row[field]).upper():
                errors.append("official_source_" + field + "_mismatch")
    elif family == "recent_tq":
        expected = row["exchange"] + "." + row["source_symbol"].split(".")[-1]
        if raw.get("symbol", "").upper() != expected.upper():
            errors.append("TQ_source_symbol_mismatch")
        if str(raw.get("duration", "")).removesuffix(".0") != "86400":
            errors.append("TQ_source_not_daily")
    return errors


def check_export_csvs(db_path, output_dir):
    """Compare every exported row and field to its exact SQLite epoch/date."""
    inventory_path = db_path.parent / "csv_inventory.json"
    inventory = json_load(inventory_path)
    findings = Findings()
    counts = Counter()
    epochs = set()
    with read_only_connection(db_path) as db:
        for item in inventory:
            epoch = item["contract_epoch_id"]
            path = db_path.parent / item["path"]
            if epoch in epochs:
                findings.add("duplicate_inventory_epoch", epoch)
            epochs.add(epoch)
            if not path.is_file() or sha(path) != item["sha256"]:
                findings.add("CSV_export_hash_mismatch", str(path))
                continue
            with path.open(encoding="utf-8-sig", newline="") as f:
                csv_reader = csv.DictReader(f)
                required = {"trade_date", "datetime", *PRICES, "volume", "open_oi", "close_oi", "contract_epoch_id", "open_oi_status", "legacy108_row_usable", "source_id", "volume_factor", "oi_factor"}
                if set(csv_reader.fieldnames or []) != required:
                    findings.add("CSV_export_schema_mismatch", str(path))
                rows = list(csv_reader)
            native = [dict(r) for r in db.execute("SELECT * FROM daily_bars WHERE contract_epoch_id=? ORDER BY trade_date", (epoch,))]
            if len(rows) != len(native) or len(rows) != item["rows"]:
                findings.add("CSV_export_row_count_mismatch", epoch)
                continue
            observed_open = 0
            for row, expected in zip(rows, native):
                for field, value in row.items():
                    if field == "datetime":
                        good = value == expected["trade_date"] + " 00:00:00+08:00"
                    elif field == "trade_date":
                        good = value == expected[field]
                    elif field not in expected:
                        good = False
                    elif expected[field] is None:
                        good = value == ""
                    elif isinstance(expected[field], (int, float)):
                        good = equal(value, expected[field])
                    else:
                        good = value == str(expected[field])
                    counts["fields_compared"] += 1
                    if not good:
                        findings.add("CSV_export_field_mismatch", {"epoch": epoch, "day": row.get("trade_date"), "field": field, "value": value, "expected": expected.get(field)})
                counts["rows_compared"] += 1
                observed_open += expected["legacy108_row_usable"]
            if observed_open != item["legacy108_rows"]:
                findings.add("CSV_inventory_legacy_count_mismatch", epoch)
            counts["files_compared"] += 1
        selected_epochs = {r[0] for r in db.execute("SELECT DISTINCT contract_epoch_id FROM daily_bars")}
        if epochs != selected_epochs:
            findings.add("CSV_inventory_epoch_set_mismatch", {"missing": sorted(selected_epochs-epochs)[:8], "extra": sorted(epochs-selected_epochs)[:8]})
        if counts["rows_compared"] != db.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0]:
            findings.add("CSV_export_total_count_mismatch", counts["rows_compared"])
    result = {"status": "PASS" if not findings.counts else "FAIL", "inventory_sha256": sha(inventory_path), "counts": dict(counts), "findings": dict(findings.counts), "examples": dict(findings.examples)}
    json_save(output_dir / "csv_export_validation.json", result)
    return result


def check_excluded_conservation(db_path, output_dir):
    """Check recorded accounting, never reinterpret an excluded observation as a bar."""
    summary = json_load(db_path.parent / "cleaning_summary.json")
    path = db_path.parent / "excluded_observations.csv.gz"
    actual = defaultdict(Counter)
    findings = Findings()
    total = 0
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            actual[row["source_id"]][row["reason"]] += 1
            total += 1
    reconciled_raw, reconciled_accepted = 0, 0
    before_raw_counter = {}
    for source_id, stats in summary["source_stats"].items():
        accepted = stats.get("accepted_source_observations", 0)
        expected_reasons = {k: v for k, v in stats.items() if k not in {"raw_observations", "accepted_source_observations"}}
        # Price-conflict delta is documented separately after source gate accounting.
        recorded = {k: v for k, v in actual[source_id].items() if k != "cross_source_price_conflict"}
        if recorded != expected_reasons:
            findings.add("excluded_reason_accounting_mismatch", {"source_id": source_id, "actual": recorded, "expected": expected_reasons})
        if "raw_observations" not in stats:
            before_raw_counter[source_id] = dict(actual[source_id])
            continue
        if stats["raw_observations"] != accepted + sum(expected_reasons.values()):
            findings.add("source_raw_accepted_excluded_partition_mismatch", source_id)
        reconciled_raw += stats["raw_observations"]
        reconciled_accepted += accepted
    unknown = set(actual) - set(summary["source_stats"])
    if unknown:
        findings.add("excluded_unknown_source", sorted(unknown)[:8])
    result = {"status": "PASS" if not findings.counts else "FAIL", "sha256": sha(path), "excluded_observations": total,
              "source_raw_observations_partition_checked": reconciled_raw, "accepted_source_observations_before_priority_dedup": reconciled_accepted,
              "identity_rejections_before_raw_counter": before_raw_counter,
              "excluded_reasons": dict(sum(actual.values(), Counter())), "findings": dict(findings.counts), "examples": dict(findings.examples),
              "boundary": "Source observations overlap; accepted-source counts must not be added to unique selected rows. Accounting audit uses declared source gate totals, not independent enumeration of every rejected raw field."}
    json_save(output_dir / "excluded_conservation_validation.json", result)
    return result


def check_september_overlap(contract, output_dir):
    """Independently match actual 2026-09 daily dates, never short-symbol year guesses."""
    import h5py
    metadata = json_load(contract["metadata_path"])
    aliases = defaultdict(list)
    for meta in metadata:
        try:
            rq_identity(meta)
        except (ValueError, KeyError):
            continue
        aliases[(meta["exchange"], str(meta.get("trading_code", meta["order_book_id"])).upper())].append(meta["order_book_id"])
    counts, by_exchange = Counter(), defaultdict(Counter)
    differences = []
    with read_only_connection(contract["db_path"]) as db:
        sources = [dict(r) for r in db.execute("SELECT * FROM sources WHERE family='recent_tq'")]
        h5path = db.execute("SELECT path FROM sources WHERE family='rqalpha'").fetchone()[0]
    with h5py.File(h5path, "r") as h5:
        for source in sources:
            with Path(source["path"]).open(encoding="utf-8-sig", newline="") as f:
                tqrows = [(i, r) for i, r in enumerate(csv.DictReader(f), 2) if r.get("trade_date", "").startswith("2026-09-")]
            if not tqrows:
                continue
            symbol = source["source_id"].split(":", 1)[1]
            ex, leaf = symbol.split(".", 1)
            keys = aliases.get((ex, leaf.upper()), [])
            rqdays = defaultdict(list)
            for key in keys:
                if key not in h5:
                    continue
                for index, raw in enumerate(h5[key][:]):
                    day = str(int(raw["datetime"]))[:8]
                    if day.startswith("202609"):
                        rqdays[day[:4]+"-"+day[4:6]+"-"+day[6:8]].append((key, index, raw))
            for index, tq in tqrows:
                counts["TQ_September_observations"] += 1
                matches = rqdays.get(tq["trade_date"], [])
                if len(matches) != 1:
                    counts["no_unique_RQ_same_contract_date"] += 1
                    continue
                key, rqrow, rq = matches[0]
                if not ((finite_number(tq["volume"]) or 0) > 0 and float(rq["volume"]) > 0):
                    counts["not_both_positive_volume"] += 1
                    continue
                counts["both_traded"] += 1
                by_exchange[ex]["both_traded"] += 1
                same_price = all(equal(tq[p], rq[p]) for p in PRICES)
                for label, same in (("OHLC_equal", same_price), ("volume_equal", equal(tq["volume"], rq["volume"])),
                                    ("close_oi_equal", equal(tq["close_oi"], rq["open_interest"])), ("open_oi_equal_close_oi", equal(tq["open_oi"], rq["open_interest"]))):
                    counts[label] += same
                    by_exchange[ex][label] += same
                if not same_price:
                    differences.append({"symbol": symbol, "date": tq["trade_date"], "TQ_source": source["path"], "TQ_row": index, "RQ_key": key, "RQ_row": rqrow,
                                        **{"TQ_"+p: float(tq[p]) for p in PRICES}, **{"RQ_"+p: float(rq[p]) for p in PRICES}})
    result = {"status": "EVIDENCE_RECOMPUTED", "counts": dict(counts), "by_exchange": {k: dict(v) for k, v in by_exchange.items()},
              "price_disagreements": len(differences), "boundary": "Direct raw-source overlap evidence; discrepant OHLC has no truth winner. Open OI differs by clock and cannot replace close OI."}
    json_save(output_dir / "september_TQ_RQ_overlap.json", result)
    if differences:
        with (output_dir / "september_TQ_RQ_price_differences.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(differences[0])); writer.writeheader(); writer.writerows(differences)
    return result


def validate_store(contract_path, output_dir):
    started = time.monotonic()
    contract = json_load(contract_path)
    db_path = Path(contract["db_path"])
    if not db_path.is_file():
        raise ValueError("final_SQLite_not_frozen_or_missing")
    output_dir.mkdir(parents=True, exist_ok=True)
    findings = Findings()
    inputs = {"contract": {"path": str(contract_path), "sha256": sha(contract_path)},
              "database": {"path": str(db_path), "sha256": sha(db_path), "bytes": db_path.stat().st_size}}
    units = json_load(contract["unit_contract_path"])
    if sha(contract["unit_contract_path"]) != contract["unit_contract_sha256"] or not units.get("cleaner_rule_approved"):
        raise ValueError("unit_contract_unapproved_or_SHA_mismatch")
    inputs["unit_contract"] = {"path": contract["unit_contract_path"], "sha256": contract["unit_contract_sha256"]}
    if not contract.get("finalized") or inputs["database"]["sha256"] != contract.get("final_database_sha256"):
        raise ValueError("database_not_finalized_or_SHA_mismatch")
    for label in ("calendar", "metadata", "quantity_conflict", "price_conflict"):
        path, expected = contract[label + "_path"], contract[label + "_sha256"]
        if sha(path) != expected:
            raise ValueError(label + "_source_SHA_mismatch")
        inputs[label] = {"path": path, "sha256": expected}
    if units["canonical_quantity_unit"] != "single_sided_contracts" or contract["quantity_unit"] != "single_sided_contracts":
        raise ValueError("quantity_contract_mismatch")
    import numpy as np
    calendar = {str(int(x))[:4] + "-" + str(int(x))[4:6] + "-" + str(int(x))[6:8]
                for x in np.load(contract["calendar_path"], allow_pickle=False)}
    metadata = json_load(contract["metadata_path"])
    rq_meta = {m["order_book_id"]: m for m in metadata}
    quarantine = units["quarantine"]
    if sha(quarantine["path"]) != quarantine["sha256"]:
        raise ValueError("unit_quarantine_SHA_mismatch")
    with Path(quarantine["path"]).open(encoding="utf-8-sig", newline="") as f:
        conflict_keys = {(r["contract_epoch_id"], r["trade_date"]) for r in csv.DictReader(f)}
    if len(conflict_keys) != quarantine["row_count"]:
        raise ValueError("unit_quarantine_key_count_mismatch")
    with Path(contract["price_conflict_path"]).open(encoding="utf-8-sig", newline="") as f:
        price_conflict_keys = {(r["contract_epoch_id"], r["trade_date"]) for r in csv.DictReader(f)}
    if len(price_conflict_keys) != contract["price_conflict_count"] or price_conflict_keys & conflict_keys:
        raise ValueError("price_quarantine_count_or_disjointness_mismatch")
    db = read_only_connection(db_path)
    reader = NativeReader()
    counts = Counter()
    coverage = defaultdict(Counter)
    source_checks = []
    source_counts = Counter()
    source_open_clock = Counter()
    try:
        integrity = db.execute("PRAGMA integrity_check").fetchall()
        if [r[0] for r in integrity] != ["ok"]:
            findings.add("sqlite_integrity_error", [list(r) for r in integrity[:8]])
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            findings.add("sqlite_foreign_key_error", {})
        schema = {r["name"]: db.execute(f'PRAGMA table_info("{r["name"]}")').fetchall()
                  for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ("daily_bars", "sources", "contracts"):
            if table not in schema:
                raise ValueError("required_table_missing:" + table)
        required = {"contract_epoch_id", "exchange", "product", "source_symbol", "contract_yyyymm", "trade_date", *PRICES,
                    "volume", "close_oi", "open_oi", "open_interest", "source_id", "source_locator", "volume_factor", "oi_factor",
                    "native_volume", "native_close_oi", "native_open_oi", "open_oi_status", "quality_status", "legacy108_row_usable", "train_eligible", "priority"}
        if not required <= {r["name"] for r in schema["daily_bars"]}:
            raise ValueError("required_daily_bars_columns_missing")
        primary = [r["name"] for r in sorted(schema["daily_bars"], key=lambda r: r["pk"]) if r["pk"]]
        if primary != ["contract_epoch_id", "trade_date"]:
            findings.add("daily_bars_wrong_primary_key", primary)
        sources = {r["source_id"]: dict(r) for r in db.execute("SELECT * FROM sources")}
        contracts = {r["contract_epoch_id"]: dict(r) for r in db.execute("SELECT * FROM contracts")}
        for source in sources.values():
            path = Path(source["path"])
            good = path.is_file() and path.stat().st_size == source["bytes"] and sha(path) == source["sha256"]
            source_checks.append({"source_id": source["source_id"], "family": source["family"], "sha_and_bytes_match": good})
            if not good:
                findings.add("source_file_identity_mismatch", source["source_id"])
        total = db.execute("SELECT COUNT(*) FROM daily_bars").fetchone()[0]
        for native_row in db.execute("SELECT * FROM daily_bars ORDER BY source_id,contract_epoch_id,trade_date"):
            row = dict(native_row)
            context = {k: row[k] for k in ("contract_epoch_id", "trade_date", "source_id", "source_locator")}
            errors = semantic_violations(row, cutoff=contract["scope_end"])
            key = row["contract_epoch_id"], row["trade_date"]
            if row["trade_date"] < contract["scope_start"]:
                errors.append("before_scope_start")
            if row["trade_date"] not in calendar:
                errors.append("not_in_frozen_trading_calendar")
            if key in conflict_keys:
                errors.append("all_source_quantity_conflict_key_leaked")
            if key in price_conflict_keys:
                errors.append("all_source_price_conflict_key_leaked")
            meta = contracts.get(row["contract_epoch_id"])
            if not meta:
                errors.append("contract_metadata_reference_missing")
            else:
                for field in ("exchange", "product", "contract_yyyymm"):
                    if str(meta[field]) != str(row[field]):
                        errors.append("contract_" + field + "_mismatch")
                for field, boundary in (("listed_date", "before"), ("delisted_date", "after")):
                    value = meta.get(field)
                    if value and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) and value != "0000-00-00":
                        if (boundary == "before" and row["trade_date"] < value) or (boundary == "after" and row["trade_date"] > value):
                            errors.append(boundary + "_metadata_lifecycle")
                counts["metadata_status:" + str(meta["metadata_status"])] += 1
            source = sources.get(row["source_id"])
            if not source:
                errors.append("source_id_missing")
            else:
                family = source["family"]
                source_counts[family] += 1
                try:
                    locator = json.loads(row["source_locator"])
                    raw = reader.get(source, locator)
                    errors.extend(csv_source_identity_violations(row, raw, family))
                    if raw_day(raw, family) != row["trade_date"]:
                        errors.append("source_trade_date_mismatch")
                    close_field = "close_oi" if family in {"recent_tq", "old_tq"} else "open_interest"
                    open_field = "open_oi" if family in {"recent_tq", "old_tq"} else None
                    errors.extend(source_violations(row, raw, family=family, close_field=close_field, open_field=open_field))
                    vf, of = expected_factors(units, family, row["exchange"], row["trade_date"], raw)
                    if not equal(vf, row["volume_factor"]) or not equal(of, row["oi_factor"]):
                        errors.append("frozen_unit_factor_mismatch")
                    if family == "rqalpha":
                        if rq_identity(rq_meta[locator["key"]]) != row["contract_epoch_id"]:
                            errors.append("RQ_source_contract_epoch_mismatch")
                        if vf == .5 and (int(raw["volume"]) % 2 or int(raw["open_interest"]) % 2):
                            errors.append("double_side_even_guard_failed")
                    if family in {"recent_tq", "old_tq"}:
                        source_open_clock["true_close_oi_source_checked"] += 1
                        if not equal(raw.get("open_oi"), raw.get("close_oi")):
                            source_open_clock["different_open_close_oi_proof_rows"] += 1
                    counts["raw_source_rows_compared"] += 1
                except (ValueError, KeyError, IndexError, OSError) as error:
                    errors.append("raw_source_lookup_or_rule_error:" + type(error).__name__ + ":" + str(error))
                if row["priority"] != contract["source_priority"].get(family):
                    errors.append("source_priority_declaration_mismatch")
            observed_open = row["open_oi"] is not None and row["open_oi_status"] == "source_observed"
            if int(observed_open) != row["legacy108_row_usable"] or row["train_eligible"] != row["legacy108_row_usable"]:
                errors.append("row_field_eligibility_mismatch")
            for field in ("volume", "close_oi", "open_oi"):
                value = finite_number(row.get(field))
                if value is not None and not math.isclose(value, round(value), abs_tol=1e-8):
                    errors.append("canonical_fractional_contract_quantity:" + field)
            for error in errors:
                findings.add(error, context)
            counts["selected_rows"] += 1
            counts["rows_with_errors"] += bool(errors)
            counts["train_eligible_rows"] += row["train_eligible"]
            counts["legacy108_row_usable_rows"] += row["legacy108_row_usable"]
            counts["missing_open_oi_rows"] += not observed_open
            group = coverage[(row["exchange"], row["trade_date"][:4], row["product"])]
            group["selected_rows"] += 1
            group["train_eligible_rows"] += row["train_eligible"]
            if counts["selected_rows"] % 250000 == 0:
                print(json.dumps({"scanned": counts["selected_rows"], "total": total, "errors": counts["rows_with_errors"]}), flush=True)
        counts["source_count"] = len(sources)
        counts["contract_metadata_count"] = len(contracts)
        counts["selected_contract_count"] = db.execute("SELECT COUNT(DISTINCT contract_epoch_id) FROM daily_bars").fetchone()[0]
        counts["all_source_quantity_quarantine_keys_checked"] = len(conflict_keys)
        counts["all_source_price_quarantine_keys_checked"] = len(price_conflict_keys)
    finally:
        reader.close()
        db.close()
    before = json_load(contract["before_integrity_path"])
    protection = []
    repository = LINE.parents[2]
    for old in before["files"]:
        path = repository / old["path"]
        good = path.is_file() and sha(path) == old["sha256"] == old["expected_sha256"]
        protection.append({"path": str(path), "unchanged": good})
        if not good:
            findings.add("protected_primary_file_changed", old["path"])
    if sha(db_path) != inputs["database"]["sha256"]:
        findings.add("database_changed_during_readonly_validation", {})
    with (output_dir / "coverage_by_exchange_year_product.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["exchange", "year", "product", "selected_rows", "train_eligible_rows"])
        writer.writeheader()
        for key, stats in sorted(coverage.items()):
            writer.writerow({**dict(zip(("exchange", "year", "product"), key)), **stats})
    result = {"generated_at": datetime.now().astimezone().isoformat(),
              "status": "PASS_SELECTED_ROW_SOURCE_ACCURACY" if not findings.counts else "FAIL_INDEPENDENT_VALIDATION",
              "script_sha256": sha(__file__), "inputs": inputs, "counts": dict(counts),
              "source_family_counts": dict(source_counts), "TQ_open_close_clock_evidence": dict(source_open_clock),
              "source_file_checks": source_checks, "findings": dict(findings.counts), "finding_examples": dict(findings.examples),
              "protected_files": protection, "elapsed_seconds": round(time.monotonic() - started, 3),
              "limitations": ["Bounded source-contract accuracy, not proof of every exchange historical observation or listing.",
                              "train_eligible is row field compatibility, never a mature AM120/60 training sample.",
                              "Selected native source comparison is exhaustive; source priority completeness and excluded conservation are audited separately."],
              "main_database_writes": 0, "new_downloads": 0, "financial_backtests": 0, "model_fits": 0}
    json_save(output_dir / "independent_validation.json", result)
    print(json.dumps({"status": result["status"], "counts": dict(counts), "findings": dict(findings.counts)}, ensure_ascii=False), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=LINE / "outputs/stage266_clean_daily/contract.json")
    parser.add_argument("--output-dir", type=Path, default=BASE)
    parser.add_argument("--mode", choices=("selected", "aux", "all"), default="all")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = {}
    if args.mode in ("selected", "all"):
        reports["selected"] = validate_store(args.contract, args.output_dir)
    if args.mode in ("aux", "all"):
        contract = json_load(args.contract)
        reports["csv_exports"] = check_export_csvs(Path(contract["db_path"]), args.output_dir)
        reports["excluded_accounting"] = check_excluded_conservation(Path(contract["db_path"]), args.output_dir)
        reports["september_overlap"] = check_september_overlap(contract, args.output_dir)
        print(json.dumps({k: {"status": v["status"], "findings": v.get("findings"), "counts": v.get("counts")} for k, v in reports.items()}, ensure_ascii=False), flush=True)
    return 0 if all(not r.get("findings") for r in reports.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
