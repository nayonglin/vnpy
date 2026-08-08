"""Frozen blind-label statistics for Stage214 all-short validation."""

from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact
from scipy.stats.contingency import odds_ratio
from sklearn.metrics import cohen_kappa_score


LABELS = frozenset(
    {
        "trend_same_direction",
        "range_or_compression",
        "mixed_or_opposite",
        "insufficient",
    }
)
CONFIDENCE_LEVELS = frozenset({"high", "medium", "low"})
LABEL_COLUMNS = ("case_id", "label", "reason", "confidence", "timestamp")
REPO_ROOT = Path(__file__).resolve().parents[4]
LINE_ROOT = REPO_ROOT / "research/lines/futures_trend_stage819_intraday_rules"
OUTPUT_DIR = LINE_ROOT / "outputs/stage214_all_short_preentry_blind_validation"


def _expected_case_ids(expected_cases: Iterable[object] | pd.DataFrame) -> set[str]:
    if isinstance(expected_cases, pd.DataFrame):
        if "case_id" not in expected_cases.columns:
            raise ValueError("expected cases missing case_id")
        values = expected_cases["case_id"]
    elif isinstance(expected_cases, pd.Series):
        values = expected_cases
    else:
        values = pd.Series(list(expected_cases), dtype="object")
    if values.isna().any():
        raise ValueError("expected case set contains missing case_id")
    case_ids = values.astype(str).str.strip()
    if case_ids.eq("").any() or case_ids.duplicated().any():
        raise ValueError("expected case set contains empty or duplicate case_id")
    return set(case_ids)


def validate_reviewer_labels(
    labels: pd.DataFrame,
    expected_cases: Iterable[object] | pd.DataFrame,
) -> None:
    """Fail closed unless one complete, frozen-protocol row exists per case."""
    missing_columns = [column for column in LABEL_COLUMNS if column not in labels.columns]
    if missing_columns:
        raise ValueError(f"labels missing columns: {missing_columns}")

    if labels["case_id"].isna().any():
        raise ValueError("case_id must be non-empty")
    case_ids = labels["case_id"].astype(str).str.strip()
    if case_ids.eq("").any():
        raise ValueError("empty case_id")
    if case_ids.duplicated().any():
        raise ValueError("duplicate case_id")
    expected_ids = _expected_case_ids(expected_cases)
    actual_ids = set(case_ids)
    if actual_ids != expected_ids:
        raise ValueError(
            "case set mismatch: "
            f"missing={sorted(expected_ids - actual_ids)}, "
            f"extra={sorted(actual_ids - expected_ids)}"
        )

    label_values = labels["label"].astype(str).str.strip()
    invalid_labels = sorted(set(label_values) - LABELS)
    if invalid_labels:
        raise ValueError(f"invalid label: {invalid_labels}")
    reasons = labels["reason"].fillna("").astype(str).str.strip()
    if reasons.eq("").any():
        raise ValueError("reason must be non-empty")
    confidence = labels["confidence"].astype(str).str.strip()
    invalid_confidence = sorted(set(confidence) - CONFIDENCE_LEVELS)
    if invalid_confidence:
        raise ValueError(f"invalid confidence: {invalid_confidence}")
    timestamps = pd.to_datetime(labels["timestamp"], errors="coerce", utc=True)
    if timestamps.isna().any():
        raise ValueError("timestamp must be non-empty and parseable")


def compute_agreement(
    labels_a: pd.DataFrame,
    labels_b: pd.DataFrame,
) -> dict[str, float]:
    """Compute exact case-aligned raw agreement and four-class Cohen's kappa."""
    expected_cases = labels_a["case_id"] if "case_id" in labels_a else []
    validate_reviewer_labels(labels_a, expected_cases)
    validate_reviewer_labels(labels_b, expected_cases)
    aligned = labels_a[["case_id", "label"]].merge(
        labels_b[["case_id", "label"]],
        on="case_id",
        how="inner",
        validate="one_to_one",
        suffixes=("_a", "_b"),
    )
    matches = aligned["label_a"].eq(aligned["label_b"])
    return {
        "case_count": int(len(aligned)),
        "matching_case_count": int(matches.sum()),
        "raw_agreement": float(matches.mean()),
        "cohen_kappa": float(
            cohen_kappa_score(aligned["label_a"], aligned["label_b"])
        ),
    }


