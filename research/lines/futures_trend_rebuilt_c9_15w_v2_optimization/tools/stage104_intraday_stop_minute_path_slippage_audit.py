from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage104"
MODEL_TAG = "stage104_intraday_stop_minute_path_slippage_audit_v2_reviewed_unique_gate"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage104_intraday_stop_minute_path_slippage_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage104_intraday_stop_minute_path_slippage_audit"
STAGES_DIR = LINE_DIR / "stages"
MINUTE_ROOT = ROOT / "examples" / "portfolio_backtesting" / "downloaded_futures"

STAGE094_OUT = LINE_DIR / "outputs" / "stage094_stage167_closed_lot_entry_state_audit"
STAGE094_PREFIX = "rebuilt_c9_v2_stage094_stage167_closed_lot_entry_state_audit"
STAGE094_TAG = "stage094_stage167_closed_lot_entry_state_audit_v1"
CLOSED_LOTS_PATH = STAGE094_OUT / f"{STAGE094_PREFIX}_closed_lots_{STAGE094_TAG}.csv.gz"

EVENT_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_event_panel_{MODEL_TAG}.csv.gz"
BY_EXIT_REASON_PATH = OUT / f"{OUTPUT_PREFIX}_by_exit_reason_{MODEL_TAG}.csv"
BY_START_PATH = OUT / f"{OUTPUT_PREFIX}_by_start_{MODEL_TAG}.csv"
BY_SYMBOL_PATH = OUT / f"{OUTPUT_PREFIX}_by_symbol_{MODEL_TAG}.csv"
MINUTE_SOURCE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_minute_source_audit_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

STOP_REASON_MULTIPLIER = {
    "stage847_intraday_05r_stop_no_reentry": 0.5,
    "stage847_intraday_retry_failed_05r_stop": 0.5,
    "stage827_intraday_c2_1r_stop": 1.0,
}

MINUTE_DIR_PRIORITY = [
    "tqsdk_stage504_next_real_open_fallback_backfill",
    "tqsdk_stage506_next_real_forward_risk_signal_frontier",
    "tqsdk_stage491_covered_key_full_session_backfill",
    "tqsdk_stage498_actual_trade_fill_key_backfill",
    "tqsdk_stage459_completed_preclose_full_bar_shard",
    "tqsdk_stage462_completed_preclose_full_dates_shard",
    "tqsdk_stage448_minute_session_rebuild_batch",
    "tqsdk_stage859_stage856_remaining_gap_backfill",
    "tqsdk_stage052_jd_minute_gap_backfill",
]

EXTERNAL_RESEARCH = [
    {
        "source": "Backtrader order execution documentation",
        "url": "https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/",
        "finding": "Stop orders should distinguish open penetration from intrabar high/low touch when reconstructing fills.",
    },
    {
        "source": "Backtrader slippage documentation",
        "url": "https://www.backtrader.com/docu/slippage/slippage/",
        "finding": "Once a Stop order is triggered, market-order style slippage semantics apply; the stop trigger is not automatically the execution price.",
    },
    {
        "source": "CFTC Stop Orders in Select Futures Markets",
        "url": "https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf",
        "finding": "Stop-market slippage can be material in futures markets, so stop-trigger evidence and execution-price evidence should be audited separately.",
    },
    {
        "source": "QuantStart transaction costs and slippage",
        "url": "https://www.quantstart.com/articles/Successful-Backtesting-of-Algorithmic-Trading-Strategies-Part-II/",
        "finding": "Backtest performance can be materially distorted when transaction costs, order type and slippage are not modeled explicitly.",
    },
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, (str, bytes)):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce")
    return pd.Series(default, index=frame.index, dtype=float)


def _safe_div(numerator: float, denominator: float) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return np.nan
    return float(numerator / denominator)


def _direction_sign(value: Any) -> int:
    text = str(value).strip().lower()
    if text in {"long", "buy"}:
        return 1
    if text in {"short", "sell"}:
        return -1
    return 0


