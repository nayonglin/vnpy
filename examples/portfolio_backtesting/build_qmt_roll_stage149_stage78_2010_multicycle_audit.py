from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from vnpy.trader.constant import Interval
from vnpy.trader.database import get_database

from main_contract_mapping import load_mapping_df, load_product_universe_symbols
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    CYCLE_WINDOWS,
    to_markdown_table,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage149_stage78_2010_multicycle_audit_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage149_stage78_2010_multicycle_audit"

COVERAGE_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

COVERAGE_PASS_THRESHOLD: float = 0.95


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _latest_database_date() -> datetime:
    overview = get_database().get_bar_overview()
    ends = [item.end for item in overview if getattr(item, "end", None)]
    if not ends:
        raise RuntimeError("No bar data found in vn.py database.")
    return max(ends)


def _load_contract_date_sets(contract_symbols: set[str], start: datetime, end: datetime) -> dict[str, set[str]]:
    database = get_database()
    result: dict[str, set[str]] = {}
    for vt_symbol in sorted(contract_symbols):
        symbol, exchange_value = vt_symbol.split(".", 1)
        exchange = next(exchange for exchange in database.get_bar_overview() if exchange.exchange.value == exchange_value).exchange
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start, end)
        result[vt_symbol] = {bar.datetime.date().isoformat() for bar in bars}
    return result


def _exchange_by_value() -> dict[str, Any]:
    overview = get_database().get_bar_overview()
    return {item.exchange.value: item.exchange for item in overview}


def load_contract_date_sets(contract_symbols: set[str], start: datetime, end: datetime) -> dict[str, set[str]]:
    database = get_database()
    exchange_by_value = _exchange_by_value()
    result: dict[str, set[str]] = {}
    for vt_symbol in sorted(contract_symbols):
        symbol, exchange_value = vt_symbol.split(".", 1)
        exchange = exchange_by_value.get(exchange_value)
        if exchange is None:
            result[vt_symbol] = set()
            continue
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start, end)
        result[vt_symbol] = {bar.datetime.date().isoformat() for bar in bars}
    return result


def build_windows(latest_date: datetime) -> list[dict[str, Any]]:
    requested_start = datetime(2010, 1, 4)
    windows: list[dict[str, Any]] = [
        {
            "window_name": "requested_2010_2026",
            "display_label": "requested_since_2010",
            "analysis_start": requested_start,
            "analysis_end": latest_date,
            "coverage_only": True,
        },
        {
            "window_name": "database_coverage_since_2016",
            "display_label": "database_since_2016",
            "analysis_start": datetime(2016, 1, 4),
            "analysis_end": latest_date,
            "coverage_only": True,
        },
        {
            "window_name": "preload_since_2019_06",
            "display_label": "preload_since_2019_06",
            "analysis_start": datetime(2019, 6, 3),
            "analysis_end": latest_date,
            "coverage_only": True,
        },
    ]
    for window in CYCLE_WINDOWS:
        copied = dict(window)
        copied["analysis_end"] = min(copied["analysis_end"], latest_date)
        copied["coverage_only"] = False
        windows.append(copied)
    return windows


