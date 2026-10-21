"""Stage070 one full-mother NARROW label build with same-read OHLC proxy.

Synthetic helpers accept arrays; actual CLI requires exact root authorization.
WIDE simulator exists for tiny boundary fixtures only; actual references accepted049.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

_spec=importlib.util.spec_from_file_location('stage070_label_kernel',Path(__file__).with_name('stage070_policy_kernel.py'))
kernel=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(kernel)
ref=kernel.ref

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


def build_labels(panel, market, dates, economics, *, policy, scope_end=None):
    """One independent quote-policy request per ready row; all original rows survive.

    Array columns avoid a 400k-row list of large dictionaries. Epoch/day lookup
    and lifecycle indices are cached once, not rebuilt inside per-event paths.
    Unknown evidence is absorbing; known cancellation is not a trade target.
    """
    k_policy = kernel.policy_k(policy)
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
        a["R0_points"][i] = k_policy * N
        if not ref.qualified_economics(e):
            a["participation_state"][i] = "economics_unresolved"
            a["label_state"][i] = "input_or_economics_unresolved"
            a["label_reason"][i] = "instrument_economics_unqualified"
            continue
        mult = float(e["contract_multiplier"])
        risk = k_policy * N * mult
        a["cash_risk_unit"][i] = risk
        a["lifecycle_index"][i] = expiry[epoch]
        try:
            for scenario in SCENARIOS:
                estimate = kernel.unit_estimate(C, N, e, scenario, policy)
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
        SL0 = F - k_policy * N
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
                a["gross_R_reference"][i] = (reference - F) / (k_policy * N)
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
    result["policy"] = policy
    result["policy_k"] = k_policy
    for scenario in SCENARIOS:
        result[f"net_R_common2N_{scenario}"] = result[f"net_pnl_{scenario}_per_lot"] / (2. * result.N_u * result.multiplier)
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


def build_proxy(panel, market, dates, economics):
    """Raw same-epoch v=u-1 projection; no label/economics/settlement-mask filter."""
    lookup = {day: k for k, day in enumerate(dates)}
    rows = []
    for i, row in enumerate(panel.itertuples(index=False)):
        u = lookup[row.u_date]
        v = u - 1
        value = dict(sequence_index=i, event_id=row.event_id, product_id=row.product_id,
                     family_id=ref.family(row.product_id), u_date=row.u_date, u_index=u,
                     reference_epoch=row.reference_epoch, v_index=v, v_date=dates[v] if v >= 0 else None,
                     H_v=np.nan, L_v=np.nan, C_v=np.nan, N_v=np.nan, ohlc_proxy_raw=np.nan,
                     N_state="N_v_unavailable", proxy_state="no_strict_previous_source_day")
        if v >= 0:
            value["proxy_state"] = "missing_or_invalid_v_bar"
            series = market.series.get(row.reference_epoch)
            j = series.locate(v) if series is not None else None
            if j is not None:
                _, H, L, C, _ = series.values[j]
                value.update(H_v=float(H), L_v=float(L), C_v=float(C), N_v=float(series.N[j]))
                if series.valid[j]:
                    ready = series.run[j] >= 20 and ref.positive(series.N[j])
                    value["N_state"] = "N_v_ready20" if ready else "N_v_insufficient_or_gap_history20"
                    value["proxy_state"] = "valid_same_epoch_previous_source_day" if ready else "N_v_not_ready20"
                    if ready:
                        value["ohlc_proxy_raw"] = (C - (H + L + C) / 3.) / series.N[j]
        rows.append(value)
    result = pd.DataFrame(rows)
    if result.event_id.tolist() != panel.event_id.tolist():
        raise AssertionError("proxy mother order changed")
    return result


def read_table(binding):
    return pd.read_csv(io.BytesIO(ref.read_bound(binding)), compression="gzip", low_memory=False)


def execute(args):
    protocol, protocol_binding, authorization, authorization_binding = kernel.authorize(args, "labels")
    inputs = authorization["input_bindings"]
    if not {"market_protocol", "wide_labels", "wide_manifest"}.issubset(inputs):
        raise ValueError("labels require accepted market bridge and WIDE049 bindings")
    wide_manifest = json.loads(ref.read_bound(inputs["wide_manifest"]))
    if wide_manifest.get("status") != "completed" or wide_manifest.get("mother_rows") != 399252:
        raise ValueError("accepted049 complete full-mother manifest required")
    accepted_wide = [a for a in wide_manifest["artifacts"] if a.get("role") == "economic_event_labels"]
    if len(accepted_wide) != 1 or any(inputs["wide_labels"][k] != accepted_wide[0][k] for k in ("path", "bytes", "sha256")):
        raise ValueError("WIDE label binding not the accepted049 artifact")
    if ref.NATIVE_QUERIES:
        raise ValueError("process already consumed native read")
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    began, clock = datetime.now(timezone.utc).isoformat(), time.monotonic()
    source_before = kernel.source_bundle("labels")
    status, error, completed_rows = "failed", None, 0
    ref.write_json(out / "actual_started.json", dict(status="started", stage="labels", source_bundle=source_before,
                   protocol=protocol_binding, authorization=authorization_binding, started_at=began, fixture=False))
    try:
        panel, market, dates, economics, _, receipt, market_protocol = kernel.load_market_bridge(authorization)
        ref.write_json(out / "source_read_receipt.json", receipt)
        labels = build_labels(panel, market, dates, economics, policy="NARROW", scope_end=protocol["finance"]["windows"][0]["end"])
        proxy = build_proxy(panel, market, dates, economics)
        wide = read_table(inputs["wide_labels"])
        for col in ("event_id", "product_id", "u_date", "reference_epoch"):
            if not labels[col].fillna("").equals(wide[col].fillna("")):
                raise ValueError("NARROW/WIDE complete mother identity differs " + col)
        if len(labels) != 399252 or labels.product_id.nunique() != 98 or labels.exchange.nunique() != 6:
            raise ValueError("full six-exchange mother changed")
        ref.write_table(out / "labels_narrow.csv.gz", labels, [])
        ref.write_table(out / "ohlc_proxy.csv.gz", proxy, [])
        cross = pd.crosstab(wide.label_state.rename("wide_state"), labels.label_state.rename("narrow_state"), dropna=False).reset_index()
        ref.write_table(out / "policy_state_cross.csv.gz", cross, [])
        closed=labels.label_state.eq("closed_complete_bar_model")
        masks=[("entry_day_stop",closed&labels.exit_index.eq(labels.entry_index)),
               ("later_boundary",closed&labels.exit_index.gt(labels.entry_index)&labels.exit_reason.eq("stop_boundary")),
               ("gap_stop",closed&labels.exit_reason.eq("gap_stop")),
               ("old_epoch_exit",closed&labels.exit_reason.eq("liquidity_reference_changed")),
               ("lifecycle_exit",closed&labels.exit_reason.eq("lifecycle_exit")),
               ("missing",labels.label_state.isin(["entry_execution_unknown","path_or_execution_unknown"]))]
        selections=[]
        for kind,mask in masks:
            matches=labels.loc[mask]
            if len(matches):
                row=matches.iloc[0]
                selections.append(dict(kind=kind,policy="NARROW",event_id=row.event_id,
                                       date=row.exit_date if kind!="missing" else row.unknown_date))
        kernel.export_native_cases(out/"finite_native_cases.json.gz",selections,{"NARROW":labels},panel,market,dates,economics)
        ref.write_json(out / "label_summary.json", kernel.safe(dict(mother_rows=len(labels),
                       policy="NARROW", policy_k=.25, label_states=dict(Counter(labels.label_state)),
                       proxy_states=dict(Counter(proxy.proxy_state)), new_wide_labels=0,
                       target="own_policy_net_R_stress", common_diagnostic_denominator="2*N_u*M",
                       raw_proxy_unmasked=True, value_zero_is_valid=True,
                       no_joint_closed_filter=True, goal_complete=False, production_qualified=False)))
        ref.assert_db_binding(market_protocol["database"])
        if kernel.source_bundle("labels") != source_before:
            raise ValueError("source changed during label build")
        status, completed_rows = "completed", len(labels)
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        terminal = dict(status=status, stage="labels", started_at=began, finished_at=datetime.now(timezone.utc).isoformat(),
                        elapsed_seconds=time.monotonic() - clock, exit_code=0 if status == "completed" else 1,
                        error=error, completed_actual_builds=int(status == "completed"), completed_label_rows=completed_rows,
                        native_source_queries=ref.NATIVE_QUERIES, actual_model_fit_calls=0, new_cash_accounts=0,
                        downloads=0, whole_database_hashes=0, fixture=False, python=sys.executable)
        ref.write_json(out / "actual_terminal.json", terminal)
    artifacts = {name: ref.file_binding(out / name) for name in
                 ("labels_narrow.csv.gz", "ohlc_proxy.csv.gz", "policy_state_cross.csv.gz", "label_summary.json", "finite_native_cases.json.gz")}
    artifacts["finite_native_cases.json.gz"].update(raw_ohlc=True,reproducibility_required=False)
    manifest = dict(schema="stage070_narrow_labels_v1", status=status, mode="actual", protocol=protocol_binding,
                    authorization=authorization_binding, source_bundle=source_before, input_bindings=inputs,
                    mother_rows=completed_rows, products=98, exchanges=6, policy="NARROW", policy_k=.25,
                    artifacts=artifacts, terminal=ref.file_binding(out / "actual_terminal.json"),
                    labels_narrow=artifacts["labels_narrow.csv.gz"], ohlc_proxy=artifacts["ohlc_proxy.csv.gz"],
                    native_source_queries=ref.NATIVE_QUERIES, actual_model_fit_calls=0, new_cash_accounts=0,
                    new_wide_labels=0, production_qualified=False, goal_complete=False)
    ref.write_json(out / "manifest.json", manifest)
    return dict(status=status, output=str(out), mother_rows=completed_rows, native_source_queries=ref.NATIVE_QUERIES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--authorization", required=True)
    parser.add_argument("--output", required=True)
    print(json.dumps(execute(parser.parse_args()), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()


