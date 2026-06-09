from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage666_stage372_500k_risk005_ag_ab as s666
from qmt_roll_official_live_config import OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage667_stage372_500k_risk005_ni_ag_ab_v1"
OUTPUT_PREFIX = "qmt_roll_stage667_stage372_500k_risk005_ni_ag_ab"
LINE_ID = "futures_trend_drawdown30_preserve_return"

CAPITAL = 500_000.0
RISK_MULTIPLIER = 0.05
EXTRA_PRODUCTS = ("ni.SHFE", "ag.SHFE")
PLUS_COMBO_STRATEGY = "stage667_stage372_500k_risk005_plus_ni_ag_entry_filter"
SOURCE_LABEL = "stage667_500k_risk005_plus_ni_ag_fixed_add_two"
SCORE_TYPE = "stage667_fixed_add_two_ni_ag"
STAGE_NAME = "Stage379"
SCRIPT_STAGE = "Stage667"
REPORT_TITLE = "# Stage667 50万 risk0.05 同时加 ni/ag 多周期审计"
REJECT_DECISION = "plus_ni_ag_rejected"
WATCH_DECISION = "plus_ni_ag_watch_not_auto_promote"
PASS_DECISION = "plus_ni_ag_passes_first_gate"

VARIANT_BASE = "stage372_500k_risk005_no_ni_ag"
VARIANT_PLUS_COMBO = "stage372_500k_risk005_plus_ni_ag"

GENERATED_DIR = OUTPUT_DIR / "stage667_generated_inputs"
UNIVERSE_PLUS_COMBO_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_ni_ag_universe_{MODEL_TAG}.csv"
HIST_ELIGIBILITY_PLUS_COMBO_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_historical_plus_ni_ag_eligibility_{MODEL_TAG}.csv"
LATEST_ELIGIBILITY_PLUS_COMBO_PATH = GENERATED_DIR / f"{OUTPUT_PREFIX}_latest_plus_ni_ag_eligibility_{MODEL_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
EXTRA_ACTIVITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_extra_activity_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s666._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s666._md_table(frame, max_rows=max_rows)


def _product_code(product_vt_symbol: str) -> str:
    return product_vt_symbol.split(".", 1)[0]


def _write_plus_combo_universe(base_symbols: list[str]) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for symbol in sorted(set(base_symbols) | set(EXTRA_PRODUCTS)):
        product, exchange = symbol.split(".", 1)
        rows.append(
            {
                "product_vt_symbol": symbol,
                "product": product,
                "exchange": exchange,
                "eligible": 1,
                "source": SOURCE_LABEL,
            }
        )
    pd.DataFrame(rows).to_csv(UNIVERSE_PLUS_COMBO_PATH, index=False, encoding="utf-8-sig")


def _write_plus_combo_eligibility(source_path: Path, target_path: Path) -> None:
    source = pd.read_csv(source_path, encoding="utf-8-sig")
    required = {"strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"}
    missing = required - set(source.columns)
    if missing:
        raise ValueError(f"eligibility source missing columns {sorted(missing)}: {source_path}")

    source_strategy = str(source["strategy"].dropna().astype(str).iloc[0])
    frame = source[source["strategy"].astype(str).eq(source_strategy)].copy()
    frame["strategy"] = PLUS_COMBO_STRATEGY
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
                        "strategy": PLUS_COMBO_STRATEGY,
                        "score_type": SCORE_TYPE,
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
    target_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(target_path, index=False, encoding="utf-8-sig")


