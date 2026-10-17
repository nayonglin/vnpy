"""Read-only candidate listing metadata, never an official or market-bar import.

The public third-party table is bound to a fixed Git commit and original Git
blob hash. CZCE 3/4 digit representations join by product and full delivery
month, with the table's last-trade date validating the year. ME is never MA.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo


LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
OUTPUT = LINE / "outputs/stage265_deep_daily/czce"
META = OUTPUT / "metadata_ildhj"
COMMIT = "e8dd9a55b9a30b1e3033fe838724c23fcdd87ad1"


def normalize_metadata_code(code: str, issue: str, expiry: str) -> dict:
    match = re.fullmatch(r"([A-Z]+)([0-9]{3,4})\.CZC", code)
    if not match:
        raise ValueError("unsupported_metadata_code")
    product, digits = match.groups()
    listed, last = date.fromisoformat(issue), date.fromisoformat(expiry)
    modulus = 10 if len(digits) == 3 else 100
    if last.year % modulus != int(digits[:-2]) or last.month != int(digits[-2:]):
        raise ValueError("metadata_delivery_date_code_mismatch")
    if not listed <= last or last.year - listed.year > 3:
        raise ValueError("metadata_date_order_or_horizon_invalid")
    return {"identity_key": (f"{product}.CZCE", f"{last.year:04d}{last.month:02d}"),
            "vendor_code_original": code, "contract_issue_date_candidate": issue,
            "last_trade_date_candidate": expiry}


def history_upper_bound(issue: str, first_main: str) -> dict:
    if issue == "unknown":
        return {"calendar_day_upper_bound_through_first_main": None,
                "AM120_impossible_even_with_daily_bars": None}
    listed, first = date.fromisoformat(issue), date.fromisoformat(first_main)
    if listed > first:
        raise ValueError("listing_after_first_main_requires_review")
    maximum = (first - listed).days + 1
    return {"calendar_day_upper_bound_through_first_main": maximum,
            "AM120_impossible_even_with_daily_bars": maximum < 120}


def main() -> None:
    raw_requests = json.loads((META / "request_manifest.json").read_text())
    groups = defaultdict(list)
    input_sha, raw_count = {}, 0
    for record in raw_requests:
        path = META / Path(record["path"]).name
        body = path.read_bytes()
        if record["commit"] != COMMIT or record["http_status"] != 200:
            raise RuntimeError("unaccepted_source_request")
        if hashlib.sha256(body).hexdigest() != record["sha256"] or len(body) != record["expected_bytes"]:
            raise RuntimeError("metadata_bytes_changed")
        if hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest() != record["git_blob_sha"]:
            raise RuntimeError("metadata_git_blob_mismatch")
        input_sha[str(path)] = record["sha256"]
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for source_row, raw in enumerate(csv.DictReader(stream), 2):
                normalized = normalize_metadata_code(raw[""], raw["contract_issue_date"], raw["last_trade_date"])
                groups[normalized["identity_key"]].append({**normalized, "source_file": path.name, "source_row": source_row})
                raw_count += 1
    contradictory = {key for key, values in groups.items()
                     if len({(v["contract_issue_date_candidate"], v["last_trade_date_candidate"]) for v in values}) > 1}
    facts = json.loads((OUTPUT / "listing_evidence.json").read_text())
    announcements = {tuple(entry["identity_key"]): entry for entry in facts["contract_first_batches"]}
    manifests = [r for r in json.loads((LINE / "outputs/stage264_pre_main_daily/manifest_contracts.json").read_text())
                 if r["exchange"] == "CZCE"]
    results = []
    for target in manifests:
        key = target["product"], target["contract_yyyymm"]
        values = groups.get(key, [])
        candidate = values[0] if values and key not in contradictory else None
        announcement = announcements.get(key)
        listing = candidate["contract_issue_date_candidate"] if candidate else "unknown"
        if announcement:
            if listing != "unknown" and listing != announcement["listing_date"]:
                raise RuntimeError(f"announcement_metadata_conflict:{target['contract_epoch_id']}")
            listing = announcement["listing_date"]
        record = {
            "contract_epoch_id": target["contract_epoch_id"], "product": target["product"],
            "vt_symbol_mapping_original": target["vt_symbol"], "contract_yyyymm": target["contract_yyyymm"],
            "first_main_date": target["first_main_date"], "first_main_date_in_scope": target["first_main_date_in_scope"],
            "vendor_code_original": candidate["vendor_code_original"] if candidate else "unknown",
            "contract_issue_date_candidate": candidate["contract_issue_date_candidate"] if candidate else "unknown",
            "last_trade_date_candidate": candidate["last_trade_date_candidate"] if candidate else "unknown",
            "candidate_source_file": candidate["source_file"] if candidate else "unknown",
            "candidate_source_row": candidate["source_row"] if candidate else "unknown",
            "candidate_status": "conflicting_metadata_rejected" if key in contradictory else "third_party_unverified_candidate" if candidate else "not_in_2018_snapshot",
            "announcement_supported_issue_date": announcement["listing_date"] if announcement else "unknown",
            "announcement_source_class": announcement["source_class"] if announcement else "unknown",
            "announcement_source_url": announcement["source_url"] if announcement else "unknown",
            "issue_date_used_for_conditional_bound": listing,
            "bound_depends_on_unverified_metadata": bool(candidate and not announcement),
            **history_upper_bound(listing, target["first_main_date"]),
            "full_lifetime_certified": False,
            "metadata_origin_and_license_status": "third_party_repository_origin_and_data_license_not_established",
        }
        results.append(record)
    with (OUTPUT / "metadata_candidates.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    (OUTPUT / "metadata_candidates.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    summary = {
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "status": "candidate_metadata_and_documented_listing_boundaries_only_no_market_bars",
        "source_repository": "ildhj0116/Work", "fixed_commit": COMMIT, "commit_date": "2018-04-26",
        "raw_metadata_rows": raw_count, "raw_metadata_identity_count": len(groups),
        "conflicting_metadata_identity_count": len(contradictory), "target_epochs": len(results),
        "target_with_candidate_metadata": sum(r["candidate_status"] == "third_party_unverified_candidate" for r in results),
        "target_with_announcement_supported_issue_date": sum(r["announcement_supported_issue_date"] != "unknown" for r in results),
        "target_issue_date_still_unknown": sum(r["issue_date_used_for_conditional_bound"] == "unknown" for r in results),
        "target_last_trade_date_still_unknown": sum(r["last_trade_date_candidate"] == "unknown" for r in results),
        "target_calendar_upper_bound_below_AM120": sum(r["AM120_impossible_even_with_daily_bars"] is True for r in results),
        "candidate_coverage_by_product": dict(Counter(r["product"] for r in results if r["candidate_status"] == "third_party_unverified_candidate")),
        "input_sha256": input_sha, "bar_downloaded_by_this_metadata_tool": 0,
        "database_writes": 0, "training_runs": 0, "backtest_runs": 0,
        "limits": ["The 2018 Git snapshot cannot cover 2019/SA; metadata origin and license remain unknown.",
                   "Matching by product and full delivery month only reconciles representation, not vendor identity certification.",
                   "Calendar days are an unconditional upper bound of one daily bar per date, not a verified exchange holiday calendar.",
                   "A small upper bound proves AM120 impossible only if the selected listing-date evidence is valid; candidate-only bounds remain conditional.",
                   "No missing metadata date is filled with a guessed listing or expiry rule; no ME-to-MA relabeling."],
    }
    (OUTPUT / "metadata_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "input_sha256"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
