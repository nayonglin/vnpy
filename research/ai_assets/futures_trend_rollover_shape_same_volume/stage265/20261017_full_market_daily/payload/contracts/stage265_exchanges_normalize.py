"""Offline official ordinary-futures daily reference normalization.

Preserves original volume and closing OI. Never writes the main database.
Empty OHLC never becomes zero or a forward-filled candle. Raw archives retain
options, TAS, aggregate and metadata rows; all ordinary no-trade rows also have
a separate table. XLSX is read using standard-library XML, XLS via xlrd.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

import xlrd
from stage265_exchanges_official_archives import OUT, digest, now, save

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
INE_PRODUCTS = {"sc", "nr", "lu", "bc", "ec"}
HEADER = {"instrument": ("合约", "合约代码"), "date": ("日期", "交易日期"),
          "open": ("开盘价", "今开盘"), "high": ("最高价",), "low": ("最低价",),
          "close": ("收盘价", "今收盘"), "volume": ("成交量",),
          "open_interest": ("持仓量",), "settle": ("结算价", "今结算"),
          "pre_settle": ("前结算",), "turnover": ("成交金额", "成交金额(万元)")}
FIELDS = ["exchange", "product", "source_symbol", "contract_yyyymm", "contract_epoch_id",
          "vt_symbol", "date", "open", "high", "low", "close", "volume", "open_interest",
          "settle", "pre_settle", "turnover", "source_id", "unit_regime", "oi_timing",
          "source_member", "source_sheet", "source_row", "row_quality"]


def text(value):
    if isinstance(value, (int, float)) and math.isfinite(value) and value == int(value):
        return str(int(value))
    return str(value).strip()


def xlsx_sheets(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in root]
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        names = [s.attrib["name"] for s in workbook.iter(NS + "sheet")]
        files = sorted((n for n in z.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)),
                       key=lambda n: int(re.search(r"sheet(\d+)", n).group(1)))
        notes = [s for s in strings if any(w in s for w in ("单位", "单边", "双边", "注：", "注:"))]
        for number, filename in enumerate(files):
            def rows(filename=filename):
                with z.open(filename) as f:
                    for _, elem in ET.iterparse(f, events=("end",)):
                        if elem.tag != NS + "row":
                            continue
                        values = []
                        for c in elem.findall(NS + "c"):
                            letters = re.match(r"[A-Z]+", c.attrib["r"]).group()
                            index = 0
                            for letter in letters:
                                index = index * 26 + ord(letter) - 64
                            while len(values) < index:
                                values.append("")
                            v = c.find(NS + "v")
                            raw = "" if v is None else v.text or ""
                            kind = c.attrib.get("t")
                            if kind == "s":
                                raw = strings[int(raw)] if raw else ""
                            elif kind == "inlineStr":
                                raw = "".join(t.text or "" for t in c.iter(NS + "t"))
                            values[index - 1] = raw
                        yield int(elem.attrib.get("r", 0)), values
                        elem.clear()
            yield names[number] if number < len(names) else filename, rows(), notes


def sheets(blob):
    if blob.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        book = xlrd.open_workbook(file_contents=blob, on_demand=True)
        try:
            for sheet in book.sheets():
                notes = [text(v) for row in range(max(0, sheet.nrows - 20), sheet.nrows)
                         for v in sheet.row_values(row) if any(w in text(v) for w in ("单位", "单边", "双边", "注：", "注:"))]
                yield sheet.name, ((i + 1, sheet.row_values(i)) for i in range(sheet.nrows)), notes
        finally:
            book.release_resources()
    elif blob.startswith(b"PK"):
        yield from xlsx_sheets(blob)
    else:
        raise ValueError("unsupported_spreadsheet_signature")


def regime(notes, exchange):
    joined = " ".join(notes)
    if "双边" in joined:
        return "official_two_sided_volume_and_close_oi"
    if "单边" in joined:
        return "official_single_sided_volume_and_close_oi"
    if exchange == "CFFEX":
        return "cffex_official_single_sided_volume_and_close_oi"
    return "official_original_units_not_inferred"


def annual_rows(rec, notes_out):
    with zipfile.ZipFile(rec["path"]) as archive:
        for member in archive.namelist():
            if member.endswith("/"):
                continue
            blob = archive.read(member)
            for sheet, rows, notes in sheets(blob):
                note = {"source_id": rec["source_id"], "source_member": member, "source_sheet": sheet,
                        "notes": notes, "unit_regime": regime(notes, rec["exchange"])}
                notes_out.append(note)
                columns, current = None, None
                for row_number, values in rows:
                    labels = [text(v) for v in values]
                    found = {key: next((labels.index(v) for v in aliases if v in labels), None)
                             for key, aliases in HEADER.items()}
                    if all(found[k] is not None for k in ("instrument", "date", "open", "high", "low", "close", "volume", "open_interest")):
                        columns, current = found, None
                        continue
                    if columns is None:
                        continue
                    raw = {k: values[i] if i is not None and i < len(values) else "" for k, i in columns.items()}
                    instrument = text(raw["instrument"])
                    day = text(raw["date"])
                    if instrument:
                        current = instrument
                    if not current or not re.fullmatch(r"\d{8}", day):
                        continue
                    yield {**raw, "instrument": current, "date": day, "source_member": member,
                           "source_sheet": sheet, "source_row": row_number, "unit_regime": note["unit_regime"]}


def cffex_rows(rec, notes_out):
    notes_out.append({"source_id": rec["source_id"], "unit_regime": regime([], "CFFEX"),
                      "notes": ["CFFEX official statistics use single-sided volume/position; raw archive retained."]})
    with zipfile.ZipFile(rec["path"]) as z:
        for member in z.namelist():
            if not re.fullmatch(r"\d{8}_1\.csv", member):
                continue
            content = z.read(member).decode("gb18030")
            for row_number, raw in enumerate(csv.DictReader(io.StringIO(content)), 2):
                raw = {str(k).strip(): str(v).strip() if v is not None else "" for k, v in raw.items()}
                out = {key: next((raw[a] for a in aliases if a in raw), "") for key, aliases in HEADER.items() if key != "date"}
                out.update(date=member[:8], source_member=member, source_sheet="CSV", source_row=row_number,
                           unit_regime=regime([], "CFFEX"))
                yield out


def tail_rows(rec, notes_out):
    data = json.loads(Path(rec["path"]).read_text())
    if str(data["report_date"]) != rec["date"]:
        raise ValueError("daily_report_date_mismatch")
    notes_out.append({"source_id": rec["source_id"], "notes": [],
                      "unit_regime": "official_2026_single_sided_volume_and_close_oi",
                      "report_date": data["report_date"], "update_date": data.get("update_date")})
    mapping = {"open": "OPENPRICE", "high": "HIGHESTPRICE", "low": "LOWESTPRICE", "close": "CLOSEPRICE",
               "volume": "VOLUME", "open_interest": "OPENINTEREST", "settle": "SETTLEMENTPRICE",
               "pre_settle": "PRESETTLEMENTPRICE", "turnover": "TURNOVER"}
    for i, row in enumerate(data["o_curinstrument"], 1):
        product = str(row.get("PRODUCTGROUPID", "")).strip()
        delivery = str(row.get("DELIVERYMONTH", "")).strip()
        yield {"instrument": product + delivery, "date": rec["date"],
               **{k: row.get(v, "") for k, v in mapping.items()}, "source_member": Path(rec["path"]).name,
               "source_sheet": "o_curinstrument", "source_row": i,
               "unit_regime": "official_2026_single_sided_volume_and_close_oi"}


def number(v):
    raw = text(v).replace(",", "")
    if raw.lower() in ("", "-", "--", "none", "nan", "null"):
        return None
    x = float(raw)
    return x if math.isfinite(x) else None


def normalize(raw, rec):
    symbol = text(raw["instrument"])
    match = re.fullmatch(r"([A-Za-z]{1,3})(\d{4})", symbol)
    if not match:
        return None, "alternative_or_aggregate_raw_retained"
    product, yymm = match.groups()
    product = product.upper() if rec["exchange"] == "CFFEX" else product.lower()
    actual_exchange = "INE" if product.lower() in INE_PRODUCTS else rec["exchange"]
    if actual_exchange != rec["exchange"]:
        return None, "mirrored_other_exchange_raw_retained"
    rawday = text(raw["date"])
    day = date(int(rawday[:4]), int(rawday[4:6]), int(rawday[6:8]))
    delivery_year = day.year // 100 * 100 + int(yymm[:2])
    if delivery_year < day.year - 50:
        delivery_year += 100
    if delivery_year > day.year + 50:
        delivery_year -= 100
    month = int(yymm[2:])
    if not 1 <= month <= 12 or not day.year <= delivery_year <= day.year + 8:
        return None, "delivery_epoch_invalid"
    contract_yyyymm = f"{delivery_year}{month:02d}"
    numbers = {k: number(raw.get(k, "")) for k in ("open", "high", "low", "close", "volume", "open_interest", "settle", "pre_settle", "turnover")}
    source_symbol = product + yymm
    out = {"exchange": actual_exchange, "product": product, "source_symbol": source_symbol,
           "contract_yyyymm": contract_yyyymm, "contract_epoch_id": f"{product}.{actual_exchange}:{contract_yyyymm}",
           "vt_symbol": f"{source_symbol}.{actual_exchange}", "date": day.isoformat(), **numbers,
           "source_id": rec["source_id"], "unit_regime": raw["unit_regime"], "oi_timing": "close_end_of_day",
           **{k: raw[k] for k in ("source_member", "source_sheet", "source_row")}, "row_quality": "valid_ohlc"}
    if (day.year, day.month) > (delivery_year, month):
        out["row_quality"] = "after_delivery_month"
    elif numbers["volume"] is None or numbers["open_interest"] is None:
        out["row_quality"] = "missing_volume_or_oi"
    elif numbers["volume"] < 0 or numbers["open_interest"] < 0:
        out["row_quality"] = "negative_volume_or_oi"
    elif any(numbers[k] is None or numbers[k] <= 0 for k in ("open", "high", "low", "close")):
        out["row_quality"] = "no_trade_missing_ohlc" if numbers["volume"] == 0 else "invalid_ohlc"
    elif not numbers["low"] <= min(numbers["open"], numbers["close"]) <= max(numbers["open"], numbers["close"]) <= numbers["high"]:
        out["row_quality"] = "inconsistent_ohlc"
    elif numbers["volume"] == 0:
        out["row_quality"] = "no_trade_with_valid_ohlc"
    return out, out["row_quality"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exchange", nargs="+", default=["SHFE", "INE", "CFFEX"])
    parser.add_argument("--resume", action="store_true", help="Reuse per-source outputs only after parser/raw/output SHA verification")
    args = parser.parse_args()
    output = OUT / "normalized"
    output.mkdir(parents=True, exist_ok=True)
    sources = []
    for name in ("official_archive_sources_manifest.json", "cffex_month_sources_manifest.json", "official_tail_sources_manifest.json"):
        path = OUT / name
        if path.exists():
            sources.extend(r for r in json.loads(path.read_text())["sources"]
                           if r.get("status") in ("downloaded", "reused_stage264") and r["exchange"] in args.exchange)
    inventory, notes, coverage = [], [], defaultdict(lambda: {"rows": 0, "min_date": "9999", "max_date": "0000", "contracts": set()})
    parser_sha = digest(__file__)
    def add_coverage(row):
        group = coverage[(row["exchange"], row["product"])]
        group["rows"] += 1
        group["min_date"] = min(group["min_date"], row["date"])
        group["max_date"] = max(group["max_date"], row["date"])
        group["contracts"].add(row["contract_yyyymm"])
    for rec in sources:
        path = Path(rec["path"])
        if digest(path) != rec["sha256"]:
            raise ValueError(f"source_sha_mismatch:{rec['source_id']}")
        cache_path = output / (rec["source_id"] + ".inventory.json")
        if args.resume and cache_path.exists():
            cached = json.loads(cache_path.read_text())
            if cached.get("parser_sha256") == parser_sha and cached["raw_sha256"] == rec["sha256"]:
                for prefix in ("normalized", "no_trade", "rejected"):
                    if digest(cached[prefix + "_path"]) != cached[prefix + "_sha256"]:
                        raise ValueError("normalized_cache_sha_mismatch")
                with gzip.open(cached["normalized_path"], "rt", newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        add_coverage(row)
                inventory.append(cached)
                notes.extend(cached.get("notes", []))
                print(json.dumps({"source_id": rec["source_id"], "action": "verified_normalized_cache"}), flush=True)
                continue
        valid_path = output / (rec["source_id"] + ".csv.gz")
        no_trade_path = output / (rec["source_id"] + "_no_trade.csv.gz")
        rejects_path = output / (rec["source_id"] + "_rejected.csv.gz")
        counts, samples, seen = Counter(), [], {}
        note_start = len(notes)
        reader = tail_rows if "_daily_" in rec["source_id"] else cffex_rows if rec["exchange"] == "CFFEX" else annual_rows
        with gzip.open(valid_path, "wt", newline="", encoding="utf-8") as good, gzip.open(no_trade_path, "wt", newline="", encoding="utf-8") as nt, gzip.open(rejects_path, "wt", newline="", encoding="utf-8") as bad:
            writers = [csv.DictWriter(f, fieldnames=FIELDS) for f in (good, nt, bad)]
            for w in writers:
                w.writeheader()
            for raw in reader(rec, notes):
                counts["raw_data_rows"] += 1
                try:
                    row, reason = normalize(raw, rec)
                except (ValueError, TypeError, KeyError) as error:
                    raise ValueError(f"normalization_failure:{rec['source_id']}:{raw.get('source_member')}:{raw.get('source_row')}:{type(error).__name__}") from error
                counts[reason] += 1
                if row is None:
                    if len(samples) < 20:
                        samples.append({"reason": reason, **raw})
                    continue
                if row["volume"] == 0:
                    writers[1].writerow(row)
                    counts["no_trade_rows_separate"] += 1
                if reason not in ("valid_ohlc", "no_trade_with_valid_ohlc"):
                    writers[2].writerow(row)
                    continue
                key = (row["exchange"], row["source_symbol"], row["date"])
                fingerprint = tuple(row[k] for k in ("open", "high", "low", "close", "volume", "open_interest", "settle", "pre_settle"))
                if key in seen:
                    if seen[key] != fingerprint:
                        raise ValueError(f"conflicting_duplicate:{rec['source_id']}:{key}")
                    counts["identical_duplicate_extra_rows"] += 1
                    continue
                seen[key] = fingerprint
                writers[0].writerow(row)
                counts["accepted_rows"] += 1
                add_coverage(row)
        info = {"source_id": rec["source_id"], "exchange": rec["exchange"], "raw_path": str(path), "raw_sha256": rec["sha256"],
                "counts": dict(counts), "excluded_samples": samples,
                "normalized_path": str(valid_path), "normalized_sha256": digest(valid_path), "normalized_bytes": valid_path.stat().st_size,
                "no_trade_path": str(no_trade_path), "no_trade_sha256": digest(no_trade_path),
                "rejected_path": str(rejects_path), "rejected_sha256": digest(rejects_path),
                "min_date": min((key[2] for key in seen), default=None), "max_date": max((key[2] for key in seen), default=None),
                "parser_sha256": parser_sha, "notes": notes[note_start:]}
        inventory.append(info)
        save(cache_path, info)
        save(output / "inventory_progress.json", inventory)
        print(json.dumps({"source_id": rec["source_id"], "accepted_rows": counts["accepted_rows"], "no_trade": counts["no_trade_rows_separate"], "max_date": info["max_date"]}), flush=True)
    products = [{"exchange": k[0], "product": k[1], **{a: b for a, b in v.items() if a != "contracts"}, "contract_count": len(v["contracts"]), "contract_yyyymm": sorted(v["contracts"])} for k, v in sorted(coverage.items())]
    result = {"generated_at": now(), "script_sha256": digest(__file__), "source_count": len(sources),
              "ordinary_futures_only": True, "main_database_written": False,
              "cross_source_units_converted": False, "oi_timing": "close_end_of_day",
              "accepted_no_trade_with_complete_prices_remains_flagged": True,
              "product_coverage": products, "sources": inventory, "notes": notes}
    save(output / "official_normalization_manifest.json", result)
    print(json.dumps({"complete": True, "source_count": len(sources), "rows": sum(v["counts"].get("accepted_rows", 0) for v in inventory), "products": len(products)}))


if __name__ == "__main__":
    main()
