from __future__ import annotations

from dataclasses import dataclass
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
STAGE = "Stage078"
MODEL_TAG = "stage078_real_cash_yield_source_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage078_real_cash_yield_source_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage078_real_cash_yield_source_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE077_CURVES_PATH = (
    LINE_DIR
    / "outputs"
    / "stage077_c9_idle_reserve_cash_yield_proxy"
    / "rebuilt_c9_v2_stage077_c9_idle_reserve_cash_yield_proxy_curves_stage077_c9_idle_reserve_cash_yield_proxy_v2.csv.gz"
)

REQUESTED_END = pd.Timestamp("2026-06-30")
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
TRADING_CAPITAL = 150_000.0
RESERVE_CAPITAL = 150_000.0
TOTAL_CAPITAL = TRADING_CAPITAL + RESERVE_CAPITAL

CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
SOURCE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_source_audit_{MODEL_TAG}.csv"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
RETENTION_PATH = OUT / f"{OUTPUT_PREFIX}_retention_vs_official_c9_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_underwater_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class CashSource:
    source_id: str
    source_label: str
    source_kind: str
    annualized_column: str
    is_direct_product: bool
    notes: str


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


def _fetch_shibor_on() -> tuple[pd.DataFrame, CashSource]:
    import akshare as ak

    raw = ak.macro_china_shibor_all()
    frame = raw.rename(columns={"日期": "date", "O/N-定价": "annualized_rate_pct"}).copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["annualized_rate_pct"] = pd.to_numeric(frame["annualized_rate_pct"], errors="coerce")
    frame = frame[["date", "annualized_rate_pct"]].dropna().sort_values("date")
    source = CashSource(
        source_id="benchmark_shibor_on",
        source_label="SHIBOR O/N benchmark",
        source_kind="benchmark_rate",
        annualized_column="annualized_rate_pct",
        is_direct_product=False,
        notes="Benchmark only; not a directly investable reserve product.",
    )
    return frame, source


def _fetch_cfets_repo_query() -> tuple[pd.DataFrame, CashSource]:
    import akshare as ak

    raw = ak.repo_rate_query(symbol="回购定盘利率")
    frame = raw.rename(columns={"date": "date", "FR001": "annualized_rate_pct"}).copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["annualized_rate_pct"] = pd.to_numeric(frame["annualized_rate_pct"], errors="coerce")
    frame = frame[["date", "annualized_rate_pct"]].dropna().sort_values("date")
    source = CashSource(
        source_id="benchmark_cfets_fr001_query",
        source_label="CFETS repo fixing FR001 query",
        source_kind="benchmark_rate",
        annualized_column="annualized_rate_pct",
        is_direct_product=False,
        notes="Benchmark query has short recent history in current AKShare endpoint.",
    )
    return frame, source


