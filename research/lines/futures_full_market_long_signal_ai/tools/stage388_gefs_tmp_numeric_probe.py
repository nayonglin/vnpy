"""One-shot Stage388 probe: two fixed GEFS f024 2m-TMP messages only."""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import traceback
import urllib.error
import urllib.request


LINE = Path(__file__).resolve().parents[1]
ROOT = LINE / "outputs/stage388_weather_mechanism_feasibility"
OUT = ROOT / "actual_run1"
DEPS = ROOT / "deps"
PROTOCOL_SHA = "400124ab9827746fd848e6e46447a2b7c514857693c7a65eec73f33c5920089e"
HOST = "https://noaa-gefs-pds.s3.amazonaws.com/"
ANCHORS = (("IA", 42.0, -93.0), ("IL", 40.0, -89.0))
EVENTS: list[dict] = []


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n")


def binding(path: Path) -> dict:
    body = path.read_bytes()
    return {"path": str(path), "bytes": len(body), "sha256": sha(body)}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(key: str, name: str, cap: int, byte_range: tuple[int, int] | None = None) -> bytes:
    """No retry/redirect, persist body and response before validating/decoding."""
    if len(EVENTS) >= 4:
        raise RuntimeError("fixed four-request weather budget exhausted")
    headers = {} if byte_range is None else {"Range": f"bytes={byte_range[0]}-{byte_range[1]}"}
    event = {"sequence": len(EVENTS) + 1, "started_at": now(), "url": HOST + key,
             "request_headers": headers, "max_body_bytes": cap, "retry": 0}
    EVENTS.append(event)
    write_json(OUT / "weather_requests.json", EVENTS)
    print(json.dumps({"event": "weather_request_started", **event}), flush=True)
    body = b""
    try:
        request = urllib.request.Request(HOST + key, headers=headers)
        opener = urllib.request.build_opener(NoRedirect())
        with opener.open(request, timeout=30) as response:
            event["status"] = response.status
            event["response_headers"] = dict(response.headers)
            expected_status = 200 if byte_range is None else 206
            if response.status != expected_status:
                # In particular, never consume a full GRIB object after HTTP200.
                raise RuntimeError(f"expected HTTP{expected_status}, received {response.status}; body not consumed")
            size = int(response.headers["Content-Length"])
            if not 0 < size <= cap:
                raise RuntimeError(f"unacceptable declared body size {size}")
            if byte_range is not None:
                first, last = byte_range
                expected_prefix = f"bytes {first}-{last}/"
                content_range = response.headers.get("Content-Range", "")
                if not content_range.startswith(expected_prefix):
                    raise RuntimeError(f"incorrect Content-Range {content_range!r}")
                total = int(content_range[len(expected_prefix):])
                if total <= last or size != last - first + 1:
                    raise RuntimeError("Content-Range/length not exact")
                event["full_object_bytes"] = total
            body = response.read(size)
            if len(body) != size:
                raise RuntimeError(f"short response {len(body)} != {size}")
        event["status_check"] = "passed"
        return body
    except urllib.error.HTTPError as error:
        event["status"] = error.code
        event["response_headers"] = dict(error.headers)
        # Small failure body retained; no data object is read on HTTP200.
        body = error.read(min(cap, 4096))
        event["error"] = repr(error)
        raise
    except BaseException as error:
        event["error"] = repr(error)
        raise
    finally:
        body_path = OUT / name
        body_path.write_bytes(body)
        event["body"] = binding(body_path)
        event["ended_at"] = now()
        write_json(OUT / f"{name}.response.json", event)
        write_json(OUT / "weather_requests.json", EVENTS)


def tmp_identity(index: bytes, run: str) -> tuple[dict, int, int]:
    rows = [line.split(":") for line in index.decode("ascii").splitlines() if line]
    expected_run = dt.datetime.fromisoformat(run.replace("Z", "+00:00")).strftime("d=%Y%m%d%H")
    matches = [(i, row) for i, row in enumerate(rows) if len(row) >= 7 and
               row[2:6] == [expected_run, "TMP", "2 m above ground", "24 hour fcst"]]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one fixed TMP2m record, got {len(matches)}")
    i, row = matches[0]
    if i + 1 >= len(rows):
        raise RuntimeError("TMP must have explicit next-record offset")
    if "ENS=low-res ctl" not in row:
        raise RuntimeError("index member is not fixed low-resolution control")
    first, stop = int(row[1]), int(rows[i + 1][1])
    if not 0 <= first < stop or stop - first > 524288:
        raise RuntimeError("invalid or oversized single-message offset")
    return {"record": ":".join(row), "next_record": ":".join(rows[i + 1]),
            "offset": first, "inclusive_last": stop - 1, "message_bytes": stop - first}, first, stop


