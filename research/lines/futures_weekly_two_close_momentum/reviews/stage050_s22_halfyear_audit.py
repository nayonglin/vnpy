"""Independently rebuild the S22 weekly books and audit all matched control rows."""
from collections import Counter
import json
from pathlib import Path

from stage040_s19_without_gold_audit import CAPITAL, FULL, HALF, LINE, TARGET, check_manifest, load_json, near, sha
from stage044_s19_daily_halfyear_audit import STARTS, STAGE041, control_path
from stage045_s19_weekly_shadow_filter_audit import completed_weeks
from stage046_s44_individual_2022_audit import RESULT as SOLO, table
from stage047_s26_2022_audit import RESULT as STAGE047
from stage048_s26_full_audit import RESULT as STAGE048, TAIL_CERT, extend_raw_market, inherited_events
from stage049_s26_halfyear_audit import RESULT as STAGE049, check_values, replay_independently

RESULT = LINE / "outputs/stage050_s22_halfyear_20261104"
STAGE049_CERT = LINE / "reviews/stage049_s26_halfyear_audit.json"
SOLO_CERT = LINE / "reviews/stage046_s44_individual_2022_audit.json"
EXPECTED = ("p.DCE", "ss.SHFE", "zn.SHFE")


def select_additions():
    former = load_json(STAGE047 / "receipt.json")["added"]
    assert len(set(former)) == 7
    metrics = table(SOLO, "product_metrics").set_index("product", verify_integrity=True)
    ranking = []
    for product in former:
        solo_path = SOLO / product
        cycles = table(solo_path, "cycles")
        total = float(cycles.net_pnl.sum())
        near(total, load_json(solo_path / "summary.json")["net_pnl"])
        near(total, metrics.at[product, "net_pnl"])
        ranking.append((product, total))
    ranking.sort(key=lambda entry: (-entry[1], entry[0]))
    top_three = tuple(product for product, _ in ranking[:3])
    assert top_three == EXPECTED
    return former, top_three, ranking


def verify_result_row(row, start, control, performance, stress, dates, added_pnl):
    known = {name: value for name, value in control.items() if name.startswith(("s19_", "s26_"))}
    known.update({f"s22_{key}": value for key, value in (performance | stress).items()})
    known.update(first_session=dates.iat[0], last_session=TARGET, days=len(dates))
    known.update({f"s22_added_pnl_{product}": value for product, value in added_pnl.items()})
    for arm in ("s19", "s22", "s26"):
        assert {f"{arm}_{key}" for key in ("equity", "net_pnl", "return_pct", "max_dd_pct", "deficit_days",
                                            "nonpositive_equity_days", "max_shortfall", "fills", "closed_cycles")} <= set(row.index)
    for field, actual in row.items():
        assert field in known, (start, field, "unexpected summary field")
        check_values(actual, known[field], (start, field))


