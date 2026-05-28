from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage404_stage079_residual_holding_gap_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage404_stage079_residual_holding_gap_attribution"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE403_DAILY_PATH = (
    OUTPUT_DIR / "qmt_roll_stage403_stage079_xsmom_execution_margin_audit_daily_stage403_stage079_xsmom_execution_margin_audit_v1.csv"
)
STAGE403_SATELLITE_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage403_stage079_xsmom_execution_margin_audit_satellite_daily_stage403_stage079_xsmom_execution_margin_audit_v1.csv"
)

BASELINE_VARIANT = "stage079"
CANDIDATE_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
ACCOUNT_CAPITAL = 615_000.0

HORIZON_TARGETS = {
    90: {
        "label": "3个月",
        "return_p05_pct": -8.0,
        "return_median_pct": 13.52,
        "positive_return_rate": 0.80,
        "annualized_below_5pct_rate": 0.22,
        "max_dd_worst_pct": -29.20,
        "max_dd_ideal_pct": -26.0,
        "dd20_breach_rate": 0.12,
        "dd30_breach_rate": 0.0,
        "ulcer_p95_pct": 15.0,
        "longest_underwater_p95_days": 80.0,
    },
    180: {
        "label": "6个月",
        "return_p05_pct": 0.0,
        "return_p05_ideal_pct": 2.0,
        "return_median_pct": 33.92,
        "positive_return_rate": 0.95,
        "annualized_below_5pct_rate": 0.06,
        "max_dd_worst_pct": -29.70,
        "max_dd_ideal_pct": -28.0,
        "dd20_breach_rate": 0.25,
        "dd30_breach_rate": 0.0,
        "ulcer_p95_pct": 17.0,
        "longest_underwater_p95_days": 150.0,
    },
}

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_gap_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_attribution_{MODEL_TAG}.csv"
WORST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_windows_{MODEL_TAG}.csv"
CONTRAST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_window_contrast_{MODEL_TAG}.csv"
MONTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_month_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _drawdown(nav: np.ndarray) -> np.ndarray:
    return nav / np.maximum.accumulate(nav) - 1.0


def _ulcer(nav: np.ndarray) -> float:
    dd = np.minimum(_drawdown(nav) * 100.0, 0.0)
    return float(np.sqrt(np.mean(np.square(dd)))) if len(dd) else 0.0


def _longest_underwater_days(index: pd.DatetimeIndex, nav: np.ndarray) -> int:
    high = np.maximum.accumulate(nav)
    underwater = nav < high * (1.0 - 1e-12)
    longest = 0
    start: pd.Timestamp | None = None
    for date, flag in zip(index, underwater):
        if bool(flag):
            if start is None:
                start = date
            longest = max(longest, int((date - start).days) + 1)
        else:
            start = None
    return int(longest)


def _load_daily() -> pd.DataFrame:
    frame = pd.read_csv(STAGE403_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    numeric_cols = [
        "c3_net_pnl",
        "c3_trade_count",
        "c3_slippage",
        "satellite_daily_pnl",
        "satellite_slippage_cost",
        "satellite_margin",
        "satellite_turnover_contracts",
        "held_contract_count",
        "stage101_scale",
        "equity",
        "trade_count",
        "combo_slippage",
    ]
    for col in numeric_cols:
        if col not in frame.columns:
            frame[col] = 0.0
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["variant", "date"])


def _load_satellite() -> pd.DataFrame:
    if not STAGE403_SATELLITE_PATH.exists():
        return pd.DataFrame(columns=["date", "variant", "margin_gate_skipped"])
    frame = pd.read_csv(STAGE403_SATELLITE_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for col in ["margin_gate_skipped", "satellite_turnover_contracts", "held_contract_count", "stage101_scale"]:
        if col not in frame.columns:
            frame[col] = 0.0
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["variant", "date"])


