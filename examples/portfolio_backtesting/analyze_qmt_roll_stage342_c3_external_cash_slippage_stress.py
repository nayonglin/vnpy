from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    MARGIN_REJECT_PCT,
    MARGIN_REVIEW_PCT,
    MARGIN_WATCH_PCT,
    TOTAL_CAPITAL,
    _to_builtin,
    _to_markdown_table,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage342_c3_external_cash_slippage_stress_v1"
OUTPUT_PREFIX = "qmt_roll_stage342_c3_external_cash_slippage_stress"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SOURCE_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_"
    "stage336_c3_cash_reserve_multiperiod_v1.csv"
)
SOURCE_MARGIN_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage327_c3_margin_concentration_overlay_probe_daily_state_"
    "stage327_c3_margin_concentration_overlay_probe_v1.csv"
)
SOURCE_PROFILE = "c3_active100_cash0"
TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0)


@dataclass(frozen=True)
class BufferProfile:
    name: str
    label: str
    cash_buffer: float


PROFILES: tuple[BufferProfile, ...] = (
    BufferProfile("buffer_0", "不加外部现金", 0.0),
    BufferProfile("buffer_115k", "外部现金11.5万", 115_000.0),
    BufferProfile("buffer_125k", "外部现金12.5万", 125_000.0),
    BufferProfile("buffer_200k", "外部现金20万", 200_000.0),
    BufferProfile("buffer_350k", "外部现金35万", 350_000.0),
    BufferProfile("buffer_600k", "外部现金60万", 600_000.0),
)


