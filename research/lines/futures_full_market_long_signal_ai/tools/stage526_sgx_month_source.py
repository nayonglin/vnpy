"""Frozen January-2019 SGX monthly source acquisition; no financial calculations."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import date, datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import time
import urllib.error
import urllib.request


PROTOCOL_SHA = "b40e8447b3c63f35915b2061df320cfbd9004bfe66146208703cb6b4140e8d9c"
SECTION = "SGX TSI IRON ORE 62% DERIVATIVES"
MONTHS = {name: index for index, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
FIELDS = ["source_requested_date", "source_header_date", "source_as_at_literal",
          "source_as_at_time_reconstructed_if_explicit", "raw_sha256", "source_section_literal",
          "contract_month_literal", "contract_yyyy_mm", "dsp_raw", "prev_dsp_raw",
          "dsp_numeric_if_finite", "prev_dsp_numeric_if_finite", "value_status",
          "http_last_modified_metadata_not_first_publish"]


def compact(value):
    return re.sub(r"\s+", " ", value).strip()


class TargetTables(HTMLParser):
    """Keep only target table's first three cells; never materialize quantity fields."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.header_parts = []
        self.seen_table = False
        self.depth = 0
        self.current = None
        self.tables = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.seen_table = True
            self.depth += 1
            if self.depth == 1:
                self.current = {"target": None, "rows": [], "row": [], "column": 0,
                                "cell": None, "first_cell_seen": False}
        elif self.depth == 1 and tag == "tr":
            self.current["row"] = []
            self.current["column"] = 0
        elif self.depth == 1 and tag in ("td", "th"):
            cur = self.current
            capture = not cur["first_cell_seen"] or (cur["target"] and cur["column"] < 3)
            cur["cell"] = [] if capture else None

    def handle_data(self, value):
        if not self.seen_table:
            self.header_parts.append(value)
        if self.depth == 1 and self.current["cell"] is not None:
            self.current["cell"].append(value)

    def handle_endtag(self, tag):
        if not self.depth:
            return
        cur = self.current
        if self.depth == 1 and tag in ("td", "th"):
            raw = "".join(cur["cell"]).strip() if cur["cell"] is not None else None
            if not cur["first_cell_seen"]:
                cur["target"] = compact(raw or "") == SECTION
                cur["first_cell_seen"] = True
            if cur["target"] and cur["column"] < 3:
                cur["row"].append(raw or "")
            cur["column"] += 1
            cur["cell"] = None
        elif self.depth == 1 and tag == "tr":
            if cur["target"]:
                cur["rows"].append(cur["row"])
        elif tag == "table":
            if self.depth == 1 and cur["target"]:
                self.tables.append(cur["rows"])
            self.depth -= 1


def finite_value(raw):
    text = raw.strip()
    if text in ("", "-", "—", "–"):
        return None, "missing"
    number = r"[+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
    if re.fullmatch(number, text):
        value = float(text.replace(",", ""))
        return (value, "finite") if math.isfinite(value) else (None, "nonfinite")
    try:
        value = float(text)
        if not math.isfinite(value):
            return None, "nonfinite"
    except ValueError:
        pass
    return None, "invalid"