def _calendarize_variant(daily: pd.DataFrame, satellite: pd.DataFrame, variant: str) -> pd.DataFrame:
    raw = daily[daily["variant"].eq(variant)].sort_values("date").drop_duplicates("date", keep="last")
    if raw.empty:
        raise RuntimeError(f"missing variant {variant}")
    calendar = pd.DataFrame({"date": pd.date_range(raw["date"].min(), raw["date"].max(), freq="D")})
    merged = calendar.merge(raw, on="date", how="left")
    merged["variant"] = variant
    merged["equity"] = merged["equity"].ffill()
    zero_cols = [
        "c3_net_pnl",
        "c3_trade_count",
        "c3_slippage",
        "satellite_daily_pnl",
        "satellite_slippage_cost",
        "satellite_turnover_contracts",
        "trade_count",
        "combo_slippage",
    ]
    for col in zero_cols:
        merged[col] = pd.to_numeric(merged.get(col, 0.0), errors="coerce").fillna(0.0)
    ffill_cols = ["satellite_margin", "held_contract_count", "stage101_scale"]
    for col in ffill_cols:
        merged[col] = pd.to_numeric(merged.get(col, 0.0), errors="coerce").ffill().fillna(0.0)
    sat = satellite[satellite["variant"].eq(variant)].groupby("date", as_index=False).agg(
        margin_gate_skipped=("margin_gate_skipped", "sum")
    )
    merged = merged.merge(sat, on="date", how="left")
    merged["margin_gate_skipped"] = pd.to_numeric(merged["margin_gate_skipped"], errors="coerce").fillna(0.0)
    merged["nav"] = merged["equity"] / ACCOUNT_CAPITAL
    merged["running_peak_nav"] = merged["nav"].cummax()
    merged["drawdown_from_full_peak_pct"] = (merged["nav"] / merged["running_peak_nav"] - 1.0) * 100.0
    return merged


def _value_at_or_before(frame: pd.DataFrame, date: pd.Timestamp, col: str) -> float:
    if date < frame["date"].iloc[0]:
        return np.nan
    row = frame[frame["date"].le(date)].tail(1)
    if row.empty:
        return np.nan
    return float(row[col].iloc[0])


