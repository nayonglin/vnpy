"""Independently admit Stage048's newly downloaded prices for the seven added products."""
import csv
from decimal import Decimal
import json
from pathlib import Path

import pandas as pd

from stage040_s19_without_gold_audit import LINE, load_json, sha

TAIL = LINE / "outputs/stage048_s26_tail/attempt002"
APPROVED = LINE / "outputs/stage024_market/approved_v1"
SEAM_RAW = APPROVED.parent / "tail_attempt002/raw_daily.csv"
ARCHIVE = Path("/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/"
               "futures_weekly_formal_no_half_r/outputs/stage040_data_approved")
PRIOR, TARGET = "2026-11-03", "2026-11-04"
ADDED = {"p.DCE", "ss.SHFE", "zn.SHFE", "ni.SHFE", "ag.SHFE", "jd.DCE", "TA.CZCE"}
BAR_FIELDS = ("open", "high", "low", "close", "volume")


def product_of(symbol):
    code, exchange = symbol.split(".")
    return f"{code.rstrip('0123456789')}.{exchange}"


def records(path, keep):
    with path.open() as stream:
        rows = [row for row in csv.DictReader(stream) if keep(row)]
    indexed = {(row["date"], row["vt_symbol"]): row for row in rows}
    assert len(indexed) == len(rows), path
    return indexed


def values(row, fields):
    return tuple(Decimal(row[key]) for key in fields)


