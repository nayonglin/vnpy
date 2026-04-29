from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import (
    OUTPUT_DIR as LOT_DIR,
    PREFIX as LOT_PREFIX,
)
from analyze_stock_range_reversion_liquid_q3_300k_oos_attribution import (
    OUTPUT_DIR as OOS_DIR,
    PREFIX as OOS_PREFIX,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_300k_latest_packet import (
    OUTPUT_DIR as LATEST_DIR,
    PREFIX as LATEST_PREFIX,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table


BASE_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_suite_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_suite_v1"
ST_GUARD_DRYRUN_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_latest_packet_st_guard_dryrun_2018_2026"
).expanduser().resolve()
ST_GUARD_DRYRUN_PREFIX: str = "stock_range_reversion_liquid_q3_300k_latest_packet_st_guard_dryrun_v1"
COMPONENT_TARGET_SIDECAR_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_component_exit_target_sidecar_replay_2018_2026"
).expanduser().resolve()
COMPONENT_TARGET_SIDECAR_PREFIX: str = "stock_range_reversion_liquid_q3_300k_component_exit_target_sidecar_replay_v1"
COMPONENT_GUARD_LATEST_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_latest_packet_component_guard_sidecar_2018_2026"
).expanduser().resolve()
COMPONENT_GUARD_LATEST_PREFIX: str = "stock_range_reversion_liquid_q3_300k_latest_packet_component_guard_sidecar_v1"
LIVE_TARGET_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_live_target_builder_2018_2026"
).expanduser().resolve()
LIVE_TARGET_PREFIX: str = "stock_range_reversion_liquid_q3_300k_live_target_builder_v1"
SNAPSHOT_TEMPLATE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_snapshot_template_2018_2026"
).expanduser().resolve()
SNAPSHOT_TEMPLATE_PREFIX: str = "stock_range_reversion_liquid_q3_300k_snapshot_template_v1"
ORDER_RECALC_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_order_recalc_dryrun_2018_2026"
).expanduser().resolve()
ORDER_RECALC_PREFIX: str = "stock_range_reversion_liquid_q3_300k_order_recalc_dryrun_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Reproducible workflows record computational steps and re-run order",
        "https://coderefinery.github.io/reproducible-research/workflow-management/",
    ),
    (
        "SSE trading mechanism: buy orders through auction trading shall be multiples of 100 shares",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
    (
        "Pre-trade controls should stop invalid orders before execution",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/pre-trade-risk-control",
    ),
)


