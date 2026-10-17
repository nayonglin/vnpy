"""Bounded public GET recorder for Stage265 evidence; never run fetched code."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

LINE = Path(__file__).resolve().parents[1]
OUTPUT = LINE / "outputs/stage265_deep_daily/opensource"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, help="Local JSON list of {key,url,max_bytes?}; only explicit public HTTPS GET")
    args = parser.parse_args()
    specs = json.loads(Path(args.spec).read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    log_path = OUTPUT / "fetch_log.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else []
    for index, spec in enumerate(specs):
        if index:
            time.sleep(0.8)
        key, url = spec["key"], spec["url"]
        if not key.replace("_", "").replace("-", "").isalnum():
            raise ValueError("unsafe_output_key")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("explicit_credential_free_https_required")
        path = OUTPUT / (key + ".raw")
        if path.exists():
            print(json.dumps({"key": key, "status": "existing_saved_raw_no_network", "bytes": path.stat().st_size}), flush=True)
            continue
        entry = {"key": key, "url": url, "method": "GET", "auth": "none", "automatic_retries": 0,
                 "requested_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()}
        limit = spec.get("max_bytes", 8 * 1024 * 1024)
        try:
            with requests.get(url, timeout=(10, 30), stream=True) as response:
                body = bytearray()
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > limit:
                        raise ValueError("response_above_evidence_size_cap")
                path.write_bytes(body)
                entry.update(status="saved", http_status=response.status_code, response_url=response.url,
                             content_type=response.headers.get("content-type", ""), bytes=len(body),
                             sha256=hashlib.sha256(body).hexdigest(), path=str(path.relative_to(LINE)))
        except (requests.RequestException, ValueError) as error:
            entry.update(status="failed_no_retry", error_type=type(error).__name__, error=str(error)[:350])
        entry["completed_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
        log.append(entry)
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({key: entry.get(key) for key in ("key", "status", "http_status", "bytes", "sha256", "error_type")}), flush=True)


if __name__ == "__main__":
    main()
