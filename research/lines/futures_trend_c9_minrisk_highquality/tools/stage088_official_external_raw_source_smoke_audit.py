from __future__ import annotations

from datetime import datetime
from io import BytesIO, StringIO
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any
import zipfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import urllib3


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage088"
MODEL_TAG = "stage088_official_external_raw_source_smoke_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage088_c9_minrisk_official_external_raw_source_smoke_audit"
ACCOUNT_CAPITAL = 150_000.0
REQUEST_TIMEOUT = 10
WRAPPER_TIMEOUT = 25
TRADING_DAYS_PER_YEAR = 252

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage088_official_external_raw_source_smoke_audit"
RAW_DIR = OUTPUT_DIR / "raw"

OFFICIAL_CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
OFFICIAL_SUMMARY_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

DIRECT_PROBE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_direct_raw_probe_{MODEL_TAG}.csv"
WRAPPER_PROBE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_akshare_wrapper_probe_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_raw_smoke_chart_{MODEL_TAG}.png"
ENDPOINT_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_endpoint_matrix_chart_{MODEL_TAG}.png"
RAW_BYTES_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_response_bytes_chart_{MODEL_TAG}.png"
NEXT_ACTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_chart_{MODEL_TAG}.png"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    )
}

SAMPLE_DATES = ["20210301", "20240603", "20260612"]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return value


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["account_equity", "drawdown_pct", "slippage", "trade_count", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    prev = curve["account_equity"].shift(1)
    if not curve.empty:
        prev.iloc[0] = ACCOUNT_CAPITAL
    curve["daily_return"] = (curve["account_equity"] / prev - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _official_metrics(curve: pd.DataFrame) -> dict[str, float]:
    official_summary = _read_csv(OFFICIAL_SUMMARY_IN, required=False)
    row = official_summary.iloc[0].to_dict() if not official_summary.empty else {}

    def val(column: str, default: float) -> float:
        try:
            number = float(row.get(column, default))
        except (TypeError, ValueError):
            return default
        return default if np.isnan(number) or np.isinf(number) else number

    returns = pd.to_numeric(curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    end = float(curve["account_equity"].iloc[-1]) if not curve.empty else ACCOUNT_CAPITAL
    return {
        "end_equity": val("end_equity", end),
        "total_return_pct": val("total_return_pct", (end / ACCOUNT_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": val("max_dd_pct", float(curve["drawdown_pct"].min()) if not curve.empty else 0.0),
        "sharpe": val("sharpe", (float(returns.mean()) / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0),
        "total_slippage": val("total_slippage", float(curve["slippage"].sum())),
        "total_trade_count": val("total_trade_count", float(curve["trade_count"].sum())),
        "win_rate_pct": val("nonzero_daily_win_rate_pct", 0.0),
        "broker10_peak_margin_to_equity_pct": val(
            "max_broker10_margin_to_equity_pct",
            float(curve["broker10_margin_to_equity_pct"].max()) if not curve.empty else 0.0,
        ),
    }


def _direct_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for date in SAMPLE_DATES:
        year = date[:4]
        czce_ext = "xlsx" if int(date) > 20251101 else "xls"
        specs.extend(
            [
                {
                    "probe_id": f"shfe_warehouse_dat_{date}",
                    "source_id": "shfe_warehouse",
                    "exchange": "SHFE",
                    "date": date,
                    "method": "GET",
                    "url": f"https://www.shfe.com.cn/data/tradedata/future/dailydata/{date}dailystock.dat",
                    "expected_kind": "json",
                    "verify_tls": True,
                },
                {
                    "probe_id": f"shfe_rank_pm_new_{date}",
                    "source_id": "shfe_member_rank",
                    "exchange": "SHFE",
                    "date": date,
                    "method": "GET",
                    "url": f"https://www.shfe.com.cn/data/tradedata/future/dailydata/pm{date}.dat",
                    "expected_kind": "json",
                    "verify_tls": True,
                },
                {
                    "probe_id": f"shfe_rank_pm_legacy_{date}",
                    "source_id": "shfe_member_rank",
                    "exchange": "SHFE",
                    "date": date,
                    "method": "GET",
                    "url": f"https://tsite.shfe.com.cn/data/dailydata/kx/pm{date}.dat",
                    "expected_kind": "json",
                    "verify_tls": True,
                },
                {
                    "probe_id": f"czce_holding_file_{date}",
                    "source_id": "czce_member_rank",
                    "exchange": "CZCE",
                    "date": date,
                    "method": "GET",
                    "url": f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{year}/{date}/FutureDataHolding.{czce_ext}",
                    "expected_kind": "excel",
                    "verify_tls": False,
                },
                {
                    "probe_id": f"czce_warehouse_file_{date}",
                    "source_id": "czce_warehouse",
                    "exchange": "CZCE",
                    "date": date,
                    "method": "GET",
                    "url": f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{year}/{date}/FutureDataWhsheet.{czce_ext}",
                    "expected_kind": "excel",
                    "verify_tls": False,
                },
                {
                    "probe_id": f"dce_member_batch_{date}",
                    "source_id": "dce_member_rank",
                    "exchange": "DCE",
                    "date": date,
                    "method": "POST_JSON",
                    "url": "http://www.dce.com.cn/dcereport/publicweb/dailystat/memberDealPosi/batchDownload",
                    "payload": {
                        "tradeDate": date,
                        "varietyId": "a",
                        "contractId": "a2601",
                        "tradeType": "1",
                        "lang": "zh",
                    },
                    "expected_kind": "zip",
                    "verify_tls": False,
                },
                {
                    "probe_id": f"dce_warehouse_json_{date}",
                    "source_id": "dce_warehouse",
                    "exchange": "DCE",
                    "date": date,
                    "method": "POST_JSON",
                    "url": "http://www.dce.com.cn/dcereport/publicweb/dailystat/wbillWeeklyQuotes",
                    "payload": {"tradeDate": date, "varietyId": "all"},
                    "expected_kind": "json",
                    "verify_tls": False,
                },
                {
                    "probe_id": f"gfex_warehouse_json_{date}",
                    "source_id": "gfex_warehouse",
                    "exchange": "GFEX",
                    "date": date,
                    "method": "POST_FORM",
                    "url": "http://www.gfex.com.cn/u/interfacesWebTdWbillWeeklyQuotes/loadList",
                    "payload": {"gen_date": date},
                    "expected_kind": "json",
                    "verify_tls": False,
                },
            ]
        )
    return specs


def _wrapper_specs() -> list[dict[str, Any]]:
    return [
        {
            "probe_id": "ak_dce_member_rank_20240603",
            "source_id": "dce_member_rank",
            "function_name": "futures_dce_position_rank",
            "args": [],
            "kwargs": {"date": "20240603", "vars_list": ["JM", "LH"]},
        },
        {
            "probe_id": "ak_dce_warehouse_20240603",
            "source_id": "dce_warehouse",
            "function_name": "futures_warehouse_receipt_dce",
            "args": [],
            "kwargs": {"date": "20240603"},
        },
        {
            "probe_id": "ak_czce_member_rank_20240603",
            "source_id": "czce_member_rank",
            "function_name": "get_rank_table_czce",
            "args": [],
            "kwargs": {"date": "20240603"},
        },
        {
            "probe_id": "ak_czce_warehouse_20240603",
            "source_id": "czce_warehouse",
            "function_name": "futures_warehouse_receipt_czce",
            "args": [],
            "kwargs": {"date": "20240603"},
        },
        {
            "probe_id": "ak_shfe_member_rank_20240603",
            "source_id": "shfe_member_rank",
            "function_name": "get_shfe_rank_table",
            "args": [],
            "kwargs": {"date": "20240603", "vars_list": ["RB", "AU"]},
        },
        {
            "probe_id": "ak_shfe_warehouse_20240603",
            "source_id": "shfe_warehouse",
            "function_name": "futures_shfe_warehouse_receipt",
            "args": [],
            "kwargs": {"date": "20240603"},
        },
        {
            "probe_id": "ak_gfex_member_rank_20240603",
            "source_id": "gfex_member_rank",
            "function_name": "futures_gfex_position_rank",
            "args": [],
            "kwargs": {"date": "20240603", "vars_list": ["lc", "si"]},
        },
        {
            "probe_id": "ak_gfex_warehouse_20240603",
            "source_id": "gfex_warehouse",
            "function_name": "futures_gfex_warehouse_receipt",
            "args": [],
            "kwargs": {"date": "20240603"},
        },
    ]


def _extension_for_probe(expected_kind: str, content_type: str, is_zip: bool) -> str:
    if is_zip:
        return "zip"
    if expected_kind == "excel":
        return "bin"
    if "json" in content_type.lower() or expected_kind == "json":
        return "json"
    if "html" in content_type.lower():
        return "html"
    return "raw"


def _parse_payload(content: bytes, expected_kind: str, content_type: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "parse_ready": 0,
        "result_kind": "",
        "row_count": 0,
        "key_or_file_count": 0,
        "sample_keys_or_files": "",
        "sample_columns": "",
        "parse_error_type": "",
        "parse_error_message": "",
    }
    if not content:
        result["parse_error_type"] = "EmptyContent"
        result["parse_error_message"] = "empty response"
        return result
    try:
        if zipfile.is_zipfile(BytesIO(content)):
            with zipfile.ZipFile(BytesIO(content), mode="r") as zf:
                names = zf.namelist()
            result.update(
                {
                    "parse_ready": int(len(names) > 0),
                    "result_kind": "zip",
                    "key_or_file_count": len(names),
                    "sample_keys_or_files": "|".join(names[:10]),
                }
            )
            return result
        if expected_kind == "json" or "json" in content_type.lower():
            data = json.loads(content.decode("utf-8", errors="ignore"))
            if isinstance(data, dict):
                keys = list(data.keys())
                row_count = 0
                if isinstance(data.get("o_cursor"), list):
                    row_count = len(data["o_cursor"])
                    columns = sorted(data["o_cursor"][0].keys()) if data["o_cursor"] else []
                elif isinstance(data.get("data"), dict) and isinstance(data["data"].get("entityList"), list):
                    row_count = len(data["data"]["entityList"])
                    columns = sorted(data["data"]["entityList"][0].keys()) if data["data"]["entityList"] else []
                elif isinstance(data.get("data"), list):
                    row_count = len(data["data"])
                    columns = sorted(data["data"][0].keys()) if data["data"] and isinstance(data["data"][0], dict) else []
                else:
                    columns = keys
                result.update(
                    {
                        "parse_ready": int(row_count > 0 or bool(keys)),
                        "result_kind": "json",
                        "row_count": int(row_count),
                        "key_or_file_count": len(keys),
                        "sample_keys_or_files": "|".join(str(key) for key in keys[:10]),
                        "sample_columns": "|".join(str(col) for col in columns[:16]),
                    }
                )
                return result
            result.update({"parse_ready": 1, "result_kind": type(data).__name__})
            return result
        if expected_kind == "excel":
            frame = pd.read_excel(BytesIO(content), nrows=200)
            result.update(
                {
                    "parse_ready": int(not frame.empty),
                    "result_kind": "excel",
                    "row_count": int(len(frame)),
                    "sample_columns": "|".join(str(col) for col in frame.columns[:16]),
                }
            )
            return result
        if "html" in content_type.lower() or content.lstrip().lower().startswith(b"<!doctype"):
            text = content.decode("utf-8", errors="ignore")
            tables = pd.read_html(StringIO(text))
            row_count = int(sum(len(table) for table in tables))
            result.update(
                {
                    "parse_ready": int(row_count > 0),
                    "result_kind": "html_table",
                    "row_count": row_count,
                    "key_or_file_count": len(tables),
                }
            )
            return result
    except Exception as exc:  # noqa: BLE001
        result["parse_error_type"] = type(exc).__name__
        result["parse_error_message"] = str(exc)[:300]
    return result


def _run_direct_probe(spec: dict[str, Any]) -> dict[str, Any]:
    row = {
        "probe_id": spec["probe_id"],
        "source_id": spec["source_id"],
        "exchange": spec["exchange"],
        "date": spec["date"],
        "method": spec["method"],
        "url": spec["url"],
        "expected_kind": spec["expected_kind"],
        "status": "error",
        "http_status": np.nan,
        "content_type": "",
        "content_bytes": 0,
        "sha256": "",
        "raw_file": "",
        "hash_ready": 0,
        "is_zip": 0,
        "error_type": "",
        "error_message": "",
    }
    try:
        if spec["method"] == "GET":
            response = requests.get(
                spec["url"],
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                verify=bool(spec.get("verify_tls", True)),
            )
        elif spec["method"] == "POST_JSON":
            response = requests.post(
                spec["url"],
                json=spec.get("payload", {}),
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                verify=bool(spec.get("verify_tls", True)),
            )
        else:
            response = requests.post(
                spec["url"],
                data=spec.get("payload", {}),
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
                verify=bool(spec.get("verify_tls", True)),
            )
        content = response.content or b""
        digest = hashlib.sha256(content).hexdigest() if content else ""
        is_zip = zipfile.is_zipfile(BytesIO(content)) if content else False
        content_type = str(response.headers.get("content-type", ""))
        raw_name = f"{spec['probe_id']}.{_extension_for_probe(spec['expected_kind'], content_type, is_zip)}"
        raw_path = RAW_DIR / raw_name
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(content)
        row.update(
            {
                "status": "http_ok" if 200 <= int(response.status_code) < 300 else "http_error",
                "http_status": int(response.status_code),
                "content_type": content_type,
                "content_bytes": int(len(content)),
                "sha256": digest,
                "raw_file": str(raw_path.relative_to(REPO_DIR)),
                "hash_ready": int(bool(digest)),
                "is_zip": int(is_zip),
            }
        )
        row.update(_parse_payload(content, spec["expected_kind"], content_type))
        if row["status"] == "http_ok" and int(row["parse_ready"]) == 1:
            row["status"] = "parsed_ok"
        elif row["status"] == "http_ok":
            row["status"] = "http_ok_parse_failed"
    except Exception as exc:  # noqa: BLE001
        row["status"] = "network_error"
        row["error_type"] = type(exc).__name__
        row["error_message"] = str(exc)[:300]
        row.update(
            {
                "parse_ready": 0,
                "result_kind": "",
                "row_count": 0,
                "key_or_file_count": 0,
                "sample_keys_or_files": "",
                "sample_columns": "",
                "parse_error_type": "",
                "parse_error_message": "",
            }
        )
    return row


WRAPPER_CHILD_CODE = r"""
import json
import sys
import traceback

import akshare as ak
import pandas as pd


def summarize(value):
    if isinstance(value, dict):
        keys = [str(key) for key in value.keys()]
        rows = 0
        columns = []
        nonempty = 0
        for item in value.values():
            if isinstance(item, pd.DataFrame):
                rows += int(len(item))
                if len(item) > 0:
                    nonempty += 1
                    columns.extend([str(col) for col in item.columns])
        return {
            "result_kind": "dict",
            "key_or_file_count": len(keys),
            "nonempty_child_count": nonempty,
            "row_count": rows,
            "sample_keys_or_files": "|".join(keys[:10]),
            "sample_columns": "|".join(sorted(set(columns))[:16]),
        }
    if isinstance(value, pd.DataFrame):
        return {
            "result_kind": "dataframe",
            "key_or_file_count": 0,
            "nonempty_child_count": int(len(value) > 0),
            "row_count": int(len(value)),
            "sample_keys_or_files": "",
            "sample_columns": "|".join(str(col) for col in value.columns[:16]),
        }
    return {
        "result_kind": type(value).__name__,
        "key_or_file_count": 0,
        "nonempty_child_count": 0,
        "row_count": 0,
        "sample_keys_or_files": "",
        "sample_columns": "",
    }


spec = json.loads(sys.argv[1])
try:
    func = getattr(ak, spec["function_name"])
    result = func(*spec.get("args", []), **spec.get("kwargs", {}))
    out = summarize(result)
    out.update(
        {
            "status": "wrapper_ok" if int(out.get("row_count", 0)) > 0 or int(out.get("key_or_file_count", 0)) > 0 else "wrapper_empty",
            "error_type": "",
            "error_message": "",
            "akshare_version": getattr(ak, "__version__", "unknown"),
        }
    )
except Exception as exc:
    out = {
        "status": "wrapper_error",
        "result_kind": "",
        "key_or_file_count": 0,
        "nonempty_child_count": 0,
        "row_count": 0,
        "sample_keys_or_files": "",
        "sample_columns": "",
        "error_type": type(exc).__name__,
        "error_message": str(exc)[:500],
        "traceback_tail": "\n".join(traceback.format_exc().splitlines()[-4:]),
        "akshare_version": getattr(ak, "__version__", "unknown"),
    }
print(json.dumps(out, ensure_ascii=False))
"""


def _run_wrapper_probe(spec: dict[str, Any]) -> dict[str, Any]:
    row = {
        "probe_id": spec["probe_id"],
        "source_id": spec["source_id"],
        "function_name": spec["function_name"],
        "args_json": json.dumps(spec.get("args", []), ensure_ascii=False),
        "kwargs_json": json.dumps(spec.get("kwargs", {}), ensure_ascii=False),
        "status": "wrapper_error",
        "timed_out": 0,
        "result_kind": "",
        "key_or_file_count": 0,
        "nonempty_child_count": 0,
        "row_count": 0,
        "sample_keys_or_files": "",
        "sample_columns": "",
        "error_type": "",
        "error_message": "",
        "akshare_version": "",
    }
    try:
        proc = subprocess.run(
            [sys.executable, "-c", WRAPPER_CHILD_CODE, json.dumps(spec, ensure_ascii=False)],
            cwd=str(REPO_DIR),
            capture_output=True,
            text=True,
            timeout=WRAPPER_TIMEOUT,
            check=False,
        )
        stdout = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
        parsed = json.loads(stdout)
        row.update(parsed)
        row["returncode"] = int(proc.returncode)
        if proc.stderr.strip() and not row.get("error_message"):
            row["error_message"] = proc.stderr.strip()[-500:]
    except subprocess.TimeoutExpired:
        row["status"] = "wrapper_timeout"
        row["timed_out"] = 1
        row["error_type"] = "TimeoutExpired"
        row["error_message"] = f"wrapper exceeded {WRAPPER_TIMEOUT}s"
    except Exception as exc:  # noqa: BLE001
        row["status"] = "wrapper_error"
        row["error_type"] = type(exc).__name__
        row["error_message"] = str(exc)[:500]
    return row


def _source_summary(direct: pd.DataFrame, wrapper: pd.DataFrame) -> pd.DataFrame:
    source_ids = sorted(set(direct["source_id"].tolist()) | set(wrapper["source_id"].tolist()))
    rows: list[dict[str, Any]] = []
    for source_id in source_ids:
        d = direct[direct["source_id"].eq(source_id)]
        w = wrapper[wrapper["source_id"].eq(source_id)]
        direct_count = int(len(d))
        direct_parsed = int(pd.to_numeric(d.get("parse_ready", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        direct_hash = int(pd.to_numeric(d.get("hash_ready", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        wrapper_count = int(len(w))
        wrapper_ok = int(w["status"].isin(["wrapper_ok", "wrapper_empty"]).sum()) if not w.empty else 0
        wrapper_rows = int(pd.to_numeric(w.get("row_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        parse_ready_series = pd.to_numeric(
            d.get("parse_ready", pd.Series(dtype=float)),
            errors="coerce",
        ).fillna(0)
        dates_parsed = sorted(d.loc[parse_ready_series.eq(1), "date"].astype(str).unique()) if not d.empty else []
        historical_smoke_ok = int(any(date < "20230101" for date in dates_parsed))
        recent_smoke_ok = int(any(date >= "20250101" for date in dates_parsed))
        official_raw_hashable = int(direct_hash > 0)
        official_raw_parse_any = int(direct_parsed > 0)
        wrapper_parse_any = int(wrapper_rows > 0)
        smoke_backfill_ready = int(
            direct_count > 0
            and direct_parsed == direct_count
            and historical_smoke_ok
            and recent_smoke_ok
            and wrapper_count > 0
            and wrapper_ok == wrapper_count
        )
        rows.append(
            {
                "source_id": source_id,
                "direct_probe_count": direct_count,
                "direct_parsed_count": direct_parsed,
                "direct_hash_count": direct_hash,
                "wrapper_probe_count": wrapper_count,
                "wrapper_ok_count": wrapper_ok,
                "wrapper_row_count": wrapper_rows,
                "official_raw_hashable": official_raw_hashable,
                "official_raw_parse_any": official_raw_parse_any,
                "wrapper_parse_any": wrapper_parse_any,
                "historical_smoke_ok": historical_smoke_ok,
                "recent_smoke_ok": recent_smoke_ok,
                "smoke_backfill_ready": smoke_backfill_ready,
                "next_action": (
                    "can_design_small_backfill_manifest_but_still_need_full_history_validation"
                    if official_raw_parse_any
                    else "endpoint_or_network_blocked_require_authorized_offline_or_vendor_raw"
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["smoke_backfill_ready", "official_raw_parse_any", "wrapper_parse_any"], ascending=False)


def _summary(curve: pd.DataFrame, direct: pd.DataFrame, wrapper: pd.DataFrame, source_summary: pd.DataFrame) -> pd.DataFrame:
    metrics = _official_metrics(curve)
    direct_parsed = int(pd.to_numeric(direct["parse_ready"], errors="coerce").fillna(0).sum())
    direct_hash = int(pd.to_numeric(direct["hash_ready"], errors="coerce").fillna(0).sum())
    wrapper_ok = int(wrapper["status"].isin(["wrapper_ok", "wrapper_empty"]).sum())
    wrapper_rows = int(pd.to_numeric(wrapper["row_count"], errors="coerce").fillna(0).sum())
    source_backfill_ready = int(source_summary["smoke_backfill_ready"].sum())
    direct_any = direct_parsed > 0
    decision = (
        "stage088_official_raw_smoke_partial_but_not_backfill_ready_no_rule"
        if direct_any
        else "stage088_official_raw_smoke_blocked_no_rule"
    )
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "direct_probe_count": int(len(direct)),
                "direct_parsed_count": direct_parsed,
                "direct_hash_count": direct_hash,
                "wrapper_probe_count": int(len(wrapper)),
                "wrapper_ok_count": wrapper_ok,
                "wrapper_row_count": wrapper_rows,
                "source_count": int(len(source_summary)),
                "smoke_backfill_ready_source_count": source_backfill_ready,
                **metrics,
            }
        ]
    )


def _plot_official_path(curve: pd.DataFrame, summary: pd.Series, source_summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2.0, 1.2, 1.2, 1.2]})
    axes[0].plot(curve["date"], curve["account_equity"], color="#0f766e", linewidth=1.5)
    axes[0].set_title("Stage088 official C9/15w path and official raw-source smoke")
    axes[0].set_ylabel("equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#dc2626", linewidth=1.2)
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#7c3aed", linewidth=1.2)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    axes[2].grid(True, alpha=0.25)
    data = source_summary.sort_values("source_id")
    x = np.arange(len(data))
    axes[3].bar(x - 0.2, data["direct_parsed_count"], width=0.4, color="#2563eb", label="direct parsed")
    axes[3].bar(x + 0.2, data["wrapper_row_count"].clip(upper=500), width=0.4, color="#f97316", label="wrapper rows clipped")
    axes[3].set_xticks(x)
    axes[3].set_xticklabels(data["source_id"], rotation=25, ha="right", fontsize=8)
    axes[3].set_title("Official endpoint smoke: parsed direct probes and wrapper rows")
    axes[3].grid(True, axis="y", alpha=0.25)
    axes[3].legend(loc="upper left")
    fig.suptitle(
        f"Decision={summary['decision']} | smoke backfill ready sources "
        f"{int(summary['smoke_backfill_ready_source_count'])}/{int(summary['source_count'])}",
        y=0.995,
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_endpoint_matrix(direct: pd.DataFrame) -> None:
    pivot = direct.pivot_table(index="probe_id", columns="date", values="parse_ready", aggfunc="max").fillna(0.0)
    fig, ax = plt.subplots(figsize=(9, max(6, 0.35 * len(pivot.index))))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", vmin=0, vmax=1, cmap="RdYlGn")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.astype(str).tolist(), rotation=0)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist(), fontsize=7)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, str(int(pivot.iloc[i, j])), ha="center", va="center", fontsize=8)
    ax.set_title("Stage088 direct official raw endpoint parse-ready matrix")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(ENDPOINT_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_raw_bytes(direct: pd.DataFrame) -> None:
    data = direct.copy()
    data["content_kb"] = pd.to_numeric(data["content_bytes"], errors="coerce").fillna(0.0) / 1024.0
    data = data.sort_values(["exchange", "source_id", "date", "probe_id"])
    fig, ax = plt.subplots(figsize=(14, max(5, 0.32 * len(data))))
    colors = np.where(data["parse_ready"].eq(1), "#16a34a", np.where(data["hash_ready"].eq(1), "#f59e0b", "#dc2626"))
    y = np.arange(len(data))
    ax.barh(y, data["content_kb"], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(data["probe_id"], fontsize=7)
    ax.set_xlabel("response size KB")
    ax.set_title("Raw official responses saved and hashed; green=parsed, amber=hash only, red=none")
    ax.grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(RAW_BYTES_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_next_action(source_summary: pd.DataFrame) -> None:
    gates = [
        "official_raw_hashable",
        "official_raw_parse_any",
        "wrapper_parse_any",
        "historical_smoke_ok",
        "recent_smoke_ok",
        "smoke_backfill_ready",
    ]
    data = source_summary.set_index("source_id")[gates].astype(float)
    fig, ax = plt.subplots(figsize=(10, max(4, 0.4 * len(data.index))))
    im = ax.imshow(data.to_numpy(), aspect="auto", vmin=0, vmax=1, cmap="RdYlGn")
    ax.set_xticks(np.arange(len(gates)))
    ax.set_xticklabels(gates, rotation=30, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index.tolist(), fontsize=8)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, str(int(data.iloc[i, j])), ha="center", va="center", fontsize=9)
    ax.set_title("Stage088 next-action gate: smoke only is not full backfill readiness")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(NEXT_ACTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, direct: pd.DataFrame, wrapper: pd.DataFrame, source_summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    report = "\n".join(
        [
            f"# {STAGE} official external raw source smoke audit",
            "",
            "## Decision",
            "",
            f"- decision: `{row['decision']}`",
            f"- official: `{OFFICIAL_LIVE_ALIAS}` / `{OFFICIAL_LIVE_VERSION}`",
            "- nature: official/raw data-source smoke; no strategy rule, no true engine, no A/B, no CTP, no order API.",
            "",
            "## Official baseline",
            "",
            f"- end equity: `{row['end_equity']:,.2f}`",
            f"- total return: `{row['total_return_pct']:.4f}%`",
            f"- max drawdown: `{row['max_dd_pct']:.4f}%`",
            f"- Sharpe: `{row['sharpe']:.4f}`",
            f"- total slippage: `{row['total_slippage']:,.0f}`",
            f"- total trade count: `{row['total_trade_count']:.0f}`",
            f"- win rate: `{row['win_rate_pct']:.4f}%`",
            f"- broker10 peak: `{row['broker10_peak_margin_to_equity_pct']:.4f}%`",
            "",
            "## Smoke summary",
            "",
            f"- direct probes: `{int(row['direct_probe_count'])}`, parsed `{int(row['direct_parsed_count'])}`, hashed `{int(row['direct_hash_count'])}`",
            f"- wrapper probes: `{int(row['wrapper_probe_count'])}`, ok `{int(row['wrapper_ok_count'])}`, wrapper rows `{int(row['wrapper_row_count'])}`",
            f"- smoke backfill-ready source count: `{int(row['smoke_backfill_ready_source_count'])}/{int(row['source_count'])}`",
            "",
            "## Source summary",
            "",
            _md_table(
                source_summary[
                    [
                        "source_id",
                        "direct_probe_count",
                        "direct_parsed_count",
                        "direct_hash_count",
                        "wrapper_row_count",
                        "historical_smoke_ok",
                        "recent_smoke_ok",
                        "smoke_backfill_ready",
                        "next_action",
                    ]
                ],
                max_rows=30,
            ),
            "",
            "## Direct raw probe sample",
            "",
            _md_table(
                direct[
                    [
                        "probe_id",
                        "status",
                        "http_status",
                        "content_bytes",
                        "parse_ready",
                        "row_count",
                        "key_or_file_count",
                        "raw_file",
                        "error_type",
                        "parse_error_type",
                    ]
                ],
                max_rows=40,
            ),
            "",
            "## AKShare wrapper probe sample",
            "",
            _md_table(
                wrapper[
                    [
                        "probe_id",
                        "status",
                        "row_count",
                        "key_or_file_count",
                        "nonempty_child_count",
                        "error_type",
                        "error_message",
                    ]
                ],
                max_rows=20,
            ),
            "",
            "## Visual outputs",
            "",
            f"- official path raw smoke chart: `{OFFICIAL_PATH_CHART_OUT}`",
            f"- endpoint matrix chart: `{ENDPOINT_MATRIX_CHART_OUT}`",
            f"- raw response bytes chart: `{RAW_BYTES_CHART_OUT}`",
            f"- next action chart: `{NEXT_ACTION_CHART_OUT}`",
            "",
            "## External sources used",
            "",
            "- AKShare futures docs/GitHub document member rank and warehouse receipt interfaces and exchange limitations.",
            "- AKShare changelog shows recent fixes/renames for DCE warehouse, CZCE warehouse, and DCE position rank wrappers.",
            "- GitHub issues in 2026 report DCE position/warehouse and SHFE warehouse wrapper failures, confirming endpoint instability risk.",
            "- Official exchange endpoints are treated as smoke evidence only when raw responses are saved and hashed in this stage.",
            "",
            "## Judgment",
            "",
            "- A successful smoke does not prove full C9 historical coverage; it only proves a route is worth a controlled backfill manifest.",
            "- A failed smoke is not alpha evidence; it is an engineering/provenance blocker.",
            "- No source in this stage is allowed into a strategy rule or A/B.",
        ]
    )
    REPORT_OUT.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    direct = pd.DataFrame([_run_direct_probe(spec) for spec in _direct_specs()])
    wrapper = pd.DataFrame([_run_wrapper_probe(spec) for spec in _wrapper_specs()])
    source_summary = _source_summary(direct, wrapper)
    summary = _summary(curve, direct, wrapper, source_summary)

    _write_csv(direct, DIRECT_PROBE_OUT)
    _write_csv(wrapper, WRAPPER_PROBE_OUT)
    _write_csv(source_summary, SOURCE_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(
        json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_official_path(curve, summary.iloc[0], source_summary)
    _plot_endpoint_matrix(direct)
    _plot_raw_bytes(direct)
    _plot_next_action(source_summary)
    _write_report(summary, direct, wrapper, source_summary)

    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
