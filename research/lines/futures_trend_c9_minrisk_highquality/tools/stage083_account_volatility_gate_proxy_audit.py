from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage083"
MODEL_TAG = "stage083_account_volatility_gate_proxy_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage083_c9_minrisk_account_volatility_gate_proxy_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage083_account_volatility_gate_proxy_audit"
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
SHORT_VOL_WINDOW = 63
SHORT_VOL_MIN_PERIODS = 42
LONG_VOL_WINDOW = 252
LONG_VOL_MIN_PERIODS = 126

CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
SUMMARY_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

CURVES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
METRICS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_metrics_{MODEL_TAG}.csv"
YEAR_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stats_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_drawdown_broker_chart_{MODEL_TAG}.png"
VOL_WEIGHT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_volatility_weight_chart_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_return_heatmap_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    peak = equity.cummax()
    return (equity / peak - 1.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    std = returns.std(ddof=0)
    if returns.empty or std <= 1e-12:
        return np.nan
    return float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR))


def _ulcer_pct(drawdown_pct: pd.Series) -> float:
    dd = pd.to_numeric(drawdown_pct, errors="coerce").fillna(0.0).clip(upper=0.0)
    return float(np.sqrt(np.mean(np.square(dd))))


def _prepare_official_curve() -> pd.DataFrame:
    data = _read_required_csv(CURVE_IN)
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "net_pnl",
        "account_equity",
        "drawdown_pct",
        "broker10_total_margin_exact",
        "broker10_margin_to_equity_pct",
        "slippage",
        "trade_count",
    ]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0) if column in data else 0.0
    data["official_prior_equity"] = data["account_equity"].shift(1).fillna(CAPITAL)
    data["official_daily_return"] = data["net_pnl"] / data["official_prior_equity"].replace(0.0, np.nan)
    return data


def _volatility_gate_weights(official: pd.DataFrame) -> pd.DataFrame:
    returns = pd.to_numeric(official["official_daily_return"], errors="coerce").replace([np.inf, -np.inf], np.nan)
    past_returns = returns.shift(1)
    short_vol = past_returns.rolling(SHORT_VOL_WINDOW, min_periods=SHORT_VOL_MIN_PERIODS).std(ddof=0) * np.sqrt(
        TRADING_DAYS_PER_YEAR
    )
    long_vol = past_returns.rolling(LONG_VOL_WINDOW, min_periods=LONG_VOL_MIN_PERIODS).std(ddof=0) * np.sqrt(
        TRADING_DAYS_PER_YEAR
    )
    raw_weight = long_vol / short_vol
    weight = raw_weight.clip(upper=1.0)
    ready = short_vol.notna() & long_vol.notna() & short_vol.gt(1e-12) & long_vol.gt(1e-12)
    weight = weight.where(ready, 1.0).fillna(1.0)
    return pd.DataFrame(
        {
            "date": official["date"],
            "vol_gate_ready": ready.astype(int),
            "short_63d_ann_vol": short_vol,
            "long_252d_ann_vol": long_vol,
            "raw_vol_ratio_weight": raw_weight,
            "risk_weight": weight,
        }
    )


