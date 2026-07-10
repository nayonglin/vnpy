from __future__ import annotations

from datetime import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE_ID = "stage129_stage125_top10_overlay_replay"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"rebuilt_c9_v2_{STAGE_ID}"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
UNIVERSE_DIR = OUT / "single_product_universes"
DAILY_DIR = OUT / "daily_by_product"
FRAMES_DIR = OUT / "frames_by_product"
STAGES_DIR = LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_1630_stage129_stage125_top10_overlay_replay.md"

STAGE124_SCRIPT = LINE_DIR / "tools" / "stage124_full_market_single_product_c9_replay.py"
RAW_MINUTE_ROOT = (
    ROOT
    / "examples"
    / "portfolio_backtesting"
    / "downloaded_futures"
    / "tqsdk_stage127_stage125_top10_loss_window_minute_backfill"
)
BASELINE_STAGE125_SUMMARY_PATH = (
    LINE_DIR
    / "outputs"
    / "stage125_loss_window_top10_product_curves"
    / "stage125_loss_window_top10_product_summary.csv"
)

TOP10_PRODUCTS = ["m.DCE", "ni.SHFE", "CY.CZCE", "eb.DCE", "y.DCE", "zn.SHFE", "ag.SHFE", "v.DCE", "PK.CZCE", "rr.DCE"]
LOSS_WINDOW_START = pd.Timestamp("2022-03-09")
LOSS_WINDOW_END = pd.Timestamp("2022-06-29")
CAPITAL = 150_000.0

OVERLAY_MINUTE_PATH = OUT / f"{OUTPUT_PREFIX}_overlay_full_minute_bars_{MODEL_TAG}.csv"
OVERLAY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_overlay_minute_audit_{MODEL_TAG}.csv"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
PERIOD_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_product_period_summary_{MODEL_TAG}.csv"
ANNUAL_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_annual_summary_{MODEL_TAG}.csv"
RUN_STATUS_PATH = OUT / f"{OUTPUT_PREFIX}_run_status_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUT / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv.gz"
TOP10_CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_loss_window_top10_curves_{MODEL_TAG}.csv"
TOP10_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_loss_window_top10_summary_{MODEL_TAG}.csv"
BASELINE_COMPARE_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_stage125_compare_{MODEL_TAG}.csv"
RESET_EQUITY_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_loss_window_reset_equity_curves_{MODEL_TAG}.png"
PNL_DIFF_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_baseline_stage125_pnl_diff_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

