from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_range_reversion_core4_v7_weak_window_trade_replay import _safe_float, _to_local_date


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
SOURCE_PREFIX: str = "qmt_range_reversion_core4_directed_product_signal_back_adjusted_v8_two_stage_stop"
SIGNAL_MODEL_TAG: str = "range_reversion_core4_v8_signal_attribution_v1"
MODEL_TAG: str = "range_reversion_core4_v8_long_tradability_v1"

CAPITAL_LEVELS: tuple[int, ...] = (200_000, 300_000, 400_000, 500_000, 800_000, 1_000_000)

CANDIDATES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
SIGNAL_DETAIL_PATH: Path = (
    OUTPUT_DIR / f"qmt_range_reversion_core4_v8_signal_attribution_detail_{SIGNAL_MODEL_TAG}.csv"
)
DETAIL_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_long_tradability_detail_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_long_tradability_product_{MODEL_TAG}.csv"
REASON_SUMMARY_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_long_tradability_reason_{MODEL_TAG}.csv"
CAPITAL_COVERAGE_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_long_tradability_capital_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_long_tradability_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_core4_v8_long_tradability_report_{MODEL_TAG}.md"


def _configure_paths(
    source_prefix: str | None = None,
    signal_model_tag: str | None = None,
    model_tag: str | None = None,
) -> None:
    global SOURCE_PREFIX
    global SIGNAL_MODEL_TAG
    global MODEL_TAG
    global CANDIDATES_PATH
    global SIGNAL_DETAIL_PATH
    global DETAIL_PATH
    global PRODUCT_SUMMARY_PATH
    global REASON_SUMMARY_PATH
    global CAPITAL_COVERAGE_PATH
    global SUMMARY_JSON_PATH
    global REPORT_PATH

    if source_prefix:
        SOURCE_PREFIX = source_prefix
    if signal_model_tag:
        SIGNAL_MODEL_TAG = signal_model_tag
    if model_tag:
        MODEL_TAG = model_tag

    report_prefix = "qmt_range_reversion_core4"
    if "_v8_" in SOURCE_PREFIX:
        report_prefix = "qmt_range_reversion_core4_v8"
    elif "_v9_" in SOURCE_PREFIX:
        report_prefix = "qmt_range_reversion_core4_v9"

    CANDIDATES_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
    SIGNAL_DETAIL_PATH = OUTPUT_DIR / f"{report_prefix}_signal_attribution_detail_{SIGNAL_MODEL_TAG}.csv"
    DETAIL_PATH = OUTPUT_DIR / f"{report_prefix}_long_tradability_detail_{MODEL_TAG}.csv"
    PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{report_prefix}_long_tradability_product_{MODEL_TAG}.csv"
    REASON_SUMMARY_PATH = OUTPUT_DIR / f"{report_prefix}_long_tradability_reason_{MODEL_TAG}.csv"
    CAPITAL_COVERAGE_PATH = OUTPUT_DIR / f"{report_prefix}_long_tradability_capital_{MODEL_TAG}.csv"
    SUMMARY_JSON_PATH = OUTPUT_DIR / f"{report_prefix}_long_tradability_summary_{MODEL_TAG}.json"
    REPORT_PATH = OUTPUT_DIR / f"{report_prefix}_long_tradability_report_{MODEL_TAG}.md"


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not CANDIDATES_PATH.exists():
        raise FileNotFoundError(CANDIDATES_PATH)
    if not SIGNAL_DETAIL_PATH.exists():
        raise FileNotFoundError(SIGNAL_DETAIL_PATH)

    candidates = pd.read_csv(CANDIDATES_PATH, encoding="utf-8-sig")
    signal_detail = pd.read_csv(SIGNAL_DETAIL_PATH, encoding="utf-8-sig")
    candidates["signal_date"] = candidates["datetime"].map(_to_local_date)
    candidates["signal_year"] = candidates["signal_date"].dt.year
    if "passed_initial_filter" in candidates.columns:
        candidates = candidates[candidates["passed_initial_filter"].fillna(0).astype(int).eq(1)].copy()
    candidates = candidates[candidates["direction"].eq("long")].copy()
    signal_detail = signal_detail[signal_detail["direction"].eq("long")].copy()
    return candidates, signal_detail


