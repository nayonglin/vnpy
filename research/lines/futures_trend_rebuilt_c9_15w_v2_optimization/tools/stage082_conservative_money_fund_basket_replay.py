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
STAGE = "Stage082"
MODEL_TAG = "stage082_conservative_money_fund_basket_replay_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage082_conservative_money_fund_basket_replay"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage082_conservative_money_fund_basket_replay"
STAGES_DIR = LINE_DIR / "stages"

STAGE077_CURVES_PATH = (
    LINE_DIR
    / "outputs"
    / "stage077_c9_idle_reserve_cash_yield_proxy"
    / "rebuilt_c9_v2_stage077_c9_idle_reserve_cash_yield_proxy_curves_stage077_c9_idle_reserve_cash_yield_proxy_v2.csv.gz"
)
STAGE081_OUT = LINE_DIR / "outputs" / "stage081_fixed_money_fund_basket_replay"
STAGE081_BASKET_PATH = (
    STAGE081_OUT
    / "rebuilt_c9_v2_stage081_fixed_money_fund_basket_replay_basket_stage081_fixed_money_fund_basket_replay_v1.csv"
)
STAGE081_HISTORY_PATH = (
    STAGE081_OUT
    / "rebuilt_c9_v2_stage081_fixed_money_fund_basket_replay_fund_history_stage081_fixed_money_fund_basket_replay_v1.csv.gz"
)
STAGE081_SOURCE_AUDIT_PATH = (
    STAGE081_OUT
    / "rebuilt_c9_v2_stage081_fixed_money_fund_basket_replay_source_audit_stage081_fixed_money_fund_basket_replay_v1.csv"
)

START_MONTHS = (
    "2020-01",
    "2020-07",
    "2021-01",
    "2021-07",
    "2022-01",
    "2022-07",
    "2023-01",
    "2023-07",
    "2024-01",
    "2024-07",
    "2025-01",
    "2025-07",
    "2026-01",
)
REQUESTED_END = pd.Timestamp("2026-06-30")
TRADING_CAPITAL = 150_000.0
RESERVE_CAPITAL = 150_000.0
TOTAL_CAPITAL = TRADING_CAPITAL + RESERVE_CAPITAL
BASKET_SIZE = 12
PER_FUND_RESERVE_CAPITAL = RESERVE_CAPITAL / BASKET_SIZE

CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
PER_START_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_purchase_audit_{MODEL_TAG}.csv"
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


def _read_official_c9() -> pd.DataFrame:
    curves = pd.read_csv(STAGE077_CURVES_PATH)
    curves = curves[curves["version"].astype(str).eq("official_c9_15w_reference")].copy()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves = curves[curves["requested_start_month"].isin(START_MONTHS)].copy()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves = curves[curves["date"].le(REQUESTED_END)].copy()
    curves["c9_equity"] = pd.to_numeric(curves["c9_equity"], errors="coerce")
    return curves[["requested_start_month", "date", "c9_equity"]].dropna().sort_values(
        ["requested_start_month", "date"]
    )


def _read_stage081_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    source_audit = pd.read_csv(STAGE081_SOURCE_AUDIT_PATH)
    if int(source_audit["fetch_error_count"].iloc[0]) != 0:
        raise RuntimeError("Stage081 source audit has fetch errors; conservative replay refuses to pass.")
    basket = pd.read_csv(STAGE081_BASKET_PATH, dtype={"fund_code": str})
    basket["fund_code"] = basket["fund_code"].astype(str).str.zfill(6)
    if len(basket) != BASKET_SIZE:
        raise RuntimeError(f"Expected {BASKET_SIZE} basket funds, got {len(basket)}")
    history = pd.read_csv(STAGE081_HISTORY_PATH, dtype={"fund_code": str})
    history["fund_code"] = history["fund_code"].astype(str).str.zfill(6)
    history["date"] = pd.to_datetime(history["date"], errors="coerce").dt.normalize()
    history["income_per_10k"] = pd.to_numeric(history["income_per_10k"], errors="coerce")
    history = history.dropna(subset=["fund_code", "date", "income_per_10k"]).copy()
    if history["fund_code"].nunique() != BASKET_SIZE:
        raise RuntimeError("Stage081 history does not contain all basket funds.")
    return basket.sort_values("fund_code").reset_index(drop=True), history, source_audit