def audit():
    paths = {
        "request": TAIL / "request.json", "mapping": TAIL / "continuous_table.raw.json",
        "prices": TAIL / "provider/raw_daily.csv", "quotes": TAIL / "provider/quotes.json",
        "prior_admitted_prices": APPROVED / "added_bars.csv", "prior_admitted_mapping": APPROVED / "added_mapping.csv",
        "prior_raw": SEAM_RAW, "archive_epochs": ARCHIVE / "physical_epochs.csv",
        "archive_specs": ARCHIVE / "specification.json", "prior_approved_specs": APPROVED / "added_specs.json",
    }
    approved_pins = load_json(APPROVED / "receipt.json")["inputs_sha256"]
    for key in ("prior_admitted_prices", "prior_admitted_mapping", "prior_raw",
                "archive_epochs", "archive_specs", "prior_approved_specs"):
        assert sha(paths[key]) == approved_pins[str(paths[key])]
    request, mapping, quotes = (load_json(paths[key]) for key in ("request", "mapping", "quotes"))
    assert (request["start"], request["end"], set(request["mains"])) == (PRIOR, TARGET, ADDED)
    assert len(request["symbols"]) == len(set(request["symbols"])) == len(quotes)
    assert set(request["symbols"]) == set(quotes)
    candidate_symbols = {symbol for symbol in request["symbols"] if product_of(symbol) in ADDED}
    assert set(request["mains"].values()) <= candidate_symbols
    prior_mains = pd.read_csv(paths["prior_admitted_mapping"], dtype=str)
    prior_mains = prior_mains.loc[prior_mains.date.eq(PRIOR)].set_index("continuous_symbol_vt", verify_integrity=True)
    verified_mains = {}
    for product, new_main in request["mains"].items():
        code, exchange = product.split(".")
        found = {}
        for day in (PRIOR, TARGET):
            eligible = [row for row in mapping[f"{exchange}.{code}"] if row[0] <= day.replace("-", "")]
            _, source = max(eligible)
            actual_exchange, symbol = source.split(".")
            assert actual_exchange == exchange
            actual = f"{symbol}.{exchange}"
            assert actual == (prior_mains.at[product, "main_contract_vt"] if day == PRIOR else new_main)
            found[day] = actual
        verified_mains[product] = found

    raw = records(paths["prices"], lambda row: True)
    assert set(raw) == {(day, symbol) for day in (PRIOR, TARGET) for symbol in request["symbols"]}
    old_admitted = records(paths["prior_admitted_prices"],
                           lambda row: row["date"] == PRIOR and row["vt_symbol"] in candidate_symbols)
    old_raw = records(paths["prior_raw"],
                      lambda row: row["date"] == PRIOR and row["vt_symbol"] in candidate_symbols)
    assert set(old_admitted) == set(old_raw) == {(PRIOR, symbol) for symbol in candidate_symbols}

    metadata = pd.read_csv(paths["archive_epochs"], dtype=str)
    metadata = metadata.loc[metadata.contract_yyyymm.ge("202611")].set_index("vt_symbol", verify_integrity=True)
    frozen_spec, approved_spec = load_json(paths["archive_specs"]), load_json(paths["prior_approved_specs"])
    admitted, expiry_metadata_differences = [], []
    for symbol in sorted(candidate_symbols):
        code, exchange = symbol.split(".")
        epoch = metadata.loc[symbol]
        quote = quotes[symbol]
        delivery = f"{int(quote['delivery_year']):04d}{int(quote['delivery_month']):02d}"
        expiration = pd.to_datetime(quote["expire_datetime"], unit="s", utc=True).tz_convert("Asia/Shanghai").date().isoformat()
        assert quote["instrument_id"] == f"{exchange}.{code}" and quote["ins_class"] == "FUTURE"
        assert epoch.product_vt_symbol == product_of(symbol) and epoch.exchange == exchange
        assert epoch.contract_yyyymm == delivery and epoch.contract_epoch_id.endswith(f".{delivery}")
        assert epoch.listed_date <= PRIOR < TARGET <= min(expiration, epoch.delisted_date, epoch.maturity_date)
        assert expiration[:7].replace("-", "") == delivery
        if not expiration == epoch.delisted_date == epoch.maturity_date:
            expiry_metadata_differences.append(dict(symbol=symbol, tq_expiry=expiration,
                                                    rq_delisted=epoch.delisted_date, rq_maturity=epoch.maturity_date))
        assert quote["volume_multiple"] == frozen_spec["sizes"][symbol] == approved_spec["sizes"][symbol]
        assert quote["price_tick"] == frozen_spec["priceticks"][symbol]
        assert old_admitted[PRIOR, symbol]["contract_epoch_id"] == epoch.contract_epoch_id
        assert values(raw[PRIOR, symbol], BAR_FIELDS) == values(old_admitted[PRIOR, symbol], BAR_FIELDS)
        assert values(raw[PRIOR, symbol], (*BAR_FIELDS, "close_oi")) == values(
            old_raw[PRIOR, symbol], (*BAR_FIELDS, "close_oi"))
        for day in (PRIOR, TARGET):
            row = raw[day, symbol]
            dt = pd.to_datetime(int(Decimal(row["datetime"])), unit="ns", utc=True).tz_convert("Asia/Shanghai")
            assert dt.date().isoformat() == day
            op, high, low, close, volume = values(row, BAR_FIELDS)
            assert 0 < low <= min(op, close) <= max(op, close) <= high and volume > 0
            tick = Decimal(str(quote["price_tick"]))
            assert all(price % tick == 0 for price in (op, high, low, close))
        row = raw[TARGET, symbol]
        admitted.append(dict(symbol=symbol, epoch=epoch.contract_epoch_id, expiry=expiration,
                             multiplier=quote["volume_multiple"], tick=quote["price_tick"],
                             date=TARGET, **{key: float(row[key]) for key in BAR_FIELDS}))
    certificate = dict(
        verdict="PASS_TAIL_INPUT_ADMISSION", original_scope="seven added Stage048 products",
        prior=PRIOR, target=TARGET, products=sorted(ADDED), request_symbols=len(request["symbols"]),
        download_rows=len(raw), added_symbols=len(admitted), added_seam_rows=len(old_admitted),
        added_target_rows=len(admitted), verified_mains=verified_mains, admitted=admitted,
        expiry_metadata_differences=expiry_metadata_differences,
        sha256={str(path): sha(path) for path in paths.values()},
    )
    Path(__file__).with_suffix(".json").write_text(json.dumps(certificate, indent=2, allow_nan=False) + "\n")
    print({key: value for key, value in certificate.items() if key not in ("sha256", "admitted")}, flush=True)


if __name__ == "__main__":
    audit()
