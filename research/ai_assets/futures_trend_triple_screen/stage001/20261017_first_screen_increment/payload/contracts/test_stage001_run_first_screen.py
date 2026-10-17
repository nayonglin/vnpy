"""Focused contracts: a first screen must prevent entry, never rewrite old gates."""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import subprocess
import sys
import json
import hashlib

try:
    import stage001_run_first_screen as runner
except ImportError:
    runner = None

ROOT = Path(__file__).resolve().parents[4]


class RunnerContractTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(runner, 'first-screen runner is not implemented')

    def lookup(self, ready=True, direction=-1):
        return runner.WeeklyLookup([dict(date='2020-01-06', product_id='SHFE.FU',
            ready=ready, direction=direction, weekly_asof='2020-01-03')])

    def context(self, product='fu.SHFE', native=True, reason=''):
        return SimpleNamespace(product_vt_symbol=product, target_contract='fu2005.SHFE',
            current_pos=0,
            target_bar=SimpleNamespace(datetime=datetime(2020, 1, 6)),
            plan=dict(product_vt_symbol=product, direction='long', signal='long_case2',
                volume=2, native_openable=native, skip_reason=reason, active_positions_before=0,
                remaining_position_slots=1, sizing=dict(selected_volume=2, margin_per_contract=100),
                selection_pairwise_score=0., selection_pairwise_rank=0,
                selection_pairwise_veto_flag=0, selection_pairwise_model_tag='',
                selection_pairwise_enabled=0, selection_pairwise_veto_penalty=0.,
                selection_pairwise_feature_ret_20d_zscore_120=0.,
                selection_pairwise_feature_close_position_60d_cs_zscore_1d=0.,
                selection_pairwise_feature_range_pct_zscore_120=0.,
                selection_pairwise_runtime_veto_match_local=0))

    def strategy(self, lookup=None, arm='C0'):
        class Base:
            max_concurrent_positions = 1
            selection_pairwise_runtime = None
            def _build_flat_entry_candidate_plan(self, context, count):
                return {**context.plan, 'sizing': dict(context.plan['sizing'])}
            def _count_active_positions(self): return 0
            def _apply_selection_pairwise_scores(self, plans): pass
            def _apply_ai_path_damage_risk_discount(self, plans): pass
            def _apply_selection_pairwise_volume_tilt(self, plans): pass
            def _incremental_margin_budget_gate_fields(self, **kwargs):
                return dict(incremental_margin_budget_gate_enabled=0,
                    incremental_margin_budget_gate_passed=1,
                    incremental_margin_budget_gate_planned_entry_margin=200)
        # Execute the real downstream planner, with only unrelated sizing/external
        # dependencies replaced. This catches a gate that changes diagnostics only.
        source = ROOT/'examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py'
        tree = ast.parse(source.read_text())
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'QmtRollPortfolioStrategy')
        method = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == '_plan_flat_entry_candidates')
        module = ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0), method], type_ignores=[])
        namespace = {}
        exec(compile(ast.fix_missing_locations(module), str(source), 'exec'), namespace)
        Base._plan_flat_entry_candidates = namespace['_plan_flat_entry_candidates']
        return runner.build_research_strategy(Base, lookup or self.lookup(), arm)()

    def test_opposed_screen_really_skips_and_does_not_take_concurrent_slot(self):
        lookup = runner.WeeklyLookup([
            dict(date='2020-01-06',product_id='SHFE.FU',ready=True,direction=-1,weekly_asof='2020-01-03'),
            dict(date='2020-01-06',product_id='SHFE.CU',ready=True,direction=1,weekly_asof='2020-01-03')])
        s = self.strategy(lookup)
        plans = s._plan_flat_entry_candidates([self.context(),self.context('cu.SHFE')])
        self.assertEqual(plans['fu.SHFE']['candidate_status'],'skipped')
        self.assertEqual(plans['fu.SHFE']['skip_reason'],'weekly_first_screen_opposed')
        self.assertEqual(plans['cu.SHFE']['candidate_status'],'opened')
        self.assertEqual(plans['cu.SHFE']['volume'],2)

    def test_neutral_ready_direction_blocks_initial_plan(self):
        s = self.strategy(self.lookup(direction=0))
        p = s._build_flat_entry_candidate_plan(self.context(),0)
        self.assertFalse(p['native_openable'])
        self.assertEqual(p['candidate_status'],'skipped')

    def test_unknown_retains_native_behavior_and_audits_fallback(self):
        s = self.strategy(self.lookup(ready=False))
        p = s._build_flat_entry_candidate_plan(self.context(),0)
        self.assertTrue(p['native_openable'])
        self.assertEqual(p['volume'],2)
        self.assertEqual(s.weekly_gate_audit[-1]['decision'],'unknown_keep_baseline')

    def test_missing_feature_retains_baseline(self):
        s = self.strategy()
        p = s._build_flat_entry_candidate_plan(self.context('au.SHFE'),0)
        self.assertTrue(p['native_openable'])
        self.assertEqual(s.weekly_gate_audit[-1]['unknown_reason'],'feature_row_missing')

    def test_original_ai_rejection_keeps_reason(self):
        s = self.strategy()
        p = s._build_flat_entry_candidate_plan(self.context(native=False,reason='ai_product_pool_blocked'),0)
        self.assertEqual(p['skip_reason'],'ai_product_pool_blocked')
        self.assertFalse(s.weekly_gate_audit[-1]['gate_blocked'])

    def test_control_arm_does_not_filter_opposed_direction(self):
        s = self.strategy(arm='A0')
        p = s._build_flat_entry_candidate_plan(self.context(),0)
        self.assertTrue(p['native_openable'])
        self.assertEqual(s.weekly_gate_audit[-1]['decision'],'control_keep_baseline')

    def test_same_week_completed_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'weekly_asof_not_prior_week'):
            runner.WeeklyLookup([dict(date='2020-01-06',product_id='SHFE.fu',ready=True,
                direction=1,weekly_asof='2020-01-06')])

    def test_duplicates_and_bad_ready_values_are_rejected(self):
        row=dict(date='2020-01-06',product_id='SHFE.fu',ready=True,direction=1,weekly_asof='2020-01-03')
        with self.assertRaisesRegex(ValueError,'duplicate_weekly_feature'):
            runner.WeeklyLookup([row,row])
        with self.assertRaisesRegex(ValueError,'invalid_ready'):
            runner.WeeklyLookup([{**row,'ready':'truthy'}])

    def test_existing_attempt_is_never_reused_even_after_failure(self):
        with TemporaryDirectory() as folder:
            output=Path(folder)/'C0'
            runner.reserve_attempt(output)
            (output/'run_failure.json').write_text('{}')
            with self.assertRaises(FileExistsError):runner.reserve_attempt(output)
            self.assertTrue((output/'run_failure.json').exists())

    def test_retry_attempt_uses_new_path_and_requires_previous_failure(self):
        with TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaisesRegex(ValueError,'previous_attempt_not_failed'):
                runner.resolve_attempt_output(root,'A0',2)
            (root/'A0').mkdir()
            (root/'A0'/'run_failure.json').write_text('{}')
            target=runner.resolve_attempt_output(root,'A0',2)
            self.assertEqual(target.name,'A0_attempt2')
            runner.reserve_attempt(target)
            with self.assertRaises(FileExistsError):runner.reserve_attempt(target)
            self.assertTrue((root/'A0'/'run_failure.json').exists())

    def test_vendor_swallowed_bar_failure_still_fails_scope(self):
        class Engine:
            def new_bars(self, dt):raise ValueError('missing_minutes:fu')
            def calculate_result(self):return None
        original=Engine.new_bars
        with self.assertRaisesRegex(RuntimeError,'backtest_bar_failed'):
            with runner.capture_engine(Engine) as captured:
                try:Engine().new_bars(datetime(2020,1,6))
                except ValueError:pass
        self.assertIs(Engine.new_bars,original)
        self.assertEqual(len(captured['failures']),1)

    def test_secondary_result_error_does_not_hide_first_bar_failure(self):
        class Engine:
            def new_bars(self,dt):raise ValueError('original_model_compatibility_failure')
            def calculate_result(self):raise KeyError('incomplete_after_swallowed_bar')
        with self.assertRaisesRegex(RuntimeError,'backtest_bar_failed') as failure:
            with runner.capture_engine(Engine):
                try:Engine().new_bars(datetime(2020,1,6))
                except ValueError:pass
                Engine().calculate_result()
        self.assertIsInstance(failure.exception.__cause__,ValueError)

    def test_frozen_model_predicts_before_any_account_replay(self):
        code='''
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import stage001_run_first_screen as r
r.configure_runtime(r.OUTPUT/'shared_empty_signal_inputs')
probe=r.model_runtime_smoke(r.PROJECT/'backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_selection_pairwise_v2_risk_weighted.joblib',r.PROJECT/'backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_summary_selection_pairwise_v2_risk_weighted.json')
print(json.dumps(probe))
'''
        process=subprocess.run([sys.executable,'-c',code,str(Path(__file__).parent)],capture_output=True,text=True)
        self.assertEqual(process.returncode,0,process.stderr)
        probe=__import__('json').loads(process.stdout)
        self.assertEqual(probe['sklearn_version'],'1.8.0')
        self.assertLess(probe['max_probability_error'],1e-12)
        self.assertEqual(probe['model_fits'],0)

    def test_overlay_receipt_rejects_changed_payload_before_financial_run(self):
        with TemporaryDirectory()as folder:
            folder=Path(folder)
            payloads={'overlay.csv':'vt_symbol,bar_datetime\n','session_manifest.csv':'status\n',
                'source_manifest.json':'{}','a0_path_equivalence.json':'{"path_equivalent":true,"intersection_count":0,"original_read_keys_missing_in_base":0}',
                'protocol_used.md':'frozen protocol'}
            for name,value in payloads.items():(folder/name).write_text(value)
            digest=lambda name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
            summary=dict(status='completed_local_overlay_pending_independent_review',base_cache_sha256=runner.EXPECTED_MINUTE,
                all_inputs_unchanged=True,production_qualified=False,
                a0_path_equivalence=json.loads(payloads['a0_path_equivalence.json']),
                builder_sha256=hashlib.sha256(Path(runner.__file__).with_name('stage002_local_minute_overlay.py').read_bytes()).hexdigest(),
                protocol_sha256=digest('protocol_used.md'),overlay_sha256=digest('overlay.csv'),
                session_manifest_sha256=digest('session_manifest.csv'),source_manifest_sha256=digest('source_manifest.json'))
            (folder/'summary.json').write_text(json.dumps(summary))
            review=dict(status='independent_overlay_and_A0_path_equivalence_pass',A0_path_equivalent=True,
                source=str(folder),original_base_SHA_unchanged=runner.EXPECTED_MINUTE,
                source_hashes={name:digest(name)for name in ['overlay.csv','source_manifest.json','session_manifest.csv','a0_path_equivalence.json','summary.json']})
            (folder/'review.json').write_text(json.dumps(review))
            kwargs=dict(expected_summary_sha256=digest('summary.json'),review_path=folder/'review.json',expected_review_sha256=digest('review.json'))
            receipt=runner.read_overlay_receipt(folder/'summary.json',**kwargs)
            self.assertTrue(receipt['a0_path_equivalent'])
            (folder/'overlay.csv').write_text('changed bytes')
            with self.assertRaisesRegex(ValueError,'overlay_fingerprint_changed'):
                runner.read_overlay_receipt(folder/'summary.json',**kwargs)

    def test_strategy_class_patch_restores_after_error(self):
        original=lambda metadata:dict(strategy_cls=object,spec='unchanged')
        module=SimpleNamespace(_c9_profile=original)
        candidate=type('Candidate',(),{})
        with self.assertRaises(ValueError):
            with runner.replace_strategy_class(module,candidate):
                self.assertIs(module._c9_profile({})['strategy_cls'],candidate)
                raise ValueError('abort')
        self.assertIs(module._c9_profile,original)

    def test_profile_preflight_never_calls_real_engine_and_restores_functions(self):
        def forbidden(*args):raise AssertionError('financial engine called in preflight')
        module=SimpleNamespace(_run_profile=forbidden)
        original_ensure=lambda metadata:None
        def live(metadata,start,end):
            s901._ensure_c9_minute_bars(metadata)
            return module._run_profile(dict(spec='assembled_real_spec'),metadata)
        s901=SimpleNamespace(s847=module,_ensure_c9_minute_bars=original_ensure,_run_live_c9=live)
        profile=runner.capture_formal_profile(s901,{},'start','end')
        self.assertEqual(profile['spec'],'assembled_real_spec')
        self.assertIs(module._run_profile,forbidden)
        self.assertIs(s901._ensure_c9_minute_bars,original_ensure)


if __name__=='__main__':unittest.main()
