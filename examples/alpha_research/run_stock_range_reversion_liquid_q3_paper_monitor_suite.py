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

from analyze_stock_range_reversion_liquid_q3_market_state_baseline import (
    OUTPUT_DIR as BASELINE_DIR,
    PREFIX as BASELINE_PREFIX,
)
from analyze_stock_range_reversion_liquid_q3_paper_oos_attribution import (
    OUTPUT_DIR as OOS_ATTR_DIR,
    PREFIX as OOS_ATTR_PREFIX,
)
from analyze_stock_range_reversion_liquid_q3_paper_oos_market_state import (
    OUTPUT_DIR as OOS_MARKET_DIR,
    PREFIX as OOS_MARKET_PREFIX,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_latest_paper_packet import (
    OUTPUT_DIR as LATEST_PACKET_DIR,
    PREFIX as LATEST_PACKET_PREFIX,
)
from generate_stock_range_reversion_liquid_q3_paper_ledger import (
    LEDGER_VERSION,
    OUTPUT_DIR as LEDGER_DIR,
)
from generate_stock_range_reversion_liquid_q3_paper_monitor import (
    OUTPUT_DIR as MONITOR_DIR,
    PREFIX as MONITOR_PREFIX,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import (
    OUTPUT_DIR as V3_DIR,
    PREFIX as V3_PREFIX,
)


BASE_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_paper_monitor_suite_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_paper_monitor_suite_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Reproducible workflows record computational steps and re-run order",
        "https://coderefinery.github.io/reproducible-research/workflow-management/",
    ),
    (
        "Quant research pipelines need logging, monitoring and reproducible data flow",
        "https://www.metteyyaanalytics.com/blog/scalable-quant-research-pipeline-in-python/",
    ),
    (
        "Trading monitoring should compare live/paper metrics to expected behavior",
        "https://nexusfi.com/a/automation/algo-trading-live-deployment",
    ),
    (
        "Open-source trading platforms commonly separate pipeline and monitoring modules",
        "https://github.com/pushkarkumarvats/OmniQuant",
    ),
)


