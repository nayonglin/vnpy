"""Run the frozen Stage002 market-context feature construction audit."""

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

import market_context_features as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
STAGE001_DIR = LINE_DIR / "artifacts/stage001_market_context_coverage"
RETURN_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_xgboost_pit_contract_returns"
OUTPUT_DIR = LINE_DIR / "artifacts/stage002_market_context_features"
INPUT_PATHS: Final = {
    "ranked_a_panel": STAGE001_DIR / "ranked_a_panel.csv",
    "coverage": STAGE001_DIR / "coverage_by_eval_product.csv",
    "month_audit": STAGE001_DIR / "month_activation_audit.csv",
    "stage001_manifest": STAGE001_DIR / "artifact_manifest.json",
    "product_returns": (
        RETURN_LINE / "artifacts/stage001_pit_contract_return_coverage/product_daily_returns.csv.gz"
    ),
    "return_manifest": (
        RETURN_LINE / "artifacts/stage001_pit_contract_return_coverage/artifact_manifest.json"
    ),
    "spec": LINE_DIR / "stages/20260902_1325_stage002_market_context_feature_preregistration.md",
}
EXPECTED_SHA256: Final = {
    "ranked_a_panel": "1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2",
    "coverage": "54eab60914d94dbf90f64b8cf266263eeaa8d17d29007e0c1849e8a0097f57b7",
    "month_audit": "0f18589174f65ad3014797fcb2fe932480090c104b1667eec8e66b6a37871f93",
    "stage001_manifest": "dd6bae8f310c2d061fe5caed876b43ffa8a1f32060099f441633e4e930ef00b7",
    "product_returns": "ff31d1bdf3ea3d8a309060243d165e82b5e7a0a8e26d26ba17f4a0ec926056fa",
    "return_manifest": "32ead9d84ff97d6722a4491e389912c40d9c6558f5f4c6afbfdaa11a64c0c9b5",
    "spec": "5f31ac2984d98acfc77aa3386ba4187596efe3d57c1bfb1a55fc33af3268924a",
}
RANKED_COLUMNS: Final = [
    "eval_date",
    "product_vt_symbol",
    "window_id",
    "pit_logistic_probability",
    "a_rank",
    "role",
]
COVERAGE_COLUMNS: Final = RANKED_COLUMNS + [
    "window_complete",
    "context_eligible",
]
MONTH_COLUMNS: Final = [
    "eval_date",
    "window_id",
    "window_start",
    "window_end",
    "window_date_count",
    "overlay_active",
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


class Stage002Error(RuntimeError):
    """Raised when the frozen Stage002 runner must fail closed."""


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
        raise Stage002Error("input_identity_keys_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name in sorted(input_paths):
        path = Path(input_paths[name])
        if not path.is_file():
            raise Stage002Error(f"input_missing:{name}")
        digest = sha256_file(path)
        if digest != str(expected_sha256[name]):
            raise Stage002Error(f"input_sha256_drift:{name}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    return identities


def _read_inputs(
    input_paths: Mapping[str, Path], *, expected_fold_count: int
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    ranked = pd.read_csv(Path(input_paths["ranked_a_panel"]), usecols=RANKED_COLUMNS)
    coverage = pd.read_csv(Path(input_paths["coverage"]), usecols=COVERAGE_COLUMNS)
    months = pd.read_csv(Path(input_paths["month_audit"]), usecols=MONTH_COLUMNS)
    returns = pd.read_csv(Path(input_paths["product_returns"]), usecols=RETURN_COLUMNS)
    accepted_ids = sorted(ranked["window_id"].astype(str).unique().tolist())
    if len(accepted_ids) != expected_fold_count:
        raise Stage002Error(f"fold_count:{len(accepted_ids)}")
    return ranked, coverage, months, returns, accepted_ids


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
        date_format="%Y-%m-%d",
        float_format="%.17g",
    )


def _publish(
    output_dir: Path,
    *,
    features: pd.DataFrame,
    month_audit: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage002Error("stage002_output_already_exists")
    if temp_dir.exists():
        raise Stage002Error("stage002_temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(features, temp_dir / "market_context_feature_panel.csv")
    _write_csv(month_audit, temp_dir / "month_feature_audit.csv")
    diagnostic_rows = [
        {
            "feature": feature,
            "challenger_unique_values": summary["challenger_unique_values"][feature],
            "challenger_standard_deviation": summary["challenger_standard_deviations"][feature],
            "folds_with_nonzero": sum(
                summary["nonzero_values_by_fold"][fold][feature] > 0
                for fold in summary["nonzero_values_by_fold"]
            ),
        }
        for feature in core.FEATURE_COLUMNS
    ]
    _write_csv(pd.DataFrame(diagnostic_rows), temp_dir / "feature_diagnostics.csv")
    (temp_dir / "stage002_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = (
        "# Stage002 上市后PIT市场上下文特征审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 特征矩阵：`{summary['feature_rows']}`行 / "
        f"`{summary['feature_months']}`月 / `{summary['feature_count']}`项。\n"
        f"- rank10/挑战者：`{summary['anchor_rows']}` / `{summary['challenger_rows']}`。\n"
        f"- 最少Top9下跌日：`{summary['minimum_downside_days_observed']}`。\n"
        "- 本阶段不读取标签列、不训练、不回测、不连接CTP、不调用订单API。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    names = [
        "feature_diagnostics.csv",
        "market_context_feature_panel.csv",
        "month_feature_audit.csv",
        "report.md",
        "stage002_summary.json",
    ]
    manifest = {name: sha256_file(temp_dir / name) for name in names}
    (temp_dir / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_dir.rename(output_dir)


def run_stage002(
    output_dir: Path = OUTPUT_DIR,
    *,
    input_paths: Mapping[str, Path] = INPUT_PATHS,
    expected_sha256: Mapping[str, str] = EXPECTED_SHA256,
    window_days: int = 120,
    top_rank_count: int = 9,
    minimum_downside_days: int = 20,
    expected_rows: int = 328,
    expected_months: int = 43,
    expected_anchor_rows: int = 43,
    expected_challenger_rows: int = 285,
    expected_min_rows_per_month: int = 6,
    expected_max_rows_per_month: int = 9,
    expected_fold_count: int = 8,
    minimum_unique_challenger_values: int = 10,
) -> dict[str, Any]:
    if Path(output_dir).exists():
        raise Stage002Error("stage002_output_already_exists")
    before = _verify_inputs(input_paths, expected_sha256)
    ranked, coverage, months, returns, accepted_ids = _read_inputs(
        input_paths, expected_fold_count=expected_fold_count
    )
    first = core.build_market_context_features(
        ranked,
        coverage,
        months,
        returns,
        window_days=window_days,
        top_rank_count=top_rank_count,
        minimum_downside_days=minimum_downside_days,
    )
    second = core.build_market_context_features(
        ranked,
        coverage,
        months,
        returns,
        window_days=window_days,
        top_rank_count=top_rank_count,
        minimum_downside_days=minimum_downside_days,
    )
    for first_frame, second_frame in zip(first, second, strict=True):
        pd.testing.assert_frame_equal(first_frame, second_frame, check_exact=True)
    features, month_feature_audit = first
    summary = core.assess_feature_contract(
        features,
        month_feature_audit,
        accepted_window_ids=accepted_ids,
        expected_rows=expected_rows,
        expected_months=expected_months,
        expected_anchor_rows=expected_anchor_rows,
        expected_challenger_rows=expected_challenger_rows,
        expected_min_rows_per_month=expected_min_rows_per_month,
        expected_max_rows_per_month=expected_max_rows_per_month,
        window_days=window_days,
        minimum_downside_days=minimum_downside_days,
        minimum_unique_challenger_values=minimum_unique_challenger_values,
    )
    after = _verify_inputs(input_paths, expected_sha256)
    if before != after:
        raise Stage002Error("input_identity_changed_during_run")
    summary.update(
        {
            "line_id": "futures_trend_xgboost_pit_market_context_after_listing",
            "stage": "Stage002",
            "formal_release_id": "m0005_20260901T165450+0800_1961d98ccb2b",
            "evidence_scope": "fixed_current_design_universe_only",
            "window_days": int(window_days),
            "top_rank_count": int(top_rank_count),
            "input_identities_before": before,
            "input_identities_after": after,
            "input_identity_stable": True,
            "repeat_exact": True,
            "ranked_columns_read": list(RANKED_COLUMNS),
            "coverage_columns_read": list(COVERAGE_COLUMNS),
            "month_columns_read": list(MONTH_COLUMNS),
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
        features=features,
        month_audit=month_feature_audit,
        summary=summary,
    )
    return summary


def main() -> None:
    print(json.dumps(run_stage002(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

