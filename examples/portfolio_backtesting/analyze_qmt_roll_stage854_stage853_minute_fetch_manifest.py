from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
RAW_ROOT = PROJECT_DIR / "downloaded_futures"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage854"
MODEL_TAG = "stage854_stage853_minute_fetch_manifest_v1"
OUTPUT_PREFIX = "qmt_roll_stage854_stage853_minute_fetch_manifest"

STAGE853_PREFIX = "qmt_roll_stage853_stage852_minute_gap_audit"
STAGE853_TAG = "stage853_stage852_minute_gap_audit_v1"
STAGE853_DETAIL_PATH = OUTPUT_DIR / f"{STAGE853_PREFIX}_gap_detail_{STAGE853_TAG}.csv"
STAGE853_FETCH_PLAN_PATH = OUTPUT_DIR / f"{STAGE853_PREFIX}_fetch_plan_by_symbol_{STAGE853_TAG}.csv"
STAGE853_DECISION_PATH = OUTPUT_DIR / f"{STAGE853_PREFIX}_decision_{STAGE853_TAG}.json"

REQUEST_PREFLIGHT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_preflight_{MODEL_TAG}.csv"
LOCAL_IMPORT_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_import_manifest_{MODEL_TAG}.csv"
DOWNLOAD_BATCH_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_batch_manifest_{MODEL_TAG}.csv"
SYMBOL_PREFLIGHT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_symbol_preflight_{MODEL_TAG}.csv"
ROOT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_root_summary_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

RAW_FILE_PATTERNS = ("{symbol}_minute*.csv",)
DOWNLOAD_START_HOUR = 20
DOWNLOAD_END_HOUR = 3
MAX_BATCH_GAP_DAYS = 7


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _normal_date_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _to_tqsdk_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _split_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return symbol, exchange


def _candidate_raw_paths(vt_symbol: str) -> list[Path]:
    symbol, exchange = _split_vt_symbol(vt_symbol)
    paths: list[Path] = []
    if not RAW_ROOT.exists():
        return paths
    for root in sorted(path for path in RAW_ROOT.iterdir() if path.is_dir()):
        exchange_dir = root / exchange
        if not exchange_dir.exists():
            continue
        for pattern in RAW_FILE_PATTERNS:
            paths.extend(sorted(exchange_dir.glob(pattern.format(symbol=symbol))))
    return sorted({path.resolve() for path in paths})


def _normalize_datetime_column(frame: pd.DataFrame) -> pd.Series:
    if "bar_datetime" in frame.columns:
        raw = frame["bar_datetime"]
    elif "datetime" in frame.columns:
        raw = frame["datetime"]
    else:
        return pd.Series(pd.NaT, index=frame.index)
    if pd.api.types.is_numeric_dtype(raw):
        return pd.to_datetime(raw, unit="ns", errors="coerce", utc=True).dt.tz_convert(
            "Asia/Shanghai"
        ).dt.tz_localize(None)
    parsed = pd.to_datetime(raw, errors="coerce")
    if getattr(parsed.dt, "tz", None) is not None:
        parsed = parsed.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
    return parsed


def _read_raw_date_counts(path: Path, required_dates: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "raw_root": path.parents[1].name if len(path.parents) >= 2 else "",
        "rows": 0,
        "first_datetime": "",
        "last_datetime": "",
        "date_counts": {},
        "status": "unknown",
        "message": "",
    }
    try:
        frame = pd.read_csv(
            path,
            usecols=lambda column: column in {"bar_datetime", "datetime"},
            encoding="utf-8-sig",
        )
    except Exception as exc:
        result["status"] = "read_failed"
        result["message"] = repr(exc)
        return result
    if frame.empty:
        result["status"] = "empty"
        return result
    dt = _normalize_datetime_column(frame)
    dt = dt.dropna()
    result["rows"] = int(len(frame))
    if dt.empty:
        result["status"] = "no_valid_datetime"
        return result
    date_text = dt.dt.strftime("%Y-%m-%d")
    counts = date_text.value_counts().to_dict()
    result["first_datetime"] = pd.Timestamp(dt.min()).strftime("%Y-%m-%d %H:%M:%S")
    result["last_datetime"] = pd.Timestamp(dt.max()).strftime("%Y-%m-%d %H:%M:%S")
    result["date_counts"] = {date: int(counts.get(date, 0)) for date in sorted(required_dates)}
    result["status"] = "readable"
    return result


