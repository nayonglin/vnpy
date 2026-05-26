from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    MARGIN_REJECT_PCT,
    MARGIN_REVIEW_PCT,
    TOTAL_CAPITAL,
    _c3_overrides,
    _margin_daily,
    _metadata,
    _safe_float,
    _to_builtin,
    _to_markdown_table,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR, build_positions_df
from run_qmt_roll_backtest import run_backtest as run_roll_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage336_c3_cash_reserve_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage336_c3_cash_reserve_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

RETURN_RETENTION_GATE_PCT: float = 90.0
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)


@dataclass(frozen=True)
class DeploymentProfile:
    name: str
    label: str
    active_weight: float

    @property
    def active_capital(self) -> float:
        return TOTAL_CAPITAL * self.active_weight

    @property
    def cash_reserve(self) -> float:
        return TOTAL_CAPITAL - self.active_capital


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    start: datetime
    end: datetime
    group: str


PROFILES: tuple[DeploymentProfile, ...] = (
    DeploymentProfile("c3_active100_cash0", "C3 100%风险资金", 1.00),
    DeploymentProfile("c3_active95_cash5", "C3 95%风险资金 + 5%现金", 0.95),
    DeploymentProfile("c3_active90_cash10", "C3 90%风险资金 + 10%现金", 0.90),
)

WINDOWS: tuple[Window, ...] = (
    Window("start_2020", "2020起点至今", START_DT, END_DT, "start_year"),
    Window("start_2021", "2021起点至今", datetime(2021, 1, 1), END_DT, "start_year"),
    Window("start_2022", "2022起点至今", datetime(2022, 1, 1), END_DT, "start_year"),
    Window("start_2023", "2023起点至今", datetime(2023, 1, 1), END_DT, "start_year"),
    Window("start_2024", "2024起点至今", datetime(2024, 1, 1), END_DT, "start_year"),
    Window("start_2025", "2025起点至今", datetime(2025, 1, 1), END_DT, "start_year"),
    Window("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT, "start_year"),
    Window("weak_2021_full", "2021弱窗口全年", datetime(2021, 1, 1), datetime(2021, 12, 31), "weak_window"),
    Window("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31), "weak_window"),
)


def _daily_from_analysis(
    analysis_df: pd.DataFrame | None,
    *,
    profile: DeploymentProfile,
    window: Window,
) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "active_balance",
                "active_net_pnl",
                "active_slippage",
                "trade_count",
                "balance",
                "profile",
                "window_name",
            ]
        )

    frame = analysis_df.copy().reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    frame["active_balance"] = pd.to_numeric(
        frame.get("balance", profile.active_capital),
        errors="coerce",
    ).ffill().fillna(profile.active_capital)
    frame["active_net_pnl"] = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    frame["active_slippage"] = pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0)
    frame["trade_count"] = pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    frame["balance"] = profile.cash_reserve + frame["active_balance"]
    frame["profile"] = profile.name
    frame["profile_label"] = profile.label
    frame["active_weight"] = profile.active_weight
    frame["active_capital"] = profile.active_capital
    frame["cash_reserve"] = profile.cash_reserve
    frame["window_name"] = window.name
    frame["window_label"] = window.label
    return frame[
        [
            "date",
            "profile",
            "profile_label",
            "window_name",
            "window_label",
            "active_weight",
            "active_capital",
            "cash_reserve",
            "active_balance",
            "active_net_pnl",
            "active_slippage",
            "trade_count",
            "balance",
        ]
    ]


