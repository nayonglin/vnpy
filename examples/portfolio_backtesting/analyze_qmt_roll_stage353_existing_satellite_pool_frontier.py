from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage353_existing_satellite_pool_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage353_existing_satellite_pool_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0

C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage352_xsmom_overlay_cash_multiperiod_combo_daily_"
    "stage352_xsmom_overlay_cash_multiperiod_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

WEIGHTS: tuple[float, ...] = (0.70, 0.75, 0.80, 0.85, 0.90, 0.925, 0.95)

WINDOWS: tuple[str, ...] = (
    "start_2020",
    "start_2021",
    "start_2022",
    "start_2023",
    "start_2024",
    "start_2025",
    "ytd_2026",
    "weak_2021_full",
    "phase_2024_2025",
)


@dataclass(frozen=True)
class SatelliteSpec:
    name: str
    path: Path
    kind: str = "balance"
    balance_col: str = "balance"
    return_col: str = ""
    notes: str = ""


SATELLITES: tuple[SatelliteSpec, ...] = (
    SatelliteSpec(
        "range_v8_two_stage_stop",
        OUTPUT_DIR / "qmt_range_reversion_core4_directed_product_signal_back_adjusted_v8_two_stage_stop_daily.csv",
        notes="已有低相关震荡策略v8",
    ),
    SatelliteSpec(
        "range_v9_short_soft_floor",
        OUTPUT_DIR / "qmt_range_reversion_core4_directed_product_signal_back_adjusted_v9_short_soft_floor_daily_equity.csv",
        notes="震荡策略v9短侧软止损",
    ),
    SatelliteSpec(
        "range_v7_intraday_stop",
        OUTPUT_DIR / "qmt_range_reversion_v7_intraday_stop_daily_equity.csv",
        notes="震荡策略v7日内止损",
    ),
    SatelliteSpec(
        "boll_v5_rsi_extreme",
        OUTPUT_DIR / "qmt_boll_reversal_refactor_v5_rsi_extreme_daily_equity.csv",
        notes="BOLL反转+RSI极值",
    ),
    SatelliteSpec(
        "no_lower_weekly_pullback_ignition",
        OUTPUT_DIR / "qmt_no_lower_shadow_swing_stage009_weekly_pullback_ignition_daily.csv",
        notes="无下影线周线顺势回撤点火",
    ),
    SatelliteSpec(
        "no_upper_twosignalhigh_short",
        OUTPUT_DIR / "qmt_no_upper_shadow_short_swing_stage006_twosignalhigh_daily.csv",
        notes="无上影线短侧波段",
    ),
    SatelliteSpec(
        "pairwise_range150_fast",
        OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_range150_fast_daily_equity.csv",
        notes="pairwise选择器range150快速版",
    ),
    SatelliteSpec(
        "carry_cost20bps",
        OUTPUT_DIR / "qmt_roll_stage343_carry_satellite_screen_satellite_daily_stage343_carry_satellite_screen_v1.csv",
        kind="return",
        return_col="satellite_return_cost20bps",
        notes="期限结构Carry，20bp成本",
    ),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def _path_metrics(nav: pd.Series) -> dict[str, float]:
    values = pd.to_numeric(nav, errors="coerce").dropna().to_numpy(dtype=float)
    if len(values) == 0:
        return {"total_return_pct": 0.0, "max_dd_pct": 0.0, "sharpe": 0.0}
    values = np.concatenate([[1.0], values])
    high = np.maximum.accumulate(values)
    dd = np.divide(values - high, high, out=np.zeros_like(values), where=high != 0.0) * 100.0
    returns = pd.Series(values).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252)) if std > 0 else 0.0
    return {
        "total_return_pct": float((values[-1] - 1.0) * 100.0),
        "max_dd_pct": float(dd.min()),
        "sharpe": sharpe,
    }


