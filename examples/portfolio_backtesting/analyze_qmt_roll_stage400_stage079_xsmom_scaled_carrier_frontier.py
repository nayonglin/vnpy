from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
STAGE087_SCRIPT = PROJECT_DIR / "analyze_qmt_roll_stage387_stage079_short_holding_candidates.py"

MODEL_TAG = "stage400_stage079_xsmom_scaled_carrier_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage400_stage079_xsmom_scaled_carrier_frontier"
LINE_ID = "futures_trend_drawdown30_preserve_return"

COMBO_DAILY_PATH = (
    OUTPUT_DIR / "qmt_roll_stage352_xsmom_overlay_cash_multiperiod_combo_daily_stage352_xsmom_overlay_cash_multiperiod_v1.csv"
)
MARGIN_PATH = (
    OUTPUT_DIR / "qmt_roll_stage352_xsmom_overlay_cash_multiperiod_margin_stage352_xsmom_overlay_cash_multiperiod_v1.csv"
)

FUTURES_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0
STAGE079_CASH = 115_000.0
TARGET_DD_PCT = -30.0
BASELINE_VARIANT = "stage079"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_frontier_{MODEL_TAG}.png"


@dataclass(frozen=True)
class ScaleSpec:
    variant: str
    label: str
    xsmom_scale: float
    candidate_class: str
    eligible_for_promotion: bool
    note: str


SCALE_SPECS: tuple[ScaleSpec, ...] = (
    ScaleSpec(BASELINE_VARIANT, "Stage079基准", 0.00, "baseline", True, "50万C3下单+11.5万现金。"),
    ScaleSpec(
        "xsmom_scale_05_cash115",
        "诊断：xsmom overlay 5%承载",
        0.05,
        "scaled_xsmom_overlay_diagnostic",
        False,
        "线性缩放Stage352冻结xsmom PnL和保证金，只用于承载边界诊断。",
    ),
    ScaleSpec(
        "xsmom_scale_10_cash115",
        "诊断：xsmom overlay 10%承载",
        0.10,
        "scaled_xsmom_overlay_diagnostic",
        False,
        "线性缩放Stage352冻结xsmom PnL和保证金，只用于承载边界诊断。",
    ),
    ScaleSpec(
        "xsmom_scale_15_cash115",
        "诊断：xsmom overlay 15%承载",
        0.15,
        "scaled_xsmom_overlay_diagnostic",
        False,
        "线性缩放Stage352冻结xsmom PnL和保证金，只用于承载边界诊断。",
    ),
    ScaleSpec(
        "xsmom_scale_20_cash115",
        "诊断：xsmom overlay 20%承载",
        0.20,
        "scaled_xsmom_overlay_diagnostic",
        False,
        "线性缩放Stage352冻结xsmom PnL和保证金，只用于承载边界诊断。",
    ),
    ScaleSpec(
        "xsmom_scale_25_cash115",
        "诊断：xsmom overlay 25%承载",
        0.25,
        "scaled_xsmom_overlay_diagnostic",
        False,
        "线性缩放Stage352冻结xsmom PnL和保证金，只用于承载边界诊断。",
    ),
    ScaleSpec(
        "xsmom_scale_50_cash115",
        "诊断：xsmom overlay 50%承载",
        0.50,
        "scaled_xsmom_overlay_diagnostic",
        False,
        "线性缩放Stage352冻结xsmom PnL和保证金，只用于承载边界诊断。",
    ),
    ScaleSpec(
        "xsmom_scale_75_cash115",
        "诊断：xsmom overlay 75%承载",
        0.75,
        "scaled_xsmom_overlay_diagnostic",
        False,
        "线性缩放Stage352冻结xsmom PnL和保证金，只用于承载边界诊断。",
    ),
    ScaleSpec(
        "xsmom_scale_100_cash115",
        "诊断：xsmom overlay 100%承载",
        1.00,
        "scaled_xsmom_overlay_diagnostic",
        False,
        "Stage099原始强度；仅作边界对照。",
    ),
)


