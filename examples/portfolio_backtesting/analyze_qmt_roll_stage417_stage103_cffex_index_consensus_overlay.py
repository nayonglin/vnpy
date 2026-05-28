from __future__ import annotations

import json
import math
import sys
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

sys.path.insert(0, str(PROJECT_DIR.resolve()))
import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402
import analyze_qmt_roll_stage405_stage079_reversal_protection_scout as s405  # noqa: E402
import analyze_qmt_roll_stage415_stage103_cffex_index_true_overlay as s415  # noqa: E402


MODEL_TAG = "stage417_stage103_cffex_index_consensus_overlay_v1"
OUTPUT_PREFIX = "qmt_roll_stage417_stage103_cffex_index_consensus_overlay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL
BROKER10_MULTIPLIER = s405.BROKER10_MULTIPLIER

CONSENSUS_BEST1_VARIANT = "stage103_plus_cffex_index_consensus_best1_guard"
CONSENSUS_SHORT1_VARIANT = "stage103_plus_cffex_index_consensus_short1_guard"
CONSENSUS_ALL_VARIANT = "stage103_plus_cffex_index_consensus_all_guard"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
MARGIN_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_audit_{MODEL_TAG}.csv"
BAD_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_window_contribution_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
OVERLAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_overlay_daily_{MODEL_TAG}.csv"
CONSENSUS_PANEL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_consensus_panel_{MODEL_TAG}.csv"
PAIRWISE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_rolling_{MODEL_TAG}.csv"
TOPDAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_edge_day_ablation_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


VARIANTS: tuple[s405.VariantSpec, ...] = (
    s405.VariantSpec(
        BASELINE_VARIANT,
        "A Stage079基准",
        "baseline",
        "none",
        0,
        0,
        0,
        "50万C3下单+11.5万现金。",
    ),
    s405.VariantSpec(
        STAGE103_VARIANT,
        "C0 Stage103 broker10_guard",
        "stage103",
        "none",
        0,
        0,
        0,
        "当前主执行相对候选。",
    ),
    s405.VariantSpec(
        CONSENSUS_BEST1_VARIANT,
        "C1 Stage103+股指60/120一致最强1手",
        "index_consensus_overlay",
        "index_consensus_best1",
        0,
        1,
        0,
        "IF/IH/IC/IM 只有60日与120日TSMOM方向一致时才可交易；每天只取60日绝对动量最强1手。",
    ),
    s405.VariantSpec(
        CONSENSUS_SHORT1_VARIANT,
        "C2 Stage103+股指60/120一致做空1手",
        "index_consensus_overlay",
        "index_consensus_short1",
        0,
        1,
        0,
        "IF/IH/IC/IM 只有60日与120日TSMOM同时为空头时才可交易；每天只取60日绝对动量最强1手。",
    ),
    s405.VariantSpec(
        CONSENSUS_ALL_VARIANT,
        "C3 Stage103+股指60/120一致全信号",
        "index_consensus_overlay_control",
        "index_consensus_all",
        0,
        0,
        0,
        "一致性过滤的过暴露对照组：所有60/120方向一致的股指信号各最多1手。",
    ),
)


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


def _build_consensus_panel() -> pd.DataFrame:
    panel = s415._build_index_panel()
    if panel.empty:
        return panel
    base_cols = [
        "date",
        "product",
        "main_contract_vt",
        "close",
        "product_return",
        "contract_multiplier",
        "margin_per_contract",
        "tick_value",
    ]
    h60 = panel[panel["horizon_days"].eq(60)].copy()
    h120 = panel[panel["horizon_days"].eq(120)][["date", "product", "momentum", "position"]].copy()
    h60 = h60[base_cols + ["momentum", "position"]].rename(
        columns={"momentum": "momentum60", "position": "position60"}
    )
    h120 = h120.rename(columns={"momentum": "momentum120", "position": "position120"})
    merged = h60.merge(h120, on=["date", "product"], how="left")
    merged["position120"] = pd.to_numeric(merged["position120"], errors="coerce").fillna(0.0)
    merged["momentum120"] = pd.to_numeric(merged["momentum120"], errors="coerce").fillna(0.0)
    merged["consensus_position"] = np.where(
        (np.sign(merged["position60"]) == np.sign(merged["position120"]))
        & (np.sign(merged["position60"]) != 0),
        np.sign(merged["position60"]),
        0.0,
    )
    merged["consensus_abs_momentum60"] = merged["momentum60"].abs()
    return merged.sort_values(["date", "product"])


