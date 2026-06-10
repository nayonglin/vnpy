from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage750_official_500k_vs_c50_monthly_start as s750
import analyze_qmt_roll_stage754_entry_oi_change_winner_loser as s754
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_winner_trade_forensics"

OUTPUT_PREFIX = "qmt_roll_stage755_a50_riskfloor_oi_confirm"
MODEL_TAG = "stage755_a50_riskfloor_oi_confirm_v1"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
RISKFLOOR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_riskfloor_lots_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
GROUP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_group_stats_{MODEL_TAG}.csv"

RISK_FLOOR_MAX = 0.100001


def _run_a50_engine() -> tuple[Any, Any, dict[str, Any]]:
    metadata = s719.s513._metadata()
    spec = s750._official_500k_spec(metadata)

    s719.s653.s517.assert_stage196_database_sentinels()
    s719.s653.s517.s506._patch_stage506_raw_roots()
    c3_overrides = s719.s513._c3_overrides(s719.s653.s517.START_DT)
    preload_start = max(s719.s653.s517.PRELOAD_START_DT, s719.s653.s517.START_DT - timedelta(days=365))
    _, open_map = s719.s653.s517.s506.s501._seed_proxy_maps()
    engine = s719.s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=s719.s653.s517.Interval.DAILY,
        start=preload_start,
        end=s719.s653.s517.END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=spec.capital.c3_capital,
    )
    setting = s719.s653.s517.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s719.s653.s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
        strategy_overrides=c3_overrides,
    )
    setting["capital_base"] = spec.capital.c3_capital
    setting.update(spec.overrides)
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    engine.calculate_result()
    return engine, replace(spec), metadata


def _profit_label(value: Any) -> str:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return "unknown"
    if number > 0:
        return "profit"
    if number < 0:
        return "loss"
    return "flat"


def _add_oi_features(closed: pd.DataFrame) -> pd.DataFrame:
    data = closed.copy()
    direction_sign = np.where(data["direction"].astype(str).eq("long"), 1.0, -1.0)
    data["theory_return_pct"] = (
        direction_sign
        * (pd.to_numeric(data["exit_price"], errors="coerce") - pd.to_numeric(data["entry_price"], errors="coerce"))
        / pd.to_numeric(data["entry_price"], errors="coerce")
        * 100.0
    )
    data["theory_outcome"] = data["theory_return_pct"].map(_profit_label)
    data["realized_outcome"] = data["realized_pnl"].map(_profit_label)
    feature_rows = [s754._entry_window_features(row) for _, row in data.iterrows()]
    return pd.concat([data.reset_index(drop=True), pd.DataFrame(feature_rows)], axis=1)