def _dir_priority(path: Path) -> tuple[int, str]:
    dataset = path.relative_to(MINUTE_ROOT).parts[0] if MINUTE_ROOT in path.parents else ""
    try:
        rank = MINUTE_DIR_PRIORITY.index(dataset)
    except ValueError:
        rank = len(MINUTE_DIR_PRIORITY) + 1
    return rank, str(path)


def _contract_from_minute_path(path: Path) -> str:
    stem = path.name
    contract = stem.replace("_completed_minute_backtest.csv", "").replace("_minute_backtest.csv", "")
    exchange = path.parent.name
    return f"{contract}.{exchange}"


def build_minute_file_index() -> dict[str, list[Path]]:
    candidates: dict[str, list[Path]] = {}
    for path in MINUTE_ROOT.glob("*/*/*minute_backtest.csv"):
        vt_symbol = _contract_from_minute_path(path)
        candidates.setdefault(vt_symbol, []).append(path)
    return {key: sorted(paths, key=_dir_priority) for key, paths in candidates.items()}


class MinuteCache:
    def __init__(self) -> None:
        self._cache: dict[Path, pd.DataFrame] = {}

    def load(self, path: Path) -> pd.DataFrame:
        if path in self._cache:
            return self._cache[path]
        usecols = ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]
        frame = pd.read_csv(path, usecols=lambda col: col in usecols, encoding="utf-8-sig")
        frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce")
        frame = frame.dropna(subset=["bar_datetime"]).copy()
        frame["bar_date"] = frame["bar_datetime"].dt.normalize()
        for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.sort_values("bar_datetime").reset_index(drop=True)
        self._cache[path] = frame
        return frame


def load_stop_lots() -> pd.DataFrame:
    lots = pd.read_csv(CLOSED_LOTS_PATH, encoding="utf-8-sig")
    data = lots[lots["exit_reason"].astype(str).isin(STOP_REASON_MULTIPLIER)].copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    for column in [
        "entry_price",
        "exit_price",
        "stop_distance",
        "volume",
        "size",
        "realized_pnl",
        "portfolio_drawdown_pct",
    ]:
        data[column] = _numeric(data, column)
    data["direction_sign"] = data["direction"].map(_direction_sign).astype(int)
    bad = data[
        data["entry_date"].isna()
        | data["exit_date"].isna()
        | data["entry_price"].isna()
        | data["exit_price"].isna()
        | data["stop_distance"].isna()
        | data["volume"].isna()
        | data["size"].isna()
        | data["direction_sign"].eq(0)
    ]
    if not bad.empty:
        raise ValueError(f"Intraday stop lots with invalid key fields: {len(bad)}")
    data["stop_r_multiple"] = data["exit_reason"].map(STOP_REASON_MULTIPLIER).astype(float)
    data["planned_stop_price"] = data["entry_price"] - data["direction_sign"] * data["stop_r_multiple"] * data["stop_distance"]
    data["favorable_fill_points_vs_planned_stop"] = data["direction_sign"] * (
        data["exit_price"] - data["planned_stop_price"]
    )
    data["adverse_slippage_points_vs_planned_stop"] = (-data["favorable_fill_points_vs_planned_stop"]).clip(lower=0.0)
    data["adverse_slippage_cash_vs_planned_stop"] = (
        data["adverse_slippage_points_vs_planned_stop"] * data["volume"] * data["size"]
    )
    data["planned_stop_price_diff_abs"] = (data["exit_price"] - data["planned_stop_price"]).abs()
    key_cols = ["vt_symbol", "entry_date", "exit_date", "direction", "entry_price", "exit_price", "exit_reason"]
    data["physical_event_key"] = data[key_cols].astype(str).agg("|".join, axis=1)
    return data.reset_index(drop=True)


def _day_for_event(paths: list[Path], cache: MinuteCache, day: pd.Timestamp) -> tuple[pd.DataFrame, str, Path | None]:
    fallback_path = paths[0] if paths else None
    for path in paths:
        bars = cache.load(path)
        day_bars = bars[bars["bar_date"].eq(day)].copy()
        if not day_bars.empty:
            return day_bars, "calendar_exit_date", path
    return pd.DataFrame(), "missing_calendar_exit_date", fallback_path


