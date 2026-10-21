"""One frozen physical join. No prices, models, network, or trading engine."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE / "outputs/stage397_county_heat_single_case"


def binding(path):
    path = Path(path)
    body = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest()}


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False) + "\n")


def nearest(lat, lon, grid_lat, grid_lon):
    """Haversine angular distance, longitude periodic, first native index tie."""
    phi = math.radians(lat)
    dphi = np.radians(grid_lat - lat)
    dlon = np.radians((grid_lon - lon + 180.) % 360. - 180.)
    hav = np.sin(dphi / 2.) ** 2 + math.cos(phi) * np.cos(np.radians(grid_lat)) * np.sin(dlon / 2.) ** 2
    hav = np.clip(hav, 0., 1.)
    index = int(np.argmin(hav))
    return index, float(2. * math.asin(math.sqrt(float(hav[index]))))


def weighted_component(pixels, values):
    """Keep the full denominator, including positive pixels with unknown heat."""
    total = sum(pixels)
    if not total:
        return None, None
    pairs = [(p, v) for p, v in zip(pixels, values) if v is not None]
    if not pairs:
        return None, 0.
    return math.fsum(p / total * v for p, v in pairs), sum(p for p, _ in pairs) / total


def run():
    start = time.monotonic()
    out = ROOT / "actual_run1"
    out.mkdir(exist_ok=False)
    protocol = json.loads((ROOT / "protocol.json").read_text())
    dump(out / "started.json", {"started_at": datetime.now(timezone.utc).isoformat(),
                               "protocol": binding(ROOT / "protocol.json"),
                               "source": binding(__file__)})
    bodies = {}
    for name, ref in protocol["sources"].items():
        raw = Path(ref["path"]).read_bytes()
        assert len(raw) == ref["bytes"] and hashlib.sha256(raw).hexdigest() == ref["sha256"], name
        bodies[name] = raw
    counties = list(csv.DictReader(io.StringIO(bodies["county_pixels"].decode())))
    points = [json.loads(x) for x in bodies["county_points"].decode().splitlines()]
    exposure = list(csv.DictReader(io.StringIO(bodies["exposure"].decode())))
    assert len(counties) == len({r["county_fips5"] for r in counties})
    assert len(points) == len({r["GEOID"] for r in points})
    point_by_fips = {r["GEOID"]: r for r in points}
    state_exposure = {}
    for r in exposure:
        postal = protocol["exposure_state_name_to_postal"][r["state"]]
        q = int(r["q2019_1000_bushels"])
        us_q = int(r["us_q2019_1000_bushels"])
        g = (int(r["pods_pct"]) - int(r["leaves_pct"])) / 100.
        assert q > 0 and us_q > 0 and 0 <= g <= 1
        assert abs(q / us_q - float(r["w"])) < 1.e-15
        assert abs(g - float(r["g"])) < 1.e-15
        assert postal not in state_exposure
        state_exposure[postal] = {"state": r["state"], "q": q, "us_q": us_q,
                                  "w": q / us_q, "g": g}
    assert len(state_exposure) == 18
    with np.load(io.BytesIO(bodies["native_heat"]), allow_pickle=False) as z:
        grid = {k: z[k] for k in z.files}
    lat, lon = grid["latitudes"], grid["longitudes"]
    assert len(lat) == len(lon) == 65160 and np.isfinite(lat).all() and np.isfinite(lon).all()
    assert grid["validtimes_utc"].tolist()[::28] == ["2020-09-02T00:00:00Z", "2020-09-09T00:00:00Z"]
    unknown = grid["old_missing"] | grid["new_missing"] | grid["revision_missing"]
    unknown |= ~np.isfinite(grid["old_EDD"]) | ~np.isfinite(grid["new_EDD"]) | ~np.isfinite(grid["revision_EDD"])
    state_pixels = defaultdict(int)
    for r in counties:
        assert len(r["county_fips5"]) == 5 and r["county_fips5"].isdigit()
        pixels = int(r["Soybeans_all"])
        assert pixels >= 0 and pixels == int(r["computed_soy_group_sum"])
        state_pixels[r["StPostal"]] += pixels
    rows = []
    by_state = defaultdict(list)
    for r in counties:
        postal, fips = r["StPostal"], r["county_fips5"]
        pixels = int(r["Soybeans_all"])
        point = point_by_fips.get(fips)
        status = "point_missing" if point is None else "point_exact_fips"
        result = {"county_fips5": fips, "original_Fips": r["Fips"],
                  "StPostal": postal, "soy_pixels": pixels,
                  "state_total_soy_pixels": state_pixels[postal],
                  "within_state_pixel_weight": pixels / state_pixels[postal] if state_pixels[postal] else None,
                  "grid_index": None, "distance_degrees": None,
                  "grid_latitude": None, "grid_longitude": None,
                  "old_heat": None, "new_heat": None, "heat_revision": None}
        if point is not None:
            if point["USPS"] != postal or point["state_FIPS"] != fips[:2] or point["point_missing"]:
                status = "point_identity_or_value_unknown"
            else:
                index, distance = nearest(point["INTPTLAT"], point["INTPTLONG"], lat, lon)
                result.update(grid_index=index, distance_degrees=math.degrees(distance),
                              grid_latitude=float(lat[index]), grid_longitude=float(lon[index]))
                if unknown[index]:
                    status = "common_heat_unknown"
                else:
                    result.update(old_heat=float(grid["old_EDD"][index]),
                                  new_heat=float(grid["new_EDD"][index]),
                                  heat_revision=float(grid["revision_EDD"][index]))
        result["spatial_status"] = status
        result["positive_mass_mapped"] = pixels > 0 and result["heat_revision"] is not None
        result["progress_status"] = "original391_state_observed" if postal in state_exposure else "original391_state_unknown"
        rows.append(result)
        by_state[postal].append(result)
    states = []
    for postal, county_rows in sorted(by_state.items()):
        pixels = [r["soy_pixels"] for r in county_rows]
        totals = {key: weighted_component(pixels, [r[key] for r in county_rows])
                  for key in ("old_heat", "new_heat", "heat_revision")}
        mapped_pixels = sum(r["soy_pixels"] for r in county_rows if r["heat_revision"] is not None)
        state = {"StPostal": postal, "county_count": len(county_rows),
                 "total_soy_pixels": sum(pixels), "mapped_soy_pixels": mapped_pixels,
                 "unmapped_positive_soy_pixels": sum(pixels) - mapped_pixels,
                 "positive_county_count": sum(r["soy_pixels"] > 0 for r in county_rows),
                 "unmapped_positive_counties": [r["county_fips5"] for r in county_rows if r["soy_pixels"] > 0 and r["heat_revision"] is None],
                 "mapped_pixel_share": totals["heat_revision"][1],
                 "covered_old_heat": totals["old_heat"][0],
                 "covered_new_heat": totals["new_heat"][0],
                 "covered_heat_revision": totals["heat_revision"][0],
                 "progress_observed": postal in state_exposure,
                 "state": None, "q2019_1000_bushels": None, "w": None, "g": None,
                 "weighted_old_component": None, "weighted_new_component": None,
                 "weighted_revision_component": None}
        if postal in state_exposure:
            e = state_exposure[postal]
            state.update(state=e["state"], q2019_1000_bushels=e["q"], w=e["w"], g=e["g"])
            for source_key, target_key in (("old_heat", "weighted_old_component"), ("new_heat", "weighted_new_component"), ("heat_revision", "weighted_revision_component")):
                value = totals[source_key][0]
                state[target_key] = None if value is None else e["w"] * e["g"] * value
        states.append(state)
    assert set(state_exposure).issubset(by_state)
    selected = [s for s in states if s["progress_observed"]]
    covered = {key: math.fsum(s[key] for s in selected if s[key] is not None)
               for key in ("weighted_old_component", "weighted_new_component", "weighted_revision_component")}
    q_us_values = {e["us_q"] for e in state_exposure.values()}
    assert len(q_us_values) == 1
    q_us = q_us_values.pop()
    q_observed = sum(e["q"] for e in state_exposure.values())
    positive_rows = [r for r in rows if r["soy_pixels"] > 0]
    summary = {"schema": "stage397_county_point_physical_single_case_v1",
               "status": "fixed_historical_physical_reconstruction_only",
               "county_rows_retained": len(rows), "zero_soy_counties_retained": len(rows) - len(positive_rows),
               "positive_soy_counties": len(positive_rows),
               "exact_point_matched_counties": sum(r["spatial_status"] == "point_exact_fips" for r in rows),
               "soy_pixels_all395": sum(r["soy_pixels"] for r in rows),
               "positive_unmapped_counties": [r["county_fips5"] for r in positive_rows if not r["positive_mass_mapped"]],
               "us_q2019": q_us, "original391_state_count": len(selected),
               "observed_progress_production_share": q_observed / q_us,
               "outside_original391_progress_unknown_production_share": (q_us - q_observed) / q_us,
               "observed_production_times_progress_proxy_mass": math.fsum(e["w"] * e["g"] for e in state_exposure.values()),
               "observed_mapped_production_times_progress_mass": math.fsum(s["w"] * s["g"] * (s["mapped_pixel_share"] or 0.) for s in selected),
               "covered_component_degC_day": covered,
               "covered_component_identity_abs_error": abs(covered["weighted_new_component"] - covered["weighted_old_component"] - covered["weighted_revision_component"]),
               "full_observed_national_old_heat": None, "full_observed_national_new_heat": None,
               "full_observed_national_heat_revision": None,
               "national_unknown_reason": "Progress/g is not observed outside original18states; never treat missing as zero or renormalize coverage.",
               "positive_mass_nearest_grid_distance_max_degrees": max(r["distance_degrees"] for r in positive_rows if r["distance_degrees"] is not None),
               "qualifications": {"strict_first_seen": False, "field_crop_location": False,
                                  "crop_damage_or_tonnage": False, "alpha": False,
                                  "higher_net_return_lower_drawdown": False, "increased_betting": False,
                                  "production": False},
               "execution": {"fits": 0, "cash_backtests": 0, "predictions": 0,
                             "network": 0, "market_api": 0, "sql": 0, "risk_change": 0}}
    with (out / "county_heat_rows.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    dump(out / "state_heat_components.json", states)
    dump(out / "summary.json", summary)
    receipt = {"schema": "stage397_actual_single_case_receipt_v1", "terminal_status": "complete",
               "finished_at": datetime.now(timezone.utc).isoformat(),
               "elapsed_seconds": time.monotonic() - start,
               "protocol": binding(ROOT / "protocol.json"), "source": binding(__file__),
               "inputs": protocol["sources"],
               "outputs": [binding(out / name) for name in ("county_heat_rows.jsonl", "state_heat_components.json", "summary.json")],
               "execution": summary["execution"]}
    dump(out / "receipt.json", receipt)
    print(json.dumps({"receipt": binding(out / "receipt.json"), "summary": summary}, allow_nan=False))


if __name__ == "__main__":
    run()
