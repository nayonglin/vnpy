"""Independent bounded067 output/069 design receipt; no source replay or fit.

One physical read and one CSV parse of the saved projection.  The accepted049
feature table supplies mother identities and a same-epoch lagged N/C check.
No author module is imported, and no SQL/H5/raw CSV or model is opened.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import time
import traceback

import numpy as np
import pandas as pd

LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "outputs/stage072_joint_independent_review/source_bounded"
P67 = LINE / "outputs/stage067_settlement_source_projection"
P69 = LINE / "outputs/stage069_settlement_narrow_joint_protocol"
EXPECTED = {
    P69 / "protocol.json": "0418566cd9b624fb5a985448b3b0d4c94dbef56280feffd49bce09e1c5bf2dde",
    LINE / "stages/20261018_1628_stage069_settlement_narrow_joint_protocol.md": "09bfa91e95b854a346ad20f59ea837739d4d037e277ba108d8e782a40e6d583d",
    P67 / "experiment/manifest.json": "75e63071fa5d90c27d6fd54acd278b80c523bba1ef6236c2848b889d05496303",
    P67 / "experiment/actual_terminal.json": "fb572fc86a54b1bf3e36d20ca3efff8fea705cd8761395717def6f34ffd42c32",
    P67 / "actual_root_handoff.json": "3687e0291e07757dfe6e1e1771db592112ff6e5371b4c315c2ec6b120522eea8",
}
IDENTITY = ["sequence_index", "event_id", "product_id", "family_id", "u_date", "reference_epoch"]
RULES = {"historical_family_reconstruction_not_full_vintage", "family_default_assumption_no_primary_rule_bound"}


def binding(path, raw=None):
    path = Path(path).resolve()
    if raw is None:
        raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def safe(value):
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(x) for x in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def write(name, value):
    (OUT / name).write_text(json.dumps(safe(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    write("actual_started.json", {"started_at": datetime.now(timezone.utc).isoformat(), "bounded_source_review_startups": 1})
    checks = {}
    bindings = []

    def require(name, condition, detail=None):
        checks[name] = {"pass": bool(condition), "detail": detail}
        if not condition:
            raise AssertionError(name + ": " + str(detail))

    try:
        raw_small = {}
        for path, expected in EXPECTED.items():
            raw = path.read_bytes()
            b = binding(path, raw)
            require("SHA:" + path.name + ":" + path.parent.name, b["sha256"] == expected, b)
            bindings.append(b)
            raw_small[str(path)] = raw
        manifest = json.loads(raw_small[str(P67 / "experiment/manifest.json")])
        protocol = json.loads(raw_small[str(P69 / "protocol.json")])
        terminal = json.loads(raw_small[str(P67 / "experiment/actual_terminal.json")])
        handoff = json.loads(raw_small[str(P67 / "actual_root_handoff.json")])
        require("source_complete_once_no_finance", terminal["completed"] and terminal["source_projection_runs_completed"] == 1
                and terminal["native_source_queries"] == 1 and terminal["model_fits"] == terminal["cash_replays"] == terminal["labels_built"] == terminal["downloads"] == 0)
        require("source_process_exit0_one_start", handoff["process_receipt"]["exit_code"] == 0
                and handoff["process_receipt"]["actual_starts"] == 1 and handoff["process_receipt"]["auto_retries"] == 0)
        raw_artifacts = {}
        for item in manifest["artifacts"]:
            path = Path(item["path"])
            raw = path.read_bytes()
            b = binding(path, raw)
            require("artifact:" + path.name, b == {k: item[k] for k in ("path", "bytes", "sha256")}, b)
            bindings.append(b)
            if path.name in {"protocol.json", "settlement_projection.csv.gz", "family_year_coverage.csv"}:
                raw_artifacts[path.name] = raw
        source_protocol = json.loads(raw_artifacts["protocol.json"])
        require("source_code_identity", manifest["script_sha256"] == handoff["code_sha256"] == source_protocol["source_sha256"])
        require("069_science_not_execution_authorization", protocol["status"] == "science_frozen_implementation_not_actual_authorization")
        require("069_exact_12fit_24cash", protocol["learner"]["fit_calls_once"] == 12 and protocol["finance"]["cash_accounts_once"] == 24)
        require("069_forward_disjoint_6x161014", protocol["learner"]["prediction_clock"] == "disjoint_forward_blocks_cutoff_to_next_cutoff"
                and protocol["learner"]["predictions_per_arm_policy"] == 161014 and protocol["learner"]["predictions_total"] == 6*161014)
        require("069_same_common_units_own_policy_targets", protocol["input"]["keep_common_X_2N_units_for_both_policies"] is True
                and protocol["learner"]["target"] == "own_policy_net_R_stress")
        require("069_fixed_risk_and_two_stops", [protocol["policies"][p]["initial_stop_N"] for p in ("WIDE", "NARROW")] == [2., .25]
                and [protocol["finance"][k] for k in ("single_risk", "total_risk", "margin_budget")] == [.0025, .02, .25])

        mother_raw = Path(source_protocol["mother"]["path"]).read_bytes()
        mb = binding(source_protocol["mother"]["path"], mother_raw)
        require("accepted_mother_binding", mb == source_protocol["mother"], mb)
        bindings.append(mb)
        mother = pd.read_csv(io.BytesIO(mother_raw), compression="gzip", usecols=IDENTITY+["normalizer"], dtype=str, keep_default_na=False)
        calendar_raw = Path(source_protocol["calendar"]["path"]).read_bytes()
        cb = binding(source_protocol["calendar"]["path"], calendar_raw)
        require("accepted_calendar_binding", cb == source_protocol["calendar"], cb)
        bindings.append(cb)
        cal = np.load(io.BytesIO(calendar_raw), allow_pickle=False)
        if cal.dtype.kind in "iu":
            dates = [f"{int(v):08d}"[:4] + "-" + f"{int(v):08d}"[4:6] + "-" + f"{int(v):08d}"[6:] for v in cal]
        elif cal.dtype.kind == "M":
            dates = cal.astype("datetime64[D]").astype(str).tolist()
        else:
            raise ValueError("unsupported calendar dtype")
        require("calendar_order", dates == sorted(set(dates)))
        lookup = {d: k for k, d in enumerate(dates)}
        columns = set(IDENTITY + ["u_index", "v_index", "v_date", "projection_state", "value_observed", "source_route", "ohlc_relation",
            "candidate_quote_epoch", "candidate_quote_date", "accepted_C_v", "C_v", "S_v", "N_v", "N_history_run", "N_state",
            "close_minus_settlement_v", "benchmark_family", "rule_state", "rule_primary_bound", "lifecycle_state", "feature_available",
            "training_accepted", "strict_pit_accepted", "available_at", "availability_basis", "source_price_unit"])
        # This is the sole CSV parse of the saved projection; its compressed bytes were read once above.
        frame = pd.read_csv(io.BytesIO(raw_artifacts["settlement_projection.csv.gz"]), compression="gzip", dtype=str, keep_default_na=False,
                            usecols=lambda name: name in columns)
        require("required_projection_columns", columns <= set(frame.columns), sorted(columns-set(frame.columns)))
        n = len(frame)
        require("complete_mother_identity_and_order", n == 399252 and frame[IDENTITY].equals(mother[IDENTITY]))
        require("unique_full_market_identity", frame.event_id.nunique() == n and frame.product_id.nunique() == 98
                and frame.family_id.nunique() == 95 and frame.product_id.str.split(".").str[0].nunique() == 6
                and not frame.duplicated(["product_id", "u_date"]).any())
        require("family_and_sequence", frame.family_id.equals(frame.product_id.str.removesuffix("_F"))
                and np.array_equal(pd.to_numeric(frame.sequence_index).to_numpy(), np.arange(n)))
        ui = frame.u_date.map(lookup)
        vi = ui - 1
        require("strict_calendar_lag", ui.notna().all() and np.array_equal(ui.to_numpy(), pd.to_numeric(frame.u_index).to_numpy())
                and np.array_equal(vi.to_numpy(), pd.to_numeric(frame.v_index).to_numpy())
                and frame.v_date.tolist() == [dates[k] if k >= 0 else "" for k in vi])
        for flag in ("feature_available", "training_accepted", "strict_pit_accepted"):
            require("original_flag_zero:"+flag, pd.to_numeric(frame[flag]).eq(0).all())
        require("no_false_exact_availability_clock", frame.available_at.eq("").all()
                and frame.availability_basis.eq("historical_reconstruction_one_source_day_lag_not_release_verified").all())
        reference = frame.reference_epoch.ne("")
        observed = frame.projection_state.eq("observed_historical_reconstruction")
        numeric = {name: pd.to_numeric(frame[name], errors="coerce") for name in ("C_v", "S_v", "N_v", "N_history_run", "accepted_C_v", "close_minus_settlement_v")}
        positive = np.ones(n, dtype=bool)
        for name in ("C_v", "S_v", "N_v"):
            positive &= np.isfinite(numeric[name].to_numpy()) & numeric[name].gt(0).to_numpy()
        nr = np.isfinite(numeric["N_v"]) & numeric["N_v"].gt(0) & numeric["N_history_run"].ge(20)
        require("N_state_uses_positive_N_and_history20", frame.N_state.eq("N_v_ready20").equals(nr))
        require("observed_flag_exactly_matches_state", pd.to_numeric(frame.value_observed).eq(1).equals(observed)
                and pd.to_numeric(frame.value_observed).isin([0, 1]).all())
        identity = frame.candidate_quote_epoch.eq(frame.reference_epoch) & frame.candidate_quote_date.eq(frame.v_date)
        ohlc = frame.ohlc_relation.eq("equal_with_fixed_absolute_tolerance_1e-8")
        require("observed_identity_ohlc_lifecycle_rule", (identity & ohlc & frame.lifecycle_state.eq("before_vendor_final_boundary")
                & frame.benchmark_family.ne("unknown") & frame.rule_state.isin(RULES))[observed].all())
        c_error = abs(numeric["C_v"]-numeric["accepted_C_v"])
        compared_c = ohlc & np.isfinite(numeric["C_v"])
        # A missing fallback row may retain the already-compared original OHLC status;
        # its candidate C is absent and it remains unknown, so do not fabricate a C.
        require("observed_C_S_finite_positive", (np.isfinite(numeric["C_v"]) & numeric["C_v"].gt(0)
                & np.isfinite(numeric["S_v"]) & numeric["S_v"].gt(0))[observed].all())
        require("compared_available_C_matches_accepted_native", c_error[compared_c].le(1e-8).all(),
                {"rows": int(compared_c.sum()), "relation_rows_without_current_candidate_C": int((ohlc & ~np.isfinite(numeric["C_v"])).sum()), "max_abs": float(c_error[compared_c].max())})
        d_error = abs(numeric["close_minus_settlement_v"]-(numeric["C_v"]-numeric["S_v"]))
        require("observed_difference_arithmetic", np.isfinite(d_error[observed]).all() and d_error[observed].le(1e-9).all(), {"max_abs": float(d_error[observed].max())})
        require("unknown_does_not_get_difference_zero", frame.loc[~observed, "close_minus_settlement_v"].eq("").all())
        require("no_identity_or_ohlc_conflict", not frame.projection_state.isin(["source_identity_or_date_conflict", "source_ohlc_conflict"]).any())
        require("source_summary_counts", dict(Counter(frame.projection_state)) == handoff["state_counts"]
                and dict(Counter(frame.source_route)) == handoff["route_counts"] and dict(Counter(frame.rule_state)) == handoff["rule_counts"]
                and int(reference.sum()) == 212852 and int(observed.sum()) == 207849)
        require("no_epoch_state_preserved", frame.projection_state.eq("no_reference_epoch").equals(~reference))

        # Independent consistency with accepted049 N/C where the same real epoch was the prior-day representative.
        old = mother[["product_id", "u_date", "reference_epoch", "normalizer"]].rename(columns={"u_date": "v_date", "reference_epoch": "prior_epoch"})
        lagged = frame[["sequence_index", "product_id", "v_date", "reference_epoch"]].merge(old, how="left", on=["product_id", "v_date"], sort=False)
        require("lagged_N_check_preserves_order", lagged.sequence_index.tolist() == frame.sequence_index.tolist())
        norm = pd.to_numeric(lagged.normalizer, errors="coerce")
        check_N = lagged.prior_epoch.eq(frame.reference_epoch) & reference & norm.gt(0) & np.isfinite(norm) & np.isfinite(numeric["accepted_C_v"])
        n_error = abs(numeric["N_v"] - norm*numeric["accepted_C_v"])
        require("N_consistent_with_accepted049_lagged_normalizer", check_N.sum() > 0
                and np.isfinite(n_error[check_N]).all() and (n_error[check_N] <= 1e-8+1e-12*abs(numeric["N_v"][check_N])).all(),
                {"same_epoch_prior_representative_rows": int(check_N.sum()), "max_abs_N_error": float(n_error[check_N].max())})

        mask = observed & pd.to_numeric(frame.value_observed).eq(1) & nr & positive & identity & ohlc \
            & frame.lifecycle_state.eq("before_vendor_final_boundary") & frame.benchmark_family.ne("unknown") & frame.rule_state.isin(RULES)
        scalar = (numeric["C_v"]-numeric["S_v"])/numeric["N_v"]
        require("research_mask_finite_scalar", np.isfinite(scalar[mask]).all())
        require("research_mask_does_not_change_original_flags", pd.to_numeric(frame.training_accepted).eq(0).all()
                and pd.to_numeric(frame.feature_available).eq(0).all())
        totals = {"mother_rows": n, "reference_rows": int(reference.sum()), "observed_rows": int(observed.sum()),
            "observed_pct_full_mother": 100*observed.sum()/n, "observed_pct_reference": 100*observed.sum()/reference.sum(),
            "N_ready20_rows": int(nr.sum()), "observed_N_ready20_rows": int((observed & nr).sum()),
            "research_mask_rows": int(mask.sum()), "research_mask_zero_scalar_rows": int((mask & scalar.eq(0)).sum()),
            "research_mask_2020plus_rows": int((mask & frame.u_date.ge("2020-01-01")).sum()),
            "state_counts": dict(Counter(frame.projection_state)), "mask_rule_counts": dict(Counter(frame.loc[mask, "rule_state"])),
            "mask_benchmark_counts": dict(Counter(frame.loc[mask, "benchmark_family"]))}
        grid = pd.DataFrame({"family_id": frame.family_id, "exchange": frame.product_id.str.split(".").str[0], "year": frame.u_date.str[:4],
            "mother_rows": 1, "reference_rows": reference.astype(int), "observed_rows": observed.astype(int), "N_ready20_rows": nr.astype(int),
            "research_mask_rows": mask.astype(int), "research_zero_scalar_rows": (mask & scalar.eq(0)).astype(int)})
        family_year = grid.groupby(["family_id", "exchange", "year"], sort=True).sum().reset_index()
        require("full_family_year_denominator", len(family_year) == 1615 and int(family_year.mother_rows.sum()) == n)
        prior_coverage = pd.read_csv(io.BytesIO(raw_artifacts["family_year_coverage.csv"]), dtype={"year": str})
        require("source_family_year_counts_match_independently", family_year[["family_id", "year", "mother_rows", "observed_rows"]].rename(columns={"observed_rows": "value_observed"}).equals(
            prior_coverage[["family_id", "year", "mother_rows", "value_observed"]]))
        family_year.to_csv(OUT / "mask_family_year.csv", index=False)
        grid.groupby(["exchange", "year"], sort=True).sum(numeric_only=True).reset_index().to_csv(OUT / "mask_exchange_year.csv", index=False)
        grid.groupby("year", sort=True).sum(numeric_only=True).reset_index().to_csv(OUT / "mask_annual.csv", index=False)
        mask_frame = frame[IDENTITY+["v_date", "projection_state", "rule_state"]].copy()
        mask_frame["research_mask_069"] = mask.astype(np.int8)
        # This is a separate research mask, never an overwrite of the067 acceptance flags.
        mask_frame.to_csv(OUT / "research_mask.csv.gz", index=False, compression="gzip")
        write("checks.json", checks)
        write("mask_summary.json", totals)
        receipt = {"schema": "stage072_bounded_source_design_review_v1", "completed": True,
            "C": 0, "I": 0, "scope": "069 bounded static design and067 saved full projection only; not root source acceptance or financial-result review",
            "input_bindings": bindings, "reviewer_source": binding(__file__), "checks_count": len(checks), "summary": totals,
            "independence": {"author_module_imports": 0, "projection_physical_reads": 1, "projection_csv_parses": 1,
                "mother_identity_reads": 1, "native_sql": 0, "raw_csv_or_h5_reads": 0, "fit": 0, "cash": 0, "downloads": 0,
                "old_suite_runs": 0, "original_source_flags_changed": False},
            "limitations": ["H/L/source-liquidity and full N recurrence inherit accepted source/kernel; no fresh native reconstruction",
                "same-epoch prior representative N independently crosschecked with accepted049 N/C; nonmatching epochs retain accepted source scope",
                "historical rule defaults and revisions are research assumptions, not first-release PIT or broker execution qualification"],
            "root_authorization_issued": False, "financial_results_accepted": False}
        receipt["artifacts"] = [binding(p) for p in sorted(OUT.iterdir()) if p.is_file()]
        write("review_receipt.json", receipt)
        write("actual_terminal.json", {"completed": True, "exit_code": 0, "bounded_source_review_startups": 1,
            "bounded_source_reviews_completed": 1, "elapsed_seconds": time.monotonic()-start, "fit": 0, "cash": 0, "native_sql": 0, "downloads": 0})
        print(json.dumps(safe({"completed": True, "C": 0, "I": 0, "checks": len(checks), "summary": totals}), ensure_ascii=False), flush=True)
    except Exception as error:
        write("checks_first_failure.json", checks)
        write("actual_terminal.json", {"completed": False, "exit_code": 1, "bounded_source_review_startups": 1,
            "bounded_source_reviews_completed": 0, "elapsed_seconds": time.monotonic()-start, "error": str(error), "traceback": traceback.format_exc(),
            "fit": 0, "cash": 0, "native_sql": 0, "downloads": 0})
        raise


if __name__ == "__main__":
    main()
