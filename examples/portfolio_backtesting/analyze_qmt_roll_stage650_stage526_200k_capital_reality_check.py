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
import analyze_qmt_roll_stage517_portfolio_margin_deleverage_frontier as s517  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
from qmt_universe import END_DT, START_DT  # noqa: E402


MODEL_TAG = "stage650_stage526_200k_capital_reality_check_v1"
OUTPUT_PREFIX = "qmt_roll_stage650_stage526_200k_capital_reality_check"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_200K = 200_000.0
STAGE526_ACCOUNT_CAPITAL = 615_000.0
STAGE526_C3_CAPITAL = 500_000.0
STAGE526_C3_RATIO = STAGE526_C3_CAPITAL / STAGE526_ACCOUNT_CAPITAL
BROKER_MARGIN_MULTIPLIER = float(s517.BROKER_MARGIN_MULTIPLIER)
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)
ROLLING_HORIZONS: tuple[int, ...] = (63, 126, 252)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_days_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class CapitalVariant:
    variant: str
    label: str
    account_capital: float
    c3_capital: float
    risk_multiplier: float
    product_cap_ratio: float
    max_concurrent_positions: int
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


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = equity.astype(float)
    return (values / values.cummax() - 1.0) * 100.0


def _max_drawdown_pct(equity: pd.Series) -> float:
    return float(_drawdown_pct(equity).min()) if not equity.empty else 0.0


def _ulcer_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    dd = _drawdown_pct(equity)
    return float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(dtype=float), 0.0)))))


def _sharpe(equity: pd.Series) -> float:
    returns = equity.astype(float).pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(returns.mean() / std * math.sqrt(252.0))


def _cagr_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    start_value = float(equity.iloc[0])
    end_value = float(equity.iloc[-1])
    if start_value <= 0 or end_value <= 0:
        return 0.0
    years = (pd.Timestamp(equity.index[-1]) - pd.Timestamp(equity.index[0])).days / 365.25
    if years <= 0:
        return 0.0
    return float((end_value / start_value) ** (1.0 / years) - 1.0) * 100.0


def _stressed_equity(frame: pd.DataFrame, cost_multiplier: float) -> pd.Series:
    ordered = frame.sort_values("date").copy()
    additional = ordered["total_slippage"].astype(float).cumsum() * max(0.0, float(cost_multiplier) - 1.0)
    equity = ordered["account_equity"].astype(float) - additional
    return pd.Series(equity.to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))


