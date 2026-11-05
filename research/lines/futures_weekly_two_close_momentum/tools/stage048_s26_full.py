"""Extend Stage047's fixed S26 to the full frozen trading history."""
import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import stage040_s19_without_gold as base
from stage024_pool44 import ARCHIVE, product_of
from stage033_s19_annual_starts import PRIOR
from stage042_s19_fixed_two import ENGINE_SHA
from stage047_s26_2022 import ADDED

STAGE047 = base.LINE / "outputs/stage047_s26_2022"
STAGE047_SHA = "e8d963ad05f3eb5c1e48f6dc9c9eae99a5ef8d65c1b3088b59945cffb1af6f3e"
DESIGN = base.LINE / "stages/20261104_2036_stage048_s26_full_design.md"
TAIL_AUDIT = base.LINE / "reviews/stage048_s26_tail_audit.json"
TAIL_AUDIT_SHA = "c532e53540d9b92f87efb6276c60f8cbe2090ab7cc4321f749ca5ccb44a72893"
START = "2015-01-01"


def add_tail(market, original, tail):
    products, days, weeks, index, rows, by_epoch, mains, specs, hashes = market
    request_path = tail / "request.json"
    quotes_path = tail / "provider/quotes.json"
    bars_path = tail / "provider/raw_daily.csv"
    mapping_path = tail / "continuous_table.raw.json"
    epoch_path = ARCHIVE / "physical_epochs.csv"
    specs_path = ARCHIVE / "specification.json"

    request = json.loads(request_path.read_text())
    quotes = json.loads(quotes_path.read_text())
    mapping = json.loads(mapping_path.read_text())
    if (days[-1] != PRIOR or base.TARGET not in index
            or set(request["mains"]) != set(ADDED) or set(request["symbols"]) != set(quotes)
            or (request["start"], request["end"]) != (PRIOR, base.TARGET)):
        raise ValueError("unexpected seven-product tail request")
    for product, target in request["mains"].items():
        code, exchange = product.split(".")
        for day, expected in ((PRIOR, mains[PRIOR, product]), (base.TARGET, target)):
            _, native = max(x for x in mapping[f"{exchange}.{code}"] if x[0] <= day.replace("-", ""))
            mapped_exchange, symbol = native.split(".")
            if f"{symbol}.{mapped_exchange}" != expected:
                raise ValueError(f"main contract mismatch: {product} {day}")

    bars = pd.read_csv(bars_path)
    if (bars.duplicated(["date", "vt_symbol"]).any()
            or not bars.date.isin([PRIOR, base.TARGET]).all()
            or not bars.vt_symbol.isin(quotes).all()):
        raise ValueError("invalid tail observations")
    bars = bars.loc[product_of(bars.vt_symbol).isin(ADDED) & bars.volume.gt(0)]
    epochs = pd.read_csv(epoch_path, dtype=str, keep_default_na=False)
    epochs = epochs.loc[epochs.contract_yyyymm.ge("202611") & epochs.product_vt_symbol.isin(ADDED)]
    epochs = epochs.set_index("vt_symbol", verify_integrity=True)
    ticks = json.loads(specs_path.read_text())["priceticks"]
    latest_rows = {}
    row_type = type(next(iter(rows.values())))
    for bar in bars.itertuples(index=False):
        quote = quotes[bar.vt_symbol]
        epoch = epochs.loc[bar.vt_symbol]
        code, exchange = bar.vt_symbol.split(".")
        trade_date = pd.to_datetime(bar.datetime, unit="ns", utc=True).tz_convert("Asia/Shanghai").date()
        expiry = pd.to_datetime(quote["expire_datetime"], unit="s", utc=True).tz_convert("Asia/Shanghai").date()
        month = f'{int(quote["delivery_year"]):04d}{int(quote["delivery_month"]):02d}'
        if (trade_date.isoformat() != bar.date or trade_date > expiry
                or quote["instrument_id"] != f"{exchange}.{code}" or quote["ins_class"] != "FUTURE"
                or month != epoch.contract_yyyymm or quote["volume_multiple"] != specs["sizes"][bar.vt_symbol]
                or quote["price_tick"] != ticks[bar.vt_symbol]
                or not 0 < bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high):
            raise ValueError(f"invalid contract or prices: {bar.vt_symbol} {bar.date}")
        value = row_type(date=bar.date, vt_symbol=bar.vt_symbol, contract_epoch_id=epoch.contract_epoch_id,
                         contract_yyyymm=month, open=bar.open, high=bar.high, low=bar.low,
                         close=bar.close, volume=bar.volume)
        if bar.date == PRIOR:
            previous = rows.get((PRIOR, bar.vt_symbol))
            if previous is None or previous._asdict() != value._asdict():
                raise ValueError(f"previous bar does not reconcile: {bar.vt_symbol}")
        else:
            latest_rows[(base.TARGET, bar.vt_symbol)] = value
    if any((base.TARGET, symbol) not in latest_rows for symbol in request["mains"].values()):
        raise ValueError("incomplete seven-product coverage on final day")
    latest_rows.update({key: row for key, row in original[4].items() if key[0] == base.TARGET})
    latest_epochs = {(row.date, row.contract_epoch_id): row for row in latest_rows.values()}
    latest_mains = {key: symbol for key, symbol in original[6].items() if key[0] == base.TARGET}
    latest_mains.update({(base.TARGET, p): symbol for p, symbol in request["mains"].items()})
    pins = {**hashes, **original[-1], **{p: base.portfolio.sha(p) for p in (
        request_path, quotes_path, bars_path, mapping_path, epoch_path, specs_path,
    )}}
    return products, [*days, base.TARGET], weeks, index, {**rows, **latest_rows}, {
        **by_epoch, **latest_epochs,
    }, {**mains, **latest_mains}, specs, pins


