"""Stage407 one bounded source worker, reusing its one received official index."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html.parser
import importlib.util
import io
import json
from pathlib import Path
import re
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE / "outputs/stage407_cot_source_years"
OUT = ROOT / "actual_run1"
PROTOCOL_SHA = "da7b46f3956ba6e571ae281f51bcd08cdf8406aa89ada83694fbba82c3e781bd"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def bind(path):
    body = path.read_bytes()
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True, allow_nan=False) + "\n")


class Index(html.parser.HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base, self.table, self.active, self.links = base, None, None, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.table = attrs.get("summary")
        if tag == "a" and self.table == "Disaggregated Futures Only Reports":
            self.active = {"url": urllib.parse.urljoin(self.base, attrs.get("href", "")),
                           "table_summary": self.table, "label": ""}

    def handle_data(self, data):
        if self.active is not None:
            self.active["label"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.active is not None:
            self.active["label"] = self.active["label"].strip()
            self.links.append(self.active)
            self.active = None
        if tag == "table":
            self.table = None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    protocol_path = ROOT / "protocol.json"
    if bind(protocol_path)["sha256"] != PROTOCOL_SHA:
        raise RuntimeError("root-frozen407 protocol changed")
    protocol = json.loads(protocol_path.read_text())
    final_path = OUT / "source_manifest.json"
    if final_path.exists():
        raise RuntimeError("one worker invocation only; no retry/redownload")
    index = json.loads((OUT / "index.response.json").read_text())
    if bind(Path(index["body"]["path"])) != index["body"]:
        raise RuntimeError("received official index changed")
    (OUT / "raw_years").mkdir(exist_ok=False)
    state = {"schema": "stage407_original_cot_year_source_manifest_v1", "started_at": now(), "status": "running",
             "protocol": bind(protocol_path), "official_index": index, "source_at_start": bind(Path(__file__).resolve()),
             "year_requests": [], "Y_reads": 0, "fit": 0, "cash": 0, "market_API": 0, "SQL": 0,
             "worker_parallel": 1, "all98products95families_retained": True,
             "mapped_channels": protocol["mapping"], "other90products_unmapped_not_zero": True,
             "historical_firstseen_verified": False, "whole_goal_achieved": False}
    save(final_path, state)
    source_bytes = index["body"]["bytes"]
    try:
        if index.get("status") in (403, 429):
            state["status"] = "stopped_after_index403or429_no_alternate_source"
            return
        if not index.get("ok"):
            state["status"] = "official_index_unavailable_no_guessed_year_paths"
            return
        parser = Index(index["url"])
        parser.feed(Path(index["body"]["path"]).read_text(encoding="utf-8"))
        anchors = {}
        for link in parser.links:
            filename = Path(urllib.parse.urlsplit(link["url"]).path).name
            match = re.fullmatch(r"fut_disagg_txt_(20\d{2})\.zip", filename)
            if match and link["label"] == "Text" and urllib.parse.urlsplit(link["url"]).hostname == "www.cftc.gov":
                anchors.setdefault(int(match.group(1)), []).append(link)
        selected = {str(year): anchors.get(year, []) for year in protocol["data"]["year_order"]}
        save(OUT / "observed_year_anchors.json", {"official_index": index["body"], "anchors": selected,
                                                   "selection": "actual FuturesOnly table Text anchors only; no guessed URL"})
        for year in protocol["data"]["year_order"]:
            links = anchors.get(year, [])
            if len(links) != 1:
                state.setdefault("unrequested_years", []).append({"year": year, "reason": "missing_or_ambiguous_actual_Text_anchor", "links": links})
                continue
            if len(state["year_requests"]) >= 16:
                state["status"] = "stopped_fixed16ZIP_budget"
                break
            url = links[0]["url"]
            if any(row["url"] == url for row in state["year_requests"]):
                raise RuntimeError("duplicate observed year URL: refuse repeated GET")
            record = {"year": year, "url": url, "anchor": links[0], "started_at": now(), "retry": 0,
                      "redirect": 0, "role": "original_disaggregated_futuresonly_textZIP"}
            state["year_requests"].append(record)
            save(final_path, state)
            body = b""
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "fian-bounded-CFTC-research/407", "Accept-Encoding": "identity"})
                try:
                    response = urllib.request.build_opener(NoRedirect()).open(request, timeout=30)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    record["status"] = response.code
                    record["headers"] = dict(response.headers)
                    declared = response.headers.get("Content-Length")
                    cap = min(8388608, 125829120 - source_bytes)
                    if cap <= 0 or (declared is not None and int(declared) > cap):
                        raise RuntimeError("fixed source/ZIP byte budget prevents body read")
                    body = response.read(cap)
                    if len(body) >= cap or (declared is not None and len(body) != int(declared)):
                        raise RuntimeError("bounded year response length mismatch")
                    record["ok"] = response.code == 200
                    if not record["ok"]:
                        record["error"] = f"HTTP{response.code}"
            except Exception as error:
                record["ok"] = False
                record["error"] = repr(error)
            finally:
                path = OUT / "raw_years" / f"fut_disagg_txt_{year}.zip"
                path.write_bytes(body)
                source_bytes += len(body)
                record["body"] = bind(path)
                record["ended_at"] = now()
                save(OUT / "raw_years" / f"fut_disagg_txt_{year}.response.json", record)
                save(final_path, state)
                print(json.dumps({"year": year, "status": record.get("status"), "ok": record.get("ok"),
                                  "bytes": len(body), "requests_with_index": 1 + len(state["year_requests"])}), flush=True)
            if record.get("status") in (403, 429):
                state["status"] = "stopped_after_year403or429_no_alternate_source"
                break
            if record.get("ok") and year == 2010:
                try:
                    with zipfile.ZipFile(io.BytesIO(body)) as archive:
                        entries = archive.infolist()
                        if sum(entry.file_size for entry in entries) > 134217728:
                            raise RuntimeError("2010 archive exceeds per-year128MiB uncompressed cap")
                        text_members = [entry for entry in entries if not entry.is_dir() and entry.filename.lower().endswith((".txt", ".csv"))]
                        if not text_members:
                            raise RuntimeError("2010 has no original text member")
                        with archive.open(text_members[0]) as raw:
                            encoding = "utf-8-sig" if raw.peek(3).startswith(b"\xef\xbb\xbf") else "cp1252"
                            reader = csv.reader(io.TextIOWrapper(raw, encoding=encoding, errors="surrogateescape", newline=""))
                            header = next(reader)
                            first = next(reader)
                    observed = {"year": 2010, "member": text_members[0].filename, "encoding": encoding,
                                "header": header, "first_identity_and_field_tokens": dict(zip(header, first)),
                                "note": "header discovery only; full stream CRC and all identity extraction follows once, no extra GET"}
                    save(OUT / "first2010_observed_schema.json", observed)
                    print(json.dumps({"first2010_header_received": True, "columns": len(header),
                                      "first2010_schema": str(OUT / "first2010_observed_schema.json")}), flush=True)
                except Exception as error:
                    record["header_discovery_error"] = repr(error)
        parse_path = Path(__file__).with_name("stage407_cot_parse_year.py")
        if parse_path.exists():
            spec = importlib.util.spec_from_file_location("stage407_parser", parse_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            parsed = []
            for record in state["year_requests"]:
                if record.get("ok"):
                    try:
                        output = OUT / "parsed_years" / str(record["year"])
                        output.mkdir(parents=True, exist_ok=False)
                        result = module.parse_year(Path(record["body"]["path"]), record["year"], protocol["mapping"], output)
                        parsed.append(result)
                        print(json.dumps({"parsed_year": record["year"], "status": result.get("status")}), flush=True)
                    except Exception as error:
                        parsed.append({"year": record["year"], "status": "unknown_parse_failure", "error": repr(error), "traceback": traceback.format_exc()})
            save(OUT / "parsed_years_manifest.json", {"parser": bind(parse_path), "years": parsed, "network_during_parse": 0})
            state["parser"] = bind(parse_path)
            state["parsed_years"] = len(parsed)
        else:
            state["parse_status"] = "pending_offline_parser_not_yet_ready"
        if state["status"] == "running":
            state["status"] = "source_year_batch_terminal_not_availability_or_alpha_qualified"
    except BaseException as error:
        state["status"] = "source_worker_terminal_preserving_received_packages"
        state["error"] = repr(error)
        state["traceback"] = traceback.format_exc()
        raise
    finally:
        state["ended_at"] = now()
        state["GET_total"] = 1 + len(state["year_requests"])
        state["source_body_bytes"] = source_bytes
        state["automatic_retries"] = state["duplicate_URL_GET"] = 0
        state["source_at_terminal"] = bind(Path(__file__).resolve())
        save(final_path, state)
        print(json.dumps({key: state.get(key) for key in ("status", "GET_total", "source_body_bytes", "parsed_years", "parse_status", "error")}), flush=True)


if __name__ == "__main__":
    main()
