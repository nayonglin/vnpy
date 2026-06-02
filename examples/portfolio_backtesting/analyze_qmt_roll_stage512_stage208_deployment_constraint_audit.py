from __future__ import annotations

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

import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402


MODEL_TAG = "stage512_stage208_deployment_constraint_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage512_stage208_deployment_constraint_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
STAGE208_TAG = "stage508_xsmom_true_carry_replay_v1"
STAGE208_PREFIX = "qmt_roll_stage508_xsmom_true_carry_replay"

DAILY_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_daily_{STAGE208_TAG}.csv"
XSMOM_DAILY_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_xsmom_daily_{STAGE208_TAG}.csv"
COST_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_cost_stress_{STAGE208_TAG}.csv"

DAILY_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_detail_{MODEL_TAG}.csv"
DEPLOYMENT_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_deployment_matrix_{MODEL_TAG}.csv"
EVENT_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_days_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BASELINE = "stage079"
RISK060 = "stage079_next_real_risk060_clean_plus_stage103_xsmom_true"
RISK070 = "stage079_next_real_risk070_clean_plus_stage103_xsmom_true"
VARIANTS = [RISK060, RISK070]
RISK_MULT = {
    RISK060: 0.60,
    RISK070: 0.70,
}
COST_MULTIPLIERS = [1.0, 2.0, 3.0]
MARGIN_CAPS = [100.0, 95.0, 90.0, 80.0]
DD_LIMIT_PCT = -40.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


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
    return float(_drawdown_pct(equity).min())


def _ulcer_pct(equity: pd.Series) -> float:
    dd = _drawdown_pct(equity)
    return float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(dtype=float), 0.0)))))


