"""Execute the exact Stage106 source-only protocol; never fit or query market data."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "research/lines/futures_full_market_long_signal_ai/outputs/stage106_member_category_probe"
PROTOCOL = OUT / "protocol.json"
EXPECTED_PROTOCOL_SHA = "803e029e048f4e09970ecb33af74493adeb0a925c6a3e9159ac5de613c489511"
QUANTITIES = ("CJ1", "CJ2", "CJ3", "CJ1_CHG", "CJ2_CHG", "CJ3_CHG")
LOCK = threading.Lock()
BODY_BYTES = 0
GET_COUNT = 0


def dump(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def sha(body: bytes):
    return hashlib.sha256(body).hexdigest()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def numeric(row, key):
    """Keep original value/type and distinguish every missing/invalid/zero state."""
    if key not in row:
        return {"state": "missing_key", "raw": None, "type": "absent", "value": None}
    raw = row[key]
    typ = type(raw).__name__
    if raw is None:
        return {"state": "null", "raw": raw, "type": typ, "value": None}
    if isinstance(raw, bool):
        return {"state": "invalid_boolean", "raw": raw, "type": typ, "value": None}
    text = str(raw).strip()
    if text == "":
        return {"state": "empty_string", "raw": raw, "type": typ, "value": None}
    # No undocumented thousands separator, dash, or decimal coercion.
    try:
        val = Decimal(text)
        if not val.is_finite():
            state = "nonfinite"
        elif val != val.to_integral_value():
            state = "noninteger"
        else:
            number = int(val)
            return {"state": "true_zero" if number == 0 else "finite_integer", "raw": raw, "type": typ, "value": number}
    except (InvalidOperation, ValueError, TypeError):
        state = "invalid_text"
    return {"state": state, "raw": raw, "type": typ, "value": None}


def fetch(day, protocol):
    global GET_COUNT, BODY_BYTES
    url = protocol["url_template"].format(date=day)
    rec = {"date": day, "url": url, "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "attempt": 1,
           "timeout_seconds": protocol["timeout_seconds"], "automatic_retry": False, "redirect_following": False}
    body = bytearray()
    start = time.monotonic()
    response = None
    with LOCK:
        GET_COUNT += 1
        assert GET_COUNT <= protocol["new_get_max"]
    try:
        opener = build_opener(NoRedirect())
        try:
            response = opener.open(Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,*/*", "Accept-Encoding": "identity"}), timeout=protocol["timeout_seconds"])
        except HTTPError as exc:
            response = exc
        rec.update(http_status=response.code, response_url=response.geturl(), headers=dict(response.headers.items()))
        while True:
            remaining_time = protocol["timeout_seconds"] - (time.monotonic() - start)
            if remaining_time <= 0:
                raise TimeoutError("total request deadline reached")
            # Make each subsequent socket read respect the remaining total deadline.
            try:
                response.fp.raw._sock.settimeout(remaining_time)
            except AttributeError:
                pass
            with LOCK:
                room = protocol["new_body_bytes_max"] - BODY_BYTES
                if room <= 0:
                    rec["truncated"] = True
                    rec["stop_reason"] = "global_body_budget_exhausted"
                    break
                data = response.read1(min(room, 65536))
                BODY_BYTES += len(data)
            if not data:
                rec["truncated"] = False
                break
            body.extend(data)
    except Exception as exc:
        rec["error"] = type(exc).__name__ + ": " + str(exc)
        rec["truncated"] = bool(body)
    finally:
        if response is not None:
            response.close()
    data = bytes(body)
    raw = OUT / "raw" / f"pm{day}.response"
    raw.write_bytes(data)
    rec.update(bytes=len(data), sha256=sha(data), raw_path=str(raw), elapsed_seconds=round(time.monotonic() - start, 3))
    dump(OUT / "requests" / f"{day}.json", rec)
    print(json.dumps({k: rec.get(k) for k in ("date", "http_status", "bytes", "truncated", "error", "elapsed_seconds")}, ensure_ascii=False), flush=True)
    return rec


def audit(rec, reused):
    data = Path(rec["raw_path"]).read_bytes()
    result = {"date": rec["date"], "reused_stage104": reused, "http_status": rec.get("http_status"),
              "bytes": len(data), "sha256": sha(data), "raw_path": rec["raw_path"], "transport_error": rec.get("error"),
              "truncated": rec.get("truncated", False)}
    try:
        obj = json.loads(data)
    except Exception as exc:
        result.update(parse_status="not_json", parse_error=str(exc), prefix_hex=data[:32].hex())
        return result, [], []
    if not isinstance(obj, dict) or not isinstance(obj.get("o_cursor"), list):
        result.update(parse_status="schema_unrecognized", top_level_type=type(obj).__name__, top_level_keys=list(obj) if isinstance(obj, dict) else [])
        return result, [], []
    rows = obj["o_cursor"]
    if any(not isinstance(r, dict) for r in rows):
        result.update(parse_status="non_mapping_row", top_level_keys=list(obj))
        return result, [], []
    fields = sorted({k for r in rows for k in r})
    contracts = sorted({str(r.get("INSTRUMENTID", "")).strip() for r in rows if re.fullmatch(r"[A-Za-z]+\d{4}", str(r.get("INSTRUMENTID", "")).strip())})
    products = sorted({re.sub(r"\d+$", "", x).lower() for x in contracts})
    category_rows = [r for r in rows if str(r.get("INSTRUMENTID", "")).strip().lower().endswith("all")]
    categories = []
    for idx, row in enumerate(category_rows):
        item = {"date": rec["date"], "category_row_index": idx, "instrument": str(row.get("INSTRUMENTID", "")).strip(),
                "product": str(row.get("INSTRUMENTID", "")).strip()[:-3].lower(), "rank": numeric(row, "RANK"),
                "product_name": row.get("PRODUCTNAME"), "product_sort": row.get("PRODUCTSORTNO"), "raw_row": row}
        for n in (1, 2, 3):
            for stem in ("PARTICIPANTID", "PARTICIPANTABBR"):
                key = f"{stem}{n}"
                item[key] = {"present": key in row, "raw": row.get(key), "type": type(row.get(key)).__name__ if key in row else "absent"}
        item["quantities"] = {k: numeric(row, k) for k in QUANTITIES}
        labels = {str(row.get(f"PARTICIPANTABBR{n}", "")).strip() for n in (1, 2, 3)}
        item["label_columns_disagree"] = len(labels) != 1
        categories.append(item)
    balances = []
    for product in sorted({r["product"] for r in categories}):
        group = [r for r in categories if r["product"] == product]
        keys = [(str(r["rank"]["raw"]), str(r["raw_row"].get("PARTICIPANTABBR1", "")).strip()) for r in group]
        item = {"date": rec["date"], "product": product, "category_row_count": len(group), "duplicate_category_keys": len(keys) - len(set(keys)),
                "labels": [str(r["raw_row"].get("PARTICIPANTABBR1", "")).strip() for r in group],
                "quantity_missing_or_invalid_count": sum(v["value"] is None for r in group for v in r["quantities"].values()),
                "negative_level_count": sum(r["quantities"][k]["value"] is not None and r["quantities"][k]["value"] < 0 for r in group for k in ("CJ1", "CJ2", "CJ3")),
                "label_columns_disagree_count": sum(r["label_columns_disagree"] for r in group)}
        for key in QUANTITIES:
            vals = [r["quantities"][key]["value"] for r in group]
            item[key + "_sum"] = sum(vals) if all(x is not None for x in vals) else None
        item["buy_sell_difference"] = item["CJ2_sum"] - item["CJ3_sum"] if item["CJ2_sum"] is not None and item["CJ3_sum"] is not None else None
        item["buy_sell_balanced"] = item["buy_sell_difference"] == 0 if item["buy_sell_difference"] is not None else None
        item["scope_qualified_all_listed_months"] = False
        balances.append(item)
    report_date = obj.get("report_date", obj.get("REPORT_DATE"))
    result.update(parse_status="json_cursor", top_level_keys=list(obj), row_fields=fields, row_count=len(rows), real_contract_count=len(contracts),
                  real_contract_products=products, category_row_count=len(categories), category_products=sorted({r["product"] for r in categories}),
                  category_absent_for_observed_contract_products=sorted(set(products) - {r["product"] for r in categories}),
                  category_labels=sorted({str(r["raw_row"].get("PARTICIPANTABBR1", "")).strip() for r in categories}),
                  category_id_field_presence={f"PARTICIPANTID{n}": sum(f"PARTICIPANTID{n}" in r["raw_row"] for r in categories) for n in (1, 2, 3)},
                  report_metadata={k: v for k, v in obj.items() if k != "o_cursor"}, report_date_matches_request=(str(report_date).replace("-", "") == rec["date"]) if report_date is not None else None,
                  earliest_publication_qualified=False, continuous_history_qualified=False)
    return result, categories, balances


def main():
    protocol_bytes = PROTOCOL.read_bytes()
    assert sha(protocol_bytes) == EXPECTED_PROTOCOL_SHA
    protocol = json.loads(protocol_bytes)
    assert len(protocol["new_dates"]) == 12 and len(set(protocol["new_dates"])) == 12
    assert protocol["new_get_max"] == 12 and protocol["concurrency_max"] == 2 and protocol["new_body_bytes_max"] == 16777216
    assert not protocol["automatic_retry"]
    for bound in protocol["bound_inputs"]:
        b = Path(bound["path"]).read_bytes()
        assert len(b) == bound["size"] and sha(b) == bound["sha256"]
    assert not (OUT / "execution_receipt.json").exists(), "actual execution is one-shot; do not rerun"
    (OUT / "raw").mkdir(exist_ok=True)
    (OUT / "requests").mkdir(exist_ok=True)
    for day in protocol["new_dates"]:
        assert not (OUT / "requests" / f"{day}.json").exists(), "prior attempt present; do not retry"
    dump(OUT / "started.json", {"protocol_sha256": EXPECTED_PROTOCOL_SHA, "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "new_dates": protocol["new_dates"]})
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(lambda day: fetch(day, protocol), protocol["new_dates"]))
    old = json.loads(Path(protocol["bound_inputs"][0]["path"]).read_text())
    reused = []
    for day in protocol["reuse_dates"]:
        q = next(q for q in old["probes"] if q["kind"] == "member" and q["exchange"] == "SHFE" and q["trade_date_requested"] == day)
        q = dict(q, date=day)
        path = Path(q["raw_path"])
        if not path.is_absolute():
            path = ROOT / path
        q["raw_path"] = str(path)
        data = path.read_bytes()
        assert len(data) == q["bytes"] and sha(data) == q["sha256"]
        reused.append(q)
    all_results, all_categories, all_balances = [], [], []
    for rec, reuse in [(r, False) for r in records] + [(r, True) for r in reused]:
        result, category, balance = audit(rec, reuse)
        all_results.append(result)
        all_categories.extend(category)
        all_balances.extend(balance)
    all_results.sort(key=lambda r: r["date"])
    dump(OUT / "per_date_audit.json", all_results)
    dump(OUT / "all_category_quantities.json", all_categories)
    dump(OUT / "all_product_balances.json", all_balances)
    receipt = {"finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "protocol_sha256": EXPECTED_PROTOCOL_SHA,
               "new_get_count": GET_COUNT, "new_body_bytes": BODY_BYTES, "concurrency_max": 2, "automatic_retry": False,
               "new_responses": records, "reused_stage104_dates": protocol["reuse_dates"],
               "fit": 0, "cash": 0, "sql": 0, "minute_download": 0, "continuous_history_qualified": False, "first_publication_qualified": False}
    assert GET_COUNT == 12 and BODY_BYTES == sum(r["bytes"] for r in records) <= protocol["new_body_bytes_max"]
    dump(OUT / "execution_receipt.json", receipt)
    summary = {"stage": 106, "new_get_count": GET_COUNT, "new_body_bytes": BODY_BYTES, "budget_bytes": 16777216,
               "http_200_dates": [r["date"] for r in records if r.get("http_status") == 200],
               "failed_or_non200_dates": [r["date"] for r in records if r.get("error") or r.get("http_status") != 200 or r.get("truncated")],
               "json_cursor_dates": sum(r["parse_status"] == "json_cursor" for r in all_results), "category_row_count": len(all_categories),
               "product_date_count": len(all_balances), "unbalanced_product_dates": sum(r["buy_sell_balanced"] is False for r in all_balances),
               "missing_balance_product_dates": sum(r["buy_sell_balanced"] is None for r in all_balances),
               "negative_level_count": sum(r["negative_level_count"] for r in all_balances),
               "missing_invalid_quantities": sum(r["quantity_missing_or_invalid_count"] for r in all_balances),
               "duplicate_category_keys": sum(r["duplicate_category_keys"] for r in all_balances),
               "category_support_by_date": {r["date"]: len(r.get("category_products", [])) for r in all_results},
               "fit": 0, "cash": 0, "sql": 0, "continuous_history_qualified": False, "first_publication_qualified": False}
    encoded = json.dumps(summary, ensure_ascii=False, indent=2).encode()
    assert len(encoded) < 2048
    (OUT / "summary.json").write_bytes(encoded)
    print(encoded.decode(), flush=True)


if __name__ == "__main__":
    main()
