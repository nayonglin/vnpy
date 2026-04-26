from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import (
    _calculate_daily_risk,
    _calculate_margin_path,
    _to_markdown_table,
)
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df, build_positions_df
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import CYCLE_WINDOWS
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage160_capital_governance_direction_sweep_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage160_capital_governance_direction_sweep"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
DIRECTION_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_direction_summary_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
DAILY_MARGIN_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_margin_{MODEL_TAG}.csv"
RUN_LOG_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_run_log_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

WINDOW_NAMES: tuple[str, ...] = (
    "full_2020_2026",
    "pre_ai_2020_2021",
    "post_signal_2022_2026",
    "latest_2026",
)


@dataclass(frozen=True)
class DirectionProfile:
    direction_id: str
    profile_name: str
    hypothesis: str
    strategy_overrides: dict[str, Any]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _target_windows() -> tuple[dict[str, Any], ...]:
    by_name = {str(window["window_name"]): window for window in CYCLE_WINDOWS}
    return tuple(by_name[name] for name in WINDOW_NAMES)


def _build_profiles() -> tuple[DirectionProfile, ...]:
    base = build_official_stage78_overrides()

    def with_base(**updates: Any) -> dict[str, Any]:
        overrides = dict(base)
        overrides.update(updates)
        return overrides

    return (
        DirectionProfile(
            direction_id="D1_static_lower_cap",
            profile_name="C_static_cap_800k",
            hypothesis="把100万固定上限下移为80万容量墙，检验峰值风险是否主要来自过高的静态sizing权益。",
            strategy_overrides=with_base(sizing_equity_cap=800_000.0),
        ),
        DirectionProfile(
            direction_id="D2_lower_base_soft_release",
            profile_name="C_soft_cap_800k_to_1m",
            hypothesis="把100万从基础仓位改成健康状态下的上限，只有低回撤低保证金压力时才从80万释放到100万。",
            strategy_overrides=with_base(
                sizing_equity_cap=800_000.0,
                enable_dynamic_sizing_equity_soft_cap=True,
                dynamic_sizing_equity_soft_cap_base=800_000.0,
                dynamic_sizing_equity_soft_cap_max=1_000_000.0,
                dynamic_sizing_equity_soft_cap_participation=0.50,
                dynamic_sizing_equity_soft_cap_margin_start_ratio=0.60,
                dynamic_sizing_equity_soft_cap_margin_full_ratio=0.80,
                dynamic_sizing_equity_soft_cap_drawdown_start_ratio=0.05,
                dynamic_sizing_equity_soft_cap_drawdown_full_ratio=0.20,
            ),
        ),
        DirectionProfile(
            direction_id="D3_total_budget_cap",
            profile_name="C_total_budget_75",
            hypothesis="保留100万sizing墙，但把组合层资金占用预算从90%降到75%，直接约束多品种并发峰值。",
            strategy_overrides=with_base(max_capital_usage_ratio=0.75),
        ),
        DirectionProfile(
            direction_id="D4_single_trade_budget_cap",
            profile_name="C_single_trade_budget_35",
            hypothesis="保留组合预算，只把单笔资金预算从70%降到35%，检验单品种保证金集中是否可被结构性削峰。",
            strategy_overrides=with_base(max_single_trade_capital_usage_ratio=0.35),
        ),
        DirectionProfile(
            direction_id="D5_peak_guard_rank1",
            profile_name="C_peak_guard90_rank1",
            hypothesis="在同日可开候选拥挤时启用增量保证金预算门，只保护排序第一，治理同日多新品种峰值。",
            strategy_overrides=with_base(
                enable_incremental_margin_budget_gate=True,
                incremental_margin_budget_gate_usage_ratio=0.90,
                incremental_margin_budget_gate_min_openable_candidates=2,
                incremental_margin_budget_gate_protected_selection_rank=1,
            ),
        ),
        DirectionProfile(
            direction_id="D6_portfolio_drawdown_gate",
            profile_name="C_drawdown_gate_10_25_floor50",
            hypothesis="在组合进入10%-25%回撤带时渐进降仓，检验资金治理是否应由权益状态而非固定金额触发。",
            strategy_overrides=with_base(
                enable_portfolio_drawdown_gate=True,
                portfolio_drawdown_gate_start_pct=0.10,
                portfolio_drawdown_gate_full_pct=0.25,
                portfolio_drawdown_gate_weight_floor=0.50,
            ),
        ),
    )