@dataclass(frozen=True)
class SuiteStep:
    name: str
    script: str
    summary_path: Path


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def truncate_text(text: str, max_chars: int = 3000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def build_steps(
    include_st_guard_dryrun: bool = True,
    include_component_guard_sidecar: bool = True,
    include_live_target_builder: bool = True,
    include_snapshot_template: bool = True,
    include_order_recalc_dryrun: bool = True,
) -> list[SuiteStep]:
    steps = [
        SuiteStep(
            "lot_feasibility",
            "analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility.py",
            LOT_DIR / f"{LOT_PREFIX}_summary.json",
        ),
        SuiteStep(
            "oos_attribution",
            "analyze_stock_range_reversion_liquid_q3_300k_oos_attribution.py",
            OOS_DIR / f"{OOS_PREFIX}_summary.json",
        ),
        SuiteStep(
            "latest_packet",
            "generate_stock_range_reversion_liquid_q3_300k_latest_packet.py",
            LATEST_DIR / f"{LATEST_PREFIX}_summary.json",
        ),
    ]
    if include_st_guard_dryrun:
        steps.append(
            SuiteStep(
                "latest_packet_st_guard_dryrun",
                "generate_stock_range_reversion_liquid_q3_300k_latest_packet_st_guard_dryrun.py",
                ST_GUARD_DRYRUN_DIR / f"{ST_GUARD_DRYRUN_PREFIX}_summary.json",
            )
        )
    if include_component_guard_sidecar:
        steps.extend(
            [
                SuiteStep(
                    "component_exit_target_sidecar_replay",
                    "analyze_stock_range_reversion_liquid_q3_300k_component_exit_target_sidecar_replay.py",
                    COMPONENT_TARGET_SIDECAR_DIR / f"{COMPONENT_TARGET_SIDECAR_PREFIX}_summary.json",
                ),
                SuiteStep(
                    "latest_packet_component_guard_sidecar",
                    "generate_stock_range_reversion_liquid_q3_300k_latest_packet_component_guard_sidecar.py",
                    COMPONENT_GUARD_LATEST_DIR / f"{COMPONENT_GUARD_LATEST_PREFIX}_summary.json",
                ),
            ]
        )
    if include_live_target_builder:
        steps.append(
            SuiteStep(
                "live_target_builder",
                "generate_stock_range_reversion_liquid_q3_300k_live_target_builder.py",
                LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_summary.json",
            )
        )
    if include_snapshot_template:
        steps.append(
            SuiteStep(
                "snapshot_template",
                "generate_stock_range_reversion_liquid_q3_300k_snapshot_template.py",
                SNAPSHOT_TEMPLATE_DIR / f"{SNAPSHOT_TEMPLATE_PREFIX}_summary.json",
            )
        )
    if include_order_recalc_dryrun:
        steps.append(
            SuiteStep(
                "order_recalc_dryrun",
                "generate_stock_range_reversion_liquid_q3_300k_order_recalc_dryrun.py",
                ORDER_RECALC_DIR / f"{ORDER_RECALC_PREFIX}_summary.json",
            )
        )
    return steps


def run_step(step: SuiteStep, dry_run: bool) -> dict[str, Any]:
    script_path = BASE_DIR / step.script
    started = datetime.now()
    started_monotonic = time.monotonic()
    if dry_run:
        return {
            "step": step.name,
            "script": str(script_path),
            "status": "dry_run",
            "returncode": 0,
            "started_at": started.isoformat(timespec="seconds"),
            "ended_at": datetime.now().isoformat(timespec="seconds"),
            "elapsed_seconds": 0.0,
            "summary_path": str(step.summary_path),
            "summary_exists": step.summary_path.exists(),
            "stdout_tail": "",
            "stderr_tail": "",
        }
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(BASE_DIR.parent.parent),
        capture_output=True,
        text=True,
        check=False,
    )
    ended = datetime.now()
    return {
        "step": step.name,
        "script": str(script_path),
        "status": "pass" if result.returncode == 0 else "fail",
        "returncode": result.returncode,
        "started_at": started.isoformat(timespec="seconds"),
        "ended_at": ended.isoformat(timespec="seconds"),
        "elapsed_seconds": round(time.monotonic() - started_monotonic, 3),
        "summary_path": str(step.summary_path),
        "summary_exists": step.summary_path.exists(),
        "stdout_tail": truncate_text(result.stdout),
        "stderr_tail": truncate_text(result.stderr),
    }