def build_coverage_table(
    mapping_df: pd.DataFrame,
    product_symbols: list[str],
    windows: list[dict[str, Any]],
    contract_date_sets: dict[str, set[str]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    product_set = set(product_symbols)
    mapping_df = mapping_df[mapping_df["continuous_symbol_vt"].isin(product_set)].copy()
    mapping_df = mapping_df[mapping_df["main_contract_vt"].fillna("") != ""].copy()
    mapping_df["date"] = pd.to_datetime(mapping_df["date"]).dt.date.astype(str)

    for window in windows:
        start_date = window["analysis_start"].date().isoformat()
        end_date = window["analysis_end"].date().isoformat()
        window_df = mapping_df[(mapping_df["date"] >= start_date) & (mapping_df["date"] <= end_date)].copy()
        total_mapped_days = 0
        total_present_days = 0

        for product in product_symbols:
            product_df = window_df[window_df["continuous_symbol_vt"] == product].copy()
            mapped_days = len(product_df)
            present_days = 0
            missing_contracts: set[str] = set()
            for row in product_df.itertuples(index=False):
                date_text = str(row.date)
                contract = str(row.main_contract_vt)
                if date_text in contract_date_sets.get(contract, set()):
                    present_days += 1
                else:
                    missing_contracts.add(contract)
            total_mapped_days += mapped_days
            total_present_days += present_days
            coverage_ratio = present_days / mapped_days if mapped_days else 1.0
            rows.append(
                {
                    "window_name": window["window_name"],
                    "display_label": window["display_label"],
                    "analysis_start": start_date,
                    "analysis_end": end_date,
                    "product_vt_symbol": product,
                    "mapped_days": mapped_days,
                    "present_days": present_days,
                    "missing_days": mapped_days - present_days,
                    "coverage_ratio": coverage_ratio,
                    "missing_contract_count": len(missing_contracts),
                    "missing_contract_examples": ",".join(sorted(missing_contracts)[:8]),
                    "coverage_only": bool(window["coverage_only"]),
                }
            )

        total_coverage_ratio = total_present_days / total_mapped_days if total_mapped_days else 1.0
        rows.append(
            {
                "window_name": window["window_name"],
                "display_label": window["display_label"],
                "analysis_start": start_date,
                "analysis_end": end_date,
                "product_vt_symbol": "__TOTAL__",
                "mapped_days": total_mapped_days,
                "present_days": total_present_days,
                "missing_days": total_mapped_days - total_present_days,
                "coverage_ratio": total_coverage_ratio,
                "missing_contract_count": 0,
                "missing_contract_examples": "",
                "coverage_only": bool(window["coverage_only"]),
            }
        )
    return pd.DataFrame(rows)


def run_valid_backtests(windows: list[dict[str, Any]], coverage_table: pd.DataFrame, strategy_overrides: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_rows = coverage_table[coverage_table["product_vt_symbol"] == "__TOTAL__"].copy()
    coverage_by_window = {
        str(row.window_name): float(row.coverage_ratio) for row in total_rows.itertuples(index=False)
    }

    for window in windows:
        window_name = str(window["window_name"])
        if bool(window["coverage_only"]):
            continue
        coverage_ratio = coverage_by_window.get(window_name, 0.0)
        if coverage_ratio < COVERAGE_PASS_THRESHOLD:
            continue
        analysis_start: datetime = window["analysis_start"]
        analysis_end: datetime = window["analysis_end"]
        print(f"[stage149] running {window_name}: {analysis_start.date()} -> {analysis_end.date()}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            capital=OFFICIAL_STAGE78_CAPITAL,
            save_artifacts=False,
            include_start_year_sweep=False,
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                official_version=OFFICIAL_STAGE78_VERSION,
                official_role=OFFICIAL_STAGE78_ROLE,
                window_name=window_name,
                display_label=str(window["display_label"]),
                coverage_ratio=coverage_ratio,
                strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )

    return pd.DataFrame(rows)


def build_report(coverage_table: pd.DataFrame, summary: pd.DataFrame, latest_date: datetime) -> str:
    total_coverage = coverage_table[coverage_table["product_vt_symbol"] == "__TOTAL__"].copy()
    total_coverage["coverage_ratio_pct"] = total_coverage["coverage_ratio"] * 100
    coverage_view = total_coverage[
        [
            "window_name",
            "analysis_start",
            "analysis_end",
            "mapped_days",
            "present_days",
            "missing_days",
            "coverage_ratio_pct",
            "coverage_only",
        ]
    ].copy()

    failed_early = total_coverage[
        total_coverage["window_name"].isin(
            ["requested_2010_2026", "database_coverage_since_2016", "preload_since_2019_06"]
        )
    ].copy()
    failed_early["gate_result"] = failed_early["coverage_ratio"].map(
        lambda value: "PASS" if float(value) >= COVERAGE_PASS_THRESHOLD else "FAIL"
    )

    lines = [
        "# Stage149 Stage78 2010 Multicycle Audit",
        "",
        "## 目的",
        "",
        "- 验证用户提出的“2010 到今天”是否能形成可信 Stage78 多周期回测。",
        "- 本脚本只做数据覆盖门禁和正式 Stage78 摘要回测，不修改 Stage78 参数。",
        "",
        "## 参数",
        "",
        f"- 版本：`{MODEL_TAG}`",
        f"- 正式基准：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 本金：`{OFFICIAL_STAGE78_CAPITAL:,.0f}`",
        f"- 基础 risk ratio：`{BASE_RISK_RATIO}`",
        f"- 数据库最新K线日期：`{latest_date.date().isoformat()}`",
        f"- 覆盖率通过阈值：`{COVERAGE_PASS_THRESHOLD:.0%}`",
        "",
        "## 数据覆盖门禁",
        "",
        to_markdown_table(coverage_view),
        "",
        "## 早期窗口门禁结论",
        "",
        to_markdown_table(
            failed_early[
                [
                    "window_name",
                    "analysis_start",
                    "analysis_end",
                    "coverage_ratio",
                    "missing_days",
                    "gate_result",
                ]
            ]
        ),
        "",
        "## 覆盖通过窗口回测结果",
        "",
    ]
    if summary.empty:
        lines.append("- 无覆盖通过窗口回测结果。")
    else:
        lines.append(
            to_markdown_table(
                summary[
                    [
                        "window_name",
                        "analysis_start",
                        "analysis_end",
                        "coverage_ratio",
                        "end_balance",
                        "total_return_pct",
                        "max_dd_percent",
                        "sharpe_ratio",
                        "total_slippage",
                        "total_trade_count",
                        "win_ratio_pct",
                    ]
                ]
            )
        )

    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    lines.extend(
        [
            "",
            "## 判断",
            "",
            "- 2010 起点不能直接作为可信 Stage78 回测，因为当前数据库/CSV没有覆盖大量 2010-2018 主力合约K线。",
            "- 覆盖通过的 2020 以后窗口可以作为正式多周期复核；这些窗口不是新策略，只是 Stage78 复验。",
            "- 若要真正做 2010 起点，先要补齐早期主力合约日线并处理郑商所/上期所历史合约代码重复问题，否则结果会被数据缺失污染。",
            "",
            "## Stage78 冻结基准引用",
            "",
            (
                f"- 2020-2026 参考：期末权益 `{reference['end_balance']:,.0f}`，"
                f"总收益 `{reference['total_return_pct']:.4f}%`，"
                f"最大回撤 `{reference['max_dd_percent']:.4f}%`，"
                f"Sharpe `{reference['sharpe_ratio']:.4f}`，"
                f"总滑点 `{reference['total_slippage']:,.0f}`，"
                f"总交易次数 `{reference['total_trade_count']:,.0f}`。"
            ),
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    latest_date = _latest_database_date()
    strategy_overrides = build_official_stage78_overrides()
    product_symbols = load_product_universe_symbols(str(strategy_overrides["product_universe_csv_path"]))
    if not product_symbols:
        raise RuntimeError("Stage78 product universe is empty.")

    windows = build_windows(latest_date)
    mapping_df = load_mapping_df()
    window_start = min(window["analysis_start"] for window in windows)
    window_end = max(window["analysis_end"] for window in windows)
    mapped_contracts = set(
        mapping_df[
            mapping_df["continuous_symbol_vt"].isin(set(product_symbols))
            & (mapping_df["main_contract_vt"].fillna("") != "")
        ]["main_contract_vt"].astype(str)
    )
    contract_date_sets = load_contract_date_sets(mapped_contracts, window_start, window_end)
    coverage_table = build_coverage_table(mapping_df, product_symbols, windows, contract_date_sets)
    summary = run_valid_backtests(windows, coverage_table, strategy_overrides)

    coverage_table.to_csv(COVERAGE_CSV_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "coverage_pass_threshold": COVERAGE_PASS_THRESHOLD,
        "latest_database_date": latest_date.date().isoformat(),
        "coverage_csv": str(COVERAGE_CSV_PATH),
        "summary_csv": str(SUMMARY_CSV_PATH),
        "report": str(REPORT_PATH),
        "coverage": coverage_table.to_dict(orient="records"),
        "summary": summary.to_dict(orient="records"),
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(coverage_table, summary, latest_date), encoding="utf-8")

    total_coverage = coverage_table[coverage_table["product_vt_symbol"] == "__TOTAL__"]
    print(total_coverage[["window_name", "analysis_start", "analysis_end", "coverage_ratio", "missing_days"]].to_string(index=False))
    if not summary.empty:
        print(summary[["window_name", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_trade_count", "win_ratio"]].to_string(index=False))
    print(f"[stage149] coverage: {COVERAGE_CSV_PATH}")
    print(f"[stage149] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage149] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
