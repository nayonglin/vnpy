from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import tushare as ts

from analyze_stock_range_reversion_etf_industry_rotation_readiness import parse_yyyymmdd, pct, safe_float


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
READINESS_DIR: Path = NATIVE_RESULTS_DIR / "stock_range_reversion_etf_industry_rotation_readiness_2018_2026"
READINESS_PREFIX: str = "stock_range_reversion_etf_industry_rotation_readiness_v1"
CANDIDATE_PATH: Path = READINESS_DIR / f"{READINESS_PREFIX}_sector_candidate_inventory.csv"

OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_sector_etf_data_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_sector_etf_data_v1"
DAILY_CACHE_DIR: Path = OUTPUT_DIR / "fund_daily_cache"

START_DATE: str = os.getenv("SECTOR_ETF_START_DATE", "20180101")
END_DATE: str = os.getenv("SECTOR_ETF_END_DATE", datetime.now().strftime("%Y%m%d"))
MAX_DOWNLOADS: int = int(os.getenv("SECTOR_ETF_MAX_DOWNLOADS", "120") or 120)
PER_BUCKET_LIMIT: int = int(os.getenv("SECTOR_ETF_PER_BUCKET_LIMIT", "18") or 18)
MIN_LIST_DATE: str = os.getenv("SECTOR_ETF_MIN_LIST_DATE", "20230101")
SLEEP_SECONDS: float = float(os.getenv("TUSHARE_FUND_DAILY_SLEEP_SECONDS", "2.0") or 0.0)
RETRIES: int = int(os.getenv("TUSHARE_FUND_DAILY_RETRIES", "5") or 1)
RETRY_SLEEP_SECONDS: float = float(os.getenv("TUSHARE_FUND_DAILY_RETRY_SLEEP_SECONDS", "25") or 0.0)
REFRESH: bool = os.getenv("REFRESH_SECTOR_ETF", "0").strip() == "1"
TRADING_DAYS: int = 252

MANAGEMENT_TIER: tuple[str, ...] = (
    "华夏基金",
    "易方达基金",
    "华泰柏瑞基金",
    "国泰基金",
    "广发基金",
    "富国基金",
    "南方基金",
    "嘉实基金",
    "招商基金",
    "银华基金",
    "博时基金",
    "华宝基金",
    "汇添富基金",
)

BUCKET_ORDER: tuple[str, ...] = (
    "financial_real_estate",
    "technology",
    "advanced_manufacturing",
    "healthcare",
    "consumer",
    "cyclicals",
    "defensive",
)


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def get_pro() -> Any:
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is missing")
    return ts.pro_api(token)


def management_rank(value: Any) -> int:
    text = "" if pd.isna(value) else str(value)
    if text in MANAGEMENT_TIER:
        return MANAGEMENT_TIER.index(text)
    return len(MANAGEMENT_TIER)


