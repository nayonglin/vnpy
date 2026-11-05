"""Rebuild the Stage048 physical weekly ledger and audit incremental PnL by period."""
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from stage040_s19_without_gold_audit import (
    CAPITAL, FULL, HISTORY, LINE, TARGET, cents, check_manifest, load_json, near, sha,
)
from stage043_s19_daily_one_audit import Bar, source_data
from stage044_s19_daily_halfyear_audit import financial_metrics
from stage045_s19_weekly_shadow_filter_audit import completed_weeks
import stage046_s44_individual_2022_audit as independent_weekly
from stage047_s26_2022_audit import normalize
from stage048_s26_tail_audit import ADDED, APPROVED, PRIOR, product_of

RESULT = LINE / "outputs/stage048_s26_full_20261104"
STAGE047 = LINE / "outputs/stage047_s26_2022"
TAIL_CERT = LINE / "reviews/stage048_s26_tail_audit.json"
START = "2015-01-01"
TABLE = independent_weekly.table


def extend_raw_market(certificate):
    calendar, guard_calendar, mains, symbols, by_epoch = source_data()
    assert calendar[-2:] == [PRIOR, TARGET]
    extra_bars = pd.read_csv(APPROVED / "added_bars.csv")
    extra_bars = extra_bars.loc[extra_bars.vt_symbol.map(product_of).isin(ADDED)]
    assert extra_bars.date.max() == PRIOR and extra_bars.volume.gt(0).all()
    for row in extra_bars.itertuples(index=False):
        bar = Bar(row.vt_symbol, row.contract_epoch_id, *map(cents, (row.open, row.high, row.low, row.close)))
        assert (row.date, bar.epoch) not in by_epoch and (row.date, bar.symbol) not in symbols
        symbols[row.date, bar.symbol] = by_epoch[row.date, bar.epoch] = bar
    mapping = pd.read_csv(APPROVED / "added_mapping.csv", keep_default_na=False)
    for row in mapping.loc[mapping.continuous_symbol_vt.isin(ADDED)
                           & mapping.main_contract_vt.ne("")].itertuples(index=False):
        assert (row.date, row.continuous_symbol_vt) not in mains
        mains[row.date, row.continuous_symbol_vt] = row.main_contract_vt
    for product, day_mains in certificate["verified_mains"].items():
        assert mains[PRIOR, product] == day_mains[PRIOR]
        mains[TARGET, product] = day_mains[TARGET]
    for row in certificate["admitted"]:
        bar = Bar(row["symbol"], row["epoch"], *[cents(row[field]) for field in ("open", "high", "low", "close")])
        assert (TARGET, bar.epoch) not in by_epoch and (TARGET, bar.symbol) not in symbols
        symbols[TARGET, bar.symbol] = by_epoch[TARGET, bar.epoch] = bar
    settings = load_json(HISTORY / "stage003_D_20261103_attempt01/contract_settings.json")
    for key, fields in load_json(APPROVED / "added_specs.json").items():
        assert not settings[key].keys() & fields.keys()
        settings[key].update(fields)
    return calendar, guard_calendar, mains, symbols, by_epoch, settings


def inherited_events(candidate, baseline, original):
    counts = {}
    for name in ("fills", "signals", "gaps", "cycles", "entry_filter", "week_body_filter", "four_up_blocks"):
        before = TABLE(baseline, name).drop(columns="cycle", errors="ignore")
        after = TABLE(candidate, name).loc[lambda frame: frame["product"].isin(original)]
        after = after.drop(columns="cycle", errors="ignore")
        pd.testing.assert_frame_equal(normalize(before), normalize(after), check_dtype=False,
                                      check_exact=False, rtol=0, atol=1e-8, obj=name)
        counts[name] = len(before)
    baseline_terminal, candidate_terminal = (load_json(path / "terminal.json") for path in (baseline, candidate))
    before = {p: {k: v for k, v in item.items() if k != "cycle"}
              for p, item in baseline_terminal["positions"].items()}
    after = {p: {k: v for k, v in item.items() if k != "cycle"}
             for p, item in candidate_terminal["positions"].items() if p in original}
    assert before == after
    for key in ("pending", "pending_reversals"):
        assert baseline_terminal[key] == {p: row for p, row in candidate_terminal[key].items() if p in original}
    counts["terminal_positions"] = len(before)
    return counts