def _build_raw_index(detail: pd.DataFrame) -> tuple[dict[str, dict[str, Any]], pd.DataFrame]:
    symbol_dates = (
        detail.groupby("vt_symbol", dropna=False)["required_date"]
        .apply(lambda series: sorted(set(series.astype(str))))
        .to_dict()
    )
    symbol_index: dict[str, dict[str, Any]] = {}
    raw_rows: list[dict[str, Any]] = []
    for vt_symbol, dates in symbol_dates.items():
        required_dates = set(dates)
        per_date_best: dict[str, dict[str, Any]] = {
            date: {
                "local_raw_date_bars": 0,
                "best_raw_path": "",
                "best_raw_root": "",
                "best_raw_rows": 0,
                "best_raw_first_datetime": "",
                "best_raw_last_datetime": "",
            }
            for date in dates
        }
        raw_paths = _candidate_raw_paths(str(vt_symbol))
        for path in raw_paths:
            info = _read_raw_date_counts(path, required_dates)
            raw_rows.append(
                {
                    "vt_symbol": str(vt_symbol),
                    "tq_symbol": _to_tqsdk_symbol(str(vt_symbol)),
                    "raw_root": info["raw_root"],
                    "raw_path": info["path"],
                    "status": info["status"],
                    "rows": info["rows"],
                    "first_datetime": info["first_datetime"],
                    "last_datetime": info["last_datetime"],
                    "message": info["message"],
                    "covered_required_dates": int(
                        sum(1 for count in info.get("date_counts", {}).values() if int(count) > 0)
                    ),
                    "required_dates": len(required_dates),
                }
            )
            if info["status"] != "readable":
                continue
            for date, count_value in info["date_counts"].items():
                count = int(count_value)
                current = per_date_best[date]
                if count > int(current["local_raw_date_bars"]):
                    current.update(
                        {
                            "local_raw_date_bars": count,
                            "best_raw_path": info["path"],
                            "best_raw_root": info["raw_root"],
                            "best_raw_rows": int(info["rows"]),
                            "best_raw_first_datetime": info["first_datetime"],
                            "best_raw_last_datetime": info["last_datetime"],
                        }
                    )
        symbol_index[str(vt_symbol)] = {
            "required_dates": dates,
            "raw_path_count": len(raw_paths),
            "per_date_best": per_date_best,
        }
    return symbol_index, pd.DataFrame(raw_rows)


