from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as s659
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage661_stage653_min_one_throttle_multiperiod as s661
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_roll_official_live_config import OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage664_stage372_plus_ni_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage664_stage372_plus_ni_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

NI_PRODUCT = "ni.SHFE"
PLUS_NI_STRATEGY = "stage664_stage372_plus_ni_entry_filter"
BASELINE_SUMMARY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage662_stage653_recovery_sleeve_multiperiod_summary_"
    "stage662_stage653_recovery_sleeve_multiperiod_v1.csv"
)
BASELINE_COST_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage662_stage653_recovery_sleeve_multiperiod_cost_stress_"
    "stage662_stage653_recovery_sleeve_multiperiod_v1.csv"
)
BASELINE_YTD_SUMMARY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_summary_"
    "stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv"
)

GENERATED_DIR = OUTPUT_DIR / "stage664_generated_inputs"
UNIVERSE_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_universe_{MODEL_TAG}.csv"
HIST_ELIGIBILITY_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_historical_eligibility_{MODEL_TAG}.csv"
LATEST_ELIGIBILITY_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_latest_eligibility_{MODEL_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
NI_ACTIVITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ni_activity_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _official_symbols() -> list[str]:
    overrides = s513._c3_overrides(s513.START_DT)
    symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    if not symbols:
        symbols = s513._metadata()["product_symbols"]
    return sorted(set(symbols))


def _write_plus_ni_universe(symbols: list[str]) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for symbol in sorted(set(symbols) | {NI_PRODUCT}):
        product, exchange = symbol.split(".", 1)
        rows.append(
            {
                "product_vt_symbol": symbol,
                "product": product,
                "exchange": exchange,
                "eligible": 1,
                "source": "stage664_stage372_plus_ni_fixed_add_one",
            }
        )
    pd.DataFrame(rows).to_csv(UNIVERSE_PATH, index=False, encoding="utf-8-sig")


def _write_plus_ni_eligibility(source_path: Path, target_path: Path) -> None:
    source = pd.read_csv(source_path, encoding="utf-8-sig")
    if source.empty:
        raise ValueError(f"empty eligibility source: {source_path}")
    required = {"strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"}
    missing = required - set(source.columns)
    if missing:
        raise ValueError(f"eligibility source missing columns {sorted(missing)}: {source_path}")

    source_strategy = str(source["strategy"].dropna().astype(str).iloc[0])
    frame = source[source["strategy"].astype(str).eq(source_strategy)].copy()
    frame["strategy"] = PLUS_NI_STRATEGY
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in ["score", "score_rank", "top_n"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    groups: list[pd.DataFrame] = []
    for eval_date, group in frame.groupby("eval_date", sort=True):
        group = group.copy()
        next_rank = int(group["score_rank"].max()) + 1
        next_top_n = int(group["top_n"].max()) + (0 if group["product_vt_symbol"].astype(str).eq(NI_PRODUCT).any() else 1)
        group["top_n"] = next_top_n
        if not group["product_vt_symbol"].astype(str).eq(NI_PRODUCT).any():
            min_score = float(group["score"].min()) if not group.empty else 0.0
            add_row = {
                "strategy": PLUS_NI_STRATEGY,
                "score_type": "stage664_fixed_add_one_ni",
                "eval_date": str(eval_date),
                "product_vt_symbol": NI_PRODUCT,
                "score": min_score - 1e-6,
                "score_rank": next_rank,
                "top_n": next_top_n,
            }
            group = pd.concat([group, pd.DataFrame([add_row])], ignore_index=True, sort=False)
        groups.append(group)

    result = pd.concat(groups, ignore_index=True, sort=False)
    result.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    result.to_csv(target_path, index=False, encoding="utf-8-sig")


def _prepare_inputs() -> dict[str, Any]:
    base_symbols = _official_symbols()
    _write_plus_ni_universe(base_symbols)
    historical_source = Path(str(s513._c3_overrides(s513.START_DT)["ai_product_pool_eligibility_path"])).resolve()
    _write_plus_ni_eligibility(historical_source, HIST_ELIGIBILITY_PATH)
    _write_plus_ni_eligibility(s659.DEFAULT_AI_ELIGIBILITY_PATH.resolve(), LATEST_ELIGIBILITY_PATH)
    expanded_symbols = sorted(set(base_symbols) | {NI_PRODUCT})
    metadata = build_contract_metadata(supported_symbols=expanded_symbols)
    return {
        "base_symbols": base_symbols,
        "expanded_symbols": expanded_symbols,
        "historical_eligibility_source": str(historical_source),
        "latest_eligibility_source": str(s659.DEFAULT_AI_ELIGIBILITY_PATH.resolve()),
        "metadata": metadata,
    }


def _plus_ni_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    spec = s660._official_spec(metadata)
    overrides = {
        **spec.overrides,
        "product_universe_csv_path": str(UNIVERSE_PATH),
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(HIST_ELIGIBILITY_PATH),
        "ai_product_pool_strategy": PLUS_NI_STRATEGY,
    }
    capital = replace(
        spec.capital,
        label="20w Stage372 recovery sleeve + ni fixed candidate",
        note=(
            "Stage664 candidate: keep Stage372 official live logic unchanged, expand the frozen product universe "
            "and every AI eligibility snapshot by adding ni.SHFE."
        ),
    )
    return replace(spec, capital=capital, overrides=overrides, profile="stage372_recovery_sleeve_plus_ni")


def _run_window_with_positions(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
    analysis_start: pd.Timestamp,
    analysis_end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_start = s653.s517.START_DT
    original_end = s653.s517.END_DT
    try:
        s653.s517.START_DT = analysis_start.to_pydatetime()
        s653.s517.END_DT = analysis_end.to_pydatetime()
        daily, positions, usage, forced_events = s653._run_variant(replace(spec), metadata)
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end

    daily["account_capital"] = spec.capital.account_capital
    daily["c3_capital"] = spec.capital.c3_capital
    daily["profile"] = spec.profile
    positions["account_capital"] = spec.capital.account_capital
    positions["c3_capital"] = spec.capital.c3_capital
    c3_margin_daily, _product_margin = s513._position_margin(positions, metadata)
    combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
    combined["profile"] = spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
    return combined, positions, usage, forced_events


def _run_latest_ytd_plus_ni(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    ytd_spec = replace(
        spec,
        overrides={
            **spec.overrides,
            "ai_product_pool_eligibility_path": str(LATEST_ELIGIBILITY_PATH),
            "ai_product_pool_strategy": PLUS_NI_STRATEGY,
        },
    )
    daily, positions, _usage, forced_events = s659._run_variant_dynamic(
        ytd_spec,
        metadata,
        datetime.strptime("2026-01-01", "%Y-%m-%d"),
        datetime.strptime("2026-06-05", "%Y-%m-%d"),
        LATEST_ELIGIBILITY_PATH,
    )
    daily["account_capital"] = ytd_spec.capital.account_capital
    daily["c3_capital"] = ytd_spec.capital.c3_capital
    daily["profile"] = ytd_spec.profile
    positions["account_capital"] = ytd_spec.capital.account_capital
    positions["c3_capital"] = ytd_spec.capital.c3_capital
    c3_margin_daily, _product_margin = s513._position_margin(positions, metadata)
    combined = s650._combine_daily(daily, c3_margin_daily, ytd_spec.capital)
    combined["profile"] = ytd_spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
    return combined, forced_events


def _baseline_summary() -> pd.DataFrame:
    baseline = pd.read_csv(BASELINE_SUMMARY_PATH, encoding="utf-8-sig")
    baseline["baseline_source"] = "stage662_stage372_locked_20w"

    ytd = pd.read_csv(BASELINE_YTD_SUMMARY_PATH, encoding="utf-8-sig")
    ytd = ytd[ytd["variant"].astype(str).eq(OFFICIAL_LIVE_PROFILE_NAME)].copy()
    if not ytd.empty:
        row = ytd.iloc[0]
        ytd_row = {
            "window_name": "ytd_2026_latest_ai",
            "window_label": "2026年初至2026-06-05最新AI池",
            "window_group": "latest_ytd",
            "source_name": "stage659_stage372_latest_ai_ytd",
            "analysis_start": "2026-01-01",
            "analysis_end": "2026-06-05",
            "trading_days": 0,
            "start_equity_path": 200000.0,
            "end_equity_path": float(row["end_equity"]),
            "path_return_pct": float(row["total_return_pct"]),
            "rebased_end_equity": float(row["end_equity"]),
            "rebased_total_return_pct": float(row["total_return_pct"]),
            "rebased_cagr_pct": float(row["cagr_pct"]),
            "rebased_max_dd_pct": float(row["max_dd_pct"]),
            "rebased_sharpe": float(row["sharpe"]),
            "rebased_min_equity": float(row["min_equity"]),
            "max_broker10_margin_to_rebased_equity_pct": float(row["max_broker10_margin_to_equity_pct"]),
            "p95_broker10_margin_to_rebased_equity_pct": float(row["p95_broker10_margin_to_equity_pct"]),
            "days_over_100pct": int(row["days_over_100pct"]),
            "days_over_90pct": int(row["days_over_90pct"]),
            "total_slippage": float(row["total_slippage"]),
            "total_trade_count": float(row["total_trade_count"]),
            "nonzero_daily_win_rate_pct": float(row["nonzero_daily_win_rate_pct"]),
            "forced_margin_deleverage_count": int(row["forced_margin_deleverage_count"]),
            "forced_margin_deleverage_closed_volume": float(row["forced_margin_deleverage_closed_volume"]),
            "dd40_pass": int(row["dd40_pass"]),
            "broker10_100_pass": int(row["broker10_100_pass"]),
            "broker10_90_watch_pass": int(float(row["max_broker10_margin_to_equity_pct"]) < 90.0),
            "account_survival_pass": int(row["account_survival_pass"]),
            "deployable_pass": int(row["deployable_pass"]),
            "caveat": "Stage659当前官方影子盘；用于Stage664 YTD对比。",
            "baseline_source": "stage659_stage372_20260605",
        }
        baseline = pd.concat([baseline[~baseline["window_name"].eq("ytd_2026_latest_ai")], pd.DataFrame([ytd_row])])
    return baseline


def _baseline_cost() -> pd.DataFrame:
    baseline = pd.read_csv(BASELINE_COST_PATH, encoding="utf-8-sig")
    ytd = pd.read_csv(BASELINE_YTD_SUMMARY_PATH, encoding="utf-8-sig")
    ytd = ytd[ytd["variant"].astype(str).eq(OFFICIAL_LIVE_PROFILE_NAME)].copy()
    if not ytd.empty:
        row = ytd.iloc[0]
        ytd_row = {
            "window_name": "ytd_2026_latest_ai",
            "window_label": "2026年初至2026-06-05最新AI池",
            "cost_multiplier": 1.0,
            "end_equity": float(row["end_equity"]),
            "total_return_pct": float(row["total_return_pct"]),
            "max_dd_pct": float(row["max_dd_pct"]),
            "sharpe": float(row["sharpe"]),
            "max_broker10_margin_to_equity_pct": float(row["max_broker10_margin_to_equity_pct"]),
            "days_over_100pct": int(row["days_over_100pct"]),
            "account_survival_pass": int(row["account_survival_pass"]),
            "deployable_pass": int(row["deployable_pass"]),
        }
        baseline = pd.concat([baseline[~baseline["window_name"].eq("ytd_2026_latest_ai")], pd.DataFrame([ytd_row])])
    return baseline


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    baseline = _baseline_summary().set_index("window_name")
    candidate = summary.set_index("window_name")
    rows: list[dict[str, Any]] = []
    for name in candidate.index:
        if name not in baseline.index:
            continue
        brow = baseline.loc[name]
        crow = candidate.loc[name]
        rows.append(
            {
                "window_name": name,
                "window_label": crow["window_label"],
                "baseline_return_pct": float(brow["rebased_total_return_pct"]),
                "candidate_return_pct": float(crow["rebased_total_return_pct"]),
                "delta_return_pct": float(crow["rebased_total_return_pct"] - brow["rebased_total_return_pct"]),
                "baseline_max_dd_pct": float(brow["rebased_max_dd_pct"]),
                "candidate_max_dd_pct": float(crow["rebased_max_dd_pct"]),
                "delta_max_dd_pct": float(crow["rebased_max_dd_pct"] - brow["rebased_max_dd_pct"]),
                "baseline_sharpe": float(brow["rebased_sharpe"]),
                "candidate_sharpe": float(crow["rebased_sharpe"]),
                "delta_sharpe": float(crow["rebased_sharpe"] - brow["rebased_sharpe"]),
                "baseline_trades": float(brow["total_trade_count"]),
                "candidate_trades": float(crow["total_trade_count"]),
                "delta_trades": float(crow["total_trade_count"] - brow["total_trade_count"]),
                "baseline_slippage": float(brow["total_slippage"]),
                "candidate_slippage": float(crow["total_slippage"]),
                "delta_slippage": float(crow["total_slippage"] - brow["total_slippage"]),
                "baseline_margin_peak_pct": float(brow["max_broker10_margin_to_rebased_equity_pct"]),
                "candidate_margin_peak_pct": float(crow["max_broker10_margin_to_rebased_equity_pct"]),
                "delta_margin_peak_pct": float(
                    crow["max_broker10_margin_to_rebased_equity_pct"]
                    - brow["max_broker10_margin_to_rebased_equity_pct"]
                ),
            }
        )

    baseline_cost = _baseline_cost()
    baseline_cost = baseline_cost[baseline_cost["cost_multiplier"].eq(2.0)].set_index("window_name")
    candidate_cost = cost[cost["cost_multiplier"].eq(2.0)].set_index("window_name")
    for row in rows:
        name = str(row["window_name"])
        if name in baseline_cost.index and name in candidate_cost.index:
            row["baseline_2x_max_dd_pct"] = float(baseline_cost.loc[name, "max_dd_pct"])
            row["candidate_2x_max_dd_pct"] = float(candidate_cost.loc[name, "max_dd_pct"])
            row["delta_2x_max_dd_pct"] = float(
                candidate_cost.loc[name, "max_dd_pct"] - baseline_cost.loc[name, "max_dd_pct"]
            )
    return pd.DataFrame(rows)


def _ni_activity(positions: pd.DataFrame, usage: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    pos = positions.copy()
    if not pos.empty:
        pos["date"] = pd.to_datetime(pos["date"], errors="coerce").dt.normalize()
        pos = pos[pos["date"].ge(pd.Timestamp("2020-01-01"))].copy()
        pos = pos[pos["vt_symbol"].astype(str).str.startswith("ni")].copy()
        rows.append(
            {
                "scope": "full_positions",
                "ni_net_pnl": float(pd.to_numeric(pos.get("net_pnl", 0.0), errors="coerce").fillna(0.0).sum()),
                "ni_slippage": float(pd.to_numeric(pos.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
                "ni_trade_count": float(pd.to_numeric(pos.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
                "ni_active_days": int(pos[pd.to_numeric(pos.get("end_pos", 0.0), errors="coerce").fillna(0.0).abs().gt(0)]["date"].nunique()),
                "ni_first_active_date": (
                    pos[pd.to_numeric(pos.get("end_pos", 0.0), errors="coerce").fillna(0.0).abs().gt(0)]["date"].min().date().isoformat()
                    if not pos.empty
                    and not pos[pd.to_numeric(pos.get("end_pos", 0.0), errors="coerce").fillna(0.0).abs().gt(0)].empty
                    else ""
                ),
                "ni_last_active_date": (
                    pos[pd.to_numeric(pos.get("end_pos", 0.0), errors="coerce").fillna(0.0).abs().gt(0)]["date"].max().date().isoformat()
                    if not pos.empty
                    and not pos[pd.to_numeric(pos.get("end_pos", 0.0), errors="coerce").fillna(0.0).abs().gt(0)].empty
                    else ""
                ),
            }
        )
    if not usage.empty:
        ni_usage = usage[usage["vt_symbol"].astype(str).str.startswith("ni")].copy()
        rows.append(
            {
                "scope": "full_trade_usage",
                "ni_net_pnl": 0.0,
                "ni_slippage": 0.0,
                "ni_trade_count": float(pd.to_numeric(ni_usage.get("order_volume", 0.0), errors="coerce").fillna(0.0).sum()),
                "ni_active_days": int(pd.to_datetime(ni_usage.get("fill_date"), errors="coerce").dt.normalize().nunique()) if not ni_usage.empty else 0,
                "ni_first_active_date": str(ni_usage["fill_date"].min()) if not ni_usage.empty else "",
                "ni_last_active_date": str(ni_usage["fill_date"].max()) if not ni_usage.empty else "",
            }
        )
    return pd.DataFrame(rows)


def _check_rows(summary: pd.DataFrame, cost: pd.DataFrame, comparison: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    checks = s661._check_rows(summary, cost, comparison, rolling)
    rows = checks.to_dict("records")
    full_cmp = comparison[comparison["window_name"].eq("full_2020_20260430")]
    if not full_cmp.empty:
        row = full_cmp.iloc[0]
        rows.append(
            {
                "check_name": "full_return_improves_vs_stage372",
                "status": "pass" if float(row["delta_return_pct"]) > 0 else "fail",
                "value": float(row["delta_return_pct"]),
                "threshold": "> 0",
                "comment": "扩池至少应提升全周期收益，否则没有接入必要。",
            }
        )
        rows.append(
            {
                "check_name": "full_sharpe_not_worse_vs_stage372",
                "status": "pass" if float(row["delta_sharpe"]) >= -0.03 else "fail",
                "value": float(row["delta_sharpe"]),
                "threshold": ">= -0.03",
                "comment": "扩池不应明显牺牲风险收益比。",
            }
        )
    since_2022 = comparison[comparison["window_name"].eq("since_2022")]
    if not since_2022.empty:
        row = since_2022.iloc[0]
        rows.append(
            {
                "check_name": "since_2022_not_single_window_only",
                "status": "watch" if float(row["delta_return_pct"]) > 0 and not full_cmp.empty and float(full_cmp.iloc[0]["delta_return_pct"]) <= 0 else "pass",
                "value": float(row["delta_return_pct"]),
                "threshold": "not only since_2022",
                "comment": "防止只因2022镍行情好而扩池。",
            }
        )
    return pd.DataFrame(rows)


def _plot_report(summary: pd.DataFrame, curves: pd.DataFrame, comparison: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), dpi=160)
    ax_nav, ax_dd, ax_cmp, ax_margin = axes.flatten()
    full = curves[curves["window_name"].eq("full_2020_20260430")].sort_values("date")
    ax_nav.plot(pd.to_datetime(full["date"]), full["rebased_nav"], color="#1f77b4", linewidth=1.2)
    ax_nav.set_title("Stage372 + ni full NAV")
    ax_nav.grid(alpha=0.25)

    ax_dd.fill_between(pd.to_datetime(full["date"]), full["drawdown_pct"].astype(float), 0.0, color="#d62728", alpha=0.35)
    ax_dd.axhline(-40.0, color="#111111", linestyle="--", linewidth=0.8)
    ax_dd.set_title("Stage372 + ni drawdown")
    ax_dd.grid(alpha=0.25)

    view = comparison[comparison["window_group"].isin(["historical_full", "start_year", "market_phase"])].copy()
    if "window_group" not in view.columns:
        view = comparison.copy()
    ax_cmp.bar(view["window_name"], view["delta_return_pct"].astype(float), color="#2ca02c")
    ax_cmp.axhline(0.0, color="#333333", linewidth=0.8)
    ax_cmp.set_title("Return delta vs Stage372")
    ax_cmp.tick_params(axis="x", rotation=35)
    ax_cmp.grid(axis="y", alpha=0.25)

    ax_margin.plot(pd.to_datetime(full["date"]), full["broker10_margin_to_rebased_equity_pct"], color="#ff7f0e", linewidth=1.0)
    ax_margin.axhline(90.0, color="#d62728", linestyle="--", linewidth=0.8)
    ax_margin.axhline(100.0, color="#8c0000", linestyle="--", linewidth=0.8)
    ax_margin.set_title("Broker10 margin / equity")
    ax_margin.grid(alpha=0.25)

    fig.suptitle("Stage664 Stage372 + ni fixed add-one pool audit", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    comparison: pd.DataFrame,
    checks: pd.DataFrame,
    ni_activity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage664 Stage372 + ni 扩池多周期审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        "- A：当前 Stage372/20万正式版。",
        "- C：Stage372/20万逻辑不变，只把 `ni.SHFE` 加入产品宇宙和每个月 AI eligibility。",
        "- 本阶段不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 决策检查",
        "",
        _md_table(checks),
        "",
        "## C 多周期结果",
        "",
        _md_table(
            summary[
                [
                    "window_name",
                    "window_label",
                    "analysis_start",
                    "analysis_end",
                    "rebased_end_equity",
                    "rebased_total_return_pct",
                    "rebased_cagr_pct",
                    "rebased_max_dd_pct",
                    "rebased_sharpe",
                    "max_broker10_margin_to_rebased_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "deployable_pass",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## A/C 对比",
        "",
        _md_table(comparison, max_rows=80),
        "",
        "## ni 活跃度",
        "",
        _md_table(ni_activity, max_rows=20),
        "",
        "## 成本压力",
        "",
        _md_table(cost, max_rows=120),
        "",
        "## 滚动窗口",
        "",
        _md_table(rolling),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 硬失败项：`{', '.join(decision['hard_fail_checks']) or '无'}`。",
        f"- 观察项：`{', '.join(decision['watch_checks']) or '无'}`。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    prepared = _prepare_inputs()
    metadata = prepared["metadata"]
    spec = _plus_ni_spec(metadata)

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    cost_rows: list[dict[str, Any]] = []
    annual_source_daily: pd.DataFrame | None = None
    full_positions: pd.DataFrame = pd.DataFrame()
    full_usage: pd.DataFrame = pd.DataFrame()

    for window_name, window_label, group, start, end in s660.WINDOWS:
        analysis_start = pd.Timestamp(start)
        analysis_end = pd.Timestamp(end) if end else pd.Timestamp("2026-04-30")
        print(f"[stage664] running {window_name}: {analysis_start.date()} -> {analysis_end.date()}", flush=True)
        frame, positions, usage, forced_events = _run_window_with_positions(
            spec=spec,
            metadata=metadata,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
        )
        if window_name == "full_2020_20260430":
            annual_source_daily = frame.copy()
            full_positions = positions.copy()
            full_usage = usage.copy()
        row, curve, costs = s660._window_metrics(
            frame,
            window_name=window_name,
            window_label=window_label,
            group=group,
            source_name="stage372_plus_ni_independent_window",
            caveat="历史窗口独立重跑，20万 fresh capital；固定加入 ni.SHFE，不重训、不重排AI。",
            forced_events=forced_events,
        )
        summary_rows.append(row)
        curve_frames.append(curve)
        cost_rows.extend(costs)

    ytd_frame, ytd_forced = _run_latest_ytd_plus_ni(spec=spec, metadata=metadata)
    ytd_row, ytd_curve, ytd_costs = s660._window_metrics(
        ytd_frame,
        window_name="ytd_2026_latest_ai",
        window_label="2026年初至2026-06-05最新AI池 + ni",
        group="latest_ytd",
        source_name="stage372_plus_ni_latest_ai_ytd",
        caveat="最新 AI 池独立年初至今影子盘；固定加入 ni.SHFE。",
        forced_events=ytd_forced,
    )
    summary_rows.append(ytd_row)
    curve_frames.append(ytd_curve)
    cost_rows.extend(ytd_costs)

    summary = pd.DataFrame(summary_rows)
    summary.insert(0, "variant", "stage372_20w_recovery_sleeve_plus_ni")
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(cost_rows)
    cost.insert(0, "variant", "stage372_20w_recovery_sleeve_plus_ni")
    if annual_source_daily is None:
        raise RuntimeError("full window daily not generated")
    annual, monthly = s660._annual_monthly(annual_source_daily, "stage372_plus_ni_full_path")
    rolling = s661._rolling_metrics(curves[curves["window_name"].eq("full_2020_20260430")])
    comparison = _comparison(summary, cost)
    if not comparison.empty:
        groups = summary.set_index("window_name")["window_group"].to_dict()
        comparison["window_group"] = comparison["window_name"].map(groups)
    ni_activity = _ni_activity(full_positions, full_usage)
    checks = _check_rows(summary, cost, comparison, rolling)
    hard_fail_checks = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch_checks = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    full_cmp = comparison[comparison["window_name"].eq("full_2020_20260430")]
    decision_label = (
        "stage372_plus_ni_candidate_rejected"
        if hard_fail_checks
        else (
            "stage372_plus_ni_candidate_watch_only"
            if full_cmp.empty or float(full_cmp.iloc[0]["delta_return_pct"]) <= 0
            else "stage372_plus_ni_candidate_passes_first_gate"
        )
    )
    decision = {
        "stage": "Stage376",
        "script_stage": "Stage664",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "baseline": "A=Stage372 official live 20w recovery sleeve",
        "candidate": "C=Stage372 + ni.SHFE fixed add-one universe and AI eligibility",
        "decision": decision_label,
        "hard_fail_checks": hard_fail_checks,
        "watch_checks": watch_checks,
        "overfitting_reflection": (
            "Adding ni after identifying 2022 trend has overfitting risk; promotion requires broad full-period and "
            "multi-start improvement, not only since_2022."
        ),
        "continued_value_reflection": (
            "Worth running as a refutation test because ni has independent liquidity/trend rationale, but not worth "
            "promoting unless it improves Stage372 without worsening cost/drawdown path."
        ),
        "inputs": {
            "universe": str(UNIVERSE_PATH),
            "historical_eligibility": str(HIST_ELIGIBILITY_PATH),
            "latest_eligibility": str(LATEST_ELIGIBILITY_PATH),
            "historical_eligibility_source": prepared["historical_eligibility_source"],
            "latest_eligibility_source": prepared["latest_eligibility_source"],
            "base_symbols": prepared["base_symbols"],
            "expanded_symbols": prepared["expanded_symbols"],
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "curves": str(CURVES_PATH),
            "rolling": str(ROLLING_PATH),
            "comparison": str(COMPARISON_PATH),
            "ni_activity": str(NI_ACTIVITY_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }

    _plot_report(summary, curves, comparison)
    _write_report(summary, cost, rolling, comparison, checks, ni_activity, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    ni_activity.to_csv(NI_ACTIVITY_PATH, index=False, encoding="utf-8-sig")
    full_positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    full_usage.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
