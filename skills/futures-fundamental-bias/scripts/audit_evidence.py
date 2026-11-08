"""Audit a manually verified public evidence bundle; never predict or trade."""
import argparse
from datetime import date, datetime, time, timedelta
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

AXES = {"supply", "demand", "inventory", "pricing", "policy", "macro", "positioning"}


def _timestamp(value, zone, date_available_next_day=False):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("time is missing")
    if len(value) == 10:
        instant = datetime.combine(date.fromisoformat(value), time(), zone)
        return instant + timedelta(days=int(date_available_next_day)), True
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("datetime requires an explicit timezone offset")
    return instant.astimezone(zone), False


def _require_row(row, seen_ids):
    if not isinstance(row, dict):
        raise ValueError("each evidence item must be an object")
    for key in ("id", "publisher", "origin", "event_key", "url", "claim", "axis", "relevance", "role", "evidence_type", "access"):
        if not isinstance(row.get(key), str) or not row[key].strip():
            raise ValueError(f"evidence requires a nonempty {key}")
    if row["id"] in seen_ids:
        raise ValueError(f"duplicate evidence id: {row['id']}")
    seen_ids.add(row["id"])
    if row["axis"] not in AXES:
        raise ValueError("unknown evidence axis")
    if row["relevance"] not in {"direct", "proxy"} or row["role"] not in {"driver", "context"}:
        raise ValueError("invalid relevance or role")
    if row["evidence_type"] not in {"fact", "opinion", "rumor"}:
        raise ValueError("invalid evidence_type")
    if row["access"] not in {"public_full", "public_excerpt", "search_snippet", "paywalled", "unavailable"}:
        raise ValueError("invalid access")
    limit = row.get("max_age_days")
    if type(limit) is not int or not 1 <= limit <= 366:
        raise ValueError("max_age_days must be an integer from 1 to 366")
    parsed = urlsplit(row["url"])
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("url must be a public HTTP(S) locator without credentials")


def audit_bundle(bundle):
    """Return admissibility/coverage. Input truth, sample mapping and bias need human review."""
    if not isinstance(bundle, dict) or not isinstance(bundle.get("evidence"), list):
        raise ValueError("bundle requires an evidence array")
    if not isinstance(bundle.get("commodity"), str) or not bundle["commodity"].strip():
        raise ValueError("commodity is required")
    try:
        zone = ZoneInfo(bundle.get("timezone", "Asia/Shanghai"))
        cutoff, cutoff_is_date = _timestamp(bundle.get("as_of"), zone)
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError(f"invalid cutoff/timezone: {exc}") from exc
    if cutoff_is_date:
        raise ValueError("as_of requires an exact timezone-aware datetime")
    if bundle.get("mode", "current") not in {"current", "historical"}:
        raise ValueError("mode must be current or historical")
    required = bundle.get("required_axes", ["supply", "demand", "inventory", "pricing"])
    if not isinstance(required, list) or any(not isinstance(axis, str) or axis not in AXES for axis in required):
        raise ValueError("required_axes contains an unknown axis")

    results, eligible, direct, seen_ids, seen_facts = [], [], [], set(), {}
    for item in bundle["evidence"]:
        _require_row(item, seen_ids)
        try:
            source_zone = ZoneInfo(item.get("source_timezone", str(zone)))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid source_timezone for {item['id']}") from exc
        row = {"id": item["id"], "eligible": False, "reasons": [], "warnings": []}
        reasons, warnings = row["reasons"], row["warnings"]
        if item["evidence_type"] != "fact":
            reasons.append("not_verified_fact")
        if item["access"] not in {"public_full", "public_excerpt"}:
            reasons.append("not_publicly_read")
        if item["access"] == "public_excerpt":
            warnings.append("public_excerpt_only")
        published = None
        try:
            published, publication_is_date = _timestamp(item.get("published_at"), source_zone, True)
            published = published.astimezone(zone)
            row["publication_available_at"] = published.isoformat()
            if publication_is_date:
                warnings.append("date_only_publication_conservative")
            if published > cutoff:
                reasons.append("published_after_cutoff")
            if (cutoff.date() - published.date()).days > item["max_age_days"]:
                reasons.append("stale_publication")
        except (TypeError, ValueError):
            reasons.append("unknown_or_invalid_publication")
        if item.get("available_at") is not None:
            try:
                available, _ = _timestamp(item["available_at"], source_zone, True)
                if available > cutoff:
                    reasons.append("available_after_cutoff")
            except (TypeError, ValueError):
                reasons.append("unknown_or_invalid_availability")
        try:
            observed, _ = _timestamp(item.get("observed_at"), source_zone)
            observed = observed.astimezone(zone)
            age = (cutoff.date() - observed.date()).days
            row["observation_age_days"] = age
            if observed > cutoff:
                reasons.append("future_observation")
            if age > item["max_age_days"]:
                reasons.append("stale_observation")
            if published and observed > published:
                reasons.append("observation_after_publication")
        except (TypeError, ValueError):
            reasons.append("unknown_or_invalid_observation")
        identity = (item["origin"], item["event_key"])
        if not reasons and identity in seen_facts:
            reasons.append("same_origin_same_fact")
            row["duplicate_of"] = seen_facts[identity]
        if not reasons:
            seen_facts[identity] = item["id"]
            row["eligible"] = True
            eligible.append(item)
            if item["role"] == "driver" and item["relevance"] == "direct":
                direct.append(item)
        results.append(row)
    axes = {item["axis"] for item in eligible if item["role"] == "driver"}
    return {
        "commodity": bundle["commodity"], "as_of": cutoff.isoformat(),
        "status": "manual_synthesis_required" if direct else "insufficient_current_direct_evidence",
        "eligible_ids": [item["id"] for item in eligible],
        "direct_driver_count": len(direct),
        "direct_axes": sorted({item["axis"] for item in direct}),
        "direct_origins": sorted({item["origin"] for item in direct}),
        "covered_axes": sorted(axes),
        "missing_axes": [axis for axis in required if axis not in axes],
        "historical_pit_certified": False,
        "limitations": ["Truth, original-source identity, sample scope, units, relevance and freshness choices require review.",
                        "A date filter does not prove historical first-release values or past delivery latency."],
        "rows": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Verified evidence JSON (see references/evidence-contract.md)")
    parser.add_argument("--output", type=Path, help="Optional audit JSON; otherwise print it")
    args = parser.parse_args(argv)
    try:
        result = audit_bundle(json.loads(args.bundle.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(f"evidence audit failed: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
