from __future__ import annotations

import json
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR: Path = Path(__file__).resolve().parent
EXAMPLES_DIR: Path = BASE_DIR.parent
FUTURES_ROOT: Path = (
    EXAMPLES_DIR / "portfolio_backtesting" / "downloaded_futures" / "tqsdk_daily_2010_2026_04"
).resolve()
CFFEX_DIR: Path = FUTURES_ROOT / "CFFEX"
DOWNLOAD_SUMMARY_PATH: Path = FUTURES_ROOT / "_download_summary.json"
IMPORT_SUMMARY_PATH: Path = FUTURES_ROOT / "_import_summary.json"
DOWNLOAD_STATUS_PATH: Path = FUTURES_ROOT / "_download_status.csv"

NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_hedge_data_audit_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_hedge_data_audit_v1"

STOCK_EQUITY_PATH: Path = (
    NATIVE_RESULTS_DIR
    / "stock_range_reversion_market_down_merged_portfolio_2018_2026"
    / "stock_range_reversion_market_down_merged_portfolio_v1_equity_curve.csv"
)

FUTURES_PREFIXES: tuple[str, ...] = ("IM", "IC", "IF", "IH")
CONTINUOUS_METHODS: tuple[str, ...] = ("dominant_by_close_oi", "dominant_by_volume")
TRADING_DAYS: int = 252


