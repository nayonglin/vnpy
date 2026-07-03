#!/usr/bin/env python3
"""Stage057: capped quality + contract OI combo proxy curves.

This is the smallest valid follow-up to Stage056. It turns frozen lot-level
overlap findings into start-month curves, while staying a closed-lot proxy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
LINE = ROOT / "research/lines" / LINE_ID
UPSTREAM_LINE = ROOT / "research/lines" / UPSTREAM_LINE_ID
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage056_combination_overlap_audit as s056  # noqa: E402


OUT = LINE / "outputs/stage057_capped_quality_oi_combo_proxy"
MODEL_TAG = "stage057_capped_quality_oi_combo_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage057_capped_quality_oi_combo_proxy"
END_DATE = pd.Timestamp("2026-06-30")
CAPITAL = 150_000.0
RUN_NOW = datetime.now()
RUN_TS = RUN_NOW.strftime("%Y%m%d_%H%M")
RUN_TIME_LABEL = RUN_NOW.strftime("%Y-%m-%d %H:%M CST")
STAGE_RECORD = LINE / "stages" / f"{RUN_TS}_stage057_capped_quality_oi_combo_proxy.md"

STAGE013_CURVES = (
    UPSTREAM_LINE
    / "outputs/stage013_account_state_pilot_gate_engine/"
    / "rebuilt_c9_stage013_account_state_pilot_gate_engine_curves_stage013_account_state_pilot_gate_engine_v1.csv"
)
OFFICIAL_CURVES = (
    UPSTREAM_LINE
    / "outputs/stage006_current_quality_feature_binder/"
    / "rebuilt_c9_stage006_current_quality_feature_binder_curves_stage006_current_quality_feature_binder_v1.csv"
)

COMBO_EVENT_DELTAS_PATH = OUT / f"{OUTPUT_PREFIX}_combo_event_deltas_{MODEL_TAG}.csv.gz"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
PER_START_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_summary_{MODEL_TAG}.csv"
VERSION_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_version_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_absolute_equity_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class ComboSpec:
    variant: str
    modules: tuple[str, ...]
    method: str
    cap_fraction: float
    note: str


COMBO_SPECS: tuple[ComboSpec, ...] = (
    ComboSpec(
        variant="stage057_stage010_plus_oi_sum_cap50",
        modules=("stage010_quality_25pct", "stage052_contract_oi_share_ge50_25pct"),
        method="sum_cap",
        cap_fraction=0.50,
        note="Stage010 broad quality 与 OI share 组合；质量侧 overlap 最高，仅作上界参考。",
    ),
    ComboSpec(
        variant="stage057_stage013_plus_oi_sum_cap50",
        modules=("stage013_guarded_quality_25pct", "stage052_contract_oi_share_ge50_25pct"),
        method="sum_cap",
        cap_fraction=0.50,
        note="Stage013 guarded quality 与 OI share 组合，单笔事件加风险上限 50%。",
    ),
    ComboSpec(
        variant="stage057_stage014_floor_plus_oi_sum_cap50",
        modules=("stage014_guarded_floor_integer", "stage052_contract_oi_share_ge50_25pct"),
        method="sum_cap",
        cap_fraction=0.50,
        note="Stage014 floor integer 与 OI share 组合，偏保守可实现口径。",
    ),
    ComboSpec(
        variant="stage057_stage014_ceil_plus_oi_sum_cap50",
        modules=("stage014_guarded_ceil_integer", "stage052_contract_oi_share_ge50_25pct"),
        method="sum_cap",
        cap_fraction=0.50,
        note="Stage014 ceil integer 与 OI share 组合；ceil 小手数超配风险仍保留警告。",
    ),
    ComboSpec(
        variant="stage057_stage022_xsmom_plus_oi_sum_cap50",
        modules=("stage022_guarded_xsmom12_not_opposed_25pct", "stage052_contract_oi_share_ge50_25pct"),
        method="sum_cap",
        cap_fraction=0.50,
        note="Stage022 xsmom-confirmed quality 与 OI share 组合，质量侧更窄。",
    ),
    ComboSpec(
        variant="stage057_stage014_floor_or_oi_max25",
        modules=("stage014_guarded_floor_integer", "stage052_contract_oi_share_ge50_25pct"),
        method="max",
        cap_fraction=0.25,
        note="两者只取更强的一层，避免任何单笔叠加。",
    ),
    ComboSpec(
        variant="stage057_stage022_xsmom_or_oi_max25",
        modules=("stage022_guarded_xsmom12_not_opposed_25pct", "stage052_contract_oi_share_ge50_25pct"),
        method="max",
        cap_fraction=0.25,
        note="xsmom 确认质量与 OI 只取一层，最保守组合。",
    ),
)


def _json_safe(value: Any) -> Any:
    return s056._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int = 20) -> str:
    return s056._md_table(frame, max_rows=max_rows)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    values = pd.to_numeric(equity, errors="coerce").dropna()
    returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or float(returns.std(ddof=1)) == 0.0:
        return 0.0
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(252.0))


def build_combo_event_deltas(events: pd.DataFrame, spec: ComboSpec) -> pd.DataFrame:
    pieces = events[events["module"].isin(spec.modules)].copy()
    rows: list[dict[str, Any]] = []
    for event_key, g in pieces.groupby("event_key", sort=False):
        g = g.sort_values("module").copy()
        fractions = pd.to_numeric(g["add_fraction"], errors="coerce").fillna(0.0)
        raw_sum = float(fractions.sum())
        raw_max = float(fractions.max())
        if spec.method == "sum_cap":
            combo_fraction = min(raw_sum, spec.cap_fraction)
        elif spec.method == "max":
            combo_fraction = min(raw_max, spec.cap_fraction)
        else:
            raise ValueError(f"unknown combo method: {spec.method}")
        first = g.iloc[0]
        realized_pnl = float(pd.to_numeric(g["realized_pnl"], errors="coerce").dropna().iloc[0])
        rows.append(
            {
                "variant": spec.variant,
                "event_key": event_key,
                "requested_start_month": str(first["requested_start_month"]),
                "entry_date": pd.Timestamp(first["entry_date"]),
                "exit_date": pd.Timestamp(first["exit_date"]),
                "vt_symbol": str(first["vt_symbol"]),
                "product": str(first["product"]),
                "direction": str(first["direction"]),
                "module_count": int(g["module"].nunique()),
                "modules": ",".join(spec.modules),
                "method": spec.method,
                "cap_fraction": float(spec.cap_fraction),
                "raw_fraction_sum": raw_sum,
                "raw_fraction_max": raw_max,
                "combo_fraction": float(combo_fraction),
                "realized_pnl": realized_pnl,
                "combo_delta_pnl": realized_pnl * combo_fraction,
                "note": spec.note,
            }
        )
    return pd.DataFrame(rows)


def build_all_combo_event_deltas(events: pd.DataFrame, specs: tuple[ComboSpec, ...] = COMBO_SPECS) -> pd.DataFrame:
    frames = [build_combo_event_deltas(events, spec) for spec in specs]
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def load_stage013_base_curves() -> pd.DataFrame:
    df = _read_csv(STAGE013_CURVES, usecols=["requested_start_month", "date", "account_equity"])
    df["variant"] = "stage013_account_state_pilot_base"
    df["source_type"] = "true_engine_base"
    return _normalize_curve_frame(df, "account_equity")


def load_official_curves() -> pd.DataFrame:
    df = _read_csv(OFFICIAL_CURVES, usecols=["requested_start_month", "date", "account_equity"])
    df["variant"] = "official_c9_15w_stage847"
    df["source_type"] = "formal_baseline_true_engine"
    return _normalize_curve_frame(df, "account_equity")


def _normalize_curve_frame(df: pd.DataFrame, equity_col: str) -> pd.DataFrame:
    result = df.copy()
    result["requested_start_month"] = result["requested_start_month"].astype(str)
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result["equity"] = pd.to_numeric(result[equity_col], errors="coerce")
    result = result.dropna(subset=["date", "equity"])
    result = result[result["date"] <= END_DATE].copy()
    return result[["variant", "source_type", "requested_start_month", "date", "equity"]].sort_values(
        ["variant", "requested_start_month", "date"]
    )


def build_proxy_curves(base_curves: pd.DataFrame, combo_deltas: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    base = base_curves[base_curves["variant"].eq("stage013_account_state_pilot_base")].copy()
    if base.empty:
        raise ValueError("stage013 base curves are empty")
    delta = combo_deltas.copy()
    delta["exit_date"] = pd.to_datetime(delta["exit_date"], errors="coerce").dt.normalize()
    daily = (
        delta.groupby(["variant", "requested_start_month", "exit_date"], dropna=False)["combo_delta_pnl"]
        .sum()
        .reset_index()
    )
    curve_dates = set(zip(base["requested_start_month"].astype(str), base["date"]))
    unmatched = int(
        sum(
            1
            for row in daily.itertuples(index=False)
            if (str(row.requested_start_month), pd.Timestamp(row.exit_date)) not in curve_dates
        )
    )
    frames: list[pd.DataFrame] = []
    for variant, d in daily.groupby("variant", sort=True):
        merged = base.merge(
            d.rename(columns={"exit_date": "date", "combo_delta_pnl": "daily_delta"})[
                ["requested_start_month", "date", "daily_delta"]
            ],
            on=["requested_start_month", "date"],
            how="left",
        )
        merged["daily_delta"] = pd.to_numeric(merged["daily_delta"], errors="coerce").fillna(0.0)
        parts = []
        for _, g in merged.groupby("requested_start_month", sort=True):
            local = g.sort_values("date").copy()
            local["cum_delta"] = local["daily_delta"].cumsum()
            local["equity"] = local["equity"] + local["cum_delta"]
            parts.append(local)
        curve = pd.concat(parts, ignore_index=True, sort=False)
        curve["variant"] = variant
        curve["source_type"] = "closed_lot_capped_combo_proxy"
        frames.append(curve[["variant", "source_type", "requested_start_month", "date", "equity", "daily_delta", "cum_delta"]])
    return pd.concat(frames, ignore_index=True, sort=False), unmatched


def summarize_curves(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    for (variant, source_type, start), g in curves.groupby(["variant", "source_type", "requested_start_month"], sort=False):
        g = g.sort_values("date")
        equity = pd.to_numeric(g["equity"], errors="coerce")
        rows.append(
            {
                "variant": variant,
                "source_type": source_type,
                "requested_start_month": start,
                "start_date": g["date"].iloc[0].date().isoformat(),
                "end_date": g["date"].iloc[-1].date().isoformat(),
                "trading_days": int(len(g)),
                "start_equity": float(equity.iloc[0]),
                "end_equity": float(equity.iloc[-1]),
                "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
                "max_drawdown_pct": float(_drawdown_pct(equity).min()),
                "sharpe": _sharpe_from_equity(equity),
            }
        )
    per_start = pd.DataFrame(rows)
    official = per_start[per_start["variant"].eq("official_c9_15w_stage847")][
        ["requested_start_month", "end_equity", "total_return_pct", "max_drawdown_pct"]
    ].rename(
        columns={
            "end_equity": "official_end_equity",
            "total_return_pct": "official_total_return_pct",
            "max_drawdown_pct": "official_max_drawdown_pct",
        }
    )
    per_start = per_start.merge(official, on="requested_start_month", how="left")
    per_start["return_diff_vs_official_pp"] = per_start["total_return_pct"] - per_start["official_total_return_pct"]
    per_start["end_equity_ratio_vs_official"] = per_start["end_equity"] / per_start["official_end_equity"]
    per_start["maxdd_diff_vs_official_pp"] = per_start["max_drawdown_pct"] - per_start["official_max_drawdown_pct"]

    version_rows: list[dict[str, Any]] = []
    for (variant, source_type), g in per_start.groupby(["variant", "source_type"], sort=False):
        comparable = g.dropna(subset=["official_total_return_pct"])
        version_rows.append(
            {
                "variant": variant,
                "source_type": source_type,
                "start_count": int(g["requested_start_month"].nunique()),
                "positive_start_count": int((g["total_return_pct"] > 0).sum()),
                "win_vs_official_count": int((comparable["return_diff_vs_official_pp"] > 0).sum()),
                "min_total_return_pct": float(g["total_return_pct"].min()),
                "median_total_return_pct": float(g["total_return_pct"].median()),
                "max_total_return_pct": float(g["total_return_pct"].max()),
                "worst_max_drawdown_pct": float(g["max_drawdown_pct"].min()),
                "median_max_drawdown_pct": float(g["max_drawdown_pct"].median()),
                "min_end_equity": float(g["end_equity"].min()),
                "median_end_equity": float(g["end_equity"].median()),
                "min_end_equity_ratio_vs_official": float(comparable["end_equity_ratio_vs_official"].min())
                if len(comparable)
                else np.nan,
                "median_end_equity_ratio_vs_official": float(comparable["end_equity_ratio_vs_official"].median())
                if len(comparable)
                else np.nan,
            }
        )
    version_summary = pd.DataFrame(version_rows).sort_values(
        ["win_vs_official_count", "min_total_return_pct", "median_total_return_pct"],
        ascending=[False, False, False],
    )
    return per_start.sort_values(["variant", "requested_start_month"]).reset_index(drop=True), version_summary.reset_index(drop=True)


def plot_absolute_equity(curves: pd.DataFrame) -> None:
    plot_variants = [
        "official_c9_15w_stage847",
        "stage013_account_state_pilot_base",
        "stage057_stage010_plus_oi_sum_cap50",
        "stage057_stage014_ceil_plus_oi_sum_cap50",
        "stage057_stage022_xsmom_plus_oi_sum_cap50",
    ]
    data = curves[curves["variant"].isin(plot_variants)].copy()
    start_order = sorted(data["requested_start_month"].unique())
    ncols = 3
    nrows = int(np.ceil(len(start_order) / ncols))
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(18, max(4, nrows * 3.4)), sharex=False)
    flat_axes = np.array(axes).reshape(-1)
    for ax, start in zip(flat_axes, start_order):
        local = data[data["requested_start_month"].eq(start)].sort_values("date")
        for variant, g in local.groupby("variant", sort=False):
            ax.plot(g["date"], g["equity"], linewidth=1.15, label=variant.replace("stage057_", "S57 "))
        ax.set_title(start)
        ax.grid(True, alpha=0.25)
        ax.tick_params(axis="x", labelrotation=30)
    for ax in flat_axes[len(start_order) :]:
        ax.axis("off")
    handles, labels = flat_axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, fontsize=8)
    fig.suptitle("Stage057 capped quality + OI combo proxy absolute equity", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def build_decision(
    combo_deltas: pd.DataFrame,
    per_start: pd.DataFrame,
    version_summary: pd.DataFrame,
    unmatched_delta_dates: int,
) -> dict[str, Any]:
    proxy_only = version_summary[version_summary["source_type"].eq("closed_lot_capped_combo_proxy")].copy()
    best = proxy_only.iloc[0].to_dict() if not proxy_only.empty else {}
    promoted = False
    reason = "proxy_only_needs_true_engine_ab"
    return {
        "stage": "Stage057",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "run_time": RUN_TIME_LABEL,
        "baseline": "Official C9/15w Stage847 formal baseline; Stage013 base is only the proxy construction base.",
        "hypothesis": "Stage056 显示 OI 自身仍有独立事件，因此用单笔 capped risk budget 检查质量+OI 组合路径，而不是裸叠同源质量链。",
        "overfit_reflection_before": "否。组合 arms 来自 Stage056 预声明事件集合与统一 cap，不按坏窗口、品种、方向或小阈值救参。",
        "continued_value_before": "是。若 capped proxy 连路径都不改善，就不需要进真实引擎；若改善，再做一次真实引擎 A/B。",
        "combo_event_rows": int(len(combo_deltas)),
        "unmatched_delta_dates": int(unmatched_delta_dates),
        "best_proxy_variant": best.get("variant"),
        "best_proxy_win_vs_official_count": best.get("win_vs_official_count"),
        "best_proxy_min_total_return_pct": best.get("min_total_return_pct"),
        "best_proxy_median_total_return_pct": best.get("median_total_return_pct"),
        "best_proxy_worst_max_drawdown_pct": best.get("worst_max_drawdown_pct"),
        "decision": "no_promotion_closed_lot_proxy",
        "promoted": promoted,
        "reason": reason,
        "next_step": "if_user_approves_run_true_engine_ab_for_one_capped_combo_only",
        "overfit_reflection_after": "否。没有新增条件，只比较预声明 capped arms；但它仍是 closed-lot proxy，存在执行反馈和保证金路径偏差。",
        "continued_value_after": "是，但只值得推进一个最强且机制可解释的 capped arm 到真实引擎；不继续扫 cap、topN、floor/ceil 细节。",
        "orders_api_called": 0,
        "ctp_connected": False,
        "live_or_email_touched": False,
    }


def write_report(
    combo_deltas: pd.DataFrame,
    per_start: pd.DataFrame,
    version_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    text = f"""# Stage057 capped quality + OI 组合 proxy 曲线审计

