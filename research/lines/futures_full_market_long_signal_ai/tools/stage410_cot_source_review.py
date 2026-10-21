"""Stage410 independent, offline, single-stream COT source review.

No imports of Stage407 parser, no market/SQL/label access.  Raw and final
phases are separate so a publication worker may finish without rereading ZIPs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
from html.parser import HTMLParser
import io
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, localcontext
from pathlib import Path
import time
from urllib.parse import urljoin
import zipfile
from zoneinfo import ZoneInfo

LINE = Path(__file__).resolve().parents[1]
SOURCE = LINE / "outputs/stage407_cot_source_years/actual_run1"
OUT = LINE / "outputs/stage410_cot_source_review"
MAP = {"SHFE.AU": "088691", "SHFE.AG": "084691", "SHFE.CU": "085692",
       "DCE.M": "026603", "DCE.Y": "007601", "DCE.C": "002602",
       "CZCE.CF": "033661", "CZCE.SR": "080732"}
NUM = {"pmpu_long": "Prod_Merc_Positions_Long_All",
       "pmpu_short": "Prod_Merc_Positions_Short_All",
       "mm_long": "M_Money_Positions_Long_All", "mm_short": "M_Money_Positions_Short_All",
       "open_interest": "Open_Interest_All"}
EXTRA = {"CFTC_Market_Code", "CFTC_Region_Code", "CFTC_Commodity_Code",
         "CFTC_SubGroup_Code", "CFTC_Contract_Market_Code", "Contract_Units", "FutOnly_or_Combined"}


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def read_json(path):
    return json.loads(path.read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def binding(path, body=None):
    body = path.read_bytes() if body is None else body
    return {"path": str(path.resolve()), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def raw_review():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "raw_source_review.json").exists():
        raise FileExistsError("Raw source audit already terminal; do not reread original ZIPs")
    began, tick = now(), time.monotonic()
    protocol = read_json(SOURCE.parent / "protocol.json")
    source = read_json(SOURCE / "source_manifest.json")
    manifest = read_json(SOURCE / "parsed_years_manifest.json")
    issues = []

    def check(condition, message, context=None, level="P1"):
        if not condition:
            issues.append({"severity": level, "message": message, "context": context})

    check(protocol["mapping"] == MAP, "fixed mapping differs")
    requests = source["year_requests"]
    check([r["year"] for r in requests] == protocol["data"]["year_order"], "actual fixed download order differs")
    check(source["GET_total"] == 17 and len(requests) == 16, "request count not 1+16")
    check(len({r["url"] for r in requests}) == 16, "duplicate year URL")
    check(source["official_index"]["status"] == 200, "index not HTTP200")
    index_path = Path(source["official_index"]["body"]["path"])
    index_body = index_path.read_bytes()
    check(binding(index_path, index_body) == source["official_index"]["body"], "index source binding differs")
    actual_bytes = len(index_body)
    reverse = {v: k for k, v in MAP.items()}
    years = {y["year"]: y for y in manifest["years"]}
    all_keys = defaultdict(list)
    market_names = defaultdict(set)
    total = Counter()
    date_formats, header_date_names = Counter(), Counter()
    mapped_dates, annual, max_error = set(), [], Decimal(0)
    numbers_zero = Counter()
    primary_names = defaultdict(set)
    for req in requests:
        year = req["year"]
        check(req["ok"] and req["status"] == 200, "year request failed", year)
        check(req["retry"] == 0 and req["redirect"] == 0, "retry or redirect occurred", year)
        check(req["anchor"]["table_summary"] == "Disaggregated Futures Only Reports" and req["anchor"]["label"] == "Text", "wrong source table", year)
        path = Path(req["body"]["path"])
        body = path.read_bytes()  # Exactly one raw ZIP read, hash and parse same bytes.
        actual_bytes += len(body)
        zbind = binding(path, body)
        check(zbind == req["body"] == years[year]["source_zip"], "ZIP binding mismatch", year)
        check(len(body) < 8388608, "ZIP exceeds fixed body limit", year)
        parsed = SOURCE / "parsed_years" / str(year)
        schema = read_json(parsed / f"schema_{year}.json")
        mapped_records = [json.loads(s) for s in (parsed / f"mapped_{year}.jsonl").read_text().splitlines()]
        mapped_by = {(r["member"], r["line_number"]): r for r in mapped_records}
        check(len(mapped_by) == len(mapped_records), "mapped provenance duplicate", year)
        identity_path = parsed / f"identities_{year}.jsonl"
        counts, bycode, names, duplicate_keys = Counter(), Counter(), defaultdict(set), defaultdict(list)
        raw_mapped = []
        crc_members = []
        with identity_path.open() as identity_file, zipfile.ZipFile(io.BytesIO(body)) as archive:
            check(sum(i.file_size for i in archive.infolist()) <= 134217728, "uncompressed size exceeds protocol", year)
            for member in archive.infolist():
                if member.is_dir():
                    continue
                if not member.filename.lower().endswith((".csv", ".txt")):
                    with archive.open(member) as f:
                        for block in iter(lambda: f.read(1024 * 1024), b""):
                            counts["uncompressed_nontext_bytes"] += len(block)
                    crc_members.append(member.filename)
                    continue
                counts["uncompressed_text_bytes"] += member.file_size
                with archive.open(member) as raw:
                    reader = csv.reader(io.TextIOWrapper(raw, encoding="cp1252", newline=""))
                    header = next(reader)
                    indices = {h.strip(): i for i, h in enumerate(header)}
                    check(len(header) == 191, "actual column count differs from191", year)
                    report_col = "Report_Date_as_YYYY-MM-DD" if "Report_Date_as_YYYY-MM-DD" in indices else "Report_Date_as_MM_DD_YYYY"
                    header_date_names[report_col] += 1
                    previous = reader.line_num
                    for tokens in reader:
                        start, previous = previous + 1, reader.line_num
                        if not tokens or not any(t.strip() for t in tokens):
                            continue
                        counts["identity_rows"] += 1
                        line = next(identity_file, None)
                        if line is None:
                            check(False, "derived identity shorter than original", [year, start])
                            continue
                        derived = json.loads(line)
                        original = {h.strip(): tokens[i] for i, h in enumerate(header)}
                        code = original["CFTC_Contract_Market_Code"].strip()
                        name = original["Market_and_Exchange_Names"]
                        report = original[report_col].strip()
                        # Independently parse what is actually in the report-date column.
                        asof = date.fromisoformat(report)
                        date_formats["ISO_YYYY_MM_DD"] += 1
                        ymd = original["As_of_Date_In_Form_YYMMDD"].strip()
                        check(len(ymd) == 6 and ymd.isdigit() and asof.strftime("%y%m%d") == ymd, "two original asof fields disagree", [year, start])
                        check(len(tokens) == len(header), "row shape mismatch", [year, start])
                        row_hash = hashlib.sha256(canonical(tokens)).hexdigest()
                        expected = {"year_tag": year, "member": member.filename, "line_number": start,
                                    "last_line_number": reader.line_num, "market_code": code,
                                    "market_code_token": original["CFTC_Contract_Market_Code"],
                                    "market_name": name, "original_column_count": len(tokens),
                                    "header_column_count": len(header), "row_shape_matches_header": len(tokens) == len(header),
                                    "original_row_tokens_sha256": row_hash, "source_zip": zbind,
                                    "original_date_tokens": {"asof_yymmdd": original["As_of_Date_In_Form_YYMMDD"], "report_date": original[report_col]},
                                    "extra_identity_tokens": {h: original[h] for h in original if h in EXTRA}}
                        check(all(derived.get(k) == v for k, v in expected.items()), "original identity projection mismatch", [year, member.filename, start])
                        check(derived["asof"]["date"] == asof.isoformat() and derived["asof"]["weekday"] == asof.weekday() and derived["asof"]["is_publication_timestamp"] is False, "asof derivation mismatch", [year, start])
                        bycode[code] += 1
                        names[code].add(name)
                        market_names[code].add(name)
                        counts[f"weekday_{asof.weekday()}"] += 1
                        if asof.year != year:
                            counts["asof_year_differs_from_archive_year"] += 1
                        key = (code, asof.isoformat())
                        duplicate_keys[key].append((row_hash, start))
                        all_keys[key].append((year, row_hash, name, start))
                        if code not in reverse:
                            continue
                        rec = mapped_by.get((member.filename, start))
                        check(rec is not None, "mapped original row absent", [year, start])
                        if rec is None:
                            continue
                        counts["mapped_rows"] += 1
                        mapped_dates.add(asof.isoformat())
                        primary_names[reverse[code]].add(name.strip())
                        raw_values = {}
                        for role, field in NUM.items():
                            token = original[field]
                            stripped = token.strip().replace(",", "")
                            value = int(stripped) if stripped.isdigit() else None
                            raw_values[role] = value
                            got = rec["original_numeric_fields"][role]
                            check(got["token"] == token and got["value"] == value, "mapped numeric token/value mismatch", [year, start, role])
                            if value == 0:
                                numbers_zero[role] += 1
                                check(got["status"] == "reported_integer", "legitimate reported zero converted unknown", [year, start, role])
                        p_l, p_s, m_l, m_s, oi = (raw_values[k] for k in ("pmpu_long", "pmpu_short", "mm_long", "mm_short", "open_interest"))
                        expected_h = expected_mm = None
                        if oi is not None and oi > 0:
                            with localcontext() as context:
                                context.prec = 50
                                if p_l is not None and p_s is not None:
                                    expected_h = Decimal(p_s - p_l) / Decimal(oi)
                                if m_l is not None and m_s is not None:
                                    expected_mm = Decimal(m_l - m_s) / Decimal(oi)
                        for role, value in (("H", expected_h), ("MM", expected_mm)):
                            if value is None:
                                check(rec[role] is None, "invalid original inputs manufactured ratio", [year, start, role])
                            else:
                                check(rec[role] is not None, "valid original numeric ratio missing", [year, start, role])
                                if rec[role] is not None:
                                    error = abs(Decimal(str(rec[role])) - value)
                                    max_error = max(max_error, error)
                                    check(error <= Decimal("1e-15"), "ratio exceeds1e-15 independentDecimal error", [year, start, role, str(error)])
                        check(rec["H_numerator_short_minus_long"] == p_s - p_l and rec["MM_numerator_long_minus_short"] == m_l - m_s and rec["ratio_denominator_OI"] == oi, "ratio signed numerator/denominator mismatch", [year, start])
                        check(rec["channel"] == reverse[code], "channel mapping mismatch", [year, start])
                        raw_mapped.append((key, rec))
                    # EOF exhausts ZipExtFile and makes standard zipfile verify CRC.
                    crc_members.append(member.filename)
            check(next(identity_file, None) is None, "derived identity contains rows absent from original", year)
        duplicates = {k: v for k, v in duplicate_keys.items() if len(v) > 1}
        conflicts = {k: v for k, v in duplicates.items() if len({r[0] for r in v}) > 1}
        for key, rec in raw_mapped:
            group = duplicate_keys[key]
            conflict = key in conflicts
            check(rec["within_year_duplicate_count"] == len(group) and rec["within_year_conflicting_duplicate"] == conflict, "mapped duplicate status mismatch", [year, key])
            if conflict:
                check(rec["H"] is None and rec["MM"] is None, "conflicting original duplicates still known", [year, key])
        expected_names = [{"market_code": c, "names": sorted(names[c]), "row_count": bycode[c]} for c in sorted(bycode)]
        check(schema["all_market_names_and_row_counts"] == expected_names, "historical all-market identities dropped or renamed", year)
        check(counts["identity_rows"] == schema["identity_rows"] == years[year]["identity_rows"], "original row count mismatch", year)
        check(counts["mapped_rows"] == schema["mapped_rows"] == len(mapped_records), "mapped row count mismatch", year)
        check(schema["within_year_duplicate_groups"] == len(duplicates) and schema["within_year_conflicting_duplicate_groups"] == len(conflicts), "year duplicate summary mismatch", year)
        total.update(counts)
        annual.append({"year": year, **dict(counts), "compressed_bytes": len(body), "markets": len(bycode),
                       "duplicate_groups": len(duplicates), "conflicting_groups": len(conflicts), "CRC_members_verified": crc_members})
        print(json.dumps({"year": year, "original_rows": counts["identity_rows"], "mapped_rows": counts["mapped_rows"], "issues_so_far": len(issues)}), flush=True)
    cross = {k: v for k, v in all_keys.items() if len({r[0] for r in v}) > 1}
    cross_conflicts = {k: v for k, v in cross.items() if len({r[1] for r in v}) > 1}
    check(actual_bytes == source["source_body_bytes"] and actual_bytes <= 125829120, "total body count/budget mismatch")
    for key in ("Y_reads", "fit", "cash", "market_API", "SQL", "automatic_retries", "duplicate_URL_GET"):
        check(source[key] == 0, "source manifest forbidden action count nonzero", key)
    result = {"schema": "stage410_independent_cot_raw_review_v1", "started_at": began, "ended_at": now(),
              "elapsed_seconds": time.monotonic() - tick, "status": "passed_source_values_not_availability" if not issues else "findings_require_root_decision",
              "source_manifest": binding(SOURCE / "source_manifest.json"), "protocol": binding(SOURCE.parent / "protocol.json"),
              "counts": dict(total), "annual": annual, "source_body_bytes_including_index": actual_bytes,
              "unique_all_historical_market_codes": len(market_names), "unique_original_asof_dates_mapped": len(mapped_dates),
              "date_content_formats": dict(date_formats), "original_date_column_names": dict(header_date_names),
              "original_mapping_names": {k: sorted(v) for k, v in primary_names.items()},
              "reported_numeric_zero_counts": dict(numbers_zero), "ratio_max_decimal_absolute_error": str(max_error),
              "cross_year_duplicate_groups": len(cross), "cross_year_conflicting_groups": len(cross_conflicts),
              "cross_year_groups": [{"code": k[0], "asof": k[1], "occurrences": v, "conflicting": k in cross_conflicts} for k, v in sorted(cross.items())],
              "issues": issues, "severity_counts": {p: sum(i["severity"] == p for i in issues) for p in ("P0", "P1", "P2")},
              "scope": {"network": 0, "Y": 0, "fit": 0, "cash": 0, "market_API": 0, "SQL": 0,
                        "raw_ZIP_reads": 16, "original_ZIP_stream_passes": 16, "old_financial_suite_runs": 0,
                        "all98products95families_policy_retained_not_joined_here": True,
                        "eight_mapping_not_full_market_alpha": True, "historical_first_seen_not_proven": True,
                        "publication_qualification": "separate_Stage408_root_projection_required"},
              "overfit_before_after": "未读收益或择参；既有COT题目的历史适应性风险仍在，源值通过不是alpha通过。",
              "continue_value": "有：一次源正确性审计有助于避免错误输入；不支持重复源校验或绕过发布时间资格。"}
    dump(OUT / "raw_source_review.json", result)
    print(json.dumps({"terminal": result["status"], "rows": total["identity_rows"], "mapped": total["mapped_rows"], "issues": len(issues), "seconds": result["elapsed_seconds"]}), flush=True)


def aggregate_review():
    """Only newly terminal aggregate; no original ZIP/year JSONL rereads."""
    began, tick = now(), time.monotonic()
    raw = read_json(OUT / "raw_source_review.json")
    manifest = read_json(SOURCE / "parsed_years_manifest.json")
    summary_path = SOURCE / "aggregate_source_summary.json"
    summary = read_json(summary_path)
    canonical_path = Path(summary["canonical_mapped"]["path"])
    canonical_body = canonical_path.read_bytes()
    records = [json.loads(s) for s in canonical_body.splitlines()]
    index_path = Path(summary["historical_identity_index"]["path"])
    index_body = index_path.read_bytes()
    index = json.loads(index_body)
    issues = []

    def check(condition, message, context=None):
        if not condition:
            issues.append({"severity": "P1", "message": message, "context": context})

    check(binding(canonical_path, canonical_body) == summary["canonical_mapped"], "canonical body binding differs")
    check(binding(index_path, index_body) == summary["historical_identity_index"], "historical index binding differs")
    dates, keys, by_year = set(), set(), defaultdict(list)
    known = 0
    additive = {"observed_origins", "cross_year_or_member_conflicting_duplicate", "observed_duplicate_count"}
    for rec in records:
        key = (rec["asof"]["date"], rec["channel"])
        check(key not in keys, "canonical duplicate key", key)
        keys.add(key)
        dates.add(key[0])
        check(rec["channel"] in MAP and rec["market_code"] == MAP[rec["channel"]], "canonical fixed mapping changed", key)
        check(rec["asof"]["is_publication_timestamp"] is False, "canonical asof mislabeled publication", key)
        check(rec["observed_duplicate_count"] == 1 and not rec["cross_year_or_member_conflicting_duplicate"], "unexpected canonical duplicate state", key)
        origins = rec["observed_origins"]
        expected_origin = {k: rec[k] for k in ("year_tag", "source_zip", "member", "line_number", "original_row_tokens_sha256")}
        check(origins == [expected_origin], "canonical original provenance not preserved", key)
        original_projection = {k: v for k, v in rec.items() if k not in additive}
        by_year[rec["year_tag"]].append(original_projection)
        known += rec["H"] is not None and rec["MM"] is not None
    for year in manifest["years"]:
        rows = sorted(by_year[year["year"]], key=lambda r: (r["member"], r["line_number"]))
        # Each actual ZIP has one text member; restore the exact author JSONL
        # serialization from canonical originals, rather than rereading it.
        reconstructed = b"".join(canonical(r) + b"\n" for r in rows)
        expected = year["outputs"]["mapped"]
        check(len(reconstructed) == expected["bytes"] and hashlib.sha256(reconstructed).hexdigest() == expected["sha256"], "canonical changed independently reviewed annual projection", year["year"])
    check(len(records) == known == raw["counts"]["mapped_rows"] == summary["canonical_grid_rows"], "canonical known row count differs")
    check(len(dates) == raw["unique_original_asof_dates_mapped"] == summary["mapped_original_asof_dates"], "canonical original date count differs")
    check(keys == {(d, c) for d in dates for c in MAP}, "observed-asof fixed8 grid incomplete")
    check(len(index) == raw["unique_all_historical_market_codes"] == summary["all_historical_codes"], "historical market index count differs")
    check(sum(r["source_row_count"] for r in index.values()) == raw["counts"]["identity_rows"] == summary["all_historical_identity_rows"], "historical index row count differs")
    check(sum(len(r["original_names"]) for r in index.values()) == summary["all_historical_names"], "historical index original-name count differs")
    check(summary["mother_products"] == 98 and summary["mother_families"] == 95 and summary["other_products_unmapped_unknown_not_deleted"] == 90, "full-market policy narrowed to mapped8")
    check(summary["visible_week_event_qualification"] == "not_performed_clock408_required" and summary["current_ZIP_may_have_historical_revisions"], "source aggregate overclaims availability/vintage")
    result = {"schema": "stage410_independent_canonical_aggregate_review_v1", "started_at": began, "ended_at": now(),
              "elapsed_seconds": time.monotonic() - tick, "aggregate": binding(summary_path),
              "canonical": binding(canonical_path, canonical_body), "historical_identity_index": binding(index_path, index_body),
              "status": "passed_canonical_source_only" if not issues else "findings_require_root_decision",
              "canonical_rows": len(records), "original_asof_dates": len(dates), "known_H_MM_rows": known,
              "all_historical_codes": len(index), "all_historical_code_name_pairs": sum(len(r["original_names"]) for r in index.values()),
              "canonical_annual_projection_hashes_match": not issues,
              "issues": issues, "severity_counts": {p: sum(i["severity"] == p for i in issues) for p in ("P0", "P1", "P2")},
              "zero_raw_ZIP_or_annual_JSONL_rereads": True, "finance_qualified": False,
              "835_is_report_asof_not_actual_release_events": True}
    dump(OUT / "aggregate_review.json", result)
    print(json.dumps({"terminal": result["status"], "issues": len(issues), "seconds": result["elapsed_seconds"]}), flush=True)


def one_boundary_fixture():
    """One seven-row synthetic fixture for branches absent in actual mapped rows."""
    fixture = OUT / "one_synthetic_boundary_fixture"
    fixture.mkdir(exist_ok=False)
    header = read_json(SOURCE / "first2010_observed_schema.json")["header"]
    fields = {h.strip(): i for i, h in enumerate(header)}
    rows = []
    cases = [("2011-01-04", "0", "0", "0", "0", "100"),
             ("2011-01-11", "1", "2", "3", "4", "0"),
             ("2011-01-18", "", "2", "3", "4", "100"),
             ("2011-01-25", "1", "2", "-1", "4", "100"),
             ("2011-02-01", "1", "2", "3", "4", "100"),
             ("2011-02-01", "9", "2", "3", "4", "100"),
             ("2011-02-08", "1", "2", "3", "4", "100")]
    report_field = "Report_Date_as_MM_DD_YYYY" if "Report_Date_as_MM_DD_YYYY" in fields else "Report_Date_as_YYYY-MM-DD"
    for number, (d, p_l, p_s, m_l, m_s, oi) in enumerate(cases):
        row = [""] * len(header)
        values = {"Market_and_Exchange_Names": "SYNTHETIC NONMARKET CORN TEST",
                  "CFTC_Contract_Market_Code": "002602", report_field: d,
                  "As_of_Date_In_Form_YYMMDD": date.fromisoformat(d).strftime("%y%m%d"),
                  "FutOnly_or_Combined": "FutOnly",
                  **dict(zip(NUM.values(), (p_l, p_s, m_l, m_s, oi)))}
        if number == 6:
            values["As_of_Date_In_Form_YYMMDD"] = "110209"
        for field, value in values.items():
            row[fields[field]] = value
        rows.append(row)
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(header)
    writer.writerows(rows)
    path = fixture / "synthetic_only.zip"
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("synthetic.csv", text.getvalue().encode("cp1252"))
    tool = LINE / "tools/stage407_cot_parse_year.py"
    spec = importlib.util.spec_from_file_location("stage410_author_fixture_only", tool)
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    summary = parser.parse_year(path, 2011, MAP, fixture / "author_projection")
    result_rows = [json.loads(s) for s in Path(summary["outputs"]["mapped"]["path"]).read_text().splitlines()]
    tests = {"legitimate_zero_known": result_rows[0]["H"] == 0 and result_rows[0]["MM"] == 0 and result_rows[0]["status"] == "known_ratios",
             "OI_zero_both_unknown": result_rows[1]["H"] is None and result_rows[1]["MM"] is None,
             "missing_PMPU_H_unknown_MM_independently_known": result_rows[2]["H"] is None and result_rows[2]["MM"] == -0.01,
             "negative_MM_MM_unknown_H_independently_known": result_rows[3]["H"] == 0.01 and result_rows[3]["MM"] is None,
             "conflicting_duplicates_both_unknown": all(result_rows[i]["H"] is None and result_rows[i]["MM"] is None and result_rows[i]["within_year_conflicting_duplicate"] for i in (4, 5)),
             "conflicting_original_dates_both_unknown": result_rows[6]["H"] is None and result_rows[6]["MM"] is None and result_rows[6]["asof"]["date"] is None,
             "no_reported_numeric_zero_to_missing": all(v["value"] == 0 and v["status"] == "reported_integer" for k, v in result_rows[0]["original_numeric_fields"].items() if k != "open_interest")}
    result = {"schema": "stage410_one_synthetic_boundary_fixture_v1", "at": now(), "rows": 7,
              "synthetic_never_financial_data": True, "tests": tests, "all_passed": all(tests.values()),
              "author_parser": binding(tool), "input": binding(path), "author_projection": summary,
              "actual_raw_ZIP_rereads": 0, "source_or_parser_mutations": 0, "fit": 0, "cash": 0}
    dump(OUT / "one_boundary_fixture_receipt.json", result)
    print(json.dumps({"all_passed": result["all_passed"], "tests": tests}), flush=True)


def publication_review():
    """One bounded review of terminal 408 original pages and normalized facts."""
    began, tick = now(), time.monotonic()
    base = LINE / "outputs/stage408_cftc_publication_evidence"
    panel_path = base / "compiled/exceptions_panel.json"
    panel = read_json(panel_path)
    receipt_path = base / "compiled/source_panel_receipt.json"
    receipt = read_json(receipt_path)
    http = read_json(base / "actual_http1/receipt.json")
    sources = {s["source_id"]: s for s in panel["sources"]}
    issues, bodies, texts, source_links = [], {}, {}, {}

    def check(condition, message, context=None):
        if not condition:
            issues.append({"severity": "P1", "message": message, "context": context})

    class OriginalHTML(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.data, self.links = [], []

        def handle_data(self, data):
            self.data.append(data)

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.links += [v for k, v in attrs if k == "href"]

    compact = lambda s: re.sub(r"\s+", "", s)
    for sid, source in sources.items():
        path = Path(source["raw"]["path"])
        body = path.read_bytes()
        check(binding(path, body) == source["raw"], "408 original body binding mismatch", sid)
        parser = OriginalHTML()
        parser.feed(body.decode("utf-8"))
        bodies[sid] = compact("".join(parser.data))
        source_links[sid] = {urljoin(source["url"], u) for u in parser.links}
        derived_path = Path(source["derived_text"]["path"])
        derived = derived_path.read_bytes()
        check(binding(derived_path, derived) == source["derived_text"], "408 derived text binding mismatch", sid)
        texts[sid] = derived.decode("utf-8").splitlines()
        check(source["evidence_type"] == "actual_HTTP200_official_HTML", "408 mislabels source type", sid)
        check(datetime.fromisoformat(source["downloaded_at_2026_UTC"]).year == 2026 and not source["historical_publication_clock_inferred_from_download"], "2026 download substituted as historical clock", sid)
    links = source_links["S01"] | source_links["S02"]
    for sid, source in sources.items():
        check(sid in ("S01", "S02") or source["url"] in links, "related official URL not found in saved entry links", sid)
    requests = http["requests"]
    check(len(requests) == 9 == receipt["actual_GET"] and len(sources) == 9, "408 GET/source count differs")
    check(sum(r["body"]["bytes"] for r in requests) == receipt["raw_body_bytes"] == 459252, "408 actual byte ledger differs")
    check(len({r["url"] for r in requests}) == 9 and all(r["status"] == 200 and r["retry"] == 0 and r["redirect"] == 0 for r in requests), "408 failed/retried/duplicate/redirected request")
    check(all(datetime.fromisoformat(a["ended_at"]) <= datetime.fromisoformat(b["started_at"]) for a, b in zip(requests, requests[1:])), "408 worker requests overlapped")
    excerpts = []

    def walk(value):
        if isinstance(value, dict):
            if {"source_id", "original_text", "derived_line_start", "derived_line_end"}.issubset(value):
                excerpts.append(value)
            else:
                for item in value.values():
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(panel)
    for excerpt in excerpts:
        sid = excerpt["source_id"]
        actual = "\n".join(texts[sid][excerpt["derived_line_start"]-1:excerpt["derived_line_end"]])
        check(actual == excerpt["original_text"], "408 evidence line range differs from saved derived text", [sid, excerpt["derived_line_start"]])
        check(compact(actual) in bodies[sid], "408 evidence excerpt not found in independent original HTML text", [sid, excerpt["derived_line_start"]])
    events = panel["publication_events"]
    check(len(events) == panel["publication_event_count"] == 54, "408 event count differs")
    ids = {e["event_id"]: e for e in events}
    ion = [e for e in events if e["event_id"].startswith("ION_")]
    check(len(ion) == 7 and all(e["confirmed_release_date"] and e["confirmed_release_at"] is None and e["research_available_at"] is None for e in ion), "ION planned/date-only fact overstated")
    check(sum(e["position_asof"] is None for e in ion) == 3, "ION last3 unknown asof manufactured")
    for e in ion:
        check("issuing" in " ".join(x["original_text"] for x in e["evidence"]).lower(), "ION actual confirmation not grounded in issuing text", e["event_id"])
    revised = [e for e in events if e.get("plan_version") == "revised"]
    initial = [e for e in events if e.get("plan_version") == "initial"]
    check(len(initial) == 17 and len(revised) == 13, "2025 planned versions collapsed")
    check(all(e["confirmed_release_date"] is None and e["confirmed_release_at"] is None and e["research_available_at"] is None and e["release_status"] == "planned_not_confirmed" for e in initial+revised), "intended2025 plan promoted to actual")
    ny = ZoneInfo("America/New_York")
    for e in events:
        if e["candidate_research_boundary_next_NY_midnight"]:
            t = datetime.fromisoformat(e["candidate_research_boundary_next_NY_midnight"])
            check(e["candidate_boundary_is_assumption"] and t.hour == 0 and t.minute == 0 and t.utcoffset() == t.replace(tzinfo=ny).utcoffset(), "date-only boundary not explicit assumption/DST", e["event_id"])
        if e["release_status"] == "planned_not_confirmed":
            check(e["research_available_at"] is None and e["confirmed_release_date"] is None, "planned event grants actual availability", e["event_id"])
    corrections = {r["correction_id"]: r for r in panel["corrections_and_scope"]}
    check(len(corrections) == 11, "correction scope count differs")
    expected_targets = {"classification2012_all": set(MAP.values()), "reporting2017_transfer": {"002602", "080732"},
                        "reporting2019_march": set(MAP.values()) - {"085692"}, "reporting2019_october": {"002602", "007601", "026603"},
                        "OI2011_corn_adjusted_at_release": {"002602"}}
    for cid, expected in expected_targets.items():
        check(set(corrections[cid]["mapped_target_codes"]) == expected, "correction target scope differs", cid)
    for cid in ("Legacy2018_concentration_not_target", "options2018_not_target", "options2014_not_target", "options2010_corn_not_automatic_target", "format2015_reportdate", "metadata2022_copper_name"):
        check(not corrections[cid]["mapped_target_codes"] and not corrections[cid]["target_disaggregated_FuturesOnly_implicated"], "unrelated Legacy/combined/metadata correction masks target", cid)
    check(corrections["OI2011_corn_adjusted_at_release"]["kind"] == "adjustment_at_publication_not_later_revision", "original-publication OI adjustment treated as later correction")
    check(panel["source_clock_rule"]["strict_original_firstseen_vintage_obtained"] is False and panel["source_clock_rule"]["current_2026_tentative_calendar_applies_to_2010_2025"] is False, "408 overstates firstseen or calendar")
    check(not receipt["financial_or_alpha_qualification"] and not panel["downstream_contract"]["source_floor_400_or_held35_computed_here"], "408 financial qualification claimed")
    domain = panel["domain"]
    check(domain["mother_universe_products"] == 98 and domain["mother_universe_families"] == 95 and domain["unmapped_products"] == 90 and not domain["mother_scope_narrowed"], "408 full-market domain narrowed")
    result = {"schema": "stage410_independent_publication_source_review_v1", "started_at": began, "ended_at": now(),
              "elapsed_seconds": time.monotonic()-tick, "panel": binding(panel_path), "source_panel_receipt": binding(receipt_path),
              "status": "passed_bounded_source_semantics_not_weekly_or_finance_qualification" if not issues else "findings_require_root_decision",
              "official_raw_pages_read_once": len(sources), "actual_author_GET": 9, "actual_author_body_bytes": 459252,
              "verified_evidence_excerpts_with_duplicate_references": len(excerpts), "normalized_events": len(events), "correction_scopes": len(corrections),
              "ION_confirmed_dates_exact_clock_unknown": 7, "ION_unknown_position_asof_rows": 3,
              "2025_initial_intended": 17, "2025_revised_intended": 13, "2025_confirmed": 0,
              "issues": issues, "severity_counts": {p: sum(i["severity"] == p for i in issues) for p in ("P0", "P1", "P2")},
              "remaining_unknowns_are_disclosed_not_source_bugs": panel["remaining_unknowns"],
              "stale_downstream_expectation_root409_builds_projection": panel["downstream_contract"].get("root409_builds_weekly_projection_and_visible_event_counts"),
              "stale_expectation_disposition": "root409 supersedes: no weekly projection or financial continuation; preserve408 original provenance",
              "ordinary_qualified_week_count_not_computed_no_need_to_construct_for_closed_value_route": True,
              "network": 0, "Y": 0, "fit": 0, "cash": 0, "market_API": 0, "SQL": 0}
    dump(OUT / "publication_review.json", result)
    print(json.dumps({"terminal": result["status"], "issues": len(issues), "excerpts": len(excerpts), "seconds": result["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("raw", "aggregate", "fixture", "publication"), required=True)
    arguments = parser.parse_args()
    {"raw": raw_review, "aggregate": aggregate_review, "fixture": one_boundary_fixture, "publication": publication_review}[arguments.phase]()
