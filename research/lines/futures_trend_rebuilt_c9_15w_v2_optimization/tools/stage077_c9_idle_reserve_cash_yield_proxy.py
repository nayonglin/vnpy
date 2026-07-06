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
STAGE = "Stage077"
MODEL_TAG = "stage077_c9_idle_reserve_cash_yield_proxy_v2"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage077_c9_idle_reserve_cash_yield_proxy"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage077_c9_idle_reserve_cash_yield_proxy"
STAGES_DIR = LINE_DIR / "stages"

C9_CURVES_PATH = (
    ROOT
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)

REQUESTED_END = pd.Timestamp("2026-06-30")
START_MONTH_MIN = "2020-01"
START_MONTH_MAX = "2026-01"
TRADING_CAPITAL = 150_000.0
RESERVE_CAPITAL = 150_000.0
TOTAL_CAPITAL = TRADING_CAPITAL + RESERVE_CAPITAL
ANNUAL_YIELD_RATES = (0.00, 0.01, 0.02, 0.03, 0.05)

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
    if std <= 0.0 or not np.isfinite(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _read_c9_curves() -> pd.DataFrame:
    frame = pd.read_csv(C9_CURVES_PATH)
    frame["requested_start_month"] = frame["requested_start_month"].astype(str)
    frame = frame[
        frame["requested_start_month"].ge(START_MONTH_MIN)
        & frame["requested_start_month"].le(START_MONTH_MAX)
    ].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["date"].le(REQUESTED_END)].copy()
    frame["c9_equity"] = pd.to_numeric(frame["account_equity"], errors="coerce")
    return frame[["requested_start_month", "date", "c9_equity"]].dropna()


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
        "annual_yield_rate": float(data["annual_yield_rate"].iloc[0]),
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
    c9 = _read_c9_curves()

    rows: list[pd.DataFrame] = []
    for start_month, group in c9.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").drop_duplicates("date").copy()
        start_date = pd.Timestamp(g["date"].iloc[0])
        official = pd.DataFrame(
            {
                "requested_start_month": start_month,
                "date": g["date"],
                "version": "official_c9_15w_reference",
                "variant_label": "Official C9 15w reference",
                "annual_yield_rate": 0.0,
                "account_capital_for_metrics": TRADING_CAPITAL,
                "account_equity_for_metrics": g["c9_equity"],
                "c9_equity": g["c9_equity"],
                "reserve_equity": np.nan,
            }
        )
        rows.append(official)
        elapsed_days = (g["date"] - start_date).dt.days.clip(lower=0)
        for rate in ANNUAL_YIELD_RATES:
            reserve_equity = RESERVE_CAPITAL * np.power(1.0 + float(rate), elapsed_days / 365.25)
            account_equity = g["c9_equity"] + reserve_equity
            version = f"c9_15w_plus_idle_reserve_yield_{int(round(rate * 10000)):04d}bp"
            label = f"C9 15w + idle reserve yield {rate:.0%}"
            rows.append(
                pd.DataFrame(
                    {
                        "requested_start_month": start_month,
                        "date": g["date"],
                        "version": version,
                        "variant_label": label,
                        "annual_yield_rate": float(rate),
                        "account_capital_for_metrics": TOTAL_CAPITAL,
                        "account_equity_for_metrics": account_equity,
                        "c9_equity": g["c9_equity"],
                        "reserve_equity": reserve_equity,
                    }
                )
            )

    curves = pd.concat(rows, ignore_index=True, sort=False)
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

    official = summary[summary["version"].eq("official_c9_15w_reference")][
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
        official, on="requested_start_month", how="left"
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
                "annual_yield_rate": float(group["annual_yield_rate"].iloc[0]),
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
        & candidates["max_days_below_initial"].lt(int(official_row["max_days_below_initial"]))
        & candidates["max_consecutive_below_initial_days"].lt(int(official_row["max_consecutive_below_initial_days"]))
    )
    best = candidates.sort_values(
        ["passes_new_goal", "annual_yield_rate", "max_consecutive_below_initial_days", "worst_drawdown_pct"],
        ascending=[False, True, True, False],
    ).iloc[0]
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage077_cash_yield_proxy_candidate_needs_real_yield_source" if bool(best["passes_new_goal"]) else "stage077_cash_yield_proxy_no_promotion_candidate",
        "best_candidate": best.to_dict(),
        "official_summary": official_row.to_dict(),
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curves, candidates)
    _write_report(variant_summary, retention, decision)
    _write_stage_record(variant_summary, decision)
    return {"decision": decision, "variant_summary": variant_summary.to_dict(orient="records"), "report": str(REPORT_PATH)}