def _zero_volume_reason(row: pd.Series) -> str:
    selected_volume = _safe_float(row.get("selected_volume"), 0.0)
    if selected_volume > 0:
        return "opened"

    contracts_by_risk = _safe_float(row.get("contracts_by_risk"), 0.0)
    contracts_by_margin = _safe_float(row.get("contracts_by_margin"), 0.0)
    contracts_by_single_trade_cap = _safe_float(row.get("contracts_by_single_trade_cap"), 0.0)

    if contracts_by_risk < 1 and contracts_by_margin >= 1 and contracts_by_single_trade_cap >= 1:
        return "risk_budget_below_one_contract"
    if contracts_by_margin < 1:
        return "margin_budget_below_one_contract"
    if contracts_by_single_trade_cap < 1:
        return "single_trade_cap_below_one_contract"
    return "other_zero_volume"


def _merge_signal_detail(candidates: pd.DataFrame, signal_detail: pd.DataFrame) -> pd.DataFrame:
    signal_cols = [
        "candidate_index",
        "signal_label",
        "forward_close_10d_r",
        "mfe_10d_r",
        "mae_10d_r",
        "mfe_20d_r",
        "mae_20d_r",
        "middle_before_initial_stop_20d",
        "initial_stop_before_middle_20d",
        "first_middle_bar",
        "first_initial_stop_bar",
        "first_hard_stop_bar",
    ]
    available_cols = [col for col in signal_cols if col in signal_detail.columns]
    return candidates.merge(signal_detail[available_cols], on="candidate_index", how="left")


def _build_detail(candidates: pd.DataFrame, signal_detail: pd.DataFrame) -> pd.DataFrame:
    merged = _merge_signal_detail(candidates, signal_detail)
    rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        target_risk_amount = _safe_float(row.get("target_risk_amount"))
        risk_per_contract = _safe_float(row.get("risk_per_contract"))
        sizing_equity = _safe_float(row.get("sizing_equity"))
        margin_per_contract = _safe_float(row.get("margin_per_contract"))
        single_trade_capital_limit = _safe_float(row.get("single_trade_capital_limit"))
        allowed_capital = _safe_float(row.get("allowed_capital"))
        planned_entry_price = _safe_float(row.get("planned_entry_price"))
        stop_distance = _safe_float(row.get("stop_distance"))
        selected_volume = _safe_float(row.get("selected_volume"), 0.0)

        effective_risk_budget_pct = target_risk_amount / sizing_equity if sizing_equity > 0 else float("nan")
        required_sizing_equity = (
            risk_per_contract / effective_risk_budget_pct
            if effective_risk_budget_pct > 0 and not pd.isna(risk_per_contract)
            else float("nan")
        )
        risk_contract_to_budget = (
            risk_per_contract / target_risk_amount if target_risk_amount > 0 else float("nan")
        )

        capital_flags = {
            f"fits_{capital}_capital": int(
                not pd.isna(required_sizing_equity) and required_sizing_equity <= capital
            )
            for capital in CAPITAL_LEVELS
        }

        rows.append(
            {
                "candidate_index": int(row["candidate_index"]),
                "signal_date": row["signal_date"],
                "signal_year": int(row["signal_year"]),
                "product_vt_symbol": str(row.get("product_vt_symbol", "")),
                "contract_vt_symbol": str(row.get("contract_vt_symbol", "")),
                "candidate_status": str(row.get("candidate_status", "")),
                "skip_reason": str(row.get("skip_reason", "")),
                "zero_volume_reason": _zero_volume_reason(row),
                "is_opened": int(_safe_float(row.get("is_opened"), 0.0)),
                "selected_volume": selected_volume,
                "target_risk_amount": target_risk_amount,
                "risk_per_contract": risk_per_contract,
                "risk_contract_to_budget": risk_contract_to_budget,
                "sizing_equity": sizing_equity,
                "effective_risk_budget_pct": effective_risk_budget_pct,
                "required_sizing_equity_for_1_contract": required_sizing_equity,
                "min_effective_risk_pct_for_1_contract": (
                    risk_per_contract / sizing_equity if sizing_equity > 0 else float("nan")
                ),
                "planned_entry_price": planned_entry_price,
                "stop_distance": stop_distance,
                "stop_distance_pct": stop_distance / planned_entry_price if planned_entry_price > 0 else float("nan"),
                "contract_size": _safe_float(row.get("size")),
                "margin_per_contract": margin_per_contract,
                "single_trade_capital_limit": single_trade_capital_limit,
                "allowed_capital": allowed_capital,
                "margin_to_single_trade_cap": (
                    margin_per_contract / single_trade_capital_limit
                    if single_trade_capital_limit > 0
                    else float("nan")
                ),
                "margin_to_allowed_capital": (
                    margin_per_contract / allowed_capital if allowed_capital > 0 else float("nan")
                ),
                "contracts_by_risk": _safe_float(row.get("contracts_by_risk")),
                "contracts_by_margin": _safe_float(row.get("contracts_by_margin")),
                "contracts_by_single_trade_cap": _safe_float(row.get("contracts_by_single_trade_cap")),
                "signal_label": str(row.get("signal_label", "")),
                "forward_close_10d_r": _safe_float(row.get("forward_close_10d_r")),
                "mfe_10d_r": _safe_float(row.get("mfe_10d_r")),
                "mae_10d_r": _safe_float(row.get("mae_10d_r")),
                "mfe_20d_r": _safe_float(row.get("mfe_20d_r")),
                "mae_20d_r": _safe_float(row.get("mae_20d_r")),
                "middle_before_initial_stop_20d": int(
                    _safe_float(row.get("middle_before_initial_stop_20d"), 0.0)
                ),
                "initial_stop_before_middle_20d": int(
                    _safe_float(row.get("initial_stop_before_middle_20d"), 0.0)
                ),
                **capital_flags,
            }
        )
    return pd.DataFrame(rows)