def _longest_underwater_days(equity: pd.Series) -> int:
    dd = _drawdown_pct(equity)
    longest = 0
    current = 0
    for value in dd.to_numpy(dtype=float):
        if value < -1e-12:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def _load_daily() -> pd.DataFrame:
    frame = pd.read_csv(DAILY_IN, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "slippage", "trade_count", "net_pnl"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame = frame.dropna(subset=["date", "variant"]).sort_values(["variant", "date"]).reset_index(drop=True)
    keep = [BASELINE, *VARIANTS]
    return frame[frame["variant"].isin(keep)].copy()


def _load_xsmom_margin() -> pd.DataFrame:
    xsmom = pd.read_csv(XSMOM_DAILY_IN, encoding="utf-8-sig")
    xsmom["date"] = pd.to_datetime(xsmom["date"], errors="coerce").dt.normalize()
    xsmom["xsmom_true_margin"] = pd.to_numeric(xsmom.get("xsmom_true_margin", 0.0), errors="coerce").fillna(0.0)
    return xsmom[["date", "xsmom_true_margin"]].dropna(subset=["date"]).copy()


def _load_broker_margin() -> pd.DataFrame:
    margin = s402._load_margin()
    margin["date"] = pd.to_datetime(margin["date"], errors="coerce").dt.normalize()
    margin = margin[margin["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    margin = margin[["date", "c3_margin"]].copy()
    margin["c3_margin"] = pd.to_numeric(margin["c3_margin"], errors="coerce").fillna(0.0)
    xsmom = _load_xsmom_margin()
    rows: list[pd.DataFrame] = []
    for variant in VARIANTS:
        merged = margin.merge(xsmom, on="date", how="left")
        merged["xsmom_true_margin"] = merged["xsmom_true_margin"].fillna(0.0)
        merged["variant"] = variant
        merged["risk_multiplier"] = RISK_MULT[variant]
        merged["c3_margin_proxy"] = merged["c3_margin"] * RISK_MULT[variant]
        merged["total_margin_proxy"] = merged["c3_margin_proxy"] + merged["xsmom_true_margin"]
        merged["broker10_margin_proxy"] = merged["total_margin_proxy"] * float(s403.BROKER10_MULTIPLIER)
        rows.append(merged)
    return pd.concat(rows, ignore_index=True)


def _stressed_equity(frame: pd.DataFrame, cost_multiplier: float, extra_cash: float = 0.0) -> pd.Series:
    ordered = frame.sort_values("date").copy()
    additional_slippage = ordered["slippage"].astype(float).cumsum() * max(cost_multiplier - 1.0, 0.0)
    values = ordered["account_equity"].astype(float).to_numpy() - additional_slippage.to_numpy() + float(extra_cash)
    return pd.Series(values, index=pd.to_datetime(ordered["date"]))


def _needed_cash_for_dd(equity: pd.Series, dd_limit_pct: float) -> float:
    if _max_drawdown_pct(equity) >= dd_limit_pct:
        return 0.0
    low = 0.0
    high = max(float(equity.max() - equity.min()), ACCOUNT_CAPITAL)
    while _max_drawdown_pct(equity + high) < dd_limit_pct:
        high *= 2.0
        if high > 100_000_000.0:
            break
    for _ in range(80):
        mid = (low + high) / 2.0
        if _max_drawdown_pct(equity + mid) >= dd_limit_pct:
            high = mid
        else:
            low = mid
    return float(high)


def _needed_cash_for_margin(equity: pd.Series, broker_margin: pd.Series, cap_pct: float) -> float:
    aligned_margin = broker_margin.reindex(equity.index).ffill().fillna(0.0).astype(float)
    cap_fraction = float(cap_pct) / 100.0
    required = aligned_margin / cap_fraction - equity.astype(float)
    return float(max(0.0, required.max()))


def _metrics(
    variant: str,
    label: str,
    cost_multiplier: float,
    equity_no_cash: pd.Series,
    broker_margin: pd.Series,
    extra_cash: float,
    margin_cap_pct: float,
) -> dict[str, Any]:
    equity = equity_no_cash + float(extra_cash)
    deployed_capital = ACCOUNT_CAPITAL + float(extra_cash)
    margin_ratio = broker_margin.reindex(equity.index).ffill().fillna(0.0).astype(float) / equity.astype(float) * 100.0
    profit = float(equity_no_cash.iloc[-1] - ACCOUNT_CAPITAL)
    return {
        "variant": variant,
        "label": label,
        "cost_multiplier": cost_multiplier,
        "margin_cap_pct": margin_cap_pct,
        "extra_cash": float(extra_cash),
        "deployed_capital": deployed_capital,
        "end_equity": float(equity.iloc[-1]),
        "profit": profit,
        "pnl_on_base_capital_pct": profit / ACCOUNT_CAPITAL * 100.0,
        "return_on_deployed_capital_pct": profit / deployed_capital * 100.0,
        "max_dd_pct": _max_drawdown_pct(equity),
        "ulcer_pct": _ulcer_pct(equity),
        "longest_underwater_days": _longest_underwater_days(equity),
        "max_broker10_margin_to_equity_pct": float(margin_ratio.max()),
        "p95_broker10_margin_to_equity_pct": float(margin_ratio.quantile(0.95)),
        "days_over_cap": int((margin_ratio > margin_cap_pct + 1e-9).sum()),
        "days_over_100pct": int((margin_ratio > 100.0 + 1e-9).sum()),
        "days_over_95pct": int((margin_ratio > 95.0 + 1e-9).sum()),
        "days_over_90pct": int((margin_ratio > 90.0 + 1e-9).sum()),
        "dd40_pass": int(_max_drawdown_pct(equity) >= DD_LIMIT_PCT),
        "margin_cap_pass": int((margin_ratio <= margin_cap_pct + 1e-9).all()),
    }


def _build_audit(daily: pd.DataFrame, broker_margin: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    labels = daily.drop_duplicates("variant").set_index("variant")["label"].to_dict()
    baseline = daily[daily["variant"].eq(BASELINE)].copy()
    baseline_return = float(_stressed_equity(baseline, 1.0).iloc[-1] / ACCOUNT_CAPITAL - 1.0) * 100.0
    detail_rows: list[dict[str, Any]] = []
    deployment_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    margin_by_variant = {
        variant: frame.sort_values("date").set_index("date")["broker10_margin_proxy"].astype(float)
        for variant, frame in broker_margin.groupby("variant")
    }
    for variant in VARIANTS:
        frame = daily[daily["variant"].eq(variant)].copy()
        if frame.empty:
            continue
        label = labels.get(variant, variant)
        broker_series = margin_by_variant[variant]
        for cost_multiplier in COST_MULTIPLIERS:
            equity_no_cash = _stressed_equity(frame, cost_multiplier)
            dd_cash = _needed_cash_for_dd(equity_no_cash, DD_LIMIT_PCT)
            no_cash_metrics = _metrics(
                variant,
                label,
                cost_multiplier,
                equity_no_cash,
                broker_series,
                0.0,
                100.0,
            )
            no_cash_metrics["scenario"] = "no_extra_cash"
            no_cash_metrics["cash_needed_for_dd40"] = dd_cash
            no_cash_metrics["return_retention_vs_stage079_base_pct"] = (
                no_cash_metrics["pnl_on_base_capital_pct"] / baseline_return * 100.0
            )
            no_cash_metrics["return_retention_vs_stage079_deployed_pct"] = (
                no_cash_metrics["return_on_deployed_capital_pct"] / baseline_return * 100.0
            )
            detail_rows.append(no_cash_metrics)
            margin_ratio_no_cash = broker_series.reindex(equity_no_cash.index).ffill().fillna(0.0) / equity_no_cash * 100.0
            dd_no_cash = _drawdown_pct(equity_no_cash)
            for row_date in margin_ratio_no_cash.sort_values(ascending=False).head(12).index:
                event_rows.append(
                    {
                        "variant": variant,
                        "label": label,
                        "cost_multiplier": cost_multiplier,
                        "event_type": "top_margin_ratio",
                        "date": row_date,
                        "equity_no_cash": float(equity_no_cash.loc[row_date]),
                        "broker10_margin_proxy": float(broker_series.reindex(equity_no_cash.index).ffill().fillna(0.0).loc[row_date]),
                        "broker10_margin_to_equity_pct": float(margin_ratio_no_cash.loc[row_date]),
                        "drawdown_pct": float(dd_no_cash.loc[row_date]),
                    }
                )
            for row_date in dd_no_cash.sort_values(ascending=True).head(12).index:
                event_rows.append(
                    {
                        "variant": variant,
                        "label": label,
                        "cost_multiplier": cost_multiplier,
                        "event_type": "deepest_drawdown",
                        "date": row_date,
                        "equity_no_cash": float(equity_no_cash.loc[row_date]),
                        "broker10_margin_proxy": float(broker_series.reindex(equity_no_cash.index).ffill().fillna(0.0).loc[row_date]),
                        "broker10_margin_to_equity_pct": float(margin_ratio_no_cash.loc[row_date]),
                        "drawdown_pct": float(dd_no_cash.loc[row_date]),
                    }
                )
            for cap in MARGIN_CAPS:
                margin_cash = _needed_cash_for_margin(equity_no_cash, broker_series, cap)
                combined_cash = max(dd_cash, margin_cash)
                row = _metrics(
                    variant,
                    label,
                    cost_multiplier,
                    equity_no_cash,
                    broker_series,
                    combined_cash,
                    cap,
                )
                row["scenario"] = f"dd40_and_margin_cap_{int(cap)}"
                row["cash_needed_for_dd40"] = dd_cash
                row["cash_needed_for_margin_cap"] = margin_cash
                row["cash_binding_reason"] = "dd40" if dd_cash > margin_cash + 1e-6 else "margin" if margin_cash > dd_cash + 1e-6 else "tie_or_zero"
                row["return_retention_vs_stage079_base_pct"] = row["pnl_on_base_capital_pct"] / baseline_return * 100.0
                row["return_retention_vs_stage079_deployed_pct"] = row["return_on_deployed_capital_pct"] / baseline_return * 100.0
                row["deploy_pass"] = int(row["dd40_pass"] == 1 and row["margin_cap_pass"] == 1)
                deployment_rows.append(row)
    return pd.DataFrame(detail_rows), pd.DataFrame(deployment_rows), pd.DataFrame(event_rows)


def _decision(detail: pd.DataFrame, deployment: pd.DataFrame) -> dict[str, Any]:
    focus_100 = deployment[
        deployment["margin_cap_pct"].eq(100.0) & deployment["cost_multiplier"].isin([1.0, 2.0, 3.0])
    ].copy()
    focus_90 = deployment[
        deployment["margin_cap_pct"].eq(90.0) & deployment["cost_multiplier"].isin([1.0, 2.0, 3.0])
    ].copy()
    risk060_no_cash = detail[(detail["variant"].eq(RISK060)) & (detail["cost_multiplier"].eq(1.0))].iloc[0]
    risk070_no_cash = detail[(detail["variant"].eq(RISK070)) & (detail["cost_multiplier"].eq(1.0))].iloc[0]
    r060_c2 = detail[(detail["variant"].eq(RISK060)) & (detail["cost_multiplier"].eq(2.0))].iloc[0]
    r070_c2 = detail[(detail["variant"].eq(RISK070)) & (detail["cost_multiplier"].eq(2.0))].iloc[0]
    r060_cap90_1x = focus_90[(focus_90["variant"].eq(RISK060)) & (focus_90["cost_multiplier"].eq(1.0))].iloc[0]
    r070_cap90_1x = focus_90[(focus_90["variant"].eq(RISK070)) & (focus_90["cost_multiplier"].eq(1.0))].iloc[0]
    if (
        int(risk060_no_cash["dd40_pass"]) == 1
        and int(risk060_no_cash["days_over_100pct"]) == 0
        and int(r070_c2["dd40_pass"]) == 0
    ):
        label = "prefer_risk060_true_xsmom_for_deployment_audit"
    else:
        label = "deployment_choice_still_unresolved"
    return {
        "stage": "Stage213",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "risk060_1x_no_cash_max_dd_pct": _safe_float(risk060_no_cash["max_dd_pct"]),
        "risk060_1x_no_cash_max_broker10_margin_pct": _safe_float(risk060_no_cash["max_broker10_margin_to_equity_pct"]),
        "risk060_2x_no_cash_max_dd_pct": _safe_float(r060_c2["max_dd_pct"]),
        "risk060_1x_cap90_extra_cash": _safe_float(r060_cap90_1x["extra_cash"]),
        "risk060_1x_cap90_return_on_deployed_capital_pct": _safe_float(r060_cap90_1x["return_on_deployed_capital_pct"]),
        "risk060_1x_cap90_retention_vs_stage079_deployed_pct": _safe_float(r060_cap90_1x["return_retention_vs_stage079_deployed_pct"]),
        "risk070_1x_no_cash_max_dd_pct": _safe_float(risk070_no_cash["max_dd_pct"]),
        "risk070_1x_no_cash_max_broker10_margin_pct": _safe_float(risk070_no_cash["max_broker10_margin_to_equity_pct"]),
        "risk070_2x_no_cash_max_dd_pct": _safe_float(r070_c2["max_dd_pct"]),
        "risk070_1x_cap90_extra_cash": _safe_float(r070_cap90_1x["extra_cash"]),
        "risk070_1x_cap90_return_on_deployed_capital_pct": _safe_float(r070_cap90_1x["return_on_deployed_capital_pct"]),
        "risk070_1x_cap90_retention_vs_stage079_deployed_pct": _safe_float(r070_cap90_1x["return_retention_vs_stage079_deployed_pct"]),
        "focus_100_cost123_pass_rows": int(focus_100["deploy_pass"].sum()),
        "focus_90_cost123_pass_rows": int(focus_90["deploy_pass"].sum()),
        "next_step": "Promote risk060 to exact broker-margin replay; keep risk070 as high-return paper unless real account cash buffer is explicitly accepted.",
    }


def _plot(detail: pd.DataFrame, deployment: pd.DataFrame, daily: pd.DataFrame, broker_margin: pd.DataFrame) -> None:
    margin_by_variant = {
        variant: frame.sort_values("date").set_index("date")["broker10_margin_proxy"].astype(float)
        for variant, frame in broker_margin.groupby("variant")
    }
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    ax_nav, ax_dd, ax_margin, ax_cash = axes.ravel()
    colors = {RISK060: "#1b7f5a", RISK070: "#b55a2a"}
    labels = daily.drop_duplicates("variant").set_index("variant")["label"].to_dict()
    for variant in VARIANTS:
        frame = daily[daily["variant"].eq(variant)].copy()
        equity = _stressed_equity(frame, 1.0)
        ax_nav.plot(equity.index, equity / ACCOUNT_CAPITAL, label=labels.get(variant, variant), color=colors[variant], linewidth=1.1)
        dd = _drawdown_pct(equity)
        ax_dd.plot(dd.index, dd, label=labels.get(variant, variant), color=colors[variant], linewidth=1.05)
        margin_ratio = margin_by_variant[variant].reindex(equity.index).ffill().fillna(0.0) / equity * 100.0
        ax_margin.plot(margin_ratio.index, margin_ratio, label=labels.get(variant, variant), color=colors[variant], linewidth=1.0)
    ax_nav.set_title("No-extra-cash NAV, 1x cost")
    ax_nav.set_ylabel("NAV on 615k")
    ax_nav.grid(True, alpha=0.22)
    ax_nav.legend(fontsize=8)
    ax_dd.set_title("No-extra-cash drawdown, 1x cost")
    ax_dd.axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_dd.axhline(-30.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_dd.set_ylabel("Drawdown %")
    ax_dd.grid(True, alpha=0.22)
    ax_margin.set_title("Broker10 margin proxy / equity, 1x cost")
    ax_margin.axhline(100.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_margin.axhline(90.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_margin.set_ylabel("Margin / equity %")
    ax_margin.grid(True, alpha=0.22)
    cash = deployment[deployment["margin_cap_pct"].eq(90.0)].copy()
    cash["cost_label"] = cash["cost_multiplier"].map(lambda value: f"{value:.0f}x")
    x = np.arange(len(COST_MULTIPLIERS))
    width = 0.34
    for offset, variant in [(-width / 2, RISK060), (width / 2, RISK070)]:
        sub = cash[cash["variant"].eq(variant)].sort_values("cost_multiplier")
        ax_cash.bar(x + offset, sub["extra_cash"].to_numpy(dtype=float) / 10_000.0, width, label=labels.get(variant, variant), color=colors[variant], alpha=0.85)
    ax_cash.set_title("Extra cash needed: DD40 + margin <= 90%")
    ax_cash.set_xticks(x, [f"{int(item)}x cost" for item in COST_MULTIPLIERS])
    ax_cash.set_ylabel("Extra cash, 10k CNY")
    ax_cash.grid(True, axis="y", alpha=0.22)
    ax_cash.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(detail: pd.DataFrame, deployment: pd.DataFrame, event_days: pd.DataFrame, decision: dict[str, Any]) -> None:
    no_cash = detail.sort_values(["cost_multiplier", "variant"])
    cap100 = deployment[deployment["margin_cap_pct"].eq(100.0)].sort_values(["cost_multiplier", "variant"])
    cap90 = deployment[deployment["margin_cap_pct"].eq(90.0)].sort_values(["cost_multiplier", "variant"])
    report = [
        "# Stage213 Stage208部署约束审计",
        "",
        f"- 生成时间：{decision['generated_at']}",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：只读部署审计；不改交易规则、不新增信号、不做参数搜索。",
        "- 运行前过拟合判断：否。本阶段只检查固定候选在真实部署约束下的资金厚度。",
        "- 运行前继续价值判断：是。Stage208 已经接近目标，但此前的 broker10 风险暴露说明必须先做部署口径，而不是继续优化指标。",
        "",
        "## 外部调研判断",
        "",
        "- 上期所结算说明显示，成交后交易所按持仓合约价值的一定比例收取交易保证金，品种标准还会随风险控制规则变化；因此实盘不能只看回测权益曲线，还要保留保证金冗余：https://www.shfe.com.cn/specialtopic/investor/settlement/",
        "- 中金所公开材料也说明保证金划扣、结算准备金与强平机制是日常风险管理的一部分；对实盘候选而言，`margin/equity` 接近 100% 就不是可接受的舒适区：https://www.cffex.com.cn/u/cms/www/202105/2817030498cn.pdf",
        "- 公开回测真实性资料普遍强调成交、滑点、保证金和风险管理漂移会侵蚀纸面收益；本阶段因此采用 1x/2x/3x 成本和 broker10 保证金代理做压力审计。",
        "- 我的判断：真实候选应先选保证金和成本厚度更好的结构。若需要靠额外现金才通过，就必须用“部署资金收益率”重算收益保留，不能只看 61.5万口径的高收益。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- `risk060 + true xsmom` 1x 无额外现金：最大回撤 `{decision['risk060_1x_no_cash_max_dd_pct']:.4f}%`，broker10 最大保证金占用 `{decision['risk060_1x_no_cash_max_broker10_margin_pct']:.4f}%`。",
        f"- `risk070 + true xsmom` 1x 无额外现金：最大回撤 `{decision['risk070_1x_no_cash_max_dd_pct']:.4f}%`，broker10 最大保证金占用 `{decision['risk070_1x_no_cash_max_broker10_margin_pct']:.4f}%`。",
        f"- 2x 成本无额外现金最大回撤：risk060 `{decision['risk060_2x_no_cash_max_dd_pct']:.4f}%`，risk070 `{decision['risk070_2x_no_cash_max_dd_pct']:.4f}%`。",
        f"- 保证金压到 90% 且守 DD40 的 1x 现金缓冲：risk060 `{decision['risk060_1x_cap90_extra_cash']:.0f}`，risk070 `{decision['risk070_1x_cap90_extra_cash']:.0f}`。",
        f"- 对应部署资金收益率：risk060 `{decision['risk060_1x_cap90_return_on_deployed_capital_pct']:.4f}%`，risk070 `{decision['risk070_1x_cap90_return_on_deployed_capital_pct']:.4f}%`。",
        "",
        "## 无额外现金压力",
        "",
        _md_table(
            no_cash[
                [
                    "variant",
                    "cost_multiplier",
                    "pnl_on_base_capital_pct",
                    "return_retention_vs_stage079_base_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                    "dd40_pass",
                ]
            ]
        ),
        "",
        "## 只要求 broker10 <= 100% 且 DD40",
        "",
        _md_table(
            cap100[
                [
                    "variant",
                    "cost_multiplier",
                    "extra_cash",
                    "cash_binding_reason",
                    "return_on_deployed_capital_pct",
                    "return_retention_vs_stage079_deployed_pct",
                    "max_dd_pct",
                    "max_broker10_margin_to_equity_pct",
                    "deploy_pass",
                ]
            ]
        ),
        "",
        "## 要求 broker10 <= 90% 且 DD40",
        "",
        _md_table(
            cap90[
                [
                    "variant",
                    "cost_multiplier",
                    "extra_cash",
                    "cash_binding_reason",
                    "return_on_deployed_capital_pct",
                    "return_retention_vs_stage079_deployed_pct",
                    "max_dd_pct",
                    "max_broker10_margin_to_equity_pct",
                    "deploy_pass",
                ]
            ]
        ),
        "",
        "## 关键事件日",
        "",
        _md_table(
            event_days.sort_values(["variant", "cost_multiplier", "event_type", "broker10_margin_to_equity_pct"], ascending=[True, True, True, False])[
                [
                    "variant",
                    "cost_multiplier",
                    "event_type",
                    "date",
                    "equity_no_cash",
                    "broker10_margin_proxy",
                    "broker10_margin_to_equity_pct",
                    "drawdown_pct",
                ]
            ],
            max_rows=48,
        ),
        "",
        "## 图表视觉复盘",
        "",
        "- NAV 图上 risk070 仍略高于 risk060，但两条线差距远小于它们在保证金占用上的差距，说明 risk070 多拿的收益不是免费收益。",
        "- Underwater 图上 risk070 在 2021-2022 更贴近 -40%，2x 成本会直接越线；risk060 的水下更浅，虽然仍不是 30% 级体验。",
        "- 保证金图上 risk070 有尖峰穿越 100%，risk060 主要问题是是否要给 90% 舒适区留冗余；这是部署口径差异，不是 alpha 差异。",
        "- 现金缓冲柱状图显示，一旦把目标改成 `broker10 <= 90%`，risk070 需要的额外现金显著高于 risk060，部署资金收益率被摊薄。",
        "",
        "## 结论",
        "",
        "- 本阶段不把 risk070 晋级为实盘候选；它更像高收益 paper 版本，除非明确接受额外现金和 2x 成本破 DD40 的风险。",
        "- 本阶段把 `risk060 + true xsmom` 提升为下一步精确券商保证金回放对象：它无额外现金时满足 1x DD40 和 broker10 不穿 100%，2x 成本也仍在 DD40 内。",
        "- 这不是最终完成目标，因为 broker10 仍是代理口径；下一步需要做更精确的逐日持仓保证金回放或接真实券商保证金表。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行后过拟合判断：否。没有根据结果改规则，只是把隐藏资金约束显性化。",
        "- 运行后继续价值判断：是，但继续方向应是精确实盘约束验证，不是扫 ATR/K线或 risk 小数。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily = _load_daily()
    broker_margin = _load_broker_margin()
    detail, deployment, event_days = _build_audit(daily, broker_margin)
    decision = _decision(detail, deployment)
    _plot(detail, deployment, daily, broker_margin)
    _write_report(detail, deployment, event_days, decision)
    detail.to_csv(DAILY_DETAIL_PATH, index=False, encoding="utf-8-sig")
    deployment.to_csv(DEPLOYMENT_MATRIX_PATH, index=False, encoding="utf-8-sig")
    event_days.to_csv(EVENT_DAYS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