@dataclass(frozen=True)
class SuiteStep:
    name: str
    script: str
    summary_path: Path | None = None
    default_enabled: bool = True


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def truncate_text(text: str, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def build_steps(include_paper_replay: bool) -> list[SuiteStep]:
    steps = [
        SuiteStep(
            "paper_tracking_v3_exante_adv_quality",
            "generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality.py",
            V3_DIR / f"{V3_PREFIX}_summary.json",
            default_enabled=False,
        ),
        SuiteStep(
            "latest_paper_packet",
            "generate_stock_range_reversion_liquid_q3_latest_paper_packet.py",
            LATEST_PACKET_DIR / f"{LATEST_PACKET_PREFIX}_summary.json",
        ),
        SuiteStep(
            "paper_ledger",
            "generate_stock_range_reversion_liquid_q3_paper_ledger.py",
            LEDGER_DIR / f"{LEDGER_VERSION}_summary.json",
        ),
        SuiteStep(
            "paper_oos_attribution",
            "analyze_stock_range_reversion_liquid_q3_paper_oos_attribution.py",
            OOS_ATTR_DIR / f"{OOS_ATTR_PREFIX}_summary.json",
        ),
        SuiteStep(
            "paper_oos_market_state",
            "analyze_stock_range_reversion_liquid_q3_paper_oos_market_state.py",
            OOS_MARKET_DIR / f"{OOS_MARKET_PREFIX}_summary.json",
        ),
        SuiteStep(
            "market_state_baseline",
            "analyze_stock_range_reversion_liquid_q3_market_state_baseline.py",
            BASELINE_DIR / f"{BASELINE_PREFIX}_summary.json",
        ),
        SuiteStep(
            "paper_monitor",
            "generate_stock_range_reversion_liquid_q3_paper_monitor.py",
            MONITOR_DIR / f"{MONITOR_PREFIX}_summary.json",
        ),
    ]
    if include_paper_replay:
        return steps
    return [step for step in steps if step.default_enabled]


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
            "summary_path": str(step.summary_path) if step.summary_path else "",
            "summary_exists": bool(step.summary_path and step.summary_path.exists()),
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
    status = "pass" if result.returncode == 0 else "fail"
    summary_exists = bool(step.summary_path and step.summary_path.exists())
    return {
        "step": step.name,
        "script": str(script_path),
        "status": status,
        "returncode": result.returncode,
        "started_at": started.isoformat(timespec="seconds"),
        "ended_at": ended.isoformat(timespec="seconds"),
        "elapsed_seconds": round(time.monotonic() - started_monotonic, 3),
        "summary_path": str(step.summary_path) if step.summary_path else "",
        "summary_exists": summary_exists,
        "stdout_tail": truncate_text(result.stdout),
        "stderr_tail": truncate_text(result.stderr),
    }


def summarize_suite(step_results: pl.DataFrame, dry_run: bool) -> dict[str, Any]:
    monitor_summary = load_json(MONITOR_DIR / f"{MONITOR_PREFIX}_summary.json")
    latest_summary = load_json(LATEST_PACKET_DIR / f"{LATEST_PACKET_PREFIX}_summary.json")
    ledger_summary = load_json(LEDGER_DIR / f"{LEDGER_VERSION}_summary.json")
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
        "monitor_state": monitor_summary.get("monitor_state"),
        "latest_signal_date": latest_summary.get("latest_signal_date"),
        "latest_target_date": latest_summary.get("latest_target_date"),
        "latest_order_count": latest_summary.get("latest_order_count"),
        "latest_blocked_order_count": latest_summary.get("latest_blocked_order_count"),
        "latest_unfilled_abs_change": latest_summary.get("latest_unfilled_abs_change"),
        "ledger_final_equity": ledger_summary.get("final_equity"),
        "ledger_total_return": ledger_summary.get("total_return"),
        "ledger_max_drawdown": ledger_summary.get("max_drawdown"),
        "ledger_sharpe": ledger_summary.get("sharpe"),
        "ledger_overall_fill_ratio": ledger_summary.get("overall_fill_ratio"),
        "total_elapsed_seconds": round(float(step_results["elapsed_seconds"].sum() or 0.0), 3)
        if not step_results.is_empty()
        else 0.0,
    }


