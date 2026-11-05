"""Independently rebuild both arms of every Stage049 half-year cold start."""
from collections import Counter
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from stage040_s19_without_gold_audit import CAPITAL, FULL, HALF, LINE, TARGET, check_manifest, load_json, near, sha
from stage044_s19_daily_halfyear_audit import STARTS, STAGE041, control_path, financial_metrics
from stage045_s19_weekly_shadow_filter_audit import completed_weeks
import stage046_s44_individual_2022_audit as independent_weekly
from stage048_s26_full_audit import RESULT as STAGE048, TAIL_CERT, extend_raw_market, inherited_events
from stage048_s26_tail_audit import ADDED

RESULT = LINE / "outputs/stage049_s26_halfyear_20261104"
STAGE048_CERT = LINE / "reviews/stage048_s26_full_audit.json"
TABLE = independent_weekly.table


def check_values(actual, expected, label):
    if expected is None:
        assert actual == "" or actual is None, (label, actual)
    elif isinstance(expected, str):
        assert actual == expected, (label, actual, expected)
    else:
        near(float(actual), expected)


def replay_independently(folder, start, config, market, weeks):
    with patch.object(independent_weekly, "END", TARGET):
        marks, opening, cycles, pending, conditional, branches, delayed = independent_weekly.reconcile(
            folder, start, config, *market, *weeks)
    performance, counts, exact_zero = financial_metrics(folder, marks, opening, pending)
    daily = TABLE(folder, "daily")
    fills = TABLE(folder, "fills")
    assert daily.date.iat[0] >= start and daily.date.iat[-1] == TARGET
    assert (daily.iloc[0][["equity", "cash", "positions", "margin"]] == [CAPITAL, CAPITAL, 0, 0]).all()
    assert fills.date.min() > daily.date.iat[0] and fills.signal_day.min() >= daily.date.iat[0]
    assert not pending and not conditional
    assert not TABLE(folder, "gaps").date.eq(TARGET).any() and fills.volume.eq(1).all()
    closing_free = (marks.equity - marks.margin).round(8)
    open_free = opening.free_equity.round(8)
    min_open = opening.loc[open_free.idxmin()].to_dict()
    min_close = daily.loc[closing_free.idxmin(), ["date", "equity", "margin", "positions"]].to_dict()
    min_close.update(free_equity=float(closing_free.min()), reason="close_mark")
    min_open["free_equity"] = float(open_free.min())
    worst = min((min_open, min_close), key=lambda item: item["free_equity"])
    for key in ("equity", "margin"):
        worst[key] = round(float(worst[key]), 8)
    position_count = int(marks.positions.iat[-1])
    stress = dict(
        nonpositive_days=counts["nonpositive_days"], nonpositive_equity_days=counts["nonpositive_days"],
        minimum_equity=min(marks.equity.min(), opening.equity.min()), min_equity=min(marks.equity.min(), opening.equity.min()),
        minimum_opening_equity=opening.equity.min(), minimum_open_equity=opening.equity.min(),
        max_opening_positions=int(opening.positions.max()), max_open_positions=int(opening.positions.max()),
        max_positions=int(marks.positions.max()), open_positions=position_count,
        minimum_free_equity=min(closing_free.min(), open_free.min()), min_free_equity=min(closing_free.min(), open_free.min()),
        max_close_margin_pct=100 * (marks.margin / marks.equity.where(marks.equity.gt(0))).max(),
        opening_snapshots=len(opening), peak_opening_margin=opening.margin.max(),
    )
    return performance, stress, counts, exact_zero, worst, daily.date


