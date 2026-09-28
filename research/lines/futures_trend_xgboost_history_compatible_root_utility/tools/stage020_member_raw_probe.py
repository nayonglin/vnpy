from __future__ import annotations

import importlib.util
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
OUTPUT = ROOT / "artifacts/stage020_member_raw_probe"
MAX_BYTES = 8 * 1024 * 1024
PLAN = [
    {"id": "shfe_20200107", "exchange": "SHFE", "method": "GET", "date": "20200107", "contract": "rb2005",
     "url": "https://www.shfe.com.cn/data/tradedata/future/dailydata/pm20200107.dat"},
    {"id": "shfe_20260828", "exchange": "SHFE", "method": "GET", "date": "20260828", "contract": None,
     "url": "https://www.shfe.com.cn/data/tradedata/future/dailydata/pm20260828.dat"},
    {"id": "czce_20200311", "exchange": "CZCE", "method": "GET", "date": "20200311", "contract": "CF005",
     "url": "http://www.czce.com.cn/cn/DFSStaticFiles/Future/2020/20200311/FutureDataHolding.xls"},
    {"id": "czce_20260828", "exchange": "CZCE", "method": "GET", "date": "20260828", "contract": None,
     "url": "http://www.czce.com.cn/cn/DFSStaticFiles/Future/2026/20260828/FutureDataHolding.xlsx"},
    {"id": "dce_20200108", "exchange": "DCE", "method": "POST", "date": "20200108", "contract": "jm2005",
     "url": "http://www.dce.com.cn/dcereport/publicweb/dailystat/memberDealPosi/batchDownload",
     "json": {"tradeDate": "20200108", "varietyId": "jm", "contractId": "jm2005", "tradeType": "1", "lang": "zh"}},
    *[{"id": f"gfex_20230822_{kind}", "exchange": "GFEX", "method": "POST", "date": "20230822", "contract": "si2310",
       "url": "http://www.gfex.com.cn/u/interfacesWebTiMemberDealPosiQuotes/loadList",
       "data": {"trade_date": "20230822", "trade_type": "0", "variety": "si", "contract_id": "si2310", "data_type": str(kind)}}
      for kind in (1, 2, 3)],
]


def now():
    return datetime.now(timezone.utc).isoformat()


