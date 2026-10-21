"""Bounded u21/D22 metadata-only extension of unchanged Stage353 code.

No quote SDK, price, account, score, model, SQL, or permanent calendar service.
The only optional HTTP request archives one already located SHFE holiday page.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import FunctionType
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

LINE = Path(__file__).resolve().parents[1]
SCOPE_SHA = "69cbc7ff9ff16bb0b46ec3704f6add980c33a4777f96eea4c353579ee117d9da"
ORIGINAL353 = {"path": str(LINE / "tools/stage353_regular_sessions.py"), "bytes": 6387,
               "sha256": "5ef528aa1265e9737a55e41601cb349664574436f712115267a2e39ecd71b650"}
ANCHORS = {"2026-10-21": "2026-10-20", "2026-10-22": "2026-10-21"}
SHFE_URL = "https://www.shfe.com.cn/services/calenderandholidays/holiday/"
CHINA = ZoneInfo("Asia/Shanghai")


def now():
    return datetime.now(timezone.utc).isoformat()


def binding(path, body=None):
    path = Path(path).resolve()
    data = path.read_bytes() if body is None else body
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def bound(ref):
    body = Path(ref["path"]).read_bytes()
    if binding(ref["path"], body) != ref:
        raise ValueError("bound input changed: " + ref["path"])
    return body


def write(path, value):
    data = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(data)
    return binding(path, data)


def isolated353_view():
    bound(ORIGINAL353)
    spec = importlib.util.spec_from_file_location("stage420_original353", ORIGINAL353["path"])
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    before = dict(original.ANCHORS)
    private_globals = dict(original.expand_sessions.__globals__)
    private_globals["ANCHORS"] = dict(ANCHORS)
    function = original.expand_sessions
    view = FunctionType(function.__code__, private_globals, function.__name__, function.__defaults__, function.__closure__)
    view.__kwdefaults__ = dict(function.__kwdefaults__ or {})
    return original, view, before


def one_fixture(original, view, calendar):
    metadata = {"symbol": "SYNTHETIC.fixture", "metadata_received": True,
                "day": [["09:00:00", "15:00:00"]], "night": [["21:00:00", "26:30:00"]],
                "expire_datetime": datetime(2027, 1, 1, 15, tzinfo=CHINA).timestamp(),
                "source_receipt": {"synthetic_only": True}}
    evidence = {"policy": "operational_regular_schedule", "source_receipt": {"synthetic_only": True}}
    kw = {"calendar": calendar, "night_anchors": ANCHORS, "evidence": evidence}
    old22 = original.expand_sessions(metadata, "2026-10-22", **kw)
    new22 = view(metadata, "2026-10-22", **kw)
    outside = view(metadata, "2026-10-23", **kw)
    expiring = dict(metadata, expire_datetime=datetime(2026, 10, 21, 15, tzinfo=CHINA).timestamp())
    last = view(expiring, "2026-10-21", **kw)
    expired = view(expiring, "2026-10-22", **kw)
    tests = {
        "original353_still_rejects22": old22["reasons"] == ["date_outside_fixed_scope"],
        "isolated22_uses21_night_anchor": new22["state"] == "operational_regular_schedule" and new22["night_anchor"] == "2026-10-21" and new22["first_open"] == "2026-10-21T21:00:00+08:00",
        "night26h30_spans_next_civil_day": new22["intervals"][0]["end"] == "2026-10-22T02:30:00+08:00",
        "outside23_remains_unknown": outside["reasons"] == ["date_outside_fixed_scope"],
        "lastday21_remains_unknown": last["state"] == "unknown" and last["reasons"] == ["last_day_override_missing"] and last["session_end"] is None,
        "after_expiry22_expired_not_unknown_or_active": expired["state"] == "expired" and expired["first_open"] is None,
    }
    if not all(tests.values()):
        raise ValueError("single bounded next-date fixture failed: " + repr(tests))
    return {"schema": "stage420_single_synthetic_metadata_fixture_v1", "at": now(), "tests": tests,
            "all_passed": True, "actual_metadata_expansion_calls": 0, "financial_data": False}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def one_shfe_original(out):
    record = {"schema": "stage420_single_official_holiday_HTML_v1", "url": SHFE_URL, "started_at": now(),
              "GET": 1, "retry": 0, "redirect": 0, "max_body_bytes": 1048576, "timeout_seconds": 20}
    body = b""
    try:
        req = urllib.request.Request(SHFE_URL, headers={"User-Agent": "fian-bounded-date-evidence/420", "Accept-Encoding": "identity"})
        try:
            response = urllib.request.build_opener(NoRedirect()).open(req, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            record["status"] = response.code
            record["content_type"] = response.headers.get("Content-Type")
            length = response.headers.get("Content-Length")
            if length and int(length) > 1048576:
                raise ValueError("declared HTML exceeds fixed1MiB cap")
            body = response.read(1048577)
            if len(body) > 1048576:
                raise ValueError("actual HTML exceeds fixed1MiB cap")
            record["ok"] = response.code == 200
    except Exception as error:
        record.update(ok=False, error_type=type(error).__name__, error=str(error))
    path = out / "official_shfe_2026_holiday.html"
    with path.open("xb") as handle:
        handle.write(body)
    record.update(ended_at=now(), body=binding(path, body), permanent_calendar_service=False,
                  coverage="SHFE annual holidays only; not all venue/date exceptions; no automatic lastday override")
    return write(out / "official_shfe_receipt.json", record)


def run(scope_path, output, acquire_shfe):
    start = now()
    scope_ref = binding(scope_path)
    if scope_ref["sha256"] != SCOPE_SHA:
        raise ValueError("root418 scope changed")
    scope = json.loads(bound(scope_ref))
    if scope["implementation_authorized"] is not True or scope["market_execution_authorized_now"] is not False:
        raise ValueError("exact metadata-only418 authorization required")
    if (scope["day"]["u_date"], scope["day"]["D_date"]) != tuple(ANCHORS):
        raise ValueError("explicit u21/D22 scope required")
    out = Path(output).resolve()
    if out != LINE / "outputs/stage420_next_sessions":
        raise ValueError("fixed420 output required")
    out.mkdir(parents=True, exist_ok=False)
    calendar_ref, identity_ref = scope["received_recent_calendar"], scope["identity"]
    calendar = json.loads(bound(calendar_ref))
    if not all(calendar["days"].get(d) is True for d in ("2026-10-20", *ANCHORS)):
        raise ValueError("explicit received calendar true required, not weekday inference")
    identity = json.loads(bound(identity_ref))
    metadata_ref = identity["source"]
    metadata = json.loads(bound(metadata_ref))
    symbols = sorted(metadata["items"])
    if len(symbols) != 874 or set(identity["identity_map"]) != set(symbols):
        raise ValueError("original complete874 identity and metadata domain required")
    original, view, original_anchors = isolated353_view()
    fixture_ref = write(out / "fixture_receipt.json", one_fixture(original, view, calendar["days"]))
    holiday_ref = one_shfe_original(out) if acquire_shfe else None
    regular = {"schema": "stage420_bounded_regular_date_evidence_v1", "policy": "operational_regular_schedule",
               "dates": list(ANCHORS), "night_anchor": ANCHORS, "calendar": calendar_ref, "metadata": metadata_ref,
               "original353": ORIGINAL353, "official_shfe": holiday_ref,
               "assurance": "received source calendar + observed periodic template, conditional on no conflicting override; not exhaustive exception search or vendor finality"}
    regular_ref = write(out / "regular_evidence.json", regular)
    evidence = {"policy": "operational_regular_schedule", "source_receipt": regular_ref}
    rows, lifecycle = [], {}
    before_date = scope["day"]["u_date"]
    old_summary = json.loads((LINE / "outputs/stage354_offline_sessions_actual/actual_run1/summary.json").read_text())
    old_dependencies = set(old_summary["dependency_symbols"])
    unknowns, upper_candidates = [], []
    for symbol in symbols:
        item = metadata["items"][symbol]
        f = item["fields"]
        received = item.get("response_matches_requested_symbol") is True and f["instrument_id"]["value"] == symbol and f["exchange_id"]["value"] == symbol.split(".")[0] and all(f[k]["state"] == "known" for k in ("instrument_id", "exchange_id", "ins_class", "trading_time.day", "trading_time.night", "expire_datetime"))
        meta = {"symbol": symbol, "metadata_received": received, "day": f["trading_time.day"]["value"], "night": f["trading_time.night"]["value"], "expire_datetime": f["expire_datetime"]["value"], "source_receipt": {"metadata": metadata_ref, "receiver321": metadata["receipt"]}}
        expiry = meta["expire_datetime"]
        stamp = datetime.fromtimestamp(expiry, CHINA) if isinstance(expiry, (float, int)) and not isinstance(expiry, bool) and math.isfinite(expiry) else None
        life = {"symbol": symbol, "epoch": identity["identity_map"][symbol], "original_expire_datetime": f["expire_datetime"], "expiry_day": stamp.date().isoformat() if stamp else None, "expiry_timestamp_as_received": stamp.isoformat() if stamp else None, "expiry_timestamp_is_confirmed_session_end": False, "metadata_received_at": metadata["receipt"]["recorded_at"], "old726_dependency": symbol in old_dependencies, "dates": {}}
        for day in ANCHORS:
            row = view(meta, day, calendar=calendar["days"], night_anchors=ANCHORS, evidence=evidence)
            rows.append(row)
            relation = "unknown" if stamp is None else "before_expiry_day" if day < life["expiry_day"] else "on_expiry_day" if day == life["expiry_day"] else "after_expiry_day"
            life["dates"][day] = {"relation": relation, "session_state": row["state"], "reasons": row["reasons"], "entry_after_expiry_known_ineligible": relation == "after_expiry_day"}
            if row["state"] == "unknown":
                unknowns.append({"symbol": symbol, "date": day, "reasons": row["reasons"], "old726_dependency": symbol in old_dependencies})
            if day == before_date and "last_day_override_missing" in row["reasons"]:
                upper_candidates.append({"symbol": symbol, "venue": symbol.split(".")[0], "epoch": life["epoch"], "old726_dependency": symbol in old_dependencies, "expiry_timestamp_as_received": life["expiry_timestamp_as_received"], "regular_day_template": meta["day"], "candidate_end_upper_bound": day + "T15:00:00+08:00", "accepted_as_clock": False, "is_exact_session_end": False, "conditions": "Only if normal venue day-end remains an upper bound; official other-hours/temporary exceptions not exhaustively excluded. No current420 clock override."})
        lifecycle[symbol] = life
    if len(rows) != 1748 or original.ANCHORS != original_anchors or view.__code__ is not original.expand_sessions.__code__:
        raise ValueError("fixed1748 domain/original353 globals/code invariant violated")
    raw = ("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True, allow_nan=False) for r in rows) + "\n").encode()
    compressed = gzip.compress(raw, compresslevel=1, mtime=0)
    sessions_path = out / "sessions.jsonl.gz"
    with sessions_path.open("xb") as handle:
        handle.write(compressed)
    sessions_ref = binding(sessions_path, compressed)
    lifecycle_ref = write(out / "lifecycle.json", {"schema": "stage420_contract_lifecycle_v1", "metadata": metadata_ref, "identity": identity_ref, "items": lifecycle, "price_or_entry_eligibility_qualified": False})
    candidates_ref = write(out / "lastday_source_end_candidates.json", {"schema": "stage420_unaccepted_lastday_upper_bound_candidates_v1", "candidates": upper_candidates, "unknowns": unknowns, "state_or_clock_changes": 0, "decision": "root must distinguish any conditional upper-bound rule from exact session overrides;420 accepts neither"})
    if binding(ORIGINAL353["path"]) != ORIGINAL353:
        raise ValueError("old353 bytes changed")
    refs = {"scope": scope_ref, "calendar": calendar_ref, "identity": identity_ref, "metadata": metadata_ref, "original353": ORIGINAL353, "regular_evidence": regular_ref, "sessions": sessions_ref, "lifecycle": lifecycle_ref, "lastday_candidates": candidates_ref, "fixture": fixture_ref}
    result = {"schema": "stage420_next_sessions_manifest_v1", "status": "completed_metadata_only_with_explicit_unknowns", "started_at": start, "completed_at": now(), "u_date": scope["day"]["u_date"], "D_date": scope["day"]["D_date"], "bindings": refs, "symbols": 874, "session_rows": 1748, "date_states": {d: dict(Counter(r["state"] for r in rows if r["trade_date"] == d)) for d in ANCHORS}, "unknown_sessions": unknowns, "lastday_candidate_count": len(upper_candidates), "lastday_old726_dependency_count": sum(r["old726_dependency"] for r in upper_candidates), "identity_count": len(identity["identity_map"]), "original353_function_code_identity_preserved": True, "original353_module_anchors_unchanged": True, "private_anchors": ANCHORS, "lastday_upper_bounds_accepted": False, "new_eligibility_not_inherited_from_u20": True, "all98products95families_retained": True, "official_SHFE_HTTP_receipt": holiday_ref, "new_API": 0, "new_calendar_API": 0, "price_reads": 0, "score": 0, "fit": 0, "cash": 0, "financial_D": 0, "SQL": 0, "state_mutation": 0, "source_completed_at_assigned": False, "D_open_at_assigned": False, "venue_finality": "unknown", "no_exhaustive_date_exception_claim": True, "tool": binding(Path(__file__))}
    write(out / "manifest.json", result)
    print(json.dumps({k: result[k] for k in ("status", "symbols", "session_rows", "date_states", "lastday_candidate_count", "lastday_old726_dependency_count")}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scope", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--acquire-shfe-raw", action="store_true")
    args = p.parse_args()
    run(Path(args.scope).resolve(), args.output, args.acquire_shfe_raw)
