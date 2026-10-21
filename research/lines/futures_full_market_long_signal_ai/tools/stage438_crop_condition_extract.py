#!/usr/bin/env python3
"""Bounded, source-only projection of already archived USDA crop-condition TXT.

No downloads, prices, labels, model work or account work. Importing this module
does no I/O. Actual execution requires a root-issued authorization bound to this
script's bytes, frozen scope bytes, and a new output directory.
"""
import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

SCOPE_SHA256 = "8a2cdd97ff0bf76ab4ced7377ce17e90d4911a219031dbc2954f6fc0c74309c5"
CROPS = ("Corn", "Soybeans")
CATEGORIES = ("Very poor", "Poor", "Fair", "Good", "Excellent")
MONTHS = {name: number for number, name in enumerate((
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"), 1)}
DATE_TEXT = r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})"
TITLE = re.compile(r"^\s*(Corn|Soybeans?) Condition\b", re.I)
EXACT_TITLE = re.compile(
    r"^\s*(Corn|Soybeans?) Condition\s*-\s*Selected States:\s*Week Ending\s*(.*)$", re.I)
NEXT_TABLE = re.compile(r"^\s*[A-Za-z][A-Za-z &'/-]*\s+-\s+Selected States\b")
NATIONAL = re.compile(r"^\s*(\d+ States|United States|U\.S\.)\s*\.*\s*:", re.I)


def sha256(blob):
    return hashlib.sha256(blob).hexdigest()


def identity(path, blob):
    return {"path": str(Path(path).resolve()), "bytes": len(blob), "sha256": sha256(blob)}


def evidence(number, text):
    return {"line_number": number, "raw_line": text}


def parse_date(text):
    match = re.fullmatch(DATE_TEXT, text.strip())
    if not match or match[1] not in MONTHS:
        return None
    try:
        return date(int(match[3]), MONTHS[match[1]], int(match[2])).isoformat()
    except ValueError:
        return None


def release_info(lines, metadata_release_date):
    candidates = []
    for number, line in enumerate(lines, 1):
        if re.match(r"^\s*Released\b", line):
            match = re.match(r"^\s*Released\s+(" + DATE_TEXT + r")(?:,|\s|$)", line)
            candidates.append({**evidence(number, line),
                               "parsed_date": parse_date(match[1]) if match else None})
    reasons = []
    if len(candidates) != 1:
        reasons.append("body_release_not_unique" if candidates else "body_release_missing")
    body_date = candidates[0]["parsed_date"] if len(candidates) == 1 else None
    if len(candidates) == 1 and body_date is None:
        reasons.append("body_release_date_unparsed")
    if body_date is not None and body_date != metadata_release_date:
        reasons.append("body_metadata_release_disagreement")
    return {"status": "known" if not reasons else "unknown", "unknown_reasons": reasons,
            "metadata_release_date": metadata_release_date, "body_release_date": body_date,
            "candidates": candidates, "historical_first_seen": "unknown",
            "historical_first_seen_reason": "archive_and_HTTP_clocks_are_not_historical_first_seen"}


def policy_passages(lines):
    passages, start = [], 0
    for stop in range(len(lines) + 1):
        if stop < len(lines) and lines[stop].strip():
            continue
        if stop > start:
            block = lines[start:stop]
            text = "\n".join(block)
            if ("Revision Policy:" in text or
                    re.search(r"(?:estimates|reports?)\b.*\breleased\b|release.*\bET\b", text, re.I)):
                passages.append({"line_start": start + 1, "line_end": stop, "raw_text": text})
        start = stop + 1
    return passages


def five_row(candidates, zero_definition):
    result = {"status": "unknown", "unknown_reasons": [], "five_categories": None,
              "good_plus_excellent": None, "raw_tokens": None, "candidates": candidates,
              "line_number": None, "raw_line": None, "aggregate_label": None,
              "zero_definition": zero_definition, "explicit_reference_date": None,
              "explicit_reference_date_status": "not_printed"}
    reasons = result["unknown_reasons"]
    if len(candidates) != 1:
        reasons.append("row_missing" if not candidates else "row_not_unique")
        return result
    item = candidates[0]
    result.update({key: item[key] for key in ("line_number", "raw_line")})
    label, values = item["raw_line"].split(":", 1)
    result["aggregate_label"] = re.sub(r"\s*\.+\s*$", "", label).strip()
    if re.match(r"^\s*Previous (?:week|year)\b", label, re.I):
        printed_dates = re.findall(DATE_TEXT, label)
        if len(printed_dates) == 1:
            month, day, year = printed_dates[0]
            result["explicit_reference_date"] = parse_date(f"{month} {day}, {year}")
            result["explicit_reference_date_status"] = "known" if result["explicit_reference_date"] else "unknown"
        elif printed_dates or re.search(r"\d", label):
            result["explicit_reference_date_status"] = "unknown"
        if result["explicit_reference_date_status"] == "unknown":
            reasons.append("printed_row_date_not_unique_or_unparsed")
    tokens = values.split()
    result["raw_tokens"] = tokens
    if len(tokens) != 5:
        reasons.append("not_exactly_five_tokens")
        return result
    numbers = []
    for token in tokens:
        if re.fullmatch(r"\d{1,3}", token):
            numbers.append(int(token))
        elif token == "-" and zero_definition:
            numbers.append(0)
        else:
            reasons.append("non_numeric_or_undefined_zero_token")
            return result
    result["five_categories"] = numbers
    result["sum_diagnostic"] = sum(numbers)
    if any(number < 0 or number > 100 for number in numbers):
        reasons.append("category_outside_0_100")
    if sum(numbers) != 100:
        reasons.append("five_categories_sum_not_100")
    if not reasons:
        result["status"] = "known"
        result["good_plus_excellent"] = numbers[3] + numbers[4]
    return result


def parse_table(lines, index):
    stop = next((i for i in range(index + 1, len(lines)) if NEXT_TABLE.match(lines[i])
                 or lines[i].startswith("Crop Progress and Condition Tables")), len(lines))
    block = [(i + 1, lines[i]) for i in range(index, stop)]
    reasons = []
    title_match = EXACT_TITLE.match(lines[index])
    reference = None
    date_lines = [evidence(index + 1, lines[index])]
    if not title_match:
        reasons.append("condition_title_format_unknown")
    else:
        reference_text = title_match[2].strip()
        if not reference_text and index + 1 < stop:
            reference_text = lines[index + 1].strip()
            date_lines.append(evidence(index + 2, lines[index + 1]))
        reference = parse_date(reference_text)
        if reference is None:
            reasons.append("reference_week_date_unparsed")
    headers = []
    header_candidates = []
    for number, line in block:
        parts = [re.sub(r"\s+", " ", p).strip().lower() for p in line.split(":")]
        if parts[0] == "state":
            header_candidates.append(evidence(number, line))
        if parts == ["state"] + [name.lower() for name in CATEGORIES]:
            headers.append(evidence(number, line))
    if len(headers) != 1:
        reasons.append("five_category_header_not_unique" if headers else "five_category_header_missing")
    zero_definition = [evidence(number, line) for number, line in block
                       if re.fullmatch(r"\s*-\s+Represents zero\.\s*", line)]
    nationals = [evidence(number, line) for number, line in block if NATIONAL.match(line)]
    previous = [evidence(number, line) for number, line in block
                if re.match(r"^\s*Previous week\b[^:]*:", line, re.I)]
    previous_year = [evidence(number, line) for number, line in block
                     if re.match(r"^\s*Previous year\b[^:]*:", line, re.I)]
    current = five_row(nationals, zero_definition)
    coverage_lines = []
    for number, line in block:
        if line.strip().startswith("[These "):
            raw = line
            if "]" not in line and number < stop:
                raw += "\n" + lines[number]
            match = re.fullmatch(r"\[These (\d+) States planted (\d+)% of the (\d{4}) "
                                 r"(corn|soybean) acreage\]", re.sub(r"\s+", " ", raw.strip()), re.I)
            coverage_lines.append({**evidence(number, line), "raw_text": raw,
                                   "line_end": number + raw.count("\n"),
                                   "state_count": int(match[1]) if match else None,
                                   "acreage_coverage_percent": int(match[2]) if match else None,
                                   "acreage_year": int(match[3]) if match else None,
                                   "acreage_crop_literal": match[4] if match else None})
    coverage = {"status": "printed" if coverage_lines else "unknown:not_printed",
                "candidates": coverage_lines}
    if len(coverage_lines) == 1 and len(nationals) == 1:
        label = NATIONAL.match(nationals[0]["raw_line"])[1]
        state_match = re.fullmatch(r"(\d+) States", label, re.I)
        if (state_match and coverage_lines[0]["state_count"] is not None and
                int(state_match[1]) != coverage_lines[0]["state_count"]):
            reasons.append("coverage_aggregate_state_count_disagreement")
    reasons.extend("current:" + reason for reason in current["unknown_reasons"])
    return {"title": evidence(index + 1, lines[index]), "line_start": index + 1,
            "line_end": stop, "reference_week_date": reference,
            "reference_date_evidence": date_lines, "header_candidates": header_candidates,
            "current": current, "printed_previous_week": five_row(previous, zero_definition),
            "printed_previous_year": five_row(previous_year, zero_definition),
            "coverage": coverage, "unknown_reasons": reasons}


def parse_report(text, metadata_release_date, source):
    lines = text.splitlines()
    release = release_info(lines, metadata_release_date)
    rows = []
    for crop in CROPS:
        tables = []
        for index, line in enumerate(lines):
            match = TITLE.match(line)
            if match and ("Corn" if match[1].lower() == "corn" else "Soybeans") == crop:
                tables.append(parse_table(lines, index))
        reasons = list(release["unknown_reasons"])
        if len(tables) != 1:
            reasons.append("condition_table_missing" if not tables else "condition_table_not_unique")
        empty = five_row([], [])
        chosen = tables[0] if len(tables) == 1 else None
        if chosen:
            reasons.extend(chosen["unknown_reasons"])
            if (chosen["reference_week_date"] and release["body_release_date"] and
                    chosen["reference_week_date"] > release["body_release_date"]):
                reasons.append("reference_week_after_body_release")
        current = dict(chosen["current"] if chosen else empty)
        if reasons:
            current["status"] = "unknown"
            current["good_plus_excellent"] = None
        rows.append({"crop": crop, "metadata_release_date": metadata_release_date,
                     "body_release": release, "source": dict(source),
                     "reference_week_date": chosen["reference_week_date"] if chosen else None,
                     "current": current, "unknown_reasons": reasons,
                     "printed_previous_week": chosen["printed_previous_week"] if chosen else empty,
                     "printed_previous_year": chosen["printed_previous_year"] if chosen else empty,
                     "coverage": chosen["coverage"] if chosen else {"status": "unknown:no_unique_table", "candidates": []},
                     "table_candidates": tables, "historical_first_seen": "unknown"})
    return {"metadata_release_date": metadata_release_date, "source": dict(source),
            "body_release": release, "literal_policy_passages": policy_passages(lines), "rows": rows}


def link_adjacent(reports):
    """Use the immediately preceding original report, including missing reports."""
    groups = defaultdict(list)
    for report in reports:
        groups[report["metadata_release_date"]].append(report)
    previous_group = []
    for _, group in sorted(groups.items()):
        previous = previous_group[0] if len(previous_group) == 1 else None
        for report in group:
          for row in report["rows"]:
            reasons, gap, previous_row = [], None, None
            if len(group) != 1:
                reasons.append("ambiguous_current_release_order")
            if len(previous_group) > 1:
                reasons.append("ambiguous_previous_release_order")
            elif previous is None:
                reasons.append("no_previous_original_report")
            else:
                previous_row = next(item for item in previous["rows"] if item["crop"] == row["crop"])
                a, b = row["reference_week_date"], previous_row["reference_week_date"]
                if not a or not b:
                    reasons.append("one_or_both_reference_week_unknown")
                else:
                    da, db = date.fromisoformat(a), date.fromisoformat(b)
                    gap = (da - db).days
                    if da.year != db.year:
                        reasons.append("reference_year_boundary")
                    if gap != 7:
                        reasons.append("reference_gap_not_7_days")
                if previous_row["current"]["status"] != "known":
                    reasons.append("previous_original_current_unknown")
            if row["current"]["status"] != "known":
                reasons.append("current_original_current_unknown")
            value = None
            if not reasons:
                value = row["current"]["good_plus_excellent"] - previous_row["current"]["good_plus_excellent"]
            row["adjacent_change"] = {
                "status": "known" if not reasons else "unknown", "unknown_reasons": reasons,
                "value_pp": value, "reference_gap_days": gap,
                "previous_metadata_release_date": previous["metadata_release_date"] if previous else None,
                "previous_source": previous["source"] if previous else None,
                "previous_release_source_candidates": [item["source"] for item in previous_group],
                "previous_reference_week_date": previous_row["reference_week_date"] if previous_row else None,
                "previous_original_GE": previous_row["current"]["good_plus_excellent"] if previous_row else None,
                "same_report_previous_week_used_as_original": False}
            diagnostic_reasons = list(reasons)
            if row["printed_previous_week"]["status"] != "known":
                diagnostic_reasons.append("printed_previous_week_unknown")
            explicit_date = row["printed_previous_week"]["explicit_reference_date"]
            if (explicit_date and previous_row and
                    explicit_date != previous_row["reference_week_date"]):
                diagnostic_reasons.append("printed_previous_date_disagrees_with_previous_original_reference")
            diagnostic = {"status": "unknown" if diagnostic_reasons else "known",
                          "unknown_reasons": diagnostic_reasons, "five_categories_differ": None,
                          "printed_previous_minus_original_GE_pp": None}
            if not diagnostic_reasons:
                printed = row["printed_previous_week"]
                diagnostic["five_categories_differ"] = printed["five_categories"] != previous_row["current"]["five_categories"]
                diagnostic["printed_previous_minus_original_GE_pp"] = printed["good_plus_excellent"] - previous_row["current"]["good_plus_excellent"]
            row["revision_diagnostic"] = diagnostic
        previous_group = group


def distribution(values):
    if not values:
        return {"n": 0, "minimum": None, "maximum": None, "mean": None, "median": None, "frequency": {}}
    return {"n": len(values), "minimum": min(values), "maximum": max(values),
            "mean": statistics.mean(values), "median": statistics.median(values),
            "frequency": dict(sorted(Counter(values).items()))}


def summarize(reports, operations):
    rows = [row for report in reports for row in report["rows"]]
    by_year_crop = []
    for year, crop in sorted({(row["metadata_release_date"][:4], row["crop"]) for row in rows}):
        group = [row for row in rows if row["metadata_release_date"][:4] == year and row["crop"] == crop]
        by_year_crop.append({"metadata_release_year": int(year), "crop": crop, "total": len(group),
                             "known_current": sum(row["current"]["status"] == "known" for row in group),
                             "known_adjacent_change": sum(row["adjacent_change"]["status"] == "known" for row in group),
                             "unknown_current": sum(row["current"]["status"] != "known" for row in group)})
    missing = Counter(reason for row in rows for reason in row["unknown_reasons"])
    revision_counts = Counter()
    revision_examples = []
    for row in rows:
        diagnostic = row["revision_diagnostic"]
        revision_counts[diagnostic["status"]] += 1
        if diagnostic["status"] == "known":
            revision_counts["five_categories_differ" if diagnostic["five_categories_differ"] else "five_categories_same"] += 1
            if diagnostic["printed_previous_minus_original_GE_pp"] != 0:
                revision_counts["GE_differs"] += 1
            if diagnostic["five_categories_differ"] and len(revision_examples) < 12:
                revision_examples.append({"crop": row["crop"], "metadata_release_date": row["metadata_release_date"],
                                          "source": row["source"], "printed_previous_week": row["printed_previous_week"],
                                          "previous_source": row["adjacent_change"]["previous_source"],
                                          "diagnostic": diagnostic})
    return {"schema": "stage438_original_crop_condition_summary_v1", "source_only": True,
            "financial_authorized": False, "year_crop": by_year_crop,
            "report_count": len(reports), "crop_rows_including_missing": len(rows),
            "shared_releases": {"metadata_distinct_release_count": len({r["metadata_release_date"] for r in reports}),
                                "body_release_agrees_with_metadata": sum(r["body_release"]["status"] == "known" for r in reports),
                                "any_crop_known": sum(any(row["current"]["status"] == "known" for row in r["rows"]) for r in reports),
                                "both_crops_known": sum(all(row["current"]["status"] == "known" for row in r["rows"]) for r in reports),
                                "two_crops_are_not_independent_release_events": True},
            "known_current": sum(r["current"]["status"] == "known" for r in rows),
            "known_adjacent_change": sum(r["adjacent_change"]["status"] == "known" for r in rows),
            "crop_distributions": {
                crop: {"GE": distribution([r["current"]["good_plus_excellent"] for r in rows
                                             if r["crop"] == crop and r["current"]["status"] == "known"]),
                       "adjacent_original_GE_change_pp": distribution([r["adjacent_change"]["value_pp"] for r in rows
                                                                        if r["crop"] == crop and r["adjacent_change"]["status"] == "known"])}
                for crop in CROPS},
            "missing_or_conflicting_reasons": dict(sorted(missing.items())),
            "adjacent_unknown_reasons": dict(sorted(Counter(reason for r in rows for reason in r["adjacent_change"]["unknown_reasons"]).items())),
            "coverage_status_counts": dict(Counter(r["coverage"]["status"] for r in rows)),
            "revision_diagnostic_counts": dict(revision_counts), "revision_examples_earliest_max12": revision_examples,
            "metadata_release_weekdays": dict(Counter(date.fromisoformat(r["metadata_release_date"]).strftime("%A") for r in reports)),
            "reference_gap_counts_by_crop": {
                crop: dict(Counter(str(r["adjacent_change"]["reference_gap_days"]) for r in rows if r["crop"] == crop)) for crop in CROPS},
            "original_first_seen": {"status": "unknown", "reports": len(reports),
                                    "reason": "No archive/HTTP clock is a historical first-seen proof."},
            "operations": dict(operations)}


def checked_json(record):
    path = Path(record["path"])
    blob = path.read_bytes()
    if len(blob) != record["bytes"] or sha256(blob) != record["sha256"]:
        raise ValueError("input identity mismatch: " + str(path))
    return json.loads(blob)


def preflight(scope_path):
    blob = Path(scope_path).read_bytes()
    if sha256(blob) != SCOPE_SHA256:
        raise ValueError("scope SHA256 differs from frozen Stage437")
    scope = json.loads(blob)
    if scope["schema"] != "stage437_original_crop_condition_source_scope_v1":
        raise ValueError("scope schema mismatch")
    inputs = {name: checked_json(record) for name, record in scope["inputs"].items()}
    index = inputs["reports_index"]
    metadata = inputs["metadata_inventory"]
    reports = [r for r in index["reports"] if r["publication"] == "crop-progress"]
    expected = scope["population"]["expected_report_rows"]
    if expected != 309 or len(reports) != expected:
        raise ValueError("expected exactly 309 crop-progress metadata rows")
    meta = defaultdict(list)
    for row in metadata["reports"]:
        meta[(row["publication"], row["release_date"])].append(row)
    if inputs["harvest_manifest"]["report_rows"] != len(index["reports"]):
        raise ValueError("harvest/index count disagreement")
    raw_root = Path(scope["inputs"]["reports_index"]["path"]).parent / "raw_txt"
    seen_dates, seen_paths = Counter(), set()
    for report in reports:
        release = report["release_date"]
        if date.fromisoformat(release).isoformat() != release:
            raise ValueError("malformed Progress release date")
        seen_dates[release] += 1
        matches = [m for m in meta.get((report["publication"], release), [])
                   if m.get("txt_urls") == report["txt_urls"]]
        if len(matches) != 1:
            raise ValueError("metadata/index report identity disagreement")
        sources = report["original_sources"]
        if len(sources) != 1 or sources[0]["role"] != "txt" or not sources[0]["ok"]:
            raise ValueError("expected one successful original TXT source per report")
        source = sources[0]
        reused = (source.get("mode") == "reused_exact391_original_no_GET" and
                  source["body"]["sha256"] == source.get("original391_body", {}).get("sha256") and
                  source["body"]["bytes"] == source.get("original391_body", {}).get("bytes"))
        if source.get("status") != 200 and not reused:
            raise ValueError("original source lacks either HTTP200 or exact Stage391 reuse identity")
        body = sources[0]["body"]
        path = Path(body["path"])
        if (path.parent != raw_root or path in seen_paths or not isinstance(body["bytes"], int)
                or body["bytes"] <= 0 or not re.fullmatch(r"[0-9a-f]{64}", body["sha256"])):
            raise ValueError("original body locator schema or uniqueness mismatch")
        seen_paths.add(path)
    return scope, sorted(reports, key=lambda r: r["release_date"]), {
        "schema": "stage438_metadata_preflight_v1", "scope_sha256": SCOPE_SHA256,
        "all_index_rows": len(index["reports"]), "crop_progress_rows": len(reports),
        "duplicate_release_date_counts": {day: count for day, count in seen_dates.items() if count > 1},
        "original_source_schema_counts": dict(Counter(r["original_sources"][0].get("mode", "HTTP200") for r in reports)),
        "unique_body_locators": len(seen_paths), "raw_body_reads": 0,
        "script": identity(__file__, Path(__file__).read_bytes()),
        "input_identities": scope["inputs"], "financial_authorized": False}


def authorize(path, out, script_identity):
    blob = Path(path).read_bytes()
    authorization = json.loads(blob)
    required = {"schema": "stage438_crop_condition_extract_authorization_v1", "authorized": True,
                "authorized_by": "root", "scope_sha256": SCOPE_SHA256,
                "script_sha256": script_identity["sha256"], "output_dir": str(Path(out).resolve()),
                "max_original_body_reads": 309, "one_actual_run": True, "financial_authorized": False}
    for key, value in required.items():
        if type(authorization.get(key)) is not type(value) or authorization.get(key) != value:
            raise ValueError("authorization mismatch: " + key)
    return identity(path, blob)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def now():
    return datetime.now(timezone.utc).isoformat()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--authorization")
    parser.add_argument("--out", required=True)
    parser.add_argument("--preflight", action="store_true", help="metadata/schema only; never opens raw TXT")
    args = parser.parse_args(argv)
    if not args.preflight and not args.authorization:
        parser.error("actual requires --authorization; use --preflight for metadata-only checks")
    scope, source_reports, preflight_result = preflight(args.scope)
    out = Path(args.out).resolve()
    if args.preflight:
        out.mkdir(parents=True, exist_ok=False)
        write_json(out / "preflight.json", preflight_result)
        print(json.dumps({"status": "metadata_preflight_complete", "raw_body_reads": 0,
                          "crop_progress_rows": len(source_reports), "out": str(out)}))
        return 0
    auth_identity = authorize(args.authorization, out, preflight_result["script"])
    out.mkdir(parents=True, exist_ok=False)
    operations = {"actual_starts": 1, "actual_terminals": 0, "original_body_reads": 0,
                  "original_body_unique_reads": 0, "same_read_SHA_size_validations": 0,
                  "HTTP": 0, "market_API": 0, "SQL": 0, "price_Y_score_reads": 0,
                  "fit": 0, "cash": 0, "future_D": 0, "original_body_writes": 0}
    start = {"schema": "stage438_crop_condition_start_v1", "started_at": now(),
             "scope_sha256": SCOPE_SHA256, "script": preflight_result["script"],
             "authorization": auth_identity, "out": str(out), "operations": dict(operations)}
    write_json(out / "startup.json", start)
    status, error, reports, paths = "failed", None, [], set()
    try:
        for report in source_reports:
            body = report["original_sources"][0]["body"]
            path = Path(body["path"])
            if path in paths or operations["original_body_reads"] >= 309:
                raise ValueError("original read budget/uniqueness violated")
            paths.add(path)
            operations["original_body_reads"] += 1
            operations["original_body_unique_reads"] = len(paths)
            raw = path.read_bytes()  # The only actual raw-body read; hash these same bytes.
            observed = identity(path, raw)
            if observed["bytes"] != body["bytes"] or observed["sha256"] != body["sha256"]:
                raise ValueError("original body SHA256/size mismatch: " + str(path))
            operations["same_read_SHA_size_validations"] += 1
            extracted = parse_report(raw.decode("utf-8-sig", errors="strict"), report["release_date"], observed)
            extracted["original_url"] = report["original_sources"][0]["url"]
            extracted["original_source_metadata"] = {key: value for key, value in report["original_sources"][0].items()
                                                     if key not in ("headers",)}
            reports.append(extracted)
        if len(reports) != 309:
            raise ValueError("incomplete original report projection")
        link_adjacent(reports)
        if identity(__file__, Path(__file__).read_bytes()) != preflight_result["script"]:
            raise ValueError("script changed during actual execution")
        operations["actual_terminals"] = 1
        write_json(out / "reports.json", {"schema": "stage438_original_crop_condition_reports_v1",
                                          "scope_sha256": SCOPE_SHA256, "reports": reports})
        with (out / "crop_rows.jsonl").open("x", encoding="utf-8") as stream:
            for report in reports:
                for row in report["rows"]:
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        write_json(out / "summary.json", summarize(reports, operations))
        write_json(out / "preflight.json", preflight_result)
        status = "complete"
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        operations["actual_terminals"] = 1
        # Keep the successfully projected prefix on error; never resume or reread automatically.
        write_json(out / "partial_reports.json", {"reports": reports, "error": error})
    terminal = {"schema": "stage438_crop_condition_terminal_v1", "ended_at": now(),
                "status": status, "error": error, "scope_sha256": SCOPE_SHA256,
                "script": preflight_result["script"], "authorization": auth_identity,
                "operations": operations}
    write_json(out / "terminal.json", terminal)
    print(json.dumps({"status": status, "error": error, "operations": operations, "out": str(out)}))
    return 0 if status == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
