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

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Reproducible workflows record computational steps and re-run order",
        "https://coderefinery.github.io/reproducible-research/workflow-management/",
    ),
    (
        "SSE trading mechanism: buy orders through auction trading shall be multiples of 100 shares",
        "https://english.sse.com.cn/start/trading/mechanism/",
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


def build_steps() -> list[SuiteStep]:
    return [
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


def summarize_suite(step_results: pl.DataFrame, dry_run: bool) -> dict[str, Any]:
    lot = load_json(LOT_DIR / f"{LOT_PREFIX}_summary.json")
    oos = load_json(OOS_DIR / f"{OOS_PREFIX}_summary.json")
    latest = load_json(LATEST_DIR / f"{LATEST_PREFIX}_summary.json")
    failed_steps = step_results.filter(pl.col("status") == "fail").height if not step_results.is_empty() else 0
    missing_summaries = (
        step_results.filter((pl.col("status") != "dry_run") & (~pl.col("summary_exists"))).height
        if not step_results.is_empty()
        else 0
    )
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
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
        "quality_warn_count": int(oos.get("quality_warn_count") or 0) + int(latest.get("quality_warn_count") or 0),
        "quality_fail_count": int(oos.get("quality_fail_count") or 0) + int(latest.get("quality_fail_count") or 0),
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
        f"- 最新目标执行日：`{summary['latest_target_date']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 可复验研究应固化运行顺序、输入输出和失败点。",
        "- 30万账户必须把100股整手约束放进固定流程，而不是靠人工临时换算。",
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
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    step_results = pl.DataFrame([run_step(step, args.dry_run) for step in build_steps()])
    summary = summarize_suite(step_results, args.dry_run)
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
            "steps": [step.__dict__ for step in build_steps()],
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
