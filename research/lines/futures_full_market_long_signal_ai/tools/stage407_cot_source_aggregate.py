"""One offline cross-year identity/duplicate aggregation; no price or clock inference."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE / "outputs/stage407_cot_source_years"
OUT = ROOT / "actual_run1"


def bind(path):
    body = path.read_bytes()
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def main():
    summary_path = OUT / "aggregate_source_summary.json"
    if summary_path.exists():
        raise RuntimeError("one offline source aggregation only")
    source = json.loads((OUT / "source_manifest.json").read_text())
    parsed_path = OUT / "parsed_years_manifest.json"
    parsed = json.loads(parsed_path.read_text())
    protocol = json.loads((ROOT / "protocol.json").read_text())
    codes = defaultdict(lambda: {"names": set(), "years": set(), "rows": 0})
    groups, dates = defaultdict(list), set()
    schemas, annual_stats, unknown_dates = [], [], []
    weekday_rows = Counter()
    for year in parsed["years"]:
        if "outputs" not in year:
            annual_stats.append(year)
            continue
        schema = json.loads(Path(year["outputs"]["schema"]["path"]).read_text())
        schemas.append(year["outputs"]["schema"])
        for market in schema["all_market_names_and_row_counts"]:
            record = codes[market["market_code"]]
            record["names"].update(market["names"])
            record["years"].add(year["year"])
            record["rows"] += market["row_count"]
        weekday_rows.update(schema["asof_weekday_counts"])
        stats = {key: schema[key] for key in ("year", "identity_rows", "mapped_rows", "mapped_known_both_ratios",
                  "date_unknown_rows", "all_historical_market_count", "within_year_duplicate_groups",
                  "within_year_conflicting_duplicate_groups", "all_member_CRC_verified")}
        stats["mapped_asof_dates"] = set()
        with Path(year["outputs"]["mapped"]["path"]).open() as file:
            for line in file:
                row = json.loads(line)
                date = row["asof"]["date"]
                if date is None:
                    unknown_dates.append(row)
                    continue
                dates.add(date)
                stats["mapped_asof_dates"].add(date)
                groups[(date, row["channel"])].append(row)
        stats["mapped_asof_dates"] = sorted(stats["mapped_asof_dates"])
        stats["mapped_asof_date_count"] = len(stats["mapped_asof_dates"])
        annual_stats.append(stats)
    canonical = OUT / "eight_mapped_channels_2010_2025.jsonl"
    conflicts, duplicate_groups, absent, known = 0, 0, 0, 0
    family_tokens = Counter()
    with canonical.open("w") as file:
        for date in sorted(dates):
            for channel, code in sorted(protocol["mapping"].items()):
                original = groups.get((date, channel), [])
                if not original:
                    absent += 1
                    row = {"channel": channel, "market_code": code, "asof": {"date": date, "is_publication_timestamp": False},
                           "H": None, "MM": None, "status": "unknown:original_mapping_code_absent_on_observed_asof",
                           "unknown_reasons": ["no_source_row_for_fixed_code"], "observed_origins": []}
                else:
                    row = dict(original[0])
                    origins = [{key: item.get(key) for key in ("year_tag", "source_zip", "member", "line_number", "original_row_tokens_sha256")}
                               for item in original]
                    row["observed_origins"] = origins
                    duplicate_groups += len(original) > 1
                    hashes = {item["original_row_tokens_sha256"] for item in original}
                    conflict = len(hashes) > 1
                    row["cross_year_or_member_conflicting_duplicate"] = conflict
                    row["observed_duplicate_count"] = len(original)
                    if conflict:
                        conflicts += 1
                        row["H"] = row["MM"] = None
                        row["status"] = "unknown:conflicting_original_duplicates"
                        row["unknown_reasons"] = list(row.get("unknown_reasons", [])) + ["same_code_asof_original_row_conflict"]
                    for item in original:
                        family_tokens[item.get("extra_identity_tokens", {}).get("FutOnly_or_Combined", "unknown").strip()] += 1
                    known += row.get("H") is not None and row.get("MM") is not None
                file.write(json.dumps(row, ensure_ascii=True, sort_keys=True, allow_nan=False) + "\n")
        for row in unknown_dates:
            row["H"] = row["MM"] = None
            row["status"] = "unknown:original_asof_date_unknown"
            file.write(json.dumps(row, ensure_ascii=True, sort_keys=True, allow_nan=False) + "\n")
    identity_index = OUT / "all_historical_identity_index.json"
    identity_index.write_text(json.dumps({code: {"original_names": sorted(value["names"]), "source_years": sorted(value["years"]),
                                                "source_row_count": value["rows"]} for code, value in sorted(codes.items())}, indent=2) + "\n")
    summary = {"schema": "stage407_offline_aggregate_source_stats_v1", "at": datetime.now(timezone.utc).isoformat(),
               "source_manifest": bind(OUT / "source_manifest.json"), "parsed_years_manifest": bind(parsed_path),
               "source_year_stats": annual_stats, "schema_bindings": schemas,
               "all_historical_identity_rows": sum(row.get("identity_rows", 0) for row in annual_stats),
               "all_historical_codes": len(codes), "all_historical_names": sum(len(value["names"]) for value in codes.values()),
               "all_identity_asof_weekday_row_counts": dict(weekday_rows), "mapped_original_asof_dates": len(dates),
               "first_mapped_asof": min(dates) if dates else None, "last_mapped_asof": max(dates) if dates else None,
               "fixed_mapping_channels": protocol["mapping"], "mother_products": 98, "mother_families": 95,
               "other_products_unmapped_unknown_not_deleted": 90, "canonical_grid_rows": len(dates) * 8,
               "known_both_ratios": known, "original_code_missing_grid_rows": absent,
               "duplicate_code_asof_channel_groups": duplicate_groups, "conflicting_groups": conflicts,
               "unknown_asof_rows": len(unknown_dates), "mapped_report_family_original_tokens": dict(family_tokens),
               "canonical_mapped": bind(canonical), "historical_identity_index": bind(identity_index),
               "asof_is_not_publication": True, "visible_week_event_qualification": "not_performed_clock408_required",
               "current_ZIP_may_have_historical_revisions": True, "Y_reads": 0, "fit": 0, "cash": 0,
               "market_API": 0, "SQL": 0, "network_during_aggregation": 0, "whole_goal_achieved": False,
               "aggregation_script": bind(Path(__file__).resolve())}
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({key: summary[key] for key in ("all_historical_identity_rows", "all_historical_codes", "mapped_original_asof_dates",
                      "canonical_grid_rows", "known_both_ratios", "original_code_missing_grid_rows", "conflicting_groups", "unknown_asof_rows")}), flush=True)


if __name__ == "__main__":
    main()
