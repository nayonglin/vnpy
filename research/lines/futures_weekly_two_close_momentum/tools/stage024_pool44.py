"""Stage024 fixed pool extension of the Stage022 S replay."""
import argparse
import json
from pathlib import Path

import pandas as pd

import run_weekly_portfolio as portfolio

LINE = Path(__file__).resolve().parents[1]
ARCHIVE = Path("/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/"
               "futures_weekly_formal_no_half_r/outputs/stage040_data_approved")
OLD_END = "2026-10-28"
BASE = LINE / "outputs/stage022_S_2015_20261103"
DESIGN = LINE / "stages/20261104_1409_stage024_expand_s_to44.md"
RAW_MAPPING = portfolio.DATA.parent / "continuous_table_20261103.raw.json"
BAR_COLUMNS = ["date", "vt_symbol", "contract_epoch_id", "contract_yyyymm",
               "open", "high", "low", "close", "volume"]
MAPPING_COLUMNS = ["date", "continuous_symbol_vt", "main_contract_vt"]


def source_hashes():
    archive_manifest = ARCHIVE / "source_manifest.json"
    files = json.loads(archive_manifest.read_text())["files"]
    names = ("receipt.json", "physical_epoch_daily.csv", "mapping.csv",
             "physical_epochs.csv", "specification.json", "stage020_universe.csv")
    pins = {ARCHIVE / name: files[str(ARCHIVE / name)] for name in names}
    pins[archive_manifest] = portfolio.sha(archive_manifest)
    pins[BASE / "inputs.json"] = next(
        row.split()[0] for row in (BASE / "SHA256SUMS").read_text().splitlines()
        if row.endswith("  inputs.json")
    )
    verify(pins)
    return pins


def verify(pins):
    for path, expected in pins.items():
        if portfolio.sha(path) != expected:
            raise ValueError(f"frozen source mismatch: {path}")


def product_of(symbols):
    return symbols.str.replace(r"\d+(?=\.)", "", regex=True)


def append_tail(market, mapping, historical, tail, new_products):
    request_path = market / "tail_request.json"
    request = json.loads(request_path.read_text())
    days = request["days"]
    if days != ["2026-10-29", "2026-10-30", "2026-11-02", "2026-11-03"]:
        raise ValueError("unexpected extension dates")
    source = json.loads(RAW_MAPPING.read_text())
    tail_mapping = []
    for product in new_products:
        code, exchange = product.split(".")
        entries = source[f"{exchange}.{code}"]
        for day in [OLD_END, *days]:
            _, native = max(row for row in entries if row[0] <= day.replace("-", ""))
            native_exchange, contract = native.split(".")
            if native_exchange != exchange or contract.rstrip("0123456789") != code:
                raise ValueError(f"bad mapping identity: {product} {day}")
            symbol = f"{contract}.{exchange}"
            if day == OLD_END:
                prior = mapping.loc[(mapping.date == day) & (mapping.continuous_symbol_vt == product)]
                if prior.main_contract_vt.tolist() != [symbol]:
                    raise ValueError(f"tail source disagrees at seam: {product}")
            else:
                if request["mains"][f"{day}/{product}"] != symbol:
                    raise ValueError(f"request mapping mismatch: {product} {day}")
                tail_mapping.append((day, product, symbol))

    raw = pd.read_csv(tail / "raw_daily.csv")
    if (raw.duplicated(["date", "vt_symbol"]).any() or not raw.date.isin(days).all()
            or not raw.vt_symbol.isin(request["symbols"]).all()):
        raise ValueError("raw tail keys are inconsistent")
    quotes = json.loads((tail / "quotes.json").read_text())
    if set(quotes) != set(request["symbols"]):
        raise ValueError("tail quote coverage mismatch")
    expiry = pd.read_csv(ARCHIVE / "physical_epochs.csv", dtype=str, keep_default_na=False)
    expiry = expiry.loc[expiry.vt_symbol.isin(request["symbols"]) & expiry.contract_yyyymm.ge("202610")]
    expiry = expiry.set_index("vt_symbol", verify_integrity=True)
    tail_bars = []
    for row in raw.loc[raw.volume.gt(0)].itertuples(index=False):
        quote = quotes[row.vt_symbol]
        epoch = expiry.loc[row.vt_symbol]
        code, exchange = row.vt_symbol.split(".")
        delivery = f'{int(quote["delivery_year"]):04d}{int(quote["delivery_month"]):02d}'
        day = pd.to_datetime(row.datetime, unit="ns", utc=True).tz_convert("Asia/Shanghai").date().isoformat()
        last = pd.to_datetime(quote["expire_datetime"], unit="s", utc=True).tz_convert("Asia/Shanghai").date().isoformat()
        if (row.date != day or day > last or quote["instrument_id"] != f"{exchange}.{code}"
                or quote["ins_class"] != "FUTURE" or delivery != epoch.contract_yyyymm
                or not 0 < row.low <= min(row.open, row.close) <= max(row.open, row.close) <= row.high):
            raise ValueError(f"invalid tail bar: {row.vt_symbol} {row.date}")
        tail_bars.append((day, row.vt_symbol, epoch.contract_epoch_id, delivery,
                          row.open, row.high, row.low, row.close, row.volume))
    added = pd.DataFrame(tail_bars, columns=BAR_COLUMNS)
    added_map = pd.DataFrame(tail_mapping, columns=MAPPING_COLUMNS)
    required = set(zip(added_map.date, added_map.main_contract_vt))
    if required - set(zip(added.date, added.vt_symbol)):
        raise ValueError(f"tail main coverage incomplete: {sorted(required - set(zip(added.date, added.vt_symbol)))}")
    return pd.concat([historical, added], ignore_index=True), pd.concat([mapping, added_map], ignore_index=True)