def _is_start_investable(status: str, redeem_status: str) -> bool:
    status_text = str(status)
    redeem_text = str(redeem_status)
    if "暂停" in status_text:
        return False
    return ("开放申购" in status_text or "限" in status_text) and "开放赎回" in redeem_text


def _status_snapshot(history: pd.DataFrame, start_date: pd.Timestamp) -> pd.DataFrame:
    snapshot = (
        history[history["date"].le(start_date)]
        .sort_values(["fund_code", "date"])
        .groupby("fund_code", as_index=False)
        .tail(1)
    )
    snapshot["start_investable"] = [
        _is_start_investable(status, redeem)
        for status, redeem in zip(snapshot["purchase_status"], snapshot["redeem_status"], strict=False)
    ]
    return snapshot.sort_values("fund_code").reset_index(drop=True)


def _fund_factor_lookup(history: pd.DataFrame, fund_code: str, *, date_start: pd.Timestamp) -> pd.Series:
    calendar = pd.DataFrame({"date": pd.date_range(date_start, REQUESTED_END, freq="D")})
    fund = history[history["fund_code"].eq(fund_code)][["date", "income_per_10k"]].drop_duplicates("date")
    merged = calendar.merge(fund, on="date", how="left")
    # Conservative rule: if a selected fund has no daily disclosure, keep that slice in zero-yield cash for the day.
    merged["daily_return"] = pd.to_numeric(merged["income_per_10k"], errors="coerce").fillna(0.0) / 10_000.0
    return pd.Series((1.0 + merged["daily_return"]).cumprod().to_numpy(dtype=float), index=merged["date"])


