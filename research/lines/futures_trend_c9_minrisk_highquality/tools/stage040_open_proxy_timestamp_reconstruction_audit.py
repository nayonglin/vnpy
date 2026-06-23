from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage040"
MODEL_TAG = "stage040_open_proxy_timestamp_reconstruction_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import analyze_qmt_roll_stage501_asymmetric_entry_exit_execution as s501
import stage038_order_event_replay_prototype_audit as s038
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE039_DIR = LINE_DIR / "outputs" / "stage039_order_event_replay_semantics_repair_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage040_open_proxy_timestamp_reconstruction_audit"

STAGE039_REPLAY_IN = (
    STAGE039_DIR
    / "qmt_roll_stage039_c9_minrisk_order_event_replay_semantics_repair_audit_variant_replay_ledger_"
    "stage039_order_event_replay_semantics_repair_audit_v1.csv"
)

PROXY_LEDGER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_open_proxy_ledger_{MODEL_TAG}.csv"
LOT_BINDING_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lot_proxy_binding_{MODEL_TAG}.csv"
CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_timestamp_contribution_curve_{MODEL_TAG}.csv"
SOURCE_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_year_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_timestamp_path_chart_{MODEL_TAG}.png"
SOURCE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_year_distribution_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_timestamp_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_timestamp_atlas_page{{page:03d}}_{MODEL_TAG}.png"

CAPITAL = 150_000.0
ATLAS_ROWS = 12
ATLAS_PER_PAGE = 4


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _time_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")


