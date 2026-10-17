"""Acquire public CFFEX monthly ZIPs; retain all raw columns, including options.

Normal official HTTP is used because HTTPS on this host timed out in the
retained probe. No authentication, site challenge solving or third-party code.
"""
from __future__ import annotations
import argparse
from datetime import date
import json
from pathlib import Path
import time

from stage265_exchanges_official_archives import OUT, archive_info, digest, fetch, now, save


def plan():
    probes = {"201004": OUT / "cffex_http_month_201004.zip",
              "202609": OUT / "cffex_http_month_202609.zip",
              "202610": OUT / "cffex_http_month_202610.zip"}
    records = []
    for year in range(2010, 2027):
        for month in range(1, 13):
            ym = f"{year}{month:02d}"
            if not "201004" <= ym <= "202610":
                continue
            path = probes.get(ym) or OUT / "cffex/raw_months" / f"{ym}.zip"
            records.append({"source_id": f"CFFEX_futures_options_{ym}", "exchange": "CFFEX",
                            "year_month": ym, "url": f"http://www.cffex.com.cn/sj/historysj/{ym}/zip/{ym}.zip",
                            "path": str(path), "status": "pending", "source_format": "zip_daily_csv_gb2312",
                            "official_download_page": "http://www.cffex.com.cn/cn/lssjxz.html",
                            "official_download_page_path": str(OUT / "cffex_history_page.txt"),
                            "official_download_page_sha256": digest(OUT / "cffex_history_page.txt"),
                            "route_reference_path": str(OUT / "akshare_daily_source.txt"),
                            "route_reference_sha256": digest(OUT / "akshare_daily_source.txt"),
                            "archive_kind": "month_to_date" if ym == "202610" else "historical_month",
                            "timestamp_semantics": "trade_date_from_daily_csv_member_name",
                            "oi_semantics": "official_end_of_day_position_not_TQ_open_oi",
                            "volume_oi_side": "official_single_side_preserve_original_no_conversion"})
    return records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--download", action="store_true")
    p.add_argument("--months", nargs="+")
    a = p.parse_args()
    path = OUT / "cffex_month_sources_manifest.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    previous = {r["source_id"]: r for r in old.get("sources", [])}
    records = plan()
    for r in records:
        if r["source_id"] in previous:
            saved = previous[r["source_id"]]
            if saved["url"] != r["url"] or saved["path"] != r["path"]:
                raise ValueError("existing_source_route_changed")
            r.update(saved)
    state = {"created_at": old.get("created_at", now()), "updated_at": now(),
             "target_complete_trade_date": "2026-10-16", "credentials_used": False,
             "main_database_written": False, "minimum_archive_year_month": "201004",
             "script_sha256": digest(__file__),
             "helper_script_sha256": digest(Path(__file__).with_name("stage265_exchanges_official_archives.py")),
             "sources": records}
    save(path, state)
    if not a.download:
        print(json.dumps({"status": "planned", "months": len(records)}))
        return
    import requests
    with requests.Session() as session:
        session.trust_env = False
        session.mount("http://", requests.adapters.HTTPAdapter(max_retries=0))
        for r in records:
            if a.months and r["year_month"] not in a.months:
                continue
            try:
                result = fetch(r, session)
                r.update(result)
                r["csv_date_members"] = sorted(m["display_name"][:8] for m in r["members"]
                                                if m["display_name"].endswith("_1.csv"))
                r["minimum_trade_date"] = min(r["csv_date_members"], default=None)
                r["maximum_trade_date"] = max(r["csv_date_members"], default=None)
            except Exception as e:
                r.update(status="failed", error_type=type(e).__name__, error=str(e), failed_at=now())
            state["updated_at"] = now()
            save(path, state)
            print(json.dumps({k: r.get(k) for k in ("source_id", "status", "action", "bytes", "maximum_trade_date", "error_type")}), flush=True)
            time.sleep(.35)


if __name__ == "__main__":
    main()
