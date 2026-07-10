from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage127"
STAGE_ID = "stage127_stage125_top10_loss_window_minute_backfill"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"rebuilt_c9_v2_{STAGE_ID}"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_1502_stage127_stage125_top10_loss_window_minute_backfill.md"

STAGE052_SCRIPT = LINE_DIR / "tools" / "stage052_tqsdk_jd_minute_backfill.py"
STAGE124_FRAMES_DIR = LINE_DIR / "outputs" / "stage124_full_market_single_product_c9_replay" / "frames_by_product"

MINUTE_ROOT = PORTFOLIO_DIR / "downloaded_futures"
BACKFILL_ROOT = MINUTE_ROOT / "tqsdk_stage127_stage125_top10_loss_window_minute_backfill"
TMP_DAY_ROOT = OUT / "tmp_entry_day_downloads"

PLAN_PATH = OUT / f"{OUTPUT_PREFIX}_plan_{MODEL_TAG}.csv"
STATUS_PATH = OUT / f"{OUTPUT_PREFIX}_download_status_{MODEL_TAG}.csv"
AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_content_audit_{MODEL_TAG}.csv"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

LOSS_WINDOW_START = pd.Timestamp("2022-03-09")
LOSS_WINDOW_END = pd.Timestamp("2022-06-29")
PRODUCTS = ["m.DCE", "ni.SHFE", "CY.CZCE", "eb.DCE", "y.DCE", "zn.SHFE", "ag.SHFE", "v.DCE", "PK.CZCE", "rr.DCE"]

ENABLE_DOWNLOAD = os.getenv("STAGE127_ENABLE_DOWNLOAD", "0").strip() == "1"
MAX_SYMBOLS = int(os.getenv("STAGE127_MAX_SYMBOLS", "6"))
MAX_SECONDS_PER_SYMBOL = int(os.getenv("STAGE127_MAX_SECONDS_PER_SYMBOL", "600"))
ENTRY_DAY_ONLY = os.getenv("STAGE127_ENTRY_DAY_ONLY", "1").strip() != "0"

SOURCE_LINKS = {
    "tqsdk_backtest": "https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html",
    "tqsdk_data_downloader": "https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html",
}


