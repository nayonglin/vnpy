from __future__ import annotations

import importlib.util
import json
import lzma
import math
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("catalog_base026", ROOT / "tools/stage024_contract_catalog.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
OUTPUT = ROOT / "artifacts/stage026_sdk_cache_catalog"
CONTRACT = ROOT / "stages/20260906_0628_stage026_sdk_cache_catalog_contract.md"
CACHE = base.WORKSPACE / ".py311/lib/python3.11/site-packages/tqsdk/expired_quotes.json.lzma"


def load_cache(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    with lzma.open(path, "rt", encoding="utf-8") as stream:
        result = json.load(stream, object_pairs_hook=unique)
    if not isinstance(result, dict):
        raise ValueError("cache_not_mapping")
    return result


def project_cache(cache, products):
    counts = dict(total=len(cache), non_future=0, other_product=0, before_start=0, included=0)
    rows = []
    for key, item in sorted(cache.items()):
        if not isinstance(item, dict) or key != item.get("instrument_id"):
            raise ValueError("cache_key_identity_mismatch")
        if item.get("ins_class") != "FUTURE":
            counts["non_future"] += 1
            continue
        if f'{item.get("product_id")}.{item.get("exchange_id")}' not in products:
            counts["other_product"] += 1
            continue
        expiry = item.get("expire_datetime")
        if isinstance(expiry, bool) or not isinstance(expiry, (int, float)) or not math.isfinite(expiry):
            raise ValueError("cache_expiry_invalid")
        day = pd.Timestamp(expiry, unit="s", tz="UTC").tz_convert("Asia/Shanghai").tz_localize(None).normalize()
        if day < base.START:
            counts["before_start"] += 1
            continue
        if set(base.RAW_COLUMNS) - item.keys():
            raise ValueError("cache_required_fields_missing")
        rows.append({name: item[name] for name in base.RAW_COLUMNS})
        counts["included"] += 1
    frame = pd.DataFrame(rows, columns=base.RAW_COLUMNS)
    if len(frame):
        base.normalise(frame, products)
    return frame, counts


def combine(modern, cached, products):
    for frame in (modern, cached):
        if len(frame):
            base.normalise(frame, products)
    new = modern.set_index("instrument_id")[base.RAW_COLUMNS[1:]]
    old = cached.set_index("instrument_id")[base.RAW_COLUMNS[1:]]
    for symbol in sorted(set(new.index) & set(old.index)):
        differing = [key for key in new.columns if new.at[symbol, key] != old.at[symbol, key]]
        if differing:
            raise ValueError(f"overlap_conflict:{symbol}:{','.join(differing)}")
    merged = pd.concat([modern, cached[~cached.instrument_id.isin(new.index)]], ignore_index=True)
    merged = merged.sort_values("instrument_id", kind="stable").reset_index(drop=True)
    sources = pd.DataFrame([{
        "instrument_id": symbol,
        "source": "stage024+sdk_pre20_cache" if symbol in new.index and symbol in old.index
                  else "stage024" if symbol in new.index else "sdk_pre20_cache",
    } for symbol in merged.instrument_id])
    return merged, sources


def run():
    if OUTPUT.exists():
        raise RuntimeError("output_already_exists")
    frozen = {
        CACHE: "6aaa792a814af975df59bafaaecc7ad7025f71050380f7c7e2bda0a5c684ac72",
        base.EVENTS: "33c48a4a3976e644365ceeccfadbf236f24bc327ae17413c363b43de7e69bcf1",
        base.OUTPUT / "summary.json": "417a26acd7d5a9553c76cf3d9438b022716f2e1c04319af45e3d2835f823b778",
    }
    for path, expected in frozen.items():
        if base.identity(path)["sha256"] != expected:
            raise RuntimeError("frozen_source_changed")
    prior = json.loads((base.OUTPUT / "summary.json").read_text())
    for value in prior["outputs"].values():
        if base.identity(value["path"]) != value:
            raise RuntimeError("stage024_output_changed")
    files = list(frozen) + [base.OUTPUT / "raw_catalog.csv.gz", CONTRACT, Path(__file__),
        ROOT / "tests/test_stage026_sdk_cache_catalog.py", ROOT / "tools/stage024_contract_catalog.py",
        base.CORE, base.WORKSPACE / ".py311/lib/python3.11/site-packages/tqsdk/api.py"]
    inputs = {str(path): base.identity(path) for path in files}
    OUTPUT.mkdir(parents=True)
    base.save(OUTPUT / "input_manifest.json", inputs)
    report = dict(status="running", started_at=datetime.now().astimezone().isoformat(),
        historical_vintage_proven=False, full_chain_bar_coverage_proven=False,
        network_request_count=0, label_read_count=0, model_fit_predict_count=0,
        strategy_backtest_count=0, reviewer_count=0, production_write_count=0)
    try:
        events = pd.read_csv(base.EVENTS, usecols=base.EVENT_COLUMNS)
        products = set(events.product_vt_symbol)
        if (len(events), events.contract_vt_symbol.nunique(), len(products)) != (276, 189, 18):
            raise RuntimeError("frozen_event_scope_changed")
        cache = load_cache(CACHE)
        cached, counts = project_cache(cache, products)
        cached.to_csv(OUTPUT / "cache_raw_projection.csv.gz", index=False)
        modern = pd.read_csv(base.OUTPUT / "raw_catalog.csv.gz")
        raw, sources = combine(modern, cached, products)
        catalog = base.normalise(raw, products)
        raw.to_csv(OUTPUT / "combined_raw_catalog.csv.gz", index=False)
        sources.to_csv(OUTPUT / "catalog_sources.csv", index=False)
        catalog.to_csv(OUTPUT / "catalog.csv.gz", index=False)
        coverage = events.merge(catalog[["vt_symbol", "product_vt_symbol", "expire_date"]].rename(
            columns={"vt_symbol": "contract_vt_symbol", "product_vt_symbol": "catalog_product"}),
            on="contract_vt_symbol", how="left", validate="many_to_one")
        coverage.to_csv(OUTPUT / "event_catalog_coverage.csv", index=False)
        report.update(base.assess(catalog, events), cache_counts=counts,
            added_contract_count=len(raw) - len(modern),
            overlap_contract_count=int(sources.source.eq("stage024+sdk_pre20_cache").sum()))
        if inputs != {str(path): base.identity(path) for path in files}:
            raise RuntimeError("inputs_changed_during_run")
        report["inputs_unchanged"] = True
    except Exception as exc:
        report.update(status="catalog_supplement_failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        report["finished_at"] = datetime.now().astimezone().isoformat()
        report["outputs"] = {p.name: base.identity(p) for p in sorted(OUTPUT.iterdir()) if p.name != "summary.json"}
        base.save(OUTPUT / "summary.json", report)
    print(json.dumps(report, allow_nan=False), flush=True)


if __name__ == "__main__":
    run()