def _empty_overlay(window_name: str, variant: str) -> pd.DataFrame:
    return s405._empty_overlay(window_name, variant)


def _simulate_consensus_overlay(
    spec: s405.VariantSpec,
    window_name: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    xsmom_sat: pd.DataFrame,
    consensus_panel: pd.DataFrame,
) -> pd.DataFrame:
    if spec.direction not in {"index_consensus_best1", "index_consensus_short1", "index_consensus_all"}:
        return _empty_overlay(window_name, spec.variant)

    start = window_frame["date"].min()
    end = window_frame["date"].max()
    index = consensus_panel[consensus_panel["date"].between(start, end)].copy()
    if index.empty:
        return _empty_overlay(window_name, spec.variant)

    c3_pnl = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()
    xsmom_by_date = xsmom_sat.set_index("date") if not xsmom_sat.empty else pd.DataFrame()
    xsmom_pnl = xsmom_by_date.get("satellite_daily_pnl", pd.Series(dtype=float)).astype(float).to_dict()
    xsmom_margin = xsmom_by_date.get("satellite_margin", pd.Series(dtype=float)).astype(float).to_dict()
    by_date: dict[pd.Timestamp, list[Any]] = {}
    for row in index.itertuples(index=False):
        by_date.setdefault(pd.Timestamp(row.date).normalize(), []).append(row)

    prev_positions: dict[str, int] = {}
    prev_contract_specs: dict[str, tuple[str, float]] = {}
    rows: list[dict[str, Any]] = []
    prev_equity = ACCOUNT_CAPITAL

    for date in window_frame["date"].sort_values():
        date = pd.Timestamp(date).normalize()
        raw_rows = [row for row in by_date.get(date, []) if float(getattr(row, "consensus_position", 0.0)) != 0.0]
        if spec.direction == "index_consensus_best1":
            raw_rows = [
                max(raw_rows, key=lambda row: abs(float(getattr(row, "momentum60", 0.0))))
            ] if raw_rows else []
        elif spec.direction == "index_consensus_short1":
            short_rows = [row for row in raw_rows if float(getattr(row, "consensus_position", 0.0)) < 0.0]
            raw_rows = [
                max(short_rows, key=lambda row: abs(float(getattr(row, "momentum60", 0.0))))
            ] if short_rows else []

        targets: dict[str, int] = {}
        contract_specs: dict[str, tuple[str, float]] = {}
        proposed_margin = 0.0
        pnl = 0.0
        desired_count = 0
        for index_row in raw_rows:
            lots = int(np.sign(float(getattr(index_row, "consensus_position", 0.0))))
            if lots == 0:
                continue
            contract = str(getattr(index_row, "main_contract_vt", ""))
            margin_per_contract = float(getattr(index_row, "margin_per_contract", 0.0))
            if not contract or margin_per_contract <= 0.0:
                continue
            desired_count += 1
            targets[contract] = lots
            contract_specs[contract] = (
                str(getattr(index_row, "product", "")),
                float(getattr(index_row, "tick_value", 0.0)),
            )
            proposed_margin += margin_per_contract
            close = float(getattr(index_row, "close", 0.0))
            product_return = float(getattr(index_row, "product_return", 0.0))
            if product_return <= -0.999999 or close <= 0.0:
                continue
            prev_close = close / (1.0 + product_return) if abs(product_return) > 1e-12 else close
            pnl += lots * prev_close * product_return * float(getattr(index_row, "contract_multiplier", 0.0))

        required_margin = (
            float(c3_margin.get(date, 0.0)) + float(xsmom_margin.get(date, 0.0)) + proposed_margin
        ) * BROKER10_MULTIPLIER
        margin_gate_skipped = int(bool(targets) and required_margin > prev_equity)
        if margin_gate_skipped:
            targets = {}
            contract_specs = {}
            proposed_margin = 0.0
            pnl = 0.0

        turnover = 0
        slippage_cost = 0.0
        for contract in set(prev_positions) | set(targets):
            delta = abs(targets.get(contract, 0) - prev_positions.get(contract, 0))
            if delta <= 0:
                continue
            turnover += delta
            _product, tick_value = contract_specs.get(contract, prev_contract_specs.get(contract, ("", 0.0)))
            slippage_cost += delta * tick_value

        overlay_daily_pnl = pnl - slippage_cost
        rows.append(
            {
                "date": date,
                "window_name": window_name,
                "variant": spec.variant,
                "overlay_daily_pnl": overlay_daily_pnl,
                "overlay_slippage_cost": slippage_cost,
                "overlay_margin": proposed_margin,
                "overlay_turnover_contracts": turnover,
                "overlay_held_contract_count": len(targets),
                "overlay_desired_product_count": desired_count,
                "overlay_rebalance": 1,
                "overlay_margin_gate_skipped": margin_gate_skipped,
            }
        )
        prev_positions = targets
        prev_contract_specs = contract_specs
        prev_equity += float(c3_pnl.get(date, 0.0)) + float(xsmom_pnl.get(date, 0.0)) + overlay_daily_pnl

    return pd.DataFrame(rows)


