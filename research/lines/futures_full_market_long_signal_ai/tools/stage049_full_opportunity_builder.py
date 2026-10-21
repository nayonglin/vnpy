"""Build Stage048 all-opportunity economic labels and maturity features once.

Synthetic callers use build_labels without I/O. Actual CLI requires a separately
frozen protocol SHA and a fresh output directory. It performs one accepted native
read, no model fitting, no cash-account replay, and no aggregate event PnL curve.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd


def file_binding(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


KERNEL_PATH = Path(__file__).with_name("stage042_cross_session_experiment.py")
KERNEL_AT_IMPORT = file_binding(KERNEL_PATH)
_spec = importlib.util.spec_from_file_location("stage049_accepted042", KERNEL_PATH)
ref = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ref)  # pure definitions only; no native read or strategy call

SCENARIOS = ("base", "stress")
PHASE = "after_all_source_close"
NUMERIC_FIELDS = [
    "N_u", "low20_u", "u_close", "lifecycle_index", "entry_index", "exit_index", "unknown_index",
    "last_path_index", "holding_source_days", "entry_reference", "exit_reference", "SL0", "entry_boundary",
    "exit_boundary", "terminal_mark", "R0_points", "cash_risk_unit", "multiplier", "round_lot", "tick_size",
    "gross_points_reference", "gross_R_reference", "policy_diagnostic_pnl",
]
OBJECT_FIELDS = [
    "family_id", "economics_status", "future_info_scope", "participation_state", "participation_known_date",
    "participation_known_phase", "label_state", "label_reason", "cancel_reason", "unknown_reason",
    "entry_date", "exit_date", "unknown_date", "label_known_date", "label_known_phase", "exit_reason",
]
for _s in SCENARIOS:
    NUMERIC_FIELDS.extend([
        f"net_pnl_{_s}_per_lot", f"net_R_{_s}", f"{_s}_entry_fill", f"{_s}_exit_fill",
        f"{_s}_entry_fee_per_lot", f"{_s}_exit_fee_per_lot", f"{_s}_total_fee_per_lot",
        f"{_s}_entry_slippage_per_lot", f"{_s}_exit_slippage_per_lot", f"{_s}_total_slippage_per_lot",
        f"{_s}_u_fee_roundtrip_per_lot", f"{_s}_u_slippage_roundtrip_per_lot", f"{_s}_u_risk_estimate_per_lot",
    ])


def build_labels(panel, market, dates, economics, *, scope_end=None):
    """One independent quote-policy request per ready row; all original rows survive.

    Array columns avoid a 400k-row list of large dictionaries. Epoch/day lookup
    and lifecycle indices are cached once, not rebuilt inside per-event paths.
    Unknown evidence is absorbing; known cancellation is not a trade target.
    """
    if panel.event_id.duplicated().any() or panel.duplicated(["product_id", "u_date"]).any():
        raise ValueError("duplicate mother identity")
    if list(dates) != sorted(set(dates)):
        raise ValueError("source calendar must be unique and ordered")
    lookup = {day: k for k, day in enumerate(dates)}
    u_indices = panel.u_date.map(lookup)
    if u_indices.isna().any():
        raise ValueError("mother date outside source calendar")
    end = int(u_indices.max()) if scope_end is None else lookup[scope_end] if isinstance(scope_end, str) else int(scope_end)
    if not 0 <= end < len(dates) or (u_indices > end).any():
        raise ValueError("invalid report end")
    n = len(panel)
    a = {name: np.full(n, np.nan, dtype=float) for name in NUMERIC_FIELDS}
    a.update({name: np.full(n, None, dtype=object) for name in OBJECT_FIELDS})
    a.update(sequence_index=np.arange(n, dtype=np.int64), u_index=u_indices.to_numpy(dtype=np.int32),
             D_index=u_indices.to_numpy(dtype=np.int32) + 1, history_run=np.zeros(n, dtype=np.int32),
             label_history_ready20=np.zeros(n, dtype=np.int8), filled=np.zeros(n, dtype=np.int8),
             trade_label_known=np.zeros(n, dtype=np.int8))
    references = {}
    for product, u, epoch in zip(panel.product_id, a["u_index"], panel.reference_epoch):
        if product not in references:
            references[product] = np.full(len(dates), None, dtype=object)
        references[product][u] = epoch or None
    date_array = np.asarray(dates, dtype="U10")
    expiry = {epoch: ref.lifecycle_index(e, epoch, date_array) for epoch, e in economics.items()}
    cache = {}
    for epoch, series in market.series.items():
        positions = np.full(len(dates), -1, dtype=np.int32)
        positions[series.days] = np.arange(len(series.days), dtype=np.int32)
        cache[epoch] = (series, positions)

    def cancel(i, reason, known):
        a["participation_state"][i] = "known_nonparticipation"
        a["label_state"][i] = "known_nonparticipation"
        a["cancel_reason"][i] = reason
        a["participation_known_date"][i] = dates[known]
        a["participation_known_phase"][i] = PHASE
        a["policy_diagnostic_pnl"][i] = 0.

    def unknown(i, state, reason, k):
        a["label_state"][i] = state
        a["unknown_reason"][i] = reason
        a["unknown_index"][i] = k
        a["unknown_date"][i] = dates[k]

    for i, row in enumerate(panel.itertuples(index=False)):
        u, D = int(a["u_index"][i]), int(a["D_index"][i])
        epoch, product = row.reference_epoch, row.product_id
        e = economics.get(epoch, {})
        a["family_id"][i] = ref.family(product)
        a["economics_status"][i] = e.get("economics_status", "unresolved_exact_epoch_metadata")
        a["future_info_scope"][i] = e.get("future_info_scope")
        a["participation_state"][i] = "not_history_ready"
        a["label_state"][i] = "not_history_ready"
        for field, key in (("multiplier", "contract_multiplier"), ("round_lot", "round_lot"), ("tick_size", "tick_size")):
            if ref.positive(e.get(key)):
                a[field][i] = float(e[key])
        entry = cache.get(epoch)
        if entry is None:
            a["label_reason"][i] = "no_accepted_u_reference_bar"
            continue
        series, positions = entry
        uj = int(positions[u])
        if uj < 0 or not series.valid[uj]:
            a["label_reason"][i] = "no_accepted_u_reference_bar"
            continue
        N, L20, run = float(series.N[uj]), float(series.low20[uj]), int(series.run[uj])
        C = float(series.values[uj, 3])
        a["N_u"][i], a["low20_u"][i], a["u_close"][i], a["history_run"][i] = N, L20, C, run
        ready = run >= 20 and ref.positive(N) and ref.positive(L20)
        a["label_history_ready20"][i] = int(ready)
        if not ready:
            a["label_reason"][i] = "insufficient_or_gap_history20"
            continue
        a["R0_points"][i] = 2. * N
        if not ref.qualified_economics(e):
            a["participation_state"][i] = "economics_unresolved"
            a["label_state"][i] = "input_or_economics_unresolved"
            a["label_reason"][i] = "instrument_economics_unqualified"
            continue
        mult = float(e["contract_multiplier"])
        risk = 2. * N * mult
        a["cash_risk_unit"][i] = risk
        a["lifecycle_index"][i] = expiry[epoch]
        try:
            for scenario in SCENARIOS:
                estimate = ref.unit_estimate(C, N, e, scenario)
                a[f"{scenario}_u_fee_roundtrip_per_lot"][i] = estimate["fee_roundtrip_per_lot"]
                a[f"{scenario}_u_slippage_roundtrip_per_lot"][i] = estimate["buy"]["slippage_per_lot"] + estimate["sell"]["slippage_per_lot"]
                a[f"{scenario}_u_risk_estimate_per_lot"][i] = estimate["risk_per_lot"]
        except ValueError:
            a["participation_state"][i] = "economics_unresolved"
            a["label_state"][i] = "input_or_economics_unresolved"
            a["label_reason"][i] = "unrepresentable_u_cost_quote"
            continue
        # A real next calendar day can be known ineligible before its quote is
        # observed. len(dates), however, is only a searchsorted sentinel and
        # cannot prove that an unrepresented future D has reached maturity.
        if D < len(dates) and D >= expiry[epoch]:
            cancel(i, "known_entry_ineligible_lifecycle", u)
            continue
        if D > end:
            a["participation_state"][i] = "not_yet_observable"
            a["label_state"][i] = "intent_right_censored"
            continue
        dj = int(positions[D])
        if dj < 0 or not series.valid[dj]:
            a["participation_state"][i] = "execution_unknown"
            unknown(i, "entry_execution_unknown", "missing_or_invalid_D_bar", D)
            continue
        F = float(series.values[dj, 0])
        SL0 = F - 2. * N
        a["entry_reference"][i], a["SL0"][i] = F, SL0
        if F <= L20:
            cancel(i, "stale_boundary_at_open", D)
            continue
        if SL0 <= 0:
            cancel(i, "invalid_initial_stop", D)
            continue
        try:
            buys = {s: ref.adverse_quote(F, "BUY", e, s) for s in SCENARIOS}
        except ValueError:
            a["participation_state"][i] = "economics_unresolved"
            a["label_state"][i] = "input_or_economics_unresolved"
            a["label_reason"][i] = "unrepresentable_entry_cost_quote"
            continue
        a["participation_state"][i] = "filled"
        a["participation_known_date"][i], a["participation_known_phase"][i] = dates[D], PHASE
        a["filled"][i] = 1
        a["entry_index"][i], a["entry_date"][i] = D, dates[D]
        B = ref.next_boundary(SL0, L20)
        a["entry_boundary"][i] = B
        for s in SCENARIOS:
            a[f"{s}_entry_fill"][i] = buys[s]["fill_price"]
            a[f"{s}_entry_fee_per_lot"][i] = buys[s]["fee_per_lot"]
            a[f"{s}_entry_slippage_per_lot"][i] = buys[s]["slippage_per_lot"]
        force = None
        for k in range(D, end + 1):
            j = int(positions[k])
            if j < 0 or not series.valid[j]:
                unknown(i, "path_or_execution_unknown", "missing_or_invalid_held_old_epoch_bar", k)
                break
            O, _, low, close, _ = series.values[j]
            reference, reason = ref.price_exit_reference(O, low, B, force)
            a["last_path_index"][i], a["holding_source_days"][i] = k, k - D + 1
            if reference is not None:
                try:
                    sells = {s: ref.adverse_quote(reference, "SELL", e, s) for s in SCENARIOS}
                except ValueError:
                    unknown(i, "input_or_economics_unresolved", "unrepresentable_exit_cost_quote", k)
                    break
                a["label_state"][i] = "closed_complete_bar_model"
                a["trade_label_known"][i] = 1
                a["exit_index"][i], a["exit_date"][i] = k, dates[k]
                a["label_known_date"][i], a["label_known_phase"][i] = dates[k], PHASE
                a["exit_reference"][i], a["exit_boundary"][i], a["exit_reason"][i] = reference, B, reason
                a["gross_points_reference"][i] = reference - F
                a["gross_R_reference"][i] = (reference - F) / (2. * N)
                for s in SCENARIOS:
                    buy, sell = buys[s], sells[s]
                    fee = buy["fee_per_lot"] + sell["fee_per_lot"]
                    slip = buy["slippage_per_lot"] + sell["slippage_per_lot"]
                    net = mult * (sell["fill_price"] - buy["fill_price"]) - fee
                    a[f"{s}_exit_fill"][i] = sell["fill_price"]
                    a[f"{s}_exit_fee_per_lot"][i] = sell["fee_per_lot"]
                    a[f"{s}_exit_slippage_per_lot"][i] = sell["slippage_per_lot"]
                    a[f"{s}_total_fee_per_lot"][i], a[f"{s}_total_slippage_per_lot"][i] = fee, slip
                    a[f"net_pnl_{s}_per_lot"][i], a[f"net_R_{s}"][i] = net, net / risk
                break
            a["terminal_mark"][i] = float(close)
            a["label_state"][i] = "open_right_censored"
            # Current-day low updates the boundary only for the following source day.
            B = ref.next_boundary(SL0, series.low20[j])
            force = ref.close_exit_request(epoch, references[product][k], k + 1, expiry[epoch])
    result = pd.concat([panel.reset_index(drop=True), pd.DataFrame(a)], axis=1)
    assert_label_integrity(result)
    return result


def assert_label_integrity(labels):
    closed = labels.label_state.eq("closed_complete_bar_model")
    nonpart = labels.participation_state.eq("known_nonparticipation")
    targets = [f"net_{kind}_{s}" if kind == "R" else f"net_pnl_{s}_per_lot" for kind in ("R", "pnl") for s in SCENARIOS]
    if labels.loc[~closed, targets].notna().any().any():
        raise AssertionError("nonclosed/unknown/cancelled trade received a target")
    if labels.loc[closed, targets].isna().any().any() or not labels.loc[closed, "filled"].eq(1).all():
        raise AssertionError("closed trade lacks paired economic target")
    if not labels.loc[nonpart, "policy_diagnostic_pnl"].eq(0.).all() or labels.loc[~nonpart, "policy_diagnostic_pnl"].notna().any():
        raise AssertionError("diagnostic cancellation zero leaked to trade/unknown policy states")
    if not labels.loc[closed, "exit_index"].ge(labels.loc[closed, "entry_index"]).all():
        raise AssertionError("exit before entry")
    if not labels.loc[closed, "entry_index"].eq(labels.loc[closed, "u_index"] + 1).all():
        raise AssertionError("entry is not strict next source date")
    if not labels.loc[closed, "label_known_date"].eq(labels.loc[closed, "exit_date"]).all():
        raise AssertionError("maturity date is not actual exit source date")


def load_protocol(path, expected_sha):
    bound = file_binding(path)
    if bound["sha256"] != expected_sha:
        raise ValueError("CLI protocol SHA does not match saved bytes")
    protocol = json.loads(Path(path).read_bytes())
    if protocol.get("schema") != "stage048_full_opportunity_build_v1":
        raise ValueError("not a frozen Stage048 build protocol")
    kernel = protocol["accepted_kernel"]
    if file_binding(KERNEL_PATH) != kernel or KERNEL_AT_IMPORT != kernel:
        raise ValueError("accepted042 kernel SHA/bytes/path differs")
    for key in ("design_document", "label_design", "feature_design", "statistical_design_review", "source_bindings", "accepted_panel_manifest"):
        ref.read_bound(protocol[key])
    policy = protocol["policy"]
    required = {"minimum_continuous_bars": 20, "N_period": 20, "stop_N": 2., "exit_lookback": 20,
                "entry_lookback": None, "take_profit": None, "maximum_holding_days": None,
                "occupancy_filter": False, "cash_filter": False, "target": "net_R_stress",
                "target_denominator": "2*N_u*exact_epoch_multiplier"}
    if any(policy[k] != value for k, value in required.items()):
        raise ValueError("label policy differs from the implemented fixed contract")
    for s in SCENARIOS:
        for internal, external in (("fee_min", "fee_min_per_lot_per_side"), ("fee_bps", "fee_notional_fraction"),
                                   ("slip_bps", "slip_price_fraction"), ("slip_ticks", "slip_ticks"),
                                   ("margin_floor", "vendor_margin_floor")):
            if ref.SCENARIOS[s][internal] != protocol["cost"][s][external]:
                raise ValueError(f"{s} {external} differs from accepted kernel cost scalar")
    authorization = protocol["authorization"]
    if any(authorization[k] != v for k, v in {"actual_builds": 1, "native_queries": 1, "new_cash_accounts": 0,
                                            "new_model_fits": 0, "downloads": 0, "production": False}.items()):
        raise ValueError("unsupported authorization scope")
    return protocol, bound


def _safe(value):
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def export_finite_audit(path, panel, labels, features, peers, market, dates, economics):
    """Only predeclared first-cause cases from arrays already read once."""
    choices = [
        ("seed20", labels.history_run.eq(20) & labels.label_history_ready20.eq(1)),
        ("gap_history", labels.history_run.between(1, 19) & labels.u_index.ge(20)),
        ("strict_D_missing", labels.label_state.eq("entry_execution_unknown")),
        ("stale_cancel", labels.cancel_reason.eq("stale_boundary_at_open")),
        ("entry_samebar_stop", labels.exit_index.eq(labels.entry_index) & labels.trade_label_known.eq(1)),
        ("later_boundary", labels.exit_index.gt(labels.entry_index) & labels.exit_reason.eq("stop_boundary")),
        ("gap_stop", labels.exit_reason.eq("gap_stop")),
        ("old_epoch_roll", labels.exit_reason.eq("liquidity_reference_changed")),
        ("observation_exit", labels.exit_reason.eq("observation_exit_requested")),
        ("lifecycle_exit", labels.exit_reason.eq("lifecycle_exit")),
        ("lifecycle_cancel", labels.cancel_reason.eq("known_entry_ineligible_lifecycle")),
        ("missing_absorbing", labels.label_state.eq("path_or_execution_unknown")),
        ("open_censor", labels.label_state.eq("open_right_censored")),
        ("intent_censor", labels.label_state.eq("intent_right_censored")),
        ("F_economics", labels.product_id.str.endswith("_F") & labels.label_history_ready20.eq(1)),
    ]
    cases = []

    def rows(epoch, begin, end):
        series = market.series.get(epoch)
        result = []
        for k in range(max(0, begin), min(end, len(dates) - 1) + 1):
            j = series.locate(k) if series is not None else None
            item = dict(source_index=k, date=dates[k], native_missing=j is None)
            if j is not None:
                item.update(valid=bool(series.valid[j]), **dict(zip(("open", "high", "low", "close", "volume"), series.values[j].tolist())))
            result.append(item)
        return result

    for kind, mask in choices:
        matches = np.flatnonzero(mask.to_numpy())
        if not len(matches):
            continue
        row = labels.iloc[int(matches[0])]
        u, run, epoch = int(row.u_index), int(row.history_run), row.reference_epoch
        final = int(row.exit_index) if pd.notna(row.exit_index) else int(row.unknown_index) if pd.notna(row.unknown_index) else int(row.last_path_index) if pd.notna(row.last_path_index) else min(u + 1, len(dates) - 1)
        cases.append(dict(kind=kind, event=row.to_dict(), economics=economics.get(epoch),
                          N_history=rows(epoch, u - run + 1, u), path=rows(epoch, u + 1, final),
                          reference_schedule=panel.loc[panel.product_id.eq(row.product_id) & panel.u_date.between(dates[u], dates[final]),
                                                       ["u_date", "reference_epoch", "status"]].to_dict("records")))
    q_cases = features.loc[features.q_missing.eq(0)].head(1)
    for row in q_cases.itertuples(index=False):
        u = int(row.u_index)
        selected = peers.loc[peers.event_id.eq(row.event_id)]
        members = list(dict.fromkeys([row.reference_epoch] + selected.peer_epoch.tolist()))
        cases.append(dict(kind="maturity_relation_first", feature=row._asdict(), mapping=selected.to_dict("records"),
                          native_pairs={epoch: rows(epoch, u - 1, u) for epoch in members}))
    payload = dict(schema="stage049_finite_native_case_slices_v1", raw_ohlc=True, reproducibility_required=False,
                   selection="first per predeclared cause, no outcome optimization", sql_queries=0, cases=cases)
    with gzip.GzipFile(filename=str(path), mode="xb", mtime=0) as stream:
        stream.write(json.dumps(_safe(payload), ensure_ascii=False, allow_nan=False).encode())
    return len(cases)


def _feature_module():
    path = Path(__file__).with_name("stage049_maturity_features.py")
    spec = importlib.util.spec_from_file_location("stage049_fixed_maturity_features", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def execute(args):
    out = Path(args.output).resolve()
    if out.exists():
        raise FileExistsError("refuse overwrite/automatic retry " + str(out))
    out.mkdir(parents=True, exist_ok=False)
    began, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    status, error, native_queries, completed_rows = "failed", None, 0, 0
    module_path = Path(__file__).with_name("stage049_maturity_features.py")
    tests_path = Path(__file__).with_name("test_stage049_full_opportunity_builder.py")
    feature_tests_path = Path(__file__).with_name("test_stage049_maturity_features.py")
    source_before = file_binding(__file__)
    feature_before = file_binding(module_path)
    ref.write_json(out / "actual_started.json", dict(status="started", started_at=began, fixture=False,
                   actual_start_count=1, native_queries_before=ref.NATIVE_QUERIES, source=source_before,
                   feature_module=feature_before, protocol_expected_sha256=args.protocol_sha256))
    try:
        protocol, protocol_binding = load_protocol(args.protocol, args.protocol_sha256)
        if ref.NATIVE_QUERIES:
            raise ValueError("actual process already consumed native input")
        ref.write_json(out / "protocol.json", protocol)
        ref.write_json(out / "input_bindings.json", {k: protocol[k] for k in
                       ("design_document", "label_design", "feature_design", "statistical_design_review", "accepted_kernel",
                        "source_bindings", "accepted_panel_manifest", "panel", "database", "calendar", "economic_projection")})
        module = _feature_module()
        panel, market, dates, economics, scope_dates, source_receipt = ref.load_all_inputs(protocol)
        native_queries = ref.NATIVE_QUERIES
        if native_queries != 1:
            raise AssertionError("expected exactly one native source query")
        ref.write_json(out / "source_read_receipt.json", source_receipt)
        scope = protocol["scope"]
        if len(panel) != scope["panel_rows"] or len(market.series) != scope["economic_exact_epochs"] + scope["economic_unresolved_epochs"]:
            raise ValueError("accepted full source scope differs")
        if source_receipt["native_contract_days"] != scope["accepted_contract_days"] or len(scope_dates) != scope["scope_source_dates"]:
            raise ValueError("accepted contract-day or report-date count differs")
        print(json.dumps(dict(phase="native_loaded_once", native_queries=native_queries,
                              native_contract_days=source_receipt["native_contract_days"], elapsed_seconds=time.monotonic() - clock)), flush=True)
        features, peers, feature_summary = module.build_features(panel, market, dates, economics)
        if features.event_id.tolist() != panel.event_id.tolist():
            raise AssertionError("feature identity/order changed")
        ref.write_table(out / "features_all.csv.gz", features, [])
        ref.write_table(out / "peer_mapping.csv.gz", peers, [])
        ref.write_json(out / "feature_summary.json", _safe(feature_summary))
        print(json.dumps(dict(phase="maturity_features_complete", rows=len(features), peer_rows=len(peers),
                              elapsed_seconds=time.monotonic() - clock)), flush=True)
        labels = build_labels(panel, market, dates, economics, scope_end=scope["end"])
        if labels.event_id.tolist() != panel.event_id.tolist():
            raise AssertionError("label identity/order changed")
        ref.write_table(out / "event_economic_labels.csv.gz", labels, [])
        interval_fields = ["sequence_index", "event_id", "product_id", "family_id", "reference_epoch", "u_date", "u_index", "D_index",
                           "label_history_ready20", "participation_state", "filled", "label_state", "entry_index", "entry_date",
                           "exit_index", "exit_date", "label_known_date", "label_known_phase", "unknown_index", "last_path_index"]
        ref.write_table(out / "dependency_intervals.csv.gz", labels[interval_fields], [])
        coverage = labels[["product_id", "family_id", "u_date", "label_state", "participation_state", "label_history_ready20", "filled", "trade_label_known"]].copy()
        coverage["u_year"] = coverage.u_date.str[:4]
        coverage["q_ready"] = features.q_missing.eq(0).to_numpy(dtype=int)
        grouped = coverage.groupby(["u_year", "product_id", "family_id", "label_state", "participation_state"], dropna=False).agg(
            rows=("u_date", "size"), history_ready20=("label_history_ready20", "sum"), filled=("filled", "sum"),
            trade_label_known=("trade_label_known", "sum"), q_ready=("q_ready", "sum")).reset_index()
        ref.write_table(out / "time_family_coverage.csv.gz", grouped, [])
        label_summary = dict(schema="stage049_complete_opportunity_economic_labels_v1", mother_rows=len(labels),
                             products=int(labels.product_id.nunique()), source_dates=int(labels.u_date.nunique()),
                             history_ready20=int(labels.label_history_ready20.sum()), filled=int(labels.filled.sum()),
                             complete_trade_labels=int(labels.trade_label_known.sum()),
                             label_states=dict(Counter(labels.label_state)), participation_states=dict(Counter(labels.participation_state)),
                             cancel_reasons=dict(Counter(labels.cancel_reason.dropna())), unknown_reasons=dict(Counter(labels.unknown_reason.dropna())),
                             exit_reasons=dict(Counter(labels.exit_reason.dropna())),
                             primary_target="net_R_stress", denominator="2*N_u*exact_epoch_multiplier",
                             targets_conditional_on_filled_complete=True, event_sum_is_not_account_equity=True,
                             no_global_future_dependent_training_weights=True, new_model_fits=0, new_cash_accounts=0,
                             audit_fields_not_automatic_X=["N_u", "low20_u", "u_close", "multiplier", "tick_size", "round_lot",
                                                          "cash_risk_unit", "*_u_fee_roundtrip_per_lot", "*_u_slippage_roundtrip_per_lot"],
                             future_outcome_fields_never_X=["entry_*", "exit_*", "label_*except_history_ready20", "net_*", "filled", "cancel_*", "unknown_*"],
                             limitations=protocol["limitations"], production_qualified=False)
        ref.write_json(out / "label_state_summary.json", _safe(label_summary))
        raw_dir = out / "excluded_raw_audit"
        raw_dir.mkdir()
        raw_path = raw_dir / "native_case_slices.json.gz"
        case_count = export_finite_audit(raw_path, panel, labels, features, peers, market, dates, economics)
        ref.assert_db_binding(protocol["database"])
        if file_binding(__file__) != source_before or file_binding(module_path) != feature_before:
            raise ValueError("builder/feature source changed during actual build")
        completed_rows, status = len(labels), "completed"
        print(json.dumps(dict(phase="all_labels_complete", rows=completed_rows, complete_trade_labels=label_summary["complete_trade_labels"],
                              finite_audit_cases=case_count, elapsed_seconds=time.monotonic() - clock)), flush=True)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        native_queries = ref.NATIVE_QUERIES
        ref.write_json(out / "actual_terminal.json", dict(status=status, started_at=began, finished_at=datetime.now(timezone.utc).isoformat(),
                       elapsed_seconds=time.monotonic() - clock, exit_code=0 if status == "completed" else 1, error=error,
                       actual_start_count=1, completed_actual_builds=int(status == "completed"), completed_label_rows=completed_rows,
                       native_source_queries=native_queries, actual_model_fit_calls=0, new_cash_accounts=0,
                       network_calls=0, fixture=False, python=sys.executable, source=source_before, feature_module=feature_before))
    roles = {
        "actual_started.json": "qualification_evidence", "actual_terminal.json": "qualification_evidence",
        "source_read_receipt.json": "qualification_evidence", "protocol.json": "feature_contract", "input_bindings.json": "feature_contract",
        "features_all.csv.gz": "feature_matrix", "peer_mapping.csv.gz": "normalized_peer_mapping",
        "event_economic_labels.csv.gz": "economic_event_labels", "dependency_intervals.csv.gz": "dependency_intervals",
        "time_family_coverage.csv.gz": "support_coverage", "label_state_summary.json": "decision_asset", "feature_summary.json": "decision_asset",
    }
    artifacts = [dict(file_binding(out / name), role=role, reproducibility_required=True, raw_ohlc=False) for name, role in roles.items()]
    manifest = dict(schema="stage049_full_opportunity_labels_and_maturity_features_v1", status=status,
                    source=source_before, tests=file_binding(tests_path), feature_module=feature_before, feature_tests=file_binding(feature_tests_path),
                    accepted_kernel=KERNEL_AT_IMPORT, protocol=protocol_binding, artifacts=artifacts,
                    excluded_raw_audit=dict(file_binding(raw_path), role="excluded_raw_audit", raw_ohlc=True, reproducibility_required=False),
                    mother_rows=completed_rows, native_source_queries=native_queries, actual_start_count=1,
                    counts=dict(parent_rows=len(panel), label_rows=len(labels), history_ready20=label_summary["history_ready20"],
                                filled=label_summary["filled"], complete_trade_labels=label_summary["complete_trade_labels"],
                                feature_rows=len(features), peer_mapping_rows=len(peers), scope_source_dates=len(scope_dates)),
                    completed_actual_builds=1, actual_model_fit_calls=0, new_cash_accounts=0,
                    economic_label_qualification="conditional_filled_complete_research_bar_model_only", production_qualified=False, goal_complete=False)
    ref.write_json(out / "manifest.json", manifest)
    return dict(status=status, output=str(out), mother_rows=completed_rows, native_source_queries=native_queries,
                actual_model_fit_calls=0, new_cash_accounts=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
