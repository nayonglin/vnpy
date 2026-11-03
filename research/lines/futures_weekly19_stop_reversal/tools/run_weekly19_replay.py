"""Offline portfolio replay of the pinned Weekly19 release."""
import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
EXAMPLES = ROOT / "examples/portfolio_backtesting"
sys.path[:0] = [str(ROOT), str(EXAMPLES)]
from vnpy.trader.constant import Interval, Offset, Status
from vnpy.trader.object import TradeData
from vnpy.trader.setting import SETTINGS

SETTINGS.update({"log.active": False, "log.file": False, "log.console": False})
from vnpy_portfoliostrategy.backtesting import BacktestingEngine
from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
from qmt_roll_weekly19_runtime import verify_frozen_sources
from weekly19_frozen import contract_metadata
from weekly19_frozen.base847 import QmtRollPortfolioStrategyStage847C9StopRetry
from weekly19_frozen.main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from weekly19_frozen.stage005_short_bottom20 import RangeHistory, range_strategy_class
from weekly19_frozen.stage022_historical_safety import check_epoch_transition, historical_strategy_class
from weekly19_frozen.stage032_daily_addon import daily_addon_strategy_class
from weekly19_frozen.weekly_adapter import completed_weeks

START = "2015-01-01"
BASE = "491d13617f61cac88b94476dc36171dc81691f30"
RELEASE = "m0007_20261102T215359+0800_b3f6b041a738"
ASSETS = EXAMPLES / "weekly19_assets"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")


def fixed_settings(mapping, empty):
    manifest = verify_frozen_sources()
    path = ASSETS / "actual_settings.json"
    if digest(path) != manifest["settings_asset_sha256"]:
        raise ValueError("fixed settings hash mismatch")
    asset = json.loads(path.read_text())
    for name, row in asset["assets"].items():
        if digest(ASSETS / name) != row["sha256"]:
            raise ValueError(f"fixed asset hash mismatch: {name}")
    settings = asset["settings"]
    for key, value in settings.items():
        if not isinstance(value, str) or not value.startswith("@"):
            continue
        category, name = value.split("/", 1)
        settings[key] = str({
            "@ASSET": ASSETS / name,
            "@INPUT": mapping,
            "@DISABLED": empty / name,
            "@EMPTY": empty / name,
        }[category])
    settings["trade_start_date"] = START
    return settings