def _calendarize_daily(daily: pd.DataFrame) -> pd.DataFrame:
    daily = daily.sort_values("date").drop_duplicates("date", keep="last")
    calendar = pd.DataFrame({"date": pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")})
    merged = calendar.merge(daily, on="date", how="left")
    merged["equity"] = pd.to_numeric(merged["equity"], errors="coerce").ffill()
    for col in ["trade_count", "combo_slippage"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0.0)
    return merged.dropna(subset=["equity"])


def _drawdown(nav: np.ndarray) -> np.ndarray:
    return nav / np.maximum.accumulate(nav) - 1.0


def _ulcer(nav: np.ndarray) -> float:
    dd = np.minimum(_drawdown(nav) * 100.0, 0.0)
    return float(np.sqrt(np.mean(np.square(dd)))) if len(dd) else 0.0


def _rolling_pairwise(full_daily: pd.DataFrame) -> pd.DataFrame:
    windows = (90, 180, 252, 504)
    candidate_variants = [CONSENSUS_BEST1_VARIANT, CONSENSUS_SHORT1_VARIANT]
    comparators = [BASELINE_VARIANT, STAGE103_VARIANT]
    by_variant = {
        variant: _calendarize_daily(frame[frame["window_name"].eq("start_2020")])
        for variant, frame in full_daily.groupby("variant")
    }
    rows: list[dict[str, Any]] = []
    for candidate_variant in candidate_variants:
        candidate = by_variant.get(candidate_variant)
        if candidate is None or candidate.empty:
            continue
        candidate = candidate.set_index("date")
        for comparator_variant in comparators:
            comparator = by_variant.get(comparator_variant)
            if comparator is None or comparator.empty:
                continue
            comparator = comparator.set_index("date")
            common = candidate[["equity"]].rename(columns={"equity": "candidate_equity"}).join(
                comparator[["equity"]].rename(columns={"equity": "comparator_equity"}),
                how="inner",
            )
            for window_days in windows:
                return_deltas: list[float] = []
                maxdd_not_worse: list[int] = []
                ulcer_not_worse: list[int] = []
                for start_date in common.index:
                    end_date = start_date + pd.Timedelta(days=window_days)
                    if end_date > common.index.max():
                        continue
                    sub = common.loc[start_date:end_date]
                    if len(sub) < 2:
                        continue
                    c_nav = sub["candidate_equity"].to_numpy(dtype=float) / float(sub["candidate_equity"].iloc[0])
                    b_nav = sub["comparator_equity"].to_numpy(dtype=float) / float(sub["comparator_equity"].iloc[0])
                    c_ret = (float(c_nav[-1]) - 1.0) * 100.0
                    b_ret = (float(b_nav[-1]) - 1.0) * 100.0
                    c_dd = float(_drawdown(c_nav).min() * 100.0)
                    b_dd = float(_drawdown(b_nav).min() * 100.0)
                    c_ulcer = _ulcer(c_nav)
                    b_ulcer = _ulcer(b_nav)
                    return_deltas.append(c_ret - b_ret)
                    maxdd_not_worse.append(int(c_dd >= b_dd - 1e-12))
                    ulcer_not_worse.append(int(c_ulcer <= b_ulcer + 1e-12))
                deltas = np.asarray(return_deltas, dtype=float)
                rows.append(
                    {
                        "candidate_variant": candidate_variant,
                        "comparator_variant": comparator_variant,
                        "window_days": window_days,
                        "count": int(len(deltas)),
                        "return_win_rate": float(np.mean(deltas >= -1e-12)) if len(deltas) else np.nan,
                        "return_delta_median_pp": float(np.median(deltas)) if len(deltas) else np.nan,
                        "return_delta_p05_pp": float(np.percentile(deltas, 5)) if len(deltas) else np.nan,
                        "maxdd_not_worse_rate": float(np.mean(maxdd_not_worse)) if maxdd_not_worse else np.nan,
                        "ulcer_not_worse_rate": float(np.mean(ulcer_not_worse)) if ulcer_not_worse else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def _top_edge_day_ablation(full_daily: pd.DataFrame) -> pd.DataFrame:
    candidate_variants = [CONSENSUS_BEST1_VARIANT, CONSENSUS_SHORT1_VARIANT]
    comparators = [BASELINE_VARIANT, STAGE103_VARIANT]
    remove_counts = (0, 1, 3, 5, 10, 20)
    full = full_daily[full_daily["window_name"].eq("start_2020")].copy()
    by_variant = {variant: _calendarize_daily(frame) for variant, frame in full.groupby("variant")}
    rows: list[dict[str, Any]] = []
    for candidate_variant in candidate_variants:
        candidate = by_variant.get(candidate_variant)
        if candidate is None or candidate.empty:
            continue
        candidate = candidate.set_index("date")
        c_pnl = candidate["equity"].diff().fillna(candidate["equity"].iloc[0] - ACCOUNT_CAPITAL)
        for comparator_variant in comparators:
            comparator = by_variant.get(comparator_variant)
            if comparator is None or comparator.empty:
                continue
            comparator = comparator.set_index("date")
            b_pnl = comparator["equity"].diff().fillna(comparator["equity"].iloc[0] - ACCOUNT_CAPITAL)
            edge = (c_pnl - b_pnl).sort_values(ascending=False)
            for n in remove_counts:
                adjusted_pnl = c_pnl.copy()
                if n > 0:
                    adjusted_pnl.loc[edge.head(n).index] -= edge.head(n)
                adjusted_equity = ACCOUNT_CAPITAL + adjusted_pnl.cumsum()
                nav = adjusted_equity.to_numpy(dtype=float) / ACCOUNT_CAPITAL
                adjusted_return = (float(nav[-1]) - 1.0) * 100.0
                adjusted_maxdd = float(_drawdown(nav).min() * 100.0)
                adjusted_ulcer = _ulcer(nav)
                b_nav = comparator["equity"].to_numpy(dtype=float) / ACCOUNT_CAPITAL
                b_return = (float(b_nav[-1]) - 1.0) * 100.0
                b_maxdd = float(_drawdown(b_nav).min() * 100.0)
                b_ulcer = _ulcer(b_nav)
                rows.append(
                    {
                        "candidate_variant": candidate_variant,
                        "comparator_variant": comparator_variant,
                        "removed_top_positive_edge_days": n,
                        "removed_edge_pnl": float(edge.head(n).sum()) if n > 0 else 0.0,
                        "candidate_adjusted_total_return_pct": adjusted_return,
                        "candidate_adjusted_max_dd_pct": adjusted_maxdd,
                        "candidate_adjusted_ulcer_pct": adjusted_ulcer,
                        "comparator_total_return_pct": b_return,
                        "comparator_max_dd_pct": b_maxdd,
                        "comparator_ulcer_pct": b_ulcer,
                        "adjusted_return_delta_pp": adjusted_return - b_return,
                        "adjusted_maxdd_delta_pp": adjusted_maxdd - b_maxdd,
                        "adjusted_ulcer_delta_pp": adjusted_ulcer - b_ulcer,
                    }
                )
    return pd.DataFrame(rows)


def _plot(full_daily: pd.DataFrame, score: pd.DataFrame, pairwise: pd.DataFrame, topday: pd.DataFrame) -> None:
    variants = [spec.variant for spec in VARIANTS]
    labels = ["Stage079", "Stage103", "ConsBest1", "ConsShort1", "ConsAll"]
    full = full_daily[full_daily["window_name"].eq("start_2020")]
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    for variant, frame in full.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=1.0)
        axes[1, 0].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=0.9)
    axes[0, 0].set_title("Full-period NAV")
    axes[0, 0].legend(fontsize=6)
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=6)

    x = np.arange(len(variants))
    s90 = score[score["horizon_days"].eq(90)].set_index("variant").reindex(variants)
    s180 = score[score["horizon_days"].eq(180)].set_index("variant").reindex(variants)
    axes[0, 1].bar(x - 0.18, s90["experience_score"].to_numpy(dtype=float), 0.36, label="90d score")
    axes[0, 1].bar(x + 0.18, s180["experience_score"].to_numpy(dtype=float), 0.36, label="180d score")
    axes[0, 1].axhline(110.0, color="#777777", linestyle="--", linewidth=0.8)
    axes[0, 1].set_title("Short holding scores")
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(labels, rotation=25, ha="right", fontsize=7)
    axes[0, 1].legend(fontsize=8)

    pw = pairwise[
        pairwise["comparator_variant"].eq(STAGE103_VARIANT) & pairwise["window_days"].isin([90, 180, 252, 504])
    ]
    for variant, frame in pw.groupby("candidate_variant"):
        axes[1, 1].plot(frame["window_days"], frame["return_win_rate"], marker="o", label=variant)
    axes[1, 1].axhline(0.5, color="#777777", linestyle="--", linewidth=0.8)
    axes[1, 1].set_title("Return win rate vs Stage103")
    axes[1, 1].set_ylim(0, 1)
    axes[1, 1].legend(fontsize=7)
    fig.suptitle("Stage117 CFFEX index 60/120 consensus overlay", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    fresh: pd.DataFrame,
    cost: pd.DataFrame,
    margin_audit: pd.DataFrame,
    gate: pd.DataFrame,
    pairwise: pd.DataFrame,
    topday: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage117 Stage103股指60/120一致性Overlay审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：低自由度结构审计；不改 Stage079/Stage103/C3 规则，不增加账户资金。",
        "- A/B/C：A=Stage079；C0=Stage103；C1/C2/C3=股指60/120趋势一致性过滤 overlay。",
        "- 外部判断：TSMOM/managed futures 有跨资产依据，但 Stage116 已证明固定路径收益可能集中，因此本阶段先加一致性过滤，再做顶部贡献日与任意启动检查。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 全周期核心指标",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "ulcer_pct",
                    "rolling252_dd30_breach_rate",
                    "rolling504_dd30_breach_rate",
                    "annual_cold_start_dd30_pass_rate",
                    "quarter_cold_start_dd30_pass_rate",
                ]
            ]
        ),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(
            horizon[
                [
                    "variant",
                    "horizon_days",
                    "return_p05_pct",
                    "return_median_pct",
                    "positive_return_rate",
                    "annualized_below_5pct_rate",
                    "max_dd_worst_pct",
                    "dd20_breach_rate",
                    "dd30_breach_rate",
                    "ulcer_p95_pct",
                    "longest_underwater_p95_days",
                ]
            ]
        ),
        "",
        "## 体验评分",
        "",
        _md_table(
            score[
                [
                    "variant",
                    "horizon_days",
                    "experience_score",
                    "improved_metric_count",
                    "target_hit_count",
                    "score_90d",
                    "score_180d",
                    "short_holding_score",
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
                    "metric_hard_pass_stage079",
                    "metric_incremental_pass_stage103",
                    "target_pass_3m6m_vs_stage079",
                    "research_promotion_pass",
                    "execution_relative_pass",
                    "deployment_absolute_margin_pass",
                    "score_90d",
                    "score_180d",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "failed_stage079_metric_checks",
                    "failed_stage103_incremental_checks",
                ]
            ]
        ),
        "",
        "## 任意启动收益/风险相对胜率",
        "",
        _md_table(pairwise),
        "",
        "## 顶部相对贡献日剔除",
        "",
        _md_table(topday),
        "",
        "## 多起点与10%保证金缓冲",
        "",
        _md_table(
            fresh[
                [
                    "window_name",
                    "variant",
                    "total_return_pct",
                    "max_dd_pct",
                    "dd30_pass",
                    "overlay_turnover",
                    "overlay_gate_skipped_days",
                    "broker10_max_margin_to_equity_pct",
                    "broker10_reject_days",
                ]
            ],
            max_rows=120,
        ),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "variant",
                    "slippage_multiplier",
                    "total_return_pct",
                    "max_dd_pct",
                    "stage079_max_dd_pct",
                    "stage103_max_dd_pct",
                    "not_worse_than_stage079_stress",
                    "not_worse_than_stage103_stress",
                ]
            ]
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段不扫相邻小数，不按日期/品种/贡献日补丁救 Stage115。",
        "- 60/120一致性是预声明结构：用一个较快窗口做方向和强度，用一个较慢窗口确认，目的是降低单一窗口和单一路径依赖。",
        "- 若一致性过滤仍不能通过硬约束、任意启动收益或顶部贡献日剔除，则股指 overlay 子路线继续降级，不再调窗口组合。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    old_variants = s405.VARIANTS
    s405.VARIANTS = VARIANTS
    try:
        combo = s402._load_combo_daily()
        margin = s402._load_margin()
        full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
        scale_by_date = s402._build_stage101_scale(full_frame)
        price_frame = s402._build_price_frame()
        price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
        signals = s402._load_signal_daily()
        signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()
        consensus_panel = _build_consensus_panel()

        xsmom_by_window: dict[str, pd.DataFrame] = {}
        overlay_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        overlay_full_by_variant: dict[str, pd.DataFrame] = {}
        candidates: list[Any] = []
        full_daily_parts: list[pd.DataFrame] = []

        for window_name, frame in combo.groupby("window_name", sort=True):
            frame = frame.sort_values("date").drop_duplicates("date", keep="last")
            margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
            xsmom = s403._simulate_guarded_round_half(window_name, frame, margin_frame, price_frame, signals, scale_by_date)
            xsmom_by_window[window_name] = xsmom
            for spec in VARIANTS:
                if spec.variant in {BASELINE_VARIANT, STAGE103_VARIANT}:
                    overlay = _empty_overlay(window_name, spec.variant)
                else:
                    overlay = _simulate_consensus_overlay(spec, window_name, frame, margin_frame, xsmom, consensus_panel)
                overlay_by_window_variant[(window_name, spec.variant)] = overlay
                use_xsmom = s405._empty_xsmom(window_name) if spec.variant == BASELINE_VARIANT else xsmom
                daily = s405._combine_daily(frame, use_xsmom, overlay, spec.variant, 1.0)
                daily["window_name"] = window_name
                daily_by_window_variant[(window_name, spec.variant)] = daily
                if window_name == "start_2020":
                    overlay_full_by_variant[spec.variant] = overlay

        for spec in VARIANTS:
            daily = daily_by_window_variant[("start_2020", spec.variant)]
            full_daily_parts.append(daily)
            equity = s402._calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
            candidates.append(s405._candidate(spec, equity))

        full_daily = pd.concat(full_daily_parts, ignore_index=True)
        overlay_all = pd.concat([frame for frame in overlay_by_window_variant.values() if not frame.empty], ignore_index=True)
        summary = pd.DataFrame([s402.s087._stats(candidate) for candidate in candidates])
        horizon = pd.DataFrame(
            [s402.s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)]
        )
        score = s402.s087._score_horizons(horizon)
        margin_audit = s405._margin_audit(combo, margin, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant)
        fresh = s405._fresh_start(combo, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant, margin_audit)
        cost = s405._cost_stress(full_frame, xsmom_by_window["start_2020"], overlay_full_by_variant)
        bad_windows = s405._bad_window_contribution(
            {spec.variant: daily_by_window_variant[("start_2020", spec.variant)] for spec in VARIANTS}
        )
        gate = s405._gate(summary, horizon, score, cost, fresh, margin_audit, bad_windows)
        pairwise = _rolling_pairwise(full_daily)
        topday = _top_edge_day_ablation(full_daily)
    finally:
        s405.VARIANTS = old_variants

    candidate_variants = [CONSENSUS_BEST1_VARIANT, CONSENSUS_SHORT1_VARIANT]
    execution_ready = gate[gate["execution_relative_pass"].eq(1) & gate["variant"].isin(candidate_variants)]
    robust_ready: list[str] = []
    for variant in execution_ready["variant"].tolist():
        pw = pairwise[pairwise["candidate_variant"].eq(variant) & pairwise["comparator_variant"].eq(STAGE103_VARIANT)]
        td = topday[
            topday["candidate_variant"].eq(variant)
            & topday["comparator_variant"].eq(STAGE103_VARIANT)
            & topday["removed_top_positive_edge_days"].eq(1)
        ]
        rolling_ok = bool((pw["return_win_rate"].fillna(0.0) >= 0.45).all()) if not pw.empty else False
        topday_ok = bool((td["adjusted_return_delta_pp"].fillna(-1e9) >= 0.0).all()) if not td.empty else False
        if rolling_ok and topday_ok:
            robust_ready.append(variant)

    decision = {
        "stage": "Stage117",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "robust_execution_relative_candidate"
        if robust_ready
        else ("fixed_path_candidate_but_robustness_gap" if len(execution_ready) else "no_new_promotion"),
        "execution_relative_ready_variants": execution_ready["variant"].tolist(),
        "robust_ready_variants": robust_ready,
        "chart": str(CHART_PATH),
        "judgement": "60/120一致性过滤若不能同时通过Stage079硬闸门、Stage103增量闸门、任意启动收益胜率和顶部贡献日剔除，则不继续调窗口或救Stage115。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    margin_audit.to_csv(MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")
    bad_windows.to_csv(BAD_WINDOW_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    full_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    overlay_all.to_csv(OVERLAY_PATH, index=False, encoding="utf-8-sig")
    consensus_panel.to_csv(CONSENSUS_PANEL_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    topday.to_csv(TOPDAY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(full_daily, score, pairwise, topday)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, gate, pairwise, topday, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
