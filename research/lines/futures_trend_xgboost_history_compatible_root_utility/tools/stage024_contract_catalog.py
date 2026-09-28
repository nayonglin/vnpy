from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.util
import json
import signal
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
OUTPUT = ROOT / "artifacts/stage024_contract_catalog"
CONTRACT = ROOT / "stages/20260906_0604_stage024_contract_chain_source_contract.md"
EVENTS = ROOT / "artifacts/stage001_history_qualification/event_features.csv"
CORE = ROOT.parent / "futures_trend_xgboost_pit_full_market_source_rebuild/tools/full_market_source_rebuild.py"
START = pd.Timestamp("2019-11-01")
CUTOFF = pd.Timestamp("2026-08-28")
RAW_COLUMNS = ["instrument_id", "ins_class", "exchange_id", "product_id", "expired",
               "expire_datetime", "delivery_year", "delivery_month", "price_tick", "volume_multiple"]
EVENT_COLUMNS = ["event_id", "decision_date", "product_vt_symbol", "contract_vt_symbol"]


def identity(path):
    path = Path(path)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def normalise(raw, products):
    frame = raw[RAW_COLUMNS].copy()
    if frame.instrument_id.duplicated().any():
        raise ValueError("raw_catalog_duplicate")
    if not frame.expired.map(lambda x: isinstance(x, (bool, np.bool_))).all():
        raise ValueError("raw_catalog_expired_not_boolean")
    numeric = ["expire_datetime", "delivery_year", "delivery_month", "price_tick", "volume_multiple"]
    values = frame[numeric].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(values.to_numpy(dtype=float)).all():
        raise ValueError("raw_catalog_nonfinite")
    if (not values.delivery_year.eq(values.delivery_year.round()).all()
            or not values.delivery_month.eq(values.delivery_month.round()).all()
            or not values.delivery_month.between(1, 12).all()):
        raise ValueError("raw_catalog_invalid_delivery_month")
    spec = importlib.util.spec_from_file_location("catalog_source_core024", CORE)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    result = core.normalise_catalog(frame, catalog_as_of=CUTOFF, source_start=START, cutoff=CUTOFF)
    if not set(result.product_vt_symbol).issubset(products):
        raise ValueError("raw_catalog_unrequested_product")
    for row in result.itertuples(index=False):
        digits = str(row.symbol)[len(row.product):]
        year_digits = len(digits) - 2
        if (year_digits not in (1, 2) or int(digits[-2:]) != int(row.delivery_month)
                or int(digits[:-2]) != int(row.delivery_year) % (10 ** year_digits)):
            raise ValueError("raw_catalog_symbol_delivery_mismatch")
    return result


def assess(catalog, events):
    data = events[EVENT_COLUMNS].copy()
    if data.event_id.duplicated().any() or catalog.vt_symbol.duplicated().any() or data.isna().any().any():
        raise ValueError("event_or_catalog_identity_invalid")
    data["decision_date"] = pd.to_datetime(data.decision_date, format="%Y-%m-%d", errors="raise")
    merged = data.merge(catalog[["vt_symbol", "product_vt_symbol", "expire_date"]].rename(
        columns={"vt_symbol": "contract_vt_symbol", "product_vt_symbol": "catalog_product"}),
        on="contract_vt_symbol", how="left", validate="many_to_one")
    missing = sorted(merged.loc[merged.catalog_product.isna(), "contract_vt_symbol"].unique())
    present = merged.catalog_product.notna()
    bad_product = merged.loc[present & merged.catalog_product.ne(merged.product_vt_symbol), "event_id"].tolist()
    expiry = pd.to_datetime(merged.expire_date, errors="raise")
    bad_expiry = merged.loc[present & (expiry.isna() | merged.decision_date.gt(expiry)), "event_id"].tolist()
    qualified = not (missing or bad_product or bad_expiry)
    return {"status": "catalog_qualified_not_bar_coverage" if qualified else "catalog_gap_stop_no_bars",
            "event_count": len(data), "event_contract_count": int(data.contract_vt_symbol.nunique()),
            "catalog_contract_count": len(catalog), "catalog_product_count": int(catalog.product_vt_symbol.nunique()),
            "missing_event_contracts": missing, "product_mismatch_event_ids": bad_product,
            "expiry_mismatch_event_ids": bad_expiry}


