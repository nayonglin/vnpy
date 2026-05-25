from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_CAPITAL, OFFICIAL_STAGE78_VERSION
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage304_cash_buffer_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage304_cash_buffer_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE302_CURVES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage302_stage78_1_full_deleverage_pressure_frontier_curves_"
    "stage302_stage78_1_full_deleverage_pressure_frontier_v1.csv"
)


@dataclass(frozen=True)
class SourceVariant:
    variant: str
    label: str


SOURCE_VARIANTS: tuple[SourceVariant, ...] = (
    SourceVariant("A_baseline_78_1", "78-1正式基准"),
    SourceVariant("C_full_delev_pressure040", "热度降暴露0.40"),
)

CASH_WEIGHTS: tuple[float, ...] = (1.00, 0.98, 0.95, 0.92, 0.90, 0.85, 0.80, 0.75)


def _path_metrics(equity: pd.Series, *, initial_capital: float = OFFICIAL_STAGE78_CAPITAL) -> dict[str, float]:
    arr = equity.to_numpy(dtype=float)
    high = np.maximum.accumulate(arr)
    drawdown = arr - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0) * 100.0
    returns = pd.Series(arr).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252)) if std > 0 else 0.0
    return {
        "end_equity": float(arr[-1]),
        "total_return_pct": float((arr[-1] / initial_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "max_drawdown": float(drawdown.min()),
        "sharpe_ratio": sharpe,
    }


def _load_curves() -> pd.DataFrame:
    df = pd.read_csv(STAGE302_CURVES_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    df = df.dropna(subset=["balance"]).copy()
    return df


def _simulate_cash_buffer(curves_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, float | str]] = []
    curve_frames: list[pd.DataFrame] = []
    for window_name, window_df in curves_df.groupby("window_name", sort=False):
        baseline_rows: dict[str, float] = {}
        for source in SOURCE_VARIANTS:
            source_df = window_df[window_df["variant"].eq(source.variant)].copy()
            if source_df.empty:
                continue
            source_df = source_df.sort_values("date").reset_index(drop=True)
            source_nav = source_df["balance"] / OFFICIAL_STAGE78_CAPITAL
            for weight in CASH_WEIGHTS:
                buffered_nav = (1.0 - weight) + weight * source_nav
                buffered_equity = buffered_nav * OFFICIAL_STAGE78_CAPITAL
                policy_name = f"{source.variant}_cash_weight_{weight:.2f}"
                curve = pd.DataFrame(
                    {
                        "date": source_df["date"],
                        "window_name": window_name,
                        "source_variant": source.variant,
                        "source_label": source.label,
                        "cash_weight": weight,
                        "cash_buffer_pct": (1.0 - weight) * 100.0,
                        "policy": policy_name,
                        "total_equity": buffered_equity,
                    }
                )
                metrics = _path_metrics(buffered_equity)
                row = {
                    "window_name": window_name,
                    "source_variant": source.variant,
                    "source_label": source.label,
                    "cash_weight": weight,
                    "cash_buffer_pct": (1.0 - weight) * 100.0,
                    "policy": policy_name,
                    **metrics,
                }
                rows.append(row)
                curve_frames.append(curve)
                if source.variant == "A_baseline_78_1" and abs(weight - 1.0) < 1e-9:
                    baseline_rows[window_name] = float(metrics["total_return_pct"])
        for row in rows:
            if row["window_name"] == window_name:
                baseline_return = baseline_rows.get(window_name, 0.0)
                candidate_return = float(row["total_return_pct"])
                row["return_retention_pct"] = candidate_return / baseline_return * 100.0 if baseline_return > 0 else 0.0
                row["strict_pass"] = int(float(row["max_dd_percent"]) >= -30.0 and float(row["return_retention_pct"]) >= 80.0)
                row["research_pass"] = int(float(row["max_dd_percent"]) >= -30.0 and float(row["return_retention_pct"]) >= 65.0)
    return pd.DataFrame(rows), pd.concat(curve_frames, ignore_index=True)


def _build_report(summary_df: pd.DataFrame) -> str:
    full = summary_df[summary_df["window_name"].eq("full_2020_2026")].copy()
    full = full.sort_values(
        ["strict_pass", "research_pass", "return_retention_pct", "max_dd_percent"],
        ascending=[False, False, False, False],
    )
    ytd = summary_df[summary_df["window_name"].eq("ytd_2026")].copy()
    ytd = ytd.sort_values(["source_variant", "cash_weight"], ascending=[True, False])
    lines = [
        "# Stage304 第78-1资金分层/现金缓冲前沿",
        "",
        "## 目标",
        "",
        "- 输入：Stage302 的78-1正式基准与热度降暴露0.40日权益曲线。",
        "- C：账户层现金缓冲，不修改alpha、品种池、入场逻辑或撮合规则。",
        "- 含义：总权益中只让一部分参与策略风险暴露，其余作为现金缓冲；这是理论边界，后续若采用必须落到真实账户资金制度。",
        "- 严格通过：全样本最大回撤小于30%，收益保留不低于80%。",
        "- 研究通过：全样本最大回撤小于30%，收益保留不低于65%。",
        "",
        "## 全样本前沿",
        "",
        full[
            [
                "source_variant",
                "source_label",
                "cash_weight",
                "cash_buffer_pct",
                "total_return_pct",
                "return_retention_pct",
                "max_dd_percent",
                "sharpe_ratio",
                "strict_pass",
                "research_pass",
            ]
        ].to_markdown(index=False),
        "",
        "## 2026年初至今窗口",
        "",
        ytd[
            [
                "source_variant",
                "source_label",
                "cash_weight",
                "cash_buffer_pct",
                "total_return_pct",
                "max_dd_percent",
                "sharpe_ratio",
            ]
        ].to_markdown(index=False),
        "",
        "## 阶段判断",
        "",
    ]
    pass_rows = full[full["strict_pass"].eq(1)]
    if pass_rows.empty:
        lines.append("- 没有严格通过候选。")
    else:
        best = pass_rows.iloc[0]
        lines.append(
            f"- 出现严格通过账户层候选：`{best['policy']}`，收益保留 `{best['return_retention_pct']:.2f}%`，最大回撤 `{best['max_dd_percent']:.2f}%`。"
        )
        lines.append("- 这不是策略alpha优化，而是账户总资金视角的风险预算；后续需要用真实执行口径确认保证金、手数离散和日报账本。")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curves_df = _load_curves()
    summary_df, buffered_curves_df = _simulate_cash_buffer(curves_df)

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    curves_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    buffered_curves_df.to_csv(curves_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(summary_df), encoding="utf-8")

    full = summary_df[summary_df["window_name"].eq("full_2020_2026")].copy()
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "input_curves": str(STAGE302_CURVES_PATH),
        "strict_pass_count": int(full["strict_pass"].sum()) if not full.empty else 0,
        "research_pass_count": int(full["research_pass"].sum()) if not full.empty else 0,
        "best_strict_pass": full[full["strict_pass"].eq(1)]
        .sort_values(["return_retention_pct", "max_dd_percent"], ascending=[False, False])
        .head(5)
        .to_dict(orient="records"),
        "best_by_drawdown": full.sort_values(["max_dd_percent", "return_retention_pct"], ascending=[False, False])
        .head(5)
        .to_dict(orient="records"),
        "paths": {
            "summary": str(summary_path),
            "curves": str(curves_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage304] summary={summary_path}")
    print(f"[stage304] curves={curves_path}")
    print(f"[stage304] report={report_path}")
    print(f"[stage304] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
