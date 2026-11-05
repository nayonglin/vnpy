"""Run twelve independent January starts of the frozen S19 full-pool strategy."""
import argparse
from contextlib import redirect_stdout
import csv
from io import StringIO
import json
from math import isfinite
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import run_weekly_portfolio as portfolio
from run_stage021_multicycle import write_checksums
from stage025_delivery_guard import load
from stage031_s19_weekly_shape_replay import BASE, BASE_MANIFEST_SHA, LINE, MARKET

DESIGN = LINE / "stages/20261104_1651_stage033_s19_annual_starts_design.md"
PRIOR = "2026-11-03"
TARGET = "2026-11-04"
YEARS = range(2015, 2027)
METRICS = ("start", "end", "days", "initial", "equity", "net_pnl", "return_pct", "max_dd_pct",
           "sharpe", "closed_cycles", "wins", "losses", "win_rate_pct", "fills", "slippage",
           "commission", "peak_margin", "peak_margin_ratio_pct", "days_margin_above_equity",
           "open_positions", "terminal_open_net_pnl", "net_pnl_double_slippage_same_path")


def extend(market, tail):
    products, days, weeks, week_index, rows, by_epoch, mains, specs, hashes = market
    if days[-1] != PRIOR or TARGET not in week_index:
        raise ValueError("missing frozen trading calendar")
    request_file = tail / "request.json"
    prices_file = tail / "provider/raw_daily.csv"
    quotes_file = tail / "provider/quotes.json"
    mapping_file = tail / "continuous_table.raw.json"
    request = json.loads(request_file.read_text())
    quotes = json.loads(quotes_file.read_text())
    mapping = json.loads(mapping_file.read_text())
    if (set(request["mains"]) != set(products) or set(request["symbols"]) != set(quotes)
            or (request["start"], request["end"]) != (PRIOR, TARGET)):
        raise ValueError("unexpected tail request")
    for product in products:
        code, exchange = product.split(".")
        for day in (PRIOR, TARGET):
            _, native = max(row for row in mapping[f"{exchange}.{code}"] if row[0] <= day.replace("-", ""))
            native_exchange, symbol = native.split(".")
            expected = mains[day, product] if day == PRIOR else request["mains"][product]
            if native_exchange != exchange or f"{symbol}.{exchange}" != expected:
                raise ValueError(f"main mapping mismatch {day} {product}")
    prices = pd.read_csv(prices_file)
    if (prices.duplicated(["date", "vt_symbol"]).any() or not prices.date.isin([PRIOR, TARGET]).all()
            or not prices.vt_symbol.isin(quotes).all()):
        raise ValueError("invalid daily response keys")
    epochs_file = portfolio.DATA / "physical_epochs.csv"
    epochs = pd.read_csv(epochs_file, dtype=str, keep_default_na=False)
    epochs = epochs.loc[epochs.contract_yyyymm.ge("202611")].set_index("vt_symbol", verify_integrity=True)
    new_rows = {}
    row_type = type(next(iter(rows.values())))
    for bar in prices.itertuples(index=False):
        if bar.volume <= 0:
            continue
        symbol = bar.vt_symbol
        epoch = epochs.loc[symbol]
        quote = quotes[symbol]
        code, exchange = symbol.split(".")
        date_from_timestamp = pd.to_datetime(bar.datetime, unit="ns", utc=True).tz_convert("Asia/Shanghai").date()
        last_day = pd.to_datetime(quote["expire_datetime"], unit="s", utc=True).tz_convert("Asia/Shanghai").date()
        delivery = f'{int(quote["delivery_year"]):04d}{int(quote["delivery_month"]):02d}'
        if (date_from_timestamp.isoformat() != bar.date or date_from_timestamp > last_day
                or quote["instrument_id"] != f"{exchange}.{code}" or quote["ins_class"] != "FUTURE"
                or delivery != epoch.contract_yyyymm or symbol not in specs["sizes"]
                or quote["volume_multiple"] != specs["sizes"][symbol]
                or quote["price_tick"] != specs["priceticks"][symbol]
                or not 0 < bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high):
            raise ValueError(f"tail contract or bar mismatch {bar.date} {symbol}")
        values = row_type(date=bar.date, vt_symbol=symbol, contract_epoch_id=epoch.contract_epoch_id,
                          contract_yyyymm=delivery, open=bar.open, high=bar.high, low=bar.low,
                          close=bar.close, volume=bar.volume)
        if bar.date == PRIOR:
            if rows.get((PRIOR, symbol)) != values:
                raise ValueError(f"tail price/volume seam mismatch {symbol}")
        else:
            new_rows[TARGET, symbol] = values
    if any((TARGET, symbol) not in new_rows for symbol in request["mains"].values()):
        raise ValueError("latest day has missing main contract bars")
    new_epochs = {(bar.date, bar.contract_epoch_id): bar for bar in new_rows.values()}
    new_mains = {(TARGET, product): symbol for product, symbol in request["mains"].items()}
    extra = {path: portfolio.sha(path) for path in
             (epochs_file, request_file, prices_file, quotes_file, mapping_file)}
    return (products, [*days, TARGET], weeks, week_index, {**rows, **new_rows},
            {**by_epoch, **new_epochs}, {**mains, **new_mains}, specs, {**hashes, **extra})


