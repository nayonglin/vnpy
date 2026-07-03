from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage016"
MODEL_TAG = "stage016_minute_microstructure_pit_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage016_minute_microstructure_pit_audit"
MAX_PRIOR_CALENDAR_DAYS = 10
MIN_CONDITION_COUNT = 80
MIN_CONDITION_YEARS = 4
MIN_MEAN_PNL_LIFT = 1.25

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage009_meta_label_entry_quality_audit as s009_quality


OUTPUT_DIR = LINE_DIR / "outputs" / "stage016_minute_microstructure_pit_audit"

STAGE009_OUTPUT_DIR = LINE_DIR / "outputs" / "stage009_meta_label_entry_quality_audit"
STAGE009_PREFIX = "rebuilt_c9_v2_stage009_meta_label_entry_quality_audit"
STAGE009_TAG = "stage009_meta_label_entry_quality_audit_v1"
STAGE009_EVENTS_PATH = STAGE009_OUTPUT_DIR / f"{STAGE009_PREFIX}_quality_events_{STAGE009_TAG}.csv.gz"

MINUTE_BARS_PATH = (
    PROJECT_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv"
)

FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv.gz"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = LINE_DIR / "stages" / "20260702_0510_stage016_minute_microstructure_pit_audit.md"

DAILY_FEATURE_COLUMNS = [
    "prior_bar_date",
    "prior_bar_count",
    "prior_day_return_pct",
    "prior_intraday_range_pct",
    "prior_path_abs_return_pct",
    "prior_efficiency_ratio",
    "prior_noise_ratio",
    "prior_close_location",
    "prior_volume_sum",
    "prior_oi_change_pct",
]


def _json_safe(value: Any) -> Any:
    return s009_quality._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s009_quality._md_table(frame, max_rows=max_rows or 30)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _direction_sign(series: pd.Series) -> pd.Series:
    return np.where(series.astype(str).str.lower().eq("long"), 1.0, -1.0)


def _normal_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.tz_localize(None).dt.normalize()


def _safe_div(numerator: float, denominator: float) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return np.nan
    return float(numerator / denominator)


def build_daily_microstructure_features(minute_bars: pd.DataFrame) -> pd.DataFrame:
    data = minute_bars.copy()
    data["vt_symbol"] = data["vt_symbol"].astype(str)
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    if "bar_date" in data.columns:
        data["bar_date"] = _normal_date(data["bar_date"])
    else:
        data["bar_date"] = data["bar_datetime"].dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close"]).copy()
    if data.empty:
        return pd.DataFrame(columns=["vt_symbol", *DAILY_FEATURE_COLUMNS])

    rows: list[dict[str, Any]] = []
    grouped = data.sort_values(["vt_symbol", "bar_date", "bar_datetime"]).groupby(["vt_symbol", "bar_date"], sort=False)
    for (vt_symbol, bar_date), group in grouped:
        day_open = float(group["open"].iloc[0])
        day_close = float(group["close"].iloc[-1])
        day_high = float(group["high"].max())
        day_low = float(group["low"].min())
        bar_count = int(len(group))
        volume_sum = float(pd.to_numeric(group.get("volume"), errors="coerce").fillna(0.0).sum())
        path_abs = float((group["close"] - group["open"]).abs().sum())
        open_oi = float(group["open_oi"].iloc[0]) if "open_oi" in group.columns and pd.notna(group["open_oi"].iloc[0]) else np.nan
        close_oi = (
            float(group["close_oi"].iloc[-1])
            if "close_oi" in group.columns and pd.notna(group["close_oi"].iloc[-1])
            else np.nan
        )
        day_return_pct = _safe_div(day_close - day_open, day_open) * 100.0
        range_pct = _safe_div(day_high - day_low, day_open) * 100.0
        path_abs_return_pct = _safe_div(path_abs, day_open) * 100.0
        efficiency_ratio = _safe_div(abs(day_close - day_open), path_abs)
        noise_ratio = _safe_div(path_abs, abs(day_close - day_open))
        close_location = _safe_div(day_close - day_low, day_high - day_low)
        oi_change_pct = _safe_div(close_oi - open_oi, open_oi) * 100.0
        rows.append(
            {
                "vt_symbol": str(vt_symbol),
                "prior_bar_date": pd.Timestamp(bar_date).normalize(),
                "prior_bar_count": bar_count,
                "prior_day_return_pct": day_return_pct,
                "prior_intraday_range_pct": range_pct,
                "prior_path_abs_return_pct": path_abs_return_pct,
                "prior_efficiency_ratio": efficiency_ratio,
                "prior_noise_ratio": noise_ratio,
                "prior_close_location": close_location,
                "prior_volume_sum": volume_sum,
                "prior_oi_change_pct": oi_change_pct,
            }
        )
    return pd.DataFrame(rows).sort_values(["vt_symbol", "prior_bar_date"]).reset_index(drop=True)