def _simulate_curves(official: pd.DataFrame) -> pd.DataFrame:
    weights = _volatility_gate_weights(official)
    official_arm = official.copy()
    official_arm["variant"] = "A_official_c9_15w"
    official_arm["risk_weight"] = 1.0
    official_arm["scaled_net_pnl"] = official_arm["net_pnl"]
    official_arm["overlay_equity"] = official_arm["account_equity"]
    official_arm["overlay_drawdown_pct"] = official_arm["drawdown_pct"]
    official_arm["scaled_broker10_margin_exact"] = official_arm["broker10_total_margin_exact"]
    official_arm["scaled_broker10_margin_to_equity_pct"] = official_arm["broker10_margin_to_equity_pct"]
    official_arm["scaled_slippage"] = official_arm["slippage"]
    for column in ["vol_gate_ready", "short_63d_ann_vol", "long_252d_ann_vol", "raw_vol_ratio_weight"]:
        official_arm[column] = np.nan

    wealth = CAPITAL
    hwm = CAPITAL
    rows: list[dict[str, Any]] = []
    merged = official.merge(weights, on="date", how="left")
    for _, row in merged.iterrows():
        weight = _safe_float(row["risk_weight"], 1.0)
        scaled_pnl = weight * _safe_float(row["net_pnl"], 0.0)
        wealth += scaled_pnl
        hwm = max(hwm, wealth)
        scaled_margin = weight * _safe_float(row["broker10_total_margin_exact"], 0.0)
        rows.append(
            {
                **row.to_dict(),
                "variant": "C_vol_gate_q63_y252_no_leverage",
                "risk_weight": weight,
                "scaled_net_pnl": scaled_pnl,
                "overlay_equity": wealth,
                "overlay_drawdown_pct": (wealth / hwm - 1.0) * 100.0,
                "scaled_broker10_margin_exact": scaled_margin,
                "scaled_broker10_margin_to_equity_pct": scaled_margin / wealth * 100.0 if wealth > 0 else np.nan,
                "scaled_slippage": weight * _safe_float(row["slippage"], 0.0),
            }
        )
    vol_gate_arm = pd.DataFrame(rows)
    return pd.concat([official_arm, vol_gate_arm], ignore_index=True, sort=False)


def _metrics(curves: pd.DataFrame, official_summary: pd.DataFrame) -> pd.DataFrame:
    base = official_summary.iloc[0].to_dict() if len(official_summary) else {}
    official_return = _safe_float(base.get("total_return_pct"))
    official_dd = _safe_float(base.get("max_dd_pct"))
    official_broker = _safe_float(base.get("max_broker10_margin_to_equity_pct"))
    rows: list[dict[str, Any]] = []
    for variant, group in curves.groupby("variant", sort=False):
        group = group.sort_values("date")
        equity = pd.to_numeric(group["overlay_equity"], errors="coerce")
        drawdown = pd.to_numeric(group["overlay_drawdown_pct"], errors="coerce")
        total_return = (float(equity.iloc[-1]) / CAPITAL - 1.0) * 100.0
        max_broker = float(pd.to_numeric(group["scaled_broker10_margin_to_equity_pct"], errors="coerce").max())
        row = {
            "variant": variant,
            "end_equity": float(equity.iloc[-1]),
            "total_return_pct": total_return,
            "return_retention_pct": total_return / official_return * 100.0 if official_return else np.nan,
            "max_dd_pct": float(drawdown.min()),
            "dd_improvement_pp": float(drawdown.min()) - official_dd,
            "ulcer_pct": _ulcer_pct(drawdown),
            "sharpe": _sharpe_from_equity(equity),
            "avg_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").mean()),
            "min_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").min()),
            "days_weight_below_80pct": int((pd.to_numeric(group["risk_weight"], errors="coerce") < 0.8).sum()),
            "days_weight_below_50pct": int((pd.to_numeric(group["risk_weight"], errors="coerce") < 0.5).sum()),
            "max_broker10_margin_to_equity_pct": max_broker,
            "days_over_100pct": int((pd.to_numeric(group["scaled_broker10_margin_to_equity_pct"], errors="coerce") > 100).sum()),
            "days_over_90pct": int((pd.to_numeric(group["scaled_broker10_margin_to_equity_pct"], errors="coerce") > 90).sum()),
            "total_scaled_slippage": float(pd.to_numeric(group["scaled_slippage"], errors="coerce").sum()),
            "official_trade_count_reference": float(pd.to_numeric(group["trade_count"], errors="coerce").sum()),
        }
        row["return_80_pass"] = int(row["return_retention_pct"] >= 80.0)
        row["dd_better_than_official"] = int(row["max_dd_pct"] > official_dd)
        row["meaningful_dd5_pass"] = int(row["dd_improvement_pp"] >= 5.0)
        row["broker10_not_worse_pass"] = int(max_broker <= official_broker + 1e-9)
        row["candidate_ready"] = int(
            variant.startswith("C_")
            and row["return_80_pass"]
            and row["dd_better_than_official"]
            and row["meaningful_dd5_pass"]
            and row["broker10_not_worse_pass"]
        )
        if not variant.startswith("C_"):
            row["decision_note"] = "official baseline"
        elif not row["dd_better_than_official"]:
            row["decision_note"] = "fails drawdown reduction; lagged volatility cuts risk after the main damage"
        elif not row["broker10_not_worse_pass"]:
            row["decision_note"] = "broker10 worsens because reduced equity base offsets scaled exposure"
        elif not row["meaningful_dd5_pass"]:
            row["decision_note"] = "drawdown improvement too small for the objective"
        else:
            row["decision_note"] = "proxy pass only; would still need true engine and A/B discipline"
        rows.append(row)
    return pd.DataFrame(rows)


