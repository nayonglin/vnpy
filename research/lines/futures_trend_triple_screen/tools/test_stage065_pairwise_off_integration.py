"""Two finite real native/B boundaries; no replay, data load or model inference."""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import stage022_run_c0_qualified_wait as runtime

LINE = Path(__file__).resolve().parents[1]
EVIDENCE = LINE / "outputs/stage070_pairwise_off_policy_implementation"
_RUNTIME = tempfile.TemporaryDirectory(prefix="stage070_policy_test_")
runtime.OUTPUT = Path(_RUNTIME.name) / "runtime"
runtime.configure_runtime(Path(_RUNTIME.name) / "shared")

import pandas as pd
import joblib
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as native
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
import qmt_roll_portfolio_strategy as qmt
import qmt_roll_ai_selection_pairwise_runtime as pairwise
from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

try:
    policy = importlib.import_module("stage065_pairwise_off_policy")
except ModuleNotFoundError as error:
    if error.name != "stage065_pairwise_off_policy":
        raise
    policy = None

NATIVE = native.QmtRollPortfolioStrategyStage847C9StopRetry
ENGINE = native.Stage847StopRetryEngine
DAY = "2026-01-06"
PRODUCTS = ["AP.CZCE", "au.SHFE", "rb.SHFE"]
CONTRACTS = ["AP605.CZCE", "au2606.SHFE", "rb2605.SHFE"]
OFF_KEYS = {
    "enable_selection_pairwise_v2", "enable_selection_pairwise_v2_catastrophic_veto",
    "enable_selection_pairwise_v2_catastrophic_hard_filter", "enable_selection_pairwise_v2_volume_tilt",
    "selection_pairwise_volume_tilt_strength", "selection_pairwise_volume_tilt_long_strength",
    "selection_pairwise_volume_tilt_short_strength", "incremental_margin_budget_gate_protected_selection_rank",
}
EXPECTED_OFF = dict.fromkeys((
    "enable_selection_pairwise_v2", "enable_selection_pairwise_v2_catastrophic_veto",
    "enable_selection_pairwise_v2_catastrophic_hard_filter", "enable_selection_pairwise_v2_volume_tilt"), False)
EXPECTED_OFF.update(selection_pairwise_volume_tilt_strength=0., selection_pairwise_volume_tilt_long_strength=0.,
    selection_pairwise_volume_tilt_short_strength=0., incremental_margin_budget_gate_protected_selection_rank=0)


def emit(name, value):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / name).write_text(json.dumps(runtime.json_safe(value), ensure_ascii=False, indent=2) + "\n")


class Weekly:
    def get(self, day, product):
        return dict(ready=True, direction=1, weekly_asof="2026-01-02")


def bar(contract, stamp=DAY, opening=95., high=99., low=89., close=95., volume=300., oi=200.):
    name, exchange = contract.split(".")
    return BarData(symbol=name, exchange=Exchange(exchange), datetime=pd.Timestamp(stamp).to_pydatetime(),
        gateway_name="FINITE_FIXTURE", open_price=opening, high_price=high, low_price=low,
        close_price=close, volume=volume, open_interest=oi)


def tiny_paths(root):
    mapping, universe = root / "mapping.csv", root / "universe.csv"
    # Deliberately reverse rows: real constructor metadata must restore product sort order.
    pd.DataFrame([dict(date=day, continuous_symbol_vt=p, main_contract_vt=c)
        for day in ("2026-01-05", DAY, "2026-01-07")
        for p, c in reversed(list(zip(PRODUCTS, CONTRACTS)))]).to_csv(mapping, index=False)
    pd.DataFrame(dict(product_vt_symbol=PRODUCTS)).to_csv(universe, index=False)
    return dict(mapping_csv_path=str(mapping), product_universe_csv_path=str(universe))


def metadata():
    return dict(vt_symbols=CONTRACTS, product_symbols=PRODUCTS,
        rates={c: .001 for c in CONTRACTS}, slippages={c: 1. for c in CONTRACTS},
        sizes={c: 10 for c in CONTRACTS}, priceticks={c: 1. for c in CONTRACTS},
        margin_ratios={c: .1 for c in CONTRACTS})


def instantiate(strategy_class, engine_class, settings):
    engine = engine_class({})
    engine.capital = float(settings.get("capital_base", 150000.))
    engine.datetime = datetime.fromisoformat(DAY)
    engine.sizes = {c: 10 for c in CONTRACTS}
    engine.priceticks = {c: 1. for c in CONTRACTS}
    engine.rates = {c: .001 for c in CONTRACTS}
    engine.slippages = {c: 1. for c in CONTRACTS}
    engine.bars = {c: bar(c) for c in CONTRACTS}
    strategy = strategy_class(engine, "finite-pairwise-off", CONTRACTS, settings)
    engine.strategy = strategy
    return strategy, engine


