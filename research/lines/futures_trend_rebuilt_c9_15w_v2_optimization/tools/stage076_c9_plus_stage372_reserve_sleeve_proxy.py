from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage076"
MODEL_TAG = "stage076_c9_plus_stage372_reserve_sleeve_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage076_c9_plus_stage372_reserve_sleeve_proxy"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage076_c9_plus_stage372_reserve_sleeve_proxy"
STAGES_DIR = LINE_DIR / "stages"

C9_CURVES_PATH = (
    ROOT
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
STAGE372_CURVES_PATH = (
    LINE_DIR
    / "outputs"
    / "stage017_fixed_sleeve_blend_audit"
    / "rebuilt_c9_v2_stage017_fixed_sleeve_blend_audit_official_stage372_curves_stage017_fixed_sleeve_blend_audit_v1.csv"
)

TOTAL_CAPITAL = 300_000.0
C9_CAPITAL = 150_000.0
RESERVE_CAPITAL = 150_000.0
STAGE372_SOURCE_CAPITAL = 200_000.0
REQUESTED_END = pd.Timestamp("2026-06-30")
SLEEVE_CAPITALS = (0.0, 30_000.0, 60_000.0, 90_000.0, 120_000.0, 150_000.0)

CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
RETENTION_PATH = OUT / f"{OUTPUT_PREFIX}_retention_vs_official_c9_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_underwater_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    return value


def _md_table(frame: pd.DataFrame) -> str:
    return "_empty_" if frame.empty else frame.to_markdown(index=False)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _max_consecutive_true(mask: pd.Series) -> int:
    best = current = 0
    for value in mask.astype(bool).tolist():
        current = current + 1 if value else 0
        best = max(best, current)
    return int(best)


def _daily_sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0 or not np.isfinite(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _read_c9() -> pd.DataFrame:
    frame = pd.read_csv(C9_CURVES_PATH)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["date"].le(REQUESTED_END)].copy()
    frame["requested_start_month"] = frame["requested_start_month"].astype(str)
    frame["c9_equity"] = pd.to_numeric(frame["account_equity"], errors="coerce")
    return frame[["requested_start_month", "date", "c9_equity"]].dropna()


def _read_stage372() -> pd.DataFrame:
    frame = pd.read_csv(STAGE372_CURVES_PATH)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["date"].le(REQUESTED_END)].copy()
    frame["requested_start_month"] = frame["requested_start_month"].astype(str)
    frame["stage372_equity"] = pd.to_numeric(frame["account_equity"], errors="coerce")
    return frame[["requested_start_month", "date", "stage372_equity"]].dropna()


