"""Run one independent S44 account per product for calendar year 2022."""
import argparse
from contextlib import redirect_stdout
from inspect import getsource
from io import StringIO
import json
from math import isfinite
from pathlib import Path

import pandas as pd

from stage040_s19_without_gold import (
    CAPITAL, LINE, MARKET, load, metrics, portfolio, reconstruct_opening, write_checksums,
)
from stage042_s19_fixed_two import ENGINE_SHA

START, END = "2022-01-01", "2022-12-30"
DESIGN = LINE / "stages/20261104_2020_stage046_s44_individual_2022_design.md"
FILL_COLUMNS = ("date", "product", "contract", "epoch", "cycle", "side", "volume", "price",
                "size", "slippage", "commission", "reason", "signal_day", "stop", "one_price")


def solo_engine():
    source_path = Path(portfolio.__file__)
    if portfolio.sha(source_path) != ENGINE_SHA:
        raise ValueError("frozen strategy engine changed")
    source = getsource(portfolio.run)
    changes = {
        "pd.DataFrame(cycles.values())": (
            'pd.DataFrame(cycles.values(), columns=["cycle", "product", "direction", "entry_day", '
            '"exit_day", "cash_flow", "terminal_mark"])'
        ),
        "returns.mean()/returns.std()*sqrt(252)": (
            "returns.mean()/returns.std()*sqrt(252) if returns.std() else None"
        ),
        "100*len(wins)/len(closed)": "100*len(wins)/len(closed) if len(closed) else None",
        "wins.sum()/losses.sum()": "wins.sum()/losses.sum() if len(losses) else None",
        "pd.DataFrame(fills).to_csv": "pd.DataFrame(fills, columns=FILL_COLUMNS).to_csv",
    }
    for old, new in changes.items():
        if source.count(old) != 1:
            raise ValueError(f"unexpected summary hook: {old}")
        source = source.replace(old, new)
    engine = dict(vars(portfolio), INITIAL=CAPITAL, START=START, FILL_COLUMNS=FILL_COLUMNS)
    exec(compile(source, str(source_path), "exec"), engine)
    return engine


def replay(output, product, market, engine):
    with redirect_stdout(StringIO()):
        engine["run"](output, week_body_filter=True, reverse_after_stop=True,
                      block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    daily = pd.read_csv(output / "daily.csv")
    fills = pd.read_csv(output / "fills.csv")
    dates = daily.date.tolist()
    if (dates != [day for day in market[1] if day >= START] or dates[-1] != END
            or daily.cash.iat[0] != CAPITAL or daily.positions.iat[0] != 0
            or not fills["product"].eq(product).all() or not fills.volume.eq(1).all()
            or not fills.date.between(dates[0], END).all()
            or not fills.signal_day.ge(dates[0]).all()):
        raise ValueError(f"unexpected calendar, identity or initial state: {product}")

    opening = reconstruct_opening(daily, fills, market)
    opening.to_csv(output / "opening_funding.csv", index=False)
    path = output / "summary.json"
    summary = json.loads(path.read_text())
    for key, value in summary.items():
        if isinstance(value, float) and not isfinite(value):
            summary[key] = None
    row = metrics(output, daily, opening, summary)
    summary["days_margin_above_equity"] = row["close_deficit_days"]
    path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")

    mains = market[6]
    market_rows = market[4]
    mapped = [(day, mains[day, product]) for day in dates if mains.get((day, product))]
    missing = [day for day, symbol in mapped if (day, symbol) not in market_rows]
    status = "traded" if len(fills) else "no_fills" if mapped else "not_listed"
    return dict(
        product=product, status=status, start=dates[0], end=dates[-1],
        mapped_days=len(mapped), main_bars_missing=len(missing),
        open_positions=summary["open_positions"], **row,
    )


def run(output):
    products, days, *other = load(MARKET, control=False)
    if len(products) != 44 or len(set(products)) != 44 or len([d for d in days if START <= d <= END]) != 242:
        raise ValueError("unexpected fixed universe or 2022 trading calendar")
    market_days = [day for day in days if day <= END]
    engine = solo_engine()
    output.mkdir(parents=True)
    rows = [replay(output / product, product, ([product], market_days, *other), engine)
            for product in products]
    ranked = pd.DataFrame(rows).sort_values(["net_pnl", "product"], ascending=[False, True])
    ranked.to_csv(output / "product_metrics.csv", index=False)
    receipt = dict(
        design_sha256=portfolio.sha(DESIGN), engine_sha256=ENGINE_SHA,
        entrypoint_sha256=portfolio.sha(Path(__file__)), start=START, end=END, capital=CAPITAL,
        products=products, attempted=len(products), completed=len(rows), unknown=0,
        market_sha256={str(path): value for path, value in other[-1].items()},
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
