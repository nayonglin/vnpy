"""One synthetic interface fixture; no actual initialization or market access."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np


class SharedProfilesFixture(unittest.TestCase):
    def test_metadata_view_own_states_shared_acceptance_and_clock_gaps(self):
        # Breaks on changing numeric artifacts, borrowing states, promoting the
        # development flag without acceptance, or committing missing/late input.
        path = Path(__file__).with_name('stage376_shared_frozen_profiles.py')
        self.assertTrue(path.exists(), 'new shared-input interface is absent')
        spec = importlib.util.spec_from_file_location('fixture376', path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        c = m.components()
        core = c.caller._components().core
        names = core.COMMON+[v+'_missing' for v in core.COMMON]
        original_model = dict(scope='main', cutoff='2026-10-20', feature_names=names,
            parameters=dict(alpha=1., fit_intercept=True, solver='cholesky'),
            coef=[.01]+[0.]*51, intercept=1.)
        original_scaler = dict(scope='main', cutoff='2026-10-20', feature_names=names,
            common=dict(columns=core.COMMON, mean=[0.]*26, scale=[1.]*26))
        before = deepcopy((original_model, original_scaler))

        class Clock(datetime):
            at = datetime(2026, 10, 19, 21, tzinfo=timezone.utc)
            @classmethod
            def now(cls, tz=None):
                value = cls.at
                cls.at += timedelta(microseconds=1)
                return value.astimezone(tz or timezone.utc)

        with tempfile.TemporaryDirectory(prefix='stage376_fixture_') as temporary:
            root = Path(temporary)
            prepared = m.prepare(root/'prepared')
            # Exercise the real public preflight and small calendar path in an
            # isolated temporary destination, never the root actual_run1 path.
            public_output = (root/'public_entry_initialization').resolve()
            with patch.object(m, 'ACTUAL', public_output), patch.object(
                    c.paper, 'new_state', wraps=c.paper.new_state) as public_states:
                public = m.initialize(prepared['bundle'], public_output)
            self.assertEqual(public['status'], 'initialized_inactive')
            self.assertEqual(public_states.call_count, 2)
            self.assertEqual(public['counts']['model_inference'], 0)
            bundle = json.loads(m.helper()._bound(prepared['bundle']))
            contract = json.loads(m.helper()._bound(bundle['frozen_inputs']['clock_contract']))
            model_b = m.helper().write(root/'synthetic_model.json', original_model)
            scaler_b = m.helper().write(root/'synthetic_scaler.json', original_scaler)
            profile = m.make_profile(original_model, original_scaler, model_b, scaler_b,
                frozen_at='2026-10-19T20:48:38+00:00', candidate=m.CANDIDATE,
                clock_contract=contract)
            self.assertEqual((original_model, original_scaler), before)
            for actual, view in ((original_model, profile['engine_model']),
                                 (original_scaler, profile['engine_scaler'])):
                normalized = deepcopy(view)
                normalized['cutoff'] = actual['cutoff']
                for key in ('actual_training_cutoff', 'source_artifact_sha256', 'engine_compatibility_mapping'):
                    normalized.pop(key)
                self.assertEqual(normalized, actual)
            row = dict(raw26=[2.]+[0.]*25)
            with self.assertRaisesRegex(ValueError, 'main2023'):
                core.infer_scores([row], original_model, original_scaler)
            scored = core.infer_scores([row], profile['engine_model'], profile['engine_scaler'])
            self.assertAlmostEqual(scored[0]['score'], 1.02)
            self.assertEqual(profile['actual_training_cutoff'], '2026-10-20')
            self.assertEqual(profile['engine_fold_tag'], '2023-01-01')
            kernel = m.helper()._load(m.TOOLS/'stage131_contract_choice_kernel.py', 'fixture376_kernel')
            with patch.object(c.caller._components().journal, 'datetime', Clock):
                latest = m._initialize_profile(profile, root/'latest', kernel)
            states_before = deepcopy(latest['states'])
            restored = m.load_context(latest['initialization_envelope'])
            self.assertEqual(restored['states'], states_before)
            self.assertNotEqual(latest['states']['base']['account_id'], latest['states']['stress']['account_id'])
            latest['states']['base']['ledger']['realized'] = 7.
            self.assertEqual(latest['states']['stress']['ledger']['realized'], 0.)
            latest['states'] = states_before
            old_model = dict(original_model, cutoff='2023-01-01')
            old_scaler = dict(original_scaler, cutoff='2023-01-01')
            old_model_b = m.helper().write(root/'synthetic_old_model.json', old_model)
            old_scaler_b = m.helper().write(root/'synthetic_old_scaler.json', old_scaler)
            old_profile = m.make_profile(old_model, old_scaler, old_model_b, old_scaler_b,
                frozen_at='2026-10-19T20:21:56+00:00', candidate=m.BASELINE,
                clock_contract=contract)
            with patch.object(c.caller._components().journal, 'datetime', Clock):
                baseline = m._initialize_profile(old_profile, root/'baseline', kernel)
            with self.assertRaisesRegex(ValueError, 'another.*policy'):
                m.validate_context(dict(latest, states=baseline['states']))
            u = 5290
            days = [(date(2026, 10, 20)+timedelta(days=i-u)).isoformat() for i in range(u+2)]
            epoch = 'DCE.P.202703'
            state = core.WilderState()
            values = dict(open=100., high=101., low=99., close=100., volume=10000., close_oi=10., quality_status='accepted')
            for j in range(u-22, u+1):
                state.append(j, values)
            adapter = m.helper()._load(m.TOOLS/'stage339_incremental_snapshot.py', 'fixture376_market')
            snapshot = dict(schema='stage339_incremental_snapshot_v1', development_only=True,
                u_index=u, u_date=days[u], dates=days,
                products=['DCE.P']+['DCE.X'+str(i).zfill(3) for i in range(97)],
                economics={epoch:dict(economics_status='exact_epoch_metadata_snapshot',
                    contract_multiplier=10., round_lot=1, tick_size=.1, vendor_margin_rate=.2)},
                series_by_epoch={epoch:state}, market=adapter.SnapshotMarket({epoch:state.to_series()}, days),
                warmup_state={epoch:state.to_dict()}, _inventory=[], _continuation_evidence=[],
                D_context=dict(confirmed=True, D_index=u+1, D_date=days[u+1]),
                source='synthetic357', version='synthetic/u20', source_receipt={'synthetic':True},
                clock=dict(source_completed_at='2026-10-20T15:15:00+08:00', D_open_at='2026-10-20T21:00:00+08:00'))
            domains = dict(schema='stage357_dual_clock_domains_v1', policy=contract,
                u_date=days[u], D_date=days[u+1], before_score=True, score_or_winner_used=False,
                input_completion=dict(epochs=[epoch], unknown_epochs=[], source_completed_at=snapshot['clock']['source_completed_at']),
                execution_deadline=dict(epochs=[epoch], unknown_epochs=[], explicit_dependencies=[],
                    D_open_at=snapshot['clock']['D_open_at']))
            composed = dict(snapshot=snapshot, clock_domains=domains,
                canonical_rows=[dict(contract_epoch_id=epoch, canonical_values=values)],
                normalization_audit={'synthetic':True}, prescore_observations={'synthetic':True})

            def accepted(obj, stem):
                proof = m.helper().write(root/(stem+'_evidence.json'), {'synthetic_fixture_evidence':True})
                return m.helper().write(root/(stem+'_acceptance.json'), dict(
                    schema=m.ACCEPTANCE_SCHEMA, accepted_by='root', status='accepted',
                    target_u=m.TARGET_U, completed361=True, passed362=True, accepted363=True,
                    evidence=dict(terminal361=proof, review362=proof, decision363=proof),
                    composed_identity=m.composed_identity(obj),
                    clock_domains_sha256=c.caller._hash(obj['clock_domains'])))

            receipt = accepted(composed, 'same')
            Clock.at = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)
            with patch.object(c.caller._components().journal, 'datetime', Clock):
                pair = m.process_pair(composed, receipt, {'latest':latest, 'baseline':baseline})
            self.assertTrue(all(value['active'] for value in pair['profiles'].values()))
            self.assertTrue(composed['snapshot']['development_only'])
            self.assertEqual(latest['states'], states_before)
            self.assertEqual({v['accepted_composed_identity'] for v in pair['profiles'].values()},
                             {m.composed_identity(composed)})
            self.assertEqual({s['caller_policy_sha256'] for s in pair['profiles']['latest']['result']['states'].values()},
                             {latest['journal'].policy_hash})
            changed = deepcopy(composed)
            changed['snapshot']['source_receipt'] = {'different_batch':True}
            with self.assertRaisesRegex(ValueError, 'composed.*binding'):
                m.process_pair(changed, receipt, {'latest':latest})
            unknown = deepcopy(composed)
            unknown['snapshot']['clock']['source_completed_at'] = None
            unknown['clock_domains']['input_completion'].update(source_completed_at=None, unknown_epochs=[epoch])
            Clock.at = datetime(2026, 10, 20, 8, 1, tzinfo=timezone.utc)
            with patch.object(c.caller._components().journal, 'datetime', Clock):
                gap = m.process_pair(unknown, accepted(unknown, 'unknown'), {'latest':latest})
            self.assertEqual(gap['profiles']['latest']['status'], 'state_gap')
            self.assertEqual(gap['profiles']['latest']['states'], states_before)
            Clock.at = datetime(2026, 10, 20, 13, tzinfo=timezone.utc)
            with patch.object(c.caller._components().journal, 'datetime', Clock):
                late = m.process_pair(composed, receipt, {'latest':latest})
            self.assertEqual(late['profiles']['latest']['status'], 'state_gap')
            self.assertFalse(late['profiles']['latest']['active'])
            self.assertEqual(late['profiles']['latest']['states'], states_before)
            self.assertEqual((original_model, original_scaler), before)


if __name__ == '__main__':
    unittest.main()