def _reserve_equity_for_start(
    history: pd.DataFrame,
    basket_codes: list[str],
    dates: pd.Series,
    start_date: pd.Timestamp,
) -> tuple[pd.Series, dict[str, Any]]:
    snapshot = _status_snapshot(history, start_date)
    active_codes = set(snapshot.loc[snapshot["start_investable"], "fund_code"].astype(str).tolist())
    paused_codes = [code for code in basket_codes if code not in active_codes]
    date_start = min(pd.Timestamp(history["date"].min()), pd.Timestamp(start_date))
    reserve = pd.Series(0.0, index=dates.index)
    for code in basket_codes:
        if code not in active_codes:
            reserve = reserve + PER_FUND_RESERVE_CAPITAL
            continue
        lookup = _fund_factor_lookup(history, code, date_start=date_start)
        start_factor = float(lookup.loc[start_date]) if start_date in lookup.index else float(lookup.loc[:start_date].iloc[-1])
        factors = lookup.reindex(pd.to_datetime(dates).dt.normalize(), method="ffill").to_numpy(dtype=float)
        reserve = reserve + pd.Series(PER_FUND_RESERVE_CAPITAL * factors / start_factor, index=dates.index)
    audit = {
        "actual_start": start_date.date().isoformat(),
        "basket_size": BASKET_SIZE,
        "active_fund_count": int(len(active_codes)),
        "paused_or_uninvestable_fund_count": int(len(paused_codes)),
        "paused_or_uninvestable_funds": ",".join(paused_codes),
        "cash_zero_yield_capital": float(PER_FUND_RESERVE_CAPITAL * len(paused_codes)),
    }
    return reserve, audit


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
    c9 = _read_official_c9()
    basket, history, source_audit = _read_stage081_inputs()
    basket_codes = basket["fund_code"].astype(str).str.zfill(6).tolist()

    rows: list[pd.DataFrame] = []
    per_start_audit_rows: list[dict[str, Any]] = []
    for start_month, group in c9.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").drop_duplicates("date").copy()
        rows.append(
            pd.DataFrame(
                {
                    "requested_start_month": start_month,
                    "date": g["date"],
                    "version": "official_c9_15w_reference",
                    "variant_label": "Official C9 15w reference",
                    "account_capital_for_metrics": TRADING_CAPITAL,
                    "account_equity_for_metrics": g["c9_equity"],
                    "c9_equity": g["c9_equity"],
                    "reserve_equity": np.nan,
                }
            )
        )
        reserve_equity, start_audit = _reserve_equity_for_start(
            history,
            basket_codes,
            g["date"],
            pd.Timestamp(g["date"].iloc[0]),
        )
        start_audit["requested_start_month"] = start_month
        per_start_audit_rows.append(start_audit)
        rows.append(
            pd.DataFrame(
                {
                    "requested_start_month": start_month,
                    "date": g["date"].reset_index(drop=True),
                    "version": "c9_15w_plus_conservative_fixed_money_fund_basket",
                    "variant_label": "C9 15w + conservative fixed money fund basket",
                    "account_capital_for_metrics": TOTAL_CAPITAL,
                    "account_equity_for_metrics": g["c9_equity"].reset_index(drop=True) + reserve_equity.reset_index(drop=True),
                    "c9_equity": g["c9_equity"].reset_index(drop=True),
                    "reserve_equity": reserve_equity.reset_index(drop=True),
                }
            )
        )

    curves = pd.concat(rows, ignore_index=True, sort=False)
    curves["stage"] = STAGE
    curves["model_tag"] = MODEL_TAG
    curves["line_id"] = LINE_ID
    curves["requested_end"] = REQUESTED_END.date().isoformat()
    curves.to_csv(CURVES_PATH, index=False)

    per_start_audit = pd.DataFrame(per_start_audit_rows)
    per_start_audit.to_csv(PER_START_AUDIT_PATH, index=False)

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

    source_summary = {
        "stage081_fetch_error_count": int(source_audit["fetch_error_count"].iloc[0]),
        "stage081_min_daily_fund_count": int(source_audit["min_daily_fund_count"].iloc[0]),
        "history_rows": int(len(history)),
        "history_fund_count": int(history["fund_code"].nunique()),
        "history_date_min": pd.Timestamp(history["date"].min()).date().isoformat(),
        "history_date_max": pd.Timestamp(history["date"].max()).date().isoformat(),
        "max_paused_or_uninvestable_fund_count": int(per_start_audit["paused_or_uninvestable_fund_count"].max()),
    }
    decision_name = (
        "stage082_conservative_basket_account_level_marginal_pass_not_promotion"
        if bool(variant_summary.loc[mask, "passes_account_level_stage077_proxy_goal"].any())
        else "stage082_conservative_basket_no_numeric_pass"
    )
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_name,
        "source_summary": source_summary,
        "variant_summary_path": str(VARIANT_SUMMARY_PATH),
        "retention_path": str(RETENTION_PATH),
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curves)
    _write_report(variant_summary, retention, per_start_audit, decision)
    _write_stage_record(variant_summary, retention, per_start_audit, decision)
    return decision