def _year_stats(curves: pd.DataFrame) -> pd.DataFrame:
    data = curves.copy()
    data["year"] = pd.to_datetime(data["date"], errors="coerce").dt.year
    rows: list[dict[str, Any]] = []
    for (variant, year), group in data.groupby(["variant", "year"], sort=False):
        group = group.sort_values("date")
        start_equity = float(group["overlay_equity"].iloc[0] - group["scaled_net_pnl"].iloc[0])
        end_equity = float(group["overlay_equity"].iloc[-1])
        rows.append(
            {
                "variant": variant,
                "year": int(year),
                "start_equity": start_equity,
                "end_equity": end_equity,
                "year_return_pct": (end_equity / start_equity - 1.0) * 100.0 if start_equity > 0 else np.nan,
                "year_pnl": float(pd.to_numeric(group["scaled_net_pnl"], errors="coerce").sum()),
                "year_max_dd_pct": float(pd.to_numeric(group["overlay_drawdown_pct"], errors="coerce").min()),
                "avg_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").mean()),
                "min_risk_weight": float(pd.to_numeric(group["risk_weight"], errors="coerce").min()),
            }
        )
    return pd.DataFrame(rows)


def _summary(metrics: pd.DataFrame) -> pd.DataFrame:
    candidate = metrics[metrics["variant"].str.startswith("C_")].iloc[0].to_dict()
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "decision": "stage083_account_vol_gate_proxy_not_promoted",
                "candidate_ready_count": int(metrics["candidate_ready"].sum()),
                "candidate_end_equity": candidate["end_equity"],
                "candidate_total_return_pct": candidate["total_return_pct"],
                "candidate_return_retention_pct": candidate["return_retention_pct"],
                "candidate_max_dd_pct": candidate["max_dd_pct"],
                "candidate_dd_improvement_pp": candidate["dd_improvement_pp"],
                "candidate_sharpe": candidate["sharpe"],
                "candidate_max_broker10_margin_to_equity_pct": candidate["max_broker10_margin_to_equity_pct"],
                "candidate_days_over_100pct": candidate["days_over_100pct"],
                "candidate_avg_risk_weight": candidate["avg_risk_weight"],
                "candidate_min_risk_weight": candidate["min_risk_weight"],
            }
        ]
    )


