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

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage835"
MODEL_TAG = "stage835_stage827_c2_event_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage835_stage827_c2_event_forensics"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")

STAGE825_FEATURES_PATH = OUTPUT_DIR / (
    "qmt_roll_stage825_stage819_intraday_rule_forensics_intraday_features_"
    "stage825_stage819_intraday_rule_forensics_v1.csv"
)
STAGE827_EVENTS_PATH = OUTPUT_DIR / (
    "qmt_roll_stage827_stage819_intraday_c2_engine_ac_intraday_events_"
    "stage827_stage819_intraday_c2_engine_ac_v1.csv"
)
STAGE827_CLOSED_PATH = OUTPUT_DIR / (
    "qmt_roll_stage827_stage819_intraday_c2_engine_ac_closed_lots_"
    "stage827_stage819_intraday_c2_engine_ac_v1.csv"
)
STAGE830_EVENTS_PATH = OUTPUT_DIR / (
    "qmt_roll_stage830_stage827_c2_broker10_margin_cap_intraday_events_"
    "stage830_stage827_c2_broker10_margin_cap_v1.csv"
)
STAGE830_CLOSED_PATH = OUTPUT_DIR / (
    "qmt_roll_stage830_stage827_c2_broker10_margin_cap_closed_lots_"
    "stage830_stage827_c2_broker10_margin_cap_v1.csv"
)

EVENT_MATCH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_match_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_stats_{MODEL_TAG}.csv"
YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_stats_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_delta_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
CHART_PATH_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

PER_PAGE = 4
MAX_ATLAS_PAGES = 10


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s825._safe_float(value, default=default)


def _event_date(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True).tz_convert("Asia/Shanghai").tz_localize(None).normalize()


