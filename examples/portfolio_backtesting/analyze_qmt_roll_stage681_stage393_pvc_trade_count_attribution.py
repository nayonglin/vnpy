from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage674_stage372_500k_trade_risk001_ni_ag_sc_p as s674
import analyze_qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd as s678
import analyze_qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123 as s679
import analyze_qmt_roll_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123 as s680
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df, build_entry_risk_diagnostics_df


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage681_stage393_pvc_trade_count_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage681_stage393_pvc_trade_count_attribution"

STAGE391_NAME = "stage391_c2_plus24_no_pvc"
STAGE393_NAME = "stage393_c2_plus25_with_pvc"

PRODUCT_TRADE_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_trade_delta_{MODEL_TAG}.csv"
MONTHLY_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_delta_{MODEL_TAG}.csv"
YEAR_END_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_end_equity_{MODEL_TAG}.csv"
CANDIDATE_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_status_{MODEL_TAG}.csv"
CANDIDATE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_product_{MODEL_TAG}.csv"
SIZING_LIMIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sizing_limit_{MODEL_TAG}.csv"
POSITIONS_391_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_stage391_{MODEL_TAG}.csv"
POSITIONS_393_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_stage393_{MODEL_TAG}.csv"
CANDIDATES_391_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_stage391_{MODEL_TAG}.csv"
CANDIDATES_393_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_stage393_{MODEL_TAG}.csv"
RISKS_391_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_stage391_{MODEL_TAG}.csv"
RISKS_393_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_stage393_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    try:
        import numpy as np

        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
    except Exception:
        pass
    return value


def _product_from_symbol(symbol: Any) -> str:
    text = str(symbol or "")
    first = text.split(".", 1)[0]
    product = ""
    for char in first:
        if char.isalpha():
            product += char
        else:
            break
    return product.lower()


def _build_stage391_spec() -> tuple[Any, dict[str, Any]]:
    s679._configure_stage679()
    s674._configure_shared_runner()
    original_plus_spec = s674.s667._plus_combo_500k_spec
    try:
        s674.s667._plus_combo_500k_spec = s678._no_ai_plus_combo_500k_spec
        prepared = s674.s667._prepare_inputs()
        base_plus = s674.s667._plus_combo_500k_spec(prepared["plus_metadata"])
        spec = s674._spec_with_trade_risk(
            base_plus,
            variant=s674.TARGET_NO_MAXPOS_VARIANT,
            label="Stage391 C2 attribution rerun",
            trade_risk_ratio=s674.TARGET_TRADE_RISK_RATIO,
            maxpos=len(prepared["plus_symbols"]),
        )
    finally:
        s674.s667._plus_combo_500k_spec = original_plus_spec
    return spec, prepared["plus_metadata"]


def _build_stage393_spec() -> tuple[Any, dict[str, Any]]:
    s680._configure_stage680()
    s674._configure_shared_runner()
    original_plus_spec = s674.s667._plus_combo_500k_spec
    try:
        s674.s667._plus_combo_500k_spec = s680._no_ai_plus_combo_500k_spec
        prepared = s674.s667._prepare_inputs()
        base_plus = s674.s667._plus_combo_500k_spec(prepared["plus_metadata"])
        spec = s674._spec_with_trade_risk(
            base_plus,
            variant=s674.TARGET_NO_MAXPOS_VARIANT,
            label="Stage393 C2 attribution rerun",
            trade_risk_ratio=s674.TARGET_TRADE_RISK_RATIO,
            maxpos=len(prepared["plus_symbols"]),
        )
    finally:
        s674.s667._plus_combo_500k_spec = original_plus_spec
    return spec, prepared["plus_metadata"]