def audit():
    folders = (RESULT, STAGE049, STAGE048, SOLO, STAGE047, STAGE041, FULL, HALF)
    manifests = {folder.name: check_manifest(folder) for folder in folders}
    receipt = load_json(RESULT / "receipt.json")
    stage049_receipt = load_json(STAGE049 / "receipt.json")
    base_config = load_json(FULL / "inputs.json")
    s26_config = load_json(STAGE049 / STARTS[0] / "inputs.json")
    control_cert = load_json(STAGE049_CERT)
    solo_cert = load_json(SOLO_CERT)
    assert control_cert["verdict"] == solo_cert["verdict"] == "PASS_WITH_LIMITATIONS"
    assert control_cert["manifest_sha256"] == sha(STAGE049 / "SHA256SUMS")
    assert solo_cert["manifest_sha256"] == sha(SOLO / "SHA256SUMS")
    assert stage049_receipt["tail_admission_sha256"] == sha(TAIL_CERT)
    assert receipt["manifests_sha256"] == {
        folder.name: sha(folder / "SHA256SUMS") for folder in (STAGE049, STAGE048, SOLO)
    }
    assert receipt["stage049_audit_sha256"] == sha(STAGE049_CERT)
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage050_s22_halfyear.py")
    design = list((LINE / "stages").glob("*_stage050_*design.md"))
    assert len(design) == 1 and receipt["design_sha256"] == sha(design[0])
    assert receipt["engine_sha256"] == sha(LINE / "tools/run_weekly_portfolio.py")
    assert (receipt["starts"], receipt["attempted_runs"], receipt["completed_runs"], receipt["unknown_runs"]) == (STARTS, 24, 24, 0)
    assert receipt["cutoff"] == TARGET and receipt["capital"] == CAPITAL
    assert receipt["market_sha256"] == stage049_receipt["market_sha256"] == s26_config["inputs_sha256"]
    pins = s26_config["inputs_sha256"] | s26_config["source_sha256"]
    assert all(sha(Path(name)) == digest for name, digest in pins.items())
    assert {path.name for path in RESULT.iterdir() if path.is_dir()} == set(STARTS)

    former, added, ranking = select_additions()
    assert set(added) == set(receipt["added"])
    products = sorted(set(base_config["products"]) | set(added))
    assert len(products) == 22 and products == receipt["products"] and "au.SHFE" in products
    excluded = sorted(set(former) - set(added))
    assert set(s26_config["products"]) - set(products) == set(excluded)
    market = extend_raw_market(load_json(TAIL_CERT))
    weeks = completed_weeks(market[1], market[4])
    control = table(STAGE049, "window_metrics").set_index("calendar_start", verify_integrity=True)
    combined = table(RESULT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    assert combined.index.tolist() == control.index.tolist() == STARTS
    proof_windows = {row["start"]: row for row in control_cert["windows"]}
    totals, unchanged_s19, unchanged_s22 = Counter(), Counter(), Counter()
    windows = []
    for start in STARTS:
        folder, s19_folder, s26_folder = RESULT / start, control_path(start), STAGE049 / start
        config = load_json(folder / "inputs.json")
        assert config == {**s26_config, "start": start, "products": products}
        assert load_json(s19_folder / "inputs.json") == {**base_config, "start": start}
        assert load_json(s26_folder / "inputs.json") == {**s26_config, "start": start}
        unchanged_s19.update(inherited_events(folder, s19_folder, base_config["products"]))
        unchanged_s22.update(inherited_events(s26_folder, folder, products))
        performance, stress, counts, zero, worst, dates = replay_independently(folder, start, config, market, weeks)
        baseline = control.loc[start]
        assert baseline.first_session == dates.iat[0] and baseline.days == len(dates)
        by_product = table(folder, "cycles").groupby("product").net_pnl.sum()
        selected_pnl = {product: float(by_product.get(product, 0)) for product in added}
        verify_result_row(combined.loc[start], start, baseline, performance, stress, dates, selected_pnl)
        removed_pnl = table(s26_folder, "cycles").groupby("product").net_pnl.sum().reindex(excluded, fill_value=0).sum()
        near(performance["net_pnl"] - baseline.s19_net_pnl, by_product.reindex(added, fill_value=0).sum())
        near(baseline.s26_net_pnl - performance["net_pnl"], removed_pnl)
        for arm in ("s19", "s26"):
            proof = proof_windows[start]
            near(baseline[f"{arm}_equity"], proof[f"{arm}_equity"])
            near(baseline[f"{arm}_max_shortfall"], max(0, -proof[f"{arm}_worst_funding"]["free_equity"]))
            assert baseline[f"{arm}_deficit_days"] == proof[f"{arm}_deficit_days"]
            assert baseline[f"{arm}_nonpositive_equity_days"] == proof[f"{arm}_nonpositive_days"]
        totals.update(counts)
        row = dict(start=start, first_session=dates.iat[0], s22_equity=float(performance["equity"]),
                   s22_net_pnl=float(performance["net_pnl"]), s22_drawdown_pct=float(performance["max_dd_pct"]),
                   s22_deficit_days=performance["deficit_days"], s22_nonpositive_days=counts["nonpositive_days"],
                   s22_zero_equity_close_dates=zero, s22_worst_funding=worst,
                   added_net_pnl=selected_pnl)
        for arm in ("s19", "s26"):
            row[f"{arm}_equity"] = float(baseline[f"{arm}_equity"])
            row[f"{arm}_drawdown_pct"] = float(baseline[f"{arm}_max_dd_pct"])
            row[f"{arm}_deficit_days"] = int(baseline[f"{arm}_deficit_days"])
            row[f"{arm}_nonpositive_days"] = int(baseline[f"{arm}_nonpositive_equity_days"])
            row[f"{arm}_worst_funding"] = proof_windows[start][f"{arm}_worst_funding"]
        windows.append(row)
        print(start, "S19/S22/S26", row["s19_equity"], row["s22_equity"], row["s26_equity"],
              "S22 funding gap days", row["s22_deficit_days"], flush=True)

    arms = ("s19", "s22", "s26")
    report = dict(
        verdict="PASS_WITH_LIMITATIONS", attempted=24, completed=len(windows), unknown=0,
        manifest_sha256=sha(RESULT / "SHA256SUMS"), manifest_entries=manifests, pinned_inputs=len(pins),
        addition_ranking_2022=ranking, products=products, additions=list(added),
        checked_s22_rows=dict(totals), unchanged_original_s19_events=dict(unchanged_s19),
        unchanged_s22_projection_from_s26=dict(unchanged_s22),
        windows_with_deficit={arm: sum(row[f"{arm}_deficit_days"] > 0 for row in windows) for arm in arms},
        windows_with_nonpositive_equity={arm: sum(row[f"{arm}_nonpositive_days"] > 0 for row in windows) for arm in arms},
        higher_final_equity_s22={arm: sum(row["s22_equity"] > row[f"{arm}_equity"] for row in windows)
                                 for arm in ("s19", "s26")},
        better_drawdown_s22={arm: sum(row["s22_drawdown_pct"] > row[f"{arm}_drawdown_pct"] for row in windows)
                             for arm in ("s19", "s26")},
        windows=windows,
        limitations=[
            "Selection uses retrospective 2022 results; half-year windows overlap.",
            "One-lot theoretical fills continue through cash shortfalls and nonpositive equity.",
            "Percentage return metrics cease to be economically interpretable after crossing zero equity.",
            "Zero commissions, static margin and open-price proxies without a queue model.",
        ],
    )
    Path(__file__).with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print({key: value for key, value in report.items() if key != "windows"}, flush=True)


if __name__ == "__main__":
    audit()
