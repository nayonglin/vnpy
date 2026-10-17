"""Re-verify or fill only the seven published October SHFE/INE tail days.

Initial Stage265 downloads preceded this saved entrypoint and were ordinary
inline public GETs. This script does not retroactively claim their provenance.
Default mode is offline; --download only fills a missing declared tail file.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
from stage265_exchanges_official_archives import OUT, digest, now, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    manifest = OUT / "official_tail_sources_manifest.json"
    state = json.loads(manifest.read_text())
    days = {"20261008", "20261009", "20261012", "20261013", "20261014", "20261015", "20261016"}
    if len(state["sources"]) != 14:
        raise ValueError("tail_source_count_mismatch")
    session = None
    if args.download:
        import requests
        session = requests.Session()
        session.trust_env = False
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=0))
    results = []
    try:
        for r in state["sources"]:
            exchange, day = r["exchange"], r["date"]
            if exchange not in {"SHFE", "INE"} or day not in days:
                raise ValueError("tail_scope_mismatch")
            domain = "www.shfe.com.cn" if exchange == "SHFE" else "www.ine.cn"
            url = f"https://{domain}/data/tradedata/future/dailydata/kx{day}.dat"
            if r["url"] != url:
                raise ValueError("tail_url_mismatch")
            path = Path(r["path"])
            path.resolve().relative_to(OUT.resolve())
            if not path.exists() and session:
                response = session.get(url, timeout=(10, 25), allow_redirects=False)
                if response.status_code != 200:
                    raise ValueError("tail_http_status")
                blob = response.content
                parsed = json.loads(blob)
                if str(parsed.get("report_date")) != day or not isinstance(parsed.get("o_curinstrument"), list):
                    raise ValueError("tail_schema_or_report_date_mismatch")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(blob)
                time.sleep(.4)
            if digest(path) != r["sha256"] or path.stat().st_size != r["bytes"]:
                raise ValueError("tail_sha_or_size_mismatch")
            parsed = json.loads(path.read_text())
            if str(parsed.get("report_date")) != day or len(parsed["o_curinstrument"]) != r["record_count"]:
                raise ValueError("tail_payload_identity_mismatch")
            results.append({"source_id": r["source_id"], "sha256": r["sha256"], "report_date": day, "verified": True})
    finally:
        if session:
            session.close()
    save(OUT / "tail_offline_verification.json", {"generated_at": now(), "script_sha256": digest(__file__),
                                                "manifest_sha256": digest(manifest), "sources": results})
    print(json.dumps({"verified": len(results), "network_requests": 0 if not args.download else "missing_files_only"}))


if __name__ == "__main__":
    main()
