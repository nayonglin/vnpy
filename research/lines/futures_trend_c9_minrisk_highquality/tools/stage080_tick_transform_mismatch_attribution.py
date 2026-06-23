from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage080"
MODEL_TAG = "stage080_tick_transform_mismatch_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage080_c9_minrisk_tick_transform_mismatch_attribution"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage080_tick_transform_mismatch_attribution"

STAGE045_CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE079_DIR = LINE_DIR / "outputs" / "stage079_tqsdk_tick_manifest_transform_smoke"
STAGE079_AUDIT_IN = (
    STAGE079_DIR
    / "qmt_roll_stage079_c9_minrisk_tqsdk_tick_manifest_transform_smoke_transform_audit_"
    "stage079_tqsdk_tick_manifest_transform_smoke_v1.csv"
)

DETAIL_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv"
CANDIDATE_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_matrix_{MODEL_TAG}.csv"
YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_matrix_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_transform_class_chart_{MODEL_TAG}.png"
CANDIDATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_transform_chart_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_transform_heatmap_{MODEL_TAG}.png"
TICK_ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_mismatch_tick_atlas_{MODEL_TAG}.png"

OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"
INITIAL_CAPITAL = 150_000.0
PRICE_TOL = 1e-9

FIRST_FIELDS = ["last_price", "bid_price1", "ask_price1", "average", "highest", "lowest"]
TOPBOOK_FIELDS = ["last_price", "bid_price1", "ask_price1"]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _price_exact(value: Any, target: float) -> bool:
    value_f = _safe_float(value)
    return bool(np.isfinite(value_f) and abs(value_f - target) <= PRICE_TOL)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(col) for col in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in display.columns) + " |")
    return "\n".join(lines)


def _official_metrics(curve: pd.DataFrame) -> dict[str, float]:
    equity = _safe_num(curve["official_equity" if "official_equity" in curve.columns else "account_equity"]).dropna()
    dd = _safe_num(curve["official_drawdown_pct" if "official_drawdown_pct" in curve.columns else "drawdown_pct"]).dropna()
    daily_ret = _safe_num(curve.get("daily_return", pd.Series(dtype=float))).dropna()
    sharpe = np.nan
    if len(daily_ret) > 2 and daily_ret.std(ddof=1) > 0:
        sharpe = float(daily_ret.mean() / daily_ret.std(ddof=1) * np.sqrt(252))
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": (float(equity.iloc[-1]) / INITIAL_CAPITAL - 1.0) * 100.0,
        "max_drawdown_pct": float(dd.min()),
        "sharpe": sharpe,
        "total_slippage": float(_safe_num(curve.get("slippage", pd.Series(dtype=float))).fillna(0.0).sum()),
        "total_trade_count": float(_safe_num(curve.get("trade_count", pd.Series(dtype=float))).sum()),
    }


