from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_SHORT_ALIAS,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage237_balanced_tranche_shadow_ledger_v1"
OUTPUT_PREFIX = "qmt_roll_stage237_balanced_tranche_shadow_ledger"

OFFICIAL_DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily.csv"
COLD_START_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage186_stage78_2026_50w_cold_start_20260101_50w_to_20260430_daily.csv"
COLD_START_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage186_stage78_2026_50w_cold_start_summary_stage186_stage78_2026_50w_cold_start_v1.json"
STAGE232_CURVES_PATH = OUTPUT_DIR / "qmt_roll_stage232_deployment_capital_tranching_curves_stage232_deployment_capital_tranching_v1.csv"


@dataclass(frozen=True)
class TranchePolicy:
    name: str
    production_floor: float
    sweep_start: float
    sweep_ratio: float
    lock_ratio: float
    expansion_ratio: float


BALANCED_TRANCHE_V1 = TranchePolicy(
    name="balanced_tranche_v1",
    production_floor=OFFICIAL_STAGE78_CAPITAL,
    sweep_start=5_000_000.0,
    sweep_ratio=0.50,
    lock_ratio=0.60,
    expansion_ratio=0.40,
)


def _load_daily(path: Path, scenario_name: str, display_label: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    df = df.dropna(subset=["date", "balance"]).sort_values("date").reset_index(drop=True)
    df["daily_return"] = df["balance"].pct_change().fillna(df["balance"] / OFFICIAL_STAGE78_CAPITAL - 1.0)
    df["scenario_name"] = scenario_name
    df["display_label"] = display_label
    return df


def _load_stage232_history_curve() -> pd.DataFrame:
    df = pd.read_csv(STAGE232_CURVES_PATH)
    df = df[
        df["policy"].eq(BALANCED_TRANCHE_V1.name)
        & df["window_name"].eq("since_2020")
    ].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    numeric_cols = [
        "production_equity",
        "locked_equity",
        "expansion_equity",
        "total_equity",
        "sweep_amount",
        "refill_amount",
        "daily_return_source",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    df["scenario_name"] = "full_history_2020_2026"
    df["display_label"] = "2020起点历史账本"
    df["source_balance"] = df["total_equity"]
    df["daily_return"] = df["daily_return_source"]
    df["event"] = np.select(
        [df["sweep_amount"] > 0, df["refill_amount"] > 0],
        ["sweep", "refill"],
        default="none",
    )
    df["threshold_gap_to_next_sweep"] = np.maximum(BALANCED_TRANCHE_V1.sweep_start - df["production_equity"], 0.0)
    return df[
        [
            "date",
            "scenario_name",
            "display_label",
            "source_balance",
            "daily_return",
            "production_equity",
            "locked_equity",
            "expansion_equity",
            "total_equity",
            "sweep_amount",
            "refill_amount",
            "event",
            "threshold_gap_to_next_sweep",
        ]
    ].copy()


def _is_month_end(dates: pd.Series, idx: int) -> bool:
    if idx == len(dates) - 1:
        return True
    current = dates.iloc[idx]
    nxt = dates.iloc[idx + 1]
    return current.month != nxt.month or current.year != nxt.year


def _simulate(df: pd.DataFrame, policy: TranchePolicy) -> tuple[pd.DataFrame, pd.DataFrame]:
    production = float(OFFICIAL_STAGE78_CAPITAL)
    locked = 0.0
    expansion = 0.0
    records: list[dict[str, Any]] = []
    transfer_rows: list[dict[str, Any]] = []

    dates = df["date"].reset_index(drop=True)
    returns = df["daily_return"].to_numpy(dtype=float)

    for idx, daily_return in enumerate(returns):
        date = dates.iloc[idx]
        source_balance = float(df["balance"].iloc[idx])
        production *= 1.0 + float(daily_return)
        if production < 0:
            production = 0.0

        refill = 0.0
        sweep = 0.0
        event = "none"
        if _is_month_end(dates, idx):
            if production < policy.production_floor and expansion > 0:
                refill = min(policy.production_floor - production, expansion)
                production += refill
                expansion -= refill
                event = "refill"
            if production > policy.sweep_start:
                sweep = (production - policy.sweep_start) * policy.sweep_ratio
                production -= sweep
                locked_add = sweep * policy.lock_ratio
                expansion_add = sweep * policy.expansion_ratio
                locked += locked_add
                expansion += expansion_add
                event = "sweep" if event == "none" else "refill_and_sweep"
                transfer_rows.append(
                    {
                        "date": date,
                        "scenario_name": str(df["scenario_name"].iloc[idx]),
                        "event_type": "sweep",
                        "sweep_amount": sweep,
                        "locked_add": locked_add,
                        "expansion_add": expansion_add,
                        "production_after": production,
                        "locked_after": locked,
                        "expansion_after": expansion,
                    }
                )
            if refill > 0:
                transfer_rows.append(
                    {
                        "date": date,
                        "scenario_name": str(df["scenario_name"].iloc[idx]),
                        "event_type": "refill",
                        "sweep_amount": 0.0,
                        "locked_add": 0.0,
                        "expansion_add": -refill,
                        "production_after": production,
                        "locked_after": locked,
                        "expansion_after": expansion,
                    }
                )

        total_equity = production + locked + expansion
        threshold_gap = max(policy.sweep_start - production, 0.0)
        records.append(
            {
                "date": date,
                "scenario_name": str(df["scenario_name"].iloc[idx]),
                "display_label": str(df["display_label"].iloc[idx]),
                "source_balance": source_balance,
                "daily_return": float(daily_return),
                "production_equity": production,
                "locked_equity": locked,
                "expansion_equity": expansion,
                "total_equity": total_equity,
                "sweep_amount": sweep,
                "refill_amount": refill,
                "event": event,
                "threshold_gap_to_next_sweep": threshold_gap,
            }
        )

    ledger = pd.DataFrame(records)
    transfers = pd.DataFrame(transfer_rows)
    return ledger, transfers


def _path_metrics(total_equity: np.ndarray) -> dict[str, float]:
    high = np.maximum.accumulate(total_equity)
    drawdown = total_equity - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0) * 100.0
    daily_return = pd.Series(total_equity).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(daily_return, ddof=1)) if len(daily_return) > 1 else 0.0
    sharpe = float(np.mean(daily_return) / std * np.sqrt(252)) if std > 0 else 0.0
    return {
        "end_total_equity": float(total_equity[-1]),
        "total_return_pct": float((total_equity[-1] / OFFICIAL_STAGE78_CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
    }


def _summarize_scenario(ledger: pd.DataFrame, transfers: pd.DataFrame) -> dict[str, Any]:
    scenario_name = str(ledger["scenario_name"].iloc[0])
    display_label = str(ledger["display_label"].iloc[0])
    metrics = _path_metrics(ledger["total_equity"].to_numpy(dtype=float))
    sweep_events = transfers[transfers["event_type"].eq("sweep")].copy() if not transfers.empty else pd.DataFrame()
    first_sweep_date = ""
    if not sweep_events.empty:
        first_sweep_date = pd.to_datetime(sweep_events["date"].iloc[0]).strftime("%Y-%m-%d")
    return {
        "scenario_name": scenario_name,
        "display_label": display_label,
        **metrics,
        "end_production_equity": float(ledger["production_equity"].iloc[-1]),
        "end_locked_equity": float(ledger["locked_equity"].iloc[-1]),
        "end_expansion_equity": float(ledger["expansion_equity"].iloc[-1]),
        "total_swept": float(ledger["sweep_amount"].sum()),
        "total_refilled": float(ledger["refill_amount"].sum()),
        "sweep_event_count": int((ledger["sweep_amount"] > 0).sum()),
        "refill_event_count": int((ledger["refill_amount"] > 0).sum()),
        "first_sweep_date": first_sweep_date,
        "current_threshold_gap": float(ledger["threshold_gap_to_next_sweep"].iloc[-1]),
    }


def _build_transfers_from_ledger(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in ledger.iterrows():
        if float(row.get("sweep_amount", 0.0)) > 0:
            sweep = float(row["sweep_amount"])
            rows.append(
                {
                    "date": row["date"],
                    "scenario_name": row["scenario_name"],
                    "event_type": "sweep",
                    "sweep_amount": sweep,
                    "locked_add": sweep * BALANCED_TRANCHE_V1.lock_ratio,
                    "expansion_add": sweep * BALANCED_TRANCHE_V1.expansion_ratio,
                    "production_after": row["production_equity"],
                    "locked_after": row["locked_equity"],
                    "expansion_after": row["expansion_equity"],
                }
            )
        if float(row.get("refill_amount", 0.0)) > 0:
            refill = float(row["refill_amount"])
            rows.append(
                {
                    "date": row["date"],
                    "scenario_name": row["scenario_name"],
                    "event_type": "refill",
                    "sweep_amount": 0.0,
                    "locked_add": 0.0,
                    "expansion_add": -refill,
                    "production_after": row["production_equity"],
                    "locked_after": row["locked_equity"],
                    "expansion_after": row["expansion_equity"],
                }
            )
    return pd.DataFrame(rows)


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df.loc[:, [c for c in columns if c in df.columns]].head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_numeric_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{float(x):,.4f}" if abs(float(x)) < 1000 else f"{float(x):,.0f}")
    return view.to_markdown(index=False)


def _build_report(summary_df: pd.DataFrame, ledger_df: pd.DataFrame, transfers_df: pd.DataFrame, cold_start_summary: dict[str, Any], paths: dict[str, str]) -> str:
    cold_summary = summary_df[summary_df["scenario_name"].eq("cold_start_2026")].copy()
    historical_summary = summary_df[summary_df["scenario_name"].eq("full_history_2020_2026")].copy()
    cold_target_date = cold_start_summary.get("target_date", "")
    cold_risk = cold_start_summary.get("risk_snapshot", {})
    lines = [
        "# Stage237 balanced_tranche_v1 影子盘资金分层账本",
        "",
        "## 口径",
        "",
        f"- 基准：`{OFFICIAL_STAGE78_SHORT_ALIAS}` / `{OFFICIAL_STAGE78_VERSION}`",
        f"- 部署制度：`{BALANCED_TRANCHE_V1.name}`，生产账户超过 `5,000,000` 时，提取超额部分的 `50%`；其中 `60%` 转锁盈账户，`40%` 转扩张储备。",
        "- 输入场景A：`full_history_2020_2026`，用于验证历史提款与锁盈路径。",
        f"- 输入场景B：`cold_start_2026`，用于给当前冷启动影子盘提供部署账本状态；目标交易日 `{cold_target_date}`。",
        "- 注意：这是账户部署层账本工具，不修改 `78-1` 信号与仓位逻辑。",
        "",
        "## 场景汇总",
        "",
        _to_markdown(
            summary_df,
            [
                "scenario_name",
                "end_total_equity",
                "total_return_pct",
                "max_drawdown_pct",
                "sharpe_ratio",
                "end_production_equity",
                "end_locked_equity",
                "end_expansion_equity",
                "total_swept",
                "sweep_event_count",
                "first_sweep_date",
                "current_threshold_gap",
            ],
            max_rows=10,
        ),
        "",
        "## 当前冷启动状态",
        "",
        f"- 风险级别：`{cold_risk.get('risk_level', '')}`",
        f"- 当前影子期末权益：`{cold_risk.get('balance', 0):,.0f}`",
        f"- 当前生产账户权益：`{float(cold_summary['end_production_equity'].iloc[0]) if not cold_summary.empty else 0:,.0f}`",
        f"- 当前锁盈账户：`{float(cold_summary['end_locked_equity'].iloc[0]) if not cold_summary.empty else 0:,.0f}`",
        f"- 当前扩张储备：`{float(cold_summary['end_expansion_equity'].iloc[0]) if not cold_summary.empty else 0:,.0f}`",
        f"- 离首次提款阈值还差：`{float(cold_summary['current_threshold_gap'].iloc[0]) if not cold_summary.empty else 0:,.0f}`",
        "",
        "## 历史提款事件",
        "",
        _to_markdown(
            transfers_df[transfers_df["scenario_name"].eq("full_history_2020_2026")].copy(),
            [
                "date",
                "event_type",
                "sweep_amount",
                "locked_add",
                "expansion_add",
                "production_after",
                "locked_after",
                "expansion_after",
            ],
            max_rows=20,
        ),
        "",
        "## 冷启动账本尾部",
        "",
        _to_markdown(
            ledger_df[ledger_df["scenario_name"].eq("cold_start_2026")].tail(15).copy(),
            [
                "date",
                "source_balance",
                "production_equity",
                "locked_equity",
                "expansion_equity",
                "total_equity",
                "sweep_amount",
                "refill_amount",
                "event",
                "threshold_gap_to_next_sweep",
            ],
            max_rows=15,
        ),
        "",
        "## 结论",
        "",
        "- `balanced_tranche_v1` 已经可以落成每日/每月可执行账本，而不是只停留在研究曲线。",
        "- 历史账本回答“过去什么时候开始锁盈”，冷启动账本回答“今天离第一次锁盈还有多远”。",
        "- 当前冷启动仍处于纯生产账户阶段，符合 Stage233 对阈值前风险暴露边界的判断。",
        "",
        "## 输出文件",
        "",
    ]
    for key, value in paths.items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_official_stage78_manifest()
    cold_start_summary = json.loads(COLD_START_SUMMARY_PATH.read_text(encoding="utf-8"))

    history_ledger = _load_stage232_history_curve()
    history_transfers = _build_transfers_from_ledger(history_ledger)

    cold_df = _load_daily(COLD_START_DAILY_PATH, "cold_start_2026", "2026冷启动账本")
    cold_ledger, cold_transfers = _simulate(cold_df, BALANCED_TRANCHE_V1)

    ledgers: list[pd.DataFrame] = [history_ledger, cold_ledger]
    transfers: list[pd.DataFrame] = []
    if not history_transfers.empty:
        transfers.append(history_transfers)
    if not cold_transfers.empty:
        transfers.append(cold_transfers)
    summary_rows: list[dict[str, Any]] = [
        _summarize_scenario(history_ledger, history_transfers),
        _summarize_scenario(cold_ledger, cold_transfers),
    ]

    ledger_df = pd.concat(ledgers, ignore_index=True)
    transfers_df = pd.concat(transfers, ignore_index=True) if transfers else pd.DataFrame(
        columns=["date", "scenario_name", "event_type", "sweep_amount", "locked_add", "expansion_add", "production_after", "locked_after", "expansion_after"]
    )
    summary_df = pd.DataFrame(summary_rows)

    paths = {
        "summary_csv": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv").resolve()),
        "ledger_csv": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_ledger_{MODEL_TAG}.csv").resolve()),
        "transfers_csv": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_transfers_{MODEL_TAG}.csv").resolve()),
        "report_md": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md").resolve()),
        "manifest_json": str((OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json").resolve()),
    }
    summary_df.to_csv(paths["summary_csv"], index=False, encoding="utf-8-sig")
    ledger_df.to_csv(paths["ledger_csv"], index=False, encoding="utf-8-sig")
    transfers_df.to_csv(paths["transfers_csv"], index=False, encoding="utf-8-sig")
    Path(paths["report_md"]).write_text(
        _build_report(summary_df, ledger_df, transfers_df, cold_start_summary, paths),
        encoding="utf-8",
    )
    Path(paths["manifest_json"]).write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "output_prefix": OUTPUT_PREFIX,
                "line_id": "futures_trend_risk_overlay",
                "official_manifest": manifest,
                "policy": BALANCED_TRANCHE_V1.__dict__,
                "inputs": {
                    "stage232_curves": str(STAGE232_CURVES_PATH.resolve()),
                    "official_daily": str(OFFICIAL_DAILY_PATH.resolve()),
                    "cold_start_daily": str(COLD_START_DAILY_PATH.resolve()),
                    "cold_start_summary": str(COLD_START_SUMMARY_PATH.resolve()),
                },
                "paths": paths,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(paths, ensure_ascii=False, indent=2))
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
