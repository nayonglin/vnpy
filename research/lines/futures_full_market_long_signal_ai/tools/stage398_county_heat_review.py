"""Independent review of new county sources and one declared spatial composition.

No download, model, financial runner, or author implementation is imported.
The source pass is saved once; composition later reuses accepted derived sources.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import re
import struct
import time
import zipfile
import zlib

LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "outputs/stage398_county_heat_review"
P395 = LINE / "outputs/stage395_fixed2010_county_source/actual_run1"
P396 = LINE / "outputs/stage396_census2010_county_points/actual_run1"
P397 = LINE / "outputs/stage397_county_heat_single_case"
SOY = ["Category_005", "Category_026", "Category_239", "Category_240", "Category_241", "Category_254"]


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Files:
    def __init__(self):
        self.cache = {}

    def read(self, path):
        path = str(Path(path).resolve())
        if path not in self.cache:
            self.cache[path] = Path(path).read_bytes()
        return self.cache[path]

    def binding(self, path):
        data = self.read(path)
        return {"path": str(Path(path).resolve()), "bytes": len(data), "sha256": digest(data)}

    def check(self, binding):
        assert self.binding(binding["path"]) == binding, binding["path"]

    def load(self, path):
        return json.loads(self.read(path))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def source_review():
    target = OUT / "source_review_receipt.json"
    if target.exists():
        raise RuntimeError("Source review already completed; do not repeat original-source parsing")
    started = now()
    tick = time.monotonic()
    f = Files()
    m395 = f.load(P395 / "parse_manifest.json")
    a395 = f.load(P395 / "acquisition_receipt.json")
    m396 = f.load(P396 / "manifest.json")
    protocol = f.load(P397 / "protocol.json")
    for b in [m395["source_binding"], m395["protocol_binding"], m395["acquisition_binding"],
              m395["source_at_parse"], a395["headers_binding"], a395["envelope_binding"],
              a395["decoded_csv_binding"], m396["raw_source"], m396["raw_member"],
              m396["county_points"], m396["script"]] + m395["output_bindings"]:
        f.check(b)
    for key in ("county_pixels", "county_points"):
        f.check(protocol["sources"][key])
    envelope = f.read(a395["envelope_binding"]["path"])
    header = struct.unpack("<IHHHHHIIIHH", envelope[:30])
    sig, version, flags, method, _, _, crc, compressed, uncompressed, nname, nextra = header
    assert sig == 0x04034B50 and method == 8 and flags & 9 == 0
    assert envelope[30:30+nname].decode("cp437") == "CDL_Cnty_Pixel_2010_30m.csv"
    body = envelope[30+nname+nextra:]
    assert len(body) == compressed == 298067 and uncompressed == 1141625
    original = f.read(m395["source_binding"]["path"])
    assert zlib.decompress(body, -15) == original
    assert zlib.crc32(original) & 0xffffffff == crc == 0x70BFC98E
    headers395 = f.load(a395["headers_binding"]["path"])
    # The acquisition receipt binds exact Range/If-Match and original headers;
    # the raw member/CRC check independently binds the actual data body.
    assert a395["HTTP_status"] == 206 and a395["HTTP_attempts"] == 1
    assert a395["Range"] == "bytes=5671161-5969284"
    assert a395["automatic_retries"] == a395["redirects"] == 0
    text = original.decode("utf-8-sig")
    rawlines = text.splitlines()
    reader = csv.DictReader(io.StringIO(text, newline=""))
    cols = reader.fieldnames
    assert cols[:2] == ["StPostal", "Fips"] and len(cols) == len(set(cols)) == 134
    counts = cols[2:]
    assert len(counts) == 132 and all(k in counts for k in SOY + ["Soybeans_all"])
    original_rows = list(reader)
    full = [json.loads(s) for s in f.read(P395 / "validated_all_count_columns.jsonl").splitlines()]
    derived = list(csv.DictReader(io.StringIO(f.read(P395 / "county_soy_rows.csv").decode())))
    assert len(original_rows) == len(full) == len(derived) == 3109
    states = defaultdict(lambda: {"rows": 0, "positive_soy_rows": 0, "zero_soy_rows": 0,
                                  "unknown_soy_rows": 0, "soy_group_pixel_sum": 0})
    normalized = {}
    for index, (row, allrow, soyrow) in enumerate(zip(original_rows, full, derived), 2):
        postal, original_fips = row["StPostal"], row["Fips"]
        assert re.fullmatch(r"[A-Z]{2}", postal) and re.fullmatch(r"\d{4,5}", original_fips)
        canonical = original_fips.zfill(5)
        assert canonical[2:] != "000" and canonical not in normalized
        number = {}
        for key in counts:
            assert re.fullmatch(r"\d+", row[key]), (canonical, key)
            number[key] = int(row[key])
        soy = sum(number[key] for key in SOY)
        assert soy == number["Soybeans_all"]
        linehash = digest(rawlines[index-1].encode())
        assert allrow["original_line_number"] == index and allrow["Fips_original"] == original_fips
        assert allrow["StPostal"] == postal and allrow["county_fips5"] == canonical
        assert allrow["state_fips2"] == canonical[:2] and allrow["county_code3"] == canonical[2:]
        assert allrow["count_columns"] == number and allrow["computed_soy_group_sum"] == soy
        assert allrow["published_Soybeans_all"] == soy and allrow["soy_sum_matches"] is True
        assert allrow["missing_columns"] == allrow["invalid_columns"] == allrow["identity_errors"] == []
        assert allrow["raw_line_sha256_utf8_without_line_ending"] == linehash
        assert (soyrow["StPostal"], soyrow["Fips"], soyrow["county_fips5"]) == (postal, original_fips, canonical)
        assert int(soyrow["original_line_number"]) == index and soyrow["raw_line_sha256"] == linehash
        assert int(soyrow["Soybeans_all"]) == int(soyrow["computed_soy_group_sum"]) == soy
        for key in SOY:
            assert int(soyrow[key]) == number[key]
        state = states[postal]
        state["rows"] += 1
        state["positive_soy_rows" if soy > 0 else "zero_soy_rows"] += 1
        state["soy_group_pixel_sum"] += soy
        normalized[canonical] = (postal, soy)
    assert len(states) == 49
    assert sum(s["positive_soy_rows"] for s in states.values()) == 2631
    assert sum(s["zero_soy_rows"] for s in states.values()) == 478
    assert sum(s["soy_group_pixel_sum"] for s in states.values()) == 349151244
    assert f.load(P395 / "state_count_summary.json")["state_summaries"] == dict(states)

    zipraw = f.read(m396["raw_source"]["path"])
    geotxt = f.read(m396["raw_member"]["path"])
    with zipfile.ZipFile(io.BytesIO(zipraw)) as archive:
        assert archive.namelist() == ["Gaz_counties_national.txt"]
        assert archive.read("Gaz_counties_national.txt") == geotxt
    original_points = list(csv.DictReader(io.StringIO(geotxt.decode("cp1252"), newline=""), delimiter="\t"))
    points = [json.loads(s) for s in f.read(P396 / "county_points.jsonl").splitlines()]
    assert len(original_points) == len(points) == 3221
    geoid_map = {}
    postal_prefix = {}
    coords = set()
    for row, point in zip(original_points, points):
        clean = {k.strip(): v.strip() for k, v in row.items()}
        geoid, postal = clean["GEOID"], clean["USPS"]
        assert re.fullmatch(r"\d{5}", geoid) and geoid not in geoid_map
        assert point["GEOID"] == geoid and point["USPS"] == postal and point["original_fields"] == row
        assert point["state_FIPS"] == geoid[:2] and point["county_FIPS"] == geoid[2:]
        lat, lon = float(clean["INTPTLAT"]), float(clean["INTPTLONG"])
        assert math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
        assert (lat, lon) == (point["INTPTLAT"], point["INTPTLONG"]) and point["point_missing"] is False
        assert (lat, lon) not in coords
        coords.add((lat, lon))
        for key, val in point["checked_nonnegative_fields"].items():
            assert float(clean[key]) == val and math.isfinite(val) and val >= 0
        if postal in postal_prefix:
            assert postal_prefix[postal] == geoid[:2]
        postal_prefix[postal] = geoid[:2]
        geoid_map[geoid] = point
    assert len(postal_prefix) == 52 and postal_prefix == m396["validation"]["state_FIPS_by_USPS"]
    assert m396["geography_vintage"] == "2010-01-01" and m396["strict_historical_first_seen"] is False
    missing = []
    mismatch = []
    for geoid, (postal, soy) in normalized.items():
        if geoid not in geoid_map:
            missing.append({"GEOID": geoid, "StPostal": postal, "soy_pixels": soy})
        elif geoid_map[geoid]["USPS"] != postal:
            mismatch.append({"GEOID": geoid, "crop_USPS": postal, "point_USPS": geoid_map[geoid]["USPS"], "soy_pixels": soy})
    result = {"schema": "stage398_source_review_v1", "status": "passed",
              "started_at": started, "ended_at": now(), "elapsed_seconds": time.monotonic()-tick,
              "review_tool_at_source_pass": f.binding(__file__),
              "protocol397": f.binding(P397 / "protocol.json"),
              "source395_manifest": f.binding(P395 / "parse_manifest.json"),
              "source396_manifest": f.binding(P396 / "manifest.json"),
              "source_bindings": [m395["source_binding"], protocol["sources"]["county_pixels"], m396["raw_member"], m396["county_points"]],
              "395": {"rows": 3109, "count_columns": 132, "raw_count_cells": 410388,
                      "positive_counties": 2631, "zero_counties": 478, "soy_pixels": 349151244,
                      "states": 49, "state_summaries": dict(states), "all_count_values_match": True,
                      "unit": "2010 classified pixel counts, not acreage or2019 production"},
              "396": {"rows": 3221, "unique_GEOID": 3221, "postal_entities": 52,
                      "missing_points": 0, "coordinate_pairs_unique": True, "original_fields_exact": True,
                      "geography_vintage": "2010-01-01", "representative_point_not_crop_centroid": True},
              "cross_source_join": {"crop_rows": 3109, "exact_match": 3109-len(missing)-len(mismatch),
                                    "missing_counties": missing, "postal_mismatches": mismatch},
              "P0": 0, "P1": 0, "P2": 0, "reviewer_network": 0, "reviewer_install": 0,
              "reviewer_fit": 0, "reviewer_cash": 0, "reviewer_SQL": 0,
              "strict_historical_first_seen": False, "alpha_qualified": False, "whole_goal": False}
    save(target, result)
    print(json.dumps({"status": result["status"], "source_receipt": Files().binding(target),
                      "cross_source_join": result["cross_source_join"], "elapsed_seconds": result["elapsed_seconds"]}))


def composition_review():
    target = OUT / "actual_review_receipt.json"
    if target.exists():
        raise RuntimeError("Composition review already completed; do not replay the single sample")
    started, tick, f = now(), time.monotonic(), Files()
    accepted_sources = f.load(OUT / "source_review_receipt.json")
    assert accepted_sources["status"] == "passed"
    actual = P397 / "actual_run1"
    receipt = f.load(actual / "receipt.json")
    assert f.binding(actual / "receipt.json")["sha256"] == "45aa6ab9040b60ba98f2ad088b22c58ba918a82c1ba91dffd68f8329b0622e8a"
    protocol = f.load(P397 / "protocol.json")
    f.check(receipt["protocol"])
    f.check(receipt["source"])
    assert receipt["terminal_status"] == "complete"
    assert accepted_sources["protocol397"] == receipt["protocol"]
    assert receipt["inputs"] == protocol["sources"]
    for b in list(receipt["inputs"].values()) + receipt["outputs"]:
        f.check(b)
    counties = list(csv.DictReader(io.StringIO(f.read(receipt["inputs"]["county_pixels"]["path"]).decode())))
    points = {r["GEOID"]: r for r in (json.loads(s) for s in f.read(receipt["inputs"]["county_points"]["path"]).splitlines())}
    exposure = list(csv.DictReader(io.StringIO(f.read(receipt["inputs"]["exposure"]["path"]).decode())))
    authored_rows = [json.loads(s) for s in f.read(actual / "county_heat_rows.jsonl").splitlines()]
    authored_states = f.load(actual / "state_heat_components.json")
    authored_summary = f.load(actual / "summary.json")
    assert len(counties) == len(authored_rows) == 3109
    # Use accepted390 arrays only; never decode its raw GRIB again.
    import numpy as np
    with np.load(io.BytesIO(f.read(receipt["inputs"]["native_heat"]["path"])), allow_pickle=False) as archive:
        native = {k: archive[k] for k in archive.files}
    lat, lon = native["latitudes"], native["longitudes"]
    assert len(lat) == len(lon) == 65160
    assert native["validtimes_utc"].tolist()[::28] == ["2020-09-02T00:00:00Z", "2020-09-09T00:00:00Z"]
    grid_sin, grid_cos = np.sin(np.radians(lat)), np.cos(np.radians(lat))
    heat_unknown = (native["old_missing"] | native["new_missing"] | native["revision_missing"] |
                    ~np.isfinite(native["old_EDD"]) | ~np.isfinite(native["new_EDD"]) |
                    ~np.isfinite(native["revision_EDD"]))
    pixels_by_state = defaultdict(int)
    for county in counties:
        pixels_by_state[county["StPostal"]] += int(county["Soybeans_all"])
    name_postal = protocol["exposure_state_name_to_postal"]
    exposures = {}
    for e in exposure:
        postal = name_postal[e["state"]]
        assert postal not in exposures
        q, us = int(e["q2019_1000_bushels"]), int(e["us_q2019_1000_bushels"])
        g = (int(e["pods_pct"]) - int(e["leaves_pct"])) / 100
        assert 0 <= g <= 1 and us == 3558281
        exposures[postal] = {"state": e["state"], "q": q, "us": us, "g": g, "w": q/us}
    assert len(exposures) == 18
    max_numeric_error = 0.
    max_distance_error = 0.
    spatial_status = Counter()
    computed_rows, by_state, absent = [], defaultdict(list), []

    def close(actual_value, expected, key, tol=1.e-11):
        nonlocal max_numeric_error
        if expected is None:
            assert actual_value is None, key
        elif isinstance(expected, (str, bool, list, int)):
            assert actual_value == expected, (key, actual_value, expected)
        else:
            assert math.isfinite(actual_value)
            error = abs(actual_value-expected)
            max_numeric_error = max(max_numeric_error, error)
            assert error <= tol, (key, actual_value, expected, error)

    for county, authored in zip(counties, authored_rows):
        postal, fips = county["StPostal"], county["county_fips5"]
        pixels, denominator = int(county["Soybeans_all"]), pixels_by_state[postal]
        point = points.get(fips)
        row = {"county_fips5": fips, "original_Fips": county["Fips"], "StPostal": postal,
               "soy_pixels": pixels, "state_total_soy_pixels": denominator,
               "within_state_pixel_weight": pixels/denominator if denominator else None,
               "grid_index": None, "distance_degrees": None, "grid_latitude": None,
               "grid_longitude": None, "old_heat": None, "new_heat": None, "heat_revision": None}
        status = "point_missing"
        if point is not None:
            if point["USPS"] != postal or point["state_FIPS"] != fips[:2] or point["point_missing"]:
                status = "point_identity_or_value_unknown"
            else:
                # Independent spherical-cosine nearest search, rather than author Haversine argmin.
                phi = math.radians(point["INTPTLAT"])
                dlon = np.radians((lon-point["INTPTLONG"]+180.) % 360.-180.)
                cosine = math.sin(phi)*grid_sin + math.cos(phi)*grid_cos*np.cos(dlon)
                index = int(np.argmax(cosine))  # first native index on an exact computed tie
                dphi = math.radians(float(lat[index])-point["INTPTLAT"])
                dlambda = math.radians((float(lon[index])-point["INTPTLONG"]+180.) % 360.-180.)
                hav = math.sin(dphi/2)**2 + math.cos(phi)*math.cos(math.radians(float(lat[index])))*math.sin(dlambda/2)**2
                distance = math.degrees(2*math.atan2(math.sqrt(max(0., hav)), math.sqrt(max(0., 1-hav))))
                row.update(grid_index=index, distance_degrees=distance,
                           grid_latitude=float(lat[index]), grid_longitude=float(lon[index]))
                status = "common_heat_unknown" if heat_unknown[index] else "point_exact_fips"
                if not heat_unknown[index]:
                    row.update(old_heat=float(native["old_EDD"][index]), new_heat=float(native["new_EDD"][index]),
                               heat_revision=float(native["revision_EDD"][index]))
        if point is None:
            absent.append({"county_fips5": fips, "StPostal": postal, "soy_pixels": pixels})
        row.update(spatial_status=status, positive_mass_mapped=pixels > 0 and row["heat_revision"] is not None,
                   progress_status="original391_state_observed" if postal in exposures else "original391_state_unknown")
        assert set(authored) == set(row)
        for key, expected in row.items():
            close(authored[key], expected, f"county:{fips}:{key}")
        if row["distance_degrees"] is not None:
            max_distance_error = max(max_distance_error, abs(authored["distance_degrees"]-row["distance_degrees"]))
        spatial_status[status] += 1
        computed_rows.append(row)
        by_state[postal].append(row)
    computed_states = []
    for postal, group in sorted(by_state.items()):
        total = sum(r["soy_pixels"] for r in group)
        known = [r for r in group if r["heat_revision"] is not None]
        mapped = sum(r["soy_pixels"] for r in known)
        heat = {}
        for key in ("old_heat", "new_heat", "heat_revision"):
            # Sum the unnormalized pixel*heat numerator, then divide by the FULL state denominator.
            heat[key] = math.fsum(r["soy_pixels"]*r[key] for r in known)/total if total and known else None
        row = {"StPostal": postal, "county_count": len(group), "total_soy_pixels": total,
               "mapped_soy_pixels": mapped, "unmapped_positive_soy_pixels": total-mapped,
               "positive_county_count": sum(r["soy_pixels"] > 0 for r in group),
               "unmapped_positive_counties": [r["county_fips5"] for r in group if r["soy_pixels"] > 0 and r["heat_revision"] is None],
               "mapped_pixel_share": mapped/total if total else None,
               "covered_old_heat": heat["old_heat"], "covered_new_heat": heat["new_heat"],
               "covered_heat_revision": heat["heat_revision"], "progress_observed": postal in exposures,
               "state": None, "q2019_1000_bushels": None, "w": None, "g": None,
               "weighted_old_component": None, "weighted_new_component": None, "weighted_revision_component": None}
        if postal in exposures:
            e = exposures[postal]
            row.update(state=e["state"], q2019_1000_bushels=e["q"], w=e["w"], g=e["g"])
            for source_key, target_key in (("old_heat", "weighted_old_component"), ("new_heat", "weighted_new_component"), ("heat_revision", "weighted_revision_component")):
                row[target_key] = None if heat[source_key] is None else heat[source_key]*e["q"]*e["g"]/e["us"]
        computed_states.append(row)
    assert len(computed_states) == len(authored_states) == 49
    for row, authored in zip(computed_states, authored_states):
        assert set(row) == set(authored)
        for key, value in row.items():
            close(authored[key], value, f"state:{row['StPostal']}:{key}")
    selected = [r for r in computed_states if r["progress_observed"]]
    assert len(selected) == 18
    covered = {key: math.fsum(r[key] for r in selected if r[key] is not None)
               for key in ("weighted_old_component", "weighted_new_component", "weighted_revision_component")}
    q_us = 3558281
    observed_q = sum(e["q"] for e in exposures.values())
    wg = math.fsum(e["q"]*e["g"]/q_us for e in exposures.values())
    mapped_wg = math.fsum(r["w"]*r["g"]*r["mapped_pixel_share"] for r in selected)
    numeric_summary = {"county_rows_retained": len(computed_rows),
                       "zero_soy_counties_retained": sum(r["soy_pixels"] == 0 for r in computed_rows),
                       "positive_soy_counties": sum(r["soy_pixels"] > 0 for r in computed_rows),
                       "exact_point_matched_counties": spatial_status["point_exact_fips"],
                       "soy_pixels_all395": sum(r["soy_pixels"] for r in computed_rows),
                       "positive_unmapped_counties": [r["county_fips5"] for r in computed_rows if r["soy_pixels"] > 0 and not r["positive_mass_mapped"]],
                       "us_q2019": q_us, "original391_state_count": 18,
                       "observed_progress_production_share": observed_q/q_us,
                       "outside_original391_progress_unknown_production_share": (q_us-observed_q)/q_us,
                       "observed_production_times_progress_proxy_mass": wg,
                       "observed_mapped_production_times_progress_mass": mapped_wg,
                       "positive_mass_nearest_grid_distance_max_degrees": max(r["distance_degrees"] for r in computed_rows if r["soy_pixels"] > 0 and r["distance_degrees"] is not None)}
    for key, value in numeric_summary.items():
        close(authored_summary[key], value, "summary:"+key)
    for key, value in covered.items():
        close(authored_summary["covered_component_degC_day"][key], value, "covered:"+key)
    for key in ("full_observed_national_old_heat", "full_observed_national_new_heat", "full_observed_national_heat_revision"):
        assert authored_summary[key] is None
    assert all(v is False for v in authored_summary["qualifications"].values())
    assert all(v == 0 for v in receipt["execution"].values())
    assert absent == [{"county_fips5": "46102", "StPostal": "SD", "soy_pixels": 28}]
    result = {"schema": "stage398_independent_county_composition_review_v1", "status": "passed_partial_physical_source_only",
              "started_at": started, "ended_at": now(), "elapsed_seconds": time.monotonic()-tick,
              "review_tool": f.binding(__file__), "source_pass": f.binding(OUT / "source_review_receipt.json"),
              "actual397": f.binding(actual / "receipt.json"), "protocol": receipt["protocol"], "outputs_checked": receipt["outputs"],
              "county_rows_checked": 3109, "state_rows_checked": 49, "progress_states": 18,
              "independent_nearest_method": "spherical cosine max with periodic longitude and first index tie; scalar angular distance separately checked",
              "max_numeric_absolute_error": max_numeric_error, "max_distance_degrees_error": max_distance_error,
              "cross_source_unknown": absent, "spatial_status_counts": dict(spatial_status),
              "summary": numeric_summary, "covered_component_degC_day": covered,
              "full_observed_national_heat": None, "unknown_progress_production_share": (q_us-observed_q)/q_us,
              "P0": 0, "P1": 0, "P2": 0,
              "reviewer_network": 0, "reviewer_install": 0, "reviewer_fit": 0, "reviewer_cash": 0, "reviewer_SQL": 0,
              "old390_GRIB_decodes": 0, "old391_original_table_parses": 0,
              "scope": "98products/95families preserved; proposed m-only source does not shrink the market universe",
              "confidence": "Source arithmetic and current-sample composition pass; one coarse historical sample does not establish forecast accuracy, point/crop representativeness, PIT, alpha or increased betting.",
              "qualifications": {"single_partial_physical_sample": True, "full_national_index": False, "strict_first_seen": False,
                                 "field_crop_location": False, "ensemble": False, "alpha": False, "financial": False,
                                 "increased_betting": False, "whole_goal": False}}
    save(target, result)
    print(json.dumps({"status": result["status"], "receipt": Files().binding(target),
                      "max_numeric_absolute_error": max_numeric_error, "covered": covered,
                      "unmapped": absent, "elapsed_seconds": result["elapsed_seconds"]}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources-only", action="store_true")
    parser.add_argument("--composition", action="store_true")
    args = parser.parse_args()
    if args.sources_only:
        source_review()
    elif args.composition:
        composition_review()
    else:
        raise SystemExit("Composition review requires the actual397 terminal and separately added binding")


if __name__ == "__main__":
    main()
