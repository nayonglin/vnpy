from __future__ import annotations

import hashlib
import inspect
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_range_reversion_directed_portfolio_strategy import QmtRangeReversionDirectedPortfolioStrategy
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OPEN_BROWSER_CHART, save_backtest_artifacts
from run_qmt_range_reversion_core4_directed_backtest import build_core4_directed_setting
from run_qmt_roll_backtest import build_backtest_engine, compute_round_trip_win_ratio


PROJECT_DIR = Path(__file__).resolve().parent
SOURCE_UNIVERSE_PATH = (
    PROJECT_DIR
    / "backtest_outputs"
    / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
)
FULL_COMMODITY_UNIVERSE_PATH = PROJECT_DIR / "qmt_range_reversion_full_commodity_universe_v10.csv"


def build_full_commodity_universe(source: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"product_vt_symbol", "exchange", "eligible"}
    missing = required_columns - set(source.columns)
    if missing:
        raise ValueError(f"full-market universe missing required columns: {sorted(missing)}")

    result = source.copy()
    eligible = pd.to_numeric(result["eligible"], errors="coerce").fillna(0).astype(int)
    exchange = result["exchange"].fillna("").astype(str).str.strip().str.upper()
    product_vt_symbol = result["product_vt_symbol"].fillna("").astype(str).str.strip()
    financial_symbol = product_vt_symbol.str.upper().str.endswith(".CFFEX")
    result = result[(eligible == 1) & (exchange != "CFFEX") & ~financial_symbol].copy()

    result["exchange"] = result["exchange"].astype(str).str.strip().str.upper()
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str).str.strip()
    result = result[result["product_vt_symbol"] != ""].copy()
    if result.empty:
        raise ValueError("full-market universe has no eligible commodity products")
    result = result.drop_duplicates(subset=["product_vt_symbol"], keep="first")
    result["direction_hint"] = "both"
    result["eligible"] = 1
    result["research_source"] = "full_market_tradable_universe_v1"
    result["notes"] = "all_eligible_commodity_products_excluding_cffex"
    return result.sort_values("product_vt_symbol").reset_index(drop=True)


def materialize_full_commodity_universe(
    source_path: str | Path = SOURCE_UNIVERSE_PATH,
    output_path: str | Path = FULL_COMMODITY_UNIVERSE_PATH,
) -> pd.DataFrame:
    source_path = Path(source_path)
    output_path = Path(output_path)
    source = pd.read_csv(source_path, encoding="utf-8-sig")
    universe = build_full_commodity_universe(source)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(output_path, index=False, encoding="utf-8-sig")
    return universe


def load_or_materialize_full_commodity_universe(
    source_path: str | Path = SOURCE_UNIVERSE_PATH,
    output_path: str | Path = FULL_COMMODITY_UNIVERSE_PATH,
) -> pd.DataFrame:
    source_path = Path(source_path)
    output_path = Path(output_path)
    if source_path.exists():
        return materialize_full_commodity_universe(source_path, output_path)
    if not output_path.exists():
        raise FileNotFoundError(
            f"neither source universe nor frozen commodity universe exists: "
            f"{source_path}, {output_path}"
        )

    frozen = pd.read_csv(output_path, encoding="utf-8-sig")
    universe = build_full_commodity_universe(frozen)
    universe.to_csv(output_path, index=False, encoding="utf-8-sig")
    return universe


def build_full_commodity_v10_setting(
    margin_ratios: dict[str, float],
    *,
    risk_ratio: float = 0.008,
    capital: float = 200_000,
    product_universe_path: str | Path = FULL_COMMODITY_UNIVERSE_PATH,
) -> dict[str, object]:
    product_universe_path = Path(product_universe_path)
    setting = build_core4_directed_setting(
        margin_ratios,
        risk_ratio=risk_ratio,
        capital=capital,
        product_universe_path=product_universe_path,
    )
    setting.update(
        {
            "product_universe_csv_path": str(product_universe_path),
            "range_direction_hints_path": "",
            "range_direction_hints_required": False,
            "long_entry_enabled": True,
            "short_entry_enabled": True,
            "range_use_product_continuous_signal": True,
            "range_product_signal_adjustment_mode": "back_adjust_additive",
            "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
            "range_previous_day_stop_long_enabled": False,
            "range_previous_day_stop_short_enabled": True,
            "range_two_stage_stop_enabled": True,
            "range_soft_stop_confirm_bars": 1,
            "range_hard_stop_r_multiple": 2.0,
        }
    )
    return setting


