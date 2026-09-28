"""Run the frozen Stage001 same-day futures curve coverage audit."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import sqlite3
import sys
from typing import Any, Final

import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import curve_coverage as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
SOURCE_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_xgboost_pit_market_context_after_listing"
OUTPUT_DIR = LINE_DIR / "artifacts/stage001_curve_coverage"
INPUT_PATHS: Final = {
    "ranked_panel": SOURCE_LINE / "artifacts/stage001_market_context_coverage/ranked_a_panel.csv",
    "database": WORKSPACE_ROOT / ".vntrader/database.db",
    "spec": LINE_DIR / "stages/20260902_1355_stage000_curve_account_label_preregistration.md",
}
EXPECTED_SHA256: Final = {
    "ranked_panel": "1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2",
    "database": "7e2633909f73d77c3b0b044199418d7c1ed2989afde480596aefbb18a83b724a",
    "spec": "b07bc7af5b59bb5e366eb9e0c471e5c77956c1599c71cb2b383b8dde0bbcf4a7",
}
PANEL_COLUMNS: Final = [
    "eval_date",
    "product_vt_symbol",
    "pit_logistic_probability",
    "window_id",
    "a_rank",
    "role",
]
DATABASE_COLUMNS: Final = [
    "symbol",
    "exchange",
    "datetime",
    "interval",
    "close_price",
    "open_interest",
    "volume",
]


class Stage001Error(RuntimeError):
    """Raised when the frozen Stage001 runner must fail closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_inputs(
    input_paths: Mapping[str, Path], expected_sha256: Mapping[str, str]
) -> dict[str, dict[str, Any]]:
    if set(input_paths) != set(expected_sha256):
        raise Stage001Error("input_identity_keys_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name in sorted(input_paths):
        path = Path(input_paths[name])
        if not path.is_file():
            raise Stage001Error(f"input_missing:{name}")
        digest = sha256_file(path)
        if digest != str(expected_sha256[name]):
            raise Stage001Error(f"input_sha256_drift:{name}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    return identities


def _read_database(database: Path, eval_dates: pd.DatetimeIndex) -> pd.DataFrame:
    if len(eval_dates) == 0:
        raise Stage001Error("eval_dates_empty")
    placeholders = ",".join("?" for _ in eval_dates)
    query = f"""
        SELECT {", ".join(DATABASE_COLUMNS)}
        FROM dbbardata
        WHERE interval = 'd'
          AND date(datetime) IN ({placeholders})
    """
    uri = f"file:{Path(database).resolve()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only = ON")
        return pd.read_sql_query(
            query,
            connection,
            params=[pd.Timestamp(value).date().isoformat() for value in eval_dates],
        )


def _assert_repeat_exact(first: tuple[pd.DataFrame, ...], second: tuple[pd.DataFrame, ...]) -> None:
    for first_frame, second_frame in zip(first, second, strict=True):
        pd.testing.assert_frame_equal(first_frame, second_frame, check_exact=True)


def _write_csv(frame: pd.DataFrame, path: Path, *, gzip: bool = False) -> None:
    options: dict[str, Any] = {
        "index": False,
        "encoding": "utf-8-sig",
        "date_format": "%Y-%m-%d",
        "float_format": "%.17g",
    }
    if gzip:
        options["compression"] = {"method": "gzip", "compresslevel": 6, "mtime": 0}
    frame.to_csv(path, **options)


def _publish(
    output_dir: Path,
    *,
    snapshots: pd.DataFrame,
    rejected: pd.DataFrame,
    coverage: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage001Error("stage001_output_already_exists")
    if temp_dir.exists():
        raise Stage001Error("stage001_temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(snapshots, temp_dir / "eligible_contract_snapshot.csv.gz", gzip=True)
    _write_csv(rejected, temp_dir / "rejected_contract_rows.csv.gz", gzip=True)
    _write_csv(coverage, temp_dir / "coverage_by_eval_product.csv")
    (temp_dir / "stage001_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = (
        "# Stage001 PIT全曲线覆盖审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 面板覆盖：`{summary['complete_rows']}/{summary['panel_rows']}`；"
        f"合格合约数最小/中位/最大：`{summary['minimum_eligible_contracts']}` / "
        f"`{summary['median_eligible_contracts']:.1f}` / `{summary['maximum_eligible_contracts']}`。\n"
        f"- 快照行：`{summary['curve_snapshot_rows']}`；PIT/同日错配："
        f"`{summary['pit_violation_rows']}` / `{summary['same_day_mismatch_rows']}`。\n"
        f"- 拒绝伪合约/非正活动合约：`{summary['synthetic_contract_rows_rejected']}` / "
        f"`{summary['nonpositive_contract_rows_rejected']}`。\n"
        "- 本阶段未读取未来标签、未训练、未回测、未连接CTP、未调用订单API。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    artifact_names = [
        "coverage_by_eval_product.csv",
        "eligible_contract_snapshot.csv.gz",
        "rejected_contract_rows.csv.gz",
        "report.md",
        "stage001_summary.json",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in artifact_names}
    (temp_dir / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_dir.rename(output_dir)


def run_stage001(
    output_dir: Path = OUTPUT_DIR,
    *,
    input_paths: Mapping[str, Path] = INPUT_PATHS,
    expected_sha256: Mapping[str, str] = EXPECTED_SHA256,
    expected_rows: int = 797,
    expected_months: int = 47,
    expected_products: int = 18,
    minimum_contracts: int = 3,
) -> dict[str, Any]:
    if Path(output_dir).exists():
        raise Stage001Error("stage001_output_already_exists")
    before = _verify_inputs(input_paths, expected_sha256)
    panel = pd.read_csv(Path(input_paths["ranked_panel"]), usecols=PANEL_COLUMNS)
    ranked = core.normalise_ranked_panel(panel)
    eval_dates = pd.DatetimeIndex(sorted(ranked["eval_date"].unique()))
    bars = _read_database(Path(input_paths["database"]), eval_dates)

    snapshots_first, rejected_first = core.build_exact_curve_snapshots(ranked, bars)
    coverage_first = core.audit_curve_coverage(
        ranked, snapshots_first, minimum_contracts=minimum_contracts
    )
    snapshots_second, rejected_second = core.build_exact_curve_snapshots(ranked, bars)
    coverage_second = core.audit_curve_coverage(
        ranked, snapshots_second, minimum_contracts=minimum_contracts
    )
    _assert_repeat_exact(
        (snapshots_first, rejected_first, coverage_first),
        (snapshots_second, rejected_second, coverage_second),
    )
    summary = core.assess_curve_coverage(
        ranked,
        snapshots_first,
        rejected_first,
        coverage_first,
        expected_rows=expected_rows,
        expected_months=expected_months,
        expected_products=expected_products,
        minimum_contracts=minimum_contracts,
    )
    after = _verify_inputs(input_paths, expected_sha256)
    if before != after:
        raise Stage001Error("input_identity_changed_during_run")
    summary.update(
        {
            "line_id": "futures_trend_xgboost_pit_curve_account_labels",
            "stage": "Stage001",
            "formal_release_id": "m0005_20260901T165450+0800_1961d98ccb2b",
            "evidence_scope": "fixed_current_design_universe_only",
            "minimum_contracts": int(minimum_contracts),
            "input_identities_before": before,
            "input_identities_after": after,
            "input_identity_stable": True,
            "repeat_exact": True,
            "panel_columns_read": list(PANEL_COLUMNS),
            "database_columns_read": list(DATABASE_COLUMNS),
            "database_open_mode": "read_only",
            "label_columns_read": [],
            "label_values_read": False,
            "sealed_holdout_files_read": [],
            "trains_model": False,
            "strategy_backtest_runs": 0,
            "ctp_connected": False,
            "order_api_called_count": 0,
        }
    )
    _publish(
        Path(output_dir),
        snapshots=snapshots_first,
        rejected=rejected_first,
        coverage=coverage_first,
        summary=summary,
    )
    return summary


def main() -> None:
    print(json.dumps(run_stage001(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