def _minute_path_record(row: pd.Series, minute_index: dict[str, list[Path]], cache: MinuteCache) -> dict[str, Any]:
    vt_symbol = str(row["vt_symbol"])
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    sign = int(row["direction_sign"])
    stop = float(row["planned_stop_price"])
    size = float(row["size"])
    volume = float(row["volume"])
    paths = minute_index.get(vt_symbol, [])
    day, minute_date_mode, source_path = _day_for_event(paths, cache, exit_date)
    record: dict[str, Any] = {
        "minute_file_found": bool(paths),
        "minute_candidate_file_count": int(len(paths)),
        "minute_source_file": str(source_path) if source_path is not None else "",
        "minute_source_dataset": source_path.relative_to(MINUTE_ROOT).parts[0] if source_path and MINUTE_ROOT in source_path.parents else "",
        "minute_date_mode": minute_date_mode,
        "minute_bar_count_on_exit_date": int(len(day)),
        "minute_first_bar_datetime": "",
        "minute_last_bar_datetime": "",
        "minute_first_open": np.nan,
        "minute_day_high": np.nan,
        "minute_day_low": np.nan,
        "minute_day_worst_beyond_stop_points": np.nan,
        "minute_day_worst_beyond_stop_cash": np.nan,
        "minute_any_hit_planned_stop": False,
        "minute_first_hit_datetime": "",
        "minute_first_hit_open": np.nan,
        "minute_first_hit_high": np.nan,
        "minute_first_hit_low": np.nan,
        "minute_first_hit_close": np.nan,
        "minute_first_hit_open_beyond_stop": False,
        "minute_first_hit_open_adverse_points": np.nan,
        "minute_first_hit_bar_worst_beyond_stop_points": np.nan,
    }
    if day.empty:
        return record

    day = day.sort_values("bar_datetime").reset_index(drop=True)
    record["minute_first_bar_datetime"] = pd.Timestamp(day["bar_datetime"].iloc[0]).isoformat()
    record["minute_last_bar_datetime"] = pd.Timestamp(day["bar_datetime"].iloc[-1]).isoformat()
    record["minute_first_open"] = float(day["open"].iloc[0])
    day_high = float(day["high"].max())
    day_low = float(day["low"].min())
    record["minute_day_high"] = day_high
    record["minute_day_low"] = day_low
    if sign > 0:
        hit_mask = day["low"].le(stop)
        day_worst = max(0.0, stop - day_low)
    else:
        hit_mask = day["high"].ge(stop)
        day_worst = max(0.0, day_high - stop)
    record["minute_day_worst_beyond_stop_points"] = float(day_worst)
    record["minute_day_worst_beyond_stop_cash"] = float(day_worst * volume * size)
    record["minute_any_hit_planned_stop"] = bool(hit_mask.any())
    if not bool(hit_mask.any()):
        return record

    hit = day.loc[hit_mask].iloc[0]
    hit_open = float(hit["open"])
    hit_high = float(hit["high"])
    hit_low = float(hit["low"])
    if sign > 0:
        open_beyond = hit_open <= stop
        first_hit_open_adverse = max(0.0, stop - hit_open)
        hit_worst = max(0.0, stop - hit_low)
    else:
        open_beyond = hit_open >= stop
        first_hit_open_adverse = max(0.0, hit_open - stop)
        hit_worst = max(0.0, hit_high - stop)
    record.update(
        {
            "minute_first_hit_datetime": pd.Timestamp(hit["bar_datetime"]).isoformat(),
            "minute_first_hit_open": hit_open,
            "minute_first_hit_high": hit_high,
            "minute_first_hit_low": hit_low,
            "minute_first_hit_close": float(hit["close"]),
            "minute_first_hit_open_beyond_stop": bool(open_beyond),
            "minute_first_hit_open_adverse_points": float(first_hit_open_adverse),
            "minute_first_hit_bar_worst_beyond_stop_points": float(hit_worst),
        }
    )
    return record


