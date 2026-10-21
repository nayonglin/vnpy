"""139限定的一次可逆规范化；本脚本不授予日线资格或构建特征。"""
from __future__ import annotations
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import struct
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[5]
LINE = ROOT / "research/lines/futures_trend_triple_screen"
OUT = Path(__file__).resolve().parent
DB = ROOT / ".vntrader/database.db"
EXPECTED_DB = "273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54"
COLUMNS = ["date", "vt_symbol", "open", "high", "low", "close", "volume"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def status(path):
    if not path.exists():
        return dict(exists=False, bytes=0)
    s = path.stat()
    return dict(exists=True, bytes=s.st_size, mtime_ns=s.st_mtime_ns)


def bind(path, role, expected=None):
    data = path.read_bytes()
    h = sha(data)
    if expected is not None and h != expected:
        raise ValueError("bound_source_changed:" + str(path))
    return data, dict(path=str(path), role=role, sha256=h, bytes=len(data), expected_sha256=expected)


def real_contract(value):
    m = re.fullmatch(r"[A-Za-z]+(\d{3,4})\.[A-Z]+", value)
    if m is None or m[1] in {"888", "889", "999", "8888", "8899", "9999", "0000"}:
        raise ValueError("alias_or_invalid_contract:" + value)


def add_fingerprint(digest, day, contract, values):
    digest.update(day.encode() + b"\0" + contract.encode() + b"\0" + struct.pack("!5d", *values))


def main():
    started = OUT / "attempt_started.json"
    if started.exists():
        raise FileExistsError("one_export_attempt_already_exists")
    dump(started, dict(started_at=datetime.now().astimezone().isoformat(), export_attempt=1,
        feature_builds=0, financial_replays=0, provider_calls=0, qualification_granted=False))
    bindings = []
    inventory_data, b = bind(LINE / "outputs/stage138_ema_daily_input_inventory/inventory.json", "138_source_inventory", "01d8c0bd0aae3a15326fca2173d193da36d471cd96e5d5af0415cbac210d42a4")
    bindings.append(b)
    inventory = json.loads(inventory_data)
    auxiliary = {}
    for path, role, expected in [
        (LINE / "outputs/stage138_ema_daily_input_inventory/bounded_followup.json", "138_carry_and_zero_volume_evidence", "6de842800f3dc9e96d7886b6480ec5909c0dbbbbac1b430eb0bc866ae9c07a3a"),
        (LINE / "stages/20261018_0959_stage138_ema_daily_input_inventory.md", "138_inventory_record", "c9c239bea67668165497717e1a467637fd691587c1991a45f6c346987af42853"),
        (LINE / "stages/20261018_1002_stage139_ema_daily_source_acceptance_boundary.md", "139_root_acceptance_boundary", None),
        (Path(__file__).resolve(), "141_exporter", None),
    ]:
        data, b = bind(path, role, expected)
        bindings.append(b)
        auxiliary[role] = data
    selected = [
        ("outputs/stage099_pairwise_off_account/preflight/A_OFF.json", "accepted_A_OFF_preflight"),
        ("outputs/stage099_pairwise_off_account/A_OFF/run_context.json", "accepted_A_OFF_context"),
        ("outputs/stage099_pairwise_off_account/A_OFF/effective_parameters.json", "accepted_A_OFF_parameters"),
        ("outputs/stage001_first_screen/A0_attempt2/effective_parameters.json", "accepted_A0_parameters"),
        ("outputs/stage005_potential_signal_demand/global_engine_calendar.csv", "accepted_calendar"),
        ("outputs/stage027_independent_review/review_receipt.json", "027_limited_component_review"),
        ("outputs/stage027_ordered_features/input_manifest.json", "027_source_identity"),
        ("tools/stage027_build_ordered_features.py", "027_same_DB_scope_producer"),
    ]
    consumed = {}
    for name, role in selected:
        path = LINE / name
        data, b = bind(path, role, inventory["source_bindings"][str(path)]["sha256"])
        bindings.append(b)
        consumed[role] = data
    producer_names = ["import_tqsdk_all_futures_daily_to_db.py", "download_tqsdk_all_futures_daily_csv.py", "qmt_roll_intraday_execution.py"]
    for name in producer_names:
        path = ROOT / "examples/portfolio_backtesting" / name
        _, b = bind(path, "original_daily_producer_or_execution_spec", inventory["source_bindings"][str(path)]["sha256"])
        bindings.append(b)
    followup = json.loads(auxiliary["138_carry_and_zero_volume_evidence"])
    for p, expected in followup["carry_source_bindings"].items():
        _, b = bind(Path(p), "actual_native_carry_boundary", expected["sha256"])
        bindings.append(b)
    parameters = json.loads(consumed["accepted_A_OFF_parameters"])
    old_parameters = json.loads(consumed["accepted_A0_parameters"])
    if any(parameters[k] != old_parameters[k] for k in ("contract_sizes", "priceticks")):
        raise ValueError("accepted_metadata_mismatch")
    contracts = sorted(parameters["contract_sizes"])
    for contract in contracts:
        real_contract(contract)
    calendar = [r["date"] for r in csv.DictReader(consumed["accepted_calendar"].decode("utf-8-sig").splitlines())]
    if calendar != sorted(set(calendar)):
        raise ValueError("invalid_original_calendar")
    calendar_set = set(calendar)
    before = {name: status(Path(str(DB) + suffix)) for name, suffix in [("db", ""), ("wal", "-wal"), ("shm", "-shm")]}
    if before["wal"]["bytes"] or before["shm"]["bytes"]:
        raise ValueError("nonempty_database_sidecar")
    # 唯一一次DB路径读取；之后仅使用这些已hash的不可变bytes。
    database_bytes = DB.read_bytes()
    database_sha = sha(database_bytes)
    if database_sha != EXPECTED_DB:
        raise ValueError("frozen_database_changed")
    bindings.append(dict(path=str(DB), role="single_read_frozen_database_bytes", sha256=database_sha, bytes=len(database_bytes), expected_sha256=EXPECTED_DB))
    csv_path, keys_path = OUT / "daily.csv", OUT / "exact_keys.csv"
    source_digest, exported_digest = hashlib.sha256(), hashlib.sha256()
    source_keys, seen_days, seen_contracts = set(), set(), set()
    zero_volume, row_count = 0, 0
    query = ("SELECT datetime,symbol||'.'||exchange,open_price,high_price,low_price,close_price,volume FROM dbbardata WHERE interval='d' AND datetime>=? AND datetime<=? AND symbol||'.'||exchange IN (" + ",".join("?" for _ in contracts) + ") ORDER BY symbol||'.'||exchange,datetime")
    with sqlite3.connect(":memory:") as db:
        db.deserialize(database_bytes)
        db.execute("PRAGMA query_only=ON")
        if db.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise ValueError("query_only_guard_not_active")
        with csv_path.open("x", encoding="utf-8", newline="") as out, keys_path.open("x", encoding="utf-8", newline="") as keys:
            writer, key_writer = csv.writer(out, lineterminator="\n"), csv.writer(keys, lineterminator="\n")
            writer.writerow(COLUMNS)
            key_writer.writerow(["vt_symbol", "date"])
            for stamp, contract, *raw in db.execute(query, ["2019-06-01 00:00:00", "2026-10-14 00:00:00", *contracts]):
                dt = datetime.fromisoformat(stamp)
                if dt.tzinfo is not None:
                    dt = dt.astimezone(ZoneInfo("Asia/Shanghai"))
                day = dt.date().isoformat()
                if dt.hour or dt.minute or dt.second or dt.microsecond or day not in calendar_set:
                    raise ValueError("unexpected_daily_datetime")
                real_contract(contract)
                key = (contract, day)
                if key in source_keys:
                    raise ValueError("duplicate_contract_date")
                values = [float(v) for v in raw]
                if any(isinstance(v, int) and int(float(v)) != v for v in raw):
                    raise ValueError("integer_not_exactly_representable")
                opening, high, low, close, volume = values
                if not all(math.isfinite(v) for v in values) or min(values[:4]) <= 0 or volume < 0 or not low <= min(opening, close) <= max(opening, close) <= high:
                    raise ValueError("invalid_ohlcv_no_silent_repair")
                formatted = [format(v, ".17g") for v in values]
                if any(struct.pack("!d", float(s)) != struct.pack("!d", v) for s, v in zip(formatted, values)):
                    raise ValueError("float_roundtrip_failed")
                writer.writerow([day, contract, *formatted])
                key_writer.writerow(key)
                source_keys.add(key)
                seen_days.add(day)
                seen_contracts.add(contract)
                zero_volume += volume == 0
                row_count += 1
                add_fingerprint(source_digest, day, contract, values)
    # 从实际写出的CSV读取标量指纹，检查磁盘输出无损；这不是独立数据资格。
    exported_keys = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise ValueError("canonical_header_mismatch")
        for row in reader:
            exported_keys.append((row["vt_symbol"], row["date"]))
            add_fingerprint(exported_digest, row["date"], row["vt_symbol"], [float(row[k]) for k in COLUMNS[2:]])
    with keys_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["vt_symbol", "date"] or [(r["vt_symbol"], r["date"]) for r in reader] != exported_keys:
            raise ValueError("exact_keys_not_identical_to_export")
    if source_digest.digest() != exported_digest.digest() or set(exported_keys) != source_keys or len(exported_keys) != row_count:
        raise ValueError("persisted_csv_roundtrip_not_lossless")
    if (row_count, len(seen_contracts), len(seen_days), zero_volume) != (116394, 533, 1786, 1468) or seen_days != calendar_set:
        raise ValueError("138_fixed_scope_changed")
    after = {name: status(Path(str(DB) + suffix)) for name, suffix in [("db", ""), ("wal", "-wal"), ("shm", "-shm")]}
    if before != after:
        raise ValueError("original_database_or_sidecar_stat_changed")
    manifest = dict(schema="stage141_ema_normalized_daily_candidate_v1", status="pending_independent_source_review", created_at=datetime.now().astimezone().isoformat(),
        candidate_only=True, qualifier_sha256=None, qualification_granted=False, required_independent_reviewer="Stage142_not_Stage141_author",
        proposed_research_acceptance_basis=["accepted_baseline_same_frozen_real_contract_DB", "lossless_seven_column_normalization", "Stage138_limited_cross_source_samples"],
        acceptance_limits=["not_all_prices_independently_reaggregated_or_vendor_verified", "Stage013_4500_exact_keys_not_extrapolated", "provider_zero_volume_rows_retained", "contract_final_bar_not_filtered_by_future_successor", "no_carry_forwardfill_splice_adjustment_or_new_calendar", "not_financial_or_production_readiness"],
        source_bindings=bindings, database_snapshot=dict(read_bytes_calls=1, deserialize=True, sqlite_connection=":memory:", query_only=True, before=before, after=after),
        source_scope=dict(interval="d", start="2019-06-01 00:00:00", end="2026-10-14 00:00:00", metadata_contracts=len(contracts), observed_contracts=len(seen_contracts), dates=len(seen_days), rows=row_count, zero_volume_rows=zero_volume, duplicate_keys=0),
        canonical_daily=dict(path=str(csv_path), sha256=sha(csv_path.read_bytes()), bytes=csv_path.stat().st_size, columns=COLUMNS, encoding="utf-8_no_BOM", float_format=".17g", order="vt_symbol,date", price_basis="real_contract_unadjusted"),
        exact_keys=dict(path=str(keys_path), sha256=sha(keys_path.read_bytes()), bytes=keys_path.stat().st_size, columns=["vt_symbol", "date"], count=len(source_keys), order="vt_symbol,date", stored_once="external_exact_keys_csv_referenced_here_not_duplicated_per_row"),
        self_checks=dict(source_scalar_sha256=source_digest.hexdigest(), persisted_csv_scalar_sha256=exported_digest.hexdigest(), all_float64_values_roundtrip=True, unique_real_contract_keys=True, calendar_exactly_equals_original=True, all_original_zero_volume_retained=True, original_path_reopened_as_sqlite=False, independent_review=False),
        execution_tick_binding=dict(rule_source=str(ROOT / "examples/portfolio_backtesting/qmt_roll_intraday_execution.py"), rule_sha256="95de37e240ed5f34e8370cf9652e958c3c44fa3f36bef1d905c3e757a8304272", rule="effective_pricetick(contract,D,accepted_configured_tick), D=next_session(u), only_u_known_rules", LC_known_on="2024-12-06", LC_first_new_execution_day="2024-12-18", announcement_boundary_record=str(LINE / "stages/20261018_1002_stage139_ema_daily_source_acceptance_boundary.md"), no_feature_tick_rows_built=True),
        financial_replays=0, features_built=0, native_runs=0, model_calls=0, provider_calls=0, financial_ready=False, production_qualified=False)
    manifest_path = OUT / "candidate_manifest.json"
    dump(manifest_path, manifest)
    print(json.dumps(dict(status=manifest["status"], rows=row_count, contracts=len(seen_contracts), dates=len(seen_days), zero_volume_rows=zero_volume,
        database_sha256=database_sha, daily_sha256=manifest["canonical_daily"]["sha256"], exact_keys_sha256=manifest["exact_keys"]["sha256"], manifest_sha256=sha(manifest_path.read_bytes()), source_scalar_sha256=source_digest.hexdigest()), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        dump(OUT / "export_failure.json", dict(status="actual_export_failed_preserve_evidence", error_type=type(error).__name__, error=str(error), qualification_granted=False))
        raise