def dependency_manifest(ec) -> dict:
    report_path = OUT / "dependency_install_report.json"
    report = json.loads(report_path.read_text())
    wheels = [{"name": item["metadata"]["name"], "version": item["metadata"]["version"],
               "download_info": item["download_info"]} for item in report["install"]]
    distributions = []
    for dist in importlib.metadata.distributions(path=[str(DEPS)]):
        records = [Path(dist.locate_file(file)) for file in (dist.files or [])
                   if str(file).endswith(".dist-info/RECORD")]
        distributions.append({"name": dist.metadata["Name"], "version": dist.version,
                              "record_bindings": [binding(path) for path in records]})
    return {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "target": str(DEPS), "eccodes_module": binding(Path(ec.__file__)),
            "native_eccodes_version": ec.codes_get_api_version(),
            "install_report": binding(report_path), "wheel_sources_and_hashes": wheels,
            "installed_distributions": sorted(distributions, key=lambda row: row["name"])}


def decode(path: Path, sample: dict, index_identity: dict, ec, np) -> dict:
    body = path.read_bytes()
    if body[:4] != b"GRIB" or body[7] != 2 or body[-4:] != b"7777":
        raise RuntimeError("GRIB2 header/terminator failure")
    if int.from_bytes(body[8:16], "big") != len(body) or len(body) != index_identity["message_bytes"]:
        raise RuntimeError("header/index/body message length mismatch")
    with path.open("rb") as file:
        gid = ec.codes_grib_new_from_file(file)
        if gid is None:
            raise RuntimeError("decoder returned no message")
        try:
            required_keys = ["edition", "discipline", "parameterCategory", "parameterNumber", "shortName", "name",
                             "units", "typeOfLevel", "level", "dataDate", "dataTime", "validityDate", "validityTime",
                             "stepType", "startStep", "endStep", "stepUnits", "gridType", "numberOfPoints",
                             "numberOfValues", "numberOfMissing", "bitmapPresent", "missingValue"]
            meta = {key: ec.codes_get(gid, key) for key in required_keys}
            optional_keys = ["Ni", "Nj", "latitudeOfFirstGridPointInDegrees", "longitudeOfFirstGridPointInDegrees",
                             "latitudeOfLastGridPointInDegrees", "longitudeOfLastGridPointInDegrees",
                             "iDirectionIncrementInDegrees", "jDirectionIncrementInDegrees", "iScansNegatively",
                             "jScansPositively", "jPointsAreConsecutive", "alternativeRowScanning", "scanningMode",
                             "centre", "subCentre", "generatingProcessIdentifier", "typeOfGeneratingProcess",
                             "tablesVersion", "localTablesVersion", "perturbationNumber", "typeOfEnsembleForecast"]
            for key in optional_keys:
                try:
                    meta[key] = ec.codes_get(gid, key)
                except ec.CodesInternalError:
                    meta[key] = None
            run = dt.datetime.fromisoformat(sample["run"].replace("Z", "+00:00"))
            valid = dt.datetime.fromisoformat(sample["valid"].replace("Z", "+00:00"))
            checks = {"edition2": meta["edition"] == 2,
                      "temperature_parameter": (meta["discipline"], meta["parameterCategory"], meta["parameterNumber"]) == (0, 0, 0),
                      "unit_kelvin": meta["units"] == "K",
                      "height_2m": meta["typeOfLevel"] == "heightAboveGround" and meta["level"] == 2,
                      "run_identity": meta["dataDate"] == int(run.strftime("%Y%m%d")) and meta["dataTime"] == 0,
                      "valid_identity": meta["validityDate"] == int(valid.strftime("%Y%m%d")) and meta["validityTime"] == 0,
                      "instant_f024": meta["stepType"] == "instant" and meta["startStep"] == 24 and meta["endStep"] == 24 and meta["stepUnits"] == 1,
                      "run_plus24": valid - run == dt.timedelta(hours=24)}
            if not all(checks.values()):
                raise RuntimeError(f"decoded identity mismatch: {checks!r}; metadata={meta!r}")
            values = np.asarray(ec.codes_get_values(gid), dtype="float64")
            lats = np.asarray(ec.codes_get_array(gid, "latitudes"), dtype="float64")
            lons = np.asarray(ec.codes_get_array(gid, "longitudes"), dtype="float64")
            if not (len(values) == len(lats) == len(lons) == meta["numberOfPoints"]):
                raise RuntimeError("decoded array/grid count mismatch")
            missing = ~np.isfinite(values) | (values == float(meta["missingValue"]))
            missing_count = int(missing.sum())
            if missing_count != int(meta["numberOfMissing"]):
                raise RuntimeError("decoder missing count differs from explicit mask")
            if not np.isfinite(lats).all() or not np.isfinite(lons).all() or missing_count == len(values):
                raise RuntimeError("invalid coordinates or all values missing")
            present = values[~missing]
            vmin, vmax = float(present.min()), float(present.max())
            # Broad physical sanity bound fixed before decoding, not agronomic selection.
            if not (100 <= vmin <= vmax <= 400):
                raise RuntimeError(f"temperature outside broad [100,400] K sanity envelope: {vmin},{vmax}")
            coordinates = np.deg2rad(lats)
            anchors = []
            for label, alat, alon in ANCHORS:
                cos_angle = (np.sin(coordinates) * np.sin(np.deg2rad(alat)) +
                             np.cos(coordinates) * np.cos(np.deg2rad(alat)) * np.cos(np.deg2rad(lons - alon)))
                nearest = int(np.argmax(cos_angle))
                if missing[nearest]:
                    kelvin = celsius = None
                else:
                    kelvin = float(values[nearest])
                    celsius = kelvin - 273.15
                anchors.append({"anchor": label, "requested_lat": alat, "requested_lon": alon,
                                "nearest_flat_index": nearest, "grid_lat": float(lats[nearest]),
                                "grid_lon_0_360": float(lons[nearest]) % 360.0,
                                "grid_lon_minus180_180": (float(lons[nearest]) + 180.0) % 360.0 - 180.0,
                                "great_circle_distance_km": float(6371.0088 * np.arccos(np.clip(cos_angle[nearest], -1, 1))),
                                "missing": bool(missing[nearest]), "kelvin": kelvin, "celsius": celsius})
            result = {"metadata": meta, "identity_checks": checks, "array_count": len(values),
                      "missing_count": missing_count, "finite_present_count": len(present),
                      "sanity_bounds_K": [100, 400], "minimum_K": vmin, "maximum_K": vmax,
                      "minimum_C": vmin - 273.15, "maximum_C": vmax - 273.15,
                      "latitude_min": float(lats.min()), "latitude_max": float(lats.max()),
                      "longitude_min": float(lons.min()), "longitude_max": float(lons.max()),
                      "anchors": anchors, "nearest_method": "great-circle angle minimum; first flat index on exact tie; never skip a missing nearest point"}
        finally:
            ec.codes_release(gid)
        extra = ec.codes_grib_new_from_file(file)
        if extra is not None:
            ec.codes_release(extra)
            raise RuntimeError("more than one decoded GRIB message")
    return result


