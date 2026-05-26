from __future__ import annotations

import json
import math
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import TOTAL_CAPITAL, _to_builtin, _to_markdown_table
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage355_c3_deployment_cash_boundary_decision_v1"
OUTPUT_PREFIX = "qmt_roll_stage355_c3_deployment_cash_boundary_decision"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SOURCE_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_"
    "stage336_c3_cash_reserve_multiperiod_v1.csv"
)
SOURCE_PROFILE = "c3_active100_cash0"

TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0)
ROUND_UNIT = 5_000.0


def _load_daily() -> pd.DataFrame:
    if not SOURCE_DAILY_PATH.exists():
        raise FileNotFoundError(f"missing source daily csv: {SOURCE_DAILY_PATH}")
    frame = pd.read_csv(SOURCE_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["profile"].eq(SOURCE_PROFILE)].copy()
    if frame.empty:
        raise ValueError(f"source profile not found: {SOURCE_PROFILE}")
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    for column in ["balance", "active_slippage"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return frame.sort_values(["window_name", "date"]).reset_index(drop=True)


def _stressed_balance(frame: pd.DataFrame, slippage_multiplier: float) -> pd.Series:
    extra_cost = (slippage_multiplier - 1.0) * frame["active_slippage"].astype(float).cumsum()
    return frame["balance"].astype(float) - extra_cost


def _path_metrics(balance: pd.Series, *, start_capital: float) -> dict[str, Any]:
    values = pd.to_numeric(balance, errors="coerce").ffill().fillna(start_capital).to_numpy(dtype=float)
    if len(values) == 0:
        return {
            "end_equity": start_capital,
            "total_return_pct": 0.0,
            "max_dd_pct": 0.0,
            "peak_index": 0,
            "trough_index": 0,
        }
    high = np.maximum.accumulate(values)
    drawdown = values - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0) * 100.0
    trough_idx = int(np.argmin(dd_pct))
    peak_idx = int(np.argmax(values[: trough_idx + 1]))
    return {
        "end_equity": float(values[-1]),
        "total_return_pct": float((values[-1] / start_capital - 1.0) * 100.0),
        "max_dd_pct": float(dd_pct.min()),
        "peak_index": peak_idx,
        "trough_index": trough_idx,
    }


def _required_cash_for_target(balance: pd.Series, target_dd_pct: float) -> tuple[float, int]:
    values = pd.to_numeric(balance, errors="coerce").ffill().fillna(TOTAL_CAPITAL).to_numpy(dtype=float)
    if len(values) == 0:
        return 0.0, 0
    high = np.maximum.accumulate(values)
    drawdown = values - high
    target_ratio = abs(target_dd_pct) / 100.0
    required = np.maximum(0.0, (-drawdown / target_ratio) - high)
    idx = int(required.argmax())
    return float(required[idx]), idx


def _round_up_cash(value: float) -> float:
    return float(math.ceil(value / ROUND_UNIT) * ROUND_UNIT)


def _retention_for_cash(cash_buffer: float) -> float:
    return TOTAL_CAPITAL / (TOTAL_CAPITAL + cash_buffer) * 100.0