def _slice_margin(daily_margin: pd.DataFrame, analysis_start: datetime, analysis_end: datetime) -> pd.DataFrame:
    if daily_margin.empty:
        return pd.DataFrame()
    frame = daily_margin.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    start = pd.Timestamp(analysis_start).normalize()
    end = pd.Timestamp(analysis_end).normalize()
    return frame[(frame["date"] >= start) & (frame["date"] <= end)].copy()


def _margin_summary(
    engine: Any,
    daily: pd.DataFrame,
    analysis_start: datetime,
    analysis_end: datetime,
    profile_name: str,
    window_name: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    daily_df = daily.copy() if daily is not None else pd.DataFrame()
    if not daily_df.empty:
        daily_df.sort_index(inplace=True)
    positions = build_positions_df(engine)
    daily_risk = _calculate_daily_risk(daily_df, OFFICIAL_STAGE78_CAPITAL)
    daily_margin, _ = _calculate_margin_path(positions, daily_risk, capital=OFFICIAL_STAGE78_CAPITAL)
    sliced = _slice_margin(daily_margin, analysis_start, analysis_end)
    if sliced.empty:
        return {
            "max_margin_to_balance_pct": 0.0,
            "max_margin_date": "",
            "margin_days_gt_60pct": 0,
            "margin_days_gt_80pct": 0,
            "margin_days_gt_100pct": 0,
            "max_active_product_count": 0.0,
        }, pd.DataFrame()

    margin = pd.to_numeric(sliced["total_margin_to_balance_pct"], errors="coerce").fillna(0.0)
    max_idx = margin.idxmax()
    sliced.insert(0, "window_name", window_name)
    sliced.insert(0, "profile_name", profile_name)
    return {
        "max_margin_to_balance_pct": _safe_float(margin.max()),
        "max_margin_date": str(sliced.loc[max_idx, "date"])[:10],
        "margin_days_gt_60pct": int((margin > 60.0).sum()),
        "margin_days_gt_80pct": int((margin > 80.0).sum()),
        "margin_days_gt_100pct": int((margin > 100.0).sum()),
        "max_active_product_count": _safe_float(
            pd.to_numeric(sliced.get("active_product_count", 0.0), errors="coerce").max()
        ),
    }, sliced


def _candidate_summary(engine: Any, profile_name: str, window_name: str) -> dict[str, Any]:
    candidates = build_entry_candidate_snapshots_df(engine)
    base = {
        "profile_name": profile_name,
        "window_name": window_name,
        "flat_candidate_count": 0,
        "opened_flat_entry_count": 0,
        "skipped_flat_entry_count": 0,
        "blocked_by_incremental_gate_count": 0,
        "blocked_by_sizing_zero_count": 0,
        "blocked_by_concurrent_limit_count": 0,
        "blocked_by_ai_pool_count": 0,
        "max_effective_sizing_equity_cap": 0.0,
        "median_effective_sizing_equity_cap": 0.0,
        "median_portfolio_drawdown_gate_weight": 1.0,
        "median_dynamic_release_weight": 0.0,
        "skip_reason_counts_json": "{}",
    }
    if candidates.empty:
        return base

    frame = candidates.copy()
    frame = frame[frame.get("entry_context", "").astype(str).eq("flat_entry")].copy()
    if frame.empty:
        return base

    for column in [
        "effective_sizing_equity_cap",
        "portfolio_drawdown_gate_weight",
        "dynamic_sizing_equity_soft_cap_release_weight",
    ]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)

    opened = frame[frame["candidate_status"].astype(str).eq("opened")]
    skipped = frame[frame["candidate_status"].astype(str).eq("skipped")]
    skip_counts = frame["skip_reason"].astype(str).value_counts().head(12).to_dict()
    base.update(
        {
            "flat_candidate_count": int(len(frame)),
            "opened_flat_entry_count": int(len(opened)),
            "skipped_flat_entry_count": int(len(skipped)),
            "blocked_by_incremental_gate_count": int((frame["skip_reason"].astype(str) == "incremental_margin_budget_gate").sum()),
            "blocked_by_sizing_zero_count": int((frame["skip_reason"].astype(str) == "sizing_zero_volume").sum()),
            "blocked_by_concurrent_limit_count": int((frame["skip_reason"].astype(str) == "concurrent_limit").sum()),
            "blocked_by_ai_pool_count": int((frame["skip_reason"].astype(str) == "ai_product_pool_blocked").sum()),
            "max_effective_sizing_equity_cap": _safe_float(frame["effective_sizing_equity_cap"].max()),
            "median_effective_sizing_equity_cap": _safe_float(frame["effective_sizing_equity_cap"].median()),
            "median_portfolio_drawdown_gate_weight": _safe_float(frame["portfolio_drawdown_gate_weight"].median(), 1.0),
            "median_dynamic_release_weight": _safe_float(frame["dynamic_sizing_equity_soft_cap_release_weight"].median()),
            "skip_reason_counts_json": json.dumps(skip_counts, ensure_ascii=False, sort_keys=True),
        }
    )
    return base