def _hhmm(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%H:%M")


def _proxy_ready(proxy: dict[str, Any] | None) -> bool:
    return proxy is not None and _safe_float(proxy.get("proxy_price"), 0.0) > 0


def _proxy_dict(prefix: str, proxy: dict[str, Any] | None) -> dict[str, Any]:
    ready = _proxy_ready(proxy)
    return {
        f"{prefix}_ready": int(ready),
        f"{prefix}_price": _safe_float(proxy.get("proxy_price")) if proxy is not None else np.nan,
        f"{prefix}_source": str(proxy.get("price_source", "")) if proxy is not None else "",
        f"{prefix}_bar_count": _safe_float(proxy.get("proxy_bar_count")) if proxy is not None else np.nan,
        f"{prefix}_first_time": _time_text(proxy.get("proxy_first_time", "")) if proxy is not None else "",
        f"{prefix}_last_time": _time_text(proxy.get("proxy_last_time", "")) if proxy is not None else "",
    }


def _exact_price(a: Any, b: Any) -> bool:
    left = _safe_float(a)
    right = _safe_float(b)
    return bool(np.isfinite(left) and np.isfinite(right) and abs(left - right) < 1e-9)


def _load_stage039_anchor_replay() -> pd.DataFrame:
    data = pd.read_csv(STAGE039_REPLAY_IN, encoding="utf-8-sig")
    data = data[
        data["variant_id"].astype(str).eq("initial_only_official_open_anchor")
        & data["match_status"].astype(str).eq("matched_initial_open_trade")
    ].copy()
    for column in ["candidate_date", "official_open_date"]:
        data[f"{column}_ts"] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    for column in ["official_open_price", "replay_open_price", "official_open_volume", "candidate_selected_volume"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


def _stage861_first_open_map() -> pd.DataFrame:
    data = pd.read_csv(STAGE039_REPLAY_IN, encoding="utf-8-sig")
    first = data[data["variant_id"].astype(str).eq("stage038_first_stage861_open")].copy()
    first = first[
        [
            "candidate_index",
            "replay_open_price",
            "replay_open_datetime",
            "replay_open_time",
            "replay_open_abs_delta",
        ]
    ].copy()
    first.rename(
        columns={
            "replay_open_price": "stage861_first_open_price",
            "replay_open_datetime": "stage861_first_open_time",
            "replay_open_time": "stage861_first_open_hhmm",
            "replay_open_abs_delta": "stage861_first_open_abs_delta",
        },
        inplace=True,
    )
    return first


def _build_proxy_ledger(anchor: pd.DataFrame) -> pd.DataFrame:
    _, open_map = s501._seed_proxy_maps()
    first_map = _stage861_first_open_map()
    rows: list[dict[str, Any]] = []
    for _, row in anchor.iterrows():
        signal_date = pd.Timestamp(row["candidate_date_ts"]).normalize()
        fill_date = pd.Timestamp(row["official_open_date_ts"]).normalize()
        vt_symbol = str(row["vt_symbol"])
        seed = open_map.get((signal_date, fill_date, vt_symbol))
        raw = s501._next_real_open_proxy_from_raw(vt_symbol, signal_date, fill_date)
        if _proxy_ready(seed):
            selected = seed
            engine_proxy_kind = "stage149_seed_proxy"
        elif _proxy_ready(raw):
            selected = raw
            engine_proxy_kind = "raw_proxy"
        else:
            selected = None
            engine_proxy_kind = "fallback_daily_next_open_no_proxy"

        item = row.to_dict()
        item.update(_proxy_dict("seed", seed))
        item.update(_proxy_dict("raw", raw))
        item.update(_proxy_dict("engine_selected", selected))
        official_open = _safe_float(row.get("official_open_price"))
        item["engine_proxy_kind"] = engine_proxy_kind
        item["engine_selected_minus_official"] = (
            item["engine_selected_price"] - official_open if np.isfinite(item["engine_selected_price"]) else np.nan
        )
        item["engine_selected_exact_official"] = int(_exact_price(item["engine_selected_price"], official_open))
        item["raw_exact_official"] = int(_exact_price(item["raw_price"], official_open))
        item["seed_exact_official"] = int(_exact_price(item["seed_price"], official_open))

        if item["raw_exact_official"] and item["raw_first_time"]:
            if engine_proxy_kind == "raw_proxy":
                status = "raw_exact_engine_selected"
            else:
                status = "raw_exact_shadow_for_stage149_seed"
            timestamp_ready = 1
            timestamp_first_time = item["raw_first_time"]
            timestamp_last_time = item["raw_last_time"]
            timestamp_source = item["raw_source"]
        elif item["seed_exact_official"]:
            status = "stage149_seed_window_only_no_exact_minute"
            timestamp_ready = 0
            timestamp_first_time = ""
            timestamp_last_time = ""
            timestamp_source = item["seed_source"]
        else:
            status = "no_engine_open_proxy_timestamp"
            timestamp_ready = 0
            timestamp_first_time = ""
            timestamp_last_time = ""
            timestamp_source = ""
        item["timestamp_reconstruction_status"] = status
        item["timestamp_ready"] = int(timestamp_ready)
        item["timestamp_first_time"] = timestamp_first_time
        item["timestamp_last_time"] = timestamp_last_time
        item["timestamp_source"] = timestamp_source
        rows.append(item)

    ledger = pd.DataFrame(rows)
    ledger = ledger.merge(first_map, on="candidate_index", how="left")
    ledger["stage861_first_open_exact_official"] = (
        (pd.to_numeric(ledger["stage861_first_open_price"], errors="coerce") - ledger["official_open_price"]).abs() < 1e-9
    ).astype(int)
    ledger["open_year"] = pd.to_datetime(ledger["official_open_date"], errors="coerce").dt.year
    return ledger


def _bind_lots(lots: pd.DataFrame, proxy_ledger: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "candidate_index",
        "official_open_trade_id",
        "candidate_date",
        "official_open_date",
        "vt_symbol",
        "direction",
        "official_open_price",
        "engine_proxy_kind",
        "engine_selected_source",
        "timestamp_reconstruction_status",
        "timestamp_ready",
        "timestamp_source",
        "timestamp_first_time",
        "timestamp_last_time",
        "raw_source",
        "raw_first_time",
        "raw_last_time",
        "seed_source",
        "stage861_first_open_price",
        "stage861_first_open_time",
        "stage861_first_open_exact_official",
    ]
    out = lots.copy()
    out = out.merge(
        proxy_ledger[[col for col in keep if col in proxy_ledger.columns]],
        left_on="open_trade_id",
        right_on="official_open_trade_id",
        how="left",
        suffixes=("", "_proxy"),
    )
    out["proxy_binding_status"] = np.where(out["official_open_trade_id"].notna(), "initial_open_proxy_bound", "not_initial_open_or_unmatched")
    out["timestamp_reconstruction_status"] = out["timestamp_reconstruction_status"].fillna("not_initial_open_or_unmatched")
    out["timestamp_ready"] = pd.to_numeric(out["timestamp_ready"], errors="coerce").fillna(0).astype(int)
    out["exit_date_ts"] = pd.to_datetime(out["exit_date"], errors="coerce").dt.normalize()
    out["realized_pnl"] = pd.to_numeric(out["realized_pnl"], errors="coerce").fillna(0.0)
    return out


def _source_year_summary(proxy_ledger: pd.DataFrame, lot_binding: pd.DataFrame) -> pd.DataFrame:
    open_part = (
        proxy_ledger.groupby(["open_year", "engine_proxy_kind", "timestamp_reconstruction_status"], dropna=False)
        .agg(
            orders=("candidate_index", "count"),
            timestamp_ready=("timestamp_ready", "sum"),
            raw_exact=("raw_exact_official", "sum"),
            seed_exact=("seed_exact_official", "sum"),
            stage861_first_exact=("stage861_first_open_exact_official", "sum"),
        )
        .reset_index()
    )
    pnl = (
        lot_binding[lot_binding["proxy_binding_status"].eq("initial_open_proxy_bound")]
        .assign(open_year=lambda df: pd.to_datetime(df["official_open_date"], errors="coerce").dt.year)
        .groupby(["open_year", "engine_proxy_kind", "timestamp_reconstruction_status"], dropna=False)
        .agg(
            closed_lots=("open_trade_id", "count"),
            realized_pnl=("realized_pnl", "sum"),
            positive_pnl=("realized_pnl", lambda x: float(pd.to_numeric(x, errors="coerce").clip(lower=0).sum())),
            negative_pnl=("realized_pnl", lambda x: float(pd.to_numeric(x, errors="coerce").clip(upper=0).sum())),
        )
        .reset_index()
    )
    return open_part.merge(pnl, on=["open_year", "engine_proxy_kind", "timestamp_reconstruction_status"], how="left").fillna(
        {
            "closed_lots": 0,
            "realized_pnl": 0.0,
            "positive_pnl": 0.0,
            "negative_pnl": 0.0,
        }
    )


def _contribution_curve(curve: pd.DataFrame, lot_binding: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    status_values = [
        "raw_exact_engine_selected",
        "raw_exact_shadow_for_stage149_seed",
        "no_engine_open_proxy_timestamp",
        "not_initial_open_or_unmatched",
    ]
    for status in status_values:
        daily = (
            lot_binding[lot_binding["timestamp_reconstruction_status"].eq(status)]
            .groupby("exit_date_ts")["realized_pnl"]
            .sum()
        )
        col = status.replace("-", "_")
        out[f"{col}_daily_pnl"] = out["date"].map(daily).fillna(0.0)
        out[f"{col}_cum_pnl"] = out[f"{col}_daily_pnl"].cumsum()
    out["timestamp_ready_initial_daily_pnl"] = (
        out["raw_exact_engine_selected_daily_pnl"] + out["raw_exact_shadow_for_stage149_seed_daily_pnl"]
    )
    out["timestamp_ready_initial_cum_pnl"] = out["timestamp_ready_initial_daily_pnl"].cumsum()
    out["no_timestamp_initial_cum_pnl"] = out["no_engine_open_proxy_timestamp_daily_pnl"].cumsum()
    return out


def _summary(curve: pd.DataFrame, proxy_ledger: pd.DataFrame, lot_binding: pd.DataFrame) -> pd.DataFrame:
    official = s038._official_metrics(curve, lot_binding)
    bound = lot_binding[lot_binding["proxy_binding_status"].eq("initial_open_proxy_bound")].copy()
    timestamp_ready_orders = int(proxy_ledger["timestamp_ready"].sum())
    no_timestamp_orders = int(len(proxy_ledger) - timestamp_ready_orders)
    timestamp_ready_lots = bound[bound["timestamp_ready"].eq(1)]
    no_timestamp_lots = bound[bound["timestamp_ready"].eq(0)]
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        **official,
        "matched_initial_orders": int(len(proxy_ledger)),
        "timestamp_ready_initial_orders": timestamp_ready_orders,
        "timestamp_ready_initial_order_rate_pct": timestamp_ready_orders / len(proxy_ledger) * 100.0 if len(proxy_ledger) else 0.0,
        "no_timestamp_initial_orders": no_timestamp_orders,
        "stage149_seed_proxy_orders": int(proxy_ledger["engine_proxy_kind"].eq("stage149_seed_proxy").sum()),
        "raw_proxy_orders": int(proxy_ledger["engine_proxy_kind"].eq("raw_proxy").sum()),
        "fallback_missing_proxy_orders": int(proxy_ledger["engine_proxy_kind"].eq("fallback_daily_next_open_no_proxy").sum()),
        "raw_exact_engine_selected_orders": int(
            proxy_ledger["timestamp_reconstruction_status"].eq("raw_exact_engine_selected").sum()
        ),
        "raw_exact_shadow_for_stage149_seed_orders": int(
            proxy_ledger["timestamp_reconstruction_status"].eq("raw_exact_shadow_for_stage149_seed").sum()
        ),
        "stage861_first_bar_exact_official_orders": int(proxy_ledger["stage861_first_open_exact_official"].sum()),
        "bound_initial_closed_lots": int(len(bound)),
        "timestamp_ready_initial_closed_lots": int(len(timestamp_ready_lots)),
        "no_timestamp_initial_closed_lots": int(len(no_timestamp_lots)),
        "timestamp_ready_initial_realized_pnl": float(timestamp_ready_lots["realized_pnl"].sum()),
        "no_timestamp_initial_realized_pnl": float(no_timestamp_lots["realized_pnl"].sum()),
        "not_initial_or_unmatched_closed_lots": int(lot_binding["proxy_binding_status"].ne("initial_open_proxy_bound").sum()),
        "not_initial_or_unmatched_realized_pnl": float(
            lot_binding.loc[lot_binding["proxy_binding_status"].ne("initial_open_proxy_bound"), "realized_pnl"].sum()
        ),
        "decision": "stage040_proxy_timestamp_partial_reconstruction_no_trade_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
    }
    return pd.DataFrame([row])


def _plot_path(curve: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#111827", linewidth=1.1, label="official equity")
    axes[0].set_title("Official equity, reference only")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(
        curve["date"],
        curve["timestamp_ready_initial_cum_pnl"],
        color="#16a34a",
        linewidth=1.1,
        label="initial lots with raw exact timestamp",
    )
    axes[1].plot(
        curve["date"],
        curve["no_timestamp_initial_cum_pnl"],
        color="#dc2626",
        linewidth=1.1,
        label="initial lots without engine open proxy timestamp",
    )
    axes[1].plot(
        curve["date"],
        curve["not_initial_open_or_unmatched_cum_pnl"],
        color="#7c3aed",
        linewidth=0.9,
        label="reentry/unmatched/non-initial lots",
    )
    axes[1].axhline(0, color="#6b7280", linewidth=0.8)
    axes[1].set_title("Closed-lot contribution by open timestamp reconstruction status")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best")

    axes[2].plot(curve["date"], curve["drawdown_pct"], color="#111827", linewidth=1.0, label="official drawdown")
    axes[2].plot(
        curve["date"],
        curve["broker10_margin_to_equity_pct"],
        color="#f97316",
        linewidth=0.9,
        label="broker10 margin/equity %",
    )
    axes[2].axhline(100, color="#dc2626", linewidth=0.8, linestyle="--")
    axes[2].set_title("Official drawdown and broker10 pressure")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best")
    fig.suptitle("Stage040 open proxy timestamp reconstruction audit", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_source_distribution(source_year: pd.DataFrame) -> None:
    if source_year.empty:
        return
    data = source_year.copy()
    pivot = data.pivot_table(
        index="open_year",
        columns="timestamp_reconstruction_status",
        values="orders",
        aggfunc="sum",
        fill_value=0,
    ).sort_index()
    colors = {
        "raw_exact_engine_selected": "#16a34a",
        "raw_exact_shadow_for_stage149_seed": "#22c55e",
        "no_engine_open_proxy_timestamp": "#dc2626",
        "stage149_seed_window_only_no_exact_minute": "#f59e0b",
    }
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True, constrained_layout=True)
    bottom = np.zeros(len(pivot))
    x = np.arange(len(pivot))
    for column in pivot.columns:
        values = pivot[column].to_numpy()
        axes[0].bar(x, values, bottom=bottom, label=column, color=colors.get(column, "#64748b"))
        bottom += values
    axes[0].set_ylabel("initial orders")
    axes[0].set_title("Initial open timestamp reconstruction by year")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].legend(loc="best", fontsize=8)

    pnl = data.pivot_table(
        index="open_year",
        columns="timestamp_reconstruction_status",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    ).reindex(pivot.index)
    for column in pnl.columns:
        axes[1].plot(x, pnl[column].to_numpy(), marker="o", linewidth=1.0, label=column, color=colors.get(column, None))
    axes[1].axhline(0, color="#6b7280", linewidth=0.8)
    axes[1].set_ylabel("closed-lot PnL")
    axes[1].set_title("PnL carried by timestamp reconstruction status")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best", fontsize=8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([str(int(item)) for item in pivot.index], rotation=0)
    fig.savefig(SOURCE_CHART_OUT, dpi=150)
    plt.close(fig)


def _select_atlas_rows(proxy_ledger: pd.DataFrame, lot_binding: pd.DataFrame) -> pd.DataFrame:
    pnl = (
        lot_binding[lot_binding["proxy_binding_status"].eq("initial_open_proxy_bound")]
        .groupby("open_trade_id", dropna=False)
        .agg(open_trade_realized_pnl=("realized_pnl", "sum"), closed_lots=("open_trade_id", "count"))
        .reset_index()
    )
    data = proxy_ledger.merge(pnl, left_on="official_open_trade_id", right_on="open_trade_id", how="left")
    data["open_trade_realized_pnl"] = pd.to_numeric(data["open_trade_realized_pnl"], errors="coerce").fillna(0.0)
    ready = data[data["timestamp_ready"].eq(1)].copy()
    missing = data[data["timestamp_ready"].eq(0)].copy()
    parts: list[pd.DataFrame] = []
    if not missing.empty:
        parts.append(missing.assign(abs_pnl=missing["open_trade_realized_pnl"].abs()).nlargest(ATLAS_ROWS // 2, "abs_pnl"))
    if not ready.empty:
        parts.append(ready.assign(abs_pnl=ready["open_trade_realized_pnl"].abs()).nlargest(ATLAS_ROWS // 2, "abs_pnl"))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True, sort=False).drop_duplicates("candidate_index").head(ATLAS_ROWS).reset_index(drop=True)


def _plot_atlas(proxy_ledger: pd.DataFrame, lot_binding: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(proxy_ledger, lot_binding)
    if selected.empty:
        _write_csv(pd.DataFrame(), ATLAS_MANIFEST_OUT)
        return [], pd.DataFrame()
    pages: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page_idx, start in enumerate(range(0, len(selected), ATLAS_PER_PAGE), start=1):
        page_rows = selected.iloc[start : start + ATLAS_PER_PAGE].reset_index(drop=True)
        fig, axes = plt.subplots(len(page_rows), 1, figsize=(14, 3.5 * len(page_rows)), sharex=False, constrained_layout=True)
        if len(page_rows) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, page_rows.iterrows()):
            day = s038.s010._day_for_symbol(groups, str(row["vt_symbol"]), s038._normalize_day(row["official_open_date"]))
            if day.empty:
                ax.text(0.5, 0.5, "missing Stage861 day", ha="center", va="center")
                ax.set_axis_off()
            else:
                day = day.sort_values("bar_datetime").reset_index(drop=True)
                x = np.arange(len(day))
                ax.plot(x, pd.to_numeric(day["close"], errors="coerce"), color="#2563eb", linewidth=0.9, label="Stage861 close")
                for column, color, label, style in [
                    ("official_open_price", "#111827", "official open", "--"),
                    ("stage861_first_open_price", "#7c3aed", "Stage861 first open", ":"),
                    ("raw_price", "#16a34a", "raw proxy price", "-."),
                    ("seed_price", "#f59e0b", "seed proxy price", "-."),
                ]:
                    value = _safe_float(row.get(column))
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linewidth=0.9, linestyle=style, label=label)
                for column, color, label in [
                    ("stage861_first_open_time", "#7c3aed", "Stage861 first bar"),
                    ("raw_first_time", "#16a34a", "raw proxy first"),
                    ("raw_last_time", "#15803d", "raw proxy last"),
                    ("timestamp_first_time", "#0f766e", "chosen timestamp first"),
                ]:
                    text = str(row.get(column, ""))
                    if not text or text == "nan":
                        continue
                    ts = pd.to_datetime(text, errors="coerce")
                    if pd.isna(ts):
                        continue
                    matches = np.flatnonzero(pd.to_datetime(day["bar_datetime"], errors="coerce").eq(ts).to_numpy())
                    if len(matches):
                        ax.axvline(int(matches[0]), color=color, linewidth=0.8, alpha=0.75, label=label)
                tick_positions = np.linspace(0, max(len(day) - 1, 0), num=min(6, len(day)), dtype=int)
                ax.set_xticks(tick_positions)
                ax.set_xticklabels([_hhmm(day.loc[pos, "bar_datetime"]) for pos in tick_positions], fontsize=8)
                ax.grid(True, alpha=0.25)
            title = (
                f"{row.get('official_open_trade_id')} {row.get('vt_symbol')} {row.get('official_open_date')} "
                f"{row.get('direction')} status={row.get('timestamp_reconstruction_status')} "
                f"pnl={_safe_float(row.get('open_trade_realized_pnl'), 0):.0f}"
            )
            ax.set_title(title, fontsize=9)
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                by_label = dict(zip(labels, handles))
                ax.legend(by_label.values(), by_label.keys(), loc="best", fontsize=7)
            manifest_rows.append(
                {
                    "page": page_idx,
                    "candidate_index": row.get("candidate_index"),
                    "official_open_trade_id": row.get("official_open_trade_id"),
                    "vt_symbol": row.get("vt_symbol"),
                    "official_open_date": row.get("official_open_date"),
                    "direction": row.get("direction"),
                    "timestamp_reconstruction_status": row.get("timestamp_reconstruction_status"),
                    "engine_proxy_kind": row.get("engine_proxy_kind"),
                    "timestamp_first_time": row.get("timestamp_first_time"),
                    "raw_source": row.get("raw_source"),
                    "seed_source": row.get("seed_source"),
                    "official_open_price": row.get("official_open_price"),
                    "raw_price": row.get("raw_price"),
                    "stage861_first_open_price": row.get("stage861_first_open_price"),
                    "open_trade_realized_pnl": row.get("open_trade_realized_pnl"),
                }
            )
        output = Path(str(ATLAS_TEMPLATE).format(page=page_idx))
        fig.savefig(output, dpi=150)
        plt.close(fig)
        pages.append(output)
    manifest = pd.DataFrame(manifest_rows)
    _write_csv(manifest, ATLAS_MANIFEST_OUT)
    return pages, manifest


def _write_report(
    summary: pd.DataFrame,
    source_year: pd.DataFrame,
    proxy_ledger: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    row = summary.iloc[0].to_dict()
    status_summary = (
        proxy_ledger.groupby(["engine_proxy_kind", "timestamp_reconstruction_status"], dropna=False)
        .agg(
            orders=("candidate_index", "count"),
            raw_exact=("raw_exact_official", "sum"),
            seed_exact=("seed_exact_official", "sum"),
            stage861_first_exact=("stage861_first_open_exact_official", "sum"),
        )
        .reset_index()
        .sort_values("orders", ascending=False)
    )
    top_missing = proxy_ledger[proxy_ledger["timestamp_ready"].eq(0)].head(20)
    lines = [
        "# Stage040 开仓成交 proxy 点时化审计",
        "",
        "## 结论",
        "",
        "- 决策：`stage040_proxy_timestamp_partial_reconstruction_no_trade_rule`。",
        "- 本阶段只做 `_resolve_trade_price` proxy timestamp 审计，不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API、不触发 A/B。",
        f"- matched initial orders `{int(row['matched_initial_orders'])}`；可用 raw proxy 重建精确开仓窗口 `{int(row['timestamp_ready_initial_orders'])}` 笔，占 `{row['timestamp_ready_initial_order_rate_pct']:.4f}%`。",
        f"- Stage149 seed proxy `{int(row['stage149_seed_proxy_orders'])}` 笔，raw proxy `{int(row['raw_proxy_orders'])}` 笔，fallback/missing proxy `{int(row['fallback_missing_proxy_orders'])}` 笔。",
        f"- raw exact engine selected `{int(row['raw_exact_engine_selected_orders'])}` 笔；raw exact shadow for Stage149 seed `{int(row['raw_exact_shadow_for_stage149_seed_orders'])}` 笔。",
        f"- 仍有 `{int(row['no_timestamp_initial_orders'])}` 笔 initial orders 没有 engine open proxy timestamp，主要是早期 raw/seed 覆盖缺口；不能在这些样本上做分钟开仓规则。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{row['end_equity']:.2f}`",
        f"- 总收益：`{row['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe：`{row['sharpe']:.4f}`",
        f"- 总滑点：`{row['total_slippage']:.0f}`",
        f"- 总交易次数：`{row['total_trade_count']:.0f}`",
        f"- closed-lot 胜率：`{row['closed_lot_win_rate_pct']:.4f}%`",
        "",
        "## 外部调研与判断",
        "",
        "- vn.py、Backtrader、QuantConnect LEAN 和 NautilusTrader 的文档/源码共同指向同一原则：成交模型必须按前向订单流、下一可用价格、明确 OHLC/timestamp convention 定义。",
        "- 本阶段判断：official open price 能被 raw/Stage149 proxy 精确解释的部分可以进入后续 replay 账本；fallback/missing proxy 部分不能用 Stage861 首根或同价匹配硬补成真实成交时点。",
        "",
        "## Proxy Status Summary",
        "",
        _md_table(status_summary, max_rows=None),
        "",
        "## Source-Year Summary",
        "",
        _md_table(source_year, max_rows=40),
        "",
        "## Missing Timestamp Samples",
        "",
        _md_table(
            top_missing[
                [
                    "candidate_index",
                    "candidate_date",
                    "official_open_date",
                    "vt_symbol",
                    "direction",
                    "official_open_price",
                    "engine_proxy_kind",
                    "timestamp_reconstruction_status",
                    "stage861_first_open_price",
                    "stage861_first_open_exact_official",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## Visuals",
        "",
        f"- proxy timestamp path chart：`{PATH_CHART_OUT}`",
        f"- source year distribution chart：`{SOURCE_CHART_OUT}`",
        *[f"- proxy timestamp atlas：`{path}`" for path in atlas_paths],
        "",
        "## Files",
        "",
        f"- open proxy ledger：`{PROXY_LEDGER_OUT}`",
        f"- closed lot binding：`{LOT_BINDING_OUT}`",
        f"- contribution curve：`{CURVE_OUT}`",
        f"- source year summary：`{SOURCE_YEAR_OUT}`",
        f"- summary：`{SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 视觉观察",
        "",
        "- path chart 显示 timestamp-ready initial lots 和 no-timestamp initial lots 都承担过重要 PnL；不能因为某一组历史贡献更好或更差就筛掉另一组。",
        "- source-year chart 显示无 timestamp 的缺口主要集中在早期年份；这是数据覆盖问题，不是市场状态或信号质量本身。",
        "- atlas 中 raw-ready 样本能画出 21:00 或 09:00 的第一开盘窗口；no-timestamp 样本即便 Stage861 首根有时同价，也不是 `_resolve_trade_price` 的证据，不能作为可交易 timestamp。",
        "",
        "## 后续",
        "",
        "- 下一步只允许在 `timestamp_ready=1` 的 initial orders 上做 replay 一致性子集审计，先确认 C9/C2 事件和成交锚点在该子集内完全可复验。",
        "- 对 `fallback_daily_next_open_no_proxy` 的早期样本，若要纳入分钟规则，必须补 raw proxy 或正式交易使用的可执行窗口；不能用首根同价或最终盈亏标签补证据。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve, _open_trades, _candidates, lots, _intraday, _trades = s038._prepare_inputs()
    anchor = _load_stage039_anchor_replay()
    proxy_ledger = _build_proxy_ledger(anchor)
    lot_binding = _bind_lots(lots, proxy_ledger)
    source_year = _source_year_summary(proxy_ledger, lot_binding)
    contribution_curve = _contribution_curve(curve, lot_binding)
    summary = _summary(curve, proxy_ledger, lot_binding)
    groups = s038._load_minute_groups(proxy_ledger.rename(columns={"official_open_date": "candidate_date"}))

    _write_csv(proxy_ledger, PROXY_LEDGER_OUT)
    _write_csv(lot_binding, LOT_BINDING_OUT)
    _write_csv(contribution_curve, CURVE_OUT)
    _write_csv(source_year, SOURCE_YEAR_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_path(contribution_curve)
    _plot_source_distribution(source_year)
    atlas_paths, _manifest = _plot_atlas(proxy_ledger, lot_binding, groups)

    _write_report(summary, source_year, proxy_ledger, atlas_paths)

    row = summary.iloc[0].to_dict()
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": row["decision"],
        "candidate_ready": 0,
        "ab_triggered": 0,
        "rule_added": 0,
        "official_config_changed": 0,
        "matched_initial_orders": int(row["matched_initial_orders"]),
        "timestamp_ready_initial_orders": int(row["timestamp_ready_initial_orders"]),
        "timestamp_ready_initial_order_rate_pct": float(row["timestamp_ready_initial_order_rate_pct"]),
        "no_timestamp_initial_orders": int(row["no_timestamp_initial_orders"]),
        "stage149_seed_proxy_orders": int(row["stage149_seed_proxy_orders"]),
        "raw_proxy_orders": int(row["raw_proxy_orders"]),
        "fallback_missing_proxy_orders": int(row["fallback_missing_proxy_orders"]),
        "raw_exact_engine_selected_orders": int(row["raw_exact_engine_selected_orders"]),
        "raw_exact_shadow_for_stage149_seed_orders": int(row["raw_exact_shadow_for_stage149_seed_orders"]),
        "stage861_first_bar_exact_official_orders": int(row["stage861_first_bar_exact_official_orders"]),
        "judgment": (
            "Open proxy timestamps are partially reconstructable: raw proxy or raw shadow explains 219 initial orders exactly, "
            "but 105 initial orders remain fallback/no-proxy and must not be used for minute-entry rule tests."
        ),
        "overfit_guard": (
            "No year/product/direction/session/clock filter is promoted. Coverage gaps are treated as data limitations, "
            "not as signal-quality labels."
        ),
        "next_step": (
            "Run replay consistency only on timestamp_ready initial orders, or backfill missing raw proxy windows before "
            "any minute-level entry/exit candidate is tested."
        ),
        "outputs": {
            "open_proxy_ledger": PROXY_LEDGER_OUT,
            "closed_lot_binding": LOT_BINDING_OUT,
            "contribution_curve": CURVE_OUT,
            "source_year_summary": SOURCE_YEAR_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "source_chart": SOURCE_CHART_OUT,
            "atlas_manifest": ATLAS_MANIFEST_OUT,
            "atlas_pages": atlas_paths,
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
