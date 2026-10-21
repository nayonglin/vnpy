"""One-shot frozen Stage390 physical same-valid-time heat revision."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import threading
import traceback
import urllib.error
import urllib.request

LINE = Path(__file__).resolve().parents[1]
DEPS = LINE / "outputs/stage388_weather_mechanism_feasibility/deps"
sys.path.insert(0, str(DEPS))
import numpy as np

ROOT = LINE / "outputs/stage390_same_valid_heat_revision"
ACTUAL = ROOT / "actual_run2"
PROTOCOL_SHA = "e7ee6cb240cb74fcb251cbdec126ebd58dba59c6c59aba4cb2d3f16c0c84bfe9"
HOST = "https://noaa-gefs-pds.s3.amazonaws.com/"
STOP = threading.Event()
LOCK = threading.Lock()
COUNTS = {"idx": 0, "range": 0, "weather": 0, "body_reserved_bytes": 0}
PRIOR_SOURCE_REQUESTS = 10
PRIOR_SOURCE_BODY_BYTES = 13320


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def binding(path):
    body = path.read_bytes()
    return {"path": str(path), "bytes": len(body), "sha256": sha(body)}


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def integrate_heat(temperatures_K):
    values = np.asarray(temperatures_K, dtype="float64")
    if values.ndim != 2 or len(values) < 2:
        raise ValueError("heat integration requires time x native-grid arrays")
    missing = ~np.isfinite(values).all(axis=0)
    excess = np.maximum(values - 273.15 - 30.0, 0.0)
    result = np.sum((excess[:-1] + excess[1:]) * 0.5, axis=0) * (6.0 / 24.0)
    result[missing] = np.nan
    return result, missing


def require_same_grid(left, right):
    if (left["metadata"] != right["metadata"] or
            not np.array_equal(left["latitudes"], right["latitudes"]) or
            not np.array_equal(left["longitudes"], right["longitudes"])):
        raise ValueError("native grid equality failed; no regrid is permitted")


def paired_heat(old_K, new_K, old_grid, new_grid):
    require_same_grid(old_grid, new_grid)
    if np.shape(old_K) != np.shape(new_K):
        raise ValueError("same-valid-time old/new shapes differ")
    old, old_missing = integrate_heat(old_K)
    new, new_missing = integrate_heat(new_K)
    unknown = old_missing | new_missing
    revision = new - old
    revision[unknown] = np.nan
    return {"old_EDD": old, "new_EDD": new, "revision_EDD": revision,
            "old_missing": old_missing, "new_missing": new_missing, "revision_missing": unknown}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(key, path, category, byte_range=None):
    if STOP.is_set():
        raise RuntimeError("stopped after first actual failure; no new request")
    with LOCK:
        if COUNTS["weather"] + PRIOR_SOURCE_REQUESTS >= 126 or COUNTS[category] >= 58:
            raise RuntimeError("frozen request budget exhausted")
        COUNTS["weather"] += 1
        COUNTS[category] += 1
        seq = COUNTS["weather"]
    cap = 32768 if category == "idx" else 524288
    headers = {} if byte_range is None else {"Range": f"bytes={byte_range[0]}-{byte_range[1]}"}
    receipt = {"sequence": seq, "started_at": now(), "url": HOST + key,
               "request_headers": headers, "category": category, "retry": 0, "redirect": 0, "cap": cap}
    save_json(path.with_suffix(path.suffix + ".request.json"), receipt)
    body = b""
    try:
        opener = urllib.request.build_opener(NoRedirect())
        request = urllib.request.Request(HOST + key, headers=headers)
        with opener.open(request, timeout=30) as response:
            receipt["status"] = response.status
            receipt["response_headers"] = dict(response.headers)
            expected = 200 if category == "idx" else 206
            if response.status != expected:
                raise RuntimeError(f"expected HTTP{expected}, got {response.status}; no body consumed")
            size = int(response.headers["Content-Length"])
            if not 0 < size <= cap:
                raise RuntimeError(f"declared body size outside bound: {size}")
            if byte_range is not None:
                first, last = byte_range
                prefix = f"bytes {first}-{last}/"
                content_range = response.headers.get("Content-Range", "")
                if not content_range.startswith(prefix) or size != last - first + 1:
                    raise RuntimeError(f"inexact Content-Range/length: {content_range}")
                total = int(content_range[len(prefix):])
                if total <= last:
                    raise RuntimeError("invalid total object length")
                receipt["full_object_bytes"] = total
            with LOCK:
                if COUNTS["body_reserved_bytes"] + size + PRIOR_SOURCE_BODY_BYTES > 32309248:
                    raise RuntimeError("total weather body budget exceeded")
                COUNTS["body_reserved_bytes"] += size
            body = response.read(size)
            if len(body) != size:
                raise RuntimeError(f"short response {len(body)} vs {size}")
        receipt["status_check"] = "passed"
        return body
    except urllib.error.HTTPError as error:
        STOP.set()
        receipt["status"] = error.code
        receipt["response_headers"] = dict(error.headers)
        with LOCK:
            allowance = max(0, min(4096, cap, 32309248 - COUNTS["body_reserved_bytes"] - PRIOR_SOURCE_BODY_BYTES))
            COUNTS["body_reserved_bytes"] += allowance
        body = error.read(allowance)
        receipt["error"] = repr(error)
        raise
    except BaseException as error:
        STOP.set()
        receipt["error"] = repr(error)
        raise
    finally:
        path.write_bytes(body)
        receipt["body"] = binding(path)
        receipt["ended_at"] = now()
        save_json(path.with_suffix(path.suffix + ".response.json"), receipt)


def acquire(job):
    try:
        date = job["run"][:10].replace("-", "")
        key = f"gefs.{date}/00/pgrb2a/gec00.t00z.pgrb2af{job['lead']:02d}"
        tag = f"{job['side']}_{date}_f{job['lead']:03d}"
        index_path = ACTUAL / (tag + ".idx")
        index = fetch(key + ".idx", index_path, "idx")
        rows = [line.split(":") for line in index.decode("ascii").splitlines() if line]
        identity = [f"d={date}00", "TMP", "2 m above ground", f"{job['lead']} hour fcst"]
        matches = [(i, row) for i, row in enumerate(rows) if len(row) >= 7 and row[2:6] == identity]
        if len(matches) != 1:
            raise RuntimeError(f"exact TMP record count {len(matches)} for {tag}")
        i, row = matches[0]
        if i + 1 >= len(rows) or "ENS=low-res ctl" not in row:
            raise RuntimeError(f"control/next-offset identity missing for {tag}")
        first, stop = int(row[1]), int(rows[i + 1][1])
        if not 0 <= first < stop or stop - first > 524288:
            raise RuntimeError("single TMP message outside fixed byte budget")
        message_path = ACTUAL / (tag + "_TMP2m.grib2")
        fetch(key, message_path, "range", (first, stop - 1))
        return {"job": job, "data_key": key, "index": binding(index_path), "message": binding(message_path),
                "index_identity": {"record": ":".join(row), "next_record": ":".join(rows[i + 1]),
                                   "first": first, "last": stop - 1, "bytes": stop - first}}
    except BaseException:
        STOP.set()
        raise


def decode(field, ec):
    path = Path(field["message"]["path"])
    body = path.read_bytes()
    if (body[:4] != b"GRIB" or body[7] != 2 or body[-4:] != b"7777" or
            int.from_bytes(body[8:16], "big") != len(body) or len(body) != field["index_identity"]["bytes"]):
        raise RuntimeError("GRIB2/index/header/terminator mismatch")
    with path.open("rb") as file:
        gid = ec.codes_grib_new_from_file(file)
        if gid is None:
            raise RuntimeError("no GRIB message")
        try:
            keys = ["edition", "discipline", "parameterCategory", "parameterNumber", "shortName", "name", "units",
                    "typeOfLevel", "level", "dataDate", "dataTime", "validityDate", "validityTime", "stepType",
                    "startStep", "endStep", "stepUnits", "numberOfMissing", "missingValue", "bitmapPresent",
                    "numberOfPoints", "numberOfValues", "perturbationNumber", "typeOfEnsembleForecast"]
            meta = {key: ec.codes_get(gid, key) for key in keys}
            grid_keys = ["gridType", "Ni", "Nj", "numberOfPoints", "latitudeOfFirstGridPointInDegrees",
                         "longitudeOfFirstGridPointInDegrees", "latitudeOfLastGridPointInDegrees",
                         "longitudeOfLastGridPointInDegrees", "iDirectionIncrementInDegrees", "jDirectionIncrementInDegrees",
                         "iScansNegatively", "jScansPositively", "jPointsAreConsecutive", "alternativeRowScanning", "scanningMode"]
            grid_meta = {key: ec.codes_get(gid, key) for key in grid_keys}
            job = field["job"]
            run = dt.datetime.fromisoformat(job["run"].replace("Z", "+00:00"))
            valid = dt.datetime.fromisoformat(job["valid"].replace("Z", "+00:00"))
            checks = {"grib2": meta["edition"] == 2,
                      "temperature": (meta["discipline"], meta["parameterCategory"], meta["parameterNumber"]) == (0, 0, 0),
                      "unitK_height2m": meta["units"] == "K" and meta["typeOfLevel"] == "heightAboveGround" and meta["level"] == 2,
                      "run": meta["dataDate"] == int(run.strftime("%Y%m%d")) and meta["dataTime"] == 0,
                      "valid": meta["validityDate"] == int(valid.strftime("%Y%m%d")) and meta["validityTime"] == valid.hour * 100,
                      "instant_lead": meta["stepType"] == "instant" and meta["startStep"] == job["lead"] and meta["endStep"] == job["lead"] and meta["stepUnits"] == 1,
                      "lead_to_valid": valid - run == dt.timedelta(hours=job["lead"]),
                      "control_member": meta["perturbationNumber"] == 0 and meta["typeOfEnsembleForecast"] == 1}
            if not all(checks.values()):
                raise RuntimeError(f"decoded fixed identity failure {checks!r}; {meta!r}")
            values = np.asarray(ec.codes_get_values(gid), dtype="float64")
            latitudes = np.asarray(ec.codes_get_array(gid, "latitudes"), dtype="float64")
            longitudes = np.asarray(ec.codes_get_array(gid, "longitudes"), dtype="float64")
            if len(values) != len(latitudes) or len(values) != len(longitudes) or len(values) != meta["numberOfPoints"]:
                raise RuntimeError("grid/array count mismatch")
            missing = ~np.isfinite(values) | (values == float(meta["missingValue"]))
            if int(missing.sum()) != meta["numberOfMissing"]:
                raise RuntimeError("explicit missing count mismatch")
            if not np.isfinite(latitudes).all() or not np.isfinite(longitudes).all():
                raise RuntimeError("nonfinite native grid coordinates")
            present = values[~missing]
            if len(present) and not (100 <= present.min() <= present.max() <= 400):
                raise RuntimeError("decoded temperature outside broad100..400K sanity range")
            values[missing] = np.nan
            grid = {"metadata": grid_meta, "latitudes": latitudes, "longitudes": longitudes}
            field["decoded"] = {"metadata": meta, "grid_metadata": grid_meta, "checks": checks,
                                "missing_count": int(missing.sum()), "minimum_K": float(present.min()) if len(present) else None,
                                "maximum_K": float(present.max()) if len(present) else None}
        finally:
            ec.codes_release(gid)
        extra = ec.codes_grib_new_from_file(file)
        if extra is not None:
            ec.codes_release(extra)
            raise RuntimeError("multiple messages in extracted Range")
    return field, grid, values


def finite_summary(array):
    finite = array[np.isfinite(array)]
    return {"finite": int(len(finite)), "missing": int(len(array) - len(finite)),
            "minimum": float(finite.min()) if len(finite) else None,
            "maximum": float(finite.max()) if len(finite) else None,
            "mean": float(finite.mean()) if len(finite) else None}


def main():
    protocol_path = ROOT / "protocol.json"
    if sha(protocol_path.read_bytes()) != PROTOCOL_SHA:
        raise RuntimeError("frozen Stage390 protocol changed")
    if ACTUAL.exists():
        raise RuntimeError("one-shot actual_run2 already exists; no retry")
    source_path = ROOT / "prepare2/source_freeze2.json"
    source = json.loads(source_path.read_text())
    if source["script"]["sha256"] != sha(Path(__file__).read_bytes()):
        raise RuntimeError("actual script differs from pre-actual source freeze")
    ACTUAL.mkdir()
    manifest = {"schema": "stage390_same_valid_single_control_heat_revision_actual_v1", "started_at": now(),
                "status": "started", "protocol": binding(protocol_path), "source_freeze": binding(source_path),
                "locator_amendment": binding(ROOT / "locator_amendment.json"),
                "fields": [], "financial": {"fit": 0, "cash": 0, "market_API": 0, "SQL": 0},
                "whole_goal_achieved": False, "single_control_not_ensemble": True,
                "strict_historical_first_seen": False}
    save_json(ACTUAL / "manifest.json", manifest)
    try:
        import eccodes as ec
        if ec.codes_get_api_version() != "2.50.0":
            raise RuntimeError("unexpected existing388 decoder version")
        manifest["native_decoder_version"] = ec.codes_get_api_version()
        case = json.loads(protocol_path.read_text())["case"]
        v0 = dt.datetime.fromisoformat(case["valid_start"].replace("Z", "+00:00"))
        validtimes = [(v0 + dt.timedelta(hours=6 * i)).isoformat().replace("+00:00", "Z") for i in range(29)]
        if validtimes[-1] != case["valid_end"]:
            raise RuntimeError("fixed29 validtime knots do not close declared interval")
        jobs = [{"side": side, "knot": i, "run": case[f"{side}_run"], "lead": case[f"{side}_leads"][i], "valid": valid}
                for i, valid in enumerate(validtimes) for side in ("old", "new")]
        fields = {"old": {}, "new": {}}
        reference_grid = None
        errors = []
        iterator = iter(jobs)
        with ThreadPoolExecutor(max_workers=4) as pool:
            pending = {pool.submit(acquire, next(iterator)): None for _ in range(4)}
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    pending.pop(future)
                    try:
                        acquired = future.result()
                        field, grid, values = decode(acquired, ec)
                        manifest["fields"].append(field)
                        if reference_grid is None:
                            reference_grid = grid
                        else:
                            require_same_grid(reference_grid, grid)
                        fields[field["job"]["side"]][field["job"]["knot"]] = values
                    except BaseException as error:
                        STOP.set()
                        errors.append({"error": repr(error), "traceback": traceback.format_exc()})
                    save_json(ACTUAL / "manifest.json", manifest)
                if not STOP.is_set():
                    for _ in range(len(done)):
                        job = next(iterator, None)
                        if job is not None:
                            pending[pool.submit(acquire, job)] = None
        if errors:
            manifest["field_errors"] = errors
            raise RuntimeError("fixed actual failed; all in-flight work drained, no replacement/retry")
        if len(manifest["fields"]) != 58 or any(len(fields[side]) != 29 for side in ("old", "new")):
            raise RuntimeError("incomplete fixed58 source fields")
        old = np.stack([fields["old"][i] for i in range(29)])
        new = np.stack([fields["new"][i] for i in range(29)])
        result = paired_heat(old, new, reference_grid, reference_grid)
        array_path = ACTUAL / "native_heat_revision.npz"
        np.savez(array_path, **result, latitudes=reference_grid["latitudes"], longitudes=reference_grid["longitudes"],
                 validtimes_utc=np.array(validtimes, dtype="U20"))
        manifest["native_arrays"] = binding(array_path)
        manifest["validtimes"] = validtimes
        manifest["grid_metadata"] = reference_grid["metadata"]
        manifest["summaries_EDD_C_days"] = {key: finite_summary(result[key]) for key in ("old_EDD", "new_EDD", "revision_EDD")}
        anchors = []
        lats, lons = reference_grid["latitudes"], reference_grid["longitudes"]
        for label, latitude, longitude in (("IA", 42., -93.), ("IL", 40., -89.)):
            cosine = (np.sin(np.deg2rad(lats)) * np.sin(np.deg2rad(latitude)) +
                      np.cos(np.deg2rad(lats)) * np.cos(np.deg2rad(latitude)) * np.cos(np.deg2rad(lons - longitude)))
            k = int(np.argmax(cosine))
            anchor = {"label": label, "requested_lat": latitude, "requested_lon": longitude,
                      "flat_index": k, "grid_lat": float(lats[k]), "grid_lon": float(lons[k]),
                      "old_temperatures_C": [float(v - 273.15) if np.isfinite(v) else None for v in old[:, k]],
                      "new_temperatures_C": [float(v - 273.15) if np.isfinite(v) else None for v in new[:, k]]}
            for key, values in result.items():
                anchor[key] = bool(values[k]) if values.dtype == bool else float(values[k]) if np.isfinite(values[k]) else None
            anchors.append(anchor)
        manifest["anchors"] = anchors
        manifest["status"] = "passed"
        manifest["limitations"] = ["native single-control fixed7day forecast heat-load proxy; no crop/production/ensemble aggregation",
                                   "37h initialization lag is historical reconstruction assumption, not a proven publication SLA",
                                   "no price/label/PnL or cost-after advantage tested"]
    except BaseException as error:
        STOP.set()
        manifest["status"] = "failed"
        manifest["error"] = repr(error)
        manifest["traceback"] = traceback.format_exc()
        raise
    finally:
        manifest["ended_at"] = now()
        manifest["counts"] = dict(COUNTS)
        manifest["cumulative_source_requests"] = PRIOR_SOURCE_REQUESTS + COUNTS["weather"]
        responses = sorted(ACTUAL.glob("*.response.json"))
        manifest["responses"] = [binding(path) for path in responses]
        manifest["weather_body_bytes"] = sum(json.loads(path.read_text())["body"]["bytes"] for path in responses)
        manifest["cumulative_source_body_bytes"] = PRIOR_SOURCE_BODY_BYTES + manifest["weather_body_bytes"]
        save_json(ACTUAL / "manifest.json", manifest)
        print(json.dumps({"status": manifest["status"], "decoded_fields": len(manifest["fields"]),
                          "counts": COUNTS, "weather_body_bytes": manifest["weather_body_bytes"],
                          "manifest": str(ACTUAL / "manifest.json")}), flush=True)


if __name__ == "__main__":
    main()