def build_event_panel(lots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    minute_index = build_minute_file_index()
    cache = MinuteCache()
    records: list[dict[str, Any]] = []
    for idx, row in lots.iterrows():
        if idx % 25 == 0:
            print(f"[stage104] minute audit {idx + 1}/{len(lots)}", flush=True)
        records.append(_minute_path_record(row, minute_index, cache))
    panel = pd.concat([lots.reset_index(drop=True), pd.DataFrame(records)], axis=1)
    panel["minute_hit_coverage_ready"] = panel["minute_bar_count_on_exit_date"].gt(0)
    panel["hit_expected_but_missing"] = panel["minute_hit_coverage_ready"] & ~panel["minute_any_hit_planned_stop"].astype(bool)
    panel["actual_exit_worse_than_day_worst"] = panel["adverse_slippage_points_vs_planned_stop"].gt(
        panel["minute_day_worst_beyond_stop_points"].fillna(0.0) + 1e-9
    )
    panel["actual_exit_exactly_planned_stop"] = panel["planned_stop_price_diff_abs"].le(1e-9)
    used = panel[panel["minute_source_file"].astype(str).ne("")].copy()
    source_rows: list[dict[str, Any]] = []
    for path_text, group in used.groupby("minute_source_file", dropna=False):
        path = Path(path_text)
        stat = path.stat() if path.exists() else None
        source_rows.append(
            {
                "minute_source_file": path_text,
                "exists": bool(path.exists()),
                "bytes": int(stat.st_size) if stat else 0,
                "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds") if stat else "",
                "row_events_using_file": int(len(group)),
                "unique_physical_events_using_file": int(group["physical_event_key"].nunique()),
                "dataset": group["minute_source_dataset"].astype(str).iloc[0] if len(group) else "",
            }
        )
    source_audit = pd.DataFrame(source_rows).sort_values(["dataset", "minute_source_file"]) if source_rows else pd.DataFrame()
    return panel, source_audit