def _decision(metrics: pd.DataFrame, summary: pd.DataFrame) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "stage_type": "readonly_account_layer_volatility_gate_proxy",
        "candidate_rule_tested": False,
        "ab_triggered": False,
        "decision": str(summary.iloc[0]["decision"]),
        "main_conclusion": (
            "fixed no-leverage volatility gate keeps return retention above 80%, but worsens drawdown and broker10 tail"
        ),
        "fixed_spec": {
            "short_vol_window": SHORT_VOL_WINDOW,
            "short_vol_min_periods": SHORT_VOL_MIN_PERIODS,
            "long_vol_window": LONG_VOL_WINDOW,
            "long_vol_min_periods": LONG_VOL_MIN_PERIODS,
            "weight_formula": "min(1, trailing_252d_annualized_vol / trailing_63d_annualized_vol), using data shifted by one trading day",
            "no_leverage": True,
            "no_floor": True,
        },
        "metrics": metrics.to_dict("records"),
        "overfit_reflection_before": (
            "No: this is a single predeclared quarter-vs-year volatility gate, not a scan over products, years, "
            "directions, weak windows, or outcome labels."
        ),
        "overfit_reflection_after": (
            "No for this fixed audit, but any attempt to rescue it by changing 21/63/126/252 windows, adding floors, "
            "or conditioning on the 2022 drawdown would be overfitting."
        ),
        "continue_value_before": (
            "Yes: after Stage082 closed existing labels, a no-leverage account-level volatility governor is a "
            "low-overfit way to test whether drawdown is simply a volatility-budget problem."
        ),
        "continue_value_after": (
            "No for this volatility-gate shape: it reacts after the main maxDD damage and weakens the equity base."
        ),
        "order_api_called": False,
        "ctp_connected": False,
        "outputs": {
            "curves": str(CURVES_OUT),
            "metrics": str(METRICS_OUT),
            "year_stats": str(YEAR_STATS_OUT),
            "summary": str(SUMMARY_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "vol_weight_chart": str(VOL_WEIGHT_CHART_OUT),
            "year_heatmap": str(YEAR_HEATMAP_OUT),
            "report": str(REPORT_OUT),
            "decision": str(DECISION_OUT),
        },
    }


