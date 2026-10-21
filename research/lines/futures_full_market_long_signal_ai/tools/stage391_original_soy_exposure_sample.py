"""One frozen 2020 USDA exposure sample; acquisition and offline parsing only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html.parser
import json
import re
from decimal import Decimal, localcontext
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/stage391_original_soy_exposure_sample/actual_run1"
MAX_BYTES = 1024 * 1024
ANNUAL_PAGE = "https://esmis.nal.usda.gov/publication/crop-production-annual-summary/2020-01-10"
PROGRESS_PAGE = "https://esmis.nal.usda.gov/publication/crop-progress/2020-08-31"
PROGRESS_PDF = "https://www.nass.usda.gov/Publications/Todays_Reports/reports/prog3620.pdf"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bind(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_json(name: str, value: dict) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.items.extend(v for k, v in attrs if k == "href")


def locate_txt(body: bytes, page_url: str, basename: str) -> str:
    parser = Links()
    parser.feed(body.decode("utf-8"))
    found = sorted({urllib.parse.urljoin(page_url, x) for x in parser.items
                    if urllib.parse.urlsplit(x).path.rsplit("/", 1)[-1] == basename})
    if len(found) != 1:
        raise ValueError(f"Expected one original {basename} anchor, got {len(found)}")
    url = found[0]
    if urllib.parse.urlsplit(url).hostname != "esmis.nal.usda.gov":
        raise ValueError("Unexpected non-ESMIS exact body link")
    return url


def acquire(finish_unattempted_progress: bool = False) -> None:
    if OUT.exists() and not finish_unattempted_progress:
        raise FileExistsError("Fresh fixed output required; acquisition may not resume or retry")
    if not finish_unattempted_progress:
        OUT.mkdir(parents=True)
    receipt = {
        "schema": "stage391_original_soy_exposure_acquisition_v1",
        "started_at": now(),
        "status": "running",
        "scope": {"http_max": 4, "locator_pages_max": 2, "original_bodies_max": 2,
                  "per_object_max_bytes": MAX_BYTES, "automatic_retries": 0,
                  "redirects": 0, "financial_runs": 0, "market_api_calls": 0,
                  "fixed_annual_release": "2020-01-10", "fixed_progress_release": "2020-08-31",
                  "decision_asof": "2020-09-01T21:00:00+08:00",
                  "fallback": "Only same original prog3620.pdf already read in386 if progress locator fails; authorized by root before acquisition"},
        "web_discovery_notes": ["Annual original ESMIS release page read via web cache; CropProgress exact original page web-cache unavailable; neither proves actual HTTP state"],
        "requests": [],
    }
    if finish_unattempted_progress:
        receipt = json.loads((OUT / "acquisition_receipt.json").read_text())
        if not (receipt["status"] == "stopped_no_retry" and len(receipt["requests"]) == 3
                and [x["role"] for x in receipt["requests"]] == ["locator", "locator", "original_annual_body"]
                and all(x.get("status") == 200 and x.get("ok") for x in receipt["requests"])):
            raise ValueError("Only the never-attempted fourth original may be completed")
        for entry in receipt["requests"]:
            if bind(Path(entry["body_binding"]["path"])) != entry["body_binding"]:
                raise ValueError("Original acquisition body changed")
        initial_path = OUT / "acquisition_initial_terminal.json"
        if initial_path.exists():
            raise FileExistsError("Manual fourth-request completion may run only once")
        initial_path.write_bytes((OUT / "acquisition_receipt.json").read_bytes())
        receipt["initial_terminal_binding"] = bind(initial_path)
        receipt["manual_completion_reason"] = "Initial local title guard rejected line-wrapped Crop Production; no original source retry. Complete only already-planned never-attempted progress body."
        receipt["manual_completion_started_at"] = now()
        receipt["status"] = "running_last_unattempted_original"
    write_json("acquisition_receipt.json", receipt)
    opener = urllib.request.build_opener(NoRedirect)

    def get(url: str, name: str, role: str) -> bytes | None:
        if len(receipt["requests"]) >= 4:
            raise RuntimeError("Fixed four-request budget exhausted")
        if urllib.parse.urlsplit(url).hostname not in {"esmis.nal.usda.gov", "www.nass.usda.gov"}:
            raise ValueError("Host outside fixed official allowlist")
        entry = {"attempt": len(receipt["requests"]) + 1, "url": url, "role": role,
                 "started_at": now(), "method": "GET", "retries": 0}
        receipt["requests"].append(entry)
        write_json("acquisition_receipt.json", receipt)
        request = urllib.request.Request(url, headers={"User-Agent": "fian-bounded-USDA-research/391", "Accept-Encoding": "identity"})
        try:
            try:
                response = opener.open(request, timeout=40)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                entry["status"] = response.code
                entry["response_url"] = response.geturl()
                headers = list(response.headers.items())
                header_path = OUT / f"{name}.headers.json"
                header_path.write_text(json.dumps(headers, ensure_ascii=False, indent=2) + "\n")
                entry["headers_binding"] = bind(header_path)
                data = response.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    entry["over_cap"] = True
                    raise ValueError("Object exceeds fixed1MiB ceiling; no body replacement")
                path = OUT / name
                path.write_bytes(data)
                entry["body_binding"] = bind(path)
                entry["ended_at"] = now()
                entry["ok"] = response.code == 200
                write_json("acquisition_receipt.json", receipt)
                return data if entry["ok"] else None
        except Exception as error:
            entry["error"] = f"{type(error).__name__}: {error}"
            entry["ok"] = False
            entry["ended_at"] = now()
            write_json("acquisition_receipt.json", receipt)
            return None

    try:
        annual_page = (OUT / "annual_release_page.html").read_bytes() if finish_unattempted_progress else get(ANNUAL_PAGE, "annual_release_page.html", "locator")
        if annual_page is None:
            raise ValueError("Annual original locator failed; no substitute permitted")
        annual_url = locate_txt(annual_page, ANNUAL_PAGE, "cropan20.txt")
        progress_page = (OUT / "progress_release_page.html").read_bytes() if finish_unattempted_progress else get(PROGRESS_PAGE, "progress_release_page.html", "locator")
        progress_url = None
        if progress_page is not None:
            progress_url = locate_txt(progress_page, PROGRESS_PAGE, "prog3620.txt")
        annual_body = (OUT / "cropan20.txt").read_bytes() if finish_unattempted_progress else get(annual_url, "cropan20.txt", "original_annual_body")
        if annual_body is None:
            raise ValueError("Annual original body failed; no retry or substitute")
        annual_header = b" ".join(annual_body[:2000].split())
        if not all(word in annual_header for word in [b"Crop Production", b"2019 Summary", b"January 2020"]):
            raise ValueError("Annual content is not fixed original2019 annual report")
        if progress_url is None:
            progress_url = PROGRESS_PDF
            progress_name = "prog3620.pdf"
            receipt["progress_path"] = "preauthorized_same_release_pdf_after_locator_failure"
        else:
            progress_name = "prog3620.txt"
            receipt["progress_path"] = "exact_original_locator_txt_anchor"
        progress_body = get(progress_url, progress_name, "original_progress_body")
        if progress_body is None:
            raise ValueError("Progress original body failed; no retry or substitute")
        receipt["status"] = "acquired_original_bodies_not_yet_parsed"
        receipt["annual_url"] = annual_url
        receipt["progress_url"] = progress_url
        receipt["body_names"] = ["cropan20.txt", progress_name]
    except Exception as error:
        receipt["status"] = "stopped_no_retry"
        receipt["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        receipt["ended_at"] = now()
        receipt["http_attempts"] = len(receipt["requests"])
        receipt["script_binding_at_acquisition_end"] = bind(Path(__file__))
        write_json("acquisition_receipt.json", receipt)


def parse_originals() -> None:
    """Read only the already acquired originals. This operation makes no HTTP calls."""
    destination = OUT / "exposure_manifest.json"
    if destination.exists():
        raise FileExistsError("Fixed sample already parsed; no repeat or replacement")
    receipt = json.loads((OUT / "acquisition_receipt.json").read_text())
    if receipt["status"] != "acquired_original_bodies_not_yet_parsed":
        raise ValueError("Both original source bodies required")
    if len(receipt["requests"]) != 4 or not all(x.get("ok") for x in receipt["requests"]):
        raise ValueError("Expected exact four successful original requests")
    for item in receipt["requests"]:
        for key in ("body_binding", "headers_binding"):
            if bind(Path(item[key]["path"])) != item[key]:
                raise ValueError("Acquired source/headers changed")
    if receipt["body_names"] != ["cropan20.txt", "prog3620.txt"]:
        raise ValueError("Only actual exact-page TXT pair is parsed by this fixed parser")
    # Original annual TXT includes Spanish non-ASCII text (0xf1); cp1252 is
    # lossless for the acquired bytes. All source table tokens are ASCII.
    annual_lines = (OUT / "cropan20.txt").read_text(encoding="cp1252").splitlines()
    progress_lines = (OUT / "prog3620.txt").read_text(encoding="cp1252").splitlines()
    annual_page = (OUT / "annual_release_page.html").read_text()
    progress_page = (OUT / "progress_release_page.html").read_text()
    if '<time datetime="2020-01-10' not in annual_page or '<time datetime="2020-08-31' not in progress_page:
        raise ValueError("Original locating page release dates changed")
    if "Released August 31, 2020" not in " ".join(progress_lines[:12]):
        raise ValueError("Original CropProgress body release mismatch")

    # These headings and year columns are inspected from the actual original TXT.
    production_header = next(i for i, line in enumerate(annual_lines)
                             if "Yield per acre" in line and "Production" in line
                             and any("Soybeans for Beans Area Planted" in x for x in annual_lines[max(0, i-4):i]))
    annual_start = production_header - 3
    year_line = annual_lines[production_header + 2]
    if re.findall(r"\b20\d{2}\b", year_line) != ["2017", "2018", "2019", "2017", "2018", "2019"]:
        raise ValueError("Original annual six-column year order unexpected")
    if "1,000 bushels" not in annual_lines[production_header + 4]:
        raise ValueError("Annual production unit mismatch")

    def label(text: str) -> str:
        return re.sub(r"\s+1/$", "", text.split(".", 1)[0].strip()).strip()

    def value(token: str, *, explicit_dash_zero: bool = False):
        if token in {"(NA)", "(D)", "(X)"}:
            return None
        if token == "-":
            if not explicit_dash_zero:
                raise ValueError("Dash cannot become zero without table footnote")
            return 0
        if not re.fullmatch(r"\d[\d,]*", token):
            raise ValueError(f"Unexpected original numeric token {token!r}")
        return int(token.replace(",", ""))

    annual = {}
    annual_end = None
    for i in range(production_header + 5, len(annual_lines)):
        line = annual_lines[i]
        if ":" not in line:
            continue
        left, right = line.split(":", 1)
        if not re.match(r"[A-Za-z]", left.strip()):
            continue
        tokens = right.split()
        if len(tokens) != 6:
            raise ValueError("Annual state row must have six original columns")
        state = label(left)
        if state in annual:
            raise ValueError("Duplicate annual state")
        annual[state] = {"q2019_1000_bushels": value(tokens[5]), "original_token": tokens[5],
                         "original_all_six_tokens": tokens, "line_number": i + 1, "raw_line": line,
                         "unit": "1000 bushels", "production_column_zero_based": 5}
        if state == "United States":
            annual_end = i + 1
            break
    if annual_end is None or annual["United States"]["q2019_1000_bushels"] != 3558281:
        raise ValueError("Original published US2019 denominator mismatch")

    source_blocks = {"annual_production": {"first_line": annual_start+1, "last_line": annual_end+5,
                                           "lines": annual_lines[annual_start:annual_end+5]}}

    def progress_table(heading: str) -> dict:
        first = progress_lines.index(heading)
        if "18 States planted 96% of the 2019 soybean acreage" not in progress_lines[first+1]:
            raise ValueError("Unexpected original coverage statement")
        dates = progress_lines[first+5]
        years = progress_lines[first+6]
        if not all(x in dates for x in ["August 30,", "August 23,", "2015-2019"]):
            raise ValueError("Original progress date header mismatch")
        if re.findall(r"\b20\d{2}\b", years) != ["2019", "2020", "2020"]:
            raise ValueError("Original progress year order mismatch")
        parsed = {}
        end = None
        for i in range(first+9, len(progress_lines)):
            line = progress_lines[i]
            if ":" not in line:
                continue
            left, right = line.split(":", 1)
            state = label(left)
            if not state:
                continue
            tokens = right.split()
            if len(tokens) != 4:
                raise ValueError("Original progress row must have four columns")
            parsed[state] = {"original_token": tokens[2], "original_all_four_tokens": tokens,
                             "line_number": i+1, "raw_line": line, "unit": "percent",
                             "current_column_zero_based": 2}
            if state == "18 States":
                end = i+1
                break
        if end is None or len(parsed) != 19:
            raise ValueError("Expected all18 original state rows and original aggregate")
        # Same original report footnote explicitly makes a displayed dash zero.
        dash_zero = any(re.fullmatch(r"-\s+Represents zero\.", x.strip()) for x in progress_lines[end:end+40])
        if not dash_zero:
            raise ValueError("Original explicit dash=zero footnote not found")
        for row in parsed.values():
            row["percent"] = value(row["original_token"], explicit_dash_zero=dash_zero)
            row["displayed_dash_is_explicit_reported_zero"] = row["original_token"] == "-"
        source_blocks[heading] = {"first_line": first+1, "last_line": end+4,
                                  "lines": progress_lines[first:end+4]}
        return parsed

    pods = progress_table("Soybeans Setting Pods - Selected States")
    leaves = progress_table("Soybeans Dropping Leaves - Selected States")
    if list(pods) != list(leaves):
        raise ValueError("Original pods and leaves state rosters differ")
    states = [x for x in pods if x != "18 States"]
    rows = []
    with localcontext() as ctx:
        ctx.prec = 36
        denominator = Decimal(annual["United States"]["q2019_1000_bushels"])
        for state in states:
            a, p, l = annual[state], pods[state], leaves[state]
            missing = []
            if a["q2019_1000_bushels"] is None:
                missing.append("original_2019_production_unavailable")
            if p["percent"] is None or l["percent"] is None:
                missing.append("original_current_stage_unavailable")
            if missing:
                w = g = wg = None
            else:
                if not 0 <= l["percent"] <= p["percent"] <= 100:
                    raise ValueError("Stage percentages invalid; no clipping/repair")
                w = Decimal(a["q2019_1000_bushels"]) / denominator
                g = Decimal(p["percent"] - l["percent"]) / Decimal(100)
                wg = w*g
            rows.append({"state": state, "q2019_1000_bushels": a["q2019_1000_bushels"],
                         "us_q2019_1000_bushels": int(denominator), "pods_pct": p["percent"],
                         "leaves_pct": l["percent"], "w": str(w) if w is not None else None,
                         "g": str(g) if g is not None else None,
                         "w_times_g": str(wg) if wg is not None else None,
                         "missing": missing, "annual_raw": a, "pods_raw": p, "leaves_raw": l})
        production_sum = sum(x["q2019_1000_bushels"] for x in rows if x["q2019_1000_bushels"] is not None)
        weighted_g_sum = sum(Decimal(x["w_times_g"]) for x in rows if x["w_times_g"] is not None)
        annual_known_sum = sum(x["q2019_1000_bushels"] for state, x in annual.items()
                               if state != "United States" and x["q2019_1000_bushels"] is not None)
        summary = {"covered_state_count": len(rows), "missing_state_count": sum(bool(x["missing"]) for x in rows),
                   "us_q2019_1000_bushels": int(denominator), "covered_q2019_1000_bushels": production_sum,
                   "covered_q2019_share_of_us": str(Decimal(production_sum)/denominator),
                   "sum_w_times_g": str(weighted_g_sum), "annual_known_state_sum": annual_known_sum,
                   "annual_known_state_sum_minus_us": annual_known_sum-int(denominator),
                   "progress_published_coverage": "18 states planted96percent of2019 acreage; this is acreage, not our computed production share",
                   "original_18_states_aggregate_not_used_as_weighted_g": {"pods": pods["18 States"], "leaves": leaves["18 States"]}}
    row_path = OUT / "exposure_rows.json"
    write_json("exposure_rows.json", {"schema": "stage391_original_soy_exposure_rows_v1", "rows": rows,
                                      "all_annual_states_and_us": annual,
                                      "annual_states_not_in_progress": [x for x in annual if x not in states and x != "United States"]})
    columns = ["state", "q2019_1000_bushels", "us_q2019_1000_bushels", "pods_pct", "leaves_pct", "w", "g", "w_times_g"]
    csv_path = OUT / "exposure_rows.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: row[key] for key in columns} for row in rows)
    write_json("original_table_excerpts.json", source_blocks)
    publish_lower = datetime(2020, 8, 31, 16, 0, tzinfo=ZoneInfo("America/New_York"))
    decision = datetime.fromisoformat("2020-09-01T21:00:00+08:00")
    manifest = {"schema": "stage391_original_soy_exposure_manifest_v1", "status": "original_fixed_sample_parsed_not_financially_qualified",
                "parsed_at": now(), "summary": summary,
                "decoding": "Original TXT interpreted ascp1252; annual byte0xf1 is Spanish text outside soybean tables; originals unchanged, table numeric tokensASCII",
                "clock": {"annual_original_release_date_from_official_page": "2020-01-10",
                          "progress_original_release_date_from_body_and_page": "2020-08-31",
                          "progress_reference_week_end": "2020-08-30",
                          "progress_original_release_policy_raw_lines": progress_lines[883:886],
                          "policy_earliest_release_ET": publish_lower.isoformat(),
                          "policy_earliest_release_UTC": publish_lower.astimezone(timezone.utc).isoformat(),
                          "policy_earliest_release_CST": publish_lower.astimezone(ZoneInfo("Asia/Shanghai")).isoformat(),
                          "decision_asof_CST": decision.isoformat(),
                          "decision_after_policy_lower_bound_hours": (decision-publish_lower).total_seconds()/3600,
                          "strict_historical_first_seen_verified": False,
                          "research_assumption": "The original official report labeled2020-08-31 was publicly available by fixed2020-09-01T21CST; policy says after16ET, not an upper bound. Current Last-Modified and release-page12UTC metadata are not proof of historical first-seen. No traded-PIT qualification asserted."},
                "source_bindings": [x["body_binding"] for x in receipt["requests"]],
                "headers_bindings": [x["headers_binding"] for x in receipt["requests"]],
                "acquisition_receipt_binding": bind(OUT/"acquisition_receipt.json"),
                "initial_terminal_receipt_binding": bind(OUT/"acquisition_initial_terminal.json"),
                "parse_outputs": [bind(row_path), bind(csv_path), bind(OUT/"original_table_excerpts.json")],
                "source_at_parse": bind(Path(__file__)),
                "execution_counts": {"http_attempts": 4, "original_body_downloads": 2, "locator_page_downloads": 2,
                                     "automatic_retries": 0, "duplicate_downloads": 0,
                                     "acquisition_script_invocations": 2, "first_preflight_title_guard_failures": 1,
                                     "parse_invocations": 2, "first_parse_utf8_decode_failures": 1,
                                     "training": 0, "cash_backtests": 0, "market_api": 0},
                "not_claimed": ["No cropmask/geometry", "No national heat quantity", "No forecast revision joined", "No signal or alpha", "No financial or risk qualification", "No true historical first-seen"]}
    write_json("exposure_manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["acquire", "finish_unattempted_progress", "parse"])
    args = parser.parse_args()
    if args.operation == "parse":
        parse_originals()
    else:
        acquire(finish_unattempted_progress=args.operation == "finish_unattempted_progress")
