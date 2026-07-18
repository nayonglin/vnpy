from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650  # noqa: E402
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653  # noqa: E402
import analyze_qmt_roll_stage658_stage653_2026_ytd_shadow as s658  # noqa: E402
from qmt_roll_official_execution_profile import ExecutionStrategyMode  # noqa: E402
import qmt_roll_official_stage372_shadow_config as stage372_cfg  # noqa: E402
import qmt_roll_official_live_config as current_live_cfg  # noqa: E402
from qmt_roll_official_live_config import (  # noqa: E402
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_BASE_PROFILE_NAME,
    OFFICIAL_LIVE_FAMILY_VERSION,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_STAGE659_MODEL_TAG,
    OFFICIAL_LIVE_STAGE659_PREFIX,
    OFFICIAL_LIVE_STRATEGY_OVERRIDES,
    OFFICIAL_LIVE_VERSION,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path(
    os.environ.get(
        "OFFICIAL_LIVE_SIGNAL_INPUT_DIR",
        os.environ.get(
            "OFFICIAL_LIVE_OUTPUT_DIR",
            PROJECT_DIR / "backtest_outputs",
        ),
    )
).expanduser().resolve(strict=False)

MODEL_TAG = OFFICIAL_LIVE_STAGE659_MODEL_TAG
OUTPUT_PREFIX = OFFICIAL_LIVE_STAGE659_PREFIX
LINE_ID = "futures_trend_drawdown30_preserve_return"

CURRENT_VARIANT = OFFICIAL_LIVE_PROFILE_NAME
BASELINE_VARIANT = s653.BASELINE_VARIANT
SELECTED_VARIANTS = (BASELINE_VARIANT, CURRENT_VARIANT)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CURRENT_POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_current_positions_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
SIGNAL_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_plan_{MODEL_TAG}.csv"
EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_days_{MODEL_TAG}.csv"
FORCED_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
FORCED_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

DEFAULT_AI_ELIGIBILITY_PATH = OFFICIAL_LIVE_AI_ELIGIBILITY_PATH


def _configure_output_paths() -> None:
    global SUMMARY_PATH, COST_PATH, DAILY_PATH, POSITIONS_PATH
    global PRODUCT_MARGIN_PATH, MONTHLY_PATH, CURRENT_POSITIONS_PATH
    global TRADE_USAGE_PATH, SIGNAL_PLAN_PATH, EVENT_PATH
    global FORCED_EVENTS_PATH, FORCED_SUMMARY_PATH, DECISION_PATH, REPORT_PATH

    SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
    DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
    POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
    PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
    MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
    CURRENT_POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_current_positions_{MODEL_TAG}.csv"
    TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
    SIGNAL_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_plan_{MODEL_TAG}.csv"
    EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_days_{MODEL_TAG}.csv"
    FORCED_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
    FORCED_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_summary_{MODEL_TAG}.csv"
    DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _configure_execution_profile(value: str) -> dict[str, Any]:
    global MODEL_TAG, OUTPUT_PREFIX, CURRENT_VARIANT
    global OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_BASE_PROFILE_NAME
    global OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_STRATEGY_OVERRIDES
    global OFFICIAL_LIVE_VERSION, DEFAULT_AI_ELIGIBILITY_PATH
    global OFFICIAL_LIVE_FAMILY_VERSION

    if value == ExecutionStrategyMode.STAGE372_20W.value:
        MODEL_TAG = stage372_cfg.MODEL_TAG
        OUTPUT_PREFIX = stage372_cfg.OUTPUT_PREFIX
        CURRENT_VARIANT = stage372_cfg.PROFILE_NAME
        OFFICIAL_LIVE_ALIAS = stage372_cfg.OFFICIAL_ALIAS
        OFFICIAL_LIVE_BASE_PROFILE_NAME = stage372_cfg.BASE_PROFILE_NAME
        OFFICIAL_LIVE_PROFILE_NAME = stage372_cfg.PROFILE_NAME
        OFFICIAL_LIVE_STRATEGY_OVERRIDES = dict(stage372_cfg.STRATEGY_OVERRIDES)
        OFFICIAL_LIVE_VERSION = stage372_cfg.OFFICIAL_VERSION
        OFFICIAL_LIVE_FAMILY_VERSION = "stage526_stage372_recovery_sleeve"
        DEFAULT_AI_ELIGIBILITY_PATH = stage372_cfg.AI_ELIGIBILITY_PATH
    elif value == ExecutionStrategyMode.C9_15W_HISTORICAL.value:
        MODEL_TAG = current_live_cfg.OFFICIAL_LIVE_STAGE659_MODEL_TAG
        OUTPUT_PREFIX = current_live_cfg.OFFICIAL_LIVE_STAGE659_PREFIX
        CURRENT_VARIANT = current_live_cfg.OFFICIAL_LIVE_PROFILE_NAME
        OFFICIAL_LIVE_ALIAS = current_live_cfg.OFFICIAL_LIVE_ALIAS
        OFFICIAL_LIVE_BASE_PROFILE_NAME = (
            current_live_cfg.OFFICIAL_LIVE_BASE_PROFILE_NAME
        )
        OFFICIAL_LIVE_PROFILE_NAME = current_live_cfg.OFFICIAL_LIVE_PROFILE_NAME
        OFFICIAL_LIVE_STRATEGY_OVERRIDES = (
            current_live_cfg.OFFICIAL_LIVE_STRATEGY_OVERRIDES
        )
        OFFICIAL_LIVE_VERSION = current_live_cfg.OFFICIAL_LIVE_VERSION
        OFFICIAL_LIVE_FAMILY_VERSION = (
            current_live_cfg.OFFICIAL_LIVE_FAMILY_VERSION
        )
        DEFAULT_AI_ELIGIBILITY_PATH = (
            current_live_cfg.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
        )
    else:
        raise ValueError(f"execution_profile_unknown:{value}")
    _configure_output_paths()
    return {
        "execution_profile": value,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "capital": (
            stage372_cfg.CAPITAL
            if value == ExecutionStrategyMode.STAGE372_20W.value
            else 150_000.0
        ),
        "capital_label": (
            stage372_cfg.CAPITAL_LABEL
            if value == ExecutionStrategyMode.STAGE372_20W.value
            else "15w"
        ),
        "model_tag": MODEL_TAG,
        "output_prefix": OUTPUT_PREFIX,
    }


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _ai_pool_audit(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    frame = pd.read_csv(path, encoding="utf-8-sig")
    strategy = "ai_top8_plus_fu_satellite_post_signal_entry_filter"
    if "strategy" in frame.columns:
        frame = frame[frame["strategy"].astype(str).eq(strategy)].copy()
    if frame.empty:
        return {"path": str(path), "exists": True, "rows": 0}
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.normalize()
    latest_date = frame["eval_date"].max()
    latest = frame[frame["eval_date"].eq(latest_date)].sort_values(["score_rank", "product_vt_symbol"])
    return {
        "path": str(path),
        "exists": True,
        "rows": int(len(frame)),
        "min_eval_date": frame["eval_date"].min().date().isoformat(),
        "max_eval_date": latest_date.date().isoformat(),
        "unique_eval_dates": int(frame["eval_date"].nunique()),
        "latest_products": latest["product_vt_symbol"].astype(str).tolist(),
    }


def _run_variant_dynamic(
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
    analysis_start: datetime,
    analysis_end: datetime,
    ai_eligibility_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_start = s653.s517.START_DT
    original_end = s653.s517.END_DT
    try:
        s653.s517.START_DT = analysis_start
        s653.s517.END_DT = analysis_end
        overrides = {
            **spec.overrides,
            "ai_product_pool_eligibility_path": str(ai_eligibility_path),
        }
        return s653._run_variant(replace(spec, overrides=overrides), metadata)
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end


def _official_live_spec(identity_map: str) -> s653.ForcedVariant:
    base_spec: s653.ForcedVariant | None = None
    for spec in s653._variants(identity_map):
        if spec.capital.variant == OFFICIAL_LIVE_BASE_PROFILE_NAME:
            base_spec = spec
            break
    if base_spec is None:
        raise ValueError(f"official live base profile not found: {OFFICIAL_LIVE_BASE_PROFILE_NAME}")

    capital = replace(
        base_spec.capital,
        variant=OFFICIAL_LIVE_PROFILE_NAME,
        label=f"20w {OFFICIAL_LIVE_ALIAS} recovery sleeve",
        note=(
            "Stage372 official live: force95->80 base plus one-lot recovery sleeve only for clean "
            "long_case1a/short_case1a structure recovery at the 0.1 risk floor."
        ),
    )
    overrides = {**base_spec.overrides, **OFFICIAL_LIVE_STRATEGY_OVERRIDES}
    return replace(base_spec, capital=capital, overrides=overrides, profile="forced_margin_95_to_80_recovery_sleeve")


def _selected_specs(identity_map: str) -> list[s653.ForcedVariant]:
    baseline_spec: s653.ForcedVariant | None = None
    for spec in s653._variants(identity_map):
        if spec.capital.variant == BASELINE_VARIANT:
            baseline_spec = spec
            break
    if baseline_spec is None:
        raise ValueError(f"baseline profile not found: {BASELINE_VARIANT}")
    return [baseline_spec, _official_live_spec(identity_map)]


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    monthly: pd.DataFrame,
    current_positions: pd.DataFrame,
    events: pd.DataFrame,
    forced_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage659 当前官方实盘 2026 年初至今最新 AI 池影子盘",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 统计区间：`{decision['analysis_start']}` 至 `{decision['analysis_end']}`。",
        "- 性质：只读影子盘绩效；不连接 CTP，不读取账户，不调用下单。",
        f"- AI 池最新 eval_date：`{decision['ai_pool_audit'].get('max_eval_date', '')}`。",
        f"- AI 池最新品种：`{', '.join(decision['ai_pool_audit'].get('latest_products', []))}`。",
        f"- 当前官方策略体：`{CURRENT_VARIANT}`。",
        "- 对照：`stage526_200k_allin_r080_pc25_maxpos4`。",
        "",
        "## 核心结果",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "end_equity",
                    "total_return_pct",
                    "cagr_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "forced_margin_deleverage_count",
                    "forced_margin_deleverage_closed_volume",
                    "deployable_pass",
                ]
            ]
        ),
        "",
        "## 月度结果",
        "",
        _md_table(
            monthly[
                [
                    "variant",
                    "month",
                    "start_equity",
                    "end_equity",
                    "return_pct",
                    "max_dd_pct",
                    "max_broker10_margin_to_equity_pct",
                    "trade_count",
                    "slippage",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 当前持仓快照",
        "",
        _md_table(current_positions, max_rows=80),
        "",
        "## 强制减仓事件",
        "",
        _md_table(forced_summary),
        "",
        "## 关键风险日",
        "",
        _md_table(events, max_rows=30),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "variant",
                    "cost_multiplier",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "deployable_pass",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`。",
        "- 这是最新 AI 池影子盘口径，不等同于全周期固定池结果。",
        "- 真实执行仍需 fresh read-only、dry-run、1手测试单和 TCA 闸门。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _empty_signal_plan() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "shadow_session_id",
            "trade_id",
            "vt_symbol",
            "direction",
            "offset",
            "volume",
            "theoretical_price",
            "real_t1_open_proxy_price",
            "day_session_open_proxy_price",
            "proxy_quality",
            "exit_reason",
        ]
    )


def _signal_plan_from_usage(usage: pd.DataFrame, target_date: datetime) -> pd.DataFrame:
    if usage.empty:
        return _empty_signal_plan()
    frame = usage[usage["variant"].astype(str).eq(CURRENT_VARIANT)].copy()
    if frame.empty or "signal_date" not in frame.columns:
        return _empty_signal_plan()
    frame["signal_date"] = pd.to_datetime(frame["signal_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    target = target_date.date().isoformat()
    frame = frame[frame["signal_date"].eq(target)].copy()
    if frame.empty:
        return _empty_signal_plan()
    frame["shadow_session_id"] = frame["trade_id"].map(lambda value: f"STAGE372LIVE-{target.replace('-', '')}-{value}")
    frame["volume"] = pd.to_numeric(frame.get("order_volume", 0.0), errors="coerce").fillna(0.0)
    frame["theoretical_price"] = pd.to_numeric(frame.get("order_price", 0.0), errors="coerce").fillna(0.0)
    frame["real_t1_open_proxy_price"] = ""
    frame["day_session_open_proxy_price"] = ""
    frame["proxy_quality"] = frame.get("price_source", "requires_next_trading_session_minute_or_qmt_bar")
    frame["exit_reason"] = frame.get("price_source", "")
    columns = list(_empty_signal_plan().columns)
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    return frame.loc[:, columns].sort_values(["vt_symbol", "trade_id"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run current official live 20w YTD shadow with latest monthly AI pool.")
    parser.add_argument(
        "--execution-profile",
        choices=[item.value for item in ExecutionStrategyMode],
        default=ExecutionStrategyMode.STAGE372_20W.value,
    )
    parser.add_argument("--analysis-start", default="")
    parser.add_argument("--target-date", default="2026-06-04")
    parser.add_argument("--ai-eligibility-path", default="")
    args = parser.parse_args()

    identity = _configure_execution_profile(args.execution_profile)
    if args.execution_profile == ExecutionStrategyMode.C9_15W_HISTORICAL.value:
        import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901  # noqa: WPS433

        original_argv = list(sys.argv)
        try:
            filtered = [sys.argv[0]]
            skip_next = False
            for item in sys.argv[1:]:
                if skip_next:
                    skip_next = False
                    continue
                if item == "--execution-profile":
                    skip_next = True
                    continue
                filtered.append(item)
            sys.argv = filtered
            s901.main()
        finally:
            sys.argv = original_argv
        return

    analysis_start_text = str(args.analysis_start).strip() or stage372_cfg.ANALYSIS_START
    analysis_start = datetime.strptime(analysis_start_text, "%Y-%m-%d")
    analysis_end = datetime.strptime(str(args.target_date), "%Y-%m-%d")
    ai_path_text = str(args.ai_eligibility_path).strip() or str(
        DEFAULT_AI_ELIGIBILITY_PATH
    )
    ai_eligibility_path = Path(ai_path_text).expanduser().resolve()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    metadata = s513._metadata()
    identity_map = s653.s519._product_identity_cluster_map(metadata)
    specs = _selected_specs(identity_map)
    spec_map = {spec.capital.variant: spec for spec in specs}

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    product_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    forced_event_frames: list[pd.DataFrame] = []

    for spec in specs:
        print(f"[stage659] running {spec.capital.variant}", flush=True)
        daily, positions, usage, forced_events = _run_variant_dynamic(
            spec, metadata, analysis_start, analysis_end, ai_eligibility_path
        )
        daily["account_capital"] = spec.capital.account_capital
        daily["c3_capital"] = spec.capital.c3_capital
        daily["profile"] = spec.profile
        positions["account_capital"] = spec.capital.account_capital
        positions["c3_capital"] = spec.capital.c3_capital
        c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
        combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
        combined["profile"] = spec.profile
        for column in [
            "forced_margin_deleverage_count",
            "forced_margin_deleverage_closed_volume",
            "forced_margin_deleverage_ratio",
            "forced_margin_deleverage_max_observed_ratio",
        ]:
            combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
        daily_frames.append(combined)
        position_frames.append(positions)
        product_frames.append(product_margin)
        if not usage.empty:
            usage_frames.append(usage)
        if not forced_events.empty:
            forced_event_frames.append(forced_events)

    combo_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False)
    product_margin_all = pd.concat(product_frames, ignore_index=True, sort=False)
    usage_all = pd.concat(usage_frames, ignore_index=True, sort=False) if usage_frames else pd.DataFrame()
    forced_events_all = (
        pd.concat(forced_event_frames, ignore_index=True, sort=False) if forced_event_frames else pd.DataFrame()
    )
    forced_summary = s653._forced_summary(specs, forced_events_all)

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = spec_map[variant]
        for cost_multiplier in s653.COST_MULTIPLIERS:
            row = s653._metrics_with_profile(frame, spec, cost_multiplier)
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    summary, cost = s653._add_retention(summary, cost)
    monthly = s658._monthly_returns(combo_daily)
    events = s650._event_days(combo_daily, product_margin_all)
    latest_date = pd.to_datetime(combo_daily["date"]).max().normalize()
    current_positions = s658._current_positions(positions_all, metadata, latest_date)
    signal_plan = _signal_plan_from_usage(usage_all, analysis_end)

    current_row = summary[summary["variant"].eq(CURRENT_VARIANT)].to_dict(orient="records")
    baseline_row = summary[summary["variant"].eq(BASELINE_VARIANT)].to_dict(orient="records")
    decision = {
        "stage": "Stage373",
        "script_stage": "Stage659",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "execution_profile": identity["execution_profile"],
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "latest_available_data_date": latest_date.date().isoformat(),
        "ai_pool_audit": _ai_pool_audit(ai_eligibility_path),
        "current_variant": current_row[0] if current_row else {},
        "baseline_variant": baseline_row[0] if baseline_row else {},
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "capital": identity["capital"],
        "capital_label": identity["capital_label"],
        "decision": "stage372_2026_ytd_latest_ai_shadow_measured_no_order_api",
        "execution_scope": "read-only backtest/shadow performance only; no CTP connection and no order API call",
        "target_signal_count": int(len(signal_plan)),
    }

    combo_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_margin_all.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    current_positions.to_csv(CURRENT_POSITIONS_PATH, index=False, encoding="utf-8-sig")
    usage_all.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    signal_plan.to_csv(SIGNAL_PLAN_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    forced_summary.to_csv(FORCED_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    if not forced_events_all.empty:
        forced_events_all.to_csv(FORCED_EVENTS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, cost, monthly, current_positions, events, forced_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
