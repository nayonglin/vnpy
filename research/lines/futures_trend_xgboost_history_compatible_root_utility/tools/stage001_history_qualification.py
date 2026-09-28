from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LINES = ROOT.parent
V4 = LINES / "futures_trend_xgboost_formal_signal_marginal_utility_v4"
SOURCE = V4 / "artifacts/stage004_counterfactual_validation/workers/A"
OUTPUT = ROOT / "artifacts/stage001_history_qualification"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


upstream = load_module("history_source_features", LINES /
    "futures_trend_xgboost_formal_signal_marginal_utility/tools/formal_signal_event_features.py")
lifecycle = load_module("history_lifecycle", V4 / "tools/stage005_event_lifecycle_audit.py")
headroom = load_module("history_headroom", V4 / "tools/stage007_objective_headroom_audit.py")
FEATURES = upstream.FEATURE_COLUMNS[2:]
ID_COLUMNS = ("event_id", *upstream.IDENTITY_KEYS, "analysis_start", "analysis_end", "candidate_index",
              "decision_datetime", "decision_date", "product_vt_symbol", "contract_vt_symbol",
              "direction", "signal", "entry_context", "candidate_status", "is_opened", "ai_eval_date")


def build_features(candidates, identity):
    identity = upstream._require_identity(identity)
    table = candidates.loc[upstream._integer(candidates, "is_opened").eq(1)
        & candidates.entry_context.eq("flat_entry") & candidates.candidate_status.eq("opened")
        & candidates.product_vt_symbol.ne("fu.SHFE")].copy().reset_index(drop=True)
    if table.empty:
        raise RuntimeError("no_root_events")
    upstream._require_text(table, ("product_vt_symbol", "contract_vt_symbol", "direction", "signal"), "candidate")
    if not table.direction.isin(["long", "short"]).all():
        raise RuntimeError("direction_invalid")
    if not table.ai_product_pool_strategy.eq(identity["formal_strategy"]).all():
        raise RuntimeError("formal_strategy_mismatch")
    table["candidate_index"] = upstream._integer(table, "candidate_index")
    if table.candidate_index.duplicated().any():
        raise RuntimeError("duplicate_event_identity")
    table["decision_datetime"] = upstream._canonical_datetime(table.datetime)
    table["decision_date"] = upstream._canonical_date(table.date, "candidate")
    table["ai_eval_date"] = upstream._canonical_date(table.ai_product_pool_signal_date, "ai_eval")
    actual_dates = pd.to_datetime(table.decision_datetime).map(lambda x: x.date().isoformat())
    if (not actual_dates.equals(table.decision_date)
            or not table.decision_date.between(upstream.ANALYSIS_START, upstream.ANALYSIS_END).all()
            or not table.ai_eval_date.lt(table.decision_date).all()):
        raise RuntimeError("decision_time_invalid")
    positive = ("planned_entry_price", "oi_price_confirm_entry_oi", "oi_price_confirm_prev_oi",
                "estimated_equity", "max_concurrent_positions")
    numeric = ("rsi_value", "ma_mid_value", "ma_long_value", "ma_mid_prev_value", "ma_long_prev_value",
               "stop_distance", "portfolio_drawdown_pct", "total_margin_in_use_before", "active_positions_before",
               "loss_streak", "same_direction_correlation_max_corr", *upstream.TRACE_COLUMNS)
    values = {key: upstream._positive(table, key) for key in positive}
    values.update({key: upstream._numeric(table, key) for key in numeric})
    for key in ("max_concurrent_positions", "active_positions_before", "loss_streak", *upstream.TRACE_COLUMNS):
        if key.endswith("max_corr_recomputed"):
            continue
        values[key] = upstream._integer(table, key)
        if values[key].lt(0).any():
            raise RuntimeError(f"negative_count:{key}")
    for key in ("stop_distance", "total_margin_in_use_before"):
        if values[key].lt(0).any():
            raise RuntimeError(f"negative_value:{key}")
    c = lambda suffix: values["same_direction_correlation_" + suffix]
    if (not c("gate_enabled").eq(1).all() or not c("candidate_history_available").eq(1).all()
            or not c("min_required_count").gt(0).all()
            or not c("candidate_return_count").ge(c("min_required_count")).all()
            or not c("trace_exact").eq(1).all()
            or not c("active_count").eq(c("active_count_recomputed")).all()
            or not c("corr_count").eq(c("corr_count_recomputed")).all()
            or not c("corr_count").eq(c("active_count")).all()
            or not np.isclose(c("max_corr"), c("max_corr_recomputed"), rtol=0, atol=1e-12).all()
            or not c("max_corr_recomputed").between(-1, 1).all()
            or (c("active_count").eq(0) & ~np.isclose(c("max_corr"), 0, rtol=0, atol=1e-12)).any()):
        raise RuntimeError("correlation_trace_invalid")
    rows = []
    for index, row in table.iterrows():
        v = lambda key: float(values[key].loc[index])
        sign = 1 if row.direction == "long" else -1
        price = v("planned_entry_price")
        event = {key: row[key] for key in ID_COLUMNS if key in table.columns}
        event.update(identity, analysis_start=upstream.ANALYSIS_START, analysis_end=upstream.ANALYSIS_END)
        event.update(
            directional_rsi=sign * (v("rsi_value") - 50) / 50,
            directional_ma_gap=sign * (v("ma_mid_value") - v("ma_long_value")) / price,
            directional_ma_slope=sign * ((v("ma_mid_value") - v("ma_mid_prev_value")
                                         + v("ma_long_value") - v("ma_long_prev_value")) / 2) / price,
            open_interest_change_pct=v("oi_price_confirm_entry_oi") / v("oi_price_confirm_prev_oi") - 1,
            stop_distance_pct=v("stop_distance") / price,
            portfolio_drawdown_pct=v("portfolio_drawdown_pct"),
            margin_to_equity_before=v("total_margin_in_use_before") / v("estimated_equity"),
            active_positions_fraction=v("active_positions_before") / v("max_concurrent_positions"),
            same_direction_correlation=v("same_direction_correlation_max_corr_recomputed"),
            loss_streak=v("loss_streak"))
        event["event_id"] = upstream._event_id(event, identity)
        rows.append(event)
    result = pd.DataFrame(rows).loc[:, [*ID_COLUMNS, *FEATURES]].sort_values(
        ["decision_date", "candidate_index"], kind="stable").reset_index(drop=True)
    if result.event_id.duplicated().any() or not np.isfinite(result.loc[:, FEATURES].to_numpy(dtype=float)).all():
        raise RuntimeError("feature_output_invalid")
    return result