def _group_stats(riskfloor: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for available_label, frame in [
        ("all_riskfloor", riskfloor),
        ("oi_available", riskfloor[riskfloor["oi_available"].eq(1)]),
    ]:
        for hit in [1, 0]:
            group = frame[pd.to_numeric(frame["entry_oi_price_confirm"], errors="coerce").fillna(-1).eq(hit)]
            if available_label == "all_riskfloor" and hit == 0:
                # Includes both explicit non-hit and missing OI rows.
                group = frame[~pd.to_numeric(frame["entry_oi_price_confirm"], errors="coerce").eq(1)]
            rows.append(
                {
                    "sample": available_label,
                    "entry_oi_price_confirm": int(hit),
                    "rows": int(len(group)),
                    "profit_count": int(group["realized_outcome"].eq("profit").sum()),
                    "loss_count": int(group["realized_outcome"].eq("loss").sum()),
                    "flat_count": int(group["realized_outcome"].eq("flat").sum()),
                    "profit_rate_pct": (
                        float(group["realized_outcome"].eq("profit").mean() * 100.0) if len(group) else np.nan
                    ),
                    "loss_rate_pct": (
                        float(group["realized_outcome"].eq("loss").mean() * 100.0) if len(group) else np.nan
                    ),
                    "avg_realized_pnl": (
                        float(pd.to_numeric(group["realized_pnl"], errors="coerce").mean()) if len(group) else np.nan
                    ),
                    "total_realized_pnl": (
                        float(pd.to_numeric(group["realized_pnl"], errors="coerce").sum()) if len(group) else 0.0
                    ),
                    "avg_theory_return_pct": (
                        float(pd.to_numeric(group["theory_return_pct"], errors="coerce").mean()) if len(group) else np.nan
                    ),
                    "avg_r_multiple": (
                        float(pd.to_numeric(group["r_multiple"], errors="coerce").mean()) if len(group) else np.nan
                    ),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    engine, spec, metadata = _run_a50_engine()
    frames = s719._extract_raw_frames(engine, spec)
    trades = frames["trades"]
    entry_risk = frames["entry_risk"]
    candidates = frames["entry_candidates"]
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")

    closed = s719._build_closed_lots(trades, entry_risk, candidates, metadata)
    enriched = _add_oi_features(closed)
    enriched.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")

    riskfloor = enriched[pd.to_numeric(enriched["risk_multiplier"], errors="coerce").le(RISK_FLOOR_MAX)].copy()
    riskfloor.sort_values(["entry_date", "lot_id"], inplace=True)
    riskfloor.to_csv(RISKFLOOR_PATH, index=False, encoding="utf-8-sig")

    group = _group_stats(riskfloor)
    group.to_csv(GROUP_PATH, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame(
        [
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "variant": spec.capital.variant,
                "profile": spec.profile,
                "capital": float(spec.capital.c3_capital),
                "risk_multiplier": float(spec.capital.risk_multiplier),
                "streak_risk_multipliers": str(spec.overrides.get("streak_risk_multipliers", "")),
                "total_closed_lots": int(len(enriched)),
                "riskfloor_lots": int(len(riskfloor)),
                "riskfloor_oi_available": int(riskfloor["oi_available"].sum()),
                "riskfloor_oi_missing": int(len(riskfloor) - riskfloor["oi_available"].sum()),
                "riskfloor_entry_oi_price_confirm_hits": int(
                    pd.to_numeric(riskfloor["entry_oi_price_confirm"], errors="coerce").eq(1).sum()
                ),
                "riskfloor_hit_profit_count": int(
                    riskfloor[
                        pd.to_numeric(riskfloor["entry_oi_price_confirm"], errors="coerce").eq(1)
                    ]["realized_outcome"].eq("profit").sum()
                ),
                "riskfloor_hit_loss_count": int(
                    riskfloor[
                        pd.to_numeric(riskfloor["entry_oi_price_confirm"], errors="coerce").eq(1)
                    ]["realized_outcome"].eq("loss").sum()
                ),
                "decision": "a50_riskfloor_oi_confirm_readonly_forensics",
                "closed_lots_path": str(CLOSED_LOTS_PATH),
                "riskfloor_path": str(RISKFLOOR_PATH),
                "group_path": str(GROUP_PATH),
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    display_cols = [
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "exit_date",
        "entry_price",
        "exit_price",
        "realized_pnl",
        "realized_outcome",
        "theory_return_pct",
        "r_multiple",
        "signal",
        "exit_reason",
        "risk_multiplier",
        "loss_streak",
        "recovery_sleeve_applied",
        "entry_close",
        "entry_close_prev1",
        "entry_oi",
        "entry_oi_prev1",
        "entry_oi_chg1_pct",
        "entry_price_direction_aligned",
        "entry_oi_gt_prev1",
        "entry_oi_price_confirm",
        "oi_available",
    ]
    print("SUMMARY")
    print(summary.to_string(index=False))
    print("\nGROUP_STATS")
    print(group.to_string(index=False))
    print("\nRISKFLOOR_LOTS")
    print(riskfloor[display_cols].to_string(index=False))


if __name__ == "__main__":
    main()
