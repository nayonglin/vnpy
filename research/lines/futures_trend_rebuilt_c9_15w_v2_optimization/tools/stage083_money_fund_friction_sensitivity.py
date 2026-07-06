from __future__ import annotations

from datetime import datetime
import importlib.util
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
STAGE = "Stage083"
MODEL_TAG = "stage083_money_fund_friction_sensitivity_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage083_money_fund_friction_sensitivity"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage083_money_fund_friction_sensitivity"
STAGES_DIR = LINE_DIR / "stages"
STAGE082_TOOL_PATH = LINE_DIR / "tools" / "stage082_conservative_money_fund_basket_replay.py"

TRADING_CAPITAL = 150_000.0
RESERVE_CAPITAL = 150_000.0
TOTAL_CAPITAL = TRADING_CAPITAL + RESERVE_CAPITAL
BASKET_SIZE = 12
PER_FUND_RESERVE_CAPITAL = RESERVE_CAPITAL / BASKET_SIZE
REQUESTED_END = pd.Timestamp("2026-06-30")

VARIANT_SPECS = (
    {"version": "stage082_base_conservative", "label": "Stage082 base conservative", "delay_days": 0, "annual_haircut_bps": 0.0},
    {"version": "tplus1_delay", "label": "T+1 income delay", "delay_days": 1, "annual_haircut_bps": 0.0},
    {"version": "tplus2_delay", "label": "T+2 income delay", "delay_days": 2, "annual_haircut_bps": 0.0},
    {"version": "haircut_25bp", "label": "25bp annual yield haircut", "delay_days": 0, "annual_haircut_bps": 25.0},
    {"version": "haircut_50bp", "label": "50bp annual yield haircut", "delay_days": 0, "annual_haircut_bps": 50.0},
    {"version": "haircut_100bp", "label": "100bp annual yield haircut", "delay_days": 0, "annual_haircut_bps": 100.0},
    {"version": "haircut_150bp", "label": "150bp annual yield haircut", "delay_days": 0, "annual_haircut_bps": 150.0},
    {"version": "haircut_200bp", "label": "200bp annual yield haircut", "delay_days": 0, "annual_haircut_bps": 200.0},
    {"version": "tplus1_haircut_50bp", "label": "T+1 delay + 50bp haircut", "delay_days": 1, "annual_haircut_bps": 50.0},
    {"version": "tplus1_haircut_100bp", "label": "T+1 delay + 100bp haircut", "delay_days": 1, "annual_haircut_bps": 100.0},
    {"version": "tplus1_haircut_150bp", "label": "T+1 delay + 150bp haircut", "delay_days": 1, "annual_haircut_bps": 150.0},
)

CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
RETENTION_PATH = OUT / f"{OUTPUT_PREFIX}_retention_vs_official_c9_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_retention_drawdown_chart_{MODEL_TAG}.png"


