"""Offline, evidence-preserving parser for original USDA report TXT bodies.

No acquisition, financial logic, current revised data, or implied first-seen clock.
Unknown report/table schemas return explicit unknown values instead of guessing.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

SCHEMA = "stage401_original_crop_report_parse_v1"
_MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
_RELEASE = re.compile(rf"\bReleased\s+({_MONTH}\s+\d{{1,2}},?\s+\d{{4}})", re.I)
_NUMERIC = re.compile(r"[+-]?(?:\d[\d,]*)(?:\.\d+)?\Z")
_MISSING = {"(NA)": "not_available", "(D)": "withheld", "(X)": "not_applicable", "(Z)": "less_than_half_unit", "NA": "not_available"}


def _json_safe(value: Any) -> Any:
    # Metadata is copied; no hidden caller mutation or non-JSON date object.
    return json.loads(json.dumps(value, ensure_ascii=False, default=str, allow_nan=False))


def _raw(lines: list[str], start: int, end: int) -> list[dict]:
    return [{"line_number": i + 1, "raw_line": lines[i]} for i in range(max(0, start), min(len(lines), end))]


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _named_date(value: str) -> date | None:
    value = re.sub(r"\s+", " ", value.strip()).replace(",", "")
    for fmt in ("%B %d %Y", "%b %d %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


def _label(value: str) -> str:
    value = re.sub(r"\.+.*$", "", value).strip()
    value = re.sub(r"(?:\s+\d+/)+\s*$", "", value).strip()
    return re.sub(r"\s+", " ", value)


def _cell(token: str, dash_zero: bool, integer: bool = False) -> dict:
    result = {"token": token, "value": None, "status": "unknown_token"}
    if token in _MISSING:
        result["status"] = _MISSING[token]
    elif token == "-":
        result.update(value=0 if dash_zero else None,
                      status="explicit_reported_zero" if dash_zero else "dash_meaning_unknown")
    elif _NUMERIC.fullmatch(token):
        try:
            number = Decimal(token.replace(",", ""))
        except InvalidOperation:
            return result
        if integer and number != number.to_integral_value():
            result["status"] = "noninteger_production_unknown"
        else:
            result.update(value=int(number) if number == number.to_integral_value() else float(number), status="reported_number")
    return result


def _rows(lines: list[str], first: int, last: int, dash_zero: bool) -> list[dict]:
    result = []
    for i in range(first, last):
        line = lines[i]
        if ":" not in line:
            continue
        left, right = line.split(":", 1)
        # Dot leaders distinguish actual state/aggregate rows from table headers.
        if not re.search(r"\.", left) or not re.match(r"\s*(?:[A-Za-z]|\d+\s+States)", left):
            continue
        tokens = right.split()
        if not tokens:
            continue
        state = _label(left)
        result.append({"state": state, "line_number": i + 1, "raw_line": line,
                       "tokens": tokens, "cells": [_cell(x, dash_zero) for x in tokens]})
        if state == "United States" or re.fullmatch(r"\d+ States", state):
            break
    return result


def _release(lines: list[str], metadata: dict) -> dict:
    occurrences = []
    # Released body label can wrap, but later narrative dates are not release labels.
    for i, line in enumerate(lines):
        if not re.search(r"\bReleased\b", line, re.I):
            continue
        joined = " ".join(x.strip() for x in lines[i:i + 3])
        match = _RELEASE.search(joined)
        if match:
            parsed = _named_date(match.group(1))
            occurrences.append({"line_number": i + 1, "raw_lines": _raw(lines, i, i + 3),
                                "matched_label": match.group(0), "date": parsed.isoformat() if parsed else None})
    dates = sorted({x["date"] for x in occurrences if x["date"]})
    stated = []
    for i, line in enumerate(lines):
        if (re.search(r"(?:\breleased?\b|\brelease\b|\brevision policy\b)", line, re.I)
                and re.search(r"(?:\d{1,2}:\d{2}|\b[ap]\.?m\.?\b|business day)", " ".join(lines[i:i + 3]), re.I)):
            stated.append({"line_number": i + 1, "raw_lines": _raw(lines, i, i + 4)})
    expected = metadata.get("release_date")
    actual = dates[0] if len(dates) == 1 else None
    return {"metadata_release_date": expected, "body_released_labels": occurrences,
            "body_release_date": actual,
            "body_metadata_date_match": actual == expected if actual and expected else None,
            "body_release_date_status": "one_explicit_body_date" if len(dates) == 1 else "unknown_or_conflicting",
            "stated_time_passages": stated,
            "actual_historical_first_seen": None, "strict_historical_first_seen_verified": False,
            "archive_timestamp_is_site_metadata_only": True,
            "clock_note": "Archive 12 UTC and present HTTP timestamps are not historical availability; retain literal body policy, no Monday/timezone/availability upper bound inferred."}


def _progress_table(lines: list[str], title: str, release_date: date | None, dash_zero: bool) -> dict:
    hits = [i for i, line in enumerate(lines) if line.strip() == title]
    base = {"present": bool(hits), "title": title, "status": "missing_table" if not hits else "unknown_schema",
            "current_column_zero_based": None, "current_reference_date": None,
            "reference_date_is_sunday": None, "unit": "percent", "rows": [], "unknown_reasons": []}
    if not hits:
        base["unknown_reasons"].append("table_not_present_in_original_report")
        return base
    if len(hits) != 1:
        base.update(heading_occurrences=_raw(lines, hits[0], hits[0] + 1),
                    unknown_reasons=["multiple_exact_table_headings_not_disambiguated"])
        return base
    start = hits[0]
    limit = min(len(lines), start + 100)
    for i in range(start + 1, limit):
        if re.match(r"^[A-Z][^:]* - Selected States(?:\s*:.*)?$", lines[i].strip()):
            limit = i
            break
    rows = _rows(lines, start + 1, limit, dash_zero)
    end = rows[-1]["line_number"] if rows else limit
    # Include trailing border and footnotes, stop at the next substantive title.
    tail = end
    while tail < limit and (not lines[tail].strip() or re.match(r"^[-(\d]", lines[tail].strip())):
        tail += 1
    base.update(heading_line_number=start + 1, raw_header_lines=_raw(lines, start, rows[0]["line_number"] - 1 if rows else limit),
                raw_table_lines=_raw(lines, start, tail), rows=rows)
    schema = None
    for i in range(start + 1, min(limit - 1, start + 15)):
        parts = lines[i].split(":")
        if len(parts) != 5 or parts[0].strip().lower() != "state":
            continue
        date_cells = [x.strip() for x in parts[1:]]
        year_parts = lines[i + 1].split(":")
        if len(year_parts) != 5:
            continue
        year_cells = [x.strip() for x in year_parts[1:]]
        years = [re.fullmatch(r"(?:19|20)\d{2}", x) for x in year_cells[:3]]
        if not all(years) or not re.search(r"Average", year_cells[3], re.I):
            continue
        dates = [_named_date(f"{date_cells[k]} {year_cells[k]}") for k in range(3)]
        if not all(dates):
            continue
        if release_date is None or [int(x) for x in year_cells[:3]] != [release_date.year - 1, release_date.year, release_date.year]:
            continue
        # Current is explicitly the third dated column, not an assumed last column.
        if dates[2] > release_date or dates[2].weekday() != 6 or dates[1] >= dates[2]:
            continue
        schema = {"date_header_line_number": i + 1, "year_header_line_number": i + 2,
                  "date_cells": date_cells, "year_cells": year_cells,
                  "dated_columns": [x.isoformat() for x in dates], "average_raw": [date_cells[3], year_cells[3]]}
        break
    if schema is None:
        base["unknown_reasons"].append("four_column_current_week_date_year_schema_not_confirmed")
    else:
        base.update(current_column_zero_based=2, current_reference_date=schema["dated_columns"][2],
                    reference_date_is_sunday=True, column_schema=schema)
    for row in rows:
        cell = _cell(row["tokens"][2], dash_zero) if schema and len(row["tokens"]) == 4 else {"token": None, "value": None, "status": "column_schema_unknown"}
        row.update(cell, current_column_zero_based=2 if schema else None, unit="percent")
        if cell["value"] is not None and not 0 <= cell["value"] <= 100:
            row.update(value=None, status="outside_percent_range_unknown")
    if not rows:
        base["unknown_reasons"].append("no_original_state_rows")
    elif not re.fullmatch(r"\d+ States|United States", rows[-1]["state"]):
        base["unknown_reasons"].append("aggregate_row_not_found")
    if len({r["state"] for r in rows}) != len(rows):
        base["unknown_reasons"].append("duplicate_original_state_labels")
    if any(len(r["tokens"]) != 4 for r in rows):
        base["unknown_reasons"].append("row_column_count_not_four")
    if schema and not base["unknown_reasons"]:
        base["status"] = "parsed_original_schema"
    return base


def _annual_table(lines: list[str], release_date: date | None, dash_zero: bool) -> dict:
    target_year = release_date.year - 1 if release_date else None
    base = {"present": False, "status": "missing_table", "production_year": target_year,
            "unit": "1000 bushels", "production_column_zero_based": None, "year_columns": None,
            "rows": [], "unknown_reasons": []}
    candidates = []
    for i, line in enumerate(lines):
        if not line.startswith("Soybeans for Beans Area Planted and Harvested, Yield, and Production"):
            continue
        # The contents page is not a data table; require the nearby real header.
        for h in range(i + 1, min(i + 13, len(lines))):
            if "Yield per acre" in lines[h] and "Production" in lines[h]:
                candidates.append((i, h))
                break
    if not candidates:
        base["unknown_reasons"].append("soybean_yield_and_production_table_not_present")
        return base
    base["present"] = True
    base["status"] = "unknown_schema"
    if len(candidates) != 1:
        base["unknown_reasons"].append("multiple_soybean_yield_production_tables_not_disambiguated")
        base["candidate_heading_line_numbers"] = [x[0] + 1 for x in candidates]
        return base
    start, header = candidates[0]
    limit = min(len(lines), header + 120)
    rows = _rows(lines, header + 1, limit, dash_zero)
    end = rows[-1]["line_number"] if rows else min(limit, header + 10)
    tail = end
    while tail < limit and (not lines[tail].strip() or re.match(r"^[-(\d]", lines[tail].strip())):
        tail += 1
    base.update(heading_line_number=start + 1, raw_header_lines=_raw(lines, start, rows[0]["line_number"] - 1 if rows else end),
                raw_table_lines=_raw(lines, start, tail), rows=rows)
    year_line = None
    for i in range(header + 1, min(header + 7, len(lines))):
        years = re.findall(r"\b(?:19|20)\d{2}\b", lines[i])
        if len(years) == 6:
            year_line = i
            break
    if year_line is None:
        base["unknown_reasons"].append("six_original_year_columns_not_found")
    else:
        years = [int(x) for x in re.findall(r"\b(?:19|20)\d{2}\b", lines[year_line])]
        groups = [x.strip() for x in lines[header].split(":")[1:]]
        unit_raw = " ".join(lines[year_line + 1:min(year_line + 5, len(lines))])
        base.update(year_columns=years, year_header_line_number=year_line + 1, group_headers=groups,
                    original_unit_lines=_raw(lines, year_line + 1, min(year_line + 5, len(lines))))
        if (len(groups) == 2 and "Yield per acre" in groups[0] and "Production" in groups[1]
                and years[:3] == years[3:] and len(set(years[:3])) == 3
                and target_year in years[3:] and "1,000 bushels" in unit_raw):
            base["production_column_zero_based"] = 3 + years[3:].index(target_year)
        else:
            base["unknown_reasons"].append("original_year_group_or_1000_bushels_unit_binding_not_confirmed")
    column = base["production_column_zero_based"]
    for row in rows:
        cell = _cell(row["tokens"][column], dash_zero, integer=True) if column is not None and len(row["tokens"]) == 6 else {"token": None, "value": None, "status": "column_schema_unknown"}
        row.update(cell, production_column_zero_based=column, production_year=target_year, unit="1000 bushels")
        if cell["value"] is not None and cell["value"] < 0:
            row.update(value=None, status="negative_production_unknown")
    if not rows or rows[-1]["state"] != "United States":
        base["unknown_reasons"].append("original_us_aggregate_not_found")
    if len({r["state"] for r in rows}) != len(rows):
        base["unknown_reasons"].append("duplicate_original_state_labels")
    if any(len(r["tokens"]) != 6 for r in rows):
        base["unknown_reasons"].append("row_column_count_not_six")
    if column is not None and not base["unknown_reasons"]:
        base["status"] = "parsed_original_schema"
    return base


def parse_report(raw_bytes: bytes, metadata: dict) -> dict:
    """Parse one complete original TXT; all returned fields are JSON safe.

    metadata publication is crop-progress or crop-production-annual-summary;
    release_date is the exact observed archive date, including rescheduled dates.
    Calling this function neither writes files nor accesses network/environment.
    """
    if not isinstance(raw_bytes, bytes) or not isinstance(metadata, dict):
        raise TypeError("parse_report requires raw bytes and metadata dict")
    try:
        text = raw_bytes.decode("utf-8-sig")
        encoding = "utf-8-sig" if raw_bytes.startswith(b"\xef\xbb\xbf") else "utf-8"
    except UnicodeDecodeError:
        text = raw_bytes.decode("cp1252", errors="surrogateescape")
        encoding = "cp1252-with-lossless-surrogateescape"
    lines = text.splitlines()
    release = _release(lines, metadata)
    release_date = _date(release["body_release_date"] or metadata.get("release_date"))
    release["table_schema_release_date_source"] = (
        "explicit_body_Released_label" if release["body_release_date"] else
        "observed_archive_release_date_label_only_body_has_no_full_Released_date")
    # A body/archive disagreement is preserved, never silently resolved.
    if release["body_metadata_date_match"] is False:
        release_date = None
    zero_lines = [i for i, line in enumerate(lines) if re.fullmatch(r"\s*-\s+Represents zero\.\s*", line, re.I)]
    tables = {}
    publication = metadata.get("publication")
    if publication == "crop-progress":
        tables = {"soybeans_setting_pods": _progress_table(lines, "Soybeans Setting Pods - Selected States", release_date, bool(zero_lines)),
                  "soybeans_dropping_leaves": _progress_table(lines, "Soybeans Dropping Leaves - Selected States", release_date, bool(zero_lines))}
    elif publication == "crop-production-annual-summary":
        tables = {"soybeans_production": _annual_table(lines, release_date, bool(zero_lines))}
    result = {"schema": SCHEMA, "source": _json_safe(metadata), "publication": publication,
              "raw": {"bytes": len(raw_bytes), "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                      "encoding": encoding, "line_count": len(lines), "original_header_lines": _raw(lines, 0, min(40, len(lines)))},
              "release": release, "tables": tables,
              "explicit_dash_zero_footnotes": [_raw(lines, i, i + 1)[0] for i in zero_lines],
              "status": "parsed_with_explicit_unknowns" if tables else "unsupported_publication_unknown",
              "no_unknown_zero_fill": True,
              "limitations": ["Only exact original soybean table schemas are interpreted; other report text remains in original raw body.",
                              "No financial meaning, exposure weights, crop locations, or historical first-seen clock inferred.",
                              "Reported N/A, D, X, Z and unrecognized cells remain unknown; only explicit same-report dash=zero permits zero."]}
    # Catch accidental non-JSON output without introducing data substitutions.
    json.dumps(result, ensure_ascii=True, allow_nan=False)
    return result
