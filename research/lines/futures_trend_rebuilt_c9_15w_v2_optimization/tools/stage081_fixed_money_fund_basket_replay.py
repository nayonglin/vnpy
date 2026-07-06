from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import math
from pathlib import Path
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage081"
MODEL_TAG = "stage081_fixed_money_fund_basket_replay_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage081_fixed_money_fund_basket_replay"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage081_fixed_money_fund_basket_replay"
STAGES_DIR = LINE_DIR / "stages"

STAGE077_CURVES_PATH = (
    LINE_DIR
    / "outputs"
    / "stage077_c9_idle_reserve_cash_yield_proxy"
    / "rebuilt_c9_v2_stage077_c9_idle_reserve_cash_yield_proxy_curves_stage077_c9_idle_reserve_cash_yield_proxy_v2.csv.gz"
)
PURCHASE_RAW_PATH = (
    LINE_DIR
    / "outputs"
    / "stage080_fund_purchase_field_gate"
    / "rebuilt_c9_v2_stage080_fund_purchase_field_gate_fund_purchase_raw_stage080_fund_purchase_field_gate_v1.csv"
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
MAX_WORKERS = 4

CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
BASKET_PATH = OUT / f"{OUTPUT_PREFIX}_basket_{MODEL_TAG}.csv"
FUND_HISTORY_PATH = OUT / f"{OUTPUT_PREFIX}_fund_history_{MODEL_TAG}.csv.gz"
SOURCE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_source_audit_{MODEL_TAG}.csv"
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


def _purchase_eligible_unbiased_universe() -> pd.DataFrame:
    purchase = pd.read_csv(PURCHASE_RAW_PATH, dtype={"fund_code": str})
    purchase["fund_code"] = purchase["fund_code"].astype(str).str.zfill(6)
    purchase["is_money_fund"] = purchase["fund_type"].fillna("").astype(str).str.contains("货币")
    purchase["purchase_min_yuan"] = pd.to_numeric(purchase["purchase_min_yuan"], errors="coerce")
    purchase["daily_limit_yuan"] = pd.to_numeric(purchase["daily_limit_yuan"], errors="coerce")
    purchase["fee_pct"] = pd.to_numeric(purchase["fee_pct"], errors="coerce")
    purchase_status = purchase["purchase_status"].fillna("").astype(str)
    purchase["purchase_open_or_capacity_ok"] = purchase_status.str.contains("开放申购", regex=False) | (
        purchase_status.str.contains("限大额", regex=False) & purchase["daily_limit_yuan"].ge(RESERVE_CAPITAL)
    )
    purchase["redeem_open"] = purchase["redeem_status"].fillna("").astype(str).str.contains("开放赎回", regex=False)
    purchase["eligible"] = (
        purchase["is_money_fund"]
        & purchase["purchase_open_or_capacity_ok"]
        & purchase["redeem_open"]
        & purchase["purchase_min_yuan"].le(RESERVE_CAPITAL)
        & purchase["daily_limit_yuan"].ge(RESERVE_CAPITAL)
        & purchase["fee_pct"].fillna(999.0).le(0.0)
    )
    universe = purchase[purchase["eligible"]].copy()
    # Avoid current-yield sorting. Fund code order is stable and independent from recent yield.
    return universe.sort_values("fund_code").reset_index(drop=True)


def _fetch_fund_history(symbol: str, *, start: str = "2020-01-01", end: str = "2026-06-30") -> pd.DataFrame:
    url = "https://api.fund.eastmoney.com/f10/lsjz"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://fundf10.eastmoney.com/jjjz_{symbol}.html",
        "Host": "api.fund.eastmoney.com",
    }
    params = {
        "fundCode": symbol,
        "pageIndex": "1",
        "pageSize": "20",
        "startDate": start,
        "endDate": end,
        "_": round(time.time() * 1000),
    }
    first = requests.get(url, params=params, headers=headers, timeout=20)
    first.raise_for_status()
    data_json = first.json()
    total_count = int(data_json.get("TotalCount") or 0)
    total_page = math.ceil(total_count / 20) if total_count else 0
    rows: list[dict[str, Any]] = []
    for page in range(1, total_page + 1):
        params["pageIndex"] = str(page)
        response = requests.get(url, params=params, headers=headers, timeout=20)
        response.raise_for_status()
        page_json = response.json()
        rows.extend(page_json.get("Data", {}).get("LSJZList", []) or [])
    if not rows:
        return pd.DataFrame(
            columns=["fund_code", "date", "income_per_10k", "annualized_rate_pct", "purchase_status", "redeem_status"]
        )
    frame = pd.DataFrame(rows)
    result = pd.DataFrame(
        {
            "fund_code": symbol,
            "date": pd.to_datetime(frame.get("FSRQ"), errors="coerce").dt.normalize(),
            "income_per_10k": pd.to_numeric(frame.get("DWJZ"), errors="coerce"),
            "annualized_rate_pct": pd.to_numeric(frame.get("LJJZ"), errors="coerce"),
            "purchase_status": frame.get("SGZT"),
            "redeem_status": frame.get("SHZT"),
        }
    )
    return result.dropna(subset=["date", "income_per_10k"]).sort_values("date")