def run(output, tail):
    base.verify_manifest(STAGE047, STAGE047_SHA)
    base.verify_manifest(base.PARENT, base.PARENT_SHA)
    if base.portfolio.sha(Path(base.portfolio.__file__)) != ENGINE_SHA:
        raise ValueError("frozen strategy changed")
    if base.portfolio.sha(TAIL_AUDIT) != TAIL_AUDIT_SHA:
        raise ValueError("tail admission changed")
    admission = json.loads(TAIL_AUDIT.read_text())
    required = (tail / "request.json", tail / "continuous_table.raw.json",
                tail / "provider/raw_daily.csv", tail / "provider/quotes.json")
    if (admission["verdict"] != "PASS_TAIL_INPUT_ADMISSION"
            or admission["target"] != base.TARGET
            or set(admission["products"]) != set(ADDED)
            or any(str(path) not in admission["sha256"] for path in required)
            or any(base.portfolio.sha(Path(path)) != sha
                   for path, sha in admission["sha256"].items())):
        raise ValueError("tail admission does not match frozen data")
    reference = json.loads((STAGE047 / "receipt.json").read_text())
    expanded = base.load(base.MARKET, control=False)
    if {str(path): digest for path, digest in expanded[-1].items()} != reference["market_sha256"]:
        raise ValueError("market differs from Stage047")
    original = base.extend(base.load(base.MARKET, control=True), base.TAIL)
    products = reference["products"]
    if len(products) != 26 or set(products) - set(original[0]) != set(ADDED):
        raise ValueError("invalid fixed S26")
    market = add_tail((products, *expanded[1:]), original, tail)
    with patch.object(base.portfolio, "INITIAL", base.CAPITAL), patch.object(
        base.portfolio, "START", START
    ), redirect_stdout(StringIO()):
        base.portfolio.run(output, week_body_filter=True, reverse_after_stop=True,
                           block_four_up=True, delivery_guard=True, market_loader=lambda: market)
    daily = pd.read_csv(output / "daily.csv")
    fills = pd.read_csv(output / "fills.csv")
    control = pd.read_csv(base.PARENT / "daily.csv")
    if (not daily.date.equals(control.date) or daily.date.iat[-1] != base.TARGET
            or daily.cash.iat[0] != base.CAPITAL or daily.positions.iat[0] != 0 or not fills.volume.eq(1).all()):
        raise ValueError("unexpected start, end, calendar or size")
    base_fills = pd.read_csv(base.PARENT / "fills.csv")
    for product in original[0]:
        control_fills = base_fills.query("product == @product")
        candidate = fills.query("product == @product")
        pd.testing.assert_frame_equal(candidate.drop(columns="cycle").reset_index(drop=True),
                                      control_fills.drop(columns="cycle").reset_index(drop=True))
    terminal = json.loads((output / "terminal.json").read_text())
    gaps = pd.read_csv(output / "gaps.csv")
    if (any((base.TARGET, pos["epoch"]) not in market[5] for pos in terminal["positions"].values())
            or gaps.date.eq(base.TARGET).any()):
        raise ValueError("unresolved execution or mark coverage on final day")

    opening = base.reconstruct_opening(daily, fills, market)
    opening.to_csv(output / "opening_funding.csv", index=False)
    summary_path = output / "summary.json"
    summary = json.loads(summary_path.read_text())
    s26 = base.metrics(output, daily, opening, summary)
    summary["days_margin_above_equity"] = s26["close_deficit_days"]
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    s19 = base.metrics(base.PARENT, control, pd.read_csv(base.PARENT / "opening_funding.csv"),
                       json.loads((base.PARENT / "summary.json").read_text()))

    annual = pd.DataFrame({"s19": control.groupby(control.date.str[:4]).net_pnl.sum(),
                           "s26": daily.groupby(daily.date.str[:4]).net_pnl.sum()})
    annual["difference"] = annual.s26 - annual.s19
    annual.index.name = "year"
    annual.to_csv(output / "annual_comparison.csv")
    cycles = pd.read_csv(output / "cycles.csv")
    added_pnl = cycles.loc[cycles["product"].isin(ADDED)].groupby("product").net_pnl.sum().to_dict()
    if abs(s26["net_pnl"] - s19["net_pnl"] - sum(added_pnl.values())) > 1e-6:
        raise ValueError("unreconciled PnL attribution")
    comparison = dict(start=daily.date.iat[0], end=base.TARGET, days=len(daily), capital=base.CAPITAL,
                      s19=s19, s26=s26, added_pnl=added_pnl,
                      difference_before_2022=annual.loc[:"2021", "difference"].sum(),
                      difference_2022=annual.loc["2022", "difference"],
                      difference_after_2022=annual.loc["2023":, "difference"].sum())
    (output / "comparison.json").write_text(json.dumps(comparison, indent=2, allow_nan=False) + "\n")
    receipt = dict(
        stage047_manifest_sha256=STAGE047_SHA, stage037_manifest_sha256=base.PARENT_SHA,
        engine_sha256=ENGINE_SHA, design_sha256=base.portfolio.sha(DESIGN),
        tail_admission_sha256=TAIL_AUDIT_SHA,
        entrypoint_sha256=base.portfolio.sha(Path(__file__)), products=products,
        start=START, end=base.TARGET, capital=base.CAPITAL,
        market_sha256={str(path): digest for path, digest in market[-1].items()},
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    base.write_checksums(output, (path for path in output.rglob("*") if path.is_file()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("tail", type=Path)
    args = parser.parse_args()
    run(args.output, args.tail.resolve())
