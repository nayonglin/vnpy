from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd
import tushare as ts


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_broad_etf_data_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_broad_etf_data_v1"
DAILY_CACHE_DIR: Path = OUTPUT_DIR / "fund_daily_cache"

START_DATE: str = os.getenv("BROAD_ETF_START_DATE", "20180101")
END_DATE: str = os.getenv("BROAD_ETF_END_DATE", datetime.now().strftime("%Y%m%d"))
SLEEP_SECONDS: float = float(os.getenv("TUSHARE_FUND_DAILY_SLEEP_SECONDS", "1.2") or 0.0)
RETRIES: int = int(os.getenv("TUSHARE_FUND_DAILY_RETRIES", "5") or 1)
RETRY_SLEEP_SECONDS: float = float(os.getenv("TUSHARE_FUND_DAILY_RETRY_SLEEP_SECONDS", "20") or 0.0)
REFRESH: bool = os.getenv("REFRESH_BROAD_ETF", "0").strip() == "1"
TRADING_DAYS: int = 252


@dataclass(frozen=True)
class BroadEtfSpec:
    ts_code: str
    index_bucket: str
    index_name: str
    role: str


BROAD_ETF_UNIVERSE: tuple[BroadEtfSpec, ...] = (
    BroadEtfSpec("510050.SH", "large_cap", "上证50", "primary"),
    BroadEtfSpec("510300.SH", "large_cap", "沪深300", "primary"),
    BroadEtfSpec("159919.SZ", "large_cap", "沪深300", "cross_check"),
    BroadEtfSpec("510500.SH", "mid_small_cap", "中证500", "primary"),
    BroadEtfSpec("159922.SZ", "mid_small_cap", "中证500", "cross_check"),
    BroadEtfSpec("512100.SH", "small_cap", "中证1000", "primary"),
    BroadEtfSpec("159845.SZ", "small_cap", "中证1000", "cross_check"),
    BroadEtfSpec("159901.SZ", "growth", "深证100", "primary"),
    BroadEtfSpec("159915.SZ", "growth", "创业板", "primary"),
    BroadEtfSpec("159908.SZ", "growth", "创业板", "cross_check"),
    BroadEtfSpec("588000.SH", "growth", "科创50", "primary"),
    BroadEtfSpec("588080.SH", "growth", "科创50", "cross_check"),
    BroadEtfSpec("510880.SH", "style", "上证红利", "primary"),
    BroadEtfSpec("515080.SH", "style", "中证红利", "cross_check"),
    BroadEtfSpec("515810.SH", "broad_market", "中证800", "primary"),
    BroadEtfSpec("159907.SZ", "micro_cap", "国证2000", "primary"),
    BroadEtfSpec("159531.SZ", "micro_cap", "中证2000", "primary_recent"),
    BroadEtfSpec("159338.SZ", "broad_market", "中证A500", "primary_recent"),
    BroadEtfSpec("159339.SZ", "broad_market", "中证A500", "cross_check_recent"),
)


def pct(value: float) -> str:
    return f"{value:.2%}"


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def get_pro() -> Any:
    token = os.getenv("TUSHARE_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TUSHARE_TOKEN is missing")
    return ts.pro_api(token)


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
    frame = call_with_retries("fund_basic", pro.fund_basic, market="E", fields=fields)
    return frame.sort_values(["list_date", "ts_code"]).reset_index(drop=True)


