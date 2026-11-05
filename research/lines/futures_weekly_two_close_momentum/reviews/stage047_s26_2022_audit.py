"""Independently reconstruct Stage047 and cross-check both shared capital accounts."""
from collections import Counter, defaultdict
import json
from pathlib import Path

import numpy as np
import pandas as pd

from stage040_s19_without_gold_audit import (
    CAPITAL, DAY_COLUMNS, HALF, LINE, OPEN_COLUMNS, check_manifest, load_json, near, sha,
)
from stage045_s19_weekly_shadow_filter_audit import completed_weeks
from stage046_s44_individual_2022_audit import (
    END, RESULT as SOLO, START, metrics, raw_market, reconcile, table,
)

RESULT = LINE / "outputs/stage047_s26_2022"
BASE = HALF / START
SOLO_AUDIT = LINE / "reviews/stage046_s44_individual_2022_audit.json"
EXPECTED_ADDED = ("p.DCE", "ss.SHFE", "zn.SHFE", "ni.SHFE", "ag.SHFE", "jd.DCE", "TA.CZCE")


def clip(folder, name):
    values = table(folder, name)
    return values.loc[values.date.le(END)].reset_index(drop=True)


def normalize(frame):
    frame = frame.reset_index(drop=True)
    nullable = {"stop", "older_close", "ma5_slope", "ma10_slope", "ma20_slope"}
    for field in nullable.intersection(frame.columns):
        frame[field] = pd.to_numeric(frame[field].mask(frame[field].eq("")))
    return frame


def crosscheck_solo_events(folder, products, include_cycles):
    totals = Counter()
    event_types = ("fills", "signals", "entry_filter", "week_body_filter", "gaps", "four_up_blocks")
    if include_cycles:
        event_types += ("cycles",)
    for name in event_types:
        portfolio = table(folder, name) if name == "cycles" else clip(folder, name)
        assert set(portfolio["product"]) <= set(products)
        for product in products:
            shared = portfolio.loc[portfolio["product"].eq(product)].drop(columns="cycle", errors="ignore")
            solo = table(SOLO / product, name).drop(columns="cycle", errors="ignore")
            if shared.empty:
                assert solo.empty
            else:
                pd.testing.assert_frame_equal(normalize(shared), normalize(solo), check_dtype=False,
                                              check_exact=False, rtol=0, atol=1e-8, obj=f"{product} {name}")
            totals[name] += len(solo)
    return dict(totals)


def reconcile_shared_from_solo(folder, products):
    portfolio_daily, portfolio_open, portfolio_fills = (
        clip(folder, name) for name in ("daily", "opening_funding", "fills"))
    solo_daily = [table(SOLO / product, "daily") for product in products]
    assert all(frame.date.equals(portfolio_daily.date) for frame in solo_daily)
    added = sum(frame[DAY_COLUMNS] for frame in solo_daily)
    capital_offset = CAPITAL * (len(products) - 1)
    added[["equity", "cash"]] -= capital_offset
    near(added, portfolio_daily[DAY_COLUMNS])

    snapshot_index = {
        product: {day: frame for day, frame in table(SOLO / product, "opening_funding").groupby("date")}
        for product in products
    }
    fills_by_day = {day: list(frame.itertuples(index=False))
                    for day, frame in portfolio_fills.groupby("date", sort=False)}
    expected = []
    fields = ["equity", "margin", "positions"]
    for day in portfolio_daily.date:
        books = {product: snapshot_index[product][day][fields].to_numpy()
                 for product in products}
        totals = sum(book[0] for book in books.values()) - [capital_offset, 0, 0]
        account, margin, positions = totals
        expected.append((day, 0, "", "before_fills", account, margin, account - margin, int(positions)))
        next_index = defaultdict(int)
        for step, fill in enumerate(fills_by_day.get(day, ()), 1):
            product = fill.product
            next_index[product] += 1
            index = next_index[product]
            totals += books[product][index] - books[product][index - 1]
            account, margin, positions = totals
            expected.append((day, step, product, fill.reason, account, margin, account - margin, int(positions)))
        assert all(next_index[product] == len(book) - 1 for product, book in books.items())
    reconstructed = pd.DataFrame(expected, columns=OPEN_COLUMNS)
    pd.testing.assert_frame_equal(reconstructed.iloc[:, :4], portfolio_open.iloc[:, :4])
    near(reconstructed.iloc[:, 4:], portfolio_open.iloc[:, 4:])

    # Both portfolios have exactly one initial allocation of capital.
    return portfolio_daily, portfolio_open, portfolio_fills


