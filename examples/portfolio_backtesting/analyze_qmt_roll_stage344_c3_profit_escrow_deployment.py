from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import TOTAL_CAPITAL, _to_builtin
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage344_c3_profit_escrow_deployment_v1"
OUTPUT_PREFIX = "qmt_roll_stage344_c3_profit_escrow_deployment"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SOURCE_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_"
    "stage336_c3_cash_reserve_multiperiod_v1.csv"
)
SOURCE_PROFILE = "c3_active100_cash0"

TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0
SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)


@dataclass(frozen=True)
class EscrowProfile:
    name: str
    label: str
    seed_reserve: float
    skim_ratio: float
    reserve_cap: float


PROFILES: tuple[EscrowProfile, ...] = (
    EscrowProfile("no_escrow", "不留存利润", 0.0, 0.0, 0.0),
    EscrowProfile("skim25_cap67k", "无初始reserve，月末高水位利润25%留存，上限6.7万", 0.0, 0.25, 67_000.0),
    EscrowProfile("skim50_cap67k", "无初始reserve，月末高水位利润50%留存，上限6.7万", 0.0, 0.50, 67_000.0),
    EscrowProfile("skim100_cap67k", "无初始reserve，月末高水位利润100%留存，上限6.7万", 0.0, 1.00, 67_000.0),
    EscrowProfile("skim25_cap115k", "无初始reserve，月末高水位利润25%留存，上限11.5万", 0.0, 0.25, 115_000.0),
    EscrowProfile("skim50_cap115k", "无初始reserve，月末高水位利润50%留存，上限11.5万", 0.0, 0.50, 115_000.0),
    EscrowProfile("skim100_cap115k", "无初始reserve，月末高水位利润100%留存，上限11.5万", 0.0, 1.00, 115_000.0),
    EscrowProfile("seed50_skim100_cap115k", "初始reserve5万，利润100%补到11.5万", 50_000.0, 1.00, 115_000.0),
    EscrowProfile("seed67_no_skim", "初始reserve6.7万，不再补reserve", 67_000.0, 0.0, 67_000.0),
    EscrowProfile("seed67_skim50_cap115k", "初始reserve6.7万，利润50%补到11.5万", 67_000.0, 0.50, 115_000.0),
    EscrowProfile("seed67_skim100_cap115k", "初始reserve6.7万，利润100%补到11.5万", 67_000.0, 1.00, 115_000.0),
    EscrowProfile("seed75_no_skim", "初始reserve7.5万，不再补reserve", 75_000.0, 0.0, 75_000.0),
    EscrowProfile("seed75_skim100_cap115k", "初始reserve7.5万，利润100%补到11.5万", 75_000.0, 1.00, 115_000.0),
    EscrowProfile("seed100_no_skim", "初始reserve10万，不再补reserve", 100_000.0, 0.0, 100_000.0),
    EscrowProfile("seed100_skim100_cap115k", "初始reserve10万，利润100%补到11.5万", 100_000.0, 1.00, 115_000.0),
    EscrowProfile("seed115_no_skim", "初始reserve11.5万，不再补reserve", 115_000.0, 0.0, 115_000.0),
)


def _to_markdown_table(df: pd.DataFrame, columns: list[str], *, max_rows: int = 80) -> str:
    if df.empty:
        return "_无数据_"
    view = df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    return view.to_markdown(index=False)


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


def _stressed_balance(frame: pd.DataFrame, slippage_multiplier: float) -> pd.Series:
    extra_cost = (slippage_multiplier - 1.0) * frame["active_slippage"].astype(float).cumsum()
    return frame["balance"].astype(float) - extra_cost


def _daily_returns(balance: pd.Series) -> pd.Series:
    previous = balance.shift(1).fillna(TOTAL_CAPITAL).replace(0.0, np.nan)
    returns = balance / previous - 1.0
    return returns.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _month_end_flags(dates: pd.Series) -> pd.Series:
    periods = pd.to_datetime(dates).dt.to_period("M")
    next_periods = periods.shift(-1)
    flags = periods.ne(next_periods)
    flags.iloc[-1] = True
    return flags