def build_adjudicated_labels(
    labels_a: pd.DataFrame,
    labels_b: pd.DataFrame,
    adjudication: pd.DataFrame,
) -> pd.DataFrame:
    """Use agreement directly and require adjudication for exactly disagreements."""
    expected_cases = labels_a["case_id"] if "case_id" in labels_a else []
    validate_reviewer_labels(labels_a, expected_cases)
    validate_reviewer_labels(labels_b, expected_cases)
    paired = labels_a[list(LABEL_COLUMNS)].merge(
        labels_b[list(LABEL_COLUMNS)],
        on="case_id",
        how="inner",
        validate="one_to_one",
        suffixes=("_a", "_b"),
    )
    disagreement_ids = set(
        paired.loc[paired["label_a"].ne(paired["label_b"]), "case_id"].astype(str)
    )
    if "case_id" not in adjudication.columns:
        raise ValueError("adjudication case set mismatch: missing case_id")
    actual_adjudication_ids = set(adjudication["case_id"].astype(str).str.strip())
    if actual_adjudication_ids != disagreement_ids:
        raise ValueError(
            "adjudication case set mismatch: "
            f"missing={sorted(disagreement_ids - actual_adjudication_ids)}, "
            f"extra={sorted(actual_adjudication_ids - disagreement_ids)}"
        )
    validate_reviewer_labels(adjudication, disagreement_ids)
    adjudication_by_case = adjudication.set_index("case_id")

    rows: list[dict[str, object]] = []
    for row in paired.itertuples(index=False):
        if row.label_a == row.label_b:
            rows.append(
                {
                    "case_id": row.case_id,
                    "label": row.label_a,
                    "reason": row.reason_a,
                    "confidence": row.confidence_a,
                    "timestamp": row.timestamp_a,
                    "label_source": "reviewer_agreement",
                }
            )
            continue
        resolved = adjudication_by_case.loc[row.case_id]
        rows.append(
            {
                "case_id": row.case_id,
                "label": resolved["label"],
                "reason": resolved["reason"],
                "confidence": resolved["confidence"],
                "timestamp": resolved["timestamp"],
                "label_source": "third_party_adjudication",
            }
        )
    return pd.DataFrame(
        rows,
        columns=[*LABEL_COLUMNS, "label_source"],
    )


