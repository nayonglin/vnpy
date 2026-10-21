"""Acquire exactly one declared 2010 county CSV member; never a whole ZIP."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import struct
import urllib.error
import urllib.request
import zlib

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/stage395_fixed2010_county_source"
OUT = BASE / "actual_run1"
PROTOCOL_SHA = "d9315f65ddd7ef7d801f9f491751f509b00b836984b8d3b11232b7693a5456ce"


def now():
    return datetime.now(timezone.utc).isoformat()


def binding(path):
    data = Path(path).read_bytes()
    return {"path": str(Path(path).resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def acquire():
    protocol_path = BASE / "protocol.json"
    if binding(protocol_path)["sha256"] != PROTOCOL_SHA:
        raise ValueError("Root frozen protocol changed")
    protocol = json.loads(protocol_path.read_text())
    if OUT.exists():
        raise FileExistsError("One original request only; output cannot be reused")
    OUT.mkdir()
    prior_path = ROOT / "outputs/stage393_fixed2010_spatial_source_path/actual_run1/receipt.json"
    prior = json.loads(prior_path.read_text())
    tail_request = prior["requests"][3]
    old_headers = {k.lower(): v for k, v in tail_request["response_headers"]}
    etag = old_headers.get("etag")
    if not etag:
        raise ValueError("393 declared archive ETag missing")
    source = protocol["source"]
    receipt = {"schema": "stage395_single2010_member_acquisition_v1", "started_at": now(), "status": "running",
               "protocol_binding": binding(protocol_path), "source_393_receipt_binding": binding(prior_path),
               "url": source["exact_zip_url"], "method": "GET", "Range": source["single_member_envelope_inclusive_range"],
               "If-Match": etag, "HTTP_attempts": 0, "automatic_retries": 0, "redirects": 0,
               "financial_runs": 0, "market_api": 0, "source_at_start": binding(__file__)}
    save("acquisition_receipt.json", receipt)
    headers = {"User-Agent": "fian-fixed2010-county-source/395", "Accept-Encoding": "identity",
               "Range": receipt["Range"], "If-Match": etag}
    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(receipt["url"], headers=headers)
    try:
        receipt["HTTP_attempts"] = 1
        save("acquisition_receipt.json", receipt)
        try:
            response = opener.open(request, timeout=protocol["network_budget"]["timeout_seconds"])
        except urllib.error.HTTPError as error:
            response = error
        with response:
            receipt["HTTP_status"] = response.code
            receipt["response_url"] = response.geturl()
            original_headers = list(response.headers.items())
            save("original_headers.json", original_headers)
            receipt["headers_binding"] = binding(OUT / "original_headers.json")
            normalized = {k.lower(): v for k, v in original_headers}
            if response.code != 206:
                receipt["body_read"] = False
                raise ValueError("Original Range not206; no full ZIP body or replacement request")
            if normalized.get("content-range") != "bytes 5671161-5969284/10859656":
                raise ValueError("Response Content-Range differs from frozen393 directory")
            if normalized.get("etag") != etag:
                raise ValueError("Archive ETag changed")
            if int(normalized.get("content-length", "0")) != source["envelope_bytes"]:
                raise ValueError("Fixed member envelope length header mismatch")
            raw = response.read(source["envelope_bytes"])
            (OUT / "original_member_envelope.bin").write_bytes(raw)
            receipt["envelope_binding"] = binding(OUT / "original_member_envelope.bin")
            if len(raw) != source["envelope_bytes"]:
                raise ValueError("Original Range body is short; no retry")
        values = struct.unpack_from("<4s5H3L2H", raw, 0)
        signature, version, flags, method, dos_time, dos_date, crc, compressed, uncompressed, name_length, extra_length = values
        filename = raw[30:30+name_length].decode("utf-8" if flags & 2048 else "cp437")
        receipt["local_header"] = {"signature_hex": signature.hex(), "version": version, "flags": flags,
                                   "compression_method": method, "dos_time": dos_time, "dos_date": dos_date,
                                   "crc32_hex": f"{crc:08x}", "compressed_bytes": compressed,
                                   "uncompressed_bytes": uncompressed, "filename_length": name_length,
                                   "extra_length": extra_length, "filename": filename}
        if signature != b"PK\x03\x04" or method != 8 or flags & 9:
            raise ValueError("Unexpected localheader/DEFLATE flags; encrypted or descriptor mode not accepted")
        if filename != source["recommended_one_fixed_member"]:
            raise ValueError("Not the frozen2010 member")
        if compressed != source["expected_deflated_bytes"] or uncompressed != source["expected_uncompressed_bytes"]:
            raise ValueError("Original localheader sizes differ from393 directory")
        if f"{crc:08x}" != source["expected_crc32"]:
            raise ValueError("Original CRC header mismatch")
        payload_start = 30+name_length+extra_length
        if payload_start+compressed != len(raw):
            raise ValueError("Member envelope contains missing or unexpected trailing bytes")
        decoder = zlib.decompressobj(-15)
        data = decoder.decompress(raw[payload_start:], uncompressed+1)
        if len(data) > uncompressed or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
            raise ValueError("Bounded DEFLATE is incomplete or over declared length")
        if len(data) != uncompressed or zlib.crc32(data) & 0xffffffff != crc:
            raise ValueError("Decoded original length/CRC mismatch")
        path = OUT / filename
        path.write_bytes(data)
        receipt["decoded_csv_binding"] = binding(path)
        receipt["DEFLATE_length_and_CRC_verified"] = True
        first_lines = data[:8192].decode("utf-8-sig").splitlines()
        save("actual_csv_schema_preview.json", {"encoding_preview": "utf-8-sig", "first_original_lines": first_lines[:3],
                                                 "status": "schema_seen_not_full_rows_parsed"})
        receipt["schema_preview_binding"] = binding(OUT / "actual_csv_schema_preview.json")
        receipt["status"] = "original_fixed2010_csv_acquired_verified_not_yet_rows_parsed"
        print(json.dumps({"status": receipt["status"], "first_original_lines": first_lines[:3], "CSV_binding": receipt["decoded_csv_binding"]}, ensure_ascii=False))
    except Exception as error:
        receipt["status"] = "stopped_no_retry"
        receipt["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        receipt["ended_at"] = now()
        save("acquisition_receipt.json", receipt)


def parse_rows():
    """Validate all actual county rows offline, retaining original identities."""
    if (OUT / "parse_manifest.json").exists():
        raise FileExistsError("Fixed2010 rows already parsed; no replacement")
    protocol_path = BASE / "protocol.json"
    if binding(protocol_path)["sha256"] != PROTOCOL_SHA:
        raise ValueError("Frozen root protocol changed")
    protocol = json.loads(protocol_path.read_text())
    acquired = json.loads((OUT / "acquisition_receipt.json").read_text())
    if acquired["status"] != "original_fixed2010_csv_acquired_verified_not_yet_rows_parsed":
        raise ValueError("Verified original member required")
    source_path = Path(acquired["decoded_csv_binding"]["path"])
    if binding(source_path) != acquired["decoded_csv_binding"]:
        raise ValueError("Decoded original CSV changed")
    raw_text = source_path.read_text(encoding="utf-8-sig")
    raw_lines = raw_text.splitlines()
    original_rows = list(csv.reader(raw_lines))
    columns, original_rows = original_rows[0], original_rows[1:]
    if len(columns) != len(set(columns)) or columns[:2] != ["StPostal", "Fips"]:
        raise ValueError("Actual identity column schema changed or duplicates")
    soybean_columns = [f"Category_{x:03d}" for x in protocol["crop_codes"]]
    if not all(x in columns for x in soybean_columns+["Soybeans_all"]):
        raise ValueError("Actual declared soybean columns missing; no substituted category")
    count_columns = columns[2:]
    if not all(re.fullmatch(r"Category_\d{3}|[A-Za-z_]+_all", x) for x in count_columns):
        raise ValueError("Unknown original non-identity column; inspect instead of coercing")
    all_path = OUT / "validated_all_count_columns.jsonl"
    soy_path = OUT / "county_soy_rows.csv"
    csv_columns = ["original_line_number", "StPostal", "Fips", "county_fips5"]+soybean_columns+[
        "Soybeans_all", "computed_soy_group_sum", "positive_soy_pixels", "missing_columns", "invalid_columns", "soy_sum_matches", "raw_line_sha256"]
    fips_seen = collections.Counter()
    state_prefixes = collections.defaultdict(set)
    state_summaries = {}
    totals = {"rows": 0, "positive_soy_rows": 0, "zero_soy_rows": 0, "unknown_soy_rows": 0,
              "missing_count_cells": 0, "invalid_count_cells": 0, "soy_group_mismatch_rows": 0,
              "malformed_identity_rows": 0, "duplicate_fips_rows": 0,
              "soy_group_pixel_sum": 0, "raw_count_cells_checked": 0}
    with all_path.open("w") as all_file, soy_path.open("w", newline="") as soy_file:
        writer = csv.DictWriter(soy_file, fieldnames=csv_columns)
        writer.writeheader()
        for row_index, raw in enumerate(original_rows, 2):
            if len(raw) != len(columns):
                raise ValueError(f"Original row{row_index} has different field count; no row drop")
            item = dict(zip(columns, raw))
            postal, original_fips = item["StPostal"], item["Fips"]
            identity_errors = []
            if not re.fullmatch(r"[A-Z]{2}", postal) or not re.fullmatch(r"\d{4,5}", original_fips):
                identity_errors.append("original_identity_syntax")
                canonical_fips = None
            else:
                canonical_fips = original_fips.zfill(5)
                if canonical_fips[-3:] == "000":
                    identity_errors.append("aggregate_not_county_code")
                fips_seen[canonical_fips] += 1
                state_prefixes[postal].add(canonical_fips[:2])
            values = {}
            missing, invalid = [], []
            for name in count_columns:
                token = item[name]
                totals["raw_count_cells_checked"] += 1
                if token == "":
                    values[name] = None
                    missing.append(name)
                elif not re.fullmatch(r"\d+", token):
                    values[name] = None
                    invalid.append({"column": name, "original_token": token})
                else:
                    values[name] = int(token)
            components = [values[x] for x in soybean_columns]
            computed = sum(components) if all(x is not None for x in components) else None
            published = values["Soybeans_all"]
            matches = computed == published if computed is not None and published is not None else None
            positive = computed > 0 if computed is not None else None
            line_hash = hashlib.sha256(raw_lines[row_index-1].encode("utf-8")).hexdigest()
            parsed = {"original_line_number": row_index, "StPostal": postal, "Fips_original": original_fips,
                      "county_fips5": canonical_fips, "state_fips2": canonical_fips[:2] if canonical_fips else None,
                      "county_code3": canonical_fips[2:] if canonical_fips else None,
                      "count_columns": values, "soy_category_columns": soybean_columns,
                      "computed_soy_group_sum": computed, "published_Soybeans_all": published,
                      "soy_sum_matches": matches, "positive_soy_pixels": positive,
                      "missing_columns": missing, "invalid_columns": invalid,
                      "identity_errors": identity_errors,
                      "raw_line_sha256_utf8_without_line_ending": line_hash}
            all_file.write(json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))+"\n")
            writer.writerow({"original_line_number": row_index, "StPostal": postal, "Fips": original_fips,
                             "county_fips5": canonical_fips, **{x: values[x] for x in soybean_columns},
                             "Soybeans_all": published, "computed_soy_group_sum": computed,
                             "positive_soy_pixels": positive, "missing_columns": json.dumps(missing),
                             "invalid_columns": json.dumps(invalid), "soy_sum_matches": matches,
                             "raw_line_sha256": line_hash})
            totals["rows"] += 1
            totals["positive_soy_rows"] += positive is True
            totals["zero_soy_rows"] += positive is False
            totals["unknown_soy_rows"] += positive is None
            totals["missing_count_cells"] += len(missing)
            totals["invalid_count_cells"] += len(invalid)
            totals["soy_group_mismatch_rows"] += matches is False
            totals["malformed_identity_rows"] += bool(identity_errors)
            if computed is not None:
                totals["soy_group_pixel_sum"] += computed
            state = state_summaries.setdefault(postal, {"rows": 0, "positive_soy_rows": 0, "zero_soy_rows": 0,
                                                        "unknown_soy_rows": 0, "soy_group_pixel_sum": 0})
            state["rows"] += 1
            state["positive_soy_rows"] += positive is True
            state["zero_soy_rows"] += positive is False
            state["unknown_soy_rows"] += positive is None
            if computed is not None:
                state["soy_group_pixel_sum"] += computed
    duplicates = {key: n for key, n in fips_seen.items() if n != 1}
    totals["duplicate_fips_rows"] = sum(n for n in duplicates.values())
    inconsistent_prefixes = {key: sorted(values) for key, values in state_prefixes.items() if len(values) != 1}
    all_prefixes = [next(iter(values)) for values in state_prefixes.values() if len(values) == 1]
    prefix_shared_by_different_postal = len(all_prefixes) != len(set(all_prefixes))
    source_schema = {"original_columns": columns, "column_count": len(columns), "count_column_count": len(count_columns),
                     "category_column_count": sum(x.startswith("Category_") for x in columns),
                     "identity_columns": columns[:2], "soy_category_columns": soybean_columns,
                     "published_group_column": "Soybeans_all", "encoding": "utf-8-sig",
                     "identity_normalization": "Preserve original Fips string; canonical5digits only via left-zero padding, not a county crosswalk or year substitution",
                     "raw_line_hash_definition": "UTF8 decoded original one-line record without CSV line ending; original wholeCSV bytes separately bound"}
    save("actual_full_schema.json", source_schema)
    save("state_count_summary.json", {"state_summaries": state_summaries,
                                      "state_postal_to_observed_fips_prefix": {k: sorted(v) for k, v in state_prefixes.items()},
                                      "duplicate_fips": duplicates, "inconsistent_state_prefixes": inconsistent_prefixes})
    critical_defects = sum(totals[x] for x in ["invalid_count_cells", "soy_group_mismatch_rows", "malformed_identity_rows", "duplicate_fips_rows"])
    manifest = {"schema": "stage395_fixed2010_county_parse_v1", "parsed_at": now(),
                "status": "all_original_rows_parsed_with_no_detected_core_defect" if not critical_defects and not inconsistent_prefixes and not prefix_shared_by_different_postal else "all_original_rows_parsed_with_scoped_defects",
                "totals": totals, "unique_fips_count": len(fips_seen), "state_postal_count": len(state_summaries),
                "source_binding": binding(source_path), "protocol_binding": binding(protocol_path),
                "acquisition_binding": binding(OUT / "acquisition_receipt.json"),
                "source_at_parse": binding(__file__),
                "output_bindings": [binding(x) for x in [all_path, soy_path, OUT/"actual_full_schema.json", OUT/"state_count_summary.json"]],
                "county_identity_validation": {"syntax_unique_and_postal_prefix_internally_checked": True,
                                               "prefix_shared_by_different_postal": prefix_shared_by_different_postal,
                                               "external_Census2010_county_crosscheck_done": False,
                                               "boundary_year_not_inferred_from_cropyear": True},
                "limits": ["Current archive derived2010 structuralprior, not2011 first-seen or exactvintage",
                           "Pixel counts are not officialNASS acreage or2019 production",
                           "No normalization or weather-cell allocation computed", "Allzero and positive counties retained",
                           "No CSV row omitted based on soybean count or financial outcome"],
                "execution_counts": {"HTTP_attempts": 1, "automatic_retries": 0, "redirects": 0,
                                     "acquisition_invocations": 1, "offline_parse_invocations": 1,
                                     "fit": 0, "cash_backtest": 0, "market_api": 0, "SQL": 0}}
    save("parse_manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "totals": totals, "state_postal_count": len(state_summaries),
                      "unique_fips_count": len(fips_seen), "schema": source_schema}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["acquire", "parse"])
    args = parser.parse_args()
    acquire() if args.operation == "acquire" else parse_rows()