def _calendar_factor_from_basket(history: pd.DataFrame, *, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    calendar = pd.DataFrame({"date": pd.date_range(start, end, freq="D")})
    daily = history.groupby("date", as_index=False).agg(
        income_per_10k_mean=("income_per_10k", "mean"),
        fund_count=("fund_code", "nunique"),
    )
    calendar = calendar.merge(daily, on="date", how="left")
    calendar["raw_available"] = calendar["income_per_10k_mean"].notna()
    calendar["fund_count"] = pd.to_numeric(calendar["fund_count"], errors="coerce").fillna(0).astype(int)
    calendar["daily_return"] = pd.to_numeric(calendar["income_per_10k_mean"], errors="coerce").fillna(0.0) / 10_000.0
    calendar["gross_factor"] = (1.0 + calendar["daily_return"]).cumprod()
    return calendar


def _reserve_equity_on_strategy_dates(factor: pd.DataFrame, dates: pd.Series, start_date: pd.Timestamp) -> pd.Series:
    lookup = factor[["date", "gross_factor"]].drop_duplicates("date").set_index("date")["gross_factor"]
    start_factor = float(lookup.loc[start_date]) if start_date in lookup.index else float(lookup.loc[:start_date].iloc[-1])
    values = lookup.reindex(pd.to_datetime(dates).dt.normalize(), method="ffill").to_numpy(dtype=float)
    return pd.Series(RESERVE_CAPITAL * values / start_factor, index=dates.index)


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
    universe = _purchase_eligible_unbiased_universe()
    basket = universe.head(BASKET_SIZE).copy()
    basket.to_csv(BASKET_PATH, index=False)

    histories: list[pd.DataFrame] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {
            executor.submit(_fetch_fund_history, str(code)): str(code)
            for code in basket["fund_code"].astype(str).str.zfill(6).tolist()
        }
        for future in as_completed(future_map):
            code = future_map[future]
            try:
                histories.append(future.result())
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{code}:{type(exc).__name__}:{exc}")
    history = pd.concat(histories, ignore_index=True, sort=False) if histories else pd.DataFrame()
    history.to_csv(FUND_HISTORY_PATH, index=False)

    date_start = min(pd.Timestamp(c9["date"].min()), pd.Timestamp("2020-01-01"))
    factor = _calendar_factor_from_basket(history, start=date_start, end=REQUESTED_END)

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
                    "account_capital_for_metrics": TRADING_CAPITAL,
                    "account_equity_for_metrics": g["c9_equity"],
                    "c9_equity": g["c9_equity"],
                    "reserve_equity": np.nan,
                }
            )
        )
        reserve_equity = _reserve_equity_on_strategy_dates(factor, g["date"], pd.Timestamp(g["date"].iloc[0]))
        rows.append(
            pd.DataFrame(
                {
                    "requested_start_month": start_month,
                    "date": g["date"].reset_index(drop=True),
                    "version": "c9_15w_plus_fixed_12_money_fund_basket",
                    "variant_label": "C9 15w + fixed 12 money fund basket",
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
    official_row = variant_summary[variant_summary["version"].eq("official_c9_15w_reference")].iloc[0]
    variant_summary["passes_stage077_numeric_goal"] = False
    mask = ~variant_summary["version"].eq("official_c9_15w_reference")
    variant_summary.loc[mask, "passes_stage077_numeric_goal"] = (
        variant_summary.loc[mask, "min_return_retention_ratio"].ge(0.5 - 1e-9)
        & variant_summary.loc[mask, "worst_drawdown_pct"].gt(float(official_row["worst_drawdown_pct"]))
        & variant_summary.loc[mask, "max_days_below_initial"].lt(int(official_row["max_days_below_initial"]))
        & variant_summary.loc[mask, "max_consecutive_below_initial_days"].lt(int(official_row["max_consecutive_below_initial_days"]))
    )
    variant_summary.to_csv(VARIANT_SUMMARY_PATH, index=False)

    source_audit = pd.DataFrame(
        [
            {
                "basket_size": int(len(basket)),
                "universe_size": int(len(universe)),
                "history_fund_count": int(history["fund_code"].nunique()) if not history.empty else 0,
                "history_rows": int(len(history)),
                "history_date_min": pd.Timestamp(history["date"].min()).date().isoformat() if not history.empty else None,
                "history_date_max": pd.Timestamp(history["date"].max()).date().isoformat() if not history.empty else None,
                "calendar_raw_coverage_pct": float(factor["raw_available"].mean() * 100.0),
                "min_daily_fund_count": int(factor.loc[factor["raw_available"], "fund_count"].min()) if factor["raw_available"].any() else 0,
                "median_daily_fund_count": float(factor.loc[factor["raw_available"], "fund_count"].median()) if factor["raw_available"].any() else 0.0,
                "fetch_error_count": int(len(errors)),
                "fetch_errors_sample": "; ".join(errors[:5]),
            }
        ]
    )
    source_audit.to_csv(SOURCE_AUDIT_PATH, index=False)

    decision_name = (
        "stage081_fixed_money_fund_basket_passes_numeric_needs_real_channel"
        if bool(variant_summary.loc[mask, "passes_stage077_numeric_goal"].any())
        else "stage081_fixed_money_fund_basket_no_numeric_pass"
    )
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_name,
        "basket_size": int(len(basket)),
        "universe_size": int(len(universe)),
        "fetch_error_count": int(len(errors)),
        "source_audit_path": str(SOURCE_AUDIT_PATH),
        "variant_summary_path": str(VARIANT_SUMMARY_PATH),
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curves)
    _write_report(basket, source_audit, variant_summary, retention, decision)
    _write_stage_record(basket, source_audit, variant_summary, decision)
    return decision


def _plot(curves: pd.DataFrame) -> None:
    starts = ["2022-01", "2022-07", "2023-01", "2024-07", "2026-01"]
    versions = ["official_c9_15w_reference", "c9_15w_plus_fixed_12_money_fund_basket"]
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
    axes[0].set_title("Stage081 fixed money fund basket: equity")
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
    basket: pd.DataFrame,
    source_audit: pd.DataFrame,
    variant_summary: pd.DataFrame,
    retention: pd.DataFrame,
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
        "passes_stage077_numeric_goal",
    ]
    basket_cols = [
        "fund_code",
        "fund_name_purchase",
        "fund_type",
        "purchase_status",
        "redeem_status",
        "purchase_min_yuan",
        "daily_limit_yuan",
        "fee_pct",
    ]
    text = f"""# Stage081 fixed money fund basket replay

## 结论

- 决策：`{decision['decision']}`。
- 选篮子规则：从 `fund_purchase_em` 公开平台字段合格的全市场货币基金中，按基金代码稳定排序取前 `{BASKET_SIZE}` 只；不使用当前 7日年化排序或阈值。
- 本阶段仍不是用户真实交易渠道确认，不能直接接入实盘默认路径。

## Source Audit

{_md_table(source_audit)}

## Basket

{_md_table(basket[basket_cols])}

## Variant Summary

{_md_table(variant_summary[variant_cols])}

## Retention 明细

{_md_table(retention[['version', 'requested_start_month', 'total_return_pct', 'official_return_pct', 'return_retention_ratio', 'max_drawdown_pct', 'days_below_delta', 'max_consecutive_below_delta']], 40)}

## 输出

- basket: `{BASKET_PATH}`
- fund_history: `{FUND_HISTORY_PATH}`
- variant_summary: `{VARIANT_SUMMARY_PATH}`
- chart: `{CHART_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(
    basket: pd.DataFrame,
    source_audit: pd.DataFrame,
    variant_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{stamp}_stage081_fixed_money_fund_basket_replay.md"
    text = f"""# Stage081 fixed money fund basket replay

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().replace(microsecond=0).isoformat()}
- 阶段性质：无当前收益筛选的固定货币基金篮子历史收益回放
- 是否重要突破：{'是，固定篮子数字过线但仍需真实渠道确认' if decision['decision'] == 'stage081_fixed_money_fund_basket_passes_numeric_needs_real_channel' else '否，固定篮子未过数字门'}