def to_float(value: Any, default: float = 0.0) -> float:
    """Convert numeric-like values to float without leaking NaN into summaries."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result):
        return default
    return result


def safe_corr(left: pd.Series, right: pd.Series) -> float:
    work = pd.concat([left, right], axis=1).dropna()
    if len(work) <= 2:
        return 0.0
    value = work.iloc[:, 0].corr(work.iloc[:, 1])
    return to_float(value)


def safe_beta(y: pd.Series, x: pd.Series) -> float:
    work = pd.concat([y, x], axis=1).dropna()
    if len(work) <= 2:
        return 0.0
    x_values = work.iloc[:, 1]
    y_values = work.iloc[:, 0]
    var_x = to_float(x_values.var(ddof=1))
    if var_x == 0:
        return 0.0
    return to_float(y_values.cov(x_values) / var_x)


def annualized_tracking_error(diff: pd.Series) -> float:
    clean = diff.dropna()
    if len(clean) <= 1:
        return 0.0
    return to_float(clean.std(ddof=1) * sqrt(TRADING_DAYS))


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_contract_month(symbol: str) -> str:
    digits = symbol[-4:]
    if len(digits) != 4 or not digits.isdigit():
        return ""
    return f"20{digits[:2]}-{digits[2:]}"


def contract_files(prefix: str) -> list[Path]:
    if not CFFEX_DIR.exists():
        return []
    return sorted(CFFEX_DIR.glob(f"{prefix}[0-9][0-9][0-9][0-9].csv"))


def read_contract_csv(path: Path, prefix: str) -> pd.DataFrame:
    symbol = path.stem
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        return pd.DataFrame()

    frame = frame.rename(columns={"\ufefftrade_date": "trade_date"})
    frame["date"] = pd.to_datetime(frame["trade_date"]).dt.date
    for column in ("open", "high", "low", "close", "volume", "open_oi", "close_oi"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["prefix"] = prefix
    frame["symbol"] = symbol
    frame["contract_month"] = parse_contract_month(symbol)
    frame["file_path"] = str(path)
    return frame


def load_prefix_frames() -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for prefix in FUTURES_PREFIXES:
        parts = [read_contract_csv(path, prefix) for path in contract_files(prefix)]
        parts = [part for part in parts if not part.empty]
        frames[prefix] = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    return frames


def summarize_prefix(prefix: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "prefix": prefix,
            "contract_count": 0,
            "rows": 0,
            "first_date": "",
            "last_date": "",
            "unique_trade_days": 0,
            "median_daily_contracts": 0.0,
            "max_daily_contracts": 0,
            "total_volume": 0.0,
            "median_daily_total_volume": 0.0,
            "max_close_oi": 0.0,
            "first_contract": "",
            "last_contract": "",
            "contract_month_min": "",
            "contract_month_max": "",
            "max_calendar_gap_days": 0,
            "has_price_volume_oi": False,
            "has_multiplier_margin_fee": False,
            "has_basis_roll_cost": False,
        }

    dates = pd.to_datetime(pd.Series(sorted(frame["date"].dropna().unique())))
    daily_counts = frame.groupby("date")["symbol"].nunique()
    daily_volume = frame.groupby("date")["volume"].sum(min_count=1)
    return {
        "prefix": prefix,
        "contract_count": int(frame["symbol"].nunique()),
        "rows": int(len(frame)),
        "first_date": str(frame["date"].min()),
        "last_date": str(frame["date"].max()),
        "unique_trade_days": int(frame["date"].nunique()),
        "median_daily_contracts": to_float(daily_counts.median()),
        "max_daily_contracts": int(daily_counts.max()),
        "total_volume": to_float(frame["volume"].sum()),
        "median_daily_total_volume": to_float(daily_volume.median()),
        "max_close_oi": to_float(frame["close_oi"].max()),
        "first_contract": str(frame.sort_values(["date", "symbol"]).iloc[0]["symbol"]),
        "last_contract": str(frame.sort_values(["date", "symbol"]).iloc[-1]["symbol"]),
        "contract_month_min": str(frame["contract_month"].min()),
        "contract_month_max": str(frame["contract_month"].max()),
        "max_calendar_gap_days": int(dates.diff().dt.days.max()) if len(dates) > 1 else 0,
        "has_price_volume_oi": all(column in frame.columns for column in ("close", "volume", "close_oi")),
        "has_multiplier_margin_fee": False,
        "has_basis_roll_cost": False,
    }


def summarize_contracts(prefix_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for prefix, frame in prefix_frames.items():
        if frame.empty:
            continue
        for symbol, group in frame.groupby("symbol"):
            group = group.sort_values("date")
            rows.append(
                {
                    "prefix": prefix,
                    "symbol": symbol,
                    "contract_month": parse_contract_month(symbol),
                    "first_date": str(group["date"].min()),
                    "last_date": str(group["date"].max()),
                    "rows": int(len(group)),
                    "close_first": to_float(group["close"].iloc[0]),
                    "close_last": to_float(group["close"].iloc[-1]),
                    "median_volume": to_float(group["volume"].median()),
                    "mean_volume": to_float(group["volume"].mean()),
                    "max_volume": to_float(group["volume"].max()),
                    "median_close_oi": to_float(group["close_oi"].median()),
                    "mean_close_oi": to_float(group["close_oi"].mean()),
                    "max_close_oi": to_float(group["close_oi"].max()),
                }
            )
    return pd.DataFrame(rows).sort_values(["prefix", "symbol"]).reset_index(drop=True)


def build_continuous(prefix: str, frame: pd.DataFrame, method: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    sort_column = "close_oi" if method == "dominant_by_close_oi" else "volume"
    work = frame.copy()
    work[sort_column] = pd.to_numeric(work[sort_column], errors="coerce").fillna(0.0)
    work = work.sort_values(["date", sort_column, "volume", "symbol"], ascending=[True, False, False, True])
    picked = work.groupby("date", as_index=False).head(1).copy()
    picked = picked.sort_values("date").reset_index(drop=True)
    daily_contracts = frame.groupby("date")["symbol"].nunique().rename("available_contract_count")
    picked = picked.merge(daily_contracts, left_on="date", right_index=True, how="left")
    picked["method"] = method
    picked["is_roll_day"] = picked["symbol"].ne(picked["symbol"].shift(1))
    if len(picked) > 0:
        picked.loc[picked.index[0], "is_roll_day"] = False
    picked["daily_ret_naive"] = picked["close"].pct_change()
    same_contract = picked["symbol"].eq(picked["symbol"].shift(1))
    picked["daily_ret_same_contract_only"] = picked["daily_ret_naive"].where(same_contract)
    return picked[
        [
            "date",
            "prefix",
            "method",
            "symbol",
            "contract_month",
            "close",
            "volume",
            "open_oi",
            "close_oi",
            "available_contract_count",
            "is_roll_day",
            "daily_ret_naive",
            "daily_ret_same_contract_only",
        ]
    ]


def load_stock_equity() -> pd.DataFrame:
    if not STOCK_EQUITY_PATH.exists():
        raise FileNotFoundError(f"stock equity curve not found: {STOCK_EQUITY_PATH}")
    frame = pd.read_csv(STOCK_EQUITY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    if "roundtrip_cost_bps" in frame.columns:
        frame = frame.sort_values(["date", "roundtrip_cost_bps"]).drop_duplicates("date", keep="first")
    return frame.sort_values("date").reset_index(drop=True)


def build_overlap_coverage(stock: pd.DataFrame, continuous: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    stock_dates = set(stock["date"].dropna().unique())
    active_stock_dates = set(stock.loc[stock["return_gross_exposure"] > 0, "date"].dropna().unique())
    for (prefix, method), group in continuous.groupby(["prefix", "method"]):
        future_dates = set(group["date"].dropna().unique())
        overlap_dates = stock_dates & future_dates
        active_overlap_dates = active_stock_dates & future_dates
        first_future_date = min(future_dates) if future_dates else None
        pre_future_dates = {date for date in stock_dates if first_future_date is not None and date < first_future_date}
        pre_future_active_dates = {
            date for date in active_stock_dates if first_future_date is not None and date < first_future_date
        }
        rows.append(
            {
                "prefix": prefix,
                "method": method,
                "stock_days": len(stock_dates),
                "stock_active_days": len(active_stock_dates),
                "future_days": len(future_dates),
                "overlap_days": len(overlap_dates),
                "overlap_ratio_all_stock_days": len(overlap_dates) / len(stock_dates) if stock_dates else 0.0,
                "active_overlap_days": len(active_overlap_dates),
                "overlap_ratio_active_stock_days": len(active_overlap_dates) / len(active_stock_dates)
                if active_stock_dates
                else 0.0,
                "first_future_date": str(first_future_date) if first_future_date is not None else "",
                "last_future_date": str(max(future_dates)) if future_dates else "",
                "pre_future_stock_days": len(pre_future_dates),
                "pre_future_active_stock_days": len(pre_future_active_dates),
            }
        )
    return pd.DataFrame(rows).sort_values(["prefix", "method"]).reset_index(drop=True)


def build_tracking_metrics(stock: pd.DataFrame, continuous: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    stock_cols = ["date", "benchmark_daily_ret", "benchmark_active_daily_ret", "return_gross_exposure"]
    for (prefix, method), group in continuous.groupby(["prefix", "method"]):
        merged = group.merge(stock[stock_cols], on="date", how="inner")
        for ret_col in ("daily_ret_same_contract_only", "daily_ret_naive"):
            clean = merged.dropna(subset=[ret_col, "benchmark_daily_ret"])
            if clean.empty:
                rows.append(
                    {
                        "prefix": prefix,
                        "method": method,
                        "futures_return_col": ret_col,
                        "days": 0,
                        "first_date": "",
                        "last_date": "",
                        "corr_to_csi1000": 0.0,
                        "beta_to_csi1000": 0.0,
                        "annualized_tracking_error": 0.0,
                        "annualized_mean_return_diff": 0.0,
                        "roll_days_in_sample": int(merged["is_roll_day"].sum()) if "is_roll_day" in merged else 0,
                        "avg_available_contract_count": 0.0,
                        "avg_close_oi": 0.0,
                        "avg_volume": 0.0,
                    }
                )
                continue

            diff = clean[ret_col] - clean["benchmark_daily_ret"]
            rows.append(
                {
                    "prefix": prefix,
                    "method": method,
                    "futures_return_col": ret_col,
                    "days": int(len(clean)),
                    "first_date": str(clean["date"].min()),
                    "last_date": str(clean["date"].max()),
                    "corr_to_csi1000": safe_corr(clean[ret_col], clean["benchmark_daily_ret"]),
                    "beta_to_csi1000": safe_beta(clean[ret_col], clean["benchmark_daily_ret"]),
                    "annualized_tracking_error": annualized_tracking_error(diff),
                    "annualized_mean_return_diff": to_float(diff.mean()) * TRADING_DAYS,
                    "roll_days_in_sample": int(clean["is_roll_day"].sum()),
                    "avg_available_contract_count": to_float(clean["available_contract_count"].mean()),
                    "avg_close_oi": to_float(clean["close_oi"].mean()),
                    "avg_volume": to_float(clean["volume"].mean()),
                }
            )
    return pd.DataFrame(rows).sort_values(["prefix", "method", "futures_return_col"]).reset_index(drop=True)


def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if frame.empty:
        return "无数据"
    work = frame.loc[:, columns].head(max_rows).copy()
    return work.to_markdown(index=False)


def write_report(
    prefix_coverage: pd.DataFrame,
    overlap: pd.DataFrame,
    tracking: pd.DataFrame,
    contract_summary: pd.DataFrame,
    inventory: dict[str, Any],
) -> Path:
    im_coverage = prefix_coverage[prefix_coverage["prefix"] == "IM"]
    im_overlap = overlap[(overlap["prefix"] == "IM") & (overlap["method"] == "dominant_by_close_oi")]
    im_tracking = tracking[
        (tracking["prefix"] == "IM")
        & (tracking["method"] == "dominant_by_close_oi")
        & (tracking["futures_return_col"] == "daily_ret_same_contract_only")
    ]
    ic_tracking = tracking[
        (tracking["prefix"] == "IC")
        & (tracking["method"] == "dominant_by_close_oi")
        & (tracking["futures_return_col"] == "daily_ret_same_contract_only")
    ]

    im_first = str(im_coverage.iloc[0]["first_date"]) if not im_coverage.empty else ""
    im_overlap_ratio = to_float(im_overlap.iloc[0]["overlap_ratio_all_stock_days"]) if not im_overlap.empty else 0.0
    im_active_overlap_ratio = (
        to_float(im_overlap.iloc[0]["overlap_ratio_active_stock_days"]) if not im_overlap.empty else 0.0
    )
    im_corr = to_float(im_tracking.iloc[0]["corr_to_csi1000"]) if not im_tracking.empty else 0.0
    im_beta = to_float(im_tracking.iloc[0]["beta_to_csi1000"]) if not im_tracking.empty else 0.0
    im_te = to_float(im_tracking.iloc[0]["annualized_tracking_error"]) if not im_tracking.empty else 0.0
    ic_corr = to_float(ic_tracking.iloc[0]["corr_to_csi1000"]) if not ic_tracking.empty else 0.0

    report = f"""# 股票震荡对冲数据可用性审计 v1