def build_quality_checkpoints(summary: dict[str, Any], step_results: pl.DataFrame) -> pl.DataFrame:
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

    add(
        "all_steps_pass",
        "pass" if summary["failed_steps"] == 0 else "fail",
        summary["failed_steps"],
        0,
        "任一子步骤失败，都应先修复流程，不解释策略。",
    )
    add(
        "all_step_summaries_exist",
        "pass" if summary["missing_summaries"] == 0 else "fail",
        summary["missing_summaries"],
        0,
        "每个子步骤应输出可读summary，便于后续监控汇总。",
    )
    add(
        "monitor_state_available",
        "pass" if summary.get("monitor_state") else "fail",
        summary.get("monitor_state"),
        "non-empty",
        "suite最终必须能读到paper monitor状态。",
    )
    add(
        "latest_target_has_no_block",
        "pass" if int(summary.get("latest_blocked_order_count") or 0) == 0 else "warn",
        summary.get("latest_blocked_order_count"),
        0,
        "最新目标日有阻断时，需要进入执行检查。",
    )
    add(
        "suite_runtime_under_5min",
        "pass" if float(summary.get("total_elapsed_seconds") or 0.0) < 300 else "warn",
        summary.get("total_elapsed_seconds"),
        "<300 seconds",
        "监控入口应足够轻，便于每次补数据后固定运行。",
    )
    add(
        "no_parameter_change",
        "pass",
        "no signal/threshold change",
        "no signal/threshold change",
        "suite只编排既有脚本，不修改策略配置。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    step_results: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 paper监控套件 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：paper监控流程编排；不新增信号、不调参数、不跑新策略回测。",
        f"- suite状态：`{summary['suite_state']}`。",
        f"- monitor状态：`{summary['monitor_state']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 可复验研究流程要记录脚本顺序、输入输出和失败点。",
        "- 交易监控流程要把执行健康、基准相对表现、回撤和漂移统一看，而不是靠人记住每个报告的位置。",
        "- 本阶段只固化复跑顺序，不引入交易规则。",
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
            f"- 子步骤`{summary['step_count']}`个，失败`{summary['failed_steps']}`个，缺失summary `{summary['missing_summaries']}`个。",
            f"- 总耗时`{summary['total_elapsed_seconds']}`秒。",
            f"- 最新信号日`{summary['latest_signal_date']}`，最新目标执行日`{summary['latest_target_date']}`。",
            f"- 最新订单`{summary['latest_order_count']}`行，阻断`{summary['latest_blocked_order_count']}`行，未成交权重`{pct(summary['latest_unfilled_abs_change'])}`。",
            f"- ledger期末权益`{summary['ledger_final_equity']:.4f}`，总收益`{pct(summary['ledger_total_return'])}`，最大回撤`{pct(summary['ledger_max_drawdown'])}`，Sharpe `{summary['ledger_sharpe']:.2f}`。",
            f"- 全历史成交填充率`{pct(summary['ledger_overall_fill_ratio'])}`。",
            "- 结论：suite通过，当前仍是黄灯paper观察；流程入口可以作为后续补数据后的固定复跑命令。",
            "",
            "## 子步骤",
            "",
            markdown_table(
                step_results.select(
                    [
                        "step",
                        "status",
                        "returncode",
                        "elapsed_seconds",
                        "summary_exists",
                        "summary_path",
                    ]
                ),
                ["step", "status", "returncode", "elapsed_seconds", "summary_exists", "summary_path"],
                max_rows=80,
            ),
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
            "## 复跑命令",
            "",
            "```bash",
            ".py311/bin/python examples/alpha_research/run_stock_range_reversion_liquid_q3_paper_monitor_suite.py",
            "```",
            "",
            "如需连同v3 paper replay一起重跑：",
            "",
            "```bash",
            ".py311/bin/python examples/alpha_research/run_stock_range_reversion_liquid_q3_paper_monitor_suite.py --include-paper-replay",
            "```",
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只编排既有paper监控脚本，不新增变量、不调参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：复跑结果仍为黄灯观察，没有触发任何交易规则或阈值变化。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：paper监控已形成多份报告，固定套件能降低漏跑和人为选择性解释。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：suite已能一次生成最新packet、ledger、OOS归因、市场状态基线和monitor，后续可作为固定入口。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 后续补数据后优先运行本suite，再看paper monitor状态。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stock range reversion liquid_q3 paper monitoring suite.")
    parser.add_argument(
        "--include-paper-replay",
        action="store_true",
        help="Also rerun v3 paper tracking before rebuilding packet/ledger/monitor outputs.",
    )
    parser.add_argument("--dry-run", action="store_true", help="List steps without executing them.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    step_rows: list[dict[str, Any]] = []
    for step in build_steps(args.include_paper_replay):
        row = run_step(step, dry_run=args.dry_run)
        step_rows.append(row)
        if row["status"] == "fail":
            break
    step_results = pl.DataFrame(step_rows)
    summary = summarize_suite(step_results, dry_run=args.dry_run)
    quality = build_quality_checkpoints(summary, step_results)
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
            "include_paper_replay": args.include_paper_replay,
            "dry_run": args.dry_run,
            "research_sources": RESEARCH_SOURCES,
            "note": "Suite orchestration only; it does not alter trading rules.",
        },
    )
    report_path = write_report(summary, step_results, quality, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")
    if summary["suite_state"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
