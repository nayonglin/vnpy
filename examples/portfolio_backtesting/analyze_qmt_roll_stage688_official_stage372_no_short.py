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
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage688_official_stage372_no_short_v1"
OUTPUT_PREFIX = "qmt_roll_stage688_official_stage372_no_short"

LINE_ID = "futures_trend_drawdown30_preserve_return"
BASE_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4"
TARGET_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_no_short"

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


def _reject_all_short_signals(self: QmtRollPortfolioStrategy, signal: str) -> bool:
    return False


def _official_spec(identity_map: str) -> s653.ForcedVariant:
    spec = s659._official_live_spec(identity_map)
    overrides = {
        **spec.overrides,
        "ai_product_pool_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
    }
    return replace(spec, overrides=overrides)


def _no_short_spec(identity_map: str) -> s653.ForcedVariant:
    base = _official_spec(identity_map)
    capital = replace(
        base.capital,
        variant=TARGET_VARIANT,
        label="Stage401 official Stage372 20w recovery sleeve no short",
        note=(
            "Stage688: keep current official Stage372 20w recovery sleeve profile, "
            "but disable all fresh short entries and short rollover/recovery paths."
        ),
    )
    overrides = {
        **base.overrides,
        "short_entry_enabled": False,
        "streak_entry_structure_recovery_signals": "long_case1a",
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_recovery_sleeve_no_short")


def _run_spec(
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
    *,
    no_short: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_can_open_short = QmtRollPortfolioStrategy._can_open_short_signal
    try:
        if no_short:
            QmtRollPortfolioStrategy._can_open_short_signal = _reject_all_short_signals
        daily, positions, usage, forced_events = s653._run_variant(spec, metadata)
    finally:
        QmtRollPortfolioStrategy._can_open_short_signal = original_can_open_short

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
    base = summary[summary["variant"].eq(BASE_VARIANT)]
    target = summary[summary["variant"].eq(TARGET_VARIANT)]
    if base.empty or target.empty:
        return pd.DataFrame()
    base_row = base.iloc[0].to_dict()
    target_row = target.iloc[0].to_dict()
    base_cost = cost[cost["variant"].eq(BASE_VARIANT)].set_index("cost_multiplier")
    target_cost = cost[cost["variant"].eq(TARGET_VARIANT)].set_index("cost_multiplier")
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
        base_value = float(base_row.get(source, 0.0) or 0.0)
        target_value = float(target_row.get(source, 0.0) or 0.0)
        rows.append({"metric": metric, "official": base_value, "no_short": target_value, "delta": target_value - base_value})
    for multiplier in (2.0, 3.0):
        if multiplier in base_cost.index and multiplier in target_cost.index:
            base_dd = float(base_cost.loc[multiplier, "max_dd_pct"])
            target_dd = float(target_cost.loc[multiplier, "max_dd_pct"])
            rows.append({"metric": f"{multiplier}x_cost_max_dd_pct", "official": base_dd, "no_short": target_dd, "delta": target_dd - base_dd})
            base_equity = float(base_cost.loc[multiplier, "end_equity"])
            target_equity = float(target_cost.loc[multiplier, "end_equity"])
            rows.append({"metric": f"{multiplier}x_cost_end_equity", "official": base_equity, "no_short": target_equity, "delta": target_equity - base_equity})
    return pd.DataFrame(rows)


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
            TARGET_VARIANT: "Official no short",
        }
    ).fillna(data["variant"])
    colors = {"Official Stage372": "#f97316", "Official no short": "#2563eb"}
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    for label, group in data.sort_values("date").groupby("label"):
        equity = group["account_equity"].astype(float)
        drawdown = (equity / equity.cummax() - 1.0) * 100.0
        axes[0].plot(group["date"], equity, label=label, linewidth=1.25, color=colors.get(label))
        axes[1].plot(group["date"], drawdown, label=label, linewidth=1.05, color=colors.get(label))
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=label, linewidth=1.05, color=colors.get(label))
    axes[0].axhline(200_000, color="#94a3b8", linestyle="--", linewidth=0.8)
    axes[0].set_title("Stage401 official Stage372 no-short ablation")
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
        "# Stage688 Official Stage372 No Short",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 基准：当前正式版 `official_live_stage372_20w_recovery_sleeve`。",
        "- 新分支：禁用全部 fresh short entry、short reverse entry、short rollover/recovery reopen。",
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
    metadata = s513._metadata()
    identity_map = s653.s519._product_identity_cluster_map(metadata)
    specs = [_official_spec(identity_map), _no_short_spec(identity_map)]

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    product_margin_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    forced_event_frames: list[pd.DataFrame] = []

    for spec in specs:
        is_target = spec.capital.variant == TARGET_VARIANT
        print(f"[stage688] running {spec.capital.variant}", flush=True)
        daily, positions, product_margin, usage, forced_events = _run_spec(
            spec,
            metadata,
            no_short=is_target,
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
    forced_summary = s653._forced_summary(specs, forced_events_all)

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = next(item for item in specs if item.capital.variant == variant)
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
        "stage": "Stage401",
        "script_stage": "Stage688",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "baseline": BASE_VARIANT,
        "target": TARGET_VARIANT,
        "summary": summary.to_dict("records"),
        "cost": cost.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "forced_summary": forced_summary.to_dict("records"),
        "decision": "official_stage372_no_short_pending_review",
        "main_conclusion": "review_full_path_metrics_before_promotion",
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "short_entry_enabled": False,
            "can_open_short_signal": "always_false",
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