def _load_stage052() -> Any:
    spec = importlib.util.spec_from_file_location("stage052_tqsdk_jd_minute_backfill", STAGE052_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE052_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return "" if pd.isna(value) else value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _slug(product: str) -> str:
    return str(product).replace(".", "_").replace("/", "_")


def _output_path_for_contract(contract_vt: str) -> Path:
    symbol, exchange = str(contract_vt).split(".", 1)
    return BACKFILL_ROOT / exchange / f"{symbol}_minute_backtest.csv"


def _tmp_day_path(contract_vt: str, entry_date: str) -> Path:
    symbol, exchange = str(contract_vt).split(".", 1)
    return TMP_DAY_ROOT / exchange / f"{symbol}_{entry_date.replace('-', '')}_minute_backtest.csv"


def _existing_minute_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in MINUTE_ROOT.glob("*/*/*minute_backtest.csv"):
        exchange = path.parent.name
        contract = path.name.replace("_completed_minute_backtest.csv", "").replace("_minute_backtest.csv", "")
        if contract:
            index.setdefault(f"{contract}.{exchange}", path)
    return index


def _entry_date_coverage(path: Path | None, entry_dates_text: str) -> tuple[bool, str, int]:
    entry_dates = [item for item in str(entry_dates_text).split("|") if item]
    if not entry_dates:
        return True, "", 0
    if path is None or not path.exists():
        return False, "|".join(entry_dates), 0
    try:
        data = pd.read_csv(path, encoding="utf-8-sig", usecols=lambda col: col in {"bar_datetime"})
    except Exception:
        return False, "|".join(entry_dates), 0
    if data.empty or "bar_datetime" not in data.columns:
        return False, "|".join(entry_dates), 0
    bar_dates = pd.to_datetime(data["bar_datetime"], errors="coerce").dropna().dt.strftime("%Y-%m-%d")
    covered = set(bar_dates)
    missing = sorted(set(entry_dates) - covered)
    return len(missing) == 0, "|".join(missing), len(set(entry_dates) & covered)


def _date_list(values: pd.Series) -> str:
    dates = sorted({pd.Timestamp(v).date().isoformat() for v in values.dropna()})
    return "|".join(dates)


def build_plan(stage052: Any) -> pd.DataFrame:
    existing = _existing_minute_index()
    rows: list[dict[str, Any]] = []
    for product in PRODUCTS:
        path = STAGE124_FRAMES_DIR / f"{_slug(product)}_closed_lots.csv.gz"
        if not path.exists():
            continue
        lots = pd.read_csv(path)
        lots["entry_date"] = pd.to_datetime(lots.get("entry_date"), errors="coerce").dt.normalize()
        lots["exit_date"] = pd.to_datetime(lots.get("exit_date"), errors="coerce").dt.normalize()
        lots["realized_pnl"] = pd.to_numeric(lots.get("realized_pnl", 0.0), errors="coerce").fillna(0.0)
        overlap = lots[
            lots["entry_date"].between(LOSS_WINDOW_START, LOSS_WINDOW_END)
            | lots["exit_date"].between(LOSS_WINDOW_START, LOSS_WINDOW_END)
        ].copy()
        for contract, group in overlap.groupby("vt_symbol", dropna=False):
            contract_text = str(contract)
            contract_lots = lots[lots["vt_symbol"].astype(str).eq(contract_text)].copy()
            entry_dates = contract_lots["entry_date"].dropna()
            if entry_dates.empty:
                continue
            existing_path = existing.get(contract_text)
            output_path = _output_path_for_contract(contract_text)
            all_entry_dates_text = _date_list(entry_dates)
            coverage_path = output_path if output_path.exists() else existing_path
            already_ready, missing_entry_dates_text, covered_entry_date_count = _entry_date_coverage(
                coverage_path, all_entry_dates_text
            )
            requested_entry_dates_text = "" if already_ready else missing_entry_dates_text
            requested_entry_date_count = len([item for item in requested_entry_dates_text.split("|") if item])
            request_start = entry_dates.min()
            request_end = entry_dates.max()
            requested_dates = pd.to_datetime(
                [item for item in requested_entry_dates_text.split("|") if item],
                errors="coerce",
            )
            if len(requested_dates):
                request_start = pd.Series(requested_dates).dropna().min()
                request_end = pd.Series(requested_dates).dropna().max()
            rows.append(
                {
                    "contract_vt": contract_text,
                    "product_vt_symbol": product,
                    "tq_symbol": stage052.to_tqsdk_symbol(contract_text),
                    "request_start_date": request_start.date().isoformat(),
                    "request_end_date": request_end.date().isoformat(),
                    "download_start_datetime": stage052._download_start(request_start).isoformat(),
                    "download_end_datetime": stage052._download_end(request_end).isoformat(),
                    "entry_date_count": int(requested_entry_date_count),
                    "entry_dates": requested_entry_dates_text,
                    "all_entry_date_count": int(entry_dates.nunique()),
                    "all_entry_dates": all_entry_dates_text,
                    "covered_entry_date_count": int(covered_entry_date_count),
                    "window_overlap_lots": int(len(group)),
                    "all_contract_lots": int(len(contract_lots)),
                    "abs_realized_pnl": float(contract_lots["realized_pnl"].abs().sum()),
                    "window_abs_realized_pnl": float(group["realized_pnl"].abs().sum()),
                    "existing_file": str(coverage_path) if coverage_path is not None else "",
                    "already_ready": bool(already_ready),
                    "output_path": str(output_path),
                }
            )
    plan = pd.DataFrame(rows)
    if plan.empty:
        return plan
    plan = plan[~plan["already_ready"].astype(bool)].copy()
    plan = plan.sort_values(
        ["window_abs_realized_pnl", "abs_realized_pnl", "entry_date_count", "contract_vt"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    plan["priority_rank"] = np.arange(1, len(plan) + 1)
    if MAX_SYMBOLS > 0:
        plan = plan.head(MAX_SYMBOLS).copy()
    columns = [
        "priority_rank",
        "contract_vt",
        "product_vt_symbol",
        "tq_symbol",
        "request_start_date",
        "request_end_date",
        "download_start_datetime",
        "download_end_datetime",
        "entry_date_count",
        "entry_dates",
        "all_entry_date_count",
        "all_entry_dates",
        "covered_entry_date_count",
        "window_overlap_lots",
        "all_contract_lots",
        "window_abs_realized_pnl",
        "abs_realized_pnl",
        "existing_file",
        "already_ready",
        "output_path",
    ]
    return plan[columns].reset_index(drop=True)


def _empty_status() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "contract_vt",
            "tq_symbol",
            "download_start_datetime",
            "download_end_datetime",
            "status",
            "rows",
            "first_bar_datetime",
            "last_bar_datetime",
            "elapsed_seconds",
            "output_path",
            "sha256",
            "message",
        ]
    )


def _expand_entry_day_plan(plan: pd.DataFrame) -> pd.DataFrame:
    if plan.empty:
        return plan.copy()
    rows: list[dict[str, Any]] = []
    for row in plan.itertuples(index=False):
        entry_dates = [item for item in str(row.entry_dates).split("|") if item]
        for entry_date in entry_dates:
            start = pd.Timestamp(entry_date)
            rows.append(
                {
                    "priority_rank": int(row.priority_rank),
                    "contract_vt": str(row.contract_vt),
                    "product_vt_symbol": str(row.product_vt_symbol),
                    "tq_symbol": str(row.tq_symbol),
                    "request_start_date": entry_date,
                    "request_end_date": entry_date,
                    "download_start_datetime": start.isoformat(),
                    "download_end_datetime": (start + timedelta(days=1)).isoformat(),
                    "entry_date": entry_date,
                    "entry_date_count": 1,
                    "entry_dates": entry_date,
                    "parent_output_path": str(row.output_path),
                    "output_path": str(_tmp_day_path(str(row.contract_vt), entry_date)),
                }
            )
    return pd.DataFrame(rows).sort_values(["priority_rank", "entry_date"]).reset_index(drop=True)


def _merge_day_downloads(day_plan: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if day_plan.empty:
        return pd.DataFrame()
    for contract, group in day_plan.groupby("contract_vt", sort=False):
        parent_path = Path(str(group["parent_output_path"].iloc[0]))
        frames: list[pd.DataFrame] = []
        source_paths: list[str] = []
        if parent_path.exists():
            try:
                existing = pd.read_csv(parent_path, encoding="utf-8-sig")
                if not existing.empty:
                    frames.append(existing)
                    source_paths.append(str(parent_path))
            except Exception:
                pass
        for row in group.itertuples(index=False):
            path = Path(str(row.output_path))
            if not path.exists():
                continue
            try:
                frame = pd.read_csv(path, encoding="utf-8-sig")
            except Exception:
                continue
            if not frame.empty:
                frames.append(frame)
                source_paths.append(str(path))
        if frames:
            data = pd.concat(frames, ignore_index=True, sort=False)
            data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
            data = data.dropna(subset=["bar_datetime"]).copy()
            data = data.sort_values(["vt_symbol", "bar_datetime"]).drop_duplicates(["vt_symbol", "bar_datetime"])
            data["bar_datetime"] = data["bar_datetime"].dt.strftime("%Y-%m-%d %H:%M:%S")
            parent_path.parent.mkdir(parents=True, exist_ok=True)
            data.to_csv(parent_path, index=False, encoding="utf-8-sig")
            rows.append(
                {
                    "contract_vt": str(contract),
                    "merged_output_path": str(parent_path),
                    "source_day_file_count": len(source_paths),
                    "rows": int(len(data)),
                    "first_bar_datetime": str(data["bar_datetime"].iloc[0]) if len(data) else "",
                    "last_bar_datetime": str(data["bar_datetime"].iloc[-1]) if len(data) else "",
                    "sha256": _sha256(parent_path),
                    "source_day_files": "|".join(source_paths),
                }
            )
        else:
            rows.append(
                {
                    "contract_vt": str(contract),
                    "merged_output_path": str(parent_path),
                    "source_day_file_count": 0,
                    "rows": 0,
                    "first_bar_datetime": "",
                    "last_bar_datetime": "",
                    "sha256": "",
                    "source_day_files": "",
                }
            )
    return pd.DataFrame(rows)


def _run_download(stage052: Any, plan: pd.DataFrame) -> pd.DataFrame:
    if plan.empty:
        return _empty_status()
    if ENTRY_DAY_ONLY:
        day_plan = _expand_entry_day_plan(plan)
        if day_plan.empty:
            return _empty_status()
        status, _ = stage052.run_backfill_download(day_plan, MAX_SECONDS_PER_SYMBOL)
        merge_status = _merge_day_downloads(day_plan)
        if not merge_status.empty:
            status = status.merge(merge_status, on="contract_vt", how="left")
        return status
    status, _ = stage052.run_backfill_download(plan, MAX_SECONDS_PER_SYMBOL)
    return status


def _audit_contract(row: Any) -> dict[str, Any]:
    output_path = Path(str(row.output_path))
    entry_dates = [item for item in str(row.entry_dates).split("|") if item]
    result: dict[str, Any] = {
        "contract_vt": str(row.contract_vt),
        "product_vt_symbol": str(row.product_vt_symbol),
        "output_path": str(output_path),
        "exists": output_path.exists(),
        "rows": 0,
        "first_bar_datetime": "",
        "last_bar_datetime": "",
        "sha256": "",
        "entry_date_count": int(row.entry_date_count),
        "entry_dates": str(row.entry_dates),
        "covered_entry_date_count": 0,
        "missing_entry_dates": str(row.entry_dates),
        "duplicate_key_count": 0,
        "ohlc_null_count": 0,
        "ohlc_relation_error_count": 0,
        "negative_volume_count": 0,
        "read_error": "",
        "strict_enough_for_entry_days": False,
    }
    if not output_path.exists():
        return result
    try:
        data = pd.read_csv(output_path, encoding="utf-8-sig")
    except Exception as exc:  # pragma: no cover
        result["read_error"] = repr(exc)
        return result
    if data.empty:
        return result
    required = ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        result["read_error"] = "missing_columns:" + ",".join(missing)
        return result
    data["bar_datetime_ts"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data = data.dropna(subset=["bar_datetime_ts"]).copy()
    for column in ["open", "high", "low", "close", "volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["bar_date"] = data["bar_datetime_ts"].dt.strftime("%Y-%m-%d")
    covered = sorted(set(data["bar_date"]) & set(entry_dates))
    missing_entry_dates = sorted(set(entry_dates) - set(covered))
    result.update(
        {
            "rows": int(len(data)),
            "first_bar_datetime": str(data["bar_datetime_ts"].min()),
            "last_bar_datetime": str(data["bar_datetime_ts"].max()),
            "sha256": _sha256(output_path),
            "covered_entry_date_count": int(len(covered)),
            "missing_entry_dates": "|".join(missing_entry_dates),
            "duplicate_key_count": int(data.duplicated(["vt_symbol", "bar_datetime_ts"]).sum()),
            "ohlc_null_count": int(data[["open", "high", "low", "close"]].isna().sum().sum()),
            "ohlc_relation_error_count": int(((data["high"] < data[["open", "close", "low"]].max(axis=1)) | (data["low"] > data[["open", "close", "high"]].min(axis=1))).sum()),
            "negative_volume_count": int(data["volume"].lt(0).sum()),
        }
    )
    result["strict_enough_for_entry_days"] = (
        result["exists"]
        and result["rows"] > 0
        and result["covered_entry_date_count"] == result["entry_date_count"]
        and result["duplicate_key_count"] == 0
        and result["ohlc_null_count"] == 0
        and result["ohlc_relation_error_count"] == 0
        and result["negative_volume_count"] == 0
        and not result["read_error"]
    )
    return result


def audit_downloads(plan: pd.DataFrame) -> pd.DataFrame:
    if plan.empty:
        return pd.DataFrame()
    return pd.DataFrame([_audit_contract(row) for row in plan.itertuples(index=False)])


def summarize(plan: pd.DataFrame, status: pd.DataFrame, audit: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {"metric": "download_enabled", "value": str(bool(ENABLE_DOWNLOAD))},
        {"metric": "entry_day_only", "value": str(bool(ENTRY_DAY_ONLY))},
        {"metric": "planned_contract_count", "value": str(int(len(plan)))},
        {"metric": "downloaded_contract_count", "value": str(int((status.get("status", pd.Series(dtype=str)).astype(str).eq("downloaded")).sum())) if not status.empty else "0"},
        {"metric": "downloaded_rows", "value": str(int(pd.to_numeric(status.get("rows", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())) if not status.empty else "0"},
        {"metric": "strict_entry_day_ready_count", "value": str(int(audit.get("strict_enough_for_entry_days", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())) if not audit.empty else "0"},
        {"metric": "order_api_called", "value": "0"},
        {"metric": "ctp_connected", "value": "False"},
    ]
    return pd.DataFrame(rows)


def make_decision(plan: pd.DataFrame, status: pd.DataFrame, audit: pd.DataFrame) -> dict[str, Any]:
    downloaded = int((status.get("status", pd.Series(dtype=str)).astype(str).eq("downloaded")).sum()) if not status.empty else 0
    strict_ready = (
        int(audit.get("strict_enough_for_entry_days", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
        if not audit.empty
        else 0
    )
    if not ENABLE_DOWNLOAD:
        decision = "stage127_plan_only_download_disabled"
    elif downloaded == 0:
        decision = "stage127_download_failed_or_empty"
    elif strict_ready < len(plan):
        decision = "stage127_partial_minute_backfill_needs_more_audit"
    else:
        decision = "stage127_batch_minute_backfill_success_raw_files_only"
    return {
        "stage": STAGE,
        "stage_id": STAGE_ID,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "scope": "Stage125 top10 products, 2022 loss-window overlapping contracts, prioritized by window absolute realized PnL.",
        "download_enabled": bool(ENABLE_DOWNLOAD),
        "max_symbols": int(MAX_SYMBOLS),
        "max_seconds_per_symbol": int(MAX_SECONDS_PER_SYMBOL),
        "entry_day_only": bool(ENTRY_DAY_ONLY),
        "planned_contract_count": int(len(plan)),
        "downloaded_contract_count": downloaded,
        "strict_entry_day_ready_count": strict_ready,
        "raw_minute_files_written_only": True,
        "stage861_full_minute_source_updated": False,
        "strategy_rule_changed": False,
        "true_engine_run": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_reflection_before": "否。本阶段补的是既有 Stage125 暴露出的分钟数据缺口，不根据补数结果调策略参数。",
        "overfit_reflection_after": "否。若下载成功，只提高数据完整性，不构成策略优化。",
        "continue_value_before": "有。Stage126 已证明 Stage125 前十品种日级账本自洽但分钟缺口影响 stop/retry 置信度，补入口日分钟线有明确价值。",
        "continue_value_after": "有。下一步需要把补到的原始分钟文件合并进 Stage861 或新建覆盖版 full-minute 源，再重跑 Stage124/125。",
        "source_links": SOURCE_LINKS,
        "outputs": {
            "plan": str(PLAN_PATH),
            "status": str(STATUS_PATH),
            "audit": str(AUDIT_PATH),
            "summary": str(SUMMARY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }


def write_report(decision: dict[str, Any], plan: pd.DataFrame, status: pd.DataFrame, audit: pd.DataFrame, summary: pd.DataFrame) -> None:
    lines = [
        "# Stage127 Stage125 前十品种窗口合约分钟补数",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：数据补齐；不回测收益，不改策略，不连接 CTP，不调用订单 API。",
        "- 说明：本阶段只把原始分钟文件写入 `downloaded_futures/tqsdk_stage127_stage125_top10_loss_window_minute_backfill`；Stage861 full-minute 源尚未更新。",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk `TqBacktest + get_kline_serial` 可按历史时间推进拿分钟 K；DataDownloader 更适合长期批量历史下载但可能需要专业版权限。",
        "- 我的判断：先补实际交易合约入口日分钟线，是验证 Stage125 stop/retry 口径的最小可行数据工程。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Plan",
        "",
        _md_table(plan, max_rows=80),
        "",
        "## Download Status",
        "",
        _md_table(status, max_rows=80),
        "",
        "## Content Audit",
        "",
        _md_table(audit, max_rows=80),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stage_record(decision: dict[str, Any], plan: pd.DataFrame, status: pd.DataFrame, audit: pd.DataFrame, summary: pd.DataFrame) -> None:
    lines = [
        "# Stage127 Stage125 前十品种窗口合约分钟补数",
        "",
        f"- 时间：{decision['generated_at']}",
        f"- line_id：`{LINE_ID}`",
        "- 类型：数据补齐，不是新策略版本，不是新回测",
        f"- decision：`{decision['decision']}`",
        f"- download_enabled：`{decision['download_enabled']}`",
        f"- planned_contract_count：`{decision['planned_contract_count']}`",
        f"- downloaded_contract_count：`{decision['downloaded_contract_count']}`",
        f"- strict_entry_day_ready_count：`{decision['strict_entry_day_ready_count']}`",
        "- 策略变更：无",
        "- true engine run：无",
        "- 订单 API：`0`",
        "- CTP：`False`",
        "- Stage861 full-minute 源更新：`False`",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Plan",
        "",
        _md_table(plan, max_rows=80),
        "",
        "## Download Status",
        "",
        _md_table(status, max_rows=80),
        "",
        "## Content Audit",
        "",
        _md_table(audit, max_rows=80),
        "",
        "## 后续",
        "",
        "- 若本批成功，继续补剩余窗口合约或全样本入场合约。",
        "- 补完后需要合并到 Stage861 或新建覆盖版 full-minute 源，再重跑 Stage124/125 才能改变回测结论。",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    BACKFILL_ROOT.mkdir(parents=True, exist_ok=True)
    stage052 = _load_stage052()
    plan = build_plan(stage052)
    status = _run_download(stage052, plan) if ENABLE_DOWNLOAD else _empty_status()
    audit = audit_downloads(plan)
    summary = summarize(plan, status, audit)
    decision = make_decision(plan, status, audit)

    plan.to_csv(PLAN_PATH, index=False, encoding="utf-8-sig")
    status.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    audit.to_csv(AUDIT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(decision, plan, status, audit, summary)
    write_stage_record(decision, plan, status, audit, summary)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