def fetch_fund_daily(pro: Any, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    DAILY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = DAILY_CACHE_DIR / f"{ts_code}_{start_date}_{end_date}.csv"
    if cache_path.exists() and not REFRESH:
        return pd.read_csv(cache_path, encoding="utf-8-sig")
    frame = call_with_retries(
        f"fund_daily {ts_code}",
        pro.fund_daily,
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
    )
    frame.to_csv(cache_path, index=False, encoding="utf-8-sig")
    return frame


def download_selected_daily(pro: Any, specs: tuple[BroadEtfSpec, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    parts: list[pd.DataFrame] = []
    status_rows: list[dict[str, Any]] = []
    for index, spec in enumerate(specs, start=1):
        try:
            frame = fetch_fund_daily(pro, spec.ts_code, START_DATE, END_DATE)
            status_rows.append(
                {
                    "ts_code": spec.ts_code,
                    "index_bucket": spec.index_bucket,
                    "index_name": spec.index_name,
                    "role": spec.role,
                    "status": "downloaded",
                    "rows": int(len(frame)),
                    "message": "",
                    "order": index,
                }
            )
            if not frame.empty:
                parts.append(frame)
            print(f"[{index}/{len(specs)}] {spec.ts_code} rows={len(frame)}", flush=True)
        except Exception as exc:
            status_rows.append(
                {
                    "ts_code": spec.ts_code,
                    "index_bucket": spec.index_bucket,
                    "index_name": spec.index_name,
                    "role": spec.role,
                    "status": "failed",
                    "rows": 0,
                    "message": repr(exc),
                    "order": index,
                }
            )
            print(f"[{index}/{len(specs)}] {spec.ts_code} failed={exc!r}", flush=True)
            if SLEEP_SECONDS:
                time.sleep(SLEEP_SECONDS)
    daily = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    return daily, pd.DataFrame(status_rows)


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
    frame["raw_vs_pct_ret_abs_diff"] = (frame["close_pct_ret"] - frame["daily_ret"]).abs()
    return frame


def equity_and_drawdown(returns: pd.Series) -> tuple[pd.Series, pd.Series]:
    equity_values: list[float] = []
    drawdown_values: list[float] = []
    equity = 1.0
    peak = 1.0
    for value in returns.fillna(0.0):
        equity *= 1.0 + to_float(value)
        peak = max(peak, equity)
        equity_values.append(equity)
        drawdown_values.append(equity / peak - 1.0 if peak else 0.0)
    return pd.Series(equity_values, index=returns.index), pd.Series(drawdown_values, index=returns.index)


def build_selected_basic(fund_basic: pd.DataFrame, specs: tuple[BroadEtfSpec, ...]) -> pd.DataFrame:
    spec_frame = pd.DataFrame([asdict(spec) for spec in specs])
    selected = spec_frame.merge(fund_basic, on="ts_code", how="left")
    selected["basic_found"] = selected["name"].notna()
    return selected.sort_values(["index_bucket", "index_name", "role", "ts_code"]).reset_index(drop=True)


def summarize_daily(selected_basic: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in selected_basic.itertuples(index=False):
        ts_code = str(row.ts_code)
        group = daily[daily["ts_code"] == ts_code].sort_values("date")
        if group.empty:
            rows.append(
                {
                    "ts_code": ts_code,
                    "name": str(row.name),
                    "index_bucket": str(row.index_bucket),
                    "index_name": str(row.index_name),
                    "role": str(row.role),
                    "rows": 0,
                    "first_trade_date": "",
                    "last_trade_date": "",
                    "years": 0.0,
                    "final_equity": 1.0,
                    "total_return": 0.0,
                    "max_drawdown": 0.0,
                    "annualized_vol": 0.0,
                    "median_amount_raw": 0.0,
                    "p10_amount_raw": 0.0,
                    "max_raw_vs_pct_ret_abs_diff": 0.0,
                    "split_artifact_suspect_days": 0,
                }
            )
            continue
        equity, drawdown = equity_and_drawdown(group["daily_ret"])
        ret = group["daily_ret"].fillna(0.0)
        years = len(group) / TRADING_DAYS if len(group) else 0.0
        rows.append(
            {
                "ts_code": ts_code,
                "name": str(row.name),
                "index_bucket": str(row.index_bucket),
                "index_name": str(row.index_name),
                "role": str(row.role),
                "list_date": str(row.list_date),
                "m_fee": to_float(row.m_fee),
                "c_fee": to_float(row.c_fee),
                "rows": int(len(group)),
                "first_trade_date": str(group["date"].min()),
                "last_trade_date": str(group["date"].max()),
                "years": years,
                "final_equity": to_float(equity.iloc[-1]) if len(equity) else 1.0,
                "total_return": to_float(equity.iloc[-1] - 1.0) if len(equity) else 0.0,
                "max_drawdown": to_float(drawdown.min()) if len(drawdown) else 0.0,
                "annualized_vol": to_float(ret.std(ddof=1) * sqrt(TRADING_DAYS)) if len(ret) > 1 else 0.0,
                "median_amount_raw": to_float(group["amount"].median()),
                "p10_amount_raw": to_float(group["amount"].quantile(0.10)),
                "max_raw_vs_pct_ret_abs_diff": to_float(group["raw_vs_pct_ret_abs_diff"].max()),
                "split_artifact_suspect_days": int((group["raw_vs_pct_ret_abs_diff"] > 0.05).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["index_bucket", "index_name", "role", "ts_code"]).reset_index(drop=True)


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.empty:
        return "无数据"
    return frame.loc[:, columns].head(max_rows).to_markdown(index=False)


def write_report(selected_basic: pd.DataFrame, summary: pd.DataFrame, status: pd.DataFrame, paths: dict[str, Path]) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    downloaded = status[status["status"] == "downloaded"]
    failed = status[status["status"] != "downloaded"]
    primary = summary[summary["role"].astype(str).str.contains("primary", na=False)].copy()
    long_history = primary[primary["years"] >= 5.0].copy()
    artifact = summary[summary["split_artifact_suspect_days"] > 0].copy()
    lines = [
        "# 股票震荡宽基ETF池数据补齐审计 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：宽基ETF数据下载与可用性审计，不是正式交易版本。",
        f"- 下载区间：`{START_DATE}`到`{END_DATE}`。",
        f"- Tushare请求节奏：逐只基金拉取，默认间隔`{SLEEP_SECONDS:.2f}`秒，失败重试`{RETRIES}`次。",
        f"- 固定候选数：`{len(BROAD_ETF_UNIVERSE)}`，成功下载：`{len(downloaded)}`，失败：`{len(failed)}`。",
        "",
        "## 核心观察",
        "",
        f"- 覆盖5年以上的primary宽基/风格ETF数量：`{len(long_history)}`。",
        "- 本阶段保留近年才上市的A500、中证2000，用于后续新指数观察，但不把它们当全历史证据。",
        f"- 原始价格收益与`pct_chg`偏离超过5%的ETF数量：`{artifact['ts_code'].nunique()}`；后续回测继续使用`pct_chg`，不使用原始价格比值。",
        "- 这一步只补池子和审计，不从收益结果里挑ETF。",
        "",
        "## 固定ETF候选",
        "",
        markdown_table(
            selected_basic,
            ["ts_code", "index_bucket", "index_name", "role", "name", "list_date", "m_fee", "c_fee", "basic_found"],
        ),
        "",
        "## 数据覆盖与流动性",
        "",
        markdown_table(
            summary,
            [
                "ts_code",
                "name",
                "index_name",
                "role",
                "first_trade_date",
                "last_trade_date",
                "years",
                "median_amount_raw",
                "p10_amount_raw",
                "max_raw_vs_pct_ret_abs_diff",
                "split_artifact_suspect_days",
            ],
        ),
        "",
        "## 下载状态",
        "",
        markdown_table(status, ["ts_code", "index_name", "role", "status", "rows", "message"]),
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：本阶段固定宽基ETF候选池，只做数据下载、覆盖审计和价格口径检查，不生成或筛选交易参数。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：下载结果没有用于删除弱ETF或挑强ETF；近年上市ETF也保留但标明只能用于短样本观察。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：上一阶段单一中证1000 ETF只能说明局部现象，必须扩大到不同宽基指数，才知道ETF震荡骨架是否有跨周期价值。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：宽基ETF池已补齐，存在多个覆盖5年以上的代表性ETF；下一步可以做固定模板跨指数状态归因。",
        "",
        "## 决策",
        "",
        "- 不接入第78。",
        "- 不进入正式股票策略。",
        "- 不做第78 A/B/C。",
        "- 下一步做`Bollinger 20/2σ + MA200`等固定模板在宽基ETF池上的状态归因。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pro = get_pro()
    fund_basic = fetch_fund_basic(pro)
    selected_basic = build_selected_basic(fund_basic, BROAD_ETF_UNIVERSE)
    raw_daily, status = download_selected_daily(pro, BROAD_ETF_UNIVERSE)
    daily = normalize_daily(raw_daily)
    summary = summarize_daily(selected_basic, daily)

    paths: dict[str, Path] = {
        "fund_basic_all": OUTPUT_DIR / f"{PREFIX}_fund_basic_all.csv",
        "selected_basic": OUTPUT_DIR / f"{PREFIX}_selected_basic.csv",
        "selected_daily": OUTPUT_DIR / f"{PREFIX}_selected_daily.csv",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "download_status": OUTPUT_DIR / f"{PREFIX}_download_status.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    fund_basic.to_csv(paths["fund_basic_all"], index=False, encoding="utf-8-sig")
    selected_basic.to_csv(paths["selected_basic"], index=False, encoding="utf-8-sig")
    daily.to_csv(paths["selected_daily"], index=False, encoding="utf-8-sig")
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    status.to_csv(paths["download_status"], index=False, encoding="utf-8-sig")
    paths["meta"].write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "script": Path(__file__).name,
                "start_date": START_DATE,
                "end_date": END_DATE,
                "sleep_seconds": SLEEP_SECONDS,
                "retries": RETRIES,
                "retry_sleep_seconds": RETRY_SLEEP_SECONDS,
                "refresh": REFRESH,
                "universe": [asdict(spec) for spec in BROAD_ETF_UNIVERSE],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    report_path = write_report(selected_basic, summary, status, paths)
    print(f"output_dir={OUTPUT_DIR}")
    print(f"report={report_path}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
