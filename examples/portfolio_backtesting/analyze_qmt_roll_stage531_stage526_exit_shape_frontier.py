from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage516_margin_aware_sizing_frontier as s516  # noqa: E402
import analyze_qmt_roll_stage517_portfolio_margin_deleverage_frontier as s517  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402


MODEL_TAG = "stage531_stage526_exit_shape_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage531_stage526_exit_shape_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
MARGIN_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_daily_{MODEL_TAG}.csv"
PRODUCT_ATTR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_window_product_attr_{MODEL_TAG}.csv"
COST_FAILURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_failure_windows_{MODEL_TAG}.csv"
EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_events_{MODEL_TAG}.csv"
PRODUCT_EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_events_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

CONTROL_VARIANT = "r080_pc25_maxpos4_control"
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    risk_multiplier: float
    overrides: dict[str, Any]
    note: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _variants(identity_map: str) -> tuple[VariantSpec, ...]:
    pc25_maxpos4 = {**s519._product_cap_overrides(0.25, identity_map), "max_concurrent_positions": 4}
    return (
        VariantSpec(
            CONTROL_VARIANT,
            "control: risk080 pc25 + maxpos4",
            0.80,
            dict(pc25_maxpos4),
            "Stage526主研究候选复刻；ATR中位止损、prev2day、MA趋势止损沿用当前默认。",
        ),
        VariantSpec(
            "r080_pc25_maxpos4_no_atr_mid",
            "ablation: disable ATR 2x mid stop",
            0.80,
            {**pc25_maxpos4, "atr_2x_mid_stop_enabled": False},
            "只关闭已有ATR 2倍大波动中位止损，检验它是否在候选中真正贡献风险控制。",
        ),
        VariantSpec(
            "r080_pc25_maxpos4_align_break",
            "C: alignment-break exit on",
            0.80,
            {**pc25_maxpos4, "exit_on_alignment_break": True},
            "开启已有趋势排列破坏退出；结构假设是坏窗口中趋势结构破坏应更快离场。",
        ),
        VariantSpec(
            "r080_pc25_maxpos4_profit_giveback",
            "C: profit giveback stop on",
            0.80,
            {
                **pc25_maxpos4,
                "enable_profit_giveback_stop": True,
                "profit_giveback_trigger_pct": 0.08,
                "profit_giveback_retain_ratio": 0.70,
                "profit_giveback_min_lock_pct": 0.03,
            },
            "开启已有盈利回吐保护，使用策略默认粗档；检验能否减少长水下而不破坏大趋势。",
        ),
    )