def replay(destination, market, year, baseline_inputs, base_market):
    start = f"{year}-01-01"
    with patch.object(portfolio, "START", start), redirect_stdout(StringIO()):
        portfolio.run(destination, week_body_filter=True, reverse_after_stop=True,
                      block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    inputs = json.loads((destination / "inputs.json").read_text())
    expected = {**baseline_inputs, "start": start, "end": market[1][-1],
                "inputs_sha256": {str(path): digest for path, digest in market[-1].items()}}
    inputs.pop("source_sha256")
    if inputs != expected:
        raise ValueError(f"unexpected start parameters {year}")
    summary = json.loads((destination / "summary.json").read_text())
    daily = pd.read_csv(destination / "daily.csv")
    fills = pd.read_csv(destination / "fills.csv")
    expected_days = [day for day in market[1] if day >= start]
    if (daily.date.tolist() != expected_days or daily.iloc[0].cash != portfolio.INITIAL
            or daily.iloc[0].positions != 0 or fills.date.min() <= expected_days[0]
            or fills.signal_day.min() < expected_days[0]
            or not all(isfinite(summary[key]) for key in METRICS[2:])):
        raise ValueError(f"invalid cold start {year}")
    if market is not base_market:
        terminal = json.loads((destination / "terminal.json").read_text())
        gaps = pd.read_csv(destination / "gaps.csv")
        if (any((TARGET, position["epoch"]) not in market[5] for position in terminal["positions"].values())
                or not gaps.loc[gaps.date.eq(TARGET)].empty):
            raise ValueError(f"missing or unexecutable tail coverage {year}")
    return dict(start_year=year, **{key: summary[key] for key in METRICS},
                cagr_pct=100 * ((summary["equity"] / summary["initial"]) ** (252 / summary["days"]) - 1),
                peak_positions=int(daily.positions.max()),
                min_free_equity=float((daily.equity - daily.margin).min()))


def run(output, tail):
    manifest = BASE / "SHA256SUMS"
    if portfolio.sha(manifest) != BASE_MANIFEST_SHA:
        raise ValueError("unexpected baseline manifest")
    baseline_files = {}
    for line in manifest.read_text().splitlines():
        digest, filename = line.split(maxsplit=1)
        baseline_files[filename] = digest
        if portfolio.sha(BASE / filename) != digest:
            raise ValueError(f"baseline hash mismatch {filename}")
    baseline_inputs = json.loads((BASE / "inputs.json").read_text())
    baseline_inputs.pop("source_sha256")
    base_market = load(MARKET, control=True)
    market = extend(base_market, tail) if tail else base_market
    reproduction = output / ("reproduction_20261103" if tail else "2015")
    reproduced = replay(reproduction, base_market, 2015, baseline_inputs, base_market)
    generated = {path.name for path in reproduction.iterdir() if path.is_file()}
    reference_outputs = {path.name for path in BASE.iterdir() if path.is_file()} - {"SHA256SUMS"}
    if generated != reference_outputs:
        raise ValueError("2015 canary output file set mismatch")
    for name in generated - {"inputs.json"}:
        if portfolio.sha(reproduction / name) != baseline_files[name]:
            raise ValueError(f"2015 canary drift {name}")
    results = []
    for year in YEARS:
        if year == 2015 and not tail:
            results.append(reproduced)
        else:
            results.append(replay(output / str(year), market, year, baseline_inputs, base_market))
    with (output / "window_metrics.csv").open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    receipt = dict(baseline_manifest_sha256=BASE_MANIFEST_SHA, design_sha256=portfolio.sha(DESIGN),
                   entrypoint_sha256=portfolio.sha(Path(__file__)), cutoff=market[1][-1], years=list(YEARS),
                   prior_control_ledger_byte_match=True,
                   source_hashes={str(path): digest for path, digest in market[-1].items()})
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tail", type=Path)
    args = parser.parse_args()
    run(args.output, args.tail)