def all_lifecycles(roots, candidates, trades, positions, calendar, mapping):
    reconciliation = lifecycle.reconcile_positions(trades, positions)
    positions = positions.assign(product=positions.vt_symbol.map(mapping), absolute_position=positions.end_pos.abs())
    if positions["product"].isna().any() or trades.vt_symbol.map(mapping).isna().any():
        raise RuntimeError("contract_product_mapping_missing")
    exposure = positions.groupby(["product", "date"]).absolute_position.sum()
    rows = []
    for target in roots.to_dict("records"):
        result = lifecycle.event_lifecycle(target, candidates, trades, exposure.loc[target["product_vt_symbol"]], calendar)
        rows.append({**{key: target[key] for key in ID_COLUMNS}, **result})
    result = pd.DataFrame(rows)
    if result.root_trade_id.dropna().duplicated().any():
        raise RuntimeError("root_fill_reused")
    return result, reconciliation


def verify_membership(actual, member):
    for source, dest in (("ai_product_pool_score", "score"), ("ai_product_pool_rank", "score_rank"),
                         ("ai_product_pool_top_n", "top_n")):
        if not np.isclose(float(actual[source]), float(member[dest]), rtol=0, atol=1e-12):
            raise RuntimeError(f"eligibility_identity_mismatch:{dest}")