def period_metrics(daily, opening, fills, closed_cycles):
    assert daily.equity.iat[0] == CAPITAL and daily.positions.iat[0] == 0
    close_free = (daily.equity - daily.margin).round(8)
    deficit = set(daily.loc[close_free.lt(0), "date"]) | set(opening.loc[opening.free_equity.lt(0), "date"])
    returns = daily.equity / np.r_[CAPITAL, daily.equity.iloc[:-1]] - 1
    drawdown = daily.equity / np.maximum.accumulate(np.r_[CAPITAL, daily.equity])[1:] - 1
    near(drawdown, daily.drawdown)
    final_equity = daily.equity.iat[-1]
    return dict(
        equity=final_equity, net_pnl=final_equity - CAPITAL, return_pct=100 * (final_equity / CAPITAL - 1),
        max_dd_pct=100 * drawdown.min(), sharpe=returns.mean() / returns.std(ddof=1) * np.sqrt(252),
        closed_cycles=len(closed_cycles), fills=len(fills), win_rate_pct=100 * closed_cycles.net_pnl.gt(0).mean(),
        slippage=fills.slippage.sum(), commission=fills.commission.sum(), deficit_days=len(deficit),
        first_deficit=min(deficit, default=""), max_shortfall=max(0, -min(close_free.min(), opening.free_equity.min())),
        peak_close_margin=daily.margin.max(), peak_open_margin=opening.margin.max(),
        max_close_positions=int(daily.positions.max()),
    )


