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
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage880"
MODEL_TAG = "stage880_stage863_session_boundary_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage880_stage863_session_boundary_audit"

STAGE861_PREFIX = "qmt_roll_stage861_stage860_full_visual_atlas"
STAGE861_TAG = "stage861_stage860_full_visual_atlas_v1"
STAGE863_PREFIX = "qmt_roll_stage863_stage847_c10_budget_lock_engine"
STAGE863_TAG = "stage863_stage847_c10_budget_lock_engine_v1"

FULL_MINUTE_BARS_PATH = OUTPUT_DIR / f"{STAGE861_PREFIX}_full_minute_bars_{STAGE861_TAG}.csv"
STAGE863_CLOSED_LOTS_PATH = OUTPUT_DIR / f"{STAGE863_PREFIX}_closed_lots_{STAGE863_TAG}.csv"
STAGE863_STOP_RETRY_EVENTS_PATH = OUTPUT_DIR / f"{STAGE863_PREFIX}_stop_retry_events_{STAGE863_TAG}.csv"

FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
SESSION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_session_summary_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

C9_ARM = s847.C9_ARM
PER_PAGE = 4
MAX_ATLAS_ROWS = 16


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normalize_date(value: Any) -> pd.Timestamp:
    return pd.to_datetime(str(value)[:10], errors="coerce").normalize()


