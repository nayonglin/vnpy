from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage414_independent_promotion_judgement_v1"
OUTPUT_PREFIX = "qmt_roll_stage414_independent_promotion_judgement"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
STAGE079_CASH = 115_000.0
BASELINE_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
STOCK_VARIANT = "stage103_stock_lot_50000_cash_65000_yield2"

STAGE403_PREFIX = "qmt_roll_stage403_stage079_xsmom_execution_margin_audit"
STAGE403_TAG = "stage403_stage079_xsmom_execution_margin_audit_v1"
STAGE409_PREFIX = "qmt_roll_stage409_stage103_robustness_overfit_audit"
STAGE409_TAG = "stage409_stage103_robustness_overfit_audit_v1"
STAGE411_PREFIX = "qmt_roll_stage411_stage103_stock_cashslot_audit"
STAGE411_TAG = "stage411_stage103_stock_cashslot_audit_v1"
STAGE412_PREFIX = "qmt_roll_stage412_stage111_liquidity_robustness_audit"
STAGE412_TAG = "stage412_stage111_liquidity_robustness_audit_v1"
STAGE413_PREFIX = "qmt_roll_stage413_cash_sweep_frontier"
STAGE413_TAG = "stage413_cash_sweep_frontier_v1"

MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_matrix_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_pairwise_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
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


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    return frame


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


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


def _cash_yield_series(cash: float, calendar: pd.DatetimeIndex, annual_yield: float) -> pd.Series:
    days = (calendar - calendar[0]).days.to_numpy(dtype=float)
    values = cash * np.power(1.0 + annual_yield, days / 365.0)
    return pd.Series(values, index=calendar)


def _max_drawdown(nav: pd.Series) -> float:
    peak = nav.cummax()
    return float((nav / peak - 1.0).min() * 100.0)


def _ulcer(nav: pd.Series) -> float:
    peak = nav.cummax()
    dd = np.minimum(nav / peak - 1.0, 0.0) * 100.0
    return float(np.sqrt(np.mean(np.square(dd))))


def _rolling_pairwise(equities: dict[str, pd.Series]) -> pd.DataFrame:
    windows = [63, 90, 126, 180, 252, 504]
    baseline = equities[BASELINE_VARIANT].astype(float)
    rows: list[dict[str, Any]] = []
    for variant, equity in equities.items():
        if variant == BASELINE_VARIANT:
            continue
        aligned = pd.concat({"baseline": baseline, "candidate": equity.astype(float)}, axis=1).dropna()
        for window in windows:
            pairs: list[dict[str, float]] = []
            for start in range(0, len(aligned) - window + 1):
                base_segment = aligned["baseline"].iloc[start : start + window]
                cand_segment = aligned["candidate"].iloc[start : start + window]
                base_return = base_segment.iloc[-1] / base_segment.iloc[0] - 1.0
                cand_return = cand_segment.iloc[-1] / cand_segment.iloc[0] - 1.0
                base_dd = _max_drawdown(base_segment / base_segment.iloc[0])
                cand_dd = _max_drawdown(cand_segment / cand_segment.iloc[0])
                base_ulcer = _ulcer(base_segment / base_segment.iloc[0])
                cand_ulcer = _ulcer(cand_segment / cand_segment.iloc[0])
                pairs.append(
                    {
                        "return_delta_pp": (cand_return - base_return) * 100.0,
                        "return_win": float(cand_return > base_return),
                        "maxdd_not_worse": float(cand_dd >= base_dd),
                        "ulcer_not_worse": float(cand_ulcer <= base_ulcer),
                    }
                )
            frame = pd.DataFrame(pairs)
            rows.append(
                {
                    "variant": variant,
                    "window_days": window,
                    "return_win_rate": float(frame["return_win"].mean()),
                    "return_delta_median_pp": float(frame["return_delta_pp"].median()),
                    "return_delta_p05_pp": float(frame["return_delta_pp"].quantile(0.05)),
                    "maxdd_not_worse_rate": float(frame["maxdd_not_worse"].mean()),
                    "ulcer_not_worse_rate": float(frame["ulcer_not_worse"].mean()),
                }
            )
    return pd.DataFrame(rows)


