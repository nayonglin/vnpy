"""Build the frozen unlabeled physical-positioning feature contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd


LINE_ID: Final = "futures_trend_xgboost_pit_physical_positioning_context"
STAGE: Final = "Stage002"
FORMAL_RELEASE_ID: Final = "m0005_20260901T165450+0800_1961d98ccb2b"
LINE_DIR = Path(__file__).resolve().parents[1]
STAGE001_DIR = LINE_DIR / "artifacts/stage001_physical_positioning_coverage"
OUTPUT_DIR = LINE_DIR / "artifacts/stage002_physical_features"

INPUT_PATHS: Final = {
    "feature_panel": STAGE001_DIR / "physical_feature_panel.csv.gz",
    "stage001_summary": STAGE001_DIR / "stage001_summary.json",
    "family_coverage": STAGE001_DIR / "family_coverage.csv",
    "stage001_manifest": STAGE001_DIR / "artifact_manifest.json",
    "preregistration": LINE_DIR
    / "stages/20260903_0256_stage002_physical_feature_preregistration.md",
    "independent_review": LINE_DIR
    / "reviews/20260903_stage002_prerun_independent_review.md",
    "review_decision": LINE_DIR
    / "reviews/20260903_stage002_prerun_review_decision.json",
}
EXPECTED_SHA256: Final = {
    "feature_panel": "62ac505b07412bbd2f5110f6131ce9a9638a47942558ae93da28601731755d7e",
    "stage001_summary": "cc6c4ae3131928190f382da154af9460c2239d33c88665c3696987ea2cac99f1",
    "family_coverage": "e96da5d74265a311b223a37245e31ae95f3c6b520df9947d010798c2113d69e6",
    "stage001_manifest": "c4436bef32a174e699a7f736a383591d3ef581c9c3fd00ee38ed076b562a29fa",
    "preregistration": "1acaacc180b778d4f311aa7f54ecb66069016423242cbac4cc91741858569ad3",
    "independent_review": "08fe767a4ba382fac502be3e1aebf9f9feed679800dc282d69a4c3896b880e83",
    "review_decision": "14485551f9826cf6872dac147285e6537c155a000ef766e512ec6258ee67646d",
}
EXPECTED_COUNTS: Final = {
    "candidate_rows": 374,
    "candidate_months": 47,
    "candidate_products": 18,
    "active_months": 35,
    "model_eligible_rows": 218,
    "rank10_anchors": 35,
    "eligible_challengers": 183,
    "segment_active_months": [13, 13, 9],
    "segment_eligible_rows": [62, 91, 65],
    "active_months_by_year": {"2022": 8, "2023": 10, "2024": 9, "2025": 8},
}

PANEL_COLUMNS: Final = [
    "eval_date",
    "product_vt_symbol",
    "pit_logistic_probability",
    "window_id",
    "a_rank",
    "role",
    "basis_available",
    "basis_dom_rate",
    "basis_near_rate",
    "member_available",
    "member_net_position_ratio",
    "member_net_position_change_ratio",
    "member_turnover_pressure_ratio",
]
MODEL_FEATURES: Final = [
    "formal_probability_delta_vs_rank10",
    "basis_dom_rate_delta_vs_rank10",
    "basis_near_rate_delta_vs_rank10",
    "member_net_position_ratio_delta_vs_rank10",
    "member_net_position_change_ratio_delta_vs_rank10",
    "member_turnover_pressure_ratio_delta_vs_rank10",
]
PHYSICAL_FEATURES: Final = MODEL_FEATURES[1:]
RAW_TO_FEATURE: Final = {
    "pit_logistic_probability": "formal_probability_delta_vs_rank10",
    "basis_dom_rate": "basis_dom_rate_delta_vs_rank10",
    "basis_near_rate": "basis_near_rate_delta_vs_rank10",
    "member_net_position_ratio": "member_net_position_ratio_delta_vs_rank10",
    "member_net_position_change_ratio": "member_net_position_change_ratio_delta_vs_rank10",
    "member_turnover_pressure_ratio": "member_turnover_pressure_ratio_delta_vs_rank10",
}
SEGMENTS: Final = ["development_initial", "development_oos", "sealed_holdout_features_only"]


class Stage002Error(RuntimeError):
    """Raised when the frozen Stage002 contract must fail closed."""


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


def _boolean(series: pd.Series, column: str) -> pd.Series:
    values = series.astype("string").str.strip().str.lower()
    mapping = {"true": True, "false": False, "1": True, "0": False}
    invalid = values.isna() | ~values.isin(mapping)
    if invalid.any():
        raise Stage002Error(f"invalid_boolean:{column}")
    return values.map(mapping).astype(bool)


def _normalise_panel(panel: pd.DataFrame) -> pd.DataFrame:
    missing = set(PANEL_COLUMNS).difference(panel.columns)
    if missing:
        raise Stage002Error(f"panel_columns_missing:{','.join(sorted(missing))}")
    result = panel[PANEL_COLUMNS].copy()
    result["eval_date"] = pd.to_datetime(result["eval_date"], errors="coerce").dt.normalize()
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str).str.strip()
    result["window_id"] = result["window_id"].astype(str).str.strip()
    result["role"] = result["role"].astype(str).str.strip()
    result["a_rank"] = pd.to_numeric(result["a_rank"], errors="coerce").astype("Int64")
    result["basis_available"] = _boolean(result["basis_available"], "basis_available")
    result["member_available"] = _boolean(result["member_available"], "member_available")
    for column in RAW_TO_FEATURE:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if result[["eval_date", "a_rank"]].isna().any().any():
        raise Stage002Error("panel_required_value_missing")
    if result["product_vt_symbol"].eq("").any():
        raise Stage002Error("panel_product_empty")
    result = result[result["a_rank"].ge(10)].copy()
    result["a_rank"] = result["a_rank"].astype(int)
    if result.duplicated(["eval_date", "product_vt_symbol", "a_rank"]).any():
        raise Stage002Error("candidate_duplicate_key")
    return result.sort_values(
        ["eval_date", "a_rank", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def _segment(index: int, development_months: int, development_oos_months: int) -> str:
    if index < int(development_months):
        return SEGMENTS[0]
    if index < int(development_months) + int(development_oos_months):
        return SEGMENTS[1]
    return SEGMENTS[2]


def _correlations(eligible: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    scopes = {
        "eligible_all": eligible,
        "eligible_challengers": eligible[eligible["a_rank"].gt(10)],
    }
    for scope, frame in scopes.items():
        matrix = frame[PHYSICAL_FEATURES].corr(method="spearman")
        for feature_x in PHYSICAL_FEATURES:
            for feature_y in PHYSICAL_FEATURES:
                rows.append(
                    {
                        "scope": scope,
                        "row_count": int(len(frame)),
                        "feature_x": feature_x,
                        "feature_y": feature_y,
                        "spearman": float(matrix.loc[feature_x, feature_y]),
                    }
                )
    return pd.DataFrame(rows)


def build_feature_artifacts(
    panel: pd.DataFrame,
    *,
    development_months: int = 18,
    development_oos_months: int = 17,
) -> dict[str, pd.DataFrame]:
    if int(development_months) < 1 or int(development_oos_months) < 1:
        raise Stage002Error("segment_months_must_be_positive")
    candidate = _normalise_panel(panel)
    candidate["row_complete"] = candidate["basis_available"] & candidate["member_available"]
    candidate["active_month"] = False
    candidate["model_eligible"] = False
    for feature in MODEL_FEATURES:
        candidate[feature] = np.nan

    eval_dates = list(pd.DatetimeIndex(sorted(candidate["eval_date"].unique())))
    month_rows: list[dict[str, Any]] = []
    for month_index, eval_date in enumerate(eval_dates):
        month_mask = candidate["eval_date"].eq(eval_date)
        group = candidate.loc[month_mask]
        anchors = group[group["a_rank"].eq(10)]
        if len(anchors) != 1:
            raise Stage002Error(f"rank10_count_invalid:{pd.Timestamp(eval_date).date()}")
        ranks = sorted(group["a_rank"].astype(int).tolist())
        if ranks != list(range(10, max(ranks) + 1)) or max(ranks) > 18:
            raise Stage002Error(f"candidate_rank_sequence_invalid:{pd.Timestamp(eval_date).date()}")
        anchor = anchors.iloc[0]
        rank10_complete = bool(anchor["row_complete"])
        complete_challengers = int(
            (group["row_complete"] & group["a_rank"].gt(10)).sum()
        )
        active = bool(rank10_complete and complete_challengers >= 2)
        eligible_mask = month_mask & candidate["row_complete"] & active
        candidate.loc[month_mask, "active_month"] = active
        candidate.loc[eligible_mask, "model_eligible"] = True
        if active:
            raw_columns = list(RAW_TO_FEATURE)
            if candidate.loc[eligible_mask, raw_columns].isna().any().any():
                raise Stage002Error(f"eligible_metric_missing:{pd.Timestamp(eval_date).date()}")
            for raw_column, feature_column in RAW_TO_FEATURE.items():
                candidate.loc[eligible_mask, feature_column] = (
                    candidate.loc[eligible_mask, raw_column] - float(anchor[raw_column])
                )
        month_rows.append(
            {
                "eval_date": pd.Timestamp(eval_date),
                "segment": _segment(month_index, development_months, development_oos_months),
                "candidate_rows": int(len(group)),
                "complete_rows": int(group["row_complete"].sum()),
                "complete_challengers": complete_challengers,
                "rank10_complete": rank10_complete,
                "active_month": active,
                "model_eligible_rows": int(eligible_mask.sum()),
                "eligible_challenger_rows": int(
                    (eligible_mask & candidate["a_rank"].gt(10)).sum()
                ),
            }
        )

    candidate = candidate.sort_values(
        ["eval_date", "a_rank", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    eligible = candidate.loc[
        candidate["model_eligible"],
        ["eval_date", "product_vt_symbol", "window_id", "a_rank", "role", *MODEL_FEATURES],
    ].reset_index(drop=True)
    month_eligibility = pd.DataFrame(month_rows)

    product_rows: list[dict[str, Any]] = []
    for product, group in candidate.groupby("product_vt_symbol", sort=True):
        challenger = group["a_rank"].gt(10)
        eligible_challenger = challenger & group["model_eligible"]
        product_rows.append(
            {
                "product_vt_symbol": product,
                "candidate_rows": int(len(group)),
                "challenger_rows": int(challenger.sum()),
                "model_eligible_rows": int(group["model_eligible"].sum()),
                "eligible_challenger_rows": int(eligible_challenger.sum()),
                "eligible_challenger_rate": (
                    float(eligible_challenger.sum() / challenger.sum())
                    if challenger.any()
                    else 0.0
                ),
            }
        )
    product_eligibility = pd.DataFrame(product_rows)

    anchors = eligible[eligible["a_rank"].eq(10)]
    challengers = eligible[eligible["a_rank"].gt(10)]
    degeneracy_rows = []
    for feature in MODEL_FEATURES:
        values = pd.to_numeric(challengers[feature], errors="coerce")
        degeneracy_rows.append(
            {
                "feature": feature,
                "eligible_finite_rows": int(np.isfinite(pd.to_numeric(eligible[feature])).sum()),
                "rank10_exact_zero_rows": int(anchors[feature].eq(0.0).sum()),
                "challenger_rows": int(len(challengers)),
                "challenger_unique_values": int(values.nunique(dropna=True)),
                "challenger_nonzero_rows": int(values.ne(0.0).sum()),
            }
        )
    feature_degeneracy = pd.DataFrame(degeneracy_rows)
    return {
        "candidate_panel": candidate,
        "eligible_panel": eligible,
        "month_eligibility": month_eligibility,
        "product_eligibility": product_eligibility,
        "feature_degeneracy": feature_degeneracy,
        "feature_correlations": _correlations(eligible),
    }


def _verify_upstream_contract(
    summary: Mapping[str, Any],
    family_coverage: pd.DataFrame,
    manifest: Mapping[str, str],
    review_decision: Mapping[str, Any],
    identities: Mapping[str, Mapping[str, Any]],
) -> None:
    expected_summary = {
        "decision": "stage001_physical_positioning_coverage_pass_ready_for_feature_preregistration",
        "eligible_families": ["basis", "member"],
        "diagnostic_only_families": ["warehouse"],
        "pit_source_date_violation_rows": 0,
        "label_columns_read": [],
        "label_values_read": False,
        "sealed_holdout_files_read": [],
        "trains_model": False,
        "model_fit_count": 0,
        "strategy_backtest_runs": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
    }
    for key, expected in expected_summary.items():
        if summary.get(key) != expected:
            raise Stage002Error(f"stage001_contract_invalid:{key}")

    family = family_coverage[["family", "eligible_for_feature_preregistration"]].copy()
    family["eligible_for_feature_preregistration"] = _boolean(
        family["eligible_for_feature_preregistration"],
        "eligible_for_feature_preregistration",
    )
    eligible = sorted(
        family.loc[family["eligible_for_feature_preregistration"], "family"].astype(str)
    )
    diagnostic = sorted(
        family.loc[~family["eligible_for_feature_preregistration"], "family"].astype(str)
    )
    if eligible != ["basis", "member"] or diagnostic != ["warehouse"]:
        raise Stage002Error("family_contract_invalid")

    manifest_expectations = {
        "physical_feature_panel.csv.gz": identities["feature_panel"]["sha256"],
        "stage001_summary.json": identities["stage001_summary"]["sha256"],
        "family_coverage.csv": identities["family_coverage"]["sha256"],
    }
    for name, digest in manifest_expectations.items():
        if manifest.get(name) != digest:
            raise Stage002Error(f"stage001_manifest_invalid:{name}")

    if review_decision.get("decision") != "ALLOW_STAGE002_TDD_IMPLEMENTATION_ONLY":
        raise Stage002Error("independent_review_not_allowed")
    if review_decision.get("allowed") is not True:
        raise Stage002Error("independent_review_allowed_flag_invalid")
    severity = review_decision.get("severity", {})
    if any(severity.get(level) != 0 for level in ["P0", "P1", "P2"]):
        raise Stage002Error("independent_review_blocking_findings")
    review_hashes = {
        "review_sha256": identities["independent_review"]["sha256"],
        "preregistration_sha256": identities["preregistration"]["sha256"],
        "stage001_manifest_sha256": identities["stage001_manifest"]["sha256"],
    }
    for key, digest in review_hashes.items():
        if review_decision.get(key) != digest:
            raise Stage002Error(f"independent_review_identity_invalid:{key}")


def _summary_counts(artifacts: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    candidate = artifacts["candidate_panel"]
    eligible = artifacts["eligible_panel"]
    month = artifacts["month_eligibility"]
    segment_active = []
    segment_rows = []
    for segment in SEGMENTS:
        rows = month[month["segment"].eq(segment)]
        segment_active.append(int(rows["active_month"].sum()))
        segment_rows.append(int(rows["model_eligible_rows"].sum()))
    active_by_year = (
        month[month["active_month"]]
        .assign(year=month.loc[month["active_month"], "eval_date"].dt.year.astype(str))
        .groupby("year")["active_month"]
        .sum()
    )
    return {
        "candidate_rows": int(len(candidate)),
        "candidate_months": int(candidate["eval_date"].nunique()),
        "candidate_products": int(candidate["product_vt_symbol"].nunique()),
        "active_months": int(month["active_month"].sum()),
        "model_eligible_rows": int(len(eligible)),
        "rank10_anchors": int(eligible["a_rank"].eq(10).sum()),
        "eligible_challengers": int(eligible["a_rank"].gt(10).sum()),
        "segment_active_months": segment_active,
        "segment_eligible_rows": segment_rows,
        "active_months_by_year": {
            str(year): int(value) for year, value in active_by_year.items()
        },
    }


def _correlation_summary(correlations: pd.DataFrame, scope: str) -> dict[str, Any]:
    rows = correlations[correlations["scope"].eq(scope)]
    lookup = rows.set_index(["feature_x", "feature_y"])["spearman"]
    basis_pair = float(
        lookup.loc[
            "basis_dom_rate_delta_vs_rank10", "basis_near_rate_delta_vs_rank10"
        ]
    )
    excluded = {
        (
            "basis_dom_rate_delta_vs_rank10",
            "basis_near_rate_delta_vs_rank10",
        ),
        (
            "basis_near_rate_delta_vs_rank10",
            "basis_dom_rate_delta_vs_rank10",
        ),
    }
    other = rows[
        rows.apply(
            lambda row: row["feature_x"] != row["feature_y"]
            and (row["feature_x"], row["feature_y"]) not in excluded,
            axis=1,
        )
    ]
    return {
        "row_count": int(rows["row_count"].iloc[0]),
        "basis_pair_spearman": basis_pair,
        "max_other_abs_spearman": float(other["spearman"].abs().max()),
    }


def _assess(
    artifacts: Mapping[str, pd.DataFrame],
    *,
    expected_counts: Mapping[str, Any],
    minimum_challenger_unique: int,
    minimum_challenger_nonzero: int,
) -> dict[str, Any]:
    counts = _summary_counts(artifacts)
    eligible = artifacts["eligible_panel"]
    degeneracy = artifacts["feature_degeneracy"]
    physical = degeneracy[degeneracy["feature"].isin(PHYSICAL_FEATURES)]
    finite = bool(np.isfinite(eligible[MODEL_FEATURES].to_numpy(dtype=float)).all())
    anchors = eligible[eligible["a_rank"].eq(10)]
    anchor_zero = bool(anchors[MODEL_FEATURES].eq(0.0).all().all())
    count_gates = {
        key: counts.get(key) == expected_counts.get(key)
        for key in EXPECTED_COUNTS
    }
    gates = {
        **count_gates,
        "eligible_features_finite": finite,
        "rank10_features_exact_zero": anchor_zero,
        "physical_unique_values": bool(
            physical["challenger_unique_values"].ge(int(minimum_challenger_unique)).all()
        ),
        "physical_nonzero_rows": bool(
            physical["challenger_nonzero_rows"].ge(int(minimum_challenger_nonzero)).all()
        ),
        "warehouse_excluded_from_model_features": not any(
            "warehouse" in feature for feature in MODEL_FEATURES
        ),
    }
    passed = bool(all(gates.values()))
    product = artifacts["product_eligibility"]
    zero_products = sorted(
        product.loc[product["eligible_challenger_rows"].eq(0), "product_vt_symbol"].astype(str)
    )
    correlations = artifacts["feature_correlations"]
    return {
        "decision": (
            "stage002_physical_features_pass_ready_for_training_contract_preregistration"
            if passed
            else "stage002_physical_features_fail_stop_no_model"
        ),
        **counts,
        "eligible_challenger_product_count": int(
            product["eligible_challenger_rows"].gt(0).sum()
        ),
        "zero_eligible_challenger_products": zero_products,
        "eligible_feature_values_finite": finite,
        "rank10_features_exact_zero": anchor_zero,
        "correlation_eligible_all": _correlation_summary(correlations, "eligible_all"),
        "correlation_eligible_challengers": _correlation_summary(
            correlations, "eligible_challengers"
        ),
        "technical_gate_results": gates,
        "technical_gate_pass_count": int(sum(bool(value) for value in gates.values())),
        "technical_gate_count": int(len(gates)),
        "technical_gate_pass": passed,
    }


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
    artifacts: Mapping[str, pd.DataFrame],
    summary: Mapping[str, Any],
) -> None:
    output_dir = Path(output_dir)
    temp_dir = output_dir.with_name(f"{output_dir.name}.tmp")
    if output_dir.exists():
        raise Stage002Error("stage002_output_already_exists")
    if temp_dir.exists():
        raise Stage002Error("stage002_temp_output_already_exists")
    temp_dir.mkdir(parents=True, exist_ok=False)
    files = {
        "candidate_physical_feature_panel.csv": artifacts["candidate_panel"],
        "model_eligible_feature_panel.csv": artifacts["eligible_panel"],
        "month_eligibility.csv": artifacts["month_eligibility"],
        "product_eligibility.csv": artifacts["product_eligibility"],
        "feature_degeneracy.csv": artifacts["feature_degeneracy"],
        "feature_correlations.csv": artifacts["feature_correlations"],
    }
    for name, frame in files.items():
        _write_csv(frame, temp_dir / name)
    (temp_dir / "stage002_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    zero_products = ", ".join(summary["zero_eligible_challenger_products"]) or "无"
    report = (
        "# Stage002 基差与会员持仓无标签特征结果\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 候选：`{summary['candidate_rows']}`行 / `{summary['candidate_months']}`月；"
        f"模型资格：`{summary['model_eligible_rows']}`行 / `{summary['active_months']}`月。\n"
        f"- 完整挑战者覆盖品种：`{summary['eligible_challenger_product_count']}/"
        f"{summary['candidate_products']}`；零完整挑战者品种：`{zero_products}`。\n"
        f"- 相关性分母：eligible-all=`{summary['correlation_eligible_all']['row_count']}`行，"
        f"challenger-only=`{summary['correlation_eligible_challengers']['row_count']}`行。\n"
        "- 证据只适用于完整物理信息子宇宙；非完整候选和非活跃月机械回退线上逻辑回归A。\n"
        "- 本阶段未读取标签，未训练、未回测、未连接CTP、未调用订单API。\n"
    )
    (temp_dir / "report.md").write_text(report, encoding="utf-8")
    artifact_names = [*files, "report.md", "stage002_summary.json"]
    manifest = {name: sha256_file(temp_dir / name) for name in artifact_names}
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
    expected_counts: Mapping[str, Any] = EXPECTED_COUNTS,
    development_months: int = 18,
    development_oos_months: int = 17,
    minimum_challenger_unique: int = 150,
    minimum_challenger_nonzero: int = 150,
) -> dict[str, Any]:
    if Path(output_dir).exists():
        raise Stage002Error("stage002_output_already_exists")
    before = _verify_inputs(input_paths, expected_sha256)
    summary001 = json.loads(Path(input_paths["stage001_summary"]).read_text(encoding="utf-8"))
    family_coverage = pd.read_csv(
        Path(input_paths["family_coverage"]),
        usecols=["family", "eligible_for_feature_preregistration"],
    )
    manifest001 = json.loads(Path(input_paths["stage001_manifest"]).read_text(encoding="utf-8"))
    review_decision = json.loads(Path(input_paths["review_decision"]).read_text(encoding="utf-8"))
    _verify_upstream_contract(
        summary001, family_coverage, manifest001, review_decision, before
    )
    panel = pd.read_csv(Path(input_paths["feature_panel"]), usecols=PANEL_COLUMNS)
    first = build_feature_artifacts(
        panel,
        development_months=development_months,
        development_oos_months=development_oos_months,
    )
    second = build_feature_artifacts(
        panel,
        development_months=development_months,
        development_oos_months=development_oos_months,
    )
    for name in first:
        pd.testing.assert_frame_equal(first[name], second[name], check_exact=True)
    summary = _assess(
        first,
        expected_counts=expected_counts,
        minimum_challenger_unique=minimum_challenger_unique,
        minimum_challenger_nonzero=minimum_challenger_nonzero,
    )
    after = _verify_inputs(input_paths, expected_sha256)
    if before != after:
        raise Stage002Error("input_identity_changed_during_run")
    summary.update(
        {
            "line_id": LINE_ID,
            "stage": STAGE,
            "formal_release_id": FORMAL_RELEASE_ID,
            "evidence_scope": "mechanically_complete_physical_evidence_subuniverse_only",
            "model_features": list(MODEL_FEATURES),
            "warehouse_feature_count": 0,
            "development_months": int(development_months),
            "development_oos_months": int(development_oos_months),
            "minimum_challenger_unique": int(minimum_challenger_unique),
            "minimum_challenger_nonzero": int(minimum_challenger_nonzero),
            "repeat_exact": True,
            "input_identities_before": before,
            "input_identities_after": after,
            "input_identity_stable": True,
            "panel_columns_read": list(PANEL_COLUMNS),
            "label_columns_read": [],
            "label_values_read": False,
            "sealed_holdout_label_files_read": [],
            "trains_model": False,
            "model_fit_count": 0,
            "parameter_search_count": 0,
            "strategy_backtest_runs": 0,
            "true_engine_backtest_runs": 0,
            "ctp_connected": False,
            "order_api_called_count": 0,
        }
    )
    _publish(Path(output_dir), first, summary)
    return summary


def main() -> None:
    print(json.dumps(run_stage002(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