- 运行时间：{RUN_TIME_LABEL}
- 研究线：`{LINE_ID}`
- 基准：正式基准仍为 `official_c9_15w_stage847`；`stage013_account_state_pilot_base` 只是 closed-lot proxy 的构造母本。
- 本阶段性质：只读 proxy 曲线，不是正式回测、不触发真实引擎、订单 API、CTP、邮件或 launchd。
- 外部调研判断：二级 sizing/组合应先统一风险预算，避免相关信号裸叠；趋势策略优化不能牺牲跨市场右尾。

## 版本汇总

{_md_table(version_summary, 30)}

## combo event delta 汇总

{_md_table(combo_deltas.groupby("variant").agg(event_count=("event_key", "nunique"), overlap_event_count=("module_count", lambda s: int((s > 1).sum())), total_delta_pnl=("combo_delta_pnl", "sum"), mean_combo_fraction=("combo_fraction", "mean"), max_combo_fraction=("combo_fraction", "max")).reset_index(), 20)}

## 最差起点样本

{_md_table(per_start.sort_values(["variant", "total_return_pct"]).groupby("variant").head(1), 30)}

## 结论

- 决策：`{decision['decision']}`，不晋级、不改实盘。
- 最强 proxy：`{decision.get('best_proxy_variant')}`。
- 下一步：`{decision['next_step']}`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continued_value_after']}
- 图表：`{CHART_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")
    STAGE_RECORD.write_text(text, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    events = s056.load_all_modules()
    combo_deltas = build_all_combo_event_deltas(events)
    stage013_base = load_stage013_base_curves()
    official = load_official_curves()
    proxy_curves, unmatched_delta_dates = build_proxy_curves(stage013_base, combo_deltas)
    stage013_base["daily_delta"] = 0.0
    stage013_base["cum_delta"] = 0.0
    official["daily_delta"] = 0.0
    official["cum_delta"] = 0.0
    curves = pd.concat([official, stage013_base, proxy_curves], ignore_index=True, sort=False)
    per_start, version_summary = summarize_curves(curves)
    decision = build_decision(combo_deltas, per_start, version_summary, unmatched_delta_dates)

    combo_deltas.to_csv(COMBO_EVENT_DELTAS_PATH, index=False)
    curves.to_csv(CURVES_PATH, index=False)
    per_start.to_csv(PER_START_PATH, index=False)
    version_summary.to_csv(VERSION_SUMMARY_PATH, index=False)
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe) + "\n", encoding="utf-8")
    plot_absolute_equity(curves)
    write_report(combo_deltas, per_start, version_summary, decision)

    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe))


if __name__ == "__main__":
    main()