def _path_metrics(values: pd.Series, *, start_capital: float = TOTAL_CAPITAL) -> dict[str, Any]:
    array = pd.to_numeric(values, errors="coerce").ffill().fillna(start_capital).to_numpy(dtype=float)
    if len(array) == 0:
        return {
            "end_equity": start_capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "max_drawdown_amount": 0.0,
            "sharpe_ratio": 0.0,
            "peak_index": 0,
            "trough_index": 0,
        }
    high = np.maximum.accumulate(array)
    drawdown = array - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0) * 100.0
    returns = pd.Series(array).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252.0)) if std > 0 else 0.0
    trough_idx = int(np.argmin(dd_pct))
    peak_idx = int(np.argmax(array[: trough_idx + 1]))
    return {
        "end_equity": float(array[-1]),
        "total_return_pct": float((array[-1] / start_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "max_drawdown_amount": float(drawdown.min()),
        "sharpe_ratio": sharpe,
        "peak_index": peak_idx,
        "trough_index": trough_idx,
    }


def _apply_profit_escrow(
    frame: pd.DataFrame,
    *,
    slippage_multiplier: float,
    profile: EscrowProfile,
) -> pd.DataFrame:
    frame = frame.sort_values("date").reset_index(drop=True).copy()
    stressed_balance = _stressed_balance(frame, slippage_multiplier)
    returns = _daily_returns(stressed_balance)
    month_end = _month_end_flags(frame["date"])

    trading_equity = float(TOTAL_CAPITAL)
    reserve_equity = float(profile.seed_reserve)
    total_high_water = float(TOTAL_CAPITAL + profile.seed_reserve)
    rows: list[dict[str, Any]] = []

    for idx, row in frame.iterrows():
        trading_equity *= 1.0 + float(returns.iloc[idx])
        transfer = 0.0
        pre_transfer_total = trading_equity + reserve_equity
        high_water_gain = max(0.0, pre_transfer_total - total_high_water)
        if (
            profile.reserve_cap > 0
            and profile.skim_ratio > 0
            and bool(month_end.iloc[idx])
            and high_water_gain > 0
            and reserve_equity < profile.reserve_cap
        ):
            transfer = min(
                profile.reserve_cap - reserve_equity,
                profile.skim_ratio * high_water_gain,
                max(0.0, trading_equity),
            )
            trading_equity -= transfer
            reserve_equity += transfer
        total_equity = trading_equity + reserve_equity
        total_high_water = max(total_high_water, pre_transfer_total, total_equity)
        rows.append(
            {
                "date": row["date"],
                "window_name": row["window_name"],
                "window_label": row["window_label"],
                "profile": profile.name,
                "profile_label": profile.label,
                "slippage_multiplier": slippage_multiplier,
                "seed_reserve": profile.seed_reserve,
                "baseline_balance": float(stressed_balance.iloc[idx]),
                "daily_return": float(returns.iloc[idx]),
                "trading_equity": float(trading_equity),
                "reserve_equity": float(reserve_equity),
                "total_equity": float(total_equity),
                "transfer_to_reserve": float(transfer),
                "trade_count": float(row.get("trade_count", 0.0)),
            }
        )
    return pd.DataFrame(rows)


def _summarize(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    daily_rows: list[pd.DataFrame] = []
    for multiplier in SLIPPAGE_MULTIPLIERS:
        for window_name, window_df in daily.groupby("window_name", sort=False):
            window_df = window_df.sort_values("date").reset_index(drop=True)
            window_label = str(window_df["window_label"].iloc[0])
            baseline_balance = _stressed_balance(window_df, multiplier)
            baseline_metrics = _path_metrics(baseline_balance)
            for profile in PROFILES:
                escrow_daily = _apply_profit_escrow(
                    window_df,
                    slippage_multiplier=multiplier,
                    profile=profile,
                )
                metrics = _path_metrics(escrow_daily["total_equity"])
                start_capital = TOTAL_CAPITAL + profile.seed_reserve
                metrics = _path_metrics(escrow_daily["total_equity"], start_capital=start_capital)
                retention = (
                    metrics["total_return_pct"] / baseline_metrics["total_return_pct"] * 100.0
                    if baseline_metrics["total_return_pct"] > 0
                    else math.nan
                )
                if baseline_metrics["total_return_pct"] > 0:
                    gate_ok = int(
                        metrics["max_dd_percent"] >= TARGET_MAX_DD_PCT
                        and retention >= RETURN_RETENTION_GATE_PCT
                    )
                else:
                    gate_ok = int(
                        metrics["max_dd_percent"] >= TARGET_MAX_DD_PCT
                        and metrics["total_return_pct"] >= baseline_metrics["total_return_pct"]
                    )
                transfers = escrow_daily["transfer_to_reserve"].astype(float)
                summary_rows.append(
                    {
                        "slippage_multiplier": multiplier,
                        "window_name": window_name,
                        "window_label": window_label,
                        "profile": profile.name,
                        "profile_label": profile.label,
                        "seed_reserve": profile.seed_reserve,
                        "skim_ratio": profile.skim_ratio,
                        "reserve_cap": profile.reserve_cap,
                        "start_capital": start_capital,
                        "end_equity": metrics["end_equity"],
                        "total_return_pct": metrics["total_return_pct"],
                        "baseline_return_pct": baseline_metrics["total_return_pct"],
                        "return_retention_vs_baseline_pct": retention,
                        "max_dd_percent": metrics["max_dd_percent"],
                        "baseline_max_dd_pct": baseline_metrics["max_dd_percent"],
                        "dd_improvement_pct_point": metrics["max_dd_percent"]
                        - baseline_metrics["max_dd_percent"],
                        "sharpe_ratio": metrics["sharpe_ratio"],
                        "end_reserve_equity": float(escrow_daily["reserve_equity"].iloc[-1]),
                        "max_reserve_equity": float(escrow_daily["reserve_equity"].max()),
                        "total_transfer_count": int((transfers > 0).sum()),
                        "total_transfer_amount": float(transfers.sum()),
                        "min_trading_equity": float(escrow_daily["trading_equity"].min()),
                        "gate_ok": gate_ok,
                        "peak_date": pd.Timestamp(
                            escrow_daily.iloc[int(metrics["peak_index"])]["date"]
                        ).date().isoformat(),
                        "trough_date": pd.Timestamp(
                            escrow_daily.iloc[int(metrics["trough_index"])]["date"]
                        ).date().isoformat(),
                    }
                )
                daily_rows.append(escrow_daily)
    return pd.DataFrame(summary_rows), pd.concat(daily_rows, ignore_index=True)


def _profile_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (multiplier, profile), group in summary.groupby(["slippage_multiplier", "profile"], sort=False):
        full = group[group["window_name"].eq("start_2020")]
        full_row = full.iloc[0] if not full.empty else group.iloc[0]
        rows.append(
            {
                "slippage_multiplier": multiplier,
                "profile": profile,
                "profile_label": str(full_row["profile_label"]),
                "skim_ratio": float(full_row["skim_ratio"]),
                "seed_reserve": float(full_row["seed_reserve"]),
                "reserve_cap": float(full_row["reserve_cap"]),
                "full_total_return_pct": float(full_row["total_return_pct"]),
                "full_retention_pct": float(full_row["return_retention_vs_baseline_pct"]),
                "full_max_dd_pct": float(full_row["max_dd_percent"]),
                "min_retention_pct": float(group["return_retention_vs_baseline_pct"].min()),
                "worst_max_dd_pct": float(group["max_dd_percent"].min()),
                "gate_pass_count": int(group["gate_ok"].sum()),
                "window_count": int(len(group)),
                "strict_all_windows": int(group["gate_ok"].sum() == len(group)),
                "max_reserve_equity": float(group["max_reserve_equity"].max()),
                "total_transfer_count": int(group["total_transfer_count"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _build_report(
    profile_summary: pd.DataFrame,
    window_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    top_1x = profile_summary[profile_summary["slippage_multiplier"].eq(1.0)].sort_values(
        ["strict_all_windows", "full_max_dd_pct", "full_retention_pct"],
        ascending=[False, False, False],
    )
    pressure = profile_summary[
        profile_summary["profile"].isin(decision.get("focus_profiles", []))
    ].sort_values(["profile", "slippage_multiplier"])
    windows = window_summary[
        window_summary["profile"].isin(decision.get("focus_profiles", []))
        & window_summary["slippage_multiplier"].eq(1.0)
    ].sort_values(["profile", "window_name"])
    return "\n".join(
        [
            "# Stage044 C3利润留存账户层筛查",
            "",
            "## 定位",
            "",
            "- 本阶段只筛查账户层利润留存，不修改78-1/C3信号、品种池、AI池或入场逻辑。",
            "- 规则：月末若总权益创高，把高水位新增利润的一定比例转入不参与交易的reserve账户，直到reserve达到上限。",
            "- 补充筛查：允许较小初始reserve作为种子资金，再用后续利润补足reserve，检验能否低于11.5万外部现金。",
            "- 这是净值层部署筛查，不是正式实盘规则；若出现候选，仍需要真实引擎验证整数手数、保证金和出入金路径。",
            "",
            "## 1x滑点概要",
            "",
            _to_markdown_table(
                top_1x,
                [
                    "profile",
                    "seed_reserve",
                    "reserve_cap",
                    "skim_ratio",
                    "full_total_return_pct",
                    "full_retention_pct",
                    "full_max_dd_pct",
                    "min_retention_pct",
                    "worst_max_dd_pct",
                    "gate_pass_count",
                    "window_count",
                    "strict_all_windows",
                    "max_reserve_equity",
                ],
                max_rows=40,
            ),
            "",
            "## 关注组合压力对比",
            "",
            _to_markdown_table(
                pressure,
                [
                    "slippage_multiplier",
                    "profile",
                    "seed_reserve",
                    "reserve_cap",
                    "skim_ratio",
                    "full_total_return_pct",
                    "full_retention_pct",
                    "full_max_dd_pct",
                    "min_retention_pct",
                    "worst_max_dd_pct",
                    "gate_pass_count",
                    "window_count",
                    "strict_all_windows",
                ],
                max_rows=80,
            ),
            "",
            "## 关注组合1x多周期",
            "",
            _to_markdown_table(
                windows,
                [
                    "profile",
                    "window_name",
                    "total_return_pct",
                    "return_retention_vs_baseline_pct",
                    "max_dd_percent",
                    "baseline_max_dd_pct",
                    "seed_reserve",
                    "end_reserve_equity",
                    "gate_ok",
                ],
                max_rows=120,
            ),
            "",
            "## 决策",
            "",
            "```json",
            json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )


def main() -> None:
    daily = _load_daily()
    window_summary, escrow_daily = _summarize(daily)
    profile_summary = _profile_summary(window_summary)

    strict_1x = profile_summary[
        profile_summary["slippage_multiplier"].eq(1.0)
        & profile_summary["strict_all_windows"].eq(1)
    ].sort_values(["full_retention_pct", "full_max_dd_pct"], ascending=[False, False])
    improved_strict_1x = strict_1x[strict_1x["seed_reserve"] < 115_000.0]
    if not improved_strict_1x.empty:
        decision_status = "profit_escrow_screen_candidate"
        best = improved_strict_1x.sort_values(
            ["seed_reserve", "full_retention_pct"],
            ascending=[True, False],
        ).iloc[0].to_dict()
    elif not strict_1x.empty:
        decision_status = "profit_escrow_no_incremental_vs_external_cash"
        best = strict_1x.sort_values(
            ["seed_reserve", "full_retention_pct"],
            ascending=[True, False],
        ).iloc[0].to_dict()
    else:
        decision_status = "profit_escrow_screen_fail"
        candidates = profile_summary[profile_summary["slippage_multiplier"].eq(1.0)].copy()
        candidates = candidates[candidates["full_max_dd_pct"] >= TARGET_MAX_DD_PCT]
        if candidates.empty:
            candidates = profile_summary[profile_summary["slippage_multiplier"].eq(1.0)].copy()
        best = candidates.sort_values(
            ["full_retention_pct", "full_max_dd_pct"],
            ascending=[False, False],
        ).iloc[0].to_dict()

    focus_profiles = ["no_escrow", str(best["profile"])]
    for profile in [
        "skim100_cap67k",
        "seed67_no_skim",
        "seed67_skim100_cap115k",
        "seed100_no_skim",
        "seed115_no_skim",
    ]:
        if profile not in focus_profiles:
            focus_profiles.append(profile)

    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "source_profile": SOURCE_PROFILE,
        "target_max_dd_pct": TARGET_MAX_DD_PCT,
        "return_retention_gate_pct": RETURN_RETENTION_GATE_PCT,
        "decision": decision_status,
        "best_1x": best,
        "strict_1x_count": int(len(strict_1x)),
        "strict_2x_count": int(
            (
                profile_summary["slippage_multiplier"].eq(2.0)
                & profile_summary["strict_all_windows"].eq(1)
            ).sum()
        ),
        "focus_profiles": focus_profiles,
        "interpretation": (
            "净值层有候选，需要真实引擎验证"
            if decision_status.endswith("candidate")
            else "当前利润留存形状未通过多周期闸门"
        ),
    }

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_profile_summary_{MODEL_TAG}.csv"
    window_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv"
    daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    profile_summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    window_summary.to_csv(window_path, index=False, encoding="utf-8-sig")
    escrow_daily.to_csv(daily_path, index=False, encoding="utf-8-sig")
    report_path.write_text(_build_report(profile_summary, window_summary, decision), encoding="utf-8")
    decision_path.write_text(
        json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"report={report_path}")
    print(f"profile_summary={summary_path}")
    print(f"window_summary={window_path}")
    print(f"daily={daily_path}")


if __name__ == "__main__":
    main()