def _rate(series: pd.Series, value: str) -> float:
    if series.empty:
        return 0.0
    return float(series.eq(value).mean())


def _product_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame()

    agg_dict: dict[str, Any] = {
        "signals": ("candidate_index", "size"),
        "opened": ("is_opened", "sum"),
        "opened_rate": ("is_opened", "mean"),
        "risk_budget_zero_count": (
            "zero_volume_reason",
            lambda s: int(s.eq("risk_budget_below_one_contract").sum()),
        ),
        "avg_risk_per_contract": ("risk_per_contract", "mean"),
        "median_risk_per_contract": ("risk_per_contract", "median"),
        "avg_target_risk_amount": ("target_risk_amount", "mean"),
        "median_required_equity": ("required_sizing_equity_for_1_contract", "median"),
        "p75_required_equity": (
            "required_sizing_equity_for_1_contract",
            lambda s: float(s.quantile(0.75)),
        ),
        "max_required_equity": ("required_sizing_equity_for_1_contract", "max"),
        "avg_risk_contract_to_budget": ("risk_contract_to_budget", "mean"),
        "avg_margin_to_allowed_capital": ("margin_to_allowed_capital", "mean"),
        "avg_forward_close_10d_r": ("forward_close_10d_r", "mean"),
        "avg_mfe_10d_r": ("mfe_10d_r", "mean"),
        "avg_mae_10d_r": ("mae_10d_r", "mean"),
        "clean_reversion_rate": ("signal_label", lambda s: _rate(s, "clean_reversion")),
        "trend_continuation_rate": ("signal_label", lambda s: _rate(s, "trend_continuation")),
        "stop_first_delayed_reversion_rate": (
            "signal_label",
            lambda s: _rate(s, "stop_first_delayed_reversion"),
        ),
    }
    for capital in CAPITAL_LEVELS:
        agg_dict[f"fits_{capital}_capital_count"] = (f"fits_{capital}_capital", "sum")

    summary = detail.groupby(["product_vt_symbol"], dropna=False).agg(**agg_dict).reset_index()
    return summary.sort_values(["signals"], ascending=False).reset_index(drop=True)


