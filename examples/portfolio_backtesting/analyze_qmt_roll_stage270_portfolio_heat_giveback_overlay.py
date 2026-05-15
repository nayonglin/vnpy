from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage270_portfolio_heat_giveback_overlay_v1"
OUTPUT_PREFIX = "qmt_roll_stage270_portfolio_heat_giveback_overlay"

INITIAL_CAPITAL = 500_000.0
TRADING_DAYS_PER_YEAR = 240

STAGE267_PREFIX = "qmt_roll_stage267_hot_product_official_add_one_validation"
BASE_DAILY_PATH = OUTPUT_DIR / f"{STAGE267_PREFIX}_official_stage78_1_static18_plus_fu_daily.csv"
Y_DAILY_PATH = OUTPUT_DIR / f"{STAGE267_PREFIX}_official_stage78_1_plus_y_DCE_daily.csv"
AG_DAILY_PATH = OUTPUT_DIR / f"{STAGE267_PREFIX}_official_stage78_1_plus_ag_SHFE_daily.csv"

SUMMARY_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
WINDOW_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv"
SLIPPAGE_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv"
SCALE_EVENTS_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scale_events_{MODEL_TAG}.csv"
CURVES_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
SUMMARY_JSON = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_MD = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class OverlayPolicy:
    name: str
    heat_return_60_soft: float
    heat_return_60_hard: float
    giveback_20_soft: float
    giveback_20_hard: float
    soft_scale: float
    hard_scale: float


POLICY = OverlayPolicy(
    name="portfolio_heat_giveback_v1",
    heat_return_60_soft=0.20,
    heat_return_60_hard=0.25,
    giveback_20_soft=-0.03,
    giveback_20_hard=-0.06,
    soft_scale=0.75,
    hard_scale=0.50,
)

WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("full_2020_2026", "2020-01-01", "2026-04-30"),
    ("since_2021", "2021-01-01", "2026-04-30"),
    ("since_2022", "2022-01-01", "2026-04-30"),
    ("since_2023", "2023-01-01", "2026-04-30"),
    ("since_2024", "2024-01-01", "2026-04-30"),
    ("since_2025", "2025-01-01", "2026-04-30"),
    ("since_2026", "2026-01-01", "2026-04-30"),
    ("stage269_full_aug_nov_2025", "2025-08-01", "2025-11-30"),
    ("stage269_ag_peak_to_trough", "2025-07-25", "2025-08-27"),
    ("stage269_y_worst_63d", "2025-08-14", "2025-11-18"),
    ("stage269_post_trough_recovery", "2025-08-28", "2025-11-17"),
    ("stage131_q2022_4_252d", "2022-10-01", "2023-09-30"),
)

SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 3.0, 5.0)