def main():
    if OUTPUT.exists():
        raise RuntimeError("output_already_exists")
    receipt_path = SOURCE / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    if receipt["status"] != "passed" or receipt["arm"] != "A" or receipt["audit"]["skip_count"] != 0:
        raise RuntimeError("baseline_receipt_invalid")
    sources = [receipt_path, Path(__file__).resolve(), ROOT / "LINE.md",
               ROOT / "tests/test_stage001_history_qualification.py",
               Path(upstream.__file__), Path(lifecycle.__file__), Path(headroom.__file__)]
    for name in ("entry_candidates", "trades", "positions", "daily", "root_features"):
        path = SOURCE / f"{name}.csv"
        actual = lifecycle.file_identity(path)
        if any(actual[key] != receipt["frames"][name][key] for key in actual):
            raise RuntimeError(f"baseline_frame_changed:{name}")
        sources.append(path)
    formal = receipt["formal_identity"]
    eligibility_path = Path(formal["eligibility_path"])
    if lifecycle.file_identity(eligibility_path)["sha256"] != formal["eligibility_sha256"]:
        raise RuntimeError("eligibility_changed")
    sources.append(eligibility_path)
    identities = {str(path): lifecycle.file_identity(path) for path in sources}
    candidates = pd.read_csv(SOURCE / "entry_candidates.csv", float_precision="round_trip")
    roots = build_features(candidates, formal)
    eligibility = upstream._prepare_eligibility(pd.read_csv(eligibility_path), formal).set_index(["eval_date", "product_vt_symbol"])
    for row in roots.to_dict("records"):
        member = eligibility.loc[(row["ai_eval_date"], row["product_vt_symbol"])]
        actual = candidates.loc[candidates.candidate_index.eq(row["candidate_index"])].iloc[0]
        verify_membership(actual, member)
    dynamic = pd.read_csv(SOURCE / "root_features.csv", float_precision="round_trip")
    common = roots.set_index("event_id").loc[dynamic.event_id, list(FEATURES)]
    dynamic_values = dynamic.loc[:, FEATURES].to_numpy(dtype=float)
    difference = float(np.max(np.abs(common.to_numpy(dtype=float) - dynamic_values)))
    if difference != 0:
        raise RuntimeError(f"dynamic_shared_feature_mismatch:{difference}")
    trades = pd.read_csv(SOURCE / "trades.csv", usecols=["trade_id", "order_id", "date", "vt_symbol", "direction", "offset", "volume", "signed_volume"], float_precision="round_trip")
    for key, mapping in {
        "direction": {"\u591a": "Long", "\u7a7a": "Short", "Long": "Long", "Short": "Short"},
        "offset": {"\u5f00": "Open", "\u5e73": "Close", "\u5e73\u4eca": "CloseToday", "\u5e73\u6628": "CloseYesterday",
                   "Open": "Open", "Close": "Close", "CloseToday": "CloseToday", "CloseYesterday": "CloseYesterday"},
    }.items():
        trades[key] = trades[key].map(mapping)
        if trades[key].isna().any():
            raise RuntimeError("unknown_trade_enum")
    positions = pd.read_csv(SOURCE / "positions.csv", usecols=["date", "vt_symbol", "start_pos", "end_pos"], float_precision="round_trip")
    daily = pd.read_csv(SOURCE / "daily.csv", usecols=["date", "account_equity"], float_precision="round_trip")
    events, reconciliation = all_lifecycles(roots, candidates, trades, positions, daily.date.tolist(), receipt["contract_products"])
    unresolved = events.status.str.startswith("unresolved").any()
    room = headroom.objective_headroom(daily, events, min_train_events=60)
    if any(lifecycle.file_identity(Path(path)) != value for path, value in identities.items()):
        raise RuntimeError("source_drift")
    OUTPUT.mkdir(mode=0o700, parents=True)
    for name, frame in (("event_features", roots), ("event_lifecycles", events)):
        with (OUTPUT / f"{name}.csv").open("x") as stream:
            frame.to_csv(stream, index=False)
    summary = {"stage": "stage001_history_qualification", "status": "failed" if unresolved else "passed",
               "event_count": len(roots), "year_counts": roots.groupby(roots.decision_date.str[:4]).size().to_dict(),
               "direction_counts": roots.direction.value_counts().to_dict(), "product_count": int(roots.product_vt_symbol.nunique()),
               "feature_count": len(FEATURES), "feature_unique_counts": roots.loc[:, FEATURES].nunique().to_dict(),
               "dynamic_shared_event_count": len(dynamic), "dynamic_max_abs_error": difference,
               "lifecycle_status_counts": events.status.value_counts().to_dict(), "reconciliation": reconciliation,
               "objective_headroom": room, "source_identities": identities, "formal_identity": formal,
               "output_identities": {name: lifecycle.file_identity(OUTPUT / f"{name}.csv") for name in ["event_features", "event_lifecycles"]},
               "new_replay_count": 0, "new_label_count": 0, "model_fit_count": 0, "reviewer_started": False,
               "eligible_for_label_preregistration": bool(not unresolved and room["strict_full_drawdown_improvement_possible"])}
    with (OUTPUT / "summary.json").open("x") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: value for key, value in summary.items() if key not in ["source_identities", "formal_identity"]}), flush=True)
    return int(unresolved)


if __name__ == "__main__":
    raise SystemExit(main())
