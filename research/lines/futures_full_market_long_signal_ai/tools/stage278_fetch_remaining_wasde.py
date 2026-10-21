"""One bounded, fresh download of the frozen USDA href catalog; no parsing/finance."""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import datetime
import hashlib
import json
import time

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE / "outputs/stage278_remaining_wasde_source"


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    protocol = json.loads((ROOT / "protocol.json").read_text())
    catalog_bytes = (ROOT / "catalog.json").read_bytes()
    assert hashlib.sha256(catalog_bytes).hexdigest() == "717c642d4168cae7d9a98cadc4672d3c78b8ba208cefdc905044262acbb4d98b"
    targets = json.loads(catalog_bytes)["targets"]
    assert len(targets) <= protocol["max_payload_requests"]
    out = ROOT / "actual_run1"
    out.mkdir(exist_ok=False)
    raw = out / "raw"
    raw.mkdir()
    terminal = {"status": "running", "started_at": stamp(), "requests_started": 0,
                "bodies_retained": 0, "failures": 0, "unattempted": len(targets),
                "bytes_retained": 0, "new_fit": 0, "new_cash": 0, "SQL": 0,
                "retry": False, "feature_or_PIT_acceptance": False, "goal_complete": False}
    write_json(out / "terminal.json", terminal)
    t0 = time.monotonic()
    last_dispatch = None
    consecutive_failures = 0
    stop_reason = None
    receipts = []
    for n, target in enumerate(targets, 1):
        if terminal["bytes_retained"] + protocol["per_file_max_bytes"] > protocol["total_payload_max_bytes"]:
            stop_reason = "insufficient_remaining_byte_budget"
            break
        if last_dispatch is not None:
            time.sleep(max(0, protocol["minimum_dispatch_spacing_seconds"] - (time.monotonic() - last_dispatch)))
        item = dict(target, ordinal=n, started_at=stamp(), status="started", attempt=1)
        request_path = out / f"request_{n:03d}.json"
        write_json(request_path, item)
        terminal["requests_started"] += 1
        terminal["unattempted"] -= 1
        last_dispatch = time.monotonic()
        body = None
        try:
            with urlopen(Request(target["retrieval_url"], headers={"User-Agent": "Mozilla/5.0 local-public-research"}),
                         timeout=protocol["timeout_seconds"]) as response:
                item.update(http_status=response.status, final_url=response.url, headers=dict(response.headers))
                body = response.read(protocol["per_file_max_bytes"] + 1)
            if len(body) > protocol["per_file_max_bytes"]:
                raise RuntimeError("per-file byte cap exceeded")
            path = raw / target["filename"]
            path.write_bytes(body)
            item.update(status="body_retained_unparsed", bytes=len(body), sha256=hashlib.sha256(body).hexdigest(), path=str(path))
            terminal["bodies_retained"] += 1
            terminal["bytes_retained"] += len(body)
            consecutive_failures = 0
        except Exception as exc:
            item.update(status="failed", error=repr(exc))
            if isinstance(exc, HTTPError):
                item["http_status"] = exc.code
                item["headers"] = dict(exc.headers)
                if exc.code in (403, 429):
                    stop_reason = f"http_{exc.code}"
            if body is not None:
                partial = raw / (target["filename"] + ".rejected")
                partial.write_bytes(body)
                item.update(rejected_body_path=str(partial), rejected_body_bytes=len(body))
                terminal["bytes_retained"] += len(body)
            consecutive_failures += 1
            terminal["failures"] += 1
            if consecutive_failures >= 3:
                stop_reason = stop_reason or "three_consecutive_failures"
        item["finished_at"] = stamp()
        write_json(request_path, item)
        receipts.append(item)
        write_json(out / "terminal.json", terminal)
        if n % 10 == 0 or item["status"] == "failed" or n == len(targets):
            print(json.dumps({k: terminal[k] for k in ("requests_started", "bodies_retained", "failures", "unattempted", "bytes_retained")}), flush=True)
        if stop_reason:
            break
    terminal.update(status="completed" if not stop_reason else "stopped_early", stop_reason=stop_reason,
                    finished_at=stamp(), elapsed_seconds=time.monotonic() - t0)
    manifest = {"schema": "stage278_raw_download_manifest_v1", "terminal": terminal,
                "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(), "requests": receipts,
                "new_fit": 0, "new_cash": 0, "cumulative_fit": 439, "cumulative_cash": 238}
    write_json(out / "manifest.json", manifest)
    write_json(out / "terminal.json", terminal)
    print(json.dumps(terminal), flush=True)


if __name__ == "__main__":
    main()