## 外部调研与判断

- 货币基金每日每万份收益可以作为现金储备账户层历史收益源；但基金篮子选择必须避免当前收益率排序造成选择偏差。
- 本阶段按公开平台申赎/限额字段合格、基金代码稳定排序取前 `{BASKET_SIZE}` 只，不使用当前 7日年化。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage081_fixed_money_fund_basket_replay.py`
- 新增参数：`BASKET_SIZE={BASKET_SIZE}`、`RESERVE_CAPITAL={RESERVE_CAPITAL}`、`START_MONTHS={START_MONTHS}`。
- 修改参数：无正式交易参数。
- 删除参数：删除 Stage079/080 后续研究中的当前收益率筛选依赖。

## Basket

{_md_table(basket[['fund_code', 'fund_name_purchase', 'fund_type', 'purchase_status', 'redeem_status', 'purchase_min_yuan', 'daily_limit_yuan', 'fee_pct']])}

## Source Audit

{_md_table(source_audit)}

## 结果

{_md_table(variant_summary)}

## 结论

- 决策：`{decision['decision']}`。
- 回测指标说明：本阶段是账户层现金收益源重放，不新增交易订单；底层 C9 交易路径不变，因此不生成新增真实滑点、交易次数或胜率。
- 运行前过拟合反思：否。篮子选择不使用收益排序或坏窗口。
- 运行后过拟合反思：若后续按篮子内历史表现挑基金或调篮子大小，就是过拟合；本阶段只验证固定规则篮子的账户层可行性。
- 继续价值：有，但仍需真实交易渠道确认，不得直接接入实盘默认路径。

## 输出文件

- report：`{REPORT_PATH}`
- decision：`{DECISION_PATH}`
- basket：`{BASKET_PATH}`
- source_audit：`{SOURCE_AUDIT_PATH}`
- variant_summary：`{VARIANT_SUMMARY_PATH}`
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    decision = build()
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
