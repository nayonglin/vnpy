"""Run the frozen Stage001 post-listing market-context coverage audit."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
import sys
from typing import Any, Final

import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import market_context_coverage as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PIT_SCORER_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_ai_pit_scorer_rebuild"
PIT_RETURN_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_xgboost_pit_contract_returns"
OUTPUT_DIR = LINE_DIR / "artifacts/stage001_market_context_coverage"
INPUT_PATHS: Final = {
    "oos_predictions": (
        PIT_SCORER_LINE / "artifacts/stage003_feature_contract_fix/oos_predictions.csv"
    ),
    "fold_audit": PIT_SCORER_LINE / "artifacts/stage003_feature_contract_fix/fold_audit.csv",
    "stage003_manifest": (
        PIT_SCORER_LINE / "artifacts/stage003_feature_contract_fix/artifact_manifest.json"
    ),
    "product_returns": (
        PIT_RETURN_LINE
        / "artifacts/stage001_pit_contract_return_coverage/product_daily_returns.csv.gz"
    ),
    "return_manifest": (
        PIT_RETURN_LINE
        / "artifacts/stage001_pit_contract_return_coverage/artifact_manifest.json"
    ),
    "spec": LINE_DIR / "stages/20260902_1312_stage000_market_context_coverage_preregistration.md",
}
EXPECTED_SHA256: Final = {
    "oos_predictions": "9ec713fd03d9f1131b22b5378a4b8feb9b1065660052cbeb427ab327b51ccce3",
    "fold_audit": "92082f0791376e3b1df337e4b07a4bc7cb1ef0e0fd3c1672141e809e3e773c69",
    "stage003_manifest": "30ab79bd2373d0ad9c9e15ea1b0d013f657cd38b3474299146bb4b4140e40c59",
    "product_returns": "ff31d1bdf3ea3d8a309060243d165e82b5e7a0a8e26d26ba17f4a0ec926056fa",
    "return_manifest": "32ead9d84ff97d6722a4491e389912c40d9c6558f5f4c6afbfdaa11a64c0c9b5",
    "spec": "e9314808a27b6814328d1b3008d0ead68c0f3e5d220f13a22e188efc2d0959d3",
}
SCORE_COLUMNS: Final = [
    "eval_date",
    "product_vt_symbol",
    "pit_logistic_probability",
    "window_id",
]
RETURN_COLUMNS: Final = [
    "product_vt_symbol",
    "selection_date",
    "return_date",
    "selected_contract_vt",
    "product_return",
    "status",
    "fallback_used",
    "cross_contract_price_used",
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


def _read_inputs(
    input_paths: Mapping[str, Path], *, expected_accepted_folds: int
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    scores = pd.read_csv(Path(input_paths["oos_predictions"]), usecols=SCORE_COLUMNS)
    folds = pd.read_csv(
        Path(input_paths["fold_audit"]),
        usecols=["window_id", "accepted", "reject_reason"],
    )
    returns = pd.read_csv(Path(input_paths["product_returns"]), usecols=RETURN_COLUMNS)
    accepted = folds[folds["accepted"].astype(str).str.lower().eq("true")]
    accepted_ids = sorted(accepted["window_id"].astype(str).tolist())
    if len(accepted_ids) != expected_accepted_folds or len(accepted_ids) != len(set(accepted_ids)):
        raise Stage001Error(f"accepted_fold_count:{len(accepted_ids)}")
    return scores, returns, accepted_ids


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
    ranked: pd.DataFrame,
    coverage: pd.DataFrame,
    missing: pd.DataFrame,
    months: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage001Error("stage001_output_already_exists")
    if temp_dir.exists():
        raise Stage001Error("stage001_temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(ranked, temp_dir / "ranked_a_panel.csv")
    _write_csv(coverage, temp_dir / "coverage_by_eval_product.csv")
    _write_csv(missing, temp_dir / "missing_window_cells.csv.gz", gzip=True)
    _write_csv(months, temp_dir / "month_activation_audit.csv")

    year_rows = [
        {"year": int(year), "active_months": int(count)}
        for year, count in summary["active_months_by_year"].items()
    ]
    fold_rows = [
        {"window_id": window_id, "active_months": int(count)}
        for window_id, count in summary["active_months_by_fold"].items()
    ]
    _write_csv(pd.DataFrame(year_rows), temp_dir / "year_activation_audit.csv")
    _write_csv(pd.DataFrame(fold_rows), temp_dir / "fold_activation_audit.csv")
    (temp_dir / "stage001_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = (
        "# Stage001 上市后PIT市场上下文覆盖审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 活跃月：`{summary['active_months']}/{summary['oos_months']}`；"
        f"非活跃月：`{summary['inactive_months']}`。\n"
        f"- 完整Top9/rank10/挑战者行：`{summary['complete_top_rows']}` / "
        f"`{summary['complete_anchor_rows']}` / `{summary['complete_challenger_rows']}`。\n"
        f"- PIT/fallback/跨合约违规：`{summary['pit_violation_rows']}` / "
        f"`{summary['fallback_rows']}` / `{summary['cross_contract_rows']}`。\n"
        "- 本阶段不读取标签列、不训练、不回测、不连接CTP、不调用订单API。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    names = [
        "coverage_by_eval_product.csv",
        "fold_activation_audit.csv",
        "missing_window_cells.csv.gz",
        "month_activation_audit.csv",
        "ranked_a_panel.csv",
        "report.md",
        "stage001_summary.json",
        "year_activation_audit.csv",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in names}
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
    window_days: int = 120,
    top_rank_count: int = 9,
    minimum_complete_challengers: int = 2,
    expected_rows: int = 797,
    expected_months: int = 47,
    expected_min_products: int = 15,
    expected_max_products: int = 18,
    expected_top_rows: int = 423,
    expected_anchor_rows: int = 47,
    expected_challenger_rows: int = 327,
    expected_accepted_folds: int = 8,
    minimum_active_months: int = 36,
    minimum_active_months_by_year: Mapping[int, int] = {
        2022: 6,
        2023: 6,
        2024: 6,
        2025: 6,
    },
    minimum_active_months_per_fold: int = 3,
) -> dict[str, Any]:
    if Path(output_dir).exists():
        raise Stage001Error("stage001_output_already_exists")
    before = _verify_inputs(input_paths, expected_sha256)
    scores, returns, accepted_ids = _read_inputs(
        input_paths, expected_accepted_folds=expected_accepted_folds
    )

    ranked_first = core.assign_anchor_roles(scores, top_rank_count=top_rank_count)
    audit_first = core.audit_context_windows(
        ranked_first,
        returns,
        window_days=window_days,
        top_rank_count=top_rank_count,
        minimum_complete_challengers=minimum_complete_challengers,
    )
    ranked_second = core.assign_anchor_roles(scores, top_rank_count=top_rank_count)
    audit_second = core.audit_context_windows(
        ranked_second,
        returns,
        window_days=window_days,
        top_rank_count=top_rank_count,
        minimum_complete_challengers=minimum_complete_challengers,
    )
    _assert_repeat_exact((ranked_first, *audit_first), (ranked_second, *audit_second))
    coverage, missing, months = audit_first
    summary = core.assess_context_coverage(
        ranked_first,
        coverage,
        missing,
        months,
        returns,
        accepted_window_ids=accepted_ids,
        expected_rows=expected_rows,
        expected_months=expected_months,
        expected_min_products=expected_min_products,
        expected_max_products=expected_max_products,
        top_rank_count=top_rank_count,
        expected_top_rows=expected_top_rows,
        expected_anchor_rows=expected_anchor_rows,
        expected_challenger_rows=expected_challenger_rows,
        window_days=window_days,
        minimum_active_months=minimum_active_months,
        minimum_active_months_by_year=minimum_active_months_by_year,
        minimum_active_months_per_fold=minimum_active_months_per_fold,
        minimum_complete_challengers=minimum_complete_challengers,
    )
    after = _verify_inputs(input_paths, expected_sha256)
    if before != after:
        raise Stage001Error("input_identity_changed_during_run")
    summary.update(
        {
            "line_id": "futures_trend_xgboost_pit_market_context_after_listing",
            "stage": "Stage001",
            "formal_release_id": "m0005_20260901T165450+0800_1961d98ccb2b",
            "evidence_scope": "fixed_current_design_universe_only",
            "window_days": int(window_days),
            "top_rank_count": int(top_rank_count),
            "minimum_complete_challengers": int(minimum_complete_challengers),
            "input_identities_before": before,
            "input_identities_after": after,
            "input_identity_stable": True,
            "repeat_exact": True,
            "score_columns_read": list(SCORE_COLUMNS),
            "return_columns_read": list(RETURN_COLUMNS),
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
        ranked=ranked_first,
        coverage=coverage,
        missing=missing,
        months=months,
        summary=summary,
    )
    return summary


def main() -> None:
    print(json.dumps(run_stage001(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

