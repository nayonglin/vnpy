from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import _safe_float, _to_builtin, _to_markdown_table
from analyze_qmt_roll_stage345_cross_sectional_momentum_satellite import _path_metrics
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage351_xsmom_overlay_cash_screen_v1"
OUTPUT_PREFIX = "qmt_roll_stage351_xsmom_overlay_cash_screen"
LINE_ID = "futures_trend_drawdown30_preserve_return"

TOTAL_CAPITAL = 500_000.0
RETURN_GATE_PCT = 80.0
MAX_DD_GATE_PCT = -30.0
MARGIN_GATE_PCT = 100.0

C3_DAILY_STATE_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage327_c3_margin_concentration_overlay_probe_daily_state_"
    "stage327_c3_margin_concentration_overlay_probe_v1.csv"
)
XSMOM_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage346_xsmom_integer_feasibility_daily_"
    "stage346_xsmom_integer_feasibility_v1.csv"
)

CASH_LEVELS: tuple[float, ...] = (0.0, 30_000.0, 50_000.0, 67_000.0, 100_000.0, 115_000.0)
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    start: str
    end: str


WINDOWS: tuple[Window, ...] = (
    Window("full_2020_2026", "2020至今", "2020-01-01", "2026-04-30"),
    Window("weak_2021_full", "2021全年切片", "2021-01-01", "2021-12-31"),
    Window("phase_2024_2025", "2024-2025切片", "2024-01-01", "2025-12-31"),
    Window("ytd_2026", "2026年初至今切片", "2026-01-01", "2026-04-30"),
)


