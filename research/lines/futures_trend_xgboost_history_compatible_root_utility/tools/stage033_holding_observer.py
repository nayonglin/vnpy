from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import inspect
import json
import math
import os
import shutil
import subprocess
import sys
import traceback
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage033_holding_observer"
WORKER_ARM = "A"
OUTPUT = ROOT / "artifacts" / STAGE
FREEZE = ROOT / "stages/stage033_input_freeze.json"
CONTRACT = ROOT / "stages/20260906_0804_stage033_holding_observer_contract.md"
START, END = "2020-01-02", "2026-08-28"
LAYER_FIELDS = ("kind", "direction", "volume", "entry_price", "stop_price", "highest_price", "lowest_price",
                "entry_date", "max_profit_pct", "entry_price_synced", "profit_giveback_stop_active")


def load(name):
    spec = importlib.util.spec_from_file_location("observer_" + name, ROOT / "tools" / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = value
    spec.loader.exec_module(value)
    return value


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("observer_nonfinite_number")
    return result


def classify(row):
    if row["product_vt_symbol"] == "fu.SHFE":
        return "fixed_fu"
    actual = row["actual_positions"]
    if not actual:
        return "unfilled_or_inconsistent_plan" if row["targets"] or row["layers"] or row["active_orders"] else "flat"
    if len(actual) != 1:
        return "multiple_actual_contracts"
    if row["active_orders"] or row["pending_close_lot_count"] or row["pending_close_reason_count"]:
        return "pending_orders_or_close_inventory"
    if actual != row["targets"]:
        return "target_position_mismatch"
    if row["rollover_pending_target_contract"]:
        return "rollover_pending"
    contract, pos = next(iter(actual.items()))
    direction = "long" if pos > 0 else "short"
    if row["state_contract"] != contract or row["state_direction"] != direction:
        return "state_contract_or_direction_mismatch"
    if not row["bar"]:
        return "missing_current_bar"
    if (not row["layers"] or any(layer["direction"] != direction or layer["volume"] <= 0 for layer in row["layers"])
            or sum(layer["volume"] for layer in row["layers"]) != abs(pos)):
        return "layer_position_mismatch"
    if any(not layer["entry_price_synced"] or layer["entry_price"] <= 0 for layer in row["layers"]):
        return "layer_not_synchronized"
    return "stable_holding"


def snapshot(strategy, bars):
    engine = strategy.strategy_engine
    day = engine.datetime.strftime("%Y-%m-%d")
    if not START <= day <= END:
        return []
    mapping = strategy.source_symbol_by_contract
    positions = {symbol: number(value) for symbol, value in strategy.pos_data.items() if number(value) != 0}
    targets = {symbol: number(value) for symbol, value in strategy.target_data.items() if number(value) != 0}
    orders = engine.active_limit_orders
    if (set(positions) | set(targets) | {order.vt_symbol for order in orders.values()}) - set(mapping):
        raise ValueError("observer_unknown_contract")
    if {mapping[symbol] for symbol in positions} - set(strategy.states):
        raise ValueError("observer_unknown_product")
    rows = []
    for product, state in sorted(strategy.states.items()):
        actual = {symbol: value for symbol, value in positions.items() if mapping[symbol] == product}
        desired = {symbol: value for symbol, value in targets.items() if mapping[symbol] == product}
        active = []
        for key, order in orders.items():
            if mapping[order.vt_symbol] != product:
                continue
            active.append({"order_id": str(key), "vt_symbol": order.vt_symbol,
                **{name: str(getattr(order, name)) for name in ("direction", "offset", "status", "datetime")},
                **{name: number(getattr(order, name)) for name in ("price", "volume", "traded")}})
        layers = [{name: getattr(layer, name) for name in LAYER_FIELDS} for layer in state.layers]
        contract = next(iter(actual)) if len(actual) == 1 else ""
        bar = bars.get(contract)
        current = None
        if bar is not None and bar.datetime.strftime("%Y-%m-%d") == day:
            current = {"vt_symbol": contract, "datetime": bar.datetime.isoformat(), "interval": str(bar.interval),
                **{name: number(getattr(bar, name)) for name in ("open_price", "high_price", "low_price", "close_price", "volume", "open_interest")}}
        row = {"date": day, "bar_datetime": engine.datetime.isoformat(), "phase": "after_strategy_on_bars",
            "product_vt_symbol": product, "actual_positions": actual, "targets": desired,
            "active_orders": active, "layers": layers, "state_contract": state.contract_vt_symbol,
            "state_direction": state.direction, "entry_date": state.entry_date,
            "bars_since_entry": state.bars_since_entry, "prev2day_stop_price": state.prev2day_stop_price,
            "rollover_pending_target_contract": state.rollover_pending_target_contract,
            "rsi_partial_exit_done": state.rsi_partial_exit_done, "bar": current,
            "pending_close_lot_count": sum(len(items) for symbol, items in strategy.pending_close_lots.items() if mapping[symbol] == product),
            "pending_close_reason_count": sum(len(items) for symbol, items in strategy.pending_close_reasons.items() if mapping[symbol] == product),
            "estimated_equity": number(strategy.estimated_equity), "total_margin_in_use": number(strategy.total_margin_in_use),
            "loss_streak": strategy.loss_streak}
        row["state_status"] = classify(row)
        json.dumps(row, allow_nan=False)
        rows.append(row)
    return rows


def method_identity(method):
    if method is None:
        return None
    path = inspect.getsourcefile(method)
    return {"module": method.__module__, "qualname": method.__qualname__, "source": path,
            "source_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest() if path else None}


def install_observer(strategy_class, rows, provenance=None):
    original = strategy_class.on_bars
    local = strategy_class.__dict__.get("on_bars")

    def observed(self, bars):
        if provenance is not None and not provenance:
            engine = self.strategy_engine
            provenance.update(strategy_on_bars=method_identity(original),
                engine_class=type(engine).__module__ + "." + type(engine).__qualname__,
                engine_mro=[cls.__module__ + "." + cls.__qualname__ for cls in type(engine).__mro__],
                engine_methods={name: method_identity(getattr(engine, name, None)) for name in
                    ("new_bars", "cross_delayed_orders", "cross_same_day_close_orders", "_resolve_trade_price", "_fill_order", "send_order")})
        result = original(self, bars)
        rows.extend(snapshot(self, bars))
        return result

    strategy_class.on_bars = observed

    def restore():
        if local is None:
            delattr(strategy_class, "on_bars")
        else:
            strategy_class.on_bars = local
    return restore


def collect_inputs():
    files = load("stage007a_runtime_equivalence").collect_inputs()
    files.update(holding_observer_runner=Path(__file__).resolve(), holding_observer_contract=CONTRACT,
        holding_observer_tests=ROOT / "tests/test_stage033_holding_observer.py",
        holding_observer_lifecycles=ROOT / "artifacts/stage003_cancelled_lifecycle/event_lifecycles.csv")
    return dict(sorted(files.items()))


def configured(rows=None, provenance=None, input_count=None):
    base, runner = load("stage004_label_batch").configured()
    base.STAGE = runner.STAGE = STAGE
    runner.collect_input_files = collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT = input_count if input_count is not None else json.loads(FREEZE.read_text())["input_file_count"]
    original_load = runner.load_v1_runner

    def local_v1():
        v1 = original_load()
        original_install = v1._install_correlation_trace_instrumentation

        def instrument(strategy_class):
            correlation_restore = original_install(strategy_class)
            observer_restore = install_observer(strategy_class, rows, provenance)

            def restore():
                observer_restore()
                correlation_restore()
            return restore

        v1._install_correlation_trace_instrumentation = instrument
        return v1

    runner.load_v1_runner = local_v1
    return base, runner


def qualify_trace(rows, daily, positions):
    observed, keys, dates, counts = {}, set(), set(), Counter()
    products_by_date = {}
    for row in rows:
        key = (row["date"], row["product_vt_symbol"])
        if key in keys or row["phase"] != "after_strategy_on_bars" or classify(row) != row["state_status"]:
            raise RuntimeError("observer_trace_identity_or_classification_invalid")
        keys.add(key)
        dates.add(row["date"])
        products_by_date.setdefault(row["date"], set()).add(row["product_vt_symbol"])
        counts[row["state_status"]] += 1
        for symbol, value in row["actual_positions"].items():
            key = (row["date"], symbol)
            if key in observed:
                raise RuntimeError("observer_duplicate_actual_position")
            observed[key] = value
    expected_dates = daily.date.astype(str).str[:10].tolist()
    if sorted(dates) != expected_dates or len({tuple(sorted(p)) for p in products_by_date.values()}) != 1:
        raise RuntimeError("observer_calendar_or_product_inventory_invalid")
    expected = {(str(row.date)[:10], row.vt_symbol): float(row.end_pos) for row in positions.itertuples() if row.end_pos != 0}
    if observed != expected:
        raise RuntimeError("observer_actual_position_differs_from_daily_ledger")
    return {"rows": len(rows), "days": len(dates), "products": len(next(iter(products_by_date.values()))),
            "nonzero_contract_days": len(observed), "state_status_counts": dict(counts), "actual_positions_exact": True}


def run_parent():
    if OUTPUT.exists():
        raise RuntimeError("observer_campaign_already_exists")
    base, runner = configured()
    batch = load("stage004_label_batch")
    equivalence = load("stage007a_runtime_equivalence")
    manifest = runner.build_input_manifest()
    runner.validate_frozen_input_contract(FREEZE, manifest)
    batch.verify_baseline_inputs(manifest)
    if shutil.disk_usage(ROOT).free < 2 * 1024 ** 3:
        raise RuntimeError("observer_disk_reserve")
    lock = batch.OUTPUT / "run.lock"
    with lock.open("x") as stream:
        json.dump({"pid": os.getpid(), "mode": STAGE}, stream)
    paths = None
    try:
        OUTPUT.mkdir(mode=0o700)
        batch.write_json(OUTPUT / "input_manifest.json", manifest)
        preflight = runner.load_metadata_preflight_module().load_preflight_module()
        root = OUTPUT / "workers" / WORKER_ARM
        database = manifest["files"]["source_database"]
        paths = runner.prepare_stage002_worker_root(root, source_database=Path(database["path"]), expected_database_sha256=database["sha256"])
        preflight.write_sandbox_profile(paths["profile"], root)
        command = ["/usr/bin/sandbox-exec", "-f", str(paths["profile"]), str(Path(sys.executable).resolve()),
                   "-I", "-S", "-B", str(Path(__file__).resolve()), "--worker", "--arm", WORKER_ARM, "--worker-root", str(root),
                   "--manifest", str(OUTPUT / "input_manifest.json")]
        with paths["log"].open("wb") as stream:
            result = subprocess.run(command, cwd=paths["runtime"], env=preflight.expected_worker_environment(paths["runtime"]), stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f"observer_worker_failed:{result.returncode}")
        receipt = json.loads(paths["receipt"].read_text())
        if (receipt["status"] != "passed" or receipt["stage"] != STAGE or receipt["arm"] != WORKER_ARM
                or receipt["file_contract_sha256"] != manifest["file_contract_sha256"]
                or receipt["formal_identity"] != manifest["formal_identity"]
                or receipt["formal_replay_call_count"] != 1 or any(receipt["sensitive_counters"].values())
                or receipt["network_connection_attempt_count"] != 0 or receipt["audit"]["skip_count"] != 0):
            raise RuntimeError("observer_worker_receipt_invalid")
        for name, identity in receipt["frames"].items():
            if runner._file_identity(root / f"{name}.csv") != identity:
                raise RuntimeError("observer_output_changed")
        frames = base.read_frames(root)
        expected = equivalence.expected_frames("A0", receipt["formal_identity"])
        equivalence.require_frame_equivalence(expected, frames)
        if receipt["metrics"] != base.equity_metrics(expected["daily"], expected["trades"]):
            raise RuntimeError("observer_metrics_changed")
        observer_receipt = json.loads((root / "observer_receipt.json").read_text())
        trace = root / "holding_states.json.gz"
        if runner._file_identity(trace) != observer_receipt["trace_identity"]:
            raise RuntimeError("observer_compressed_trace_changed")
        raw = gzip.decompress(trace.read_bytes())
        if hashlib.sha256(raw).hexdigest() != observer_receipt["raw_sha256"]:
            raise RuntimeError("observer_raw_trace_changed")
        rows = json.loads(raw)
        qualification = qualify_trace(rows, frames["daily"], frames["positions"])
        if len(rows) != observer_receipt["row_count"]:
            raise RuntimeError("observer_row_count_changed")
        archiver = batch.load("holding_archiver", batch.V4 / "tools/stage006_prefix_equivalence.py")
        archives = {name: archiver.archive_csv(root / f"{name}.csv", item) for name, item in receipt["frames"].items()}
        batch.write_json(root / "archive_receipt.json", archives)
        collector = load("stage005_label_collection")
        for name, item in archives.items():
            collector.verify_archive(root / f"{name}.csv.gz", item)
        runner.validate_current_input_manifest(manifest)
        summary = {"stage": STAGE, "status": "observation_qualified_not_model", "all_seven_frames_exact": True,
            "qualification": qualification, "metrics": receipt["metrics"], "formal_replay_call_count": 1,
            "new_training_label_count": 0, "historical_model_fit_predict_count": 0, "reviewer_started": False,
            "new_model_strategy_candidate": False, "file_contract_sha256": manifest["file_contract_sha256"],
            "worker_receipt_sha256": batch.digest(paths["receipt"]),
            "observer_receipt_identity": runner._file_identity(root / "observer_receipt.json"),
            "trace_identity": runner._file_identity(trace)}
        batch.write_json(OUTPUT / "summary.json", summary)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        if OUTPUT.exists() and not (OUTPUT / "failure.json").exists():
            batch.write_json(OUTPUT / "failure.json", {"status": "failed", "error": str(exc), "traceback": traceback.format_exc()})
        raise
    finally:
        if paths and paths["runtime"].exists():
            shutil.rmtree(paths["runtime"])
        lock.unlink()


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--worker", action="store_true")
    parser.add_argument("--arm", choices=[WORKER_ARM])
    parser.add_argument("--worker-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.freeze:
        _, runner = configured(input_count=len(collect_inputs()))
        manifest = runner.build_input_manifest()
        runner.validate_input_manifest_payload(manifest)
        load("stage004_label_batch").verify_baseline_inputs(manifest)
        payload = {key: manifest[key] for key in ("schema_version", "stage", "line_id", "input_file_count",
            "input_logical_key_sha256", "file_contract_sha256", "runtime_contract_sha256")}
        payload["execution_authorized"] = True
        load("stage004_label_batch").write_json(FREEZE, payload)
        print(json.dumps(payload), flush=True)
    elif args.worker:
        if args.arm != WORKER_ARM:
            parser.error("observer requires plain A worker arm")
        rows, provenance = [], {}
        base, runner = configured(rows, provenance)
        base.run_worker(args)
        raw = json.dumps(rows, separators=(",", ":"), allow_nan=False).encode()
        path = args.worker_root / "holding_states.json.gz"
        runner._write_bytes_exclusive(path, gzip.compress(raw, mtime=0))
        runner._write_json_exclusive(args.worker_root / "observer_receipt.json", {"row_count": len(rows),
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "trace_identity": runner._file_identity(path), "runtime_provenance": provenance})
    else:
        run_parent()


if __name__ == "__main__":
    main()
