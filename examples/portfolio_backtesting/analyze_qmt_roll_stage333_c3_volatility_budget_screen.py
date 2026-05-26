from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import _to_builtin, _to_markdown_table
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage333_c3_volatility_budget_screen_v1"
OUTPUT_PREFIX = "qmt_roll_stage333_c3_volatility_budget_screen"
LINE_ID = "futures_trend_drawdown30_preserve_return"

TOTAL_CAPITAL = 500_000.0
BASELINE_VARIANT = "A_c3_supply_headwind"
BASELINE_RETURN_PCT = 6085.129999999999
BASELINE_DD_PCT = -31.076697649967006

SOURCE_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage332_c3_existing_position_release_screen_daily_"
    "stage332_c3_existing_position_release_screen_v1.csv"
)

LOOKBACKS: tuple[int, ...] = (20, 60, 120)
TARGET_ANNUAL_VOLS: tuple[float, ...] = (0.50, 0.60, 0.70)


@dataclass(frozen=True)
class Window:
    name: str
    start: str
    end: str


WINDOWS: tuple[Window, ...] = (
    Window("full_2020_2026", "2020-01-01", "2026-04-30"),
    Window("start_2021", "2021-01-01", "2026-04-30"),
    Window("start_2022", "2022-01-01", "2026-04-30"),
    Window("start_2023", "2023-01-01", "2026-04-30"),
    Window("start_2024", "2024-01-01", "2026-04-30"),
    Window("weak_2021_drawdown", "2021-05-01", "2021-08-31"),
)