def _request_preflight(detail: pd.DataFrame, symbol_index: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in detail.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        date_text = _normal_date_text(row.required_date)
        item = symbol_index.get(vt_symbol, {})
        best = item.get("per_date_best", {}).get(date_text, {})
        local_bars = int(best.get("local_raw_date_bars", 0) or 0)
        if local_bars > 0:
            action = "local_raw_import_candidate"
        elif int(item.get("raw_path_count", 0) or 0) > 0:
            action = "download_exact_contract_date"
        else:
            action = "download_exact_contract_full_symbol"
        rows.append(
            {
                **row._asdict(),
                "required_date": date_text,
                "tq_symbol": _to_tqsdk_symbol(vt_symbol),
                "local_action": action,
                "local_raw_date_bars": local_bars,
                "best_raw_root": str(best.get("best_raw_root", "")),
                "best_raw_path": str(best.get("best_raw_path", "")),
                "best_raw_rows": int(best.get("best_raw_rows", 0) or 0),
                "best_raw_first_datetime": str(best.get("best_raw_first_datetime", "")),
                "best_raw_last_datetime": str(best.get("best_raw_last_datetime", "")),
                "raw_path_count_for_symbol": int(item.get("raw_path_count", 0) or 0),
            }
        )
    return pd.DataFrame(rows)


def _local_import_manifest(preflight: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "request_type",
        "source_id",
        "vt_symbol",
        "tq_symbol",
        "product",
        "required_date",
        "direction",
        "priority_abs_pnl",
        "realized_pnl",
        "big_winner",
        "local_raw_date_bars",
        "best_raw_root",
        "best_raw_path",
        "best_raw_first_datetime",
        "best_raw_last_datetime",
    ]
    data = preflight[preflight["local_raw_date_bars"].fillna(0).gt(0)].copy()
    if data.empty:
        return pd.DataFrame(columns=cols)
    return data[cols].sort_values(["priority_abs_pnl", "vt_symbol"], ascending=[False, True]).reset_index(drop=True)


def _group_dates_into_batches(dates: list[str]) -> list[tuple[pd.Timestamp, pd.Timestamp, list[str]]]:
    parsed = [pd.Timestamp(date) for date in sorted(set(dates))]
    if not parsed:
        return []
    batches: list[list[pd.Timestamp]] = [[parsed[0]]]
    for date in parsed[1:]:
        if (date - batches[-1][-1]).days <= MAX_BATCH_GAP_DAYS:
            batches[-1].append(date)
        else:
            batches.append([date])
    return [(batch[0], batch[-1], [date.strftime("%Y-%m-%d") for date in batch]) for batch in batches]


def _download_batch_manifest(preflight: pd.DataFrame) -> pd.DataFrame:
    missing = preflight[preflight["local_raw_date_bars"].fillna(0).le(0)].copy()
    if missing.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for vt_symbol, group in missing.groupby("vt_symbol", sort=True):
        dates = sorted(set(group["required_date"].astype(str)))
        for batch_index, (start_date, end_date, batch_dates) in enumerate(_group_dates_into_batches(dates), start=1):
            download_start = (start_date - timedelta(days=1)).replace(hour=DOWNLOAD_START_HOUR)
            download_end = (end_date + timedelta(days=1)).replace(hour=DOWNLOAD_END_HOUR)
            rows.append(
                {
                    "vt_symbol": str(vt_symbol),
                    "tq_symbol": _to_tqsdk_symbol(str(vt_symbol)),
                    "product": str(group["product"].mode().iloc[0]),
                    "batch_index": batch_index,
                    "missing_dates": len(batch_dates),
                    "missing_date_list": ",".join(batch_dates),
                    "first_missing_date": start_date.strftime("%Y-%m-%d"),
                    "last_missing_date": end_date.strftime("%Y-%m-%d"),
                    "download_start_dt": download_start.strftime("%Y-%m-%d %H:%M:%S"),
                    "download_end_dt": download_end.strftime("%Y-%m-%d %H:%M:%S"),
                    "priority_abs_pnl": float(group.loc[group["required_date"].isin(batch_dates), "priority_abs_pnl"].sum()),
                    "big_winner_requests": int(group.loc[group["required_date"].isin(batch_dates), "big_winner"].sum()),
                    "request_types": ",".join(sorted(group["request_type"].astype(str).unique())),
                    "root_causes": ",".join(sorted(group["root_cause"].astype(str).unique())),
                    "raw_path_count_for_symbol": int(group["raw_path_count_for_symbol"].max()),
                    "suggested_raw_path": str(
                        RAW_ROOT
                        / f"tqsdk_{STAGE.lower()}_gap_backfill"
                        / str(vt_symbol).split(".", 1)[1]
                        / f"{str(vt_symbol).split('.', 1)[0]}_minute_backtest.csv"
                    ),
                }
            )
    return (
        pd.DataFrame(rows)
        .sort_values(["priority_abs_pnl", "missing_dates", "vt_symbol"], ascending=[False, False, True])
        .reset_index(drop=True)
    )


def _symbol_preflight(preflight: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for vt_symbol, group in preflight.groupby("vt_symbol", sort=True):
        local = group[group["local_raw_date_bars"].fillna(0).gt(0)]
        missing = group[group["local_raw_date_bars"].fillna(0).le(0)]
        rows.append(
            {
                "vt_symbol": str(vt_symbol),
                "tq_symbol": _to_tqsdk_symbol(str(vt_symbol)),
                "product": str(group["product"].mode().iloc[0]),
                "requests": int(len(group)),
                "required_dates": int(group["required_date"].nunique()),
                "local_recoverable_requests": int(len(local)),
                "local_recoverable_dates": int(local["required_date"].nunique()),
                "needs_download_requests": int(len(missing)),
                "needs_download_dates": int(missing["required_date"].nunique()),
                "priority_abs_pnl_total": float(group["priority_abs_pnl"].sum()),
                "priority_abs_pnl_local_recoverable": float(local["priority_abs_pnl"].sum()),
                "priority_abs_pnl_needs_download": float(missing["priority_abs_pnl"].sum()),
                "big_winner_total": int(group["big_winner"].sum()),
                "big_winner_local_recoverable": int(local["big_winner"].sum()),
                "big_winner_needs_download": int(missing["big_winner"].sum()),
                "raw_path_count_for_symbol": int(group["raw_path_count_for_symbol"].max()),
                "local_roots": ",".join(sorted(set(local["best_raw_root"].astype(str)) - {""})),
                "download_date_list": ",".join(sorted(set(missing["required_date"].astype(str)))),
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["priority_abs_pnl_needs_download", "priority_abs_pnl_local_recoverable"], ascending=False)
        .reset_index(drop=True)
    )


def _raw_root_summary(raw_rows: pd.DataFrame) -> pd.DataFrame:
    if raw_rows.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for root, group in raw_rows.groupby("raw_root", dropna=False):
        rows.append(
            {
                "raw_root": str(root),
                "files": int(len(group)),
                "readable_files": int(group["status"].astype(str).eq("readable").sum()),
                "symbols": int(group["vt_symbol"].nunique()),
                "covered_required_dates_sum": int(group["covered_required_dates"].sum()),
                "rows": int(pd.to_numeric(group["rows"], errors="coerce").fillna(0).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["covered_required_dates_sum", "files"], ascending=False).reset_index(drop=True)


def _summary(
    preflight: pd.DataFrame,
    local_manifest: pd.DataFrame,
    download_manifest: pd.DataFrame,
    symbol_preflight: pd.DataFrame,
    raw_root_summary: pd.DataFrame,
) -> pd.DataFrame:
    local = preflight[preflight["local_raw_date_bars"].fillna(0).gt(0)]
    missing = preflight[preflight["local_raw_date_bars"].fillna(0).le(0)]
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "decision": "stage854_local_raw_partial_recovery_then_download_manifest_no_rule",
                "gap_requests": int(len(preflight)),
                "gap_symbols": int(preflight["vt_symbol"].nunique()),
                "local_raw_recoverable_requests": int(len(local)),
                "local_raw_recoverable_symbols": int(local["vt_symbol"].nunique()),
                "still_needs_download_requests": int(len(missing)),
                "still_needs_download_symbols": int(missing["vt_symbol"].nunique()),
                "download_batches": int(len(download_manifest)),
                "priority_abs_pnl_local_recoverable": float(local["priority_abs_pnl"].sum()),
                "priority_abs_pnl_still_needs_download": float(missing["priority_abs_pnl"].sum()),
                "big_winner_local_recoverable": int(local["big_winner"].sum()),
                "big_winner_still_needs_download": int(missing["big_winner"].sum()),
                "raw_roots_with_hits": int(
                    raw_root_summary[raw_root_summary["covered_required_dates_sum"].fillna(0).gt(0)]["raw_root"].nunique()
                )
                if not raw_root_summary.empty
                else 0,
                "symbols_with_existing_raw_but_wrong_dates": int(
                    symbol_preflight[
                        symbol_preflight["raw_path_count_for_symbol"].fillna(0).gt(0)
                        & symbol_preflight["local_recoverable_requests"].fillna(0).eq(0)
                    ]["vt_symbol"].nunique()
                )
                if not symbol_preflight.empty
                else 0,
                "new_rule_allowed": 0,
                "engine_allowed": 0,
            }
        ]
    )


def _write_report(
    summary: pd.DataFrame,
    symbol_preflight: pd.DataFrame,
    local_manifest: pd.DataFrame,
    download_manifest: pd.DataFrame,
    raw_root_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    top_local = symbol_preflight[symbol_preflight["local_recoverable_requests"].fillna(0).gt(0)].head(20)
    top_download = symbol_preflight[symbol_preflight["needs_download_requests"].fillna(0).gt(0)].head(25)
    lines = [
        "# Stage854 Stage853后分钟K补数清单与本地raw预检",
        "",
        "## 阶段定位",
        "",
        "- 阶段性质：数据补齐预检；不下载数据、不改策略、不接引擎、不连接 CTP、不调用下单。",
        "- 目标：把 Stage853 的 exact contract/date 缺口拆成“本地 raw 已有但未合并”和“仍需外部补数”，形成下一步可执行 manifest。",
        "",
        "## 外部/GitHub调研判断",
        "",
        "- TqSdk 官方文档显示 `DataDownloader` 用于下载静态历史数据到 CSV，适合作为本阶段后续 exact contract/date 补数工具。",
        "- TqSdk `get_kline_serial` 更适合实时/近端序列引用，且历史序列长度有限；本线不把它作为全周期缺口补数主路径。",
        "- GitHub 上 `shinnytech/tqsdk-python` 与 `vnpy/vnpy_tqsdk` 说明仓库现有 DataDownloader/TqSdk 路径可复用，但旧合约和权限问题必须单独记录为数据阻断，不能解释成策略现象。",
        "",
        "## 核心摘要",
        "",
        _md_table(summary),
        "",
        "## raw目录覆盖汇总",
        "",
        _md_table(raw_root_summary, max_rows=30),
        "",
        "## 本地raw可恢复优先级",
        "",
        _md_table(top_local, max_rows=20),
        "",
        "## 仍需下载优先级",
        "",
        _md_table(top_download, max_rows=25),
        "",
        "## 下载批次样例",
        "",
        _md_table(download_manifest.head(25), max_rows=25),
        "",
        "## 结论",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        "- 本阶段不写交易规则。下一步应先把本地 raw 可恢复部分合并为一个 Stage819 本线专用分钟源，再对仍缺部分按 download manifest 补数。",
        "- exact 合约当天有 raw 数据时，优先做导入/合并，不重复下载；exact 合约当天没有 raw 数据时，才用 TqSdk DataDownloader 补。",
        "- 不能用同产品其他合约替代 exact 合约路径，也不能用 raw 覆盖率去筛年份、品种或方向。",
        "",
        "## 反思",
        "",
        "- 运行前过拟合判断：否。只处理数据覆盖与下载路径，不选择规则、不救阈值。",
        "- 运行后过拟合判断：否。发现本地 raw 可恢复只说明数据管道未合并，不改变策略解释。",
        "- 运行前继续价值判断：有价值。Stage853 证明缺口影响大，本阶段能减少无效重复下载。",
        "- 运行后继续价值判断：有价值。若先导入本地 raw，再补剩余缺口，才能重跑 Stage825/849 图谱并继续判断日内规则。",
        "",
        "## 输出",
        "",
        f"- request_preflight：`{REQUEST_PREFLIGHT_PATH}`",
        f"- local_import_manifest：`{LOCAL_IMPORT_MANIFEST_PATH}`",
        f"- download_batch_manifest：`{DOWNLOAD_BATCH_MANIFEST_PATH}`",
        f"- symbol_preflight：`{SYMBOL_PREFLIGHT_PATH}`",
        f"- raw_root_summary：`{ROOT_SUMMARY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    detail = _load_csv(STAGE853_DETAIL_PATH).copy()
    if detail.empty:
        raise RuntimeError("Stage853 gap detail is empty")
    detail["required_date"] = detail["required_date"].map(_normal_date_text)
    for column in ["priority_abs_pnl", "realized_pnl", "big_winner", "same_product_date_bars"]:
        if column in detail.columns:
            detail[column] = pd.to_numeric(detail[column], errors="coerce").fillna(0.0)

    stage853_fetch_plan = _load_csv(STAGE853_FETCH_PLAN_PATH)
    stage853_decision = _load_json(STAGE853_DECISION_PATH)

    symbol_index, raw_rows = _build_raw_index(detail)
    preflight = _request_preflight(detail, symbol_index)
    local_manifest = _local_import_manifest(preflight)
    download_manifest = _download_batch_manifest(preflight)
    symbol_preflight = _symbol_preflight(preflight)
    raw_root_summary = _raw_root_summary(raw_rows)
    summary = _summary(preflight, local_manifest, download_manifest, symbol_preflight, raw_root_summary)

    preflight.to_csv(REQUEST_PREFLIGHT_PATH, index=False, encoding="utf-8-sig")
    local_manifest.to_csv(LOCAL_IMPORT_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    download_manifest.to_csv(DOWNLOAD_BATCH_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    symbol_preflight.to_csv(SYMBOL_PREFLIGHT_PATH, index=False, encoding="utf-8-sig")
    raw_root_summary.to_csv(ROOT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "line_id": LINE_ID,
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage854_local_raw_partial_recovery_then_download_manifest_no_rule",
        "new_rule_allowed": 0,
        "engine_allowed": 0,
        "download_allowed_next_stage": 1,
        "local_import_allowed_next_stage": 1,
        "metrics": summary.iloc[0].to_dict(),
        "stage853_decision": stage853_decision.get("decision", ""),
        "stage853_fetch_symbols": int(stage853_fetch_plan["vt_symbol"].nunique()) if not stage853_fetch_plan.empty else 0,
        "next_step": (
            "First merge local raw minute files listed by local_import_manifest into a Stage819-line minute source; "
            "then use download_batch_manifest only for remaining exact contract/date gaps; rerun Stage825/849 atlases after data fill."
        ),
        "inputs": {
            "stage853_gap_detail": str(STAGE853_DETAIL_PATH),
            "stage853_fetch_plan": str(STAGE853_FETCH_PLAN_PATH),
            "stage853_decision": str(STAGE853_DECISION_PATH),
            "raw_root": str(RAW_ROOT),
        },
        "outputs": {
            "request_preflight": str(REQUEST_PREFLIGHT_PATH),
            "local_import_manifest": str(LOCAL_IMPORT_MANIFEST_PATH),
            "download_batch_manifest": str(DOWNLOAD_BATCH_MANIFEST_PATH),
            "symbol_preflight": str(SYMBOL_PREFLIGHT_PATH),
            "raw_root_summary": str(ROOT_SUMMARY_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, symbol_preflight, local_manifest, download_manifest, raw_root_summary, decision)

    print(f"[{STAGE}] decision: {decision['decision']}")
    print(summary.to_string(index=False))
    print(f"[{STAGE}] report: {REPORT_PATH}")
    print(f"[{STAGE}] decision json: {DECISION_PATH}")


if __name__ == "__main__":
    main()
