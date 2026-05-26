from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    LINE_ID,
    TOTAL_CAPITAL,
    _c3_overrides,
    _safe_float,
    _to_builtin,
    _to_markdown_table,
)
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import run_backtest as run_roll_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage354_c3_max_trade_risk_cap_frontier_v1"
OUTPUT_PREFIX = "qmt_roll_stage354_c3_max_trade_risk_cap_frontier"


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    max_risk_per_trade: float | None


FULL_WINDOW = Window("full_2020_2026", "2020起点至今", START_DT, END_DT)

WINDOWS: tuple[Window, ...] = (
    FULL_WINDOW,
    Window("start_2021", "2021起点至今", datetime(2021, 1, 1), END_DT),
    Window("start_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    Window("start_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    Window("start_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    Window("start_2025", "2025起点至今", datetime(2025, 1, 1), END_DT),
    Window("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT),
    Window("year_2021", "2021独立窗口", datetime(2021, 1, 1), datetime(2021, 12, 31)),
    Window("phase_2024_2025", "2024-2025独立窗口", datetime(2024, 1, 1), datetime(2025, 12, 31)),
)

PROFILES: tuple[Profile, ...] = (
    Profile("baseline", "C3原始单笔风险", None),
    Profile("cap_22500", "单笔风险上限2.25万", 22_500.0),
    Profile("cap_30000", "单笔风险上限3.00万", 30_000.0),
    Profile("cap_37500", "单笔风险上限3.75万", 37_500.0),
    Profile("cap_45000", "单笔风险上限4.50万", 45_000.0),
    Profile("cap_60000", "单笔风险上限6.00万", 60_000.0),
)

FULL_DD_GATE = -30.0
RETENTION_GATE = 80.0


def _run_profile(window: Window, profile: Profile) -> dict[str, Any]:
    overrides = _c3_overrides(window.start)
    if profile.max_risk_per_trade is not None:
        overrides["max_risk_per_trade"] = profile.max_risk_per_trade
    preload_start = max(PRELOAD_START_DT, window.start - timedelta(days=365))
    print(
        f"[stage354] run {profile.name} {window.name} "
        f"max_risk={profile.max_risk_per_trade or 'default'}",
        flush=True,
    )
    _, _, statistics = run_roll_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=overrides,
        analysis_start=window.start,
        analysis_end=window.end,
        preload_start=preload_start,
        capital=TOTAL_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_{profile.name}_{window.name}",
        chart_title=f"Stage354 {profile.label} {window.label}",
    )
    return {
        "window_name": window.name,
        "window_label": window.label,
        "analysis_start": window.start.date().isoformat(),
        "analysis_end": window.end.date().isoformat(),
        "profile_name": profile.name,
        "profile_label": profile.label,
        "max_risk_per_trade": profile.max_risk_per_trade,
        "end_balance": _safe_float(statistics.get("end_balance")),
        "total_return_pct": _safe_float(statistics.get("total_return")),
        "max_dd_pct": _safe_float(statistics.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
        "return_drawdown_ratio": _safe_float(statistics.get("return_drawdown_ratio")),
        "total_trade_count": int(_safe_float(statistics.get("total_trade_count"))),
        "total_slippage": _safe_float(statistics.get("total_slippage")),
        "total_commission": _safe_float(statistics.get("total_commission")),
        "win_ratio_pct": _safe_float(statistics.get("win_ratio")),
    }


def _retention(candidate_return: float, baseline_return: float) -> float:
    if baseline_return > 0:
        return candidate_return / baseline_return * 100.0
    return math.nan


def _annotate(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    baseline = (
        df[df["profile_name"].eq("baseline")]
        .set_index("window_name")[["total_return_pct", "max_dd_pct", "sharpe_ratio", "total_trade_count"]]
        .rename(
            columns={
                "total_return_pct": "baseline_return_pct",
                "max_dd_pct": "baseline_max_dd_pct",
                "sharpe_ratio": "baseline_sharpe",
                "total_trade_count": "baseline_trade_count",
            }
        )
    )
    df = df.merge(baseline, on="window_name", how="left")
    df["return_retention_vs_baseline_pct"] = df.apply(
        lambda row: _retention(float(row["total_return_pct"]), float(row["baseline_return_pct"])),
        axis=1,
    )
    df["max_dd_improvement_pct_point"] = df["max_dd_pct"] - df["baseline_max_dd_pct"]
    df["trade_count_diff_vs_baseline"] = df["total_trade_count"] - df["baseline_trade_count"]
    df["dd_gate_ok"] = (df["max_dd_pct"] >= FULL_DD_GATE).astype(int)
    df["positive_return_window"] = (df["baseline_return_pct"] > 0).astype(int)
    df["retention_gate_ok"] = np.where(
        df["baseline_return_pct"] > 0,
        (df["return_retention_vs_baseline_pct"] >= RETENTION_GATE).astype(int),
        (df["total_return_pct"] >= df["baseline_return_pct"]).astype(int),
    )
    df["window_gate_ok"] = ((df["dd_gate_ok"] == 1) & (df["retention_gate_ok"] == 1)).astype(int)
    return df


def _select_full_candidates(full_df: pd.DataFrame) -> list[str]:
    candidates = full_df[
        (~full_df["profile_name"].eq("baseline"))
        & (full_df["dd_gate_ok"] == 1)
        & (full_df["retention_gate_ok"] == 1)
    ]["profile_name"].tolist()
    return candidates


def _profile_summary(window_df: pd.DataFrame) -> pd.DataFrame:
    if window_df.empty:
        return pd.DataFrame()
    grouped = []
    for profile_name, group in window_df.groupby("profile_name", sort=False):
        positive = group[group["baseline_return_pct"] > 0]
        full = group[group["window_name"].eq(FULL_WINDOW.name)]
        full_row = full.iloc[0] if not full.empty else group.iloc[0]
        grouped.append(
            {
                "profile_name": profile_name,
                "profile_label": str(full_row["profile_label"]),
                "max_risk_per_trade": full_row["max_risk_per_trade"],
                "full_return_pct": _safe_float(full_row["total_return_pct"]),
                "full_max_dd_pct": _safe_float(full_row["max_dd_pct"]),
                "full_retention_pct": _safe_float(full_row["return_retention_vs_baseline_pct"]),
                "full_sharpe": _safe_float(full_row["sharpe_ratio"]),
                "full_trade_count": int(_safe_float(full_row["total_trade_count"])),
                "window_gate_pass_count": int(group["window_gate_ok"].sum()),
                "window_count": int(len(group)),
                "positive_window_gate_pass_count": int(positive["window_gate_ok"].sum()),
                "positive_window_count": int(len(positive)),
                "min_positive_retention_pct": _safe_float(positive["return_retention_vs_baseline_pct"].min(), math.nan),
                "worst_window_max_dd_pct": _safe_float(group["max_dd_pct"].min()),
                "decision": "pending",
            }
        )
    result = pd.DataFrame(grouped)
    if result.empty:
        return result
    result["decision"] = np.where(
        (~result["profile_name"].eq("baseline"))
        & (result["full_max_dd_pct"] >= FULL_DD_GATE)
        & (result["full_retention_pct"] >= RETENTION_GATE)
        & (result["positive_window_gate_pass_count"] == result["positive_window_count"])
        & (result["worst_window_max_dd_pct"] >= FULL_DD_GATE),
        "candidate_requires_slippage_stress",
        "fail_or_baseline",
    )
    return result


def _build_report(full_screen_df: pd.DataFrame, window_df: pd.DataFrame, summary_df: pd.DataFrame) -> str:
    lines = [
        "# Stage354 C3单笔风险上限真实引擎筛查",
        "",
        "## 目标",
        "",
        "- 不改 C3 的入场、AI池、品种池和出场逻辑，只测试已有 `max_risk_per_trade` 参数。",
        "- 经济含义：权益复利放大后，单笔风险不再无限跟随账户权益增长，而是限制在粗粒度绝对风险预算内。",
        "- 预声明粗档位：2.25万、3.00万、3.75万、4.50万、6.00万；不做小数救援。",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟随长期有效的证据更支持分散和风险预算，而不是单窗口补丁；波动缩放/风险预算类方法在文献中是常见结构。",
        "- 但本线前序已经反证了多个账户层波动预算形状，所以本阶段只验证更窄的单笔风险集中度，而不是重新调全局波动阈值。",
        "",
        "## 全周期粗筛",
        "",
    ]
    display_full = [
        "profile_name",
        "max_risk_per_trade",
        "total_return_pct",
        "max_dd_pct",
        "return_retention_vs_baseline_pct",
        "max_dd_improvement_pct_point",
        "sharpe_ratio",
        "total_trade_count",
        "dd_gate_ok",
        "retention_gate_ok",
        "window_gate_ok",
    ]
    lines.append(_to_markdown_table(full_screen_df, display_full))
    lines.extend(["", "## 多周期复验", ""])
    if window_df.empty or window_df["window_name"].nunique() <= 1:
        lines.append("- 全周期没有同时满足回撤与收益保留的候选，因此未展开多周期复验。")
    else:
        display_windows = [
            "window_name",
            "profile_name",
            "total_return_pct",
            "max_dd_pct",
            "return_retention_vs_baseline_pct",
            "max_dd_improvement_pct_point",
            "sharpe_ratio",
            "window_gate_ok",
        ]
        lines.append(_to_markdown_table(window_df, display_windows, max_rows=120))
    lines.extend(["", "## 汇总判断", ""])
    if summary_df.empty:
        lines.append("- 未生成有效汇总。")
    else:
        display_summary = [
            "profile_name",
            "max_risk_per_trade",
            "full_return_pct",
            "full_max_dd_pct",
            "full_retention_pct",
            "positive_window_gate_pass_count",
            "positive_window_count",
            "min_positive_retention_pct",
            "worst_window_max_dd_pct",
            "decision",
        ]
        lines.append(_to_markdown_table(summary_df, display_summary))
        promoted = summary_df[summary_df["decision"].eq("candidate_requires_slippage_stress")]
        if promoted.empty:
            lines.append("")
            lines.append("- 结论：本轮没有出现可晋级到滑点压力测试的单笔风险上限候选。")
        else:
            names = "、".join(promoted["profile_name"].astype(str).tolist())
            lines.append("")
            lines.append(f"- 结论：`{names}` 通过本轮多周期粗筛，下一步必须做 2x/3x 滑点压力和交易路径差异归因。")
    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 本阶段不是按结果微调阈值，而是测试少数有经济含义的粗档位；如果失败，不继续围绕相邻小数救结果。",
            "- 它只使用下单前已知的权益/风险预算参数，不引入未来收益、未来回撤或事后品种信息。",
            "",
            "## 继续价值反思",
            "",
            "- 有价值：若成功，它可以直接落在已有真实引擎参数上；若失败，也能更清楚地界定 C3 的自然回撤边界。",
            "- 下一步取决于是否出现候选：有候选则补滑点压力；无候选则停止单笔风险上限路线，回到真正独立收益源或部署层现金边界。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for profile in PROFILES:
        rows.append(_run_profile(FULL_WINDOW, profile))

    full_screen_df = _annotate(rows)
    full_candidates = _select_full_candidates(full_screen_df)

    if full_candidates:
        selected_profiles = [profile for profile in PROFILES if profile.name == "baseline" or profile.name in full_candidates]
        existing_keys = {(row["window_name"], row["profile_name"]) for row in rows}
        for window in WINDOWS:
            for profile in selected_profiles:
                key = (window.name, profile.name)
                if key in existing_keys:
                    continue
                rows.append(_run_profile(window, profile))

    window_df = _annotate(rows)
    summary_df = _profile_summary(window_df)

    full_screen_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_screen_{MODEL_TAG}.csv"
    window_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_results_{MODEL_TAG}.csv"
    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    full_screen_df.to_csv(full_screen_path, index=False, encoding="utf-8-sig")
    window_df.to_csv(window_path, index=False, encoding="utf-8-sig")
    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(full_screen_df, window_df, summary_df), encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital": TOTAL_CAPITAL,
        "profiles": [profile.__dict__ for profile in PROFILES],
        "full_candidates": full_candidates,
        "decision": "candidate_requires_slippage_stress"
        if not summary_df[summary_df["decision"].eq("candidate_requires_slippage_stress")].empty
        else "no_candidate",
        "paths": {
            "full_screen": str(full_screen_path),
            "window_results": str(window_path),
            "summary": str(summary_path),
            "report": str(report_path),
        },
        "summary": summary_df.to_dict(orient="records"),
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[stage354] full_screen={full_screen_path}")
    print(f"[stage354] window_results={window_path}")
    print(f"[stage354] summary={summary_path}")
    print(f"[stage354] report={report_path}")
    print(f"[stage354] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
