"""Stage001 qualification for roll-adjusted trend-quality labels."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd


LINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
UPSTREAM_TOOLS = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_expiry_safe_roll_mapping/tools"
)
if str(UPSTREAM_TOOLS) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_TOOLS))

import stage001_expiry_safe_roll_mapping as upstream_stage

import roll_adjusted_trend_quality as core


publisher = upstream_stage.upstream
UPSTREAM_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_expiry_safe_roll_mapping/"
    "artifacts/stage001_expiry_safe_roll_mapping"
)
SOURCE_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_source_rebuild/"
    "artifacts/stage002_endofday_source_rebuild"
)
FEATURE_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/"
    "artifacts/stage001_daily_ranker_contract"
)
V2_CONTRACT_DIR = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker_v2/"
    "artifacts/stage001_v2_contract_requalification"
)
DEFAULT_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_roll_adjusted_trend_quality_labels"
UPSTREAM_PASS_DECISION = (
    "stage001_expiry_safe_roll_mapping_pass_allow_roll_label_generator_"
    "preregistration_only"
)
SOURCE_PASS_DECISION = (
    "stage002_endofday_source_rebuild_coverage_pass_allow_new_model_"
    "preregistration_only"
)
V2_CONTRACT_PASS_DECISION = (
    "stage001_daily_ranker_v2_contract_pass_allow_stage002_"
    "preregistration_only"
)
PASS_DECISION = (
    "stage001_roll_adjusted_trend_quality_labels_pass_allow_model_"
    "preregistration_only"
)
FAIL_DECISION = "stage001_roll_adjusted_trend_quality_labels_fail_close_no_model"

DEFAULT_INPUT_PATHS = {
    "upstream_manifest": UPSTREAM_DIR / "artifact_manifest.json",
    "upstream_paths": UPSTREAM_DIR / "expiry_safe_paths.csv.gz",
    "upstream_legs": UPSTREAM_DIR / "expiry_safe_legs.csv.gz",
    "upstream_summary": UPSTREAM_DIR / "summary.json",
    "source_manifest": SOURCE_DIR / "artifact_manifest.json",
    "source_summary": SOURCE_DIR / "stage002_summary.json",
    "source_bars": SOURCE_DIR / "normalised_daily_bars.csv.gz",
    "feature_manifest": FEATURE_DIR / "artifact_manifest.json",
    "feature_panel": FEATURE_DIR / "model_feature_panel.csv.gz",
    "v2_contract_manifest": V2_CONTRACT_DIR / "artifact_manifest.json",
    "v2_contract_summary": V2_CONTRACT_DIR / "summary.json",
}
DEFAULT_EXPECTED_SHA256 = {
    "upstream_manifest": "9f768fc6de7ccd3eb240c29f0444249bd333356d756b137197dc78e4f5f44d76",
    "upstream_paths": "a3f2c1249085b872372f8f0aca2d1cbaf77ecb8a7bc04056f9118f077c16748e",
    "upstream_legs": "db2fcffc24053cbb5c540a699bc47f19149d54eeb66aa2b57057707f346a92da",
    "upstream_summary": "6f994dd88896781a7f1af9e9760890540445dc8539a6349ae416b82bcf37283f",
    "source_manifest": "e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a",
    "source_summary": "67dcdb174bf7e253e100138eff1ec0b644c6a7cc68c0806f71aff10c66f00939",
    "source_bars": "f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4",
    "feature_manifest": "0ec63c32cf8fbe33a85bed16d20a94aaeb7d2ee9a5906670819e91d3671e702a",
    "feature_panel": "1e4ebb1942dc066eb1164dc82e7e0412fe10d433e57aa5b8b8ab3b71822344ac",
    "v2_contract_manifest": "7428e753607ff44b39f0e3510e29493ec96b4163a35fa261791da7d819b27b79",
    "v2_contract_summary": "a25817cbbd6da47dde8d711adf35ef70cc37422476060a2e652db37aaed7536d",
}


@dataclass(frozen=True)
class ExpectedCounts:
    path_rows: int = 56_272
    path_qids: int = 1_046
    leg_rows: int = 1_125_440
    feature_rows: int = 57_528
    holding_period: int = 20
    minimum_candidates_per_qid: int = 30
    relevance_levels: int = 5


class Stage001Error(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage001Error(f"json_root_not_object:{path}")
    return value


def _normalise_identity_dates(
    frame: pd.DataFrame, columns: list[str], name: str
) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        result[column] = pd.to_datetime(
            result[column], errors="coerce"
        ).dt.normalize()
        if result[column].isna().any():
            raise Stage001Error(f"invalid_date:{name}:{column}")
    return result


def _load_paths(path: Path) -> pd.DataFrame:
    columns = [
        "query_date",
        "product_vt_symbol",
        "main_contract_vt",
        "entry_date",
        "label_end",
        "leg_count",
        "path_valid",
    ]
    frame = pd.read_csv(path, encoding="utf-8-sig", usecols=columns)
    frame = _normalise_identity_dates(
        frame, ["query_date", "entry_date", "label_end"], "paths"
    )
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["main_contract_vt"] = frame["main_contract_vt"].astype(str)
    if frame.duplicated(core.PATH_KEYS).any():
        raise Stage001Error("duplicate_path_identity")
    return frame.sort_values(core.PATH_KEYS, kind="mergesort").reset_index(
        drop=True
    )


def _load_legs(path: Path) -> pd.DataFrame:
    columns = [
        "query_date",
        "product_vt_symbol",
        "leg_index",
        "previous_date",
        "return_date",
        "selected_contract_vt",
        "leg_valid",
        "previous_bar_present",
        "return_bar_present",
        "roll_event",
    ]
    return pd.read_csv(path, encoding="utf-8-sig", usecols=columns)


def _load_feature_identities(path: Path) -> pd.DataFrame:
    columns = ["query_date", "product_vt_symbol", "main_contract_vt"]
    frame = pd.read_csv(path, encoding="utf-8-sig", usecols=columns)
    frame = _normalise_identity_dates(frame, ["query_date"], "features")
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["main_contract_vt"] = frame["main_contract_vt"].astype(str)
    if frame.duplicated(core.PATH_KEYS).any():
        raise Stage001Error("duplicate_feature_identity")
    return frame.sort_values(core.PATH_KEYS, kind="mergesort").reset_index(
        drop=True
    )


def _load_close_prices(path: Path) -> pd.DataFrame:
    return pd.read_csv(
        path,
        encoding="utf-8-sig",
        usecols=["datetime", "symbol", "exchange", "interval", "close_price"],
        dtype={"symbol": "string", "exchange": "string", "interval": "string"},
    )


def _verify_upstream_bundles(
    *,
    upstream_dir: Path = UPSTREAM_DIR,
    source_dir: Path = SOURCE_DIR,
    feature_dir: Path = FEATURE_DIR,
    v2_contract_dir: Path = V2_CONTRACT_DIR,
) -> dict[str, dict[str, object]]:
    return {
        "upstream": publisher.verify_published_bundle(
            upstream_dir, verify_inputs=True
        ),
        "source": upstream_stage.v2.verify_path_manifest_bundle(source_dir),
        "feature": publisher.verify_published_bundle(
            feature_dir, verify_inputs=True
        ),
        "v2_contract": publisher.verify_published_bundle(
            v2_contract_dir, verify_inputs=True
        ),
    }


def _verification_gate(
    verifications: Mapping[str, Mapping[str, object]]
) -> bool:
    return set(verifications) == {
        "upstream",
        "source",
        "feature",
        "v2_contract",
    } and all(bool(value.get("verified")) for value in verifications.values())


def _feature_coverage(
    paths: pd.DataFrame, features: pd.DataFrame
) -> dict[str, int]:
    joined = paths[core.PATH_KEYS + ["main_contract_vt"]].merge(
        features.rename(columns={"main_contract_vt": "feature_main_contract_vt"}),
        how="left",
        on=core.PATH_KEYS,
        validate="one_to_one",
        indicator=True,
    )
    missing = joined["_merge"].ne("both")
    mismatch = (
        joined["_merge"].eq("both")
        & joined["main_contract_vt"].ne(joined["feature_main_contract_vt"])
    )
    return {
        "feature_identity_missing_paths": int(missing.sum()),
        "feature_contract_mismatch_paths": int(mismatch.sum()),
    }


def _maximum(frame: pd.DataFrame, column: str) -> float:
    if frame.empty:
        return float("inf")
    value = pd.to_numeric(frame[column], errors="coerce").max()
    return float(value) if pd.notna(value) else float("inf")


def assess_stage001(
    paths: pd.DataFrame,
    legs: pd.DataFrame,
    labels: pd.DataFrame,
    qid_diagnostics: pd.DataFrame,
    *,
    close_audit: Mapping[str, int],
    feature_rows: int,
    feature_coverage: Mapping[str, int],
    upstream_bundles_verified: bool,
    upstream_summary_valid: bool,
    source_summary_valid: bool,
    v2_contract_summary_valid: bool,
    input_identity_stable: bool,
    expected: ExpectedCounts = ExpectedCounts(),
) -> dict[str, object]:
    tolerance = 1e-12
    path_widths = labels.groupby("query_date", sort=False).size()
    formula_columns = [
        "return_sum_error",
        "efficiency_formula_error",
        "drawdown_formula_error",
        "capture_quality_formula_error",
    ]
    formula_maxima = {
        column: _maximum(labels, column) for column in formula_columns
    }
    logical_close_reads = int(close_audit.get("logical_close_reads", -1))
    cross_contract = int(
        close_audit.get("cross_contract_price_comparisons", -1)
    )
    gates = {
        "input_provenance": bool(
            upstream_bundles_verified
            and upstream_summary_valid
            and source_summary_valid
            and v2_contract_summary_valid
            and input_identity_stable
        ),
        "frozen_counts": bool(
            len(paths) == expected.path_rows
            and paths["query_date"].nunique() == expected.path_qids
            and len(legs) == expected.leg_rows
            and feature_rows == expected.feature_rows
            and len(labels) == expected.path_rows
            and len(qid_diagnostics) == expected.path_qids
        ),
        "upstream_path_structure": bool(
            paths["path_valid"].fillna(False).astype(bool).all()
            and pd.to_numeric(paths["leg_count"], errors="coerce")
            .eq(expected.holding_period)
            .all()
            and legs["leg_valid"].fillna(False).astype(bool).all()
            and labels["leg_count"].eq(expected.holding_period).all()
        ),
        "feature_identity_coverage": bool(
            int(feature_coverage["feature_identity_missing_paths"]) == 0
            and int(feature_coverage["feature_contract_mismatch_paths"]) == 0
        ),
        "close_integrity": bool(
            logical_close_reads == expected.leg_rows * 2
            and int(close_audit.get("missing_endpoint_legs", -1)) == 0
            and int(close_audit.get("invalid_close_legs", -1)) == 0
            and cross_contract == 0
            and int(labels["cross_contract_price_comparisons"].sum()) == 0
        ),
        "formula_integrity": bool(
            all(value <= tolerance for value in formula_maxima.values())
            and labels["future_trend_efficiency"].between(
                -tolerance, 1.0 + tolerance
            ).all()
            and labels["future_oriented_max_drawdown"].le(tolerance).all()
            and (
                labels["future_trend_capture_quality"]
                <= labels["future_abs_log_return"] + tolerance
            ).all()
        ),
        "qid_relevance_nondegenerate": bool(
            not path_widths.empty
            and int(path_widths.min()) >= expected.minimum_candidates_per_qid
            and int(qid_diagnostics["target_unique_count"].min())
            >= expected.relevance_levels
            and int(qid_diagnostics["relevance_level_count"].min())
            == expected.relevance_levels
            and np.isfinite(qid_diagnostics["target_std"]).all()
            and qid_diagnostics["target_std"].gt(0).all()
        ),
        "research_boundary": True,
    }
    all_gates_passed = all(gates.values())
    direction_counts = {
        str(int(key)): int(value)
        for key, value in labels["future_trend_sign"].value_counts().items()
    }
    return {
        "line_id": "futures_trend_xgboost_pit_roll_adjusted_trend_quality_labels",
        "stage": "Stage001",
        "decision": PASS_DECISION if all_gates_passed else FAIL_DECISION,
        "all_gates_passed": all_gates_passed,
        "gates": gates,
        "expected_counts": asdict(expected),
        "path_rows": int(len(paths)),
        "path_qids": int(paths["query_date"].nunique()),
        "leg_rows": int(len(legs)),
        "feature_rows": int(feature_rows),
        "label_rows": int(len(labels)),
        "qid_rows": int(len(qid_diagnostics)),
        "qid_width_min": int(path_widths.min()),
        "qid_width_median": float(path_widths.median()),
        "qid_width_max": int(path_widths.max()),
        "target_unique_min": int(qid_diagnostics["target_unique_count"].min()),
        "relevance_level_min": int(
            qid_diagnostics["relevance_level_count"].min()
        ),
        "logical_close_reads": logical_close_reads,
        "cross_contract_price_comparisons": cross_contract,
        "roll_leg_count": int(legs["roll_event"].astype(bool).sum()),
        "paths_with_roll": int(labels["roll_count"].gt(0).sum()),
        "future_direction_counts": direction_counts,
        "negative_capture_quality_paths": int(
            labels["future_trend_capture_quality"].lt(0).sum()
        ),
        "strictly_negative_oriented_drawdown_paths": int(
            labels["future_oriented_max_drawdown"].lt(0).sum()
        ),
        "formula_max_errors": formula_maxima,
        **dict(feature_coverage),
        "future_label_value_rows_read": int(len(labels)),
        "future_return_calculations": int(len(legs)),
        "xgboost_fit_count": 0,
        "xgboost_predict_count": 0,
        "strategy_backtest_runs": 0,
        "true_engine_runs": 0,
        "sealed_holdout_rows": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
        "tradeability_claim_count": 0,
        "independent_reviewer_required": False,
        "independent_reviewer_reason": "no_backtest_result_produced",
    }


def _report(summary: Mapping[str, object]) -> str:
    gate_lines = "\n".join(
        f"- `{name}`：{'通过' if passed else '失败'}"
        for name, passed in summary["gates"].items()
    )
    return (
        "# Stage001逐合约换月调整趋势质量标签资格\n\n"
        f"- 决策：`{summary['decision']}`\n"
        f"- 路径/qid/leg：{summary['path_rows']} / {summary['path_qids']} / {summary['leg_rows']}\n"
        f"- qid宽度：{summary['qid_width_min']} / {summary['qid_width_median']} / {summary['qid_width_max']}\n"
        f"- 逻辑close读取：{summary['logical_close_reads']}\n"
        f"- 跨合约价格比较：{summary['cross_contract_price_comparisons']}\n"
        f"- 含换月路径：{summary['paths_with_roll']}\n"
        f"- 未来净方向计数：{summary['future_direction_counts']}\n"
        f"- 负趋势捕获质量路径：{summary['negative_capture_quality_paths']}\n"
        "- 标签是市场路径代理，不是可成交PnL或账户回撤。\n"
        "- XGBoost fit/predict、策略回测、true engine、holdout、CTP、订单和生产写入：全部为0。\n\n"
        "## 门禁\n\n"
        f"{gate_lines}\n"
    )


def verify_final_bundle(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, object]:
    return publisher.verify_published_bundle(output_dir, verify_inputs=True)


def run_stage001(
    *,
    line_dir: Path = LINE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    upstream_dir: Path = UPSTREAM_DIR,
    source_dir: Path = SOURCE_DIR,
    feature_dir: Path = FEATURE_DIR,
    v2_contract_dir: Path = V2_CONTRACT_DIR,
    input_paths: Mapping[str, Path] = DEFAULT_INPUT_PATHS,
    expected_sha256: Mapping[str, str] = DEFAULT_EXPECTED_SHA256,
    expected: ExpectedCounts = ExpectedCounts(),
) -> dict[str, object]:
    final_path = publisher.assert_line_local_output(line_dir, output_dir)
    if final_path.exists():
        raise Stage001Error(f"final_output_exists:{final_path}")
    identities_before = publisher.collect_input_identities(
        input_paths, expected_sha256
    )
    verifications = _verify_upstream_bundles(
        upstream_dir=upstream_dir,
        source_dir=source_dir,
        feature_dir=feature_dir,
        v2_contract_dir=v2_contract_dir,
    )
    if not _verification_gate(verifications):
        errors = [
            f"{name}:{','.join(str(x) for x in value.get('errors', []))}"
            for name, value in verifications.items()
            if not value.get("verified")
        ]
        raise Stage001Error("upstream_bundle_invalid:" + ";".join(errors))

    upstream_summary = _read_json(input_paths["upstream_summary"])
    source_summary = _read_json(input_paths["source_summary"])
    v2_contract_summary = _read_json(input_paths["v2_contract_summary"])
    paths = _load_paths(input_paths["upstream_paths"])
    legs = _load_legs(input_paths["upstream_legs"])
    features = _load_feature_identities(input_paths["feature_panel"])
    feature_coverage = _feature_coverage(paths, features)
    prices = _load_close_prices(input_paths["source_bars"])
    leg_returns, close_audit = core.build_leg_returns(legs, prices)
    labels = core.aggregate_path_labels(
        leg_returns, expected_leg_count=expected.holding_period
    )
    labels, qid_diagnostics = core.add_cross_sectional_relevance(
        labels,
        levels=expected.relevance_levels,
        minimum_qid_width=expected.minimum_candidates_per_qid,
    )
    identities_after = publisher.collect_input_identities(
        input_paths, expected_sha256
    )
    summary = assess_stage001(
        paths,
        legs,
        labels,
        qid_diagnostics,
        close_audit=close_audit,
        feature_rows=len(features),
        feature_coverage=feature_coverage,
        upstream_bundles_verified=_verification_gate(verifications),
        upstream_summary_valid=bool(
            upstream_summary.get("all_gates_passed")
            and upstream_summary.get("decision") == UPSTREAM_PASS_DECISION
        ),
        source_summary_valid=bool(
            source_summary.get("all_gates_passed")
            and source_summary.get("decision") == SOURCE_PASS_DECISION
        ),
        v2_contract_summary_valid=bool(
            v2_contract_summary.get("all_gates_passed")
            and v2_contract_summary.get("decision")
            == V2_CONTRACT_PASS_DECISION
        ),
        input_identity_stable=identities_before == identities_after,
        expected=expected,
    )
    summary["run_timestamp"] = datetime.now().astimezone().isoformat()
    summary["input_identities_before"] = identities_before
    summary["input_identities_after"] = identities_after
    summary["upstream_verifications"] = verifications
    summary["upstream_summary_identity"] = {
        "decision": upstream_summary.get("decision"),
        "all_gates_passed": upstream_summary.get("all_gates_passed"),
    }
    summary["source_summary_identity"] = {
        "decision": source_summary.get("decision"),
        "all_gates_passed": source_summary.get("all_gates_passed"),
    }
    summary["v2_contract_summary_identity"] = {
        "decision": v2_contract_summary.get("decision"),
        "all_gates_passed": v2_contract_summary.get("all_gates_passed"),
    }
    summary["implementation_identities"] = {
        "runner_sha256": publisher.sha256_file(Path(__file__)),
        "core_sha256": publisher.sha256_file(Path(core.__file__)),
    }
    publisher.publish_bundle(
        {
            "leg_returns.csv.gz": leg_returns,
            "path_labels.csv.gz": labels,
            "qid_diagnostics.csv.gz": qid_diagnostics,
        },
        {
            "summary.json": summary,
            "input_identities.json": identities_after,
            "upstream_verification.json": verifications,
            "report.md": _report(summary),
        },
        line_dir=line_dir,
        final_dir=final_path,
        input_identities=identities_after,
    )
    verification = verify_final_bundle(final_path)
    if not verification["verified"]:
        raise Stage001Error(
            "published_bundle_invalid:" + ",".join(verification["errors"])
        )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage001 roll-adjusted trend-quality label qualification"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.verify_only:
        result = verify_final_bundle()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["verified"] else 1
    try:
        summary = run_stage001()
    except (
        Stage001Error,
        core.TrendQualityError,
        publisher.Stage001Error,
    ) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["all_gates_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

