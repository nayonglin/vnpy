"""Fetch daily market observations only, for the Stage024 fixed expansion."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import signal
import time

import pandas as pd
from tqsdk import TqApi, TqAuth, TqSim


def deny_orders(*args, **kwargs):
    raise RuntimeError("market data only")


def fetch(request_path, credentials_path, output):
    request = json.loads(request_path.read_text())
    credentials = json.loads(credentials_path.read_text())
    TqApi.insert_order = deny_orders
    TqApi.cancel_order = deny_orders
    output.mkdir(parents=True)
    start, end = request["start"], request["end"]
    quotes, series = {}, {}
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("market data deadline")))
    signal.alarm(95)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            auth = TqAuth(credentials["datafeed.username"], credentials["datafeed.password"])
            with TqApi(TqSim(), auth=auth, disable_print=True, debug=False) as api:
                async def subscribe():
                    for symbol in request["symbols"]:
                        code, exchange = symbol.split(".")
                        native = f"{exchange}.{code}"
                        quotes[symbol] = api.get_quote(native)
                        series[symbol] = api.get_kline_serial(native, 86400, 30)

                api.create_task(subscribe())
                deadline = time.monotonic() + 75
                while len(series) != len(request["symbols"]) or not all(
                    api.is_serial_ready(series[symbol]) and quotes[symbol].get("instrument_id")
                    for symbol in request["symbols"]
                ):
                    if time.monotonic() > deadline:
                        raise TimeoutError("daily serials incomplete")
                    api.wait_update(deadline=time.time() + 1)
                frames = {symbol: frame.copy() for symbol, frame in series.items()}
                fields = ("instrument_id", "ins_class", "delivery_year", "delivery_month",
                          "expire_datetime", "price_tick", "volume_multiple")
                quote_data = {symbol: {field: quote.get(field) for field in fields}
                              for symbol, quote in quotes.items()}
        rows = []
        for symbol, frame in frames.items():
            frame = frame.loc[frame.id.ge(0) & frame.datetime.gt(0)].copy()
            frame["date"] = pd.to_datetime(frame.datetime, unit="ns", utc=True).dt.tz_convert(
                "Asia/Shanghai"
            ).dt.strftime("%Y-%m-%d")
            frame = frame.loc[frame.date.between(start, end)].assign(vt_symbol=symbol)
            rows.append(frame[["vt_symbol", "date", "id", "datetime", "open", "high", "low", "close",
                               "volume", "close_oi"]])
        pd.concat(rows, ignore_index=True).to_csv(output / "raw_daily.csv", index=False)
        (output / "quotes.json").write_text(json.dumps(quote_data, default=lambda v: v.item(), indent=2) + "\n")
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("credentials", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        fetch(args.request, args.credentials, args.output)
    except Exception as exc:
        # Credentials and provider connection detail stay out of logs.
        (args.output / "failure.json").write_text(json.dumps({"type": type(exc).__name__}) + "\n")
        raise SystemExit(type(exc).__name__)