def _path_metrics(equity: pd.Series, *, initial_capital: float = TOTAL_CAPITAL) -> dict[str, float]:
    arr = pd.to_numeric(equity, errors="coerce").ffill().dropna().to_numpy(dtype=float)
    if len(arr) == 0:
        return {
            "end_equity": initial_capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
        }
    high = np.maximum.accumulate(arr)
    drawdown = arr - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0.0) * 100.0
    returns = pd.Series(arr).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252.0)) if std > 0 else 0.0
    return {
        "end_equity": float(arr[-1]),
        "total_return_pct": float((arr[-1] / initial_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "max_drawdown": float(drawdown.min()),
        "sharpe_ratio": sharpe,
    }


def _load_c3_daily() -> pd.DataFrame:
    df = pd.read_csv(SOURCE_DAILY_PATH)
    df = df[df["variant"].eq(BASELINE_VARIANT)].copy()
    if df.empty:
        raise RuntimeError(f"Missing baseline variant {BASELINE_VARIANT} in {SOURCE_DAILY_PATH}")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    for col in ("balance", "net_pnl", "slippage", "trade_count"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    previous_balance = df["balance"].shift(1).fillna(TOTAL_CAPITAL).replace(0.0, np.nan).ffill()
    df["base_daily_return"] = (df["net_pnl"] / previous_balance).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    df["baseline_equity_linear"] = TOTAL_CAPITAL * (1.0 + df["base_daily_return"]).cumprod()
    return df


def _simulate_window(
    window_df: pd.DataFrame,
    *,
    lookback: int | None,
    target_annual_vol: float | None,
) -> pd.DataFrame:
    frame = window_df.copy().reset_index(drop=True)
    raw_return = frame["base_daily_return"].astype(float)
    if lookback is None or target_annual_vol is None:
        frame["risk_scale"] = 1.0
        frame["policy_equity"] = TOTAL_CAPITAL * (1.0 + raw_return).cumprod()
        return frame

    realized_vol = raw_return.rolling(lookback).std(ddof=1).shift(1) * np.sqrt(252.0)
    scale = target_annual_vol / realized_vol
    scale = scale.replace([np.inf, -np.inf], 1.0).fillna(1.0).clip(lower=0.0, upper=1.0)
    scaled_return = raw_return * scale
    frame["risk_scale"] = scale.astype(float)
    frame["policy_equity"] = TOTAL_CAPITAL * (1.0 + scaled_return).cumprod()
    return frame


def _build_rows() -> tuple[pd.DataFrame, pd.DataFrame]:
    source = _load_c3_daily()
    rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []

    for window in WINDOWS:
        window_df = source[
            source["date"].ge(pd.Timestamp(window.start))
            & source["date"].le(pd.Timestamp(window.end))
        ].copy()
        if window_df.empty:
            continue

        baseline = _simulate_window(window_df, lookback=None, target_annual_vol=None)
        baseline_metrics = _path_metrics(baseline["policy_equity"])
        baseline_return = float(baseline_metrics["total_return_pct"])
        baseline_dd = float(baseline_metrics["max_dd_percent"])
        base_row = {
            "window_name": window.name,
            "variant": "A_c3_daily_linear",
            "lookback": 0,
            "target_annual_vol": 0.0,
            "avg_risk_scale": 1.0,
            "min_risk_scale": 1.0,
            "risk_scaled_day_count": 0,
            "estimated_total_slippage": float(window_df["slippage"].sum()),
            "total_trade_count": float(window_df["trade_count"].sum()),
            **baseline_metrics,
            "baseline_return_pct": baseline_return,
            "return_retention_pct": 100.0,
            "baseline_max_dd_pct": baseline_dd,
            "max_dd_improvement_vs_baseline_pct": 0.0,
            "dd_ok": int(baseline_dd >= -30.0),
            "return_ok": 1,
            "strict_pass": 0,
            "research_pass": 0,
        }
        rows.append(base_row)
        curve_frames.append(
            pd.DataFrame(
                {
                    "date": baseline["date"],
                    "window_name": window.name,
                    "variant": "A_c3_daily_linear",
                    "equity": baseline["policy_equity"],
                    "risk_scale": baseline["risk_scale"],
                }
            )
        )

        for lookback in LOOKBACKS:
            for target in TARGET_ANNUAL_VOLS:
                sim = _simulate_window(window_df, lookback=lookback, target_annual_vol=target)
                metrics = _path_metrics(sim["policy_equity"])
                risk_scale = sim["risk_scale"].astype(float)
                retention = (
                    float(metrics["total_return_pct"]) / baseline_return * 100.0
                    if baseline_return > 0
                    else 0.0
                )
                dd_improvement = float(metrics["max_dd_percent"]) - baseline_dd
                scaled_slippage = float((window_df["slippage"].to_numpy(dtype=float) * risk_scale.to_numpy(dtype=float)).sum())
                variant = f"C_vol_budget_lb{lookback}_target{int(target * 100):02d}"
                row = {
                    "window_name": window.name,
                    "variant": variant,
                    "lookback": lookback,
                    "target_annual_vol": target,
                    "avg_risk_scale": float(risk_scale.mean()),
                    "min_risk_scale": float(risk_scale.min()),
                    "risk_scaled_day_count": int((risk_scale < 0.999999).sum()),
                    "estimated_total_slippage": scaled_slippage,
                    "total_trade_count": float(window_df["trade_count"].sum()),
                    **metrics,
                    "baseline_return_pct": baseline_return,
                    "return_retention_pct": retention,
                    "baseline_max_dd_pct": baseline_dd,
                    "max_dd_improvement_vs_baseline_pct": dd_improvement,
                    "dd_ok": int(float(metrics["max_dd_percent"]) >= -30.0),
                    "return_ok": int(retention >= 80.0),
                    "strict_pass": int(float(metrics["max_dd_percent"]) >= -30.0 and retention >= 80.0),
                    "research_pass": int(float(metrics["max_dd_percent"]) >= -30.0 and retention >= 70.0),
                }
                rows.append(row)
                curve_frames.append(
                    pd.DataFrame(
                        {
                            "date": sim["date"],
                            "window_name": window.name,
                            "variant": variant,
                            "equity": sim["policy_equity"],
                            "risk_scale": sim["risk_scale"],
                        }
                    )
                )

    return pd.DataFrame(rows), pd.concat(curve_frames, ignore_index=True)


def _candidate_stability(summary: pd.DataFrame) -> pd.DataFrame:
    candidates = summary[~summary["variant"].eq("A_c3_daily_linear")].copy()
    rows: list[dict[str, Any]] = []
    for variant, group in candidates.groupby("variant", sort=False):
        full = group[group["window_name"].eq("full_2020_2026")]
        nonweak = group[~group["window_name"].eq("weak_2021_drawdown")]
        positive_windows = nonweak[nonweak["baseline_return_pct"].gt(0)].copy()
        rows.append(
            {
                "variant": variant,
                "lookback": int(group["lookback"].iloc[0]),
                "target_annual_vol": float(group["target_annual_vol"].iloc[0]),
                "full_return_pct": float(full["total_return_pct"].iloc[0]) if not full.empty else 0.0,
                "full_return_retention_pct": float(full["return_retention_pct"].iloc[0]) if not full.empty else 0.0,
                "full_max_dd_percent": float(full["max_dd_percent"].iloc[0]) if not full.empty else 0.0,
                "full_strict_pass": int(full["strict_pass"].iloc[0]) if not full.empty else 0,
                "positive_window_count": int(len(positive_windows)),
                "positive_window_strict_pass_count": int(positive_windows["strict_pass"].sum()),
                "min_positive_window_retention_pct": float(positive_windows["return_retention_pct"].min())
                if not positive_windows.empty
                else 0.0,
                "max_positive_window_dd_pct": float(positive_windows["max_dd_percent"].min())
                if not positive_windows.empty
                else 0.0,
                "avg_risk_scale_full": float(full["avg_risk_scale"].iloc[0]) if not full.empty else 0.0,
                "min_risk_scale_full": float(full["min_risk_scale"].iloc[0]) if not full.empty else 0.0,
            }
        )
    stability = pd.DataFrame(rows)
    stability["all_positive_windows_pass"] = (
        stability["positive_window_count"].gt(0)
        & stability["positive_window_strict_pass_count"].eq(stability["positive_window_count"])
    ).astype(int)
    stability["promotion_screen_pass"] = (
        stability["full_strict_pass"].eq(1) & stability["all_positive_windows_pass"].eq(1)
    ).astype(int)
    return stability.sort_values(
        [
            "promotion_screen_pass",
            "full_strict_pass",
            "positive_window_strict_pass_count",
            "full_return_retention_pct",
            "full_max_dd_percent",
        ],
        ascending=[False, False, False, False, False],
    )


def _build_report(summary: pd.DataFrame, stability: pd.DataFrame) -> str:
    full = summary[summary["window_name"].eq("full_2020_2026")].copy()
    full = full.sort_values(
        ["strict_pass", "return_retention_pct", "max_dd_percent"],
        ascending=[False, False, False],
    )
    windows = summary[summary["variant"].isin(stability.head(5)["variant"].tolist() + ["A_c3_daily_linear"])]
    windows = windows.sort_values(["variant", "window_name"])
    pass_rows = stability[stability["promotion_screen_pass"].eq(1)]
    if pass_rows.empty:
        decision = "screen_fail_no_stable_daily_candidate"
        decision_text = "- 没有候选同时通过全样本和正收益多起点窗口；波动率预算只能保留为研究线索。"
    else:
        decision = "daily_screen_candidate_requires_real_engine"
        best = pass_rows.iloc[0]
        decision_text = (
            f"- 日收益层出现候选 `{best['variant']}`：全样本收益保留 "
            f"`{best['full_return_retention_pct']:.4f}%`，最大回撤 `{best['full_max_dd_percent']:.4f}%`。"
            " 这还不是正式候选，必须进入真实引擎验证整数手数、保证金和持仓调整。"
        )

    lines = [
        "# Stage033 C3波动率预算日收益层筛查",
        "",
        "## 目标",
        "",
        "- A：C3原始日收益路径。",
        "- C：只用策略自身过去收益波动率做风险预算；高波动时降风险，低波动时不加杠杆。",
        "- 通过标准：全样本最大回撤进入30%以内，收益保留不低于80%；同时正收益起点窗口也需要满足同一条件。",
        "- 注意：这是日收益层筛查，不是最终真实引擎结论。",
        "",
        "## 全样本结果",
        "",
        _to_markdown_table(
            full[
                [
                    "variant",
                    "total_return_pct",
                    "return_retention_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "avg_risk_scale",
                    "min_risk_scale",
                    "risk_scaled_day_count",
                    "strict_pass",
                ]
            ].head(12),
            max_rows=12,
        ),
        "",
        "## 候选稳定性",
        "",
        _to_markdown_table(
            stability[
                [
                    "variant",
                    "full_return_retention_pct",
                    "full_max_dd_percent",
                    "positive_window_strict_pass_count",
                    "positive_window_count",
                    "min_positive_window_retention_pct",
                    "max_positive_window_dd_pct",
                    "promotion_screen_pass",
                ]
            ].head(12),
            max_rows=12,
        ),
        "",
        "## 多窗口明细",
        "",
        _to_markdown_table(
            windows[
                [
                    "variant",
                    "window_name",
                    "total_return_pct",
                    "return_retention_pct",
                    "max_dd_percent",
                    "avg_risk_scale",
                    "strict_pass",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 阶段判断",
        "",
        f"- 决策标签：`{decision}`。",
        decision_text,
        "",
        "## 过拟合反思",
        "",
        "- 运行前：不是过拟合。候选只用自身历史波动率，使用标准20/60/120日窗口和50/60/70%年化目标，不使用品种黑名单或特定日期补丁。",
        "- 运行后：若全窗口不稳，不继续调成57%、63%或35日这类小数；若通过，也只能进入真实引擎，不直接晋级。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前：有价值。外部趋势策略资料和本地回撤归因都指向组合风险预算，而不是新增开仓过滤。",
        "- 运行后：继续价值取决于是否出现多窗口稳定候选；若出现，下一步是实盘可执行的真实引擎验证。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    summary, curves = _build_rows()
    stability = _candidate_stability(summary)
    report = _build_report(summary, stability)

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    stability_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stability_{MODEL_TAG}.csv"
    curves_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    stability.to_csv(stability_path, index=False, encoding="utf-8-sig")
    curves.to_csv(curves_path, index=False, encoding="utf-8-sig")
    report_path.write_text(report, encoding="utf-8")

    pass_rows = stability[stability["promotion_screen_pass"].eq(1)]
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_daily": str(SOURCE_DAILY_PATH),
        "decision": "daily_screen_candidate_requires_real_engine"
        if not pass_rows.empty
        else "screen_fail_no_stable_daily_candidate",
        "pass_count": int(len(pass_rows)),
        "best_variant": str(pass_rows.iloc[0]["variant"]) if not pass_rows.empty else "",
        "summary": str(summary_path),
        "stability": str(stability_path),
        "curves": str(curves_path),
        "report": str(report_path),
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
