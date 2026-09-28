"""Repair cutoff-day daily bars by copying serials only after backtest completion."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Final

import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import full_market_source_rebuild as source_core  # noqa: E402
import stage001_full_market_source_rebuild as stage1  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
LINE_ID: Final = stage1.LINE_ID
SOURCE_START: Final = stage1.SOURCE_START
CUTOFF: Final = stage1.CUTOFF
PASS_DECISION: Final = (
    "stage002_endofday_source_rebuild_coverage_pass_allow_new_model_preregistration_only"
)
FAIL_DECISION: Final = "stage002_endofday_source_rebuild_coverage_fail_close_no_model"
SPEC_PATH = (
    LINE_DIR
    / "stages/20260904_1141_stage002_endofday_source_rebuild_preregistration.md"
)

STAGE1_PATHS = stage1.build_output_paths()
STAGE1_FROZEN_INPUTS: Final = {
    "catalog": STAGE1_PATHS["catalog"],
    "mapping": STAGE1_PATHS["mapping"],
    "archive_inventory": STAGE1_PATHS["archive_inventory"],
    "acquisition_plan": STAGE1_PATHS["acquisition_plan"],
    "prepare_receipt": STAGE1_PATHS["prepare_receipt"],
    "stage001_summary": STAGE1_PATHS["summary"],
    "stage001_monthly": STAGE1_PATHS["monthly_coverage"],
    "stage001_manifest": STAGE1_PATHS["artifact_manifest"],
}
STAGE1_EXPECTED_SHA256: Final = {
    "catalog": "c733e5d85bab4349efb9bd25e2afdd689562718ffd608bff9a4f11964ab13bfc",
    "mapping": "1b9059e42161a71aaacd7d6367cbe4c7cd95eb944a1f463baf360aa038fec34d",
    "archive_inventory": "04ff533525f8da3a25b283f292de7882050dcf5ebd774dbdee5034de57b7df37",
    "acquisition_plan": "21a2e2f5dd6b2c76cbbed39ca43c96c22155dc50f35b02d04471db53657b9a24",
    "prepare_receipt": "971076b5242273b79728a7b94a4fecae5bffd649018793887454e8fa9041587d",
    "stage001_summary": "a9ba8d212aa0f40587fedca7ac50667a8fee23799e8a9e6a320706f246ef67fc",
    "stage001_monthly": "3d864f14a1f858be796cef2e0c1abcc054a082f954a4e143db2a23adf5162bb6",
    "stage001_manifest": "d40046f9ef81aeca66849bfdcfc75093e650b286e478357f42f270859c09fc3b",
}


class Stage002Error(RuntimeError):
    """Raised when the end-of-day repair cannot publish exact evidence."""


def build_output_paths(line_dir: Path = LINE_DIR) -> dict[str, Path]:
    output_dir = Path(line_dir) / "artifacts" / "stage002_endofday_source_rebuild"
    paths = {
        "output_dir": output_dir,
        "incremental_root": output_dir / "raw_incremental",
        "catalog": output_dir / "asof_contract_catalog.csv.gz",
        "mapping": output_dir / "pit_main_contract_mapping.csv.gz",
        "archive_inventory": output_dir / "archive_inventory.csv.gz",
        "acquisition_plan": output_dir / "acquisition_plan.csv",
        "prepare_receipt": output_dir / "prepare_receipt.json",
        "incremental_status": output_dir / "incremental_status.csv",
        "normalised_bars": output_dir / "normalised_daily_bars.csv.gz",
        "metadata": output_dir / "invariant_product_metadata.csv",
        "coverage": output_dir / "coverage_by_eval_product.csv.gz",
        "monthly_coverage": output_dir / "monthly_coverage.csv",
        "rejected": output_dir / "rejected_rows.csv.gz",
        "summary": output_dir / "stage002_summary.json",
        "report": output_dir / "report.md",
        "artifact_manifest": output_dir / "artifact_manifest.json",
    }
    return {
        name: source_core.assert_line_local_output(Path(line_dir), path)
        for name, path in paths.items()
    }


def collect_finished_serials(
    api: Any,
    symbols: list[str],
    *,
    data_length: int,
    source_start: pd.Timestamp,
    cutoff: pd.Timestamp,
    finished_exception: type[BaseException],
) -> dict[str, pd.DataFrame]:
    """Subscribe the entire batch, advance to end-of-day, then freeze each serial."""

    serials = {
        symbol: api.get_kline_serial(
            symbol, duration_seconds=86_400, data_length=data_length
        )
        for symbol in symbols
    }
    try:
        while True:
            api.wait_update()
    except finished_exception:
        pass
    return {
        symbol: stage1.serial_to_raw_frame(
            serial.copy(deep=True),
            tq_symbol=symbol,
            source_start=source_start,
            cutoff=cutoff,
        )
        for symbol, serial in serials.items()
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _incremental_path(root: Path, tq_symbol: str) -> Path:
    exchange, symbol = tq_symbol.split(".", 1)
    return source_core.assert_line_local_output(
        LINE_DIR, Path(root) / exchange / f"{symbol}.csv.gz"
    )


def _verify_stage1_inputs() -> dict[str, dict[str, Any]]:
    return stage1.verify_input_identities(
        STAGE1_FROZEN_INPUTS, STAGE1_EXPECTED_SHA256
    )


def run_prepare(paths: dict[str, Path] | None = None) -> dict[str, Any]:
    output_paths = dict(paths or build_output_paths())
    output_dir = output_paths["output_dir"]
    output_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(output_dir, 0o700)
    output_paths["incremental_root"].mkdir(parents=True, mode=0o700, exist_ok=True)
    if output_paths["prepare_receipt"].exists():
        raise Stage002Error("stage002_prepare_receipt_already_exists")
    before = _verify_stage1_inputs()
    copy_names = ("catalog", "mapping", "archive_inventory", "acquisition_plan")
    for name in copy_names:
        shutil.copyfile(STAGE1_PATHS[name], output_paths[name])
    after = _verify_stage1_inputs()
    if before != after:
        raise Stage002Error("stage001_identity_changed_during_stage002_prepare")
    copied = {
        name: {
            "source_sha256": STAGE1_EXPECTED_SHA256[name],
            "copied_sha256": stage1.sha256_file(output_paths[name]),
            "exact": stage1.sha256_file(output_paths[name]) == STAGE1_EXPECTED_SHA256[name],
        }
        for name in copy_names
    }
    if not all(item["exact"] for item in copied.values()):
        raise Stage002Error("stage002_prepare_copy_identity_mismatch")
    receipt = {
        "line_id": LINE_ID,
        "stage": "Stage002.prepare",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "repair": "subscribe_full_batch_then_advance_to_BacktestFinished_before_copy",
        "source_start": SOURCE_START.date().isoformat(),
        "cutoff": CUTOFF.date().isoformat(),
        "stage001_failure_decision": "stage001_source_rebuild_coverage_fail_close_no_model",
        "stage001_failure_month": "2026-06-30",
        "stage001_failure_root_cause": "cutoff_day_serial_copied_before_backtest_completion",
        "stage001_inputs_before": before,
        "stage001_inputs_after": after,
        "copied_artifacts": copied,
        "label_values_read": False,
        "model_fit_count": 0,
        "strategy_backtest_runs": 0,
        "production_files_written": 0,
    }
    stage1._write_json(output_paths["prepare_receipt"], receipt)
    return receipt


def fetch_endofday_history_batch(
    symbols: list[str],
    *,
    source_start: pd.Timestamp = SOURCE_START,
    cutoff: pd.Timestamp = CUTOFF,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim

    username, password = stage1._credentials()
    data_length = min(
        10_000,
        max(1_000, int((cutoff - source_start).days * 5 / 7) + 500),
    )
    api = TqApi(
        TqSim(),
        backtest=TqBacktest(start_dt=cutoff.date(), end_dt=cutoff.date()),
        auth=TqAuth(username, password),
    )
    try:
        frames = collect_finished_serials(
            api,
            symbols,
            data_length=data_length,
            source_start=source_start,
            cutoff=cutoff,
            finished_exception=BacktestFinished,
        )
        return frames, {}
    except Exception as exc:
        return {}, {symbol: repr(exc) for symbol in symbols}
    finally:
        api.close()


def run_acquire(
    paths: dict[str, Path] | None = None,
    *,
    batch_size: int = 40,
) -> dict[str, Any]:
    output_paths = dict(paths or build_output_paths())
    if batch_size <= 0:
        raise Stage002Error("batch_size_invalid")
    if not output_paths["prepare_receipt"].is_file():
        raise Stage002Error("stage002_prepare_receipt_missing")
    plan = pd.read_csv(output_paths["acquisition_plan"], encoding="utf-8-sig")
    fetch_symbols = sorted(
        plan.loc[plan["action"].eq("fetch_asof_history"), "tq_symbol"].astype(str)
    )
    status = stage1._read_status(output_paths["incremental_status"])
    pending: list[str] = []
    for tq_symbol in fetch_symbols:
        raw_path = _incremental_path(output_paths["incremental_root"], tq_symbol)
        if raw_path.is_file():
            receipt = stage1.inspect_incremental_raw(
                raw_path,
                tq_symbol=tq_symbol,
                source_start=SOURCE_START,
                cutoff=CUTOFF,
            )
            receipt["message"] = "stage002_resume_revalidated"
            status = stage1._upsert_status(status, receipt)
        else:
            pending.append(tq_symbol)
    stage1._write_csv(status, output_paths["incremental_status"])

    total = len(pending)
    for offset in range(0, total, batch_size):
        batch = pending[offset : offset + batch_size]
        frames, errors = fetch_endofday_history_batch(batch)
        for tq_symbol in batch:
            raw_path = _incremental_path(output_paths["incremental_root"], tq_symbol)
            if tq_symbol in frames:
                raw_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                stage1._write_csv(frames[tq_symbol], raw_path)
                receipt = stage1.inspect_incremental_raw(
                    raw_path,
                    tq_symbol=tq_symbol,
                    source_start=SOURCE_START,
                    cutoff=CUTOFF,
                )
            else:
                receipt = {
                    "tq_symbol": tq_symbol,
                    "status": "failed",
                    "rows": 0,
                    "min_date": "",
                    "max_date": "",
                    "path": str(raw_path),
                    "sha256": "",
                    "message": errors.get(tq_symbol, "unknown_stage002_fetch_failure"),
                }
            status = stage1._upsert_status(status, receipt)
        stage1._write_csv(status, output_paths["incremental_status"])
        print(
            f"[stage002 acquire] {min(offset + batch_size, total)}/{total} "
            f"status={status['status'].value_counts().to_dict()}",
            flush=True,
        )

    failed = status[
        status["status"].eq("failed") & status["tq_symbol"].isin(fetch_symbols)
    ]
    if not failed.empty:
        retry_symbols = sorted(failed["tq_symbol"].astype(str).tolist())
        print(
            f"[stage002 acquire] retrying {len(retry_symbols)} failed contracts one by one",
            flush=True,
        )
        for tq_symbol in retry_symbols:
            frames, errors = fetch_endofday_history_batch([tq_symbol])
            raw_path = _incremental_path(output_paths["incremental_root"], tq_symbol)
            if tq_symbol in frames:
                raw_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
                stage1._write_csv(frames[tq_symbol], raw_path)
                receipt = stage1.inspect_incremental_raw(
                    raw_path,
                    tq_symbol=tq_symbol,
                    source_start=SOURCE_START,
                    cutoff=CUTOFF,
                )
            else:
                receipt = {
                    "tq_symbol": tq_symbol,
                    "status": "failed",
                    "rows": 0,
                    "min_date": "",
                    "max_date": "",
                    "path": str(raw_path),
                    "sha256": "",
                    "message": errors.get(tq_symbol, "unknown_stage002_fetch_failure"),
                }
            status = stage1._upsert_status(status, receipt)
            stage1._write_csv(status, output_paths["incremental_status"])

    relevant = status[status["tq_symbol"].isin(fetch_symbols)].copy()
    return {
        "line_id": LINE_ID,
        "stage": "Stage002.acquire",
        "acquisition_semantics": "cutoff_day_end_of_backtest_snapshot",
        "planned_fetch_contracts": len(fetch_symbols),
        "status_counts": {
            str(key): int(value)
            for key, value in relevant["status"].value_counts().sort_index().items()
        },
        "failed_contracts": sorted(
            relevant.loc[relevant["status"].eq("failed"), "tq_symbol"].astype(str).tolist()
        ),
        "label_values_read": False,
        "model_fit_count": 0,
        "strategy_backtest_runs": 0,
        "production_files_written": 0,
    }


def _rewrite_stage002_evidence(
    summary: dict[str, Any], output_paths: dict[str, Path]
) -> dict[str, Any]:
    summary["stage"] = "Stage002"
    summary["decision"] = (
        PASS_DECISION if summary["all_gates_passed"] else FAIL_DECISION
    )
    summary["created_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    summary["parent_stage001"] = {
        "summary_sha256": STAGE1_EXPECTED_SHA256["stage001_summary"],
        "decision": "stage001_source_rebuild_coverage_fail_close_no_model",
        "failed_month": "2026-06-30",
        "minimum_eligible_products": 0,
        "root_cause": "cutoff_day_serial_copied_before_backtest_completion",
    }
    summary["repair"] = {
        "changed_component": "incremental_tqsdk_daily_acquisition_timing_only",
        "old_semantics": "copy_serial_immediately_after_subscription",
        "new_semantics": "subscribe_batch_advance_to_BacktestFinished_then_copy",
        "catalog_changed": False,
        "mapping_changed": False,
        "acquisition_plan_changed": False,
        "coverage_config_changed": False,
    }
    summary["spec_identity"] = {
        "path": str(SPEC_PATH.resolve()),
        "sha256": stage1.sha256_file(SPEC_PATH) if SPEC_PATH.is_file() else "",
    }
    summary["implementation_identities"]["stage002_runner"] = stage1.sha256_file(
        Path(__file__)
    )
    stage1._write_json(output_paths["summary"], summary)
    report = (
        "# Stage002 截止日完整日K数据源修复与覆盖审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        "- 唯一实现修复：整批订阅后推进到 `BacktestFinished`，再复制截止日日K。\n"
        "- 目录、主力映射、采集计划、54个月、资格阈值和覆盖核心均与Stage001完全相同。\n"
        f"- 日线：`{summary['source_diagnostics']['normalised_rows']}`行；未来行="
        f"`{summary['source_diagnostics']['rows_after_cutoff_dropped']}`。\n"
        f"- 覆盖行/合格行/池外挑战行：`{summary['coverage_rows']}/"
        f"{summary['eligible_rows']}/{summary['challenger_rows']}`。\n"
        f"- 每月合格品种最小/中位/最大：`{summary['minimum_eligible_products']}` / "
        f"`{summary['median_eligible_products']:.1f}` / "
        f"`{summary['maximum_eligible_products']}`。\n"
        f"- A-rank10合格月/动作就绪月：`{summary['formal_replacement_eligible_months']}` / "
        f"`{summary['action_ready_months']}`；合格月池外挑战者最小值="
        f"`{summary['minimum_challengers_on_eligible_baseline_month']}`。\n"
        f"- source gates：`{json.dumps(summary['source_gates'], ensure_ascii=False, sort_keys=True)}`。\n"
        f"- coverage gates：`{json.dumps(summary['gates'], ensure_ascii=False, sort_keys=True)}`。\n"
        "- 未读取收益标签，未fit/predict，未运行策略回测，未连接CTP，未调用订单API，"
        "未写生产文件。\n"
        "- 通过仅证明数据资格，仍不证明XGBoost能提高收益或降低回撤。\n"
    )
    output_paths["report"].write_text(report, encoding="utf-8")

    existing_manifest = json.loads(output_paths["artifact_manifest"].read_text(encoding="utf-8"))
    artifact_names = [
        "catalog",
        "mapping",
        "archive_inventory",
        "acquisition_plan",
        "prepare_receipt",
        "incremental_status",
        "normalised_bars",
        "metadata",
        "coverage",
        "monthly_coverage",
        "rejected",
        "summary",
        "report",
    ]
    manifest = {
        "artifacts": {
            name: {
                "path": str(output_paths[name].resolve()),
                "size": int(output_paths[name].stat().st_size),
                "sha256": stage1.sha256_file(output_paths[name]),
            }
            for name in artifact_names
        },
        "source_files": existing_manifest["source_files"],
    }
    stage1._write_json(output_paths["artifact_manifest"], manifest)
    return summary


def run_audit(paths: dict[str, Path] | None = None) -> dict[str, Any]:
    output_paths = dict(paths or build_output_paths())
    summary = stage1.run_audit(output_paths)
    return _rewrite_stage002_evidence(summary, output_paths)


def run_stage002(*, phase: str, authorized: bool, batch_size: int) -> dict[str, Any]:
    stage1.require_authorization(authorized)
    if not SPEC_PATH.is_file():
        raise Stage002Error("stage002_preregistration_missing")
    if phase == "prepare":
        return run_prepare()
    if phase == "acquire":
        return run_acquire(batch_size=batch_size)
    if phase == "audit":
        return run_audit()
    if phase == "all":
        return {
            "prepare": run_prepare(),
            "acquire": run_acquire(batch_size=batch_size),
            "audit": run_audit(),
        }
    raise Stage002Error(f"phase_invalid:{phase}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", choices=("prepare", "acquire", "audit", "all"), default="all"
    )
    parser.add_argument("--batch-size", type=int, default=40)
    parser.add_argument("--authorized-data-rebuild", action="store_true")
    args = parser.parse_args()
    result = run_stage002(
        phase=args.phase,
        authorized=args.authorized_data_rebuild,
        batch_size=args.batch_size,
    )
    print(json.dumps(_json_safe(result), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