def _build_equities() -> dict[str, pd.Series]:
    stage403_daily = _read_csv(OUTPUT_DIR / f"{STAGE403_PREFIX}_daily_{STAGE403_TAG}.csv")
    stage403_daily = stage403_daily[
        stage403_daily["window_name"].eq("start_2020")
        & stage403_daily["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])
    ].copy()
    calendar = pd.date_range(stage403_daily["date"].min(), stage403_daily["date"].max(), freq="D")
    pivot = (
        stage403_daily.pivot_table(index="date", columns="variant", values="equity", aggfunc="last")
        .sort_index()
        .reindex(calendar)
        .ffill()
    )
    stage103_core = pivot[STAGE103_VARIANT] - STAGE079_CASH

    stage411_daily = _read_csv(OUTPUT_DIR / f"{STAGE411_PREFIX}_daily_{STAGE411_TAG}.csv")
    stock = (
        stage411_daily[stage411_daily["variant"].eq(STOCK_VARIANT)]
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .set_index("date")["equity"]
        .reindex(calendar)
        .ffill()
    )
    return {
        BASELINE_VARIANT: pivot[BASELINE_VARIANT],
        STAGE103_VARIANT: pivot[STAGE103_VARIANT],
        "stage103_cash_sweep_0120bp": stage103_core + _cash_yield_series(STAGE079_CASH, calendar, 0.012),
        "stage103_cash_sweep_0200bp": stage103_core + _cash_yield_series(STAGE079_CASH, calendar, 0.02),
        STOCK_VARIANT: stock,
    }


def _row_from_outputs(
    variant: str,
    label: str,
    variant_type: str,
    summary: pd.DataFrame,
    gate: pd.DataFrame,
    rolling: pd.DataFrame,
    stage409_decision: dict[str, Any],
    stage412_decision: dict[str, Any],
) -> dict[str, Any]:
    srow = summary[summary["variant"].eq(variant)].iloc[0]
    grow = gate[gate["variant"].eq(variant)].iloc[0] if variant in set(gate["variant"]) else pd.Series(dtype=object)
    r90 = rolling[(rolling["variant"].eq(variant)) & (rolling["window_days"].eq(90))]
    r180 = rolling[(rolling["variant"].eq(variant)) & (rolling["window_days"].eq(180))]
    r252 = rolling[(rolling["variant"].eq(variant)) & (rolling["window_days"].eq(252))]
    return {
        "variant": variant,
        "label": label,
        "variant_type": variant_type,
        "total_return_pct": _safe_float(srow["total_return_pct"]),
        "max_dd_pct": _safe_float(srow["max_dd_pct"]),
        "sharpe": _safe_float(srow["sharpe"]),
        "ulcer_pct": _safe_float(srow["ulcer_pct"]),
        "score_90d": _safe_float(grow.get("score_90d", np.nan), np.nan),
        "score_180d": _safe_float(grow.get("score_180d", np.nan), np.nan),
        "hard_metric_pass": int(_safe_float(grow.get("hard_pass", grow.get("metric_hard_pass_stage079", 0))) == 1.0),
        "target_pass": int(_safe_float(grow.get("target_pass", grow.get("target_pass_3m6m_vs_stage079", 0))) == 1.0),
        "ideal_all_targets_hit": int(_safe_float(grow.get("ideal_all_targets_hit", 0)) == 1.0),
        "return_win_90d": _safe_float(r90["return_win_rate"].iloc[0], np.nan) if not r90.empty else np.nan,
        "return_win_180d": _safe_float(r180["return_win_rate"].iloc[0], np.nan) if not r180.empty else np.nan,
        "return_win_252d": _safe_float(r252["return_win_rate"].iloc[0], np.nan) if not r252.empty else np.nan,
        "ulcer_not_worse_90d": _safe_float(r90["ulcer_not_worse_rate"].iloc[0], np.nan) if not r90.empty else np.nan,
        "ulcer_not_worse_180d": _safe_float(r180["ulcer_not_worse_rate"].iloc[0], np.nan) if not r180.empty else np.nan,
        "stage103_bootstrap_return_win": _safe_float(
            stage409_decision.get("resample", [{}])[0].get("stage103_return_win_rate", np.nan), np.nan
        ),
        "stock_liquid_110_reject_days": int(stage412_decision.get("stage111_liquid_110_reject_days", 0))
        if variant == STOCK_VARIANT
        else 0,
        "stock_liquid_110_required_extra_cash": _safe_float(
            stage412_decision.get("stage111_liquid_110_required_extra_cash", 0.0), 0.0
        )
        if variant == STOCK_VARIANT
        else 0.0,
    }


def _judge(row: pd.Series) -> dict[str, Any]:
    variant = str(row["variant"])
    if variant == BASELINE_VARIANT:
        return {
            "promotion_level": "baseline_only",
            "promotion_score": 0,
            "judgement": "作为旧baseline保留，不是新增晋级对象。",
        }
    if variant == STOCK_VARIANT:
        return {
            "promotion_level": "paper_only_reject_deployment",
            "promotion_score": 55,
            "judgement": "短持有分数略好，但收益胜率和期货可用保证金不够干净，只能paper观察。",
        }
    if variant == "stage103_cash_sweep_0200bp":
        return {
            "promotion_level": "paper_cash_assumption",
            "promotion_score": 70,
            "judgement": "若能稳定拿到2%现金收益，可作为paper增强；2026现实现金收益下不能当默认假设。",
        }
    if variant == "stage103_cash_sweep_0120bp":
        return {
            "promotion_level": "operational_overlay",
            "promotion_score": 78,
            "judgement": "现实现金管理可作为Stage103的低风险执行细节，但不是独立alpha晋级。",
        }
    return {
        "promotion_level": "promote_engineering_paper",
        "promotion_score": 82,
        "judgement": "值得从研究候选晋级到工程化复跑和paper影子盘；暂不升为正式替代或绝对部署版本。",
    }


def _plot(matrix: pd.DataFrame) -> None:
    view = matrix[matrix["variant"].ne(BASELINE_VARIANT)].copy()
    labels = ["Stage103", "Cash 1.2%", "Cash 2.0%", "Stock slot"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].bar(labels, view["promotion_score"], color=["#4c78a8", "#72b7b2", "#f58518", "#e45756"])
    axes[0].axhline(80, color="gray", linestyle="--", linewidth=1)
    axes[0].set_ylim(0, 100)
    axes[0].set_title("Independent promotion judgement")
    axes[0].set_ylabel("Judgement score")
    axes[0].tick_params(axis="x", rotation=25)

    width = 0.38
    x = np.arange(len(view))
    axes[1].bar(x - width / 2, view["return_win_90d"], width, label="90d return win")
    axes[1].bar(x + width / 2, view["return_win_180d"], width, label="180d return win")
    axes[1].axhline(0.5, color="gray", linestyle="--", linewidth=1)
    axes[1].set_ylim(0, 1.0)
    axes[1].set_xticks(x, labels, rotation=25)
    axes[1].set_title("Any-start return win rate vs Stage079")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage409_decision = _read_json(OUTPUT_DIR / f"{STAGE409_PREFIX}_decision_{STAGE409_TAG}.json")
    stage412_decision = _read_json(OUTPUT_DIR / f"{STAGE412_PREFIX}_decision_{STAGE412_TAG}.json")
    stage413_summary = _read_csv(OUTPUT_DIR / f"{STAGE413_PREFIX}_summary_{STAGE413_TAG}.csv")
    stage413_gate = _read_csv(OUTPUT_DIR / f"{STAGE413_PREFIX}_gate_{STAGE413_TAG}.csv")
    stage411_summary = _read_csv(OUTPUT_DIR / f"{STAGE411_PREFIX}_summary_{STAGE411_TAG}.csv")
    stage411_gate = _read_csv(OUTPUT_DIR / f"{STAGE411_PREFIX}_gate_{STAGE411_TAG}.csv")
    rolling = _rolling_pairwise(_build_equities())

    stage413_variants = [BASELINE_VARIANT, STAGE103_VARIANT, "stage103_cash_sweep_0120bp", "stage103_cash_sweep_0200bp"]
    rows = [
        _row_from_outputs(
            variant,
            {
                BASELINE_VARIANT: "Stage079 baseline",
                STAGE103_VARIANT: "Stage103 broker10_guard",
                "stage103_cash_sweep_0120bp": "Stage103 + cash sweep 1.2%",
                "stage103_cash_sweep_0200bp": "Stage103 + cash sweep 2.0%",
            }[variant],
            {
                BASELINE_VARIANT: "baseline",
                STAGE103_VARIANT: "core_candidate",
                "stage103_cash_sweep_0120bp": "realistic_cash_overlay",
                "stage103_cash_sweep_0200bp": "optimistic_cash_overlay",
            }[variant],
            stage413_summary,
            stage413_gate,
            rolling,
            stage409_decision,
            stage412_decision,
        )
        for variant in stage413_variants
    ]
    rows.append(
        _row_from_outputs(
            STOCK_VARIANT,
            "Stage103 + 50k stock slot + 65k cash 2%",
            "illiquid_cashslot_paper",
            stage411_summary,
            stage411_gate,
            rolling,
            stage409_decision,
            stage412_decision,
        )
    )
    matrix = pd.DataFrame(rows)
    judgement = pd.DataFrame([_judge(row) for _, row in matrix.iterrows()])
    matrix = pd.concat([matrix, judgement], axis=1)
    matrix["independent_promotion"] = matrix["promotion_level"].isin(["promote_engineering_paper", "operational_overlay"]).astype(int)
    matrix["absolute_deployment"] = 0
    matrix.loc[matrix["variant"].eq(BASELINE_VARIANT), "absolute_deployment"] = 0

    decision = {
        "stage": "Stage114",
        "line_id": LINE_ID,
        "decision": "promote_stage103_to_engineering_paper_not_absolute_deployment",
        "my_judgement": "即使不强行要求所有3/6个月理想目标，Stage103也值得晋级到工程化复跑和paper影子盘；现实现金sweep可作为它的执行细节；股票槽位和2%现金收益假设不晋级部署。",
        "primary_candidate": STAGE103_VARIANT,
        "allowed_operational_overlay": "stage103_cash_sweep_0120bp",
        "not_promoted": [STOCK_VARIANT, "stage103_cash_sweep_0200bp"],
        "why_not_absolute_deployment": [
            "Stage103的任意窗口收益胜率不足，90/180/252日收益胜率仍低于50%或不强。",
            "Stage409显示block bootstrap收益胜率约55%，收益端不是压倒性优势。",
            "Stage403经纪商10%保证金审计仍不是绝对无拒单部署结论，需要接真实券商保证金。",
        ],
        "chart": str(CHART_PATH),
    }

    matrix.to_csv(MATRIX_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(matrix)

    report = [
        "# Stage114 独立晋级判断审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：决策审计；不新增交易规则，不继续扫参。",
        "- 外部调研结论：walk-forward/rolling window 是判断任意启动体验的合理框架；2026年5月货币基金现金收益接近1%附近，不能把2%当默认可获得收益。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 我的判断",
        "",
        decision["my_judgement"],
        "",
        "## 晋级矩阵",
        "",
        _md_table(
            matrix[
                [
                    "variant",
                    "variant_type",
                    "promotion_level",
                    "promotion_score",
                    "independent_promotion",
                    "absolute_deployment",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "ulcer_pct",
                    "score_90d",
                    "score_180d",
                    "return_win_90d",
                    "return_win_180d",
                    "return_win_252d",
                    "stock_liquid_110_reject_days",
                    "stock_liquid_110_required_extra_cash",
                    "judgement",
                ]
            ]
        ),
        "",
        "## 任意启动滚动对比",
        "",
        _md_table(rolling),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段不根据结果反调入场、出场、品种池或参数。",
        "- 晋级结论只允许提升到工程化复跑 / paper；不把短样本增益解释成正式实盘替代。",
        "- 现金收益只接受外部现实收益率，不把2%或更高收益率作为默认可得alpha。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