def normalize_list_date(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    work["list_dt"] = work["list_date"].map(parse_yyyymmdd)
    work["min_list_dt"] = pd.to_datetime(MIN_LIST_DATE, format="%Y%m%d", errors="coerce")
    return work


def select_representative_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    work = normalize_list_date(candidates)
    work = work[
        (work["is_current_listed"].astype(str) == "True")
        & work["list_dt"].notna()
        & (work["list_dt"] <= work["min_list_dt"])
    ].copy()
    if work.empty:
        return work
    work["management_rank"] = work["management"].map(management_rank)
    work["m_fee_num"] = pd.to_numeric(work.get("m_fee"), errors="coerce").fillna(9.9)
    work["c_fee_num"] = pd.to_numeric(work.get("c_fee"), errors="coerce").fillna(9.9)
    work = work.sort_values(
        ["industry_bucket", "list_dt", "management_rank", "m_fee_num", "c_fee_num", "ts_code"]
    ).reset_index(drop=True)

    bucket_frames: dict[str, list[dict[str, Any]]] = {}
    for bucket, group in work.groupby("industry_bucket", sort=False):
        group = group.head(PER_BUCKET_LIMIT).copy()
        bucket_frames[str(bucket)] = group.to_dict("records")

    selected_rows: list[dict[str, Any]] = []
    while len(selected_rows) < MAX_DOWNLOADS:
        made_progress = False
        for bucket in BUCKET_ORDER:
            rows = bucket_frames.get(bucket, [])
            if not rows:
                continue
            selected_rows.append(rows.pop(0))
            made_progress = True
            if len(selected_rows) >= MAX_DOWNLOADS:
                break
        if not made_progress:
            break

    selected = pd.DataFrame(selected_rows)
    if selected.empty:
        return selected
    selected["selection_rank"] = range(1, len(selected) + 1)
    selected["selection_reason"] = (
        "当前上市；list_date不晚于"
        + MIN_LIST_DATE
        + "；按行业桶分散抽样，桶内优先长历史和头部管理人。"
    )
    return selected.drop(columns=["min_list_dt"], errors="ignore")


def call_with_retries(name: str, func: Any, **kwargs: Any) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            frame = func(**kwargs)
            if SLEEP_SECONDS:
                time.sleep(SLEEP_SECONDS)
            return frame
        except Exception as exc:
            last_error = exc
            print(f"[tushare] retry {attempt}/{RETRIES} failed {name}: {exc}", flush=True)
            if attempt < RETRIES and RETRY_SLEEP_SECONDS:
                time.sleep(RETRY_SLEEP_SECONDS)
    raise RuntimeError(f"Tushare call failed after retries for {name}: {last_error}")


def fetch_fund_daily(pro: Any, ts_code: str) -> pd.DataFrame:
    DAILY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = DAILY_CACHE_DIR / f"{ts_code}_{START_DATE}_{END_DATE}.csv"
    if cache_path.exists() and not REFRESH:
        return pd.read_csv(cache_path, encoding="utf-8-sig")
    frame = call_with_retries(
        f"fund_daily {ts_code}",
        pro.fund_daily,
        ts_code=ts_code,
        start_date=START_DATE,
        end_date=END_DATE,
    )
    frame.to_csv(cache_path, index=False, encoding="utf-8-sig")
    return frame


def download_selected_daily(pro: Any, selected: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    parts: list[pd.DataFrame] = []
    status_rows: list[dict[str, Any]] = []
    total = len(selected)
    for index, row in enumerate(selected.itertuples(index=False), start=1):
        ts_code = str(row.ts_code)
        try:
            frame = fetch_fund_daily(pro, ts_code)
            status_rows.append(
                {
                    "ts_code": ts_code,
                    "name": str(row.name),
                    "industry_bucket": str(row.industry_bucket),
                    "status": "downloaded",
                    "rows": int(len(frame)),
                    "message": "",
                    "order": index,
                }
            )
            if not frame.empty:
                frame = frame.copy()
                frame["industry_bucket"] = str(row.industry_bucket)
                frame["etf_name"] = str(row.name)
                parts.append(frame)
            print(f"[{index}/{total}] {ts_code} {row.name} rows={len(frame)}", flush=True)
        except Exception as exc:
            status_rows.append(
                {
                    "ts_code": ts_code,
                    "name": str(row.name),
                    "industry_bucket": str(row.industry_bucket),
                    "status": "failed",
                    "rows": 0,
                    "message": repr(exc),
                    "order": index,
                }
            )
            print(f"[{index}/{total}] {ts_code} {row.name} failed={exc!r}", flush=True)
            if SLEEP_SECONDS:
                time.sleep(SLEEP_SECONDS)
    daily = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    return daily, pd.DataFrame(status_rows)


def normalize_daily(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return daily
    frame = daily.copy()
    frame["date"] = pd.to_datetime(frame["trade_date"].astype(str), format="%Y%m%d", errors="coerce").dt.date
    for column in ("pre_close", "open", "high", "low", "close", "change", "pct_chg", "vol", "amount"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.sort_values(["ts_code", "date"]).reset_index(drop=True)
    frame["daily_ret"] = frame["pct_chg"] / 100.0
    frame["close_pct_ret"] = frame.groupby("ts_code")["close"].pct_change()
    frame["raw_vs_pct_ret_abs_diff"] = (frame["close_pct_ret"] - frame["daily_ret"]).abs()
    return frame


def equity_and_drawdown(returns: pd.Series) -> tuple[pd.Series, pd.Series]:
    equity_values: list[float] = []
    drawdown_values: list[float] = []
    equity = 1.0
    peak = 1.0
    for value in returns.fillna(0.0):
        equity *= 1.0 + safe_float(value, 0.0)
        peak = max(peak, equity)
        equity_values.append(equity)
        drawdown_values.append(equity / peak - 1.0 if peak else 0.0)
    return pd.Series(equity_values, index=returns.index), pd.Series(drawdown_values, index=returns.index)


def summarize_daily(selected: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in selected.itertuples(index=False):
        ts_code = str(row.ts_code)
        group = daily[daily["ts_code"] == ts_code].sort_values("date") if not daily.empty else pd.DataFrame()
        if group.empty:
            rows.append(
                {
                    "ts_code": ts_code,
                    "name": str(row.name),
                    "industry_bucket": str(row.industry_bucket),
                    "selection_rank": int(row.selection_rank),
                    "rows": 0,
                    "first_trade_date": "",
                    "last_trade_date": "",
                    "years": 0.0,
                    "final_equity": float("nan"),
                    "total_return": float("nan"),
                    "max_drawdown": float("nan"),
                    "annualized_vol": float("nan"),
                    "median_amount_raw": float("nan"),
                    "p10_amount_raw": float("nan"),
                    "max_raw_vs_pct_ret_abs_diff": float("nan"),
                    "split_artifact_suspect_days": 0,
                }
            )
            continue
        equity, drawdown = equity_and_drawdown(group["daily_ret"])
        raw_diff = pd.to_numeric(group["raw_vs_pct_ret_abs_diff"], errors="coerce")
        rows.append(
            {
                "ts_code": ts_code,
                "name": str(row.name),
                "industry_bucket": str(row.industry_bucket),
                "selection_rank": int(row.selection_rank),
                "rows": int(len(group)),
                "first_trade_date": str(group["date"].iloc[0]),
                "last_trade_date": str(group["date"].iloc[-1]),
                "years": len(group) / TRADING_DAYS,
                "final_equity": float(equity.iloc[-1]),
                "total_return": float(equity.iloc[-1] - 1.0),
                "max_drawdown": float(drawdown.min()),
                "annualized_vol": float(group["daily_ret"].std(ddof=0) * (TRADING_DAYS**0.5)),
                "median_amount_raw": float(group["amount"].median()),
                "p10_amount_raw": float(group["amount"].quantile(0.10)),
                "max_raw_vs_pct_ret_abs_diff": float(raw_diff.max(skipna=True)),
                "split_artifact_suspect_days": int((raw_diff > 0.005).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["industry_bucket", "selection_rank"]).reset_index(drop=True)


def build_bucket_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    available = summary[summary["rows"] > 0].copy()
    if available.empty:
        return pd.DataFrame()
    return (
        available.groupby("industry_bucket")
        .agg(
            etf_count=("ts_code", "count"),
            long_history_5y_count=("years", lambda s: int((s >= 5.0).sum())),
            median_years=("years", "median"),
            median_amount_raw=("median_amount_raw", "median"),
            p10_amount_raw_median=("p10_amount_raw", "median"),
            median_total_return=("total_return", "median"),
            worst_max_drawdown=("max_drawdown", "min"),
            split_artifact_suspect_days=("split_artifact_suspect_days", "sum"),
        )
        .reset_index()
        .sort_values(["long_history_5y_count", "etf_count"], ascending=False)
    )


def markdown_table(frame: pd.DataFrame, columns: list[str] | None = None, limit: int = 20) -> str:
    if frame.empty:
        return "\n无数据。\n"
    work = frame.copy()
    if columns is not None:
        work = work[[col for col in columns if col in work.columns]]
    if limit > 0:
        work = work.head(limit)
    return work.to_markdown(index=False)


def build_report(
    selected: pd.DataFrame,
    status: pd.DataFrame,
    summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M CST")
    status_counts = status["status"].value_counts().to_dict() if not status.empty else {}
    selected_display = selected.copy()
    if "list_date" in selected_display.columns:
        selected_display["list_date"] = selected_display["list_date"].map(lambda value: str(value).replace(".0", ""))
    summary_display = summary.copy()
    for column in ("total_return", "max_drawdown", "annualized_vol"):
        if column in summary_display.columns:
            summary_display[f"{column}_pct"] = summary_display[column].map(pct)
    bucket_display = bucket_summary.copy()
    for column in ("median_total_return", "worst_max_drawdown"):
        if column in bucket_display.columns:
            bucket_display[f"{column}_pct"] = bucket_display[column].map(pct)
    return f"""# 股票震荡行业/主题ETF数据包 v1

- 记录时间：{now}
- 当前研究线：股票震荡独立策略研究，不接入第78。
- 本阶段性质：行业/主题ETF数据补齐与数据体检，不是策略回测。
- 下载区间：`{START_DATE}` 到 `{END_DATE}`。
- 下载节奏：每次Tushare请求后 sleep `{SLEEP_SECONDS}` 秒，失败重试 `{RETRIES}` 次。
- 候选选择：当前上市、`list_date <= {MIN_LIST_DATE}`，按行业桶分散抽样，桶内优先长历史和头部管理人。
- 选中候选数：`{len(selected)}`。
- 下载状态：`{status_counts}`。

## 行业桶数据概览

{markdown_table(bucket_display, ["industry_bucket", "etf_count", "long_history_5y_count", "median_years", "median_amount_raw", "p10_amount_raw_median", "median_total_return_pct", "worst_max_drawdown_pct", "split_artifact_suspect_days"], 20)}

## 下载标的样本

{markdown_table(selected_display, ["selection_rank", "ts_code", "name", "industry_bucket", "list_date", "management", "m_fee", "c_fee"], 40)}

## ETF数据体检样本

{markdown_table(summary_display, ["ts_code", "name", "industry_bucket", "rows", "first_trade_date", "last_trade_date", "years", "median_amount_raw", "p10_amount_raw", "total_return_pct", "max_drawdown_pct", "split_artifact_suspect_days"], 40)}

## 运行前过拟合反思

- 判断：否。
- 原因：本阶段只按事前规则补数据，不根据收益表现挑ETF，不回测策略。

## 运行后过拟合反思

- 判断：否。
- 原因：输出保留全部选中ETF的成功/失败、覆盖、流动性和异常价格差异，不做参数选择。

## 运行前继续价值反思

- 判断：是。
- 原因：第309阶段确认行业/主题ETF候选存在，但本地日线缺失，必须先补数据。

## 运行后继续价值反思

- 判断：是。
- 原因：若数据覆盖和流动性通过，下一步可以做行业中期强势+短期回撤的信号归因；若覆盖不足，则应转向行业指数而不是ETF实盘标的。

## 输出文件

- `{PREFIX}_selected_basic.csv`
- `{PREFIX}_download_status.csv`
- `{PREFIX}_selected_daily.csv`
- `{PREFIX}_summary.csv`
- `{PREFIX}_bucket_summary.csv`
- `{PREFIX}_meta.json`
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = read_csv(CANDIDATE_PATH)
    if candidates.empty:
        raise FileNotFoundError(f"Sector ETF candidate inventory not found: {CANDIDATE_PATH}")
    selected = select_representative_candidates(candidates)
    if selected.empty:
        raise RuntimeError("No sector ETF candidates selected")
    selected.to_csv(OUTPUT_DIR / f"{PREFIX}_selected_basic.csv", index=False, encoding="utf-8-sig")

    pro = get_pro()
    raw_daily, status = download_selected_daily(pro, selected)
    daily = normalize_daily(raw_daily)
    summary = summarize_daily(selected, daily)
    bucket_summary = build_bucket_summary(summary)

    status.to_csv(OUTPUT_DIR / f"{PREFIX}_download_status.csv", index=False, encoding="utf-8-sig")
    daily.to_csv(OUTPUT_DIR / f"{PREFIX}_selected_daily.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT_DIR / f"{PREFIX}_summary.csv", index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(OUTPUT_DIR / f"{PREFIX}_bucket_summary.csv", index=False, encoding="utf-8-sig")

    meta = {
        "generated_at": datetime.now().isoformat(),
        "start_date": START_DATE,
        "end_date": END_DATE,
        "max_downloads": MAX_DOWNLOADS,
        "per_bucket_limit": PER_BUCKET_LIMIT,
        "min_list_date": MIN_LIST_DATE,
        "sleep_seconds": SLEEP_SECONDS,
        "retries": RETRIES,
        "selected_count": int(len(selected)),
        "download_status": status["status"].value_counts().to_dict() if not status.empty else {},
        "daily_rows": int(len(daily)),
        "summary_rows": int(len(summary)),
        "source_candidate_path": str(CANDIDATE_PATH),
    }
    write_json(OUTPUT_DIR / f"{PREFIX}_meta.json", meta)

    report = build_report(selected, status, summary, bucket_summary)
    (OUTPUT_DIR / f"{PREFIX}_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
