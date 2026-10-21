"""Fetch exactly one officially located Census2010 national county Gazetteer."""
from __future__ import annotations

import collections
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import traceback
import urllib.error
import urllib.request
import zipfile

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE / "outputs/stage396_census2010_county_points"
OUT = ROOT / "actual_run1"
URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/Gaz_counties_national.zip"
PAGE = "https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.2010.html"
REFERENCE = "https://www2.census.gov/data/api-documentation/locating-quickfacts-data-points-in-data-census-gov-and-census-gov.pdf"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def bind(path):
    body = path.read_bytes()
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    if OUT.exists():
        raise RuntimeError("one final data request only: actual_run1 already exists")
    OUT.mkdir()
    receipt = {"schema": "stage396_census2010_county_points_actual_v1", "started_at": now(),
               "status": "started", "script": bind(Path(__file__).resolve()),
               "source": URL, "locator_page": PAGE, "official_reference_with_exact2010_link": REFERENCE,
               "locator_evidence": "2010 Gazetteer Counties section plus official QuickFacts reference Land area2010 link; not a guessed URL",
               "geography_vintage": "2010-01-01", "strict_historical_first_seen": False,
               "download_is_current_historical_structure_reconstruction": True,
               "point_semantics": "official representative/internal county point; not actual soybean crop placement",
               "limits": {"zip_bytes": 2097152, "uncompressed_total_bytes": 5242880, "final_data_requests": 1, "retry": 0, "redirect": 0},
               "fit": 0, "cash": 0, "market_API": 0, "SQL": 0, "whole_goal_achieved": False}
    write_json(OUT / "manifest.json", receipt)
    response = {"url": URL, "started_at": now(), "retry": 0, "redirect": 0,
                "request_headers": {"User-Agent": "Mozilla/5.0 (compatible; Stage396 public-data research)"}}
    body = b""
    try:
        try:
            request = urllib.request.Request(URL, headers=response["request_headers"])
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as stream:
                response["status"] = stream.status
                response["headers"] = dict(stream.headers)
                if stream.status != 200:
                    raise RuntimeError(f"expected HTTP200, got {stream.status}")
                declared = stream.headers.get("Content-Length")
                if declared is not None and not 0 < int(declared) <= 2097152:
                    raise RuntimeError("declared ZIP size outside2MiB limit")
                body = stream.read(2097152)
                if len(body) >= 2097152 or (declared is not None and len(body) != int(declared)):
                    raise RuntimeError("bounded ZIP response length failed")
        except urllib.error.HTTPError as error:
            response["status"] = error.code
            response["headers"] = dict(error.headers)
            body = error.read(4096)
            response["error"] = repr(error)
            raise
        finally:
            zip_path = OUT / "Gaz_counties_national.zip"
            zip_path.write_bytes(body)
            response["body"] = bind(zip_path)
            response["ended_at"] = now()
            write_json(OUT / "source.response.json", response)
            receipt["raw_source"] = response["body"]
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            entries = archive.infolist()
            if sum(entry.file_size for entry in entries) > 5242880:
                raise RuntimeError("ZIP uncompressed contents exceed5MiB limit")
            receipt["archive_schema"] = [{"filename": entry.filename, "bytes": entry.file_size,
                                           "compressed_bytes": entry.compress_size, "CRC32": f"{entry.CRC:08x}",
                                           "compress_type": entry.compress_type} for entry in entries]
            texts = [entry for entry in entries if not entry.is_dir() and entry.filename.lower().endswith(".txt")]
            if len(texts) != 1:
                raise RuntimeError("national Gazetteer must have one unambiguous text member")
            member = texts[0]
            raw = archive.read(member)  # zipfile validates the complete CRC32.
            if len(raw) != member.file_size:
                raise RuntimeError("member uncompressed length mismatch")
        raw_path = OUT / Path(member.filename).name
        raw_path.write_bytes(raw)
        receipt["raw_member"] = bind(raw_path)
        receipt["CRC_verified"] = True
        try:
            text = raw.decode("utf-8-sig")
            encoding = "utf-8-sig"
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
            encoding = "cp1252"
        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter="\t")
        original_headers = reader.fieldnames
        if original_headers is None:
            raise RuntimeError("missing original Gazetteer header")
        normalized = [key.strip() for key in original_headers]
        if len(set(normalized)) != len(normalized):
            raise RuntimeError("duplicate normalized headers")
        if not {"USPS", "GEOID", "NAME", "INTPTLAT", "INTPTLONG"}.issubset(normalized):
            raise RuntimeError(f"unexpected source schema: {normalized!r}")
        receipt["original_schema"] = original_headers
        receipt["normalized_schema"] = normalized
        receipt["text_encoding"] = encoding
        rows = []
        geoids = set()
        states = collections.defaultdict(set)
        duplicate_coordinates = collections.Counter()
        for row_number, original in enumerate(reader, 2):
            if None in original:
                raise RuntimeError(f"extra source columns on row{row_number}")
            row = {key.strip(): value.strip() for key, value in original.items()}
            geoid = row["GEOID"]
            if not re.fullmatch(r"[0-9]{5}", geoid) or geoid[:2] == "00" or geoid[2:] == "000":
                raise RuntimeError(f"invalid original five-digit county GEOID {geoid!r}")
            if geoid in geoids:
                raise RuntimeError(f"duplicate original GEOID {geoid}")
            geoids.add(geoid)
            if not re.fullmatch(r"[A-Z]{2}", row["USPS"]):
                raise RuntimeError(f"invalid USPS identifier on {geoid}")
            states[row["USPS"]].add(geoid[:2])
            lat = float(row["INTPTLAT"]) if row["INTPTLAT"] else None
            lon = float(row["INTPTLONG"]) if row["INTPTLONG"] else None
            missing = lat is None or lon is None
            if (lat is not None and (not math.isfinite(lat) or not -90 <= lat <= 90) or
                    lon is not None and (not math.isfinite(lon) or not -180 <= lon <= 180)):
                raise RuntimeError(f"invalid representative point on {geoid}")
            numeric_checks = {}
            for field in normalized:
                if field in ("POP10", "HU10", "ALAND", "AWATER", "ALAND_SQMI", "AWATER_SQMI"):
                    value = float(row[field])
                    if not math.isfinite(value) or value < 0:
                        raise RuntimeError(f"invalid nonnegative field {field} on {geoid}")
                    numeric_checks[field] = value
            if not missing:
                duplicate_coordinates[(lat, lon)] += 1
            rows.append({"GEOID": geoid, "state_FIPS": geoid[:2], "county_FIPS": geoid[2:],
                         "USPS": row["USPS"], "NAME": row["NAME"], "INTPTLAT": lat, "INTPTLONG": lon,
                         "point_missing": missing, "original_fields": original,
                         "checked_nonnegative_fields": numeric_checks})
        if not rows or any(len(values) != 1 for values in states.values()):
            raise RuntimeError("empty county table or inconsistent USPS to state FIPS mapping")
        points_path = OUT / "county_points.jsonl"
        with points_path.open("w") as file:
            for row in rows:
                file.write(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        receipt["county_points"] = bind(points_path)
        present_rows = [row for row in rows if not row["point_missing"]]
        receipt["validation"] = {"rows": len(rows), "unique_GEOID": len(geoids), "duplicate_GEOID": 0,
                                 "state_FIPS_by_USPS": {key: next(iter(value)) for key, value in sorted(states.items())},
                                 "missing_points": len(rows) - len(present_rows),
                                 "repeated_coordinate_pairs": sum(count > 1 for count in duplicate_coordinates.values()),
                                 "latitude_min": min(row["INTPTLAT"] for row in present_rows),
                                 "latitude_max": max(row["INTPTLAT"] for row in present_rows),
                                 "longitude_min": min(row["INTPTLONG"] for row in present_rows),
                                 "longitude_max": max(row["INTPTLONG"] for row in present_rows)}
        receipt["status"] = "passed"
    except BaseException as error:
        receipt["status"] = "failed"
        receipt["error"] = repr(error)
        receipt["traceback"] = traceback.format_exc()
        raise
    finally:
        receipt["ended_at"] = now()
        write_json(OUT / "manifest.json", receipt)
        print(json.dumps({"status": receipt["status"], "manifest": str(OUT / "manifest.json"),
                          "data_requests": 1, "fit": 0, "cash": 0}), flush=True)


if __name__ == "__main__":
    main()