def _load_stage082_module() -> Any:
    spec = importlib.util.spec_from_file_location("stage082_conservative_money_fund_basket_replay", STAGE082_TOOL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {STAGE082_TOOL_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S82 = _load_stage082_module()


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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


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


def _fund_factor_lookup(
    history: pd.DataFrame,
    fund_code: str,
    *,
    date_start: pd.Timestamp,
    annual_haircut_bps: float,
) -> pd.Series:
    calendar = pd.DataFrame({"date": pd.date_range(date_start, REQUESTED_END, freq="D")})
    fund = history[history["fund_code"].eq(fund_code)][["date", "income_per_10k"]].drop_duplicates("date")
    merged = calendar.merge(fund, on="date", how="left")
    daily_haircut = annual_haircut_bps / 10_000.0 / 365.0
    merged["daily_return"] = pd.to_numeric(merged["income_per_10k"], errors="coerce").fillna(0.0) / 10_000.0
    merged["daily_return"] = (merged["daily_return"] - daily_haircut).clip(lower=-0.999999)
    return pd.Series((1.0 + merged["daily_return"]).cumprod().to_numpy(dtype=float), index=merged["date"])


def _reserve_equity_for_start(
    history: pd.DataFrame,
    basket_codes: list[str],
    dates: pd.Series,
    start_date: pd.Timestamp,
    *,
    delay_days: int,
    annual_haircut_bps: float,
) -> pd.Series:
    snapshot = S82._status_snapshot(history, start_date)
    active_codes = set(snapshot.loc[snapshot["start_investable"], "fund_code"].astype(str).tolist())
    date_start = min(pd.Timestamp(history["date"].min()), pd.Timestamp(start_date))
    income_start = start_date + pd.Timedelta(days=delay_days)
    reserve = pd.Series(0.0, index=dates.index)
    for code in basket_codes:
        if code not in active_codes:
            reserve = reserve + PER_FUND_RESERVE_CAPITAL
            continue
        lookup = _fund_factor_lookup(history, code, date_start=date_start, annual_haircut_bps=annual_haircut_bps)
        start_factor = float(lookup.loc[income_start]) if income_start in lookup.index else float(lookup.loc[:income_start].iloc[-1])
        date_values = lookup.reindex(pd.to_datetime(dates).dt.normalize(), method="ffill")
        factors = date_values.to_numpy(dtype=float) / start_factor
        factors = np.where(pd.to_datetime(dates).dt.normalize().le(income_start), 1.0, factors)
        reserve = reserve + pd.Series(PER_FUND_RESERVE_CAPITAL * factors, index=dates.index)
    return reserve


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
    c9 = S82._read_official_c9()
    basket, history, source_audit = S82._read_stage081_inputs()
    basket_codes = basket["fund_code"].astype(str).str.zfill(6).tolist()

    rows: list[pd.DataFrame] = []
    for start_month, group in c9.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").drop_duplicates("date").copy()
        rows.append(
            pd.DataFrame(
                {
                    "requested_start_month": start_month,
                    "date": g["date"],
                    "version": "official_c9_15w_reference",
                    "variant_label": "Official C9 15w reference",
                    "delay_days": 0,
                    "annual_haircut_bps": 0.0,
                    "account_capital_for_metrics": TRADING_CAPITAL,
                    "account_equity_for_metrics": g["c9_equity"],
                    "c9_equity": g["c9_equity"],
                    "reserve_equity": np.nan,
                }
            )
        )
        for spec in VARIANT_SPECS:
            reserve = _reserve_equity_for_start(
                history,
                basket_codes,
                g["date"],
                pd.Timestamp(g["date"].iloc[0]),
                delay_days=int(spec["delay_days"]),
                annual_haircut_bps=float(spec["annual_haircut_bps"]),
            )
            rows.append(
                pd.DataFrame(
                    {
                        "requested_start_month": start_month,
                        "date": g["date"].reset_index(drop=True),
                        "version": str(spec["version"]),
                        "variant_label": str(spec["label"]),
                        "delay_days": int(spec["delay_days"]),
                        "annual_haircut_bps": float(spec["annual_haircut_bps"]),
                        "account_capital_for_metrics": TOTAL_CAPITAL,
                        "account_equity_for_metrics": g["c9_equity"].reset_index(drop=True) + reserve.reset_index(drop=True),
                        "c9_equity": g["c9_equity"].reset_index(drop=True),
                        "reserve_equity": reserve.reset_index(drop=True),
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
    retention["days_below_improved"] = retention["days_below_delta"].lt(0)
    retention["max_consecutive_below_improved"] = retention["max_consecutive_below_delta"].lt(0)
    retention.to_csv(RETENTION_PATH, index=False)

    variant_rows: list[dict[str, Any]] = []
    for version, group in summary.groupby("version", sort=False):
        ret = retention[retention["version"].eq(version)]
        spec_rows = curves[curves["version"].eq(version)]
        variant_rows.append(
            {
                "version": version,
                "variant_label": str(group["variant_label"].iloc[0]),
                "delay_days": int(spec_rows["delay_days"].dropna().iloc[0]) if not spec_rows.empty else 0,
                "annual_haircut_bps": float(spec_rows["annual_haircut_bps"].dropna().iloc[0]) if not spec_rows.empty else 0.0,
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
                "days_below_improved_count": int(ret["days_below_improved"].sum()) if not ret.empty else 0,
                "max_consecutive_below_improved_count": int(ret["max_consecutive_below_improved"].sum()) if not ret.empty else 0,
            }
        )
    variant_summary = pd.DataFrame(variant_rows)
    official_row = variant_summary[variant_summary["version"].eq("official_c9_15w_reference")].iloc[0]
    variant_summary["passes_account_level_stage077_proxy_goal"] = False
    mask = ~variant_summary["version"].eq("official_c9_15w_reference")
    variant_summary.loc[mask, "passes_account_level_stage077_proxy_goal"] = (
        variant_summary.loc[mask, "min_return_retention_ratio"].ge(0.5 - 1e-9)
        & variant_summary.loc[mask, "worst_drawdown_pct"].gt(float(official_row["worst_drawdown_pct"]))
        & variant_summary.loc[mask, "max_days_below_initial"].lt(int(official_row["max_days_below_initial"]))
        & variant_summary.loc[mask, "max_consecutive_below_initial_days"].lt(int(official_row["max_consecutive_below_initial_days"]))
    )
    variant_summary.to_csv(VARIANT_SUMMARY_PATH, index=False)

    passing = variant_summary[mask & variant_summary["passes_account_level_stage077_proxy_goal"]].copy()
    robust_spec = variant_summary[variant_summary["version"].eq("tplus1_haircut_50bp")]
    decision_name = (
        "stage083_light_friction_survives_but_edge_thin_not_promotion"
        if not robust_spec.empty and bool(robust_spec["passes_account_level_stage077_proxy_goal"].iloc[0])
        else "stage083_friction_breaks_stage082_edge_downgrade_cash_basket"
    )
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_name,
        "passing_variant_count": int(len(passing)),
        "stage081_fetch_error_count": int(source_audit["fetch_error_count"].iloc[0]),
        "variant_summary_path": str(VARIANT_SUMMARY_PATH),
        "retention_path": str(RETENTION_PATH),
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(variant_summary)
    _write_report(variant_summary, retention, decision)
    _write_stage_record(variant_summary, retention, decision)
    return decision


def _plot(variant_summary: pd.DataFrame) -> None:
    data = variant_summary[~variant_summary["version"].eq("official_c9_15w_reference")].copy()
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    x = np.arange(len(data))
    colors = ["#2563eb" if bool(v) else "#dc2626" for v in data["passes_account_level_stage077_proxy_goal"]]
    axes[0].bar(x, data["min_return_retention_ratio"], color=colors)
    axes[0].axhline(0.5, color="#111827", linestyle="--", linewidth=0.8)
    axes[0].set_ylabel("min retention")
    axes[0].set_title("Stage083 friction sensitivity")
    axes[1].bar(x, data["worst_drawdown_pct"], color=colors)
    axes[1].axhline(float(variant_summary.loc[variant_summary["version"].eq("official_c9_15w_reference"), "worst_drawdown_pct"].iloc[0]), color="#111827", linestyle="--", linewidth=0.8)
    axes[1].set_ylabel("worst DD %")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["version"], rotation=35, ha="right", fontsize=8)
    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(variant_summary: pd.DataFrame, retention: pd.DataFrame, decision: dict[str, Any]) -> None:
    variant_cols = [
        "version",
        "delay_days",
        "annual_haircut_bps",
        "min_return_pct",
        "median_return_pct",
        "min_return_retention_ratio",
        "worst_drawdown_pct",
        "max_days_below_initial",
        "max_consecutive_below_initial_days",
        "days_below_improved_count",
        "max_consecutive_below_improved_count",
        "passes_account_level_stage077_proxy_goal",
    ]
    text = f"""# Stage083 money fund friction sensitivity

## 结论

- 决策：`{decision['decision']}`。
- 口径：不换基金、不扫篮子大小；固定 Stage082 保守篮子，只加入收益确认延迟和年化收益 haircut。
- 外部调研判断：每万份收益可作为货基日收益源，但快速赎回存在额度限制，确认/赎回时效是资金治理硬约束；因此 Stage082 必须做摩擦敏感性。

## Variant Summary

{_md_table(variant_summary[variant_cols])}

## Retention 明细

{_md_table(retention[['version', 'requested_start_month', 'total_return_pct', 'official_return_pct', 'return_retention_ratio', 'max_drawdown_pct', 'days_below_delta', 'max_consecutive_below_delta']], 80)}

## 输出

- curves: `{CURVES_PATH}`
- retention: `{RETENTION_PATH}`
- variant_summary: `{VARIANT_SUMMARY_PATH}`
- chart: `{CHART_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(variant_summary: pd.DataFrame, retention: pd.DataFrame, decision: dict[str, Any]) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{stamp}_stage083_money_fund_friction_sensitivity.md"
    passing = variant_summary[variant_summary["passes_account_level_stage077_proxy_goal"] & ~variant_summary["version"].eq("official_c9_15w_reference")]
    text = f"""# Stage083 money fund friction sensitivity

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().replace(microsecond=0).isoformat()}
- 阶段性质：Stage082 固定货币基金篮子的真实渠道摩擦敏感性
- 是否重要突破：否，验证账户层弱候选的摩擦承受力

## 外部调研与判断

- 天天基金帮助说明，每万份收益是货币基金每一万份单位当日收益，通常工作日晚公布；七日年化只代表过去七个自然日折算，不代表未来。
- 易方达 000009 快速赎回协议显示，快速赎回有单只货基单日限额、收益停止和暂停服务等约束。
- 东方财富转载的监管文件显示，T+0 快速赎回提现单只货基单销售渠道单日上限不高于 `1万元`，普通赎回不受该快速额度限制。
- 本阶段判断：现金篮子不能只看历史收益，必须在确认延迟和收益 haircut 后仍保留目标边际；否则降级。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage083_money_fund_friction_sensitivity.py`
- 新增参数：`delay_days in {{0,1,2}}`、`annual_haircut_bps in {{0,25,50,100,150,200}}`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## 结果

{_md_table(variant_summary)}

## 结论

- 决策：`{decision['decision']}`。
- 通过 variant 数：`{len(passing)}`。
- 回测指标说明：本阶段是账户层现金收益摩擦敏感性，不新增交易订单；底层 C9 交易路径不变，因此不生成新增真实滑点、交易次数或胜率。
- 运行前过拟合反思：否。只对真实渠道摩擦做固定压力测试，不换基金、不调篮子。
- 运行后过拟合反思：若因为某个 haircut 失败而换基金、换数量或改口径，就是过拟合；应把失败视为账户层弱候选的鲁棒性不足。
- 继续价值：取决于摩擦后是否仍过线。若只在极轻摩擦下过线，后续只做真实渠道确认，不进入正式；若轻摩擦也失败，现金篮子降级。

## 输出文件

- report：`{REPORT_PATH}`
- decision：`{DECISION_PATH}`
- variant_summary：`{VARIANT_SUMMARY_PATH}`
- retention：`{RETENTION_PATH}`
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    decision = build()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