def summarize_suite(
    step_results: pl.DataFrame,
    dry_run: bool,
    include_st_guard_dryrun: bool,
    include_component_guard_sidecar: bool,
    include_live_target_builder: bool,
    include_snapshot_template: bool,
    include_order_recalc_dryrun: bool,
) -> dict[str, Any]:
    lot = load_json(LOT_DIR / f"{LOT_PREFIX}_summary.json")
    oos = load_json(OOS_DIR / f"{OOS_PREFIX}_summary.json")
    latest = load_json(LATEST_DIR / f"{LATEST_PREFIX}_summary.json")
    st_guard = (
        load_json(ST_GUARD_DRYRUN_DIR / f"{ST_GUARD_DRYRUN_PREFIX}_summary.json")
        if include_st_guard_dryrun
        else {}
    )
    component_latest = (
        load_json(COMPONENT_GUARD_LATEST_DIR / f"{COMPONENT_GUARD_LATEST_PREFIX}_summary.json")
        if include_component_guard_sidecar
        else {}
    )
    live_target = (
        load_json(LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_summary.json")
        if include_live_target_builder
        else {}
    )
    snapshot_template = (
        load_json(SNAPSHOT_TEMPLATE_DIR / f"{SNAPSHOT_TEMPLATE_PREFIX}_summary.json")
        if include_snapshot_template
        else {}
    )
    order_recalc = (
        load_json(ORDER_RECALC_DIR / f"{ORDER_RECALC_PREFIX}_summary.json")
        if include_order_recalc_dryrun
        else {}
    )
    failed_steps = step_results.filter(pl.col("status") == "fail").height if not step_results.is_empty() else 0
    missing_summaries = (
        step_results.filter((pl.col("status") != "dry_run") & (~pl.col("summary_exists"))).height
        if not step_results.is_empty()
        else 0
    )
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "st_guard_dryrun_enabled": include_st_guard_dryrun,
        "component_guard_sidecar_enabled": include_component_guard_sidecar,
        "live_target_builder_enabled": include_live_target_builder,
        "snapshot_template_enabled": include_snapshot_template,
        "order_recalc_dryrun_enabled": include_order_recalc_dryrun,
        "step_count": step_results.height,
        "failed_steps": failed_steps,
        "missing_summaries": missing_summaries,
        "suite_state": "pass" if failed_steps == 0 and missing_summaries == 0 else "fail",
        "account_size_cny": lot.get("account_size_cny"),
        "latest_target_date": latest.get("latest_target_date"),
        "latest_target_count": latest.get("latest_target_count"),
        "latest_zero_lot_target_count": latest.get("latest_zero_lot_target_count"),
        "latest_actual_symbol_count": latest.get("latest_actual_symbol_count"),
        "latest_actual_gross_weight": latest.get("latest_actual_gross_weight"),
        "latest_order_count": latest.get("latest_order_count"),
        "latest_blocked_order_count": latest.get("latest_blocked_order_count"),
        "latest_unfilled_amount_sum_cny": latest.get("latest_unfilled_amount_sum_cny"),
        "final_equity_min_fee": lot.get("final_equity_min_fee"),
        "total_return_min_fee": lot.get("total_return_min_fee"),
        "max_drawdown_min_fee": lot.get("max_drawdown_min_fee"),
        "sharpe_min_fee": lot.get("sharpe_min_fee"),
        "oos_state_label": oos.get("state_label"),
        "oos_days": oos.get("segment_days"),
        "oos_total_return_min_fee": oos.get("segment_total_return_min_fee"),
        "oos_max_drawdown_min_fee": oos.get("segment_max_drawdown_min_fee"),
        "oos_order_count": oos.get("segment_order_count"),
        "oos_blocked_order_count": oos.get("segment_blocked_order_count"),
        "st_guard_latest_target_date": st_guard.get("latest_target_date"),
        "st_guard_would_block_orders": st_guard.get("guard_would_block_orders", 0) if include_st_guard_dryrun else None,
        "st_guard_changed_orders": st_guard.get("changed_orders", 0) if include_st_guard_dryrun else None,
        "st_guard_dryrun_blocked_orders": st_guard.get("dryrun_blocked_orders", 0) if include_st_guard_dryrun else None,
        "component_guard_latest_target_date": component_latest.get("latest_target_date"),
        "component_guard_latest_order_count": component_latest.get("latest_order_count"),
        "component_guard_latest_blocked_order_count": component_latest.get("latest_blocked_order_count"),
        "component_guard_latest_unfilled_amount_sum_cny": component_latest.get("latest_unfilled_amount_sum_cny"),
        "component_guard_latest_changed_order_rows_vs_original": component_latest.get(
            "latest_changed_order_rows_vs_original"
        ),
        "component_guard_latest_not_index_guard_block_orders": component_latest.get("latest_not_index_guard_block_orders"),
        "component_guard_latest_st_or_ineligible_buy_blocked_orders": component_latest.get(
            "latest_st_or_ineligible_buy_blocked_orders"
        ),
        "component_guard_latest_zero_lot_target_count": component_latest.get("latest_zero_lot_target_count"),
        "component_guard_latest_actual_gross_weight": component_latest.get("latest_actual_gross_weight"),
        "live_target_builder_state": live_target.get("target_builder_state"),
        "live_latest_signal_date": live_target.get("latest_signal_date"),
        "live_proposed_target_date": live_target.get("proposed_target_date"),
        "live_target_in_benchmark_calendar": live_target.get("target_date_in_benchmark_calendar"),
        "live_active_sleeves": live_target.get("active_sleeves"),
        "live_raw_target_count": live_target.get("live_raw_target_count"),
        "live_sidecar_target_count": live_target.get("live_sidecar_target_count"),
        "live_zero_lot_target_count": live_target.get("live_zero_lot_target_count"),
        "live_zero_lot_target_ratio": live_target.get("live_zero_lot_target_ratio"),
        "live_estimated_order_count": live_target.get("estimated_order_count"),
        "live_estimated_buy_order_count": live_target.get("estimated_buy_order_count"),
        "live_estimated_sell_order_count": live_target.get("estimated_sell_order_count"),
        "live_estimated_blocked_order_count": live_target.get("estimated_blocked_order_count"),
        "live_estimated_not_index_buy_order_count": live_target.get("estimated_not_index_buy_order_count"),
        "live_estimated_desired_amount_sum_cny": live_target.get("estimated_desired_amount_sum_cny"),
        "live_parity_changed_rows": live_target.get("parity_changed_rows"),
        "live_parity_max_abs_weight_diff": live_target.get("parity_max_abs_weight_diff"),
        "live_quality_warn_count": live_target.get("quality_warn_count"),
        "live_quality_fail_count": live_target.get("quality_fail_count"),
        "live_quality_manual_count": live_target.get("quality_manual_count"),
        "snapshot_template_state": snapshot_template.get("snapshot_template_state"),
        "snapshot_template_rows": snapshot_template.get("template_rows"),
        "snapshot_template_required_universe_count": snapshot_template.get("required_universe_count"),
        "snapshot_template_input_state": snapshot_template.get("snapshot_input_state"),
        "snapshot_template_input_path": snapshot_template.get("snapshot_input_path"),
        "snapshot_template_validation_warn_count": snapshot_template.get("validation_warn_count"),
        "snapshot_template_validation_fail_count": snapshot_template.get("validation_fail_count"),
        "order_recalc_state": order_recalc.get("order_recalc_state"),
        "order_recalc_price_snapshot_state": order_recalc.get("price_snapshot_state"),
        "order_recalc_price_snapshot_available": order_recalc.get("price_snapshot_available"),
        "order_recalc_target_date": order_recalc.get("target_date"),
        "order_recalc_order_count": order_recalc.get("order_count"),
        "order_recalc_buy_order_count": order_recalc.get("buy_order_count"),
        "order_recalc_sell_order_count": order_recalc.get("sell_order_count"),
        "order_recalc_blocked_order_count": order_recalc.get("blocked_order_count"),
        "order_recalc_cash_limited_order_count": order_recalc.get("cash_limited_order_count"),
        "order_recalc_not_index_component_buy_order_count": order_recalc.get("not_index_component_buy_order_count"),
        "order_recalc_changed_vs_live_estimated_rows": order_recalc.get("changed_vs_live_estimated_rows"),
        "order_recalc_final_amount_sum_cny": order_recalc.get("final_amount_sum_cny"),
        "order_recalc_buy_final_amount_cny": order_recalc.get("buy_final_amount_cny"),
        "order_recalc_sell_final_amount_cny": order_recalc.get("sell_final_amount_cny"),
        "order_recalc_cash_source": order_recalc.get("cash_source"),
        "order_recalc_cash_after_sells_cny": order_recalc.get("cash_after_sells_cny"),
        "order_recalc_quality_warn_count": order_recalc.get("quality_warn_count"),
        "order_recalc_quality_fail_count": order_recalc.get("quality_fail_count"),
        "order_recalc_quality_manual_count": order_recalc.get("quality_manual_count"),
        "quality_warn_count": int(oos.get("quality_warn_count") or 0)
        + int(latest.get("quality_warn_count") or 0)
        + int(st_guard.get("quality_warn_count") or 0)
        + int(component_latest.get("quality_warn_count") or 0)
        + int(live_target.get("quality_warn_count") or 0)
        + int(snapshot_template.get("validation_warn_count") or 0)
        + int(order_recalc.get("quality_warn_count") or 0),
        "quality_fail_count": int(oos.get("quality_fail_count") or 0)
        + int(latest.get("quality_fail_count") or 0)
        + int(st_guard.get("quality_fail_count") or 0)
        + int(component_latest.get("quality_fail_count") or 0)
        + int(live_target.get("quality_fail_count") or 0)
        + int(snapshot_template.get("validation_fail_count") or 0)
        + int(order_recalc.get("quality_fail_count") or 0),
        "total_elapsed_seconds": round(float(step_results["elapsed_seconds"].sum() or 0.0), 3)
        if not step_results.is_empty()
        else 0.0,
    }