def _run_one(
    *,
    profile_name: str,
    direction_id: str,
    hypothesis: str,
    strategy_overrides: dict[str, Any],
    window: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame, pd.DataFrame]:
    window_name = str(window["window_name"])
    analysis_start: datetime = window["analysis_start"]
    analysis_end: datetime = window["analysis_end"]
    print(
        f"[stage160-capital-governance] {window_name} / {profile_name}: "
        f"{analysis_start.date()} -> {analysis_end.date()}",
        flush=True,
    )

    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, daily, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=strategy_overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    margin_row, daily_margin = _margin_summary(
        engine,
        daily,
        analysis_start,
        analysis_end,
        profile_name,
        window_name,
    )
    row = build_summary_row(
        statistics,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        model_tag=MODEL_TAG,
        direction_id=direction_id,
        hypothesis=hypothesis,
        profile_name=profile_name,
        base_version=OFFICIAL_STAGE78_VERSION,
        official_role=OFFICIAL_STAGE78_ROLE,
        window_name=window_name,
        display_label=str(window["display_label"]),
        capital=OFFICIAL_STAGE78_CAPITAL,
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
        strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
        **margin_row,
    )
    candidate_row = _candidate_summary(engine, profile_name, window_name)
    candidate_row.update({"direction_id": direction_id, "hypothesis": hypothesis})
    run_log = pd.DataFrame(
        {
            "profile_name": [profile_name],
            "window_name": [window_name],
            "log_line": ["\n".join(log_buffer.getvalue().splitlines()[-40:])],
        }
    )
    return row, candidate_row, daily_margin, run_log


def _build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    reference = summary[summary["profile_name"].astype(str).eq("A_official_stage78_reference")].copy()
    candidates = summary[~summary["profile_name"].astype(str).eq("A_official_stage78_reference")].copy()
    if reference.empty or candidates.empty:
        return pd.DataFrame()

    compare_columns = [
        "window_name",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
        "win_ratio_pct",
        "max_margin_to_balance_pct",
        "margin_days_gt_80pct",
        "margin_days_gt_100pct",
    ]
    merged = candidates.merge(
        reference[compare_columns],
        on="window_name",
        how="left",
        suffixes=("_c", "_a"),
    )
    for column in compare_columns[1:]:
        merged[f"{column}_diff"] = (
            pd.to_numeric(merged[f"{column}_c"], errors="coerce")
            - pd.to_numeric(merged[f"{column}_a"], errors="coerce")
        )
    return merged


def _direction_decision(direction_rows: pd.DataFrame) -> str:
    full_rows = direction_rows[direction_rows["window_name"].astype(str).eq("full_2020_2026")]
    if full_rows.empty:
        return "fail_no_full_window"
    full = full_rows.iloc[0]
    gt100_diff = _safe_float(full.get("margin_days_gt_100pct_diff"))
    gt80_diff = _safe_float(full.get("margin_days_gt_80pct_diff"))
    max_margin_diff = _safe_float(full.get("max_margin_to_balance_pct_diff"))
    total_return_diff = _safe_float(full.get("total_return_pct_diff"))
    sharpe_diff = _safe_float(full.get("sharpe_ratio_diff"))

    latest_rows = direction_rows[direction_rows["window_name"].astype(str).eq("latest_2026")]
    latest_worse = False
    if not latest_rows.empty:
        latest = latest_rows.iloc[0]
        latest_worse = (
            _safe_float(latest.get("total_return_pct_diff")) < -5.0
            or _safe_float(latest.get("max_dd_percent_diff")) < -5.0
        )

    if gt100_diff >= 0 and gt80_diff >= 0 and max_margin_diff >= -5.0:
        return "fail_no_material_peak_margin_improvement"
    if total_return_diff < -250.0 or sharpe_diff < -0.08:
        return "fail_return_quality_damage"
    if latest_worse:
        return "fail_latest_window_damage"
    if gt100_diff < 0 and gt80_diff < 0 and max_margin_diff <= -10.0:
        return "candidate_needs_quarterly_walkforward"
    return "research_only_mixed_result"