def _prepare_inputs() -> dict[str, Any]:
    base_symbols = s666._official_symbols()
    plus_symbols = sorted(set(base_symbols) | set(EXTRA_PRODUCTS))
    _write_plus_combo_universe(base_symbols)
    historical_source = Path(str(s666.s513._c3_overrides(s666.s513.START_DT)["ai_product_pool_eligibility_path"])).resolve()
    latest_source = s666.s659.DEFAULT_AI_ELIGIBILITY_PATH.resolve()
    _write_plus_combo_eligibility(historical_source, HIST_ELIGIBILITY_PLUS_COMBO_PATH)
    _write_plus_combo_eligibility(latest_source, LATEST_ELIGIBILITY_PLUS_COMBO_PATH)
    return {
        "base_symbols": base_symbols,
        "plus_symbols": plus_symbols,
        "historical_eligibility_source": str(historical_source),
        "latest_eligibility_source": str(latest_source),
        "base_metadata": s666.build_contract_metadata(supported_symbols=base_symbols),
        "plus_metadata": s666.build_contract_metadata(supported_symbols=plus_symbols),
    }


def _base_500k_spec(metadata: dict[str, Any]) -> s666.s653.ForcedVariant:
    official = s666.s660._official_spec(metadata)
    extra_label = "+".join(_product_code(symbol) for symbol in EXTRA_PRODUCTS)
    capital = replace(
        official.capital,
        variant=VARIANT_BASE,
        label=f"50w Stage372 recovery sleeve risk005 no-{extra_label}",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        risk_multiplier=RISK_MULTIPLIER,
        note=(
            f"{SCRIPT_STAGE} B: keep Stage372 official logic and product pool, set account/c3 capital to 500k "
            "and capital risk_multiplier to 0.05."
        ),
    )
    return replace(official, capital=capital, profile=VARIANT_BASE)


def _plus_combo_500k_spec(metadata: dict[str, Any]) -> s666.s653.ForcedVariant:
    official = s666.s660._official_spec(metadata)
    extra_label = "+".join(_product_code(symbol) for symbol in EXTRA_PRODUCTS)
    capital = replace(
        official.capital,
        variant=VARIANT_PLUS_COMBO,
        label=f"50w Stage372 recovery sleeve risk005 plus-{extra_label}",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        risk_multiplier=RISK_MULTIPLIER,
        note=(
            f"{SCRIPT_STAGE} C: 500k/risk005 plus fixed {', '.join(EXTRA_PRODUCTS)} "
            "in product universe and every AI eligibility snapshot."
        ),
    )
    overrides = {
        **official.overrides,
        "product_universe_csv_path": str(UNIVERSE_PLUS_COMBO_PATH),
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(HIST_ELIGIBILITY_PLUS_COMBO_PATH),
        "ai_product_pool_strategy": PLUS_COMBO_STRATEGY,
    }
    return replace(official, capital=capital, overrides=overrides, profile=VARIANT_PLUS_COMBO)


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["variant"].eq(VARIANT_BASE)].set_index("window_name")
    plus = summary[summary["variant"].eq(VARIANT_PLUS_COMBO)].set_index("window_name")
    rows: list[dict[str, Any]] = []
    for name in plus.index:
        if name not in base.index:
            continue
        brow = base.loc[name]
        crow = plus.loc[name]
        rows.append(
            {
                "window_name": name,
                "window_label": crow["window_label"],
                "window_group": crow["window_group"],
                "base_return_pct": float(brow["rebased_total_return_pct"]),
                "plus_combo_return_pct": float(crow["rebased_total_return_pct"]),
                "delta_return_pct": float(crow["rebased_total_return_pct"] - brow["rebased_total_return_pct"]),
                "base_max_dd_pct": float(brow["rebased_max_dd_pct"]),
                "plus_combo_max_dd_pct": float(crow["rebased_max_dd_pct"]),
                "delta_max_dd_pct": float(crow["rebased_max_dd_pct"] - brow["rebased_max_dd_pct"]),
                "base_sharpe": float(brow["rebased_sharpe"]),
                "plus_combo_sharpe": float(crow["rebased_sharpe"]),
                "delta_sharpe": float(crow["rebased_sharpe"] - brow["rebased_sharpe"]),
                "base_trades": float(brow["total_trade_count"]),
                "plus_combo_trades": float(crow["total_trade_count"]),
                "delta_trades": float(crow["total_trade_count"] - brow["total_trade_count"]),
                "base_slippage": float(brow["total_slippage"]),
                "plus_combo_slippage": float(crow["total_slippage"]),
                "delta_slippage": float(crow["total_slippage"] - brow["total_slippage"]),
                "base_margin_peak_pct": float(brow["max_broker10_margin_to_rebased_equity_pct"]),
                "plus_combo_margin_peak_pct": float(crow["max_broker10_margin_to_rebased_equity_pct"]),
                "delta_margin_peak_pct": float(
                    crow["max_broker10_margin_to_rebased_equity_pct"] - brow["max_broker10_margin_to_rebased_equity_pct"]
                ),
            }
        )
    base_cost = cost[(cost["variant"].eq(VARIANT_BASE)) & (cost["cost_multiplier"].eq(2.0))].set_index("window_name")
    plus_cost = cost[(cost["variant"].eq(VARIANT_PLUS_COMBO)) & (cost["cost_multiplier"].eq(2.0))].set_index("window_name")
    for row in rows:
        name = str(row["window_name"])
        if name in base_cost.index and name in plus_cost.index:
            row["base_2x_max_dd_pct"] = float(base_cost.loc[name, "max_dd_pct"])
            row["plus_combo_2x_max_dd_pct"] = float(plus_cost.loc[name, "max_dd_pct"])
            row["delta_2x_max_dd_pct"] = float(plus_cost.loc[name, "max_dd_pct"] - base_cost.loc[name, "max_dd_pct"])
    return pd.DataFrame(rows)