def summarize(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(group_cols, dropna=False, sort=True):
        key_tuple = key if isinstance(key, tuple) else (key,)
        row = {col: key_tuple[idx] for idx, col in enumerate(group_cols)}
        by_start = group.groupby("requested_start_month")["realized_pnl"].sum()
        by_physical = group.drop_duplicates("physical_event_key")
        row.update(
            {
                "rows": int(len(group)),
                "unique_physical_events": int(group["physical_event_key"].nunique()),
                "start_count": int(group["requested_start_month"].nunique()),
                "symbol_count": int(group["vt_symbol"].nunique()),
                "realized_pnl_sum": float(group["realized_pnl"].sum()),
                "realized_pnl_mean": float(group["realized_pnl"].mean()) if len(group) else np.nan,
                "coverage_rate": float(group["minute_hit_coverage_ready"].mean()) if len(group) else np.nan,
                "planned_stop_hit_rate": float(group["minute_any_hit_planned_stop"].mean()) if len(group) else np.nan,
                "missing_expected_hit_rows": int(group["hit_expected_but_missing"].sum()),
                "actual_exact_stop_rate": float(group["actual_exit_exactly_planned_stop"].mean()) if len(group) else np.nan,
                "adverse_slippage_cash_sum": float(group["adverse_slippage_cash_vs_planned_stop"].sum()),
                "adverse_slippage_cash_mean": float(group["adverse_slippage_cash_vs_planned_stop"].mean()) if len(group) else np.nan,
                "adverse_slippage_cash_max": float(group["adverse_slippage_cash_vs_planned_stop"].max()) if len(group) else np.nan,
                "minute_day_worst_beyond_cash_sum": float(
                    group["minute_day_worst_beyond_stop_cash"].fillna(0.0).sum()
                ),
                "first_hit_open_beyond_rate": float(group["minute_first_hit_open_beyond_stop"].mean())
                if len(group)
                else np.nan,
                "first_hit_open_adverse_cash_sum": float(
                    (group["minute_first_hit_open_adverse_points"].fillna(0.0) * group["volume"] * group["size"]).sum()
                ),
                "actual_exit_worse_than_day_worst_rows": int(group["actual_exit_worse_than_day_worst"].sum()),
                "positive_start_count": int(by_start.gt(0).sum()) if len(by_start) else 0,
                "negative_start_count": int(by_start.lt(0).sum()) if len(by_start) else 0,
                "unique_event_adverse_slippage_cash_sum": float(
                    by_physical["adverse_slippage_cash_vs_planned_stop"].sum()
                ),
                "unique_event_worst_beyond_cash_sum": float(
                    by_physical["minute_day_worst_beyond_stop_cash"].fillna(0.0).sum()
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def make_decision(panel: pd.DataFrame) -> dict[str, Any]:
    coverage_rate = float(panel["minute_hit_coverage_ready"].mean()) if len(panel) else np.nan
    hit_rate = float(panel["minute_any_hit_planned_stop"].mean()) if len(panel) else np.nan
    exact_rate = float(panel["actual_exit_exactly_planned_stop"].mean()) if len(panel) else np.nan
    adverse_cash = float(panel["adverse_slippage_cash_vs_planned_stop"].sum())
    unique_panel = panel.drop_duplicates("physical_event_key")
    unique_adverse_cash = float(unique_panel["adverse_slippage_cash_vs_planned_stop"].sum())
    open_beyond_cash = float(
        (panel["minute_first_hit_open_adverse_points"].fillna(0.0) * panel["volume"] * panel["size"]).sum()
    )
    unique_open_beyond_cash = float(
        (
            unique_panel["minute_first_hit_open_adverse_points"].fillna(0.0)
            * unique_panel["volume"]
            * unique_panel["size"]
        ).sum()
    )
    worse_than_day_worst = int(panel["actual_exit_worse_than_day_worst"].sum())
    missing_expected_hit = int(panel["hit_expected_but_missing"].sum())
    adverse_rows = panel[panel["adverse_slippage_cash_vs_planned_stop"].gt(0)].copy()
    adverse_unique = unique_panel[unique_panel["adverse_slippage_cash_vs_planned_stop"].gt(0)].copy()
    open_beyond_rows = panel[panel["minute_first_hit_open_adverse_points"].fillna(0.0).gt(0)].copy()
    open_beyond_unique = unique_panel[unique_panel["minute_first_hit_open_adverse_points"].fillna(0.0).gt(0)].copy()
    row_broad_slippage = bool(
        adverse_cash >= 200_000
        and adverse_rows["requested_start_month"].nunique() >= 4
        and adverse_rows["vt_symbol"].nunique() >= 10
    )
    unique_broad_slippage = bool(
        unique_adverse_cash >= 200_000
        and len(adverse_unique) >= 10
        and adverse_unique["vt_symbol"].nunique() >= 10
    )
    broad_slippage = bool(
        row_broad_slippage and unique_broad_slippage
    )
    open_penetration_warning = bool(
        open_beyond_cash >= 200_000
        and unique_open_beyond_cash >= 100_000
        and len(open_beyond_unique) >= 3
    )
    if coverage_rate < 0.8 or hit_rate < 0.8:
        decision = "stage104_intraday_stop_minute_path_coverage_or_semantics_insufficient"
        next_step = (
            "先排查 exit_date 与夜盘交易日映射、Stage827/847 planned stop 语义，"
            "不能据此设计止损优化。"
        )
        continue_after = "有但必须先补语义"
        continue_reason = "分钟文件或交易日映射不能稳定复原止损触发路径。"
        overfit_after = "否。当前是覆盖/语义闸门失败，不允许扫阈值或按局部事件修参数。"
        candidate_rule_count = 0
        best_candidate = ""
    elif broad_slippage:
        decision = "stage104_intraday_stop_actual_exit_adverse_slippage_candidate_for_execution_model_audit"
        next_step = (
            "只允许进入执行模型审计：用固定 stop-market slippage/开盘穿越保护做一次 proxy，"
            "不得扫品种、方向、年份或止损倍数。"
        )
        continue_after = "有"
        continue_reason = "实际退出价相对 planned stop 存在宽样本不利偏移，可能影响水下体验。"
        overfit_after = "否但需谨慎。证据来自执行价偏移，不来自收益目标反推。"
        candidate_rule_count = 1
        best_candidate = "intraday_stop_adverse_slippage_execution_audit"
    else:
        decision = "stage104_intraday_stop_actual_exit_no_material_adverse_slippage_candidate"
        next_step = (
            "不把 actual exit 相对 planned stop 的成交偏移作为主优化方向；"
            "若继续执行层，只能围绕开盘穿越做固定代理风险审计，否则转向非日内止损的账户层暴露、趋势衰退或组合相关性。"
        )
        continue_after = "有但需换问题"
        continue_reason = "actual exit 相对 planned stop 未形成 material adverse slippage；开盘穿越只保留为执行代理 warning，不能直接倒推止损参数。"
        overfit_after = "否。固定 Stage827/847 止损族和预声明阈值，没有按结果筛选窗口。"
        candidate_rule_count = 0
        best_candidate = ""
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "candidate_rule_count": candidate_rule_count,
        "best_candidate": best_candidate,
        "rows": int(len(panel)),
        "unique_physical_events": int(panel["physical_event_key"].nunique()) if len(panel) else 0,
        "exit_reasons": sorted(panel["exit_reason"].astype(str).unique().tolist()),
        "minute_coverage_rate": coverage_rate,
        "planned_stop_hit_rate": hit_rate,
        "actual_exact_stop_rate": exact_rate,
        "missing_expected_hit_rows": missing_expected_hit,
        "adverse_slippage_cash_sum": adverse_cash,
        "unique_physical_event_adverse_slippage_cash_sum": unique_adverse_cash,
        "row_broad_adverse_slippage": row_broad_slippage,
        "unique_broad_adverse_slippage": unique_broad_slippage,
        "adverse_slippage_positive_row_start_count": int(adverse_rows["requested_start_month"].nunique())
        if len(adverse_rows)
        else 0,
        "adverse_slippage_positive_row_symbol_count": int(adverse_rows["vt_symbol"].nunique())
        if len(adverse_rows)
        else 0,
        "adverse_slippage_positive_unique_event_count": int(len(adverse_unique)),
        "adverse_slippage_positive_unique_symbol_count": int(adverse_unique["vt_symbol"].nunique())
        if len(adverse_unique)
        else 0,
        "first_hit_open_adverse_cash_sum": open_beyond_cash,
        "unique_physical_event_first_hit_open_adverse_cash_sum": unique_open_beyond_cash,
        "open_penetration_warning": open_penetration_warning,
        "open_penetration_positive_row_start_count": int(open_beyond_rows["requested_start_month"].nunique())
        if len(open_beyond_rows)
        else 0,
        "open_penetration_positive_unique_event_count": int(len(open_beyond_unique)),
        "actual_exit_worse_than_day_worst_rows": worse_than_day_worst,
        "promote_to_proxy": False,
        "promote_to_true_engine": False,
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "next_step": next_step,
        "overfit_after": overfit_after,
        "continue_after": continue_after,
        "continue_reason": continue_reason,
    }


def write_report(
    panel: pd.DataFrame,
    by_exit_reason: pd.DataFrame,
    by_start: pd.DataFrame,
    by_symbol: pd.DataFrame,
    source_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    top_adverse = panel.sort_values("adverse_slippage_cash_vs_planned_stop", ascending=False).head(40)
    missing_hit = panel[panel["hit_expected_but_missing"]].head(80)
    report = f"""# {STAGE} Intraday Stop Minute Path Slippage Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：这一步只审计执行层事实，不设计新止损规则。止损触发价、开盘穿越、分钟内最差穿越、实际退出价必须分开统计；v2 已按独立复核意见把行级重复样本和去重物理事件同时纳入 decision，避免把多起点重复误判为广泛证据。

## Decision

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## By Exit Reason

{_md_table(by_exit_reason)}

## By Start

{_md_table(by_start, 120)}

## By Symbol

{_md_table(by_symbol.sort_values("adverse_slippage_cash_sum", ascending=False), 120)}

## Top Actual Adverse Slippage vs Planned Stop

{_md_table(top_adverse[[
        "requested_start_month",
        "vt_symbol",
        "entry_date",
        "exit_date",
        "direction",
        "exit_reason",
        "entry_price",
        "exit_price",
        "stop_distance",
        "planned_stop_price",
        "adverse_slippage_cash_vs_planned_stop",
        "minute_any_hit_planned_stop",
        "minute_first_hit_datetime",
        "minute_first_hit_open_beyond_stop",
        "minute_day_worst_beyond_stop_cash",
    ]], 40)}

## Missing Expected Stop Hits

{_md_table(missing_hit[[
        "requested_start_month",
        "vt_symbol",
        "entry_date",
        "exit_date",
        "direction",
        "exit_reason",
        "entry_price",
        "exit_price",
        "planned_stop_price",
        "minute_bar_count_on_exit_date",
        "minute_source_file",
    ]], 80)}

## Minute Source Audit

{_md_table(source_audit, 160)}

## 统计口径

- 样本：Stage094 closed lots 中 `stage847_intraday_05r_stop_no_reentry`、`stage847_intraday_retry_failed_05r_stop`、`stage827_intraday_c2_1r_stop` 三类日内止损退出。
- planned stop：Stage847 固定 `entry_price ± 0.5 * stop_distance`；Stage827 C2 固定 `entry_price ± 1.0 * stop_distance`。这是复核用 planned proxy，不修改真实策略。
- 实际不利滑点：按方向计算 `exit_price` 相对 planned stop 的不利点数，再乘 `volume * size`。
- 分钟触发：同合约分钟线中 `exit_date` 自然日；多分钟源按预声明优先级选择第一份能覆盖该自然日的文件。
- 夜盘限制：本阶段先用自然日，不把夜盘映射成交易日；若 coverage/hit 失败，优先排查交易日映射而不是调策略。
- 去重：报告同时给出多起点样本行数和 `physical_event_key` 去重后的事件数，避免把同一物理止损重复样本误当作独立执行证据。
- 去重金额：`physical_event_key` 去重金额采用该物理事件的第一条代表行；由于多起点重复会带来不同 volume，它用于保守 breadth/重复样本闸门，不用于替代真实多起点组合 PnL。
- 候选闸门：coverage 与 hit rate 均需 `>=80%`；actual exit 相对 planned stop 的不利偏移必须同时通过行级和去重物理事件 material/breadth 闸门，才进入执行模型 proxy 审计。
- 开盘穿越 warning：首根命中 bar 开盘穿越只作为 stop-market 执行代理风险，不等同于当前回测 `exit_price` 的不利滑点。

## 过拟合反思

- 运行前：否。本阶段固定退出原因族、止损倍数和覆盖阈值，只检验止损执行事实。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。它能回答亏损是否来自止损价被远远穿透。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- event_panel：`{EVENT_PANEL_PATH}`
- by_exit_reason：`{BY_EXIT_REASON_PATH}`
- by_start：`{BY_START_PATH}`
- by_symbol：`{BY_SYMBOL_PATH}`
- minute_source_audit：`{MINUTE_SOURCE_AUDIT_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    by_exit_reason: pd.DataFrame,
    by_start: pd.DataFrame,
    by_symbol: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage104_intraday_stop_minute_path_slippage_audit.md"
    text = f"""# Stage104 日内止损分钟路径/滑点法证

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区：`{ROOT}`
- 阶段性质：只读执行法证；不改策略、不跑 true engine
- 是否重要突破：否
- 是否触发A/B：否，本阶段没有可合入策略候选

## 外部调研与判断

- 参考资料：Backtrader order execution、Backtrader slippage、CFTC futures stop orders、QuantStart transaction cost/slippage。
- 我的判断：止损触发与成交价格必须分开复核；如果 actual exit 相对 planned stop 没有系统性偏离，继续围绕日内止损调参会过拟合；开盘穿越风险只可作为单独执行代理审计。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage104_intraday_stop_minute_path_slippage_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：只读审计参数 `Stage847=0.5R`、`Stage827=1.0R`、coverage/hit 闸门 `80%`、行级 material adverse slippage `200,000`、去重物理事件 material adverse slippage `200,000`、开盘穿越 warning 去重金额 `100,000`。
- 修改参数：无正式策略参数。
- 删除参数：无。

## 回测/审计参数

- 样本来源：`{CLOSED_LOTS_PATH}`
- 分钟源目录：`{MINUTE_ROOT}`
- 止损退出族：`{", ".join(STOP_REASON_MULTIPLIER)}`
- true engine：未运行。
- 订单 API：`0`
- CTP：未连接。

## 结果摘要

- 决策：`{decision['decision']}`
- 样本行数：`{decision['rows']}`
- 去重物理事件数：`{decision['unique_physical_events']}`
- 去重金额口径：`physical_event_key` 第一条代表行，仅用于 breadth/重复样本闸门。
- 分钟覆盖率：`{decision['minute_coverage_rate']:.4f}`
- planned stop 命中率：`{decision['planned_stop_hit_rate']:.4f}`
- 实际退出价等于 planned stop 比率：`{decision['actual_exact_stop_rate']:.4f}`
- 实际不利滑点金额：`{decision['adverse_slippage_cash_sum']:,.2f}`
- 去重物理事件实际不利滑点金额：`{decision['unique_physical_event_adverse_slippage_cash_sum']:,.2f}`
- 行级 broad adverse slippage 闸门：`{decision['row_broad_adverse_slippage']}`
- 去重 broad adverse slippage 闸门：`{decision['unique_broad_adverse_slippage']}`
- 首根命中 bar 开盘穿越金额：`{decision['first_hit_open_adverse_cash_sum']:,.2f}`
- 去重物理事件首根命中 bar 开盘穿越金额：`{decision['unique_physical_event_first_hit_open_adverse_cash_sum']:,.2f}`
- 开盘穿越 execution warning：`{decision['open_penetration_warning']}`
- 分钟最差穿越仍解释不了实际退出价的行数：`{decision['actual_exit_worse_than_day_worst_rows']}`
- 候选规则数：`{decision['candidate_rule_count']}`
- 最佳候选：`{decision['best_candidate'] or '无'}`

## By Exit Reason

{_md_table(by_exit_reason)}

## By Start

{_md_table(by_start, 120)}

## By Symbol

{_md_table(by_symbol.sort_values("adverse_slippage_cash_sum", ascending=False), 120)}

## 标准回测指标

- 期末权益：不适用，本阶段只读法证未重跑策略。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用；本阶段统计 planned stop 相对实际退出价的执行偏移。
- 总交易次数：不适用。
- 胜率：不适用。

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 后续规划和 TODO

- {decision['next_step']}

## 过拟合反思

- 运行前：否，固定样本和止损语义，只审计执行事实。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有，直接回应止损是否被远超止损价成交。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- 报告：`{REPORT_PATH}`
- 事件明细：`{EVENT_PANEL_PATH}`
- 退出原因汇总：`{BY_EXIT_REASON_PATH}`
- 起点汇总：`{BY_START_PATH}`
- 品种汇总：`{BY_SYMBOL_PATH}`
- 分钟源审计：`{MINUTE_SOURCE_AUDIT_PATH}`
- 输入审计：`{INPUT_AUDIT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    input_audit = _input_audit([CLOSED_LOTS_PATH])
    if not bool(input_audit["exists"].all()):
        raise FileNotFoundError(CLOSED_LOTS_PATH)
    lots = load_stop_lots()
    panel, source_audit = build_event_panel(lots)
    by_exit_reason = summarize(panel, ["exit_reason"]).sort_values("realized_pnl_sum")
    by_start = summarize(panel, ["requested_start_month"]).sort_values("requested_start_month")
    by_symbol = summarize(panel, ["vt_symbol"]).sort_values("realized_pnl_sum")
    decision = make_decision(panel)

    panel.to_csv(EVENT_PANEL_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    by_exit_reason.to_csv(BY_EXIT_REASON_PATH, index=False, encoding="utf-8-sig")
    by_start.to_csv(BY_START_PATH, index=False, encoding="utf-8-sig")
    by_symbol.to_csv(BY_SYMBOL_PATH, index=False, encoding="utf-8-sig")
    source_audit.to_csv(MINUTE_SOURCE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(panel, by_exit_reason, by_start, by_symbol, source_audit, decision)
    stage_path = write_stage_record(by_exit_reason, by_start, by_symbol, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"[stage104] report={REPORT_PATH}")
    print(f"[stage104] stage_record={stage_path}")


if __name__ == "__main__":
    main()
