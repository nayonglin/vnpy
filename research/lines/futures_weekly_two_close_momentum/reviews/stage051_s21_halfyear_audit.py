"""Independently rebuild S21 and reconcile the removed zinc sleeve in every window."""
from collections import Counter
import json
from pathlib import Path

from stage040_s19_without_gold_audit import CAPITAL, FULL, HALF, LINE, TARGET, check_manifest, load_json, near, sha
from stage044_s19_daily_halfyear_audit import STARTS, STAGE041, control_path
from stage045_s19_weekly_shadow_filter_audit import completed_weeks
from stage046_s44_individual_2022_audit import table
from stage048_s26_full_audit import RESULT as STAGE048, TAIL_CERT, extend_raw_market, inherited_events
from stage049_s26_halfyear_audit import RESULT as STAGE049, check_values, replay_independently
from stage050_s22_halfyear_audit import RESULT as STAGE050

RESULT = LINE / "outputs/stage051_s21_halfyear_20261104"
PRIOR_CERT = LINE / "reviews/stage050_s22_halfyear_audit.json"
REMOVED = "zn.SHFE"
ADDITIONS = ("p.DCE", "ss.SHFE")
CONTROLS = ("s19", "s22", "s26")


def verify_window(row, start, control, performance, stress, dates, added_pnl):
    known = {name: value for name, value in control.items() if name.startswith(("s19_", "s22_", "s26_"))}
    known.update({f"s21_{key}": value for key, value in (performance | stress).items()})
    known.update(first_session=dates.iat[0], last_session=TARGET, days=len(dates))
    known.update({f"s21_added_pnl_{product}": value for product, value in added_pnl.items()})
    for arm in (*CONTROLS, "s21"):
        assert {f"{arm}_{key}" for key in ("equity", "net_pnl", "return_pct", "max_dd_pct", "deficit_days",
                                            "nonpositive_equity_days", "max_shortfall", "fills", "closed_cycles")} <= set(row.index)
    for field, actual in row.items():
        assert field in known, (start, field, "unexpected summary field")
        check_values(actual, known[field], (start, field))


