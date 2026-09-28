"""Independently verify saved attribution artifacts using standard-library arithmetic."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path


OUT = Path(__file__).resolve().parents[1] / "artifacts/stage001_20260731"
PROB = "predicted_product_suitability_probability"


def rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close(a: float, b: float, tolerance: float = 1e-12) -> None:
    assert math.isfinite(a) and math.isfinite(b)
    assert abs(a - b) <= tolerance, (a, b, abs(a - b))


def main() -> None:
    summary = json.loads((OUT / "reproduction_summary.json").read_text())
    model = json.loads((OUT / "model_snapshot.json").read_text())
    for name, record in summary["source_identities"].items():
        assert sha(Path(name)) == record["sha256"], name
    score_rows = rows(OUT / "product_scores_and_features.csv")
    scores = {r["product_vt_symbol"]: r for r in score_rows}
    detail = rows(OUT / "feature_contributions.csv")
    assert len(detail) == 18 * 108
    features = model["features"]
    feature_index = {f: i for i, f in enumerate(features)}
    assert len(feature_index) == 108
    seen = set()
    contributions = defaultdict(list)
    matrix = {}
    for row in detail:
        product, feature = row["product_vt_symbol"], row["feature"]
        assert (product, feature) not in seen
        seen.add((product, feature))
        i = feature_index[feature]
        x = float(scores[product][feature])
        expected_z = (x - model["scaler_mean"][i]) / model["scaler_scale"][i]
        value = expected_z * model["coefficients"][i]
        close(x, float(row["raw_value"]))
        close(model["scaler_mean"][i], float(row["training_mean"]))
        close(model["scaler_scale"][i], float(row["training_scale"]))
        close(expected_z, float(row["standardized_value"]))
        close(model["coefficients"][i], float(row["coefficient"]))
        close(value, float(row["contribution_log_odds"]))
        contributions[product].append(value)
        matrix[(product, feature)] = value
    probability_errors = []
    for product, values in contributions.items():
        assert len(values) == 108
        logit = model["intercept"] + math.fsum(values)
        probability = 1.0 / (1.0 + math.exp(-logit))
        expected = float(scores[product][PROB])
        probability_errors.append(abs(probability - expected))
        close(probability, expected)
        close(logit, float(scores[product]["decision_log_odds"]))
        close(math.fsum(v for v in values if v > 0), float(scores[product]["positive_contribution_sum"]))
        close(math.fsum(v for v in values if v < 0), float(scores[product]["negative_contribution_sum"]))
    official_path = next(Path(p) for p in summary["source_identities"] if "m0004_" in p and p.endswith("latest_pool.csv"))
    official = rows(official_path)
    ranked = sorted(scores, key=lambda p: (-float(scores[p][PROB]), -float(scores[p]["simple_trend_suitability_score"]), p))
    non_fixed = sorted([r for r in official if r["selection_role"] == "model_ranked"], key=lambda r: int(r["ai_rank"]))
    assert ranked[:10] == [r["product_vt_symbol"] for r in non_fixed]
    for row in non_fixed:
        close(float(row[PROB]), float(scores[row["product_vt_symbol"]][PROB]), 1e-10)
    assert "fu.SHFE" not in scores
    fixed = [r for r in official if r["selection_role"] == "fixed_fu"]
    assert len(fixed) == 1 and int(fixed[0]["ai_rank"]) == 11
    close(float(fixed[0][PROB]), float(non_fixed[-1][PROB]) - 1e-6)
    pairs = rows(OUT / "adjacent_rank_contributions.csv")
    assert len(pairs) == 17 * 108
    pair_sums = defaultdict(list)
    pair_seen = set()
    for row in pairs:
        high, low, feature = row["higher_product"], row["lower_product"], row["feature"]
        assert (high, low, feature) not in pair_seen
        pair_seen.add((high, low, feature))
        value = matrix[(high, feature)] - matrix[(low, feature)]
        close(value, float(row["contribution_difference_log_odds"]))
        pair_sums[(high, low)].append(value)
    for (high, low), values in pair_sums.items():
        assert len(values) == 108
        assert int(scores[low]["model_rank"]) == int(scores[high]["model_rank"]) + 1
        close(math.fsum(values), float(scores[high]["decision_log_odds"]) - float(scores[low]["decision_log_odds"]))
    groups = defaultdict(list)
    for row in rows(OUT / "factor_group_contributions.csv"):
        groups[row["product_vt_symbol"]].append(float(row["contribution_log_odds"]))
    for product, values in groups.items():
        assert len(values) == 7
        close(math.fsum(values), math.fsum(contributions[product]))
    assert set(groups) == set(scores)
    result = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "pass", "method": "standard_library_csv_math_fsum_no_sklearn_no_training",
        "verified_feature_rows": len(detail), "verified_adjacent_rows": len(pairs),
        "independent_max_probability_error": max(probability_errors),
        "production_source_hashes_unchanged": True, "official_top10_scores_and_order_match": True,
        "artifact_hashes": {p.name: sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "verification.json"},
    }
    (OUT / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "artifact_hashes"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