def _build_direction_summary(comparison: pd.DataFrame) -> pd.DataFrame:
    if comparison.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for (direction_id, profile_name), group in comparison.groupby(["direction_id", "profile_name"], sort=False):
        full_rows = group[group["window_name"].astype(str).eq("full_2020_2026")]
        full = full_rows.iloc[0].to_dict() if not full_rows.empty else {}
        rows.append(
            {
                "direction_id": direction_id,
                "profile_name": profile_name,
                "hypothesis": str(group["hypothesis"].iloc[0]),
                "decision": _direction_decision(group),
                "full_end_balance_diff": _safe_float(full.get("end_balance_diff")),
                "full_total_return_pct_diff": _safe_float(full.get("total_return_pct_diff")),
                "full_max_dd_percent_diff": _safe_float(full.get("max_dd_percent_diff")),
                "full_sharpe_diff": _safe_float(full.get("sharpe_ratio_diff")),
                "full_trade_count_diff": int(_safe_float(full.get("total_trade_count_diff"))),
                "full_slippage_diff": _safe_float(full.get("total_slippage_diff")),
                "full_max_margin_to_balance_pct_diff": _safe_float(full.get("max_margin_to_balance_pct_diff")),
                "full_margin_days_gt_80pct_diff": int(_safe_float(full.get("margin_days_gt_80pct_diff"))),
                "full_margin_days_gt_100pct_diff": int(_safe_float(full.get("margin_days_gt_100pct_diff"))),
                "windows_tested": int(group["window_name"].nunique()),
            }
        )
    return pd.DataFrame(rows)