def _plot(curves: pd.DataFrame, candidates: pd.DataFrame) -> None:
    plot_versions = ["official_c9_15w_reference"]
    plot_versions += candidates["version"].tolist()
    starts = ["2022-01", "2022-07", "2023-01", "2024-07", "2026-01"]
    fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True)
    for version in plot_versions:
        for start in starts:
            data = curves[curves["version"].eq(version) & curves["requested_start_month"].eq(start)].sort_values("date")
            if data.empty:
                continue
            equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce")
            label = f"{start} {version.replace('c9_15w_plus_idle_reserve_yield_', 'y')}"
            axes[0].plot(data["date"], equity, linewidth=0.9, label=label)
            axes[1].plot(data["date"], _drawdown_pct(equity), linewidth=0.9, label=label)
    axes[0].axhline(TOTAL_CAPITAL, color="#6b7280", linestyle="--", linewidth=0.8, label="300k capital")
    axes[0].set_title("Stage077 C9 15w + idle reserve cash yield: equity")
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
    text = f"""# Stage077 C9 idle reserve cash yield proxy

## 结论

- 决策：`{decision['decision']}`。
- 口径：起点 `{START_MONTH_MIN}` 到 `{START_MONTH_MAX}` 逐半年；C9 15w 主袖保持不变；15w 缓冲资金不补亏、不跑旧策略，只按固定年化现金收益累积；总账户分母固定 300,000。
- 这是 curve-level proxy，不是真实可投货币基金或券商保证金利息验证；若通过，还要确认真实可获得收益率、流动性、税费和回撤同步性。

## 汇总

{_md_table(variant_summary[focus_cols])}

## Retention 明细

{_md_table(retention[['version', 'requested_start_month', 'total_return_pct', 'official_return_pct', 'return_retention_ratio', 'max_drawdown_pct', 'days_below_delta', 'max_consecutive_below_delta']].head(90))}

## 输出

- curves: `{CURVES_PATH}`
- summary: `{VARIANT_SUMMARY_PATH}`
- chart: `{CHART_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(variant_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{stamp}_stage077_c9_idle_reserve_cash_yield_proxy.md"
    text = f"""# Stage077 C9 idle reserve cash yield proxy

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().replace(microsecond=0).isoformat()}
- 阶段性质：30w 缓冲资金现金收益 curve-level proxy
- 回测起点：`{START_MONTH_MIN}` 到 `{START_MONTH_MAX}` 逐半年，终点 `{REQUESTED_END.date().isoformat()}`
- 是否重要突破：{'是，代理满足新目标但需真实收益源验证' if decision['decision'] == 'stage077_cash_yield_proxy_candidate_needs_real_yield_source' else '否，代理未满足新目标'}

## 外部调研与判断

- managed futures 文献支持现金/抵押品收益是账户总回报的一部分；pysystemtrade capital correction 支持区分总资本和在险资本。
- 本阶段不把收益率当策略参数优化，只做固定情景 `0/1/2/3/5%`。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage077_c9_idle_reserve_cash_yield_proxy.py`
- 新增参数：`ANNUAL_YIELD_RATES={ANNUAL_YIELD_RATES}`。
- 新增口径参数：`START_MONTH_MIN={START_MONTH_MIN}`、`START_MONTH_MAX={START_MONTH_MAX}`、`REQUESTED_END={REQUESTED_END.date().isoformat()}`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## 结果

{_md_table(variant_summary)}

## 结论

- 决策：`{decision['decision']}`。
- 运行前过拟合反思：否。现金收益是外部账户层变量，固定情景不是坏窗口救参。
- 运行后过拟合反思：若按结果挑一个不可获得的年化收益率或忽略流动性/税费，就是统计幻觉。
- 继续价值：只有低现实收益率也能通过时，才值得进入真实资金产品/流动性审计。
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    result = build()
    print(json.dumps(_json_safe(result["decision"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