def main() -> None:
    if not OUT.is_dir() or (OUT / "numeric_receipt.json").exists() or (OUT / "weather_requests.json").exists():
        raise RuntimeError("one-shot actual_run1 must exist and be unattempted")
    protocol_path = ROOT / "protocol.json"
    if sha(protocol_path.read_bytes()) != PROTOCOL_SHA:
        raise RuntimeError("frozen protocol changed")
    protocol = json.loads(protocol_path.read_text())
    terminal = json.loads((OUT / "dependency_install_terminal.json").read_text())
    if terminal["returncode"] != 0:
        raise RuntimeError("isolated dependency installation failed; no weather requests permitted")
    receipt = {"schema": "stage388_fixed_tmp_numeric_receipt_v1", "started_at": now(),
               "protocol": binding(protocol_path), "probe_script": binding(Path(__file__).resolve()),
               "status": "started", "samples": [], "fit": 0, "cash": 0, "market_api": 0,
               "single_instant_not_EDD": True, "research_goal_achieved": False}
    write_json(OUT / "numeric_receipt.json", receipt)
    try:
        sys.path.insert(0, str(DEPS))
        import eccodes as ec
        import numpy as np
        dependencies = dependency_manifest(ec)
        write_json(OUT / "dependency_manifest.json", dependencies)
        receipt["dependencies"] = binding(OUT / "dependency_manifest.json")
        if importlib.metadata.version("eccodes") != "2.50.0":
            raise RuntimeError("wrong isolated eccodes Python package version")
        for sample in protocol["samples"]:
            tag = sample["run"][:10].replace("-", "") + "_00_f024"
            row = {"sample": sample, "status": "started"}
            receipt["samples"].append(row)
            write_json(OUT / "numeric_receipt.json", receipt)
            index_name = tag + ".idx"
            index = fetch(sample["data_key"] + ".idx", index_name, 32768)
            identity, first, stop = tmp_identity(index, sample["run"])
            row["index"] = binding(OUT / index_name)
            row["index_identity"] = identity
            message_name = tag + "_TMP2m.grib2"
            fetch(sample["data_key"], message_name, 524288, (first, stop - 1))
            row["message"] = binding(OUT / message_name)
            row["decoded"] = decode(OUT / message_name, sample, identity, ec, np)
            row["status"] = "passed"
            write_json(OUT / "numeric_receipt.json", receipt)
        receipt["status"] = "passed"
        receipt["limitations"] = ["two fixed single-control f024 instants only; not full ensemble or temporal heat integral",
                                  "no strict historical first-seen proof or financial/alpha qualification",
                                  "not a full-market weather feature dataset; no forecast revision computed"]
    except BaseException as error:
        receipt["status"] = "failed"
        receipt["error"] = repr(error)
        receipt["traceback"] = traceback.format_exc()
        raise
    finally:
        receipt["weather_request_count"] = len(EVENTS)
        receipt["weather_body_bytes"] = sum(event.get("body", {}).get("bytes", 0) for event in EVENTS)
        receipt["retry"] = 0
        receipt["ended_at"] = now()
        write_json(OUT / "numeric_receipt.json", receipt)
        print(json.dumps({"event": "numeric_probe_terminal", "status": receipt["status"],
                          "weather_request_count": len(EVENTS), "receipt": str(OUT / "numeric_receipt.json")}), flush=True)


if __name__ == "__main__":
    main()