def financial_check(folder, configuration, market, weeks):
    with patch.object(independent_weekly, "END", TARGET):
        marks, opening, cycles, pending, reversal, branches, delayed = independent_weekly.reconcile(
            folder, START, configuration, *market, *weeks)
    results, counts, zero_close = financial_metrics(folder, marks, opening, pending)
    assert not pending and not reversal
    assert not TABLE(folder, "gaps").date.eq(TARGET).any()
    assert TABLE(folder, "fills").volume.eq(1).all()
    return marks, opening, results, counts, zero_close


def audit():
    manifests = {folder.name: check_manifest(folder) for folder in (RESULT, STAGE047, FULL)}
    receipt = load_json(RESULT / "receipt.json")
    previous = load_json(STAGE047 / "receipt.json")
    assert receipt["stage047_manifest_sha256"] == sha(STAGE047 / "SHA256SUMS")
    assert receipt["stage037_manifest_sha256"] == sha(FULL / "SHA256SUMS")
    assert receipt["engine_sha256"] == sha(LINE / "tools/run_weekly_portfolio.py")
    assert receipt["design_sha256"] == sha(LINE / "stages/20261104_2036_stage048_s26_full_design.md")
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage048_s26_full.py")
    assert (receipt["start"], receipt["end"], receipt["capital"]) == (START, TARGET, CAPITAL)
    assert receipt["products"] == previous["products"] and len(set(receipt["products"])) == 26
    assert set(previous["added"]) == ADDED
    base = load_json(FULL / "inputs.json")
    assert set(base["products"]) | ADDED == set(receipt["products"])
    assert not set(base["products"]) & ADDED and len(base["products"]) == 19
    expected_pins = receipt["market_sha256"]
    assert all(expected_pins[name] == digest for name, digest in previous["market_sha256"].items())
    assert all(expected_pins[name] == digest for name, digest in base["inputs_sha256"].items())
    assert all(sha(Path(name)) == digest for name, digest in (expected_pins | base["source_sha256"]).items())
    config = load_json(RESULT / "inputs.json")
    assert config == {**base, "products": receipt["products"], "inputs_sha256": expected_pins}

    certificate = load_json(TAIL_CERT)
    assert certificate["verdict"] == "PASS_TAIL_INPUT_ADMISSION" and set(certificate["products"]) == ADDED
    assert certificate["target"] == TARGET
    assert all(sha(Path(name)) == digest for name, digest in certificate["sha256"].items())
    assert {name: digest for name, digest in certificate["sha256"].items() if "stage048_s26_tail" in name} == {
        name: digest for name, digest in expected_pins.items() if "stage048_s26_tail" in name
    }
    market = extend_raw_market(certificate)
    weeks = completed_weeks(market[1], market[4])
    retained = inherited_events(RESULT, FULL, base["products"])
    marks, opening, candidate, candidate_counts, candidate_zero = financial_check(RESULT, config, market, weeks)
    base_marks, base_open, baseline, baseline_counts, baseline_zero = financial_check(FULL, base, market, weeks)
    candidate_daily = TABLE(RESULT, "daily")
    base_daily = TABLE(FULL, "daily")
    assert candidate_daily.date.equals(base_daily.date)
    comparison = load_json(RESULT / "comparison.json")
    assert (comparison["start"], comparison["end"], comparison["days"], comparison["capital"]) == (
        candidate_daily.date.iat[0], TARGET, len(candidate_daily), CAPITAL)
    for arm, values in (("s26", candidate), ("s19", baseline)):
        assert set(comparison[arm]) == set(values)
        for key, expected in values.items():
            if isinstance(expected, str):
                assert comparison[arm][key] == expected
            else:
                near(comparison[arm][key], expected)
    annual = pd.DataFrame({
        "s19": base_daily.groupby(base_daily.date.str[:4]).net_pnl.sum(),
        "s26": candidate_daily.groupby(candidate_daily.date.str[:4]).net_pnl.sum(),
    })
    annual["difference"] = annual.s26 - annual.s19
    annual.index.name = "year"
    observed = TABLE(RESULT, "annual_comparison").set_index("year")
    annual.index = annual.index.astype(int)
    pd.testing.assert_frame_equal(annual, observed, check_dtype=False, check_exact=False, rtol=0, atol=1e-8)
    segments = dict(
        difference_before_2022=annual.loc[:2021, "difference"].sum(),
        difference_2022=annual.at[2022, "difference"],
        difference_after_2022=annual.loc[2023:, "difference"].sum(),
    )
    for key, value in segments.items():
        near(comparison[key], value)
    near(sum(segments.values()), candidate["net_pnl"] - baseline["net_pnl"])
    additions = TABLE(RESULT, "cycles").groupby("product").net_pnl.sum().loc[sorted(ADDED)].to_dict()
    assert set(comparison["added_pnl"]) == ADDED
    for product, pnl in additions.items():
        near(comparison["added_pnl"][product], pnl)
    near(sum(additions.values()), sum(segments.values()))
    end_positions = load_json(RESULT / "terminal.json")["positions"]
    admitted_epochs = {row["epoch"] for row in certificate["admitted"]}
    extra_end = {product: pos["epoch"] for product, pos in end_positions.items() if product in ADDED}
    assert set(extra_end.values()) <= admitted_epochs
    pre_target = candidate_daily.date.ne(TARGET)
    target_fills = TABLE(RESULT, "fills").loc[lambda frame: frame.date.eq(TARGET)]
    extra_target_fills = target_fills.loc[target_fills["product"].isin(ADDED)]
    assert set(extra_target_fills.epoch) <= admitted_epochs
    worst_open = opening.loc[opening.free_equity.idxmin()].to_dict()
    close_free = (marks.equity - marks.margin).round(8)
    worst_close = candidate_daily.loc[close_free.idxmin(), ["date", "equity", "margin", "positions"]].to_dict()
    worst_close["free_equity"] = float(close_free.min())
    independent_2022 = load_json(STAGE047 / "comparison.json")
    annual_2022 = {column: float(annual.at[2022, column]) for column in ("s19", "s26", "difference")}
    fresh_2022 = {"s19": independent_2022["s19"]["net_pnl"], "s26": independent_2022["s26"]["net_pnl"]}
    report = dict(
        verdict="PASS_WITH_LIMITATIONS", manifests=manifests, manifest_sha256=sha(RESULT / "SHA256SUMS"),
        pinned_inputs=len(expected_pins | base["source_sha256"]), tail_certificate_sha256=sha(TAIL_CERT),
        checked_rows=dict(s19=baseline_counts, s26=candidate_counts), unchanged_original_events=retained,
        exact_zero_equity_close_dates=dict(s19=baseline_zero, s26=candidate_zero),
        target_day_total_fills=len(target_fills), target_day_added_fills=len(extra_target_fills),
        added_held_at_cutoff=extra_end, additions_pnl=additions,
        attribution_segments={key: float(value) for key, value in segments.items()},
        annual_2022_with_inherited_positions=annual_2022, fresh_2022=fresh_2022,
        worst_open=worst_open, worst_close=worst_close,
        limitations=[
            "Seven additions were selected from 2022 profits, so full history is retrospective; the before/after segments are not formal out-of-sample tests.",
            "The 2022 segment includes inherited capital and positions from earlier years.",
            "Fixed one-lot theoretical trading continues through static margin shortfalls.",
            "Daily opening prints do not establish order queue executability. Zero commission.",
            "Added-contract vendor expiry metadata differs by one day for p2701.DCE; both dates are later than the cutoff and in the same delivery month.",
        ],
    )
    Path(__file__).with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(report, flush=True)


if __name__ == "__main__":
    audit()