def _window_rows(frame: pd.DataFrame, baseline: pd.DataFrame, horizon_days: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    date_to_idx = {date: idx for idx, date in enumerate(frame["date"])}
    baseline_date_to_idx = {date: idx for idx, date in enumerate(baseline["date"])}
    last_start = frame["date"].max() - pd.Timedelta(days=horizon_days)
    for start_idx, start_date in enumerate(frame["date"]):
        if start_date > last_start:
            break
        end_date = start_date + pd.Timedelta(days=horizon_days)
        end_idx = date_to_idx.get(end_date)
        base_start_idx = baseline_date_to_idx.get(start_date)
        base_end_idx = baseline_date_to_idx.get(end_date)
        if end_idx is None or base_start_idx is None or base_end_idx is None:
            continue
        seg = frame.iloc[start_idx : end_idx + 1]
        base_seg = baseline.iloc[base_start_idx : base_end_idx + 1]
        nav = seg["equity"].to_numpy(dtype=float) / float(seg["equity"].iloc[0])
        base_nav = base_seg["equity"].to_numpy(dtype=float) / float(base_seg["equity"].iloc[0])
        dd = _drawdown(nav)
        base_dd = _drawdown(base_nav)
        ret_pct = float((nav[-1] - 1.0) * 100.0)
        base_ret_pct = float((base_nav[-1] - 1.0) * 100.0)
        annualized_pct = float((np.power(max(nav[-1], 1e-12), 365.0 / horizon_days) - 1.0) * 100.0)
        prior20_date = start_date - pd.Timedelta(days=20)
        prior60_date = start_date - pd.Timedelta(days=60)
        prior120_date = start_date - pd.Timedelta(days=120)
        start_equity = float(seg["equity"].iloc[0])
        prior20_equity = _value_at_or_before(frame, prior20_date, "equity")
        prior60_equity = _value_at_or_before(frame, prior60_date, "equity")
        prior120_equity = _value_at_or_before(frame, prior120_date, "equity")
        rows.append(
            {
                "horizon_days": horizon_days,
                "horizon_label": HORIZON_TARGETS[horizon_days]["label"],
                "start_date": start_date,
                "end_date": end_date,
                "start_year": int(start_date.year),
                "start_month": int(start_date.month),
                "return_pct": ret_pct,
                "baseline_return_pct": base_ret_pct,
                "return_vs_stage079_pp": ret_pct - base_ret_pct,
                "annualized_return_pct": annualized_pct,
                "positive_return": int(ret_pct > 0.0),
                "annualized_below_5pct": int(annualized_pct < 5.0),
                "max_dd_pct": float(dd.min() * 100.0),
                "baseline_max_dd_pct": float(base_dd.min() * 100.0),
                "dd20_breach": int(float(dd.min() * 100.0) < -20.0),
                "dd30_breach": int(float(dd.min() * 100.0) < -30.0),
                "ulcer_pct": _ulcer(nav),
                "baseline_ulcer_pct": _ulcer(base_nav),
                "longest_underwater_days": _longest_underwater_days(pd.DatetimeIndex(seg["date"]), nav),
                "baseline_longest_underwater_days": _longest_underwater_days(pd.DatetimeIndex(base_seg["date"]), base_nav),
                "start_full_path_drawdown_pct": float(seg["drawdown_from_full_peak_pct"].iloc[0]),
                "prior20_return_pct": float((start_equity / prior20_equity - 1.0) * 100.0) if prior20_equity > 0 else np.nan,
                "prior60_return_pct": float((start_equity / prior60_equity - 1.0) * 100.0) if prior60_equity > 0 else np.nan,
                "prior120_return_pct": float((start_equity / prior120_equity - 1.0) * 100.0) if prior120_equity > 0 else np.nan,
                "window_c3_pnl": float(seg["c3_net_pnl"].sum()),
                "window_satellite_pnl": float(seg["satellite_daily_pnl"].sum()),
                "window_combo_slippage": float(seg["combo_slippage"].sum()),
                "satellite_active_days": int((seg["held_contract_count"] > 0).sum()),
                "satellite_active_rate": float((seg["held_contract_count"] > 0).mean()),
                "satellite_avg_held_contracts": float(seg["held_contract_count"].mean()),
                "satellite_max_held_contracts": float(seg["held_contract_count"].max()),
                "stage101_scale_start": float(seg["stage101_scale"].iloc[0]),
                "stage101_scale_avg": float(seg["stage101_scale"].mean()),
                "guard_skipped_days": int(seg["margin_gate_skipped"].sum()),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    target = HORIZON_TARGETS[horizon_days]
    result["return_below_target_tail"] = (result["return_pct"] < target["return_p05_pct"]).astype(int)
    result["ulcer_above_target"] = (result["ulcer_pct"] > target["ulcer_p95_pct"]).astype(int)
    result["underwater_above_target"] = (
        result["longest_underwater_days"] > target["longest_underwater_p95_days"]
    ).astype(int)
    result["window_target_fail_count"] = result[
        [
            "return_below_target_tail",
            "annualized_below_5pct",
            "dd20_breach",
            "dd30_breach",
            "ulcer_above_target",
            "underwater_above_target",
        ]
    ].sum(axis=1)
    return_rank = 1.0 - result["return_pct"].rank(pct=True, method="average")
    dd_rank = 1.0 - result["max_dd_pct"].rank(pct=True, method="average")
    ulcer_rank = result["ulcer_pct"].rank(pct=True, method="average")
    underwater_rank = result["longest_underwater_days"].rank(pct=True, method="average")
    result["pain_score"] = 0.35 * return_rank + 0.25 * dd_rank + 0.20 * ulcer_rank + 0.20 * underwater_rank
    result["return_bottom5_group"] = (result["return_pct"] <= result["return_pct"].quantile(0.05)).astype(int)
    result["ulcer_top5_group"] = (result["ulcer_pct"] >= result["ulcer_pct"].quantile(0.95)).astype(int)
    result["underwater_top5_group"] = (
        result["longest_underwater_days"] >= result["longest_underwater_days"].quantile(0.95)
    ).astype(int)
    return result


def _target_gap(windows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon_days, frame in windows.groupby("horizon_days", sort=True):
        target = HORIZON_TARGETS[int(horizon_days)]
        metrics = {
            "return_p05_pct": float(frame["return_pct"].quantile(0.05)),
            "return_median_pct": float(frame["return_pct"].median()),
            "positive_return_rate": float(frame["positive_return"].mean()),
            "annualized_below_5pct_rate": float(frame["annualized_below_5pct"].mean()),
            "max_dd_worst_pct": float(frame["max_dd_pct"].min()),
            "dd20_breach_rate": float(frame["dd20_breach"].mean()),
            "dd30_breach_rate": float(frame["dd30_breach"].mean()),
            "ulcer_p95_pct": float(frame["ulcer_pct"].quantile(0.95)),
            "longest_underwater_p95_days": float(frame["longest_underwater_days"].quantile(0.95)),
        }
        larger_is_better = {"return_p05_pct", "return_median_pct", "positive_return_rate", "max_dd_worst_pct"}
        for metric, actual in metrics.items():
            target_value = target[metric]
            if metric in larger_is_better:
                pass_target = actual >= target_value
                gap = actual - target_value
            else:
                pass_target = actual <= target_value
                gap = target_value - actual
            rows.append(
                {
                    "horizon_days": int(horizon_days),
                    "horizon_label": target["label"],
                    "metric": metric,
                    "actual": actual,
                    "target": target_value,
                    "gap_positive_is_good": gap,
                    "pass_target": int(pass_target),
                }
            )
    return pd.DataFrame(rows)


def _bad_window_contrast(windows: pd.DataFrame) -> pd.DataFrame:
    feature_cols = [
        "return_pct",
        "baseline_return_pct",
        "return_vs_stage079_pp",
        "annualized_return_pct",
        "max_dd_pct",
        "ulcer_pct",
        "longest_underwater_days",
        "start_full_path_drawdown_pct",
        "prior20_return_pct",
        "prior60_return_pct",
        "prior120_return_pct",
        "window_c3_pnl",
        "window_satellite_pnl",
        "satellite_active_rate",
        "stage101_scale_start",
        "stage101_scale_avg",
        "guard_skipped_days",
    ]
    group_defs = {
        "return_bottom5": "return_bottom5_group",
        "dd20_breach": "dd20_breach",
        "ulcer_top5": "ulcer_top5_group",
        "underwater_top5": "underwater_top5_group",
    }
    rows: list[dict[str, Any]] = []
    for horizon_days, frame in windows.groupby("horizon_days", sort=True):
        for group_name, group_col in group_defs.items():
            bad = frame[frame[group_col].eq(1)]
            good = frame[frame[group_col].eq(0)]
            if bad.empty or good.empty:
                continue
            for feature in feature_cols:
                rows.append(
                    {
                        "horizon_days": int(horizon_days),
                        "horizon_label": HORIZON_TARGETS[int(horizon_days)]["label"],
                        "bad_group": group_name,
                        "feature": feature,
                        "bad_mean": float(bad[feature].mean()),
                        "other_mean": float(good[feature].mean()),
                        "bad_minus_other": float(bad[feature].mean() - good[feature].mean()),
                        "bad_count": int(len(bad)),
                        "other_count": int(len(good)),
                    }
                )
    return pd.DataFrame(rows)


def _month_summary(windows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (horizon_days, start_year, start_month), frame in windows.groupby(
        ["horizon_days", "start_year", "start_month"], sort=True
    ):
        rows.append(
            {
                "horizon_days": int(horizon_days),
                "horizon_label": HORIZON_TARGETS[int(horizon_days)]["label"],
                "start_year": int(start_year),
                "start_month": int(start_month),
                "count": int(len(frame)),
                "mean_return_pct": float(frame["return_pct"].mean()),
                "median_return_pct": float(frame["return_pct"].median()),
                "bottom_tail_rate": float(frame["return_below_target_tail"].mean()),
                "annualized_below_5pct_rate": float(frame["annualized_below_5pct"].mean()),
                "dd20_breach_rate": float(frame["dd20_breach"].mean()),
                "ulcer_above_target_rate": float(frame["ulcer_above_target"].mean()),
                "underwater_above_target_rate": float(frame["underwater_above_target"].mean()),
                "mean_satellite_pnl": float(frame["window_satellite_pnl"].mean()),
                "mean_c3_pnl": float(frame["window_c3_pnl"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["horizon_days", "dd20_breach_rate", "bottom_tail_rate"], ascending=[True, False, False])


def _plot(gap: pd.DataFrame, windows: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage404] skip chart: {exc}", flush=True)
        return
    fig, axes = plt.subplots(3, 1, figsize=(13, 10))
    for horizon_days, frame in windows.groupby("horizon_days", sort=True):
        label = f"{int(horizon_days)}d"
        axes[0].hist(frame["return_pct"], bins=60, alpha=0.45, label=label)
        axes[1].hist(frame["max_dd_pct"], bins=60, alpha=0.45, label=label)
    axes[0].axvline(-8.0, color="#d62728", linestyle="--", linewidth=1.0, label="3m target tail")
    axes[0].axvline(0.0, color="#9467bd", linestyle="--", linewidth=1.0, label="6m target tail")
    axes[0].set_title("Stage104 residual holding return distribution")
    axes[0].set_xlabel("Window return %")
    axes[1].axvline(-20.0, color="#d62728", linestyle="--", linewidth=1.0)
    axes[1].set_title("Window max drawdown distribution")
    axes[1].set_xlabel("Window max drawdown %")
    gap_plot = gap.assign(horizon_plot_label=gap["horizon_days"].map(lambda value: f"{int(value)}d"))
    gap_pivot = gap_plot.pivot_table(index="metric", columns="horizon_plot_label", values="gap_positive_is_good", aggfunc="first")
    gap_pivot.plot(kind="bar", ax=axes[2])
    axes[2].axhline(0.0, color="black", linewidth=1.0)
    axes[2].set_title("Positive gap means target passed")
    axes[2].set_ylabel("Gap")
    axes[0].legend(fontsize=8)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    gap: pd.DataFrame,
    worst: pd.DataFrame,
    contrast: pd.DataFrame,
    month_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    contrast_focus = contrast[
        contrast["feature"].isin(
            [
                "return_pct",
                "return_vs_stage079_pp",
                "prior60_return_pct",
                "start_full_path_drawdown_pct",
                "window_c3_pnl",
                "window_satellite_pnl",
                "satellite_active_rate",
                "stage101_scale_avg",
            ]
        )
    ]
    report = [
        "# Stage104 Stage079剩余短持有体验缺口归因",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：只读归因；固定 Stage103 `broker10_guard`，不产生新交易规则。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 目标缺口",
        "",
        _md_table(gap),
        "",
        "## 最痛窗口",
        "",
        _md_table(
            worst[
                [
                    "horizon_label",
                    "start_date",
                    "end_date",
                    "return_pct",
                    "return_vs_stage079_pp",
                    "max_dd_pct",
                    "ulcer_pct",
                    "longest_underwater_days",
                    "prior60_return_pct",
                    "window_c3_pnl",
                    "window_satellite_pnl",
                    "satellite_active_rate",
                    "stage101_scale_avg",
                    "pain_score",
                ]
            ],
            max_rows=24,
        ),
        "",
        "## 坏窗口状态对比",
        "",
        _md_table(contrast_focus, max_rows=80),
        "",
        "## 年月聚类",
        "",
        _md_table(month_summary.head(40)),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段只读取 Stage103 固定候选的滚动窗口，没有增加任何交易规则、阈值或品种筛选。",
        "- 坏窗口归因只用于决定下一阶段研究方向；不得把某个日期、月份或品种直接硬编码进策略。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily = _load_daily()
    satellite = _load_satellite()
    baseline = _calendarize_variant(daily, satellite, BASELINE_VARIANT)
    candidate = _calendarize_variant(daily, satellite, CANDIDATE_VARIANT)
    windows = pd.concat(
        [_window_rows(candidate, baseline, horizon_days) for horizon_days in sorted(HORIZON_TARGETS)],
        ignore_index=True,
    )
    gap = _target_gap(windows)
    worst = windows.sort_values(["horizon_days", "pain_score"], ascending=[True, False]).groupby(
        "horizon_days", as_index=False
    ).head(20)
    contrast = _bad_window_contrast(windows)
    month_summary = _month_summary(windows)

    gap_failed = gap[gap["pass_target"].eq(0)]
    bottom5 = windows[windows["return_bottom5_group"].eq(1)]
    contrast_key = contrast[
        contrast["bad_group"].eq("return_bottom5")
        & contrast["feature"].isin(["window_c3_pnl", "window_satellite_pnl", "return_vs_stage079_pp"])
    ]
    decision = {
        "stage": "Stage104",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "diagnostic_only_no_new_rule",
        "candidate": CANDIDATE_VARIANT,
        "failed_target_metrics": gap_failed[["horizon_label", "metric", "actual", "target"]].to_dict(orient="records"),
        "bottom5_window_count": int(len(bottom5)),
        "key_contrast": contrast_key.to_dict(orient="records"),
        "judgement": "Stage103虽通过晋级分数，但理想目标剩余缺口仍主要集中在短持有左尾和水下恢复；本阶段只做归因，下一步需要新结构，不应继续调Stage103小参数。",
        "chart": str(CHART_PATH),
    }

    gap.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    worst.to_csv(WORST_PATH, index=False, encoding="utf-8-sig")
    contrast.to_csv(CONTRAST_PATH, index=False, encoding="utf-8-sig")
    month_summary.to_csv(MONTH_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(gap, windows)
    _write_report(gap, worst, contrast, month_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
