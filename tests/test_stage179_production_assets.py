from __future__ import annotations

import json
import hashlib
from dataclasses import replace
import os
from pathlib import Path
from unittest.mock import patch
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

from qmt_roll_official_live_production_assets import (  # noqa: E402
    PRODUCTION_REQUIRED_DATA_ASSETS,
    ProductionAssetError,
    build_production_asset_inventory,
    validate_production_asset_inventory,
    validate_production_data_link,
    validate_production_venv_link,
)
from qmt_roll_official_live_daily_data_receipt import (  # noqa: E402
    build_and_write_production_daily_data_receipt,
    initialize_production_database_from_sqlite_backup,
    load_and_validate_production_daily_data_receipt,
    serialize_production_daily_data_receipt,
)
from qmt_roll_official_execution_profile import C9_15W_PROFILE  # noqa: E402
from qmt_roll_official_pending_artifact import (  # noqa: E402
    artifact_hashes_for_profile,
    validate_pending_artifact_cohort,
)
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as stage901  # noqa: E402


class Stage179ProductionAssetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name).resolve()
        self.data_root = root / "canonical-data"
        self.data_root.mkdir(mode=0o700)
        self.data_root.chmod(0o700)
        payloads = {
            PRODUCTION_REQUIRED_DATA_ASSETS[0]: (
                "date,vt_symbol\n2026-07-20,rb.SHFE\n2026-07-21,jm.DCE\n"
            ),
            PRODUCTION_REQUIRED_DATA_ASSETS[1]: (
                "contract,max_date\nrb2609,2026-07-21\n"
            ),
            PRODUCTION_REQUIRED_DATA_ASSETS[2]: json.dumps(
                {
                    "max_saved_date": "2026-07-21",
                    "mapping_update": {"combined_max_date": "2026-07-21"},
                    "forward_trading_calendar": {
                        "source": "tqsdk.TqContCalendar",
                        "completed_target_date": "2026-07-21",
                        "next_trading_session_date": "2026-07-22",
                        "trading_dates_sha256": "f" * 64,
                    },
                }
            ),
            PRODUCTION_REQUIRED_DATA_ASSETS[3]: (
                "vt_symbol,bar_datetime,open,high,low,close\n"
                "jm.DCE,2026-07-21 21:00:00,1,1,1,1\n"
            ),
        }
        for relative, content in payloads.items():
            path = self.data_root / relative
            path.write_text(content, encoding="utf-8")
            path.chmod(0o600)
        self.deploy_root = root / "stable-deploy"
        self.deploy_root.mkdir(mode=0o700)
        self.deploy_root.chmod(0o700)
        self.data_link = self.deploy_root / "backtest_outputs"
        self.data_link.symlink_to(self.data_root, target_is_directory=True)
        self.commit = "a" * 40
        self.manifest_sha256 = "b" * 64
        self.trader_dir = self.deploy_root / ".vntrader"
        self.trader_dir.mkdir(mode=0o700)
        self.trader_dir.chmod(0o700)
        self.database = self.trader_dir / "database.db"
        connection = sqlite3.connect(self.database)
        try:
            connection.execute("CREATE TABLE dbbardata (datetime TEXT NOT NULL)")
            connection.execute(
                "INSERT INTO dbbardata(datetime) VALUES (?)",
                ("2026-07-21 00:00:00",),
            )
            connection.commit()
        finally:
            connection.close()
        self.database.chmod(0o600)
        self.receipt_root = root / "data-readiness"
        self.receipt_root.mkdir(mode=0o700)
        self.receipt_root.chmod(0o700)
        self.receipt_path = self.receipt_root / "latest.json"
        self.ai_path = self.data_root / "official-ai-eligibility.csv"
        self.ai_path.write_text(
            "eval_date,product_vt_symbol,eligible\n"
            "2026-06-30,jm.DCE,1\n",
            encoding="utf-8",
        )
        self.ai_path.chmod(0o600)
        ai_sha256 = hashlib.sha256(self.ai_path.read_bytes()).hexdigest()
        self.signal_root = self.deploy_root / "signal-input"
        self.signal_root.mkdir(mode=0o700)
        self.signal_root.chmod(0o700)
        profile_paths = {
            "official_summary": self.signal_root / C9_15W_PROFILE.summary_path.name,
            "signal_plan": self.signal_root / C9_15W_PROFILE.signal_plan_path.name,
            "current_positions": (
                self.signal_root / C9_15W_PROFILE.current_positions_path.name
            ),
            "pending_orders": self.signal_root / C9_15W_PROFILE.pending_orders_path.name,
        }
        decision = {
            "analysis_end": "2026-07-21",
            "latest_available_data_date": "2026-07-21",
            "execution_profile": C9_15W_PROFILE.profile_key,
            "official_live_version": C9_15W_PROFILE.official_version,
            "capital": C9_15W_PROFILE.capital,
            "capital_label": C9_15W_PROFILE.capital_label,
            "shadow_replay_ai_pool_status": "valid",
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "order_api_called": False,
            "strategy_ai_product_pool_eligibility_path": str(self.ai_path),
            "ai_pool_audit": {
                "path": str(self.ai_path),
                "eligibility_sha256": ai_sha256,
                "max_eval_date": "2026-06-30",
                "missing_required_eval_dates": [],
            },
        }
        profile_paths["official_summary"].write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        profile_paths["signal_plan"].write_text(
            "vt_symbol,direction,offset,volume\n",
            encoding="utf-8",
        )
        profile_paths["current_positions"].write_text(
            "vt_symbol,direction,end_pos\n",
            encoding="utf-8",
        )
        profile_paths["pending_orders"].write_text(
            "cohort_id,target_date,execution_profile,official_live_version,capital,capital_label\n",
            encoding="utf-8",
        )
        for path in profile_paths.values():
            path.chmod(0o600)
        hashes = {
            key: hashlib.sha256(path.read_bytes()).hexdigest()
            for key, path in profile_paths.items()
        }
        audit = {
            "schema_version": 1,
            "status": "ready",
            "cohort_id": "c" * 64,
            "target_date": "2026-07-21",
            "execution_profile": C9_15W_PROFILE.profile_key,
            "official_live_version": C9_15W_PROFILE.official_version,
            "capital": C9_15W_PROFILE.capital,
            "capital_label": C9_15W_PROFILE.capital_label,
            "official_summary_sha256": hashes["official_summary"],
            "signal_plan_sha256": hashes["signal_plan"],
            "current_positions_sha256": hashes["current_positions"],
            "pending_orders_sha256": hashes["pending_orders"],
            "pending_order_count": 0,
            "order_api_called_count": 0,
        }
        audit_path = self.signal_root / C9_15W_PROFILE.pending_orders_audit_path.name
        audit_path.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        audit_path.chmod(0o600)

    def inventory(self) -> dict[str, object]:
        return build_production_asset_inventory(
            declared_data_link=self.data_link,
            expected_data_root=self.data_root,
            source_commit=self.commit,
            target_cutoff_date="2026-07-21",
            generated_at_utc="2026-07-21T05:59:00Z",
        )

    def set_data_target(self, *, target_date: str, next_session_date: str) -> None:
        (self.data_root / PRODUCTION_REQUIRED_DATA_ASSETS[0]).write_text(
            f"date,vt_symbol\n{target_date},jm.DCE\n",
            encoding="utf-8",
        )
        (self.data_root / PRODUCTION_REQUIRED_DATA_ASSETS[1]).write_text(
            f"contract,max_date\njm2609,{target_date}\n",
            encoding="utf-8",
        )
        (self.data_root / PRODUCTION_REQUIRED_DATA_ASSETS[2]).write_text(
            json.dumps(
                {
                    "max_saved_date": target_date,
                    "mapping_update": {"combined_max_date": target_date},
                    "forward_trading_calendar": {
                        "source": "tqsdk.TqContCalendar",
                        "completed_target_date": target_date,
                        "next_trading_session_date": next_session_date,
                        "trading_dates_sha256": "f" * 64,
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.data_root / PRODUCTION_REQUIRED_DATA_ASSETS[3]).write_text(
            "vt_symbol,bar_datetime,open,high,low,close\n"
            f"jm.DCE,{target_date} 21:00:00,1,1,1,1\n",
            encoding="utf-8",
        )
        for relative in PRODUCTION_REQUIRED_DATA_ASSETS:
            (self.data_root / relative).chmod(0o600)

    def validate(self, payload: dict[str, object]) -> dict[str, object]:
        return validate_production_asset_inventory(
            payload,
            declared_data_link=self.data_link,
            expected_data_root=self.data_root,
            source_commit=self.commit,
            target_cutoff_date="2026-07-21",
            manifest_created_at_utc="2026-07-21T06:00:00Z",
        )

    def test_inventory_binds_exact_link_hashes_sizes_and_target_freshness(self) -> None:
        payload = self.inventory()
        loaded = self.validate(payload)

        self.assertEqual("2026-07-21", loaded["target_cutoff_date"])
        self.assertEqual(
            set(PRODUCTION_REQUIRED_DATA_ASSETS),
            {row["relative_path"] for row in loaded["assets"]},
        )
        self.assertTrue(all(len(row["sha256"]) == 64 for row in loaded["assets"]))
        self.assertEqual(
            str(self.data_root.resolve()),
            str(validate_production_data_link(
                declared_data_link=self.data_link,
                expected_data_root=self.data_root,
            )),
        )

    def test_asset_byte_change_is_rejected(self) -> None:
        payload = self.inventory()
        asset = self.data_root / PRODUCTION_REQUIRED_DATA_ASSETS[3]
        asset.write_text("changed\n", encoding="utf-8")
        asset.chmod(0o600)

        with self.assertRaisesRegex(
            ProductionAssetError,
            "inventory_bytes_mismatch",
        ):
            self.validate(payload)

    def test_link_must_be_owned_symlink_to_exact_canonical_root(self) -> None:
        wrong_root = Path(self.tempdir.name).resolve() / "wrong-data"
        wrong_root.mkdir(mode=0o700)
        wrong_root.chmod(0o700)

        with self.assertRaisesRegex(
            ProductionAssetError,
            "link_target_mismatch",
        ):
            validate_production_data_link(
                declared_data_link=self.data_link,
                expected_data_root=wrong_root,
            )

        self.data_link.unlink()
        self.data_link.mkdir(mode=0o700)
        with self.assertRaisesRegex(
            ProductionAssetError,
            "link_not_symlink",
        ):
            validate_production_data_link(
                declared_data_link=self.data_link,
                expected_data_root=self.data_root,
            )

    def test_ancestor_symlink_is_rejected_even_when_leaf_target_is_exact(self) -> None:
        root = Path(self.tempdir.name).resolve()
        real_parent = root / "real-parent"
        real_parent.mkdir(mode=0o700)
        real_parent.chmod(0o700)
        (real_parent / "backtest_outputs").symlink_to(
            self.data_root,
            target_is_directory=True,
        )
        alias_parent = root / "alias-parent"
        alias_parent.symlink_to(real_parent, target_is_directory=True)

        with self.assertRaisesRegex(
            ProductionAssetError,
            "ancestor_symlink_forbidden",
        ):
            validate_production_data_link(
                declared_data_link=alias_parent / "backtest_outputs",
                expected_data_root=self.data_root,
            )

    def test_stale_mapping_or_insecure_target_is_rejected(self) -> None:
        mapping = self.data_root / PRODUCTION_REQUIRED_DATA_ASSETS[0]
        mapping.write_text("date\n2026-07-20\n", encoding="utf-8")
        mapping.chmod(0o600)
        with self.assertRaisesRegex(
            ProductionAssetError,
            "target_freshness_mismatch",
        ):
            self.inventory()

        mapping.write_text("date\n2026-07-21\n", encoding="utf-8")
        mapping.chmod(0o600)
        self.data_root.chmod(0o777)
        with self.assertRaisesRegex(
            ProductionAssetError,
            "root_(?:ancestor_)?writable_by_other",
        ):
            self.inventory()

    def test_inventory_freshness_follows_next_trading_session_not_36h(self) -> None:
        cases = (
            (
                "2026-07-17",
                "2026-07-20",
                "2026-07-17T08:35:00Z",
                "2026-07-20T00:55:00Z",
            ),
            (
                "2026-09-30",
                "2026-10-08",
                "2026-09-30T08:35:00Z",
                "2026-10-08T00:55:00Z",
            ),
        )
        for target, next_session, generated_at, validation_at in cases:
            with self.subTest(target=target, next_session=next_session):
                self.set_data_target(
                    target_date=target,
                    next_session_date=next_session,
                )
                payload = build_production_asset_inventory(
                    declared_data_link=self.data_link,
                    expected_data_root=self.data_root,
                    source_commit=self.commit,
                    target_cutoff_date=target,
                    generated_at_utc=generated_at,
                )
                loaded = validate_production_asset_inventory(
                    payload,
                    declared_data_link=self.data_link,
                    expected_data_root=self.data_root,
                    source_commit=self.commit,
                    target_cutoff_date=target,
                    manifest_created_at_utc=validation_at,
                )
                self.assertEqual(next_session, loaded["semantic_freshness"]["next_trading_session_date"])

                with self.assertRaisesRegex(
                    ProductionAssetError,
                    "trading_session_expired",
                ):
                    validate_production_asset_inventory(
                        payload,
                        declared_data_link=self.data_link,
                        expected_data_root=self.data_root,
                        source_commit=self.commit,
                        target_cutoff_date=target,
                        manifest_created_at_utc=(
                            "2026-07-21T00:00:00Z"
                            if next_session == "2026-07-20"
                            else "2026-10-09T00:00:00Z"
                        ),
                    )

    def test_daily_receipt_binds_mutable_data_database_and_target_date(self) -> None:
        payload = build_and_write_production_daily_data_receipt(
            output_path=self.receipt_path,
            declared_data_link=self.data_link,
            expected_data_root=self.data_root,
            source_commit=self.commit,
            manifest_sha256=self.manifest_sha256,
            target_cutoff_date="2026-07-21",
            production_database_path=self.database,
            signal_input_root=self.signal_root,
            official_ai_eligibility_path=self.ai_path,
            generated_at_utc="2026-07-21T08:40:00Z",
        )
        loaded = load_and_validate_production_daily_data_receipt(
            self.receipt_path,
            declared_data_link=self.data_link,
            expected_data_root=self.data_root,
            source_commit=self.commit,
            manifest_sha256=self.manifest_sha256,
            target_cutoff_date="2026-07-21",
            production_database_path=self.database,
            signal_input_root=self.signal_root,
            official_ai_eligibility_path=self.ai_path,
            validation_at_utc="2026-07-21T09:00:00Z",
        )

        self.assertEqual(payload, loaded)
        self.assertEqual(0o600, self.receipt_path.stat().st_mode & 0o777)
        self.assertEqual("2026-07-21", loaded["database_asset"]["max_bar_date"])
        self.assertEqual(
            serialize_production_daily_data_receipt(payload),
            self.receipt_path.read_bytes(),
        )

    def test_data_update_and_receipt_tamper_invalidate_old_daily_receipt(self) -> None:
        payload = build_and_write_production_daily_data_receipt(
            output_path=self.receipt_path,
            declared_data_link=self.data_link,
            expected_data_root=self.data_root,
            source_commit=self.commit,
            manifest_sha256=self.manifest_sha256,
            target_cutoff_date="2026-07-21",
            production_database_path=self.database,
            signal_input_root=self.signal_root,
            official_ai_eligibility_path=self.ai_path,
            generated_at_utc="2026-07-21T08:40:00Z",
        )
        asset = self.data_root / PRODUCTION_REQUIRED_DATA_ASSETS[3]
        asset.write_text(asset.read_text(encoding="utf-8") + "changed\n", encoding="utf-8")
        asset.chmod(0o600)
        with self.assertRaisesRegex(
            ProductionAssetError,
            "inventory_bytes_mismatch",
        ):
            load_and_validate_production_daily_data_receipt(
                self.receipt_path,
                declared_data_link=self.data_link,
                expected_data_root=self.data_root,
                source_commit=self.commit,
                manifest_sha256=self.manifest_sha256,
                target_cutoff_date="2026-07-21",
                production_database_path=self.database,
                signal_input_root=self.signal_root,
                official_ai_eligibility_path=self.ai_path,
                validation_at_utc="2026-07-21T09:00:00Z",
            )

        self.receipt_path.write_bytes(
            serialize_production_daily_data_receipt(
                {**payload, "receipt_sha256": "0" * 64}
            )
        )
        self.receipt_path.chmod(0o600)
        with self.assertRaisesRegex(
            ProductionAssetError,
            "receipt_digest_mismatch",
        ):
            load_and_validate_production_daily_data_receipt(
                self.receipt_path,
                declared_data_link=self.data_link,
                expected_data_root=self.data_root,
                source_commit=self.commit,
                manifest_sha256=self.manifest_sha256,
                target_cutoff_date="2026-07-21",
                production_database_path=self.database,
                signal_input_root=self.signal_root,
                official_ai_eligibility_path=self.ai_path,
                validation_at_utc="2026-07-21T09:00:00Z",
            )

    def test_daily_receipt_refuses_cross_day_reuse(self) -> None:
        build_and_write_production_daily_data_receipt(
            output_path=self.receipt_path,
            declared_data_link=self.data_link,
            expected_data_root=self.data_root,
            source_commit=self.commit,
            manifest_sha256=self.manifest_sha256,
            target_cutoff_date="2026-07-21",
            production_database_path=self.database,
            signal_input_root=self.signal_root,
            official_ai_eligibility_path=self.ai_path,
            generated_at_utc="2026-07-21T08:40:00Z",
        )
        with self.assertRaisesRegex(
            ProductionAssetError,
            "receipt_identity_mismatch",
        ):
            load_and_validate_production_daily_data_receipt(
                self.receipt_path,
                declared_data_link=self.data_link,
                expected_data_root=self.data_root,
                source_commit=self.commit,
                manifest_sha256=self.manifest_sha256,
                target_cutoff_date="2026-07-22",
                production_database_path=self.database,
                signal_input_root=self.signal_root,
                official_ai_eligibility_path=self.ai_path,
                validation_at_utc="2026-07-22T09:00:00Z",
            )

    def test_signal_or_ai_change_invalidates_old_daily_receipt(self) -> None:
        build_and_write_production_daily_data_receipt(
            output_path=self.receipt_path,
            declared_data_link=self.data_link,
            expected_data_root=self.data_root,
            source_commit=self.commit,
            manifest_sha256=self.manifest_sha256,
            target_cutoff_date="2026-07-21",
            production_database_path=self.database,
            signal_input_root=self.signal_root,
            official_ai_eligibility_path=self.ai_path,
            generated_at_utc="2026-07-21T08:40:00Z",
        )
        signal_plan = self.signal_root / C9_15W_PROFILE.signal_plan_path.name
        signal_plan.write_text(
            signal_plan.read_text(encoding="utf-8")
            + "jm.DCE,short,open,1\n",
            encoding="utf-8",
        )
        signal_plan.chmod(0o600)
        with self.assertRaisesRegex(
            ProductionAssetError,
            "(?:pending_cohort_invalid|signal_bundle_mismatch)",
        ):
            load_and_validate_production_daily_data_receipt(
                self.receipt_path,
                declared_data_link=self.data_link,
                expected_data_root=self.data_root,
                source_commit=self.commit,
                manifest_sha256=self.manifest_sha256,
                target_cutoff_date="2026-07-21",
                production_database_path=self.database,
                signal_input_root=self.signal_root,
                official_ai_eligibility_path=self.ai_path,
                validation_at_utc="2026-07-21T09:00:00Z",
            )

    def test_controlled_venv_link_rejects_group_writable_python_then_passes_hardened(self) -> None:
        root = Path(self.tempdir.name).resolve()
        venv_root = root / "main-venv"
        (venv_root / "bin").mkdir(parents=True, mode=0o700)
        formal = (
            venv_root
            / "lib/python3.11/site-packages/vnpy_ctp/api/libs"
        )
        formal.mkdir(parents=True, mode=0o700)
        for name in (
            "thostmduserapi_se.framework",
            "thosttraderapi_se.framework",
        ):
            (formal / name).mkdir(mode=0o700)
        python_binary = venv_root / "bin/python3.11"
        python_binary.write_bytes(b"test-python")
        python_binary.chmod(0o775)
        (venv_root / "bin/python").symlink_to("python3.11")
        venv_link = self.deploy_root / ".py311"
        venv_link.symlink_to(venv_root, target_is_directory=True)

        with self.assertRaisesRegex(
            ProductionAssetError,
            "python_security_invalid",
        ):
            validate_production_venv_link(
                declared_venv_link=venv_link,
                expected_venv_root=venv_root,
            )

        python_binary.chmod(0o755)
        observed_root, observed_python, frameworks = validate_production_venv_link(
            declared_venv_link=venv_link,
            expected_venv_root=venv_root,
        )
        self.assertEqual(venv_root.resolve(), observed_root)
        self.assertEqual(python_binary.resolve(), observed_python)
        self.assertEqual(formal.resolve(), frameworks[0])

    def test_initial_database_uses_sqlite_backup_and_private_destination(self) -> None:
        destination_dir = Path(self.tempdir.name).resolve() / "initial-db"
        destination_dir.mkdir(mode=0o700)
        destination_dir.chmod(0o700)
        destination = destination_dir / "database.db"

        initialize_production_database_from_sqlite_backup(
            source_path=self.database,
            destination_path=destination,
        )

        self.assertEqual(0o600, destination.stat().st_mode & 0o777)
        connection = sqlite3.connect(f"file:{destination}?mode=ro", uri=True)
        try:
            self.assertEqual(
                "ok",
                connection.execute("PRAGMA quick_check").fetchone()[0],
            )
            self.assertEqual(
                "2026-07-21 00:00:00",
                connection.execute("SELECT max(datetime) FROM dbbardata").fetchone()[0],
            )
        finally:
            connection.close()
        with self.assertRaisesRegex(
            ProductionAssetError,
            "destination_exists",
        ):
            initialize_production_database_from_sqlite_backup(
                source_path=self.database,
                destination_path=destination,
            )

    def test_stable_leaf_links_are_ignored_and_keep_tree_clean(self) -> None:
        root = Path(self.tempdir.name).resolve() / "git-clean-tree"
        root.mkdir(mode=0o700)
        (root / "examples/portfolio_backtesting").mkdir(parents=True)
        (root / ".gitignore").write_text(
            (ROOT / ".gitignore").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "add", ".gitignore"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=stage179-test",
                "-c",
                "user.email=stage179-test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "baseline",
            ],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        link_target = Path(self.tempdir.name).resolve() / "link-target"
        link_target.mkdir(mode=0o700)
        (root / ".py311").symlink_to(link_target, target_is_directory=True)
        (root / "examples/portfolio_backtesting/backtest_outputs").symlink_to(
            link_target,
            target_is_directory=True,
        )

        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertEqual("", status.stdout)

    def test_stage901_publishes_private_cohort_with_audit_seal_last(self) -> None:
        profile = replace(
            C9_15W_PROFILE,
            summary_path=self.signal_root / C9_15W_PROFILE.summary_path.name,
            signal_plan_path=self.signal_root / C9_15W_PROFILE.signal_plan_path.name,
            current_positions_path=(
                self.signal_root / C9_15W_PROFILE.current_positions_path.name
            ),
            pending_orders_path=(
                self.signal_root / C9_15W_PROFILE.pending_orders_path.name
            ),
            pending_orders_audit_path=(
                self.signal_root / C9_15W_PROFILE.pending_orders_audit_path.name
            ),
        )
        decision = {
            "analysis_end": "2026-07-21",
            "generated_at": "2026-07-21 16:35:00",
            "execution_profile": profile.profile_key,
            "official_live_version": profile.official_version,
            "capital": profile.capital,
            "capital_label": profile.capital_label,
        }
        pending = pd.DataFrame(
            [
                {
                    "vt_symbol": "jm.DCE",
                    "direction": "short",
                    "offset": "open",
                    "volume": 1,
                }
            ]
        )

        published_decision, published_pending, audit = (
            stage901._publish_execution_artifact_cohort(
                decision=decision,
                signal_plan=pd.DataFrame(
                    [{"vt_symbol": "jm.DCE", "direction": "short"}]
                ),
                current_positions=pd.DataFrame(
                    columns=["vt_symbol", "direction", "end_pos"]
                ),
                pending_orders=pending,
                profile=profile,
            )
        )

        self.assertEqual(audit["cohort_id"], published_decision["cohort_id"])
        self.assertEqual(audit["cohort_id"], published_pending.iloc[0]["cohort_id"])
        self.assertTrue(
            all(
                (path.stat().st_mode & 0o777) == 0o600
                for path in (
                    profile.summary_path,
                    profile.signal_plan_path,
                    profile.current_positions_path,
                    profile.pending_orders_path,
                    profile.pending_orders_audit_path,
                )
            )
        )
        validate_pending_artifact_cohort(
            profile,
            target_date="2026-07-21",
            pending_orders=pd.read_csv(
                profile.pending_orders_path,
                encoding="utf-8-sig",
            ),
            audit=json.loads(profile.pending_orders_audit_path.read_text()),
            artifact_hashes=artifact_hashes_for_profile(profile),
        )

        old_audit = profile.pending_orders_audit_path.read_bytes()
        original_replace = os.replace

        def fail_before_audit(source: object, destination: object) -> None:
            if Path(destination) == profile.pending_orders_audit_path:
                raise OSError("injected audit publish failure")
            original_replace(source, destination)

        with patch.object(stage901.os, "replace", side_effect=fail_before_audit):
            with self.assertRaisesRegex(OSError, "audit publish failure"):
                stage901._publish_execution_artifact_cohort(
                    decision={**decision, "generated_at": "2026-07-21 16:36:00"},
                    signal_plan=pd.DataFrame(
                        [{"vt_symbol": "lc.GFEX", "direction": "long"}]
                    ),
                    current_positions=pd.DataFrame(
                        columns=["vt_symbol", "direction", "end_pos"]
                    ),
                    pending_orders=pending,
                    profile=profile,
                )
        self.assertEqual(old_audit, profile.pending_orders_audit_path.read_bytes())
        with self.assertRaisesRegex(ValueError, "sha256_mismatch"):
            validate_pending_artifact_cohort(
                profile,
                target_date="2026-07-21",
                pending_orders=pd.read_csv(
                    profile.pending_orders_path,
                    encoding="utf-8-sig",
                ),
                audit=json.loads(profile.pending_orders_audit_path.read_text()),
                artifact_hashes=artifact_hashes_for_profile(profile),
            )

if __name__ == "__main__":
    unittest.main()
