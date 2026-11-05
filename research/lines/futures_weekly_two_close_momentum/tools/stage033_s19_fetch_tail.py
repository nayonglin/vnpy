"""Fetch the fixed next completed day from TqSdk for the S19 research line."""
import contextlib
from datetime import date
import io
import json
from pathlib import Path
import sys

from stage024_fetch_tail import fetch
from stage025_delivery_guard import load
from stage031_s19_weekly_shape_replay import MARKET

PRIOR = "2026-11-03"
TARGET = "2026-11-04"


def prepare(output, credentials):
    import requests
    from tqsdk import TqAuth
    from tqsdk.calendar import TqContCalendar

    market = load(MARKET, control=True)
    products, _, _, _, rows, _, mains, specs, _ = market
    config = json.loads(credentials.read_text())
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        auth = TqAuth(config["datafeed.username"], config["datafeed.password"])
        auth.login()
        response = requests.get("https://files.shinnytech.com/continuous_table.json",
                                headers=auth._base_headers, timeout=25)
        response.raise_for_status()
        TqContCalendar.continuous = {f"KQ.m@{key}": value for key, value in response.json().items()}
        native_products = {f"KQ.m@{exchange}.{code}": product
                           for product in products for code, exchange in (product.split("."),)}
        calendar = TqContCalendar(date.fromisoformat(PRIOR), date.fromisoformat(TARGET),
                                  list(native_products), headers=auth._base_headers)
    frame = calendar.df.set_index(calendar.df.date.dt.strftime("%Y-%m-%d"))
    if list(frame.index) != [PRIOR, TARGET]:
        raise ValueError("provider calendar mismatch")
    mapping = {}
    for key, product in native_products.items():
        for day in (PRIOR, TARGET):
            exchange, code = frame.loc[day, key].split(".")
            if (exchange != product.split(".")[1] or code.rstrip("0123456789") != product.split(".")[0]):
                raise ValueError("provider product mismatch")
            symbol = f"{code}.{exchange}"
            if day == PRIOR and symbol != mains[day, product]:
                raise ValueError("provider mapping seam mismatch")
            if day == TARGET:
                mapping[product] = symbol

    recent = {symbol for (day, product), symbol in mains.items()
              if "2026-08-01" <= day <= PRIOR and symbol and symbol in specs["sizes"]
              and (bar := rows.get((PRIOR, symbol))) is not None and bar.contract_yyyymm >= "202611"}
    symbols = sorted(recent | set(mapping.values()))
    (output / "continuous_table.raw.json").write_bytes(response.content)
    request = dict(start=PRIOR, end=TARGET, symbols=symbols, mains=mapping)
    (output / "request.json").write_text(json.dumps(request, indent=2) + "\n")
    return output / "request.json"


if __name__ == "__main__":
    destination, credentials = map(Path, sys.argv[1:3])
    destination.mkdir(parents=True)
    try:
        request = prepare(destination, credentials)
        fetch(request, credentials, destination / "provider")
    except Exception as exc:
        (destination / "failure.json").write_text(json.dumps({"error_type": type(exc).__name__}) + "\n")
        raise SystemExit(type(exc).__name__)
