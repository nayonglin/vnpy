"""Stage256 pure adapter checks; never starts the backtest engine."""
from __future__ import annotations

import csv
import hashlib
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path

from stage256_run_account import account_kind, adapted_stage251, validate_registry_account, validate_pool_rows


EVAL_DATES = ["2024-12-31", "2025-01-27"]
UNIVERSE = [f"p{i:02d}.X" for i in range(18)]
FIXED = "fu.SHFE"


def pool_rows(strategy="stage256_random_monthly_v1"):
    rows = []
    for evaluation in EVAL_DATES:
        for rank, product in enumerate([*UNIVERSE[:10], FIXED], 1):
            rows.append({"strategy": strategy, "score_type": "stage256_schema_order",
                         "eval_date": evaluation, "product_vt_symbol": product,
                         "score": "0", "score_rank": str(rank), "top_n": "11"})
    return rows


class Stage256AdapterTest(unittest.TestCase):
    def test_pool_accepts_equal_width_snapshots(self):
        result = validate_pool_rows(pool_rows(), "stage256_random_monthly_v1", EVAL_DATES, UNIVERSE)
        self.assertEqual(result["selected_eval_dates"], EVAL_DATES)
        self.assertEqual(result["selected_snapshot_count"], 2)

    def test_pool_rejects_broken_width_rank_universe_or_score(self):
        changes = [lambda rows: rows.pop(),
                   lambda rows: rows.__setitem__(10, {**rows[10], "score_rank": "10"}),
                   lambda rows: rows.__setitem__(0, {**rows[0], "product_vt_symbol": "outside.X"}),
                   lambda rows: rows.__setitem__(0, {**rows[0], "score": "nan"})]
        for change in changes:
            rows = pool_rows()
            change(rows)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_pool_rows(rows, "stage256_random_monthly_v1", EVAL_DATES, UNIVERSE)

    def test_account_ids_are_frozen(self):
        self.assertEqual(account_kind("AI_MONTHLY"), "ai_monthly")
        self.assertEqual(account_kind("AI_INITIAL_FIXED"), "ai_initial_fixed")
        self.assertEqual(account_kind("RANDOM_199"), "random_monthly")
        for invalid in ("RANDOM_000", "RANDOM_200", "RANDOM_1", "OTHER"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                account_kind(invalid)

    def test_registry_rejects_pool_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            pool = Path(directory) / "pool.csv"
            with pool.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=pool_rows()[0])
                writer.writeheader()
                writer.writerows(pool_rows())
            registry = {"start": "2025-01-01", "end": "2026-10-14",
                        "expected_eval_dates": EVAL_DATES, "non_fu_universe": UNIVERSE,
                        "accounts": {"RANDOM_001": {"pool_file": str(pool.resolve()),
                                                    "pool_sha256": "0" * 64,
                                                    "policy_id": "stage256_random_monthly_v1",
                                                    "kind": "random_monthly", "path_id": 1}}}
            with self.assertRaisesRegex(ValueError, "pool_sha256"):
                validate_registry_account(registry, "RANDOM_001", pool)
            registry["accounts"]["RANDOM_001"]["pool_sha256"] = hashlib.sha256(pool.read_bytes()).hexdigest()
            validated = validate_registry_account(registry, "RANDOM_001", pool)
            self.assertEqual(validated["policy_id"], "stage256_random_monthly_v1")

    def test_only_declared_flags_pool_and_exact_reference_are_adapted_then_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reference = root / "accepted_A_parameters.json"
            other = root / "other.json"
            payload = {"spec": {"overrides": {"enable_stage847_half_r_stop_retry": True,
                                                 "ai_product_pool_strategy": "ai_top10_plus_fu_official_live_v1",
                                                 "ai_product_pool_eligibility_path": "/official.csv"}}}
            reference.write_text(__import__("json").dumps(payload))
            other.write_text(__import__("json").dumps(payload))
            pool = root / "random.csv"
            pool.write_text("frozen")
            original_build = lambda: {"enable_stage847_half_r_stop_retry": True,
                                      "enable_ai_product_pool_filter": True,
                                      "ai_product_pool_strategy": "ai_top10_plus_fu_official_live_v1",
                                      "ai_product_pool_eligibility_path": "/official.csv", "risk_multiplier": 0.4}
            s901 = SimpleNamespace(build_official_live_strategy_overrides=original_build)
            stage251 = SimpleNamespace(declared_ablation=lambda *_: None,
                                       audit_historical_ai_pool=lambda *_: {"status": "valid", "eligibility_sha256": "official"})
            old_declared, old_audit = stage251.declared_ablation, stage251.audit_historical_ai_pool
            baseline = root / "baseline"
            with adapted_stage251(stage251, pool, "stage256_random_monthly_v1", reference,
                                  EVAL_DATES, {"all_snapshot_count": 58, "all_eval_dates": EVAL_DATES},
                                  root, baseline):
                with stage251.declared_ablation(s901, "C"):
                    changed = s901.build_official_live_strategy_overrides()
                    self.assertIs(changed["enable_stage847_half_r_stop_retry"], False)
                    self.assertEqual(changed["risk_multiplier"], 0.4)
                    self.assertEqual(changed["ai_product_pool_eligibility_path"], str(pool))
                self.assertIs(s901.build_official_live_strategy_overrides, original_build)
                altered = __import__("json").loads(reference.read_text())
                untouched = __import__("json").loads(other.read_text())
                self.assertEqual(altered["spec"]["overrides"]["ai_product_pool_strategy"], "stage256_random_monthly_v1")
                self.assertEqual(altered["spec"]["overrides"]["ai_product_pool_eligibility_path"], str(baseline.resolve() / "random.csv"))
                self.assertEqual(untouched, payload)
                self.assertEqual(stage251.audit_historical_ai_pool(pool, EVAL_DATES)["strategy"], "stage256_random_monthly_v1")
                with self.assertRaisesRegex(ValueError, "required_eval_dates_drift"):
                    stage251.audit_historical_ai_pool(pool, EVAL_DATES[:1])
            self.assertIs(stage251.declared_ablation, old_declared)
            self.assertIs(stage251.audit_historical_ai_pool, old_audit)
            self.assertEqual(__import__("json").loads(reference.read_text()), payload)


if __name__ == "__main__":
    unittest.main()