def check_aggregate_row(row, start, date, s19, s26, s19_stress, s26_stress, added_pnl):
    shared = {
        "first_session": date.iat[0], "last_session": TARGET, "days": len(date),
        "pnl_difference": added_pnl,
        "return_difference_pp": s26["return_pct"] - s19["return_pct"],
        "drawdown_difference_pp": s26["max_dd_pct"] - s19["max_dd_pct"],
    }
    full = shared | {f"s19_{key}": value for key, value in (s19 | s19_stress).items()}
    full.update({f"s26_{key}": value for key, value in (s26 | s26_stress).items()})
    assert {"first_session", "last_session", "days"} <= set(row.index)
    for arm in ("s19", "s26"):
        assert {f"{arm}_{key}" for key in ("equity", "net_pnl", "return_pct", "max_dd_pct", "deficit_days",
                                            "max_shortfall", "fills", "closed_cycles")} <= set(row.index)
    for field, value in row.items():
        assert field in full, (start, field, "unrecognized aggregate field")
        check_values(value, full[field], (start, field))


def audit():
    folders = (RESULT, STAGE048, STAGE041, FULL, HALF)
    manifest_entries = {folder.name: check_manifest(folder) for folder in folders}
    receipt = load_json(RESULT / "receipt.json")
    stage048_config = load_json(STAGE048 / "inputs.json")
    stage037_config = load_json(FULL / "inputs.json")
    prior_audit = load_json(STAGE048_CERT)
    assert prior_audit["verdict"] == "PASS_WITH_LIMITATIONS"
    assert prior_audit["manifest_sha256"] == sha(STAGE048 / "SHA256SUMS")
    assert prior_audit["tail_certificate_sha256"] == sha(TAIL_CERT)
    assert receipt["manifests_sha256"] == {folder.name: sha(folder / "SHA256SUMS")
                                          for folder in (STAGE048, STAGE041, FULL, HALF)}
    assert receipt["full_audit_sha256"] == sha(STAGE048_CERT)
    assert receipt["tail_admission_sha256"] == sha(TAIL_CERT)
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage049_s26_halfyear.py")
    design = list((LINE / "stages").glob("*_stage049_*design.md"))
    assert len(design) == 1 and receipt["design_sha256"] == sha(design[0])
    assert (receipt["starts"], receipt["attempted_runs"], receipt["completed_runs"], receipt["unknown_runs"]) == (STARTS, 24, 24, 0)
    assert receipt["cutoff"] == TARGET and receipt["capital"] == CAPITAL
    assert receipt["products"] == stage048_config["products"] and len(set(receipt["products"])) == 26
    assert receipt["market_sha256"] == stage048_config["inputs_sha256"]
    assert all(sha(Path(name)) == digest for name, digest in
               (stage048_config["inputs_sha256"] | stage048_config["source_sha256"]).items())
    if "engine_sha256" in receipt:
        assert receipt["engine_sha256"] == sha(LINE / "tools/run_weekly_portfolio.py")
    assert {path.name for path in RESULT.iterdir() if path.is_dir()} == set(STARTS)

    market = extend_raw_market(load_json(TAIL_CERT))
    weeks = completed_weeks(market[1], market[4])
    controls = TABLE(STAGE041, "window_metrics").set_index("calendar_start", verify_integrity=True)
    aggregate = TABLE(RESULT, "window_metrics").set_index("calendar_start", verify_integrity=True)
    assert aggregate.index.tolist() == controls.index.tolist() == STARTS
    shared_2015 = {path.name for path in (RESULT / STARTS[0]).iterdir()} & {path.name for path in STAGE048.iterdir()}
    identical_2015 = {name for name in shared_2015
                      if (RESULT / STARTS[0] / name).read_bytes() == (STAGE048 / name).read_bytes()}
    assert {"daily.csv", "fills.csv", "cycles.csv", "signals.csv", "opening_funding.csv", "terminal.json"} <= identical_2015

    base_totals, candidate_totals, unchanged = Counter(), Counter(), Counter()
    windows = []
    for start in STARTS:
        folder, control = RESULT / start, control_path(start)
        config = load_json(folder / "inputs.json")
        base_config = load_json(control / "inputs.json")
        assert config == {**stage048_config, "start": start}
        assert base_config == {**stage037_config, "start": start}
        unchanged.update(inherited_events(folder, control, base_config["products"]))
        s19, base_stress, base_counts, base_zero, base_worst, base_dates = replay_independently(
            control, start, base_config, market, weeks)
        s26, candidate_stress, candidate_counts, candidate_zero, candidate_worst, candidate_dates = replay_independently(
            folder, start, config, market, weeks)
        assert candidate_dates.equals(base_dates)
        for key, expected in s19.items():
            check_values(controls.at[start, f"s19_{key}"], expected, (start, "stage041", key))
        by_product = TABLE(folder, "cycles").groupby("product").net_pnl.sum()
        added = float(by_product.reindex(sorted(ADDED), fill_value=0).sum())
        near(s26["net_pnl"] - s19["net_pnl"], added)
        check_aggregate_row(aggregate.loc[start], start, candidate_dates, s19, s26, base_stress, candidate_stress, added)
        base_totals.update(base_counts)
        candidate_totals.update(candidate_counts)
        windows.append(dict(
            start=start, first_session=candidate_dates.iat[0], s19_equity=float(s19["equity"]),
            s26_equity=float(s26["equity"]), added_net_pnl=added,
            s19_drawdown_pct=float(s19["max_dd_pct"]), s26_drawdown_pct=float(s26["max_dd_pct"]),
            s19_deficit_days=s19["deficit_days"], s26_deficit_days=s26["deficit_days"],
            s19_nonpositive_days=base_counts["nonpositive_days"], s26_nonpositive_days=candidate_counts["nonpositive_days"],
            s19_zero_equity_closes=base_zero, s26_zero_equity_closes=candidate_zero,
            s19_worst_funding=base_worst, s26_worst_funding=candidate_worst,
        ))
        print(start, "S19→S26", s19["equity"], s26["equity"], "gap days", s19["deficit_days"], s26["deficit_days"],
              "nonpositive days", base_counts["nonpositive_days"], candidate_counts["nonpositive_days"], flush=True)

    windows_with_deficit = {arm: sum(row[f"{arm}_deficit_days"] > 0 for row in windows) for arm in ("s19", "s26")}
    windows_with_nonpositive = {arm: sum(row[f"{arm}_nonpositive_days"] > 0 for row in windows) for arm in ("s19", "s26")}
    report = dict(
        verdict="PASS_WITH_LIMITATIONS", attempted=24, completed=len(windows), unknown=0,
        manifest_sha256=sha(RESULT / "SHA256SUMS"), manifest_entries=manifest_entries,
        pinned_inputs=len(stage048_config["inputs_sha256"] | stage048_config["source_sha256"]),
        stage048_reproduced_files=sorted(identical_2015), checked_rows=dict(s19=dict(base_totals), s26=dict(candidate_totals)),
        unchanged_original_events=dict(unchanged),
        windows_with_deficit=windows_with_deficit, windows_with_nonpositive_equity=windows_with_nonpositive,
        higher_final_equity_s26=sum(row["s26_equity"] > row["s19_equity"] for row in windows),
        lower_final_equity_s26=sum(row["s26_equity"] < row["s19_equity"] for row in windows),
        better_drawdown_s26=sum(row["s26_drawdown_pct"] > row["s19_drawdown_pct"] for row in windows),
        windows=windows,
        limitations=[
            "Seven additions were chosen by retrospective 2022 profitability; half-year windows overlap.",
            "Fixed one-lot theoretical fills continue through static margin shortfalls and nonpositive equity.",
            "After crossing zero equity, percentage returns and Sharpe are not economically interpretable.",
            "Zero commission and daily open proxies, with no opening queue model.",
        ],
    )
    Path(__file__).with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print({key: value for key, value in report.items() if key != "windows"}, flush=True)


if __name__ == "__main__":
    audit()
