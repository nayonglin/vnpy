from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage319_supply_headwind_risk_scale_validation import C3_OVERRIDES


MODEL_TAG = "stage356_c3_time_scale_diversification_scout_v1"
OUTPUT_PREFIX = "qmt_roll_stage356_c3_time_scale_diversification_scout"
LINE_ID = "futures_trend_drawdown30_preserve_return"

TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    ma_short: int
    ma_mid: int
    ma_long: int
    ma_extra_long: int


PROFILES: tuple[Profile, ...] = (
    Profile("C3_base_5_10_20_40", "C3基准周期5/10/20/40", 5, 10, 20, 40),
    Profile("C3_fast_3_6_12_24", "C3快周期3/6/12/24", 3, 6, 12, 24),
    Profile("C3_slow_10_20_40_80", "C3慢周期10/20/40/80", 10, 20, 40, 80),
)

WINDOWS: tuple[tuple[str, str, datetime, datetime], ...] = (
    ("start_2020", "2020起点至今", START_DT, END_DT),
    ("start_2021", "2021起点至今", datetime(2021, 1, 1), END_DT),
    ("start_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    ("start_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    ("start_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    ("start_2025", "2025起点至今", datetime(2025, 1, 1), END_DT),
    ("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT),
    ("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31)),
)

BLEND_SPECS: tuple[tuple[str, dict[str, float]], ...] = (
    ("blend_base70_fast30", {"C3_base_5_10_20_40": 0.70, "C3_fast_3_6_12_24": 0.30}),
    ("blend_base80_fast20", {"C3_base_5_10_20_40": 0.80, "C3_fast_3_6_12_24": 0.20}),
    ("blend_base70_slow30", {"C3_base_5_10_20_40": 0.70, "C3_slow_10_20_40_80": 0.30}),
    ("blend_base80_slow20", {"C3_base_5_10_20_40": 0.80, "C3_slow_10_20_40_80": 0.20}),
    (
        "blend_base60_fast20_slow20",
        {
            "C3_base_5_10_20_40": 0.60,
            "C3_fast_3_6_12_24": 0.20,
            "C3_slow_10_20_40_80": 0.20,
        },
    ),
)


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_builtin(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_builtin(item) for item in value]
    if isinstance(value, tuple):
        return [_to_builtin(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        if np.isnan(result) or np.isinf(result):
            return None
        return result
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _profile_overrides(profile: Profile, analysis_start: datetime) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides["trade_start_date"] = analysis_start.date().isoformat()
    overrides.update(C3_OVERRIDES)
    overrides.update(
        {
            "ma_short": profile.ma_short,
            "ma_mid": profile.ma_mid,
            "ma_long": profile.ma_long,
            "ma_extra_long": profile.ma_extra_long,
            "array_manager_size_floor": max(120, profile.ma_extra_long + 60),
            "warmup_days": max(120, profile.ma_extra_long + 60),
        }
    )
    return overrides


def _run_profile(
    profile: Profile,
    window_name: str,
    display_label: str,
    analysis_start: datetime,
    analysis_end: datetime,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    preload_start = max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    _, analysis_df, statistics = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_profile_overrides(profile, analysis_start),
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        preload_start=preload_start,
        capital=OFFICIAL_STAGE78_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_{profile.name}_{window_name}",
        chart_title=f"Stage356 {profile.label} {display_label}",
    )
    return analysis_df, statistics


def _path_metrics(nav: pd.Series) -> dict[str, float]:
    values = pd.to_numeric(nav, errors="coerce").dropna().to_numpy(dtype=float)
    if len(values) == 0:
        return {"total_return_pct": 0.0, "max_dd_pct": 0.0, "sharpe": 0.0}
    high = np.maximum.accumulate(values)
    dd = np.divide(values - high, high, out=np.zeros_like(values), where=high != 0.0) * 100.0
    returns = pd.Series(values).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252.0)) if std > 0 else 0.0
    return {
        "total_return_pct": float((values[-1] - 1.0) * 100.0),
        "max_dd_pct": float(dd.min()),
        "sharpe": sharpe,
    }


def _run_suite() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []

    for window_name, display_label, analysis_start, analysis_end in WINDOWS:
        for profile in PROFILES:
            print(f"[stage356] {window_name} {profile.name}", flush=True)
            analysis_df, statistics = _run_profile(profile, window_name, display_label, analysis_start, analysis_end)
            summary_rows.append(
                build_summary_row(
                    statistics,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    variant=profile.name,
                    display_label=profile.label,
                    window_name=window_name,
                    official_version=OFFICIAL_STAGE78_VERSION,
                    official_role=OFFICIAL_STAGE78_ROLE,
                    model_tag=MODEL_TAG,
                    capital=OFFICIAL_STAGE78_CAPITAL,
                    base_risk_ratio=BASE_RISK_RATIO,
                    ma_short=profile.ma_short,
                    ma_mid=profile.ma_mid,
                    ma_long=profile.ma_long,
                    ma_extra_long=profile.ma_extra_long,
                    total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                    total_slippage=float(statistics.get("total_slippage", 0) or 0),
                    total_commission=float(statistics.get("total_commission", 0) or 0),
                    profit_days=int(statistics.get("profit_days", 0) or 0),
                    loss_days=int(statistics.get("loss_days", 0) or 0),
                )
            )
            if analysis_df is not None and not analysis_df.empty:
                curve_df = analysis_df[["balance"]].reset_index().rename(columns={"index": "date"})
                curve_df["date"] = pd.to_datetime(curve_df["date"]).dt.normalize()
                curve_df["variant"] = profile.name
                curve_df["display_label"] = profile.label
                curve_df["window_name"] = window_name
                first_balance = float(curve_df["balance"].iloc[0] or OFFICIAL_STAGE78_CAPITAL)
                curve_df["normalized_nav"] = curve_df["balance"] / max(1e-9, first_balance)
                curve_frames.append(curve_df)

    summary_df = pd.DataFrame(summary_rows)
    curves_df = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()
    return summary_df, curves_df


def _build_correlation(curves_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if curves_df.empty:
        return pd.DataFrame(rows)
    for window_name, group in curves_df.groupby("window_name", sort=False):
        pivot = group.pivot_table(index="date", columns="variant", values="normalized_nav", aggfunc="last").sort_index()
        returns = pivot.pct_change().fillna(0.0)
        variants = list(returns.columns)
        for i, left in enumerate(variants):
            for right in variants[i + 1 :]:
                rows.append(
                    {
                        "window_name": window_name,
                        "left_variant": left,
                        "right_variant": right,
                        "daily_return_corr": float(returns[left].corr(returns[right])),
                    }
                )
    return pd.DataFrame(rows)


def _build_blends(curves_df: pd.DataFrame, summary_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if curves_df.empty:
        return pd.DataFrame(rows)
    base_by_window = summary_df[summary_df["variant"].eq("C3_base_5_10_20_40")].set_index("window_name")
    for window_name, group in curves_df.groupby("window_name", sort=False):
        pivot = group.pivot_table(index="date", columns="variant", values="normalized_nav", aggfunc="last").sort_index()
        if "C3_base_5_10_20_40" not in pivot.columns:
            continue
        base_return = float(base_by_window.loc[window_name, "total_return_pct"]) if window_name in base_by_window.index else 0.0
        positive_base = base_return > 0.0
        for blend_name, weights in BLEND_SPECS:
            if not all(variant in pivot.columns for variant in weights):
                continue
            total_weight = sum(weights.values())
            nav = sum(pivot[variant].ffill().fillna(1.0) * (weight / total_weight) for variant, weight in weights.items())
            metrics = _path_metrics(nav)
            retention = metrics["total_return_pct"] / base_return * 100.0 if base_return > 0.0 else np.nan
            gate_ok = metrics["max_dd_pct"] >= TARGET_MAX_DD_PCT and (
                not positive_base or retention >= RETURN_RETENTION_GATE_PCT
            )
            rows.append(
                {
                    "window_name": window_name,
                    "blend_name": blend_name,
                    "weights_json": json.dumps(weights, ensure_ascii=False, sort_keys=True),
                    "base_return_pct": base_return,
                    "blend_return_pct": metrics["total_return_pct"],
                    "retention_vs_base_pct": retention,
                    "blend_max_dd_pct": metrics["max_dd_pct"],
                    "blend_sharpe": metrics["sharpe"],
                    "positive_base_window": int(positive_base),
                    "gate_ok": int(gate_ok),
                }
            )
    return pd.DataFrame(rows)


def _build_report(summary_df: pd.DataFrame, corr_df: pd.DataFrame, blend_df: pd.DataFrame) -> str:
    full_summary = summary_df[summary_df["window_name"].eq("start_2020")].copy()
    multi = (
        summary_df.groupby("variant", as_index=False)
        .agg(
            min_return_pct=("total_return_pct", "min"),
            full_return_pct=("total_return_pct", lambda s: float(summary_df.loc[s.index][summary_df.loc[s.index, "window_name"].eq("start_2020")]["total_return_pct"].iloc[0]) if any(summary_df.loc[s.index, "window_name"].eq("start_2020")) else np.nan),
            worst_max_dd_pct=("max_dd_percent", "min"),
            median_sharpe=("sharpe_ratio", "median"),
            total_trades_full=("total_trade_count", lambda s: int(summary_df.loc[s.index][summary_df.loc[s.index, "window_name"].eq("start_2020")]["total_trade_count"].iloc[0]) if any(summary_df.loc[s.index, "window_name"].eq("start_2020")) else 0),
        )
        .sort_values(["worst_max_dd_pct", "full_return_pct"], ascending=[False, False])
    )
    full_corr = corr_df[corr_df["window_name"].eq("start_2020")].copy()
    blend_full = blend_df[blend_df["window_name"].eq("start_2020")].copy()
    blend_multi = (
        blend_df.groupby("blend_name", as_index=False)
        .agg(
            gate_pass_count=("gate_ok", "sum"),
            window_count=("gate_ok", "count"),
            min_retention_vs_base_pct=("retention_vs_base_pct", "min"),
            worst_max_dd_pct=("blend_max_dd_pct", "min"),
            full_return_pct=("blend_return_pct", lambda s: float(blend_df.loc[s.index][blend_df.loc[s.index, "window_name"].eq("start_2020")]["blend_return_pct"].iloc[0]) if any(blend_df.loc[s.index, "window_name"].eq("start_2020")) else np.nan),
        )
        .sort_values(["gate_pass_count", "worst_max_dd_pct", "min_retention_vs_base_pct"], ascending=[False, False, False])
        if not blend_df.empty
        else pd.DataFrame()
    )
    return "\n".join(
        [
            "# Stage356 C3时间尺度分散侦察",
            "",
            "## 定位",
            "",
            "- 不替换正式第78-1，也不修改 C3 正式候选；本阶段只侦察不同固定趋势周期是否能成为低相关卫星。",
            "- 周期只取三组结构化倍数：`3/6/12/24`、`5/10/20/40`、`10/20/40/80`，不做小数阈值搜索。",
            "- 净值组合只用于判断相关性和路径互补，若出现线索，后续必须再做真实资金拆分和滑点压力。",
            "",
            "## 单版本全样本",
            "",
            to_markdown_table(
                full_summary[
                    [
                        "variant",
                        "total_return_pct",
                        "max_dd_percent",
                        "sharpe_ratio",
                        "total_trade_count",
                        "total_slippage",
                        "win_ratio_pct",
                    ]
                ]
            ),
            "",
            "## 单版本多窗口",
            "",
            to_markdown_table(
                multi[
                    [
                        "variant",
                        "full_return_pct",
                        "min_return_pct",
                        "worst_max_dd_pct",
                        "median_sharpe",
                        "total_trades_full",
                    ]
                ]
            ),
            "",
            "## 全样本日收益相关性",
            "",
            to_markdown_table(full_corr),
            "",
            "## 净值组合全样本",
            "",
            to_markdown_table(
                blend_full[
                    [
                        "blend_name",
                        "base_return_pct",
                        "blend_return_pct",
                        "retention_vs_base_pct",
                        "blend_max_dd_pct",
                        "blend_sharpe",
                        "gate_ok",
                    ]
                ]
            ),
            "",
            "## 净值组合多窗口",
            "",
            to_markdown_table(blend_multi),
            "",
            "## 结论",
            "",
            "- 本阶段只回答“时间尺度是否有分散价值”，不直接晋级实盘候选。",
            "- 若快/慢周期与基准相关性高且净值组合不能稳定压入30%回撤，停止该方向；若组合多窗口稳定改善，再进入真实资金拆分复验。",
            "",
            "## 反思",
            "",
            "- 是否过拟合：否。周期组是预先固定的整数倍结构，不根据历史弱窗口微调。",
            "- 是否还有价值继续：有，但只在出现低相关和多窗口改善时继续；否则应停止，避免在同源趋势参数里消耗样本。",
        ]
    )


def main() -> None:
    assert_stage196_database_sentinels()
    manifest = build_official_stage78_manifest()
    summary_df, curves_df = _run_suite()
    corr_df = _build_correlation(curves_df)
    blend_df = _build_blends(curves_df, summary_df)

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    curves_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
    corr_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_correlation_{MODEL_TAG}.csv"
    blend_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blend_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    curves_df.to_csv(curves_path, index=False, encoding="utf-8-sig")
    corr_df.to_csv(corr_path, index=False, encoding="utf-8-sig")
    blend_df.to_csv(blend_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(summary_df, corr_df, blend_df), encoding="utf-8")

    full_base = summary_df[
        summary_df["window_name"].eq("start_2020") & summary_df["variant"].eq("C3_base_5_10_20_40")
    ].iloc[0]
    full_blends = blend_df[blend_df["window_name"].eq("start_2020")].copy()
    best_full_blend = (
        full_blends.sort_values(["gate_ok", "blend_max_dd_pct", "retention_vs_base_pct"], ascending=[False, False, False])
        .head(1)
        .to_dict("records")
    )
    blend_multi = (
        blend_df.groupby("blend_name", as_index=False)
        .agg(
            gate_pass_count=("gate_ok", "sum"),
            window_count=("gate_ok", "count"),
            min_retention_vs_base_pct=("retention_vs_base_pct", "min"),
            worst_max_dd_pct=("blend_max_dd_pct", "min"),
        )
        .sort_values(["gate_pass_count", "worst_max_dd_pct", "min_retention_vs_base_pct"], ascending=[False, False, False])
    )
    best_multi_blend = blend_multi.head(1).to_dict("records")
    all_window_pass = bool((blend_multi["gate_pass_count"] == blend_multi["window_count"]).any())
    decision = {
        "decision": "fail_multiperiod_time_scale_source_not_promoted"
        if not all_window_pass
        else "scout_promising_requires_true_capital_validation",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "manifest": manifest,
        "target_max_dd_pct": TARGET_MAX_DD_PCT,
        "return_retention_gate_pct": RETURN_RETENTION_GATE_PCT,
        "base_full_return_pct": float(full_base["total_return_pct"]),
        "base_full_max_dd_pct": float(full_base["max_dd_percent"]),
        "best_full_blend": best_full_blend[0] if best_full_blend else {},
        "best_multi_blend": best_multi_blend[0] if best_multi_blend else {},
        "all_window_pass": all_window_pass,
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage356] report: {report_path}")


if __name__ == "__main__":
    main()
