"""Replay S19 with daily signal bars and fixed one-lot entries in 2026."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage040_s19_without_gold as baseline
from stage042_s19_fixed_two import ENGINE_SHA

LINE = baseline.LINE
START = "2026-01-01"
DESIGN = LINE / "stages/20261104_1936_stage043_s19_daily_one_design.md"


def daily_signal_market(market):
    products, days, weeks, _, rows, by_epoch, mains, specs, hashes = market
    calendar = sorted(day for week in weeks for day in week)
    if len(set(calendar)) != len(calendar) or not set(days).issubset(calendar):
        raise ValueError("daily signal calendar differs from frozen market")
    periods = [[day] for day in calendar]
    period_index = {day: index for index, day in enumerate(calendar)}
    return products, days, periods, period_index, rows, by_epoch, mains, specs, hashes


def run(output):
    baseline.verify_manifest(baseline.HALFYEAR, baseline.HALFYEAR_SHA)
    control = baseline.HALFYEAR / START
    config = json.loads((control / "inputs.json").read_text())
    if baseline.portfolio.sha(Path(baseline.portfolio.__file__)) != ENGINE_SHA:
        raise ValueError("unexpected strategy engine")
    market = baseline.extend(baseline.load(baseline.MARKET, control=True), baseline.TAIL)
    if (list(market[0]) != config["products"]
            or {str(path): digest for path, digest in market[-1].items()} != config["inputs_sha256"]):
        raise ValueError("frozen market data mismatch")
    daily_market = daily_signal_market(market)
    with patch.object(baseline.portfolio, "INITIAL", baseline.CAPITAL), patch.object(
        baseline.portfolio, "START", START
    ), redirect_stdout(StringIO()):
        baseline.portfolio.run(output, week_body_filter=True, reverse_after_stop=True,
                               block_four_up=True, delivery_guard=True, market_loader=lambda: daily_market)

    inputs = output / "inputs.json"
    if json.loads(inputs.read_text()) != config:
        raise ValueError("strategy flags differ from weekly reference")
    inputs.write_text(json.dumps({**config, "signal_bar": "1d", "fixed_entry_lots": 1}, indent=2) + "\n")

    daily = pd.read_csv(output / "daily.csv")
    fills = pd.read_csv(output / "fills.csv")
    reference = pd.read_csv(control / "daily.csv")
    if (not daily.date.equals(reference.date) or daily.date.iat[-1] != baseline.TARGET
            or daily.cash.iat[0] != baseline.CAPITAL or daily.positions.iat[0] != 0
            or fills.date.min() <= daily.date.iat[0] or fills.signal_day.min() < daily.date.iat[0]
            or not fills.volume.eq(1).all()):
        raise ValueError("unexpected cold start, sizing or end date")
    opening = baseline.reconstruct_opening(daily, fills, daily_market)
    opening.to_csv(output / "opening_funding.csv", index=False)
    summary_file = output / "summary.json"
    summary = json.loads(summary_file.read_text())
    daily_metrics = baseline.metrics(output, daily, opening, summary)
    summary["days_margin_above_equity"] = daily_metrics["close_deficit_days"]
    summary_file.write_text(json.dumps(summary, indent=2) + "\n")
    weekly_metrics = baseline.metrics(control, reference, pd.read_csv(control / "opening_funding.csv"),
                                     json.loads((control / "summary.json").read_text()))
    comparison = dict(
        start=daily.date.iat[0], end=daily.date.iat[-1], days=len(daily), capital=baseline.CAPITAL,
        weekly=weekly_metrics, daily=daily_metrics,
        daily_fill_reasons={key: int(value) for key, value in fills.reason.value_counts().items()},
        daily_nonpositive_equity_days=len(set(daily.loc[daily.equity.le(0), "date"])
                                         | set(opening.loc[opening.equity.le(0), "date"])),
    )
    (output / "comparison.json").write_text(json.dumps(comparison, indent=2) + "\n")
    receipt = dict(
        weekly_reference_manifest_sha256=baseline.HALFYEAR_SHA,
        design_sha256=baseline.portfolio.sha(DESIGN),
        entrypoint_sha256=baseline.portfolio.sha(Path(__file__)),
        signal_bar="1d", fixed_entry_lots=1, attempted=1, completed=1, unknown=0,
        market_sha256=config["inputs_sha256"], source_sha256=config["source_sha256"],
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    baseline.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