def _load_daily(path: Path, source_label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in ["net_pnl", "slippage", "trade_count", "balance", "turnover"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    df["source_label"] = source_label
    return df.sort_values("date").reset_index(drop=True)


def _path_metrics(df: pd.DataFrame, pnl_col: str, initial_capital: float = INITIAL_CAPITAL) -> dict[str, Any]:
    if df.empty:
        return {
            "end_balance": initial_capital,
            "total_return_pct": 0.0,
            "max_drawdown": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_net_pnl": 0.0,
            "total_slippage": 0.0,
            "total_trade_count": 0.0,
            "win_rate_pct": 0.0,
            "worst_day": "",
            "worst_day_net_pnl": 0.0,
        }
    net_pnl = pd.to_numeric(df[pnl_col], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    equity = initial_capital + np.cumsum(net_pnl)
    previous = np.concatenate([[initial_capital], equity[:-1]])
    returns = np.divide(net_pnl, previous, out=np.zeros_like(net_pnl), where=previous != 0.0)
    high = np.maximum.accumulate(equity)
    drawdown = equity - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0.0) * 100.0
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    worst_idx = int(np.argmin(net_pnl))
    return {
        "end_balance": float(equity[-1]),
        "total_return_pct": float((equity[-1] / initial_capital - 1.0) * 100.0),
        "max_drawdown": float(drawdown.min()),
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": float(np.mean(returns) / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0,
        "total_net_pnl": float(net_pnl.sum()),
        "total_slippage": float(pd.to_numeric(df.get("effective_slippage", df.get("slippage", 0.0)), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(df.get("effective_trade_count", df.get("trade_count", 0.0)), errors="coerce").fillna(0.0).sum()),
        "win_rate_pct": float((net_pnl > 0).mean() * 100.0),
        "worst_day": pd.Timestamp(df["date"].iloc[worst_idx]).date().isoformat(),
        "worst_day_net_pnl": float(net_pnl[worst_idx]),
    }


def _apply_overlay(daily: pd.DataFrame, policy: OverlayPolicy) -> pd.DataFrame:
    frame = daily.copy().reset_index(drop=True)
    raw_net_pnl = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    raw_slippage = pd.to_numeric(frame["slippage"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    raw_trade_count = pd.to_numeric(frame["trade_count"], errors="coerce").fillna(0.0).to_numpy(dtype=float)

    equity_values: list[float] = []
    scales: list[float] = []
    reasons: list[str] = []
    ret60_values: list[float] = []
    dd20_values: list[float] = []
    effective_pnl: list[float] = []

    equity = INITIAL_CAPITAL
    for idx, pnl in enumerate(raw_net_pnl):
        history = [INITIAL_CAPITAL, *equity_values]
        prev_equity = history[-1]
        if len(history) >= 61:
            ret60 = prev_equity / history[-61] - 1.0 if history[-61] else 0.0
        else:
            ret60 = 0.0
        window20 = history[-20:]
        high20 = max(window20) if window20 else prev_equity
        dd20 = prev_equity / high20 - 1.0 if high20 else 0.0

        if ret60 >= policy.heat_return_60_hard and dd20 <= policy.giveback_20_hard:
            scale = policy.hard_scale
            reason = "hard_heat_giveback"
        elif ret60 >= policy.heat_return_60_soft and dd20 <= policy.giveback_20_soft:
            scale = policy.soft_scale
            reason = "soft_heat_giveback"
        else:
            scale = 1.0
            reason = "full_risk"

        scaled_pnl = float(pnl) * scale
        equity += scaled_pnl
        scales.append(scale)
        reasons.append(reason)
        ret60_values.append(ret60)
        dd20_values.append(dd20)
        effective_pnl.append(scaled_pnl)
        equity_values.append(equity)

    frame["variant"] = policy.name
    frame["risk_scale"] = scales
    frame["scale_reason"] = reasons
    frame["prev_ret60"] = ret60_values
    frame["prev_dd20_from_high"] = dd20_values
    frame["effective_net_pnl"] = effective_pnl
    frame["effective_slippage"] = raw_slippage * np.asarray(scales, dtype=float)
    frame["effective_trade_count"] = raw_trade_count * np.asarray(scales, dtype=float)
    frame["effective_balance"] = INITIAL_CAPITAL + np.cumsum(np.asarray(effective_pnl, dtype=float))
    high = frame["effective_balance"].cummax()
    frame["effective_drawdown"] = frame["effective_balance"] - high
    frame["effective_ddpercent"] = (frame["effective_balance"] / high - 1.0) * 100.0
    return frame


def _raw_curve(daily: pd.DataFrame) -> pd.DataFrame:
    frame = daily.copy().reset_index(drop=True)
    frame["variant"] = "baseline_raw"
    frame["risk_scale"] = 1.0
    frame["scale_reason"] = "full_risk"
    frame["prev_ret60"] = 0.0
    frame["prev_dd20_from_high"] = 0.0
    frame["effective_net_pnl"] = frame["net_pnl"]
    frame["effective_slippage"] = frame["slippage"]
    frame["effective_trade_count"] = frame["trade_count"]
    frame["effective_balance"] = INITIAL_CAPITAL + pd.to_numeric(frame["effective_net_pnl"], errors="coerce").fillna(0.0).cumsum()
    high = frame["effective_balance"].cummax()
    frame["effective_drawdown"] = frame["effective_balance"] - high
    frame["effective_ddpercent"] = (frame["effective_balance"] / high - 1.0) * 100.0
    return frame


def _window_slice(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    return df[(df["date"] >= start_ts) & (df["date"] <= end_ts)].copy()


def _window_summary(daily_inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source_label, source_df in daily_inputs.items():
        for window_name, start, end in WINDOWS:
            raw_part = _window_slice(source_df, start, end)
            if raw_part.empty:
                continue
            for frame in (_raw_curve(raw_part), _apply_overlay(raw_part, POLICY)):
                variant = str(frame["variant"].iloc[0])
                metrics = _path_metrics(frame, "effective_net_pnl")
                rows.append(
                    {
                        "source_label": source_label,
                        "window_name": window_name,
                        "start_date": start,
                        "end_date": end,
                        "variant": variant,
                        **metrics,
                        "risk_reduced_day_count": int((frame["risk_scale"] < 1.0).sum()),
                        "avg_risk_scale": float(frame["risk_scale"].mean()),
                        "hard_day_count": int(frame["scale_reason"].eq("hard_heat_giveback").sum()),
                        "soft_day_count": int(frame["scale_reason"].eq("soft_heat_giveback").sum()),
                    }
                )
    return pd.DataFrame(rows)


def _summary_diff(window_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (source_label, window_name), group in window_summary.groupby(["source_label", "window_name"], sort=False):
        base = group[group["variant"].eq("baseline_raw")]
        cand = group[group["variant"].eq(POLICY.name)]
        if base.empty or cand.empty:
            continue
        b = base.iloc[0]
        c = cand.iloc[0]
        rows.append(
            {
                "source_label": source_label,
                "window_name": window_name,
                "candidate_end_balance": c["end_balance"],
                "baseline_end_balance": b["end_balance"],
                "end_balance_diff_vs_A": c["end_balance"] - b["end_balance"],
                "candidate_total_return_pct": c["total_return_pct"],
                "baseline_total_return_pct": b["total_return_pct"],
                "return_diff_vs_A": c["total_return_pct"] - b["total_return_pct"],
                "candidate_max_dd_percent": c["max_dd_percent"],
                "baseline_max_dd_percent": b["max_dd_percent"],
                "dd_diff_vs_A": c["max_dd_percent"] - b["max_dd_percent"],
                "candidate_sharpe_ratio": c["sharpe_ratio"],
                "baseline_sharpe_ratio": b["sharpe_ratio"],
                "sharpe_diff_vs_A": c["sharpe_ratio"] - b["sharpe_ratio"],
                "candidate_total_slippage": c["total_slippage"],
                "baseline_total_slippage": b["total_slippage"],
                "slippage_diff_vs_A": c["total_slippage"] - b["total_slippage"],
                "risk_reduced_day_count": c["risk_reduced_day_count"],
                "avg_risk_scale": c["avg_risk_scale"],
                "hard_day_count": c["hard_day_count"],
                "soft_day_count": c["soft_day_count"],
                "candidate_worst_day": c["worst_day"],
                "candidate_worst_day_net_pnl": c["worst_day_net_pnl"],
                "baseline_worst_day": b["worst_day"],
                "baseline_worst_day_net_pnl": b["worst_day_net_pnl"],
            }
        )
    return pd.DataFrame(rows)


def _slippage_stress(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source_label, source_df in curves.groupby("source_label", sort=False):
        for variant, frame in source_df.groupby("variant", sort=False):
            for multiplier in SLIPPAGE_MULTIPLIERS:
                stressed = frame.copy()
                extra_slippage = (multiplier - 1.0) * pd.to_numeric(stressed["effective_slippage"], errors="coerce").fillna(0.0)
                stressed["stressed_net_pnl"] = stressed["effective_net_pnl"] - extra_slippage
                metrics = _path_metrics(stressed, "stressed_net_pnl")
                rows.append(
                    {
                        "source_label": source_label,
                        "variant": variant,
                        "slippage_multiplier": multiplier,
                        **metrics,
                    }
                )
    return pd.DataFrame(rows)


def _scale_events(curves: pd.DataFrame) -> pd.DataFrame:
    events = curves[curves["risk_scale"] < 1.0].copy()
    if events.empty:
        return events
    return events[
        [
            "source_label",
            "date",
            "variant",
            "risk_scale",
            "scale_reason",
            "prev_ret60",
            "prev_dd20_from_high",
            "net_pnl",
            "effective_net_pnl",
            "effective_balance",
            "effective_ddpercent",
        ]
    ].sort_values(["source_label", "date"])


def _format_table(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_无数据_"
    view = df.loc[:, columns].head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    return view.to_markdown(index=False, disable_numparse=True)


def _decision(summary_diff: pd.DataFrame, slippage_df: pd.DataFrame) -> dict[str, Any]:
    base = summary_diff[
        summary_diff["source_label"].eq("A_static18_fu") & summary_diff["window_name"].eq("full_2020_2026")
    ]
    latest = summary_diff[
        summary_diff["source_label"].eq("A_static18_fu") & summary_diff["window_name"].eq("since_2026")
    ]
    weak = summary_diff[
        summary_diff["source_label"].eq("A_static18_fu")
        & summary_diff["window_name"].isin(["stage269_full_aug_nov_2025", "stage269_y_worst_63d", "stage269_ag_peak_to_trough"])
    ]
    slip_5x = slippage_df[
        slippage_df["source_label"].eq("A_static18_fu")
        & slippage_df["variant"].eq(POLICY.name)
        & slippage_df["slippage_multiplier"].eq(5.0)
    ]
    base_row = base.iloc[0].to_dict() if not base.empty else {}
    latest_row = latest.iloc[0].to_dict() if not latest.empty else {}
    weak_dd_improved = int((weak["dd_diff_vs_A"] > 0).sum()) if not weak.empty else 0
    weak_return_not_worse = int((weak["return_diff_vs_A"] >= -5.0).sum()) if not weak.empty else 0
    full_pass = bool(
        base_row
        and base_row.get("dd_diff_vs_A", -999.0) > 0
        and base_row.get("sharpe_diff_vs_A", -999.0) >= -0.05
        and base_row.get("return_diff_vs_A", -999.0) >= -250.0
    )
    latest_pass = bool(
        latest_row
        and latest_row.get("dd_diff_vs_A", -999.0) >= -1.0
        and latest_row.get("return_diff_vs_A", -999.0) >= -5.0
    )
    stress_pass = bool(not slip_5x.empty and float(slip_5x.iloc[0]["end_balance"]) > INITIAL_CAPITAL)
    pass_minimal = bool(full_pass and latest_pass and weak_dd_improved >= 2 and stress_pass)
    return {
        "policy": POLICY.__dict__,
        "test_type": "daily_capital_multiplier_replay_not_fill_level_backtest",
        "promotion_decision": "candidate_for_engine_backtest" if pass_minimal else "fail_do_not_promote",
        "full_period_pass": full_pass,
        "latest_2026_pass": latest_pass,
        "weak_window_dd_improved_count": weak_dd_improved,
        "weak_window_return_not_worse_count": weak_return_not_worse,
        "slippage_5x_positive_equity_pass": stress_pass,
        "pass_minimal_gate": pass_minimal,
        "next_step": "engine_level_A_vs_C_backtest" if pass_minimal else "stop_this_overlay_shape",
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = {
        "A_static18_fu": BASE_DAILY_PATH,
        "C_plus_y_DCE": Y_DAILY_PATH,
        "C_plus_ag_SHFE": AG_DAILY_PATH,
    }
    curve_frames: list[pd.DataFrame] = []
    for source_label, path in inputs.items():
        daily = _load_daily(path, source_label)
        curve_frames.append(_raw_curve(daily))
        curve_frames.append(_apply_overlay(daily, POLICY))
    curves = pd.concat(curve_frames, ignore_index=True)
    window_summary = _window_summary({label: _load_daily(path, label) for label, path in inputs.items()})
    summary_diff = _summary_diff(window_summary)
    slippage_df = _slippage_stress(curves)
    scale_events = _scale_events(curves)
    decision = _decision(summary_diff, slippage_df)

    curves.to_csv(CURVES_CSV, index=False)
    window_summary.to_csv(WINDOW_CSV, index=False)
    summary_diff.to_csv(SUMMARY_CSV, index=False)
    slippage_df.to_csv(SLIPPAGE_CSV, index=False)
    scale_events.to_csv(SCALE_EVENTS_CSV, index=False)
    SUMMARY_JSON.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    base_diff = summary_diff[summary_diff["source_label"].eq("A_static18_fu")].copy()
    report = f"""# Stage270 组合层 Heat/Giveback 风险倍率回放

## 设计

- A：Stage78-1 `static18+fu` 原始日收益路径。
- C：A + `{POLICY.name}`，只根据前一日组合权益状态给下一日整体风险乘数。
- 这是日级资本倍率回放，不是撮合级回测；若通过，才值得做引擎级 A vs C。
- 窗口表均按对应窗口从 `500,000` 独立回放；触发样本表仅用于查看全路径触发形态。
- 不修改 alpha、不修改品种池、不救 `y/ag/lc` 单品种。

## 预注册规则

```json
{json.dumps(POLICY.__dict__, ensure_ascii=False, indent=2)}
```

## 判定

```json
{json.dumps(decision, ensure_ascii=False, indent=2, default=str)}
```

## A基准路径 A vs C

{_format_table(base_diff, ["window_name", "end_balance_diff_vs_A", "return_diff_vs_A", "dd_diff_vs_A", "sharpe_diff_vs_A", "risk_reduced_day_count", "avg_risk_scale", "hard_day_count", "soft_day_count"], 20)}

## 所有路径主窗口

{_format_table(summary_diff[summary_diff["window_name"].eq("full_2020_2026")], ["source_label", "end_balance_diff_vs_A", "return_diff_vs_A", "dd_diff_vs_A", "sharpe_diff_vs_A", "risk_reduced_day_count", "avg_risk_scale"], 10)}

## A基准滑点压力

{_format_table(slippage_df[slippage_df["source_label"].eq("A_static18_fu")], ["variant", "slippage_multiplier", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage"], 10)}

## A基准触发样本

{_format_table(scale_events[scale_events["source_label"].eq("A_static18_fu")], ["date", "risk_scale", "scale_reason", "prev_ret60", "prev_dd20_from_high", "net_pnl", "effective_net_pnl", "effective_balance", "effective_ddpercent"], 20)}

## 输出文件

- `{SUMMARY_CSV.name}`
- `{WINDOW_CSV.name}`
- `{SLIPPAGE_CSV.name}`
- `{SCALE_EVENTS_CSV.name}`
- `{CURVES_CSV.name}`
- `{SUMMARY_JSON.name}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2, default=str))
    print(f"report={REPORT_MD}")


if __name__ == "__main__":
    main()