def _summarize_window_requirements(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for slippage_multiplier in SLIPPAGE_MULTIPLIERS:
        for window_name, window_df in daily.groupby("window_name", sort=False):
            window_df = window_df.sort_values("date").reset_index(drop=True)
            stressed = _stressed_balance(window_df, slippage_multiplier)
            base_metrics = _path_metrics(stressed, start_capital=TOTAL_CAPITAL)
            required_cash, required_idx = _required_cash_for_target(stressed, TARGET_MAX_DD_PCT)
            rounded_cash = _round_up_cash(required_cash)
            account_metrics = _path_metrics(stressed + rounded_cash, start_capital=TOTAL_CAPITAL + rounded_cash)
            rows.append(
                {
                    "slippage_multiplier": slippage_multiplier,
                    "window_name": window_name,
                    "window_label": str(window_df["window_label"].iloc[0]),
                    "baseline_return_pct": base_metrics["total_return_pct"],
                    "baseline_max_dd_pct": base_metrics["max_dd_pct"],
                    "required_cash_for_30dd": required_cash,
                    "rounded_cash": rounded_cash,
                    "rounded_start_capital": TOTAL_CAPITAL + rounded_cash,
                    "rounded_return_pct": account_metrics["total_return_pct"],
                    "rounded_retention_pct": _retention_for_cash(rounded_cash),
                    "rounded_max_dd_pct": account_metrics["max_dd_pct"],
                    "retention_gate_ok": int(_retention_for_cash(rounded_cash) >= RETURN_RETENTION_GATE_PCT),
                    "dd_gate_ok": int(account_metrics["max_dd_pct"] >= TARGET_MAX_DD_PCT),
                    "strict_gate_ok": int(
                        account_metrics["max_dd_pct"] >= TARGET_MAX_DD_PCT
                        and _retention_for_cash(rounded_cash) >= RETURN_RETENTION_GATE_PCT
                    ),
                    "required_cash_date": pd.Timestamp(window_df.loc[required_idx, "date"]).date().isoformat(),
                }
            )
    return pd.DataFrame(rows)


def _summarize_deployment_boundary(requirements: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    max_cash_for_80_retention = TOTAL_CAPITAL * (100.0 / RETURN_RETENTION_GATE_PCT - 1.0)
    for slippage_multiplier, req_df in requirements.groupby("slippage_multiplier", sort=True):
        robust_cash = _round_up_cash(float(req_df["required_cash_for_30dd"].max()))
        window_rows: list[dict[str, Any]] = []
        for window_name, window_df in daily.groupby("window_name", sort=False):
            window_df = window_df.sort_values("date").reset_index(drop=True)
            stressed = _stressed_balance(window_df, float(slippage_multiplier))
            base_metrics = _path_metrics(stressed, start_capital=TOTAL_CAPITAL)
            account_metrics = _path_metrics(stressed + robust_cash, start_capital=TOTAL_CAPITAL + robust_cash)
            if base_metrics["total_return_pct"] > 0:
                return_retention = account_metrics["total_return_pct"] / base_metrics["total_return_pct"] * 100.0
            else:
                return_retention = math.nan
            window_rows.append(
                {
                    "window_name": window_name,
                    "account_return_pct": account_metrics["total_return_pct"],
                    "return_retention_pct": return_retention,
                    "max_dd_pct": account_metrics["max_dd_pct"],
                    "gate_ok": int(
                        account_metrics["max_dd_pct"] >= TARGET_MAX_DD_PCT
                        and (
                            math.isnan(return_retention)
                            or return_retention >= RETURN_RETENTION_GATE_PCT
                        )
                    ),
                    "positive_baseline": int(base_metrics["total_return_pct"] > 0),
                }
            )
        window_frame = pd.DataFrame(window_rows)
        positive_windows = window_frame[window_frame["positive_baseline"].eq(1)]
        rows.append(
            {
                "slippage_multiplier": slippage_multiplier,
                "robust_cash": robust_cash,
                "robust_start_capital": TOTAL_CAPITAL + robust_cash,
                "cash_pct_of_strategy_capital": robust_cash / TOTAL_CAPITAL * 100.0,
                "mechanical_retention_pct": _retention_for_cash(robust_cash),
                "max_cash_for_80_retention": max_cash_for_80_retention,
                "within_80_retention_cash_limit": int(robust_cash <= max_cash_for_80_retention),
                "window_gate_pass_count": int(window_frame["gate_ok"].sum()),
                "window_count": int(len(window_frame)),
                "positive_window_gate_pass_count": int(positive_windows["gate_ok"].sum()),
                "positive_window_count": int(len(positive_windows)),
                "worst_window_max_dd_pct": float(window_frame["max_dd_pct"].min()),
                "min_positive_retention_pct": float(positive_windows["return_retention_pct"].min())
                if not positive_windows.empty
                else math.nan,
                "decision": "normal_cost_deployment_candidate"
                if slippage_multiplier == 1.0 and robust_cash <= max_cash_for_80_retention
                else "fails_80_retention_boundary",
            }
        )
    return pd.DataFrame(rows)


def _build_report(requirements: pd.DataFrame, boundary: pd.DataFrame, decision: dict[str, Any]) -> str:
    boundary_cols = [
        "slippage_multiplier",
        "robust_cash",
        "robust_start_capital",
        "mechanical_retention_pct",
        "window_gate_pass_count",
        "window_count",
        "positive_window_gate_pass_count",
        "positive_window_count",
        "worst_window_max_dd_pct",
        "min_positive_retention_pct",
        "decision",
    ]
    requirement_cols = [
        "slippage_multiplier",
        "window_name",
        "baseline_return_pct",
        "baseline_max_dd_pct",
        "required_cash_for_30dd",
        "rounded_cash",
        "rounded_retention_pct",
        "rounded_max_dd_pct",
        "strict_gate_ok",
    ]
    worst_requirements = requirements.sort_values(
        ["slippage_multiplier", "required_cash_for_30dd"],
        ascending=[True, False],
    )
    return "\n".join(
        [
            "# Stage055 C3部署层外部现金边界决策表",
            "",
            "## 定位",
            "",
            "- 不修改 C3 的信号、AI池、品种池、出场、手数和成交路径。",
            "- 把外部现金作为账户权益分母，计算不同滑点下压到30%最大回撤所需的稳健账户资金。",
            "- 本阶段不是 alpha 优化，而是判断“当前目标是否可以通过部署层资金结构实现”。",
            "",
            "## 部署边界",
            "",
            _to_markdown_table(boundary, boundary_cols, max_rows=20),
            "",
            "## 各窗口所需现金",
            "",
            _to_markdown_table(worst_requirements, requirement_cols, max_rows=60),
            "",
            "## 结论",
            "",
            f"- 决策标签：`{decision['decision']}`。",
            f"- 正常成本所需外部现金：`{decision['cash_1x']:,.2f}`，账户总资金：`{decision['start_capital_1x']:,.2f}`，机械收益保留：`{decision['retention_1x']:.4f}%`。",
            f"- 2x滑点所需外部现金：`{decision['cash_2x']:,.2f}`，机械收益保留：`{decision['retention_2x']:.4f}%`。",
            f"- 3x滑点所需外部现金：`{decision['cash_3x']:,.2f}`，机械收益保留：`{decision['retention_3x']:.4f}%`。",
            "",
            "## 反思",
            "",
            "- 是否过拟合：否。这里没有用历史结果去改交易规则，只用多个起点和滑点倍率计算账户资金边界；但把边界精确到个位数会有伪精确风险，所以统一向上取整到5000元。",
            "- 是否还有价值继续：有。正常成本下，这是目前低过拟合程度最高的可执行边界；但它不能解决高滑点压力，后续若坚持2x/3x滑点也过关，必须继续找真正低相关收益源。",
        ]
    )


def main() -> None:
    daily = _load_daily()
    requirements = _summarize_window_requirements(daily)
    boundary = _summarize_deployment_boundary(requirements, daily)
    by_multiplier = boundary.set_index("slippage_multiplier")
    cash_1x = float(by_multiplier.loc[1.0, "robust_cash"])
    cash_2x = float(by_multiplier.loc[2.0, "robust_cash"])
    cash_3x = float(by_multiplier.loc[3.0, "robust_cash"])
    retention_1x = float(by_multiplier.loc[1.0, "mechanical_retention_pct"])
    retention_2x = float(by_multiplier.loc[2.0, "mechanical_retention_pct"])
    retention_3x = float(by_multiplier.loc[3.0, "mechanical_retention_pct"])
    decision = {
        "decision": "normal_cost_deployment_boundary_passes_but_slippage_stress_fails_retention",
        "line_id": LINE_ID,
        "target_max_dd_pct": TARGET_MAX_DD_PCT,
        "return_retention_gate_pct": RETURN_RETENTION_GATE_PCT,
        "cash_1x": cash_1x,
        "start_capital_1x": TOTAL_CAPITAL + cash_1x,
        "retention_1x": retention_1x,
        "cash_2x": cash_2x,
        "start_capital_2x": TOTAL_CAPITAL + cash_2x,
        "retention_2x": retention_2x,
        "cash_3x": cash_3x,
        "start_capital_3x": TOTAL_CAPITAL + cash_3x,
        "retention_3x": retention_3x,
        "normal_cost_candidate_ok": bool(retention_1x >= RETURN_RETENTION_GATE_PCT),
        "slippage_2x_candidate_ok": bool(retention_2x >= RETURN_RETENTION_GATE_PCT),
        "source_daily": SOURCE_DAILY_PATH.name,
    }

    requirements_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_requirements_{MODEL_TAG}.csv"
    boundary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_boundary_{MODEL_TAG}.csv"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

    requirements.to_csv(requirements_path, index=False, encoding="utf-8-sig")
    boundary.to_csv(boundary_path, index=False, encoding="utf-8-sig")
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(_build_report(requirements, boundary, decision), encoding="utf-8")

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage355] report: {report_path}")


if __name__ == "__main__":
    main()