def _summary_and_cost(combo_daily: pd.DataFrame, specs: tuple[VariantSpec, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec_map = {spec.variant: spec for spec in specs}
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = spec_map[variant]
        for cost_multiplier in COST_MULTIPLIERS:
            equity = s516._stressed_equity(frame, cost_multiplier)
            row = s516._metrics_from_equity(
                equity,
                frame,
                variant=variant,
                label=spec.label,
                cost_multiplier=cost_multiplier,
            )
            row.update({"risk_multiplier": spec.risk_multiplier, "note": spec.note})
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    return pd.DataFrame(summary_rows), pd.DataFrame(cost_rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = equity.astype(float)
    return (values / values.cummax() - 1.0) * 100.0


def _max_dd_window(equity: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    dd = _drawdown_pct(equity)
    trough = pd.Timestamp(dd.idxmin())
    peak = pd.Timestamp(equity.loc[:trough].idxmax())
    return peak.normalize(), trough.normalize(), float(dd.loc[trough])


def _cost_failure_windows(combo_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date").copy()
        dates = pd.to_datetime(ordered["date"]).reset_index(drop=True)
        for cost_multiplier in COST_MULTIPLIERS:
            equity = s516._stressed_equity(ordered, cost_multiplier)
            peak, trough, max_dd = _max_dd_window(equity)
            window = ordered[ordered["date"].between(peak, trough)].copy()
            start_eq = float(equity.loc[peak]) if peak in equity.index else float(equity.iloc[0])
            end_eq = float(equity.loc[trough]) if trough in equity.index else float(equity.iloc[-1])
            rows.append(
                {
                    "variant": variant,
                    "label": str(ordered["label"].iloc[0]),
                    "cost_multiplier": cost_multiplier,
                    "peak_date": peak.date().isoformat(),
                    "trough_date": trough.date().isoformat(),
                    "window_days": int(len(window)),
                    "max_dd_pct": max_dd,
                    "window_return_pct": (end_eq / max(start_eq, 1e-9) - 1.0) * 100.0,
                    "window_total_net_pnl": float(window["total_net_pnl"].sum()) if len(window) else 0.0,
                    "window_c3_net_pnl": float(window["net_pnl"].sum()) if len(window) else 0.0,
                    "window_xsmom_net_pnl": float(window["xsmom_true_daily_pnl"].sum()) if len(window) else 0.0,
                    "window_total_slippage": float(window["total_slippage"].sum()) if len(window) else 0.0,
                    "window_trade_count": float(window["trade_count"].sum()) if len(window) else 0.0,
                    "broker10_max_pct": float(window["broker10_margin_to_equity_pct"].max()) if len(window) else 0.0,
                    "date_count": int(len(dates)),
                }
            )
    return pd.DataFrame(rows)


def _product_bad_window_attr(product_margin: pd.DataFrame, cost_failure: pd.DataFrame) -> pd.DataFrame:
    if product_margin.empty or cost_failure.empty:
        return pd.DataFrame()
    product = product_margin.copy()
    product["date"] = pd.to_datetime(product["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "holding_pnl", "trading_pnl", "slippage", "trade_count", "c3_margin_exact"]:
        if column not in product.columns:
            product[column] = 0.0
        product[column] = pd.to_numeric(product[column], errors="coerce").fillna(0.0)
    rows: list[pd.DataFrame] = []
    for window in cost_failure[cost_failure["cost_multiplier"].eq(3.0)].itertuples(index=False):
        start = pd.Timestamp(window.peak_date)
        end = pd.Timestamp(window.trough_date)
        frame = product[
            product["variant"].eq(window.variant)
            & product["date"].between(start, end)
        ].copy()
        if frame.empty:
            continue
        grouped = (
            frame.groupby("product_vt_symbol", as_index=False)
            .agg(
                net_pnl=("net_pnl", "sum"),
                holding_pnl=("holding_pnl", "sum"),
                trading_pnl=("trading_pnl", "sum"),
                slippage=("slippage", "sum"),
                trade_count=("trade_count", "sum"),
                max_c3_margin=("c3_margin_exact", "max"),
                active_days=("c3_margin_exact", lambda item: int((item > 0.0).sum())),
            )
            .sort_values("net_pnl", ascending=True)
        )
        grouped["variant"] = window.variant
        grouped["cost_multiplier"] = float(window.cost_multiplier)
        grouped["peak_date"] = window.peak_date
        grouped["trough_date"] = window.trough_date
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _rolling_delta(rolling: pd.DataFrame) -> pd.DataFrame:
    control = rolling[rolling["variant"].eq(CONTROL_VARIANT)].copy()
    if control.empty:
        return pd.DataFrame()
    baseline = control.set_index("holding_days")
    rows: list[dict[str, Any]] = []
    for row in rolling.itertuples(index=False):
        horizon = int(row.holding_days)
        if horizon not in baseline.index:
            continue
        base = baseline.loc[horizon]
        rows.append(
            {
                "variant": str(row.variant),
                "label": str(row.label),
                "holding_days": horizon,
                "p05_return_pct": float(row.p05_return_pct),
                "p05_delta_vs_control": float(row.p05_return_pct) - float(base["p05_return_pct"]),
                "median_return_pct": float(row.median_return_pct),
                "median_delta_vs_control": float(row.median_return_pct) - float(base["median_return_pct"]),
                "positive_rate_pct": float(row.positive_rate_pct),
                "positive_rate_delta_vs_control": float(row.positive_rate_pct) - float(base["positive_rate_pct"]),
                "min_window_dd_pct": float(row.min_window_dd_pct),
                "min_window_dd_delta_vs_control": float(row.min_window_dd_pct) - float(base["min_window_dd_pct"]),
            }
        )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, rolling_delta: pd.DataFrame) -> dict[str, Any]:
    control_row = summary[summary["variant"].eq(CONTROL_VARIANT)]
    if control_row.empty:
        raise RuntimeError("missing control summary")
    control = control_row.iloc[0]
    control_cost = cost[cost["variant"].eq(CONTROL_VARIANT)].set_index("cost_multiplier")
    control_3x_dd = _safe_float(control_cost.loc[3.0, "max_dd_pct"]) if 3.0 in control_cost.index else 0.0
    ranked: list[dict[str, Any]] = []
    for row in summary.itertuples(index=False):
        variant = str(row.variant)
        cost_rows = cost[cost["variant"].eq(variant)].set_index("cost_multiplier")
        two_x_dd = _safe_float(cost_rows.loc[2.0, "max_dd_pct"]) if 2.0 in cost_rows.index else 0.0
        three_x_dd = _safe_float(cost_rows.loc[3.0, "max_dd_pct"]) if 3.0 in cost_rows.index else 0.0
        h63 = rolling_delta[
            rolling_delta["variant"].eq(variant) & rolling_delta["holding_days"].eq(63)
        ]
        h126 = rolling_delta[
            rolling_delta["variant"].eq(variant) & rolling_delta["holding_days"].eq(126)
        ]
        h63_p05_delta = _safe_float(h63["p05_delta_vs_control"].iloc[0]) if not h63.empty else 0.0
        h126_p05_delta = _safe_float(h126["p05_delta_vs_control"].iloc[0]) if not h126.empty else 0.0
        hard_pass = int(
            int(row.dd40_pass) == 1
            and int(row.broker10_100_pass) == 1
            and two_x_dd >= -40.0
        )
        replacement_pass = int(
            hard_pass
            and _safe_float(row.total_return_pct) >= _safe_float(control["total_return_pct"]) * 0.95
            and _safe_float(row.max_dd_pct) >= _safe_float(control["max_dd_pct"]) - 1e-9
            and _safe_float(row.ulcer_pct) <= _safe_float(control["ulcer_pct"]) + 1e-9
            and h63_p05_delta >= 0.0
            and h126_p05_delta >= 0.0
        )
        stress_upgrade = int(three_x_dd >= -40.0 and three_x_dd > control_3x_dd)
        score = (
            _safe_float(row.total_return_pct) / max(_safe_float(control["total_return_pct"]), 1e-9) * 100.0
            + h63_p05_delta * 1.4
            + h126_p05_delta * 1.0
            + max(three_x_dd - control_3x_dd, -25.0) * 1.5
            - max(0.0, _safe_float(row.max_broker10_margin_to_equity_pct) - 100.0) * 5.0
        )
        ranked.append(
            {
                "variant": variant,
                "label": str(row.label),
                "replacement_pass": replacement_pass,
                "hard_pass": hard_pass,
                "stress_upgrade": stress_upgrade,
                "score": score,
                "total_return_pct": _safe_float(row.total_return_pct),
                "return_retention_vs_control_pct": _safe_float(row.total_return_pct) / max(_safe_float(control["total_return_pct"]), 1e-9) * 100.0,
                "max_dd_pct": _safe_float(row.max_dd_pct),
                "ulcer_pct": _safe_float(row.ulcer_pct),
                "sharpe": _safe_float(row.sharpe),
                "two_x_max_dd_pct": two_x_dd,
                "three_x_max_dd_pct": three_x_dd,
                "h63_p05_delta_vs_control": h63_p05_delta,
                "h126_p05_delta_vs_control": h126_p05_delta,
                "max_broker10_margin_to_equity_pct": _safe_float(row.max_broker10_margin_to_equity_pct),
                "days_over_100pct": int(row.days_over_100pct),
                "total_trade_count": _safe_float(row.total_trade_count),
                "total_slippage": _safe_float(row.total_slippage),
            }
        )
    ranked = sorted(ranked, key=lambda item: (item["replacement_pass"], item["stress_upgrade"], item["score"]), reverse=True)
    replacement = [item for item in ranked if item["variant"] != CONTROL_VARIANT and item["replacement_pass"]]
    stress = [item for item in ranked if item["variant"] != CONTROL_VARIANT and item["stress_upgrade"]]
    if replacement:
        label = "exit_shape_replacement_candidate_found"
        best = replacement[0]
    elif stress:
        label = "exit_shape_stress_upgrade_only_not_replacement"
        best = stress[0]
    else:
        label = "exit_shape_no_promotion_keep_stage526_candidate"
        best = next((item for item in ranked if item["variant"] == CONTROL_VARIANT), ranked[0] if ranked else {})
    return {
        "stage": "Stage231",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "best_variant": best,
        "control_variant": CONTROL_VARIANT,
        "ranked_variants": ranked,
        "predeclared_replacement_gate": {
            "normal_cost_dd40": True,
            "normal_broker10_le_100": True,
            "two_x_cost_dd40": True,
            "total_return_ge_95pct_control": True,
            "normal_maxdd_not_worse_than_control": True,
            "ulcer_not_worse_than_control": True,
            "63d_and_126d_p05_not_worse_than_control": True,
        },
        "interpretation": (
            "Only promote an exit-shape change if it improves the 3/6 month left tail without degrading "
            "full-period return, max drawdown, Ulcer, exact margin, and 2x cost survival."
        ),
    }


def _plot(combo_daily: pd.DataFrame, summary: pd.DataFrame, cost: pd.DataFrame, rolling_delta: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    colors = ["#0f766e", "#2563eb", "#dc2626", "#7c3aed", "#334155"]
    variants = summary["variant"].tolist()
    color_map = {variant: colors[index % len(colors)] for index, variant in enumerate(variants)}

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    ax_nav, ax_dd, ax_hold, ax_cost = axes.flatten()
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        dates = pd.to_datetime(ordered["date"])
        equity = pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=dates)
        ax_nav.plot(dates, equity / s516.ACCOUNT_CAPITAL, label=variant, linewidth=1.0, color=color_map.get(variant))
        ax_dd.plot(dates, _drawdown_pct(equity), label=variant, linewidth=0.9, color=color_map.get(variant))

    ax_nav.set_title("NAV: exit-shape variants")
    ax_nav.grid(alpha=0.25)
    ax_nav.legend(fontsize=7)
    ax_dd.set_title("Underwater drawdown")
    ax_dd.axhline(-40.0, color="#111827", linestyle="--", linewidth=1)
    ax_dd.grid(alpha=0.25)

    focus = rolling_delta[rolling_delta["holding_days"].isin([63, 126])].copy()
    if not focus.empty:
        x = np.arange(len(focus))
        ax_hold.bar(
            x,
            focus["p05_delta_vs_control"],
            color=[color_map.get(v, "#64748b") for v in focus["variant"]],
            alpha=0.85,
        )
        ax_hold.axhline(0.0, color="#111827", linewidth=1)
        ax_hold.set_xticks(x)
        ax_hold.set_xticklabels([f"{v}\n{h}d" for v, h in zip(focus["variant"], focus["holding_days"])], rotation=60, ha="right", fontsize=7)
    ax_hold.set_title("63/126d p05 return delta vs control")
    ax_hold.grid(axis="y", alpha=0.25)

    cost3 = cost[cost["cost_multiplier"].eq(3.0)].copy()
    ax_cost.barh(cost3["variant"], cost3["max_dd_pct"], color=[color_map.get(v, "#64748b") for v in cost3["variant"]])
    ax_cost.axvline(-40.0, color="#111827", linestyle="--", linewidth=1)
    ax_cost.set_title("3x cost max drawdown")
    ax_cost.grid(axis="x", alpha=0.25)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    rolling_delta: pd.DataFrame,
    windows: pd.DataFrame,
    cost_failure: pd.DataFrame,
    product_attr: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    cost_view = cost.sort_values(["variant", "cost_multiplier"])
    summary_view = summary.sort_values("total_return_pct", ascending=False)
    hold_view = rolling[rolling["holding_days"].isin([63, 126, 252, 504])].sort_values(["holding_days", "p05_return_pct"], ascending=[True, False])
    delta_view = rolling_delta[rolling_delta["holding_days"].isin([63, 126])].sort_values(["holding_days", "p05_delta_vs_control"], ascending=[True, False])
    product_view = product_attr.sort_values(["variant", "net_pnl"], ascending=[True, True]).groupby("variant").head(8)
    report = [
        "# Stage231 Stage526候选退出形态前沿",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：A/C 最小真实引擎验证；固定 `risk0.80 + product cap25 + maxpos4`，只比较已有退出开关。",
        "- A/B触发判断：触发 A/C。退出形态若通过可能替换当前主研究候选，必须按正式候选标准审计。",
        "- 运行前过拟合判断：否。只测已有低自由度开关，不新增产品黑名单、日期过滤或连续阈值扫描。",
        "- 运行前继续价值判断：是。Stage229 已确认未完成风险来自 2022 长回撤和 3x 成本压力，退出形态是当前最直接的机制检验。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随研究普遍把移动均线/通道突破作为核心退出框架；止损规则并不必然提升趋势策略，过紧会造成 whipsaw。",
        "- ATR trailing stop 的优势是随波动调节，但公开资料也反复提示区间震荡会频繁止损。因此本阶段只做已有开关的方向验证，不扫 ATR 倍数。",
        "",
        "## 预声明晋级门槛",
        "",
        "- 正常成本：DD40、broker10 exact <= 100%。",
        "- 2x成本：DD40。",
        "- 相对 control：总收益不少于95%，最大回撤不劣化，Ulcer不劣化。",
        "- 任意启动体验：63日和126日 p05 收益不劣化。",
        "- 若只改善3x成本但损害上述指标，只能作为研究经验，不能替换候选。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision.get('decision', '')}`。",
        f"- 最优/保留版本：`{decision.get('best_variant', {}).get('variant', '')}`。",
        "",
        "## 全周期 1x 成本",
        "",
        _md_table(
            summary_view[
                [
                    "variant",
                    "total_return_pct",
                    "return_retention_vs_stage079_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "longest_underwater_days",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                ]
            ]
        ),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost_view[
                [
                    "variant",
                    "cost_multiplier",
                    "total_return_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                ]
            ],
            max_rows=60,
        ),
        "",
        "## 任意启动持有体验",
        "",
        _md_table(
            hold_view[
                [
                    "variant",
                    "holding_days",
                    "min_return_pct",
                    "p05_return_pct",
                    "p10_return_pct",
                    "median_return_pct",
                    "positive_rate_pct",
                    "min_window_dd_pct",
                    "worst_return_start",
                    "worst_return_end",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 3/6个月左尾相对control",
        "",
        _md_table(delta_view, max_rows=40),
        "",
        "## 多起点/分段",
        "",
        _md_table(
            windows[
                [
                    "variant",
                    "window_name",
                    "window_return_pct",
                    "window_max_dd_pct",
                    "window_ulcer_pct",
                    "window_max_broker10_margin_to_equity_pct",
                    "window_days_over_100pct",
                ]
            ].sort_values(["variant", "window_name"]),
            max_rows=120,
        ),
        "",
        "## 1x/2x/3x最大回撤窗口",
        "",
        _md_table(cost_failure, max_rows=80),
        "",
        "## 3x失败窗口产品归因",
        "",
        _md_table(
            product_view[
                [
                    "variant",
                    "product_vt_symbol",
                    "net_pnl",
                    "holding_pnl",
                    "trading_pnl",
                    "slippage",
                    "trade_count",
                    "max_c3_margin",
                    "active_days",
                ]
            ],
            max_rows=64,
        ),
        "",
        "## 决策JSON",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    identity_map = s519._product_identity_cluster_map(metadata)
    specs = _variants(identity_map)
    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    for spec in specs:
        print(f"[stage531] running {spec.variant}", flush=True)
        daily, positions, _usage = s517._run_variant(spec, metadata)
        daily_frames.append(daily)
        position_frames.append(positions)

    c3_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions = pd.concat(position_frames, ignore_index=True, sort=False)
    c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
    xsmom_daily = s513._load_xsmom_daily()
    combo_daily = s517._combine_daily(c3_daily, c3_margin_daily, xsmom_daily)
    summary, cost = _summary_and_cost(combo_daily, specs)
    rolling = s516._rolling_holding(combo_daily)
    rolling_delta = _rolling_delta(rolling)
    windows = s516._window_metrics(combo_daily)
    events, product_events = s516._event_days(combo_daily, product_margin)
    cost_failure = _cost_failure_windows(combo_daily)
    product_attr = _product_bad_window_attr(product_margin, cost_failure)
    decision = _decision(summary, cost, rolling_delta)

    _plot(combo_daily, summary, cost, rolling_delta)
    _write_report(summary, cost, rolling, rolling_delta, windows, cost_failure, product_attr, decision)

    combo_daily.to_csv(MARGIN_DAILY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    product_events.to_csv(PRODUCT_EVENT_PATH, index=False, encoding="utf-8-sig")
    cost_failure.to_csv(COST_FAILURE_PATH, index=False, encoding="utf-8-sig")
    product_attr.to_csv(PRODUCT_ATTR_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