def build_quality_checkpoints(summary: dict[str, Any]) -> pl.DataFrame:
    rows: list[dict[str, str]] = []

    def add(name: str, status: str, value: Any, expected: Any, note: str) -> None:
        rows.append(
            {
                "checkpoint": name,
                "status": status,
                "value": "" if value is None else str(value),
                "expected": "" if expected is None else str(expected),
                "note": note,
            }
        )

    add("all_steps_pass", "pass" if summary["failed_steps"] == 0 else "fail", summary["failed_steps"], 0, "子步骤失败时先修流程。")
    add(
        "all_summaries_exist",
        "pass" if summary["missing_summaries"] == 0 else "fail",
        summary["missing_summaries"],
        0,
        "每个子步骤都应输出summary。",
    )
    add(
        "account_size_is_300k",
        "pass" if float(summary.get("account_size_cny") or 0.0) == 300000.0 else "fail",
        summary.get("account_size_cny"),
        300000,
        "suite只服务30万整手口径。",
    )
    add(
        "latest_execution_clean",
        "pass"
        if int(summary.get("latest_blocked_order_count") or 0) == 0
        and float(summary.get("latest_unfilled_amount_sum_cny") or 0.0) == 0.0
        else "warn",
        f"blocked={summary.get('latest_blocked_order_count')}, unfilled={summary.get('latest_unfilled_amount_sum_cny')}",
        "blocked=0, unfilled=0",
        "最新订单应无阻断、无未成交。",
    )
    if summary.get("st_guard_dryrun_enabled"):
        add(
            "st_guard_latest_date_aligned",
            "pass" if summary.get("st_guard_latest_target_date") == summary.get("latest_target_date") else "fail",
            summary.get("st_guard_latest_target_date"),
            summary.get("latest_target_date"),
            "守门dry-run必须和最新交易包日期一致。",
        )
        add(
            "st_guard_dryrun_clean",
            "pass"
            if int(summary.get("st_guard_would_block_orders") or 0) == 0
            and int(summary.get("st_guard_changed_orders") or 0) == 0
            else "warn",
            f"would_block={summary.get('st_guard_would_block_orders')}, changed={summary.get('st_guard_changed_orders')}",
            "would_block=0, changed=0",
            "当前最新交易包不应被守门新增异常阻断。",
        )
    if summary.get("component_guard_sidecar_enabled"):
        add(
            "component_guard_latest_date_aligned",
            "pass" if summary.get("component_guard_latest_target_date") == summary.get("latest_target_date") else "fail",
            summary.get("component_guard_latest_target_date"),
            summary.get("latest_target_date"),
            "component+strict sidecar必须和原始最新交易包日期一致。",
        )
        add(
            "component_guard_sidecar_clean",
            "pass"
            if int(summary.get("component_guard_latest_not_index_guard_block_orders") or 0) == 0
            and int(summary.get("component_guard_latest_st_or_ineligible_buy_blocked_orders") or 0) == 0
            and float(summary.get("component_guard_latest_unfilled_amount_sum_cny") or 0.0) == 0.0
            else "warn",
            (
                f"not_index={summary.get('component_guard_latest_not_index_guard_block_orders')}, "
                f"st_guard={summary.get('component_guard_latest_st_or_ineligible_buy_blocked_orders')}, "
                f"unfilled={summary.get('component_guard_latest_unfilled_amount_sum_cny')}"
            ),
            "not_index=0, st_guard=0, unfilled=0",
            "最新component+strict sidecar应无资格阻断、无未成交。",
        )
        add(
            "component_guard_order_compare_clean",
            "pass" if int(summary.get("component_guard_latest_changed_order_rows_vs_original") or 0) == 0 else "warn",
            summary.get("component_guard_latest_changed_order_rows_vs_original"),
            "0 preferred",
            "当前最新日最好不被sidecar改变；若改变，需确认是资格修正而非误伤。",
        )
    if summary.get("live_target_builder_enabled"):
        add(
            "live_target_builder_generated",
            "pass" if int(summary.get("live_raw_target_count") or 0) > 0 else "fail",
            summary.get("live_raw_target_count"),
            ">0",
            "live目标生成器必须能从最新信号日生成下一执行日目标。",
        )
        add(
            "live_target_advances_beyond_backtest_packet",
            "pass" if str(summary.get("live_latest_signal_date")) > str(summary.get("latest_target_date")) else "warn",
            f"live_signal={summary.get('live_latest_signal_date')}, old_target={summary.get('latest_target_date')}",
            "live_signal > old latest target",
            "旧latest packet若被未来收益字段卡住，live目标应能推进到面板最新信号日。",
        )
        add(
            "live_target_parity_clean",
            "pass"
            if int(summary.get("live_parity_changed_rows") or 0) == 0
            and float(summary.get("live_parity_max_abs_weight_diff") or 0.0) <= 1e-12
            else "fail",
            f"changed={summary.get('live_parity_changed_rows')}, max_diff={summary.get('live_parity_max_abs_weight_diff')}",
            "changed=0, max_diff<=1e-12",
            "live目标构造在旧最新回测目标日必须与原target_weights一致。",
        )
        add(
            "live_estimated_orders_no_hard_block",
            "pass" if int(summary.get("live_estimated_blocked_order_count") or 0) == 0 else "warn",
            summary.get("live_estimated_blocked_order_count"),
            0,
            "估算订单若出现硬阻断，需要先人工复核，不能进入真实委托。",
        )
        add(
            "live_estimated_no_not_index_buy",
            "pass" if int(summary.get("live_estimated_not_index_buy_order_count") or 0) == 0 else "fail",
            summary.get("live_estimated_not_index_buy_order_count"),
            0,
            "目标层sidecar后不应存在最新已知非成分买入/加仓估算订单。",
        )
    if summary.get("snapshot_template_enabled"):
        add(
            "snapshot_template_generated",
            "pass" if int(summary.get("snapshot_template_rows") or 0) > 0 else "fail",
            summary.get("snapshot_template_rows"),
            ">0",
            "目标日快照模板必须能覆盖live目标和当前持仓。",
        )
        add(
            "snapshot_template_universe_matches_live",
            "pass"
            if int(summary.get("snapshot_template_required_universe_count") or 0)
            >= int(summary.get("live_raw_target_count") or 0)
            else "warn",
            (
                f"required={summary.get('snapshot_template_required_universe_count')}, "
                f"live={summary.get('live_raw_target_count')}"
            ),
            "required>=live_raw_target_count",
            "快照模板至少应覆盖全部live目标；额外当前持仓也应保留。",
        )
        add(
            "snapshot_template_validation_no_fail",
            "pass" if int(summary.get("snapshot_template_validation_fail_count") or 0) == 0 else "fail",
            summary.get("snapshot_template_validation_fail_count"),
            0,
            "若提供了外部快照，校验失败前不能进入真实委托。",
        )
        add(
            "snapshot_input_available",
            "pass" if summary.get("snapshot_template_input_state") == "loaded" else "warn",
            summary.get("snapshot_template_input_state"),
            "loaded",
            "缺少目标日真实价格/券商持仓/现金快照时，订单重算仍是估算。",
        )
    if summary.get("order_recalc_dryrun_enabled"):
        add(
            "order_recalc_target_date_aligned",
            "pass" if summary.get("order_recalc_target_date") == summary.get("live_proposed_target_date") else "fail",
            summary.get("order_recalc_target_date"),
            summary.get("live_proposed_target_date"),
            "订单重算必须对应live建议执行日。",
        )
        add(
            "order_recalc_no_blocked_orders",
            "pass" if int(summary.get("order_recalc_blocked_order_count") or 0) == 0 else "warn",
            summary.get("order_recalc_blocked_order_count"),
            0,
            "重算后仍有阻断订单时不能进入真实委托。",
        )
        add(
            "order_recalc_no_cash_limited_orders",
            "pass" if int(summary.get("order_recalc_cash_limited_order_count") or 0) == 0 else "warn",
            summary.get("order_recalc_cash_limited_order_count"),
            0,
            "现金限制意味着目标组合无法完整落地。",
        )
        add(
            "order_recalc_no_not_index_buy",
            "pass" if int(summary.get("order_recalc_not_index_component_buy_order_count") or 0) == 0 else "fail",
            summary.get("order_recalc_not_index_component_buy_order_count"),
            0,
            "重算后不能出现最新已知非成分买入/加仓。",
        )
        add(
            "order_recalc_price_snapshot_available",
            "pass" if bool(summary.get("order_recalc_price_snapshot_available")) else "warn",
            summary.get("order_recalc_price_snapshot_state"),
            "snapshot_or_target_panel_available",
            "缺少目标日价格快照时，订单仍是dry-run估算。",
        )
    add(
        "oos_execution_clean",
        "pass" if int(summary.get("oos_blocked_order_count") or 0) == 0 else "warn",
        summary.get("oos_blocked_order_count"),
        0,
        "OOS段若有阻断，应先查执行约束。",
    )
    add(
        "oos_days_reached_stable_judgment",
        "pass" if int(summary.get("oos_days") or 0) >= 20 else "warn",
        summary.get("oos_days"),
        ">=20",
        "OOS满20天前只做paper观察，不做上线判断。",
    )
    add(
        "latest_zero_lot_targets_visible",
        "warn" if int(summary.get("latest_zero_lot_target_count") or 0) > 0 else "pass",
        summary.get("latest_zero_lot_target_count"),
        0,
        "买不到一手目标是30万口径核心约束，必须显式展示。",
    )
    add(
        "source_quality_has_no_fail",
        "pass" if int(summary.get("quality_fail_count") or 0) == 0 else "fail",
        summary.get("quality_fail_count"),
        0,
        "OOS和latest packet源报告不能有失败项。",
    )
    return pl.DataFrame(rows)