def _plot(curves: pd.DataFrame) -> None:
    starts = ["2022-01", "2022-07", "2023-01", "2024-07", "2026-01"]
    versions = ["official_c9_15w_reference", "c9_15w_plus_conservative_fixed_money_fund_basket"]
    fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True)
    for version in versions:
        for start in starts:
            data = curves[curves["version"].eq(version) & curves["requested_start_month"].eq(start)].sort_values("date")
            if data.empty:
                continue
            equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce")
            label = f"{start} {version.replace('c9_15w_plus_', '')}"
            axes[0].plot(data["date"], equity, linewidth=0.9, label=label)
            axes[1].plot(data["date"], _drawdown_pct(equity), linewidth=0.9, label=label)
    axes[0].axhline(TOTAL_CAPITAL, color="#6b7280", linestyle="--", linewidth=0.8, label="300k capital")
    axes[0].set_title("Stage082 conservative fixed money fund basket: equity")
    axes[0].set_ylabel("equity")
    axes[1].set_title("drawdown")
    axes[1].set_ylabel("drawdown %")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=7, ncol=3)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(
    variant_summary: pd.DataFrame,
    retention: pd.DataFrame,
    per_start_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    variant_cols = [
        "version",
        "start_count",
        "positive_count",
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
    retention_cols = [
        "requested_start_month",
        "total_return_pct",
        "official_return_pct",
        "return_retention_ratio",
        "max_drawdown_pct",
        "official_max_drawdown_pct",
        "drawdown_improvement_pp",
        "days_below_delta",
        "max_consecutive_below_delta",
        "days_below_improved",
        "max_consecutive_below_improved",
    ]
    text = f"""# Stage082 conservative money fund basket replay

## 结论

- 决策：`{decision['decision']}`。
- 口径：复用 Stage081 固定 12 只基金和已抓取历史；Stage081 抓取失败数必须为 `0`；每只基金固定占储备资金 `1/12`；每日缺失收益按 `0`；起点当日 `暂停申购` 或不可赎回的基金不买入，其对应资金全程留现金 `0` 收益。
- 本阶段仍是账户层总资金体验，不是 C9 交易 alpha 或正式实盘变更。

## Variant Summary

{_md_table(variant_summary[variant_cols])}

## Per-start 可购性审计

{_md_table(per_start_audit)}

## Retention 明细

{_md_table(retention[retention_cols], 40)}

## 输出

- curves: `{CURVES_PATH}`
- per_start_audit: `{PER_START_AUDIT_PATH}`
- retention: `{RETENTION_PATH}`
- variant_summary: `{VARIANT_SUMMARY_PATH}`
- chart: `{CHART_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(
    variant_summary: pd.DataFrame,
    retention: pd.DataFrame,
    per_start_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{stamp}_stage082_conservative_money_fund_basket_replay.md"
    text = f"""# Stage082 conservative money fund basket replay

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().replace(microsecond=0).isoformat()}
- 阶段性质：Stage081 独立审查后的保守 PIT 可购性与缺失 0 收益重放
- 是否重要突破：否，账户层边际过线只能作为资金治理弱候选，不能直接晋级

## 外部调研与判断

- 货币基金每日万份收益可以作为储备资金账户层收益源，但必须把可购性和缺失数据处理做保守。
- 本阶段不使用当前 7日年化排序，不按历史收益挑基金；也不把暂停申购基金的份额重分配给其他基金。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage082_conservative_money_fund_basket_replay.py`
- 新增参数：`PER_FUND_RESERVE_CAPITAL={PER_FUND_RESERVE_CAPITAL}`。
- 修改参数：无正式交易参数。
- 删除参数：删除 Stage081 中“有数据基金均值”和“忽略起点暂停申购”的宽松假设。

## 结果

{_md_table(variant_summary)}

## Per-start 可购性审计

{_md_table(per_start_audit)}

## Retention 明细

{_md_table(retention[['requested_start_month', 'total_return_pct', 'official_return_pct', 'return_retention_ratio', 'max_drawdown_pct', 'drawdown_improvement_pp', 'days_below_delta', 'max_consecutive_below_delta']], 40)}

## 结论

- 决策：`{decision['decision']}`。
- 回测指标说明：本阶段是账户层现金收益源重放，不新增交易订单；底层 C9 交易路径不变，因此不生成新增真实滑点、交易次数或胜率。
- 运行前过拟合反思：否。规则来自独立审查要求的保守口径，不按坏窗口、收益率或基金表现调参。
- 运行后过拟合反思：若继续按篮子大小、基金代码范围、暂停申购处理或当前收益率救过线，就是过拟合；本阶段只允许作为账户层资金治理证据。
- 继续价值：有但有限。若保守口径仍过线，下一步不是直接晋级，而是审真实交易渠道和税费/赎回时效；若不过线，则现金篮子方向降级。

## 输出文件

- report：`{REPORT_PATH}`
- decision：`{DECISION_PATH}`
- curves：`{CURVES_PATH}`
- variant_summary：`{VARIANT_SUMMARY_PATH}`
- retention：`{RETENTION_PATH}`
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    decision = build()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