def _session_label(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return "none"
    minute = int(ts.hour) * 60 + int(ts.minute)
    if 0 <= minute <= 2 * 60 + 45:
        return "pre_day_night"
    if 9 * 60 <= minute <= 15 * 60 + 15:
        return "day_session"
    if 21 * 60 <= minute <= 23 * 60 + 59:
        return "post_day_night"
    return "break_or_other"


def _prepare_events() -> pd.DataFrame:
    data = _load_required_csv(STAGE863_STOP_RETRY_EVENTS_PATH).copy()
    data = data[data["profile"].astype(str).eq(C9_ARM)].copy()
    if data.empty:
        raise RuntimeError(f"no C9 stop/retry events in {STAGE863_STOP_RETRY_EVENTS_PATH}")
    data["event_date"] = data["datetime"].map(_normalize_date)
    for column in ["first_stop_time", "reentry_time", "retry_failed_time"]:
        data[f"{column}_ts"] = pd.to_datetime(data.get(column), errors="coerce")
        data[column.replace("_time", "_session")] = data.get(column, "").map(_session_label)
    data["retry_reentered"] = pd.to_numeric(data.get("retry_reentered"), errors="coerce").fillna(0).astype(int)
    data["retry_failed"] = pd.to_numeric(data.get("retry_failed"), errors="coerce").fillna(0).astype(int)
    for column in ["entry_price", "stop_price", "progress_price", "risk_price", "stop_r", "volume"]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    data["event_key"] = (
        data["vt_symbol"].astype(str)
        + "|"
        + data["direction"].astype(str)
        + "|"
        + data["event_date"].dt.strftime("%Y-%m-%d")
    )
    data["session_pattern"] = (
        data["first_stop_session"].astype(str)
        + "->"
        + data["reentry_session"].astype(str)
        + "->"
        + data["retry_failed_session"].astype(str)
    )
    data["cross_session_reentry"] = (
        data["retry_reentered"].eq(1)
        & data["first_stop_session"].ne("none")
        & data["reentry_session"].ne("none")
        & data["first_stop_session"].ne(data["reentry_session"])
    ).astype(int)
    data["day_to_post_night_reentry"] = (
        data["retry_reentered"].eq(1)
        & data["first_stop_session"].eq("day_session")
        & data["reentry_session"].eq("post_day_night")
    ).astype(int)
    return data.reset_index(drop=True)


def _prepare_closed_lots() -> pd.DataFrame:
    data = _load_required_csv(STAGE863_CLOSED_LOTS_PATH).copy()
    data = data[data["arm"].astype(str).eq(C9_ARM)].copy()
    if data.empty:
        raise RuntimeError(f"no C9 closed lots in {STAGE863_CLOSED_LOTS_PATH}")
    data["entry_date_norm"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    for column in ["lot_id", "realized_pnl", "r_multiple", "winner", "big_winner", "size", "volume"]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    data["event_key"] = (
        data["vt_symbol"].astype(str)
        + "|"
        + data["direction"].astype(str)
        + "|"
        + data["entry_date_norm"].dt.strftime("%Y-%m-%d")
    )
    return data.reset_index(drop=True)


def _build_event_features(events: pd.DataFrame, closed_lots: pd.DataFrame) -> pd.DataFrame:
    lot_agg = (
        closed_lots.groupby("event_key", dropna=False)
        .agg(
            matched_lots=("lot_id", "count"),
            matched_pnl=("realized_pnl", "sum"),
            matched_winner=("winner", "max"),
            matched_big_winner=("big_winner", "max"),
            size_first=("size", "first"),
            matched_volume=("volume", "sum"),
            matched_min_r=("r_multiple", "min"),
            matched_max_r=("r_multiple", "max"),
        )
        .reset_index()
    )
    data = events.merge(lot_agg, on="event_key", how="left")
    data["matched_lots"] = pd.to_numeric(data.get("matched_lots"), errors="coerce").fillna(0).astype(int)
    for column in [
        "matched_pnl",
        "matched_winner",
        "matched_big_winner",
        "size_first",
        "matched_volume",
        "matched_min_r",
        "matched_max_r",
    ]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    data["event_year"] = data["event_date"].dt.year
    data["initial_stop_loss_cash"] = -(
        pd.to_numeric(data["stop_r"], errors="coerce")
        * pd.to_numeric(data["risk_price"], errors="coerce")
        * pd.to_numeric(data["size_first"], errors="coerce")
        * pd.to_numeric(data["volume"], errors="coerce")
    )
    data["reentry_leg_pnl_proxy"] = np.where(
        data["retry_reentered"].eq(1),
        pd.to_numeric(data["matched_pnl"], errors="coerce") - data["initial_stop_loss_cash"],
        0.0,
    )
    data["same_session_only_proxy_delta"] = np.where(
        data["cross_session_reentry"].eq(1),
        -data["reentry_leg_pnl_proxy"],
        0.0,
    )
    data["same_session_only_proxy_total_pnl"] = data["matched_pnl"] + data["same_session_only_proxy_delta"]
    data["same_session_only_proxy_decision"] = np.where(
        data["cross_session_reentry"].eq(1),
        "affected_cross_session_reentry",
        "not_affected",
    )
    return data.reset_index(drop=True)


def _session_summary(features: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        features.groupby(["final_state", "first_stop_session", "reentry_session", "retry_failed_session"], dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            products=("product_vt_symbol", "nunique"),
            volume=("volume", "sum"),
            matched_lots=("matched_lots", "sum"),
            matched_pnl=("matched_pnl", "sum"),
            matched_winners=("matched_winner", "sum"),
            matched_big_winners=("matched_big_winner", "sum"),
            cross_session_reentries=("cross_session_reentry", "sum"),
            same_session_only_proxy_delta=("same_session_only_proxy_delta", "sum"),
            median_first_stop_bar=("first_stop_bar_index", "median"),
            median_reentry_bar=("reentry_bar_index", "median"),
        )
        .reset_index()
    )
    grouped["win_rate_pct"] = np.where(
        grouped["events"].gt(0),
        grouped["matched_winners"] / grouped["events"] * 100.0,
        0.0,
    )
    return grouped.sort_values(["events", "matched_pnl"], ascending=[False, False]).reset_index(drop=True)


def _proxy_summary(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    affected = features["cross_session_reentry"].eq(1)
    delta = pd.to_numeric(features["same_session_only_proxy_delta"], errors="coerce").fillna(0.0)
    matched_pnl = pd.to_numeric(features["matched_pnl"], errors="coerce").fillna(0.0)
    winners = affected & features["reentry_leg_pnl_proxy"].gt(0)
    losers = affected & features["reentry_leg_pnl_proxy"].lt(0)
    big = affected & pd.to_numeric(features["matched_big_winner"], errors="coerce").fillna(0).gt(0)
    yearly = (
        pd.DataFrame(
            {
                "event_year": features["event_year"],
                "affected": affected.astype(int),
                "matched_pnl": matched_pnl,
                "gross_proxy_delta": delta,
                "winner_cut": np.where(winners, delta, 0.0),
                "loser_saved": np.where(losers, delta, 0.0),
                "big_winner_cut": np.where(big, delta, 0.0),
            }
        )
        .groupby("event_year", dropna=False)
        .agg(
            affected_events=("affected", "sum"),
            matched_pnl=("matched_pnl", "sum"),
            gross_proxy_delta=("gross_proxy_delta", "sum"),
            winner_cut=("winner_cut", "sum"),
            loser_saved=("loser_saved", "sum"),
            big_winner_cut=("big_winner_cut", "sum"),
        )
        .reset_index()
    )
    rows = [
        {
            "proxy_id": "P1_same_session_only_retry",
            "rule_text": "Proxy: after a C9 0.5R first stop, allow retry only inside the same broad continuous session; block day-session stop -> post-day-night reclaim.",
            "all_events": int(len(features)),
            "affected_events": int(affected.sum()),
            "affected_event_pct": float(affected.mean() * 100.0) if len(features) else 0.0,
            "affected_original_pnl": float(matched_pnl.loc[affected].sum()),
            "gross_proxy_delta": float(delta.sum()),
            "proxy_total_pnl": float(matched_pnl.sum() + delta.sum()),
            "winner_cut": float(delta.loc[winners].sum()),
            "loser_saved": float(delta.loc[losers].sum()),
            "big_winner_cut": float(delta.loc[big].sum()),
            "affected_big_winner_events": int(big.sum()),
            "positive_delta_years": int(yearly["gross_proxy_delta"].gt(0).sum()),
            "negative_delta_years": int(yearly["gross_proxy_delta"].lt(0).sum()),
            "worst_year_delta": float(yearly["gross_proxy_delta"].min()) if not yearly.empty else 0.0,
            "best_year_delta": float(yearly["gross_proxy_delta"].max()) if not yearly.empty else 0.0,
            "decision": "proxy_only_not_promoted",
        }
    ]
    return pd.DataFrame(rows), yearly


def _plot_summary_chart(session_summary: pd.DataFrame, proxy_summary: pd.DataFrame) -> None:
    top = session_summary.copy().head(12)
    top["pattern"] = (
        top["first_stop_session"].astype(str)
        + " / "
        + top["reentry_session"].astype(str)
        + " / "
        + top["retry_failed_session"].astype(str)
        + " / "
        + top["final_state"].astype(str)
    )
    fig, axes = plt.subplots(1, 2, figsize=(18, 5.5), constrained_layout=True)
    colors = np.where(top["matched_pnl"].ge(0), "#16a34a", "#dc2626")
    axes[0].bar(top["pattern"], top["matched_pnl"], color=colors)
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("C9 stop/retry event PnL by session pattern")
    axes[0].tick_params(axis="x", rotation=35, labelsize=7)
    axes[0].grid(axis="y", alpha=0.2)

    axes[1].bar(proxy_summary["proxy_id"], proxy_summary["gross_proxy_delta"], color="#7c3aed")
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Proxy delta: same-session-only retry")
    axes[1].tick_params(axis="x", rotation=15, labelsize=8)
    axes[1].grid(axis="y", alpha=0.2)
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _load_minute_bars(vt_symbols: set[str]) -> pd.DataFrame:
    data = _load_required_csv(FULL_MINUTE_BARS_PATH)
    data = data[data["vt_symbol"].astype(str).isin(vt_symbols)].copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close"]).reset_index(
        drop=True
    )


def _select_atlas_events(features: pd.DataFrame) -> pd.DataFrame:
    selected: list[pd.DataFrame] = []
    cross = features[features["cross_session_reentry"].eq(1)].copy()
    if not cross.empty:
        selected.append(cross.sort_values("matched_pnl").head(4))
        selected.append(cross.sort_values("matched_pnl", ascending=False).head(4))
    post_retry_fail = features[
        features["reentry_session"].eq("day_session")
        & features["retry_failed_session"].eq("post_day_night")
    ].copy()
    if not post_retry_fail.empty:
        selected.append(post_retry_fail.sort_values("matched_pnl").head(4))
    same_session_open = features[
        features["reentry_session"].eq("day_session")
        & features["final_state"].eq("open_after_reentry")
    ].copy()
    if not same_session_open.empty:
        selected.append(same_session_open.sort_values("matched_pnl", ascending=False).head(4))
    if not selected:
        return pd.DataFrame()
    return (
        pd.concat(selected, ignore_index=True, sort=False)
        .drop_duplicates(["vt_symbol", "direction", "event_date", "final_state"])
        .head(MAX_ATLAS_ROWS)
        .reset_index(drop=True)
    )


def _index_for_time(day: pd.DataFrame, value: Any) -> int:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts) or day.empty:
        return -1
    matched = day.index[day["bar_datetime"].eq(ts)]
    if len(matched):
        return int(matched[0])
    diffs = (day["bar_datetime"] - ts).abs()
    if diffs.empty:
        return -1
    pos = int(diffs.idxmin())
    return pos if diffs.loc[pos] <= pd.Timedelta(minutes=1) else -1


def _shade_sessions(ax: plt.Axes, window: pd.DataFrame) -> None:
    if window.empty:
        return
    labels = window["bar_datetime"].map(_session_label).tolist()
    spans: list[tuple[int, int, str]] = []
    start = 0
    current = labels[0]
    for idx, label in enumerate(labels[1:], start=1):
        if label != current:
            spans.append((start, idx - 1, current))
            start = idx
            current = label
    spans.append((start, len(labels) - 1, current))
    colors = {
        "pre_day_night": "#dbeafe",
        "day_session": "#fef3c7",
        "post_day_night": "#ede9fe",
        "break_or_other": "#f3f4f6",
    }
    for left, right, label in spans:
        color = colors.get(label)
        if color:
            ax.axvspan(left, right, color=color, alpha=0.18, linewidth=0)


def _plot_row(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row["vt_symbol"])
    event_date = pd.Timestamp(row["event_date"]).normalize()
    day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = day[day["bar_date"].eq(event_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
    record = {
        "vt_symbol": vt_symbol,
        "event_date": event_date.strftime("%Y-%m-%d") if pd.notna(event_date) else "",
        "chart_missing_minutes": int(day.empty),
    }
    if day.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, f"missing minute bars\n{vt_symbol} {event_date:%Y-%m-%d}", ha="center", va="center")
        return record

    window = day.head(520).reset_index(drop=True)
    _shade_sessions(ax, window)
    s825._plot_candles(ax, window)
    entry = _safe_float(row.get("entry_price"))
    stop = _safe_float(row.get("stop_price"))
    progress = _safe_float(row.get("progress_price"))
    if entry > 0:
        ax.axhline(entry, color="#1d4ed8", linewidth=1.0, alpha=0.9)
    if stop > 0:
        ax.axhline(stop, color="#dc2626", linewidth=0.9, alpha=0.85)
    if progress > 0:
        ax.axhline(progress, color="#16a34a", linewidth=0.9, alpha=0.85)
    markers = [
        ("first_stop_time", "#dc2626", "stop"),
        ("reentry_time", "#2563eb", "reentry"),
        ("retry_failed_time", "#991b1b", "retry fail"),
    ]
    for column, color, label in markers:
        idx = _index_for_time(window, row.get(column))
        if idx >= 0:
            ax.axvline(idx, color=color, linewidth=1.0, alpha=0.9)
            y = ax.get_ylim()[1]
            ax.text(idx, y, label, color=color, fontsize=7, rotation=90, va="top", ha="right")
    ticks = np.linspace(0, len(window) - 1, num=min(9, len(window)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    ax.set_title(
        (
            f"{vt_symbol} {row.get('direction')} {event_date:%Y-%m-%d} "
            f"{row.get('session_pattern')} {row.get('final_state')} "
            f"pnl={_safe_float(row.get('matched_pnl')):,.0f} "
            f"proxy_delta={_safe_float(row.get('same_session_only_proxy_delta')):,.0f}"
        ),
        fontsize=8.2,
        loc="left",
    )
    return record


def _plot_atlas(features: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_events(features)
    if selected.empty:
        return [], pd.DataFrame()
    minute_bars = _load_minute_bars(set(selected["vt_symbol"].dropna().astype(str)))
    minute_by_symbol = s825._minute_groups(minute_bars)
    page_count = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, page_count + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.25 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            rec = _plot_row(ax, row, minute_by_symbol)
            rec.update(
                {
                    "chart_page": page,
                    "final_state": str(row.get("final_state", "")),
                    "session_pattern": str(row.get("session_pattern", "")),
                    "matched_pnl": _safe_float(row.get("matched_pnl")),
                    "same_session_only_proxy_delta": _safe_float(row.get("same_session_only_proxy_delta")),
                    "cross_session_reentry": int(_safe_float(row.get("cross_session_reentry"), 0.0)),
                }
            )
            records.append(rec)
        fig.suptitle(
            (
                f"Stage880 C9 session-boundary audit page {page}/{page_count}; "
                "blue shade=pre-day night, yellow=day, purple=post-day night; "
                "blue line=entry, red=stop/retry-fail, green=progress"
            ),
            fontsize=12,
        )
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _write_report(
    features: pd.DataFrame,
    session_summary: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    yearly: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    cross = features[features["cross_session_reentry"].eq(1)].copy()
    lines = [
        "# Stage880 Session Boundary Audit",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读审计；不改策略、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## External Research Judgment",
        "",
        "- 公共日内突破/趋势资料通常强调 session open、opening range、stop/retry 与隔夜/夜盘边界必须分开处理；vn.py/CTA 类引擎也要求明确 bar timestamp 与 trading session 语义。",
        "- 我的判断：Stage879 后不应继续扫 OR/R/OI 小阈值；交易时段边界是交易制度外生结构，值得一次只读审计，尤其要检查 C9 的 same-calendar retry 是否实际跨越 day/night session。",
        "",
        "## Key Counts",
        "",
        f"- C9 stop/retry events：`{len(features)}`",
        f"- cross-session reentry events：`{int(features['cross_session_reentry'].sum())}`",
        f"- day-session stop -> post-day-night reentry events：`{int(features['day_to_post_night_reentry'].sum())}`",
        f"- cross-session original matched PnL：`{_safe_float(cross['matched_pnl'].sum(), 0.0):,.1f}`",
        "",
        "## Session Summary",
        "",
        _md_table(session_summary, max_rows=30),
        "",
        "## Proxy Summary",
        "",
        _md_table(proxy_summary, max_rows=20),
        "",
        "## Yearly Proxy",
        "",
        _md_table(yearly, max_rows=80),
        "",
        "## Charts",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
        *[f"- atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- 决策：`stage880_session_boundary_same_session_retry_not_promoted_no_engine`",
        "- 理由：跨时段重试确实存在，但 day->post-night reentry 的净贡献为正；把它们粗暴限定为同连续时段重试，会砍掉恢复路径，暂不能进入真实引擎。",
        "- 下一步：时段边界保留为复盘标签；若继续，必须寻找能保护 day->post-night 右尾的账户/持仓生存规则，不能直接写 `禁止夜盘重试`、`禁止跨时段重试` 或继续扫开平盘分钟。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events = _prepare_events()
    closed_lots = _prepare_closed_lots()
    features = _build_event_features(events, closed_lots)
    session_summary = _session_summary(features)
    proxy_summary, yearly = _proxy_summary(features)
    _plot_summary_chart(session_summary, proxy_summary)
    atlas_paths, atlas_manifest = _plot_atlas(features)
    _write_report(features, session_summary, proxy_summary, yearly, atlas_paths)

    features.to_csv(FEATURES_PATH, index=False, encoding="utf-8-sig")
    session_summary.to_csv(SESSION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    proxy = proxy_summary.iloc[0].to_dict()
    cross = features[features["cross_session_reentry"].eq(1)].copy()
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "c9_stop_retry_events": int(len(features)),
        "cross_session_reentry_events": int(features["cross_session_reentry"].sum()),
        "day_to_post_night_reentry_events": int(features["day_to_post_night_reentry"].sum()),
        "cross_session_original_pnl": _safe_float(cross["matched_pnl"].sum(), 0.0),
        "same_session_only_proxy_delta": _safe_float(proxy.get("gross_proxy_delta"), 0.0),
        "same_session_only_winner_cut": _safe_float(proxy.get("winner_cut"), 0.0),
        "same_session_only_loser_saved": _safe_float(proxy.get("loser_saved"), 0.0),
        "same_session_only_big_winner_cut": _safe_float(proxy.get("big_winner_cut"), 0.0),
        "decision": "stage880_session_boundary_same_session_retry_not_promoted_no_engine",
        "next_action": "Keep session boundary as a forensic tag; do not promote no-night/cross-session retry bans.",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