def _build_report(summary: pd.DataFrame, comparison: pd.DataFrame, direction_summary: pd.DataFrame) -> str:
    result_columns = [
        "profile_name",
        "window_name",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
        "win_ratio_pct",
        "max_margin_to_balance_pct",
        "margin_days_gt_80pct",
        "margin_days_gt_100pct",
    ]
    comparison_columns = [
        "profile_name",
        "window_name",
        "end_balance_diff",
        "total_return_pct_diff",
        "max_dd_percent_diff",
        "sharpe_ratio_diff",
        "total_slippage_diff",
        "total_trade_count_diff",
        "max_margin_to_balance_pct_diff",
        "margin_days_gt_80pct_diff",
        "margin_days_gt_100pct_diff",
    ]
    direction_columns = [
        "direction_id",
        "profile_name",
        "decision",
        "full_total_return_pct_diff",
        "full_sharpe_diff",
        "full_max_margin_to_balance_pct_diff",
        "full_margin_days_gt_80pct_diff",
        "full_margin_days_gt_100pct_diff",
        "windows_tested",
    ]
    serious = direction_summary[
        direction_summary["decision"].astype(str).eq("candidate_needs_quarterly_walkforward")
    ]
    if serious.empty:
        judgement = (
            "本轮没有直接晋级候选；若所有方向都被判为失败或混合结果，100万硬上限暂时不能简单替换，"
            "下一步只能从新机制层面研究开仓分批/延迟，而不是继续调现有阈值。"
        )
    else:
        names = ", ".join(serious["profile_name"].astype(str).tolist())
        judgement = f"`{names}` 达到下一轮季度walk-forward触发条件，但仍不能直接替代第78正式版本。"

    return "\n".join(
        [
            "# Stage160 Capital Governance Direction Sweep",
            "",
            "## Boundary",
            "",
            "- A = `official_stage78_defensive_v1`.",
            "- C = Stage78 plus one predeclared deployment-layer capital/margin governance direction.",
            "- This experiment does not change product universe, entry/exit logic, AI pool, ranking, or signal definitions.",
            "- The goal is to test structural alternatives to the fixed `1,000,000` sizing-equity cap without product/date blacklists.",
            "",
            "## Predeclared Directions",
            "",
            _to_markdown_table(direction_summary[["direction_id", "profile_name", "hypothesis", "decision"]], max_rows=20)
            if not direction_summary.empty
            else "_pending_",
            "",
            "## Results",
            "",
            _to_markdown_table(summary[result_columns], max_rows=80),
            "",
            "## A Vs C",
            "",
            _to_markdown_table(comparison[comparison_columns], max_rows=120)
            if not comparison.empty
            else "_empty_",
            "",
            "## Direction Decisions",
            "",
            _to_markdown_table(direction_summary[direction_columns], max_rows=20)
            if not direction_summary.empty
            else "_empty_",
            "",
            "## Judgement",
            "",
            f"- {judgement}",
            "- A direction is considered serious only when it removes full-period >100% margin days, reduces >80% margin days, lowers max margin materially, and does not materially damage latest-window behavior.",
            "- Return improvement alone is not enough because this branch is deployment risk governance.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    windows = _target_windows()
    profiles = _build_profiles()

    summary_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    margin_frames: list[pd.DataFrame] = []
    run_log_frames: list[pd.DataFrame] = []

    reference_overrides = build_official_stage78_overrides()
    for window in windows:
        row, candidate_row, daily_margin, run_log = _run_one(
            profile_name="A_official_stage78_reference",
            direction_id="A_reference",
            hypothesis="第78正式基准，作为资金治理方向的冻结比较对象。",
            strategy_overrides=reference_overrides,
            window=window,
        )
        summary_rows.append(row)
        candidate_rows.append(candidate_row)
        if not daily_margin.empty:
            margin_frames.append(daily_margin)
        run_log_frames.append(run_log)

        for profile in profiles:
            row, candidate_row, daily_margin, run_log = _run_one(
                profile_name=profile.profile_name,
                direction_id=profile.direction_id,
                hypothesis=profile.hypothesis,
                strategy_overrides=profile.strategy_overrides,
                window=window,
            )
            summary_rows.append(row)
            candidate_rows.append(candidate_row)
            if not daily_margin.empty:
                margin_frames.append(daily_margin)
            run_log_frames.append(run_log)

    summary = pd.DataFrame(summary_rows)
    summary.sort_values(["analysis_start", "profile_name"], inplace=True)
    comparison = _build_comparison(summary)
    direction_summary = _build_direction_summary(comparison)
    candidate_summary = pd.DataFrame(candidate_rows)
    daily_margin_all = pd.concat(margin_frames, ignore_index=True, sort=False) if margin_frames else pd.DataFrame()
    run_log_all = pd.concat(run_log_frames, ignore_index=True, sort=False) if run_log_frames else pd.DataFrame()

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    direction_summary.to_csv(DIRECTION_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    daily_margin_all.to_csv(DAILY_MARGIN_CSV_PATH, index=False, encoding="utf-8-sig")
    run_log_all.to_csv(RUN_LOG_CSV_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(summary, comparison, direction_summary), encoding="utf-8")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "base_version": OFFICIAL_STAGE78_VERSION,
                "official_role": OFFICIAL_STAGE78_ROLE,
                "capital": OFFICIAL_STAGE78_CAPITAL,
                "base_risk_ratio": BASE_RISK_RATIO,
                "windows": [
                    {
                        "window_name": str(window["window_name"]),
                        "analysis_start": window["analysis_start"].date().isoformat(),
                        "analysis_end": window["analysis_end"].date().isoformat(),
                    }
                    for window in windows
                ],
                "profiles": [asdict(profile) for profile in profiles],
                "summary": summary.to_dict(orient="records"),
                "comparison": comparison.to_dict(orient="records"),
                "direction_summary": direction_summary.to_dict(orient="records"),
                "output_paths": {
                    "summary": str(SUMMARY_CSV_PATH),
                    "comparison": str(COMPARISON_CSV_PATH),
                    "direction_summary": str(DIRECTION_SUMMARY_CSV_PATH),
                    "candidate_summary": str(CANDIDATE_SUMMARY_CSV_PATH),
                    "daily_margin": str(DAILY_MARGIN_CSV_PATH),
                    "run_log": str(RUN_LOG_CSV_PATH),
                    "report": str(REPORT_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"[stage160-capital-governance] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage160-capital-governance] comparison: {COMPARISON_CSV_PATH}")
    print(f"[stage160-capital-governance] direction summary: {DIRECTION_SUMMARY_CSV_PATH}")
    print(f"[stage160-capital-governance] candidate summary: {CANDIDATE_SUMMARY_CSV_PATH}")
    print(f"[stage160-capital-governance] daily margin: {DAILY_MARGIN_CSV_PATH}")
    print(f"[stage160-capital-governance] report: {REPORT_PATH}")
    print(direction_summary.to_string(index=False))


if __name__ == "__main__":
    main()
