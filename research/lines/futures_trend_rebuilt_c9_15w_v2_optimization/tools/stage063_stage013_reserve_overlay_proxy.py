from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage063"
MODEL_TAG = "stage063_stage013_reserve_overlay_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage063_stage013_reserve_overlay_proxy"

BASE_CAPITAL = 150_000.0
RESERVE_AMOUNTS = (0.0, 50_000.0, 100_000.0, 150_000.0)
MIN_START_MONTH = "2021-07"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage063_stage013_reserve_overlay_proxy"
STAGES_DIR = LINE_DIR / "stages"

STAGE062_OUT = LINE_DIR / "outputs" / "stage062_stage013_full_monthly_ai_candidate_official"
CURVES_PATH = (
    STAGE062_OUT
    / "rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_stage013_curves_stage062_stage013_full_monthly_ai_candidate_official_v1.csv.gz"
)
SUMMARY_PATH = (
    STAGE062_OUT
    / "rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_stage013_summary_stage062_stage013_full_monthly_ai_candidate_official_v1.csv"
)

RESERVE_CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_reserve_curves_{MODEL_TAG}.csv.gz"
START_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_start_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
REQUIRED_RESERVE_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_required_reserve_by_start_{MODEL_TAG}.png"
WEAK_START_NAV_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_weak_start_total_nav_{MODEL_TAG}.png"
BROKER_TOPUP_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_broker_topup_proxy_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    return value