SOURCE_LINKS = {
    "tqsdk_backtest": "https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html",
    "tqsdk_api": "https://doc.shinnytech.com/tqsdk/1.5.0/reference/tqsdk.api.html",
    "tqsdk_github": "https://github.com/shinnytech/tqsdk-python",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return None if not math.isfinite(number) else number
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
    return data.to_markdown(index=False, floatfmt=".4f")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _slug(product: str) -> str:
    return str(product).replace(".", "_").replace("/", "_")


def _product_from_vt(vt_symbol: Any) -> str:
    text = str(vt_symbol or "").strip()
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    match = re.match(r"([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def _load_stage124() -> Any:
    spec = importlib.util.spec_from_file_location("stage124_full_market_single_product_c9_replay", STAGE124_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE124_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _prepare_minute_frame(frame: pd.DataFrame, source_name: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi", "bar_date", "minute_source"]
        )
    data = frame.copy()
    if "vt_symbol" not in data.columns and "contract_vt" in data.columns:
        data["vt_symbol"] = data["contract_vt"]
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data = data.dropna(subset=["vt_symbol", "bar_datetime", "open", "high", "low", "close"]).copy()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        else:
            data[column] = np.nan
    data["bar_date"] = data["bar_datetime"].dt.normalize()
    data["minute_source"] = source_name
    columns = ["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi", "bar_date", "minute_source"]
    return data[columns].reset_index(drop=True)


def _selected_vt_symbols_from_universe(stage124: Any, universe: pd.DataFrame) -> set[str]:
    vt_symbols: set[str] = set()
    for row in universe.itertuples(index=False):
        product = str(row.product_vt_symbol)
        universe_path = UNIVERSE_DIR / f"{_slug(product)}.csv"
        single = universe[universe["product_vt_symbol"].astype(str).eq(product)].copy()
        universe_path.parent.mkdir(parents=True, exist_ok=True)
        single.to_csv(universe_path, index=False, encoding="utf-8-sig")
        metadata = stage124._metadata(universe_path)
        vt_symbols.update(str(item) for item in metadata.get("vt_symbols", []))
    return vt_symbols


def build_overlay_minute_file(stage124: Any, selected_universe: pd.DataFrame) -> pd.DataFrame:
    OUT.mkdir(parents=True, exist_ok=True)
    vt_symbols = _selected_vt_symbols_from_universe(stage124, selected_universe)
    base_path = stage124.s901.s861.FULL_MINUTE_BARS_PATH
    base_frames: list[pd.DataFrame] = []
    if base_path.exists():
        for chunk in pd.read_csv(base_path, encoding="utf-8-sig", chunksize=500_000):
            if "vt_symbol" not in chunk.columns:
                continue
            part = chunk[chunk["vt_symbol"].astype(str).isin(vt_symbols)].copy()
            if not part.empty:
                base_frames.append(_prepare_minute_frame(part, "stage861_base_subset"))
    raw_frames: list[pd.DataFrame] = []
    for path in sorted(RAW_MINUTE_ROOT.glob("*/*_minute_backtest.csv")):
        try:
            raw = pd.read_csv(path, encoding="utf-8-sig")
        except Exception:
            continue
        raw = _prepare_minute_frame(raw, "stage127_stage125_top10_entry_day_backfill")
        raw = raw[raw["vt_symbol"].astype(str).isin(vt_symbols)].copy()
        if not raw.empty:
            raw_frames.append(raw)
    frames = [frame for frame in [*base_frames, *raw_frames] if not frame.empty]
    if frames:
        data = pd.concat(frames, ignore_index=True, sort=False)
        data["source_priority"] = data["minute_source"].astype(str).str.contains("stage127").astype(int)
        data = data.sort_values(["vt_symbol", "bar_datetime", "source_priority"])
        data = data.drop_duplicates(["vt_symbol", "bar_datetime"], keep="last").drop(columns=["source_priority"])
        data = data.sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)
    else:
        data = pd.DataFrame(columns=["vt_symbol", "bar_datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi", "bar_date", "minute_source"])
    data.to_csv(OVERLAY_MINUTE_PATH, index=False, encoding="utf-8-sig")
    raw_concat = pd.concat(raw_frames, ignore_index=True, sort=False) if raw_frames else pd.DataFrame()
    audit = pd.DataFrame(
        [
            {"metric": "selected_product_count", "value": len(TOP10_PRODUCTS)},
            {"metric": "selected_vt_symbol_count", "value": len(vt_symbols)},
            {"metric": "base_path", "value": str(base_path)},
            {"metric": "base_path_exists", "value": bool(base_path.exists())},
            {"metric": "base_subset_rows", "value": int(sum(len(frame) for frame in base_frames))},
            {"metric": "raw_backfill_rows", "value": int(len(raw_concat))},
            {"metric": "overlay_rows", "value": int(len(data))},
            {"metric": "overlay_symbol_count", "value": int(data["vt_symbol"].nunique()) if not data.empty else 0},
            {"metric": "overlay_duplicate_key_count", "value": int(data.duplicated(["vt_symbol", "bar_datetime"]).sum()) if not data.empty else 0},
            {"metric": "overlay_sha256", "value": _sha256(OVERLAY_MINUTE_PATH) if OVERLAY_MINUTE_PATH.exists() else ""},
        ]
    )
    audit.to_csv(OVERLAY_AUDIT_PATH, index=False, encoding="utf-8-sig")
    return audit


def _configure_stage124(stage124: Any, selected_universe: pd.DataFrame) -> None:
    stage124.STAGE_ID = STAGE_ID
    stage124.MODEL_TAG = MODEL_TAG
    stage124.OUT = OUT
    stage124.UNIVERSE_DIR = UNIVERSE_DIR
    stage124.DAILY_DIR = DAILY_DIR
    stage124.FRAMES_DIR = FRAMES_DIR
    stage124.STAGE_RECORD_PATH = STAGE_RECORD_PATH
    stage124.SUMMARY_PATH = SUMMARY_PATH
    stage124.PERIOD_SUMMARY_PATH = PERIOD_SUMMARY_PATH
    stage124.ANNUAL_SUMMARY_PATH = ANNUAL_SUMMARY_PATH
    stage124.RUN_STATUS_PATH = RUN_STATUS_PATH
    stage124.CLOSED_LOTS_PATH = CLOSED_LOTS_PATH
    stage124.REPORT_PATH = REPORT_PATH
    stage124.DECISION_PATH = DECISION_PATH
    stage124.LOSS_WINDOW_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_loss_window_daily_pnl_bar_{MODEL_TAG}.png"
    stage124.FULL_SAMPLE_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_full_sample_daily_pnl_bar_{MODEL_TAG}.png"
    stage124.SCATTER_PATH = OUT / f"{OUTPUT_PREFIX}_loss_window_vs_full_sample_scatter_{MODEL_TAG}.png"
    stage124.s901.s861.FULL_MINUTE_BARS_PATH = OVERLAY_MINUTE_PATH
    stage124.s901._FULL_MINUTE_BY_SYMBOL_CACHE = None
    stage124.s901._FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS = set()
    stage124.s901._LAST_MINUTE_AUDIT = {}

    def load_selected_universe(limit: int | None = None) -> pd.DataFrame:
        frame = selected_universe.copy()
        if limit is not None:
            frame = frame.head(int(limit)).copy()
        return frame.reset_index(drop=True)

    stage124._load_universe = load_selected_universe


def _run_selected_products(stage124: Any, selected_universe: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily_frames: list[pd.DataFrame] = []
    closed_frames: list[pd.DataFrame] = []
    statuses: list[dict[str, Any]] = []
    for index, row in enumerate(selected_universe.itertuples(index=False), start=1):
        series = pd.Series(row._asdict())
        product = str(series["product_vt_symbol"])
        print(f"[stage129] {index:02d}/{len(selected_universe)} {product}", flush=True)
        daily, closed, status = stage124._run_product(series, selected_universe, force=True)
        daily_frames.append(daily)
        if not closed.empty:
            closed_frames.append(closed)
        statuses.append(status)
    return stage124._summaries(daily_frames, closed_frames, statuses, selected_universe)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _top10_window_curves(summary: pd.DataFrame, closed_all: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    curve_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for product in TOP10_PRODUCTS:
        daily_path = DAILY_DIR / f"{_slug(product)}_daily.csv.gz"
        if not daily_path.exists():
            continue
        daily = pd.read_csv(daily_path, encoding="utf-8-sig")
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        daily = daily.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        window = daily[daily["date"].between(LOSS_WINDOW_START, LOSS_WINDOW_END)].copy()
        prior = daily[daily["date"].lt(LOSS_WINDOW_START)].tail(1).copy()
        if not prior.empty:
            prior["net_pnl"] = 0.0
            prior["trade_count"] = 0.0
            window = pd.concat([prior, window], ignore_index=True, sort=False)
        if window.empty:
            continue
        window["product_vt_symbol"] = product
        window["net_pnl"] = pd.to_numeric(window.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
        window["trade_count"] = pd.to_numeric(window.get("trade_count", 0.0), errors="coerce").fillna(0.0)
        window["window_reset_equity"] = CAPITAL + window["net_pnl"].cumsum()
        curve_frames.append(
            window[["date", "product_vt_symbol", "net_pnl", "trade_count", "account_equity", "window_reset_equity"]].copy()
        )
        actual_window = window[window["date"].between(LOSS_WINDOW_START, LOSS_WINDOW_END)].copy()
        closed_pnl = 0.0
        if not closed_all.empty and "exit_date" in closed_all.columns:
            closed = closed_all[closed_all["product_vt_symbol"].astype(str).eq(product)].copy()
            closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce").dt.normalize()
            closed_pnl = float(pd.to_numeric(closed[closed["exit_date"].between(LOSS_WINDOW_START, LOSS_WINDOW_END)]["realized_pnl"], errors="coerce").fillna(0.0).sum())
        dd = _drawdown_pct(window["window_reset_equity"])
        daily_net = float(actual_window["net_pnl"].sum())
        summary_rows.append(
            {
                "product": product,
                "daily_net_pnl": daily_net,
                "window_return_pct": daily_net / CAPITAL * 100.0,
                "closed_lot_realized_pnl": closed_pnl,
                "trade_count": int(actual_window["trade_count"].sum()),
                "active_days": int(actual_window["net_pnl"].abs().gt(1e-12).sum()),
                "max_drawdown_pct": float(dd.min()) if len(dd) else 0.0,
                "end_reset_equity": float(window["window_reset_equity"].iloc[-1]),
                "start_actual_equity": float(actual_window["account_equity"].iloc[0]) if len(actual_window) and "account_equity" in actual_window.columns else np.nan,
                "end_actual_equity": float(actual_window["account_equity"].iloc[-1]) if len(actual_window) and "account_equity" in actual_window.columns else np.nan,
            }
        )
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    top10_summary = pd.DataFrame(summary_rows)
    if not top10_summary.empty:
        top10_summary.sort_values("daily_net_pnl", ascending=False, inplace=True)
    return curves, top10_summary


def _baseline_compare(top10_summary: pd.DataFrame) -> pd.DataFrame:
    if not BASELINE_STAGE125_SUMMARY_PATH.exists() or top10_summary.empty:
        return pd.DataFrame()
    baseline = pd.read_csv(BASELINE_STAGE125_SUMMARY_PATH, encoding="utf-8-sig")
    baseline = baseline.add_prefix("baseline_")
    current = top10_summary.add_prefix("overlay_")
    compare = current.merge(baseline, left_on="overlay_product", right_on="baseline_product", how="left")
    for column in ["daily_net_pnl", "window_return_pct", "trade_count", "max_drawdown_pct"]:
        compare[f"delta_{column}"] = pd.to_numeric(compare[f"overlay_{column}"], errors="coerce") - pd.to_numeric(compare[f"baseline_{column}"], errors="coerce")
    return compare.sort_values("overlay_daily_net_pnl", ascending=False).reset_index(drop=True)


def _plot_curves(curves: pd.DataFrame, compare: pd.DataFrame) -> None:
    if not curves.empty:
        data = curves.copy()
        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        fig, ax = plt.subplots(figsize=(13, 7))
        for product, group in data.groupby("product_vt_symbol", sort=False):
            ax.plot(group["date"], group["window_reset_equity"], linewidth=1.5, label=product)
        ax.axhline(CAPITAL, color="#111827", linewidth=1.0, linestyle="--")
        ax.set_title("Stage129 overlay replay: Stage125 top10 reset equity")
        ax.set_ylabel("reset equity")
        ax.grid(alpha=0.25)
        ax.legend(ncol=2, fontsize=8)
        fig.tight_layout()
        fig.savefig(RESET_EQUITY_CHART_PATH, dpi=170)
        plt.close(fig)
    if not compare.empty:
        data = compare.sort_values("delta_daily_net_pnl", ascending=True)
        colors = np.where(data["delta_daily_net_pnl"].ge(0.0), "#16a34a", "#dc2626")
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.barh(data["overlay_product"], data["delta_daily_net_pnl"], color=colors)
        ax.axvline(0, color="#111827", linewidth=1.0)
        ax.set_title("Stage129 overlay replay vs old Stage125: loss-window PnL delta")
        ax.set_xlabel("delta daily net pnl")
        ax.grid(axis="x", alpha=0.25)
        fig.tight_layout()
        fig.savefig(PNL_DIFF_CHART_PATH, dpi=170)
        plt.close(fig)


def _make_decision(
    overlay_audit: pd.DataFrame,
    summary: pd.DataFrame,
    run_status: pd.DataFrame,
    top10_summary: pd.DataFrame,
    compare: pd.DataFrame,
) -> dict[str, Any]:
    ok_count = int(run_status["status"].astype(str).eq("ok").sum()) if not run_status.empty and "status" in run_status.columns else 0
    minute_loaded_positive = int(pd.to_numeric(run_status.get("minute_loaded_symbol_count", pd.Series(dtype=float)), errors="coerce").fillna(0).gt(0).sum()) if not run_status.empty else 0
    return {
        "stage": "Stage129",
        "stage_id": STAGE_ID,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": "stage129_stage125_top10_overlay_replay_completed",
        "scope": "Rerun Stage125 top10 products as standalone C9/15w true-engine replays with Stage127 raw minute overlay injected through Stage901/Stage861 minute source.",
        "selected_product_count": len(TOP10_PRODUCTS),
        "ok_product_count": ok_count,
        "minute_loaded_positive_product_count": minute_loaded_positive,
        "overlay_rows": int(pd.to_numeric(overlay_audit[overlay_audit["metric"].eq("overlay_rows")]["value"], errors="coerce").iloc[0]) if not overlay_audit.empty else 0,
        "overlay_symbol_count": int(pd.to_numeric(overlay_audit[overlay_audit["metric"].eq("overlay_symbol_count")]["value"], errors="coerce").iloc[0]) if not overlay_audit.empty else 0,
        "loss_window_total_pnl": float(pd.to_numeric(top10_summary.get("daily_net_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()) if not top10_summary.empty else 0.0,
        "baseline_delta_total_pnl": float(pd.to_numeric(compare.get("delta_daily_net_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()) if not compare.empty else 0.0,
        "stage861_original_file_overwritten": False,
        "strategy_rule_changed": False,
        "true_engine_run": True,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_reflection_before": "否。本阶段只把已验收 raw 分钟补数接入固定 C9/15w 回测，不新增参数、阈值、品种排序规则。",
        "overfit_reflection_after": "否。结果只用于验证数据接线和 stop/retry 口径变化，不能直接作为扩池规则。",
        "continue_value_before": "有。Stage128 已证明 raw entry-day 数据完整，但 Stage861 未接入；必须重跑才能知道结果是否变化。",
        "continue_value_after": "有。若结果变化显著，下一步才考虑全 57 品种 overlay 重跑；若变化很小，Stage125 日级库存结论更稳。",
        "source_links": SOURCE_LINKS,
        "outputs": {
            "overlay_minute": str(OVERLAY_MINUTE_PATH),
            "overlay_audit": str(OVERLAY_AUDIT_PATH),
            "summary": str(SUMMARY_PATH),
            "period_summary": str(PERIOD_SUMMARY_PATH),
            "run_status": str(RUN_STATUS_PATH),
            "top10_curves": str(TOP10_CURVES_PATH),
            "top10_summary": str(TOP10_SUMMARY_PATH),
            "baseline_compare": str(BASELINE_COMPARE_PATH),
            "reset_equity_chart": str(RESET_EQUITY_CHART_PATH),
            "pnl_diff_chart": str(PNL_DIFF_CHART_PATH),
            "report": str(REPORT_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    overlay_audit: pd.DataFrame,
    summary: pd.DataFrame,
    run_status: pd.DataFrame,
    top10_summary: pd.DataFrame,
    compare: pd.DataFrame,
) -> None:
    status_cols = [
        "product_vt_symbol",
        "status",
        "minute_source",
        "minute_requested_symbol_count",
        "minute_loaded_symbol_count",
        "minute_missing_symbol_count",
        "daily_rows",
        "closed_lots",
    ]
    available_status_cols = [column for column in status_cols if column in run_status.columns]
    lines = [
        "# Stage129 Stage125 前十品种 overlay 复跑",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- decision：`{decision['decision']}`",
        "- 阶段性质：数据接线复跑；不改策略参数，不覆盖 Stage861 原文件，不连接 CTP，不调用订单 API。",
        f"- overlay minute：`{OVERLAY_MINUTE_PATH}`",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk 官方文档和 GitHub 仍支持 `TqBacktest + get_kline_serial + wait_update` 的历史 K 线获取路径。",
        "- 我的判断：回测阶段不再重新联网取数，只消费 Stage127/128 已验收的本地 raw 分钟文件，并通过 overlay 注入 Stage901/Stage861 分钟源。",
        "",
        "## Overlay Audit",
        "",
        _md_table(overlay_audit),
        "",
        "## Top10 Loss Window Summary",
        "",
        _md_table(top10_summary, max_rows=20),
        "",
        "## Compare With Old Stage125",
        "",
        _md_table(
            compare[
                [
                    "overlay_product",
                    "overlay_daily_net_pnl",
                    "baseline_daily_net_pnl",
                    "delta_daily_net_pnl",
                    "overlay_trade_count",
                    "baseline_trade_count",
                    "delta_trade_count",
                    "overlay_max_drawdown_pct",
                    "baseline_max_drawdown_pct",
                    "delta_max_drawdown_pct",
                ]
            ]
            if not compare.empty
            else pd.DataFrame(),
            max_rows=20,
        ),
        "",
        "## Run Status",
        "",
        _md_table(run_status[available_status_cols] if available_status_cols else run_status, max_rows=20),
        "",
        "## Product Summary",
        "",
        _md_table(
            summary[
                [
                    "product_vt_symbol",
                    "loss_window_daily_net_pnl",
                    "total_net_pnl",
                    "total_trade_count",
                    "max_drawdown_pct",
                    "sharpe",
                ]
            ]
            if not summary.empty
            else pd.DataFrame(),
            max_rows=20,
        ),
        "",
        "## Charts",
        "",
        f"- reset equity：`{RESET_EQUITY_CHART_PATH}`",
        f"- baseline diff：`{PNL_DIFF_CHART_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], top10_summary: pd.DataFrame, compare: pd.DataFrame, run_status: pd.DataFrame) -> None:
    lines = [
        "# Stage129 Stage125 前十品种 overlay 复跑",
        "",
        f"- 时间：{decision['generated_at']}",
        f"- line_id：`{LINE_ID}`",
        "- 类型：数据接线复跑，不是新策略版本",
        f"- decision：`{decision['decision']}`",
        f"- selected_product_count：`{decision['selected_product_count']}`",
        f"- ok_product_count：`{decision['ok_product_count']}`",
        f"- minute_loaded_positive_product_count：`{decision['minute_loaded_positive_product_count']}`",
        f"- overlay_rows：`{decision['overlay_rows']}`",
        f"- overlay_symbol_count：`{decision['overlay_symbol_count']}`",
        f"- loss_window_total_pnl：`{decision['loss_window_total_pnl']:.4f}`",
        f"- baseline_delta_total_pnl：`{decision['baseline_delta_total_pnl']:.4f}`",
        "- 策略变更：无",
        "- true engine run：有，仅 Stage125 前十单品种 replay",
        "- 订单 API：`0`",
        "- CTP：`False`",
        "- Stage861 原文件覆盖：`False`",
        "",
        "## Top10 Summary",
        "",
        _md_table(top10_summary, max_rows=20),
        "",
        "## Compare",
        "",
        _md_table(compare, max_rows=20),
        "",
        "## Run Status",
        "",
        _md_table(run_status, max_rows=20),
        "",
        "## 后续",
        "",
        "- 本阶段只验证 Stage125 前十品种 overlay 接线，不等于 full-market 57 品种全量重跑。",
        "- 若需要重新排序全市场候选池，下一步做 Stage130：全 57 品种 overlay force replay，再重新派生 Stage125 风格曲线。",
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
    UNIVERSE_DIR.mkdir(parents=True, exist_ok=True)
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage124 = _load_stage124()
    full_universe = stage124._load_universe(limit=None)
    selected_universe = full_universe[full_universe["product_vt_symbol"].astype(str).isin(TOP10_PRODUCTS)].copy()
    selected_universe["_order"] = selected_universe["product_vt_symbol"].astype(str).map({product: i for i, product in enumerate(TOP10_PRODUCTS)})
    selected_universe = selected_universe.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)
    overlay_audit = build_overlay_minute_file(stage124, selected_universe)
    _configure_stage124(stage124, selected_universe)
    summary, period, annual, run_status, closed_all = _run_selected_products(stage124, selected_universe)
    curves, top10_summary = _top10_window_curves(summary, closed_all)
    compare = _baseline_compare(top10_summary)
    _plot_curves(curves, compare)
    decision = _make_decision(overlay_audit, summary, run_status, top10_summary, compare)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    period.to_csv(PERIOD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    run_status.to_csv(RUN_STATUS_PATH, index=False, encoding="utf-8-sig")
    closed_all.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(TOP10_CURVES_PATH, index=False, encoding="utf-8-sig")
    top10_summary.to_csv(TOP10_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    compare.to_csv(BASELINE_COMPARE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, overlay_audit, summary, run_status, top10_summary, compare)
    _write_stage_record(decision, top10_summary, compare, run_status)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