def _load_stage087_module():
    spec = importlib.util.spec_from_file_location("stage087_gate_for_stage400", STAGE087_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE087_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage087_gate_for_stage400"] = module
    spec.loader.exec_module(module)
    return module


s087 = _load_stage087_module()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
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
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _load_combo_daily() -> pd.DataFrame:
    frame = pd.read_csv(COMBO_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for col in ["c3_net_pnl", "c3_slippage", "daily_pnl", "slippage_cost", "trade_count", "turnover_contracts"]:
        frame[col] = pd.to_numeric(frame.get(col, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["window_name", "date"])


def _load_margin() -> pd.DataFrame:
    frame = pd.read_csv(MARGIN_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for col in ["account_balance", "c3_margin", "satellite_margin", "total_margin"]:
        frame[col] = pd.to_numeric(frame.get(col, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["window_name", "date"])


def _equity_from_frame(frame: pd.DataFrame, scale: float, slippage_multiplier: float = 1.0) -> pd.Series:
    pnl = frame["c3_net_pnl"].astype(float) + float(scale) * frame["daily_pnl"].astype(float)
    slippage = frame["c3_slippage"].astype(float) + float(scale) * frame["slippage_cost"].astype(float)
    stressed = pnl - (float(slippage_multiplier) - 1.0) * slippage
    equity = FUTURES_CAPITAL + stressed.cumsum() + STAGE079_CASH
    return pd.Series(equity.to_numpy(dtype=float), index=frame["date"])


def _calendarize(equity: pd.Series) -> pd.Series:
    equity = equity.sort_index().dropna()
    calendar = pd.date_range(equity.index.min(), equity.index.max(), freq="D")
    return equity.reindex(calendar).ffill().dropna()


def _candidate(spec: ScaleSpec, equity: pd.Series) -> Any:
    return s087.Candidate(
        variant=spec.variant,
        label=spec.label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class=spec.candidate_class,
        eligible_for_promotion=spec.eligible_for_promotion,
        note=spec.note,
    )


def _cost_stress(full: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_dd: dict[float, float] = {}
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for spec in SCALE_SPECS:
            equity = _calendarize(_equity_from_frame(full, spec.xsmom_scale, multiplier))
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s087._max_drawdown(nav)
            if spec.variant == BASELINE_VARIANT:
                baseline_dd[multiplier] = max_dd
            rows.append(
                {
                    "variant": spec.variant,
                    "label": spec.label,
                    "xsmom_scale": spec.xsmom_scale,
                    "slippage_multiplier": multiplier,
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                }
            )
    result = pd.DataFrame(rows)
    result["baseline_stage079_max_dd_pct"] = result["slippage_multiplier"].map(baseline_dd)
    result["not_worse_than_stage079_stress"] = (
        result["max_dd_pct"] >= result["baseline_stage079_max_dd_pct"] - 1e-9
    ).astype(int)
    return result


def _fresh_start(combo: pd.DataFrame, margin: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, frame in combo.groupby("window_name", sort=True):
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        m = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
        for spec in SCALE_SPECS:
            equity = _equity_from_frame(frame, spec.xsmom_scale, 1.0)
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s087._max_drawdown(nav)
            if m.empty:
                max_margin_to_equity = 0.0
                reject_days = 0
            else:
                total_margin = m["c3_margin"].astype(float) + spec.xsmom_scale * m["satellite_margin"].astype(float)
                equity_on_margin_dates = equity.reindex(m["date"]).ffill().to_numpy(dtype=float)
                margin_equity = total_margin.to_numpy(dtype=float) / equity_on_margin_dates * 100.0
                max_margin_to_equity = float(np.nanmax(margin_equity)) if len(margin_equity) else 0.0
                reject_days = int(np.sum(margin_equity > 100.0))
            rows.append(
                {
                    "window_name": window_name,
                    "variant": spec.variant,
                    "label": spec.label,
                    "xsmom_scale": spec.xsmom_scale,
                    "start_date": str(frame["date"].min().date()),
                    "end_date": str(frame["date"].max().date()),
                    "end_equity": float(equity.iloc[-1]),
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                    "dd30_pass": int(max_dd >= TARGET_DD_PCT),
                    "max_margin_to_equity_pct": max_margin_to_equity,
                    "reject_days": reject_days,
                }
            )
    return pd.DataFrame(rows)


def _gate(summary: pd.DataFrame, score: pd.DataFrame, cost: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    score_one = score.drop_duplicates(["variant", "label"])[
        ["variant", "label", "score_90d", "score_180d", "short_holding_score"]
    ]
    improved = score.groupby(["variant", "label", "horizon_days"])["improved_metric_count"].first().reset_index()
    improved_p = improved.pivot(index=["variant", "label"], columns="horizon_days", values="improved_metric_count").reset_index()
    improved_p.columns = ["variant", "label", "improved_count_90d", "improved_count_180d"]
    fresh_failures = (
        fresh[fresh["dd30_pass"].eq(0)]
        .groupby("variant")["window_name"]
        .apply(lambda values: ",".join(sorted(map(str, values))))
        .to_dict()
    )
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        c = cost[cost["variant"].eq(row["variant"])]
        checks = {
            "eligible_not_diagnostic": int(row["eligible_for_promotion"]) == 1,
            "total_return_not_lower": _safe_float(row["total_return_pct"]) >= _safe_float(baseline["total_return_pct"]) - 1e-4,
            "max_dd_not_worse": _safe_float(row["max_dd_pct"]) >= _safe_float(baseline["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": _safe_float(row["max_dd_pct"]) >= TARGET_DD_PCT,
            "sharpe_not_lower": _safe_float(row["sharpe"]) >= _safe_float(baseline["sharpe"]) - 1e-4,
            "ulcer_not_higher": _safe_float(row["ulcer_pct"]) <= _safe_float(baseline["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": _safe_float(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_float(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_pass_100": _safe_float(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_pass_100": _safe_float(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
            "capital_not_increased": _safe_float(row["capital_used"]) <= ACCOUNT_CAPITAL,
            "cost_stress_not_worse": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
            "fresh_start_dd30_pass": str(row["variant"]) not in fresh_failures,
        }
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                "xsmom_scale": row["xsmom_scale"],
                **{name: int(flag) for name, flag in checks.items()},
                "hard_constraint_pass": int(all(checks.values())),
                "fresh_start_failed_windows": fresh_failures.get(str(row["variant"]), ""),
                "failed_hard_checks": ",".join([name for name, flag in checks.items() if not flag]),
            }
        )
    result = pd.DataFrame(rows).merge(score_one, on=["variant", "label"], how="left").merge(
        improved_p, on=["variant", "label"], how="left"
    )
    result["score90_improve_ge10pct"] = (result["score_90d"] >= 110.0).astype(int)
    result["score180_improve_ge10pct"] = (result["score_180d"] >= 110.0).astype(int)
    result["improved_5of8_each"] = ((result["improved_count_90d"] >= 5) & (result["improved_count_180d"] >= 5)).astype(int)
    result["target_pass_3m6m"] = (
        result["score90_improve_ge10pct"].eq(1)
        & result["score180_improve_ge10pct"].eq(1)
        & result["improved_5of8_each"].eq(1)
    ).astype(int)
    result["formal_promotion_pass"] = (result["hard_constraint_pass"].eq(1) & result["target_pass_3m6m"].eq(1)).astype(int)
    return result.sort_values(["formal_promotion_pass", "short_holding_score"], ascending=[False, False])


def _plot(daily: pd.DataFrame, gate: pd.DataFrame, fresh: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage400] skip chart: {exc}", flush=True)
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    selected = {
        "stage079",
        "xsmom_scale_15_cash115",
        "xsmom_scale_25_cash115",
        "xsmom_scale_100_cash115",
    }
    for variant, frame in daily[daily["variant"].isin(selected)].groupby("variant"):
        frame = frame.sort_values("date")
        equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        nav = equity / ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=1.2)
        dd = nav / nav.cummax() - 1.0
        axes[1, 0].plot(dd.index, dd * 100.0, label=variant, linewidth=1.1)

    axes[0, 0].set_title("Full-period NAV")
    axes[0, 0].set_ylabel("NAV")
    axes[0, 0].legend(fontsize=8)
    axes[1, 0].set_title("Full-period drawdown")
    axes[1, 0].set_ylabel("Drawdown %")
    axes[1, 0].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=8)

    frontier = gate.sort_values("xsmom_scale")
    axes[0, 1].plot(frontier["xsmom_scale"], frontier["score_90d"], marker="o", label="90d score")
    axes[0, 1].plot(frontier["xsmom_scale"], frontier["score_180d"], marker="o", label="180d score")
    axes[0, 1].axhline(110.0, color="gray", linestyle="--", linewidth=1.0)
    axes[0, 1].set_title("3m/6m experience score")
    axes[0, 1].set_xlabel("xsmom scale")
    axes[0, 1].legend(fontsize=8)

    ytd = fresh[fresh["window_name"].eq("ytd_2026")].sort_values("xsmom_scale")
    axes[1, 1].plot(ytd["xsmom_scale"], ytd["max_dd_pct"], marker="o", label="YTD 2026 DD")
    axes[1, 1].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 1].set_title("Fresh-start YTD 2026 drawdown")
    axes[1, 1].set_xlabel("xsmom scale")
    axes[1, 1].set_ylabel("Max DD %")
    axes[1, 1].legend(fontsize=8)

    fig.suptitle("Stage100/400 Stage079 xsmom scaled carrier frontier", y=0.99)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    cost: pd.DataFrame,
    fresh: pd.DataFrame,
    gate: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    compact_summary = summary[
        [
            "variant",
            "xsmom_scale",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "ulcer_pct",
            "rolling252_dd30_breach_rate",
            "rolling504_dd30_breach_rate",
        ]
    ]
    fresh_compact = fresh[fresh["window_name"].isin(["start_2024", "start_2025", "ytd_2026"])][
        ["window_name", "variant", "xsmom_scale", "total_return_pct", "max_dd_pct", "dd30_pass", "max_margin_to_equity_pct", "reject_days"]
    ]
    report = [
        "# Stage100 Stage079 xsmom缩放承载边界诊断",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：只读诊断；复用Stage352固定xsmom overlay日PnL/滑点/保证金，线性缩放为承载能力边界。",
        "- 不是正式可交易版本：5%-100%缩放不是逐笔真实手数重建，不能直接晋级实盘。",
        "- 本阶段要回答的问题：Stage099失败是信号源无效，还是承载强度/冷启动风险不匹配？",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 外部调研与判断",
        "",
        "- Moskowitz/Ooi/Pedersen 的时间序列动量研究、AQR百年趋势跟随研究、商品期货趋势/风险平价/动量研究，都支持趋势/动量类收益源跨资产存在，但强调分散和风险预算。",
        "- 因此，本阶段不继续救单个失败窗口，而是审计同一冻结xsmom源在不同承载强度下的全周期收益、短持有体验和多起点冷启动。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 全周期核心指标",
        "",
        _md_table(compact_summary),
        "",
        "## 3个月/6个月体验评分",
        "",
        _md_table(
            score[
                [
                    "variant",
                    "horizon_days",
                    "experience_score",
                    "improved_metric_count",
                    "score_90d",
                    "score_180d",
                    "short_holding_score",
                ]
            ].sort_values(["variant", "horizon_days"])
        ),
        "",
        "## 关键冷启动窗口",
        "",
        _md_table(fresh_compact.sort_values(["window_name", "xsmom_scale"])),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "variant",
                    "xsmom_scale",
                    "slippage_multiplier",
                    "total_return_pct",
                    "max_dd_pct",
                    "baseline_stage079_max_dd_pct",
                    "not_worse_than_stage079_stress",
                ]
            ]
        ),
        "",
        "## 晋级闸门",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "xsmom_scale",
                    "hard_constraint_pass",
                    "target_pass_3m6m",
                    "formal_promotion_pass",
                    "score_90d",
                    "score_180d",
                    "improved_count_90d",
                    "improved_count_180d",
                    "fresh_start_failed_windows",
                    "failed_hard_checks",
                ]
            ]
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 缩放表只用于判定承载强度边界，不把5%/10%/15%/20%当作可上线参数。",
        "- 结果显示冷启动安全阈值与3/6个月体验提升阈值互相冲突，因此不能靠继续扫缩放比例解决。",
        "- 后续若继续，应转向真实低成本承载、独立paper监控或新收益源，不应继续修 `ytd_2026` 的条件。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combo = _load_combo_daily()
    margin = _load_margin()
    full = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    if full.empty:
        raise RuntimeError("missing start_2020 in Stage352 combo daily")

    candidates: list[Any] = []
    daily_parts: list[pd.DataFrame] = []
    for spec in SCALE_SPECS:
        equity = _calendarize(_equity_from_frame(full, spec.xsmom_scale, 1.0))
        candidates.append(_candidate(spec, equity))
        daily_parts.append(
            pd.DataFrame(
                {
                    "date": equity.index,
                    "variant": spec.variant,
                    "label": spec.label,
                    "xsmom_scale": spec.xsmom_scale,
                    "equity": equity.to_numpy(dtype=float),
                }
            )
        )

    summary = pd.DataFrame([s087._stats(candidate) for candidate in candidates])
    scale_by_variant = {spec.variant: spec.xsmom_scale for spec in SCALE_SPECS}
    summary["xsmom_scale"] = summary["variant"].map(scale_by_variant)
    horizon = pd.DataFrame([s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
    horizon["xsmom_scale"] = horizon["variant"].map(scale_by_variant)
    score = s087._score_horizons(horizon)
    score["xsmom_scale"] = score["variant"].map(scale_by_variant)
    fresh = _fresh_start(combo, margin)
    cost = _cost_stress(full)
    gate = _gate(summary, score, cost, fresh)
    daily = pd.concat(daily_parts, ignore_index=True)

    formal = gate[gate["formal_promotion_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)]
    target_not_fresh_safe = gate[
        ~gate["variant"].eq(BASELINE_VARIANT)
        & gate["target_pass_3m6m"].eq(1)
        & gate["fresh_start_dd30_pass"].eq(0)
    ]
    fresh_safe = gate[
        ~gate["variant"].eq(BASELINE_VARIANT)
        & gate["fresh_start_dd30_pass"].eq(1)
        & gate["max_dd_below_30"].eq(1)
    ].sort_values("xsmom_scale")
    max_fresh_safe = fresh_safe.tail(1)
    decision = {
        "stage": "Stage100",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "formal_promotion_candidate" if len(formal) else "no_formal_promotion_scaled_overlay_boundary_fail",
        "formal_promoted_variants": formal["variant"].tolist(),
        "target_pass_but_fresh_start_fail_variants": target_not_fresh_safe["variant"].tolist(),
        "max_fresh_start_safe_scaled_variant": max_fresh_safe["variant"].iloc[0] if not max_fresh_safe.empty else "",
        "max_fresh_start_safe_scale": float(max_fresh_safe["xsmom_scale"].iloc[0]) if not max_fresh_safe.empty else None,
        "max_fresh_start_safe_score90": float(max_fresh_safe["score_90d"].iloc[0]) if not max_fresh_safe.empty else None,
        "max_fresh_start_safe_score180": float(max_fresh_safe["score_180d"].iloc[0]) if not max_fresh_safe.empty else None,
        "best_full_sample_variant": gate.iloc[0]["variant"] if not gate.empty else "",
        "chart": str(CHART_PATH),
        "judgement": "xsmom源本身值得作为独立paper重点线索；但线性缩小载体无法同时满足冷启动30回撤和3/6个月体验提升，不能作为Stage079正式优化版晋级。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(daily, gate, fresh)
    _write_report(summary, horizon, score, cost, fresh, gate, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