def attach_prior_microstructure_features(
    events: pd.DataFrame,
    daily_features: pd.DataFrame,
    *,
    max_prior_calendar_days: int = MAX_PRIOR_CALENDAR_DAYS,
) -> pd.DataFrame:
    left = events.copy()
    left["_event_order"] = np.arange(len(left))
    left["vt_symbol"] = left["vt_symbol"].astype(str)
    left["entry_date"] = _normal_date(left["entry_date"])
    right = daily_features.copy()
    right["vt_symbol"] = right["vt_symbol"].astype(str)
    right["prior_bar_date"] = _normal_date(right["prior_bar_date"])
    result_parts: list[pd.DataFrame] = []
    for vt_symbol, group in left.groupby("vt_symbol", sort=False):
        symbol_daily = right[right["vt_symbol"].eq(vt_symbol)].copy()
        symbol_events = group.sort_values("entry_date").copy()
        if symbol_daily.empty:
            merged = symbol_events.copy()
            for column in DAILY_FEATURE_COLUMNS:
                merged[column] = pd.NaT if column == "prior_bar_date" else np.nan
        else:
            merged = pd.merge_asof(
                symbol_events,
                symbol_daily.drop(columns=["vt_symbol"]).sort_values("prior_bar_date"),
                left_on="entry_date",
                right_on="prior_bar_date",
                direction="backward",
                allow_exact_matches=False,
            )
        result_parts.append(merged)
    result = pd.concat(result_parts, ignore_index=True, sort=False).sort_values("_event_order").reset_index(drop=True)
    result["prior_lag_calendar_days"] = (result["entry_date"] - result["prior_bar_date"]).dt.days
    stale = result["prior_lag_calendar_days"].gt(max_prior_calendar_days) | result["prior_lag_calendar_days"].isna()
    for column in DAILY_FEATURE_COLUMNS:
        if column == "prior_bar_date":
            result.loc[stale, column] = pd.NaT
        else:
            result.loc[stale, column] = np.nan
    result.loc[stale, "prior_lag_calendar_days"] = np.nan

    sign = _direction_sign(result["direction"])
    result["prior_signal_return_pct"] = sign * pd.to_numeric(result["prior_day_return_pct"], errors="coerce")
    close_location = pd.to_numeric(result["prior_close_location"], errors="coerce")
    result["prior_signal_close_location"] = np.where(sign > 0, close_location, 1.0 - close_location)
    result["minute_prior_available"] = result["prior_bar_date"].notna().astype("int64")
    result = result.drop(columns=["_event_order"])
    return result