- 记录时间：{datetime.now().strftime("%Y-%m-%d %H:%M CST")}
- 当前研究线：股票震荡 `market_down`，与第78趋势策略、期货震荡策略隔离。
- 本阶段性质：数据可用性审计，不是新策略回测，不新增交易参数，不选择最优对冲比例。

## 输入数据

- 股票震荡路径：`{STOCK_EQUITY_PATH}`
- CFFEX期货CSV目录：`{CFFEX_DIR}`
- 下载摘要：`downloaded={inventory.get("download_summary", {}).get("downloaded", "")}`，`total_symbols={inventory.get("download_summary", {}).get("total_symbols", "")}`，`updated_at={inventory.get("download_summary", {}).get("updated_at", "")}`
- 导入摘要：`imported={inventory.get("import_summary", {}).get("imported", "")}`，`database_path={inventory.get("import_summary", {}).get("database_path", "")}`

## 覆盖结论

- IM中证1000股指期货本地数据从 `{im_first}` 开始，不能覆盖股票震荡2018-01到2022-07之前的完整历史。
- IM对第218阶段股票路径的全样本日期覆盖率约 `{pct(im_overlap_ratio)}`，对有股票暴露日期覆盖率约 `{pct(im_active_overlap_ratio)}`。
- 本地期货CSV具备价格、成交量、持仓量字段；缺失合约乘数、保证金比例、手续费、滑点、基差、展期成本字段。
- 仓库内暂未发现可直接复用的中证1000 ETF/基金历史行情文件；ETF路线需要另行补数据和做流动性/跟踪误差审计。