def _drawdown_pct(values: pd.Series) -> pd.Series:
    series = pd.to_numeric(values, errors="coerce").ffill()
    peak = series.cummax()
    return (series / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _load_stage062_curves() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not CURVES_PATH.exists():
        raise FileNotFoundError(CURVES_PATH)
    curves = pd.read_csv(CURVES_PATH)
    summary = pd.read_csv(SUMMARY_PATH)
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    summary["requested_start_month"] = summary["requested_start_month"].astype(str)
    curves = curves[curves["requested_start_month"].ge(MIN_START_MONTH)].copy()
    summary = summary[summary["requested_start_month"].ge(MIN_START_MONTH)].copy()
    curves["account_equity"] = pd.to_numeric(curves["account_equity"], errors="coerce")
    curves = curves.dropna(subset=["date", "account_equity"])
    return curves, summary


def _topup_account_proxy(equity: pd.Series, reserve: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    pnl = pd.to_numeric(equity, errors="coerce").diff().fillna(pd.to_numeric(equity, errors="coerce").iloc[0] - BASE_CAPITAL)
    account = BASE_CAPITAL
    reserve_left = reserve
    account_values: list[float] = []
    reserve_values: list[float] = []
    injected_values: list[float] = []
    cumulative_injected = 0.0
    for value in pnl:
        account += float(value)
        if account < BASE_CAPITAL and reserve_left > 0.0:
            inject = min(BASE_CAPITAL - account, reserve_left)
            account += inject
            reserve_left -= inject
            cumulative_injected += inject
        account_values.append(account)
        reserve_values.append(reserve_left)
        injected_values.append(cumulative_injected)
    index = equity.index
    return (
        pd.Series(account_values, index=index),
        pd.Series(reserve_values, index=index),
        pd.Series(injected_values, index=index),
    )


def build_reserve_overlay() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    OUT.mkdir(parents=True, exist_ok=True)
    curves, summary = _load_stage062_curves()
    curve_frames: list[pd.DataFrame] = []
    start_rows: list[dict[str, Any]] = []
    variant_rows: list[dict[str, Any]] = []

    for start, group in curves.groupby("requested_start_month", sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        equity = group["account_equity"]
        min_equity = float(equity.min())
        required_reserve = max(0.0, BASE_CAPITAL - min_equity)
        below_base = equity.lt(BASE_CAPITAL)
        first_below = group.loc[below_base, "date"].min() if below_base.any() else pd.NaT
        last_below = group.loc[below_base, "date"].max() if below_base.any() else pd.NaT
        start_rows.append(
            {
                "requested_start_month": start,
                "actual_start": group["date"].iloc[0].date().isoformat(),
                "actual_end": group["date"].iloc[-1].date().isoformat(),
                "end_equity": float(equity.iloc[-1]),
                "strategy_return_pct": float((equity.iloc[-1] / BASE_CAPITAL - 1.0) * 100.0),
                "min_equity": min_equity,
                "required_reserve_to_keep_broker_equity_ge_150k": required_reserve,
                "days_below_150k": int(below_base.sum()),
                "first_below_150k": first_below.date().isoformat() if pd.notna(first_below) else "",
                "last_below_150k": last_below.date().isoformat() if pd.notna(last_below) else "",
            }
        )
        for reserve in RESERVE_AMOUNTS:
            total_initial = BASE_CAPITAL + reserve
            idle_total_equity = equity + reserve
            idle_total_nav = idle_total_equity / total_initial
            idle_total_dd = _drawdown_pct(idle_total_equity)
            topup_account, reserve_left, injected = _topup_account_proxy(equity, reserve)
            topup_broker_nav = topup_account / BASE_CAPITAL
            topup_total_nav = (topup_account + reserve_left) / total_initial
            frame = group[["date", "requested_start_month", "days_since_start"]].copy()
            frame["reserve_amount"] = reserve
            frame["reserve_label"] = f"reserve_{int(reserve)}"
            frame["strategy_equity"] = equity
            frame["strategy_nav"] = equity / BASE_CAPITAL
            frame["idle_total_equity"] = idle_total_equity
            frame["idle_total_nav"] = idle_total_nav
            frame["idle_total_drawdown_pct"] = idle_total_dd
            frame["topup_broker_equity_proxy"] = topup_account
            frame["topup_broker_nav_proxy"] = topup_broker_nav
            frame["reserve_remaining_proxy"] = reserve_left
            frame["reserve_injected_proxy"] = injected
            frame["topup_total_nav_proxy"] = topup_total_nav
            frame["topup_reserve_exhausted"] = reserve_left.le(0.0).astype(int)
            curve_frames.append(frame)
            variant_rows.append(
                {
                    "requested_start_month": start,
                    "reserve_amount": reserve,
                    "reserve_label": f"reserve_{int(reserve)}",
                    "total_initial_capital": total_initial,
                    "idle_total_end_nav": float(idle_total_nav.iloc[-1]),
                    "idle_total_return_pct": float((idle_total_nav.iloc[-1] - 1.0) * 100.0),
                    "idle_total_max_drawdown_pct": float(idle_total_dd.min()),
                    "idle_total_days_underwater": int(idle_total_nav.lt(1.0).sum()),
                    "topup_broker_min_nav_proxy": float(topup_broker_nav.min()),
                    "topup_total_end_nav_proxy": float(topup_total_nav.iloc[-1]),
                    "topup_total_return_pct_proxy": float((topup_total_nav.iloc[-1] - 1.0) * 100.0),
                    "topup_reserve_used_proxy": float(injected.iloc[-1]),
                    "topup_reserve_remaining_proxy": float(reserve_left.iloc[-1]),
                    "topup_reserve_exhausted_days_proxy": int(reserve_left.le(0.0).sum()),
                }
            )

    reserve_curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    start_summary = pd.DataFrame(start_rows)
    variant_detail = pd.DataFrame(variant_rows)
    aggregate = (
        variant_detail.groupby(["reserve_amount", "reserve_label"], as_index=False)
        .agg(
            start_count=("requested_start_month", "nunique"),
            positive_total_return_count=("idle_total_return_pct", lambda s: int(pd.to_numeric(s).gt(0.0).sum())),
            min_total_return_pct=("idle_total_return_pct", "min"),
            median_total_return_pct=("idle_total_return_pct", "median"),
            max_total_return_pct=("idle_total_return_pct", "max"),
            worst_total_max_drawdown_pct=("idle_total_max_drawdown_pct", "min"),
            median_total_max_drawdown_pct=("idle_total_max_drawdown_pct", "median"),
            max_days_underwater=("idle_total_days_underwater", "max"),
            median_days_underwater=("idle_total_days_underwater", "median"),
            max_required_topup_used_proxy=("topup_reserve_used_proxy", "max"),
            starts_with_proxy_reserve_exhausted=("topup_reserve_exhausted_days_proxy", lambda s: int(pd.to_numeric(s).gt(0).sum())),
        )
        .reset_index(drop=True)
    )
    reserve_curves.to_csv(RESERVE_CURVES_PATH, index=False, encoding="utf-8-sig")
    start_summary.to_csv(START_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_curves": str(CURVES_PATH),
        "source_summary": str(SUMMARY_PATH),
        "min_start_month": MIN_START_MONTH,
        "base_capital": BASE_CAPITAL,
        "reserve_amounts": list(RESERVE_AMOUNTS),
        "start_count": int(start_summary["requested_start_month"].nunique()),
        "max_required_reserve_to_keep_broker_equity_ge_150k": float(
            start_summary["required_reserve_to_keep_broker_equity_ge_150k"].max()
        ),
        "worst_required_reserve_start": str(
            start_summary.loc[
                start_summary["required_reserve_to_keep_broker_equity_ge_150k"].idxmax(),
                "requested_start_month",
            ]
        ),
        "aggregate": aggregate.to_dict(orient="records"),
        "candidate_interpretation": (
            "Idle reserve improves whole-account drawdown by dilution, not by alpha. Top-up proxy can keep broker "
            "equity near 150k until reserve is exhausted, but a true effect on later position sizing requires a "
            "real-engine cashflow rerun."
        ),
        "overfit_reflection_before": (
            "否。本阶段预先固定 reserve=0/5/10/15 万，只做部署层资金口径，不按单个亏损窗口调参。"
        ),
        "overfit_reflection_after": (
            "否。结果用于判断账户容量和后续真引擎必要性；若按 22/23 特定谷底反推精确入金日和金额才会过拟合。"
        ),
        "continue_value_before": (
            "有。用户实际资金超过 15 万，储备金是实盘部署层真实约束，不是编造收益。"
        ),
        "continue_value_after": (
            "有。代理显示外部储备金能显著降低总资金回撤/水下体感，但不能证明策略 alpha；下一步若要交易化，需要真引擎 cashflow。"
        ),
        "strategy_changed": False,
        "official_live_config_changed": False,
        "true_engine_rerun": False,
        "order_api_called": False,
        "ctp_connected": False,
        "outputs": {
            "reserve_curves": str(RESERVE_CURVES_PATH),
            "start_summary": str(START_SUMMARY_PATH),
            "variant_summary": str(VARIANT_SUMMARY_PATH),
            "required_reserve_chart": str(REQUIRED_RESERVE_CHART_PATH),
            "weak_start_nav_chart": str(WEAK_START_NAV_CHART_PATH),
            "broker_topup_chart": str(BROKER_TOPUP_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return reserve_curves, start_summary, aggregate, decision


def _plot_outputs(reserve_curves: pd.DataFrame, start_summary: pd.DataFrame) -> None:
    starts = start_summary.sort_values("requested_start_month")
    fig, ax = plt.subplots(figsize=(16, 7), constrained_layout=True)
    colors = np.where(starts["required_reserve_to_keep_broker_equity_ge_150k"].gt(50_000.0), "#dc2626", "#2563eb")
    ax.bar(
        starts["requested_start_month"],
        starts["required_reserve_to_keep_broker_equity_ge_150k"],
        color=colors,
    )
    ax.axhline(50_000.0, color="#f97316", linestyle="--", linewidth=0.9, label="50k reserve")
    ax.axhline(100_000.0, color="#16a34a", linestyle="--", linewidth=0.9, label="100k reserve")
    ax.axhline(150_000.0, color="#111827", linestyle="--", linewidth=0.9, label="150k reserve")
    ax.set_title("Stage063 Required Reserve To Keep Broker Equity >= 150k")
    ax.set_ylabel("reserve required")
    ax.tick_params(axis="x", rotation=35)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="best")
    fig.savefig(REQUIRED_RESERVE_CHART_PATH, dpi=160)
    plt.close(fig)

    weak_starts = ["2022-01", "2023-01", "2026-01"]
    labels = {
        0.0: "no reserve",
        50_000.0: "reserve 50k",
        100_000.0: "reserve 100k",
        150_000.0: "reserve 150k",
    }
    fig, axes = plt.subplots(len(weak_starts), 1, figsize=(18, 11), sharex=False, constrained_layout=True)
    for ax, start in zip(np.array(axes).reshape(-1), weak_starts):
        subset = reserve_curves[reserve_curves["requested_start_month"].eq(start)].copy()
        for reserve in RESERVE_AMOUNTS:
            group = subset[subset["reserve_amount"].eq(reserve)].sort_values("date")
            if group.empty:
                continue
            ax.plot(group["date"], group["idle_total_nav"], linewidth=1.2, label=labels[reserve])
        ax.axhline(1.0, color="#111827", linestyle="--", linewidth=0.8)
        ax.set_title(f"{start} total NAV with idle reserve")
        ax.set_ylabel("total NAV")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    axes[-1].set_xlabel("date")
    fig.savefig(WEAK_START_NAV_CHART_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(len(weak_starts), 1, figsize=(18, 11), sharex=False, constrained_layout=True)
    for ax, start in zip(np.array(axes).reshape(-1), weak_starts):
        subset = reserve_curves[
            reserve_curves["requested_start_month"].eq(start) & reserve_curves["reserve_amount"].eq(150_000.0)
        ].sort_values("date")
        if subset.empty:
            continue
        ax.plot(subset["date"], subset["strategy_nav"], linewidth=1.0, label="original broker NAV", color="#dc2626")
        ax.plot(
            subset["date"],
            subset["topup_broker_nav_proxy"],
            linewidth=1.1,
            label="top-up broker NAV proxy, reserve 150k",
            color="#2563eb",
        )
        ax.plot(
            subset["date"],
            subset["reserve_remaining_proxy"] / 150_000.0,
            linewidth=1.0,
            label="reserve remaining / 150k",
            color="#16a34a",
        )
        ax.axhline(1.0, color="#111827", linestyle="--", linewidth=0.8)
        ax.set_title(f"{start} broker top-up proxy with 150k reserve")
        ax.set_ylabel("ratio")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=8, loc="best")
    axes[-1].set_xlabel("date")
    fig.savefig(BROKER_TOPUP_CHART_PATH, dpi=160)
    plt.close(fig)


def _md_table(frame: pd.DataFrame) -> str:
    return frame.to_markdown(index=False) if not frame.empty else "_empty_"


def write_report_and_record(decision: dict[str, Any], start_summary: pd.DataFrame, aggregate: pd.DataFrame) -> Path:
    now = datetime.now()
    weak = start_summary[
        start_summary["requested_start_month"].isin(["2022-01", "2023-01", "2026-01"])
    ].copy()
    lines = [
        "# Stage063 Stage013 reserve overlay proxy",
        "",
        f"- generated_at: `{decision['generated_at']}`",
        f"- line_id: `{LINE_ID}`",
        f"- source curves: `{CURVES_PATH}`",
        f"- min_start_month: `{MIN_START_MONTH}`",
        f"- base capital: `{BASE_CAPITAL:,.0f}`",
        f"- reserve amounts: `{', '.join(f'{x:,.0f}' for x in RESERVE_AMOUNTS)}`",
        "",
        "## Judgment",
        "",
        "- Early loss does make recovery harder because account-equity based sizing naturally shrinks future absolute exposure.",
        "- Idle reserve reduces whole-account drawdown by dilution, but also dilutes return.",
        "- Top-up reserve can preserve broker account capacity, but this proxy does not model larger future positions; true validation needs engine-level cashflow.",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate),
        "",
        "## Weak Starts",
        "",
        _md_table(
            weak[
                [
                    "requested_start_month",
                    "strategy_return_pct",
                    "min_equity",
                    "required_reserve_to_keep_broker_equity_ge_150k",
                    "days_below_150k",
                    "first_below_150k",
                    "last_below_150k",
                ]
            ]
        ),
        "",
        "## Decision",
        "",
        "- decision: `reserve_overlay_proxy_useful_but_not_alpha`",
        "- next: if user wants live deployment, implement deterministic engine-level cashflow: keep 150k trading sleeve, reserve outside, top up at month-end or next-session after close only when broker equity < 150k.",
        "",
        "## Outputs",
        "",
    ]
    for key, value in decision["outputs"].items():
        lines.append(f"- {key}: `{value}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGES_DIR / f"{now.strftime('%Y%m%d_%H%M')}_stage063_stage013_reserve_overlay_proxy.md"
    stage_lines = [
        "# Stage063 Stage013 储备金部署层代理测算",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{now.isoformat(timespec='seconds')}",
        "- 阶段性质：只读部署层代理测算；不回测、不改策略、不连接 CTP、不调用下单",
        "- 是否重要突破：否；提供储备金方向的账户容量判断",
        "- 是否触发A/B：否；这不是新 alpha，只是资金部署层",
        "",
        "## 外部调研与判断",
        "",
        "- 参考 pysystemtrade capital correction、TWR 出入金口径和既有 Stage042 现金流边界。判断：储备金可以做账户容量/追加保证金/水下体验治理，但不能计入策略收益。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改脚本：无",
        "- 删除脚本：无",
        "- 新增参数：`reserve_amounts=0/50000/100000/150000`，`base_capital=150000`",
        "- 修改参数：无正式策略参数修改",
        "- 删除参数：无",
        "",
        "## 结果",
        "",
        f"- 起点：`{MIN_START_MONTH}` 及以后，共 `{decision['start_count']}` 个启动点",
        f"- 最大需要储备金才能让代理 broker equity 不低于 15 万：`{decision['max_required_reserve_to_keep_broker_equity_ge_150k']:.2f}`，起点 `{decision['worst_required_reserve_start']}`",
        "- 聚合结果见 variant summary；弱启动点见 start summary。",
        "- 真引擎：未跑；本阶段不改变后续仓位大小，因此只能作为下界/口径测算。",
        "",
        "## 结论",
        "",
        "- 储备金逻辑有现实价值，但要拆成“总资金口径”和“交易账户补资口径”。",
        "- 如果只把备用金放在外面，总资金回撤会变小但收益也被稀释。",
        "- 如果要让回本更快，必须在真实引擎里让补资影响后续 sizing；本阶段代理不能证明这一点。",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
    ]
    stage_path.write_text("\n".join(stage_lines) + "\n", encoding="utf-8")
    return stage_path


def main() -> None:
    curves, start_summary, aggregate, decision = build_reserve_overlay()
    _plot_outputs(curves, start_summary)
    stage_path = write_report_and_record(decision, start_summary, aggregate)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"stage_record: {stage_path}", flush=True)
    print(f"report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