def query_catalog(products):
    from tqsdk import TqApi, TqAuth, TqBacktest, TqSim
    from vnpy.trader.setting import SETTINGS

    username, password = (str(SETTINGS.get(key) or "") for key in ("datafeed.username", "datafeed.password"))
    if not username or not password:
        raise RuntimeError("catalog_credentials_missing")
    api = TqApi(TqSim(), backtest=TqBacktest(start_dt=CUTOFF.date(), end_dt=CUTOFF.date()),
                auth=TqAuth(username, password), debug=False, disable_print=True)
    try:
        symbols = sorted(set(api.query_quotes(ins_class="FUTURE",
            exchange_id=sorted({p.split(".")[1] for p in products}),
            product_id=sorted({p.split(".")[0] for p in products}))))
        if not symbols:
            raise RuntimeError("catalog_inventory_empty")
        save(OUTPUT / "queried_symbols.json", symbols)
        frames = []
        for index in range(0, len(symbols), 80):
            batch = symbols[index:index + 80]
            frame = pd.DataFrame(api.query_symbol_info(batch)).copy()
            if "instrument_id" not in frame.columns and frame.index.name == "instrument_id":
                frame = frame.reset_index()
            if "instrument_id" not in frame.columns or sorted(frame.instrument_id) != batch:
                raise RuntimeError("catalog_query_identity_mismatch")
            frame = frame[RAW_COLUMNS].copy()
            frame.to_csv(OUTPUT / f"raw_catalog_batch_{index // 80:03d}.csv.gz", index=False)
            frames.append(frame)
            print(f"catalog metadata {min(index + 80, len(symbols))}/{len(symbols)}", flush=True)
        return pd.concat(frames, ignore_index=True)
    finally:
        api.close()


def run():
    if OUTPUT.exists():
        raise RuntimeError("catalog_output_already_exists")
    if identity(EVENTS)["sha256"] != "33c48a4a3976e644365ceeccfadbf236f24bc327ae17413c363b43de7e69bcf1":
        raise RuntimeError("catalog_event_source_changed")
    events = pd.read_csv(EVENTS, usecols=EVENT_COLUMNS)
    if len(events) != 276 or events.contract_vt_symbol.nunique() != 189 or events.product_vt_symbol.nunique() != 18:
        raise RuntimeError("catalog_event_inventory_changed")
    files = [EVENTS, CONTRACT, CORE, Path(__file__), ROOT / "tests/test_stage024_contract_catalog.py",
             WORKSPACE / ".py311/lib/python3.11/site-packages/tqsdk/api.py"]
    inputs = {str(path): identity(path) for path in files}
    OUTPUT.mkdir(parents=True)
    save(OUTPUT / "input_manifest.json", inputs)
    summary = {"status": "running", "started_at": datetime.now().astimezone().isoformat(),
               "cutoff": str(CUTOFF.date()), "source_start": str(START.date()),
               "tqsdk_version": importlib.metadata.version("tqsdk"),
               "historical_vintage_proven": False, "query_backtest_is_strategy_backtest": False,
               "strategy_backtest_count": 0, "price_download_count": 0,
               "label_read_count": 0, "model_fit_count": 0, "model_predict_count": 0,
               "reviewer_count": 0, "production_write_count": 0}
    save(OUTPUT / "summary.json", summary)
    try:
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("catalog_timeout")))
        signal.alarm(300)
        products = set(events.product_vt_symbol)
        raw = query_catalog(products)
        signal.alarm(0)
        raw.to_csv(OUTPUT / "raw_catalog.csv.gz", index=False)
        catalog = normalise(raw, products)
        catalog.to_csv(OUTPUT / "catalog.csv.gz", index=False)
        summary.update(assess(catalog, events), raw_catalog_rows=len(raw))
        if inputs != {str(path): identity(path) for path in files}:
            raise RuntimeError("catalog_inputs_changed_during_query")
    except Exception as exc:
        summary.update(status="catalog_technical_failure_stop", error_type=type(exc).__name__)
        raise
    finally:
        signal.alarm(0)
        summary["finished_at"] = datetime.now().astimezone().isoformat()
        summary["outputs"] = {path.name: identity(path) for path in sorted(OUTPUT.iterdir()) if path.name != "summary.json"}
        save(OUTPUT / "summary.json", summary)
    print(json.dumps(summary, allow_nan=False), flush=True)


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        print(json.dumps({"status": "stopped", "error_type": type(error).__name__}), flush=True)
        raise SystemExit(1) from None
