"""Stage052 fixed maturity-information cash comparison; root executes once.

Import and synthetic helpers do no native SQL, fit or account replay. The actual
CLI accepts a complete Stage053 manifest and the frozen052 protocol, refuses an
existing output, reads native data once, and runs exactly twelve main accounts.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd


PROTOCOL_SHA = "968fa3505143587950d65fe27db0aa376916b0f005ffc6219b2af880a7e6974c"
ARMS = ("COMMON", "ALIGNED", "SHUFFLED")
KERNEL_PATH = Path(__file__).with_name("stage042_cross_session_experiment.py")
_spec = importlib.util.spec_from_file_location("stage054_accepted042", KERNEL_PATH)
ref = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ref)
SIGNAL_FIELDS = ["event_id", "product_id", "family_id", "u_date", "u_index", "reference_epoch",
                 "label_history_ready20", "N_u", "low20_u", "u_close", "history_run", "lifecycle_index"]
PANEL_FIELDS = ["event_id", "product_id", "exchange", "product", "u_date", "reference_epoch", "status", "planned_execution_date", "direction"]


def safe(value):
    if isinstance(value, dict):
        return {str(k): safe(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return safe(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    return value


def write_json(path, value):
    ref.write_json(path, safe(value))


def read_csv_bound(binding, **kwargs):
    return pd.read_csv(io.BytesIO(gzip.decompress(ref.read_bound(binding))), **kwargs)


def load_protocol(path, sha):
    binding = ref.file_binding(path)
    if binding["sha256"] != sha or sha != PROTOCOL_SHA:
        raise ValueError("frozen052 protocol SHA differs")
    protocol = json.loads(ref.read_bound(binding))
    if protocol["schema"] != "stage052_maturity_information_cash_v1" or protocol["arms"] != list(ARMS):
        raise ValueError("052 protocol identity differs")
    if protocol["cash_accounts_expected"] != 12 or protocol["actual_fit_calls_expected"] != 27:
        raise ValueError("052 finite budget differs")
    if protocol["scope"]["panel_rows"] != 399252 or protocol["scope"]["fallback_candidates_enabled"]:
        raise ValueError("full mother/fallback scope changed")
    for name in ("design_document", "accepted_kernel", "accepted_panel_manifest", "data_manifest", "data_review"):
        ref.read_bound(protocol[name])
    if ref.file_binding(KERNEL_PATH) != protocol["accepted_kernel"]:
        raise ValueError("accepted042 pure kernel bytes differ")
    constants = {"initial_capital": ref.INITIAL, "target_new_family_risk_fraction": ref.SINGLE_RISK,
        "total_initial_risk_fraction": ref.TOTAL_RISK, "margin_reserve_fraction": ref.MARGIN_CAP, "margin_buffer": ref.MARGIN_BUFFER}
    if any(protocol["cash"][k] != v for k,v in constants.items()):
        raise ValueError("cash constants differ from accepted042")
    for name, scenario in ref.SCENARIOS.items():
        for dest, source in [("fee_min", "fee_min_per_lot_per_side"), ("fee_bps", "fee_notional_fraction"),
            ("slip_bps", "slip_price_fraction"), ("slip_ticks", "slip_ticks"), ("margin_floor", "vendor_margin_floor")]:
            if scenario[dest] != protocol["cash"][name][source]:
                raise ValueError("cost/margin scenario differs")
    return protocol, binding


def load_fit_manifest(path, sha, protocol_binding):
    binding = ref.file_binding(path)
    if binding["sha256"] != sha:
        raise ValueError("053 manifest SHA differs")
    manifest = json.loads(ref.read_bound(binding))
    if manifest["schema"] != "stage053_maturity_information_fit_v1" or manifest["status"] != "completed":
        raise ValueError("053 must be a complete final manifest")
    if manifest["protocol"] != protocol_binding:
        raise ValueError("053/054 protocol binding mismatch")
    if manifest["actual_fit_calls_started"] != 27 or manifest["actual_fit_calls_completed"] != 27:
        raise ValueError("053 actual fit budget incomplete")
    terminal = json.loads(ref.read_bound(manifest["terminal"]))
    if terminal["status"] != "completed" or terminal["exit_code"] != 0:
        raise ValueError("053 terminal not successful")
    if terminal["actual_fit_calls_started"] != 27 or terminal["actual_fit_calls_completed"] != 27 or terminal["native_source_queries"] != 0 or terminal["new_cash_accounts"] != 0:
        raise ValueError("053 terminal actual counters differ from finite contract")
    return manifest, binding


def make_signals(labels, predictions, arm):
    """Only u fields enter execution; future label/participation states never do."""
    fields = list(dict.fromkeys([c for c in PANEL_FIELDS if c in labels] + SIGNAL_FIELDS))
    base = labels[fields].copy()
    if base.event_id.duplicated().any() or base.duplicated(["product_id", "u_date"]).any():
        raise ValueError("duplicate full mother identity")
    chosen = predictions.loc[predictions.arm.eq(arm)].copy()
    if chosen.event_id.duplicated().any():
        raise ValueError("duplicate prediction per event/arm")
    expected = base.loc[base.u_date.ge("2020-01-01"), "event_id"]
    if set(chosen.event_id) != set(expected):
        raise ValueError("predictions must retain the complete 2020+ mother")
    identity = chosen.merge(base[["event_id", "product_id", "family_id", "u_date", "u_index", "label_history_ready20"]], on="event_id", validate="one_to_one", suffixes=("", "_label"))
    for col in ("product_id", "family_id", "u_date", "u_index"):
        if not identity[col].eq(identity[col+"_label"]).all():
            raise ValueError("prediction/u identity mismatch " + col)
    if not identity.history_ready20.eq(identity.label_history_ready20).all():
        raise ValueError("prediction history20 differs from049")
    action = identity.label_history_ready20.eq(1) & np.isfinite(identity.score) & identity.score.gt(0)
    if "selected" in identity and not identity.selected.eq(action.astype(int)).all():
        raise ValueError("053 selected violates fixed action")
    payload = chosen[["event_id", "scope", "cutoff", "score"]].rename(columns={"scope": "prediction_scope"})
    result = base.merge(payload, on="event_id", how="left", sort=False, validate="one_to_one")
    result["potential"] = (result.label_history_ready20.eq(1) & np.isfinite(result.score) & result.score.gt(0)).astype(np.int8)
    result["arm"] = arm
    result["D_index"] = result.u_index + 1
    return result


def validate_held_groups(predictions):
    if set(predictions.scope) != {"holdout_0", "holdout_1"}:
        raise ValueError("held combined file must preserve both original scope fields")
    expected = predictions.family_id.map(lambda family: "holdout_" + str(int(hashlib.sha256(family.encode()).hexdigest(),16)%2))
    if not predictions.scope.eq(expected).all():
        raise ValueError("held scope does not match frozen family group")
    return predictions


def daily_log_growth(daily, initial):
    eq = daily.equity.to_numpy(dtype=float)
    path = np.r_[float(initial), eq]
    insolvent = daily.get("ever_insolvent", pd.Series(False, index=daily.index)).astype(bool).any()
    if insolvent or not np.isfinite(path).all() or np.any(path <= 0):
        return None, "survival_failure_no_log_repair"
    return np.diff(np.log(path)), "valid"


def circular_indices(n, repetitions=2000, block_length=252, seed=20261018):
    if n <= 0 or repetitions <= 0 or block_length <= 0:
        raise ValueError("nonpositive bootstrap dimensions")
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(repetitions, math.ceil(n / block_length)), dtype=np.int64)
    return ((starts[:, :, None] + np.arange(block_length)) % n).reshape(repetitions, -1)[:, :n].astype(np.int32)


def paired_log_statistics(accounts, initial, indices):
    dates = accounts["ALIGNED"].date.tolist()
    if any(accounts[arm].date.tolist() != dates for arm in ARMS):
        raise ValueError("paired daily dates differ")
    if indices.shape[1] != len(dates):
        raise ValueError("bootstrap index width differs")
    logs, states = {}, {}
    for arm in ARMS:
        logs[arm], states[arm] = daily_log_growth(accounts[arm], initial)
    results, distributions = {}, {}
    for reference in ("SHUFFLED", "COMMON"):
        name = "ALIGNED_minus_" + reference
        valid = states["ALIGNED"] == states[reference] == "valid"
        if valid:
            difference = logs["ALIGNED"] - logs[reference]
            distribution = difference[indices].mean(axis=1)
            low, high = np.quantile(distribution, [.025,.975])
            results[name] = dict(status="valid", mean_daily_log_difference=float(difference.mean()),
                cumulative_log_difference=float(difference.sum()), ci95_low=float(low), ci95_high=float(high), source_days=len(dates))
        else:
            distribution = np.full(len(indices), np.nan)
            results[name] = dict(status="survival_failure_no_log_repair", mean_daily_log_difference=None,
                cumulative_log_difference=None, ci95_low=None, ci95_high=None, source_days=len(dates))
        distributions[name] = distribution
    return results, pd.DataFrame(distributions)


def held_diagnostics(predictions, labels):
    """Conditional opportunity diagnostic, never a policy cash/return estimator."""
    keep = ["event_id", "label_state", "participation_state", "net_R_stress"]
    linked = predictions.merge(labels[keep], on="event_id", how="left", validate="many_to_one")
    if linked.label_state.isna().any():
        raise ValueError("held prediction absent from complete labels")
    linked["selected"] = (linked.history_ready20.eq(1) & np.isfinite(linked.score) & linked.score.gt(0)).astype(np.int8)
    closed = linked.label_state.eq("closed_complete_bar_model")
    cancel = linked.participation_state.eq("known_nonparticipation")
    if not np.isfinite(linked.loc[closed, "net_R_stress"]).all():
        raise ValueError("closed held outcome is nonfinite")
    linked["identified_domain"] = closed | cancel
    # Deliberately never fill the unknown/open outcome with zero.
    linked["diagnostic_outcome_R"] = np.where(cancel, 0., np.where(closed, linked.net_R_stress, np.nan))
    linked["masked_identified_R"] = linked.selected * linked.diagnostic_outcome_R
    reports, daily_tables = {}, []
    for scope, group in linked.groupby("scope", sort=True):
        if group.duplicated(["event_id", "arm"]).any():
            raise ValueError("duplicate held prediction")
        mother = {arm: set(group.loc[group.arm.eq(arm), "event_id"]) for arm in ARMS}
        if any(mother[a] != mother["ALIGNED"] for a in ARMS):
            raise ValueError("held arms do not share full mother")
        domain = group.loc[group.identified_domain].copy()
        domain_sets = {a: set(domain.loc[domain.arm.eq(a), "event_id"]) for a in ARMS}
        common = set.intersection(*domain_sets.values())
        domain = domain.loc[domain.event_id.isin(common)]
        daily = domain.groupby(["u_date", "arm"], sort=True).masked_identified_R.mean().unstack("arm").reindex(columns=ARMS)
        daily["ALIGNED_minus_SHUFFLED"] = daily.ALIGNED - daily.SHUFFLED
        daily["ALIGNED_minus_COMMON"] = daily.ALIGNED - daily.COMMON
        daily = daily.reset_index().assign(scope=scope)
        daily_tables.append(daily)
        counts = {}
        for arm, armgroup in group.groupby("arm", sort=True):
            selected = armgroup.selected.eq(1)
            counts[arm] = dict(full_mother_events=len(armgroup), finite_scores=int(np.isfinite(armgroup.score).sum()), selected=int(selected.sum()),
                selected_closed=int((selected & armgroup.label_state.eq("closed_complete_bar_model")).sum()),
                selected_known_nonparticipation=int((selected & armgroup.participation_state.eq("known_nonparticipation")).sum()),
                selected_unknown_or_open=int((selected & ~armgroup.identified_domain).sum()),
                selected_label_states=dict(Counter(armgroup.loc[selected, "label_state"])))
        unknown = group.loc[~group.identified_domain].pivot(index="event_id", columns="arm", values="selected")
        unknown_difference = int(unknown.ALIGNED.ne(unknown.SHUFFLED).sum()) if len(unknown) else 0
        point = float(daily.ALIGNED_minus_SHUFFLED.mean()) if len(daily) else None
        status = "unsupported" if point is not None and point <= 0 else "unknown" if point is None or unknown_difference else "supported"
        reports[scope] = dict(identified_common_events=len(common), identified_source_days=len(daily),
            ALIGNED_minus_SHUFFLED_daily_equal_mean_R=point,
            ALIGNED_minus_COMMON_daily_equal_mean_R=float(daily.ALIGNED_minus_COMMON.mean()) if len(daily) else None,
            unknown_differential_selected_events=unknown_difference, unknown_R_bounds=None, arms=counts, status=status,
            meaning="conditional_on_closed_or_known_nonparticipation_common_domain; equal u-day mean(mask*stress netR); not full opportunity value or cash")
    return dict(schema="stage054_held_conditional_diagnostic_v1", groups=reports, unknown_not_zero=True,
                full_policy_value_qualified=False, cash_return_qualified=False), pd.concat(daily_tables, ignore_index=True) if daily_tables else pd.DataFrame(), linked


def cash_diagnostics(book, initial):
    daily = pd.DataFrame(book["daily"])
    fills = pd.DataFrame(book["fills"])
    position_days = pd.DataFrame(book["position_days"])
    log, log_status = daily_log_growth(daily, initial)
    years = []
    previous = float(initial)
    for year, group in daily.groupby(daily.date.str[:4], sort=True):
        path = np.r_[previous, group.equity.to_numpy(float)]
        years.append(dict(year=year, partial=year=="2026", source_days=len(group), starting_equity=previous,
            ending_equity=float(path[-1]), cash_growth=float(path[-1]-previous), return_pct=(float(path[-1])/previous-1)*100 if previous>0 else None,
            max_drawdown_pct=float((path/np.maximum.accumulate(path)-1).min()*100),
            continuous_account_slice=True, independent_cold_start=False))
        previous=float(path[-1])
    # Exact family/day equity attribution: d(realized gross)-fees+d(unrealized).
    attributed = []
    if len(fills) or len(position_days):
        daily_f = pd.DataFrame(columns=["date","family_id","realized_gross","fee"])
        if len(fills):
            daily_f = fills.groupby(["date","family_id"])[["realized_gross","fee"]].sum().reset_index()
        unreal = pd.DataFrame(columns=["date","family_id","unrealized"])
        if len(position_days):
            unreal = position_days.groupby(["date","family_id"]).unrealized.sum().reset_index()
        families = sorted(set(daily_f.family_id) | set(unreal.family_id))
        for fam in families:
            f = daily_f.loc[daily_f.family_id.eq(fam)].set_index("date").reindex(daily.date, fill_value=0.)
            u = unreal.loc[unreal.family_id.eq(fam)].set_index("date").unrealized.reindex(daily.date, fill_value=0.)
            contribution = f.realized_gross.to_numpy(float)-f.fee.to_numpy(float)+np.diff(np.r_[0.,u.to_numpy(float)])
            for date, value, fee in zip(daily.date, contribution, f.fee):
                attributed.append(dict(date=date, year=date[:4], family_id=fam, net_equity_contribution=float(value), fee=float(fee)))
    attr = pd.DataFrame(attributed, columns=["date","year","family_id","net_equity_contribution","fee"])
    family_year = attr.groupby(["family_id","year"], sort=True)[["net_equity_contribution","fee"]].sum().reset_index() if len(attr) else attr.drop(columns=["date"])
    if len(attr):
        by_day = attr.groupby("date").net_equity_contribution.sum().reindex(daily.date, fill_value=0.)
        residual = float(np.max(np.abs(by_day.to_numpy()-np.diff(np.r_[initial,daily.equity.to_numpy()]))))
        if residual > 1e-5:
            raise AssertionError("family/day equity attribution does not reconcile")
    else:
        residual = float(abs(daily.equity.iloc[-1]-initial))
    concentration=[]
    for year, group in family_year.groupby("year", sort=True):
        values=group.net_equity_contribution
        wins=group.loc[values.gt(0)].sort_values("net_equity_contribution", ascending=False)
        losses=group.loc[values.lt(0)].sort_values("net_equity_contribution")
        win_total=float(wins.net_equity_contribution.sum());loss_total=float(-losses.net_equity_contribution.sum())
        concentration.append(dict(year=year, gross_positive_contributions=win_total, gross_negative_contributions=loss_total,
            largest_winning_family=None if wins.empty else wins.iloc[0].family_id,
            largest_winner_share=None if not win_total else float(wins.iloc[0].net_equity_contribution/win_total),
            top5_winner_share=None if not win_total else float(wins.head(5).net_equity_contribution.sum()/win_total),
            largest_losing_family=None if losses.empty else losses.iloc[0].family_id,
            largest_loser_share=None if not loss_total else float(-losses.iloc[0].net_equity_contribution/loss_total)))
    gap=None
    if len(fills):
        g=fills.loc[fills.reason.eq("gap_stop")].copy()
        if len(g):
            g["gap_net_fill_pnl"]=g.realized_gross-g.fee
            gap=safe(g.sort_values("gap_net_fill_pnl").iloc[0].to_dict())
    return dict(log_status=log_status, cumulative_log_growth=None if log is None else float(log.sum()),
        annual_slices=years, family_year_concentration=concentration, attribution_max_abs_error=residual,
        worst_gap_stop_fill=gap, stale_days=int(daily.stale_positions.gt(0).sum()),
        max_stale_notional=float(daily.stale_notional.max()), minimum_stale_zero_equity=float(daily.stale_zero_equity.min()),
        minimum_all_open_zero_equity=float(daily.unresolved_zero_equity.min()),
        unresolved_zero_is_scenario_not_universal_bound=True), family_year


def point_comparisons(summaries, daily_accounts, initial):
    rows=[]
    for scenario in ("base","stress"):
        for window in ("primary_2020","cold_2023"):
            for reference in ("SHUFFLED","COMMON"):
                a=summaries[("ALIGNED",scenario,window)];b=summaries[(reference,scenario,window)]
                al,ast=daily_log_growth(daily_accounts[("ALIGNED",scenario,window)],initial)
                bl,bst=daily_log_growth(daily_accounts[(reference,scenario,window)],initial)
                rows.append(dict(scenario=scenario,window_id=window,contrast="ALIGNED_minus_"+reference,
                    cumulative_log_growth_difference=float(al.sum()-bl.sum()) if ast==bst=="valid" else None,
                    return_percentage_point_difference=a["total_return_pct"]-b["total_return_pct"],
                    drawdown_percentage_point_difference=a["max_drawdown_pct"]-b["max_drawdown_pct"],
                    survival_failure=ast!="valid" or bst!="valid",
                    all_open_zero_ending_equity_difference=a["all_open_long_zero_scenario_equity"]-b["all_open_long_zero_scenario_equity"]))
    return rows


def continuation_conditions(summaries, points, bootstrap, held):
    primary=[r for r in points if r["scenario"]=="base" and r["window_id"]=="primary_2020"]
    first=all(r["ci95_low"] is not None and r["ci95_low"]>0 for r in bootstrap.values()) and all(
        not r["survival_failure"] and r["return_percentage_point_difference"]>0 and r["drawdown_percentage_point_difference"]>=0 for r in primary)
    stress=summaries[("ALIGNED","stress","primary_2020")]
    cold=[r for r in points if r["window_id"]=="cold_2023"]
    second=not stress["ever_insolvent"] and stress["total_return_pct"]>0 and all(
        not r["survival_failure"] and r["cumulative_log_growth_difference"]>0 and r["drawdown_percentage_point_difference"]>=0 for r in cold)
    # A differential unresolved long exposure has no accepted finite payoff
    # bound. Alternative zero-value scenarios are disclosed rather than used to
    # alter sizing or repaired into a confidence interval.
    uncertain_primary=any(r["all_open_zero_ending_equity_difference"]<=0 for r in primary)
    uncertain_second=stress["all_open_long_zero_scenario_equity"]<=stress["initial_capital"] or any(r["all_open_zero_ending_equity_difference"]<=0 for r in cold)
    groups=held["groups"]
    third="unsupported" if any(g["status"]=="unsupported" for g in groups.values()) else "supported" if len(groups)==2 and all(g["status"]=="supported" for g in groups.values()) else "unknown"
    return [dict(condition=1,status="unknown" if first and uncertain_primary else "supported" if first else "unsupported", nominal_pass=bool(first),
        reason="both main2020 base paired log CI lower>0 plus return up and DD not worse; unresolved-zero scenario disclosed"),
        dict(condition=2,status="unknown" if second and uncertain_second else "supported" if second else "unsupported",nominal_pass=bool(second),
        reason="ALIGNED primary stress self-positive/survives; both cold2023 costs positive increments and DD not worse; zero-value sensitivity disclosed"),
        dict(condition=3,status=third,reason="both family-held identified common-domain daily mask*stressR positive; differential selected unknown has no finite R bound; conditional diagnostic only")]


class NativeCases:
    """First predeclared causes only, extracted from the single loaded Market."""
    def __init__(self,labels,market,dates):
        self.labels=labels.set_index("event_id");self.market=market;self.dates=dates;self.seen=set();self.cases=[]

    def add(self,kind,event_id,day=None):
        if kind in self.seen or event_id not in self.labels.index:
            return
        row=self.labels.loc[event_id];u=int(row.u_index);epoch=row.reference_epoch
        indices=range(max(0,u-int(row.history_run)+1),min(len(self.dates),u+2))
        if day is not None:
            k=int(np.searchsorted(self.dates,day));indices=sorted(set(indices)|set(range(max(0,k-2),min(len(self.dates),k+2))))
        bars=[]
        series=self.market.series.get(epoch)
        for k in indices:
            j=series.locate(k) if series is not None else None
            bars.append(dict(date=self.dates[k],native_missing=True) if j is None else dict(date=self.dates[k],native_missing=False,
                valid_positive_volume=bool(series.valid[j]),**{name:safe(v) for name,v in zip(("open","high","low","close","volume"),series.values[j])}))
        self.cases.append(dict(kind=kind,event_id=event_id,epoch=epoch,u_date=row.u_date,history_run=int(row.history_run),
            complete_contiguous_warmup=True,N_u=safe(row.N_u),low20_u=safe(row.low20_u),bars=bars));self.seen.add(kind)

    def export(self,path):
        raw=json.dumps(safe(dict(schema="stage054_first_native_cases_v1",raw_ohlc=True,reproducibility_required=False,
            sql_queries=0,selection="first cause in fixed account iteration; no result tuning",cases=self.cases)),ensure_ascii=False,allow_nan=False).encode()
        with gzip.GzipFile(filename=str(path),mode="xb",mtime=0) as stream:
            stream.write(raw)


def execute(args):
    out=Path(args.output).resolve()
    if out.exists():
        raise FileExistsError("refuse overwrite/automatic rerun " + str(out))
    protocol,protocol_binding=load_protocol(args.protocol,args.protocol_sha256)
    fit,fit_binding=load_fit_manifest(args.fit_manifest,args.fit_manifest_sha256,protocol_binding)
    out.mkdir(parents=True,exist_ok=False)
    began=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
    started=computed=completed=0;status="failed";error=None;summary_map={};daily_accounts={};audit=None
    native_before=ref.NATIVE_QUERIES
    write_json(out/"actual_started.json",dict(started_at=began,source=ref.file_binding(__file__),protocol=protocol_binding,fit_manifest=fit_binding,
        authorized_cash_accounts=12,authorized_native_SQL=1,new_model_fits=0,fixture=False))
    try:
        write_json(out/"protocol.json",protocol)
        write_json(out/"input_bindings.json",dict(protocol=protocol_binding,fit_manifest=fit_binding,labels=protocol["labels"],
            predictions=fit["predictions"],kernel=protocol["accepted_kernel"],database=protocol["database"],calendar=protocol["calendar"],economic_projection=protocol["economic_projection"]))
        main=read_csv_bound(fit["predictions"]["main"],keep_default_na=False,na_values=[""])
        held_predictions=read_csv_bound(fit["predictions"]["holdout_combined"],keep_default_na=False,na_values=[""])
        labels=read_csv_bound(protocol["labels"],keep_default_na=False,na_values=[""],usecols=list(dict.fromkeys(PANEL_FIELDS+SIGNAL_FIELDS+["label_state","participation_state","net_R_stress"])))
        labels["reference_epoch"]=labels.reference_epoch.fillna("")
        for key,frame in (("main",main),("holdout_combined",held_predictions)):
            if len(frame)!=161014*3 or set(frame.arm)!=set(ARMS) or frame.duplicated(["event_id","arm"]).any():
                raise ValueError("complete053 prediction scope mismatch " + key)
        if not main.scope.eq("main").all():
            raise ValueError("prediction scope mismatch")
        validate_held_groups(held_predictions)
        # Validate all action adapters before consuming the single SQL allowance.
        signals_by_arm={arm:make_signals(labels,main,arm) for arm in ARMS}
        for arm in ARMS:
            make_signals(labels,held_predictions,arm)
        held,held_daily,held_linkage=held_diagnostics(held_predictions,labels)
        write_json(out/"held_conditional_diagnostic.json",held)
        ref.write_table(out/"held_identified_daily.csv.gz",held_daily,[])
        ref.write_table(out/"held_full_score_linkage.csv.gz",held_linkage,[])
        panel,market,dates,economics,scope_dates,source_receipt=ref.load_all_inputs(protocol)
        if len(labels)!=399252:
            raise ValueError("049 mother incomplete")
        identity=panel.merge(labels[PANEL_FIELDS],on="event_id",how="outer",validate="one_to_one",suffixes=("_panel","_049"),indicator=True)
        if not identity._merge.eq("both").all() or any(not identity[c+"_panel"].eq(identity[c+"_049"].fillna("")).all() for c in PANEL_FIELDS if c!="event_id"):
            raise ValueError("panel/049 original identity/reference changed")
        write_json(out/"source_read_receipt.json",source_receipt)
        audit=NativeCases(labels,market,dates)
        for arm in ARMS:
            signal=signals_by_arm[arm]
            ref.write_table(out/("signals_"+arm+".csv.gz"),signal,[])
            chosen=signal.loc[signal.potential.eq(1)].sort_values(["u_index","event_id"])
            if len(chosen):
                audit.add("first_selected_"+arm,chosen.event_id.iloc[0])
        write_json(out/"signal_summary.json",dict(mother_rows_per_arm=399252,prediction_rows_per_arm=161014,
            action="history_ready20 and finite score>0; no future mask",arms={a:dict(potentials=int(s.potential.sum()),finite_scores=int(np.isfinite(s.score).sum())) for a,s in signals_by_arm.items()},
            no_2019_pseudo_predictions=True,full_reference_rows_preserved=True))
        for arm in ARMS:
            signals=signals_by_arm[arm];prepared=ref.organize(signals)
            for scenario in protocol["cash_scenarios"]:
                for window in protocol["cash_windows"]:
                    start=int(np.searchsorted(dates,window["start"]));end=int(np.searchsorted(dates,window["end"],side="right"))-1
                    account_id=arm+"__"+scenario+"__"+window["id"];started+=1
                    print(json.dumps(dict(phase="cash_account_started",account_id=account_id,started_research_cash_accounts=started)),flush=True)
                    book=ref.run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,ref.INITIAL,prepared);computed+=1
                    directory=out/"cash"/account_id;directory.mkdir(parents=True)
                    for name,columns in [("fills",["account_id","event_id","date","side","qty","fee"]),("daily",["account_id","date","equity"]),
                        ("budgets",["account_id","event_id","u_date","execution_date","qty_cap","D_qty","D_state"]),
                        ("position_days",["account_id","event_id","date","qty","mark"]),("closed_episodes",["account_id","event_id","net_pnl"]),
                        ("open_episodes",["account_id","event_id","state","qty"])]:
                        for row in book[name]:
                            row.update(account_id=account_id,window_id=window["id"],scenario=scenario,arm=arm)
                        ref.write_table(directory/(name+".csv.gz"),book[name],columns)
                    diagnostics,family_year=cash_diagnostics(book,ref.INITIAL)
                    summary=dict(book["summary"],account_id=account_id,arm=arm,scenario=scenario,window_id=window["id"],requested_start=window["start"],requested_end=window["end"],
                        source_start=dates[start],source_end=dates[end],source_dates=end-start+1,mark="native_close_not_settlement",fee_margin_specs="static_vendor_snapshot_fixed_scenario",
                        diagnostics=diagnostics)
                    write_json(directory/"summary.json",summary)
                    ref.write_table(directory/"family_year_contributions.csv.gz",family_year,[])
                    daily=pd.DataFrame(book["daily"]);logs,log_status=daily_log_growth(daily,ref.INITIAL)
                    daily_log=daily[["date","equity"]].copy();daily_log["daily_log_growth"]=np.nan if logs is None else logs;daily_log["status"]=log_status
                    ref.write_table(directory/"daily_log_growth.csv.gz",daily_log,[])
                    summary_map[(arm,scenario,window["id"])]=summary;daily_accounts[(arm,scenario,window["id"])]=daily
                    for fill in book["fills"]:
                        if fill["side"]=="SELL" and fill["reason"] in ("gap_stop","research_deferred_liquidation","risk_margin_joint_reduction","liquidity_reference_changed","lifecycle_exit"):
                            audit.add("cash_"+fill["reason"],fill["event_id"],fill["date"])
                    completed+=1
                    print(json.dumps(dict(phase="cash_account_complete",account_id=account_id,completed_research_cash_accounts=completed,
                        ending_equity=summary["ending_equity"],closed_trades=summary["closed_trades"],elapsed_seconds=time.monotonic()-clock)),flush=True)
        if (started,computed,completed)!=(12,12,12) or ref.NATIVE_QUERIES-native_before!=1:
            raise AssertionError("finite actual cash/SQL budget differs")
        primary={a:daily_accounts[(a,"base","primary_2020")] for a in ARMS}
        config=protocol["bootstrap"]
        indices=circular_indices(len(primary["ALIGNED"]),config["repetitions"],config["block_length_source_days"],config["seed"])
        np.save(out/"bootstrap_indices.npy",indices,allow_pickle=False)
        bootstrap,distribution=paired_log_statistics(primary,ref.INITIAL,indices)
        distribution.insert(0,"replicate",np.arange(len(distribution),dtype=int))
        ref.write_table(out/"paired_bootstrap_distribution.csv.gz",distribution,[])
        write_json(out/"paired_bootstrap.json",dict(config=config,indices=ref.file_binding(out/"bootstrap_indices.npy"),
            indices_array_sha256=hashlib.sha256(indices.tobytes(order="C")).hexdigest(),contrasts=bootstrap,
            source_dates=primary["ALIGNED"].date.tolist(),same_indices_all_contrasts=True,
            interpretation="2000 resamples are not independent markets; six complete years and research selection limit inference"))
        points=point_comparisons(summary_map,daily_accounts,ref.INITIAL)
        write_json(out/"point_comparisons.json",points)
        conditions=continuation_conditions(summary_map,points,bootstrap,held)
        write_json(out/"continuation_conditions.json",dict(conditions=conditions,goal_complete=False,production_qualified=False,
            narrow_stop_or_increased_bet_qualified=False,information_candidate_only=True))
        write_json(out/"cash_summary.json",dict(accounts=list(summary_map.values()),independent_cold_start_accounts=12,
            annual_slices_are_not_new_accounts=True,model_fits=0,production_qualified=False))
        pd.DataFrame([{k:v for k,v in s.items() if k!="diagnostics"} for s in summary_map.values()]).to_csv(out/"cash_summary.csv",index=False)
        (out/"excluded_raw_audit").mkdir()
        audit.export(out/"excluded_raw_audit/native_case_slices.json.gz")
        ref.assert_db_binding(protocol["database"]);status="completed"
    except BaseException as exc:
        error=f"{type(exc).__name__}: {exc}"
        raise
    finally:
        write_json(out/"actual_terminal.json",dict(status=status,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,
            exit_code=0 if status=="completed" else 1,error=error,actual_model_fit_calls=0,started_research_cash_accounts=started,
            computed_research_cash_accounts=computed,completed_research_cash_accounts=completed,native_source_queries=ref.NATIVE_QUERIES-native_before,
            fixture=False,python=sys.executable,numpy=np.__version__,pandas=pd.__version__,source=ref.file_binding(__file__)))
        files=[]
        for path in sorted(out.rglob("*")):
            if path.is_file() and "excluded_raw_audit" not in path.parts and path.name!="manifest.json":
                files.append(dict(ref.file_binding(path),raw_ohlc=False,reproducibility_required=True,
                    role="qualification_evidence" if path.name in ("actual_started.json","actual_terminal.json","source_read_receipt.json") else "decision_asset"))
        excluded=out/"excluded_raw_audit/native_case_slices.json.gz"
        write_json(out/"manifest.json",dict(schema="stage054_maturity_cash_comparison_v1",status=status,protocol=protocol_binding,fit_manifest=fit_binding,
            source=ref.file_binding(__file__),tests=ref.file_binding(Path(__file__).with_name("test_stage054_maturity_cash_compare.py")),
            terminal=ref.file_binding(out/"actual_terminal.json"),artifacts=files,
            excluded_raw_audit=dict(ref.file_binding(excluded),raw_ohlc=True,reproducibility_required=False,role="external_ignored_raw_audit") if excluded.exists() else None,
            started_research_cash_accounts=started,computed_research_cash_accounts=computed,completed_research_cash_accounts=completed,
            native_source_queries=ref.NATIVE_QUERIES-native_before,actual_model_fit_calls=0,production_qualified=False,goal_complete=False))
    return dict(status=status,output=str(out),completed_research_cash_accounts=completed,native_source_queries=ref.NATIVE_QUERIES-native_before,actual_model_fit_calls=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ("protocol","protocol-sha256","fit-manifest","fit-manifest-sha256","output"):
        parser.add_argument("--"+flag,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False))


if __name__=="__main__":
    main()