class DailyOpenReplay(BacktestingEngine):
    """Fill once against a real next trading-day open, as in Stage014."""

    def __init__(self, calendar, epoch_lookup):
        super().__init__()
        self.next_day = dict(zip(calendar, calendar[1:]))
        self.epoch_lookup = epoch_lookup
        self.days_run = []
        self.fills = []
        self.open_sleeve = {}

    def new_bars(self, dt):
        self.days_run.append(str(dt.date()))
        super().new_bars(dt)

    def cross_limit_order(self):
        day = str(self.datetime.date())
        real = {
            symbol: bar for symbol in self.vt_symbols
            if (bar := self.history_data.get((self.datetime, symbol))) is not None
        }
        check_epoch_transition(self, self.datetime, real, self.epoch_lookup)
        for order in list(self.active_limit_orders.values()):
            symbol = order.vt_symbol
            bar = real.get(symbol)
            if self.next_day.get(str(order.datetime.date())) != day or bar is None or bar.volume <= 0:
                raise ValueError(f"strict next daily open missing: {day} {symbol}")
            self.fill_at_open(order, bar)

    def fill_at_open(self, order, bar):
        strategy = self.strategy
        if order.status == Status.SUBMITTING:
            order.status = Status.NOTTRADED
            strategy.update_order(order)
        order.traded = order.volume
        order.status = Status.ALLTRADED
        strategy.update_order(order)
        self.active_limit_orders.pop(order.vt_orderid)
        self.trade_count += 1
        trade = TradeData(
            symbol=order.symbol, exchange=order.exchange, orderid=order.orderid,
            tradeid=str(self.trade_count), direction=order.direction, offset=order.offset,
            price=float(bar.open_price), volume=order.volume, datetime=self.datetime,
            gateway_name=self.gateway_name,
        )
        trade.trading_date = self.datetime.date()
        trade.signal_datetime = order.datetime
        trade.signal_order_id = order.vt_orderid
        strategy.update_trade(trade)
        self.trades[trade.vt_tradeid] = trade
        self.fills.append(dict(
            trade_id=trade.vt_tradeid, date=str(trade.trading_date), symbol=trade.vt_symbol,
            side=trade.direction.name.lower(), offset=trade.offset.name.lower(),
            price=trade.price, volume=trade.volume, signal_day=str(order.datetime.date()),
            reason=strategy.trade_reason_by_trade_id.get(trade.vt_tradeid, ""),
            commission=trade.price * trade.volume * self.sizes[trade.vt_symbol] * self.rates[trade.vt_symbol],
            slippage=trade.volume * self.sizes[trade.vt_symbol] * self.slippages[trade.vt_symbol],
        ))
        return trade


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--reserve-wrapper", type=Path, required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--arm", choices=("A", "C"), required=True)
    args = parser.parse_args()
    if Path.cwd() != ROOT:
        raise ValueError("run from isolated checkout root")
    out = args.out.resolve()
    out.mkdir(parents=True)
    data = args.data.resolve()
    identity = assert_official_checkout_matches_active_material(ROOT)
    if identity.material_release_id != RELEASE:
        raise ValueError("formal material drift")
    if subprocess.check_output(["git", "diff", "--name-only", BASE, "--", "examples", "official_strategy_materials"], text=True).strip():
        raise ValueError("formal source drift")
    reserve_path = args.reserve_wrapper.resolve()
    sys.path.insert(0, str(reserve_path.parent))
    from stage014_reserve import reserve_strategy_class
    if reserve_path.name != "stage014_reserve.py":
        raise ValueError("unexpected reserve wrapper name")
    mapping = data / "mapping.csv"
    files = [mapping, data / "daily.sqlite", data / "physical_epoch_daily.csv", data / "metadata.csv", reserve_path]
    source_hashes = [
        Path(__file__).resolve(), Path(__file__).with_name("reversal_replay.py"),
        Path(__file__).with_name("weekly_stop_reversal.py"),
    ]
    if (data / "forward_calendar.csv").is_file():
        receipt = json.loads((data / "receipt.json").read_text())
        if receipt["date_end"] != args.end or not receipt["data_ready_for_bounded_replay"]:
            raise ValueError("data cutoff/authority mismatch")
        files += [data / name for name in ("receipt.json", "forward_calendar.csv", "source_manifest.json")]
    if args.arm == "C" and not (data / "forward_calendar.csv").is_file():
        raise ValueError("candidate needs admitted replay calendar")
    write_json(out / "inputs.json", {
        "identity": asdict(identity), "arm": args.arm, "start": START, "end": args.end,
        "inputs_sha256": {str(path): digest(path) for path in [*files, *source_hashes]},
        "execution": "declared daily open model",
        "reverse_execution": "next trading day open after flat, within same execution week" if args.arm == "C" else None,
        "python": sys.version, "study_git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    })
    import vnpy.trader.database as database
    import vnpy_sqlite.sqlite_database as driver
    if not driver.db.is_closed():
        driver.db.close()
    driver.db.init(str(data / "daily.sqlite"), pragmas={"query_only": 1})
    database.database = driver.SqliteDatabase()
    contract_metadata.ALL_FUTURES_CONTRACT_METADATA_PATH = data / "metadata.csv"
    settings = fixed_settings(mapping, out / "nonexistent")
    products = load_product_universe_symbols(settings["product_universe_csv_path"])
    if len(products) != 19:
        raise ValueError("formal universe drift")
    metadata = build_contract_metadata(mapping, products)
    settings["margin_ratios"] = metadata["margin_ratios"]
    rows = pd.read_csv(mapping, usecols=["date", "continuous_symbol_vt"])
    calendar = sorted(set(rows.loc[rows.continuous_symbol_vt.isin(products), "date"]))
    if args.end not in calendar:
        raise ValueError("requested cutoff missing from calendar")
    epochs = pd.read_csv(data / "physical_epoch_daily.csv", dtype={"date": str})
    if epochs.duplicated(["vt_symbol", "date"]).any():
        raise ValueError("duplicate physical epoch")
    epoch_lookup = {(row.vt_symbol, row.date): row.contract_epoch_id for row in epochs.itertuples(index=False)}
    forward = data / "forward_calendar.csv"
    future_days = pd.read_csv(forward).date.astype(str).tolist() if forward.is_file() else []
    execution_calendar = sorted(set(calendar).union(future_days))
    weeks = completed_weeks(execution_calendar)
    history = RangeHistory(epochs)
    base = daily_addon_strategy_class(
        QmtRollPortfolioStrategyStage847C9StopRetry, weeks, execution_calendar, epoch_lookup, enabled=False,
    )
    strategy_class = historical_strategy_class(
        reserve_strategy_class(range_strategy_class(base, history, True), history, True, START), START,
    )
    engine_class = DailyOpenReplay
    if args.arm == "C":
        from reversal_replay import reversal_engine, reversal_strategy
        engine_class = reversal_engine(engine_class)
        strategy_class = reversal_strategy(strategy_class)
    engine = engine_class(execution_calendar, epoch_lookup)
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"], interval=Interval.DAILY,
        start=datetime(2014, 1, 1), end=datetime.fromisoformat(args.end + "T23:59:59"),
        rates=metadata["rates"], slippages=metadata["slippages"], sizes=metadata["sizes"],
        priceticks=metadata["priceticks"], capital=150_000,
    )
    engine.add_strategy(strategy_class, settings)
    engine.output = lambda message: print(message, flush=True) if "Traceback" in message else None
    engine.load_data()
    print("loaded bars", len(engine.history_data), flush=True)
    engine.run_backtesting()
    if getattr(engine, "intraday_execution_failure", None):
        raise RuntimeError(engine.intraday_execution_failure)
    replay_days = [day for day in engine.days_run if START <= day <= args.end]
    expected = [day for day in calendar if START <= day <= args.end]
    if replay_days != expected:
        raise ValueError(f"incomplete replay: actual {len(replay_days)}, expected {len(expected)}; last {replay_days[-1:]}")
    result = engine.calculate_result()
    result.index.name = "date"
    result = result.loc[datetime.fromisoformat(START).date():].copy()
    snapshots = pd.DataFrame(engine.strategy.reserve_daily_snapshots)
    snapshots = snapshots.drop_duplicates("date", keep="last").set_index("date")
    result.index = result.index.astype(str)
    result = result.join(snapshots, validate="one_to_one")
    if result["total_account_equity"].isna().any():
        raise ValueError("account snapshots do not cover result dates")
    pnl_error = result["net_pnl"].cumsum() + 300_000 - result["total_account_equity"]
    if pnl_error.abs().max() > 1e-6:
        raise ValueError(f"account bridge residual {pnl_error.abs().max()}")
    terminal_inventory = {}
    for symbol, volume in engine.strategy.pos_data.items():
        if not volume:
            continue
        bar = engine.history_data.get((engine.datetime, symbol))
        if bar is None or bar.volume <= 0:
            raise ValueError(f"terminal held contract is missing real positive bar: {symbol}")
        terminal_inventory[symbol] = dict(
            volume=int(volume), close=bar.close_price, sleeve=engine.open_sleeve.get(symbol, "native"),
        )
    result.to_csv(out / "daily.csv")
    pd.DataFrame(engine.fills).to_csv(out / "trades.csv", index=False)
    write_json(out / "reserve_events.json", engine.strategy.reserve_transfer_events)
    write_json(out / "contract_settings.json", {
        name: metadata[name] for name in ("sizes", "rates", "slippages", "priceticks", "margin_ratios")
    })
    write_json(out / "terminal_inventory.json", terminal_inventory)
    if args.arm == "C":
        pd.DataFrame(engine.reversal_decisions).to_csv(out / "reversal_decisions.csv", index=False)
    print(f"{args.arm}: {len(result)} days, {len(engine.fills)} fills", flush=True)


if __name__ == "__main__":
    main()
