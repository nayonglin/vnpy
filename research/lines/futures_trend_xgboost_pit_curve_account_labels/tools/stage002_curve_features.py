"""Run the frozen Stage002 label-free futures curve feature audit."""

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

import curve_features as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
SOURCE_LINE = WORKSPACE_ROOT / "research/lines/futures_trend_xgboost_pit_market_context_after_listing"
STAGE001_DIR = LINE_DIR / "artifacts/stage001_curve_coverage"
OUTPUT_DIR = LINE_DIR / "artifacts/stage002_curve_features"
INPUT_PATHS: Final = {
    "ranked_panel": SOURCE_LINE / "artifacts/stage001_market_context_coverage/ranked_a_panel.csv",
    "curve_snapshot": STAGE001_DIR / "eligible_contract_snapshot.csv.gz",
    "coverage": STAGE001_DIR / "coverage_by_eval_product.csv",
    "stage001_summary": STAGE001_DIR / "stage001_summary.json",
    "stage001_manifest": STAGE001_DIR / "artifact_manifest.json",
    "spec": LINE_DIR / "stages/20260902_1407_stage002_curve_feature_preregistration.md",
}
EXPECTED_SHA256: Final = {
    "ranked_panel": "1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2",
    "curve_snapshot": "f206370c52bd9589795f34c3c31ffc25b197d3fa02cebb55c2da721b8cb557db",
    "coverage": "b92cf89d816fc56e3a7152ad958bea8e7d6bafae30feb8b81a6f4793388e9fcf",
    "stage001_summary": "34e749e534c0f5250f6de8f80c7cb7cc63c630868f1205bb68f30bafd50bdbbd",
    "stage001_manifest": "02e23076e4564a3c1867b04d8c3f6e9b7973045b688d3ca5da30ed39768b275c",
    "spec": "792506266a10a0e26dbf3c2795103282fb6d04d1576db4f32bbcdd5f7d262a3a",
}
PANEL_COLUMNS: Final = [
    "eval_date",
    "product_vt_symbol",
    "pit_logistic_probability",
    "window_id",
    "a_rank",
    "role",
]
SNAPSHOT_COLUMNS: Final = [
    "eval_date",
    "feature_date",
    "product_vt_symbol",
    "contract_vt_symbol",
    "contract_maturity",
    "close_price",
    "open_interest",
    "volume",
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


def _assert_repeat_exact(first: tuple[pd.DataFrame, ...], second: tuple[pd.DataFrame, ...]) -> None:
    for first_frame, second_frame in zip(first, second, strict=True):
        pd.testing.assert_frame_equal(first_frame, second_frame, check_exact=True)


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
    descriptors: pd.DataFrame,
    features: pd.DataFrame,
    diagnostics: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage002Error("stage002_output_already_exists")
    if temp_dir.exists():
        raise Stage002Error("stage002_temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)
    _write_csv(descriptors, temp_dir / "raw_curve_descriptors.csv")
    _write_csv(features, temp_dir / "candidate_curve_feature_panel.csv")
    _write_csv(diagnostics, temp_dir / "feature_diagnostics.csv")
    (temp_dir / "stage002_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = (
        "# Stage002 PIT全曲线特征审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 原始描述量/候选矩阵：`{summary['descriptor_rows']}` / "
        f"`{summary['candidate_rows']}`；月份：`{summary['months']}`。\n"
        f"- 锚点/挑战者：`{summary['anchor_rows']}` / `{summary['challenger_rows']}`；"
        f"特征：`{summary['feature_count']}`。\n"
        "- 8项特征在标签前冻结；未读取标签、未训练、未回测、未连接CTP。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    names = [
        "candidate_curve_feature_panel.csv",
        "feature_diagnostics.csv",
        "raw_curve_descriptors.csv",
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
    expected_rows: int = 374,
    expected_months: int = 47,
    expected_anchor_rows: int = 47,
    expected_challenger_rows: int = 327,
    expected_folds: int = 8,
    minimum_contracts: int = 3,
    anchor_rank: int = 10,
) -> dict[str, Any]:
    if Path(output_dir).exists():
        raise Stage002Error("stage002_output_already_exists")
    before = _verify_inputs(input_paths, expected_sha256)
    stage001_summary = json.loads(Path(input_paths["stage001_summary"]).read_text(encoding="utf-8"))
    if (
        stage001_summary.get("decision")
        != "stage001_curve_coverage_pass_ready_for_feature_preregistration"
        or stage001_summary.get("all_gates_passed") is not True
    ):
        raise Stage002Error("stage001_not_passed")
    coverage = pd.read_csv(
        Path(input_paths["coverage"]),
        usecols=["eval_date", "product_vt_symbol", "curve_complete"],
    )
    complete = coverage["curve_complete"].astype(str).str.lower().eq("true")
    if not complete.all():
        raise Stage002Error("stage001_coverage_incomplete")
    panel = pd.read_csv(Path(input_paths["ranked_panel"]), usecols=PANEL_COLUMNS)
    snapshots = pd.read_csv(Path(input_paths["curve_snapshot"]), usecols=SNAPSHOT_COLUMNS)

    descriptors_first = core.compute_curve_descriptors(
        snapshots, minimum_contracts=minimum_contracts
    )
    features_first = core.build_candidate_feature_matrix(
        panel, descriptors_first, anchor_rank=anchor_rank
    )
    descriptors_second = core.compute_curve_descriptors(
        snapshots, minimum_contracts=minimum_contracts
    )
    features_second = core.build_candidate_feature_matrix(
        panel, descriptors_second, anchor_rank=anchor_rank
    )
    _assert_repeat_exact(
        (descriptors_first, features_first),
        (descriptors_second, features_second),
    )
    summary, diagnostics = core.assess_curve_features(
        panel,
        descriptors_first,
        features_first,
        expected_rows=expected_rows,
        expected_months=expected_months,
        expected_anchor_rows=expected_anchor_rows,
        expected_challenger_rows=expected_challenger_rows,
        expected_folds=expected_folds,
        anchor_rank=anchor_rank,
    )
    after = _verify_inputs(input_paths, expected_sha256)
    if before != after:
        raise Stage002Error("input_identity_changed_during_run")
    summary.update(
        {
            "line_id": "futures_trend_xgboost_pit_curve_account_labels",
            "stage": "Stage002",
            "formal_release_id": "m0005_20260901T165450+0800_1961d98ccb2b",
            "feature_columns": list(core.MODEL_FEATURES),
            "raw_curve_features": list(core.RAW_CURVE_FEATURES),
            "anchor_rank": int(anchor_rank),
            "minimum_contracts": int(minimum_contracts),
            "input_identities_before": before,
            "input_identities_after": after,
            "input_identity_stable": True,
            "repeat_exact": True,
            "panel_columns_read": list(PANEL_COLUMNS),
            "snapshot_columns_read": list(SNAPSHOT_COLUMNS),
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
        descriptors=descriptors_first,
        features=features_first,
        diagnostics=diagnostics,
        summary=summary,
    )
    return summary


def main() -> None:
    print(json.dumps(run_stage002(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