def audit():
    manifest_entries = {folder.name: check_manifest(folder) for folder in (RESULT, SOLO, HALF)}
    receipt = load_json(RESULT / "receipt.json")
    assert receipt["stage046_manifest_sha256"] == sha(SOLO / "SHA256SUMS")
    assert receipt["stage046_manifest_sha256"] == load_json(SOLO_AUDIT)["manifest_sha256"]
    assert load_json(SOLO_AUDIT)["verdict"] == "PASS_WITH_LIMITATIONS"
    assert receipt["stage038_manifest_sha256"] == sha(HALF / "SHA256SUMS")
    assert receipt["design_sha256"] == sha(LINE / "stages/20261104_2032_stage047_s26_2022_design.md")
    assert receipt["entrypoint_sha256"] == sha(LINE / "tools/stage047_s26_2022.py")
    assert receipt["engine_sha256"] == sha(LINE / "tools/run_weekly_portfolio.py")
    assert (receipt["start"], receipt["end"], receipt["capital"]) == (START, END, CAPITAL)
    baseline = load_json(BASE / "inputs.json")
    base_products = baseline["products"]
    ranking = table(SOLO, "product_metrics").sort_values(["net_pnl", "product"], ascending=[False, True])
    top = ranking.head(15)["product"].tolist()
    added = tuple(product for product in top if product not in base_products)
    assert added == tuple(receipt["added"]) == EXPECTED_ADDED
    products = sorted(set(base_products) | set(added))
    assert products == receipt["products"] and len(products) == 26 and "au.SHFE" in products
    assert len(base_products) == 19
    pins = receipt["market_sha256"]
    assert pins == load_json(SOLO / "receipt.json")["market_sha256"]
    assert all(sha(Path(name)) == digest for name, digest in (pins | baseline["source_sha256"]).items())
    config = load_json(RESULT / "inputs.json")
    assert config == {**baseline, "products": products, "end": END, "inputs_sha256": pins}
    market = raw_market()
    weeks = completed_weeks(market[1], market[4])
    marks, opening, _, pending, conditional, branches, delayed = reconcile(
        RESULT, START, config, *market[:-1], *weeks)
    complete_metrics, counts = metrics(RESULT, marks, opening, pending)

    cross_checks = {
        "s19": crosscheck_solo_events(BASE, base_products, include_cycles=False),
        "s26": crosscheck_solo_events(RESULT, products, include_cycles=True),
    }
    base_daily, base_opening, base_fills = reconcile_shared_from_solo(BASE, base_products)
    candidate_daily, candidate_opening, candidate_fills = reconcile_shared_from_solo(RESULT, products)
    assert base_daily.date.equals(candidate_daily.date) and len(candidate_daily) == 242
    base_cycles = table(BASE, "cycles").loc[lambda frame: frame.exit_day.ne("") & frame.exit_day.le(END)]
    candidate_cycles = table(RESULT, "cycles")
    solo_base_books = [table(SOLO / product, "cycles") for product in base_products]
    solo_base_cycles = pd.concat([frame for frame in solo_base_books if not frame.empty])
    solo_base_closed = solo_base_cycles.loc[solo_base_cycles.exit_day.ne("")]
    fields = ["product", "direction", "entry_day", "exit_day", "cash_flow", "terminal_mark", "net_pnl"]
    pd.testing.assert_frame_equal(base_cycles[fields].sort_values(fields).reset_index(drop=True),
                                  solo_base_closed[fields].sort_values(fields).reset_index(drop=True),
                                  check_dtype=False, check_exact=False, rtol=0, atol=1e-8)
    computed = {
        "s19": period_metrics(base_daily, base_opening, base_fills, solo_base_closed),
        "s26": period_metrics(candidate_daily, candidate_opening, candidate_fills,
                              candidate_cycles.loc[candidate_cycles.exit_day.ne("")]),
    }
    for key in complete_metrics.keys() & computed["s26"].keys():
        if isinstance(complete_metrics[key], str):
            assert complete_metrics[key] == computed["s26"][key]
        else:
            near(complete_metrics[key], computed["s26"][key])
    comparison = load_json(RESULT / "comparison.json")
    assert (comparison["start"], comparison["end"], comparison["days"], comparison["initial"]) == (
        "2022-01-04", END, 242, CAPITAL)
    for arm, values in computed.items():
        assert set(comparison[arm]) == set(values)
        for key, expected in values.items():
            if isinstance(expected, str):
                assert comparison[arm][key] == expected
            else:
                near(comparison[arm][key], expected)

    by_product = candidate_cycles.groupby("product").net_pnl.sum()
    contribution = {product: float(by_product[product]) for product in added}
    for product, pnl in contribution.items():
        near(pnl, comparison["added_pnl"][product])
        near(pnl, ranking.set_index("product").at[product, "net_pnl"])
    near(by_product.reindex(base_products, fill_value=0).sum(), computed["s19"]["net_pnl"])
    near(computed["s26"]["net_pnl"] - computed["s19"]["net_pnl"], sum(contribution.values()))
    worst_open = candidate_opening.loc[candidate_opening.free_equity.idxmin()].to_dict()
    s26_close_free = (candidate_daily.equity - candidate_daily.margin).round(8)
    worst_close = candidate_daily.loc[s26_close_free.idxmin(), ["date", "equity", "margin", "positions"]].to_dict()
    worst_close["free_equity"] = float(s26_close_free.min())
    audit_result = dict(
        verdict="PASS_WITH_LIMITATIONS", products=len(products), added_pnl=contribution,
        added_pnl_total=sum(contribution.values()), checked_rows=counts,
        manifest_entries=manifest_entries, manifest_sha256=sha(RESULT / "SHA256SUMS"),
        pinned_inputs=len(pins | baseline["source_sha256"]), selection_top15=top,
        events_matching_audited_solo_books=cross_checks,
        both_accounts_daily_reconciled=242, opening_snapshots_reconciled={"s19": len(base_opening), "s26": len(candidate_opening)},
        minimum_close_equity=float(candidate_daily.equity.min()), pending_at_cutoff=pending,
        conditional_reversals_at_cutoff=conditional, worst_open=worst_open, worst_close=worst_close,
        execution_branches=dict(branches), delayed_stop_rows=delayed,
        limitations=[
            "Seven additions selected from 2022 profitability and evaluated on the same 2022 sample.",
            "One shared capital allocation per arm. Theoretical fills continue through margin shortfalls.",
            "Static margin, zero commission, and opening/closing price proxies. No queue simulation.",
            "Inherited one missing nickel physical bar retained in admitted market coverage.",
        ],
    )
    Path(__file__).with_suffix(".json").write_text(json.dumps(audit_result, indent=2, allow_nan=False) + "\n")
    print(audit_result, flush=True)


if __name__ == "__main__":
    audit()