def _reason_summary(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame()
    return detail.groupby(["zero_volume_reason"], dropna=False).agg(
        signals=("candidate_index", "size"),
        opened=("is_opened", "sum"),
        avg_risk_per_contract=("risk_per_contract", "mean"),
        avg_target_risk_amount=("target_risk_amount", "mean"),
        median_required_equity=("required_sizing_equity_for_1_contract", "median"),
        avg_forward_close_10d_r=("forward_close_10d_r", "mean"),
        avg_mfe_10d_r=("mfe_10d_r", "mean"),
        avg_mae_10d_r=("mae_10d_r", "mean"),
        clean_reversion_rate=("signal_label", lambda s: _rate(s, "clean_reversion")),
        trend_continuation_rate=("signal_label", lambda s: _rate(s, "trend_continuation")),
    ).reset_index().sort_values(["signals"], ascending=False).reset_index(drop=True)


def _capital_coverage(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for product, group in detail.groupby("product_vt_symbol", dropna=False):
        for capital in CAPITAL_LEVELS:
            flag = f"fits_{capital}_capital"
            fits = int(group[flag].sum())
            rows.append(
                {
                    "product_vt_symbol": product,
                    "capital": capital,
                    "signals": int(len(group)),
                    "fits_one_contract_by_risk": fits,
                    "coverage_rate": fits / len(group) if len(group) else 0.0,
                    "avg_forward_close_10d_r_of_fit": (
                        float(group.loc[group[flag].eq(1), "forward_close_10d_r"].mean())
                        if fits
                        else float("nan")
                    ),
                }
            )
    return pd.DataFrame(rows)


def _write_report(
    detail: pd.DataFrame,
    product_summary: pd.DataFrame,
    reason_summary: pd.DataFrame,
    capital_coverage: pd.DataFrame,
) -> None:
    risk_zero_count = int(detail["zero_volume_reason"].eq("risk_budget_below_one_contract").sum())
    skipped_count = int(detail["is_opened"].eq(0).sum())
    lines = [
        "# QMT震荡Core4 V8长侧可交易性归因",
        "",
        "## 范围",
        "- 只读取v8长侧候选信号、v8信号层归因结果和仓位测算字段，不运行新策略回测。",
        "- 不新增交易规则、不提高风险、不修改第78趋势策略。",
        "- 目标是解释`y.DCE`、`nr.INE`等长侧信号为什么大量`sizing_zero_volume`。",
        "",
        "## 结论",
        f"- 长侧候选信号数：`{len(detail)}`。",
        f"- 实际开仓数：`{int(detail['is_opened'].sum())}`。",
        f"- 未开仓数：`{skipped_count}`。",
        f"- 其中`risk_budget_below_one_contract`：`{risk_zero_count}`。",
        "- 若`contracts_by_margin`和`contracts_by_single_trade_cap`均大于0，但`contracts_by_risk=0`，说明瓶颈是单合约风险超过当前目标风险预算，而不是保证金不够。",
        "",
        "## 按品种",
        product_summary.to_markdown(index=False) if not product_summary.empty else "- 无。",
        "",
        "## 按零仓原因",
        reason_summary.to_markdown(index=False) if not reason_summary.empty else "- 无。",
        "",
        "## 按资金规模的单合约风险覆盖",
        capital_coverage.to_markdown(index=False) if not capital_coverage.empty else "- 无。",
        "",
        "## 输出",
        f"- 明细：`{DETAIL_PATH}`",
        f"- 品种汇总：`{PRODUCT_SUMMARY_PATH}`",
        f"- 原因汇总：`{REASON_SUMMARY_PATH}`",
        f"- 资金覆盖：`{CAPITAL_COVERAGE_PATH}`",
        f"- JSON摘要：`{SUMMARY_JSON_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _json_safe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    safe = frame.where(pd.notna(frame), None)
    return safe.to_dict(orient="records")


def run_analysis() -> dict[str, Any]:
    candidates, signal_detail = _load_inputs()
    detail = _build_detail(candidates, signal_detail)
    product_summary = _product_summary(detail)
    reason_summary = _reason_summary(detail)
    capital_coverage = _capital_coverage(detail)

    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    reason_summary.to_csv(REASON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    capital_coverage.to_csv(CAPITAL_COVERAGE_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "signal_model_tag": SIGNAL_MODEL_TAG,
        "long_signals": int(len(detail)),
        "opened_signals": int(detail["is_opened"].sum()) if not detail.empty else 0,
        "risk_budget_below_one_contract": int(
            detail["zero_volume_reason"].eq("risk_budget_below_one_contract").sum()
        )
        if not detail.empty
        else 0,
        "product_summary": _json_safe_records(product_summary),
        "reason_summary": _json_safe_records(reason_summary),
        "outputs": {
            "detail": str(DETAIL_PATH),
            "product_summary": str(PRODUCT_SUMMARY_PATH),
            "reason_summary": str(REASON_SUMMARY_PATH),
            "capital_coverage": str(CAPITAL_COVERAGE_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(detail, product_summary, reason_summary, capital_coverage)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze long-side tradability for range reversion Core4 v8.")
    parser.add_argument("--source-prefix", default=SOURCE_PREFIX)
    parser.add_argument("--signal-model-tag", default=SIGNAL_MODEL_TAG)
    parser.add_argument("--model-tag", default=MODEL_TAG)
    args = parser.parse_args()

    _configure_paths(
        source_prefix=args.source_prefix,
        signal_model_tag=args.signal_model_tag,
        model_tag=args.model_tag,
    )
    summary = run_analysis()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