def _load_stage009_events() -> pd.DataFrame:
    data = _read_csv(STAGE009_EVENTS_PATH)
    data["entry_date"] = _normal_date(data["entry_date"])
    data["exit_date"] = _normal_date(data["exit_date"])
    data["entry_year"] = data["entry_date"].dt.year.astype("int64")
    for column in [
        "realized_pnl",
        "r_multiple",
        "big_winner",
        "bad_path",
        "ai_product_pool_rank",
        "selected_volume",
        "risk_multiplier",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


def _load_filtered_minute_bars(vt_symbols: set[str]) -> pd.DataFrame:
    usecols = [
        "vt_symbol",
        "bar_datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_oi",
        "close_oi",
        "bar_date",
    ]
    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(MINUTE_BARS_PATH, usecols=usecols, chunksize=500_000, encoding="utf-8-sig"):
        filtered = chunk[chunk["vt_symbol"].astype(str).isin(vt_symbols)].copy()
        if not filtered.empty:
            chunks.append(filtered)
    return pd.concat(chunks, ignore_index=True, sort=False) if chunks else pd.DataFrame(columns=usecols)


def add_microstructure_buckets(features: pd.DataFrame) -> pd.DataFrame:
    data = features.copy()
    sig_ret = pd.to_numeric(data["prior_signal_return_pct"], errors="coerce")
    sig_close = pd.to_numeric(data["prior_signal_close_location"], errors="coerce")
    eff = pd.to_numeric(data["prior_efficiency_ratio"], errors="coerce")
    noise = pd.to_numeric(data["prior_noise_ratio"], errors="coerce")
    oi = pd.to_numeric(data["prior_oi_change_pct"], errors="coerce")

    data["prior_signal_return_bucket"] = "missing"
    data.loc[sig_ret.gt(0.05), "prior_signal_return_bucket"] = "positive"
    data.loc[sig_ret.lt(-0.05), "prior_signal_return_bucket"] = "negative"
    data.loc[sig_ret.abs().le(0.05), "prior_signal_return_bucket"] = "flat"

    data["prior_signal_close_bucket"] = "missing"
    data.loc[sig_close.ge(2.0 / 3.0), "prior_signal_close_bucket"] = "signal_side_close"
    data.loc[sig_close.le(1.0 / 3.0), "prior_signal_close_bucket"] = "against_side_close"
    data.loc[sig_close.gt(1.0 / 3.0) & sig_close.lt(2.0 / 3.0), "prior_signal_close_bucket"] = "middle_close"

    data["prior_efficiency_bucket"] = "missing"
    data.loc[eff.ge(0.60), "prior_efficiency_bucket"] = "high_efficiency"
    data.loc[eff.lt(0.30), "prior_efficiency_bucket"] = "low_efficiency"
    data.loc[eff.ge(0.30) & eff.lt(0.60), "prior_efficiency_bucket"] = "mid_efficiency"

    data["prior_noise_bucket"] = "missing"
    data.loc[noise.le(2.0), "prior_noise_bucket"] = "low_noise"
    data.loc[noise.gt(4.0), "prior_noise_bucket"] = "high_noise"
    data.loc[noise.gt(2.0) & noise.le(4.0), "prior_noise_bucket"] = "mid_noise"

    data["prior_oi_bucket"] = "missing"
    data.loc[oi.gt(0.05), "prior_oi_bucket"] = "oi_up"
    data.loc[oi.lt(-0.05), "prior_oi_bucket"] = "oi_down"
    data.loc[oi.abs().le(0.05), "prior_oi_bucket"] = "oi_flat"

    data["prior_microstructure_state"] = "missing"
    favorable = sig_ret.gt(0.05) & sig_close.ge(2.0 / 3.0) & eff.ge(0.30)
    adverse = sig_ret.lt(-0.05) & sig_close.le(1.0 / 3.0)
    noisy_reversal = sig_ret.lt(-0.05) & noise.gt(4.0)
    data.loc[favorable, "prior_microstructure_state"] = "favorable_directional"
    data.loc[adverse, "prior_microstructure_state"] = "adverse_directional"
    data.loc[noisy_reversal, "prior_microstructure_state"] = "adverse_high_noise"
    neutral = data["minute_prior_available"].eq(1) & data["prior_microstructure_state"].eq("missing")
    data.loc[neutral, "prior_microstructure_state"] = "neutral_or_mixed"
    return data


def _condition_specs(features: pd.DataFrame) -> list[tuple[str, str, pd.Series]]:
    return [
        (
            "prior_return_positive",
            "Prior available trading day moved with signal direction.",
            features["prior_signal_return_bucket"].eq("positive"),
        ),
        (
            "prior_return_negative",
            "Prior available trading day moved against signal direction.",
            features["prior_signal_return_bucket"].eq("negative"),
        ),
        (
            "prior_signal_side_close",
            "Prior close was in signal-side third of intraday range.",
            features["prior_signal_close_bucket"].eq("signal_side_close"),
        ),
        (
            "prior_against_side_close",
            "Prior close was in against-side third of intraday range.",
            features["prior_signal_close_bucket"].eq("against_side_close"),
        ),
        (
            "prior_high_efficiency",
            "Prior day had high directional efficiency.",
            features["prior_efficiency_bucket"].eq("high_efficiency"),
        ),
        (
            "prior_high_noise",
            "Prior day had high minute path noise.",
            features["prior_noise_bucket"].eq("high_noise"),
        ),
        (
            "prior_oi_up_and_return_positive",
            "Prior day had OI up and signal-direction price return positive.",
            features["prior_oi_bucket"].eq("oi_up") & features["prior_signal_return_bucket"].eq("positive"),
        ),
        (
            "prior_favorable_directional",
            "Prior day was signal-directional with signal-side close and non-low efficiency.",
            features["prior_microstructure_state"].eq("favorable_directional"),
        ),
        (
            "prior_adverse_directional",
            "Prior day was adverse-directional by return and close location.",
            features["prior_microstructure_state"].eq("adverse_directional"),
        ),
        (
            "prior_adverse_high_noise",
            "Prior day was adverse by return and high path noise.",
            features["prior_microstructure_state"].eq("adverse_high_noise"),
        ),
    ]


def summarize_conditions(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_count = int(len(features))
    base_pnl = float(_numeric(features, "realized_pnl", 0.0).fillna(0.0).sum())
    base_mean_pnl = float(_numeric(features, "realized_pnl", 0.0).fillna(0.0).mean()) if base_count else np.nan
    base_bad_path_rate = float(_numeric(features, "bad_path", 0.0).fillna(0.0).mean() * 100.0) if base_count else np.nan
    rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    for condition_id, description, mask in _condition_specs(features):
        mask = mask.reindex(features.index).fillna(False).astype(bool)
        subset = features.loc[mask].copy()
        pnl = _numeric(subset, "realized_pnl", 0.0).fillna(0.0)
        bad_path = _numeric(subset, "bad_path", 0.0).fillna(0.0)
        big_winner = _numeric(subset, "big_winner", 0.0).fillna(0.0)
        event_count = int(len(subset))
        year = (
            subset.groupby("entry_year", dropna=False)
            .agg(
                event_count=("lot_id", "size"),
                total_pnl=("realized_pnl", "sum"),
                mean_pnl=("realized_pnl", "mean"),
                bad_path_rate_pct=("bad_path", lambda s: float(pd.to_numeric(s, errors="coerce").fillna(0.0).mean() * 100.0)),
            )
            .reset_index()
            if event_count
            else pd.DataFrame(columns=["entry_year", "event_count", "total_pnl", "mean_pnl", "bad_path_rate_pct"])
        )
        for item in year.to_dict("records"):
            yearly_rows.append({"condition_id": condition_id, **item})
        year_count = int(year["entry_year"].nunique()) if not year.empty else 0
        positive_years = int(year["total_pnl"].gt(0.0).sum()) if not year.empty else 0
        mean_pnl = float(pnl.mean()) if event_count else np.nan
        bad_path_rate = float(bad_path.mean() * 100.0) if event_count else np.nan
        candidate_eligible = bool(
            event_count >= MIN_CONDITION_COUNT
            and year_count >= MIN_CONDITION_YEARS
            and positive_years == year_count
            and np.isfinite(mean_pnl)
            and np.isfinite(base_mean_pnl)
            and mean_pnl >= base_mean_pnl * MIN_MEAN_PNL_LIFT
            and (not np.isfinite(base_bad_path_rate) or bad_path_rate <= base_bad_path_rate)
        )
        rows.append(
            {
                "condition_id": condition_id,
                "description": description,
                "event_count": event_count,
                "event_pct": float(event_count / base_count * 100.0) if base_count else np.nan,
                "total_pnl": float(pnl.sum()) if event_count else 0.0,
                "pnl_share_pct": float(pnl.sum() / base_pnl * 100.0) if abs(base_pnl) > 1e-12 else np.nan,
                "mean_pnl": mean_pnl,
                "mean_pnl_lift": float(mean_pnl / base_mean_pnl) if np.isfinite(mean_pnl) and abs(base_mean_pnl) > 1e-12 else np.nan,
                "win_rate_pct": float(pnl.gt(0.0).mean() * 100.0) if event_count else np.nan,
                "big_winner_rate_pct": float(big_winner.mean() * 100.0) if event_count else np.nan,
                "bad_path_rate_pct": bad_path_rate,
                "bad_path_delta_pp": float(bad_path_rate - base_bad_path_rate)
                if np.isfinite(bad_path_rate) and np.isfinite(base_bad_path_rate)
                else np.nan,
                "year_count": year_count,
                "positive_years": positive_years,
                "candidate_eligible": candidate_eligible,
            }
        )
    summary = pd.DataFrame(rows).sort_values(["candidate_eligible", "mean_pnl_lift"], ascending=[False, False])
    return summary.reset_index(drop=True), pd.DataFrame(yearly_rows)


def coverage_summary(features: pd.DataFrame, minute_bars: pd.DataFrame, daily_features: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "metric": "stage009_event_rows",
            "value": int(len(features)),
        },
        {
            "metric": "stage009_unique_vt_symbols",
            "value": int(features["vt_symbol"].nunique()),
        },
        {
            "metric": "minute_bar_rows_filtered",
            "value": int(len(minute_bars)),
        },
        {
            "metric": "minute_daily_feature_rows",
            "value": int(len(daily_features)),
        },
        {
            "metric": "prior_minute_available_rows",
            "value": int(features["minute_prior_available"].sum()),
        },
        {
            "metric": "prior_minute_available_pct",
            "value": float(features["minute_prior_available"].mean() * 100.0) if len(features) else np.nan,
        },
    ]
    return pd.DataFrame(rows)


def _decision(features: pd.DataFrame, condition_summary: pd.DataFrame, coverage: pd.DataFrame) -> dict[str, Any]:
    candidate_count = int(condition_summary["candidate_eligible"].sum()) if not condition_summary.empty else 0
    best = condition_summary.iloc[0].to_dict() if not condition_summary.empty else {}
    available_pct = float(
        coverage.loc[coverage["metric"].eq("prior_minute_available_pct"), "value"].iloc[0]
    ) if not coverage.empty else np.nan
    if candidate_count:
        decision = "stage016_prior_minute_microstructure_has_candidate_needs_engine_proxy"
        reason = "至少一个入场前分钟结构条件跨年正贡献且均值/坏路径优于母本，可进入下一阶段真实路径 proxy。"
        continue_after = "有价值，但下一步必须冻结条件并接真实组合路径，不能扫阈值。"
    else:
        decision = "stage016_prior_minute_microstructure_no_stable_candidate_keep_readonly"
        reason = "入场前一交易日分钟结构没有形成跨年稳定、均值提升、坏路径不恶化的候选。"
        continue_after = "有限。继续围绕前一日分钟阈值调参大概率过拟合；若继续，应转更结构化的账户外层或新增外生特征。"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_event_rows": int(len(features)),
        "prior_minute_available_pct": available_pct,
        "candidate_count": candidate_count,
        "best_condition_id": best.get("condition_id"),
        "best_event_count": int(best.get("event_count", 0)) if best else 0,
        "best_mean_pnl_lift": float(best.get("mean_pnl_lift", np.nan)) if best else np.nan,
        "best_positive_years": int(best.get("positive_years", 0)) if best else 0,
        "best_year_count": int(best.get("year_count", 0)) if best else 0,
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "decision": decision,
        "decision_reason": reason,
        "external_research_judgment": (
            "Trend-following literature says core alpha should preserve cross-market trend right tails; "
            "intraday/fast-alpha research is best treated as tactical execution or sizing overlay. "
            "This stage therefore uses only pre-entry prior-day minute structure and does not alter C9 logic."
        ),
        "overfit_reflection_before": (
            "否。假设来自外部 fast-alpha/whipsaw 研究和已有分钟数据可用性；本阶段只预声明少量形态，不按失败窗口调参。"
        ),
        "overfit_reflection_after": (
            "若本阶段没有候选后继续调 close-location/efficiency/noise 阈值，就是过拟合；应停止或换信息源。"
        ),
        "continue_value_before": "有价值。当前 AI 字段二级模型失败后，入场前分钟结构是新的 PIT 信息源，值得一次只读审计。",
        "continue_value_after": continue_after,
        "official_live_impact": {
            "strategy_changed": False,
            "official_live_config_changed": False,
            "order_api_called": False,
            "ctp_connected": False,
            "research_only": True,
        },
    }


