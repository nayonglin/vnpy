from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    TOTAL_CAPITAL,
    _to_builtin,
    _to_markdown_table,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage340_c3_external_cash_buffer_deployment_v1"
OUTPUT_PREFIX = "qmt_roll_stage340_c3_external_cash_buffer_deployment"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SOURCE_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage339_c3_layered_profit_lock_sizing_screen_daily_"
    "stage339_c3_layered_profit_lock_sizing_screen_v1.csv"
)
SOURCE_VARIANT = "A_c3_supply_headwind"
TARGET_MAX_DD_PCT = -30.0


@dataclass(frozen=True)
class BufferProfile:
    name: str
    label: str
    cash_buffer: float


def _load_c3_daily() -> pd.DataFrame:
    if not SOURCE_DAILY_PATH.exists():
        raise FileNotFoundError(f"missing source daily csv: {SOURCE_DAILY_PATH}")
    frame = pd.read_csv(SOURCE_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["variant"].eq(SOURCE_VARIANT)].copy()
    if frame.empty:
        raise ValueError(f"source variant not found: {SOURCE_VARIANT}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce").ffill().fillna(TOTAL_CAPITAL)
    frame = frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    return frame


def _path_metrics(balance: pd.Series, *, start_capital: float) -> dict[str, Any]:
    values = pd.to_numeric(balance, errors="coerce").ffill().fillna(start_capital).to_numpy(dtype=float)
    high = np.maximum.accumulate(values)
    drawdown = values - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0) * 100.0
    returns = pd.Series(values).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252)) if std > 0 else 0.0
    trough_idx = int(np.argmin(dd_pct)) if len(dd_pct) else 0
    peak_idx = int(np.argmax(values[: trough_idx + 1])) if len(values) else 0
    return {
        "end_equity": float(values[-1]),
        "total_return_pct": float((values[-1] / start_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()) if len(dd_pct) else 0.0,
        "max_drawdown_amount": float(drawdown.min()) if len(drawdown) else 0.0,
        "sharpe_ratio": sharpe,
        "peak_index": peak_idx,
        "trough_index": trough_idx,
    }


def _required_cash_for_target(daily: pd.DataFrame, target_dd_pct: float) -> dict[str, Any]:
    if target_dd_pct >= 0:
        raise ValueError("target_dd_pct must be negative")
    target_ratio = abs(target_dd_pct) / 100.0
    balance = daily["balance"].astype(float).to_numpy()
    high = np.maximum.accumulate(balance)
    drawdown = balance - high
    required = np.maximum(0.0, (-drawdown / target_ratio) - high)
    idx = int(required.argmax())
    return {
        "cash_buffer": float(required[idx]),
        "date": pd.Timestamp(daily.iloc[idx]["date"]).date().isoformat(),
        "peak_balance": float(high[idx]),
        "trough_balance": float(balance[idx]),
        "drawdown_amount": float(drawdown[idx]),
    }


def _build_profiles(required_cash: float) -> tuple[BufferProfile, ...]:
    rounded_up = float(np.ceil(required_cash / 1000.0) * 1000.0)
    return (
        BufferProfile("buffer_0", "不加外部现金", 0.0),
        BufferProfile("buffer_2w", "外部现金2万", 20_000.0),
        BufferProfile("buffer_5w", "外部现金5万", 50_000.0),
        BufferProfile("buffer_exact_30dd", "刚好压到30%所需现金", required_cash),
        BufferProfile("buffer_round_67k", "实操向上取整6.7万", rounded_up),
        BufferProfile("buffer_7_5w", "外部现金7.5万", 75_000.0),
        BufferProfile("buffer_10w", "外部现金10万", 100_000.0),
    )


def _summarize_profiles(daily: pd.DataFrame, profiles: tuple[BufferProfile, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_metrics = _path_metrics(daily["balance"], start_capital=TOTAL_CAPITAL)
    rows: list[dict[str, Any]] = []
    curve_rows: list[pd.DataFrame] = []
    for profile in profiles:
        start_capital = TOTAL_CAPITAL + profile.cash_buffer
        account_balance = daily["balance"].astype(float) + profile.cash_buffer
        metrics = _path_metrics(account_balance, start_capital=start_capital)
        rows.append(
            {
                "profile": profile.name,
                "label": profile.label,
                "cash_buffer": profile.cash_buffer,
                "cash_buffer_pct_of_strategy_capital": profile.cash_buffer / TOTAL_CAPITAL * 100.0,
                "start_capital": start_capital,
                "end_equity": metrics["end_equity"],
                "total_return_pct": metrics["total_return_pct"],
                "return_retention_vs_c3_pct": metrics["total_return_pct"] / base_metrics["total_return_pct"] * 100.0,
                "max_dd_percent": metrics["max_dd_percent"],
                "max_drawdown_amount": metrics["max_drawdown_amount"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "strict_pass": int(metrics["max_dd_percent"] >= TARGET_MAX_DD_PCT and metrics["total_return_pct"] / base_metrics["total_return_pct"] >= 0.8),
                "peak_date": pd.Timestamp(daily.iloc[int(metrics["peak_index"])]["date"]).date().isoformat(),
                "trough_date": pd.Timestamp(daily.iloc[int(metrics["trough_index"])]["date"]).date().isoformat(),
            }
        )
        curve = daily[["date", "balance"]].copy()
        curve["profile"] = profile.name
        curve["account_balance"] = account_balance
        curve["account_highlevel"] = np.maximum.accumulate(account_balance.to_numpy(dtype=float))
        curve["account_ddpercent"] = (
            curve["account_balance"] / curve["account_highlevel"].replace(0.0, np.nan) - 1.0
        ) * 100.0
        curve_rows.append(curve)
    return pd.DataFrame(rows), pd.concat(curve_rows, ignore_index=True)


def _build_report(summary: pd.DataFrame, required: dict[str, Any], decision: dict[str, Any]) -> str:
    columns = [
        "profile",
        "cash_buffer",
        "cash_buffer_pct_of_strategy_capital",
        "total_return_pct",
        "return_retention_vs_c3_pct",
        "max_dd_percent",
        "strict_pass",
    ]
    return "\n".join(
        [
            "# Stage040 C3外部现金缓冲部署口径",
            "",
            "## 定位",
            "",
            "- 本阶段不改变C3策略交易路径、不减少下单资金、不新增alpha参数。",
            "- 只测试账户里额外放一笔不参与下单的现金时，账户口径最大回撤和收益保留如何变化。",
            "- 该口径用于部署资金边界判断，不等同于策略本身收益率提升。",
            "",
            "## 所需现金",
            "",
            f"- 将全样本最大回撤压到 `{TARGET_MAX_DD_PCT:.2f}%` 所需外部现金：`{required['cash_buffer']:,.2f}`。",
            f"- 约占50万策略资金：`{required['cash_buffer'] / TOTAL_CAPITAL * 100.0:.4f}%`。",
            f"- 约束发生日期：`{required['date']}`；高点权益：`{required['peak_balance']:,.2f}`；低点权益：`{required['trough_balance']:,.2f}`。",
            "",
            "## 结果",
            "",
            _to_markdown_table(summary, columns, max_rows=20),
            "",
            "## 结论",
            "",
            f"- 决策标签：`{decision['decision']}`。",
            f"- 推荐观察口径：`{decision['recommended_profile']}`。",
            f"- 推荐口径总收益：`{decision['recommended_return_pct']:.4f}%`，收益保留：`{decision['recommended_retention_pct']:.4f}%`，最大回撤：`{decision['recommended_max_dd_pct']:.4f}%`。",
            "",
            "## 反思",
            "",
            "- 是否过拟合：否。本阶段没有调交易规则，只按数学关系计算账户外部现金缓冲；但如果把6.7万当成精确神奇数字会变成伪精确，实盘应向上取整并留安全垫。",
            "- 是否还有价值继续：有。它不能提高策略本身，但能在不破坏C3交易路径的情况下，把账户展示回撤压入30以内，并明确需要额外资金的代价。",
        ]
    )


def main() -> None:
    daily = _load_c3_daily()
    required = _required_cash_for_target(daily, TARGET_MAX_DD_PCT)
    profiles = _build_profiles(float(required["cash_buffer"]))
    summary, curves = _summarize_profiles(daily, profiles)

    passing = summary[summary["strict_pass"].eq(1)].sort_values("cash_buffer")
    recommended = passing.iloc[0] if not passing.empty else summary.sort_values("max_dd_percent", ascending=False).iloc[0]
    decision = {
        "decision": "deployment_candidate_requires_extra_cash" if not passing.empty else "no_profile_passed",
        "recommended_profile": str(recommended["profile"]),
        "recommended_cash_buffer": float(recommended["cash_buffer"]),
        "recommended_return_pct": float(recommended["total_return_pct"]),
        "recommended_retention_pct": float(recommended["return_retention_vs_c3_pct"]),
        "recommended_max_dd_pct": float(recommended["max_dd_percent"]),
        "target_max_dd_pct": TARGET_MAX_DD_PCT,
        "required_cash": required,
        "source_daily": SOURCE_DAILY_PATH.name,
        "source_variant": SOURCE_VARIANT,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
    }

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    curves_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    curves.to_csv(curves_path, index=False, encoding="utf-8-sig")
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_report(summary, required, decision), encoding="utf-8")

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage340] report: {report_path}")


if __name__ == "__main__":
    main()
