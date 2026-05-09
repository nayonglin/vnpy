from __future__ import annotations

import contextlib
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage194_stage78_2015_multicycle_viability import (
    COVERAGE_PASS_THRESHOLD,
    build_coverage_table,
    load_contract_date_sets,
)
from analyze_qmt_roll_stage199_stage78_2015_2019_deep_signal_trace import to_markdown_table
from main_contract_mapping import get_preferred_mapping_path, load_mapping_df, load_product_universe_symbols
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
GENERATED_DIR: Path = OUTPUT_DIR / "stage205_generated_inputs"

MODEL_TAG: str = "stage205_stage78_fu_legal_mapping_counterfactual_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage205_stage78_fu_legal_mapping_counterfactual"

FU_LEGAL_START: datetime = datetime(2018, 7, 16)
REQUESTED_START: datetime = datetime(2015, 1, 5)
PRELOAD_START: datetime = datetime(2014, 1, 5)

LEGAL_MAPPING_PATH: Path = GENERATED_DIR / f"{OUTPUT_PREFIX}_fu_from_20180716_{MODEL_TAG}.csv"
COVERAGE_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


WINDOWS: tuple[dict[str, Any], ...] = (
    {
        "window_name": "requested_since_2015",
        "display_label": "2015起点请求窗口",
        "analysis_start": REQUESTED_START,
        "analysis_end": END_DT,
        "kind": "coverage_request",
        "run_backtest": True,
    },
    {
        "window_name": "early_data_2015_2017",
        "display_label": "2015-2017早期数据段",
        "analysis_start": datetime(2015, 1, 5),
        "analysis_end": datetime(2017, 12, 29),
        "kind": "coverage_request",
        "run_backtest": True,
    },
    {
        "window_name": "transition_2018_2019",
        "display_label": "2018-2019过渡数据段",
        "analysis_start": datetime(2018, 1, 2),
        "analysis_end": datetime(2019, 12, 31),
        "kind": "coverage_request",
        "run_backtest": True,
    },
    {
        "window_name": "full_2020_2026",
        "display_label": "2020-2026正式可信窗口",
        "analysis_start": datetime(2020, 1, 1),
        "analysis_end": END_DT,
        "kind": "trusted_multicycle",
        "run_backtest": True,
    },
)


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt(value: Any, digits: int = 4) -> str:
    return f"{_safe_float(value):,.{digits}f}"


def build_fu_legal_mapping() -> tuple[Path, dict[str, Any]]:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    mapping_path = get_preferred_mapping_path()
    df = pd.read_csv(mapping_path)
    df["date"] = pd.to_datetime(df["date"])
    df["continuous_symbol_vt"] = df["continuous_symbol_vt"].fillna("").astype(str)
    early_fu_mask = (df["continuous_symbol_vt"] == "fu.SHFE") & (df["date"] < FU_LEGAL_START)
    blanked_rows = int(early_fu_mask.sum())
    blanked_contracts = sorted(df.loc[early_fu_mask, "main_contract_vt"].dropna().astype(str).unique().tolist())
    df.loc[early_fu_mask, ["main_contract_tq", "main_contract_vt"]] = ""
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df.to_csv(LEGAL_MAPPING_PATH, index=False, encoding="utf-8-sig")
    return LEGAL_MAPPING_PATH, {
        "source_mapping_path": str(mapping_path),
        "legal_mapping_path": str(LEGAL_MAPPING_PATH),
        "fu_legal_start": FU_LEGAL_START.date().isoformat(),
        "blanked_fu_rows_before_legal_start": blanked_rows,
        "blanked_fu_contracts": blanked_contracts,
    }