def product_count_from_metadata(metadata: dict[str, Any]) -> int:
    return len(metadata.get("product_symbols", []))


def _sha256_file(path: str | Path) -> str:
    path = Path(path)
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_run_identity(
    setting: dict[str, object],
    *,
    product_universe_path: str | Path,
    source_universe_path: str | Path = SOURCE_UNIVERSE_PATH,
) -> dict[str, str]:
    setting_payload = json.dumps(setting, sort_keys=True, default=str, separators=(",", ":"))
    strategy_path = Path(inspect.getfile(QmtRangeReversionDirectedPortfolioStrategy))
    return {
        "execution_model": "same_day_close_on_bar",
        "setting_sha256": hashlib.sha256(setting_payload.encode("utf-8")).hexdigest(),
        "product_universe_sha256": _sha256_file(product_universe_path),
        "source_universe_sha256": _sha256_file(source_universe_path),
        "strategy_source_sha256": _sha256_file(strategy_path),
        "runner_source_sha256": _sha256_file(__file__),
    }


def run_backtest(
    *,
    risk_ratio: float = 0.008,
    analysis_start: datetime = START_DT,
    analysis_end: datetime = END_DT,
    preload_start: datetime | None = None,
    capital: float = 200_000,
    save_artifacts: bool = True,
    product_universe_path: str | Path = FULL_COMMODITY_UNIVERSE_PATH,
    file_prefix: str = "qmt_range_reversion_full_commodity_v10",
    chart_title: str = "QMT Range Reversion Full Commodity V10 Backtest",
    strategy_tag: str = "range_reversion_full_commodity_v10",
) -> tuple[Any, Any, dict[str, Any]]:
    preload_start = preload_start or max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    product_universe_path = Path(product_universe_path)
    if product_universe_path == FULL_COMMODITY_UNIVERSE_PATH:
        load_or_materialize_full_commodity_universe(output_path=product_universe_path)

    engine, metadata = build_backtest_engine(
        preload_start=preload_start,
        backtest_end=analysis_end,
        capital=capital,
        product_universe_csv_path=str(product_universe_path),
    )
    setting = build_full_commodity_v10_setting(
        metadata["margin_ratios"],
        risk_ratio=risk_ratio,
        capital=capital,
        product_universe_path=product_universe_path,
    )
    engine.add_strategy(QmtRangeReversionDirectedPortfolioStrategy, setting)

    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is not None:
        analysis_df = daily_df.loc[
            (daily_df.index >= analysis_start.date())
            & (daily_df.index <= analysis_end.date())
        ].copy()
    else:
        analysis_df = None

    statistics = engine.calculate_statistics(analysis_df)
    win_ratio_pct, win_count, round_trip_count = compute_round_trip_win_ratio(engine)
    statistics.update(
        {
            "win_ratio": win_ratio_pct,
            "win_count": win_count,
            "round_trip_count": round_trip_count,
            "strategy_tag": strategy_tag,
            "product_universe_csv_path": str(product_universe_path),
            "product_count": product_count_from_metadata(metadata),
            "risk_ratio": risk_ratio,
            "capital": capital,
            "analysis_start_requested": analysis_start.date().isoformat(),
            "analysis_end_requested": analysis_end.date().isoformat(),
            **build_run_identity(setting, product_universe_path=product_universe_path),
        }
    )
    engine.daily_df = analysis_df

    if save_artifacts:
        save_backtest_artifacts(
            engine,
            statistics,
            file_prefix=file_prefix,
            chart_title=chart_title,
            mapping_csv_path=Path(str(setting["mapping_csv_path"])).resolve(),
            analysis_start=analysis_start,
        )
    return engine, analysis_df, statistics


def main() -> None:
    universe = load_or_materialize_full_commodity_universe()
    print(f"full commodity products: {len(universe)}")
    engine, _, statistics = run_backtest()
    print(statistics)
    if OPEN_BROWSER_CHART:
        engine.show_chart()


if __name__ == "__main__":
    main()