def _summarize(group: pd.DataFrame, *, version: str, capital: float) -> dict[str, Any]:
    data = group.sort_values("date").drop_duplicates("date").copy()
    equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
    dd = _drawdown_pct(equity)
    below = equity < capital - 1e-9
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "version": version,
        "variant_label": str(data["variant_label"].iloc[0]),
        "requested_start_month": str(data["requested_start_month"].iloc[0]),
        "actual_start": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
        "actual_end": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(data)),
        "account_capital": capital,
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / capital - 1.0) * 100.0),
        "max_drawdown_pct": float(dd.min()),
        "sharpe": _daily_sharpe(equity),
        "min_equity": float(equity.min()),
        "days_below_initial": int(below.sum()),
        "max_consecutive_below_initial_days": _max_consecutive_true(below),
    }


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    c9 = _read_c9()
    stage372 = _read_stage372()
    starts = sorted(set(c9["requested_start_month"]) & set(stage372["requested_start_month"]))
    c9 = c9[c9["requested_start_month"].isin(starts)].copy()
    stage372 = stage372[stage372["requested_start_month"].isin(starts)].copy()
    merged = c9.merge(stage372, on=["requested_start_month", "date"], how="inner").sort_values(
        ["requested_start_month", "date"]
    )

    curve_parts: list[pd.DataFrame] = []
    for start_month, group in merged.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").drop_duplicates("date").copy()
        official = pd.DataFrame(
            {
                "requested_start_month": start_month,
                "date": g["date"],
                "version": "official_c9_15w_reference",
                "variant_label": "Official C9 15w reference",
                "account_capital_for_metrics": C9_CAPITAL,
                "account_equity_for_metrics": g["c9_equity"],
                "c9_equity": g["c9_equity"],
                "stage372_equity_scaled": np.nan,
                "idle_cash": np.nan,
                "sleeve_capital": 0.0,
            }
        )
        curve_parts.append(official)
        for sleeve_capital in SLEEVE_CAPITALS:
            idle_cash = RESERVE_CAPITAL - sleeve_capital
            stage372_scaled = sleeve_capital * (g["stage372_equity"] / STAGE372_SOURCE_CAPITAL)
            total_equity = g["c9_equity"] + idle_cash + stage372_scaled
            label = f"C9 15w + Stage372 reserve sleeve {sleeve_capital / 10000:.0f}w"
            variant = f"c9_15w_plus_stage372_sleeve_{int(sleeve_capital):06d}"
            curve_parts.append(
                pd.DataFrame(
                    {
                        "requested_start_month": start_month,
                        "date": g["date"],
                        "version": variant,
                        "variant_label": label,
                        "account_capital_for_metrics": TOTAL_CAPITAL,
                        "account_equity_for_metrics": total_equity,
                        "c9_equity": g["c9_equity"],
                        "stage372_equity_scaled": stage372_scaled,
                        "idle_cash": idle_cash,
                        "sleeve_capital": sleeve_capital,
                    }
                )
            )
    curves = pd.concat(curve_parts, ignore_index=True, sort=False)
    curves["stage"] = STAGE
    curves["model_tag"] = MODEL_TAG
    curves["line_id"] = LINE_ID
    curves["requested_end"] = REQUESTED_END.date().isoformat()
    curves.to_csv(CURVES_PATH, index=False)

    summary = pd.DataFrame(
        [
            _summarize(group, version=str(version), capital=float(group["account_capital_for_metrics"].iloc[0]))
            for version, by_version in curves.groupby("version", sort=False)
            for _, group in by_version.groupby("requested_start_month", sort=True)
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False)

    official_summary = summary[summary["version"].eq("official_c9_15w_reference")][
        ["requested_start_month", "total_return_pct", "max_drawdown_pct", "days_below_initial", "max_consecutive_below_initial_days"]
    ].rename(
        columns={
            "total_return_pct": "official_return_pct",
            "max_drawdown_pct": "official_max_drawdown_pct",
            "days_below_initial": "official_days_below_initial",
            "max_consecutive_below_initial_days": "official_max_consecutive_below_initial_days",
        }
    )
    retention = summary[~summary["version"].eq("official_c9_15w_reference")].merge(
        official_summary, on="requested_start_month", how="left"
    )
    retention["return_retention_ratio"] = retention["total_return_pct"] / retention["official_return_pct"].replace(0.0, np.nan)
    retention["drawdown_improvement_pp"] = retention["max_drawdown_pct"] - retention["official_max_drawdown_pct"]
    retention["days_below_delta"] = retention["days_below_initial"] - retention["official_days_below_initial"]
    retention["max_consecutive_below_delta"] = (
        retention["max_consecutive_below_initial_days"] - retention["official_max_consecutive_below_initial_days"]
    )
    retention.to_csv(RETENTION_PATH, index=False)

    variant_rows: list[dict[str, Any]] = []
    for version, group in summary.groupby("version", sort=False):
        ret = retention[retention["version"].eq(version)]
        variant_rows.append(
            {
                "version": version,
                "variant_label": str(group["variant_label"].iloc[0]),
                "start_count": int(group["requested_start_month"].nunique()),
                "positive_count": int(group["total_return_pct"].gt(0).sum()),
                "min_return_pct": float(group["total_return_pct"].min()),
                "median_return_pct": float(group["total_return_pct"].median()),
                "max_return_pct": float(group["total_return_pct"].max()),
                "min_return_retention_ratio": 1.0 if version == "official_c9_15w_reference" else float(ret["return_retention_ratio"].min()),
                "median_return_retention_ratio": 1.0 if version == "official_c9_15w_reference" else float(ret["return_retention_ratio"].median()),
                "worst_drawdown_pct": float(group["max_drawdown_pct"].min()),
                "median_drawdown_pct": float(group["max_drawdown_pct"].median()),
                "max_days_below_initial": int(group["days_below_initial"].max()),
                "median_days_below_initial": float(group["days_below_initial"].median()),
                "max_consecutive_below_initial_days": int(group["max_consecutive_below_initial_days"].max()),
                "median_consecutive_below_initial_days": float(group["max_consecutive_below_initial_days"].median()),
            }
        )
    variant_summary = pd.DataFrame(variant_rows)
    variant_summary.to_csv(VARIANT_SUMMARY_PATH, index=False)

    official_row = variant_summary[variant_summary["version"].eq("official_c9_15w_reference")].iloc[0]
    candidates = variant_summary[~variant_summary["version"].eq("official_c9_15w_reference")].copy()
    candidates["passes_new_goal"] = (
        candidates["min_return_retention_ratio"].ge(0.5 - 1e-9)
        & candidates["worst_drawdown_pct"].gt(float(official_row["worst_drawdown_pct"]))
        & candidates["max_days_below_initial"].le(int(official_row["max_days_below_initial"]))
        & candidates["max_consecutive_below_initial_days"].lt(int(official_row["max_consecutive_below_initial_days"]))
    )
    best = candidates.sort_values(
        ["passes_new_goal", "max_consecutive_below_initial_days", "worst_drawdown_pct", "median_return_pct"],
        ascending=[False, True, False, False],
    ).iloc[0]
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage076_proxy_has_promising_reserve_sleeve_candidate" if bool(best["passes_new_goal"]) else "stage076_proxy_no_promotion_candidate",
        "overlap_start_count": int(len(starts)),
        "best_candidate": best.to_dict(),
        "official_summary": official_row.to_dict(),
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot(curves, candidates)
    _write_report(variant_summary, retention, decision)
    _write_stage_record(variant_summary, decision)
    return {
        "variant_summary": variant_summary.to_dict(orient="records"),
        "decision": decision,
        "report": str(REPORT_PATH),
    }


def _plot(curves: pd.DataFrame, candidates: pd.DataFrame) -> None:
    plot_versions = ["official_c9_15w_reference"]
    plot_versions += candidates.sort_values("sleeve_capital" if "sleeve_capital" in candidates.columns else "version")[
        "version"
    ].tolist()
    starts = ["2022-01", "2022-07", "2023-01", "2024-07"]
    fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True)
    for version in plot_versions:
        for start in starts:
            data = curves[curves["version"].eq(version) & curves["requested_start_month"].eq(start)].sort_values("date")
            if data.empty:
                continue
            label = f"{start} {version.replace('c9_15w_plus_stage372_sleeve_', 'sleeve_')}"
            equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce")
            capital = float(data["account_capital_for_metrics"].iloc[0])
            axes[0].plot(data["date"], equity, linewidth=0.9, label=label)
            axes[1].plot(data["date"], _drawdown_pct(equity), linewidth=0.9, label=label)
    axes[0].axhline(TOTAL_CAPITAL, color="#6b7280", linestyle="--", linewidth=0.8, label="300k capital")
    axes[0].set_title("Stage076 C9 15w + Stage372 reserve sleeve: equity")
    axes[0].set_ylabel("equity")
    axes[1].set_title("drawdown")
    axes[1].set_ylabel("drawdown %")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=3)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(variant_summary: pd.DataFrame, retention: pd.DataFrame, decision: dict[str, Any]) -> None:
    focus_cols = [
        "version",
        "variant_label",
        "start_count",
        "positive_count",
        "min_return_pct",
        "median_return_pct",
        "min_return_retention_ratio",
        "worst_drawdown_pct",
        "max_days_below_initial",
        "max_consecutive_below_initial_days",
    ]
    text = f"""# Stage076 C9 + Stage372 reserve sleeve proxy

## 结论

- 决策：`{decision['decision']}`。
- 口径：C9 15w 主袖保持不变；15w 缓冲资金中固定一部分跑 legacy Stage372 独立袖，剩余为现金；总账户分母固定 300,000。
- 这是 curve-level proxy，不是同一账户真实组合引擎；若通过，只能进入真实引擎/逐月验证，不能直接晋级。

## 汇总

{_md_table(variant_summary[focus_cols])}

## Retention 明细

{_md_table(retention[['version', 'requested_start_month', 'total_return_pct', 'official_return_pct', 'return_retention_ratio', 'max_drawdown_pct', 'days_below_delta', 'max_consecutive_below_delta']].head(80))}

## 输出

- curves: `{CURVES_PATH}`
- summary: `{VARIANT_SUMMARY_PATH}`
- chart: `{CHART_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(variant_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{stamp}_stage076_c9_plus_stage372_reserve_sleeve_proxy.md"
    text = f"""# Stage076 C9 plus Stage372 reserve sleeve proxy

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().replace(microsecond=0).isoformat()}
- 阶段性质：30w 缓冲资金独立低相关 sleeve curve-level proxy
- 是否重要突破：{'是，代理满足新目标，需真实引擎验证' if decision['decision'] == 'stage076_proxy_has_promising_reserve_sleeve_candidate' else '否，代理未满足新目标'}

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage076_c9_plus_stage372_reserve_sleeve_proxy.py`
- 新增参数：`SLEEVE_CAPITALS={SLEEVE_CAPITALS}`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## 结果

{_md_table(variant_summary)}

## 结论

- 决策：`{decision['decision']}`。
- 运行前过拟合反思：否。独立袖是结构分散，不按坏窗口调参。
- 运行后过拟合反思：若失败后扫 sleeve 金额小数、按月份开关 Stage372 或按坏窗口切换，就是过拟合。
- 继续价值：只有代理通过时才进入真实组合引擎；否则停止这条固定 Stage372 袖方向。
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    result = build()
    print(json.dumps(_json_safe(result["decision"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