def _load_daily() -> pd.DataFrame:
    if not SOURCE_DAILY_PATH.exists():
        raise FileNotFoundError(f"missing source daily csv: {SOURCE_DAILY_PATH}")
    frame = pd.read_csv(SOURCE_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["profile"].eq(SOURCE_PROFILE)].copy()
    if frame.empty:
        raise ValueError(f"source profile not found: {SOURCE_PROFILE}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["balance", "active_slippage", "trade_count"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.sort_values(["window_name", "date"]).reset_index(drop=True)


def _load_margin_daily() -> pd.DataFrame:
    if not SOURCE_MARGIN_PATH.exists():
        return pd.DataFrame()
    frame = pd.read_csv(SOURCE_MARGIN_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["balance", "slippage", "c3_margin"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.sort_values("date").reset_index(drop=True)


def _stressed_balance(frame: pd.DataFrame, slippage_multiplier: float) -> pd.Series:
    extra_cost = (slippage_multiplier - 1.0) * frame["active_slippage"].astype(float).cumsum()
    return frame["balance"].astype(float) - extra_cost


def _stressed_margin_balance(frame: pd.DataFrame, slippage_multiplier: float) -> pd.Series:
    extra_cost = (slippage_multiplier - 1.0) * frame["slippage"].astype(float).cumsum()
    return frame["balance"].astype(float) - extra_cost


def _path_metrics(balance: pd.Series, *, start_capital: float) -> dict[str, Any]:
    values = pd.to_numeric(balance, errors="coerce").ffill().fillna(start_capital).to_numpy(dtype=float)
    if len(values) == 0:
        return {
            "end_equity": start_capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "max_drawdown_amount": 0.0,
            "sharpe_ratio": 0.0,
            "peak_index": 0,
            "trough_index": 0,
        }
    high = np.maximum.accumulate(values)
    drawdown = values - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0) * 100.0
    returns = pd.Series(values).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252)) if std > 0 else 0.0
    trough_idx = int(np.argmin(dd_pct))
    peak_idx = int(np.argmax(values[: trough_idx + 1]))
    return {
        "end_equity": float(values[-1]),
        "total_return_pct": float((values[-1] / start_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "max_drawdown_amount": float(drawdown.min()),
        "sharpe_ratio": sharpe,
        "peak_index": peak_idx,
        "trough_index": trough_idx,
    }


def _required_cash_for_target(balance: pd.Series) -> float:
    values = pd.to_numeric(balance, errors="coerce").ffill().fillna(TOTAL_CAPITAL).to_numpy(dtype=float)
    if len(values) == 0:
        return 0.0
    high = np.maximum.accumulate(values)
    drawdown = values - high
    target_ratio = abs(TARGET_MAX_DD_PCT) / 100.0
    required = np.maximum(0.0, (-drawdown / target_ratio) - high)
    return float(required.max())


def _retention_for_cash(cash_buffer: float) -> float:
    return TOTAL_CAPITAL / (TOTAL_CAPITAL + cash_buffer) * 100.0


def _gate(baseline_return: float, candidate_return: float, candidate_dd: float) -> tuple[int, float]:
    if baseline_return > 0:
        retention = candidate_return / baseline_return * 100.0
        ok = candidate_dd >= TARGET_MAX_DD_PCT and retention >= RETURN_RETENTION_GATE_PCT
        return int(ok), retention
    return int(candidate_dd >= TARGET_MAX_DD_PCT and candidate_return >= baseline_return), math.nan


def _summarize_windows(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    required_rows: list[dict[str, Any]] = []
    max_cash_for_80_retention = TOTAL_CAPITAL * (100.0 / RETURN_RETENTION_GATE_PCT - 1.0)
    for multiplier in SLIPPAGE_MULTIPLIERS:
        for window_name, window_df in daily.groupby("window_name", sort=False):
            window_df = window_df.sort_values("date").reset_index(drop=True)
            window_label = str(window_df["window_label"].iloc[0])
            stressed_balance = _stressed_balance(window_df, multiplier)
            baseline_metrics = _path_metrics(stressed_balance, start_capital=TOTAL_CAPITAL)
            required_cash = _required_cash_for_target(stressed_balance)
            required_rows.append(
                {
                    "slippage_multiplier": multiplier,
                    "window_name": window_name,
                    "window_label": window_label,
                    "baseline_return_pct": baseline_metrics["total_return_pct"],
                    "baseline_max_dd_pct": baseline_metrics["max_dd_percent"],
                    "required_cash_for_30dd": required_cash,
                    "required_cash_pct_of_strategy_capital": required_cash / TOTAL_CAPITAL * 100.0,
                    "required_cash_retention_pct": _retention_for_cash(required_cash),
                    "within_80_retention_cash_limit": int(required_cash <= max_cash_for_80_retention),
                }
            )
            for profile in PROFILES:
                start_capital = TOTAL_CAPITAL + profile.cash_buffer
                account_balance = stressed_balance + profile.cash_buffer
                metrics = _path_metrics(account_balance, start_capital=start_capital)
                gate_ok, retention = _gate(
                    baseline_metrics["total_return_pct"],
                    metrics["total_return_pct"],
                    metrics["max_dd_percent"],
                )
                rows.append(
                    {
                        "slippage_multiplier": multiplier,
                        "window_name": window_name,
                        "window_label": window_label,
                        "profile": profile.name,
                        "label": profile.label,
                        "cash_buffer": profile.cash_buffer,
                        "total_return_pct": metrics["total_return_pct"],
                        "baseline_return_pct": baseline_metrics["total_return_pct"],
                        "return_retention_vs_baseline_pct": retention,
                        "max_dd_percent": metrics["max_dd_percent"],
                        "baseline_max_dd_pct": baseline_metrics["max_dd_percent"],
                        "gate_ok": gate_ok,
                        "peak_date": pd.Timestamp(window_df.iloc[int(metrics["peak_index"])]["date"]).date().isoformat(),
                        "trough_date": pd.Timestamp(window_df.iloc[int(metrics["trough_index"])]["date"]).date().isoformat(),
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(required_rows)


def _summarize_margin(margin_daily: pd.DataFrame) -> pd.DataFrame:
    if margin_daily.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for multiplier in SLIPPAGE_MULTIPLIERS:
        stressed_balance = _stressed_margin_balance(margin_daily, multiplier)
        for profile in PROFILES:
            account_balance = stressed_balance + profile.cash_buffer
            margin_pct = margin_daily["c3_margin"].astype(float) / account_balance.replace(0.0, np.nan) * 100.0
            margin_pct = margin_pct.fillna(0.0)
            rows.append(
                {
                    "slippage_multiplier": multiplier,
                    "profile": profile.name,
                    "cash_buffer": profile.cash_buffer,
                    "max_margin_to_equity_pct": float(margin_pct.max()),
                    "p95_margin_to_equity_pct": float(margin_pct.quantile(0.95)),
                    "watch_days_ge_60": int((margin_pct >= MARGIN_WATCH_PCT).sum()),
                    "review_days_ge_80": int((margin_pct >= MARGIN_REVIEW_PCT).sum()),
                    "reject_days_ge_100": int((margin_pct >= MARGIN_REJECT_PCT).sum()),
                }
            )
    return pd.DataFrame(rows)


def _build_report(
    window_summary: pd.DataFrame,
    required_cash: pd.DataFrame,
    margin_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    required_view = required_cash.sort_values(
        ["slippage_multiplier", "required_cash_for_30dd"],
        ascending=[True, False],
    )
    window_view = window_summary[
        window_summary["profile"].isin(["buffer_115k", "buffer_125k", "buffer_350k"])
    ].sort_values(["slippage_multiplier", "window_name", "cash_buffer"])
    margin_view = margin_summary[
        margin_summary["profile"].isin(["buffer_115k", "buffer_125k", "buffer_350k"])
    ].sort_values(["slippage_multiplier", "cash_buffer"])
    return "\n".join(
        [
            "# Stage042 C3外部现金缓冲滑点压力验证",
            "",
            "## 定位",
            "",
            "- 本阶段检验 Stage041 的外部现金部署候选在更高滑点成本下是否仍成立。",
            "- 交易路径仍不改变；高滑点通过日度额外滑点成本累计扣减权益来做压力估算。",
            "- 这不是策略优化，而是实盘前成本安全边界审计。",
            "",
            "## 关键窗口所需现金",
            "",
            _to_markdown_table(
                required_view,
                [
                    "slippage_multiplier",
                    "window_name",
                    "baseline_return_pct",
                    "baseline_max_dd_pct",
                    "required_cash_for_30dd",
                    "required_cash_retention_pct",
                    "within_80_retention_cash_limit",
                ],
                max_rows=40,
            ),
            "",
            "## 固定现金档位结果",
            "",
            _to_markdown_table(
                window_view,
                [
                    "slippage_multiplier",
                    "window_name",
                    "profile",
                    "cash_buffer",
                    "total_return_pct",
                    "return_retention_vs_baseline_pct",
                    "max_dd_percent",
                    "gate_ok",
                ],
                max_rows=90,
            ),
            "",
            "## 保证金压力",
            "",
            _to_markdown_table(
                margin_view,
                [
                    "slippage_multiplier",
                    "profile",
                    "cash_buffer",
                    "max_margin_to_equity_pct",
                    "p95_margin_to_equity_pct",
                    "reject_days_ge_100",
                ],
                max_rows=30,
            ),
            "",
            "## 结论",
            "",
            f"- 决策标签：`{decision['decision']}`。",
            f"- 80%收益保留允许的最大外部现金：`{decision['max_cash_for_80_retention']:,.2f}`。",
            f"- 2x滑点下最大所需现金：`{decision['max_required_cash_2x']:,.2f}`。",
            f"- 3x滑点下最大所需现金：`{decision['max_required_cash_3x']:,.2f}`。",
            f"- `11.5万`在2x滑点通过数：`{decision['buffer_115k_pass_2x']}/{decision['window_count']}`。",
            f"- `12.5万`在2x滑点通过数：`{decision['buffer_125k_pass_2x']}/{decision['window_count']}`。",
            "",
            "## 反思",
            "",
            "- 是否过拟合：否。本阶段只是固定滑点倍数压力测试，没有调交易信号。",
            "- 是否还有价值继续：有。它把部署候选从“正常成本可行”修正为“高滑点下不满足80%收益保留”。",
        ]
    )


def main() -> None:
    daily = _load_daily()
    margin_daily = _load_margin_daily()
    window_summary, required_cash = _summarize_windows(daily)
    margin_summary = _summarize_margin(margin_daily)

    window_count = int(window_summary["window_name"].nunique())
    max_cash_for_80 = TOTAL_CAPITAL * (100.0 / RETURN_RETENTION_GATE_PCT - 1.0)
    pass_counts = (
        window_summary.groupby(["slippage_multiplier", "profile"])["gate_ok"]
        .sum()
        .astype(int)
        .to_dict()
    )
    req_by_multiplier = required_cash.groupby("slippage_multiplier")["required_cash_for_30dd"].max().to_dict()
    decision = {
        "decision": "external_cash_candidate_fails_slippage_stress_under_80_retention"
        if req_by_multiplier.get(2.0, 0.0) > max_cash_for_80
        else "external_cash_candidate_survives_2x_slippage",
        "window_count": window_count,
        "max_cash_for_80_retention": max_cash_for_80,
        "max_required_cash_1x": float(req_by_multiplier.get(1.0, 0.0)),
        "max_required_cash_2x": float(req_by_multiplier.get(2.0, 0.0)),
        "max_required_cash_3x": float(req_by_multiplier.get(3.0, 0.0)),
        "max_required_cash_5x": float(req_by_multiplier.get(5.0, 0.0)),
        "buffer_115k_pass_1x": int(pass_counts.get((1.0, "buffer_115k"), 0)),
        "buffer_115k_pass_2x": int(pass_counts.get((2.0, "buffer_115k"), 0)),
        "buffer_115k_pass_3x": int(pass_counts.get((3.0, "buffer_115k"), 0)),
        "buffer_125k_pass_1x": int(pass_counts.get((1.0, "buffer_125k"), 0)),
        "buffer_125k_pass_2x": int(pass_counts.get((2.0, "buffer_125k"), 0)),
        "buffer_125k_pass_3x": int(pass_counts.get((3.0, "buffer_125k"), 0)),
        "target_max_dd_pct": TARGET_MAX_DD_PCT,
        "return_retention_gate_pct": RETURN_RETENTION_GATE_PCT,
        "source_daily": SOURCE_DAILY_PATH.name,
        "source_margin": SOURCE_MARGIN_PATH.name if SOURCE_MARGIN_PATH.exists() else "",
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
    }

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv"
    required_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_required_cash_{MODEL_TAG}.csv"
    margin_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_summary_{MODEL_TAG}.csv"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

    window_summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    required_cash.to_csv(required_path, index=False, encoding="utf-8-sig")
    margin_summary.to_csv(margin_path, index=False, encoding="utf-8-sig")
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_report(window_summary, required_cash, margin_summary, decision), encoding="utf-8")

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage342] report: {report_path}")


if __name__ == "__main__":
    main()
