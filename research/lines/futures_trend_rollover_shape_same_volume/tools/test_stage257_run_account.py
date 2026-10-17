"""Stage257 纯适配窄测；不运行经济回测。"""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

try:
    import stage257_run_account as runner
except ModuleNotFoundError:
    runner = None


U = [f"p{i:02}.X" for i in range(18)]
FU = "fu.SHFE"


def rows_for(d, members, policy="research"):
    return [dict(strategy=policy, score_type="research_membership", eval_date=d,
                 product_vt_symbol=p, score="0", score_rank=str(i), top_n=str(len(members)))
            for i, p in enumerate(members, 1)]


class Stage257RunnerTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(runner, "Stage257 runner implementation required")

    def test_variable_width_and_common_pre_ai_pool(self):
        rows = rows_for("2019-12-31", U + [FU]) + rows_for("2022-01-28", U[:8] + [FU])
        audit = runner.validate_pool_rows(rows, "research", U)
        self.assertEqual(audit["widths"], {"2019-12-31": 19, "2022-01-28": 9})
        self.assertEqual(audit["all_snapshot_count"], 2)

    def test_legacy18_requires_explicit_policy_and_other_snapshots_still_fu(self):
        rows = rows_for("2019-12-31", U) + rows_for("2022-01-28", U[:10] + [FU])
        with self.assertRaisesRegex(ValueError, "pre_ai"):
            runner.validate_pool_rows(rows, "research", U)
        result = runner.validate_pool_rows(rows, "research", U, legacy_pre_ai=True)
        self.assertEqual(result["widths"]["2019-12-31"], 18)

    def test_rejects_duplicate_nonfinite_wrong_width_and_wrong_fixed_fu_rank(self):
        original = rows_for("2019-12-31", U + [FU]) + rows_for("2022-01-28", U[:8] + [FU])
        for field, value in [("product_vt_symbol", U[1]), ("score", "nan"),
                             ("top_n", "11"), ("score_rank", "2")]:
            rows = [dict(r) for r in original]
            rows[-1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                runner.validate_pool_rows(rows, "research", U)

    def test_monthly_contract_members_and_width_are_binding(self):
        rows = rows_for("2019-12-31", U + [FU]) + rows_for("2022-01-28", U[:8] + [FU])
        contract = {"2022-01-28": {"U_members": U[:15], "K": 8}}
        runner.validate_pool_rows(rows, "research", U, snapshot_contracts=contract)
        contract["2022-01-28"]["K"] = 9
        with self.assertRaisesRegex(ValueError, "contract"):
            runner.validate_pool_rows(rows, "research", U, snapshot_contracts=contract)

    def test_window_is_registry_bound_and_alias_cannot_execute(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pool.csv"; p.write_text("frozen")
            entry = dict(window_id="FULL", pool_id="P", start="2020-01-01", end="2026-10-14",
                         pool_file=str(p), pool_sha256=runner.sha256(p), policy_id="research", kind="random_monthly", path_id=1)
            manifest = dict(capital=150000, policies={"P": {k:entry[k] for k in ("pool_file", "pool_sha256", "policy_id", "kind", "path_id")}},
                            windows=[dict(window_id="FULL", start=entry["start"], end=entry["end"])],
                            accounts={"RUN":entry}, aliases={"ALIAS":"RUN"})
            self.assertEqual(runner.validate_registry_account(manifest, "RUN")["window_id"], "FULL")
            with self.assertRaisesRegex(ValueError, "alias"):
                runner.validate_registry_account(manifest, "ALIAS")
            entry["end"] = "2025-12-31"
            with self.assertRaisesRegex(ValueError, "window"):
                runner.validate_registry_account(manifest, "RUN")

    def test_required_months_keep_pre_ai_boundary_and_missing_month_fails(self):
        available = ["2019-12-31", "2022-01-28", "2022-02-28"]
        self.assertEqual(runner.require_window_snapshots(available, ["2019-12-31", "2020-01-23", "2022-01-28"]), ["2019-12-31", "2022-01-28"])
        with self.assertRaisesRegex(ValueError, "missing_required"):
            runner.require_window_snapshots(available, ["2022-03-31"])

    def test_private_builder_outputs_preserve_shared_files_and_restore_on_exception(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); shared = root / "shared"; shared.mkdir()
            attrs = ("UNIVERSE_PATH", "AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH", "AI_SATELLITE_ELIGIBILITY_PATH")
            module = SimpleNamespace(**{name:shared/(name+".csv") for name in attrs})
            for name in attrs: getattr(module, name).write_text(name)
            original = {name:getattr(module,name) for name in attrs}
            with self.assertRaisesRegex(RuntimeError, "stop"):
                with runner.private_builder_paths(module, root/"private") as paths:
                    for name in attrs:
                        self.assertNotEqual(getattr(module,name), original[name])
                        getattr(module,name).write_text("private-write")
                        self.assertEqual(original[name].read_text(), name)
                    self.assertEqual(set(paths), set(attrs))
                    raise RuntimeError("stop")
            for name in attrs: self.assertEqual(getattr(module,name), original[name])

    def test_adaptation_preserves_risk_costs_and_restores_every_patch(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); pool = root/"pool.csv"; pool.write_text("pool")
            private = root/"private.csv"; private.write_text("universe")
            reference = root/"accepted.json"
            original_settings = dict(enable_stage847_half_r_stop_retry=True, enable_ai_product_pool_filter=True,
                ai_product_pool_strategy=runner.OFFICIAL_POLICY, ai_product_pool_eligibility_path="old", product_universe_csv_path="old-universe", risk_multiplier=0.4)
            reference.write_text(json.dumps({"spec":{"overrides":original_settings}}))
            build = lambda:dict(original_settings)
            s901=SimpleNamespace(build_official_live_strategy_overrides=build)
            old_declared=lambda *_:None; old_audit=lambda *_:dict(status="valid",eligibility_sha256="official")
            stage251=SimpleNamespace(declared_ablation=old_declared,audit_historical_ai_pool=old_audit)
            audit=dict(all_eval_dates=["2019-12-31", "2022-01-28"],all_snapshot_count=2)
            with runner.adapted_stage251(stage251,pool,"research",reference,audit,root,root/"baseline",private):
                with stage251.declared_ablation(s901,"C"):
                    got=s901.build_official_live_strategy_overrides()
                    self.assertFalse(got["enable_stage847_half_r_stop_retry"])
                    self.assertEqual(got["risk_multiplier"],0.4)
                    self.assertEqual(got["product_universe_csv_path"],str(private))
                comparison=json.loads(reference.read_text())["spec"]["overrides"]
                self.assertEqual(comparison["product_universe_csv_path"],str(root.resolve()/"baseline/private.csv"))
                self.assertEqual(stage251.audit_historical_ai_pool(pool,["2020-01-23", "2022-01-28"])["scope"],"Stage257 frozen research eligibility")
            self.assertIs(stage251.declared_ablation,old_declared)
            self.assertIs(stage251.audit_historical_ai_pool,old_audit)
            self.assertIs(s901.build_official_live_strategy_overrides,build)
            self.assertEqual(json.loads(reference.read_text())["spec"]["overrides"],original_settings)

    def test_stage257_export_identity_replaces_inherited_labels(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)
            (out/"metrics.json").write_text(json.dumps(dict(variant="stage251_C_half_r_ablation",label="Stage251 C",total_return=3)))
            (out/"run_provenance.json").write_text(json.dumps(dict(arm="C",source_scope="Stage251",minute_input_sha256="x")))
            (out/"daily.csv").write_text("date,balance,profile,result_scope\n2020-01-02,150000,stage251_C_half_r_ablation,offline_half_r_ablation\n")
            runner.relabel_exports(out,"FULL__R001",dict(window_id="FULL",pool_id="R001"))
            metrics=json.loads((out/"metrics.json").read_text())
            self.assertEqual(metrics["variant"],"stage257_FULL__R001")
            self.assertEqual(metrics["total_return"],3)
            self.assertEqual(json.loads((out/"run_provenance.json").read_text())["stage"],257)
            self.assertNotIn("stage251_C_half_r_ablation",(out/"daily.csv").read_text())

    def test_runtime_supported_universe_is_captured_before_trading(self):
        class Engine:
            capital=150000
            def add_strategy(self, cls, setting):
                self.strategy=SimpleNamespace(product_symbols=setting["products"],
                    states=dict.fromkeys(setting["products"]),pos_data=setting.get("positions",{}))
        original=Engine.add_strategy
        expected=sorted(runner.NON_FU_UNIVERSE+[FU])
        with runner.capture_supported_products(Engine) as captured:
            Engine().add_strategy(None,{"products":expected})
            self.assertEqual(captured[0]["actual_supported_symbols"],expected)
            self.assertEqual(captured[0]["actual_product_state_keys"],expected)
            self.assertEqual(captured[0]["initial_positions"],{})
            with self.assertRaisesRegex(ValueError,"initial_account"):
                Engine().add_strategy(None,{"products":expected,"positions":{"rb2601.SHFE":1}})
            with self.assertRaisesRegex(ValueError,"loaded_universe"):
                Engine().add_strategy(None,{"products":expected[:-1]})
        self.assertIs(Engine.add_strategy,original)


if __name__ == "__main__": unittest.main()