def build_coverage(mapping_path: Path, profile_name: str, product_symbols: list[str]) -> pd.DataFrame:
    mapping_df = load_mapping_df(mapping_path)
    mapping_df["date"] = pd.to_datetime(mapping_df["date"])
    window_start = min(window["analysis_start"] for window in WINDOWS)
    window_end = max(window["analysis_end"] for window in WINDOWS)
    contract_symbols = set(
        mapping_df[
            mapping_df["continuous_symbol_vt"].isin(set(product_symbols))
            & (mapping_df["date"] >= window_start)
            & (mapping_df["date"] <= window_end)
            & mapping_df["main_contract_vt"].fillna("").ne("")
        ]["main_contract_vt"].astype(str)
    )
    contract_date_sets = load_contract_date_sets(contract_symbols, window_start, window_end)
    coverage_df = build_coverage_table(mapping_df, product_symbols, list(WINDOWS), contract_date_sets)
    coverage_df.insert(0, "profile_name", profile_name)
    coverage_df["coverage_pass_threshold"] = COVERAGE_PASS_THRESHOLD
    coverage_df["coverage_pass"] = coverage_df["coverage_ratio"] >= COVERAGE_PASS_THRESHOLD
    return coverage_df


def run_window(profile_name: str, mapping_path: Path | None, window: dict[str, Any]) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    if mapping_path is not None:
        overrides["mapping_csv_path"] = str(mapping_path)
    with contextlib.redirect_stdout(io.StringIO()):
        _, _, stats = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=overrides,
            analysis_start=window["analysis_start"],
            analysis_end=window["analysis_end"],
            preload_start=PRELOAD_START,
            capital=OFFICIAL_STAGE78_CAPITAL,
            save_artifacts=False,
            include_start_year_sweep=False,
            file_prefix=f"{OUTPUT_PREFIX}_{profile_name}_{window['window_name']}",
            chart_title=f"Stage205 {profile_name} {window['window_name']}",
        )
    return build_summary_row(
        stats,
        analysis_start=window["analysis_start"],
        analysis_end=window["analysis_end"],
        profile_name=profile_name,
        window_name=window["window_name"],
        display_label=window["display_label"],
        kind=window["kind"],
        mapping_csv_path=str(mapping_path or get_preferred_mapping_path()),
        total_slippage=float(stats.get("total_slippage", 0) or 0),
        total_commission=float(stats.get("total_commission", 0) or 0),
        total_net_pnl=float(stats.get("total_net_pnl", 0) or 0),
        profit_days=int(stats.get("profit_days", 0) or 0),
        loss_days=int(stats.get("loss_days", 0) or 0),
    )