def _metrics(frame: pd.DataFrame, spec: CapitalVariant, cost_multiplier: float) -> dict[str, Any]:
    ordered = frame.sort_values("date").copy()
    equity = _stressed_equity(ordered, cost_multiplier)
    account_capital = float(spec.account_capital)
    total_profit = float(equity.iloc[-1] - account_capital) if not equity.empty else 0.0
    margin_ratio = (
        ordered["broker10_total_margin_exact"].astype(float).to_numpy()
        / np.maximum(equity.to_numpy(dtype=float), 1e-9)
        * 100.0
    )
    nonzero_pnl = ordered["total_net_pnl"].astype(float)
    nonzero_pnl = nonzero_pnl[nonzero_pnl.abs() > 1e-12]
    return {
        "variant": spec.variant,
        "label": spec.label,
        "cost_multiplier": float(cost_multiplier),
        "account_capital": account_capital,
        "c3_capital": float(spec.c3_capital),
        "risk_multiplier": float(spec.risk_multiplier),
        "product_cap_ratio": float(spec.product_cap_ratio),
        "max_concurrent_positions": int(spec.max_concurrent_positions),
        "end_equity": float(equity.iloc[-1]) if not equity.empty else account_capital,
        "total_return_pct": total_profit / account_capital * 100.0 if account_capital > 0 else 0.0,
        "cagr_pct": _cagr_pct(equity),
        "max_dd_pct": _max_drawdown_pct(equity),
        "ulcer_pct": _ulcer_pct(equity),
        "sharpe": _sharpe(equity),
        "min_equity": float(equity.min()) if not equity.empty else account_capital,
        "max_broker10_margin_to_equity_pct": float(np.max(margin_ratio)) if len(margin_ratio) else 0.0,
        "p95_broker10_margin_to_equity_pct": float(np.quantile(margin_ratio, 0.95)) if len(margin_ratio) else 0.0,
        "days_over_100pct": int(np.sum(margin_ratio > 100.0 + 1e-9)),
        "days_over_90pct": int(np.sum(margin_ratio > 90.0 + 1e-9)),
        "days_equity_below_zero": int(np.sum(equity.to_numpy(dtype=float) <= 0.0)),
        "total_slippage": float(ordered["total_slippage"].sum()),
        "total_trade_count": float(ordered["trade_count"].sum()),
        "nonzero_daily_win_rate_pct": float((nonzero_pnl > 0.0).mean() * 100.0) if len(nonzero_pnl) else 0.0,
        "dd40_pass": int(_max_drawdown_pct(equity) >= -40.0),
        "broker10_100_pass": int(np.all(margin_ratio <= 100.0 + 1e-9)) if len(margin_ratio) else 1,
        "account_survival_pass": int(np.all(equity.to_numpy(dtype=float) > 0.0)) if len(equity) else 1,
        "deployable_pass": int(
            _max_drawdown_pct(equity) >= -40.0
            and np.all(margin_ratio <= 100.0 + 1e-9)
            and np.all(equity.to_numpy(dtype=float) > 0.0)
        )
        if len(equity)
        else 0,
        "note": spec.note,
    }


def _rolling_holding(combo_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date").reset_index(drop=True)
        equity = ordered["account_equity"].astype(float).to_numpy()
        dates = pd.to_datetime(ordered["date"]).reset_index(drop=True)
        label = str(ordered["label"].iloc[0])
        for horizon in ROLLING_HORIZONS:
            if len(ordered) <= horizon:
                continue
            returns: list[float] = []
            dds: list[float] = []
            starts: list[str] = []
            ends: list[str] = []
            for start_idx in range(0, len(ordered) - horizon):
                end_idx = start_idx + horizon
                window_values = equity[start_idx : end_idx + 1]
                start_value = max(float(window_values[0]), 1e-9)
                returns.append(float(window_values[-1] / start_value - 1.0) * 100.0)
                peaks = np.maximum.accumulate(window_values)
                dds.append(float(np.min(window_values / np.maximum(peaks, 1e-9) - 1.0) * 100.0))
                starts.append(pd.Timestamp(dates.iloc[start_idx]).date().isoformat())
                ends.append(pd.Timestamp(dates.iloc[end_idx]).date().isoformat())
            ret_arr = np.asarray(returns, dtype=float)
            dd_arr = np.asarray(dds, dtype=float)
            worst_idx = int(np.argmin(ret_arr))
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "holding_days": int(horizon),
                    "sample_count": int(len(ret_arr)),
                    "min_return_pct": float(np.min(ret_arr)),
                    "p05_return_pct": float(np.quantile(ret_arr, 0.05)),
                    "median_return_pct": float(np.median(ret_arr)),
                    "positive_rate_pct": float(np.mean(ret_arr > 0.0) * 100.0),
                    "min_window_dd_pct": float(np.min(dd_arr)),
                    "worst_return_start": starts[worst_idx],
                    "worst_return_end": ends[worst_idx],
                }
            )
    return pd.DataFrame(rows)


