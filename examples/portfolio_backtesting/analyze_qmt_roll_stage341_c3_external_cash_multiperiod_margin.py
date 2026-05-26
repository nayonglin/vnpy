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


MODEL_TAG = "stage341_c3_external_cash_multiperiod_margin_v1"
OUTPUT_PREFIX = "qmt_roll_stage341_c3_external_cash_multiperiod_margin"
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


@dataclass(frozen=True)
class BufferProfile:
    name: str
    label: str
    cash_buffer: float


PROFILES: tuple[BufferProfile, ...] = (
    BufferProfile("buffer_0", "不加外部现金", 0.0),
    BufferProfile("buffer_67k", "外部现金6.7万", 67_000.0),
    BufferProfile("buffer_75k", "外部现金7.5万", 75_000.0),
    BufferProfile("buffer_100k", "外部现金10万", 100_000.0),
    BufferProfile("buffer_115k", "外部现金11.5万", 115_000.0),
    BufferProfile("buffer_125k", "外部现金12.5万", 125_000.0),
)


def _load_multiperiod_daily() -> pd.DataFrame:
    if not SOURCE_DAILY_PATH.exists():
        raise FileNotFoundError(f"missing source daily csv: {SOURCE_DAILY_PATH}")
    frame = pd.read_csv(SOURCE_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["profile"].eq(SOURCE_PROFILE)].copy()
    if frame.empty:
        raise ValueError(f"source profile not found: {SOURCE_PROFILE}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce").ffill().fillna(TOTAL_CAPITAL)
    frame["active_net_pnl"] = pd.to_numeric(frame.get("active_net_pnl", 0.0), errors="coerce").fillna(0.0)
    frame["active_slippage"] = pd.to_numeric(frame.get("active_slippage", 0.0), errors="coerce").fillna(0.0)
    frame["trade_count"] = pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    return frame.sort_values(["window_name", "date"]).reset_index(drop=True)