def normalize_report(body, requested_date, raw_sha256, last_modified):
    parser = TargetTables()
    parser.feed(body.decode("utf-8", errors="replace"))
    header = compact(" ".join(parser.header_parts))
    matches = list(re.finditer(r"\(\s*(?:DSPs\s+)?as\s+at\s+(.+?)SG\s+Time\s*\)", header, re.I))
    literal = matches[0].group(0) if len(matches) == 1 else None
    source_date = None
    source_time = None
    flags = []
    if len(matches) != 1:
        flags.append("source_header_missing" if not matches else "source_header_ambiguous")
    else:
        m = re.search(r"[A-Za-z]+,\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4}),\s*(.*)", matches[0].group(1))
        if m:
            try:
                source_date = datetime.strptime(" ".join(m.group(i) for i in (1, 2, 3)), "%B %d %Y").date().isoformat()
                clocks = list(re.finditer(r"\b(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)\b", m.group(4), re.I))
                if len(clocks) == 1:
                    hour = int(clocks[0].group(1))
                    minute = int(clocks[0].group(2) or 0)
                    if 1 <= hour <= 12 and 0 <= minute <= 59:
                        hour = hour % 12 + (12 if clocks[0].group(3).lower() == "pm" else 0)
                        source_time = f"{source_date}T{hour:02d}:{minute:02d}:00+08:00"
            except ValueError:
                pass
        if source_date is None:
            flags.append("source_header_unparsed")
        elif source_date != requested_date:
            flags.append("source_date_mismatch")
    rows = []
    duplicate_months = []
    if not parser.tables:
        flags.append("target_section_missing")
    elif len(parser.tables) != 1:
        flags.append("target_section_ambiguous")
    else:
        table = parser.tables[0]
        schema_rows = [i for i, row in enumerate(table)
                       if [compact(x) for x in row[:3]] == ["Contract Month", "DSP (US$)", "Prev DSP (US$)"]]
        if len(schema_rows) != 1:
            flags.append("target_schema_invalid")
        else:
            for source_row in table[schema_rows[0] + 1:]:
                if not source_row:
                    continue
                label = source_row[0]
                month = re.fullmatch(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(\d{2})", label)
                if not month:
                    continue
                if len(source_row) != 3:
                    flags.append("monthly_row_schema_invalid")
                    continue
                dsp, prev = source_row[1:3]
                numeric, state = finite_value(dsp)
                prev_numeric, prev_state = finite_value(prev)
                rows.append(dict(zip(FIELDS, [requested_date, source_date, literal, source_time,
                    raw_sha256, SECTION, label,
                    f"{2000 + int(month.group(2)):04d}-{MONTHS[month.group(1)]:02d}",
                    dsp, prev, numeric, prev_numeric, f"dsp={state};prev={prev_state}", last_modified])))
            duplicate_months = sorted(key for key, count in Counter(r["contract_month_literal"] for r in rows).items() if count > 1)
            if duplicate_months:
                flags.append("duplicate_month_rows")
            if not rows:
                flags.append("target_month_rows_missing")
    return {"date_status": flags[0] if flags else "ok", "quality_flags": list(dict.fromkeys(flags)),
            "source_header_date": source_date, "source_as_at_literal": literal,
            "source_as_at_time_reconstructed_if_explicit": source_time,
            "target_table_count": len(parser.tables), "duplicate_months": duplicate_months, "rows": rows}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, obj):
    with path.open("x") as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def acquire_one(day, url, out, network):
    begin = time.monotonic()
    meta = {"source_requested_date": day, "url": url, "source_mode": "new_get",
            "method": "GET", "request_attempt": 1, "started_at_utc": utc_now(),
            "redirects_allowed": False, "retries": 0, "timeout_seconds": 15,
            "body_limit_bytes": network["body_limit_bytes"], "status_code": None,
            "response_headers": {}, "exception": None, "body_complete": False,
            "raw_path": None, "raw_bytes": 0, "raw_sha256": None}
    write_json(out / "requests" / f"{day}.started.json", meta)
    response = None
    body = None
    try:
        opener = urllib.request.build_opener(NoRedirect)
        request = urllib.request.Request(url, method="GET", headers={"User-Agent": "Stage526 fixed January-2019 public source audit"})
        try:
            response = opener.open(request, timeout=network["timeout_seconds"])
        except urllib.error.HTTPError as error:
            response = error  # Retain HTTP error bodies as raw evidence too.
        meta["status_code"] = response.code
        meta["response_url"] = response.geturl()
        meta["response_headers"] = dict(response.headers.items())
        body = response.read(network["body_limit_bytes"])
        meta["body_complete"] = len(body) < network["body_limit_bytes"]
        if not meta["body_complete"]:
            meta["exception"] = "body_limit_reached_completeness_unknown"
    except Exception as error:
        meta["exception"] = f"{type(error).__name__}: {error}"
        partial = getattr(error, "partial", None)
        if isinstance(partial, bytes):
            body = partial[:network["body_limit_bytes"]]
    finally:
        if response is not None:
            response.close()
    if body is not None:
        raw_path = out / "raw" / f"{day}.raw.bin"
        with raw_path.open("xb") as stream:
            stream.write(body)
        meta.update(raw_path=str(raw_path.resolve()), raw_bytes=len(body), raw_sha256=hashlib.sha256(body).hexdigest())
    meta["finished_at_utc"] = utc_now()
    meta["elapsed_seconds"] = time.monotonic() - begin
    if meta["exception"] is not None:
        status = {"date_status": "body_limit_or_incomplete" if response is not None else "network_error", "rows": []}
    elif meta["status_code"] != 200:
        status = {"date_status": "http_error", "rows": []}
    else:
        try:
            status = normalize_report(body, day, meta["raw_sha256"], meta["response_headers"].get("Last-Modified"))
        except Exception as error:
            status = {"date_status": "normalization_exception", "rows": [], "normalization_exception": f"{type(error).__name__}: {error}"}
    meta["normalization_date_status"] = status["date_status"]
    write_json(out / "requests" / f"{day}.http.json", meta)
    return meta, status


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--protocol", required=True)
    args = ap.parse_args()
    protocol_path = Path(args.protocol).resolve()
    protocol_bytes = protocol_path.read_bytes()
    assert hashlib.sha256(protocol_bytes).hexdigest() == PROTOCOL_SHA, "Frozen protocol changed"
    protocol = json.loads(protocol_bytes)
    out = protocol_path.parent
    days = protocol["requested_weekdays"]
    network = protocol["network"]
    expected = [date(2019, 1, n).isoformat() for n in range(1, 32) if date(2019, 1, n).weekday() < 5]
    assert days == expected and len(days) == 23
    assert network["max_new_GET"] == 22 and network["max_parallel"] == 2
    assert network["retry"] == 0 and network["redirects"] is False
    assert network["timeout_seconds"] == 15 and network["body_limit_bytes"] == 2097152
    assert protocol["normalized_fields"] == FIELDS and protocol["section_allowlist"] == [SECTION]
    assert protocol["cache"]["date"] == "2019-01-09"
    started = utc_now()
    started_receipt = {"schema": "stage526_actual_started_v1", "started_at_utc": started,
                       "protocol_sha256": PROTOCOL_SHA, "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       "max_new_get": 22, "new_fit": 0, "new_cash": 0, "new_SQL": 0,
                       "note": "Exclusive-create prevents automatic reruns; source failures remain unknown."}
    write_json(out / "actual_started.json", started_receipt)
    (out / "requests").mkdir()
    (out / "raw").mkdir()
    metadata = []
    normalized = {}
    fatal = None
    try:
        cache = protocol["cache"]
        cache_body = Path(cache["raw_path"]).read_bytes()
        assert hashlib.sha256(cache_body).hexdigest() == cache["raw_sha256"]
        assert len(cache_body) == cache["raw_bytes"]
        cached_meta = {"source_requested_date": cache["date"], "url": cache["url"],
                       "source_mode": "reused_stage525_cache_no_GET", "request_attempt": 0,
                       "status_code": cache["status_code"], "response_headers": cache["response_headers"],
                       "raw_path": cache["raw_path"], "raw_bytes": len(cache_body),
                       "raw_sha256": cache["raw_sha256"], "body_complete": True,
                       "parent_request_started_at_utc": cache["started_at_utc"],
                       "parent_request_finished_at_utc": cache["finished_at_utc"],
                       "cache_read_at_utc": utc_now()}
        normalized[cache["date"]] = normalize_report(cache_body, cache["date"], cache["raw_sha256"], cache["response_headers"].get("Last-Modified"))
        cached_meta["normalization_date_status"] = normalized[cache["date"]]["date_status"]
        metadata.append(cached_meta)
        write_json(out / "requests" / f"{cache['date']}.cache_reference.json", cached_meta)
        tasks = []
        for day in days:
            if day == cache["date"]:
                continue
            d = date.fromisoformat(day)
            month_name = tuple(MONTHS)[d.month - 1]
            url = network["fixed_url_template"].format(yyyy=f"{d.year:04d}", mm=f"{d.month:02d}", dd=f"{d.day:02d}", Mon=month_name)
            tasks.append((day, url))
        assert len(tasks) == 22
        print(json.dumps({"event": "started", **started_receipt}, ensure_ascii=False), flush=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(acquire_one, day, url, out, network) for day, url in tasks]
            with (out / "progress.jsonl").open("x") as progress:
                for index, future in enumerate(as_completed(futures), 1):
                    meta, status = future.result()
                    metadata.append(meta)
                    normalized[meta["source_requested_date"]] = status
                    event = {"event": "request_completed", "completed_at_utc": utc_now(), "new_get_completed": index,
                             "source_requested_date": meta["source_requested_date"], "status_code": meta["status_code"],
                             "date_status": status["date_status"], "raw_bytes": meta["raw_bytes"]}
                    progress.write(json.dumps(event, ensure_ascii=False) + "\n")
                    progress.flush()
                    print(json.dumps(event, ensure_ascii=False), flush=True)
    except BaseException as error:
        fatal = f"{type(error).__name__}: {error}"
    metadata.sort(key=lambda x: x["source_requested_date"])
    rows = [row for day in days for row in normalized.get(day, {}).get("rows", [])]
    with (out / "normalized_monthly.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    statuses = []
    by_date = {x["source_requested_date"]: x for x in metadata}
    for day in days:
        meta = by_date.get(day, {})
        status = normalized.get(day, {"date_status": "not_completed_unknown", "rows": []})
        statuses.append({"source_requested_date": day, "source_mode": meta.get("source_mode"),
                         "status_code": meta.get("status_code"), "raw_path": meta.get("raw_path"),
                         "raw_sha256": meta.get("raw_sha256"), "raw_bytes": meta.get("raw_bytes"),
                         **{k: v for k, v in status.items() if k != "rows"}, "monthly_row_count": len(status["rows"])})
    write_json(out / "date_statuses.json", {"weekday_not_exchange_calendar": True, "dates": statuses})
    manifest = {**started_receipt, "schema": "stage526_single_month_source_manifest_v1",
                "finished_at_utc": utc_now(), "process_status": "completed" if fatal is None else "failed",
                "fatal_exception": fatal, "new_get_attempted": sum(m["request_attempt"] for m in metadata),
                "new_get_budget": 22, "cache_reuse_count": sum(m["request_attempt"] == 0 for m in metadata),
                "retry_count": 0, "redirects_followed": 0, "requested_weekday_count": 23,
                "http_counts_including_cache": dict(Counter(str(m["status_code"]) for m in metadata)),
                "date_status_counts": dict(Counter(s["date_status"] for s in statuses)),
                "monthly_rows": len(rows), "value_status_counts": dict(Counter(r["value_status"] for r in rows)),
                "normalized_fields": FIELDS, "normalized_csv_path": str((out / "normalized_monthly.csv").resolve()),
                "date_statuses_path": str((out / "date_statuses.json").resolve()), "requests": metadata,
                "publication_time_certified": False, "independent_review": "pending",
                "limitations": ["23 weekdays are not an SGX trading calendar", "2019 page-wide 8pm is not per-product 17:30",
                                "Last-Modified is metadata, not first-publication timestamp", "PrevDSP never overwrites archived prior DSP",
                                "Finite normalized prices are not independently price-verified or executable fills"]}
    write_json(out / "manifest.json", manifest)
    terminal = {"event": "finished", "process_status": manifest["process_status"], "finished_at_utc": manifest["finished_at_utc"],
                "new_get_attempted": manifest["new_get_attempted"], "cache_reuse_count": manifest["cache_reuse_count"],
                "date_status_counts": manifest["date_status_counts"], "monthly_rows": len(rows), "fatal_exception": fatal}
    write_json(out / "actual_finished.json", terminal)
    print(json.dumps(terminal, ensure_ascii=False), flush=True)
    if fatal is not None:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
