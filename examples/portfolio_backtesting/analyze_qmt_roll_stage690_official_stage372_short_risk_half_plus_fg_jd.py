from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import math
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as s659
import analyze_qmt_roll_stage666_stage372_500k_risk005_ag_ab as s666
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage690_official_stage372_short_risk_half_plus_fg_jd_v1"
OUTPUT_PREFIX = "qmt_roll_stage690_official_stage372_short_risk_half_plus_fg_jd"

LINE_ID = "futures_trend_drawdown30_preserve_return"
BASE_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4"
SHORT_RISK_HALF_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_short_risk_half"
TARGET_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_short_risk_half_plus_fg_jd"
SHORT_RISK_MULTIPLIER = 0.5
EXTRA_PRODUCTS = ("FG.CZCE", "jd.DCE")
PLUS_STRATEGY = "stage690_official_stage372_short_risk_half_plus_fg_jd_entry_filter"
PLUS_SCORE_TYPE = "stage690_fixed_add_fg_jd"
GENERATED_DIR = OUTPUT_DIR / "stage690_generated_inputs"
UNIVERSE_PLUS_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_fg_jd_universe_{MODEL_TAG}.csv"
ELIGIBILITY_PLUS_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_fg_jd_eligibility_{MODEL_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
FORCED_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
FORCED_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_summary_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _official_spec(identity_map: str) -> s653.ForcedVariant:
    spec = s659._official_live_spec(identity_map)
    overrides = {
        **spec.overrides,
        "ai_product_pool_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
    }
    return replace(spec, overrides=overrides)


def _short_risk_half_spec(identity_map: str) -> s653.ForcedVariant:
    base = _official_spec(identity_map)
    capital = replace(
        base.capital,
        variant=SHORT_RISK_HALF_VARIANT,
        label="Stage402 official Stage372 20w recovery sleeve short risk half",
        note=(
            "Stage689: keep current official Stage372 20w recovery sleeve profile, "
            "but multiply short entry risk budget by 0.5 after official sizing."
        ),
    )
    return replace(base, capital=capital, profile="official_stage372_recovery_sleeve_short_risk_half")


def _short_risk_half_plus_fg_jd_spec(identity_map: str) -> s653.ForcedVariant:
    base = _short_risk_half_spec(identity_map)
    capital = replace(
        base.capital,
        variant=TARGET_VARIANT,
        label="Stage403 official Stage372 short risk half plus FG/jd",
        note=(
            "Stage690: keep Stage402 short risk half, then add FG.CZCE and jd.DCE to the product universe "
            "and every AI eligibility snapshot. FG.CZCE is already in the official universe, so jd.DCE is "
            "the effective new product if the base pool already contains FG.CZCE."
        ),
    )
    overrides = {
        **base.overrides,
        "product_universe_csv_path": str(UNIVERSE_PLUS_PATH),
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(ELIGIBILITY_PLUS_PATH),
        "ai_product_pool_strategy": PLUS_STRATEGY,
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_short_risk_half_plus_fg_jd")


def _write_plus_universe(base_symbols: list[str]) -> dict[str, Any]:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    base_set = set(base_symbols)
    plus_symbols = sorted(base_set | set(EXTRA_PRODUCTS))
    rows: list[dict[str, Any]] = []
    for symbol in plus_symbols:
        product, exchange = symbol.split(".", 1)
        rows.append(
            {
                "product_vt_symbol": symbol,
                "product": product,
                "exchange": exchange,
                "eligible": 1,
                "source": "stage690_short_risk_half_plus_fg_jd",
            }
        )
    pd.DataFrame(rows).to_csv(UNIVERSE_PLUS_PATH, index=False, encoding="utf-8-sig")
    return {
        "base_symbols": sorted(base_set),
        "plus_symbols": plus_symbols,
        "requested_extra_products": list(EXTRA_PRODUCTS),
        "already_in_base": sorted(base_set & set(EXTRA_PRODUCTS)),
        "effective_new_products": sorted(set(EXTRA_PRODUCTS) - base_set),
    }


def _write_plus_eligibility(source_path: Path) -> None:
    source = pd.read_csv(source_path, encoding="utf-8-sig")
    required = {"strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"}
    missing = required - set(source.columns)
    if missing:
        raise ValueError(f"eligibility source missing columns {sorted(missing)}: {source_path}")

    source_strategy = str(source["strategy"].dropna().astype(str).iloc[0])
    frame = source[source["strategy"].astype(str).eq(source_strategy)].copy()
    frame["strategy"] = PLUS_STRATEGY
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in ["score", "score_rank", "top_n"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    groups: list[pd.DataFrame] = []
    for eval_date, group in frame.groupby("eval_date", sort=True):
        group = group.copy()
        existing = set(group["product_vt_symbol"].astype(str))
        products_to_add = [symbol for symbol in EXTRA_PRODUCTS if symbol not in existing]
        if products_to_add:
            max_rank = int(group["score_rank"].max()) if not group.empty else 0
            max_top_n = int(group["top_n"].max()) if not group.empty else 0
            min_score = float(group["score"].min()) if not group.empty else 0.0
            group["top_n"] = max_top_n + len(products_to_add)
            add_rows = []
            for idx, symbol in enumerate(products_to_add, start=1):
                add_rows.append(
                    {
                        "strategy": PLUS_STRATEGY,
                        "score_type": PLUS_SCORE_TYPE,
                        "eval_date": str(eval_date),
                        "product_vt_symbol": symbol,
                        "score": min_score - 1e-6 * idx,
                        "score_rank": max_rank + idx,
                        "top_n": max_top_n + len(products_to_add),
                    }
                )
            group = pd.concat([group, pd.DataFrame(add_rows)], ignore_index=True, sort=False)
        groups.append(group)

    result = pd.concat(groups, ignore_index=True, sort=False)
    result.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    ELIGIBILITY_PLUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(ELIGIBILITY_PLUS_PATH, index=False, encoding="utf-8-sig")


def _prepare_inputs() -> dict[str, Any]:
    base_symbols = s666._official_symbols()
    universe = _write_plus_universe(base_symbols)
    _write_plus_eligibility(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)
    base_metadata = s666.build_contract_metadata(supported_symbols=universe["base_symbols"])
    plus_metadata = s666.build_contract_metadata(supported_symbols=universe["plus_symbols"])
    return {
        **universe,
        "base_metadata": base_metadata,
        "plus_metadata": plus_metadata,
        "base_product_count": len(universe["base_symbols"]),
        "plus_product_count": len(universe["plus_symbols"]),
        "universe_path": str(UNIVERSE_PLUS_PATH),
        "eligibility_path": str(ELIGIBILITY_PLUS_PATH),
    }


def _apply_short_risk_half(sizing: dict[str, Any], strategy: QmtRollPortfolioStrategy) -> dict[str, Any]:
    adjusted = dict(sizing)
    risk_amount_before = float(adjusted.get("risk_amount") or 0.0)
    risk_per_contract = float(adjusted.get("risk_per_contract") or 0.0)
    contracts_by_risk_before = int(adjusted.get("contracts_by_risk") or 0)
    selected_volume_before = int(adjusted.get("selected_volume") or 0)
    min_position_size = max(1, int(getattr(strategy, "min_position_size", 1) or 1))

    risk_amount_after = max(0.0, risk_amount_before * SHORT_RISK_MULTIPLIER)
    contracts_by_risk_after = (
        int(math.floor(risk_amount_after / risk_per_contract))
        if risk_per_contract > 0.0 and contracts_by_risk_before is not None
        else contracts_by_risk_before
    )
    contracts_by_risk_after = max(0, contracts_by_risk_after)
    if 0 < contracts_by_risk_after < min_position_size:
        contracts_by_risk_after = 0

    selected_volume_after = min(selected_volume_before, contracts_by_risk_after)
    if 0 < selected_volume_after < min_position_size:
        selected_volume_after = 0

    adjusted.update(
        {
            "risk_amount": risk_amount_after,
            "target_risk_amount_before_short_multiplier": risk_amount_before,
            "short_risk_multiplier": SHORT_RISK_MULTIPLIER,
            "short_risk_amount_after_multiplier": risk_amount_after,
            "contracts_by_risk_before_short_multiplier": contracts_by_risk_before,
            "contracts_by_risk": contracts_by_risk_after,
            "selected_volume_before_short_multiplier": selected_volume_before,
            "selected_volume": max(0, int(selected_volume_after)),
            "short_risk_half_volume_reduced": int(selected_volume_after < selected_volume_before),
        }
    )
    if adjusted.get("risk_ratio") is not None:
        adjusted["risk_ratio_before_short_multiplier"] = adjusted["risk_ratio"]
        adjusted["risk_ratio"] = float(adjusted["risk_ratio"]) * SHORT_RISK_MULTIPLIER
    if selected_volume_after <= 0 and selected_volume_before > 0:
        adjusted["short_risk_half_zeroed_by_one_lot_granularity"] = 1
    else:
        adjusted["short_risk_half_zeroed_by_one_lot_granularity"] = 0
    return adjusted


def _short_risk_half_sizing(original):
    def wrapped(
        self: QmtRollPortfolioStrategy,
        vt_symbol,
        direction,
        bar,
        history,
        signal_data,
        risk_mode_override=None,
        entry_context="flat_entry",
        apply_env_gate=True,
        active_positions_before=None,
        correlation_snapshot=None,
    ):
        sizing = original(
            self,
            vt_symbol,
            direction,
            bar,
            history,
            signal_data,
            risk_mode_override=risk_mode_override,
            entry_context=entry_context,
            apply_env_gate=apply_env_gate,
            active_positions_before=active_positions_before,
            correlation_snapshot=correlation_snapshot,
        )
        if direction != "short":
            return sizing
        return _apply_short_risk_half(sizing, self)

    return wrapped


def _run_spec(
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
    *,
    short_risk_half: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_sizing = QmtRollPortfolioStrategy._calculate_entry_sizing
    try:
        if short_risk_half:
            QmtRollPortfolioStrategy._calculate_entry_sizing = _short_risk_half_sizing(original_sizing)
        daily, positions, usage, forced_events = s653._run_variant(spec, metadata)
    finally:
        QmtRollPortfolioStrategy._calculate_entry_sizing = original_sizing

    positions["account_capital"] = spec.capital.account_capital
    positions["c3_capital"] = spec.capital.c3_capital
    c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
    combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
    combined["profile"] = spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
    return combined, positions, product_margin, usage, forced_events


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    pairs = [
        ("official_vs_short_half", BASE_VARIANT, SHORT_RISK_HALF_VARIANT),
        ("short_half_vs_plus_fg_jd", SHORT_RISK_HALF_VARIANT, TARGET_VARIANT),
        ("official_vs_plus_fg_jd", BASE_VARIANT, TARGET_VARIANT),
    ]
    by_variant = {variant: frame.iloc[0].to_dict() for variant, frame in summary.groupby("variant", sort=False)}
    cost_by_variant = {
        variant: frame.set_index("cost_multiplier") for variant, frame in cost.groupby("variant", sort=False)
    }
    for compare_name, reference_variant, candidate_variant in pairs:
        if reference_variant not in by_variant or candidate_variant not in by_variant:
            continue
        ref_row = by_variant[reference_variant]
        cand_row = by_variant[candidate_variant]
        ref_cost = cost_by_variant.get(reference_variant, pd.DataFrame())
        cand_cost = cost_by_variant.get(candidate_variant, pd.DataFrame())
        rows.extend(_comparison_rows(compare_name, ref_row, cand_row, ref_cost, cand_cost))
    return pd.DataFrame(rows)


def _comparison_rows(
    compare_name: str,
    ref_row: dict[str, Any],
    cand_row: dict[str, Any],
    ref_cost: pd.DataFrame,
    cand_cost: pd.DataFrame,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fields = [
        ("end_equity", "end_equity"),
        ("total_return_pct", "return_pct"),
        ("max_dd_pct", "max_dd_pct"),
        ("sharpe", "sharpe"),
        ("total_slippage", "slippage"),
        ("total_trade_count", "trade_count"),
        ("nonzero_daily_win_rate_pct", "win_rate_pct"),
        ("max_broker10_margin_to_equity_pct", "max_margin_pct"),
        ("p95_broker10_margin_to_equity_pct", "p95_margin_pct"),
        ("forced_margin_deleverage_count", "forced_count"),
        ("forced_margin_deleverage_closed_volume", "forced_volume"),
    ]
    for source, metric in fields:
        base_value = float(ref_row.get(source, 0.0) or 0.0)
        target_value = float(cand_row.get(source, 0.0) or 0.0)
        rows.append(
            {
                "compare_name": compare_name,
                "metric": metric,
                "reference_variant": ref_row.get("variant", ""),
                "candidate_variant": cand_row.get("variant", ""),
                "reference_value": base_value,
                "candidate_value": target_value,
                "delta": target_value - base_value,
            }
        )
    for multiplier in (2.0, 3.0):
        if multiplier in ref_cost.index and multiplier in cand_cost.index:
            base_dd = float(ref_cost.loc[multiplier, "max_dd_pct"])
            target_dd = float(cand_cost.loc[multiplier, "max_dd_pct"])
            rows.append(
                {
                    "compare_name": compare_name,
                    "metric": f"{multiplier}x_cost_max_dd_pct",
                    "reference_variant": ref_row.get("variant", ""),
                    "candidate_variant": cand_row.get("variant", ""),
                    "reference_value": base_dd,
                    "candidate_value": target_dd,
                    "delta": target_dd - base_dd,
                }
            )
            base_equity = float(ref_cost.loc[multiplier, "end_equity"])
            target_equity = float(cand_cost.loc[multiplier, "end_equity"])
            rows.append(
                {
                    "compare_name": compare_name,
                    "metric": f"{multiplier}x_cost_end_equity",
                    "reference_variant": ref_row.get("variant", ""),
                    "candidate_variant": cand_row.get("variant", ""),
                    "reference_value": base_equity,
                    "candidate_value": target_equity,
                    "delta": target_equity - base_equity,
                }
            )
    return rows


def _annual_monthly(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["account_equity"] = pd.to_numeric(data["account_equity"], errors="coerce").fillna(0.0)
    data["trade_count"] = pd.to_numeric(data.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    data["slippage"] = pd.to_numeric(data.get("slippage", 0.0), errors="coerce").fillna(0.0)

    def summarize(frame: pd.DataFrame, key: str, label: str) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for (variant, period), group in frame.groupby(["variant", key], sort=True):
            group = group.sort_values("date")
            equity = group["account_equity"].astype(float)
            peak = equity.cummax()
            dd = ((equity - peak) / peak.replace(0.0, pd.NA) * 100.0).min()
            start_equity = float(equity.iloc[0])
            end_equity = float(equity.iloc[-1])
            rows.append(
                {
                    "variant": variant,
                    label: period,
                    "period_start_equity": start_equity,
                    "period_end_equity": end_equity,
                    "period_pnl": float(end_equity - start_equity),
                    "period_return_pct": float((end_equity / start_equity - 1.0) * 100.0) if start_equity else 0.0,
                    "period_max_dd_pct": float(dd or 0.0),
                    "total_trade_count": float(group["trade_count"].sum()),
                    "total_slippage": float(group["slippage"].sum()),
                }
            )
        return pd.DataFrame(rows)

    data["year"] = data["date"].dt.year
    data["month"] = data["date"].dt.strftime("%Y-%m")
    return summarize(data, "year", "year"), summarize(data, "month", "month")


def _product_summary(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame()
    data = positions.copy()
    data["product"] = data["vt_symbol"].astype(str).str.extract(r"^([A-Za-z]+)", expand=False).str.lower()
    for column in ["net_pnl", "slippage", "trade_count", "end_pos"]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    active = data[data["end_pos"].abs().gt(0)].copy()
    rows: list[dict[str, Any]] = []
    for (variant, product), group in data.groupby(["variant", "product"], sort=True):
        active_group = active[(active["variant"].eq(variant)) & (active["product"].eq(product))]
        rows.append(
            {
                "variant": variant,
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


def _plot(daily: pd.DataFrame) -> None:
    if daily.empty:
        return
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["label"] = data["variant"].map(
        {
            BASE_VARIANT: "Official Stage372",
            SHORT_RISK_HALF_VARIANT: "Official short risk x0.5",
            TARGET_VARIANT: "Short risk x0.5 + FG/jd",
        }
    ).fillna(data["variant"])
    colors = {
        "Official Stage372": "#f97316",
        "Official short risk x0.5": "#2563eb",
        "Short risk x0.5 + FG/jd": "#16a34a",
    }
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    for label, group in data.sort_values("date").groupby("label"):
        equity = group["account_equity"].astype(float)
        drawdown = (equity / equity.cummax() - 1.0) * 100.0
        axes[0].plot(group["date"], equity, label=label, linewidth=1.25, color=colors.get(label))
        axes[1].plot(group["date"], drawdown, label=label, linewidth=1.05, color=colors.get(label))
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=label, linewidth=1.05, color=colors.get(label))
    axes[0].axhline(200_000, color="#94a3b8", linestyle="--", linewidth=0.8)
    axes[0].set_title("Stage403 official Stage372 short-risk-half plus FG/jd")
    axes[0].set_ylabel("Equity")
    axes[1].axhline(-30, color="#f59e0b", linestyle="--", linewidth=0.8, alpha=0.8)
    axes[1].axhline(-40, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.8)
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("DD %")
    axes[2].axhline(90, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.55)
    axes[2].axhline(100, color="#991b1b", linestyle="--", linewidth=0.8, alpha=0.55)
    axes[2].set_title("Broker10 margin / equity")
    axes[2].set_ylabel("Margin %")
    for ax in axes:
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    annual: pd.DataFrame,
    product: pd.DataFrame,
    forced_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage690 Official Stage372 Short Risk Half Plus FG/jd",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 基准：当前正式版 `official_live_stage372_20w_recovery_sleeve`。",
        "- B 分支：保留空头开仓路径，但把空头开仓 sizing 的 `risk_amount` 乘以 `0.5` 后重新限制手数。",
        "- C 分支：在 B 分支基础上把 `FG.CZCE` 与 `jd.DCE` 写入品种池和 AI eligibility；`FG.CZCE` 已在正式池中时，实际新增为 `jd.DCE`。",
        "- 其他正式配置、AI池、20万资金、force95->80、recovery sleeve、product cap25、maxpos4 均保持不变。",
        "- 不连接 CTP，不调用下单。",
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Cost Stress",
        "",
        cost.to_markdown(index=False),
        "",
        "## Comparison",
        "",
        comparison.to_markdown(index=False),
        "",
        "## Annual",
        "",
        annual.to_markdown(index=False),
        "",
        "## Forced Deleverage",
        "",
        forced_summary.to_markdown(index=False),
        "",
        "## Product",
        "",
        product.to_markdown(index=False),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- main conclusion: {decision['main_conclusion']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    inputs = _prepare_inputs()
    base_metadata = inputs["base_metadata"]
    plus_metadata = inputs["plus_metadata"]
    base_identity_map = s653.s519._product_identity_cluster_map(base_metadata)
    plus_identity_map = s653.s519._product_identity_cluster_map(plus_metadata)
    specs = [
        (_official_spec(base_identity_map), base_metadata, False),
        (_short_risk_half_spec(base_identity_map), base_metadata, True),
        (_short_risk_half_plus_fg_jd_spec(plus_identity_map), plus_metadata, True),
    ]

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    product_margin_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    forced_event_frames: list[pd.DataFrame] = []

    spec_objects: list[s653.ForcedVariant] = [item[0] for item in specs]
    for spec, metadata, apply_short_half in specs:
        print(f"[stage690] running {spec.capital.variant}", flush=True)
        daily, positions, product_margin, usage, forced_events = _run_spec(
            spec,
            metadata,
            short_risk_half=apply_short_half,
        )
        daily_frames.append(daily)
        position_frames.append(positions)
        product_margin_frames.append(product_margin)
        if not usage.empty:
            usage_frames.append(usage)
        if not forced_events.empty:
            forced_event_frames.append(forced_events)

    combo_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False)
    product_margin_all = pd.concat(product_margin_frames, ignore_index=True, sort=False)
    usage_all = pd.concat(usage_frames, ignore_index=True, sort=False) if usage_frames else pd.DataFrame()
    forced_events_all = (
        pd.concat(forced_event_frames, ignore_index=True, sort=False) if forced_event_frames else pd.DataFrame()
    )
    forced_summary = s653._forced_summary(spec_objects, forced_events_all)

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = next(item[0] for item in specs if item[0].capital.variant == variant)
        for cost_multiplier in s653.COST_MULTIPLIERS:
            row = s653._metrics_with_profile(frame, spec, cost_multiplier)
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    official_return = float(summary.loc[summary["variant"].eq(BASE_VARIANT), "total_return_pct"].iloc[0])
    for frame in (summary, cost):
        frame["return_retention_vs_official_pct"] = (
            pd.to_numeric(frame["total_return_pct"], errors="coerce").fillna(0.0)
            / official_return
            * 100.0
        ) if official_return else 0.0
    comparison = _comparison(summary, cost)
    annual, monthly = _annual_monthly(combo_daily)
    product = _product_summary(positions_all)
    _plot(combo_daily)

    decision = {
        "stage": "Stage403",
        "script_stage": "Stage690",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "baseline": BASE_VARIANT,
        "short_risk_half": SHORT_RISK_HALF_VARIANT,
        "target": TARGET_VARIANT,
        "summary": summary.to_dict("records"),
        "cost": cost.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "forced_summary": forced_summary.to_dict("records"),
        "decision": "official_stage372_short_risk_half_plus_fg_jd_pending_review",
        "main_conclusion": "review_full_path_metrics_before_promotion",
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "short_entry_enabled": True,
            "short_risk_multiplier": SHORT_RISK_MULTIPLIER,
            "requested_extra_products": list(EXTRA_PRODUCTS),
            "already_in_base": inputs["already_in_base"],
            "effective_new_products": inputs["effective_new_products"],
            "base_product_count": inputs["base_product_count"],
            "plus_product_count": inputs["plus_product_count"],
            "can_open_short_signal": "official_default",
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "daily": str(DAILY_PATH),
            "positions": str(POSITIONS_PATH),
            "product": str(PRODUCT_PATH),
            "product_margin": str(PRODUCT_MARGIN_PATH),
            "trade_usage": str(TRADE_USAGE_PATH),
            "forced_events": str(FORCED_EVENTS_PATH),
            "forced_summary": str(FORCED_SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
            "chart": str(CHART_PATH),
        },
    }

    combo_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_margin_all.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    usage_all.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    forced_events_all.to_csv(FORCED_EVENTS_PATH, index=False, encoding="utf-8-sig")
    forced_summary.to_csv(FORCED_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, cost, comparison, annual, product, forced_summary, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
