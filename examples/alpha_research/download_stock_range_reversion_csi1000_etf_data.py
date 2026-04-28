from __future__ import annotations

import json
import os
import time
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd
import tushare as ts

from audit_stock_range_reversion_hedge_data import STOCK_EQUITY_PATH, TRADING_DAYS, pct, safe_beta, safe_corr, to_float


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_csi1000_etf_data_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_csi1000_etf_data_v1"
DAILY_CACHE_DIR: Path = OUTPUT_DIR / "fund_daily_cache"

PLAIN_CSI1000_ETF_CODES: tuple[str, ...] = (
    "512100.SH",
    "516300.SH",
    "159845.SZ",
    "560010.SH",
    "159633.SZ",
    "159629.SZ",
    "560110.SH",
)
EXCLUDE_NAME_KEYWORDS: tuple[str, ...] = ("增强", "价值", "成长", "LOF", "退市", "A", "B")
SLEEP_SECONDS: float = float(os.getenv("TUSHARE_SLEEP_SECONDS", "0.6"))
REFRESH: bool = os.getenv("REFRESH_CSI1000_ETF", "0").strip() == "1"


def get_pro() -> Any:
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is missing")
    return ts.pro_api(token)


def load_stock_benchmark() -> pd.DataFrame:
    frame = pd.read_csv(STOCK_EQUITY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame.sort_values(["date", "roundtrip_cost_bps"]).drop_duplicates("date", keep="first")
    return frame[["date", "benchmark_daily_ret", "benchmark_active_daily_ret", "return_gross_exposure"]].reset_index(
        drop=True
    )


def fetch_fund_basic(pro: Any) -> pd.DataFrame:
    fields = ",".join(
        [
            "ts_code",
            "name",
            "management",
            "custodian",
            "fund_type",
            "found_date",
            "due_date",
            "list_date",
            "issue_amount",
            "m_fee",
            "c_fee",
        ]
    )
    frame = pro.fund_basic(market="E", fields=fields)
    frame = frame.sort_values(["list_date", "ts_code"]).reset_index(drop=True)
    return frame


def filter_csi1000_candidates(fund_basic: pd.DataFrame) -> pd.DataFrame:
    name = fund_basic["name"].astype(str)
    candidates = fund_basic[name.str.contains("1000|中证1000|1000ETF", case=False, na=False)].copy()
    candidates["is_selected_plain_csi1000_etf"] = candidates["ts_code"].isin(PLAIN_CSI1000_ETF_CODES)
    candidates["has_excluded_keyword"] = candidates["name"].astype(str).apply(
        lambda value: any(keyword in value for keyword in EXCLUDE_NAME_KEYWORDS)
    )
    return candidates.sort_values(["is_selected_plain_csi1000_etf", "list_date"], ascending=[False, True]).reset_index(
        drop=True
    )


def fetch_fund_daily(pro: Any, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    DAILY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = DAILY_CACHE_DIR / f"{ts_code}_{start_date}_{end_date}.csv"
    if cache_path.exists() and not REFRESH:
        return pd.read_csv(cache_path, encoding="utf-8-sig")

    frame = pro.fund_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    frame.to_csv(cache_path, index=False, encoding="utf-8-sig")
    time.sleep(SLEEP_SECONDS)
    return frame


def download_selected_daily(pro: Any, selected_codes: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    status_rows: list[dict[str, Any]] = []
    for index, ts_code in enumerate(selected_codes, start=1):
        try:
            frame = fetch_fund_daily(pro, ts_code, start_date, end_date)
            status_rows.append(
                {
                    "ts_code": ts_code,
                    "status": "downloaded",
                    "rows": int(len(frame)),
                    "message": "",
                    "order": index,
                }
            )
            if not frame.empty:
                parts.append(frame)
            print(f"[{index}/{len(selected_codes)}] {ts_code} rows={len(frame)}", flush=True)
        except Exception as exc:
            status_rows.append(
                {
                    "ts_code": ts_code,
                    "status": "failed",
                    "rows": 0,
                    "message": repr(exc),
                    "order": index,
                }
            )
            print(f"[{index}/{len(selected_codes)}] {ts_code} failed={exc!r}", flush=True)
            time.sleep(SLEEP_SECONDS)
    pd.DataFrame(status_rows).to_csv(OUTPUT_DIR / f"{PREFIX}_download_status.csv", index=False, encoding="utf-8-sig")
    return pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()


def normalize_daily(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return daily
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["trade_date"].astype(str)).dt.date
    for column in ("pre_close", "open", "high", "low", "close", "change", "pct_chg", "vol", "amount"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.sort_values(["ts_code", "date"]).reset_index(drop=True)
    frame["daily_ret"] = frame["pct_chg"] / 100.0
    frame["close_pct_ret"] = frame.groupby("ts_code")["close"].pct_change()
    return frame


def annualized_tracking_error(diff: pd.Series) -> float:
    clean = diff.dropna()
    if len(clean) <= 1:
        return 0.0
    return to_float(clean.std(ddof=1) * sqrt(TRADING_DAYS))


def build_etf_summary(
    candidates: pd.DataFrame,
    daily: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    tracking_rows: list[dict[str, Any]] = []
    stock_dates = set(benchmark["date"].dropna().unique())
    active_dates = set(benchmark.loc[benchmark["return_gross_exposure"] > 0, "date"].dropna().unique())

    for row in candidates.itertuples(index=False):
        ts_code = str(row.ts_code)
        fund_rows = daily[daily["ts_code"] == ts_code].sort_values("date")
        overlap_dates = set(fund_rows["date"].dropna().unique()) & stock_dates if not fund_rows.empty else set()
        active_overlap_dates = set(fund_rows["date"].dropna().unique()) & active_dates if not fund_rows.empty else set()
        rows.append(
            {
                "ts_code": ts_code,
                "name": str(row.name),
                "management": str(row.management),
                "fund_type": str(row.fund_type),
                "found_date": str(row.found_date),
                "list_date": str(row.list_date),
                "due_date": str(row.due_date),
                "m_fee": to_float(row.m_fee),
                "c_fee": to_float(row.c_fee),
                "issue_amount": to_float(row.issue_amount),
                "is_selected_plain_csi1000_etf": bool(row.is_selected_plain_csi1000_etf),
                "has_excluded_keyword": bool(row.has_excluded_keyword),
                "daily_rows": int(len(fund_rows)),
                "first_trade_date": str(fund_rows["date"].min()) if not fund_rows.empty else "",
                "last_trade_date": str(fund_rows["date"].max()) if not fund_rows.empty else "",
                "overlap_days": len(overlap_dates),
                "overlap_ratio_stock_days": len(overlap_dates) / len(stock_dates) if stock_dates else 0.0,
                "active_overlap_days": len(active_overlap_dates),
                "overlap_ratio_active_days": len(active_overlap_dates) / len(active_dates) if active_dates else 0.0,
                "median_amount_raw": to_float(fund_rows["amount"].median()) if not fund_rows.empty else 0.0,
                "p25_amount_raw": to_float(fund_rows["amount"].quantile(0.25)) if not fund_rows.empty else 0.0,
                "p10_amount_raw": to_float(fund_rows["amount"].quantile(0.10)) if not fund_rows.empty else 0.0,
                "median_vol_raw": to_float(fund_rows["vol"].median()) if not fund_rows.empty else 0.0,
            }
        )
        if fund_rows.empty:
            continue
        merged = fund_rows.merge(benchmark, on="date", how="inner")
        clean = merged.dropna(subset=["daily_ret", "benchmark_daily_ret"])
        diff = clean["daily_ret"] - clean["benchmark_daily_ret"]
        active_clean = clean[clean["return_gross_exposure"] > 0]
        tracking_rows.append(
            {
                "ts_code": ts_code,
                "name": str(row.name),
                "is_selected_plain_csi1000_etf": bool(row.is_selected_plain_csi1000_etf),
                "days": int(len(clean)),
                "active_days": int(len(active_clean)),
                "first_date": str(clean["date"].min()) if len(clean) else "",
                "last_date": str(clean["date"].max()) if len(clean) else "",
                "corr_to_csi1000": safe_corr(clean["daily_ret"], clean["benchmark_daily_ret"]),
                "beta_to_csi1000": safe_beta(clean["daily_ret"], clean["benchmark_daily_ret"]),
                "annualized_tracking_error": annualized_tracking_error(diff),
                "annualized_mean_return_diff": to_float(diff.mean()) * TRADING_DAYS if len(clean) else 0.0,
                "active_corr_to_csi1000": safe_corr(active_clean["daily_ret"], active_clean["benchmark_daily_ret"])
                if len(active_clean)
                else 0.0,
                "active_beta_to_csi1000": safe_beta(active_clean["daily_ret"], active_clean["benchmark_daily_ret"])
                if len(active_clean)
                else 0.0,
                "median_amount_raw": to_float(clean["amount"].median()) if len(clean) else 0.0,
                "p10_amount_raw": to_float(clean["amount"].quantile(0.10)) if len(clean) else 0.0,
            }
        )

    return (
        pd.DataFrame(rows).sort_values(
            ["is_selected_plain_csi1000_etf", "overlap_days", "median_amount_raw"],
            ascending=[False, False, False],
        ),
        pd.DataFrame(tracking_rows).sort_values(
            ["is_selected_plain_csi1000_etf", "days", "annualized_tracking_error"],
            ascending=[False, False, True],
        ),
    )


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 40) -> str:
    if frame.empty:
        return "无数据"
    return frame.loc[:, columns].head(max_rows).to_markdown(index=False)


def write_report(candidates: pd.DataFrame, summary: pd.DataFrame, tracking: pd.DataFrame, start_date: str, end_date: str) -> Path:
    selected_tracking = tracking[tracking["is_selected_plain_csi1000_etf"]].copy()
    selected_summary = summary[summary["is_selected_plain_csi1000_etf"]].copy()
    oldest = selected_summary.sort_values("first_trade_date").head(1)
    best_overlap = selected_summary.sort_values(["overlap_days", "median_amount_raw"], ascending=False).head(1)
    best_tracking = selected_tracking.sort_values(["days", "annualized_tracking_error"], ascending=[False, True]).head(1)
    oldest_code = str(oldest.iloc[0]["ts_code"]) if not oldest.empty else ""
    best_overlap_code = str(best_overlap.iloc[0]["ts_code"]) if not best_overlap.empty else ""
    best_tracking_code = str(best_tracking.iloc[0]["ts_code"]) if not best_tracking.empty else ""
    best_tracking_te = to_float(best_tracking.iloc[0]["annualized_tracking_error"]) if not best_tracking.empty else 0.0

    report = f"""# 股票震荡中证1000 ETF数据补齐审计 v1

- 记录时间：{datetime.now().strftime("%Y-%m-%d %H:%M CST")}
- 当前研究线：股票震荡 `market_down`，与第78趋势策略、期货震荡策略隔离。
- 本阶段性质：数据下载与可用性审计，不是策略回测。
- Tushare请求节奏：逐只基金拉取，间隔`{SLEEP_SECONDS:.2f}`秒。
- 下载区间：`{start_date}`到`{end_date}`。

## 下载结论

- Tushare基金基础表筛出中证1000相关基金/ETF `{len(candidates)}` 只。
- 本阶段下载普通中证1000 ETF `{len(PLAIN_CSI1000_ETF_CODES)}` 只：`{", ".join(PLAIN_CSI1000_ETF_CODES)}`。
- 最早可用普通ETF是 `{oldest_code}`，可以覆盖2018之后较长历史。
- 覆盖天数和流动性综合看，当前候选里 `{best_overlap_code}` 最适合先做全历史ETF路线审计。
- 跟踪误差口径看，全样本覆盖优先下 `{best_tracking_code}` 年化跟踪误差约 `{pct(best_tracking_te)}`。
- `amount`字段保留Tushare原始口径；实盘容量前需要再核对成交额单位和盘口冲击。

## 相关基金候选

{markdown_table(candidates, ["ts_code", "name", "list_date", "due_date", "m_fee", "c_fee", "is_selected_plain_csi1000_etf", "has_excluded_keyword"])}

## 普通ETF覆盖与流动性

{markdown_table(selected_summary, ["ts_code", "name", "first_trade_date", "last_trade_date", "overlap_days", "overlap_ratio_stock_days", "active_overlap_days", "overlap_ratio_active_days", "median_amount_raw", "p10_amount_raw", "m_fee", "c_fee"])}

## 普通ETF跟踪

{markdown_table(selected_tracking, ["ts_code", "name", "days", "corr_to_csi1000", "beta_to_csi1000", "annualized_tracking_error", "annualized_mean_return_diff", "median_amount_raw", "p10_amount_raw"])}

## 运行前过拟合反思

- 判断：否。
- 原因：本阶段只补数据并做覆盖、流动性、跟踪误差审计，不生成交易参数。

## 运行后过拟合反思

- 判断：否。
- 原因：没有选择最优ETF进入策略，只标记候选优先级，并保留了上市时间、费用和成交额差异。

## 运行前继续价值反思

- 判断：是。
- 原因：IM对冲被一手颗粒度约束挡住后，ETF是更适合当前资金体量的低颗粒度工具。

## 运行后继续价值反思

- 判断：有。
- 原因：ETF数据已补齐，且存在能覆盖2018后的普通中证1000ETF；下一步可以做ETF对冲/替代的低颗粒度压力测试，但必须纳入ETF跟踪误差和成交额约束。

## 决策

- 不接入第78。
- 不进入正式股票策略。
- 不做第78 A/B/C。
- 下一步优先做“股票篮子 + 普通中证1000ETF”的低颗粒度压力测试，而不是继续优化IM对冲比例。

## 输出文件

- `{OUTPUT_DIR / f"{PREFIX}_fund_basic_all.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_csi1000_candidates.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_selected_daily.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_etf_summary.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_tracking_metrics.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_download_status.csv"}`
"""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    benchmark = load_stock_benchmark()
    start_date = pd.to_datetime(min(benchmark["date"])).strftime("%Y%m%d")
    end_date = pd.to_datetime(max(benchmark["date"])).strftime("%Y%m%d")

    pro = get_pro()
    fund_basic = fetch_fund_basic(pro)
    candidates = filter_csi1000_candidates(fund_basic)
    selected_codes = [code for code in PLAIN_CSI1000_ETF_CODES if code in set(fund_basic["ts_code"])]
    daily = normalize_daily(download_selected_daily(pro, selected_codes, start_date, end_date))
    summary, tracking = build_etf_summary(candidates, daily, benchmark)

    fund_basic.to_csv(OUTPUT_DIR / f"{PREFIX}_fund_basic_all.csv", index=False, encoding="utf-8-sig")
    candidates.to_csv(OUTPUT_DIR / f"{PREFIX}_csi1000_candidates.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(OUTPUT_DIR / f"{PREFIX}_selected_daily.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT_DIR / f"{PREFIX}_etf_summary.csv", index=False, encoding="utf-8-sig")
    tracking.to_csv(OUTPUT_DIR / f"{PREFIX}_tracking_metrics.csv", index=False, encoding="utf-8-sig")
    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "stock_equity_path": str(STOCK_EQUITY_PATH),
        "start_date": start_date,
        "end_date": end_date,
        "selected_codes": selected_codes,
        "sleep_seconds": SLEEP_SECONDS,
        "refresh": REFRESH,
    }
    (OUTPUT_DIR / f"{PREFIX}_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report_path = write_report(candidates, summary, tracking, start_date, end_date)

    print(f"output_dir={OUTPUT_DIR}")
    print(f"report={report_path}")
    print(summary.to_string(index=False))
    print(tracking.to_string(index=False))


if __name__ == "__main__":
    main()