def _plot_path(curves: pd.DataFrame) -> None:
    colors = {"A_official_c9_15w": "#111827", "C_vol_gate_q63_y252_no_leverage": "#0f766e"}
    labels = {"A_official_c9_15w": "A official C9/15w", "C_vol_gate_q63_y252_no_leverage": "C vol gate proxy"}
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    for variant, group in curves.groupby("variant", sort=False):
        group = group.sort_values("date")
        color = colors.get(variant)
        label = labels.get(variant, variant)
        axes[0].plot(group["date"], group["overlay_equity"], color=color, linewidth=1.1, label=label)
        axes[1].plot(group["date"], group["overlay_drawdown_pct"], color=color, linewidth=1.0, label=label)
        axes[2].plot(group["date"], group["scaled_broker10_margin_to_equity_pct"], color=color, linewidth=1.0, label=label)
    axes[0].set_yscale("log")
    axes[0].set_title("Stage083 Official C9/15w vs no-leverage volatility gate proxy")
    axes[0].set_ylabel("Equity (log)")
    axes[1].axhline(-40, color="#dc2626", linestyle="--", linewidth=0.8, alpha=0.7)
    axes[1].axhline(-50, color="#7f1d1d", linestyle="--", linewidth=0.8, alpha=0.7)
    axes[1].set_ylabel("Drawdown %")
    axes[2].axhline(100, color="#991b1b", linestyle="--", linewidth=0.8, alpha=0.7)
    axes[2].set_ylabel("Broker10 %")
    for ax in axes:
        ax.grid(True, alpha=0.22)
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_vol_weight(curves: pd.DataFrame) -> None:
    data = curves[curves["variant"].eq("C_vol_gate_q63_y252_no_leverage")].copy().sort_values("date")
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    axes[0].plot(data["date"], data["short_63d_ann_vol"], color="#ea580c", linewidth=1.0, label="63d annualized vol")
    axes[0].plot(data["date"], data["long_252d_ann_vol"], color="#2563eb", linewidth=1.0, label="252d annualized vol")
    axes[0].set_ylabel("Annualized vol")
    axes[0].set_title("Stage083 lagged official-equity volatility inputs")
    axes[1].plot(data["date"], data["risk_weight"], color="#0f766e", linewidth=1.0, label="risk weight")
    axes[1].set_ylim(0.0, 1.05)
    axes[1].set_ylabel("Weight")
    axes[2].plot(data["date"], data["overlay_drawdown_pct"], color="#0f766e", linewidth=1.0, label="C drawdown")
    axes[2].plot(data["date"], data["drawdown_pct"], color="#111827", linewidth=0.9, alpha=0.75, label="A drawdown")
    axes[2].set_ylabel("Drawdown %")
    for ax in axes:
        ax.grid(True, alpha=0.22)
        ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(VOL_WEIGHT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_year_heatmap(year_stats: pd.DataFrame) -> None:
    pivot = year_stats.pivot(index="variant", columns="year", values="year_return_pct")
    fig, ax = plt.subplots(figsize=(14, 4.8))
    matrix = pivot.to_numpy(dtype=float)
    limit = np.nanmax(np.abs(matrix)) if matrix.size else 1.0
    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=-limit, vmax=limit)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(int(year)) for year in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_title("Stage083 Year Returns: Official vs Vol Gate Proxy")
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]:.0f}%", ha="center", va="center", fontsize=8, color="#111827")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="year return %")
    fig.tight_layout()
    fig.savefig(YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, metrics: pd.DataFrame, year_stats: pd.DataFrame, decision: dict[str, Any]) -> None:
    metric_cols = [
        "variant",
        "end_equity",
        "total_return_pct",
        "return_retention_pct",
        "max_dd_pct",
        "dd_improvement_pp",
        "sharpe",
        "avg_risk_weight",
        "min_risk_weight",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "candidate_ready",
        "decision_note",
    ]
    year_cols = ["variant", "year", "year_return_pct", "year_max_dd_pct", "avg_risk_weight", "min_risk_weight"]
    lines = [
        "# Stage083 账户层波动闸门代理审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段性质：只读账户层代理审计；不写真引擎、不新增交易规则、不触发 A/B、不连接 CTP、不调用订单 API。",
        "- 固定规则：用前一交易日之前的官方日收益计算 `63` 日与 `252` 日年化波动；当 `63d > 252d` 时风险权重为 `252d/63d`，否则为 `1`；绝不加杠杆、无产品/年份/方向/盈亏标签。",
        "",
        "## 外部调研与判断",
        "",
        "- CTA/trend-following 资料普遍把 target volatility / volatility budgeting 作为仓位治理的基础工具。",
        "- 本阶段只测一个 quarter-vs-year、no-leverage archetype；它不是分钟进出场最终方案，只是账户层边界审计。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=5),
        "",
        "## Metrics",
        "",
        _md_table(metrics[metric_cols], max_rows=10),
        "",
        "## Year Stats",
        "",
        _md_table(year_stats[year_cols], max_rows=40),
        "",
        "## Visual Outputs",
        "",
        f"- path/drawdown/broker10 chart：`{PATH_CHART_OUT}`",
        f"- volatility/weight chart：`{VOL_WEIGHT_CHART_OUT}`",
        f"- year heatmap：`{YEAR_HEATMAP_OUT}`",
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 主结论：`{decision['main_conclusion']}`",
        f"- 过拟合反思：`{decision['overfit_reflection_after']}`",
        f"- 继续价值：`{decision['continue_value_after']}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage083] loading official curve", flush=True)
    official = _prepare_official_curve()
    official_summary = _read_required_csv(SUMMARY_IN)
    print("[stage083] simulating fixed volatility gate proxy", flush=True)
    curves = _simulate_curves(official)
    metrics = _metrics(curves, official_summary)
    year_stats = _year_stats(curves)
    summary = _summary(metrics)
    decision = _decision(metrics, summary)
    print("[stage083] plotting visuals", flush=True)
    _plot_path(curves)
    _plot_vol_weight(curves)
    _plot_year_heatmap(year_stats)
    curves.to_csv(CURVES_OUT, index=False, encoding="utf-8-sig")
    metrics.to_csv(METRICS_OUT, index=False, encoding="utf-8-sig")
    year_stats.to_csv(YEAR_STATS_OUT, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    _write_report(summary, metrics, year_stats, decision)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[stage083] decision={decision['decision']}", flush=True)
    print(f"[stage083] summary={SUMMARY_OUT}", flush=True)
    print(f"[stage083] path_chart={PATH_CHART_OUT}", flush=True)


if __name__ == "__main__":
    main()
