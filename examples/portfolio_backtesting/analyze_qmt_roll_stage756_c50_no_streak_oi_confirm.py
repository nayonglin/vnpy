from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage754_entry_oi_change_winner_loser as s754
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_winner_trade_forensics"

OUTPUT_PREFIX = "qmt_roll_stage756_c50_no_streak_oi_confirm"
MODEL_TAG = "stage756_c50_no_streak_oi_confirm_v1"

TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
GROUP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_group_stats_{MODEL_TAG}.csv"
YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stats_{MODEL_TAG}.csv"
DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_direction_stats_{MODEL_TAG}.csv"
HIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_hit_lots_{MODEL_TAG}.csv"
MISS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_miss_lots_{MODEL_TAG}.csv"


def _run_c50_engine() -> tuple[Any, Any, dict[str, Any]]:
    metadata = s719.s513._metadata()
    spec = s748._candidate_500k_spec(metadata)

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
    enriched = pd.concat([data.reset_index(drop=True), pd.DataFrame(feature_rows)], axis=1)
    enriched["entry_oi_price_confirm_filled"] = (
        pd.to_numeric(enriched["entry_oi_price_confirm"], errors="coerce").fillna(0).astype(int)
    )
    return enriched


def _stats_row(frame: pd.DataFrame, *, sample: str, hit_value: int | None = None) -> dict[str, Any]:
    if hit_value is not None:
        group = frame[pd.to_numeric(frame["entry_oi_price_confirm"], errors="coerce").eq(hit_value)].copy()
    else:
        group = frame.copy()
    return {
        "sample": sample,
        "entry_oi_price_confirm": hit_value if hit_value is not None else "all",
        "rows": int(len(group)),
        "products": int(group["product"].nunique()) if len(group) else 0,
        "years": int(pd.to_datetime(group["entry_date"]).dt.year.nunique()) if len(group) else 0,
        "profit_count": int(group["realized_outcome"].eq("profit").sum()),
        "loss_count": int(group["realized_outcome"].eq("loss").sum()),
        "flat_count": int(group["realized_outcome"].eq("flat").sum()),
        "profit_rate_pct": float(group["realized_outcome"].eq("profit").mean() * 100.0) if len(group) else np.nan,
        "loss_rate_pct": float(group["realized_outcome"].eq("loss").mean() * 100.0) if len(group) else np.nan,
        "total_realized_pnl": float(pd.to_numeric(group["realized_pnl"], errors="coerce").sum()) if len(group) else 0.0,
        "avg_realized_pnl": float(pd.to_numeric(group["realized_pnl"], errors="coerce").mean()) if len(group) else np.nan,
        "median_realized_pnl": float(pd.to_numeric(group["realized_pnl"], errors="coerce").median()) if len(group) else np.nan,
        "avg_theory_return_pct": float(pd.to_numeric(group["theory_return_pct"], errors="coerce").mean()) if len(group) else np.nan,
        "median_theory_return_pct": (
            float(pd.to_numeric(group["theory_return_pct"], errors="coerce").median()) if len(group) else np.nan
        ),
        "avg_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").mean()) if len(group) else np.nan,
        "median_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()) if len(group) else np.nan,
        "max_realized_pnl": float(pd.to_numeric(group["realized_pnl"], errors="coerce").max()) if len(group) else np.nan,
        "min_realized_pnl": float(pd.to_numeric(group["realized_pnl"], errors="coerce").min()) if len(group) else np.nan,
        "max_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").max()) if len(group) else np.nan,
        "min_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").min()) if len(group) else np.nan,
    }


def _group_stats(data: pd.DataFrame) -> pd.DataFrame:
    oi_available = data[data["oi_available"].eq(1)].copy()
    rows = [
        _stats_row(data, sample="all_closed_lots", hit_value=None),
        _stats_row(oi_available, sample="oi_available", hit_value=None),
        _stats_row(oi_available, sample="oi_available", hit_value=1),
        _stats_row(oi_available, sample="oi_available", hit_value=0),
        _stats_row(data[~data["oi_available"].eq(1)], sample="oi_missing", hit_value=None),
    ]
    all_non_hit = data[~pd.to_numeric(data["entry_oi_price_confirm"], errors="coerce").eq(1)].copy()
    rows.append(_stats_row(all_non_hit, sample="all_non_hit_or_missing", hit_value=None))
    return pd.DataFrame(rows)