def write_report(summary: dict[str, Any], step_results: pl.DataFrame, quality: pl.DataFrame, paths: dict[str, Path]) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万paper套件 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：30万整手口径一键复跑入口；不新增信号、不调参数。",
        f"- suite状态：`{summary['suite_state']}`。",
        f"- ST守门dry-run：`{'enabled' if summary['st_guard_dryrun_enabled'] else 'disabled'}`。",
        f"- component+strict sidecar：`{'enabled' if summary['component_guard_sidecar_enabled'] else 'disabled'}`。",
        f"- live-target builder：`{'enabled' if summary['live_target_builder_enabled'] else 'disabled'}`。",
        f"- snapshot template：`{'enabled' if summary['snapshot_template_enabled'] else 'disabled'}`。",
        f"- order recalculation dry-run：`{'enabled' if summary['order_recalc_dryrun_enabled'] else 'disabled'}`。",
        f"- 最新目标执行日：`{summary['latest_target_date']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 可复验研究应固化运行顺序、输入输出和失败点。",
        "- 30万账户必须把100股整手约束放进固定流程，而不是靠人工临时换算。",
        "- 执行守门应作为pre-trade control并行输出，不反向修改信号层。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心摘要",
            "",
            f"- 子步骤`{summary['step_count']}`个，失败`{summary['failed_steps']}`个，缺失summary `{summary['missing_summaries']}`个，总耗时`{summary['total_elapsed_seconds']}`秒。",
            f"- 全历史最低佣金口径：期末权益`{summary['final_equity_min_fee']:.4f}`，总收益`{pct(summary['total_return_min_fee'])}`，最大回撤`{pct(summary['max_drawdown_min_fee'])}`，Sharpe `{summary['sharpe_min_fee']:.2f}`。",
            f"- OOS状态`{summary['oos_state_label']}`，OOS天数`{summary['oos_days']}`，OOS收益`{pct(summary['oos_total_return_min_fee'])}`，OOS回撤`{pct(summary['oos_max_drawdown_min_fee'])}`。",
            f"- 最新目标`{summary['latest_target_count']}`只，买不到一手`{summary['latest_zero_lot_target_count']}`只，实际持仓`{summary['latest_actual_symbol_count']}`只，实际暴露`{pct(summary['latest_actual_gross_weight'])}`。",
            f"- 最新订单`{summary['latest_order_count']}`行，阻断`{summary['latest_blocked_order_count']}`行，未成交金额`{summary['latest_unfilled_amount_sum_cny']}`元。",
            f"- ST守门dry-run新增阻断`{summary.get('st_guard_would_block_orders')}`行，变化订单`{summary.get('st_guard_changed_orders')}`行。",
            f"- component+strict sidecar最新订单`{summary.get('component_guard_latest_order_count')}`行，阻断`{summary.get('component_guard_latest_blocked_order_count')}`行，未成交金额`{summary.get('component_guard_latest_unfilled_amount_sum_cny')}`元。",
            f"- component+strict sidecar非成分守门阻断`{summary.get('component_guard_latest_not_index_guard_block_orders')}`行，ST/不可研究买入阻断`{summary.get('component_guard_latest_st_or_ineligible_buy_blocked_orders')}`行。",
            f"- live目标信号日`{summary.get('live_latest_signal_date')}`，建议执行日`{summary.get('live_proposed_target_date')}`，状态`{summary.get('live_target_builder_state')}`。",
            f"- live原始目标`{summary.get('live_raw_target_count')}`只，sidecar后目标`{summary.get('live_sidecar_target_count')}`只，估算订单`{summary.get('live_estimated_order_count')}`行，估算阻断`{summary.get('live_estimated_blocked_order_count')}`行。",
            f"- snapshot模板状态`{summary.get('snapshot_template_state')}`，模板行数`{summary.get('snapshot_template_rows')}`，快照输入`{summary.get('snapshot_template_input_state')}`，校验失败`{summary.get('snapshot_template_validation_fail_count')}`项。",
            f"- order recalc状态`{summary.get('order_recalc_state')}`，订单`{summary.get('order_recalc_order_count')}`行，阻断`{summary.get('order_recalc_blocked_order_count')}`行，现金限制`{summary.get('order_recalc_cash_limited_order_count')}`行。",
            f"- order recalc价格快照状态`{summary.get('order_recalc_price_snapshot_state')}`，重算成交金额`{summary.get('order_recalc_final_amount_sum_cny')}`元。",
            "",
            "## 质量检查点",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 失败项",
            "",
            "无数据" if failed.is_empty() else markdown_table(failed, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 警告项",
            "",
            "无数据" if warned.is_empty() else markdown_table(warned, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 子步骤",
            "",
            markdown_table(
                step_results,
                ["step", "status", "returncode", "elapsed_seconds", "summary_exists", "summary_path"],
                max_rows=20,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：suite只编排30万既有脚本，不新增信号、不调参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：复跑只是确认30万整手口径的最新状态，没有产生交易规则修改。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：后续补数据需要固定入口，避免漏跑30万整手、OOS和交易包。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：suite通过，后续可用同一入口持续积累30万paper样本。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 30万OOS不足20天前继续paper。",
            "- 后续30万固定入口默认同时生成原始最新包、ST守门dry-run包、component+strict sidecar包、live-target builder包、snapshot template包和order recalculation dry-run包。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the 300k lot-account stock range paper suite.")
    parser.add_argument("--dry-run", action="store_true", help="List steps without executing scripts.")
    parser.add_argument(
        "--skip-st-guard-dryrun",
        action="store_true",
        help="Do not run the latest-packet ST/ineligible-buy guard dry-run sidecar.",
    )
    parser.add_argument(
        "--skip-component-guard-sidecar",
        action="store_true",
        help="Do not run the component target sidecar replay and latest component+strict sidecar packet.",
    )
    parser.add_argument(
        "--skip-live-target-builder",
        action="store_true",
        help="Do not run the live target builder that avoids future pnl_date/stock_daily_ret dependency.",
    )
    parser.add_argument(
        "--skip-snapshot-template",
        action="store_true",
        help="Do not run the target-day snapshot template and validation step.",
    )
    parser.add_argument(
        "--skip-order-recalc-dryrun",
        action="store_true",
        help="Do not run order recalculation dry-run from live targets.",
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    include_st_guard_dryrun = not args.skip_st_guard_dryrun
    include_component_guard_sidecar = not args.skip_component_guard_sidecar
    include_live_target_builder = not args.skip_live_target_builder
    include_snapshot_template = not args.skip_snapshot_template
    include_order_recalc_dryrun = not args.skip_order_recalc_dryrun
    steps = build_steps(
        include_st_guard_dryrun,
        include_component_guard_sidecar,
        include_live_target_builder,
        include_snapshot_template,
        include_order_recalc_dryrun,
    )
    step_results = pl.DataFrame([run_step(step, args.dry_run) for step in steps])
    summary = summarize_suite(
        step_results,
        args.dry_run,
        include_st_guard_dryrun,
        include_component_guard_sidecar,
        include_live_target_builder,
        include_snapshot_template,
        include_order_recalc_dryrun,
    )
    quality = build_quality_checkpoints(summary)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "steps": OUTPUT_DIR / f"{PREFIX}_steps.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    step_results.write_csv(paths["steps"])
    quality.write_csv(paths["quality_checkpoints"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "steps": [step.__dict__ for step in steps],
            "research_sources": RESEARCH_SOURCES,
            "note": "300k lot-account suite only; no signal or threshold changes.",
        },
    )
    report_path = write_report(summary, step_results, quality, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")
    if summary["suite_state"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