def _plot(condition_summary: pd.DataFrame) -> None:
    if condition_summary.empty:
        return
    shown = condition_summary.head(10).copy()
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), constrained_layout=True)
    axes[0].barh(shown["condition_id"], shown["mean_pnl_lift"], color="#2563eb")
    axes[0].axvline(1.0, color="#111827", linewidth=0.8)
    axes[0].set_title("Stage016 prior-minute condition mean PnL lift")
    axes[0].set_xlabel("mean PnL lift vs Stage009 event panel")
    axes[0].invert_yaxis()
    axes[0].grid(True, axis="x", alpha=0.25)
    axes[1].barh(shown["condition_id"], shown["positive_years"], color="#16a34a")
    axes[1].set_title("Positive years by condition")
    axes[1].set_xlabel("years")
    axes[1].invert_yaxis()
    axes[1].grid(True, axis="x", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    coverage: pd.DataFrame,
    condition_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
) -> None:
    key_metrics = {
        key: decision[key]
        for key in [
            "input_event_rows",
            "prior_minute_available_pct",
            "candidate_count",
            "best_condition_id",
            "best_event_count",
            "best_mean_pnl_lift",
            "best_positive_years",
            "best_year_count",
        ]
    }
    text = f"""# Stage016 Prior-minute Microstructure PIT Audit

- line_id：`{LINE_ID}`
- 记录时间：{decision["generated_at"]}
- 决策：`{decision["decision"]}`

## 假设

当前可见 AI 字段二级模型 OOS 不稳定后，换一个信息源：只看入场日前一可用交易日的分钟结构，审计它是否能解释 Stage009 的信号质量。这个阶段不使用入场日之后的分钟线，不改策略。

## 方法

- 输入事件：Stage009 quality events。
- 输入分钟线：Stage861 full minute bars。
- PIT 约束：每笔事件只 merge `vt_symbol` 相同且 `bar_date < entry_date` 的最近一个分钟交易日，超过 `{MAX_PRIOR_CALENDAR_DAYS}` 个自然日视为缺失。
- 特征：方向收益、日内效率、路径噪音、收盘位置、OI 变化；只做预声明分桶。
- 候选门槛：事件数 `>= {MIN_CONDITION_COUNT}`、覆盖年数 `>= {MIN_CONDITION_YEARS}`、所有覆盖年 PnL 为正、均值 PnL lift `>= {MIN_MEAN_PNL_LIFT}`、bad_path 不高于母本。

## 结果概要

```json
{json.dumps(_json_safe(key_metrics), ensure_ascii=False, indent=2)}
```

## 覆盖率

{_md_table(coverage, max_rows=20)}

## 条件摘要

{_md_table(condition_summary, max_rows=20)}

## 年度摘要

{_md_table(year_summary, max_rows=40)}

## 结论

- {decision["decision_reason"]}
- 本阶段只读，不改策略、不改 AI 池、不连接 CTP、不调用订单 API。

## 过拟合反思

- 运行前：{decision["overfit_reflection_before"]}
- 运行后：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前：{decision["continue_value_before"]}
- 运行后：{decision["continue_value_after"]}
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(
    decision: dict[str, Any],
    coverage: pd.DataFrame,
    condition_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
) -> None:
    text = f"""# Stage016 Prior-minute Microstructure PIT Audit

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：当前重建 C9 入场前分钟结构只读审计；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；只有稳定候选进入真实路径 proxy 后才讨论