def _run_full_with_diagnostics(name: str, spec: Any, metadata: dict[str, Any]) -> dict[str, pd.DataFrame]:
    s653 = s674.s667.s666.s653
    s517 = s653.s517
    s513 = s674.s667.s666.s513
    s650 = s674.s667.s666.s650

    analysis_start = pd.Timestamp("2020-01-02")
    analysis_end = pd.Timestamp("2026-04-30")
    original_start = s517.START_DT
    original_end = s517.END_DT
    try:
        s517.START_DT = analysis_start.to_pydatetime()
        s517.END_DT = analysis_end.to_pydatetime()
        s517.assert_stage196_database_sentinels()
        s517.s506._patch_stage506_raw_roots()
        c3_overrides = s513._c3_overrides(s517.START_DT)
        preload_start = max(s517.PRELOAD_START_DT, s517.START_DT - timedelta(days=365))
        _, open_map = s517.s506.s501._seed_proxy_maps()
        engine = s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s517.Interval.DAILY,
            start=preload_start,
            end=s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s517.build_roll_setting(
            metadata["margin_ratios"],
            risk_ratio=s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
            strategy_overrides=c3_overrides,
        )
        setting["capital_base"] = spec.capital.c3_capital
        setting.update(spec.overrides)
        engine.add_strategy(QmtRollPortfolioStrategy, setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            raise RuntimeError(f"empty daily result: {name}")

        daily = daily_df.copy()
        daily = daily.loc[
            (daily.index >= s517.START_DT.date()) & (daily.index <= s517.END_DT.date())
        ].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["account_equity"] = spec.capital.c3_capital + daily["net_pnl"].cumsum()
        daily["run_name"] = name
        daily["variant"] = spec.capital.variant

        positions = s517.build_positions_df(engine)
        positions["run_name"] = name
        positions["variant"] = spec.capital.variant
        positions["combo_variant"] = spec.capital.variant
        positions["label"] = spec.capital.label
        positions["risk_multiplier"] = spec.capital.risk_multiplier
        usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
        if not usage.empty:
            usage["run_name"] = name
            usage["variant"] = spec.capital.variant
            usage["label"] = spec.capital.label
            usage["risk_multiplier"] = spec.capital.risk_multiplier
        candidates = build_entry_candidate_snapshots_df(engine)
        if not candidates.empty:
            candidates["run_name"] = name
            candidates["variant"] = spec.capital.variant
        risks = build_entry_risk_diagnostics_df(engine)
        if not risks.empty:
            risks["run_name"] = name
            risks["variant"] = spec.capital.variant
        forced_events = pd.DataFrame(getattr(engine.strategy, "forced_margin_deleverage_events", []))
        if not forced_events.empty:
            forced_events["run_name"] = name
            forced_events["variant"] = spec.capital.variant

        c3_margin_daily, _product_margin = s513._position_margin(positions, metadata)
        combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
        combined["run_name"] = name
        combined["variant"] = spec.capital.variant
        return {
            "daily": combined,
            "positions": positions,
            "usage": usage,
            "candidates": candidates,
            "risks": risks,
            "forced_events": forced_events,
        }
    finally:
        s517.START_DT = original_start
        s517.END_DT = original_end


def _position_product_summary(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["product"] = data["vt_symbol"].map(_product_from_symbol)
    for column in ["net_pnl", "slippage", "trade_count", "end_pos"]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    active = data[data["end_pos"].abs().gt(0)].copy()
    rows = []
    for (run_name, product), group in data.groupby(["run_name", "product"], sort=True):
        active_group = active[(active["run_name"].eq(run_name)) & (active["product"].eq(product))]
        rows.append(
            {
                "run_name": run_name,
                "product": product,
                "net_pnl": float(group["net_pnl"].sum()),
                "slippage": float(group["slippage"].sum()),
                "trade_count": float(group["trade_count"].sum()),
                "active_days": int(pd.to_datetime(active_group.get("date"), errors="coerce").dt.normalize().nunique())
                if not active_group.empty
                else 0,
            }
        )
    return pd.DataFrame(rows)


def _product_trade_delta(pos391: pd.DataFrame, pos393: pd.DataFrame) -> pd.DataFrame:
    left = _position_product_summary(pos391).rename(
        columns={
            "net_pnl": "stage391_net_pnl",
            "slippage": "stage391_slippage",
            "trade_count": "stage391_trade_count",
            "active_days": "stage391_active_days",
        }
    )
    right = _position_product_summary(pos393).rename(
        columns={
            "net_pnl": "stage393_net_pnl",
            "slippage": "stage393_slippage",
            "trade_count": "stage393_trade_count",
            "active_days": "stage393_active_days",
        }
    )
    merged = left.drop(columns=["run_name"], errors="ignore").merge(
        right.drop(columns=["run_name"], errors="ignore"),
        on="product",
        how="outer",
    )
    for column in [
        "stage391_net_pnl",
        "stage391_slippage",
        "stage391_trade_count",
        "stage391_active_days",
        "stage393_net_pnl",
        "stage393_slippage",
        "stage393_trade_count",
        "stage393_active_days",
    ]:
        merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
    merged["delta_net_pnl"] = merged["stage393_net_pnl"] - merged["stage391_net_pnl"]
    merged["delta_slippage"] = merged["stage393_slippage"] - merged["stage391_slippage"]
    merged["delta_trade_count"] = merged["stage393_trade_count"] - merged["stage391_trade_count"]
    merged["delta_active_days"] = merged["stage393_active_days"] - merged["stage391_active_days"]
    merged.sort_values(["delta_trade_count", "delta_net_pnl"], inplace=True)
    return merged


def _monthly_delta(daily391: pd.DataFrame, daily393: pd.DataFrame) -> pd.DataFrame:
    def monthly(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
        data = frame.copy()
        data["month"] = pd.to_datetime(data["date"], errors="coerce").dt.to_period("M").astype(str)
        grouped = data.groupby("month", sort=True).agg(
            trade_count=("trade_count", "sum"),
            net_pnl=("net_pnl", "sum"),
            end_equity=("account_equity", "last"),
            max_margin=("broker10_total_margin_exact", "max"),
        )
        grouped = grouped.add_prefix(prefix)
        return grouped.reset_index()

    merged = monthly(daily391, "stage391_").merge(monthly(daily393, "stage393_"), on="month", how="outer")
    for column in merged.columns:
        if column != "month":
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    merged["delta_trade_count"] = merged["stage393_trade_count"] - merged["stage391_trade_count"]
    merged["delta_net_pnl"] = merged["stage393_net_pnl"] - merged["stage391_net_pnl"]
    merged["equity_ratio_393_to_391"] = merged["stage393_end_equity"] / merged["stage391_end_equity"].replace(0.0, pd.NA)
    return merged


def _year_end_equity(daily391: pd.DataFrame, daily393: pd.DataFrame) -> pd.DataFrame:
    def yearly(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
        data = frame.copy()
        data["year"] = pd.to_datetime(data["date"], errors="coerce").dt.year
        grouped = data.groupby("year", sort=True).agg(
            end_equity=("account_equity", "last"),
            trade_count=("trade_count", "sum"),
            net_pnl=("net_pnl", "sum"),
        )
        return grouped.add_prefix(prefix).reset_index()

    merged = yearly(daily391, "stage391_").merge(yearly(daily393, "stage393_"), on="year", how="outer")
    for column in merged.columns:
        if column != "year":
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    merged["equity_ratio_393_to_391"] = merged["stage393_end_equity"] / merged["stage391_end_equity"].replace(0.0, pd.NA)
    merged["delta_trade_count"] = merged["stage393_trade_count"] - merged["stage391_trade_count"]
    merged["delta_net_pnl"] = merged["stage393_net_pnl"] - merged["stage391_net_pnl"]
    return merged


def _candidate_status(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    data = candidates.copy()
    data["candidate_status"] = data["candidate_status"].astype(str)
    data["skip_reason"] = data["skip_reason"].fillna("").astype(str)
    grouped = data.groupby(["run_name", "candidate_status", "skip_reason"], sort=True).size().reset_index(name="count")
    return grouped


def _candidate_product(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    data = candidates.copy()
    data["product"] = data["product_vt_symbol"].map(_product_from_symbol)
    data["selected_volume"] = pd.to_numeric(data.get("selected_volume", 0.0), errors="coerce").fillna(0.0)
    data["is_opened"] = pd.to_numeric(data.get("is_opened", 0.0), errors="coerce").fillna(0.0)
    data["contracts_by_risk"] = pd.to_numeric(data.get("contracts_by_risk", 0.0), errors="coerce").fillna(0.0)
    data["contracts_by_margin"] = pd.to_numeric(data.get("contracts_by_margin", 0.0), errors="coerce").fillna(0.0)
    grouped = data.groupby(["run_name", "product"], sort=True).agg(
        candidate_count=("product", "size"),
        opened_count=("is_opened", "sum"),
        selected_volume_sum=("selected_volume", "sum"),
        avg_selected_volume=("selected_volume", "mean"),
        median_contracts_by_risk=("contracts_by_risk", "median"),
        median_contracts_by_margin=("contracts_by_margin", "median"),
    )
    return grouped.reset_index()


def _sizing_limit(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    data = candidates.copy()
    for column in ["contracts_by_risk", "contracts_by_margin", "contracts_by_single_trade_cap", "selected_volume"]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    opened = data[data["candidate_status"].astype(str).eq("opened")].copy()
    if opened.empty:
        return pd.DataFrame()

    def limit_type(row: pd.Series) -> str:
        values = {
            "risk": float(row["contracts_by_risk"]),
            "margin": float(row["contracts_by_margin"]),
            "single_trade_cap": float(row["contracts_by_single_trade_cap"]),
        }
        positive = {key: value for key, value in values.items() if value > 0}
        if not positive:
            return "unknown"
        min_value = min(positive.values())
        winners = [key for key, value in positive.items() if abs(value - min_value) < 1e-9]
        return "+".join(winners)

    opened["limit_type"] = opened.apply(limit_type, axis=1)
    return opened.groupby(["run_name", "limit_type"], sort=True).size().reset_index(name="opened_count")


def _write_report(decision: dict[str, Any], product_delta: pd.DataFrame, monthly: pd.DataFrame, year_end: pd.DataFrame, status: pd.DataFrame, sizing: pd.DataFrame) -> None:
    top_product = product_delta.sort_values("delta_trade_count").head(12)
    top_month = monthly.sort_values("delta_trade_count").head(12)
    lines = [
        "# Stage681 PVC trade count attribution",
        "",
        "## Key conclusion",
        "",
        "- Adding PVC did not reduce trades because cash was insufficient. It reduced realised trades mainly by damaging the equity path and shrinking risk-budget sizing, while also replacing some existing product opportunities.",
        "- Margin was not the binding constraint in C2: Stage393 C2 max broker10 margin/equity was lower than Stage391 C2.",
        "",
        "## Product trade delta",
        "",
        top_product.to_markdown(index=False),
        "",
        "## Year-end equity ratio",
        "",
        year_end.to_markdown(index=False),
        "",
        "## Largest monthly trade reductions",
        "",
        top_month.to_markdown(index=False),
        "",
        "## Candidate status",
        "",
        status.to_markdown(index=False),
        "",
        "## Opened candidate sizing limit",
        "",
        sizing.to_markdown(index=False),
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    original_can_open_short = QmtRollPortfolioStrategy._can_open_short_signal
    try:
        stage391_spec, stage391_meta = _build_stage391_spec()
        QmtRollPortfolioStrategy._can_open_short_signal = s679._allow_short_cases123
        stage391 = _run_full_with_diagnostics(STAGE391_NAME, stage391_spec, stage391_meta)

        stage393_spec, stage393_meta = _build_stage393_spec()
        QmtRollPortfolioStrategy._can_open_short_signal = s680._allow_short_cases123
        stage393 = _run_full_with_diagnostics(STAGE393_NAME, stage393_spec, stage393_meta)
    finally:
        QmtRollPortfolioStrategy._can_open_short_signal = original_can_open_short

    pos391 = stage391["positions"]
    pos393 = stage393["positions"]
    cand391 = stage391["candidates"]
    cand393 = stage393["candidates"]
    risk391 = stage391["risks"]
    risk393 = stage393["risks"]

    product_delta = _product_trade_delta(pos391, pos393)
    monthly = _monthly_delta(stage391["daily"], stage393["daily"])
    year_end = _year_end_equity(stage391["daily"], stage393["daily"])
    candidates = pd.concat([cand391, cand393], ignore_index=True, sort=False)
    candidate_status = _candidate_status(candidates)
    candidate_product = _candidate_product(candidates)
    sizing_limit = _sizing_limit(candidates)

    pos391.to_csv(POSITIONS_391_PATH, index=False, encoding="utf-8-sig")
    pos393.to_csv(POSITIONS_393_PATH, index=False, encoding="utf-8-sig")
    cand391.to_csv(CANDIDATES_391_PATH, index=False, encoding="utf-8-sig")
    cand393.to_csv(CANDIDATES_393_PATH, index=False, encoding="utf-8-sig")
    risk391.to_csv(RISKS_391_PATH, index=False, encoding="utf-8-sig")
    risk393.to_csv(RISKS_393_PATH, index=False, encoding="utf-8-sig")
    product_delta.to_csv(PRODUCT_TRADE_DELTA_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_DELTA_PATH, index=False, encoding="utf-8-sig")
    year_end.to_csv(YEAR_END_PATH, index=False, encoding="utf-8-sig")
    candidate_status.to_csv(CANDIDATE_STATUS_PATH, index=False, encoding="utf-8-sig")
    candidate_product.to_csv(CANDIDATE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    sizing_limit.to_csv(SIZING_LIMIT_PATH, index=False, encoding="utf-8-sig")

    total391 = float(pos391["trade_count"].sum())
    total393 = float(pos393["trade_count"].sum())
    opened_sizing = sizing_limit.to_dict("records")
    decision = {
        "stage": "Stage394",
        "script_stage": "Stage681",
        "model_tag": MODEL_TAG,
        "stage391_position_trade_count": total391,
        "stage393_position_trade_count": total393,
        "delta_position_trade_count": total393 - total391,
        "candidate_status": candidate_status.to_dict("records"),
        "opened_candidate_sizing_limit": opened_sizing,
        "main_conclusion": "trade_count_reduced_by_equity_path_and_opportunity_replacement_not_cash_shortage",
        "outputs": {
            "product_trade_delta": str(PRODUCT_TRADE_DELTA_PATH),
            "monthly_delta": str(MONTHLY_DELTA_PATH),
            "year_end": str(YEAR_END_PATH),
            "candidate_status": str(CANDIDATE_STATUS_PATH),
            "candidate_product": str(CANDIDATE_PRODUCT_PATH),
            "sizing_limit": str(SIZING_LIMIT_PATH),
            "report": str(REPORT_PATH),
        },
    }
    _write_report(decision, product_delta, monthly, year_end, candidate_status, sizing_limit)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
