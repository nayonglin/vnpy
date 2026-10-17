"""Offline self-audit and catalog for Stage265 official daily reference data.

This is an implementer's audit, not the required independent data review.
"""
from collections import Counter, defaultdict
import csv
from datetime import date
import gzip
import json
import math
from pathlib import Path

from stage265_exchanges_official_archives import OUT, archive_info, digest, now, save


def main():
    sources, identities = [], set()
    manifests = {}
    for name in ("official_archive_sources_manifest.json", "cffex_month_sources_manifest.json", "official_tail_sources_manifest.json"):
        p = OUT / name
        manifests[name] = digest(p)
        for rec in json.loads(p.read_text())["sources"]:
            if rec["status"] not in ("downloaded", "reused_stage264") or rec["source_id"] in identities:
                raise ValueError("pending_failed_or_duplicate_source")
            identities.add(rec["source_id"])
            p = Path(rec["path"])
            if digest(p) != rec["sha256"] or p.stat().st_size != rec["bytes"]:
                raise ValueError("source_sha_or_size_mismatch")
            if p.suffix == ".zip":
                info = archive_info(p)
                if not info["crc_valid"]:
                    raise ValueError("archive_crc_failed")
            else:
                data = json.loads(p.read_text())
                if str(data["report_date"]) != rec["date"]:
                    raise ValueError("tail_report_date_mismatch")
            sources.append(rec)
    if len(sources) != 247:
        raise ValueError("expected_247_sources")
    norm_path = OUT / "normalized/official_normalization_manifest.json"
    normal = json.loads(norm_path.read_text())
    normalized = {s["source_id"]: s for s in normal["sources"]}
    if set(normalized) != identities:
        raise ValueError("normalization_source_set_mismatch")
    keys, contracts = set(), defaultdict(set)
    census = defaultdict(lambda: {"accepted": set(), "zero_trade": set(), "rejected": set()})
    rows, unit_rows, totals, by_exchange = 0, Counter(), Counter(), Counter()
    for rec in sources:
        n = normalized[rec["source_id"]]
        if n["raw_sha256"] != rec["sha256"]:
            raise ValueError("normalized_raw_identity_mismatch")
        for prefix in ("normalized", "no_trade", "rejected"):
            if digest(n[prefix + "_path"]) != n[prefix + "_sha256"]:
                raise ValueError("normalized_file_sha_mismatch")
        file_rows = 0
        with gzip.open(n["normalized_path"], "rt", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = row["exchange"] + "|" + row["source_symbol"] + "|" + row["date"]
                if key in keys:
                    raise ValueError("cross_source_duplicate_ordinary_day")
                keys.add(key)
                if row["source_id"] != rec["source_id"] or row["oi_timing"] != "close_end_of_day":
                    raise ValueError("row_source_or_clock_mismatch")
                day = date.fromisoformat(row["date"])
                if day > date(2026, 10, 16):
                    raise ValueError("past_target_trade_date")
                op, hi, lo, cl, vol, oi = (float(row[k]) for k in ("open", "high", "low", "close", "volume", "open_interest"))
                if not all(math.isfinite(v) for v in (op, hi, lo, cl, vol, oi)):
                    raise ValueError("nonfinite_accepted_row")
                if not 0 < lo <= min(op, cl) <= max(op, cl) <= hi or min(vol, oi) < 0:
                    raise ValueError("invalid_accepted_ohlcv")
                file_rows += 1
                rows += 1
                by_exchange[row["exchange"]] += 1
                unit_rows[row["unit_regime"]] += 1
                contracts[row["exchange"]].add((row["product"], row["contract_yyyymm"]))
                if row["date"] == "2026-10-16":
                    census[(row["exchange"], row["product"])]["accepted"].add(row["source_symbol"])
        if file_rows != n["counts"].get("accepted_rows", 0):
            raise ValueError("normalized_row_count_mismatch")
        no_trade_rows = 0
        with gzip.open(n["no_trade_path"], "rt", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if float(row["volume"]) != 0:
                    raise ValueError("nonzero_volume_in_no_trade_table")
                if row["date"] == "2026-10-16":
                    census[(row["exchange"], row["product"])]["zero_trade"].add(row["source_symbol"])
                no_trade_rows += 1
        if no_trade_rows != n["counts"].get("no_trade_rows_separate", 0):
            raise ValueError("no_trade_row_count_mismatch")
        totals.update(n["counts"])
        with gzip.open(n["rejected_path"], "rt", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["date"] == "2026-10-16":
                    census[(row["exchange"], row["product"])]["rejected"].add(row["source_symbol"])
    result = {"generated_at": now(), "status": "pass_implementer_self_audit_not_independent_review",
              "script_sha256": digest(__file__), "source_count": len(sources),
              "archive_count": sum(Path(s["path"]).suffix == ".zip" for s in sources),
              "source_bytes_including_stage264_reuse": sum(s["bytes"] for s in sources),
              "reused_stage264_bytes": sum(s["bytes"] for s in sources if s["status"] == "reused_stage264"),
              "ordinary_accepted_rows": rows, "cross_source_duplicate_keys": 0,
              "accepted_invalid_ohlcv_rows": 0, "by_exchange_rows": dict(by_exchange),
              "contract_count_by_exchange": {k: len(v) for k, v in contracts.items()},
              "unit_regime_rows": dict(unit_rows), "raw_classification_counts": dict(totals),
              "main_database_written": False, "cross_source_units_converted": False,
              "independent_review_complete": False,
              "unified_training_data_qualified": False,
              "remaining_limitations": ["GFEX official endpoints returned challenge HTML/TLS host mismatch",
                                        "some XLSX archive members omit unit notes; original units remain un-inferred",
                                        "observed date bounds are not a listing/delisting metadata certification",
                                        "official anomalous or incomplete OHLC stays in rejected tables"],
              "source_manifests": manifests, "normalization_manifest_sha256": digest(norm_path)}
    save(OUT / "official_self_validation.json", result)
    catalog = {**result, "normalization_manifest_path": str(norm_path), "product_coverage": normal["product_coverage"],
               "research_reference_path": str(OUT / "official_source_research.json"),
               "unknown_unit_sources": sorted({n["source_id"] for n in normal["notes"] if n["unit_regime"] == "official_original_units_not_inferred"}),
               "sources": [{"source_id": s["source_id"], "exchange": s["exchange"], "url": s["url"],
                            "path": s["path"], "sha256": s["sha256"], "bytes": s["bytes"], "status": s["status"],
                            **{k: normalized[s["source_id"]][k] for k in ("normalized_path", "normalized_sha256", "no_trade_path", "no_trade_sha256", "rejected_path", "rejected_sha256", "min_date", "max_date", "counts")}}
                           for s in sources]}
    save(OUT / "official_reference_catalog.json", catalog)
    census_rows = []
    for (exchange, product), values in sorted(census.items()):
        ordinary = values["accepted"] | values["zero_trade"] | values["rejected"]
        census_rows.append({"exchange": exchange, "product": product,
                            "ordinary_contract_count": len(ordinary),
                            "accepted_ohlc_contract_count": len(values["accepted"]),
                            "zero_trade_contract_count": len(values["zero_trade"]),
                            "rejected_ohlc_contract_count": len(values["rejected"]),
                            "zero_trade_also_accepted_count": len(values["accepted"] & values["zero_trade"]),
                            "contracts": sorted(ordinary),
                            "zero_trade_contracts": sorted(values["zero_trade"])})
    save(OUT / "latest_trade_date_census.json", {"trade_date": "2026-10-16", "counting": "unique ordinary exchange/product/symbol; no_trade/rejected overlap is a set union",
                                               "official_reference_only_not_six_exchange_total": True,
                                               "products": census_rows})
    print(json.dumps({k: v for k, v in result.items() if k not in ("remaining_limitations", "source_manifests")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