def prepare(destination, market, tail):
    pins = source_hashes()
    base_inputs = json.loads((BASE / "inputs.json").read_text())
    originals = set(base_inputs["products"])
    universe = pd.read_csv(ARCHIVE / "stage020_universe.csv")
    products = set(universe.product_vt_symbol)
    if len(universe) != len(products) or len(products) != 44 or len(originals) != 19 or not originals <= products:
        raise ValueError("universe does not preserve the original 19")
    if not universe.eligible.eq(1).all():
        raise ValueError("ineligible source product")
    new_products = sorted(products - originals)
    old_market = portfolio.load_market()
    days = set(old_market[1])
    historical = pd.read_csv(ARCHIVE / "physical_epoch_daily.csv", usecols=BAR_COLUMNS,
                             dtype={"contract_yyyymm": str})
    historical = historical.loc[product_of(historical.vt_symbol).isin(new_products) & historical.date.isin(days)]
    mapping = pd.read_csv(ARCHIVE / "mapping.csv", usecols=MAPPING_COLUMNS, dtype=str, keep_default_na=False)
    mapping = mapping.loc[mapping.continuous_symbol_vt.isin(new_products) & mapping.date.isin(days)]
    end = OLD_END
    if tail is not None:
        historical, mapping = append_tail(market, mapping, historical[BAR_COLUMNS], tail, new_products)
        end = portfolio.END
        for path in (market / "tail_request.json", RAW_MAPPING, tail / "raw_daily.csv", tail / "quotes.json"):
            pins[path] = portfolio.sha(path)
    price = historical[["open", "high", "low", "close", "volume"]]
    if (historical.duplicated(["date", "vt_symbol"]).any()
            or historical.duplicated(["date", "contract_epoch_id"]).any()
            or mapping.duplicated(["date", "continuous_symbol_vt"]).any()
            or not (price.gt(0) & price.lt(float("inf"))).all().all()
            or not (historical.low.le(historical[["open", "close"]].min(axis=1))
                    & historical.high.ge(historical[["open", "close"]].max(axis=1))).all()):
        raise ValueError("invalid expanded market data")
    specs = json.loads((ARCHIVE / "specification.json").read_text())
    # Entry and roll targets always come from the main map. Other physical
    # bars are retained as evidence, but cannot introduce a new position.
    symbols = sorted(set(mapping.main_contract_vt) - {""})
    spec_keys = ("sizes", "slippages", "rates", "margin_ratios")
    new_specs = {key: {symbol: specs[key][symbol] for symbol in symbols} for key in spec_keys}
    if set(new_specs["rates"].values()) != {0.0}:
        raise ValueError("expanded pool must preserve zero commission")
    verify(pins)
    destination.mkdir(parents=True)
    historical[BAR_COLUMNS].to_csv(destination / "added_bars.csv", index=False)
    mapping[MAPPING_COLUMNS].to_csv(destination / "added_mapping.csv", index=False)
    (destination / "added_specs.json").write_text(json.dumps(new_specs, sort_keys=True) + "\n")
    inputs = {**pins, **old_market[-1], Path(__file__): portfolio.sha(Path(__file__)),
              DESIGN: portfolio.sha(DESIGN)}
    for file in destination.iterdir():
        inputs[file] = portfolio.sha(file)
    receipt = dict(end=end, originals=sorted(originals), products=sorted(products),
                   added_products=new_products, added_bars=len(historical), added_mapping=len(mapping),
                   inputs_sha256={str(path): digest for path, digest in inputs.items()})
    (destination / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"{end}: {len(historical)} added physical bars, {len(mapping)} mapping rows, {len(symbols)} contracts")


def load_expanded(approved, control):
    receipt_path = approved / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    pins = {Path(path): digest for path, digest in receipt["inputs_sha256"].items()}
    verify(pins)
    products, days, weeks, week_index, rows, by_epoch, mains, specs, _ = portfolio.load_market()
    if products != receipt["originals"]:
        raise ValueError("frozen S pool mismatch")
    end = receipt["end"]
    days = [day for day in days if day <= end]
    if not control:
        products = receipt["products"]
        bars = pd.read_csv(approved / "added_bars.csv", dtype={"contract_yyyymm": str})
        mapping = pd.read_csv(approved / "added_mapping.csv", dtype=str, keep_default_na=False)
        added_specs = json.loads((approved / "added_specs.json").read_text())
        new_rows = {(row.date, row.vt_symbol): row for row in bars.itertuples(index=False)}
        new_epochs = {(row.date, row.contract_epoch_id): row for row in new_rows.values()}
        new_mains = {(row.date, row.continuous_symbol_vt): row.main_contract_vt for row in mapping.itertuples(index=False)}
        if (new_rows.keys() & rows.keys() or new_epochs.keys() & by_epoch.keys()
                or new_mains.keys() & mains.keys()
                or any(added_specs[key].keys() & specs[key].keys() for key in added_specs)):
            raise ValueError("extension would overwrite frozen S")
        rows.update(new_rows)
        by_epoch.update(new_epochs)
        mains.update(new_mains)
        for key, values in added_specs.items():
            specs[key].update(values)
    return products, days, weeks, week_index, rows, by_epoch, mains, specs, {
        **pins, receipt_path: portfolio.sha(receipt_path),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "control", "expand"))
    parser.add_argument("market", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tail", type=Path)
    args = parser.parse_args()
    args.market = args.market.resolve()
    if args.action == "prepare":
        prepare(args.output.resolve(), args.market, args.tail.resolve() if args.tail else None)
    else:
        portfolio.run(args.output, week_body_filter=True, reverse_after_stop=True, block_four_up=True,
                      market_loader=lambda: load_expanded(args.market, args.action == "control"))