def audit():
    folders = (RESULT, STAGE050, STAGE049, STAGE048, STAGE041, FULL, HALF)
    manifests = {folder.name: check_manifest(folder) for folder in folders}
    receipt = load_json(RESULT / "receipt.json")
    prior_receipt = load_json(STAGE050 / "receipt.json")
    base_config = load_json(FULL / "inputs.json")
    s22_config = load_json(STAGE050 / STARTS[0] / "inputs.json")
    prior_cert = load_json(PRIOR_CERT)
    assert prior_cert["verdict"] == "PASS_WITH_LIMITATIONS"
    assert prior_cert["manifest_sha256"] == sha(STAGE050 / "SHA256SUMS")
    assert load_json(STAGE049 / "receipt.json")["tail_admission_sha256"] == sha(TAIL_CERT)
    by_name = {folder.name: folder for folder in folders[1:]}
    for name, digest in receipt["manifests_sha256"].items():
        assert digest == sha(by_name[name] / "SHA256SUMS")
    assert receipt["manifests_sha256"][STAGE050.name] == sha(STAGE050 / "SHA256SUMS")
    assert receipt["stage050_audit_sha256"] == sha(PRIOR_CERT)
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage051_s21_halfyear.py")
    design = list((LINE / "stages").glob("*_stage051_*design.md"))
    assert len(design) == 1 and receipt["design_sha256"] == sha(design[0])
    assert receipt["engine_sha256"] == sha(LINE / "tools/run_weekly_portfolio.py")
    assert (receipt["starts"], receipt["attempted_runs"], receipt["completed_runs"], receipt["unknown_runs"]) == (STARTS, 24, 24, 0)
    assert receipt["cutoff"] == TARGET and receipt["capital"] == CAPITAL
    assert receipt["market_sha256"] == prior_receipt["market_sha256"] == s22_config["inputs_sha256"]
    pins = s22_config["inputs_sha256"] | s22_config["source_sha256"]
    assert all(sha(Path(name)) == digest for name, digest in pins.items())
    assert {path.name for path in RESULT.iterdir() if path.is_dir()} == set(STARTS)
    assert set(prior_receipt["added"]) == {*ADDITIONS, REMOVED}
    assert receipt["excluded"] == REMOVED and tuple(receipt["added"]) == ADDITIONS
    products = [product for product in s22_config["products"] if product != REMOVED]
    assert len(products) == 21 and products == receipt["products"] and "au.SHFE" in products
    assert set(products) - set(base_config["products"]) == set(ADDITIONS)
    assert set(s22_config["products"]) - set(products) == {REMOVED}

    market = extend_raw_market(load_json(TAIL_CERT))
    weeks = completed_weeks(market[1], market[4])
    control = table(STAGE050, "window_metrics").set_index("calendar_start", verify_integrity=True)
    combined = table(RESULT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    assert combined.index.tolist() == control.index.tolist() == STARTS
    proof_windows = {row["start"]: row for row in prior_cert["windows"]}
    totals, unchanged_s19, unchanged_s21 = Counter(), Counter(), Counter()
    windows = []
    for start in STARTS:
        folder, s19_folder, s22_folder = RESULT / start, control_path(start), STAGE050 / start
        config = load_json(folder / "inputs.json")
        assert config == {**s22_config, "start": start, "products": products}
        assert load_json(s19_folder / "inputs.json") == {**base_config, "start": start}
        assert load_json(s22_folder / "inputs.json") == {**s22_config, "start": start}
        unchanged_s19.update(inherited_events(folder, s19_folder, base_config["products"]))
        unchanged_s21.update(inherited_events(s22_folder, folder, products))
        performance, stress, counts, zero, worst, dates = replay_independently(folder, start, config, market, weeks)
        baseline = control.loc[start]
        assert baseline.first_session == dates.iat[0] and baseline.days == len(dates)
        by_product = table(folder, "cycles").groupby("product").net_pnl.sum()
        selected_pnl = {product: float(by_product.get(product, 0)) for product in ADDITIONS}
        verify_window(combined.loc[start], start, baseline, performance, stress, dates, selected_pnl)
        s22_cycles = table(s22_folder, "cycles")
        zinc_pnl = float(s22_cycles.loc[s22_cycles["product"].eq(REMOVED), "net_pnl"].sum())
        near(zinc_pnl, baseline[f"s22_added_pnl_{REMOVED}"])
        near(performance["net_pnl"] - baseline.s19_net_pnl, sum(selected_pnl.values()))
        near(baseline.s22_net_pnl - performance["net_pnl"], zinc_pnl)
        proof = proof_windows[start]
        for arm in CONTROLS:
            near(baseline[f"{arm}_equity"], proof[f"{arm}_equity"])
            near(baseline[f"{arm}_max_shortfall"], max(0, -proof[f"{arm}_worst_funding"]["free_equity"]))
            assert baseline[f"{arm}_deficit_days"] == proof[f"{arm}_deficit_days"]
            assert baseline[f"{arm}_nonpositive_equity_days"] == proof[f"{arm}_nonpositive_days"]
        totals.update(counts)
        row = dict(start=start, first_session=dates.iat[0], s21_equity=float(performance["equity"]),
                   s21_net_pnl=float(performance["net_pnl"]), s21_drawdown_pct=float(performance["max_dd_pct"]),
                   s21_deficit_days=performance["deficit_days"], s21_nonpositive_days=counts["nonpositive_days"],
                   s21_zero_equity_close_dates=zero, s21_worst_funding=worst,
                   added_net_pnl=selected_pnl, removed_zinc_net_pnl=zinc_pnl)
        for arm in CONTROLS:
            row[f"{arm}_equity"] = float(baseline[f"{arm}_equity"])
            row[f"{arm}_drawdown_pct"] = float(baseline[f"{arm}_max_dd_pct"])
            row[f"{arm}_deficit_days"] = int(baseline[f"{arm}_deficit_days"])
            row[f"{arm}_nonpositive_days"] = int(baseline[f"{arm}_nonpositive_equity_days"])
            row[f"{arm}_worst_funding"] = proof[f"{arm}_worst_funding"]
        windows.append(row)
        print(start, "S19/S21/S22", row["s19_equity"], row["s21_equity"], row["s22_equity"],
              "S21 funding gap days", row["s21_deficit_days"], flush=True)

    arms = ("s19", "s21", "s22", "s26")
    report = dict(
        verdict="PASS_WITH_LIMITATIONS", attempted=24, completed=len(windows), unknown=0,
        manifest_sha256=sha(RESULT / "SHA256SUMS"), manifest_entries=manifests, pinned_inputs=len(pins),
        products=products, additions=list(ADDITIONS), removed=REMOVED,
        checked_s21_rows=dict(totals), unchanged_original_s19_events=dict(unchanged_s19),
        unchanged_s21_projection_from_s22=dict(unchanged_s21),
        windows_with_deficit={arm: sum(row[f"{arm}_deficit_days"] > 0 for row in windows) for arm in arms},
        windows_with_nonpositive_equity={arm: sum(row[f"{arm}_nonpositive_days"] > 0 for row in windows) for arm in arms},
        higher_final_equity_s21={arm: sum(row["s21_equity"] > row[f"{arm}_equity"] for row in windows) for arm in CONTROLS},
        better_drawdown_s21={arm: sum(row["s21_drawdown_pct"] > row[f"{arm}_drawdown_pct"] for row in windows)
                             for arm in CONTROLS},
        windows=windows,
        limitations=[
            "Zinc removed after observing the historical results. Overlapping starts are not independent observations.",
            "One-lot theoretical fills continue through cash shortfalls and nonpositive equity.",
            "Percentage return metrics cease to be economically interpretable after crossing zero equity.",
            "Zero commissions, static margin and open-price proxies without a queue model.",
        ],
    )
    Path(__file__).with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print({key: value for key, value in report.items() if key != "windows"}, flush=True)


if __name__ == "__main__":
    audit()