def _bucket_stats(data: pd.DataFrame, column: str, path: Path) -> pd.DataFrame:
    valid = data[data["oi_available"].eq(1)].copy()
    rows: list[dict[str, Any]] = []
    if valid.empty or column not in valid.columns:
        result = pd.DataFrame()
        result.to_csv(path, index=False, encoding="utf-8-sig")
        return result
    for value, group in valid.groupby(column, dropna=False, sort=True):
        for hit in [1, 0]:
            subset = group[pd.to_numeric(group["entry_oi_price_confirm"], errors="coerce").eq(hit)].copy()
            row = _stats_row(subset, sample=str(value), hit_value=None)
            row[column] = value
            row["entry_oi_price_confirm"] = hit
            rows.append(row)
    result = pd.DataFrame(rows)
    result.to_csv(path, index=False, encoding="utf-8-sig")
    return result


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    engine, spec, metadata = _run_c50_engine()
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

    hit = enriched[pd.to_numeric(enriched["entry_oi_price_confirm"], errors="coerce").eq(1)].copy()
    miss = enriched[
        enriched["oi_available"].eq(1)
        & ~pd.to_numeric(enriched["entry_oi_price_confirm"], errors="coerce").eq(1)
    ].copy()
    hit.to_csv(HIT_PATH, index=False, encoding="utf-8-sig")
    miss.to_csv(MISS_PATH, index=False, encoding="utf-8-sig")

    group = _group_stats(enriched)
    group.to_csv(GROUP_PATH, index=False, encoding="utf-8-sig")
    year = _bucket_stats(enriched.assign(entry_year=pd.to_datetime(enriched["entry_date"]).dt.year), "entry_year", YEAR_PATH)
    direction = _bucket_stats(enriched, "direction", DIRECTION_PATH)

    summary = pd.DataFrame(
        [
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "source_line_id": s748.LINE_ID,
                "variant": spec.capital.variant,
                "profile": spec.profile,
                "capital": float(spec.capital.c3_capital),
                "risk_multiplier": float(spec.capital.risk_multiplier),
                "streak_risk_multipliers": str(spec.overrides.get("streak_risk_multipliers", "")),
                "enable_streak_entry_structure_risk_recovery": bool(
                    spec.overrides.get("enable_streak_entry_structure_risk_recovery", True)
                ),
                "enable_recovery_sleeve": bool(spec.overrides.get("enable_recovery_sleeve", True)),
                "total_closed_lots": int(len(enriched)),
                "oi_available": int(enriched["oi_available"].sum()),
                "oi_missing": int(len(enriched) - enriched["oi_available"].sum()),
                "entry_oi_price_confirm_hits": int(len(hit)),
                "hit_profit_count": int(hit["realized_outcome"].eq("profit").sum()),
                "hit_loss_count": int(hit["realized_outcome"].eq("loss").sum()),
                "hit_profit_rate_pct": float(hit["realized_outcome"].eq("profit").mean() * 100.0)
                if len(hit)
                else np.nan,
                "hit_total_realized_pnl": float(hit["realized_pnl"].sum()) if len(hit) else 0.0,
                "miss_oi_available_count": int(len(miss)),
                "miss_profit_count": int(miss["realized_outcome"].eq("profit").sum()),
                "miss_loss_count": int(miss["realized_outcome"].eq("loss").sum()),
                "miss_profit_rate_pct": float(miss["realized_outcome"].eq("profit").mean() * 100.0)
                if len(miss)
                else np.nan,
                "miss_total_realized_pnl": float(miss["realized_pnl"].sum()) if len(miss) else 0.0,
                "decision": "c50_no_streak_oi_confirm_readonly_forensics",
                "closed_lots_path": str(CLOSED_LOTS_PATH),
                "hit_path": str(HIT_PATH),
                "miss_path": str(MISS_PATH),
                "group_path": str(GROUP_PATH),
                "year_path": str(YEAR_PATH),
                "direction_path": str(DIRECTION_PATH),
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
        "realized_pnl",
        "realized_outcome",
        "theory_return_pct",
        "r_multiple",
        "signal",
        "exit_reason",
        "risk_multiplier",
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
    print("\nYEAR_STATS")
    print(year.to_string(index=False))
    print("\nDIRECTION_STATS")
    print(direction.to_string(index=False))
    print("\nHIT_LOTS")
    print(hit[display_cols].to_string(index=False))


if __name__ == "__main__":
    main()