def _month_ranges(start: str, end: str) -> list[tuple[str, str]]:
    start_ts = pd.Timestamp(start).to_period("M").to_timestamp()
    end_ts = pd.Timestamp(end).to_period("M").to_timestamp()
    ranges: list[tuple[str, str]] = []
    current = start_ts
    while current <= end_ts:
        month_end = current + pd.offsets.MonthEnd(0)
        chunk_end = min(month_end, pd.Timestamp(end))
        ranges.append((current.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        current = current + pd.offsets.MonthBegin(1)
    return ranges


def _fetch_cfets_repo_hist() -> tuple[pd.DataFrame, CashSource, list[str]]:
    import akshare as ak

    errors: list[str] = []
    pieces: list[pd.DataFrame] = []
    for start_date, end_date in _month_ranges("2020-01-01", REQUESTED_END.date().isoformat()):
        try:
            part = ak.repo_rate_hist(start_date=start_date, end_date=end_date)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{start_date}-{end_date}:{type(exc).__name__}:{exc}")
            continue
        if part is None or part.empty:
            continue
        pieces.append(part)
    raw = pd.concat(pieces, ignore_index=True, sort=False) if pieces else pd.DataFrame()
    if raw.empty:
        frame = pd.DataFrame(columns=["date", "annualized_rate_pct"])
    else:
        rate_col = "FDR001" if "FDR001" in raw.columns else "FR001"
        frame = raw.rename(columns={"date": "date", rate_col: "annualized_rate_pct"}).copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
        frame["annualized_rate_pct"] = pd.to_numeric(frame["annualized_rate_pct"], errors="coerce")
        frame = frame[["date", "annualized_rate_pct"]].dropna().drop_duplicates("date").sort_values("date")
    source = CashSource(
        source_id="benchmark_cfets_fdr001_hist",
        source_label="CFETS deposit repo fixing FDR001 history",
        source_kind="benchmark_rate",
        annualized_column="annualized_rate_pct",
        is_direct_product=False,
        notes="Monthly historical benchmark pulls; not a directly investable reserve product.",
    )
    return frame, source, errors


def _fetch_money_fund_000009() -> tuple[pd.DataFrame, CashSource]:
    import akshare as ak

    raw = ak.fund_money_fund_info_em(symbol="000009")
    frame = raw.rename(
        columns={"净值日期": "date", "每万份收益": "income_per_10k", "7日年化收益率": "annualized_rate_pct"}
    ).copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["income_per_10k"] = pd.to_numeric(frame["income_per_10k"], errors="coerce")
    frame["annualized_rate_pct"] = pd.to_numeric(frame["annualized_rate_pct"], errors="coerce")
    frame["purchase_status"] = raw.get("申购状态")
    frame["redeem_status"] = raw.get("赎回状态")
    frame = frame[["date", "income_per_10k", "annualized_rate_pct", "purchase_status", "redeem_status"]].dropna(
        subset=["date", "income_per_10k"]
    )
    frame = frame.sort_values("date")
    source = CashSource(
        source_id="product_money_fund_000009",
        source_label="Money fund 000009 actual income sample",
        source_kind="money_fund_actual_income",
        annualized_column="annualized_rate_pct",
        is_direct_product=True,
        notes="Actual daily per-10k income sample; current subscription status must be accepted separately.",
    )
    return frame, source


def _calendar_factor_from_rate(frame: pd.DataFrame, *, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    data = frame.dropna(subset=["date", "annualized_rate_pct"]).drop_duplicates("date").sort_values("date")
    calendar = pd.DataFrame({"date": pd.date_range(start, end, freq="D")})
    calendar = calendar.merge(data[["date", "annualized_rate_pct"]], on="date", how="left")
    raw_available = calendar["annualized_rate_pct"].notna()
    calendar["annualized_rate_pct"] = calendar["annualized_rate_pct"].ffill()
    calendar.loc[calendar["annualized_rate_pct"].isna(), "annualized_rate_pct"] = 0.0
    calendar["daily_return"] = np.power(1.0 + calendar["annualized_rate_pct"] / 100.0, 1.0 / 365.25) - 1.0
    calendar["gross_factor"] = (1.0 + calendar["daily_return"]).cumprod()
    calendar["raw_available"] = raw_available
    return calendar


def _calendar_factor_from_money_fund(frame: pd.DataFrame, *, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    data = frame.dropna(subset=["date", "income_per_10k"]).drop_duplicates("date").sort_values("date")
    calendar = pd.DataFrame({"date": pd.date_range(start, end, freq="D")})
    calendar = calendar.merge(
        data[["date", "income_per_10k", "annualized_rate_pct", "purchase_status", "redeem_status"]],
        on="date",
        how="left",
    )
    raw_available = calendar["income_per_10k"].notna()
    calendar["daily_return"] = pd.to_numeric(calendar["income_per_10k"], errors="coerce").fillna(0.0) / 10_000.0
    calendar["annualized_rate_pct"] = pd.to_numeric(calendar["annualized_rate_pct"], errors="coerce")
    calendar["gross_factor"] = (1.0 + calendar["daily_return"]).cumprod()
    calendar["raw_available"] = raw_available
    return calendar


def _source_status(source: CashSource, frame: pd.DataFrame, factor: pd.DataFrame, c9_dates: pd.Series) -> dict[str, Any]:
    date_min = pd.Timestamp(frame["date"].min()) if not frame.empty else pd.NaT
    date_max = pd.Timestamp(frame["date"].max()) if not frame.empty else pd.NaT
    c9_unique = pd.DataFrame({"date": pd.to_datetime(c9_dates).drop_duplicates().sort_values()})
    coverage = c9_unique.merge(factor[["date", "raw_available"]], on="date", how="left")
    c9_raw_coverage_pct = float(coverage["raw_available"].fillna(False).mean() * 100.0) if not coverage.empty else 0.0
    calendar_raw_coverage_pct = float(factor["raw_available"].fillna(False).mean() * 100.0) if not factor.empty else 0.0
    latest = frame.sort_values("date").tail(1)
    latest_rate = float(pd.to_numeric(latest.get(source.annualized_column), errors="coerce").iloc[0]) if not latest.empty else np.nan
    purchase_status = None
    redeem_status = None
    if "purchase_status" in latest.columns:
        purchase_status = str(latest["purchase_status"].iloc[0])
    if "redeem_status" in latest.columns:
        redeem_status = str(latest["redeem_status"].iloc[0])

    return {
        "source_id": source.source_id,
        "source_label": source.source_label,
        "source_kind": source.source_kind,
        "is_direct_product": source.is_direct_product,
        "raw_rows": int(len(frame)),
        "calendar_rows": int(len(factor)),
        "source_date_min": None if pd.isna(date_min) else date_min.date().isoformat(),
        "source_date_max": None if pd.isna(date_max) else date_max.date().isoformat(),
        "c9_date_raw_coverage_pct": c9_raw_coverage_pct,
        "calendar_raw_coverage_pct": calendar_raw_coverage_pct,
        "annualized_rate_min_pct": float(pd.to_numeric(frame.get(source.annualized_column), errors="coerce").min()),
        "annualized_rate_median_pct": float(pd.to_numeric(frame.get(source.annualized_column), errors="coerce").median()),
        "annualized_rate_latest_pct": latest_rate,
        "latest_purchase_status": purchase_status,
        "latest_redeem_status": redeem_status,
        "notes": source.notes,
    }


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
        "source_id": str(data["source_id"].iloc[0]),
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
    if sorted(c9["requested_start_month"].unique().tolist()) != list(START_MONTHS):
        raise RuntimeError("Stage078 expected exactly the predefined 13 start months")

    source_frames: list[tuple[pd.DataFrame, CashSource, list[str]]] = []
    fetch_errors: list[str] = []
    for fetcher in (_fetch_shibor_on, _fetch_cfets_repo_query, _fetch_money_fund_000009):
        try:
            frame, source = fetcher()
            source_frames.append((frame, source, []))
        except Exception as exc:  # noqa: BLE001
            fetch_errors.append(f"{fetcher.__name__}:{type(exc).__name__}:{exc}")
    try:
        frame, source, errors = _fetch_cfets_repo_hist()
        source_frames.append((frame, source, errors))
    except Exception as exc:  # noqa: BLE001
        fetch_errors.append(f"_fetch_cfets_repo_hist:{type(exc).__name__}:{exc}")

    date_start = min(pd.Timestamp(c9["date"].min()), pd.Timestamp("2020-01-01"))
    date_end = REQUESTED_END

    curve_rows: list[pd.DataFrame] = []
    official_rows: list[pd.DataFrame] = []
    for start_month, group in c9.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").drop_duplicates("date").copy()
        official_rows.append(
            pd.DataFrame(
                {
                    "requested_start_month": start_month,
                    "date": g["date"],
                    "version": "official_c9_15w_reference",
                    "variant_label": "Official C9 15w reference",
                    "source_id": "official_c9",
                    "account_capital_for_metrics": TRADING_CAPITAL,
                    "account_equity_for_metrics": g["c9_equity"],
                    "c9_equity": g["c9_equity"],
                    "reserve_equity": np.nan,
                }
            )
        )
    curve_rows.extend(official_rows)

    source_audits: list[dict[str, Any]] = []
    for frame, source, errors in source_frames:
        if source.source_kind == "money_fund_actual_income":
            factor = _calendar_factor_from_money_fund(frame, start=date_start, end=date_end)
        else:
            factor = _calendar_factor_from_rate(frame, start=date_start, end=date_end)
        audit = _source_status(source, frame, factor, c9["date"])
        audit["fetch_error_count"] = int(len(errors))
        audit["fetch_errors_sample"] = "; ".join(errors[:5])
        source_audits.append(audit)
        for start_month, group in c9.groupby("requested_start_month", sort=True):
            g = group.sort_values("date").drop_duplicates("date").copy()
            start_date = pd.Timestamp(g["date"].iloc[0])
            reserve_equity = _reserve_equity_on_strategy_dates(factor, g["date"], start_date)
            account_equity = g["c9_equity"].reset_index(drop=True) + reserve_equity.reset_index(drop=True)
            curve_rows.append(
                pd.DataFrame(
                    {
                        "requested_start_month": start_month,
                        "date": g["date"].reset_index(drop=True),
                        "version": f"c9_15w_plus_{source.source_id}",
                        "variant_label": f"C9 15w + {source.source_label}",
                        "source_id": source.source_id,
                        "account_capital_for_metrics": TOTAL_CAPITAL,
                        "account_equity_for_metrics": account_equity,
                        "c9_equity": g["c9_equity"].reset_index(drop=True),
                        "reserve_equity": reserve_equity.reset_index(drop=True),
                    }
                )
            )

    curves = pd.concat(curve_rows, ignore_index=True, sort=False)
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
                "source_id": str(group["source_id"].iloc[0]),
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
    candidates = variant_summary[~variant_summary["version"].eq("official_c9_15w_reference")].copy()
    candidates["passes_stage077_numeric_goal"] = (
        candidates["min_return_retention_ratio"].ge(0.5 - 1e-9)
        & candidates["worst_drawdown_pct"].gt(float(official_row["worst_drawdown_pct"]))
        & candidates["max_days_below_initial"].lt(int(official_row["max_days_below_initial"]))
        & candidates["max_consecutive_below_initial_days"].lt(int(official_row["max_consecutive_below_initial_days"]))
    )
    source_audit = pd.DataFrame(source_audits)
    source_audit["passes_stage077_numeric_goal"] = source_audit["source_id"].map(
        candidates.set_index("source_id")["passes_stage077_numeric_goal"].to_dict()
    ).fillna(False)
    source_audit["accepted_for_cash_governance_replay"] = (
        source_audit["passes_stage077_numeric_goal"].astype(bool)
        & source_audit["is_direct_product"].astype(bool)
        & source_audit["latest_purchase_status"].fillna("").str.contains("开放申购")
        & source_audit["latest_redeem_status"].fillna("").str.contains("开放赎回")
        & source_audit["c9_date_raw_coverage_pct"].ge(95.0)
    )
    source_audit.to_csv(SOURCE_AUDIT_PATH, index=False)
    variant_summary = variant_summary.merge(
        candidates[["version", "passes_stage077_numeric_goal"]],
        on="version",
        how="left",
    )
    variant_summary["passes_stage077_numeric_goal"] = variant_summary["passes_stage077_numeric_goal"].fillna(False)
    variant_summary = variant_summary.merge(
        source_audit[["source_id", "accepted_for_cash_governance_replay"]],
        on="source_id",
        how="left",
    )
    variant_summary["accepted_for_cash_governance_replay"] = variant_summary[
        "accepted_for_cash_governance_replay"
    ].fillna(False)
    variant_summary.to_csv(VARIANT_SUMMARY_PATH, index=False)

    accepted = source_audit[source_audit["accepted_for_cash_governance_replay"]]
    numeric_pass = source_audit[source_audit["passes_stage077_numeric_goal"]]
    if not accepted.empty:
        decision_name = "stage078_real_cash_source_accepted_for_cash_governance_replay"
    elif not numeric_pass.empty:
        decision_name = "stage078_numeric_pass_but_no_accepted_real_cash_source"
    else:
        decision_name = "stage078_no_real_cash_source_passed_numeric_gate"
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_name,
        "fetch_errors": fetch_errors,
        "accepted_source_count": int(len(accepted)),
        "numeric_pass_source_count": int(len(numeric_pass)),
        "source_audit_path": str(SOURCE_AUDIT_PATH),
        "variant_summary_path": str(VARIANT_SUMMARY_PATH),
        "created_at": datetime.now().replace(microsecond=0).isoformat(),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curves, variant_summary)
    _write_report(source_audit, variant_summary, retention, decision)
    _write_stage_record(source_audit, variant_summary, decision)
    return {"decision": decision, "variant_summary": variant_summary.to_dict(orient="records")}


def _plot(curves: pd.DataFrame, variant_summary: pd.DataFrame) -> None:
    plot_versions = ["official_c9_15w_reference"]
    plot_versions += (
        variant_summary[variant_summary["passes_stage077_numeric_goal"].astype(bool)]["version"].head(4).tolist()
    )
    starts = ["2022-01", "2022-07", "2023-01", "2024-07", "2026-01"]
    fig, axes = plt.subplots(2, 1, figsize=(15, 9), sharex=True)
    for version in plot_versions:
        for start in starts:
            data = curves[curves["version"].eq(version) & curves["requested_start_month"].eq(start)].sort_values("date")
            if data.empty:
                continue
            equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce")
            label = f"{start} {version.replace('c9_15w_plus_', '')}"
            axes[0].plot(data["date"], equity, linewidth=0.9, label=label)
            axes[1].plot(data["date"], _drawdown_pct(equity), linewidth=0.9, label=label)
    axes[0].axhline(TOTAL_CAPITAL, color="#6b7280", linestyle="--", linewidth=0.8, label="300k capital")
    axes[0].set_title("Stage078 real cash yield source audit: equity")
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
    source_audit: pd.DataFrame,
    variant_summary: pd.DataFrame,
    retention: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    focus_cols = [
        "version",
        "source_id",
        "start_count",
        "positive_count",
        "min_return_pct",
        "median_return_pct",
        "min_return_retention_ratio",
        "worst_drawdown_pct",
        "max_days_below_initial",
        "max_consecutive_below_initial_days",
        "passes_stage077_numeric_goal",
        "accepted_for_cash_governance_replay",
    ]
    audit_cols = [
        "source_id",
        "source_kind",
        "is_direct_product",
        "raw_rows",
        "source_date_min",
        "source_date_max",
        "c9_date_raw_coverage_pct",
        "annualized_rate_median_pct",
        "annualized_rate_latest_pct",
        "latest_purchase_status",
        "latest_redeem_status",
        "passes_stage077_numeric_goal",
        "accepted_for_cash_governance_replay",
        "notes",
    ]
    text = f"""# Stage078 real cash yield source audit

## 结论

- 决策：`{decision['decision']}`。
- 口径：沿用 Stage077 v2 的 `2020-01` 到 `2026-01` 逐半年 13 个起点，终点 `2026-06-30`；C9 15w 交易曲线不变，15w 储备金只按现金收益源累计。
- 本阶段只验证账户层现金收益源，不新增交易信号、订单、持仓或实盘入口。

## Source Audit

{_md_table(source_audit[audit_cols])}

## Variant Summary

{_md_table(variant_summary[focus_cols])}

## Retention 明细

{_md_table(retention[['version', 'requested_start_month', 'total_return_pct', 'official_return_pct', 'return_retention_ratio', 'max_drawdown_pct', 'days_below_delta', 'max_consecutive_below_delta']].head(80))}

## 输出

- source_audit: `{SOURCE_AUDIT_PATH}`
- variant_summary: `{VARIANT_SUMMARY_PATH}`
- curves: `{CURVES_PATH}`
- chart: `{CHART_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(source_audit: pd.DataFrame, variant_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = STAGES_DIR / f"{stamp}_stage078_real_cash_yield_source_audit.md"
    focus_cols = [
        "version",
        "source_id",
        "start_count",
        "positive_count",
        "min_return_pct",
        "median_return_pct",
        "min_return_retention_ratio",
        "worst_drawdown_pct",
        "max_days_below_initial",
        "max_consecutive_below_initial_days",
        "passes_stage077_numeric_goal",
        "accepted_for_cash_governance_replay",
    ]
    text = f"""# Stage078 real cash yield source audit

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().replace(microsecond=0).isoformat()}
- 阶段性质：真实/基准现金收益源账户层审计
- 回测起点：`2020-01` 到 `2026-01` 逐半年，终点 `{REQUESTED_END.date().isoformat()}`
- 是否重要突破：{'是，发现可进入现金治理回放的真实收益源' if decision['accepted_source_count'] else '否，暂未发现可直接接受的真实收益源'}

## 外部调研与判断

- managed futures/collateral return 资料支持现金或抵押品收益是账户总回报的一部分，但它不是交易 alpha。
- Backtrader/QuantConnect/pysystemtrade 这类框架也把利息或资本校正放在账户现金流/资本层，而不是交易信号层。
- 本阶段因此只做资金治理审计，不改 C9 交易逻辑。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage078_real_cash_yield_source_audit.py`
- 新增参数：`START_MONTHS={START_MONTHS}`、`RESERVE_CAPITAL={RESERVE_CAPITAL}`、`TOTAL_CAPITAL={TOTAL_CAPITAL}`。
- 修改参数：无正式交易参数。
- 删除参数：无。

## Source Audit

{_md_table(source_audit)}

## 结果

{_md_table(variant_summary[focus_cols])}

## 结论

- 决策：`{decision['decision']}`。
- 总滑点、总交易次数、胜率：本阶段是账户层现金收益源重放，不新增订单，底层 C9 交易路径不变，因此不生成新增真实滑点、交易次数或胜率。
- 运行前过拟合反思：否。真实收益源审计是 Stage077 的必要可实现性验证，不按坏窗口救参。
- 运行后过拟合反思：若按历史表现挑某只货币基金或忽略申购/赎回/税费/保证金占用，就是会计幻觉；本阶段以 accepted gate 阻止直接上线。
- 继续价值：{'有，已有可接受收益源可进入现金治理回放' if decision['accepted_source_count'] else '有但条件化，需要真实可投、可申赎、可审计的现金产品或券商计息账本'}。

## 输出文件

- report：`{REPORT_PATH}`
- decision：`{DECISION_PATH}`
- source_audit：`{SOURCE_AUDIT_PATH}`
- variant_summary：`{VARIANT_SUMMARY_PATH}`
"""
    path.write_text(text, encoding="utf-8")


def main() -> None:
    result = build()
    print(json.dumps(_json_safe(result["decision"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