def source_tool():
    spec = importlib.util.spec_from_file_location("stage020_source_identity", ROOT / "tools/stage019_member_concentration_source.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def inspect(item, body):
    result = {"evidence_level": "readable_carrier_only", "historical_publication_verified": False,
              "historical_revision_verified": False, "raw_rank_member_completeness_verified": False}
    exchange = item["exchange"]
    if exchange == "SHFE":
        data = json.loads(body)
        rows = data.get("o_cursor")
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("shfe_cursor_empty")
        symbols = {str(row.get("INSTRUMENTID", "")).strip().lower() for row in rows}
        present = item["contract"].lower() in symbols if item["contract"] else None
        if present is False:
            raise RuntimeError("shfe_expected_contract_missing")
        result.update(row_count=len(rows), expected_contract_present=present,
                      declared_report_date=data.get("report_date"), field_names=sorted(rows[0]))
    elif exchange == "CZCE":
        if not body.startswith((b"PK", bytes.fromhex("d0cf11e0a1b11ae1"))):
            raise RuntimeError("czce_workbook_format_invalid")
        frame = pd.read_excel(io.BytesIO(body), header=None)
        if frame.empty:
            raise RuntimeError("czce_workbook_empty")
        cells = frame.fillna("").astype(str).to_numpy().ravel().tolist()
        present = any(re.search(r"(?<![A-Za-z0-9])" + re.escape(item["contract"]) + r"(?![A-Za-z0-9])", text, re.I)
                      for text in cells) if item["contract"] else None
        if present is False:
            raise RuntimeError("czce_expected_contract_missing")
        result.update(row_count=len(frame), column_count=len(frame.columns), expected_contract_present=present,
                      response_date_identity_verified=False)
    elif exchange == "DCE":
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            names = archive.namelist()
        matches = [name for name in names if name.startswith(item["date"] + "_" + item["contract"] + "_")]
        if not matches:
            raise RuntimeError("dce_date_contract_archive_member_missing")
        result.update(archive_member_count=len(names), matching_archive_members=matches,
                      archive_extracted=False, archive_content_semantics_verified=False)
    elif exchange == "GFEX":
        data = json.loads(body)
        rows = data.get("data")
        if not isinstance(rows, list) or not rows:
            raise RuntimeError("gfex_rows_empty")
        if not all(isinstance(row, dict) and "abbr" in row and "todayQty" in row for row in rows):
            raise RuntimeError("gfex_member_fields_missing")
        result.update(row_count=len(rows), field_names=sorted(rows[0]), response_contract_identity_verified=False,
                      response_date_identity_verified=False)
    else:
        raise RuntimeError("unexpected_exchange")
    return result


def fetch(item, output):
    record = {**item, "status": "started", "started_at_utc": now(), "body_truncated": False,
              "http_status": None, "received_bytes": 0}
    response = None
    body = bytearray()
    write_json(output / (item["id"] + ".json"), record)
    try:
        kwargs = {key: item[key] for key in ("json", "data") if key in item}
        response = requests.request(item["method"], item["url"], timeout=(5, 15), allow_redirects=False, stream=True, **kwargs)
        record.update(http_status=response.status_code, content_type=response.headers.get("Content-Type"))
        for chunk in response.iter_content(chunk_size=65536):
            if len(body) + len(chunk) > MAX_BYTES:
                body.extend(chunk[:MAX_BYTES - len(body)])
                record["body_truncated"] = True
                raise RuntimeError("response_size_limit")
            body.extend(chunk)
        if response.status_code != 200:
            raise RuntimeError(f"http_status:{response.status_code}")
        record["inspection"] = inspect(item, bytes(body))
        record["status"] = "carrier_readable"
    except Exception as exc:
        record.update(status="failed", error=f"{type(exc).__name__}:{exc}")
    finally:
        if response is not None:
            response.close()
        body_path = output / (item["id"] + ".body")
        body_path.write_bytes(body)
        record.update(received_bytes=len(body), completed_at_utc=now(), body_identity=source_tool().identity(body_path))
        write_json(output / (item["id"] + ".json"), record)
    return record


def execute(plan, output, *, attempt=fetch):
    records, failed_exchanges = [], set()
    for item in plan:
        if item["exchange"] in failed_exchanges:
            record = {**item, "status": "skipped_after_exchange_failure", "recorded_at_utc": now()}
        else:
            record = attempt(item, output)
            if record["status"] != "carrier_readable":
                failed_exchanges.add(item["exchange"])
        records.append(record)
        write_json(output / "journal.json", records)
    return records


def run():
    if OUTPUT.exists():
        raise RuntimeError("member_raw_probe_output_already_exists")
    helper = source_tool()
    upstream = ROOT / "artifacts/stage019_member_concentration_source"
    upstream_summary = upstream / "summary.json"
    if helper.identity(upstream_summary)["sha256"] != "4d8a0e2e8cadd016f3db20ff98196bf1219f4919d91dca8787e87dcf02615ad7":
        raise RuntimeError("member_source_summary_changed")
    old = json.loads(upstream_summary.read_text())
    old_inputs = json.loads((upstream / "input_manifest.json").read_text())
    for item in [*old_inputs.values(), *old["outputs"].values()]:
        if helper.identity(Path(item["path"])) != item:
            raise RuntimeError("member_source_upstream_changed")
    paths = [upstream_summary, upstream / "input_manifest.json", upstream / "event_coverage.csv",
             Path(__file__), ROOT / "tools/stage019_member_concentration_source.py",
             ROOT / "tests/test_stage020_member_raw_probe.py", ROOT / "stages/20260906_0502_stage020_member_raw_probe_contract.md",
             REPO / ".py311/lib/python3.11/site-packages/akshare/futures/cot.py",
             REPO / ".py311/lib/python3.11/site-packages/akshare/futures/cons.py"]
    inputs = {str(path): helper.identity(path) for path in paths}
    events = pd.read_csv(upstream / "event_coverage.csv", usecols=["decision_date", "contract_vt_symbol", "required_source_date"])
    events["exchange"] = events.contract_vt_symbol.str.split(".").str[-1]
    earliest = events.sort_values("decision_date", kind="mergesort").groupby("exchange").first()
    for item in (PLAN[0], PLAN[2], PLAN[4], PLAN[5]):
        row = earliest.loc[item["exchange"]]
        if row.required_source_date.replace("-", "") != item["date"] or row.contract_vt_symbol.split(".")[0].lower() != item["contract"].lower():
            raise RuntimeError("probe_not_first_event_per_exchange")
    OUTPUT.mkdir(parents=True)
    write_json(OUTPUT / "input_manifest.json", inputs)
    records = execute(PLAN, OUTPUT)
    for path, before in inputs.items():
        if helper.identity(Path(path)) != before:
            write_json(OUTPUT / "failure.json", {"error": "probe_input_changed", "path": path})
            raise RuntimeError("probe_input_changed")
    outputs = {path.name: helper.identity(path) for path in sorted(OUTPUT.iterdir()) if path.is_file()}
    summary = {"stage": "stage020_member_raw_probe", "created_at_utc": now(), "status": "bounded_probe_completed",
               "decision": "inspect_carriers_before_any_rebuild", "planned_request_count": len(PLAN),
               "network_attempt_count": sum(row["status"] != "skipped_after_exchange_failure" for row in records),
               "readable_carrier_count": sum(row["status"] == "carrier_readable" for row in records),
               "failed_request_count": sum(row["status"] == "failed" for row in records),
               "skipped_request_count": sum(row["status"] == "skipped_after_exchange_failure" for row in records),
               "new_label_count": 0, "new_fit_count": 0, "new_prediction_count": 0,
               "new_strategy_replay_count": 0, "reviewer_started": False,
               "full_history_coverage_verified": False, "records": records, "source_count": len(inputs), "outputs": outputs}
    write_json(OUTPUT / "summary.json", summary)
    print(json.dumps({key: value for key, value in summary.items() if key not in ("outputs",)}, indent=2, allow_nan=False))


if __name__ == "__main__":
    run()