def _naive_datetime(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    if getattr(ts, "tzinfo", None) is not None:
        ts = ts.tz_convert("Asia/Shanghai").tz_localize(None)
    return ts


def _date(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def _load_features() -> pd.DataFrame:
    if not STAGE825_FEATURES_PATH.exists():
        raise RuntimeError(f"Missing Stage825 features: {STAGE825_FEATURES_PATH}")
    features = pd.read_csv(STAGE825_FEATURES_PATH, encoding="utf-8-sig")
    for column in ("entry_date", "exit_date"):
        features[column] = pd.to_datetime(features[column], errors="coerce").dt.tz_localize(None).dt.normalize()
    for column in (
        "entry_price",
        "exit_price",
        "volume",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "entry_day_mfe_r",
        "entry_day_mae_r",
        "mfe_30m_r",
        "mae_30m_r",
        "mfe_60m_r",
        "mae_60m_r",
        "mfe_120m_r",
        "mae_120m_r",
    ):
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")
    features["entry_price_key"] = pd.to_numeric(features["entry_price"], errors="coerce").round(6)
    return features


def _load_closed(path: Path, arm_contains: str) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing closed lots: {path}")
    closed = pd.read_csv(path, encoding="utf-8-sig")
    closed = closed[closed["arm"].astype(str).str.contains(arm_contains, na=False)].copy()
    for column in ("entry_date", "exit_date"):
        closed[column] = pd.to_datetime(closed[column], errors="coerce").dt.tz_localize(None).dt.normalize()
    for column in ("entry_price", "exit_price", "volume", "realized_pnl", "risk_amount", "r_multiple"):
        if column in closed.columns:
            closed[column] = pd.to_numeric(closed[column], errors="coerce")
    return closed


def _load_events(path: Path, source: str) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing intraday events: {path}")
    events = pd.read_csv(path, encoding="utf-8-sig")
    events["source_arm"] = source
    events["entry_date"] = events["datetime"].map(_event_date)
    events["hit_dt"] = pd.to_datetime(events["hit_time"], errors="coerce")
    events["entry_price"] = pd.to_numeric(events["entry_price"], errors="coerce")
    events["stop_price"] = pd.to_numeric(events["stop_price"], errors="coerce")
    events["confirm_price"] = pd.to_numeric(events["confirm_price"], errors="coerce")
    events["risk_price"] = pd.to_numeric(events["risk_price"], errors="coerce")
    events["event_volume"] = pd.to_numeric(events["volume"], errors="coerce")
    events["entry_price_key"] = events["entry_price"].round(6)
    return events


def _baseline_aggregate(features: pd.DataFrame) -> pd.DataFrame:
    keys = ["vt_symbol", "direction", "entry_date", "entry_price_key"]
    agg_spec: dict[str, Any] = {
        "lot_id": lambda x: ",".join(str(int(v)) for v in x.dropna().astype(float)),
        "realized_pnl": "sum",
        "volume": "sum",
        "risk_amount": "sum",
        "r_multiple": "mean",
        "exit_date": "max",
        "exit_price": "mean",
        "entry_day_mfe_r": "mean",
        "entry_day_mae_r": "mean",
        "mfe_30m_r": "mean",
        "mae_30m_r": "mean",
        "mfe_60m_r": "mean",
        "mae_60m_r": "mean",
        "mfe_120m_r": "mean",
        "mae_120m_r": "mean",
        "entry_day_first_0p5r_outcome": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "entry_day_first_1p0r_outcome": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "entry_day_first_2p0r_outcome": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "signal": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "exit_reason": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "minute_coverage_state": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
    }
    available = {key: value for key, value in agg_spec.items() if key in features.columns}
    result = features.groupby(keys, dropna=False).agg(available).reset_index()
    result.rename(
        columns={
            "lot_id": "baseline_lot_ids",
            "realized_pnl": "baseline_realized_pnl",
            "volume": "baseline_volume",
            "risk_amount": "baseline_risk_amount",
            "r_multiple": "baseline_avg_r_multiple",
            "exit_date": "baseline_exit_date",
            "exit_price": "baseline_exit_price",
        },
        inplace=True,
    )
    result["baseline_match_count"] = result["baseline_lot_ids"].astype(str).map(
        lambda value: 0 if value in {"", "nan"} else len(value.split(","))
    )
    return result


def _matched_events(
    *,
    events: pd.DataFrame,
    closed: pd.DataFrame,
    baseline: pd.DataFrame,
) -> pd.DataFrame:
    closed_cols = [
        "open_trade_id",
        "lot_id",
        "realized_pnl",
        "r_multiple",
        "risk_amount",
        "exit_reason",
        "exit_date",
        "exit_price",
        "volume",
        "arm",
    ]
    closed_part = closed[[column for column in closed_cols if column in closed.columns]].copy()
    closed_part.rename(
        columns={
            "lot_id": "c_lot_id",
            "realized_pnl": "c_stop_realized_pnl",
            "r_multiple": "c_stop_r_multiple",
            "risk_amount": "c_stop_risk_amount",
            "exit_reason": "c_stop_exit_reason",
            "exit_date": "c_stop_exit_date",
            "exit_price": "c_stop_exit_price",
            "volume": "c_stop_volume",
            "arm": "c_arm",
        },
        inplace=True,
    )
    merged = events.merge(
        closed_part,
        left_on="trade_id",
        right_on="open_trade_id",
        how="left",
        indicator="closed_merge",
    )
    keys = ["vt_symbol", "direction", "entry_date", "entry_price_key"]
    merged = merged.merge(baseline, on=keys, how="left", indicator="baseline_merge")
    merged["entry_year"] = merged["entry_date"].dt.year.astype("Int64")
    merged["baseline_match_found"] = merged["baseline_merge"].eq("both").astype(int)
    merged["closed_match_found"] = merged["closed_merge"].eq("both").astype(int)
    merged["event_minus_baseline_pnl"] = pd.to_numeric(merged["c_stop_realized_pnl"], errors="coerce") - pd.to_numeric(
        merged["baseline_realized_pnl"], errors="coerce"
    )
    merged["event_minus_baseline_r"] = pd.to_numeric(merged["c_stop_r_multiple"], errors="coerce") - pd.to_numeric(
        merged["baseline_avg_r_multiple"], errors="coerce"
    )
    merged["stop_hour"] = pd.to_datetime(merged["hit_time"], errors="coerce").dt.hour
    merged["hit_minutes_from_midnight"] = (
        pd.to_datetime(merged["hit_time"], errors="coerce").dt.hour * 60
        + pd.to_datetime(merged["hit_time"], errors="coerce").dt.minute
    )
    merged["hit_session_bucket"] = np.select(
        [
            merged["hit_minutes_from_midnight"].between(9 * 60, 10 * 60 + 15, inclusive="both"),
            merged["hit_minutes_from_midnight"].between(10 * 60 + 16, 11 * 60 + 30, inclusive="both"),
            merged["hit_minutes_from_midnight"].between(13 * 60, 15 * 60 + 15, inclusive="both"),
            merged["hit_minutes_from_midnight"].between(21 * 60, 23 * 60 + 59, inclusive="both"),
        ],
        ["morning_early", "morning_late", "afternoon", "night"],
        default="other",
    )
    return merged


def _summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source, group in frame.groupby("source_arm", sort=False):
        matched = group[group["baseline_match_found"].eq(1)]
        positive = matched[matched["event_minus_baseline_pnl"].gt(0)]
        negative = matched[matched["event_minus_baseline_pnl"].lt(0)]
        rows.append(
            {
                "source_arm": source,
                "events": int(len(group)),
                "closed_match": int(group["closed_match_found"].sum()),
                "baseline_match": int(group["baseline_match_found"].sum()),
                "event_stop_pnl_sum": float(pd.to_numeric(group["c_stop_realized_pnl"], errors="coerce").sum()),
                "matched_baseline_pnl_sum": float(pd.to_numeric(matched["baseline_realized_pnl"], errors="coerce").sum()),
                "event_minus_baseline_pnl_sum": float(pd.to_numeric(matched["event_minus_baseline_pnl"], errors="coerce").sum()),
                "event_minus_baseline_pnl_median": float(pd.to_numeric(matched["event_minus_baseline_pnl"], errors="coerce").median()),
                "positive_direct_events": int(len(positive)),
                "negative_direct_events": int(len(negative)),
                "positive_direct_pnl": float(positive["event_minus_baseline_pnl"].sum()),
                "negative_direct_pnl": float(negative["event_minus_baseline_pnl"].sum()),
                "avg_entry_day_mfe_r": float(pd.to_numeric(matched["entry_day_mfe_r"], errors="coerce").mean()),
                "avg_entry_day_mae_r": float(pd.to_numeric(matched["entry_day_mae_r"], errors="coerce").mean()),
                "decision": "diagnostic_only_not_promoted",
            }
        )
    return pd.DataFrame(rows)


def _bucket_stats(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    bucket_columns = [
        "source_arm",
        "entry_year",
        "direction",
        "signal",
        "entry_day_first_1p0r_outcome",
        "hit_session_bucket",
        "product_vt_symbol",
        "c_stop_exit_reason",
    ]
    data = frame[frame["baseline_match_found"].eq(1)].copy()
    for column in bucket_columns:
        if column not in data.columns:
            continue
        for value, group in data.groupby(column, dropna=False):
            if column not in {"source_arm", "entry_year"} and len(group) < 3:
                continue
            rows.append(
                {
                    "bucket": column,
                    "value": str(value),
                    "events": int(len(group)),
                    "event_stop_pnl": float(pd.to_numeric(group["c_stop_realized_pnl"], errors="coerce").sum()),
                    "baseline_pnl": float(pd.to_numeric(group["baseline_realized_pnl"], errors="coerce").sum()),
                    "event_minus_baseline_pnl": float(pd.to_numeric(group["event_minus_baseline_pnl"], errors="coerce").sum()),
                    "positive_direct_events": int(pd.to_numeric(group["event_minus_baseline_pnl"], errors="coerce").gt(0).sum()),
                    "negative_direct_events": int(pd.to_numeric(group["event_minus_baseline_pnl"], errors="coerce").lt(0).sum()),
                    "median_event_minus_baseline_r": float(pd.to_numeric(group["event_minus_baseline_r"], errors="coerce").median()),
                    "avg_entry_day_mfe_r": float(pd.to_numeric(group["entry_day_mfe_r"], errors="coerce").mean()),
                    "avg_entry_day_mae_r": float(pd.to_numeric(group["entry_day_mae_r"], errors="coerce").mean()),
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["bucket", "event_minus_baseline_pnl"], ascending=[True, False], inplace=True)
    return result


def _yearly_stats(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    data = frame[frame["baseline_match_found"].eq(1)].copy()
    for (source, year), group in data.groupby(["source_arm", "entry_year"], dropna=False):
        rows.append(
            {
                "source_arm": source,
                "entry_year": int(year) if not pd.isna(year) else 0,
                "events": int(len(group)),
                "event_stop_pnl": float(group["c_stop_realized_pnl"].sum()),
                "baseline_pnl": float(group["baseline_realized_pnl"].sum()),
                "event_minus_baseline_pnl": float(group["event_minus_baseline_pnl"].sum()),
                "positive_direct_events": int(group["event_minus_baseline_pnl"].gt(0).sum()),
                "negative_direct_events": int(group["event_minus_baseline_pnl"].lt(0).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["source_arm", "entry_year"]).reset_index(drop=True)


def _load_minute_bars(features: pd.DataFrame) -> pd.DataFrame:
    vt_symbols = set(features["vt_symbol"].astype(str).dropna().unique())
    return s825._load_minute_bars(vt_symbols)


def _plot_event_chart(summary: pd.DataFrame, yearly: pd.DataFrame) -> None:
    if summary.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(16, 5), constrained_layout=True)
    x = np.arange(len(summary))
    axes[0].bar(x, summary["event_minus_baseline_pnl_sum"], color=["#2563eb", "#7c3aed"][: len(summary)])
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(summary["source_arm"], rotation=12)
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("C2 Stop Event PnL vs Matched Baseline")
    axes[0].grid(True, axis="y", alpha=0.2)
    if not yearly.empty:
        pivot = yearly.pivot_table(index="entry_year", columns="source_arm", values="event_minus_baseline_pnl", aggfunc="sum").fillna(0.0)
        pivot.plot(kind="bar", ax=axes[1], color=["#2563eb", "#7c3aed"])
        axes[1].axhline(0, color="#111827", linewidth=0.8)
        axes[1].set_title("Event Direct Delta By Entry Year")
        axes[1].grid(True, axis="y", alpha=0.2)
    fig.suptitle("Stage835 C2 stop event forensic diagnostic; direct event attribution only", fontsize=13)
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_atlas(frame: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    data = frame[frame["source_arm"].eq("C2_engine") & frame["baseline_match_found"].eq(1)].copy()
    if data.empty:
        return [], pd.DataFrame()
    data["abs_event_delta"] = pd.to_numeric(data["event_minus_baseline_pnl"], errors="coerce").abs()
    data.sort_values("abs_event_delta", ascending=False, inplace=True)
    data = data.head(PER_PAGE * MAX_ATLAS_PAGES)
    minute_by_symbol = s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(data) / PER_PAGE)) if len(data) else 0
    paths: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = data.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.2 * len(part))), constrained_layout=True)
        if len(part) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, part.iterrows(), strict=False):
            lot_ids = str(row.get("baseline_lot_ids", ""))
            vt_symbol = str(row["vt_symbol"])
            direction = str(row["direction"])
            entry_date = _date(row["entry_date"])
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            entry_day = bars[bars["bar_date"].eq(entry_date)].copy().head(240).reset_index(drop=True)
            if entry_day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minutes {vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
                continue
            s825._plot_candles(ax, entry_day)
            entry_price = _safe_float(row.get("entry_price"))
            stop_price = _safe_float(row.get("stop_price"))
            confirm_price = _safe_float(row.get("confirm_price"))
            ax.axhline(entry_price, color="#2563eb", linewidth=0.9, alpha=0.85)
            ax.axhline(stop_price, color="#dc2626", linewidth=0.9, alpha=0.85)
            ax.axhline(confirm_price, color="#16a34a", linewidth=0.9, alpha=0.85)
            hit_dt = pd.to_datetime(row.get("hit_time"), errors="coerce")
            if not pd.isna(hit_dt):
                matches = entry_day.index[entry_day["bar_datetime"].eq(hit_dt)]
                if len(matches):
                    x = int(matches[0])
                    ax.scatter([x], [stop_price], c="#dc2626", s=40, marker="x", zorder=6)
                    ax.text(x, stop_price, "C2 stop", fontsize=7, color="#dc2626")
            ticks = np.linspace(0, len(entry_day) - 1, num=min(7, len(entry_day)), dtype=int)
            ax.set_xticks(ticks)
            ax.set_xticklabels([pd.Timestamp(entry_day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
            ax.grid(True, alpha=0.18, linewidth=0.5)
            ax.tick_params(axis="y", labelsize=7)
            ax.set_title(
                (
                    f"lot{lot_ids} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
                    f"event={row['c_stop_realized_pnl']:,.0f} baseline={row['baseline_realized_pnl']:,.0f} "
                    f"delta={row['event_minus_baseline_pnl']:,.0f} "
                    f"MFE={_safe_float(row.get('entry_day_mfe_r')):.2f}R MAE={_safe_float(row.get('entry_day_mae_r')):.2f}R"
                ),
                fontsize=8.5,
                loc="left",
            )
            manifest_rows.append(
                {
                    "chart_page": page,
                    "trade_id": str(row.get("trade_id", "")),
                    "baseline_lot_ids": lot_ids,
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_date.strftime("%Y-%m-%d"),
                    "event_minus_baseline_pnl": _safe_float(row.get("event_minus_baseline_pnl")),
                }
            )
        fig.suptitle(
            "Stage835 C2 stop event atlas (blue=entry, red=1R stop, green=1R confirm)",
            fontsize=13,
        )
        path = Path(str(CHART_PATH_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest_rows)


def _write_report(
    summary: pd.DataFrame,
    bucket: pd.DataFrame,
    yearly: pd.DataFrame,
    chart_paths: list[Path],
) -> None:
    lines = [
        "# Stage835 C2/C4日内止损事件级法证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        f"- 区间：`{START.date()}` 到 `{END.date()}`",
        "- 阶段性质：只读事件级归因和K线图谱；不改正式策略、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- MAE/MFE 方法的核心是分开看赢家和输家：立即失败、先走顺后反转、从未给过顺向机会是不同问题。",
        "- NinjaTrader 风险管理文章强调 MAE 可帮助为具体 setup 设定止损，避免过早打掉正常波动，也要防止灾难亏损。",
        "- 本阶段不设计新参数，只确认 C2 真实触发事件到底是直接正贡献、直接负贡献，还是混合样本。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=10),
        "",
        "## Yearly Stats",
        "",
        _md_table(yearly, max_rows=50),
        "",
        "## Bucket Stats",
        "",
        _md_table(bucket.head(80), max_rows=80),
        "",
        "## Charts",
        "",
        f"- event delta chart：`{CHART_PATH}`",
        *[f"- atlas：`{path}`" for path in chart_paths],
        "",
        "## Judgment",
        "",
        "- 本阶段只回答事件层问题，不证明完整组合可晋级。",
        "- 若直接事件大多为正，但完整 C2/C4 尾部仍失败，则下一步应研究释放资金再使用纪律，而不是继续修改 C2 止损倍数。",
        "- 若直接事件内部也高度混合，则应先找可见分界，否则不应进入真实引擎。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    baseline = _baseline_aggregate(features)
    c2_events = _load_events(STAGE827_EVENTS_PATH, "C2_engine")
    c4_events = _load_events(STAGE830_EVENTS_PATH, "C4_broker10_cap")
    c2_closed = _load_closed(STAGE827_CLOSED_PATH, "c2_engine")
    c4_closed = _load_closed(STAGE830_CLOSED_PATH, "c2_broker10_100_cap")
    c2_matched = _matched_events(events=c2_events, closed=c2_closed, baseline=baseline)
    c4_matched = _matched_events(events=c4_events, closed=c4_closed, baseline=baseline)
    event_match = pd.concat([c2_matched, c4_matched], ignore_index=True, sort=False)
    summary = _summary(event_match)
    bucket = _bucket_stats(event_match)
    yearly = _yearly_stats(event_match)
    _plot_event_chart(summary, yearly)
    minute_bars = _load_minute_bars(features)
    chart_paths, atlas_manifest = _plot_atlas(event_match, minute_bars)
    _write_report(summary, bucket, yearly, chart_paths)

    event_match.to_csv(EVENT_MATCH_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    bucket.to_csv(BUCKET_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    direct_positive = bool(
        not summary.empty and (pd.to_numeric(summary["event_minus_baseline_pnl_sum"], errors="coerce") > 0).all()
    )
    decision_label = (
        "stage835_c2_direct_events_positive_but_path_risk_unresolved"
        if direct_positive
        else "stage835_c2_direct_events_mixed_no_new_rule"
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "decision": decision_label,
        "summary": summary.to_dict("records"),
        "overfit_reflection": (
            "Stage835 is read-only attribution using already frozen C2/C4 events. It does not tune R, products, "
            "years, or time windows. Turning these buckets into filters without a frozen follow-up would overfit."
        ),
        "continue_value": (
            "Continue only if this separates direct stop value from second-order capital reuse risk; next step should "
            "address reuse discipline rather than C2 stop threshold scanning."
        ),
        "outputs": {
            "event_match": str(EVENT_MATCH_PATH),
            "summary": str(SUMMARY_PATH),
            "bucket_stats": str(BUCKET_PATH),
            "yearly_stats": str(YEARLY_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in chart_paths],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("summary")
    print(summary.to_string(index=False))
    print("yearly")
    print(yearly.to_string(index=False))
    print("top buckets")
    print(bucket.head(40).to_string(index=False))


if __name__ == "__main__":
    main()