def _load_ticks(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    ticks = _read_csv(path)
    if "tick_datetime" in ticks.columns:
        ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
    for col in [
        "last_price",
        "average",
        "highest",
        "lowest",
        "bid_price1",
        "ask_price1",
        "volume",
        "open_interest",
    ]:
        if col in ticks.columns:
            ticks[col] = _safe_num(ticks[col])
    return ticks.dropna(subset=["tick_datetime"]).sort_values("tick_datetime").reset_index(drop=True)


def _target_minute(row: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(row["authority_anchor_time"]).floor("min")
    return start, start + pd.Timedelta(minutes=1)


def _first_exact_fields(first: pd.Series, official: float, fields: list[str]) -> list[str]:
    result = []
    for field in fields:
        if field in first.index and _price_exact(first[field], official):
            result.append(field)
    return result


def _tick_touch_stats(target: pd.DataFrame, official: float, start: pd.Timestamp) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "any_last_bid_ask_touch": 0,
        "any_first_tick_state_touch": 0,
        "official_inside_any_spread": 0,
        "first_topbook_touch_index": np.nan,
        "first_topbook_touch_offset_sec": np.nan,
        "first_topbook_touch_fields": "",
        "first_state_touch_index": np.nan,
        "first_state_touch_offset_sec": np.nan,
        "first_state_touch_fields": "",
        "min_topbook_abs_diff": np.nan,
        "min_spread_gap": np.nan,
    }
    if target.empty:
        return stats

    topbook_diffs: list[float] = []
    spread_gaps: list[float] = []
    for idx, tick in target.iterrows():
        top_fields = _first_exact_fields(tick, official, TOPBOOK_FIELDS)
        state_fields = _first_exact_fields(tick, official, FIRST_FIELDS)
        if top_fields:
            stats["any_last_bid_ask_touch"] = 1
            if pd.isna(stats["first_topbook_touch_index"]):
                stats["first_topbook_touch_index"] = int(idx)
                stats["first_topbook_touch_offset_sec"] = float((tick["tick_datetime"] - start).total_seconds())
                stats["first_topbook_touch_fields"] = ",".join(top_fields)
        if state_fields:
            stats["any_first_tick_state_touch"] = 1
            if pd.isna(stats["first_state_touch_index"]):
                stats["first_state_touch_index"] = int(idx)
                stats["first_state_touch_offset_sec"] = float((tick["tick_datetime"] - start).total_seconds())
                stats["first_state_touch_fields"] = ",".join(state_fields)
        for field in TOPBOOK_FIELDS:
            if field in target.columns:
                value = _safe_float(tick[field])
                if np.isfinite(value):
                    topbook_diffs.append(abs(value - official))
        bid = _safe_float(tick.get("bid_price1"))
        ask = _safe_float(tick.get("ask_price1"))
        if np.isfinite(bid) and np.isfinite(ask):
            lo = min(bid, ask)
            hi = max(bid, ask)
            if lo <= official <= hi:
                stats["official_inside_any_spread"] = 1
                spread_gaps.append(0.0)
            else:
                spread_gaps.append(min(abs(official - lo), abs(official - hi)))
    if topbook_diffs:
        stats["min_topbook_abs_diff"] = float(min(topbook_diffs))
    if spread_gaps:
        stats["min_spread_gap"] = float(min(spread_gaps))
    return stats


def _build_detail(audit: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for _, row in audit.iterrows():
        official = _safe_float(row["official_open_price"])
        start, end = _target_minute(row)
        ticks = _load_ticks(Path(str(row["tick_path"])))
        target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
        target = target.reset_index(drop=True)
        record: dict[str, Any] = {
            "candidate_index": int(row["candidate_index"]),
            "official_open_trade_id": row["official_open_trade_id"],
            "vt_symbol": row["vt_symbol"],
            "tq_symbol": row["tq_symbol"],
            "direction": row.get("direction", ""),
            "official_open_year": int(row["official_open_year"]),
            "official_open_date": row["official_open_date"],
            "authority_anchor_time": row["authority_anchor_time"],
            "official_open_price": official,
            "raw_anchor_open": _safe_float(row.get("raw_anchor_open")),
            "stage449_anchor_open": _safe_float(row.get("stage449_anchor_open")),
            "tick_path": row["tick_path"],
            "target_tick_rows": int(len(target)),
            "realized_pnl": _safe_float(row.get("realized_pnl"), 0.0),
            "source_decision_class": row.get("source_decision_class", ""),
        }
        if not target.empty:
            first = target.iloc[0]
            last = target.iloc[-1]
            record.update(
                {
                    "first_tick_datetime": first["tick_datetime"],
                    "first_tick_offset_sec": float((first["tick_datetime"] - start).total_seconds()),
                    "first_last": _safe_float(first.get("last_price")),
                    "first_bid1": _safe_float(first.get("bid_price1")),
                    "first_ask1": _safe_float(first.get("ask_price1")),
                    "first_mid1": (_safe_float(first.get("bid_price1")) + _safe_float(first.get("ask_price1"))) / 2,
                    "first_average": _safe_float(first.get("average")),
                    "first_highest": _safe_float(first.get("highest")),
                    "first_lowest": _safe_float(first.get("lowest")),
                    "last_last": _safe_float(last.get("last_price")),
                    "target_min_last": float(_safe_num(target["last_price"]).min()),
                    "target_max_last": float(_safe_num(target["last_price"]).max()),
                }
            )
            first_state_fields = _first_exact_fields(first, official, FIRST_FIELDS)
            first_topbook_fields = _first_exact_fields(first, official, TOPBOOK_FIELDS)
            record["first_tick_state_exact_fields"] = ",".join(first_state_fields)
            record["first_tick_topbook_exact_fields"] = ",".join(first_topbook_fields)
            record["first_tick_state_union_exact"] = int(bool(first_state_fields))
            record["first_tick_topbook_union_exact"] = int(bool(first_topbook_fields))
            for field, out_col in [
                ("last_price", "first_last_exact"),
                ("bid_price1", "first_bid1_exact"),
                ("ask_price1", "first_ask1_exact"),
                ("average", "first_average_exact"),
                ("highest", "first_highest_exact"),
                ("lowest", "first_lowest_exact"),
            ]:
                record[out_col] = int(_price_exact(first.get(field), official))
            record["first_mid1_exact"] = int(_price_exact(record["first_mid1"], official))
            record["last_last_exact"] = int(_price_exact(record["last_last"], official))
            record["target_min_last_exact"] = int(_price_exact(record["target_min_last"], official))
            record["target_max_last_exact"] = int(_price_exact(record["target_max_last"], official))
        else:
            for col in [
                "first_tick_datetime",
                "first_tick_offset_sec",
                "first_last",
                "first_bid1",
                "first_ask1",
                "first_mid1",
                "first_average",
                "first_highest",
                "first_lowest",
                "last_last",
                "target_min_last",
                "target_max_last",
            ]:
                record[col] = np.nan
            for col in [
                "first_tick_state_exact_fields",
                "first_tick_topbook_exact_fields",
            ]:
                record[col] = ""
            for col in [
                "first_tick_state_union_exact",
                "first_tick_topbook_union_exact",
                "first_last_exact",
                "first_bid1_exact",
                "first_ask1_exact",
                "first_average_exact",
                "first_highest_exact",
                "first_lowest_exact",
                "first_mid1_exact",
                "last_last_exact",
                "target_min_last_exact",
                "target_max_last_exact",
            ]:
                record[col] = 0

        record.update(_tick_touch_stats(target, official, start))
        if record["first_last_exact"]:
            transform_class = "strict_vnpy_first_last_exact"
        elif record["any_last_bid_ask_touch"]:
            transform_class = "topbook_touch_but_not_first_last"
        elif record["first_tick_state_union_exact"]:
            transform_class = "first_tick_state_only_not_topbook"
        else:
            transform_class = "no_tick_state_match"
        record["transform_class"] = transform_class
        records.append(record)
    return pd.DataFrame(records).sort_values(["official_open_year", "official_open_date", "candidate_index"]).reset_index(drop=True)


def _candidate_matrix(detail: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("first_last", "first_last_exact", "deterministic_topbook", "vnpy BarGenerator-compatible first last_price"),
        ("first_bid1", "first_bid1_exact", "deterministic_topbook", "first tick bid_price1"),
        ("first_ask1", "first_ask1_exact", "deterministic_topbook", "first tick ask_price1"),
        ("first_mid1", "first_mid1_exact", "deterministic_topbook", "first tick mid of bid/ask"),
        ("first_average", "first_average_exact", "deterministic_tick_state", "first tick cumulative average"),
        ("first_highest", "first_highest_exact", "deterministic_tick_state", "first tick cumulative highest"),
        ("first_lowest", "first_lowest_exact", "deterministic_tick_state", "first tick cumulative lowest"),
        ("last_last", "last_last_exact", "deterministic_topbook", "target minute last last_price"),
        ("target_min_last", "target_min_last_exact", "deterministic_topbook", "target minute min last_price"),
        ("target_max_last", "target_max_last_exact", "deterministic_topbook", "target minute max last_price"),
        ("any_last_bid_ask_touch", "any_last_bid_ask_touch", "diagnostic_upper_bound", "any target-minute last/bid/ask equals official"),
        ("inside_any_spread", "official_inside_any_spread", "diagnostic_upper_bound", "official inside any target-minute bid/ask spread"),
        ("first_tick_state_union", "first_tick_state_union_exact", "diagnostic_upper_bound", "official equals any first-tick state field"),
    ]
    rows = []
    total = len(detail)
    years = sorted(detail["official_open_year"].unique())
    for name, col, kind, desc in specs:
        exact = int(_safe_num(detail[col]).fillna(0).sum())
        by_year = detail.groupby("official_open_year")[col].sum()
        full_years = 0
        for year in years:
            year_total = int((detail["official_open_year"] == year).sum())
            if year_total and int(by_year.get(year, 0)) == year_total:
                full_years += 1
        rows.append(
            {
                "transform": name,
                "kind": kind,
                "description": desc,
                "exact_count": exact,
                "total_count": total,
                "exact_rate": exact / total if total else np.nan,
                "full_exact_year_count": full_years,
                "year_count": len(years),
                "all_rows_exact": int(exact == total and total > 0),
                "all_years_full_exact": int(full_years == len(years) and len(years) > 0),
            }
        )
    return pd.DataFrame(rows).sort_values(["exact_count", "transform"], ascending=[False, True]).reset_index(drop=True)


def _year_matrix(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, data in detail.groupby("official_open_year"):
        rows.append(
            {
                "year": int(year),
                "manifest_rows": int(len(data)),
                "first_last_exact": int(data["first_last_exact"].sum()),
                "first_average_exact": int(data["first_average_exact"].sum()),
                "first_lowest_exact": int(data["first_lowest_exact"].sum()),
                "first_bid1_exact": int(data["first_bid1_exact"].sum()),
                "any_last_bid_ask_touch": int(data["any_last_bid_ask_touch"].sum()),
                "official_inside_any_spread": int(data["official_inside_any_spread"].sum()),
                "first_tick_state_union_exact": int(data["first_tick_state_union_exact"].sum()),
                "net_realized_pnl": float(_safe_num(data["realized_pnl"]).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


def _decision(summary: dict[str, Any]) -> tuple[str, str]:
    if summary["manifest_size"] == 0:
        return "stage080_no_manifest_no_rule", "restore_stage079_outputs_before_transform_attribution"
    if summary["best_deterministic_exact_count"] == summary["manifest_size"]:
        return (
            "stage080_unified_transform_found_expand_full_219_no_rule",
            "expand_same_transform_to_all_timestamp_ready_initial_opens_before_any_microstructure_rule",
        )
    if (
        summary["any_last_bid_ask_touch_count"] < summary["manifest_size"]
        or summary["inside_any_spread_count"] < summary["manifest_size"]
    ):
        return (
            "stage080_no_unified_topbook_transform_tq_tick_downgraded_to_tca_no_rule",
            "stop_tq_tick_as_same_source_microstructure_and_use_only_tca_or_authorized_vendor_tick",
        )
    return (
        "stage080_no_single_field_transform_no_rule",
        "inspect_stage449_raw_generation_or_authorized_vendor_open_field_before_rules",
    )


def _plot_official_path(curve: pd.DataFrame, detail: pd.DataFrame) -> None:
    curve = curve.copy()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    detail = detail.copy()
    detail["official_open_date"] = pd.to_datetime(detail["official_open_date"], errors="coerce")
    equity_col = "official_equity" if "official_equity" in curve.columns else "account_equity"
    dd_col = "official_drawdown_pct" if "official_drawdown_pct" in curve.columns else "drawdown_pct"
    colors = {
        "strict_vnpy_first_last_exact": "#2ca02c",
        "topbook_touch_but_not_first_last": "#ff7f0e",
        "first_tick_state_only_not_topbook": "#d62728",
        "no_tick_state_match": "#7f7f7f",
    }
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), gridspec_kw={"height_ratios": [2, 1, 1.2]})
    axes[0].plot(curve["date"], curve[equity_col], color="#1f77b4", lw=1.8, label="Official C9/15w equity")
    for bucket, data in detail.groupby("transform_class"):
        x = data["official_open_date"].astype("int64")
        y = np.interp(x, curve["date"].astype("int64"), curve[equity_col])
        axes[0].scatter(data["official_open_date"], y, s=42, color=colors.get(bucket, "#7f7f7f"), label=bucket, alpha=0.88)
    axes[0].set_title("Official path unchanged; Stage080 classifies tick transform mismatch only")
    axes[0].set_ylabel("Equity")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)
    axes[1].plot(curve["date"], curve[dd_col], color="#9467bd", lw=1.4)
    axes[1].fill_between(curve["date"], curve[dd_col], 0, color="#9467bd", alpha=0.15)
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(alpha=0.25)
    for bucket, data in detail.sort_values("official_open_date").groupby("transform_class"):
        pnl = data.sort_values("official_open_date").set_index("official_open_date")["realized_pnl"].cumsum()
        axes[2].plot(pnl.index, pnl.values, marker="o", lw=1.4, color=colors.get(bucket, "#7f7f7f"), label=bucket)
    axes[2].axhline(0, color="black", lw=0.8, alpha=0.45)
    axes[2].set_title("Manifest realized PnL by transform class (diagnostic distribution only)")
    axes[2].set_ylabel("Cumulative PnL")
    axes[2].grid(alpha=0.25)
    axes[2].legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(OFFICIAL_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_candidate_chart(matrix: pd.DataFrame) -> None:
    data = matrix.sort_values("exact_count", ascending=True)
    colors = data["kind"].map(
        {
            "deterministic_topbook": "#1f77b4",
            "deterministic_tick_state": "#ff7f0e",
            "diagnostic_upper_bound": "#9467bd",
        }
    ).fillna("#7f7f7f")
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.barh(data["transform"], data["exact_count"], color=colors, alpha=0.86)
    for _, row in data.iterrows():
        ax.text(row["exact_count"] + 0.25, row["transform"], f"{int(row['exact_count'])}/{int(row['total_count'])}", va="center", fontsize=8)
    ax.axvline(data["total_count"].max(), color="black", lw=0.8, linestyle="--", alpha=0.45)
    ax.set_title("Stage080 predefined transform candidates; no single deterministic transform reaches 28/28")
    ax.set_xlabel("Exact rows")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CANDIDATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_year_heatmap(year: pd.DataFrame) -> None:
    cols = [
        "first_last_exact",
        "first_average_exact",
        "first_lowest_exact",
        "first_bid1_exact",
        "any_last_bid_ask_touch",
        "official_inside_any_spread",
        "first_tick_state_union_exact",
    ]
    values = year[cols].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    im = ax.imshow(values, aspect="auto", cmap="YlGnBu", vmin=0, vmax=max(1.0, float(year["manifest_rows"].max())))
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(year)))
    ax.set_yticklabels(year["year"].astype(str))
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{int(values[i, j])}", ha="center", va="center", fontsize=8)
    ax.set_title("Stage080 transform evidence by year (each year has 4 manifest rows)")
    fig.colorbar(im, ax=ax, shrink=0.82, label="Exact rows")
    fig.tight_layout()
    fig.savefig(YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_tick_atlas(detail: pd.DataFrame) -> None:
    samples = pd.concat(
        [
            detail[detail["transform_class"].eq("first_tick_state_only_not_topbook")],
            detail[detail["transform_class"].eq("topbook_touch_but_not_first_last")].sort_values("realized_pnl", key=lambda s: s.abs(), ascending=False).head(4),
            detail[detail["transform_class"].eq("strict_vnpy_first_last_exact")].head(2),
        ],
        ignore_index=True,
    ).drop_duplicates("candidate_index").head(10)
    if samples.empty:
        return
    fig, axes = plt.subplots(len(samples), 1, figsize=(14, max(4, 2.2 * len(samples))), squeeze=False)
    for i, (_, row) in enumerate(samples.iterrows()):
        ax = axes[i, 0]
        ticks = _load_ticks(Path(str(row["tick_path"])))
        start, end = _target_minute(row)
        window = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] <= end + pd.Timedelta(seconds=20))].copy()
        if not window.empty:
            for col, color, label in [
                ("last_price", "#1f77b4", "last"),
                ("bid_price1", "#2ca02c", "bid1"),
                ("ask_price1", "#d62728", "ask1"),
                ("average", "#8c564b", "avg"),
                ("highest", "#17becf", "highest"),
                ("lowest", "#bcbd22", "lowest"),
            ]:
                if col in window.columns:
                    alpha = 0.85 if col in TOPBOOK_FIELDS else 0.55
                    lw = 1.0 if col in TOPBOOK_FIELDS else 0.8
                    ax.plot(window["tick_datetime"], window[col], color=color, lw=lw, alpha=alpha, label=label)
        else:
            ax.text(0.5, 0.5, "no local tick rows", transform=ax.transAxes, ha="center", va="center")
        for col, color, label in [
            ("official_open_price", "black", "official"),
            ("raw_anchor_open", "#ff7f0e", "raw"),
            ("stage449_anchor_open", "#9467bd", "stage449"),
        ]:
            value = _safe_float(row.get(col))
            if np.isfinite(value):
                ax.axhline(value, color=color, linestyle="--", lw=0.9, label=label)
        ax.axvline(start, color="#999999", linestyle=":", lw=0.8)
        ax.set_title(
            f"candidate {int(row['candidate_index'])} {row['vt_symbol']} {row['authority_anchor_time']} "
            f"class={row['transform_class']} first_fields={row['first_tick_state_exact_fields']}",
            fontsize=9,
        )
        ax.grid(alpha=0.22)
        ax.legend(loc="upper left", fontsize=6, ncol=6)
    fig.tight_layout()
    fig.savefig(TICK_ATLAS_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: dict[str, Any], matrix: pd.DataFrame, year: pd.DataFrame, detail: pd.DataFrame) -> None:
    head_cols = [
        "candidate_index",
        "vt_symbol",
        "official_open_year",
        "official_open_price",
        "transform_class",
        "first_tick_state_exact_fields",
        "first_last_exact",
        "first_average_exact",
        "any_last_bid_ask_touch",
        "official_inside_any_spread",
        "realized_pnl",
    ]
    report = [
        "# Stage080 tick transform mismatch attribution",
        "",
        f"- decision: `{summary['decision']}`",
        f"- next_step: `{summary['next_step']}`",
        f"- official: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "",
        "## Summary",
        "",
        _md_table(pd.DataFrame([summary])),
        "",
        "## Candidate Matrix",
        "",
        _md_table(matrix[["transform", "kind", "exact_count", "total_count", "exact_rate", "full_exact_year_count", "all_rows_exact"]]),
        "",
        "## Year Matrix",
        "",
        _md_table(year),
        "",
        "## Detail Head",
        "",
        _md_table(detail[head_cols], max_rows=28),
        "",
        "## Visual Outputs",
        "",
        f"- official path chart: `{OFFICIAL_PATH_CHART_OUT.relative_to(REPO_DIR)}`",
        f"- candidate transform chart: `{CANDIDATE_CHART_OUT.relative_to(REPO_DIR)}`",
        f"- year heatmap: `{YEAR_HEATMAP_OUT.relative_to(REPO_DIR)}`",
        f"- mismatch tick atlas: `{TICK_ATLAS_OUT.relative_to(REPO_DIR)}`",
        "",
        "## Interpretation",
        "",
        "- This stage is a transform attribution gate only; it does not add a trading rule or run a true engine.",
        "- `first_last` is the strict BarGenerator-compatible candidate; it remains far below full coverage.",
        "- `first_tick_state_union` reaching full coverage is diagnostic only because the exact field varies across last/bid/ask/average/highest/lowest.",
        "- Rule permission remains `0` because no single deterministic top-book or first-tick field transform rebuilds official/raw/Stage449 open across the small manifest.",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _read_csv(STAGE045_CURVE_IN)
    audit = _read_csv(STAGE079_AUDIT_IN)
    for col in ["official_open_date", "authority_anchor_time"]:
        audit[col] = pd.to_datetime(audit[col], errors="coerce")
    detail = _build_detail(audit)
    matrix = _candidate_matrix(detail)
    year = _year_matrix(detail)
    metrics = _official_metrics(curve)
    deterministic = matrix[matrix["kind"].isin(["deterministic_topbook", "deterministic_tick_state"])]
    best = deterministic.sort_values("exact_count", ascending=False).iloc[0]
    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        **metrics,
        "manifest_size": int(len(detail)),
        "manifest_year_count": int(detail["official_open_year"].nunique()),
        "best_deterministic_transform": str(best["transform"]),
        "best_deterministic_exact_count": int(best["exact_count"]),
        "first_last_exact_count": int(detail["first_last_exact"].sum()),
        "first_average_exact_count": int(detail["first_average_exact"].sum()),
        "first_tick_state_union_exact_count": int(detail["first_tick_state_union_exact"].sum()),
        "any_last_bid_ask_touch_count": int(detail["any_last_bid_ask_touch"].sum()),
        "inside_any_spread_count": int(detail["official_inside_any_spread"].sum()),
        "topbook_or_spread_miss_count": int(
            ((detail["any_last_bid_ask_touch"].eq(0)) | (detail["official_inside_any_spread"].eq(0))).sum()
        ),
        "strict_vnpy_first_last_exact_count": int(detail["transform_class"].eq("strict_vnpy_first_last_exact").sum()),
        "topbook_touch_but_not_first_last_count": int(detail["transform_class"].eq("topbook_touch_but_not_first_last").sum()),
        "first_tick_state_only_not_topbook_count": int(detail["transform_class"].eq("first_tick_state_only_not_topbook").sum()),
        "rule_candidate_allowed_count": 0,
    }
    decision, next_step = _decision(summary)
    summary["decision"] = decision
    summary["next_step"] = next_step

    _write_csv(detail, DETAIL_OUT)
    _write_csv(matrix, CANDIDATE_MATRIX_OUT)
    _write_csv(year, YEAR_MATRIX_OUT)
    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot_official_path(curve, detail)
    _plot_candidate_chart(matrix)
    _plot_year_heatmap(year)
    _plot_tick_atlas(detail)
    _write_report(summary, matrix, year, detail)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