def _load_c3_daily() -> pd.DataFrame:
    if not C3_DAILY_STATE_PATH.exists():
        raise FileNotFoundError(C3_DAILY_STATE_PATH)
    frame = pd.read_csv(C3_DAILY_STATE_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["balance", "net_pnl", "slippage", "c3_margin"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return frame[["date", "balance", "net_pnl", "slippage", "c3_margin"]].rename(
        columns={
            "balance": "c3_balance",
            "net_pnl": "c3_net_pnl",
            "slippage": "c3_slippage",
        }
    )


def _load_xsmom_daily() -> pd.DataFrame:
    if not XSMOM_DAILY_PATH.exists():
        raise FileNotFoundError(XSMOM_DAILY_PATH)
    frame = pd.read_csv(XSMOM_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["daily_pnl", "slippage_cost", "actual_margin", "turnover_contracts"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return frame


def _required_cash_for_dd(base_equity: pd.Series, target_dd_pct: float = -30.0) -> float:
    equity = pd.to_numeric(base_equity, errors="coerce").ffill().fillna(TOTAL_CAPITAL)
    high = equity.cummax()
    floor_ratio = 1.0 + target_dd_pct / 100.0
    numerator = floor_ratio * high - equity
    denominator = 1.0 - floor_ratio
    required = numerator / denominator
    return max(0.0, float(required.max()))


def _required_cash_for_margin(base_equity: pd.Series, total_margin: pd.Series) -> float:
    equity = pd.to_numeric(base_equity, errors="coerce").ffill().fillna(TOTAL_CAPITAL)
    margin = pd.to_numeric(total_margin, errors="coerce").fillna(0.0)
    return max(0.0, float((margin - equity).max()))


def _path_from_pnl(frame: pd.DataFrame, pnl_column: str, initial_capital: float) -> pd.Series:
    return initial_capital + pd.to_numeric(frame[pnl_column], errors="coerce").fillna(0.0).cumsum()


def _slice_window(frame: pd.DataFrame, window: Window) -> pd.DataFrame:
    start = pd.Timestamp(window.start)
    end = pd.Timestamp(window.end)
    result = frame[frame["date"].between(start, end)].copy()
    return result.sort_values("date").reset_index(drop=True)


def _evaluate_profile_window(
    c3: pd.DataFrame,
    xsmom: pd.DataFrame,
    profile: str,
    window: Window,
    cash: float,
    slippage_multiplier: float,
) -> dict[str, Any]:
    sat = xsmom[xsmom["profile"].eq(profile)].copy()
    merged = c3.merge(
        sat[["date", "daily_pnl", "slippage_cost", "actual_margin", "turnover_contracts"]],
        on="date",
        how="left",
    )
    for column in ["daily_pnl", "slippage_cost", "actual_margin", "turnover_contracts"]:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    merged = _slice_window(merged, window)
    if merged.empty:
        raise RuntimeError(f"empty merged window {window.name} {profile}")

    merged["c3_stressed_pnl"] = merged["c3_net_pnl"] - (slippage_multiplier - 1.0) * merged["c3_slippage"]
    merged["sat_stressed_pnl"] = merged["daily_pnl"] - (slippage_multiplier - 1.0) * merged["slippage_cost"]
    merged["combo_pnl"] = merged["c3_stressed_pnl"] + merged["sat_stressed_pnl"]
    initial = TOTAL_CAPITAL + cash
    merged["account_balance"] = _path_from_pnl(merged, "combo_pnl", initial)
    merged["base_without_cash_balance"] = _path_from_pnl(merged, "combo_pnl", TOTAL_CAPITAL)
    merged["total_margin"] = merged["c3_margin"] + merged["actual_margin"]
    merged["margin_to_equity_pct"] = merged["total_margin"] / merged["account_balance"].replace(0.0, np.nan) * 100.0
    merged["margin_to_equity_pct"] = merged["margin_to_equity_pct"].fillna(0.0)

    c3_only = merged[["date", "c3_stressed_pnl"]].copy()
    c3_only["balance"] = _path_from_pnl(c3_only, "c3_stressed_pnl", TOTAL_CAPITAL)
    c3_metrics = _path_metrics(c3_only["balance"], TOTAL_CAPITAL)
    metrics = _path_metrics(merged["account_balance"], initial)
    return_pct = float(metrics["total_return_pct"])
    c3_return_pct = float(c3_metrics["total_return_pct"])
    retention = return_pct / c3_return_pct * 100.0 if c3_return_pct > 0 else math.nan
    max_margin_to_equity = float(merged["margin_to_equity_pct"].max())
    return {
        "profile": profile,
        "window_name": window.name,
        "window_label": window.label,
        "cash": cash,
        "slippage_multiplier": slippage_multiplier,
        "end_balance": float(metrics["end_balance"]),
        "total_return_pct": return_pct,
        "max_dd_pct": float(metrics["max_dd_percent"]),
        "sharpe": float(metrics["sharpe_ratio"]),
        "c3_return_pct": c3_return_pct,
        "c3_max_dd_pct": float(c3_metrics["max_dd_percent"]),
        "return_retention_vs_c3_pct": retention,
        "max_margin_to_equity_pct": max_margin_to_equity,
        "review_days": int((merged["margin_to_equity_pct"] >= 90.0).sum()),
        "reject_days": int((merged["margin_to_equity_pct"] > MARGIN_GATE_PCT).sum()),
        "total_turnover_contracts": int(merged["turnover_contracts"].sum()),
        "total_slippage": float((merged["c3_slippage"] + merged["slippage_cost"]).sum() * slippage_multiplier),
        "gate_ok": int(
            float(metrics["max_dd_percent"]) >= MAX_DD_GATE_PCT
            and (retention >= RETURN_GATE_PCT if np.isfinite(retention) else c3_return_pct <= 0 and return_pct >= c3_return_pct)
            and max_margin_to_equity <= MARGIN_GATE_PCT
        ),
        "required_cash_dd30": _required_cash_for_dd(merged["base_without_cash_balance"], MAX_DD_GATE_PCT),
        "required_cash_margin100": _required_cash_for_margin(merged["base_without_cash_balance"], merged["total_margin"]),
    }


def _evaluate_all(c3: pd.DataFrame, xsmom: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    profiles = [str(item) for item in xsmom["profile"].drop_duplicates().tolist()]
    rows: list[dict[str, Any]] = []
    for profile in profiles:
        for window in WINDOWS:
            for cash in CASH_LEVELS:
                rows.append(_evaluate_profile_window(c3, xsmom, profile, window, cash, 1.0))
    summary = pd.DataFrame(rows)

    stress_rows: list[dict[str, Any]] = []
    for profile in profiles:
        for multiplier in SLIPPAGE_MULTIPLIERS:
            stress_rows.append(_evaluate_profile_window(c3, xsmom, profile, WINDOWS[0], 0.0, multiplier))
            required0 = stress_rows[-1]
            required_cash = max(required0["required_cash_dd30"], required0["required_cash_margin100"])
            stress_rows.append(_evaluate_profile_window(c3, xsmom, profile, WINDOWS[0], float(math.ceil(required_cash / 1000.0) * 1000.0), multiplier))
    stress = pd.DataFrame(stress_rows)
    return summary, stress


def _build_report(summary: pd.DataFrame, stress: pd.DataFrame, decision: dict[str, Any]) -> str:
    full = summary[summary["window_name"].eq("full_2020_2026")].sort_values(
        ["gate_ok", "cash", "total_return_pct"],
        ascending=[False, True, False],
    )
    stress_view = stress.sort_values(["profile", "slippage_multiplier", "cash"])
    lines = [
        "# Stage051 C3 + 横截面动量Overlay + 外部现金筛查",
        "",
        "## 定位",
        "",
        "- 本阶段不是继续微调 `35/15`，而是保留 C3 50万原路径，把 Stage346 的横截面动量整数手数作为保证金 overlay。",
        "- 目标是判断：独立收益源 + 账户现金缓冲，是否比纯外部现金缓冲更接近“30以内且保收益”。",
        "- 本阶段是日收益/保证金筛查，不是最终真实组合引擎；若有候选，必须多起点真实引擎验证。",
        "",
        "## 全样本粗筛",
        "",
        _to_markdown_table(
            full,
            [
                "profile",
                "cash",
                "total_return_pct",
                "return_retention_vs_c3_pct",
                "max_dd_pct",
                "max_margin_to_equity_pct",
                "review_days",
                "reject_days",
                "required_cash_dd30",
                "required_cash_margin100",
                "gate_ok",
            ],
            max_rows=30,
        ),
        "",
        "## 滑点压力与解析所需现金",
        "",
        _to_markdown_table(
            stress_view,
            [
                "profile",
                "slippage_multiplier",
                "cash",
                "total_return_pct",
                "return_retention_vs_c3_pct",
                "max_dd_pct",
                "max_margin_to_equity_pct",
                "required_cash_dd30",
                "required_cash_margin100",
                "gate_ok",
            ],
            max_rows=40,
        ),
        "",
        "## 判断",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最佳全样本候选：`{decision.get('best_full_profile')}`，现金 `{decision.get('best_full_cash')}`。",
        f"- 最小解析现金需求：`{decision.get('min_required_cash')}`。",
        "",
        "## 反思",
        "",
        "- 是否过拟合：否。本阶段使用既有 C3 和既有 xsmom 执行口径，不调品种、不改窗口、不微调阈值。",
        "- 是否还有价值继续：若候选只能靠更高保证金或滑点压力不稳，则不应晋级；若比纯现金缓冲更省现金且收益更高，再进入真实引擎多周期。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    c3 = _load_c3_daily()
    xsmom = _load_xsmom_daily()
    summary, stress = _evaluate_all(c3, xsmom)

    full_ok = summary[(summary["window_name"].eq("full_2020_2026")) & summary["gate_ok"].eq(1)].copy()
    best = full_ok.sort_values(["cash", "total_return_pct"], ascending=[True, False]).head(1)
    full_base = summary[summary["window_name"].eq("full_2020_2026")].copy()
    required_cash = float(
        full_base.assign(
            required_cash=lambda df: np.maximum(df["required_cash_dd30"], df["required_cash_margin100"])
        )["required_cash"].min()
    )
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "overlay_cash_screen_candidate_requires_real_engine" if not best.empty else "overlay_cash_screen_no_candidate",
        "best_full_profile": None if best.empty else str(best["profile"].iloc[0]),
        "best_full_cash": None if best.empty else float(best["cash"].iloc[0]),
        "best_full_return_pct": None if best.empty else float(best["total_return_pct"].iloc[0]),
        "best_full_max_dd_pct": None if best.empty else float(best["max_dd_pct"].iloc[0]),
        "best_full_retention_pct": None if best.empty else float(best["return_retention_vs_c3_pct"].iloc[0]),
        "min_required_cash": required_cash,
        "overfit_judgement": "否。既有C3路径+既有xsmom执行口径+解析现金，不做小数救援。",
        "continue_value_judgement": "若候选比纯现金缓冲更省资金且收益更高，则值得真实引擎复验；否则停止。",
    }

    paths = {
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "stress": OUTPUT_DIR / f"{OUTPUT_PREFIX}_stress_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
    }
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    stress.to_csv(paths["stress"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    paths["report"].write_text(_build_report(summary, stress, decision), encoding="utf-8")

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage351] report: {paths['report']}")


if __name__ == "__main__":
    main()
