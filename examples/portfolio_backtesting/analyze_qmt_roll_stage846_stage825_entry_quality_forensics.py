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
STAGE = "Stage846"
MODEL_TAG = "stage846_stage825_entry_quality_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage846_stage825_entry_quality_forensics"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")

STAGE825_PREFIX = "qmt_roll_stage825_stage819_intraday_rule_forensics"
STAGE825_TAG = "stage825_stage819_intraday_rule_forensics_v1"
STAGE825_INTRADAY_FEATURES_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_intraday_features_{STAGE825_TAG}.csv"
STAGE825_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_summary_{STAGE825_TAG}.csv"

QUALITY_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_lots_{MODEL_TAG}.csv"
TAXONOMY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_taxonomy_summary_{MODEL_TAG}.csv"
PROXY_LOT_DELTAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_lot_deltas_{MODEL_TAG}.csv"
PROXY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_summary_{MODEL_TAG}.csv"
PROXY_YEARLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_proxy_yearly_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_quality_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_quality_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_quality_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PER_PAGE = 4
MAX_ATLAS_ROWS = 24
OPENING_RANGE_BARS = 15


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normal_date(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    text = str(value)
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        ts = pd.to_datetime(text[:10], errors="coerce")
    else:
        ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    return pd.Timestamp(ts).normalize()


def _direction_sign(direction: Any) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _prepare_features() -> tuple[pd.DataFrame, pd.DataFrame]:
    features = _load_csv(STAGE825_INTRADAY_FEATURES_PATH).copy()
    summary = _load_csv(STAGE825_SUMMARY_PATH).copy()
    for column in ("entry_date", "exit_date"):
        if column in features.columns:
            features[column] = features[column].map(_normal_date)
    numeric_cols = [
        "lot_id",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "entry_price",
        "exit_price",
        "risk_pct",
        "entry_day_mfe_r",
        "entry_day_mae_r",
        "entry_day_close_return_pct",
        "opening_range_breakout_confirmed",
        "confirm_fast_60m_1r",
        "fail_fast_60m_05r",
        "mfe_60m_r",
        "mae_60m_r",
        "reentry_cross_count_after_05r_stop",
        "big_winner",
        "winner",
    ]
    features = _numeric(features, numeric_cols)
    features["entry_year"] = features["entry_date"].dt.year
    features["covered_entry_day"] = features["minute_coverage_state"].astype(str).eq("entry_day_covered").astype(int)
    features["winner"] = features["realized_pnl"].gt(0).astype(int)
    if "big_winner" not in features.columns or features["big_winner"].isna().all():
        positive = features.loc[features["r_multiple"].gt(0), "r_multiple"].dropna()
        threshold = float(positive.quantile(0.8)) if len(positive) else np.inf
        features["big_winner"] = features["r_multiple"].ge(threshold).astype(int)
    else:
        features["big_winner"] = features["big_winner"].fillna(0).astype(int)
    features["entry_day_first_0p5r_outcome"] = features["entry_day_first_0p5r_outcome"].fillna("missing").astype(str)
    features["reentry_cross_count_after_05r_stop"] = (
        pd.to_numeric(features["reentry_cross_count_after_05r_stop"], errors="coerce").fillna(0)
    )
    features["entry_quality_bucket"] = features.apply(_entry_quality_bucket, axis=1)
    features["or15_confirm_state"] = np.where(
        features["covered_entry_day"].eq(1),
        np.where(pd.to_numeric(features["opening_range_breakout_confirmed"], errors="coerce").fillna(0).eq(1), "or15_confirmed", "or15_not_confirmed"),
        "missing_minutes",
    )
    features["confirm60_state"] = np.where(
        features["covered_entry_day"].eq(1),
        np.where(pd.to_numeric(features["confirm_fast_60m_1r"], errors="coerce").fillna(0).eq(1), "confirm60_1r", "no_confirm60_1r"),
        "missing_minutes",
    )
    return features, summary


def _entry_quality_bucket(row: pd.Series) -> str:
    if int(_safe_float(row.get("covered_entry_day"), 0)) != 1:
        return "missing_minutes"
    outcome = str(row.get("entry_day_first_0p5r_outcome", "missing"))
    reentry = _safe_float(row.get("reentry_cross_count_after_05r_stop"), 0.0) > 0
    close_ret = _safe_float(row.get("entry_day_close_return_pct"), 0.0)
    if outcome == "target_first":
        return "target_first_05r"
    if outcome == "ambiguous_same_bar":
        return "ambiguous_same_bar"
    if outcome == "stop_first":
        if reentry:
            return "stop_first_recovered"
        if close_ret < 0:
            return "stop_first_unrecovered_close_bad"
        return "stop_first_no_reentry_mixed"
    if outcome == "neither":
        return "neither_close_good" if close_ret > 0 else "neither_close_bad"
    return "covered_other"


def _rate(series: pd.Series) -> float:
    data = pd.to_numeric(series, errors="coerce").dropna()
    if data.empty:
        return np.nan
    return float(data.mean() * 100.0)


def _taxonomy_summary(features: pd.DataFrame, column: str = "entry_quality_bucket") -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bucket, group in features.groupby(column, dropna=False):
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce")
        r_mult = pd.to_numeric(group["r_multiple"], errors="coerce")
        winners = group[pnl.gt(0)]
        losers = group[pnl.lt(0)]
        big = group[group["big_winner"].eq(1)]
        rows.append(
            {
                "bucket_type": column,
                "bucket": str(bucket),
                "lots": int(len(group)),
                "covered_lots": int(group["covered_entry_day"].sum()),
                "total_pnl": float(pnl.sum()),
                "total_r": float(r_mult.sum()),
                "median_r": float(r_mult.median()) if len(group) else np.nan,
                "win_rate_pct": float(group["winner"].mean() * 100.0) if len(group) else np.nan,
                "winner_lots": int(len(winners)),
                "winner_pnl": float(pd.to_numeric(winners["realized_pnl"], errors="coerce").sum()) if len(winners) else 0.0,
                "loser_lots": int(len(losers)),
                "loser_pnl": float(pd.to_numeric(losers["realized_pnl"], errors="coerce").sum()) if len(losers) else 0.0,
                "big_winner_lots": int(len(big)),
                "big_winner_pnl": float(pd.to_numeric(big["realized_pnl"], errors="coerce").sum()) if len(big) else 0.0,
                "median_entry_day_mfe_r": float(pd.to_numeric(group.get("entry_day_mfe_r"), errors="coerce").median()),
                "median_entry_day_mae_r": float(pd.to_numeric(group.get("entry_day_mae_r"), errors="coerce").median()),
                "or15_confirm_rate_pct": _rate(group["opening_range_breakout_confirmed"]) if "opening_range_breakout_confirmed" in group else np.nan,
                "confirm60_1r_rate_pct": _rate(group["confirm_fast_60m_1r"]) if "confirm_fast_60m_1r" in group else np.nan,
                "first05_stop_lots": int(group["entry_day_first_0p5r_outcome"].eq("stop_first").sum()),
                "first05_target_lots": int(group["entry_day_first_0p5r_outcome"].eq("target_first").sum()),
                "reentry_after_05r_stop_lots": int(pd.to_numeric(group["reentry_cross_count_after_05r_stop"], errors="coerce").fillna(0).gt(0).sum()),
            }
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["bucket_type", "total_pnl"], ascending=[True, False], inplace=True)
    return result.reset_index(drop=True)


def _proxy_specs(features: pd.DataFrame) -> list[dict[str, Any]]:
    covered = features["covered_entry_day"].eq(1)
    risk = pd.to_numeric(features["risk_amount"], errors="coerce").fillna(0.0)
    original = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    first_stop = covered & features["entry_day_first_0p5r_outcome"].eq("stop_first") & risk.gt(0)
    recovered = first_stop & pd.to_numeric(features["reentry_cross_count_after_05r_stop"], errors="coerce").fillna(0).gt(0)
    no_reentry = first_stop & ~recovered
    stop_cash = -0.5 * risk

    p1 = original.copy()
    p1.loc[first_stop] = stop_cash.loc[first_stop]

    p2 = original.copy()
    p2.loc[recovered] = original.loc[recovered] + stop_cash.loc[recovered]
    p2.loc[no_reentry] = stop_cash.loc[no_reentry]

    or_not_confirmed = covered & ~pd.to_numeric(features["opening_range_breakout_confirmed"], errors="coerce").fillna(0).eq(1)
    p3 = original.copy()
    p3.loc[or_not_confirmed] = 0.0

    no_confirm60 = covered & ~pd.to_numeric(features["confirm_fast_60m_1r"], errors="coerce").fillna(0).eq(1)
    p4 = original.copy()
    p4.loc[no_confirm60] = 0.0

    p5 = original.copy()
    p5.loc[no_reentry] = 0.0

    return [
        {
            "proxy_id": "P1_stop05_no_retry_all_day_proxy",
            "proxy_family": "real_time_stop",
            "proxy_text": "开仓日先触发0.5R反向即按-0.5R退出，且当天不重试；缺分钟样本保持原值。",
            "affected": first_stop,
            "adjusted": p1,
            "live_feasible": True,
            "diagnostic_only_reason": "只读lot代理，未重跑组合资金路径，不能当成真实引擎结果。",
        },
        {
            "proxy_id": "P2_stop05_retry_on_entry_reclaim_proxy",
            "proxy_family": "real_time_stop_retry",
            "proxy_text": "先按0.5R实时止损；若当天重新穿越原入场价，则假定允许一次重试并沿用原后续结果。",
            "affected": first_stop,
            "adjusted": p2,
            "live_feasible": "partly",
            "diagnostic_only_reason": "使用当天是否重回入场价做只读近似；真实引擎需逐分钟重放重试成交和资金路径。",
        },
        {
            "proxy_id": "P3_block_or15_no_breakout_proxy",
            "proxy_family": "entry_confirmation",
            "proxy_text": "开盘15分钟区间没有按信号方向突破则不入场；缺分钟样本保持原值。",
            "affected": or_not_confirmed,
            "adjusted": p3,
            "live_feasible": True,
            "diagnostic_only_reason": "只读拒单代理，未处理错过后续再突破、替代入场价和资金复用。",
        },
        {
            "proxy_id": "P4_block_no_60m_1r_confirm_proxy",
            "proxy_family": "fast_confirmation",
            "proxy_text": "入场后60分钟内未达到1R顺向则视为质量不足并拒绝该笔。",
            "affected": no_confirm60,
            "adjusted": p4,
            "live_feasible": False,
            "diagnostic_only_reason": "确认条件发生在入场后，直接拒绝原始入场有语义混淆；只用来衡量右尾误伤。",
        },
        {
            "proxy_id": "P5_block_stop_first_no_reentry_eod_diagnostic",
            "proxy_family": "hindsight_ceiling",
            "proxy_text": "仅事后剔除0.5R先止损且当天未重回入场价的样本，用作可分离上限，不是可实时规则。",
            "affected": no_reentry,
            "adjusted": p5,
            "live_feasible": False,
            "diagnostic_only_reason": "需要知道全天是否重回入场价，不能直接实盘化。",
        },
    ]


def _proxy_tables(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    lot_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    base_total_pnl = float(original.sum())
    for spec in _proxy_specs(features):
        affected = spec["affected"].fillna(False)
        adjusted = pd.to_numeric(spec["adjusted"], errors="coerce").fillna(original)
        delta = adjusted - original
        tmp = features.copy()
        tmp["_affected"] = affected.astype(int)
        tmp["_original"] = original
        tmp["_adjusted"] = adjusted
        tmp["_delta"] = delta
        affected_frame = tmp[tmp["_affected"].eq(1)].copy()
        winners = affected_frame[affected_frame["_original"].gt(0)]
        losers = affected_frame[affected_frame["_original"].lt(0)]
        big = affected_frame[affected_frame["big_winner"].eq(1)]
        summary_rows.append(
            {
                "proxy_id": spec["proxy_id"],
                "proxy_family": spec["proxy_family"],
                "proxy_text": spec["proxy_text"],
                "live_feasible": spec["live_feasible"],
                "diagnostic_only_reason": spec["diagnostic_only_reason"],
                "all_lots": int(len(tmp)),
                "covered_lots": int(tmp["covered_entry_day"].sum()),
                "affected_lots": int(len(affected_frame)),
                "affected_original_pnl": float(affected_frame["_original"].sum()) if len(affected_frame) else 0.0,
                "affected_adjusted_pnl": float(affected_frame["_adjusted"].sum()) if len(affected_frame) else 0.0,
                "proxy_delta": float(delta.sum()),
                "base_total_pnl": base_total_pnl,
                "proxy_total_pnl": float(adjusted.sum()),
                "affected_winner_lots": int(len(winners)),
                "affected_loser_lots": int(len(losers)),
                "affected_big_winner_lots": int(len(big)),
                "winner_delta_sum": float(winners["_delta"].sum()) if len(winners) else 0.0,
                "loser_delta_sum": float(losers["_delta"].sum()) if len(losers) else 0.0,
                "big_winner_delta_sum": float(big["_delta"].sum()) if len(big) else 0.0,
                "median_delta": float(affected_frame["_delta"].median()) if len(affected_frame) else 0.0,
            }
        )
        for _, row in tmp.iterrows():
            lot_rows.append(
                {
                    "proxy_id": spec["proxy_id"],
                    "lot_id": int(row["lot_id"]),
                    "vt_symbol": row.get("vt_symbol", ""),
                    "product": row.get("product", ""),
                    "direction": row.get("direction", ""),
                    "entry_date": row["entry_date"].strftime("%Y-%m-%d") if not pd.isna(row["entry_date"]) else "",
                    "entry_year": int(row["entry_year"]) if not pd.isna(row["entry_year"]) else 0,
                    "entry_quality_bucket": row.get("entry_quality_bucket", ""),
                    "covered_entry_day": int(row.get("covered_entry_day", 0)),
                    "affected": int(row["_affected"]),
                    "original_pnl": float(row["_original"]),
                    "adjusted_pnl": float(row["_adjusted"]),
                    "proxy_delta": float(row["_delta"]),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                    "risk_amount": _safe_float(row.get("risk_amount")),
                    "big_winner": int(row.get("big_winner", 0)),
                    "entry_day_first_0p5r_outcome": row.get("entry_day_first_0p5r_outcome", ""),
                    "reentry_cross_count_after_05r_stop": _safe_float(row.get("reentry_cross_count_after_05r_stop"), 0.0),
                    "opening_range_breakout_confirmed": _safe_float(row.get("opening_range_breakout_confirmed"), np.nan),
                    "confirm_fast_60m_1r": _safe_float(row.get("confirm_fast_60m_1r"), np.nan),
                }
            )
        for year, group in tmp.groupby("entry_year", dropna=False):
            affected_year = group[group["_affected"].eq(1)]
            yearly_rows.append(
                {
                    "proxy_id": spec["proxy_id"],
                    "entry_year": int(year) if not pd.isna(year) else 0,
                    "lots": int(len(group)),
                    "affected_lots": int(len(affected_year)),
                    "affected_original_pnl": float(affected_year["_original"].sum()) if len(affected_year) else 0.0,
                    "proxy_delta": float(group["_delta"].sum()),
                    "winner_delta_sum": float(group[group["_original"].gt(0)]["_delta"].sum()),
                    "loser_delta_sum": float(group[group["_original"].lt(0)]["_delta"].sum()),
                    "big_winner_delta_sum": float(group[group["big_winner"].eq(1)]["_delta"].sum()),
                }
            )
    return pd.DataFrame(lot_rows), pd.DataFrame(summary_rows), pd.DataFrame(yearly_rows)


def _plot_chart(taxonomy: pd.DataFrame, proxy_summary: pd.DataFrame, features: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    quality = taxonomy[taxonomy["bucket_type"].eq("entry_quality_bucket")].copy()
    quality = quality.sort_values("total_pnl")
    axes[0, 0].barh(quality["bucket"], quality["total_pnl"], color=np.where(quality["total_pnl"].ge(0), "#2563eb", "#dc2626"))
    axes[0, 0].axvline(0, color="#6b7280", linewidth=0.8)
    axes[0, 0].set_title("Entry quality bucket total PnL")
    axes[0, 0].set_xlabel("total pnl")

    proxy = proxy_summary.sort_values("proxy_delta")
    axes[0, 1].barh(proxy["proxy_id"], proxy["proxy_delta"], color=np.where(proxy["proxy_delta"].ge(0), "#2563eb", "#dc2626"))
    axes[0, 1].axvline(0, color="#6b7280", linewidth=0.8)
    axes[0, 1].set_title("Gross proxy delta vs original lots")
    axes[0, 1].set_xlabel("proxy delta")

    covered = features[features["covered_entry_day"].eq(1)].copy()
    colors = np.where(covered["realized_pnl"].gt(0), "#2563eb", "#dc2626")
    sizes = np.clip(pd.to_numeric(covered["risk_amount"], errors="coerce").fillna(0.0) / 600 + 16, 16, 100)
    axes[1, 0].scatter(covered["entry_day_mae_r"], covered["entry_day_mfe_r"], c=colors, s=sizes, alpha=0.68)
    axes[1, 0].axhline(0.5, color="#16a34a", linewidth=0.8, linestyle="--")
    axes[1, 0].axvline(0.5, color="#dc2626", linewidth=0.8, linestyle="--")
    axes[1, 0].set_title("Entry-day MAE/MFE in R (covered lots)")
    axes[1, 0].set_xlabel("entry-day MAE R")
    axes[1, 0].set_ylabel("entry-day MFE R")

    y = np.arange(len(proxy_summary))
    ordered = proxy_summary.sort_values("proxy_id")
    axes[1, 1].barh(y - 0.18, ordered["loser_delta_sum"], height=0.36, color="#16a34a", label="loser delta")
    axes[1, 1].barh(y + 0.18, ordered["winner_delta_sum"], height=0.36, color="#f97316", label="winner delta")
    axes[1, 1].set_yticks(y)
    axes[1, 1].set_yticklabels(ordered["proxy_id"], fontsize=8)
    axes[1, 1].axvline(0, color="#6b7280", linewidth=0.8)
    axes[1, 1].set_title("Proxy tradeoff: left-tail saved vs right-tail damaged")
    axes[1, 1].legend(fontsize=8)

    for ax in axes.ravel():
        ax.grid(True, alpha=0.22)
    fig.suptitle("Stage846 Stage825 entry quality diagnostic", fontsize=13)
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame, proxy_lot_deltas: pd.DataFrame) -> pd.DataFrame:
    p2 = proxy_lot_deltas[proxy_lot_deltas["proxy_id"].eq("P2_stop05_retry_on_entry_reclaim_proxy")][
        ["lot_id", "proxy_delta"]
    ].rename(columns={"proxy_delta": "p2_proxy_delta"})
    data = features.merge(p2, on="lot_id", how="left")
    covered = data[data["covered_entry_day"].eq(1)].copy()
    selections: list[pd.DataFrame] = []

    specs = [
        ("stop_first_unrecovered_close_bad_worst", covered[covered["entry_quality_bucket"].eq("stop_first_unrecovered_close_bad")].sort_values("realized_pnl").head(4)),
        ("stop_first_recovered_best", covered[covered["entry_quality_bucket"].eq("stop_first_recovered")].sort_values("realized_pnl", ascending=False).head(4)),
        ("stop_first_recovered_worst", covered[covered["entry_quality_bucket"].eq("stop_first_recovered")].sort_values("realized_pnl").head(4)),
        ("target_first_big_winner", covered[covered["entry_quality_bucket"].eq("target_first_05r") & covered["big_winner"].eq(1)].sort_values("realized_pnl", ascending=False).head(4)),
        (
            "or_no_breakout_winner",
            covered[
                ~pd.to_numeric(covered["opening_range_breakout_confirmed"], errors="coerce").fillna(0).eq(1)
                & covered["realized_pnl"].gt(0)
            ].sort_values("realized_pnl", ascending=False).head(4),
        ),
        (
            "no_60m_confirm_big_winner",
            covered[
                ~pd.to_numeric(covered["confirm_fast_60m_1r"], errors="coerce").fillna(0).eq(1)
                & covered["big_winner"].eq(1)
            ].sort_values("realized_pnl", ascending=False).head(4),
        ),
    ]
    for label, frame in specs:
        if frame.empty:
            continue
        part = frame.copy()
        part["atlas_reason"] = label
        selections.append(part)
    if not selections:
        return pd.DataFrame()
    selected = pd.concat(selections, ignore_index=True, sort=False)
    selected = selected.drop_duplicates("lot_id", keep="first").head(MAX_ATLAS_ROWS)
    return selected.reset_index(drop=True)


def _plot_entry_lot(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    vt_symbol = str(row["vt_symbol"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    direction = str(row["direction"])
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    day = bars[bars["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").head(280).reset_index(drop=True) if not bars.empty else pd.DataFrame()
    record = {
        "lot_id": int(row["lot_id"]),
        "vt_symbol": vt_symbol,
        "entry_date": entry_date.strftime("%Y-%m-%d"),
        "direction": direction,
        "atlas_reason": row.get("atlas_reason", ""),
        "chart_missing_minutes": int(day.empty),
    }
    if day.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
        return record

    s825._plot_candles(ax, day)
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("risk_pct"))
    sign = _direction_sign(direction)
    if np.isfinite(entry_price):
        ax.axhline(entry_price, color="#2563eb", linewidth=0.95, label="entry")
    if np.isfinite(entry_price) and np.isfinite(risk_pct) and risk_pct > 0:
        ax.axhline(entry_price * (1.0 - sign * 0.5 * risk_pct), color="#dc2626", linewidth=0.9, linestyle="--", label="0.5R stop")
        ax.axhline(entry_price * (1.0 + sign * 0.5 * risk_pct), color="#16a34a", linewidth=0.85, linestyle="--", label="0.5R target")
        ax.axhline(entry_price * (1.0 + sign * 1.0 * risk_pct), color="#15803d", linewidth=0.85, linestyle=":", label="1R target")
    if len(day) >= OPENING_RANGE_BARS:
        opening = day.head(OPENING_RANGE_BARS)
        ax.axhline(float(opening["high"].max()), color="#7c3aed", linewidth=0.75, linestyle="--", alpha=0.75)
        ax.axhline(float(opening["low"].min()), color="#7c3aed", linewidth=0.75, linestyle="--", alpha=0.75)
        ax.axvspan(0, OPENING_RANGE_BARS - 1, color="#fef3c7", alpha=0.22)
    ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    ax.grid(True, alpha=0.18)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(handles[:4], labels[:4], loc="best", fontsize=7)
    ax.set_title(
        (
            f"{row.get('atlas_reason', '')} | lot{int(row['lot_id'])} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
            f"bucket={row.get('entry_quality_bucket', '')} pnl={_safe_float(row.get('realized_pnl')):,.0f} "
            f"R={_safe_float(row.get('r_multiple')):.2f} P2delta={_safe_float(row.get('p2_proxy_delta'), 0.0):,.0f} "
            f"first05={row.get('entry_day_first_0p5r_outcome', '')} reentry={_safe_float(row.get('reentry_cross_count_after_05r_stop'), 0.0):.0f} "
            f"OR={_safe_float(row.get('opening_range_breakout_confirmed'), np.nan):.0f} c60={_safe_float(row.get('confirm_fast_60m_1r'), np.nan):.0f}"
        ),
        fontsize=8.1,
        loc="left",
    )
    return record


def _plot_atlas(features: pd.DataFrame, proxy_lot_deltas: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(features, proxy_lot_deltas)
    if selected.empty:
        return [], pd.DataFrame()
    vt_symbols = set(selected["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    selected = selected.head(MAX_ATLAS_ROWS).copy()
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.35 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            record = _plot_entry_lot(ax, row, minute_by_symbol)
            record["page"] = page
            record["entry_quality_bucket"] = row.get("entry_quality_bucket", "")
            record["realized_pnl"] = _safe_float(row.get("realized_pnl"))
            record["r_multiple"] = _safe_float(row.get("r_multiple"))
            record["p2_proxy_delta"] = _safe_float(row.get("p2_proxy_delta"), 0.0)
            manifest_rows.append(record)
        fig.suptitle("Stage846 entry quality minute-K atlas", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest_rows)


def _decision(proxy_summary: pd.DataFrame) -> str:
    p2 = proxy_summary[proxy_summary["proxy_id"].eq("P2_stop05_retry_on_entry_reclaim_proxy")]
    p3 = proxy_summary[proxy_summary["proxy_id"].eq("P3_block_or15_no_breakout_proxy")]
    p4 = proxy_summary[proxy_summary["proxy_id"].eq("P4_block_no_60m_1r_confirm_proxy")]
    p2_delta = float(p2["proxy_delta"].iloc[0]) if len(p2) else 0.0
    p2_big_damage = float(p2["big_winner_delta_sum"].iloc[0]) if len(p2) else 0.0
    p3_delta = float(p3["proxy_delta"].iloc[0]) if len(p3) else 0.0
    p4_delta = float(p4["proxy_delta"].iloc[0]) if len(p4) else 0.0
    if p2_delta > 0 and p2_big_damage > -1_500_000 and p3_delta < 0 and p4_delta < 0:
        return "stage846_stop_retry_proxy_supported_but_confirmation_filters_rejected_diagnostic"
    if p2_delta > 0:
        return "stage846_stop_retry_proxy_positive_but_needs_real_engine"
    return "stage846_entry_quality_proxy_mixed_no_rule"


def _write_report(
    summary: pd.DataFrame,
    features: pd.DataFrame,
    taxonomy: pd.DataFrame,
    proxy_summary: pd.DataFrame,
    proxy_yearly: pd.DataFrame,
    atlas_paths: list[Path],
    decision: str,
) -> None:
    row = summary.iloc[0].to_dict() if not summary.empty else {}
    quality = taxonomy[taxonomy["bucket_type"].eq("entry_quality_bucket")]
    lines = [
        "# Stage846 Stage825入场质量只读法证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        f"- 区间：`{START.date()}` 到 `{END.date()}`",
        "- 阶段性质：只读法证；读取 Stage825 逐笔分钟特征，不重新回测，不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- CME futures order types：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types",
        "- CME position and risk management：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management",
        "- CFTC stop-loss order education：https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf",
        "- vn.py GitHub：https://github.com/vnpy/vnpy",
        "- 我的判断：CME 和 CFTC 的止损/仓位管理资料支持预先定义止损和风险管理纪律，但不支持把单根K线或单一阈值当成趋势失败证明。",
        "- 我的判断：公开 ORB/突破确认资料常强调假突破、波动过滤和止损，但参数不可直接复制到本组合；vn.py 的信号、成交、风控和持仓事件也应隔离，所以本阶段只做 lot-level 代理和图谱。",
        "",
        "## Full-Period Reference",
        "",
        _md_table(
            pd.DataFrame(
                [
                    {
                        "end_equity": row.get("end_equity"),
                        "total_return_pct": row.get("total_return_pct"),
                        "max_dd_pct": row.get("max_dd_pct"),
                        "sharpe": row.get("sharpe"),
                        "total_slippage": row.get("total_slippage"),
                        "total_trade_count": row.get("total_trade_count"),
                        "win_rate_pct": row.get("nonzero_daily_win_rate_pct"),
                    }
                ]
            ),
            max_rows=5,
        ),
        "",
        "## Coverage",
        "",
        _md_table(
            pd.DataFrame(
                [
                    {
                        "closed_lots": int(len(features)),
                        "entry_day_covered_lots": int(features["covered_entry_day"].sum()),
                        "missing_entry_day_lots": int(len(features) - features["covered_entry_day"].sum()),
                        "covered_pct": float(features["covered_entry_day"].mean() * 100.0) if len(features) else 0.0,
                    }
                ]
            ),
            max_rows=5,
        ),
        "",
        "## Entry Quality Taxonomy",
        "",
        _md_table(quality, max_rows=30),
        "",
        "## Gross Proxy Diagnostics",
        "",
        _md_table(proxy_summary, max_rows=20),
        "",
        "## Proxy Yearly Deltas",
        "",
        _md_table(proxy_yearly, max_rows=60),
        "",
        "## Atlas",
        "",
        *[f"- `{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        f"- 决策标签：`{decision}`。",
        "- 本阶段没有产生可直接接入正式版或候选版的规则；所有 P1-P5 都是只读 gross proxy，不是组合引擎。",
        "- 若 P2 正向，它只说明“实时止损后允许有限重试”比 no-retry 更接近趋势策略直觉；仍需冻结真实分钟引擎验证成交、资金复用和保证金路径。",
        "- P3 OR15 简单拒单代理若为正，也不能直接晋级；它没有处理等待突破后的替代入场价、重试成交和资金复用，而且 Stage834 的 OR15 close/hold 贴近交易语义版本已经反证过。",
        "- OR15 或 60m 确认若为负，说明延迟/确认过滤大概率误伤右尾，不应继续沿 OR 长度、确认分钟或 R 倍数扫参。",
        "- 过拟合判断：否。阶段使用预声明的低自由度 taxonomy 和代理口径，没有按年份、品种、方向或图谱挑参数；继续调 `0.5R/1R/15/60m` 才会过拟合。",
        "- 继续价值判断：有。若 P2 的损益结构稳定，下一步只允许做一个冻结的分钟级真实引擎 A/C；若 P2 也混杂，则停止入场止损重试路线。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features, summary = _prepare_features()
    taxonomy_frames = [
        _taxonomy_summary(features, "entry_quality_bucket"),
        _taxonomy_summary(features, "or15_confirm_state"),
        _taxonomy_summary(features, "confirm60_state"),
    ]
    taxonomy = pd.concat(taxonomy_frames, ignore_index=True, sort=False)
    proxy_lot_deltas, proxy_summary, proxy_yearly = _proxy_tables(features)
    _plot_chart(taxonomy, proxy_summary, features)
    atlas_paths, atlas_manifest = _plot_atlas(features, proxy_lot_deltas)
    decision = _decision(proxy_summary)

    features.to_csv(QUALITY_LOTS_PATH, index=False, encoding="utf-8-sig")
    taxonomy.to_csv(TAXONOMY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_lot_deltas.to_csv(PROXY_LOT_DELTAS_PATH, index=False, encoding="utf-8-sig")
    proxy_summary.to_csv(PROXY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    proxy_yearly.to_csv(PROXY_YEARLY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, features, taxonomy, proxy_summary, proxy_yearly, atlas_paths, decision)

    row = summary.iloc[0].to_dict() if not summary.empty else {}
    decision_payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "decision": decision,
        "full_period_result": {
            "end_equity": row.get("end_equity"),
            "total_return_pct": row.get("total_return_pct"),
            "max_dd_pct": row.get("max_dd_pct"),
            "sharpe": row.get("sharpe"),
            "total_slippage": row.get("total_slippage"),
            "total_trade_count": row.get("total_trade_count"),
            "win_rate_pct": row.get("nonzero_daily_win_rate_pct"),
        },
        "closed_lots": int(len(features)),
        "entry_day_covered_lots": int(features["covered_entry_day"].sum()),
        "minute_coverage_pct": float(features["covered_entry_day"].mean() * 100.0) if len(features) else 0.0,
        "taxonomy_summary": taxonomy.to_dict("records"),
        "proxy_summary": proxy_summary.to_dict("records"),
        "overfit_reflection": (
            "No. Stage846 is a fixed read-only taxonomy and gross proxy test. It does not tune by year, product, direction, "
            "minute window, or R multiple. Further small-threshold rescue would be overfitting."
        ),
        "continue_value": (
            "Yes if a stop-and-retry proxy improves left-tail without destroying right-tail; otherwise stop this route. "
            "Any promotion requires a frozen minute-level engine A/C."
        ),
        "outputs": {
            "quality_lots": str(QUALITY_LOTS_PATH),
            "taxonomy_summary": str(TAXONOMY_SUMMARY_PATH),
            "proxy_lot_deltas": str(PROXY_LOT_DELTAS_PATH),
            "proxy_summary": str(PROXY_SUMMARY_PATH),
            "proxy_yearly": str(PROXY_YEARLY_PATH),
            "chart": str(CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2))
    print("proxy_summary")
    print(proxy_summary.to_string(index=False))
    print("taxonomy_entry_quality")
    print(taxonomy[taxonomy["bucket_type"].eq("entry_quality_bucket")].to_string(index=False))


if __name__ == "__main__":
    main()
