"""Offline original Disaggregated Futures Only ZIP parser for Stage407.

All original rows retain identity provenance. Only the eight protocol mappings
receive PMPU/MM ratios; no release-time, Tuesday, vintage, or alpha inference.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

MAX_UNCOMPRESSED = 128 * 1024 * 1024
FIXED_MAPPING = {"SHFE.AU": "088691", "SHFE.AG": "084691", "SHFE.CU": "085692", "DCE.M": "026603",
                 "DCE.Y": "007601", "DCE.C": "002602", "CZCE.CF": "033661", "CZCE.SR": "080732"}
FIELDS = {
    "market_code": ["CFTC_Contract_Market_Code"],
    "market_name": ["Market_and_Exchange_Names"],
    "asof_yymmdd": ["As_of_Date_In_Form_YYMMDD"],
    "report_date": ["Report_Date_as_YYYY-MM-DD", "Report_Date_as_MM_DD_YYYY"],
    "pmpu_long": ["Prod_Merc_Positions_Long_All"],
    "pmpu_short": ["Prod_Merc_Positions_Short_All"],
    "mm_long": ["M_Money_Positions_Long_All"],
    "mm_short": ["M_Money_Positions_Short_All"],
    "open_interest": ["Open_Interest_All"],
}
EXTRA_IDENTITIES = ["CFTC_Market_Code", "CFTC_Region_Code", "CFTC_Commodity_Code", "CFTC_SubGroup_Code",
                    "CFTC_Contract_Market_Code", "Contract_Units", "FutOnly_or_Combined"]


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def _binding(path: Path) -> dict:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": h.hexdigest()}


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lstrip("\ufeff").strip().lower()).strip("_")


def _columns(header: list[str]) -> tuple[dict, dict]:
    positions = defaultdict(list)
    for i, name in enumerate(header):
        positions[_key(name)].append(i)
    selected = {}
    audit = {}
    for role, aliases in FIELDS.items():
        hits = sorted({i for name in aliases for i in positions.get(_key(name), [])})
        selected[role] = hits[0] if len(hits) == 1 else None
        audit[role] = {"index_zero_based": selected[role], "actual_header": header[hits[0]] if len(hits) == 1 else None,
                       "status": "exact_named_field" if len(hits) == 1 else "missing_or_ambiguous", "candidate_indices": hits}
    return selected, audit


def _token(row: list[str], index: int | None) -> str | None:
    return row[index] if index is not None and index < len(row) else None


def _number(token: str | None) -> dict:
    value = None
    status = "missing_numeric"
    if token is not None and re.fullmatch(r"[+-]?\d[\d,]*(?:\.0+)?", token.strip()):
        try:
            number = Decimal(token.strip().replace(",", ""))
            if number < 0:
                status = "negative_position_unknown"
            elif number == number.to_integral_value():
                value, status = int(number), "reported_integer"
        except InvalidOperation:
            pass
    return {"token": token, "value": value, "status": status}


def _date_token(token: str | None, role: str) -> dict:
    result = {"token": token, "date": None, "format": None, "status": "missing_date"}
    if token is None or not token.strip():
        return result
    text = token.strip()
    formats = ["%y%m%d"] if role == "asof_yymmdd" else ["%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        # The raw YYMMDD field must actually have all six literal digits.
        if role == "asof_yymmdd" and not re.fullmatch(r"\d{6}", text):
            continue
        result.update(date=parsed.isoformat(), format=fmt, status="explicit_parsed_date")
        return result
    result["status"] = "unrecognized_date_unknown"
    return result


def _dates(tokens: dict) -> dict:
    values = {role: _date_token(tokens.get(role), role) for role in ("asof_yymmdd", "report_date")}
    known = {x["date"] for x in values.values() if x["date"]}
    invalid = any(x["status"] == "unrecognized_date_unknown" for x in values.values())
    if invalid:
        status, chosen = "present_date_unparseable_unknown", None
    elif len(known) > 1:
        status, chosen = "conflicting_original_dates_unknown", None
    elif len(known) == 1:
        status, chosen = "explicit_original_asof_date", next(iter(known))
    else:
        status, chosen = "missing_dates_unknown", None
    return {"date": chosen, "status": status, "original_fields": values,
            "weekday": datetime.fromisoformat(chosen).weekday() if chosen else None,
            "is_publication_timestamp": False}


def _write_lines(path: Path, values: list[dict]) -> None:
    with path.open("x", encoding="utf-8") as handle:
        for value in values:
            handle.write(_canonical(value).decode("ascii") + "\n")


def parse_year(zip_path, year, mapping, output_dir) -> dict:
    """Parse one retained ZIP once; write identities/mapped/schema files.

    The caller owns acquisition, cross-year duplicates, publication evidence,
    broad-universe joins, and later source qualification. Existing outputs refuse
    replacement. ZIP bytes and all market rows are never survivor-filtered.
    """
    zip_path, output_dir, year = Path(zip_path), Path(output_dir), int(year)
    if mapping != FIXED_MAPPING:
        raise ValueError("Only the fixed Stage407 eight-channel protocol mapping is authorized")
    output_dir.mkdir(parents=True, exist_ok=True)
    destinations = {name: output_dir / f"{name}_{year}.{ext}" for name, ext in
                    [("identities", "jsonl"), ("mapped", "jsonl"), ("schema", "json")]}
    if any(x.exists() for x in destinations.values()):
        raise FileExistsError("Year outputs already exist; do not replace original parse")
    source = _binding(zip_path)
    reverse = {code: channel for channel, code in mapping.items()}
    identities, mapped, member_audits = [], [], []
    duplicates = defaultdict(list)
    all_names = defaultdict(set)
    count_by_code = Counter()
    declared_total = 0
    actual_text_total = 0
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        declared_total = sum(x.file_size for x in members)
        if declared_total > MAX_UNCOMPRESSED:
            raise ValueError("Declared year uncompressed size exceeds128MiB")
        for member in members:
            if member.is_dir():
                continue
            audit = {"member": member.filename, "uncompressed_bytes": member.file_size,
                     "compressed_bytes": member.compress_size, "crc32": f"{member.CRC:08x}",
                     "status": "not_text_member_not_interpreted", "rows": 0, "crc_verified": False}
            member_audits.append(audit)
            if not member.filename.lower().endswith((".txt", ".csv")):
                # Stream even unrecognized members to validate their stored CRC.
                with archive.open(member) as handle:
                    for _ in iter(lambda: handle.read(1024 * 1024), b""):
                        pass
                audit["crc_verified"] = True
                continue
            with archive.open(member) as raw:
                buffered = io.BufferedReader(raw)
                encoding = "utf-8-sig" if buffered.peek(3).startswith(b"\xef\xbb\xbf") else "cp1252"
                text = io.TextIOWrapper(buffered, encoding=encoding, errors="surrogateescape", newline="")
                reader = csv.reader(text)
                header = None
                for candidate in reader:
                    if candidate and any(x.strip() for x in candidate):
                        header = candidate
                        break
                if header is None:
                    audit.update(status="empty_text_member", crc_verified=True, encoding=encoding)
                    continue
                indices, fields = _columns(header)
                audit.update(status="parsed_with_explicit_unknowns", original_header=header,
                             header_line_number=reader.line_num, fields=fields, encoding=encoding)
                extra = [(i, name) for i, name in enumerate(header) if _key(name) in {_key(x) for x in EXTRA_IDENTITIES}]
                previous_line = reader.line_num
                for tokens in reader:
                    start_line, end_line = previous_line + 1, reader.line_num
                    previous_line = end_line
                    if not tokens or not any(x.strip() for x in tokens):
                        continue
                    selected = {role: _token(tokens, index) for role, index in indices.items()}
                    code_token = selected["market_code"]
                    code = code_token.strip() if code_token is not None else None
                    name_token = selected["market_name"]
                    dates = _dates(selected)
                    raw_hash = hashlib.sha256(_canonical(tokens)).hexdigest()
                    identity = {"source_zip": source, "year_tag": year, "member": member.filename,
                                "line_number": start_line, "last_line_number": end_line,
                                "market_code": code, "market_code_token": code_token,
                                "market_name": name_token, "original_date_tokens": {k: selected[k] for k in ("asof_yymmdd", "report_date")},
                                "asof": dates, "extra_identity_tokens": {name: _token(tokens, i) for i, name in extra},
                                "original_column_count": len(tokens), "original_row_tokens_sha256": raw_hash,
                                "header_column_count": len(header), "row_shape_matches_header": len(tokens) == len(header)}
                    identities.append(identity)
                    audit["rows"] += 1
                    all_names[code].add(name_token)
                    count_by_code[code] += 1
                    date_key = dates["date"] or "unknown:" + json.dumps(identity["original_date_tokens"], sort_keys=True)
                    duplicates[(code, date_key)].append((identity, raw_hash))
                    if code not in reverse:
                        continue
                    numbers = {role: _number(selected[role]) for role in ("pmpu_long", "pmpu_short", "mm_long", "mm_short", "open_interest")}
                    oi = numbers["open_interest"]["value"]
                    reasons = []
                    if dates["date"] is None:
                        reasons.append(dates["status"])
                    if len(tokens) != len(header):
                        reasons.append("row_column_count_differs_from_header")
                    if any(indices[x] is None for x in ("market_code", "market_name", "pmpu_long", "pmpu_short", "mm_long", "mm_short", "open_interest")):
                        reasons.append("required_exact_named_field_missing_or_ambiguous")
                    if oi is None or oi <= 0:
                        reasons.append("open_interest_missing_or_nonpositive")
                    eligible = not reasons
                    p_long, p_short = (numbers[x]["value"] for x in ("pmpu_long", "pmpu_short"))
                    m_long, m_short = (numbers[x]["value"] for x in ("mm_long", "mm_short"))
                    H = (p_short - p_long) / oi if eligible and p_long is not None and p_short is not None else None
                    MM = (m_long - m_short) / oi if eligible and m_long is not None and m_short is not None else None
                    if p_long is None or p_short is None:
                        reasons.append("pmpu_position_missing_or_negative")
                    if m_long is None or m_short is None:
                        reasons.append("mm_position_missing_or_negative")
                    mapped.append({**identity, "channel": reverse[code], "original_numeric_fields": numbers,
                                   "H": H, "MM": MM, "H_numerator_short_minus_long": p_short - p_long if p_short is not None and p_long is not None else None,
                                   "MM_numerator_long_minus_short": m_long - m_short if m_long is not None and m_short is not None else None,
                                   "ratio_denominator_OI": oi, "unknown_reasons": reasons,
                                   "status": "known_ratios" if H is not None and MM is not None else "explicit_unknown",
                                   "within_year_duplicate_count": 1, "within_year_conflicting_duplicate": False})
                # Consuming to EOF verifies zipfile CRC, including final CSV bytes.
                audit["crc_verified"] = True
                actual_text_total += member.file_size
    mapped_by_provenance = {(r["member"], r["line_number"]): r for r in mapped}
    duplicate_groups, conflicting_groups = 0, 0
    for (code, date_key), entries in duplicates.items():
        if len(entries) < 2:
            continue
        duplicate_groups += 1
        conflict = len({row_hash for _, row_hash in entries}) > 1
        conflicting_groups += int(conflict)
        for identity, _ in entries:
            identity.update(within_year_duplicate_count=len(entries), within_year_conflicting_duplicate=conflict)
            record = mapped_by_provenance.get((identity["member"], identity["line_number"]))
            if record is not None:
                record.update(within_year_duplicate_count=len(entries), within_year_conflicting_duplicate=conflict)
                if conflict:
                    record.update(H=None, MM=None, status="explicit_unknown_conflicting_duplicate")
                    record["unknown_reasons"].append("same_year_same_code_date_original_rows_conflict")
    _write_lines(destinations["identities"], identities)
    _write_lines(destinations["mapped"], mapped)
    schema = {"schema": "stage407_original_cot_year_parse_v1", "year": year, "source_zip": source,
              "parser_source": _binding(Path(__file__)), "mapping": mapping, "members": member_audits,
              "declared_uncompressed_bytes": declared_total, "parsed_text_uncompressed_bytes": actual_text_total,
              "uncompressed_limit": MAX_UNCOMPRESSED, "all_member_CRC_verified": all(x["crc_verified"] for x in member_audits),
              "identity_rows": len(identities), "mapped_rows": len(mapped),
              "mapped_known_both_ratios": sum(r["H"] is not None and r["MM"] is not None for r in mapped),
              "all_historical_market_count": len(count_by_code),
              "all_market_names_and_row_counts": [{"market_code": code, "names": sorted(names, key=lambda x: str(x)), "row_count": count_by_code[code]}
                                                   for code, names in sorted(all_names.items(), key=lambda x: str(x[0]))],
              "within_year_duplicate_groups": duplicate_groups, "within_year_conflicting_duplicate_groups": conflicting_groups,
              "date_unknown_rows": sum(r["asof"]["date"] is None for r in identities),
              "asof_weekday_counts": dict(Counter(str(r["asof"]["weekday"]) for r in identities)),
              "channel_counts": {c: {"rows": sum(r["channel"] == c for r in mapped),
                                       "known_both": sum(r["channel"] == c and r["H"] is not None and r["MM"] is not None for r in mapped)} for c in mapping},
              "no_survivor_filter": True, "cross_year_duplicate_resolution": "not_performed_parent_responsibility",
              "first_seen_or_release_clock_inferred": False, "ratios_are_not_alpha_qualification": True,
              "execution_counts": {"network": 0, "Y_reads": 0, "training": 0, "cash_backtests": 0, "market_API": 0, "SQL": 0}}
    with destinations["schema"].open("x", encoding="utf-8") as handle:
        json.dump(schema, handle, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")
    return {"schema": schema["schema"], "year": year, "source_zip": source,
            "identity_rows": schema["identity_rows"], "mapped_rows": schema["mapped_rows"],
            "mapped_known_both_ratios": schema["mapped_known_both_ratios"],
            "within_year_duplicate_groups": duplicate_groups, "within_year_conflicting_duplicate_groups": conflicting_groups,
            "all_member_CRC_verified": schema["all_member_CRC_verified"],
            "outputs": {name: _binding(path) for name, path in destinations.items()}}