def _extra_activity(positions: pd.DataFrame, usage: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    codes = {_product_code(symbol) for symbol in EXTRA_PRODUCTS}
    pos = positions.copy()
    if not pos.empty:
        pos["date"] = pd.to_datetime(pos["date"], errors="coerce").dt.normalize()
        pos["product"] = pos["vt_symbol"].astype(str).str.split(".", n=1).str[0].str.extract(r"^([A-Za-z]+)", expand=False)
        pos = pos[pos["product"].isin(codes)].copy()
        for product, group in pos.groupby("product", sort=True):
            active = group[pd.to_numeric(group.get("end_pos", 0.0), errors="coerce").fillna(0.0).abs().gt(0)]
            rows.append(
                {
                    "scope": "full_positions",
                    "product": product,
                    "net_pnl": float(pd.to_numeric(group.get("net_pnl", 0.0), errors="coerce").fillna(0.0).sum()),
                    "slippage": float(pd.to_numeric(group.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
                    "trade_count": float(pd.to_numeric(group.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
                    "active_days": int(active["date"].nunique()),
                    "first_active_date": active["date"].min().date().isoformat() if not active.empty else "",
                    "last_active_date": active["date"].max().date().isoformat() if not active.empty else "",
                }
            )
        rows.append(
            {
                "scope": "full_positions",
                "product": "combined",
                "net_pnl": float(pd.to_numeric(pos.get("net_pnl", 0.0), errors="coerce").fillna(0.0).sum()),
                "slippage": float(pd.to_numeric(pos.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
                "trade_count": float(pd.to_numeric(pos.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
                "active_days": int(pos[pd.to_numeric(pos.get("end_pos", 0.0), errors="coerce").fillna(0.0).abs().gt(0)]["date"].nunique()),
                "first_active_date": "",
                "last_active_date": "",
            }
        )
    if not usage.empty:
        use = usage.copy()
        use["product"] = use["vt_symbol"].astype(str).str.split(".", n=1).str[0].str.extract(r"^([A-Za-z]+)", expand=False)
        use = use[use["product"].isin(codes)].copy()
        for product, group in use.groupby("product", sort=True):
            dates = pd.to_datetime(group.get("fill_date"), errors="coerce").dt.normalize()
            rows.append(
                {
                    "scope": "full_trade_usage",
                    "product": product,
                    "net_pnl": 0.0,
                    "slippage": 0.0,
                    "trade_count": float(pd.to_numeric(group.get("order_volume", 0.0), errors="coerce").fillna(0.0).sum()),
                    "active_days": int(dates.nunique()) if not group.empty else 0,
                    "first_active_date": dates.min().date().isoformat() if not group.empty and pd.notna(dates.min()) else "",
                    "last_active_date": dates.max().date().isoformat() if not group.empty and pd.notna(dates.max()) else "",
                }
            )
    return pd.DataFrame(rows)


def _checks(summary: pd.DataFrame, cost: pd.DataFrame, comparison: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    extra_label = "+".join(_product_code(symbol) for symbol in EXTRA_PRODUCTS)
    for variant in (VARIANT_BASE, VARIANT_PLUS_COMBO):
        full = summary[(summary["variant"].eq(variant)) & (summary["window_name"].eq("full_2020_20260430"))]
        cost2 = cost[(cost["variant"].eq(variant)) & (cost["window_name"].eq("full_2020_20260430")) & (cost["cost_multiplier"].eq(2.0))]
        if not full.empty:
            row = full.iloc[0]
            rows.extend(
                [
                    {
                        "variant": variant,
                        "check_name": "full_dd40",
                        "status": "pass" if float(row["rebased_max_dd_pct"]) >= -40.0 else "fail",
                        "value": float(row["rebased_max_dd_pct"]),
                        "threshold": ">= -40",
                        "comment": "全周期正常成本最大回撤。",
                    },
                    {
                        "variant": variant,
                        "check_name": "full_margin100",
                        "status": "pass" if int(row["days_over_100pct"]) == 0 else "fail",
                        "value": int(row["days_over_100pct"]),
                        "threshold": "0 days",
                        "comment": "broker10保证金不穿100%。",
                    },
                    {
                        "variant": variant,
                        "check_name": "full_return_positive",
                        "status": "pass" if float(row["rebased_total_return_pct"]) > 0 else "fail",
                        "value": float(row["rebased_total_return_pct"]),
                        "threshold": "> 0",
                        "comment": "低风险倍率不应把长期收益压成负。",
                    },
                ]
            )
        if not cost2.empty:
            row = cost2.iloc[0]
            rows.append(
                {
                    "variant": variant,
                    "check_name": "full_2x_cost_dd40",
                    "status": "pass" if float(row["max_dd_pct"]) >= -40.0 else "fail",
                    "value": float(row["max_dd_pct"]),
                    "threshold": ">= -40",
                    "comment": "全周期2x成本压力最大回撤。",
                }
            )
        roll = rolling[rolling["variant"].eq(variant)]
        if not roll.empty:
            rows.append(
                {
                    "variant": variant,
                    "check_name": "rolling_p05_return_min",
                    "status": "watch" if float(roll["p05_return_pct"].min()) < 0 else "pass",
                    "value": float(roll["p05_return_pct"].min()),
                    "threshold": ">= 0 preferred",
                    "comment": "短持有左尾体验。",
                }
            )
    full_cmp = comparison[comparison["window_name"].eq("full_2020_20260430")]
    if not full_cmp.empty:
        row = full_cmp.iloc[0]
        rows.append(
            {
                "variant": "plus_combo_vs_base",
                "check_name": "plus_combo_full_return_improves",
                "status": "pass" if float(row["delta_return_pct"]) > 0 else "fail",
                "value": float(row["delta_return_pct"]),
                "threshold": "> 0",
                "comment": f"同时固定加{extra_label}至少应提升50万/risk005全周期收益。",
            }
        )
        rows.append(
            {
                "variant": "plus_combo_vs_base",
                "check_name": "plus_combo_sharpe_not_worse",
                "status": "pass" if float(row["delta_sharpe"]) >= -0.03 else "fail",
                "value": float(row["delta_sharpe"]),
                "threshold": ">= -0.03",
                "comment": f"同时固定加{extra_label}不应明显伤害风险收益比。",
            }
        )
    return pd.DataFrame(rows)


def _plot(curves: pd.DataFrame, comparison: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), dpi=160)
    ax_nav, ax_dd, ax_delta, ax_margin = axes.flatten()
    full = curves[curves["window_name"].eq("full_2020_20260430")].copy()
    for variant, group in full.groupby("variant", sort=False):
        group = group.sort_values("date")
        ax_nav.plot(pd.to_datetime(group["date"]), group["rebased_nav"], linewidth=1.1, label=variant)
        ax_dd.plot(pd.to_datetime(group["date"]), group["drawdown_pct"], linewidth=1.0, label=variant)
        ax_margin.plot(pd.to_datetime(group["date"]), group["broker10_margin_to_rebased_equity_pct"], linewidth=1.0, label=variant)
    ax_nav.set_title("Full NAV")
    ax_dd.set_title("Full drawdown")
    ax_delta.set_title("Plus ni+ag return delta")
    ax_margin.set_title("Broker10 margin / equity")
    for ax in (ax_nav, ax_dd, ax_margin):
        ax.grid(alpha=0.25)
        ax.legend(fontsize=8)
    ax_dd.axhline(-40.0, color="#111111", linestyle="--", linewidth=0.8)
    ax_margin.axhline(90.0, color="#d62728", linestyle="--", linewidth=0.8)
    ax_margin.axhline(100.0, color="#8c0000", linestyle="--", linewidth=0.8)
    view = comparison[comparison["window_group"].isin(["historical_full", "start_year", "market_phase"])]
    ax_delta.bar(view["window_name"], view["delta_return_pct"].astype(float), color="#2ca02c")
    ax_delta.axhline(0.0, color="#333333", linewidth=0.8)
    ax_delta.tick_params(axis="x", rotation=35)
    ax_delta.grid(axis="y", alpha=0.25)
    extra_label = "+".join(_product_code(symbol) for symbol in EXTRA_PRODUCTS)
    fig.suptitle(f"{SCRIPT_STAGE} 500k risk005 base vs plus {extra_label}", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    rolling: pd.DataFrame,
    checks: pd.DataFrame,
    activity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    key_cols = [
        "variant",
        "window_name",
        "analysis_start",
        "analysis_end",
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "max_broker10_margin_to_rebased_equity_pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "deployable_pass",
    ]
    extra_label = "/".join(_product_code(symbol) for symbol in EXTRA_PRODUCTS)
    lines = [
        REPORT_TITLE,
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        f"- B：Stage372逻辑，50万，`risk_multiplier=0.05`，不加 `{extra_label}`。",
        f"- C：B基础上固定加入 `{', '.join(EXTRA_PRODUCTS)}` 到产品宇宙和每月AI eligibility。",
        "- 本阶段不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 检查",
        "",
        _md_table(checks, max_rows=80),
        "",
        "## 多周期结果",
        "",
        _md_table(summary[key_cols], max_rows=120),
        "",
        "## C vs B",
        "",
        _md_table(comparison, max_rows=80),
        "",
        "## 成本压力",
        "",
        _md_table(cost, max_rows=160),
        "",
        "## 滚动窗口",
        "",
        _md_table(rolling, max_rows=60),
        "",
        f"## {extra_label} 活跃度",
        "",
        _md_table(activity, max_rows=20),
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
    base_spec = _base_500k_spec(prepared["base_metadata"])
    plus_spec = _plus_combo_500k_spec(prepared["plus_metadata"])

    all_summary_rows: list[dict[str, Any]] = []
    all_curve_frames: list[pd.DataFrame] = []
    all_cost_rows: list[dict[str, Any]] = []
    annual_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []

    base_summary, base_curves, base_cost, _base_pos, _base_usage, base_annual, base_monthly = s666._run_variant_suite(
        spec=base_spec,
        metadata=prepared["base_metadata"],
        latest_ai_path=s666.s659.DEFAULT_AI_ELIGIBILITY_PATH.resolve(),
    )
    plus_summary, plus_curves, plus_cost, plus_positions, plus_usage, plus_annual, plus_monthly = s666._run_variant_suite(
        spec=plus_spec,
        metadata=prepared["plus_metadata"],
        latest_ai_path=LATEST_ELIGIBILITY_PLUS_COMBO_PATH,
    )

    all_summary_rows.extend(base_summary)
    all_summary_rows.extend(plus_summary)
    all_curve_frames.extend(base_curves)
    all_curve_frames.extend(plus_curves)
    all_cost_rows.extend(base_cost)
    all_cost_rows.extend(plus_cost)
    annual_frames.extend([base_annual, plus_annual])
    monthly_frames.extend([base_monthly, plus_monthly])

    summary = pd.DataFrame(all_summary_rows)
    curves = pd.concat(all_curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(all_cost_rows)
    comparison = _comparison(summary, cost)
    rolling = s666._rolling_metrics(curves[curves["window_name"].eq("full_2020_20260430")])
    annual = pd.concat([frame for frame in annual_frames if not frame.empty], ignore_index=True, sort=False)
    monthly = pd.concat([frame for frame in monthly_frames if not frame.empty], ignore_index=True, sort=False)
    activity = _extra_activity(plus_positions, plus_usage)
    checks = _checks(summary, cost, comparison, rolling)

    hard_fail_checks = checks[checks["status"].eq("fail")].apply(lambda row: f"{row['variant']}:{row['check_name']}", axis=1).tolist()
    watch_checks = checks[checks["status"].eq("watch")].apply(lambda row: f"{row['variant']}:{row['check_name']}", axis=1).tolist()
    full_cmp = comparison[comparison["window_name"].eq("full_2020_20260430")]
    decision_name = REJECT_DECISION
    if not full_cmp.empty and float(full_cmp.iloc[0]["delta_return_pct"]) > 0 and float(full_cmp.iloc[0]["delta_sharpe"]) >= -0.03:
        decision_name = WATCH_DECISION if watch_checks else PASS_DECISION
    decision = {
        "stage": STAGE_NAME,
        "script_stage": SCRIPT_STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_profile": OFFICIAL_LIVE_PROFILE_NAME,
        "arms": {
            "B": f"{VARIANT_BASE}: 500k, risk_multiplier=0.05, official Stage372 pool",
            "C": f"{VARIANT_PLUS_COMBO}: B plus fixed {', '.join(EXTRA_PRODUCTS)}",
        },
        "decision": decision_name,
        "hard_fail_checks": hard_fail_checks,
        "watch_checks": watch_checks,
        "overfitting_reflection": (
            f"The 500k/risk005 capital profile is structural, but manually adding {', '.join(EXTRA_PRODUCTS)} has "
            "selection-after-review risk. Promotion requires broad-window improvement, not additive single-product narratives."
        ),
        "continued_value_reflection": (
            "The combined sleeve is worth measuring because added products may interact through exposure timing. It is only worth "
            "continuing if it improves the base and does not damage start-year, cost, or margin path quality."
        ),
        "inputs": {
            "base_symbols": prepared["base_symbols"],
            "plus_symbols": prepared["plus_symbols"],
            "historical_eligibility_source": prepared["historical_eligibility_source"],
            "latest_eligibility_source": prepared["latest_eligibility_source"],
            "plus_combo_universe": str(UNIVERSE_PLUS_COMBO_PATH),
            "plus_combo_historical_eligibility": str(HIST_ELIGIBILITY_PLUS_COMBO_PATH),
            "plus_combo_latest_eligibility": str(LATEST_ELIGIBILITY_PLUS_COMBO_PATH),
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "rolling": str(ROLLING_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "curves": str(CURVES_PATH),
            "extra_activity": str(EXTRA_ACTIVITY_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }

    _plot(curves, comparison)
    _write_report(summary, cost, comparison, rolling, checks, activity, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    activity.to_csv(EXTRA_ACTIVITY_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
