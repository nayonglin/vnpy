from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage517_portfolio_margin_deleverage_frontier as s517
import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as s659
from qmt_roll_official_execution_profile import (
    ExecutionStrategyMode,
    resolve_execution_profile,
)
import qmt_roll_official_stage372_shadow_config as stage372_cfg
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path(
    os.environ.get("OFFICIAL_LIVE_OUTPUT_DIR", PROJECT_DIR / "backtest_outputs")
).expanduser().resolve(strict=False)
MODEL_TAG = "stage179_stage372_pending_order_audit_v1"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _enum_text(value: Any) -> str:
    return str(getattr(value, "value", value))


def _pending_order_rows(engine: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for vt_orderid, order in (
        getattr(engine, "active_limit_orders", {}) or {}
    ).items():
        rows.append(
            {
                "vt_orderid": str(vt_orderid),
                "orderid": str(getattr(order, "orderid", "")),
                "vt_symbol": str(getattr(order, "vt_symbol", "")),
                "direction": _enum_text(getattr(order, "direction", "")),
                "offset": _enum_text(getattr(order, "offset", "")),
                "price": float(getattr(order, "price", 0.0) or 0.0),
                "volume": int(float(getattr(order, "volume", 0) or 0)),
                "traded": int(float(getattr(order, "traded", 0) or 0)),
                "datetime": _json_safe(getattr(order, "datetime", "")),
                "status": _enum_text(getattr(order, "status", "")),
            }
        )
    return sorted(rows, key=lambda row: (row["vt_symbol"], row["vt_orderid"]))


def _target_rows(frame: pd.DataFrame, target_date: str) -> pd.DataFrame:
    if frame.empty or "date" not in frame.columns:
        return pd.DataFrame()
    result = frame.copy()
    result["date"] = pd.to_datetime(
        result["date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    return result[result["date"].eq(target_date)].reset_index(drop=True)


def _output_paths(target_date: str) -> dict[str, Path]:
    profile = resolve_execution_profile(ExecutionStrategyMode.STAGE372_20W)
    date_key = target_date.replace("-", "")
    return {
        "pending_orders": profile.pending_orders_path,
        "target_events": OUTPUT_DIR / f"qmt_roll_stage179_stage372_target_events_{date_key}.csv",
        "target_entry_candidates": OUTPUT_DIR / f"qmt_roll_stage179_stage372_entry_candidates_{date_key}.csv",
        "summary": OUTPUT_DIR / f"qmt_roll_stage179_stage372_pending_audit_{date_key}.json",
    }


def run_pending_audit(
    *,
    target_date: str,
    analysis_start: str = stage372_cfg.ANALYSIS_START,
) -> dict[str, Any]:
    profile = resolve_execution_profile(ExecutionStrategyMode.STAGE372_20W)
    target = datetime.strptime(target_date, "%Y-%m-%d")
    start = datetime.strptime(analysis_start, "%Y-%m-%d")
    s659._configure_execution_profile(profile.profile_key)
    metadata = s513._metadata()
    identity_map = s653.s519._product_identity_cluster_map(metadata)
    spec = s659._official_live_spec(identity_map)
    spec = replace(
        spec,
        overrides={
            **spec.overrides,
            "ai_product_pool_eligibility_path": str(
                stage372_cfg.AI_ELIGIBILITY_PATH
            ),
        },
    )

    original_start = s517.START_DT
    original_end = s517.END_DT
    try:
        s517.START_DT = start
        s517.END_DT = target
        s653.s517.assert_stage196_database_sentinels()
        s653.s517.s506._patch_stage506_raw_roots()
        c3_overrides = s513._c3_overrides(s517.START_DT)
        preload_start = max(
            s517.PRELOAD_START_DT,
            s517.START_DT - timedelta(days=365),
        )
        _, open_map = s517.s506.s501._seed_proxy_maps()
        engine = s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
        engine.output = lambda _message: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s517.Interval.DAILY,
            start=preload_start,
            end=s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s517.build_roll_setting(
            metadata["margin_ratios"],
            risk_ratio=s517.BASE_RISK_RATIO
            * float(spec.capital.risk_multiplier),
            strategy_overrides=c3_overrides,
        )
        setting["capital_base"] = spec.capital.c3_capital
        setting.update(spec.overrides)
        engine.add_strategy(QmtRollPortfolioStrategy, setting)
        engine.load_data()
        engine.run_backtesting()

        strategy = getattr(engine, "strategy", None)
        pending_orders = pd.DataFrame(_pending_order_rows(engine))
        trade_events = pd.DataFrame(
            getattr(strategy, "trade_event_diagnostics", [])
            if strategy
            else []
        )
        entry_candidates = pd.DataFrame(
            getattr(strategy, "entry_candidate_snapshots", [])
            if strategy
            else []
        )
        target_events = _target_rows(trade_events, target_date)
        target_candidates = _target_rows(entry_candidates, target_date)
        paths = _output_paths(target_date)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        pending_orders.to_csv(
            paths["pending_orders"], index=False, encoding="utf-8-sig"
        )
        target_events.to_csv(
            paths["target_events"], index=False, encoding="utf-8-sig"
        )
        target_candidates.to_csv(
            paths["target_entry_candidates"],
            index=False,
            encoding="utf-8-sig",
        )
        summary = {
            "model_tag": MODEL_TAG,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "execution_profile": profile.profile_key,
            "official_live_version": profile.official_version,
            "capital": profile.capital,
            "capital_label": profile.capital_label,
            "target_date": target_date,
            "analysis_start": analysis_start,
            "pending_order_count": int(len(pending_orders)),
            "target_event_count": int(len(target_events)),
            "target_entry_candidate_count": int(len(target_candidates)),
            "pending_orders": pending_orders.to_dict(orient="records"),
            "target_events": target_events.to_dict(orient="records"),
            "target_entry_candidates": target_candidates.to_dict(
                orient="records"
            ),
            "order_api_called_count": 0,
            "outputs": {key: str(path) for key, path in paths.items()},
        }
        safe = _json_safe(summary)
        paths["summary"].write_text(
            json.dumps(safe, ensure_ascii=False, indent=2, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )
        return safe
    finally:
        s517.START_DT = original_start
        s517.END_DT = original_end


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export Stage372 final-bar pending orders and diagnostics."
    )
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--analysis-start", default=stage372_cfg.ANALYSIS_START)
    args = parser.parse_args()
    summary = run_pending_audit(
        target_date=args.target_date,
        analysis_start=args.analysis_start,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
