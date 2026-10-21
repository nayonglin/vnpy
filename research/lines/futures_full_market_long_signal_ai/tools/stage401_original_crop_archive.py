"""Bounded one-logical-harvest original ESMIS reports, using observed forms/links."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import collections
import datetime as dt
import hashlib
import html.parser
import importlib.util
import json
from pathlib import Path
import shutil
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE / "outputs/stage401_original_crop_archive"
OUT = ROOT / "actual_run1"
DOMAIN = "https://esmis.nal.usda.gov"
PROGRESS = DOMAIN + "/publication/crop-progress"
ANNUAL = DOMAIN + "/publication/crop-production-annual-summary"
LOCK = threading.Lock()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def bind(path):
    body = path.read_bytes()
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Index(html.parser.HTMLParser):
    def __init__(self, url):
        super().__init__()
        self.url, self.options, self.rows, self.next_urls = url, [], [], []
        self.form_action = None
        self.select_date = False
        self.row = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form" and "views-exposed-form" in a.get("class", ""):
            self.form_action = urllib.parse.urljoin(self.url, a.get("action", ""))
        if tag == "select":
            self.select_date = a.get("name") == "date"
        if tag == "option" and self.select_date and a.get("value"):
            self.options.append(a["value"])
        if tag == "tr":
            self.row = {"datetimes": [], "txt_urls": [], "release_pages": []}
        if tag == "time" and self.row is not None and a.get("datetime"):
            self.row["datetimes"].append(a["datetime"])
        if tag == "a" and a.get("href"):
            url = urllib.parse.urljoin(self.url, a["href"])
            if a.get("aria-label") == "Next page":
                self.next_urls.append(url)
            if self.row is not None:
                path = urllib.parse.urlsplit(url).path
                if path.lower().endswith(".txt"):
                    self.row["txt_urls"].append(url)
                if path.startswith("/publication/") and path.count("/") >= 3:
                    self.row["release_pages"].append(url)

    def handle_endtag(self, tag):
        if tag == "select":
            self.select_date = False
        if tag == "tr" and self.row is not None:
            row, self.row = self.row, None
            times = sorted(set(row["datetimes"]))
            if times and row["release_pages"]:
                row["archive_datetime_labels"] = times
                row["release_date"] = times[0][:10] if len(times) == 1 else None
                row["txt_urls"] = sorted(set(row["txt_urls"]))
                row["release_pages"] = sorted(set(row["release_pages"]))
                self.rows.append(row)


def parsed_index(record):
    parser = Index(record["url"])
    parser.feed(Path(record["body"]["path"]).read_text(encoding="utf-8"))
    return parser


class Harvest:
    def __init__(self):
        self.records = [json.loads(path.read_text()) for path in sorted(OUT.glob("locator_*_root.response.json"))]
        if len(self.records) != 2:
            raise RuntimeError("exact two already-received root pages required")
        for record in self.records:
            if bind(Path(record["body"]["path"])) != record["body"]:
                raise RuntimeError("original root locator changed")
        self.by_url = {record["url"]: record for record in self.records}
        self.counts = collections.Counter({"locator": 2, "txt": 0})
        self.body_bytes = sum(record["body"]["bytes"] for record in self.records)
        self.reserved = 0
        (OUT / "requests").mkdir(exist_ok=False)
        (OUT / "raw_txt").mkdir(exist_ok=False)
        (OUT / "locators").mkdir(exist_ok=False)

    def get(self, url, role):
        with LOCK:
            if url in self.by_url:
                return self.by_url[url]
            if (self.counts[role] >= (80 if role == "locator" else 400) or
                    sum(self.counts.values()) >= 480):
                return {"url": url, "ok": False, "error": "unrequested: fixed GET budget exhausted", "role": role}
            if urllib.parse.urlsplit(url).hostname != "esmis.nal.usda.gov":
                return {"url": url, "ok": False, "error": "unrequested: link outside exact official host", "role": role}
            self.counts[role] += 1
            seq = sum(self.counts.values())
            record = {"sequence": seq, "url": url, "role": role, "started_at": now(), "retry": 0, "redirect": 0}
            self.by_url[url] = record
            self.records.append(record)
        response_path = OUT / "requests" / f"{seq:04d}.response.json"
        save(response_path, record)
        name = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])
        name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
        body_path = OUT / ("locators" if role == "locator" else "raw_txt") / f"{seq:04d}_{name or 'index'}"
        if role == "locator":
            body_path = body_path.with_suffix(".html")
        body, reserve = b"", 0
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "fian-bounded-USDA-research/401", "Accept-Encoding": "identity"})
            try:
                response = urllib.request.build_opener(NoRedirect()).open(request, timeout=30)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                record["status"] = response.code
                record["headers"] = dict(response.headers)
                declared = response.headers.get("Content-Length")
                reserve = min(int(declared), 2000000) if declared is not None else 2000000
                with LOCK:
                    if self.body_bytes + self.reserved + reserve > 200000000:
                        reserve = 0
                        raise RuntimeError("fixed200MB source body budget exhausted before reading")
                    self.reserved += reserve
                if declared is not None and int(declared) > 2000000:
                    raise RuntimeError("declared source body exceeds2MB; not consumed")
                body = response.read(reserve)
                if len(body) >= 2000000 or (declared is not None and len(body) != int(declared)):
                    raise RuntimeError("bounded original response length mismatch")
                record["ok"] = response.code == 200
                if not record["ok"]:
                    record["error"] = f"HTTP{response.code}; no retry"
        except BaseException as error:
            record["ok"] = False
            record["error"] = repr(error)
        finally:
            with LOCK:
                self.reserved -= reserve
                self.body_bytes += len(body)
            body_path.write_bytes(body)
            record["body"] = bind(body_path)
            record["ended_at"] = now()
            save(response_path, record)
        return record

    def batch(self, urls, role):
        urls = list(dict.fromkeys(urls))
        with ThreadPoolExecutor(max_workers=4) as pool:
            return list(pool.map(lambda url: self.get(url, role), urls))


def in_scope(row, publication):
    day = row.get("release_date")
    if not day or not re_date(day):
        return False
    year, month = int(day[:4]), int(day[5:7])
    if not 2017 <= year <= 2025:
        return False
    if publication == "crop-progress":
        return 4 <= month <= 11
    return month == 1 or (day == "2019-02-08" and any(url.endswith("/cropan19.txt") for url in row["txt_urls"]))


def re_date(day):
    try:
        return dt.date.fromisoformat(day).isoformat() == day
    except ValueError:
        return False


def main():
    terminal = OUT / "harvest_manifest.json"
    if terminal.exists():
        raise RuntimeError("one bounded harvest already invoked; no retry")
    scope = json.loads((ROOT / "scope.json").read_text())
    amendment = json.loads((ROOT / "annual_schedule_amendment.json").read_text())
    if bind(ROOT / "scope.json")["sha256"] != amendment["original_scope_sha256"]:
        raise RuntimeError("scope/amendment binding changed")
    state = {"schema": "stage401_original_crop_archive_harvest_v1", "started_at": now(), "status": "started",
             "scope": bind(ROOT / "scope.json"), "annual_schedule_amendment": bind(ROOT / "annual_schedule_amendment.json"),
             "script_at_start": bind(Path(__file__).resolve()), "fit": 0, "cash": 0, "market_API": 0, "SQL": 0}
    save(terminal, state)
    harvest = Harvest()
    inventory, coverage = [], []
    try:
        progress_root = harvest.by_url[PROGRESS]
        annual_root = harvest.by_url[ANNUAL]
        progress = parsed_index(progress_root)
        annual = parsed_index(annual_root)
        if progress.form_action != PROGRESS:
            raise RuntimeError("observed CropProgress date form action mismatch")
        target_months = [f"{year}-{month:02d}" for year in range(2017, 2026) for month in range(4, 12)]
        month_urls = {}
        for month in target_months:
            if month in progress.options:
                month_urls[month] = PROGRESS + "?" + urllib.parse.urlencode({"date": month})
            else:
                coverage.append({"publication": "crop-progress", "month": month,
                                 "status": "unknown:no_native_date_option", "not_zero_or_imputed": True})
        locator_urls = list(month_urls.values())
        if min(int(row["release_date"][:4]) for row in annual.rows if row["release_date"]) > 2017:
            locator_urls.extend(annual.next_urls[:1])
        locator_records = harvest.batch(locator_urls, "locator")
        pages = [(annual_root, "crop-production-annual-summary")]
        for record in locator_records:
            publication = "crop-progress" if urllib.parse.urlsplit(record["url"]).path == "/publication/crop-progress" else "crop-production-annual-summary"
            pages.append((record, publication))
            if not record.get("ok"):
                coverage.append({"publication": publication, "locator_url": record["url"], "status": "unknown:locator_failed", "error": record.get("error")})
        # Follow only actually observed next links, and only the same native date filter.
        seen_pages = set()
        while pages:
            record, publication = pages.pop(0)
            if record["url"] in seen_pages or not record.get("ok"):
                continue
            seen_pages.add(record["url"])
            index = parsed_index(record)
            eligible = [row for row in index.rows if in_scope(row, publication)]
            for row in eligible:
                inventory.append({**row, "publication": publication,
                                  "locator_url": record["url"], "locator_body": record["body"],
                                  "archive_clock_is_metadata_not_firstseen": True})
            query_month = urllib.parse.parse_qs(urllib.parse.urlsplit(record["url"]).query).get("date", [None])[0]
            if publication == "crop-progress":
                coverage.append({"publication": publication, "month": query_month, "status": "native_locator_received",
                                 "locator_url": record["url"], "release_rows": len(eligible)})
            for next_url in index.next_urls[:1]:
                if publication == "crop-progress":
                    next_month = urllib.parse.parse_qs(urllib.parse.urlsplit(next_url).query).get("date", [None])[0]
                    allowed = query_month is not None and next_month == query_month
                else:
                    allowed = bool(index.rows) and min(int(row["release_date"][:4]) for row in index.rows if row["release_date"]) > 2017
                if allowed and next_url not in seen_pages:
                    pages.append((harvest.get(next_url, "locator"), publication))
        save(OUT / "metadata_inventory.json", {"reports": inventory, "coverage": coverage,
                                               "selection": "complete frozen year/month source population, no temperature/price/PnL consulted"})
        cached_391 = {}
        old_receipt = LINE / "outputs/stage391_original_soy_exposure_sample/actual_run1/acquisition_receipt.json"
        old = json.loads(old_receipt.read_text())
        for entry in old["requests"]:
            if entry["role"].startswith("original_") and entry.get("ok"):
                if bind(Path(entry["body_binding"]["path"])) != entry["body_binding"]:
                    raise RuntimeError("original391 cache identity changed")
                cached_391[entry["url"]] = entry
        all_urls = sorted({url for row in inventory for url in row["txt_urls"]})
        sources = {}
        for url in all_urls:
            if url in cached_391:
                original = cached_391[url]
                name = "reused391_" + Path(urllib.parse.urlsplit(url).path).name
                path = OUT / "raw_txt" / name
                shutil.copyfile(original["body_binding"]["path"], path)
                sources[url] = {"url": url, "role": "txt", "ok": True, "mode": "reused_exact391_original_no_GET",
                                "body": bind(path), "original391_body": original["body_binding"],
                                "original391_headers": original["headers_binding"], "original391_receipt": bind(old_receipt)}
        for record in harvest.batch([url for url in all_urls if url not in sources], "txt"):
            sources[record["url"]] = record
        for row in inventory:
            row["original_sources"] = [sources[url] for url in row["txt_urls"]]
            row["raw_status"] = "unknown:no_original_TXT_link" if not row["txt_urls"] else "received" if all(sources[url].get("ok") for url in row["txt_urls"]) else "unknown:one_or_more_TXT_failed"
        save(OUT / "reports_index.json", {"reports": inventory, "coverage": coverage})
        parser_path = Path(__file__).with_name("stage401_parse_original_crop_reports.py")
        parsed = []
        if parser_path.exists():
            spec = importlib.util.spec_from_file_location("stage401_parser", parser_path)
            parser = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(parser)
            for row in inventory:
                for source in row["original_sources"]:
                    if source.get("ok"):
                        try:
                            value = parser.parse_report(Path(source["body"]["path"]).read_bytes(),
                                                        {"publication": row["publication"], "release_date": row["release_date"], "url": source["url"]})
                            value["source_body_binding"] = source["body"]
                            value["locator_binding"] = row["locator_body"]
                            parsed.append(value)
                        except Exception as error:
                            parsed.append({"source": source["url"], "status": "unknown:offline_parser_error", "error": repr(error)})
            save(OUT / "parsed_original_tables.json", {"reports": parsed, "parser": bind(parser_path), "network_during_parse": 0})
            state["parser"] = bind(parser_path)
            state["parsed_reports"] = len(parsed)
        else:
            state["parse_status"] = "pending_offline_parser_file_not_yet_ready"
        state["status"] = "bounded_harvest_complete_with_explicit_unknowns"
    except BaseException as error:
        state["status"] = "harvest_terminal_preserving_received_sources"
        state["error"] = repr(error)
        state["traceback"] = traceback.format_exc()
        raise
    finally:
        state["ended_at"] = now()
        state["request_counts"] = dict(harvest.counts)
        state["GET_total"] = sum(harvest.counts.values())
        state["source_body_bytes"] = harvest.body_bytes
        state["unique_requested_URLs"] = len(harvest.by_url)
        state["request_failures"] = [record for record in harvest.records if not record.get("ok")]
        state["all_request_records"] = harvest.records
        state["automatic_retries"] = state["duplicate_URL_GET"] = 0
        state["report_rows"] = len(inventory)
        state["coverage"] = coverage
        state["script_at_terminal"] = bind(Path(__file__).resolve())
        save(terminal, state)
        print(json.dumps({key: state.get(key) for key in ("status", "GET_total", "request_counts", "source_body_bytes", "report_rows", "parsed_reports", "error")}), flush=True)


if __name__ == "__main__":
    main()
