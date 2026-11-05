"""Replay frozen Q/R on common 18 products at independent calendar starts."""
from bisect import bisect_left
from contextlib import redirect_stdout
import csv
from datetime import date
from decimal import Decimal
from io import StringIO
import json
from math import isfinite
from pathlib import Path
from unittest.mock import patch

import run_weekly_portfolio as portfolio


LINE = Path(__file__).resolve().parents[1]
OUTPUT = LINE / "outputs" / "stage021_q_r_multicycle_2015_20261103"
METRICS = ("equity", "net_pnl", "return_pct", "max_dd_pct", "sharpe", "slippage",
           "fills", "closed_cycles", "win_rate_pct", "payoff", "profit_factor",
           "peak_margin_ratio_pct", "days_margin_above_equity", "open_positions",
           "pending_signals", "one_price_exits")


def write_checksums(directory, files):
    entries = [(path.relative_to(directory).as_posix(), portfolio.sha(path))
               for path in sorted(files, key=lambda path: (path.suffix, path.as_posix()))]
    (directory / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in entries))


def replay(output, market, start, end, arm):
    products, days, *remaining = market
    end_index = bisect_left(days, end)
    assert days[end_index] == end
    bounded = (products, days[:end_index + 1], *remaining)
    staging = output.with_name(f".{output.name}.running")
    with patch.object(portfolio, "load_market", return_value=bounded), \
         patch.object(portfolio, "START", start), patch.object(portfolio, "END", end), \
         redirect_stdout(StringIO()):
        portfolio.run(staging, week_body_filter=True, reverse_after_stop=True, two_close_entry=arm == "R")
    result = json.loads((staging / "summary.json").read_text())
    first = bisect_left(days, start)
    assert (result["start"], result["end"], result["days"]) == (days[first], end, end_index + 1 - first)
    assert result["initial"] == 300_000 and all(isfinite(result[key]) for key in METRICS)
    with (staging / "daily.csv").open() as source:
        daily = list(csv.DictReader(source))
    assert Decimal(daily[0]["cash"]) == 300_000 and int(daily[0]["positions"]) == 0
    assert [row["date"] for row in daily] == days[first:end_index + 1]
    write_checksums(staging, staging.glob("*"))
    staging.rename(output)
    return {key: result[key] for key in ("start", "end", "days", "initial", *METRICS)}


def main():
    market = portfolio.load_market()
    products = [product for product in market[0] if product != "fu.SHFE"]
    assert len(products) == 18
    market = (products, *market[1:])
    days = market[1]
    OUTPUT.mkdir()
    for arm in ("Q", "R"):
        full = OUTPUT / "full" / arm
        replay(full, market, portfolio.START, portfolio.END, arm)
        baseline = LINE / "outputs" / f"stage020_{arm}_18_2015_20261103"
        for source in full.iterdir():
            assert source.read_bytes() == (baseline / source.name).read_bytes(), source
    print("Full-period Q/R outputs matched Stage020.", flush=True)

    rows = []
    cutoff = date.fromisoformat(portfolio.END)
    for years in (1, 2, 3):
        for year in range(2015, cutoff.year):
            for month in (1, 6):
                start, anniversary = date(year, month, 1), date(year + years, month, 1)
                if anniversary > cutoff:
                    continue
                end = days[bisect_left(days, anniversary.isoformat()) - 1]
                window = f"{years}y_{start.isoformat()}"
                for arm in ("Q", "R"):
                    metrics = replay(OUTPUT / "runs" / window / arm, market, start.isoformat(), end, arm)
                    rows.append(dict(window=window, years=years, cohort={1: "January", 6: "June"}[month],
                                     calendar_start=start.isoformat(), anniversary=anniversary.isoformat(),
                                     arm=arm, **metrics))
        print(f"{years}y paired windows: {sum(row['years'] == years for row in rows)//2}", flush=True)

    assert len(rows) == 120
    with (OUTPUT / "window_metrics.csv").open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_checksums(OUTPUT, (p for p in OUTPUT.rglob("*") if p.is_file()))


if __name__ == "__main__":
    main()