def _combine_daily(c3_daily: pd.DataFrame, margin_daily: pd.DataFrame, spec: CapitalVariant) -> pd.DataFrame:
    merged = c3_daily.sort_values("date").merge(
        margin_daily[margin_daily["variant"].eq(spec.variant)][
            ["date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
        ],
        on="date",
        how="left",
    )
    for column in ["c3_margin_exact", "c3_active_contracts", "c3_active_products"]:
        merged[column] = pd.to_numeric(merged.get(column, 0.0), errors="coerce").fillna(0.0)
    merged["total_net_pnl"] = merged["net_pnl"].astype(float)
    merged["total_slippage"] = merged["slippage"].astype(float)
    merged["account_equity"] = float(spec.account_capital) + merged["total_net_pnl"].cumsum()
    merged["total_margin_exact"] = merged["c3_margin_exact"]
    merged["broker10_total_margin_exact"] = merged["total_margin_exact"] * BROKER_MARGIN_MULTIPLIER
    merged["broker10_margin_to_equity_pct"] = (
        merged["broker10_total_margin_exact"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    merged["xsmom_enabled"] = 0
    return merged


def _event_days(combo_daily: pd.DataFrame, product_margin: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        equity = pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))
        margin_ratio = pd.Series(ordered["broker10_margin_to_equity_pct"].to_numpy(dtype=float), index=pd.to_datetime(ordered["date"]))
        dates = list(margin_ratio.sort_values(ascending=False).head(5).index)
        dates.extend(list(_drawdown_pct(equity).sort_values(ascending=True).head(5).index))
        seen: set[pd.Timestamp] = set()
        for date in dates:
            date = pd.Timestamp(date).normalize()
            if date in seen:
                continue
            seen.add(date)
            row = ordered[ordered["date"].eq(date)].iloc[0]
            products = product_margin[
                product_margin["variant"].eq(variant)
                & product_margin["date"].eq(date)
                & product_margin["c3_margin_exact"].gt(0.0)
            ].sort_values("c3_margin_exact", ascending=False)
            top_products = ",".join(products["product_vt_symbol"].head(5).astype(str).tolist()) if not products.empty else ""
            rows.append(
                {
                    "variant": variant,
                    "label": str(row["label"]),
                    "date": date.date().isoformat(),
                    "account_equity": float(row["account_equity"]),
                    "drawdown_pct": float(_drawdown_pct(equity).loc[date]),
                    "broker10_margin_to_equity_pct": float(row["broker10_margin_to_equity_pct"]),
                    "c3_margin_exact": float(row["c3_margin_exact"]),
                    "c3_active_products": int(row["c3_active_products"]),
                    "top_margin_products": top_products,
                }
            )
    return pd.DataFrame(rows)


def _stage526_specs(identity_map: str) -> list[CapitalVariant]:
    return [
        CapitalVariant(
            variant="stage526_200k_allin_r080_pc25_maxpos4",
            label="20w all-in Stage526 core r080 pc25 maxpos4",
            account_capital=ACCOUNT_200K,
            c3_capital=ACCOUNT_200K,
            risk_multiplier=0.80,
            product_cap_ratio=0.25,
            max_concurrent_positions=4,
            note="20万全部作为Stage526 C3核心资金；不启用原61.5万口径的xsmom/现金腿。",
        ),
        CapitalVariant(
            variant="stage526_200k_ratio_cash_r080_pc25_maxpos4",
            label="20w ratio-cash Stage526 core r080 pc25 maxpos4",
            account_capital=ACCOUNT_200K,
            c3_capital=ACCOUNT_200K * STAGE526_C3_RATIO,
            risk_multiplier=0.80,
            product_cap_ratio=0.25,
            max_concurrent_positions=4,
            note="按原Stage526 50/61.5资金比例，只给C3核心约16.26万，下余现金；xsmom腿关闭。",
        ),
        CapitalVariant(
            variant="stage526_200k_defensive_r050_pc25_maxpos2",
            label="20w defensive probe r050 pc25 maxpos2",
            account_capital=ACCOUNT_200K,
            c3_capital=ACCOUNT_200K,
            risk_multiplier=0.50,
            product_cap_ratio=0.25,
            max_concurrent_positions=2,
            note="小资金可行性探针；改变风险倍率和最大同时品种，不视为Stage526原版。",
        ),
    ]


def _to_s517_spec(spec: CapitalVariant, identity_map: str) -> s517.VariantSpec:
    return s517.VariantSpec(
        variant=spec.variant,
        label=spec.label,
        risk_multiplier=spec.risk_multiplier,
        overrides={
            **s519._product_cap_overrides(spec.product_cap_ratio, identity_map),
            "max_concurrent_positions": spec.max_concurrent_positions,
        },
        note=spec.note,
    )


def _plot(combo_daily: pd.DataFrame, summary: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    ax_nav, ax_dd, ax_margin, ax_scatter = axes.flatten()
    colors = ["#2563eb", "#dc2626", "#059669"]
    color_map = {variant: colors[idx % len(colors)] for idx, variant in enumerate(summary["variant"].tolist())}
    for variant, frame in combo_daily.groupby("variant", sort=False):
        ordered = frame.sort_values("date")
        x = pd.to_datetime(ordered["date"])
        equity = pd.Series(ordered["account_equity"].to_numpy(dtype=float), index=x)
        label = str(ordered["label"].iloc[0])
        capital = float(ordered["account_capital"].iloc[0])
        ax_nav.plot(x, equity / capital, label=label, linewidth=1.0, color=color_map.get(variant))
        ax_dd.plot(x, _drawdown_pct(equity), label=label, linewidth=0.9, color=color_map.get(variant))
        ax_margin.plot(x, ordered["broker10_margin_to_equity_pct"], label=label, linewidth=0.9, color=color_map.get(variant))
    ax_nav.set_title("NAV")
    ax_nav.grid(alpha=0.25)
    ax_nav.legend(fontsize=7)
    ax_dd.axhline(-40.0, color="#111827", linestyle="--", linewidth=1.0)
    ax_dd.set_title("Drawdown")
    ax_dd.grid(alpha=0.25)
    ax_margin.axhline(100.0, color="#111827", linestyle="--", linewidth=1.0)
    ax_margin.axhline(90.0, color="#64748b", linestyle=":", linewidth=0.9)
    ax_margin.set_title("Broker10 margin/equity")
    ax_margin.grid(alpha=0.25)
    ax_scatter.scatter(
        summary["total_return_pct"],
        summary["max_dd_pct"],
        s=np.maximum(summary["max_broker10_margin_to_equity_pct"], 1.0),
        c=[color_map.get(v, "#334155") for v in summary["variant"]],
        alpha=0.85,
    )
    for row in summary.itertuples(index=False):
        ax_scatter.annotate(str(row.variant).replace("stage526_200k_", "").replace("_", "\n"), (row.total_return_pct, row.max_dd_pct), fontsize=7)
    ax_scatter.axhline(-40.0, color="#111827", linestyle="--", linewidth=1.0)
    ax_scatter.set_title("Return vs max drawdown")
    ax_scatter.set_xlabel("Total return %")
    ax_scatter.set_ylabel("Max drawdown %")
    ax_scatter.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame) -> dict[str, Any]:
    full = summary.sort_values(["deployable_pass", "total_return_pct"], ascending=[False, False]).copy()
    deployable = full[full["deployable_pass"].eq(1)].copy()
    best = deployable.head(1) if not deployable.empty else full.head(1)
    best_row = best.to_dict(orient="records")[0] if not best.empty else {}
    exact = summary[summary["variant"].eq("stage526_200k_allin_r080_pc25_maxpos4")]
    exact_row = exact.to_dict(orient="records")[0] if not exact.empty else {}
    return {
        "stage": "Stage350",
        "script_stage": "Stage650",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "stage526_200k_not_deployable" if int(exact_row.get("deployable_pass", 0) or 0) == 0 else "stage526_200k_exact_core_passes_basic_gates",
        "exact_stage526_200k": exact_row,
        "best_basic_gate_variant": best_row,
        "cost_rows": cost.to_dict(orient="records"),
        "pass_definition": "account equity > 0, max drawdown >= -40%, broker10 margin/equity <= 100%",
        "hard_limit": "This run disables the original 61.5w xsmom/cash leg. It is a 20w core-capital reality check, not a live-trading approval.",
    }


def _write_report(summary: pd.DataFrame, cost: pd.DataFrame, rolling: pd.DataFrame, events: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage650 Stage526 20万资金现实可行性审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：部署资金层 A/C 审计；不改 Stage526 alpha，不接 CTP，不调用下单。",
        "- A：原 Stage526 权威口径 `61.5万账户/50万C3资金/xsmom现金组合腿`。",
        "- C：20万账户下的 Stage526 C3 核心真实整数手重放；原 xsmom/现金腿关闭。",
        "- 运行前过拟合判断：否。只变资金口径和预声明粗风险探针，不用历史坏窗口救参。",
        "- 运行前继续价值判断：是。用户真实资金改为20万，必须先验证合约整数手与保证金约束。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 外部调研判断",
        "",
        "- 期货小资金账户的关键不是收益线性缩放，而是整数合约、保证金和波动风险会让原组合失真。",
        "- vn.py/PortfolioStrategy 可承载多合约策略，但资金小于原模型资金口径时，必须先做真实整数手与保证金重放。",
        "",
        "## 核心结果",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "account_capital",
                    "c3_capital",
                    "risk_multiplier",
                    "max_concurrent_positions",
                    "end_equity",
                    "total_return_pct",
                    "cagr_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "days_equity_below_zero",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "deployable_pass",
                ]
            ]
        ),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "variant",
                    "cost_multiplier",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "deployable_pass",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 63/126/252日任意启动体验",
        "",
        _md_table(
            rolling[
                [
                    "variant",
                    "holding_days",
                    "p05_return_pct",
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
        "## 关键风险日",
        "",
        _md_table(events, max_rows=40),
        "",
        "## 结论",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        "- 如果原版 20万 all-in 不通过，不能直接实盘；只能考虑更低风险的独立小资金版本，并重新走执行/TCA/风控验收。",
        "- 本阶段没有给出真实交易许可；Stage526 的 live TCA 缺口仍未关闭。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    identity_map = s519._product_identity_cluster_map(metadata)
    specs = _stage526_specs(identity_map)

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    margin_frames: list[pd.DataFrame] = []
    product_frames: list[pd.DataFrame] = []

    original_c3_capital = s517.C3_CAPITAL
    try:
        for spec in specs:
            print(f"[stage650] running {spec.variant} account={spec.account_capital:.0f} c3={spec.c3_capital:.0f}", flush=True)
            s517.C3_CAPITAL = float(spec.c3_capital)
            daily, positions, usage = s517._run_variant(_to_s517_spec(spec, identity_map), metadata)
            daily["account_capital"] = float(spec.account_capital)
            daily["c3_capital"] = float(spec.c3_capital)
            positions["account_capital"] = float(spec.account_capital)
            positions["c3_capital"] = float(spec.c3_capital)
            c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
            combined = _combine_daily(daily, c3_margin_daily, spec)
            daily_frames.append(combined)
            position_frames.append(positions)
            margin_frames.append(c3_margin_daily)
            product_frames.append(product_margin)
            if not usage.empty:
                usage["account_capital"] = float(spec.account_capital)
                usage["c3_capital"] = float(spec.c3_capital)
                usage_frames.append(usage)
    finally:
        s517.C3_CAPITAL = original_c3_capital

    combo_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False)
    product_margin_all = pd.concat(product_frames, ignore_index=True, sort=False)
    usage_all = pd.concat(usage_frames, ignore_index=True, sort=False) if usage_frames else pd.DataFrame()

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    spec_map = {spec.variant: spec for spec in specs}
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = spec_map[variant]
        for cost_multiplier in COST_MULTIPLIERS:
            row = _metrics(frame, spec, cost_multiplier)
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    rolling = _rolling_holding(combo_daily)
    events = _event_days(combo_daily, product_margin_all)
    decision = _decision(summary, cost)
    _plot(combo_daily, summary)
    _write_report(summary, cost, rolling, events, decision)

    combo_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_margin_all.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    if not usage_all.empty:
        usage_all.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