def run_backtest_matrix(legal_mapping_path: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    profiles: tuple[tuple[str, Path | None], ...] = (
        ("baseline_original_mapping", None),
        ("fu_legal_from_20180716", legal_mapping_path),
    )
    for profile_name, mapping_path in profiles:
        for window in WINDOWS:
            print(f"[stage205] run {profile_name} {window['window_name']}", flush=True)
            rows.append(run_window(profile_name, mapping_path, window))
    return pd.DataFrame(rows)


def build_report(summary_df: pd.DataFrame, coverage_df: pd.DataFrame, mapping_info: dict[str, Any]) -> str:
    total_coverage = coverage_df[coverage_df["product_vt_symbol"] == "__TOTAL__"].copy()
    coverage_view = total_coverage[
        [
            "profile_name",
            "window_name",
            "mapped_days",
            "present_days",
            "missing_days",
            "coverage_ratio",
            "coverage_pass",
        ]
    ].copy()
    coverage_view["coverage_ratio"] = coverage_view["coverage_ratio"].map(lambda value: _fmt(value, 4))

    summary_view = summary_df[
        [
            "profile_name",
            "window_name",
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "sharpe_ratio",
            "total_trade_count",
            "total_slippage",
            "win_ratio_pct",
        ]
    ].copy()
    summary_view["end_balance"] = summary_view["end_balance"].map(lambda value: _fmt(value, 2))
    summary_view["total_slippage"] = summary_view["total_slippage"].map(lambda value: _fmt(value, 2))
    for column in ["total_return_pct", "max_dd_percent", "sharpe_ratio", "win_ratio_pct"]:
        summary_view[column] = summary_view[column].map(lambda value: _fmt(value, 4))

    product_gaps = coverage_df[
        (coverage_df["product_vt_symbol"] != "__TOTAL__") & (coverage_df["missing_days"] > 0)
    ].copy()
    product_gaps = product_gaps.sort_values(["profile_name", "window_name", "missing_days"], ascending=[True, True, False])

    return f"""# Stage205 第78 fu历史合法映射反事实

## 口径

- 策略版本：`{OFFICIAL_STAGE78_VERSION}`
- 策略角色：`{OFFICIAL_STAGE78_ROLE}`
- 资金：`{OFFICIAL_STAGE78_CAPITAL:,.0f}`
- baseline_original_mapping：使用当前全市场主力映射。
- fu_legal_from_20180716：`fu.SHFE`在2018-07-16前不参与映射，其他第78参数不变。
- 依据：上期所2018-06-26公告，老180燃料油合约终止交易，保税380燃料油合约2018-07-16挂牌。
- 本阶段是可交易域反事实，不是收益调参。
- 注：所有窗口统一使用2014-01-05预加载，目的是做baseline与fu_legal同口径对照；`full_2020_2026`不替代正式2020冷启动报告。

## 映射改动

- 源映射：`{mapping_info['source_mapping_path']}`
- 生成映射：`{mapping_info['legal_mapping_path']}`
- fu合法起点：`{mapping_info['fu_legal_start']}`
- 置空早期fu映射行数：`{mapping_info['blanked_fu_rows_before_legal_start']}`
- 置空合约：`{', '.join(mapping_info['blanked_fu_contracts'])}`

## 覆盖率

{to_markdown_table(coverage_view, max_rows=20)}

## 回测摘要

{to_markdown_table(summary_view, max_rows=20)}

## 剩余缺口

{to_markdown_table(product_gaps[['profile_name', 'window_name', 'product_vt_symbol', 'mapped_days', 'present_days', 'missing_days', 'coverage_ratio', 'missing_contract_examples']], max_rows=60)}

## 判断

1. 如果fu合法映射显著提升2015-2017覆盖率，说明早期缺口主要来自老燃料油不可交易/不可验证。
2. 如果2015起点收益结构仍能维持正收益，说明第78不是完全依赖早期fu噪声。
3. 如果2020-2026结果不变，说明该处理只影响历史合法域，不污染正式样本。

## 过拟合反思

- 本阶段不是为了提高收益而剔除品种，而是按交易所制度切换定义历史可交易域。
- 后续不得继续按收益选择其他品种的历史起点；只有明确制度/上市/终止交易依据才允许做类似处理。
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    legal_mapping_path, mapping_info = build_fu_legal_mapping()
    overrides = build_official_stage78_overrides()
    product_symbols = load_product_universe_symbols(str(overrides["product_universe_csv_path"]))
    if not product_symbols:
        raise RuntimeError("Stage78 product universe is empty.")

    coverage_frames = [
        build_coverage(get_preferred_mapping_path(), "baseline_original_mapping", product_symbols),
        build_coverage(legal_mapping_path, "fu_legal_from_20180716", product_symbols),
    ]
    coverage_df = pd.concat(coverage_frames, ignore_index=True)
    summary_df = run_backtest_matrix(legal_mapping_path)

    coverage_df.to_csv(COVERAGE_CSV_PATH, index=False, encoding="utf-8-sig")
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "mapping_info": mapping_info,
        "outputs": {
            "legal_mapping": str(legal_mapping_path),
            "coverage": str(COVERAGE_CSV_PATH),
            "summary": str(SUMMARY_CSV_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary_df, coverage_df, mapping_info), encoding="utf-8")

    print(f"legal_mapping: {legal_mapping_path}")
    print(f"coverage: {COVERAGE_CSV_PATH}")
    print(f"summary: {SUMMARY_CSV_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
