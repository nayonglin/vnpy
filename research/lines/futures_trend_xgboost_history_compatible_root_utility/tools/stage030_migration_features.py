from __future__ import annotations

import bisect
import copy
import importlib.util
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("migration_coverage030", ROOT / "tools/stage028_chain_coverage.py")
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)
base = coverage.base
SOURCE = ROOT / "artifacts/stage029_corrected_chain_coverage"
OUTPUT = ROOT / "artifacts/stage030_migration_features"
BASE_SPEC = ROOT / "stages/stage004_model_spec.json"
CONTRACT = ROOT / "stages/20260906_0712_stage030_migration_feature_contract.md"
FEATURES = ["own_oi_share_change_5d", "deferred_oi_share_change_5d"]
CONTEXT_IDS = ["decision_date", "source_date", "window_start", "product_vt_symbol", "contract_vt_symbol"]
EVENT_IDS = ["event_id", "candidate_index", "decision_date", "product_vt_symbol", "contract_vt_symbol", "direction"]


def contexts(bars, catalog, windows, calendar):
    coverage.valid_calendar(calendar)
    coverage.dates(bars.trade_date)
    if (bars.duplicated(["tq_symbol", "trade_date"]).any() or catalog.tq_symbol.duplicated().any()
            or catalog.vt_symbol.duplicated().any() or not bars.trade_date.isin(calendar).all()
            or not set(bars.tq_symbol).issubset(catalog.tq_symbol)
            or windows.duplicated(["decision_date", "product_vt_symbol"]).any()):
        raise ValueError("migration_input_identity_invalid")
    values = bars.close_oi.to_numpy(float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("migration_oi_invalid")
    for row in windows.itertuples():
        index = bisect.bisect_left(calendar, row.decision_date)
        if (index == 0 or index >= len(calendar) or calendar[index] != row.decision_date
                or row.source_date != calendar[index - 1] or row.window_start != calendar[max(0, index - 6)]):
            raise ValueError("migration_window_not_exactly_prior")
    data = bars[["tq_symbol", "trade_date", "close_oi"]].merge(catalog[["tq_symbol", "vt_symbol",
        "product_vt_symbol", "delivery_year", "delivery_month"]], on="tq_symbol", how="left", validate="many_to_one")
    data["maturity"] = data.delivery_year * 12 + data.delivery_month
    if not np.isfinite(data.maturity).all() or data.duplicated(["trade_date", "product_vt_symbol", "maturity"]).any():
        raise ValueError("migration_maturity_ambiguous")
    data = data.sort_values(["trade_date", "product_vt_symbol", "maturity"], kind="stable")
    groups = data.groupby(["trade_date", "product_vt_symbol"])
    total = groups.close_oi.transform("sum")
    if total.le(0).any():
        raise ValueError("migration_chain_oi_nonpositive")
    data["own_share"] = data.close_oi / total
    data["deferred_share"] = (total - groups.close_oi.cumsum()) / total
    shares = {(r.tq_symbol, r.trade_date): (r.own_share, r.deferred_share) for r in data.itertuples()}
    next_day = dict(zip(calendar[:-1], calendar[1:], strict=True))
    data["decision_date"] = data.trade_date.map(next_day)
    candidates = data.merge(windows, on=["decision_date", "product_vt_symbol"], how="inner", validate="many_to_one")
    if not candidates.trade_date.eq(candidates.source_date).all():
        raise ValueError("migration_candidate_source_mismatch")
    records, inventory = [], []
    for row in candidates.itertuples():
        identity = {name: getattr(row, name) for name in CONTEXT_IDS if name != "contract_vt_symbol"}
        identity["contract_vt_symbol"] = row.vt_symbol
        state = row.coverage_status
        index = bisect.bisect_left(calendar, row.decision_date)
        prior = calendar[max(0, index - 6):index]
        if state == "available" and (len(prior) != 6 or any((row.tq_symbol, day) not in shares for day in prior)):
            state = "actual_contract_window_missing"
        inventory.append({**identity, "coverage_status": state})
        if state != "available":
            continue
        start = shares[(row.tq_symbol, prior[0])]
        end = shares[(row.tq_symbol, prior[-1])]
        records.append({**identity, **{name: float(end[i] - start[i]) for i, name in enumerate(FEATURES)}})
    context = pd.DataFrame(records, columns=CONTEXT_IDS + FEATURES).sort_values(
        ["decision_date", "contract_vt_symbol"], kind="stable").reset_index(drop=True)
    if context.duplicated(["decision_date", "contract_vt_symbol"]).any() or not np.isfinite(context[FEATURES].to_numpy(float)).all():
        raise ValueError("migration_context_invalid")
    return context, pd.DataFrame(inventory)


def features_for_decision(context, day, contract, product):
    if list(context.index.names) == ["decision_date", "contract_vt_symbol"]:
        if (day, contract) not in context.index:
            raise ValueError("migration_context_missing")
        row = context.loc[(day, contract)]
        if not isinstance(row, pd.Series):
            raise ValueError("migration_context_duplicate")
    else:
        selected = context.loc[context.decision_date.eq(day) & context.contract_vt_symbol.eq(contract)]
        if len(selected) != 1:
            raise ValueError("migration_context_missing_or_duplicate")
        row = selected.iloc[0]
    if row.product_vt_symbol != product or not row.window_start < row.source_date < day:
        raise ValueError("migration_context_identity_or_time_invalid")
    values = row[FEATURES].to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError("migration_lookup_nonfinite")
    return {key: float(value) for key, value in zip(FEATURES, values, strict=True)}


def candidate_spec(original):
    result = copy.deepcopy(original)
    if set(result["features"]) & set(FEATURES):
        raise ValueError("migration_features_already_present")
    result["features"] = [*result["features"], *FEATURES]
    return result


def run():
    if OUTPUT.exists():
        raise RuntimeError("migration_output_already_exists")
    if base.identity(SOURCE / "summary.json")["sha256"] != "99dd22b49cdef929aa20b22e48a652773f3763684a878f3e4f65b1a0519aa916":
        raise RuntimeError("corrected_source_summary_changed")
    source = json.loads((SOURCE / "summary.json").read_text())
    if source["status"] != "corrected_event_source_qualified_not_model" or source["event_status_counts"] != {"available": 276}:
        raise RuntimeError("corrected_source_not_qualified")
    if base.identity(BASE_SPEC)["sha256"] != "9065479d7c5ac457c2f92ba3e8aa4ec5a3b7c9150dcf6497deeb815957d44a16":
        raise RuntimeError("original_model_spec_changed")
    sources = json.loads((SOURCE / "input_manifest.json").read_text())
    sources.update({v["path"]: v for v in source["outputs"].values()})
    for path, value in sources.items():
        if base.identity(path) != value:
            raise RuntimeError("migration_frozen_source_changed")
    paths = [SOURCE / "summary.json", BASE_SPEC, Path(__file__), CONTRACT, ROOT / "tests/test_stage030_migration_features.py"]
    sources.update({str(p): base.identity(p) for p in paths})
    OUTPUT.mkdir(parents=True)
    base.save(OUTPUT / "input_manifest.json", sources)
    report = dict(status="running", started_at=datetime.now().astimezone().isoformat(),
        label_read_count=0, model_fit_predict_count=0, strategy_backtest_count=0,
        reviewer_count=0, production_write_count=0, historical_evidence_type="development_not_untouched_holdout")
    try:
        bars = pd.read_csv(coverage.OUTPUT / "source_bars.csv.gz", usecols=["tq_symbol", "trade_date", "close_oi"])
        catalog = pd.read_csv(SOURCE / "corrected_catalog.csv.gz")
        windows = pd.read_csv(SOURCE / "a_calendar_coverage.csv.gz")
        calendar = pd.read_csv(coverage.OUTPUT / "calendar.csv").date.tolist()
        context, inventory = contexts(bars, catalog, windows, calendar)
        events = pd.read_csv(base.EVENTS, usecols=EVENT_IDS)
        expected = pd.read_csv(SOURCE / "event_coverage.csv")
        if len(events) != 276 or set(events.event_id) != set(expected.event_id):
            raise RuntimeError("migration_event_inventory_changed")
        indexed = context.set_index(["decision_date", "contract_vt_symbol"], drop=False, verify_integrity=True)
        records = []
        for row in events.to_dict("records"):
            values = features_for_decision(indexed, row["decision_date"], row["contract_vt_symbol"], row["product_vt_symbol"])
            current = indexed.loc[(row["decision_date"], row["contract_vt_symbol"])]
            prior = expected.loc[expected.event_id.eq(row["event_id"])].iloc[0]
            if (current.source_date != prior.source_date or current.window_start != prior.window_start
                    or any(row[key] != prior[key] for key in coverage.EVENT_COLUMNS)):
                raise RuntimeError("migration_event_source_identity_changed")
            records.append({**row, "source_date": current.source_date, "window_start": current.window_start, **values})
        event_features = pd.DataFrame(records)
        new_spec = candidate_spec(json.loads(BASE_SPEC.read_text()))
        if len(new_spec["features"]) != 12 or not np.isfinite(event_features[FEATURES].to_numpy(float)).all():
            raise RuntimeError("migration_candidate_dimensions_or_values_invalid")
        for name, value in {"contract_context.csv.gz": context, "context_inventory.csv.gz": inventory,
            "event_migration_features.csv": event_features}.items():
            value.to_csv(OUTPUT / name, index=False)
        base.save(OUTPUT / "candidate_model_spec.json", new_spec)
        report.update(status="migration_features_qualified_no_models", event_count=len(event_features),
            context_count=len(context), inventory_count=len(inventory),
            inventory_status_counts=inventory.coverage_status.value_counts().to_dict(),
            features=FEATURES, candidate_feature_count=12)
        if any(base.identity(path) != value for path, value in sources.items()):
            raise RuntimeError("migration_inputs_changed_during_run")
        report["inputs_unchanged"] = True
    except Exception as exc:
        report.update(status="migration_feature_failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        report["finished_at"] = datetime.now().astimezone().isoformat()
        report["outputs"] = {p.name: base.identity(p) for p in sorted(OUTPUT.iterdir()) if p.name != "summary.json"}
        base.save(OUTPUT / "summary.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "outputs"}), flush=True)


if __name__ == "__main__":
    run()