def _to_markdown_table(df: pd.DataFrame, float_digits: int = 4) -> str:
    if df.empty:
        return "_无数据_"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        cells: list[str] = []
        for col in cols:
            value = row[col]
            if isinstance(value, float):
                cells.append(f"{value:.{float_digits}f}")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _load_c3_windows() -> dict[str, pd.Series]:
    df = pd.read_csv(C3_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["c3_balance"] = pd.to_numeric(df["c3_balance"], errors="coerce")
    result: dict[str, pd.Series] = {}
    for window_name in WINDOWS:
        part = df[df["window_name"].eq(window_name)].dropna(subset=["c3_balance"]).sort_values("date")
        if part.empty:
            continue
        nav = pd.Series(part["c3_balance"].to_numpy(dtype=float) / C3_CAPITAL, index=part["date"])
        result[window_name] = nav
    return result


def _load_satellite_nav(spec: SatelliteSpec) -> pd.Series:
    if not spec.path.exists():
        return pd.Series(dtype=float)
    df = pd.read_csv(spec.path)
    if "date" not in df.columns:
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    if df.empty:
        return pd.Series(dtype=float)
    if spec.kind == "return":
        if spec.return_col not in df.columns:
            return pd.Series(dtype=float)
        ret = pd.to_numeric(df[spec.return_col], errors="coerce").fillna(0.0)
        nav = (1.0 + ret).cumprod()
    else:
        if spec.balance_col not in df.columns:
            return pd.Series(dtype=float)
        balance = pd.to_numeric(df[spec.balance_col], errors="coerce").ffill()
        first = _safe_float(balance.dropna().iloc[0], 0.0) if not balance.dropna().empty else 0.0
        if first <= 0.0:
            return pd.Series(dtype=float)
        nav = balance / first
    return pd.Series(nav.to_numpy(dtype=float), index=df["date"])


def _align_satellite_to_window(satellite_nav: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    if satellite_nav.empty or len(index) == 0:
        return pd.Series(1.0, index=index)
    aligned = satellite_nav.reindex(index).ffill().fillna(1.0)
    first = _safe_float(aligned.iloc[0], 1.0)
    if first == 0.0:
        return aligned
    return aligned / first


def _retention(candidate_return: float, base_return: float) -> float:
    if base_return <= 0.0:
        return np.nan
    return candidate_return / base_return * 100.0


def _run() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    c3_windows = _load_c3_windows()
    window_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for spec in SATELLITES:
        satellite_nav_full = _load_satellite_nav(spec)
        if satellite_nav_full.empty:
            summary_rows.append(
                {
                    "satellite": spec.name,
                    "status": "missing_or_empty",
                    "notes": spec.notes,
                }
            )
            continue
        for window_name, c3_nav in c3_windows.items():
            sat_nav = _align_satellite_to_window(satellite_nav_full, c3_nav.index)
            c3_metrics = _path_metrics(c3_nav)
            sat_metrics = _path_metrics(sat_nav)
            corr = float(c3_nav.pct_change().fillna(0.0).corr(sat_nav.pct_change().fillna(0.0)))
            for c3_weight in WEIGHTS:
                sat_weight = 1.0 - c3_weight
                combo_nav = c3_weight * c3_nav + sat_weight * sat_nav
                combo_metrics = _path_metrics(combo_nav)
                retention = _retention(combo_metrics["total_return_pct"], c3_metrics["total_return_pct"])
                positive_window = c3_metrics["total_return_pct"] > 0.0
                gate_ok = (
                    combo_metrics["max_dd_pct"] >= TARGET_MAX_DD_PCT
                    and (not positive_window or retention >= RETURN_RETENTION_GATE_PCT)
                )
                window_rows.append(
                    {
                        "satellite": spec.name,
                        "window_name": window_name,
                        "c3_weight": c3_weight,
                        "satellite_weight": sat_weight,
                        "c3_return_pct": c3_metrics["total_return_pct"],
                        "c3_max_dd_pct": c3_metrics["max_dd_pct"],
                        "satellite_return_pct": sat_metrics["total_return_pct"],
                        "satellite_max_dd_pct": sat_metrics["max_dd_pct"],
                        "combo_return_pct": combo_metrics["total_return_pct"],
                        "combo_max_dd_pct": combo_metrics["max_dd_pct"],
                        "combo_sharpe": combo_metrics["sharpe"],
                        "retention_vs_c3_pct": retention,
                        "corr_c3_satellite": corr,
                        "positive_window": int(positive_window),
                        "gate_ok": int(gate_ok),
                        "notes": spec.notes,
                    }
                )

    window_df = pd.DataFrame(window_rows)
    if not window_df.empty:
        for (satellite, c3_weight), group in window_df.groupby(["satellite", "c3_weight"], sort=False):
            positive = group[group["positive_window"].eq(1)].copy()
            full = group[group["window_name"].eq("start_2020")]
            if full.empty:
                continue
            full_row = full.iloc[0]
            pass_count = int(group["gate_ok"].sum())
            positive_pass_count = int(positive["gate_ok"].sum())
            positive_count = int(len(positive))
            all_windows_ok = pass_count == len(group)
            positive_windows_ok = positive_pass_count == positive_count
            summary_rows.append(
                {
                    "satellite": satellite,
                    "status": "evaluated",
                    "c3_weight": c3_weight,
                    "satellite_weight": 1.0 - c3_weight,
                    "window_count": int(len(group)),
                    "gate_pass_count": pass_count,
                    "positive_window_count": positive_count,
                    "positive_gate_pass_count": positive_pass_count,
                    "all_windows_ok": int(all_windows_ok),
                    "positive_windows_ok": int(positive_windows_ok),
                    "full_return_pct": float(full_row["combo_return_pct"]),
                    "full_max_dd_pct": float(full_row["combo_max_dd_pct"]),
                    "full_retention_vs_c3_pct": float(full_row["retention_vs_c3_pct"]),
                    "worst_combo_max_dd_pct": float(group["combo_max_dd_pct"].min()),
                    "min_positive_retention_pct": float(positive["retention_vs_c3_pct"].min()) if not positive.empty else np.nan,
                    "median_corr_c3_satellite": float(group["corr_c3_satellite"].median()),
                    "notes": str(full_row["notes"]),
                }
            )

    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        eval_mask = summary_df["status"].eq("evaluated")
        summary_df.loc[eval_mask, "promotion_score"] = (
            summary_df.loc[eval_mask, "positive_windows_ok"].astype(float) * 1000.0
            + summary_df.loc[eval_mask, "all_windows_ok"].astype(float) * 1000.0
            + summary_df.loc[eval_mask, "min_positive_retention_pct"].fillna(-999.0)
            + summary_df.loc[eval_mask, "worst_combo_max_dd_pct"].fillna(-999.0)
        )
        summary_df["promotion_score"] = summary_df["promotion_score"].fillna(-9999.0)
        summary_df = summary_df.sort_values(
            [
                "all_windows_ok",
                "positive_windows_ok",
                "gate_pass_count",
                "positive_gate_pass_count",
                "worst_combo_max_dd_pct",
                "min_positive_retention_pct",
                "full_retention_vs_c3_pct",
            ],
            ascending=[False, False, False, False, False, False, False],
        )

    passed = summary_df[
        summary_df.get("status", pd.Series(dtype=str)).eq("evaluated")
        & summary_df.get("all_windows_ok", pd.Series(dtype=int)).eq(1)
        & summary_df.get("positive_windows_ok", pd.Series(dtype=int)).eq(1)
    ].copy()
    if passed.empty:
        decision = {
            "decision": "no_existing_satellite_netvalue_candidate",
            "reason": "no existing satellite passed all net-value windows under coarse weights",
        }
    else:
        best = passed.iloc[0].to_dict()
        decision = {
            "decision": "netvalue_candidate_requires_true_capital_validation",
            "best": best,
            "reason": "net-value pass is only a direction screen; true capital, margin, and integer-lot validation still required",
        }
    return summary_df, window_df, decision


def _build_report(summary_df: pd.DataFrame, window_df: pd.DataFrame, decision: dict[str, Any]) -> str:
    top = summary_df[summary_df["status"].eq("evaluated")].head(20).copy() if not summary_df.empty else pd.DataFrame()
    top_cols = [
        "satellite",
        "c3_weight",
        "satellite_weight",
        "gate_pass_count",
        "positive_gate_pass_count",
        "full_return_pct",
        "full_max_dd_pct",
        "full_retention_vs_c3_pct",
        "worst_combo_max_dd_pct",
        "min_positive_retention_pct",
        "median_corr_c3_satellite",
    ]
    top = top[[c for c in top_cols if c in top.columns]] if not top.empty else top
    fail_focus = window_df[
        window_df["gate_ok"].eq(0)
        & window_df["c3_weight"].isin((0.80, 0.85, 0.90))
    ].copy() if not window_df.empty else pd.DataFrame()
    fail_focus = fail_focus[
        [
            "satellite",
            "window_name",
            "c3_weight",
            "combo_return_pct",
            "combo_max_dd_pct",
            "retention_vs_c3_pct",
            "corr_c3_satellite",
        ]
    ].head(40) if not fail_focus.empty else fail_focus
    lines = [
        "# Stage353 现有卫星净值层低相关方向筛查",
        "",
        "## 目标",
        "",
        "- 不新增策略参数，不改 C3，不重跑入场逻辑。",
        "- 只用已有卫星日收益/净值，做粗权重净值层组合，判断是否值得进入真实资金复验。",
        "- 该阶段不是正式候选；净值层过关也必须再做保证金、整数手数、滑点和多起点真实引擎验证。",
        "",
        "## 阶段判断",
        "",
        f"- 决策：`{decision.get('decision')}`。",
        f"- 原因：{decision.get('reason')}",
        "",
        "## Top净值层组合",
        "",
        _to_markdown_table(top),
        "",
        "## 典型失败窗口",
        "",
        _to_markdown_table(fail_focus),
        "",
        "## 过拟合反思",
        "",
        "- 本阶段不是过拟合，因为卫星池只来自既有研究产物，权重为粗档位，且只作为方向筛查。",
        "- 若看到某个净值组合好看后直接调权重小数或宣称可实盘，就是过拟合和执行口径偷换。",
        "",
        "## 继续价值反思",
        "",
        "- 若没有净值层候选，本方向应降级；若有候选，下一步只做真实资金复验，不继续扫权重小数。",
    ]
    return "\n".join(lines)


def main() -> None:
    summary_df, window_df, decision = _run()
    summary_df.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    window_df.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(summary_df, window_df, decision), encoding="utf-8")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage353] summary={SUMMARY_PATH}")
    print(f"[stage353] window={WINDOW_PATH}")
    print(f"[stage353] report={REPORT_PATH}")
    print(f"[stage353] decision={DECISION_PATH}")
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