def _path_metrics_from_balance(balance: pd.Series, *, capital: float = TOTAL_CAPITAL) -> dict[str, float]:
    if balance.empty:
        return {
            "end_balance": capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
        }
    values = pd.to_numeric(balance, errors="coerce").ffill().fillna(capital).to_numpy(dtype=float)
    high = np.maximum.accumulate(values)
    drawdown = values - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0) * 100.0
    returns = pd.Series(values).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252)) if std > 0 else 0.0
    return {
        "end_balance": float(values[-1]),
        "total_return_pct": float((values[-1] / capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "max_drawdown": float(drawdown.min()),
        "sharpe_ratio": sharpe,
    }


def _margin_summary_for_profile(
    positions: pd.DataFrame,
    metadata: dict[str, Any],
    daily: pd.DataFrame,
) -> dict[str, Any]:
    if daily.empty:
        return {
            "max_margin_to_equity_pct": 0.0,
            "p95_margin_to_equity_pct": 0.0,
            "review_days": 0,
            "reject_days": 0,
            "max_active_products": 0,
        }
    margin = daily[["date", "balance"]].copy()
    margin = margin.merge(_margin_daily(positions, metadata, "active"), on="date", how="left")
    for column in ["active_margin", "active_active_products"]:
        margin[column] = pd.to_numeric(margin.get(column, 0.0), errors="coerce").fillna(0.0)
    margin["margin_to_equity_pct"] = (
        margin["active_margin"] / margin["balance"].replace(0.0, np.nan) * 100.0
    ).fillna(0.0)
    return {
        "max_margin_to_equity_pct": _safe_float(margin["margin_to_equity_pct"].max()),
        "p95_margin_to_equity_pct": _safe_float(margin["margin_to_equity_pct"].quantile(0.95)),
        "review_days": int((margin["margin_to_equity_pct"] >= MARGIN_REVIEW_PCT).sum()),
        "reject_days": int((margin["margin_to_equity_pct"] >= MARGIN_REJECT_PCT).sum()),
        "max_active_products": int(margin["active_active_products"].max()) if "active_active_products" in margin else 0,
    }


def _window_gate(baseline_return: float, candidate_return: float, candidate_dd: float) -> tuple[int, float]:
    if baseline_return > 0:
        retention = candidate_return / baseline_return * 100.0
        ok = candidate_dd >= -30.0 and retention >= RETURN_RETENTION_GATE_PCT
        return int(ok), retention
    ok = candidate_dd >= -30.0 and candidate_return >= baseline_return
    return int(ok), math.nan


def _run_profile(
    profile: DeploymentProfile,
    window: Window,
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame]:
    preload_start = max(PRELOAD_START_DT, window.start - timedelta(days=365))
    print(
        f"[stage336] run {profile.name} {window.name} active_capital={profile.active_capital:.0f}",
        flush=True,
    )
    engine, analysis_df, statistics = run_roll_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_c3_overrides(window.start),
        analysis_start=window.start,
        analysis_end=window.end,
        preload_start=preload_start,
        capital=profile.active_capital,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_{profile.name}_{window.name}",
        chart_title=f"Stage336 {profile.label} {window.label}",
    )
    daily = _daily_from_analysis(analysis_df, profile=profile, window=window)
    metrics = _path_metrics_from_balance(daily["balance"] if not daily.empty else pd.Series(dtype=float))
    margin_metrics = _margin_summary_for_profile(build_positions_df(engine), metadata, daily)
    row = {
        "profile": profile.name,
        "profile_label": profile.label,
        "window_name": window.name,
        "window_label": window.label,
        "window_group": window.group,
        "analysis_start": window.start.date().isoformat(),
        "analysis_end": window.end.date().isoformat(),
        "active_weight": profile.active_weight,
        "active_capital": profile.active_capital,
        "cash_reserve": profile.cash_reserve,
        "end_balance": metrics["end_balance"],
        "total_return_pct": metrics["total_return_pct"],
        "max_dd_pct": metrics["max_dd_percent"],
        "max_drawdown": metrics["max_drawdown"],
        "sharpe": metrics["sharpe_ratio"],
        "active_engine_return_pct": _safe_float(statistics.get("total_return")),
        "active_engine_max_dd_pct": _safe_float(statistics.get("max_ddpercent")),
        "total_slippage": _safe_float(statistics.get("total_slippage")),
        "total_trade_count": int(_safe_float(statistics.get("total_trade_count"))),
        "win_ratio_pct": _safe_float(statistics.get("win_ratio")),
        **margin_metrics,
    }
    return row, daily


def _add_relative_gates(summary_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary_df.groupby("window_name", sort=False):
        baseline = group[group["profile"].eq("c3_active100_cash0")]
        if baseline.empty:
            continue
        baseline_row = baseline.iloc[0]
        baseline_return = float(baseline_row["total_return_pct"])
        baseline_dd = float(baseline_row["max_dd_pct"])
        for _, row in group.iterrows():
            item = row.to_dict()
            gate_ok, retention = _window_gate(
                baseline_return,
                float(row["total_return_pct"]),
                float(row["max_dd_pct"]),
            )
            item["baseline_return_pct"] = baseline_return
            item["baseline_max_dd_pct"] = baseline_dd
            item["return_retention_vs_baseline_pct"] = retention
            item["dd_improvement_vs_baseline_pct"] = float(row["max_dd_pct"]) - baseline_dd
            item["window_gate_ok"] = gate_ok
            item["dd_lt_30_ok"] = int(float(row["max_dd_pct"]) >= -30.0)
            item["retention_ge_90_ok"] = int(
                baseline_return > 0
                and not math.isnan(retention)
                and retention >= RETURN_RETENTION_GATE_PCT
            )
            rows.append(item)
    return pd.DataFrame(rows)


def _build_slippage_stress(daily_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    full = daily_df[daily_df["window_name"].eq("start_2020")].copy()
    if full.empty:
        return pd.DataFrame()
    for profile_name, group in full.groupby("profile", sort=False):
        group = group.sort_values("date").copy()
        profile_label = str(group["profile_label"].iloc[0])
        active_weight = float(group["active_weight"].iloc[0])
        cash_reserve = float(group["cash_reserve"].iloc[0])
        for multiplier in SLIPPAGE_MULTIPLIERS:
            stressed = group.copy()
            stressed["stressed_active_net_pnl"] = stressed["active_net_pnl"] - (
                multiplier - 1.0
            ) * stressed["active_slippage"]
            stressed["balance"] = cash_reserve + group["active_capital"].iloc[0] + stressed[
                "stressed_active_net_pnl"
            ].cumsum()
            metrics = _path_metrics_from_balance(stressed["balance"])
            rows.append(
                {
                    "profile": profile_name,
                    "profile_label": profile_label,
                    "active_weight": active_weight,
                    "slippage_multiplier": multiplier,
                    "total_return_pct": metrics["total_return_pct"],
                    "max_dd_pct": metrics["max_dd_percent"],
                    "sharpe": metrics["sharpe_ratio"],
                    "total_slippage": float(group["active_slippage"].sum() * multiplier),
                }
            )
    stress_df = pd.DataFrame(rows)
    if stress_df.empty:
        return stress_df
    baseline = stress_df[stress_df["profile"].eq("c3_active100_cash0")][
        ["slippage_multiplier", "total_return_pct", "max_dd_pct"]
    ].rename(
        columns={
            "total_return_pct": "baseline_return_pct",
            "max_dd_pct": "baseline_max_dd_pct",
        }
    )
    stress_df = stress_df.merge(baseline, on="slippage_multiplier", how="left")
    stress_df["return_retention_vs_baseline_pct"] = np.where(
        stress_df["baseline_return_pct"] > 0,
        stress_df["total_return_pct"] / stress_df["baseline_return_pct"] * 100.0,
        np.nan,
    )
    stress_df["stress_gate_ok"] = (
        (stress_df["max_dd_pct"] >= -30.0)
        & (stress_df["return_retention_vs_baseline_pct"] >= RETURN_RETENTION_GATE_PCT)
    ).astype(int)
    return stress_df


def _build_report(summary_df: pd.DataFrame, stress_df: pd.DataFrame) -> str:
    lines = [
        "# Stage336 C3部署层现金留白多周期验证",
        "",
        "## 目标",
        "",
        "- 不改 C3 入场、出场、AI池、品种池和止损逻辑，只改变账户层可用于策略的风险资金。",
        "- 只测试 `95%` 和 `90%` 两个粗档位，避免围绕 `30%` 回撤线做小数调参。",
        f"- 收益闸门：正收益窗口相对 100% C3 保留至少 `{RETURN_RETENTION_GATE_PCT:.0f}%`，且候选最大回撤不低于 `-30%`。",
        "",
        "## 多周期结果",
        "",
    ]
    display_cols = [
        "window_name",
        "profile",
        "total_return_pct",
        "return_retention_vs_baseline_pct",
        "max_dd_pct",
        "dd_improvement_vs_baseline_pct",
        "sharpe",
        "max_margin_to_equity_pct",
        "review_days",
        "reject_days",
        "window_gate_ok",
    ]
    lines.append(_to_markdown_table(summary_df, display_cols, max_rows=200))
    lines.extend(["", "## 全样本滑点压力", ""])
    if stress_df.empty:
        lines.append("_empty_")
    else:
        lines.append(
            _to_markdown_table(
                stress_df,
                [
                    "profile",
                    "slippage_multiplier",
                    "total_return_pct",
                    "return_retention_vs_baseline_pct",
                    "max_dd_pct",
                    "sharpe",
                    "stress_gate_ok",
                ],
                max_rows=100,
            )
        )
    lines.extend(["", "## 阶段判断", ""])
    candidate_rows = summary_df[~summary_df["profile"].eq("c3_active100_cash0")].copy()
    positive_or_control = candidate_rows[
        candidate_rows["window_group"].isin(["start_year", "weak_window"])
    ]
    pass_counts = (
        positive_or_control.groupby("profile")["window_gate_ok"].agg(["sum", "count"]).reset_index()
        if not positive_or_control.empty
        else pd.DataFrame()
    )
    if pass_counts.empty:
        lines.append("- 没有候选完成有效验证。")
    else:
        for _, row in pass_counts.iterrows():
            lines.append(f"- `{row['profile']}`：多周期通过 `{int(row['sum'])}/{int(row['count'])}`。")
        full_candidates = candidate_rows[candidate_rows["window_name"].eq("start_2020")]
        best_full = full_candidates.sort_values(
            ["window_gate_ok", "total_return_pct"],
            ascending=[False, False],
        ).head(1)
        if not best_full.empty:
            row = best_full.iloc[0]
            lines.append(
                f"- 全样本最优候选 `{row['profile']}`：收益 `{row['total_return_pct']:.4f}%`，"
                f"最大回撤 `{row['max_dd_pct']:.4f}%`，收益保留 `{row['return_retention_vs_baseline_pct']:.2f}%`。"
            )
    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 本阶段低过拟合：只验证粗档资金留白，不用历史弱品种或单一年份做补丁。",
            "- 如果 `95%` 只在全样本刚好过线，但多起点失败，就不能继续调 `96%/94%` 救结果。",
            "",
            "## 继续价值反思",
            "",
            "- 有价值：这是实盘部署层能真实执行的风控动作，且不会污染 C3 alpha。",
            "- 但它只能解决账户回撤口径，不代表策略本身回撤结构已经消失。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = _metadata()
    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []

    for window in WINDOWS:
        for profile in PROFILES:
            row, daily = _run_profile(profile, window, metadata)
            summary_rows.append(row)
            daily_frames.append(daily)

    summary_df = _add_relative_gates(pd.DataFrame(summary_rows))
    daily_df = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
    stress_df = _build_slippage_stress(daily_df)

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
    stress_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    daily_df.to_csv(daily_path, index=False, encoding="utf-8-sig")
    stress_df.to_csv(stress_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(summary_df, stress_df), encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "total_capital": TOTAL_CAPITAL,
        "return_retention_gate_pct": RETURN_RETENTION_GATE_PCT,
        "profiles": [
            {
                "name": profile.name,
                "active_weight": profile.active_weight,
                "active_capital": profile.active_capital,
                "cash_reserve": profile.cash_reserve,
            }
            for profile in PROFILES
        ],
        "full_window": summary_df[summary_df["window_name"].eq("start_2020")].to_dict(orient="records"),
        "failed_candidate_windows": summary_df[
            (~summary_df["profile"].eq("c3_active100_cash0")) & (summary_df["window_gate_ok"].eq(0))
        ].to_dict(orient="records"),
        "slippage_stress": stress_df.to_dict(orient="records"),
        "paths": {
            "summary": str(summary_path),
            "daily": str(daily_path),
            "slippage_stress": str(stress_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[stage336] summary={summary_path}")
    print(f"[stage336] daily={daily_path}")
    print(f"[stage336] slippage_stress={stress_path}")
    print(f"[stage336] report={report_path}")
    print(f"[stage336] decision={decision_path}")
    print(report_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