## 外部调研与判断

- 参考资料：managed futures/trend following 研究、pysystemtrade 资金/仓位回测文档、Concretum fast-alpha tactical overlay、intraday trend following/whipsaw 过滤讨论。
- 我的判断：分钟级信息更适合作为执行质量或 sizing overlay，不能替代日线趋势主逻辑；所以本阶段只看入场前已知的前一交易日分钟结构，不使用入场日后验确认。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage016_minute_microstructure_pit_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage016_minute_microstructure_pit_audit.py`
- 新增参数：`MAX_PRIOR_CALENDAR_DAYS={MAX_PRIOR_CALENDAR_DAYS}`、`MIN_CONDITION_COUNT={MIN_CONDITION_COUNT}`、`MIN_CONDITION_YEARS={MIN_CONDITION_YEARS}`、`MIN_MEAN_PNL_LIFT={MIN_MEAN_PNL_LIFT}`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- 输入事件数：`{decision["input_event_rows"]}`
- 前一交易日分钟特征覆盖率：`{decision["prior_minute_available_pct"]:.4f}%`
- 稳定候选数：`{decision["candidate_count"]}`
- 最优条件：`{decision["best_condition_id"]}`
- 最优条件事件数：`{decision["best_event_count"]}`
- 最优条件 mean PnL lift：`{decision["best_mean_pnl_lift"]:.4f}`
- 最优条件正贡献年数/覆盖年数：`{decision["best_positive_years"]}/{decision["best_year_count"]}`
- 决策：`{decision["decision"]}`
- 原因：{decision["decision_reason"]}

## 覆盖率

{_md_table(coverage, max_rows=20)}

## 条件摘要

{_md_table(condition_summary, max_rows=20)}

## 年度摘要

{_md_table(year_summary, max_rows=40)}

## 过拟合反思

- 运行前判断：{decision["overfit_reflection_before"]}
- 运行后判断：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前判断：{decision["continue_value_before"]}
- 运行后判断：{decision["continue_value_after"]}

## 输出文件

- features: `{FEATURES_PATH}`
- condition_summary: `{CONDITION_SUMMARY_PATH}`
- year_summary: `{YEAR_SUMMARY_PATH}`
- coverage: `{COVERAGE_PATH}`
- chart: `{CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    STAGE_RECORD_PATH.write_text(text, encoding="utf-8")


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events = _load_stage009_events()
    minute_bars = _load_filtered_minute_bars(set(events["vt_symbol"].astype(str).unique()))
    daily_features = build_daily_microstructure_features(minute_bars)
    features = attach_prior_microstructure_features(events, daily_features)
    features = add_microstructure_buckets(features)
    condition_summary, year_summary = summarize_conditions(features)
    coverage = coverage_summary(features, minute_bars, daily_features)
    decision = _decision(features, condition_summary, coverage)

    features.to_csv(FEATURES_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    _plot(condition_summary)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, coverage, condition_summary, year_summary)
    _write_stage_record(decision, coverage, condition_summary, year_summary)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
