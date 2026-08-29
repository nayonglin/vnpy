from __future__ import annotations

import inspect
import hashlib
import json
from argparse import Namespace
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import build_qmt_roll_stage182_ai_product_pool_live_inference_runner as stage182  # noqa: E402
import build_qmt_roll_stage183_ai_product_pool_source_refresh as stage183  # noqa: E402
from qmt_roll_ai_artifact_registry import load_publication_request  # noqa: E402
from qmt_roll_official_ai_pool_policy import (  # noqa: E402
    OFFICIAL_AI_FIXED_PRODUCT,
    OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
    OFFICIAL_AI_RANKED_PRODUCT_COUNT,
    OFFICIAL_AI_TOTAL_PRODUCT_COUNT,
)
import run_qmt_roll_stage935_official_live_monthly_ai_pool_update as stage935  # noqa: E402


class Stage935AiPoolPathConsistencyTest(unittest.TestCase):
    SOURCE_PREFIX = "qmt_roll_stage183_ai_source_floor35"

    def _write_stage182_sources(self, root: Path, max_date: str) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{self.SOURCE_PREFIX}_position_changes_2020_2026_04.csv").write_text(
            "date,vt_symbol,start_pos,end_pos,pos_change\n"
            f"{max_date},rb2610.SHFE,0,0,0\n",
            encoding="utf-8",
        )
        (root / f"{self.SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv").write_text(
            "date,product_vt_symbol,candidate_status\n"
            f"{max_date},rb.SHFE,rejected\n",
            encoding="utf-8",
        )

    def _stage183_summary(
        self,
        root: Path,
        *,
        daily_date: str = "2026-08-03",
        position_date: str = "2026-08-03",
        candidate_date: str = "2026-07-31",
    ) -> dict[str, object]:
        root.mkdir(parents=True, exist_ok=True)
        daily = root / f"{self.SOURCE_PREFIX}_daily.csv"
        position = root / f"{self.SOURCE_PREFIX}_position_changes_2020_2026_04.csv"
        candidate = root / f"{self.SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
        daily.write_text(
            f"date,balance\n{daily_date},200000\n",
            encoding="utf-8",
        )
        position.write_text(
            f"date,vt_symbol,end_pos\n{position_date},rb2610.SHFE,0\n",
            encoding="utf-8",
        )
        candidate.write_text(
            "date,product_vt_symbol,candidate_status\n"
            f"{candidate_date},rb.SHFE,rejected\n",
            encoding="utf-8",
        )
        artifact_paths = {
            "daily": daily,
            "position_changes": position,
            "entry_candidate_snapshots": candidate,
        }
        artifact_identities = {
            name: {
                "size": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for name, path in artifact_paths.items()
        }
        return {
            "analysis_end": "2026-08-03",
            "source_prefix": self.SOURCE_PREFIX,
            "artifact_root": str(root),
            "artifact_dates": {
                "daily_max_date": daily_date,
                "position_changes_max_date": position_date,
                "entry_candidate_snapshots_max_date": candidate_date,
            },
            "artifact_identities": artifact_identities,
            "outputs": {
                "daily": str(daily),
                "position_changes": str(position),
                "entry_candidate_snapshots": str(candidate),
            },
            "safety": {
                "overwrites_official_stage78_eligibility": False,
                "real_order_enabled": False,
            },
        }

    def _stage182_bundle_paths(self, root: Path) -> dict[str, Path]:
        return {
            "live_pool": root / stage182.LIVE_POOL_PATH.name,
            "live_eligibility": root / stage182.LIVE_ELIGIBILITY_PATH.name,
            "combined_eligibility": root / stage182.COMBINED_ELIGIBILITY_PATH.name,
            "summary": root / stage182.SUMMARY_PATH.name,
            "report": root / stage182.REPORT_PATH.name,
        }

    def _write_stage182_bundle(
        self,
        paths: dict[str, Path],
        marker: str,
    ) -> None:
        for name, path in paths.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{name}:{marker}\n", encoding="utf-8")

    def test_stage182_live_eligibility_selects_top10_non_fu_plus_fixed_fu(self) -> None:
        scored = pd.DataFrame(
            {
                "product_vt_symbol": [
                    OFFICIAL_AI_FIXED_PRODUCT,
                    *[
                        f"p{index}.TEST"
                        for index in range(1, OFFICIAL_AI_RANKED_PRODUCT_COUNT + 3)
                    ],
                ],
                stage182.PROBABILITY_COLUMN: [
                    0.99,
                    *[
                        0.90 - index * 0.01
                        for index in range(1, OFFICIAL_AI_RANKED_PRODUCT_COUNT + 3)
                    ],
                ],
                stage182.SIMPLE_SCORE_COLUMN: [
                    99.0,
                    *[
                        90.0 - index
                        for index in range(1, OFFICIAL_AI_RANKED_PRODUCT_COUNT + 3)
                    ],
                ],
            }
        )

        eligibility = stage182._build_live_eligibility(
            scored,
            pd.Timestamp("2026-07-31"),
        )

        self.assertEqual(OFFICIAL_AI_TOTAL_PRODUCT_COUNT, len(eligibility))
        self.assertEqual(
            [
                *[
                    f"p{index}.TEST"
                    for index in range(1, OFFICIAL_AI_RANKED_PRODUCT_COUNT + 1)
                ],
                OFFICIAL_AI_FIXED_PRODUCT,
            ],
            eligibility["product_vt_symbol"].tolist(),
        )
        self.assertEqual(
            list(range(1, OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1)),
            eligibility["score_rank"].tolist(),
        )
        self.assertEqual(
            {OFFICIAL_AI_TOTAL_PRODUCT_COUNT},
            set(eligibility["top_n"].tolist()),
        )
        self.assertEqual(
            {OFFICIAL_AI_PRODUCT_POOL_STRATEGY},
            set(eligibility["strategy"].tolist()),
        )

        published = stage182._build_published_live_pool(scored, eligibility)
        self.assertEqual(OFFICIAL_AI_TOTAL_PRODUCT_COUNT, len(published))
        self.assertEqual(
            list(range(1, OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1)),
            published["ai_rank"].tolist(),
        )
        self.assertEqual(
            [OFFICIAL_AI_PRODUCT_POOL_STRATEGY],
            published["strategy"].drop_duplicates().tolist(),
        )
        self.assertEqual(
            OFFICIAL_AI_FIXED_PRODUCT,
            published.iloc[-1]["product_vt_symbol"],
        )
        self.assertEqual("fixed_fu", published.iloc[-1]["selection_role"])

    def test_stage182_report_uses_official_top10_plus_fu_strategy(self) -> None:
        summary = {
            "generated_at": "2026-08-30T09:15:00+08:00",
            "eval_date": "2026-07-31",
            "source_max_date": "2026-08-03",
            "source_paths": {"source_prefix": "stage183-source"},
            "training_label_cutoff": "2026-05-07",
            "train_rows": 100,
            "feature_count": 10,
            "live_rows": 11,
        }
        live_pool = pd.DataFrame(
            columns=[
                "ai_rank",
                "product_vt_symbol",
                stage182.PROBABILITY_COLUMN,
                stage182.SIMPLE_SCORE_COLUMN,
            ]
        )
        live_eligibility = pd.DataFrame(
            columns=[
                "eval_date",
                "product_vt_symbol",
                "score",
                "score_rank",
                "top_n",
                "score_type",
            ]
        )

        report = stage182.build_report(summary, live_pool, live_eligibility)

        self.assertIn(
            f"Strategy: `{OFFICIAL_AI_PRODUCT_POOL_STRATEGY}`",
            report,
        )
        self.assertNotIn("ai_top8", report.lower())

    def test_stage935_success_writes_material_request_without_git_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            artifacts = self._stage182_bundle_paths(root / "canonical")
            self._write_stage182_bundle(artifacts, "candidate")
            with (
                patch.object(stage935, "CONTROL_OUTPUT_DIR", root / "control"),
                patch.object(
                    stage935,
                    "_current_source_commit",
                    side_effect=AssertionError("explicit commit means no Git lookup"),
                ),
            ):
                request_path = stage935._write_material_publication_request(
                    artifacts=artifacts,
                    eval_date="2026-07-31",
                    source_max_date="2026-08-03",
                    training_label_cutoff="2026-05-07",
                    source_commit="d6080c914ae9884eaa984618f37f18022ef5e058",
                )
            payload = load_publication_request(request_path)

        self.assertEqual("official_candidate", payload["promotion_scope"])
        self.assertEqual(5, len(payload["ai_artifacts"]))
        self.assertEqual(0, payload["order_api_called_count"])

    def test_stage183_artifact_paths_use_real_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control_root = Path(directory).resolve() / "control"
            control_root.mkdir()

            build_paths = getattr(stage183, "_build_artifact_paths", None)
            self.assertTrue(
                callable(build_paths),
                "Stage183 must expose runtime-root artifact path construction",
            )
            paths = build_paths(
                source_prefix=self.SOURCE_PREFIX,
                artifact_root=control_root,
            )

        self.assertEqual(
            control_root,
            paths["position_changes"].resolve().parent,
        )
        self.assertEqual(
            control_root,
            paths["entry_candidate_snapshots"].resolve().parent,
        )

    def test_stage183_sparse_candidate_date_is_not_daily_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control_root = Path(directory).resolve() / "control"
            control_root.mkdir()
            paths = stage183._build_artifact_paths(self.SOURCE_PREFIX, control_root)
            paths["daily"].write_text(
                "date,balance\n2026-08-03,200000\n",
                encoding="utf-8",
            )
            paths["position_changes"].write_text(
                "date,vt_symbol,end_pos\n2026-08-03,rb2610.SHFE,0\n",
                encoding="utf-8",
            )
            paths["entry_candidate_snapshots"].write_text(
                "date,product_vt_symbol,candidate_status\n"
                "2026-07-31,rb.SHFE,rejected\n",
                encoding="utf-8",
            )

            collect_dates = getattr(stage183, "_collect_artifact_dates", None)
            self.assertTrue(
                callable(collect_dates),
                "Stage183 must expose artifact-date collection for source validation",
            )
            dates = collect_dates(paths)

        self.assertEqual("2026-08-03", dates["daily_max_date"])
        self.assertEqual("2026-08-03", dates["position_changes_max_date"])
        self.assertEqual(
            "2026-07-31",
            dates["entry_candidate_snapshots_max_date"],
        )

    def test_stage183_records_source_file_content_identities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control_root = Path(directory).resolve() / "control"
            summary = self._stage183_summary(control_root)
            paths = {
                name: Path(path)
                for name, path in summary["outputs"].items()
            }
            collect_identities = getattr(stage183, "_collect_artifact_identities", None)
            self.assertTrue(
                callable(collect_identities),
                "Stage183 must bind source evidence to file bytes",
            )
            identities = collect_identities(paths)
            for name, identity in identities.items():
                source = paths[name]
                self.assertEqual(source.stat().st_size, identity["size"])
                self.assertEqual(source.stat().st_mtime_ns, identity["mtime_ns"])
                self.assertEqual(
                    hashlib.sha256(source.read_bytes()).hexdigest(),
                    identity["sha256"],
                )

    def test_stage182_source_dir_does_not_fall_back_to_stale_data_root(self) -> None:
        original_position_changes = stage182.suitability.POSITION_CHANGES_PATH
        original_entry_snapshots = stage182.suitability.ENTRY_SNAPSHOTS_PATH
        self.addCleanup(
            setattr,
            stage182.suitability,
            "POSITION_CHANGES_PATH",
            original_position_changes,
        )
        self.addCleanup(
            setattr,
            stage182.suitability,
            "ENTRY_SNAPSHOTS_PATH",
            original_entry_snapshots,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            stale_data_root = root / "data"
            control_root = root / "control"
            self._write_stage182_sources(stale_data_root, "2026-07-21")
            self._write_stage182_sources(control_root, "2026-08-03")

            self.assertIn(
                "source_dir",
                inspect.signature(stage182._configure_source_paths).parameters,
                "Stage182 source configuration must require an explicit source root",
            )
            source_paths = stage182._configure_source_paths(
                self.SOURCE_PREFIX,
                source_dir=control_root,
            )

        self.assertEqual(
            control_root,
            Path(source_paths["position_changes"]).resolve().parent,
        )
        self.assertIn(
            "entry_candidate_snapshots",
            source_paths,
            "Stage182 and Stage183 must use one canonical entry snapshot key",
        )
        self.assertNotIn("entry_snapshots", source_paths)
        self.assertEqual(
            control_root,
            stage182.suitability.POSITION_CHANGES_PATH.resolve().parent,
        )

    def test_stage182_rejects_source_bytes_changed_during_inference(self) -> None:
        original_position_changes = stage182.suitability.POSITION_CHANGES_PATH
        original_entry_snapshots = stage182.suitability.ENTRY_SNAPSHOTS_PATH
        self.addCleanup(
            setattr,
            stage182.suitability,
            "POSITION_CHANGES_PATH",
            original_position_changes,
        )
        self.addCleanup(
            setattr,
            stage182.suitability,
            "ENTRY_SNAPSHOTS_PATH",
            original_entry_snapshots,
        )
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory).resolve() / "control"
            self._write_stage182_sources(source_root, "2026-08-03")
            source_paths = stage182._configure_source_paths(
                self.SOURCE_PREFIX,
                source_dir=source_root,
            )
            before = stage182._collect_source_identities(source_paths)
            position_path = Path(source_paths["position_changes"])
            position_path.write_text(
                position_path.read_text(encoding="utf-8")
                + "2026-08-03,jm2609.DCE,0,1,1\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "source files changed"):
                stage182._assert_source_identities_unchanged(
                    source_paths,
                    before,
                )

    def test_stage182_output_dir_is_candidate_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate_root = Path(directory).resolve() / "candidate"
            build_output_paths = getattr(stage182, "_build_output_paths", None)
            self.assertTrue(
                callable(build_output_paths),
                "Stage182 must expose candidate output path construction",
            )
            paths = build_output_paths(candidate_root)

        self.assertEqual(
            {
                "live_pool",
                "live_eligibility",
                "combined_eligibility",
                "summary",
                "report",
            },
            set(paths),
        )
        self.assertTrue(
            all(path.resolve().parent == candidate_root for path in paths.values())
        )
        self.assertNotEqual(
            stage182.COMBINED_ELIGIBILITY_PATH.resolve(),
            paths["combined_eligibility"].resolve(),
        )

    def test_stage935_rejects_cross_root_stage183_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            control_root = root / "control"
            stale_data_root = root / "data"
            summary = self._stage183_summary(stale_data_root)

            validate = getattr(stage935, "_validate_stage183_source", None)
            self.assertTrue(
                callable(validate),
                "Stage935 must validate Stage183 source identity before inference",
            )
            result = validate(
                summary,
                expected_root=control_root,
                resolved_target_date="2026-08-03",
                source_prefix=self.SOURCE_PREFIX,
            )

        self.assertEqual("invalid", result["validation_status"])
        self.assertIn(
            "stage183_source_path_outside_control_root",
            result["blockers"],
        )

    def test_stage935_accepts_sparse_candidate_with_complete_daily_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control_root = Path(directory).resolve() / "control"
            summary = self._stage183_summary(
                control_root,
                daily_date="2026-08-03",
                position_date="2026-08-03",
                candidate_date="2026-07-31",
            )

            validate = getattr(stage935, "_validate_stage183_source", None)
            self.assertTrue(
                callable(validate),
                "Stage935 must validate complete daily and sparse event sources",
            )
            result = validate(
                summary,
                expected_root=control_root,
                resolved_target_date="2026-08-03",
                source_prefix=self.SOURCE_PREFIX,
            )

        self.assertEqual("valid", result["validation_status"])
        self.assertEqual([], result["blockers"])
        self.assertEqual(
            "2026-07-31",
            result["artifact_dates"]["entry_candidate_snapshots_max_date"],
        )

    def test_stage935_rejects_stage183_source_content_replaced_after_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control_root = Path(directory).resolve() / "control"
            summary = self._stage183_summary(control_root)
            position_path = Path(summary["outputs"]["position_changes"])
            position_path.write_text(
                "date,vt_symbol,end_pos\n"
                "2026-08-03,rb2610.SHFE,0\n"
                "2026-08-03,jm2609.DCE,1\n",
                encoding="utf-8",
            )

            result = stage935._validate_stage183_source(
                summary,
                expected_root=control_root,
                resolved_target_date="2026-08-03",
                source_prefix=self.SOURCE_PREFIX,
            )

        self.assertEqual("invalid", result["validation_status"])
        self.assertIn(
            "stage183_position_changes_identity_mismatch",
            result["blockers"],
        )

    def test_stage935_stage182_command_uses_control_root_for_source_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            control_root = Path(directory).resolve() / "control"
            immutable_seed = Path(directory).resolve() / "official-material.csv"
            immutable_seed.write_text("seed\n", encoding="utf-8")
            build_command = getattr(stage935, "_build_stage182_command", None)
            self.assertTrue(
                callable(build_command),
                "Stage935 must build Stage182 with explicit source and output roots",
            )
            command = build_command(
                source_prefix=self.SOURCE_PREFIX,
                source_dir=control_root,
                output_dir=control_root,
                seed_combined_eligibility_path=immutable_seed,
            )

        self.assertEqual(str(stage935.PYTHON_PATH), command[0])
        self.assertEqual(str(stage935.STAGE182_PATH), command[1])
        self.assertEqual(
            [
                "--source-prefix",
                self.SOURCE_PREFIX,
                "--source-dir",
                str(control_root),
                "--output-dir",
                str(control_root),
                "--seed-combined-eligibility",
                str(immutable_seed),
            ],
            command[2:],
        )

    def test_stage182_combined_history_is_seeded_from_active_immutable_material(
        self,
    ) -> None:
        products = [
            *[f"p{index}.TEST" for index in range(1, 11)],
            OFFICIAL_AI_FIXED_PRODUCT,
        ]
        columns = stage182.ELIGIBILITY_COLUMNS
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            immutable_seed = root / "active-material-combined.csv"
            seed_rows = [
                {
                    "strategy": OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
                    "score_type": "stage182_promoted_ai_probability_top10_plus_fixed_fu",
                    "eval_date": "2026-06-30",
                    "product_vt_symbol": product,
                    "score": 12 - rank,
                    "score_rank": rank,
                    "top_n": OFFICIAL_AI_TOTAL_PRODUCT_COUNT,
                }
                for rank, product in enumerate(products, start=1)
            ]
            pd.DataFrame(seed_rows, columns=columns).to_csv(
                immutable_seed,
                index=False,
                encoding="utf-8-sig",
            )
            live = pd.DataFrame(
                [
                    {
                        **row,
                        "eval_date": "2026-07-31",
                        "score_type": "stage182_live_monthly_ai_probability",
                    }
                    for row in seed_rows
                ],
                columns=columns,
            )

            combined, _official_path, audit = stage182._build_combined_eligibility(
                live,
                seed_combined_eligibility_path=immutable_seed,
            )

        official_rows = combined[
            combined["strategy"].eq(OFFICIAL_AI_PRODUCT_POOL_STRATEGY)
        ]
        self.assertEqual(
            ["2026-06-30", "2026-07-31"],
            sorted(official_rows["eval_date"].unique().tolist()),
        )
        self.assertNotIn("old.TEST", set(combined["product_vt_symbol"]))
        self.assertEqual(str(immutable_seed), audit["seed_combined_eligibility_path"])
        self.assertEqual(11, audit["preserved_live_snapshot_rows"])

    def test_stage182_refuses_to_build_combined_without_immutable_seed(self) -> None:
        live = pd.DataFrame(columns=stage182.ELIGIBILITY_COLUMNS)

        with self.assertRaisesRegex(
            RuntimeError,
            "stage182_immutable_seed_combined_eligibility_required",
        ):
            stage182._build_combined_eligibility(live)

    def test_stage182_rejects_fractional_rank_in_immutable_seed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / "combined.csv"
            pd.DataFrame(
                [
                    {
                        "strategy": OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
                        "score_type": "stage182_promoted_ai_probability_top10_plus_fixed_fu",
                        "eval_date": "2026-06-30",
                        "product_vt_symbol": "p1.TEST",
                        "score": 1.0,
                        "score_rank": 1.5,
                        "top_n": 1,
                    }
                ],
                columns=stage182.ELIGIBILITY_COLUMNS,
            ).to_csv(seed, index=False, encoding="utf-8-sig")

            with self.assertRaisesRegex(
                RuntimeError,
                "stage182_eligibility_rank_or_top_n_not_integer",
            ):
                stage182._build_combined_eligibility(
                    pd.DataFrame(columns=stage182.ELIGIBILITY_COLUMNS),
                    seed_combined_eligibility_path=seed,
                )

    def test_stage182_cli_requires_immutable_seed(self) -> None:
        with (
            patch.object(sys, "argv", ["stage182"]),
            self.assertRaises(SystemExit),
        ):
            stage182.main()

    def test_stage935_rejects_nonisolated_candidate_output_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            shared_root = Path(directory).resolve() / "shared"
            shared_root.mkdir()
            summary = {
                "expected_eval_date": "2026-07-31",
                "resolved_target_date": "2026-08-03",
                "resolver_evidence": {},
                "update_reasons": [],
                "commands": {},
                "blockers": [],
            }
            args = Namespace(
                source_prefix=self.SOURCE_PREFIX,
                skip_data_update=True,
                data_update_timeout_seconds=1,
                source_refresh_timeout_seconds=1,
                inference_timeout_seconds=1,
                as_of="2026-08-03 21:00:00",
                data_ready_time="16:30",
            )
            with (
                patch.object(stage935, "CONTROL_OUTPUT_DIR", shared_root),
                patch.object(stage935, "DATA_ASSET_DIR", shared_root),
                patch.object(stage935, "_run_command") as run_command,
            ):
                result = stage935._execute_update(summary, args)

        self.assertEqual(
            "monthly_ai_pool_update_blocked",
            result["automation_status"],
        )
        self.assertIn(
            "stage935_control_output_dir_not_isolated",
            result["blockers"],
        )
        run_command.assert_not_called()

    def test_stage935_rejects_stage182_source_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source_root = root / "control"
            source_summary = self._stage183_summary(source_root)
            expected_paths = {
                name: str(path)
                for name, path in source_summary["outputs"].items()
            }
            expected_identities = source_summary["artifact_identities"]
            paths = self._stage182_bundle_paths(root / "candidate")
            self._write_stage182_bundle(paths, "candidate")
            paths["summary"].write_text(
                json.dumps(
                    {
                        "eval_date": "2026-07-31",
                        "source_max_date": "2026-08-03",
                        "source_paths": expected_paths,
                        "source_identities": {
                            **expected_identities,
                            "position_changes": {
                                **expected_identities["position_changes"],
                                "sha256": "0" * 64,
                            },
                        },
                        "outputs": {
                            name: str(path) for name, path in paths.items()
                        },
                        "safety": {
                            "overwrites_official_stage78_eligibility": False,
                            "uses_future_label_for_eval_date": False,
                            "real_order_enabled": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            validation = stage935._validate_stage182_outputs(
                expected_eval_date="2026-07-31",
                paths=paths,
                require_official_path=False,
                require_declared_outputs=True,
                expected_source_paths=expected_paths,
                expected_source_identities=expected_identities,
            )

        self.assertEqual("invalid", validation["validation_status"])
        self.assertIn(
            "stage182_source_identity_not_stage183_validated_source",
            validation["blockers"],
        )

    def test_stage935_rejects_source_changed_after_stage182_inference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source_root = root / "control"
            source_summary = self._stage183_summary(source_root)
            expected_paths = {
                name: str(path)
                for name, path in source_summary["outputs"].items()
            }
            expected_identities = source_summary["artifact_identities"]
            paths = self._stage182_bundle_paths(root / "candidate")
            self._write_stage182_bundle(paths, "candidate")
            paths["summary"].write_text(
                json.dumps(
                    {
                        "eval_date": "2026-07-31",
                        "source_max_date": "2026-08-03",
                        "source_paths": expected_paths,
                        "source_identities": {
                            name: expected_identities[name]
                            for name in (
                                "position_changes",
                                "entry_candidate_snapshots",
                            )
                        },
                        "outputs": {
                            name: str(path) for name, path in paths.items()
                        },
                        "safety": {
                            "overwrites_official_stage78_eligibility": False,
                            "uses_future_label_for_eval_date": False,
                            "real_order_enabled": False,
                        },
                    }
                ),
                encoding="utf-8",
            )
            position_path = Path(expected_paths["position_changes"])
            position_path.write_text(
                position_path.read_text(encoding="utf-8")
                + "2026-08-03,jm2609.DCE,1\n",
                encoding="utf-8",
            )

            validation = stage935._validate_stage182_outputs(
                expected_eval_date="2026-07-31",
                paths=paths,
                require_official_path=False,
                require_declared_outputs=True,
                expected_source_paths=expected_paths,
                expected_source_identities=expected_identities,
            )

        self.assertEqual("invalid", validation["validation_status"])
        self.assertIn(
            "stage182_source_changed_after_stage183_validation",
            validation["blockers"],
        )

    def test_stage935_invalid_candidate_does_not_publish_formal_combined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            candidate_paths = self._stage182_bundle_paths(root / "candidate")
            canonical_paths = self._stage182_bundle_paths(root / "canonical")
            self._write_stage182_bundle(candidate_paths, "candidate")
            self._write_stage182_bundle(canonical_paths, "old")
            old_combined = canonical_paths["combined_eligibility"].read_bytes()

            publish = getattr(stage935, "_publish_stage182_candidate", None)
            self.assertTrue(
                callable(publish),
                "Stage935 must publish only a prevalidated Stage182 candidate",
            )
            receipt = publish(
                candidate_paths=candidate_paths,
                canonical_paths=canonical_paths,
                candidate_validation={
                    "validation_status": "invalid",
                    "blockers": ["stage182_eval_date_not_expected"],
                },
                post_validate=lambda: {"validation_status": "valid", "blockers": []},
            )
            final_combined = canonical_paths["combined_eligibility"].read_bytes()

        self.assertEqual("blocked_candidate_invalid", receipt["publication_status"])
        self.assertEqual(old_combined, final_combined)

    def test_stage935_publish_activates_combined_last(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            candidate_paths = self._stage182_bundle_paths(root / "candidate")
            canonical_paths = self._stage182_bundle_paths(root / "canonical")
            self._write_stage182_bundle(candidate_paths, "candidate")
            self._write_stage182_bundle(canonical_paths, "old")
            publish_order: list[str] = []

            publish = getattr(stage935, "_publish_stage182_candidate", None)
            atomic_copy = getattr(stage935, "_atomic_copy_file", None)
            self.assertTrue(callable(publish), "Stage935 candidate publisher is required")
            self.assertTrue(callable(atomic_copy), "Stage935 durable atomic copy is required")

            canonical_by_path = {
                path.resolve(): name for name, path in canonical_paths.items()
            }

            def recording_copy(source: Path, target: Path) -> None:
                name = canonical_by_path.get(target.resolve())
                if name is not None:
                    publish_order.append(name)
                atomic_copy(source, target)

            with patch.object(stage935, "_atomic_copy_file", side_effect=recording_copy):
                receipt = publish(
                    candidate_paths=candidate_paths,
                    canonical_paths=canonical_paths,
                    candidate_validation={"validation_status": "valid", "blockers": []},
                    post_validate=lambda: {"validation_status": "valid", "blockers": []},
                )

            candidate_hash = stage935._sha256_file(
                candidate_paths["combined_eligibility"]
            )
            canonical_hash = stage935._sha256_file(
                canonical_paths["combined_eligibility"]
            )

        self.assertEqual("published", receipt["publication_status"])
        self.assertEqual("combined_eligibility", publish_order[-1])
        self.assertEqual(candidate_hash, canonical_hash)

    def test_stage935_publish_rolls_back_combined_after_post_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            candidate_paths = self._stage182_bundle_paths(root / "candidate")
            canonical_paths = self._stage182_bundle_paths(root / "canonical")
            self._write_stage182_bundle(candidate_paths, "candidate")
            self._write_stage182_bundle(canonical_paths, "old")
            old_combined = canonical_paths["combined_eligibility"].read_bytes()

            publish = getattr(stage935, "_publish_stage182_candidate", None)
            self.assertTrue(
                callable(publish),
                "Stage935 candidate publisher must support rollback",
            )
            receipt = publish(
                candidate_paths=candidate_paths,
                canonical_paths=canonical_paths,
                candidate_validation={"validation_status": "valid", "blockers": []},
                post_validate=lambda: {
                    "validation_status": "invalid",
                    "blockers": ["stage182_combined_missing_eval_date_rows"],
                },
            )
            final_combined = canonical_paths["combined_eligibility"].read_bytes()

        self.assertEqual("blocked_post_validation_failed", receipt["publication_status"])
        self.assertEqual("restored", receipt["rollback_status"])
        self.assertEqual(old_combined, final_combined)

    def test_stage935_publish_rolls_back_when_combined_copy_raises_after_replace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            candidate_paths = self._stage182_bundle_paths(root / "candidate")
            canonical_paths = self._stage182_bundle_paths(root / "canonical")
            self._write_stage182_bundle(candidate_paths, "candidate")
            self._write_stage182_bundle(canonical_paths, "old")
            old_combined = canonical_paths["combined_eligibility"].read_bytes()
            old_hash = stage935._sha256_file(
                canonical_paths["combined_eligibility"]
            )

            real_atomic_copy = stage935._atomic_copy_file

            def raise_after_combined_replace(source: Path, target: Path) -> None:
                real_atomic_copy(source, target)
                if (
                    source.resolve()
                    == candidate_paths["combined_eligibility"].resolve()
                    and target.resolve()
                    == canonical_paths["combined_eligibility"].resolve()
                ):
                    raise OSError("injected directory fsync failure after replace")

            with patch.object(
                stage935,
                "_atomic_copy_file",
                side_effect=raise_after_combined_replace,
            ):
                receipt = stage935._publish_stage182_candidate(
                    candidate_paths=candidate_paths,
                    canonical_paths=canonical_paths,
                    candidate_validation={"validation_status": "valid", "blockers": []},
                    post_validate=lambda: {"validation_status": "valid", "blockers": []},
                )
            final_combined = canonical_paths["combined_eligibility"].read_bytes()
            restored_hash = stage935._sha256_file(
                canonical_paths["combined_eligibility"]
            )

        self.assertEqual("blocked_publication_exception", receipt["publication_status"])
        self.assertEqual("restored", receipt["rollback_status"])
        self.assertEqual(old_combined, final_combined)
        self.assertEqual(old_hash, restored_hash)
        self.assertEqual(old_hash, receipt["pre_publication_combined_sha256"])
        self.assertEqual(old_hash, receipt["restored_combined_sha256"])

    def test_stage935_backup_cleanup_failure_does_not_report_false_block(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            candidate_paths = self._stage182_bundle_paths(root / "candidate")
            canonical_paths = self._stage182_bundle_paths(root / "canonical")
            self._write_stage182_bundle(candidate_paths, "candidate")
            self._write_stage182_bundle(canonical_paths, "old")
            canonical_combined = canonical_paths["combined_eligibility"]
            candidate_combined = candidate_paths["combined_eligibility"]
            real_fsync_directory = stage935._fsync_directory

            def fail_only_after_backup_unlink(path: Path) -> None:
                backup_exists = any(
                    canonical_combined.parent.glob(
                        f".{canonical_combined.name}.backup.*"
                    )
                )
                combined_is_candidate = (
                    canonical_combined.read_bytes() == candidate_combined.read_bytes()
                )
                if combined_is_candidate and not backup_exists:
                    raise OSError("injected backup cleanup directory fsync failure")
                real_fsync_directory(path)

            with patch.object(
                stage935,
                "_fsync_directory",
                side_effect=fail_only_after_backup_unlink,
            ):
                receipt = stage935._publish_stage182_candidate(
                    candidate_paths=candidate_paths,
                    canonical_paths=canonical_paths,
                    candidate_validation={"validation_status": "valid", "blockers": []},
                    post_validate=lambda: {"validation_status": "valid", "blockers": []},
                )

        self.assertEqual("published", receipt["publication_status"])
        self.assertEqual("not_needed", receipt["rollback_status"])
        self.assertIn("backup_cleanup_warning", receipt)

    def test_stage935_candidate_validation_rejects_truncated_combined_official_pool(
        self,
    ) -> None:
        strategy = OFFICIAL_AI_PRODUCT_POOL_STRATEGY
        products = [
            "jm.DCE",
            "si.GFEX",
            "SA.CZCE",
            "au.SHFE",
            "lc.GFEX",
            "cu.SHFE",
            "SM.CZCE",
            "lh.DCE",
            "rb.SHFE",
            "m.DCE",
            OFFICIAL_AI_FIXED_PRODUCT,
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            mapping = root / "mapping.csv"
            eval_dates = ["2026-04-30", "2026-05-29", "2026-06-30", "2026-07-31"]
            mapping.write_text(
                "date\n" + "".join(f"{date}\n" for date in eval_dates) + "2026-08-03\n",
                encoding="utf-8",
            )
            paths = self._stage182_bundle_paths(root / "candidate")
            paths["live_pool"].parent.mkdir(parents=True, exist_ok=True)
            paths["live_pool"].write_text(
                "product_vt_symbol\n" + "".join(f"{product}\n" for product in products),
                encoding="utf-8",
            )
            header = (
                "strategy,score_type,eval_date,product_vt_symbol,score,score_rank,top_n\n"
            )
            live_rows = "".join(
                (
                    f"{strategy},stage182_live,2026-07-31,{product},"
                    f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1 - rank},{rank},"
                    f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT}\n"
                )
                for rank, product in enumerate(products, start=1)
            )
            paths["live_eligibility"].write_text(
                header + live_rows,
                encoding="utf-8",
            )
            truncated_combined_rows = "".join(
                (
                    f"{strategy},stage182_live,{date},jm.DCE,1,1,"
                    f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT}\n"
                )
                for date in eval_dates
            )
            paths["combined_eligibility"].write_text(
                header + truncated_combined_rows,
                encoding="utf-8",
            )
            paths["report"].write_text("candidate report\n", encoding="utf-8")
            paths["summary"].write_text(
                json.dumps(
                    {
                        "eval_date": "2026-07-31",
                        "source_max_date": "2026-08-03",
                        "outputs": {name: str(path) for name, path in paths.items()},
                        "safety": {
                            "overwrites_official_stage78_eligibility": False,
                            "uses_future_label_for_eval_date": False,
                            "real_order_enabled": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(stage935, "ALL_FUTURES_MAPPING_PATH", mapping):
                validation = stage935._validate_stage182_outputs(
                    expected_eval_date="2026-07-31",
                    paths=paths,
                    require_official_path=False,
                    require_declared_outputs=True,
                )

        self.assertEqual("invalid", validation["validation_status"])
        self.assertIn(
            "stage182_combined_required_eval_date_rows_not_official_count",
            validation["blockers"],
        )
        self.assertIn(
            "stage182_combined_current_official_pool_mismatch",
            validation["blockers"],
        )

    def test_stage935_combined_audit_rejects_malformed_historical_official_pool(
        self,
    ) -> None:
        strategy = OFFICIAL_AI_PRODUCT_POOL_STRATEGY
        products = [
            "jm.DCE",
            "si.GFEX",
            "SA.CZCE",
            "au.SHFE",
            "lc.GFEX",
            "cu.SHFE",
            "SM.CZCE",
            "lh.DCE",
            "rb.SHFE",
            "m.DCE",
            OFFICIAL_AI_FIXED_PRODUCT,
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            mapping = root / "mapping.csv"
            eval_dates = ["2026-04-30", "2026-05-29", "2026-06-30", "2026-07-31"]
            mapping.write_text(
                "date\n" + "".join(f"{date}\n" for date in eval_dates) + "2026-08-03\n",
                encoding="utf-8",
            )
            combined = root / "combined.csv"
            header = (
                "strategy,score_type,eval_date,product_vt_symbol,score,score_rank,top_n\n"
            )
            rows: list[str] = []
            for date in eval_dates:
                for rank, product in enumerate(products, start=1):
                    if date == "2026-04-30":
                        product = "jm.DCE"
                        rank = 1
                    rows.append(
                        (
                            f"{strategy},stage182_live,{date},{product},1,{rank},"
                            f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT}\n"
                        )
                    )
            combined.write_text(header + "".join(rows), encoding="utf-8")

            with patch.object(stage935, "ALL_FUTURES_MAPPING_PATH", mapping):
                audit = stage935._combined_eval_date_audit(
                    "2026-07-31",
                    combined_path=combined,
                )

        self.assertEqual([], audit["invalid_row_count_eval_dates"])
        self.assertIn(
            "2026-04-30",
            audit["invalid_unique_product_eval_dates"],
        )
        self.assertIn("2026-04-30", audit["invalid_rank_eval_dates"])

    def test_stage935_combined_audit_accepts_top10_plus_fixed_fu_history(self) -> None:
        products = [
            *[
                f"p{index}.TEST"
                for index in range(1, OFFICIAL_AI_RANKED_PRODUCT_COUNT + 1)
            ],
            OFFICIAL_AI_FIXED_PRODUCT,
        ]
        eval_dates = ["2026-04-30", "2026-05-29", "2026-06-30", "2026-07-31"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            mapping = root / "mapping.csv"
            mapping.write_text(
                "date\n" + "".join(f"{date}\n" for date in eval_dates) + "2026-08-03\n",
                encoding="utf-8",
            )
            combined = root / "combined.csv"
            header = (
                "strategy,score_type,eval_date,product_vt_symbol,score,score_rank,top_n\n"
            )
            rows = "".join(
                (
                    f"{OFFICIAL_AI_PRODUCT_POOL_STRATEGY},stage182_live,"
                    f"{date},{product},{OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1 - rank},"
                    f"{rank},{OFFICIAL_AI_TOTAL_PRODUCT_COUNT}\n"
                )
                for date in eval_dates
                for rank, product in enumerate(products, start=1)
            )
            combined.write_text(header + rows, encoding="utf-8")

            with patch.object(stage935, "ALL_FUTURES_MAPPING_PATH", mapping):
                audit = stage935._combined_eval_date_audit(
                    "2026-07-31",
                    combined_path=combined,
                )

        self.assertEqual([], audit["missing_recent_eval_dates"])
        self.assertEqual([], audit["invalid_row_count_eval_dates"])
        self.assertEqual([], audit["invalid_unique_product_eval_dates"])
        self.assertEqual([], audit["invalid_rank_eval_dates"])
        self.assertEqual([], audit["invalid_top_n_eval_dates"])
        self.assertEqual([], audit["missing_fixed_fu_eval_dates"])

    def test_stage935_combined_audit_rejects_missing_product_value(self) -> None:
        products = [*[f"p{index}.TEST" for index in range(1, 11)], OFFICIAL_AI_FIXED_PRODUCT]
        eval_dates = ["2026-04-30", "2026-05-29", "2026-06-30", "2026-07-31"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            mapping = root / "mapping.csv"
            mapping.write_text(
                "date\n" + "".join(f"{date}\n" for date in eval_dates) + "2026-08-03\n",
                encoding="utf-8",
            )
            combined = root / "combined.csv"
            rows = [
                {
                    "strategy": OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
                    "score_type": "stage182_live",
                    "eval_date": date,
                    "product_vt_symbol": (
                        None if date == "2026-04-30" and rank == 1 else product
                    ),
                    "score": OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1 - rank,
                    "score_rank": rank,
                    "top_n": OFFICIAL_AI_TOTAL_PRODUCT_COUNT,
                }
                for date in eval_dates
                for rank, product in enumerate(products, start=1)
            ]
            pd.DataFrame(rows).to_csv(combined, index=False, encoding="utf-8-sig")

            with patch.object(stage935, "ALL_FUTURES_MAPPING_PATH", mapping):
                audit = stage935._combined_eval_date_audit(
                    "2026-07-31",
                    combined_path=combined,
                )

        self.assertIn("2026-04-30", audit["invalid_contract_eval_dates"])
        self.assertIn(
            "product_value",
            audit["contract_blockers_by_eval_date"]["2026-04-30"],
        )

    def test_stage935_combined_audit_rejects_fixed_fu_inside_ranked_top10(self) -> None:
        products = ["fu.SHFE", *[f"p{index}.TEST" for index in range(1, 11)]]
        eval_dates = ["2026-04-30", "2026-05-29", "2026-06-30", "2026-07-31"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            mapping = root / "mapping.csv"
            mapping.write_text(
                "date\n" + "".join(f"{date}\n" for date in eval_dates) + "2026-08-03\n",
                encoding="utf-8",
            )
            combined = root / "combined.csv"
            header = (
                "strategy,score_type,eval_date,product_vt_symbol,score,score_rank,top_n\n"
            )
            rows = "".join(
                (
                    "ai_top10_plus_fu_official_live_v1,stage182_live,"
                    f"{date},{product},{12-rank},{rank},11\n"
                )
                for date in eval_dates
                for rank, product in enumerate(products, start=1)
            )
            combined.write_text(header + rows, encoding="utf-8")

            with patch.object(stage935, "ALL_FUTURES_MAPPING_PATH", mapping):
                audit = stage935._combined_eval_date_audit(
                    "2026-07-31",
                    combined_path=combined,
                )

        self.assertEqual(eval_dates, audit["invalid_fixed_product_rank_eval_dates"])

    def test_stage935_validation_accepts_top10_plus_fixed_fu_bundle(self) -> None:
        products = [
            *[
                f"p{index}.TEST"
                for index in range(1, OFFICIAL_AI_RANKED_PRODUCT_COUNT + 1)
            ],
            OFFICIAL_AI_FIXED_PRODUCT,
        ]
        eval_dates = ["2026-04-30", "2026-05-29", "2026-06-30", "2026-07-31"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            mapping = root / "mapping.csv"
            mapping.write_text(
                "date\n" + "".join(f"{date}\n" for date in eval_dates) + "2026-08-03\n",
                encoding="utf-8",
            )
            paths = self._stage182_bundle_paths(root / "candidate")
            paths["live_pool"].parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                {
                    "strategy": [OFFICIAL_AI_PRODUCT_POOL_STRATEGY] * len(products),
                    "eval_date": ["2026-07-31"] * len(products),
                    "product_vt_symbol": products,
                    "predicted_product_suitability_probability": list(
                        range(OFFICIAL_AI_TOTAL_PRODUCT_COUNT, 0, -1)
                    ),
                    "ai_rank": list(range(1, OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1)),
                    "selection_role": [
                        *["model_ranked"] * OFFICIAL_AI_RANKED_PRODUCT_COUNT,
                        "fixed_fu",
                    ],
                    "source_score_type": ["stage182_live"] * len(products),
                }
            ).to_csv(paths["live_pool"], index=False, encoding="utf-8-sig")
            header = (
                "strategy,score_type,eval_date,product_vt_symbol,score,score_rank,top_n\n"
            )
            live_rows = "".join(
                (
                    f"{OFFICIAL_AI_PRODUCT_POOL_STRATEGY},stage182_live,2026-07-31,"
                    f"{product},{OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1 - rank},{rank},"
                    f"{OFFICIAL_AI_TOTAL_PRODUCT_COUNT}\n"
                )
                for rank, product in enumerate(products, start=1)
            )
            paths["live_eligibility"].write_text(header + live_rows, encoding="utf-8")
            combined_rows = "".join(
                (
                    f"{OFFICIAL_AI_PRODUCT_POOL_STRATEGY},stage182_live,"
                    f"{date},{product},{OFFICIAL_AI_TOTAL_PRODUCT_COUNT + 1 - rank},"
                    f"{rank},{OFFICIAL_AI_TOTAL_PRODUCT_COUNT}\n"
                )
                for date in eval_dates
                for rank, product in enumerate(products, start=1)
            )
            paths["combined_eligibility"].write_text(
                header + combined_rows,
                encoding="utf-8",
            )
            paths["report"].write_text("candidate report\n", encoding="utf-8")
            paths["summary"].write_text(
                json.dumps(
                    {
                        "eval_date": "2026-07-31",
                        "source_max_date": "2026-08-03",
                        "outputs": {name: str(path) for name, path in paths.items()},
                        "safety": {
                            "overwrites_official_stage78_eligibility": False,
                            "uses_future_label_for_eval_date": False,
                            "real_order_enabled": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(stage935, "ALL_FUTURES_MAPPING_PATH", mapping):
                validation = stage935._validate_stage182_outputs(
                    expected_eval_date="2026-07-31",
                    paths=paths,
                    require_official_path=False,
                    require_declared_outputs=True,
                )
                malformed_combined = pd.read_csv(paths["combined_eligibility"])
                malformed_combined.loc[
                    malformed_combined["eval_date"].astype(str).eq("2026-04-30")
                    & malformed_combined["score_rank"].eq(1),
                    "product_vt_symbol",
                ] = None
                malformed_combined.to_csv(
                    paths["combined_eligibility"],
                    index=False,
                    encoding="utf-8-sig",
                )
                invalid_validation = stage935._validate_stage182_outputs(
                    expected_eval_date="2026-07-31",
                    paths=paths,
                    require_official_path=False,
                    require_declared_outputs=True,
                )

        self.assertEqual([], validation["blockers"])
        self.assertEqual("valid", validation["validation_status"])
        self.assertEqual(products, validation["top_products"])
        self.assertEqual("invalid", invalid_validation["validation_status"])
        self.assertIn(
            "stage182_combined_required_eval_date_contract_invalid",
            invalid_validation["blockers"],
        )

    def test_stage935_validation_rejects_malformed_latest_pool(self) -> None:
        products = [
            *[f"p{index}.TEST" for index in range(1, 11)],
            OFFICIAL_AI_FIXED_PRODUCT,
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            paths = self._stage182_bundle_paths(root)
            paths["live_pool"].parent.mkdir(parents=True, exist_ok=True)
            paths["live_pool"].write_text(
                "product_vt_symbol\n" + "".join(f"{product}\n" for product in products),
                encoding="utf-8",
            )
            header = "strategy,score_type,eval_date,product_vt_symbol,score,score_rank,top_n\n"
            rows = "".join(
                (
                    f"{OFFICIAL_AI_PRODUCT_POOL_STRATEGY},stage182_live,2026-07-31,"
                    f"{product},{12-rank},{rank},11\n"
                )
                for rank, product in enumerate(products, start=1)
            )
            paths["live_eligibility"].write_text(header + rows, encoding="utf-8")
            paths["combined_eligibility"].write_text(header + rows, encoding="utf-8")
            paths["report"].write_text("report\n", encoding="utf-8")
            paths["summary"].write_text(
                json.dumps(
                    {
                        "eval_date": "2026-07-31",
                        "source_max_date": "2026-08-03",
                        "safety": {
                            "overwrites_official_stage78_eligibility": False,
                            "uses_future_label_for_eval_date": False,
                            "real_order_enabled": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            validation = stage935._validate_stage182_outputs(
                expected_eval_date="2026-07-31",
                paths=paths,
                require_official_path=False,
            )

        self.assertEqual("invalid", validation["validation_status"])
        self.assertIn("stage182_live_pool_required_columns_missing", validation["blockers"])

    def test_stage935_combined_audit_rejects_fractional_ranks(self) -> None:
        products = [*[f"p{index}.TEST" for index in range(1, 11)], OFFICIAL_AI_FIXED_PRODUCT]
        eval_dates = ["2026-04-30", "2026-05-29", "2026-06-30", "2026-07-31"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            mapping = root / "mapping.csv"
            mapping.write_text(
                "date\n" + "".join(f"{date}\n" for date in eval_dates) + "2026-08-03\n",
                encoding="utf-8",
            )
            combined = root / "combined.csv"
            pd.DataFrame(
                [
                    {
                        "strategy": OFFICIAL_AI_PRODUCT_POOL_STRATEGY,
                        "score_type": "stage182_live",
                        "eval_date": date,
                        "product_vt_symbol": product,
                        "score": 12 - rank,
                        "score_rank": rank + 0.5,
                        "top_n": 11,
                    }
                    for date in eval_dates
                    for rank, product in enumerate(products, start=1)
                ]
            ).to_csv(combined, index=False, encoding="utf-8-sig")

            with patch.object(stage935, "ALL_FUTURES_MAPPING_PATH", mapping):
                audit = stage935._combined_eval_date_audit(
                    "2026-07-31",
                    combined_path=combined,
                )

        self.assertEqual(eval_dates, audit["invalid_rank_eval_dates"])


if __name__ == "__main__":
    unittest.main()