class PairwiseOffIntegrationTests(unittest.TestCase):
    def need_policy(self):
        self.assertIsNotNone(policy, "new shared OFF policy is absent at the real native/B boundary")
        return policy

    def test_disabled_profiles_native_and_b_no_model(self):
        # Catches missing final OFF projection, MRO override and any model access.
        p = self.need_policy()
        self.assertEqual(dict(p.OFF_SETTINGS), EXPECTED_OFF)
        meta = metadata()
        formal = runtime.capture_formal_profile(s901, meta, pd.Timestamp(runtime.START), pd.Timestamp(runtime.END))
        before = asdict(formal["spec"]), dict(formal)
        runner = importlib.import_module("stage065_run_pairwise_off")
        # Root's external data-tool binding contract is independent of whole
        # prepare/data/native execution; source files are hashed, never imported.
        import hashlib
        with tempfile.TemporaryDirectory(prefix="stage084_scope_binding_") as scope_temp:
            scope_root=Path(scope_temp).resolve()
            scope_sources=(scope_root/"scope.py",scope_root/"provider.py")
            with patch.object(runner,"DATA_SCOPE_SOURCES",scope_sources):
                self.assertFalse(runner.data_scope_bindings()['data_scope_ready'])
                for path in scope_sources:path.write_text("raise AssertionError('source must not execute')\n")
                unreviewed=runner.data_scope_bindings()
                self.assertFalse(unreviewed['data_scope_ready'])
                expected_sources={str(path):dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
                    for path in scope_sources}
                self.assertEqual(unreviewed['source_bindings'],expected_sources)
                review=scope_root/"review.json"
                review.write_text(json.dumps(dict(independent_review=True,p0_findings=0,p1_findings=0,
                    source_bindings=expected_sources)))
                reviewed=runner.data_scope_bindings(review,hashlib.sha256(review.read_bytes()).hexdigest())
                self.assertTrue(reviewed['data_scope_ready'])
                self.assertEqual(reviewed['source_bindings'],expected_sources)
                provider=scope_sources[1];old=provider.read_bytes();provider.write_bytes(old+b"# changed\n")
                with self.assertRaisesRegex(ValueError,"source_review"):
                    runner.data_scope_bindings(review,hashlib.sha256(review.read_bytes()).hexdigest())
                provider.write_bytes(old)
        reference = s901.s847.s827.s772._build_setting(metadata=meta, spec=formal["spec"],
            base_c3_overrides=dict(s901.s513._c3_overrides(pd.Timestamp(runtime.START).to_pydatetime())),
            start=pd.Timestamp(runtime.START))
        self.assertTrue(reference["enable_selection_pairwise_v2"])
        self.assertEqual(reference["selection_pairwise_volume_tilt_long_strength"], .15)
        calls = dict(load=0, runtime=0, score=0, predict=0, fit=0, old_smoke=0)
        def forbidden(name):
            def fail(*args, **kwargs):
                calls[name] += 1
                raise AssertionError("forbidden model path: " + name)
            return fail
        from sklearn.pipeline import Pipeline
        records = []
        with tempfile.TemporaryDirectory(prefix="stage070_construct_") as temp, ExitStack() as stack:
            paths = tiny_paths(Path(temp))
            stack.enter_context(patch.object(joblib, "load", forbidden("load")))
            stack.enter_context(patch.object(pairwise.SelectionPairwiseRuntimeModel, "__init__", forbidden("runtime")))
            stack.enter_context(patch.object(pairwise.SelectionPairwiseRuntimeModel, "score_candidate_pool", forbidden("score")))
            for name in ("predict", "predict_proba"):
                stack.enter_context(patch.object(Pipeline, name, forbidden("predict")))
            stack.enter_context(patch.object(Pipeline, "fit", forbidden("fit")))
            stack.enter_context(patch.object(runtime, "model_runtime_smoke", forbidden("old_smoke")))
            for arm in ("A_OFF", "B_OFF"):
                off = p.make_off_profile(formal, arm)
                projected, projected_engine = runner.build_account_profile(formal, arm, NATIVE, ENGINE,
                    weekly=Weekly(), fi={}, next_days={}, qualify=lambda *args: None)
                self.assertEqual(projected["spec"].overrides["enable_selection_pairwise_v2"], False)
                self.assertEqual(projected["spec"].overrides["selection_pairwise_volume_tilt_long_strength"], 0.)
                self.assertEqual(projected["strategy_cls"] is NATIVE, arm == "A_OFF")
                fake847=SimpleNamespace(START=pd.Timestamp("2000-01-01"), END=pd.Timestamp("2001-01-01"),
                    Stage847StopRetryEngine=ENGINE,s827=SimpleNamespace(_GLOBAL_MINUTE_BY_SYMBOL={"before":1}))
                def run_direct(profile, metadata):
                    self.assertIs(profile["strategy_cls"], projected["strategy_cls"])
                    self.assertIs(fake847.Stage847StopRetryEngine, projected_engine)
                    self.assertFalse(profile["spec"].overrides["enable_selection_pairwise_v2"])
                    return pd.DataFrame({"date":[pd.Timestamp(DAY)]}), {"tiny":pd.DataFrame({"event":["fixture"]})}
                fake847._run_profile=run_direct
                fake901=SimpleNamespace(s847=fake847,_run_live_c9=forbidden("old_smoke"))
                original_global=fake847.s827._GLOBAL_MINUTE_BY_SYMBOL
                daily, exported, spec=runner.run_profile_once(fake901,projected,meta,
                    engine_class=projected_engine,start=pd.Timestamp(runtime.START),end=pd.Timestamp(runtime.END),
                    minute_audit=dict(source="tiny_dispatch",loaded_symbol_count=3))
                self.assertIs(spec,projected["spec"])
                self.assertEqual(daily.account_capital.tolist(),[150000.])
                self.assertEqual(daily.minute_source.tolist(),["tiny_dispatch"])
                self.assertEqual(exported["tiny"].profile.tolist(),[spec.profile])
                self.assertEqual(fake847.START,pd.Timestamp("2000-01-01"))
                self.assertEqual(fake847.END,pd.Timestamp("2001-01-01"))
                self.assertIs(fake847.s827._GLOBAL_MINUTE_BY_SYMBOL,original_global)
                self.assertIs(fake847.Stage847StopRetryEngine,ENGINE)
                self.assertEqual(asdict(formal["spec"]), before[0])
                self.assertEqual(formal, before[1])
                self.assertEqual(off["spec"].capital, formal["spec"].capital)
                self.assertEqual(off["profile"], formal["profile"])
                requested = s901.s847.s827.s772._build_setting(metadata=meta, spec=off["spec"],
                    base_c3_overrides=dict(s901.s513._c3_overrides(pd.Timestamp(runtime.START).to_pydatetime())),
                    start=pd.Timestamp(runtime.START))
                self.assertEqual(set(p.OFF_SETTINGS), OFF_KEYS)
                self.assertEqual(requested, p.expected_off_settings(reference))
                strategy_cls, engine_cls = p.select_account_classes(arm, NATIVE, ENGINE,
                    weekly=Weekly(), fi={}, next_days={}, qualify=lambda *args: None)
                if arm == "A_OFF":
                    self.assertIs(strategy_cls, NATIVE)
                    self.assertIs(engine_cls, ENGINE)
                else:
                    self.assertEqual(strategy_cls.__name__, "Stage035IndependentB_TS")
                    self.assertIn(NATIVE, strategy_cls.__mro__)
                    self.assertIn(ENGINE, engine_cls.__mro__)
                # Only tiny mapping resources differ from the real formal settings.
                fixture_requested = {**requested, **paths}
                fixture_reference = {**reference, **paths}
                strategy, engine = instantiate(strategy_cls, engine_cls, fixture_requested)
                # Stage022 also treats these two fields as engine metadata.
                account_fields = {key for key in fixture_requested
                    if not hasattr(strategy, key) and key in ("account_capital", "c3_capital")}
                self.assertTrue(all(fixture_requested[key] == engine.capital for key in account_fields))
                actual = {key: engine.capital if key in account_fields else getattr(strategy, key)
                    for key in fixture_requested}
                delta = p.check_settings_delta(fixture_reference, fixture_requested, actual,
                    shared=Path(_RUNTIME.name)/"shared", reference_shared=Path(_RUNTIME.name)/"shared")
                self.assertEqual(set(delta["allowed_keys"]), OFF_KEYS)
                self.assertTrue(delta["actual_settings_match_off_expected"])
                self.assertTrue(strategy.stage827_require_complete_minutes)
                effective = p.check_effective_off_policy(strategy)
                self.assertIsNone(strategy.selection_pairwise_runtime)
                self.assertIsNone(strategy.ai_path_damage_runtime)
                self.assertTrue(strategy.enable_ai_product_pool_filter)
                self.assertEqual(strategy.ai_product_pool_eligibility_path, reference["ai_product_pool_eligibility_path"])
                if arm == "B_OFF":
                    self.assertEqual(strategy.ts_machine.arm, "B_TS")
                preflight = p.disabled_pairwise_preflight()
                self.assertEqual(preflight["status"], "disabled_by_shared_pairwise_free_policy")
                # Requested reference omission is resolved from native declaration defaults.
                omitted = {k:v for k,v in fixture_reference.items() if k != "incremental_margin_budget_gate_protected_selection_rank"}
                omitted_delta = p.check_settings_delta(omitted, fixture_requested, actual,
                    shared=Path(temp), reference_shared=Path(temp))
                self.assertEqual(omitted_delta["declared_defaults_used"]["incremental_margin_budget_gate_protected_selection_rank"], 0)
                for drift_key, drift_value in (("risk_ratio_of_total_assets", .777),
                        ("ai_product_pool_eligibility_path", "/tmp/unexpected-pool"), ("unknown_new_path", "/tmp/x")):
                    bad = {**fixture_requested, drift_key: drift_value}
                    with self.assertRaisesRegex(ValueError, "settings"):
                        p.check_settings_delta(fixture_reference, bad, bad,
                            shared=Path(temp), reference_shared=Path(temp))
                bad_actual = {**actual, "incremental_margin_budget_gate_protected_selection_rank": 1}
                with self.assertRaisesRegex(ValueError, "settings"):
                    p.check_settings_delta(omitted, fixture_requested, bad_actual,
                        shared=Path(temp), reference_shared=Path(temp))
                records.append(dict(arm=arm, strategy=strategy_cls.__name__, engine=engine_cls.__name__,
                    strategy_mro=[cls.__name__ for cls in strategy_cls.__mro__],
                    engine_mro=[cls.__name__ for cls in engine_cls.__mro__], delta=delta,
                    effective=effective, preflight=preflight, omitted_reference_delta=omitted_delta,
                    fixture_requested=fixture_requested, fixture_actual=actual,
                    engine_metadata_fields=sorted(account_fields)))
        self.assertEqual(calls, dict.fromkeys(calls, 0))
        emit("test1.json", dict(status="passed_finite_real_boundary", cases=records, spies=calls,
            numerical_stack={name:sys.modules[name].__version__ for name in ("numpy","pandas","sklearn","joblib")},
            financial_replays=0, production_qualified=False))

    def test_real_planner_fallback_slot_margin_and_b_final_budget(self):
        # New common policy is the missing boundary; frozen native code stays intact.
        p = self.need_policy()
        self.assertEqual(set(p.OFF_SETTINGS), OFF_KEYS)
        self.assertEqual(p.disabled_pairwise_preflight()["fallback"], "metadata_sorted_product_insertion_order")
        records = self.planner_cases(p)
        final = self.b_product_loop(p)
        emit("test2.json", dict(status="passed_finite_real_planner_and_product_loop", planner=records,
            b_final_budget=final, financial_replays=0, production_qualified=False))

    def test_real_fill_identity_checkpoint_and_pure_export(self):
        # Breaks caught: fabricated native provenance, lost actual mother identity,
        # unbound deserialization or pure export silently executing financial/data paths.
        try:
            cp = importlib.import_module("stage065_account_checkpoint")
        except ModuleNotFoundError as error:
            if error.name != "stage065_account_checkpoint":
                raise
            cp = None
        self.assertIsNotNone(cp, "neutral account-only checkpoint/export is absent")
        import hashlib
        import shutil
        import sqlite3
        import types
        import vnpy.trader.database as database
        import vnpy_portfoliostrategy.backtesting as backtesting
        from stage031_run_ordered_checkpoint import build_execution_clock
        from sklearn.pipeline import Pipeline
        import stage065_run_pairwise_off as runner
        records, rejects = [], []
        with tempfile.TemporaryDirectory(prefix="stage076_checkpoint_") as temp:
            base = Path(temp).resolve()
            source_fixture = base / "bound_fixture_source.py"
            source_fixture.write_text("# pinned fixture source, not a future runner\n")
            for arm in ("A_OFF", "B_OFF"):
                payload, classes, fill_evidence = self.checkpoint_fill_fixture(arm, base / arm)
                source_paths = [*cp.REQUIRED_SOURCES, source_fixture]
                sources = {str(x): dict(sha256=hashlib.sha256(x.read_bytes()).hexdigest(),bytes=x.stat().st_size)
                    for x in source_paths}
                preflight = dict(fixture_only=True, reference_calendar_scope="tiny_fixture",
                    reference_calendar=["2026-01-07"], source_bindings=sources,
                    data_bindings={str(base/arm/"mapping.csv"):dict(
                        sha256=hashlib.sha256((base/arm/"mapping.csv").read_bytes()).hexdigest(),
                        bytes=(base/arm/"mapping.csv").stat().st_size)},
                    account_classes=classes, disabled_pairwise=policy.disabled_pairwise_preflight())
                output = base / "snapshots" / arm
                context = cp.new_run_context(output,arm=arm,preflight=preflight,started_at="2026-10-18T06:00:00+08:00")
                payload.update(preflight=preflight,run_context=context)
                manifest = cp.save_raw_checkpoint(output,payload)
                raw = output/"checkpoint/raw_account.pkl.gz"
                self.assertTrue(raw.is_file())
                self.assertFalse((output/"checkpoint/validation_seal.json").exists())
                validation = dict(cp.ENGINE_VALIDATION,fixture_only=True,
                    reference_calendar_scope="tiny_fixture",actual_daily_count=1)
                for bad in (dict(validation,actual_settings_match_off_expected=False),
                        dict(validation,engine_returned=False),dict(validation,actual_daily_count=1641)):
                    with self.assertRaisesRegex(ValueError,"validat"):
                        cp.seal_checkpoint(output,manifest,bad)
                    self.assertTrue(raw.is_file())
                    self.assertFalse((output/"checkpoint/validation_seal.json").exists())
                    self.assertFalse((output/"summary.json").exists())
                seal=cp.seal_checkpoint(output,manifest,validation)
                self.assertTrue(seal["fixture_only"])
                restored,binding=cp.load_sealed_checkpoint(output,arm=arm)
                self.assertEqual(restored["ordered"] is None,arm=="A_OFF")
                clock,usage=build_execution_clock(restored["capture"],restored["actual_trade_identities"])
                self.assertEqual(len(clock),4)
                self.assertEqual(clock.signal_order_id.nunique(),1)
                self.assertEqual(clock.signal_identity_source.unique().tolist(),["actual_TradeData_explicit"])
                self.assertNotIn("signal_datetime",restored["capture"]["usage"][1])
                for mutation in ("missing_parent","usage_signal_conflict","ordinary_signal_missing"):
                    capture=deepcopy(restored["capture"]);identities=deepcopy(restored["actual_trade_identities"])
                    if mutation=="missing_parent": identities[1]["intraday_episode_id"]="BACKTEST.missing"
                    elif mutation=="usage_signal_conflict": capture["usage"][1]["signal_order_id"]="WRONG.order"
                    else: capture["usage"][0].pop("signal_order_id")
                    with self.assertRaises(ValueError):build_execution_clock(capture,identities)
                    rejects.append(arm+":"+mutation)
                # Every mutation is restored to the exact prior bytes, no cloned-owner shortcut.
                targets=[raw,output/"checkpoint/raw_manifest.json",output/"checkpoint/validation_seal.json",
                    output/"run_context.json",output/"preflight_used.json",source_fixture,
                    output/next(iter(context["source_snapshots"].values()))["snapshot"]]
                for target in targets:
                    original=target.read_bytes()
                    target.write_bytes(original+b" ")
                    try:
                        with patch.object(cp.pickle,"loads",side_effect=AssertionError("must reject before deserialize")):
                            with self.assertRaises(ValueError):cp.load_sealed_checkpoint(output,arm=arm)
                    finally:target.write_bytes(original)
                    rejects.append(arm+":tamper:"+target.name)
                sealpath=output/"checkpoint/validation_seal.json"
                original_seal=sealpath.read_bytes();sealpath.unlink()
                with patch.object(cp.pickle,"loads",side_effect=AssertionError("unsealed deserialize")):
                    with self.assertRaises(ValueError):cp.load_sealed_checkpoint(output,arm=arm)
                    with self.assertRaises(ValueError):cp.load_sealed_checkpoint(output,arm="B_OFF" if arm=="A_OFF" else "A_OFF")
                sealpath.write_bytes(original_seal)
                rejects.extend([arm+":unsealed",arm+":cross_arm"])
                moved=raw.with_suffix(".saved");raw.rename(moved);raw.symlink_to(moved)
                try:
                    with patch.object(cp.pickle,"loads",side_effect=AssertionError("symlink deserialize")):
                        with self.assertRaises(ValueError):cp.load_sealed_checkpoint(output,arm=arm)
                finally:raw.unlink();moved.rename(raw)
                rejects.append(arm+":symlink")
                external=base/"external"/arm
                shutil.copytree(output,external)
                with patch.object(cp.pickle,"loads",side_effect=AssertionError("external snapshot deserialize")):
                    with self.assertRaises(ValueError):cp.load_sealed_checkpoint(external,arm=arm)
                rejects.append(arm+":external_copy")
                reads={};real_read=cp._read_regular
                def read_once(path):
                    key=str(path);reads[key]=reads.get(key,0)+1
                    if reads[key]>1:raise AssertionError("pinned bytes reopened: "+key)
                    return real_read(path)
                with patch.object(cp,"_read_regular",side_effect=read_once):
                    cp.load_sealed_checkpoint(output,arm=arm)
                for target in (raw,output/"checkpoint/raw_manifest.json",sealpath,output/"run_context.json"):
                    self.assertEqual(reads[str(target)],1)
                export_calls=dict(engine=0,replay=0,data=0,accepted061=0,database=0,minute=0,model=0,predict=0)
                def forbid(name):
                    def failed(*args,**kwargs):
                        export_calls[name]+=1
                        raise AssertionError("export-only touched "+name)
                    return failed
                fake061=types.ModuleType("stage061_accepted_wait_delta")
                fake061.load_accepted_delta=forbid("accepted061")
                with ExitStack() as stack:
                    stack.enter_context(patch.dict(sys.modules,{"stage061_accepted_wait_delta":fake061}))
                    for cls in (ENGINE,NATIVE):stack.enter_context(patch.object(cls,"__init__",forbid("engine")))
                    stack.enter_context(patch.object(ENGINE,"run_backtesting",forbid("replay")))
                    stack.enter_context(patch.object(ENGINE,"load_data",forbid("data")))
                    stack.enter_context(patch.object(runtime,"read_data_stack",forbid("data")))
                    stack.enter_context(patch.object(pd,"read_csv",forbid("data")))
                    stack.enter_context(patch.object(pd,"read_parquet",forbid("data")))
                    stack.enter_context(patch.object(sqlite3,"connect",forbid("database")))
                    stack.enter_context(patch.object(database,"get_database",forbid("database")))
                    stack.enter_context(patch.object(backtesting,"get_database",forbid("database")))
                    stack.enter_context(patch.object(s901,"_ensure_c9_minute_bars",forbid("minute")))
                    stack.enter_context(patch.object(s901,"_load_stage861_full_minute_bars",forbid("minute")))
                    stack.enter_context(patch.object(joblib,"load",forbid("model")))
                    stack.enter_context(patch.object(pairwise.SelectionPairwiseRuntimeModel,"__init__",forbid("model")))
                    stack.enter_context(patch.object(pairwise.SelectionPairwiseRuntimeModel,"score_candidate_pool",forbid("predict")))
                    stack.enter_context(patch.object(runtime,"model_runtime_smoke",forbid("model")))
                    stack.enter_context(patch.object(Pipeline,"predict",forbid("predict")))
                    stack.enter_context(patch.object(Pipeline,"predict_proba",forbid("predict")))
                    stack.enter_context(patch.object(Pipeline,"fit",forbid("model")))
                    stack.enter_context(patch.object(runner,"prepare_account",forbid("data")))
                    stack.enter_context(patch.object(runner,"execute_account",forbid("engine")))
                    stack.enter_context(patch.object(runner,"OUTPUT",base/"snapshots"))
                    first=cp.reserve_export_destination(output,arm=arm)
                    def bad_metrics(*args):raise RuntimeError("metrics export sentinel")
                    with self.assertRaisesRegex(RuntimeError,"metrics export sentinel"):
                        cp.export_checkpoint(output,first,arm=arm,metrics_function=bad_metrics,export_only=True)
                    self.assertTrue((first/"export_failure.json").is_file())
                    self.assertFalse((first/"summary.json").exists())
                    second=output/"exports/export_002"
                    previous_runtime_output=runtime.OUTPUT
                    self.assertEqual(runner.main(["--arm",arm,"--export-only"]),0)
                    self.assertIs(runtime.OUTPUT,previous_runtime_output)
                    summary=json.loads((second/"summary.json").read_text())
                    with self.assertRaises(FileExistsError):cp.reserve_export_destination(output,arm=arm)
                self.assertEqual(export_calls,dict.fromkeys(export_calls,0))
                self.assertEqual(summary["arm"],arm)
                self.assertEqual(summary["ordered_applicable"],arm=="B_OFF")
                self.assertEqual(summary["ordered_counts"] is None,arm=="A_OFF")
                self.assertEqual(summary["signal_machine_arm"],"B_TS" if arm=="B_OFF" else None)
                self.assertEqual(summary["financial_replays"],0)
                self.assertTrue(summary["fixture_only"])
                self.assertEqual(summary["financial_replays_this_export_process"],0)
                self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(),manifest["raw_sha256"])
                self.assertEqual(sealpath.read_bytes(),original_seal)
                self.assertEqual((second/"ordered_gate_audit.csv").exists(),arm=="B_OFF")
                exported=pd.read_csv(second/"trades.csv")
                self.assertEqual(exported.research_arm.unique().tolist(),[arm])
                self.assertEqual(exported.trading_date.unique().tolist(),["2026-01-07"])
                self.assertEqual(summary["statistics"]["end_equity"],float(payload["combined"].account_equity.iloc[-1]))
                records.append(dict(arm=arm,fill=fill_evidence,classes=classes,summary=summary,
                    checkpoint_binding=binding,single_read_counts=reads,export_only_spies=export_calls,
                    raw_survived_validation_failure=True,seal_survived_export_failure=True))
            self.assertIsNone(cp.write_comparison_if_ready(base/"snapshots"))
            source_failed=base/"source_guard"/"B_OFF"
            source_context=cp.new_run_context(source_failed,arm="B_OFF",preflight=preflight,started_at="source-guard")
            source_payload={**payload,"run_context":source_context}
            old_source=source_fixture.read_bytes();source_fixture.write_bytes(old_source+b"# changed after engine\n")
            try:
                source_manifest=cp.save_raw_checkpoint(source_failed,source_payload)
                with self.assertRaisesRegex(ValueError,"source_binding"):
                    cp.seal_checkpoint(source_failed,source_manifest,validation)
                self.assertTrue((source_failed/"checkpoint/raw_account.pkl.gz").is_file())
                self.assertFalse((source_failed/"checkpoint/validation_seal.json").exists())
            finally:source_fixture.write_bytes(old_source)
            clock_failed=base/"clock_guard"/"B_OFF"
            clock_context=cp.new_run_context(clock_failed,arm="B_OFF",preflight=preflight,started_at="clock-guard")
            clock_payload=deepcopy(payload);clock_payload["run_context"]=clock_context
            clock_payload["actual_trade_identities"][1]["intraday_episode_id"]="MISSING.parent"
            clock_manifest=cp.save_raw_checkpoint(clock_failed,clock_payload)
            cp.seal_checkpoint(clock_failed,clock_manifest,validation)
            bad_export=cp.reserve_export_destination(clock_failed,arm="B_OFF")
            with self.assertRaisesRegex(ValueError,"parent_missing"):
                cp.export_checkpoint(clock_failed,bad_export,arm="B_OFF",export_only=True)
            self.assertTrue((clock_failed/"checkpoint/validation_seal.json").is_file())
            self.assertTrue((bad_export/"export_failure.json").is_file())
            self.assertFalse((bad_export/"summary.json").exists())
            objects_failed=base/"objects_guard"/"B_OFF"
            objects_context=cp.new_run_context(objects_failed,arm="B_OFF",preflight=preflight,started_at="object-guard")
            objects_payload={**payload,"run_context":objects_context,"frames":{
                **payload["frames"],"hidden_object":pd.DataFrame({"payload":[object()]})}}
            with self.assertRaisesRegex(ValueError,"non_account_object"):
                cp.save_raw_checkpoint(objects_failed,objects_payload)
            self.assertFalse((objects_failed/"checkpoint/raw_account.pkl.gz").exists())
            # Incomplete engine return only persists marked partial evidence, never a seal.
            partial=base/"partial"/"A_OFF"
            preflight["account_classes"]=records[0]["classes"]
            cp.new_run_context(partial,arm="A_OFF",preflight=preflight,started_at="partial")
            with self.assertRaisesRegex(ValueError,"incomplete"):
                cp.save_raw_checkpoint(partial,dict(capture={"failures":["engine did not return"]}))
            self.assertTrue((partial/"failure_capture.pkl.gz").is_file())
            self.assertTrue(json.loads((partial/"run_failure.json").read_text())["partial"])
            self.assertFalse((partial/"checkpoint/validation_seal.json").exists())
        self.assertEqual(policy.__file__,str(Path(__file__).with_name("stage065_pairwise_off_policy.py")))
        evidence=dict(status="passed_finite_real_fill_checkpoint_export",cases=records,rejected_cases=rejects,
            task1_2_previously_reviewed_test_sha256="51731fdd31bd9fe2d7ba7f04ed34fc99f3c19fddb70dd7abae839d35c5771539",
            raw_survived_real_source_guard_failure=True,seal_survived_real_clock_failure=True,
            financial_replays=0,fixture_only=True,production_qualified=False)
        destination=LINE/"outputs/stage076_pairwise_off_checkpoint_implementation"
        destination.mkdir(parents=True,exist_ok=True)
        (destination/"test3.json").write_text(json.dumps(runtime.json_safe(evidence),ensure_ascii=False,indent=2)+"\n")

    def checkpoint_fill_fixture(self, arm, folder):
        from dataclasses import replace
        from stage031_run_ordered_checkpoint import actual_trade_identities, pending_intent_snapshot
        folder.mkdir(parents=True)
        paths=tiny_paths(folder)
        # Restrict this fixture's real constructor metadata to one AP product.
        pd.DataFrame([dict(date=d,continuous_symbol_vt="AP.CZCE",main_contract_vt="AP605.CZCE")
            for d in ("2026-01-05",DAY,"2026-01-07","2026-01-08")]).to_csv(paths["mapping_csv_path"],index=False)
        fi={(DAY,"AP605.CZCE"):dict(ready=True,fi2=-1.)}
        cls,engine_cls=policy.select_account_classes(arm,NATIVE,ENGINE,weekly=Weekly(),fi=fi,
            next_days={DAY:"2026-01-07"},qualify=lambda *args:None)
        settings={**paths,**policy.OFF_SETTINGS,"capital_base":100000.,"fixed_size":0,
            "min_risk_per_trade":0.,"short_entry_enabled":True,"max_position_size":500,
            "max_capital_usage_ratio":1.,"max_single_trade_capital_usage_ratio":1.,
            "risk_ratio_volume_open_interest_surge":.012,"risk_ratio_of_total_assets":.012,
            "enable_ai_product_pool_filter":False,"enable_supply_demand_headwind_filter":False,
            "enable_ai_path_damage_risk_discount":False,"ma5_extreme_filter_enabled":True,
            "short_ma5_slope_filter_enabled":True,"wick_chop_filter_enabled":True,
            "enable_stage830_broker10_margin_cap":True,"stage830_broker_margin_multiplier":1.65,
            "stage830_projected_broker10_margin_to_equity_cap":1.,"enable_stage847_half_r_stop_retry":True,
            "stage847_stop_retry_r":.5,"stage847_max_retries":1,"enable_stage827_intraday_c2_stop":True}
        strategy,engine=instantiate(cls,engine_cls,settings)
        engine.output=lambda message:None
        strategy.trading=True
        symbol="AP605.CZCE"
        signalbar=bar(symbol,DAY,100.,110.,99.,100.)
        engine.bars={symbol:signalbar}
        am=strategy.ams[symbol]
        for index in range(am.size):
            close=80.+20.*index/am.size
            am.update_bar(bar(symbol,datetime.fromisoformat(DAY)-timedelta(days=am.size-index),
                close,close+1.,close-1.,close,300. if index==am.size-1 else 100.,200. if index==am.size-1 else 100.))
        native_signal="long_case1a" if arm=="A_OFF" else ""
        strategy._generate_signal=lambda manager,history:strategy._signal_result(native_signal,True,False,
            100.,100.,100.,100.,"regular",False,rsi_value=50.)
        strategy.on_bars(engine.bars)
        self.assertEqual(hasattr(strategy,"ts_machine"),arm=="B_OFF")
        if arm=="B_OFF":
            self.assertEqual((strategy.ts_pending_intents[0]["trigger"],strategy.ts_pending_intents[0]["plan"]["sizing"]["stop_price"]),(111.,99.))
        else:self.assertGreater(len(engine.active_limit_orders),0)
        engine.datetime=datetime.fromisoformat("2026-01-07")
        engine.bars={symbol:bar(symbol,"2026-01-07",100.,130.,70.,100.)}
        grid=native.s827.execution.session_minutes(symbol,"2026-01-07",strategy.available_trade_dates)
        minutes=pd.DataFrame(dict(bar_datetime=grid,open=100.,high=100.,low=100.,close=100.))
        first=0 if arm=="A_OFF" else list(grid).index(pd.Timestamp("2026-01-07T11:00:00"))
        minutes.loc[first,["open","high","low","close"]]=[111.,120.,100.,110.] if arm=="A_OFF" else [100.,120.,100.,110.]
        minutes.loc[first+1,["open","high","low","close"]]=[105.,112.,104.,111.]
        strategy.stage827_minute_by_symbol={symbol:minutes}
        fill_calls=[];original_fill=engine._fill_order
        def fill(order,dbar):
            fill_calls.append(order.vt_orderid)
            return original_fill(order,dbar)
        engine._fill_order=fill
        with runtime.capture_engine(engine_cls) as capture:
            engine.cross_delayed_orders()
            engine.update_daily_close(engine.bars,engine.datetime)
            daily=engine.calculate_result().reset_index()
        trades=engine.get_all_trades()
        self.assertEqual(len(fill_calls),1)
        self.assertEqual([t.price for t in trades],[111.,105.,111.,105.])
        self.assertEqual(pd.Timestamp(trades[2].datetime)-pd.Timestamp(trades[0].datetime),pd.Timedelta(minutes=1))
        cost=sum(t.volume*10*(t.price*.001+1.) for t in trades)
        self.assertAlmostEqual(strategy.trade_costs_total,cost)
        self.assertAlmostEqual(float(daily.commission.iloc[0]+daily.slippage.iloc[0]),cost)
        self.assertEqual(strategy.get_pos(symbol),0)
        formal=policy.make_off_profile(runtime.capture_formal_profile(s901,metadata(),
            pd.Timestamp(runtime.START),pd.Timestamp(runtime.END)),arm)
        # Record the settings actually used by this tiny constructor, rather
        # than attaching the official profile's unused economic overrides.
        spec=replace(formal["spec"],overrides=dict(settings),profile=arm+"_tiny_fixture",
            capital=replace(formal["spec"].capital,account_capital=100000.,c3_capital=100000.,
                risk_multiplier=1.,product_cap_ratio=strategy.max_single_trade_capital_usage_ratio,
                max_concurrent_positions=strategy.max_concurrent_positions,
                variant=arm+"_tiny_fixture",label=arm+" finite native fill fixture",
                note="Fixture only; no full account replay."))
        margin=pd.DataFrame(columns=["variant","date","c3_margin_exact","c3_active_contracts","c3_active_products"])
        combined=native.s827.s772._combine_daily(daily,margin,spec)
        frames={"trades":native.s827.s778.build_trades_df(engine),"positions":native.s827.s778.build_positions_df(engine),
            "entry_risk":native.s827.s778.build_entry_risk_diagnostics_df(engine),
            "entry_candidates":native.s827.s778.build_entry_candidate_snapshots_df(engine),
            "trade_events":pd.DataFrame(strategy.trade_event_diagnostics),
            "stop_retry_events":pd.DataFrame(strategy.stage847_stop_retry_events).drop(columns=["synthetic_trades"],errors="ignore"),
            "pending_orders":native._active_limit_orders_frame(engine)}
        ordered=None if arm=="A_OFF" else dict(decision=deepcopy(strategy.ts_decision_audit),fill=deepcopy(strategy.ts_fill_audit),
            execution=deepcopy(engine.ts_execution_audit),pending=[pending_intent_snapshot(x) for x in strategy.ts_pending_intents])
        identities=actual_trade_identities(trades)
        return dict(combined=combined,frames=frames,capture=deepcopy(capture),actual_trade_identities=identities,
            ordered=ordered,actual=[dict(strategy_class=cls.__name__,actual={k:getattr(strategy,k) for k in settings})],
            parameters=dict(spec=asdict(spec),contract_sizes=dict(engine.sizes),rates=dict(engine.rates),
                slippages=dict(engine.slippages),priceticks=dict(engine.priceticks)),spec=asdict(spec),input_fingerprints={},
            engine_elapsed_seconds=0.,wait_audit=[],resolver_audit=[],qualification_audit={}),dict(
                strategy_module=cls.__module__,strategy_name=cls.__name__,engine_module=engine_cls.__module__,engine_name=engine_cls.__name__),dict(
                    actual_827_fill_calls=fill_calls,identities=identities,prices=[t.price for t in trades],
                    volumes=[t.volume for t in trades],cost_once=cost,native_signal=native_signal,
                    reference_calendar=["2026-01-07"],synthetic_usage_signal_fields_absent=True)

    def planner_cases(self, p):
        records = []
        with tempfile.TemporaryDirectory(prefix="stage070_planner_") as temp:
            paths = tiny_paths(Path(temp))
            for slots, budget, wanted, statuses in ((2,1000.,[3,3,3],["opened","opened","skipped"]),
                    (3,450.,[3,1,0],["opened","opened","skipped"])):
                setting = {**paths, **p.OFF_SETTINGS, "capital_base": 150000.,
                    "enable_ai_product_pool_filter":False, "enable_ai_path_damage_risk_discount":False,
                    "enable_incremental_margin_budget_gate":True,
                    "incremental_margin_budget_gate_reduce_volume":True,
                    "incremental_margin_budget_gate_min_openable_candidates":1,
                    "max_concurrent_positions":slots}
                strategy, _ = instantiate(NATIVE, ENGINE, setting)
                self.assertEqual(strategy.product_symbols, PRODUCTS)
                # Isolate history/sizing construction only; real planner, tilt and margin gate remain.
                strategy._incremental_margin_budget_gate_allowed_capital = lambda context: budget
                def candidate(context, base):
                    return dict(product_vt_symbol=context.product_vt_symbol, native_openable=True,
                        direction="long", signal="long_case1a", volume=3, skip_reason="",
                        sizing=dict(selected_volume=3, margin_per_contract=100., effective_max_concurrent_positions=slots),
                        selection_pairwise_score={PRODUCTS[0]:-100.,PRODUCTS[1]:0.,PRODUCTS[2]:100.}[context.product_vt_symbol],
                        selection_pairwise_rank=0, selection_pairwise_veto_flag=0, selection_pairwise_model_tag="",
                        selection_pairwise_enabled=0, selection_pairwise_veto_penalty=0.,
                        selection_pairwise_feature_ret_20d_zscore_120=0.,
                        selection_pairwise_feature_close_position_60d_cs_zscore_1d=0.,
                        selection_pairwise_feature_range_pct_zscore_120=0., selection_pairwise_runtime_veto_match_local=0)
                strategy._build_flat_entry_candidate_plan = candidate
                plans = strategy._plan_flat_entry_candidates([SimpleNamespace(product_vt_symbol=x,current_pos=0) for x in strategy.product_symbols])
                self.assertEqual(list(plans), PRODUCTS)
                self.assertEqual([v["volume"] for v in plans.values()], wanted)
                self.assertEqual([v["candidate_status"] for v in plans.values()], statuses)
                self.assertEqual(plans[PRODUCTS[2]]["skip_reason"], "concurrent_limit" if slots==2 else "incremental_margin_budget_gate")
                for plan in plans.values():
                    sizing = plan["sizing"]
                    self.assertEqual(plan["volume"], sizing["selected_volume"])
                    self.assertEqual(plan["selection_pairwise_rank"], 0)
                    self.assertEqual(sizing["incremental_margin_budget_gate_protected_by_rank"], 0)
                    self.assertEqual(sizing["selection_pairwise_volume_tilt_applied"],0)
                    self.assertEqual(sizing["selection_pairwise_volume_tilt_multiplier"],1.)
                records.append(dict(slots=slots,budget=budget,plans=list(plans.values())))
        return records

    def b_product_loop(self, p):
        with tempfile.TemporaryDirectory(prefix="stage070_b_loop_") as temp:
            paths = tiny_paths(Path(temp))
            fi = {(DAY,c):dict(ready=True,fi2=-1.) for c in CONTRACTS}
            cls, engine_cls = p.select_account_classes("B_OFF",NATIVE,ENGINE,
                weekly=Weekly(),fi=fi,next_days={DAY:"2026-01-07"},qualify=lambda *args:None)
            setting = {**paths, **p.OFF_SETTINGS, "capital_base":100000., "fixed_size":0,
                "min_risk_per_trade":0., "stop_loss_pct":.1, "risk_ratio_volume_open_interest_surge":.44,
                "risk_ratio_of_total_assets":.44, "max_position_size":500,
                "max_concurrent_positions":3,"max_capital_usage_ratio":.025,
                "max_single_trade_capital_usage_ratio":1., "enable_ai_product_pool_filter":False,
                "enable_supply_demand_headwind_filter":False,"enable_ai_path_damage_risk_discount":False,
                "enable_stage830_broker10_margin_cap":True,"stage830_broker_margin_multiplier":1.65,
                "stage830_projected_broker10_margin_to_equity_cap":1.,
                "enable_stage847_half_r_stop_retry":True,"stage847_stop_retry_r":.5,"stage847_max_retries":1,
                "enable_stage827_intraday_c2_stop":True}
            strategy, engine = instantiate(cls,engine_cls,setting)
            strategy.trading=True
            for c in CONTRACTS:
                am=strategy.ams[c]
                for index in range(am.size):
                    close=70.+24.*index/am.size
                    am.update_bar(bar(c,datetime.fromisoformat(DAY)-timedelta(days=am.size-index),
                        close,close+1.,close-1.,close,300. if index==am.size-1 else 100.,200. if index==am.size-1 else 100.))
                self.assertTrue(am.inited)
            # Literal no native alpha; B observes real weekly/FI/T/S and full product loop.
            strategy._generate_signal=lambda manager,history:strategy._signal_result("",True,False,95.,95.,95.,95.,"regular",False,rsi_value=50.)
            reservations=[]
            original=strategy._reserve_intrabar_entry
            def reserve(product,sizing,quantity,*,count_active_position):
                before=strategy.pending_margin_reservation
                result=original(product,sizing,quantity,count_active_position=count_active_position)
                reservations.append(dict(product=product,q=quantity,m=sizing["margin_per_contract"],
                    before=before,after=strategy.pending_margin_reservation,count_active_position=count_active_position))
                return result
            strategy._reserve_intrabar_entry=reserve
            strategy.on_bars(engine.bars)
            audits=strategy.b_ts_final_budget_audit
            self.assertEqual([x["product_vt_symbol"] for x in audits],PRODUCTS)
            self.assertEqual([x["b_ts_final_budget_volume_before"] for x in audits],[10,10,10])
            self.assertEqual([x["b_ts_final_budget_volume_after"] for x in audits],[10,10,5])
            self.assertEqual([x["b_ts_final_budget_gross_margin_before"] for x in audits],[0.,1000.,2000.])
            self.assertEqual([x["b_ts_final_budget_original_rank"] for x in audits],[0,0,0])
            self.assertEqual([x["rank"] for x in strategy.ts_pending_intents],[1,2,3])
            self.assertEqual([x["plan"]["volume"] for x in strategy.ts_pending_intents],[10,10,5])
            self.assertEqual([x["plan"]["sizing"]["selected_volume"] for x in strategy.ts_pending_intents],[10,10,5])
            self.assertEqual([x["selection_pairwise_rank"] for x in strategy.ts_decision_audit],[0,0,0])
            self.assertEqual([(x["product"],x["q"]) for x in reservations],list(zip(PRODUCTS,[10,10,5])))
            self.assertEqual(strategy.pending_margin_reservation,2500.)
            self.assertEqual(strategy.pending_active_products,set(PRODUCTS))
            self.assertEqual(engine.limit_orders,{})
            self.assertEqual(engine.trades,{})
            for item in strategy.ts_pending_intents:
                sizing=item["plan"]["sizing"]
                self.assertEqual((item["trigger"],sizing["stop_price"],sizing["risk_per_contract"],sizing["margin_per_contract"]),(100.,89.,110.,100.))
                self.assertEqual(sizing["selection_pairwise_rank"],0)
                self.assertEqual(sizing["incremental_margin_budget_gate_protected_by_rank"],0)
                self.assertEqual(sizing["selection_pairwise_volume_tilt_applied"],0)
                self.assertEqual(sizing["selection_pairwise_volume_tilt_multiplier"],1.)
                self.assertEqual(sizing["risk_amount"],1100.)
                self.assertEqual(sizing["limited_balance"],2500.)
            return dict(audits=audits,reservations=reservations,pending_ordinals=[x["rank"] for x in strategy.ts_pending_intents],
                pairwise_ranks=[x["selection_pairwise_rank"] for x in strategy.ts_decision_audit],
                signal_machine_arm=strategy.ts_machine.arm,orders=0,fills=0)


if __name__ == "__main__":
    unittest.main()