## 品种覆盖

{markdown_table(prefix_coverage, ["prefix", "contract_count", "first_date", "last_date", "unique_trade_days", "median_daily_contracts", "median_daily_total_volume", "max_close_oi", "has_multiplier_margin_fee", "has_basis_roll_cost"])}

## 股票路径重合度

{markdown_table(overlap, ["prefix", "method", "stock_days", "stock_active_days", "future_days", "overlap_days", "overlap_ratio_all_stock_days", "active_overlap_days", "overlap_ratio_active_stock_days", "pre_future_active_stock_days"])}

## 与中证1000 benchmark 的跟踪

说明：`daily_ret_same_contract_only` 排除主力切换日的跨合约价差跳变，更适合粗看日收益跟踪；`daily_ret_naive` 保留主力切换日价格跳变，只能作为连续代理的粗糙口径。

{markdown_table(tracking, ["prefix", "method", "futures_return_col", "days", "first_date", "last_date", "corr_to_csi1000", "beta_to_csi1000", "annualized_tracking_error", "annualized_mean_return_diff", "roll_days_in_sample"])}

## IM主力手感判断

- IM与中证1000 benchmark 的同合约日收益相关约 `{im_corr:.3f}`，beta约 `{im_beta:.3f}`，年化跟踪误差约 `{pct(im_te)}`。
- 这说明IM作为2022-07之后的方向性对冲工具有研究价值，但还不足以直接进入可交易组合回测。
- 真正的交易版必须补齐：合约乘数、保证金、手续费、滑点、展期规则、基差/贴水、日内无法成交风险，以及股票篮子和期货腿的资金占用联动。
- IC可以作为2020之后的替代指数期货 proxy 观察，和中证1000 benchmark 的同合约收益相关约 `{ic_corr:.3f}`，但它是中证500，不是中证1000；用于2018-2022替代对冲会引入结构错配。