def _safe_probability(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else float("nan")


def _sample_odds_ratio(table: list[list[int]]) -> float:
    numerator = int(table[0][0]) * int(table[1][1])
    denominator = int(table[0][1]) * int(table[1][0])
    if denominator == 0:
        return float("inf") if numerator else float("nan")
    return float(numerator / denominator)


def _compute_primary_statistics(
    joined: pd.DataFrame,
    *,
    require_both_groups: bool,
) -> dict[str, object]:
    required = {"case_id", "label", "aggregate_r"}
    missing = sorted(required - set(joined.columns))
    if missing:
        raise ValueError(f"joined data missing columns: {missing}")
    case_ids = joined["case_id"].astype(str).str.strip()
    if case_ids.eq("").any() or case_ids.duplicated().any():
        raise ValueError("joined case_id must be non-empty and unique")
    labels = joined["label"].astype(str).str.strip()
    invalid_labels = sorted(set(labels) - LABELS)
    if invalid_labels:
        raise ValueError(f"invalid label: {invalid_labels}")

    frame = joined.copy()
    frame["aggregate_r"] = pd.to_numeric(frame["aggregate_r"], errors="coerce")
    frame = frame[
        frame["label"].ne("insufficient")
        & np.isfinite(frame["aggregate_r"])
    ].copy()
    frame["signal_positive"] = frame["label"].eq("trend_same_direction")
    frame["outcome_ge_2r"] = frame["aggregate_r"].ge(2.0)
    positive = frame[frame["signal_positive"]]
    negative = frame[~frame["signal_positive"]]
    if require_both_groups and (positive.empty or negative.empty):
        raise ValueError("primary analysis requires both signal-positive and negative cases")

    table = [
        [int(positive["outcome_ge_2r"].sum()), int((~positive["outcome_ge_2r"]).sum())],
        [int(negative["outcome_ge_2r"].sum()), int((~negative["outcome_ge_2r"]).sum())],
    ]
    positive_rate = _safe_probability(table[0][0], sum(table[0]))
    negative_rate = _safe_probability(table[1][0], sum(table[1]))
    fisher = fisher_exact(table, alternative="two-sided")
    conditional = odds_ratio(table, kind="conditional")
    interval = conditional.confidence_interval(0.95)
    return {
        "analyzable_case_count": int(len(frame)),
        "signal_positive_case_count": int(len(positive)),
        "signal_negative_case_count": int(len(negative)),
        "contingency_table": table,
        "signal_positive_ge_2r_probability": positive_rate,
        "signal_negative_ge_2r_probability": negative_rate,
        "risk_difference": float(positive_rate - negative_rate),
        "sample_odds_ratio": _sample_odds_ratio(table),
        "conditional_odds_ratio": float(conditional.statistic),
        "conditional_odds_ratio_ci95_lower": float(interval.low),
        "conditional_odds_ratio_ci95_upper": float(interval.high),
        "fisher_exact_two_sided_pvalue": float(fisher.pvalue),
        "signal_positive_median_aggregate_r": float(positive["aggregate_r"].median()),
        "signal_negative_median_aggregate_r": float(negative["aggregate_r"].median()),
        "signal_positive_profit_probability": float(positive["aggregate_r"].gt(0).mean()),
        "signal_negative_profit_probability": float(negative["aggregate_r"].gt(0).mean()),
    }


def compute_primary_statistics(joined: pd.DataFrame) -> dict[str, object]:
    """Compute the single frozen 2R/trend-same-direction primary analysis."""
    return _compute_primary_statistics(joined, require_both_groups=True)


def compute_leave_one_out(
    joined: pd.DataFrame,
    group_column: str,
) -> pd.DataFrame:
    """Recompute frozen primary statistics after removing each named group once."""
    if group_column not in joined.columns:
        raise ValueError(f"joined data missing group column: {group_column}")
    frame = joined.copy()
    frame["aggregate_r"] = pd.to_numeric(frame["aggregate_r"], errors="coerce")
    frame = frame[
        frame["label"].astype(str).ne("insufficient")
        & np.isfinite(frame["aggregate_r"])
    ].copy()
    if frame[group_column].isna().any():
        raise ValueError(f"group column contains missing values: {group_column}")
    counts = frame[group_column].value_counts(dropna=False)
    if counts.empty:
        raise ValueError("leave-one-out requires at least one analyzable group")
    maximum_frequency = int(counts.max())
    tied = sorted(
        [group for group, count in counts.items() if int(count) == maximum_frequency],
        key=lambda value: str(value),
    )
    selected_highest = tied[0]
    tie_evidence = (
        f"frequency={maximum_frequency};tie_break=ascending_group_name"
        if len(tied) > 1
        else f"frequency={maximum_frequency};unique_highest_frequency"
    )

    rows: list[dict[str, object]] = []
    for group in sorted(counts.index.tolist(), key=lambda value: str(value)):
        remaining = frame[frame[group_column].ne(group)].copy()
        metrics = _compute_primary_statistics(remaining, require_both_groups=False)
        rows.append(
            {
                "group_column": group_column,
                "excluded_group": group,
                "excluded_count": int(counts.loc[group]),
                "remaining_case_count": int(len(remaining)),
                "selected_highest_frequency": bool(group == selected_highest),
                "selection_evidence": tie_evidence if group == selected_highest else "not_selected",
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _table_effects(table: list[list[int]]) -> dict[str, object]:
    positive_rate = _safe_probability(table[0][0], sum(table[0]))
    negative_rate = _safe_probability(table[1][0], sum(table[1]))
    conditional = odds_ratio(table, kind="conditional")
    return {
        "contingency_table": table,
        "risk_difference": float(positive_rate - negative_rate),
        "sample_odds_ratio": _sample_odds_ratio(table),
        "conditional_odds_ratio": float(conditional.statistic),
    }


def compute_gap_bounds(
    joined: pd.DataFrame,
    unresolved: pd.DataFrame,
) -> dict[str, object]:
    """Assign every unresolved case to each frozen signal/outcome cell in turn."""
    base_table = compute_primary_statistics(joined)["contingency_table"]
    unresolved_count = int(len(unresolved))
    assignments = [
        ("signal_positive__outcome_ge_2r", 0, 0),
        ("signal_positive__outcome_lt_2r", 0, 1),
        ("signal_negative__outcome_ge_2r", 1, 0),
        ("signal_negative__outcome_lt_2r", 1, 1),
    ]
    scenarios: list[dict[str, object]] = []
    for assignment, row_index, column_index in assignments:
        table = [list(base_table[0]), list(base_table[1])]
        table[row_index][column_index] += unresolved_count
        effects = _table_effects(table)
        scenarios.append(
            {
                "assignment": assignment,
                **effects,
                "direction_positive": bool(
                    effects["risk_difference"] > 0
                    and effects["conditional_odds_ratio"] > 1
                ),
            }
        )
    most_favorable = max(
        scenarios,
        key=lambda scenario: (
            float(scenario["risk_difference"]),
            float(scenario["conditional_odds_ratio"]),
        ),
    )
    most_adverse = min(
        scenarios,
        key=lambda scenario: (
            float(scenario["risk_difference"]),
            float(scenario["conditional_odds_ratio"]),
        ),
    )
    return {
        "unresolved_case_count": unresolved_count,
        "base_contingency_table": base_table,
        "scenarios": scenarios,
        "most_favorable": most_favorable,
        "most_adverse": most_adverse,
        "worst_case_direction_preserved": bool(most_adverse["direction_positive"]),
    }


def _gate(
    name: str,
    value: object,
    threshold: str,
    passed: bool,
    evidence: str,
) -> dict[str, object]:
    return {
        "name": name,
        "value": value,
        "threshold": threshold,
        "passed": bool(passed),
        "evidence": evidence,
    }


def evaluate_decision(
    metrics: dict[str, object],
    agreement: dict[str, float],
    year_loo: pd.DataFrame,
    product_loo: pd.DataFrame,
    gap_bounds: dict[str, object],
) -> dict[str, object]:
    """Apply the two reliability, eight primary, and one gap gate without search."""
    year_odds = pd.to_numeric(year_loo.get("conditional_odds_ratio"), errors="coerce")
    selected_product = product_loo[
        product_loo.get(
            "selected_highest_frequency",
            pd.Series(False, index=product_loo.index),
        ).astype(bool)
    ]
    selected_product_odds = (
        float(selected_product.iloc[0]["conditional_odds_ratio"])
        if len(selected_product) == 1
        else float("nan")
    )
    minimum_year_odds = float(year_odds.min()) if not year_odds.empty else float("nan")

    reliability_gates = [
        _gate(
            "raw_agreement_at_least_0_80",
            float(agreement["raw_agreement"]),
            ">= 0.80",
            float(agreement["raw_agreement"]) >= 0.80,
            "raw matching cases divided by all independently reviewed cases",
        ),
        _gate(
            "cohen_kappa_at_least_0_60",
            float(agreement["cohen_kappa"]),
            ">= 0.60",
            float(agreement["cohen_kappa"]) >= 0.60,
            "four-label case-aligned Cohen's kappa",
        ),
    ]
    primary_effect_gates = [
        _gate(
            "ge_2r_probability_lift_at_least_0_15",
            float(metrics["risk_difference"]),
            ">= 0.15",
            float(metrics["risk_difference"]) >= 0.15,
            "P(aggregate_r>=2|same-direction) minus P(aggregate_r>=2|other)",
        ),
        _gate(
            "conditional_odds_ratio_above_2",
            float(metrics["conditional_odds_ratio"]),
            "> 2",
            float(metrics["conditional_odds_ratio"]) > 2.0,
            f"sample_odds_ratio={metrics['sample_odds_ratio']}",
        ),
        _gate(
            "two_sided_fisher_p_below_0_05",
            float(metrics["fisher_exact_two_sided_pvalue"]),
            "< 0.05",
            float(metrics["fisher_exact_two_sided_pvalue"]) < 0.05,
            "two-sided Fisher exact test on the frozen 2x2 table",
        ),
        _gate(
            "conditional_odds_ratio_ci95_lower_above_1",
            float(metrics["conditional_odds_ratio_ci95_lower"]),
            "> 1",
            float(metrics["conditional_odds_ratio_ci95_lower"]) > 1.0,
            f"upper={metrics['conditional_odds_ratio_ci95_upper']}",
        ),
        _gate(
            "same_direction_median_r_above_other",
            float(metrics["signal_positive_median_aggregate_r"]),
            f"> {metrics['signal_negative_median_aggregate_r']}",
            float(metrics["signal_positive_median_aggregate_r"])
            > float(metrics["signal_negative_median_aggregate_r"]),
            f"other_median={metrics['signal_negative_median_aggregate_r']}",
        ),
        _gate(
            "same_direction_profit_probability_above_other",
            float(metrics["signal_positive_profit_probability"]),
            f"> {metrics['signal_negative_profit_probability']}",
            float(metrics["signal_positive_profit_probability"])
            > float(metrics["signal_negative_profit_probability"]),
            f"other_probability={metrics['signal_negative_profit_probability']}",
        ),
    ]
    stability_gates = [
        _gate(
            "every_year_leave_one_out_odds_ratio_above_1",
            minimum_year_odds,
            "> 1 for every omitted year",
            bool(not year_odds.empty and year_odds.notna().all() and (year_odds > 1).all()),
            f"omitted_year_count={len(year_loo)};minimum_odds_ratio={minimum_year_odds}",
        ),
        _gate(
            "highest_frequency_product_leave_one_out_direction_positive",
            selected_product_odds,
            "> 1 after one deterministic highest-frequency product removal",
            bool(np.isfinite(selected_product_odds) and selected_product_odds > 1),
            (
                f"selected_rows={len(selected_product)};"
                f"excluded_product={selected_product.iloc[0]['excluded_group'] if len(selected_product) == 1 else 'invalid'}"
            ),
        ),
    ]
    gap_gate = _gate(
        "worst_case_gap_direction_preserved",
        bool(gap_bounds["worst_case_direction_preserved"]),
        "is true",
        bool(gap_bounds["worst_case_direction_preserved"]),
        f"most_adverse={gap_bounds.get('most_adverse', {})}",
    )
    gates = [*reliability_gates, *primary_effect_gates, *stability_gates, gap_gate]

    if not all(gate["passed"] for gate in reliability_gates):
        decision = "visual_definition_not_reproducible"
    elif not gap_gate["passed"]:
        decision = "insufficient_data"
    elif not all(gate["passed"] for gate in primary_effect_gates):
        decision = "reject_signal"
    elif not all(gate["passed"] for gate in stability_gates):
        decision = "attribution_only"
    else:
        decision = "eligible_for_numeric_rule_translation"
    return {
        "decision": decision,
        "all_gates_passed": bool(all(gate["passed"] for gate in gates)),
        "gates": gates,
    }


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if np.isfinite(number) else None
    return value


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(_json_safe(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def reveal(output_dir: Path = OUTPUT_DIR) -> dict[str, object]:
    """Load only frozen named artifacts, reveal once, and write machine decisions."""
    output_dir = Path(output_dir)
    paths = {
        "reviewer_a": output_dir / "reviewer_a_labels.csv",
        "reviewer_b": output_dir / "reviewer_b_labels.csv",
        "adjudication": output_dir / "adjudication_labels.csv",
        "reviewer_manifest": output_dir / "reviewer_manifest.csv",
        "mapping": output_dir / "blind_mapping.csv",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing frozen reveal inputs: {missing}")

    labels_a = pd.read_csv(paths["reviewer_a"])
    labels_b = pd.read_csv(paths["reviewer_b"])
    adjudication = pd.read_csv(paths["adjudication"])
    reviewer_manifest = pd.read_csv(paths["reviewer_manifest"])
    mapping = pd.read_csv(paths["mapping"])
    expected_cases = reviewer_manifest["case_id"]
    validate_reviewer_labels(labels_a, expected_cases)
    validate_reviewer_labels(labels_b, expected_cases)
    agreement = compute_agreement(labels_a, labels_b)
    adjudicated = build_adjudicated_labels(labels_a, labels_b, adjudication)

    if "case_id" not in mapping.columns or mapping["case_id"].astype(str).duplicated().any():
        raise ValueError("blind mapping requires unique case_id")
    missing_mapping = set(adjudicated["case_id"].astype(str)) - set(
        mapping["case_id"].astype(str)
    )
    if missing_mapping:
        raise ValueError(f"adjudicated cases missing from blind mapping: {sorted(missing_mapping)}")
    joined_all = mapping.merge(
        adjudicated,
        on="case_id",
        how="left",
        validate="one_to_one",
    )
    joined_all["aggregate_r"] = pd.to_numeric(
        joined_all["aggregate_r"], errors="coerce"
    )
    if "entry_year" not in joined_all.columns and "entry_date" in joined_all.columns:
        joined_all["entry_year"] = pd.to_datetime(
            joined_all["entry_date"], errors="coerce"
        ).dt.year
    if "vt_symbol" not in joined_all.columns:
        raise ValueError("blind mapping missing vt_symbol for product robustness")
    joined_all["product"] = (
        joined_all["vt_symbol"].astype(str).str.extract(r"^([A-Za-z]+)", expand=False)
    )
    if joined_all["product"].isna().any():
        raise ValueError("cannot derive product from vt_symbol")

    analyzable_mask = (
        joined_all["label"].notna()
        & joined_all["label"].ne("insufficient")
        & np.isfinite(joined_all["aggregate_r"])
    )
    joined = joined_all.loc[analyzable_mask].copy()
    unresolved = joined_all.loc[~analyzable_mask].copy()
    primary = compute_primary_statistics(joined)
    year_loo = compute_leave_one_out(joined, "entry_year")
    product_loo = compute_leave_one_out(joined, "product")
    gap_bounds = compute_gap_bounds(joined, unresolved)
    decision = evaluate_decision(
        primary,
        agreement,
        year_loo,
        product_loo,
        gap_bounds,
    )

    adjudicated.to_csv(output_dir / "adjudicated_labels.csv", index=False)
    year_loo.to_csv(output_dir / "year_leave_one_out.csv", index=False)
    product_loo.to_csv(output_dir / "product_leave_one_out.csv", index=False)
    _write_json(output_dir / "agreement.json", agreement)
    _write_json(output_dir / "primary_statistics.json", primary)
    _write_json(output_dir / "gap_bounds.json", gap_bounds)
    _write_json(output_dir / "decision.json", decision)
    return {
        "agreement": agreement,
        "adjudicated_labels": adjudicated,
        "primary_statistics": primary,
        "year_leave_one_out": year_loo,
        "product_leave_one_out": product_loo,
        "gap_bounds": gap_bounds,
        "decision": decision,
    }