def _load_margin_daily() -> pd.DataFrame:
    if not SOURCE_MARGIN_PATH.exists():
        return pd.DataFrame()
    frame = pd.read_csv(SOURCE_MARGIN_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["balance", "c3_margin", "c3_active_contracts", "c3_active_products"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.sort_values("date").reset_index(drop=True)


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


def _required_cash_for_target(balance: pd.Series, target_dd_pct: float) -> float:
    if target_dd_pct >= 0:
        raise ValueError("target_dd_pct must be negative")
    values = pd.to_numeric(balance, errors="coerce").ffill().fillna(TOTAL_CAPITAL).to_numpy(dtype=float)
    if len(values) == 0:
        return 0.0
    high = np.maximum.accumulate(values)
    drawdown = values - high
    target_ratio = abs(target_dd_pct) / 100.0
    required = np.maximum(0.0, (-drawdown / target_ratio) - high)
    return float(required.max())


def _gate(baseline_return: float, candidate_return: float, candidate_dd: float) -> tuple[int, float]:
    if baseline_return > 0:
        retention = candidate_return / baseline_return * 100.0
        return int(candidate_dd >= TARGET_MAX_DD_PCT and retention >= RETURN_RETENTION_GATE_PCT), retention
    retention = math.nan
    return int(candidate_dd >= TARGET_MAX_DD_PCT and candidate_return >= baseline_return), retention


def _summarize_windows(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    required_rows: list[dict[str, Any]] = []
    for window_name, window_df in daily.groupby("window_name", sort=False):
        window_df = window_df.sort_values("date").reset_index(drop=True)
        window_label = str(window_df["window_label"].iloc[0])
        baseline_metrics = _path_metrics(window_df["balance"], start_capital=TOTAL_CAPITAL)
        required_cash = _required_cash_for_target(window_df["balance"], TARGET_MAX_DD_PCT)
        required_rows.append(
            {
                "window_name": window_name,
                "window_label": window_label,
                "baseline_return_pct": baseline_metrics["total_return_pct"],
                "baseline_max_dd_pct": baseline_metrics["max_dd_percent"],
                "required_cash_for_30dd": required_cash,
                "required_cash_pct_of_strategy_capital": required_cash / TOTAL_CAPITAL * 100.0,
            }
        )
        for profile in PROFILES:
            account_start_capital = TOTAL_CAPITAL + profile.cash_buffer
            account_balance = window_df["balance"].astype(float) + profile.cash_buffer
            metrics = _path_metrics(account_balance, start_capital=account_start_capital)
            gate_ok, retention = _gate(
                baseline_metrics["total_return_pct"],
                metrics["total_return_pct"],
                metrics["max_dd_percent"],
            )
            rows.append(
                {
                    "window_name": window_name,
                    "window_label": window_label,
                    "profile": profile.name,
                    "label": profile.label,
                    "cash_buffer": profile.cash_buffer,
                    "start_capital": account_start_capital,
                    "end_equity": metrics["end_equity"],
                    "total_return_pct": metrics["total_return_pct"],
                    "baseline_return_pct": baseline_metrics["total_return_pct"],
                    "return_retention_vs_baseline_pct": retention,
                    "max_dd_percent": metrics["max_dd_percent"],
                    "baseline_max_dd_pct": baseline_metrics["max_dd_percent"],
                    "dd_improvement_pct_point": metrics["max_dd_percent"] - baseline_metrics["max_dd_percent"],
                    "sharpe_ratio": metrics["sharpe_ratio"],
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
    for profile in PROFILES:
        account_balance = margin_daily["balance"].astype(float) + profile.cash_buffer
        margin_pct = margin_daily["c3_margin"].astype(float) / account_balance.replace(0.0, np.nan) * 100.0
        margin_pct = margin_pct.fillna(0.0)
        max_idx = int(margin_pct.idxmax())
        rows.append(
            {
                "profile": profile.name,
                "label": profile.label,
                "cash_buffer": profile.cash_buffer,
                "max_margin_to_equity_pct": float(margin_pct.max()),
                "p95_margin_to_equity_pct": float(margin_pct.quantile(0.95)),
                "watch_days_ge_60": int((margin_pct >= MARGIN_WATCH_PCT).sum()),
                "review_days_ge_80": int((margin_pct >= MARGIN_REVIEW_PCT).sum()),
                "reject_days_ge_100": int((margin_pct >= MARGIN_REJECT_PCT).sum()),
                "max_margin_date": pd.Timestamp(margin_daily.loc[max_idx, "date"]).date().isoformat(),
                "max_margin": float(margin_daily.loc[max_idx, "c3_margin"]),
                "max_margin_day_account_equity": float(account_balance.loc[max_idx]),
                "max_active_contracts": int(margin_daily["c3_active_contracts"].max()),
                "max_active_products": int(margin_daily["c3_active_products"].max()),
            }
        )
    return pd.DataFrame(rows)


def _build_report(
    window_summary: pd.DataFrame,
    required_cash: pd.DataFrame,
    margin_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    window_cols = [
        "window_name",
        "profile",
        "cash_buffer",
        "total_return_pct",
        "return_retention_vs_baseline_pct",
        "max_dd_percent",
        "gate_ok",
    ]
    required_cols = [
        "window_name",
        "baseline_return_pct",
        "baseline_max_dd_pct",
        "required_cash_for_30dd",
        "required_cash_pct_of_strategy_capital",
    ]
    margin_cols = [
        "profile",
        "cash_buffer",
        "max_margin_to_equity_pct",
        "p95_margin_to_equity_pct",
        "watch_days_ge_60",
        "review_days_ge_80",
        "reject_days_ge_100",
    ]
    return "\n".join(
        [
            "# Stage041 C3外部现金缓冲多周期与保证金验证",
            "",
            "## 定位",
            "",
            "- 本阶段继续验证 Stage040 的部署候选。",
            "- 交易路径仍不改变；只把外部现金作为账户权益分母，检查多起点、弱窗口和保证金占用。",
            "- 这不是策略参数优化，而是资金边界和实盘准备口径。",
            "",
            "## 多周期结果",
            "",
            _to_markdown_table(window_summary, window_cols, max_rows=80),
            "",
            "## 各窗口压到30%所需现金",
            "",
            _to_markdown_table(required_cash, required_cols, max_rows=30),
            "",
            "## 保证金口径",
            "",
            _to_markdown_table(margin_summary, margin_cols, max_rows=20),
            "",
            "## 结论",
            "",
            f"- 决策标签：`{decision['decision']}`。",
            f"- `buffer_67k` 多周期通过数：`{decision['buffer_67k_gate_pass_count']}/{decision['window_count']}`。",
            f"- `buffer_100k` 多周期通过数：`{decision['buffer_100k_gate_pass_count']}/{decision['window_count']}`。",
            f"- `buffer_115k` 多周期通过数：`{decision['buffer_115k_gate_pass_count']}/{decision['window_count']}`。",
            f"- `buffer_125k` 多周期通过数：`{decision['buffer_125k_gate_pass_count']}/{decision['window_count']}`。",
            f"- `buffer_67k` 最大保证金/权益：`{decision['buffer_67k_max_margin_pct']:.4f}%`。",
            f"- `buffer_100k` 最大保证金/权益：`{decision['buffer_100k_max_margin_pct']:.4f}%`。",
            f"- `buffer_115k` 最大保证金/权益：`{decision['buffer_115k_max_margin_pct']:.4f}%`。",
            "",
            "## 反思",
            "",
            "- 是否过拟合：否。本阶段只检查固定现金缓冲档位，不用结果反调交易规则。",
            "- 是否还有价值继续：有。若用户接受额外现金，该口径能把风险边界落到真实账户准备；若不接受，则应回到C3自然回撤边界或寻找真正低相关收益源。",
        ]
    )


def main() -> None:
    daily = _load_multiperiod_daily()
    margin_daily = _load_margin_daily()
    window_summary, required_cash = _summarize_windows(daily)
    margin_summary = _summarize_margin(margin_daily)

    window_count = int(window_summary["window_name"].nunique())
    by_profile = window_summary.groupby("profile")["gate_ok"].sum().to_dict()
    margin_by_profile = margin_summary.set_index("profile") if not margin_summary.empty else pd.DataFrame()
    decision = {
        "decision": "buffer_115k_deployment_candidate_passes_multiperiod_margin_check"
        if by_profile.get("buffer_115k", 0) == window_count
        else "no_fixed_buffer_full_pass",
        "window_count": window_count,
        "buffer_67k_gate_pass_count": int(by_profile.get("buffer_67k", 0)),
        "buffer_75k_gate_pass_count": int(by_profile.get("buffer_75k", 0)),
        "buffer_100k_gate_pass_count": int(by_profile.get("buffer_100k", 0)),
        "buffer_115k_gate_pass_count": int(by_profile.get("buffer_115k", 0)),
        "buffer_125k_gate_pass_count": int(by_profile.get("buffer_125k", 0)),
        "buffer_67k_max_margin_pct": float(margin_by_profile.loc["buffer_67k", "max_margin_to_equity_pct"])
        if not margin_by_profile.empty and "buffer_67k" in margin_by_profile.index
        else math.nan,
        "buffer_100k_max_margin_pct": float(margin_by_profile.loc["buffer_100k", "max_margin_to_equity_pct"])
        if not margin_by_profile.empty and "buffer_100k" in margin_by_profile.index
        else math.nan,
        "buffer_115k_max_margin_pct": float(margin_by_profile.loc["buffer_115k", "max_margin_to_equity_pct"])
        if not margin_by_profile.empty and "buffer_115k" in margin_by_profile.index
        else math.nan,
        "buffer_125k_max_margin_pct": float(margin_by_profile.loc["buffer_125k", "max_margin_to_equity_pct"])
        if not margin_by_profile.empty and "buffer_125k" in margin_by_profile.index
        else math.nan,
        "max_required_cash": float(required_cash["required_cash_for_30dd"].max()) if not required_cash.empty else 0.0,
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
    print(f"[stage341] report: {report_path}")


if __name__ == "__main__":
    main()