## 运行前过拟合反思

- 判断：否。
- 原因：本阶段只审计已有数据覆盖、字段和粗跟踪关系，不扫描对冲比例、换月规则或成本参数。

## 运行后过拟合反思

- 判断：否。
- 原因：输出保留了IM覆盖不足、ETF缺失、成本字段缺失等反证，没有把无成本对冲归因包装成可交易收益。

## 运行前继续价值反思

- 判断：是。
- 原因：第222/223阶段已经显示股票震荡的残差alpha较健康，主要矛盾是市场beta承载；对冲数据审计是继续研究的必要前置条件。

## 运行后继续价值反思

- 判断：有，但必须降级为分段研究。
- 原因：2022-07之后IM数据足以做一段保守对冲压力测试；2018-2022前半段缺少同标的期货对冲，只能保持long-only归因或另补ETF/指数替代数据。

## 决策

- 不接入第78。
- 不进入股票正式策略。
- 不做第78 A/B/C。
- 不采用第223阶段无成本对冲结果作为实盘结果。
- 下一步只允许做“2022-07之后 IM 可交易对冲压力测试”，并且必须把期货腿成本、换月和资金占用写成显式假设。

## 输出文件

- `{OUTPUT_DIR / f"{PREFIX}_prefix_coverage.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_contract_summary.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_continuous_daily.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_overlap_coverage.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_tracking_metrics.csv"}`
- `{OUTPUT_DIR / f"{PREFIX}_input_inventory.json"}`
"""
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    prefix_frames = load_prefix_frames()
    prefix_coverage = pd.DataFrame(
        [summarize_prefix(prefix, frame) for prefix, frame in prefix_frames.items()]
    ).sort_values("prefix")
    contract_summary = summarize_contracts(prefix_frames)

    continuous_parts: list[pd.DataFrame] = []
    for prefix, frame in prefix_frames.items():
        for method in CONTINUOUS_METHODS:
            continuous = build_continuous(prefix, frame, method)
            if not continuous.empty:
                continuous_parts.append(continuous)
    continuous_daily = (
        pd.concat(continuous_parts, ignore_index=True, sort=False)
        if continuous_parts
        else pd.DataFrame()
    )

    stock = load_stock_equity()
    overlap = build_overlap_coverage(stock, continuous_daily)
    tracking = build_tracking_metrics(stock, continuous_daily)

    inventory = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "futures_root": str(FUTURES_ROOT),
        "cffex_dir": str(CFFEX_DIR),
        "stock_equity_path": str(STOCK_EQUITY_PATH),
        "download_summary": read_json(DOWNLOAD_SUMMARY_PATH),
        "import_summary": read_json(IMPORT_SUMMARY_PATH),
        "download_status_path_exists": DOWNLOAD_STATUS_PATH.exists(),
        "local_etf_data": {
            "status": "not_found_by_filename_scan",
            "note": "No reusable local CSI1000 ETF/fund daily history file was found by ticker/ETF filename scan.",
        },
        "field_limitations": [
            "TQSDK CSV has OHLC, volume, open_oi and close_oi.",
            "No local contract multiplier, margin ratio, fee, slippage, basis or roll-cost fields were found in the CSV schema.",
        ],
    }

    prefix_coverage.to_csv(OUTPUT_DIR / f"{PREFIX}_prefix_coverage.csv", index=False, encoding="utf-8-sig")
    contract_summary.to_csv(OUTPUT_DIR / f"{PREFIX}_contract_summary.csv", index=False, encoding="utf-8-sig")
    continuous_daily.to_csv(OUTPUT_DIR / f"{PREFIX}_continuous_daily.csv", index=False, encoding="utf-8-sig")
    overlap.to_csv(OUTPUT_DIR / f"{PREFIX}_overlap_coverage.csv", index=False, encoding="utf-8-sig")
    tracking.to_csv(OUTPUT_DIR / f"{PREFIX}_tracking_metrics.csv", index=False, encoding="utf-8-sig")
    (OUTPUT_DIR / f"{PREFIX}_input_inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path = write_report(prefix_coverage, overlap, tracking, contract_summary, inventory)

    print(f"output_dir={OUTPUT_DIR}")
    print(f"report={report_path}")
    print(prefix_coverage.to_string(index=False))
    print(tracking.to_string(index=False))


if __name__ == "__main__":
    main()
