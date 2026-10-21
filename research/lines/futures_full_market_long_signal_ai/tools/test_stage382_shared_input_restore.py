"""One combined public-interface fixture; every market value is synthetic."""
from copy import deepcopy
from datetime import date, timedelta
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

TOOLS = Path(__file__).resolve().parent
TOOL = TOOLS/'stage382_shared_input_restore.py'


def load(name):
    spec = importlib.util.spec_from_file_location('tiny382_'+name, TOOLS/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SharedInputRestoreTiny(unittest.TestCase):
    def test_public_loaders_preserve_accounts_and_restore_once_with_full_bound_inputs(self):
        # Removing final-state restoration, source/econ/clock checks, or silently
        # creating an absent journal must break this public-interface fixture.
        self.assertTrue(TOOL.is_file(), '382 public loaders are not implemented')
        m = load('stage382_shared_input_restore')
        p = m.profiles()
        h, c = p.helper(), p.components()
        core = c.caller._components().core
        adapter = h._load(TOOLS/'stage339_incremental_snapshot.py', 'tiny382_original339')
        contract = json.loads((TOOLS.parent/'outputs/stage356_reference_asset_closure/clock_contract.json').read_bytes())
        names = core.COMMON+[v+'_missing' for v in core.COMMON]
        model = dict(scope='main', cutoff='2023-01-01', feature_names=names, coef=[0.]*52, intercept=1.)
        scaler = dict(scope='main', cutoff='2023-01-01', feature_names=names,
                      common=dict(columns=core.COMMON, mean=[0.]*26, scale=[1.]*26))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            def write(name, value):
                return h.write(root/name, c.caller._clean(value))
            mb, sb = write('old_model.json', model), write('old_scaler.json', scaler)
            cb = write('clock_contract.json', contract)
            profile = p.make_profile(model, scaler, mb, sb, frozen_at='2026-10-19T20:00:00+00:00',
                                     candidate=p.BASELINE, clock_contract=contract)
            kernel = h._load(TOOLS/'stage131_contract_choice_kernel.py', 'tiny382_pure131')
            baseline_dir = root/'baseline'
            baseline_dir.mkdir()
            journal = c.journal.ForwardJournal(baseline_dir/'model_journal', profile['policy_identity'])
            states = {s:c.paper.new_state(scenario=s, account_id='original_'+s,
                start_u=5290, base_kernel=kernel) for s in ('base', 'stress')}
            for state in states.values():
                state['caller_policy_sha256'] = journal.policy_hash
            files = {s:h.write(baseline_dir/(s+'_state.json'), json.loads(c.paper.export_state(v)))
                     for s,v in states.items()}
            frozen_inputs = dict(model=mb, scaler=sb, clock_contract=cb)
            sources = {n:h.binding(TOOLS/n) for n in h.CALLER_FILES}
            kernels = {n:h.binding(TOOLS/n) for n in h.KERNEL_SHA}
            identity_file = write('baseline_policy.json', profile['policy_identity'])
            freeze = write('baseline_freeze.json', dict(schema='stage359_research_reference_freeze_v1',
                receipt=dict(kind='research_reference_freeze', recorded_at=profile['T_model']), clock_contract=cb))
            reference = dict(freeze_event=freeze, policy_identity=identity_file)
            bundle = write('baseline_bundle.json', dict(schema='stage368_initialization_source_bundle_v1',
                frozen_inputs=frozen_inputs, frozen_sources=sources, reference=reference))
            event = journal.append('paper_state_initialized', dict(states=states, state_files=files,
                frozen_inputs=frozen_inputs, policy_identity=profile['policy_identity'], T0=profile['T_model']),
                key='original-empty-accounts')
            envelope = dict(schema='stage368_paper_initialization_envelope_v1', status='initialized_inactive',
                active=False, T0=profile['T_model'], T_init=event['recorded_at'], event=event,
                policy_identity=profile['policy_identity'], state_files=files, source_bundle=bundle,
                reference=reference, kernel_sources=kernels)
            eb = h.write(baseline_dir/'initialization_envelope.json', envelope)
            manifest = dict(schema='stage368_initialization_manifest_v1', status='initialized_inactive',
                active=False, T0=envelope['T0'], T_init=envelope['T_init'], initialization_envelope=eb,
                state_files=files, source_bundle=bundle, policy_identity=identity_file,
                reference=reference, kernel_sources=kernels)
            baseline_manifest = h.write(baseline_dir/'manifest.json', manifest)
            latest_model, latest_scaler = deepcopy(model), deepcopy(scaler)
            latest_model['cutoff'] = latest_scaler['cutoff'] = '2026-10-20'
            latest_mb, latest_sb = write('latest_model.json', latest_model), write('latest_scaler.json', latest_scaler)
            latest_profile = p.make_profile(latest_model, latest_scaler, latest_mb, latest_sb,
                frozen_at='2026-10-19T21:00:00+00:00', candidate=p.CANDIDATE, clock_contract=contract)
            latest = p._initialize_profile(latest_profile, root/'latest', kernel)

            dates = []
            day = date(2026, 9, 1)
            while day <= date(2026, 10, 21):
                if day.weekday() < 5:
                    dates.append(day.isoformat())
                day += timedelta(days=1)
            u = dates.index('2026-10-20')
            a, stale, empty = 'DCE.P.202703', 'DCE.Q.202703', 'DCE.R.202703'
            products = ['DCE.P','DCE.P_F','DCE.Q','DCE.Q_F','DCE.R','DCE.R_F']+['DCE.X'+str(i).zfill(3) for i in range(92)]
            bar = dict(open=100., high=101., low=99., close=100., volume=10000., close_oi=10., quality_status='accepted')
            warmup = {}
            for epoch, last in ((a, u-1), (stale, u-2)):
                state = core.WilderState()
                for index in range(last+1):
                    state.append(index, bar)
                warmup[epoch] = state.to_dict()
            inventory = [dict(epoch=e, product_id=e.rsplit('.',1)[0], rows=len(v['history']),
                last_index=v['last_seen'], last_date=dates[v['last_seen']], has_current_bar=v['last_seen']==u-1)
                for e,v in warmup.items()]
            inventory.append(dict(epoch=empty, product_id='DCE.R', rows=0, last_index=None,
                                  last_date=None, has_current_bar=False))
            eco = dict(economics_status='exact_epoch_metadata_snapshot', contract_multiplier=10.,
                round_lot=1., tick_size=None, vendor_margin_rate=.2, listed_date='2020-01-01')
            full_econ = {a:eco, stale:dict(eco, contract_multiplier=20.), empty:dict(eco, contract_multiplier=30.)}
            inp = dict(economics331=write('economics331.json', {a:eco, stale:full_econ[stale]}),
                economics344=write('economics344.json', {empty:full_econ[empty]}), clock_contract=cb,
                calendar338=write('calendar338.json', dict(days={d:True for d in dates})))
            raw_calendar = io.BytesIO()
            np.save(raw_calendar, np.asarray([int(d.replace('-','')) for d in dates], dtype=np.int64))
            inp['source_calendar'] = h._write_raw(root/'calendar.npy', raw_calendar.getvalue())
            inp['roster'] = h._write_raw(root/'roster.csv', ('product_id\n'+'\n'.join(products)+'\n').encode())
            batch = root/'batch'
            batch.mkdir()
            capture = write('capture.json', dict(status='completed', synthetic=True))
            original = dict(inputs=inp, capture=capture)
            normalization = dict(status='completed', canonical_rows_accepted=True)
            canonical = [dict(contract_epoch_id=a, trade_date=dates[u], identity_state='known_explicit',
                units_status='canonical_normalized', canonical_quality_status='accepted', model_input_eligible=True,
                date_mapping_state='operational_midnight_label', canonical_values=dict(bar, high=105.,close=104.),
                source_receipt=dict(synthetic=True))]
            snap = adapter.build_incremental_snapshot(warmup, inventory, canonical, dates=dates,
                previous_u_date=dates[u-1], u_date=dates[u], products=products, economics=full_econ,
                calendar_confirmation=dict(confirmed=True, u_date=dates[u],u_index=u,proof=original),
                normalization_receipt=normalization, source_receipt=original,
                D_context=dict(confirmed=True,D_index=u+1,D_date=dates[u+1],proof='bound_calendar_next_source_date'),core=core)
            snap['clock'] = dict(source_completed_at=None, D_open_at='2026-10-20T21:00:00+08:00',
                                 domain_policy=contract['version'])
            domains = dict(schema='stage357_dual_clock_domains_v1', policy=contract,u_date=dates[u],D_date=dates[u+1],
                input_completion=dict(epochs=[a],unknown_epochs=[a],source_completed_at=None),
                execution_deadline=dict(epochs=[a],eligibility_unknown_epochs=[],excluded_original_ineligible=[],
                    explicit_dependencies=[],unknown_epochs=[],D_open_at=snap['clock']['D_open_at']),
                before_score=True,score_or_winner_used=False,prior354_strict_result_unchanged=True)
            obs = core.build_u_observations(snap['series_by_epoch'],u,dates,full_econ,products,D_context=snap['D_context'])
            self.assertEqual(len(obs['raw_rows']),1)
            source_journal = c.journal.ForwardJournal(batch/'model_journal', profile['policy_identity'])
            provenance = dict(u_index=u,u_date=dates[u],source=snap['source'],version=snap['version'],
                source_receipt=snap['source_receipt'],development_only=True,D_context=snap['D_context'],
                clock=snap['clock'],claimed_adapter_received_at=None)
            receipt = source_journal.append('input_snapshot', provenance, key='synthetic-input-only')
            artifacts = {}
            values = dict(warmup_state=snap['warmup_state'], epoch_inventory=snap['_inventory'],
                continuation_evidence=snap['_continuation_evidence'], canonical_overlay=canonical,
                normalization_audit=dict(synthetic=True), clock_domains=domains, current_economics={a:eco},
                result=dict(result=dict(observations=obs,input_receipt=receipt,policy_identity=profile['policy_identity'])))
            for name,value in values.items():
                artifacts[name] = h.write(batch/(name+'.json'),c.caller._clean(value))
            artifacts['capture'] = capture
            source_bundle = write('batch_source_bundle.json', dict(schema='stage357_daily_collect_compose_source_bundle_v1',
                sources=[h.binding(TOOLS/n) for n in ('stage357_daily_collect_compose.py','stage339_incremental_snapshot.py',*h.CALLER_FILES)]))
            batch_manifest = dict(schema='stage357_daily_collect_compose_manifest_v1', status='completed_observation',
                source_bundle=source_bundle,inputs=inp,artifacts=artifacts,target_u=dates[u],mode='observe_only',
                T0=profile['T_model'],active=False,new_fit=0,new_cash=0,canonical_rows=1)
            bb = h.write(batch/'manifest.json', batch_manifest)
            before = {str(f):f.read_bytes() for f in root.rglob('*') if f.is_file()}
            with patch.object(c.paper,'new_state',side_effect=AssertionError('new account forbidden')), \
                 patch.object(c.journal.ForwardJournal,'append',side_effect=AssertionError('append forbidden')), \
                 patch.object(core,'infer_scores',side_effect=AssertionError('inference forbidden')), \
                 patch.object(core.WilderState,'append',side_effect=AssertionError('double append forbidden')):
                restored_base = m.load_baseline_context(baseline_manifest)
                restored_latest = p.load_context(latest['initialization_envelope'])
                restored = m.restore_composed(bb)
                self.assertEqual(restored_base['states'],states)
                self.assertEqual(restored_base['profile']['policy_identity'],profile['policy_identity'])
                self.assertEqual(restored_base['T_init'],event['recorded_at'])
                self.assertEqual(restored_base['journal'].path,journal.path)
                self.assertNotEqual(restored_base['journal'].policy_hash,restored_latest['journal'].policy_hash)
                rs = restored['snapshot']
                self.assertTrue(rs['development_only'])
                self.assertEqual(rs['warmup_state'],snap['warmup_state'])
                self.assertEqual(rs['warmup_state'][a]['last_seen'],u)
                self.assertAlmostEqual(rs['warmup_state'][a]['N'],2.2,places=14)
                self.assertIsInstance(rs['series_by_epoch'][a],core.WilderState)
                self.assertIsNone(rs['market'].bar(stale,u))
                self.assertEqual(len(rs['market'].series[empty].days),0)
                self.assertEqual(rs['economics'],full_econ)
                self.assertEqual((len(rs['products']),len({v.removesuffix('_F') for v in rs['products']})),(98,95))
                self.assertEqual(restored['clock_domains'],domains)
                self.assertIsNone(rs['clock']['source_completed_at'])
                self.assertEqual(rs['source_receipt'],snap['source_receipt'])
                self.assertEqual(c.caller._clean(restored['prescore_observations']),c.caller._clean(obs))
                self.assertEqual(before,{str(f):f.read_bytes() for f in root.rglob('*') if f.is_file()})
                missing = deepcopy(envelope)
                missing['state_files']['base']['path'] = str(root/'absent.json')
                with self.assertRaises(ValueError):
                    m.load_baseline_context(write('missing_envelope_manifest.json',dict(manifest,
                        initialization_envelope=write('missing_envelope.json',missing))))
                missing_dir = baseline_dir/'model_journal'
                parked = baseline_dir/'parked'
                missing_dir.rename(parked)
                try:
                    with self.assertRaises(ValueError):m.load_baseline_context(baseline_manifest)
                    self.assertFalse(missing_dir.exists())
                finally:parked.rename(missing_dir)
                for name, mutate in (
                    ('wrong_observations', lambda v:v['artifacts'].update(result=write('wrong_obs.json',
                        dict(result=dict(observations=dict(c.caller._clean(obs),raw_rows=[]),
                            input_receipt=receipt,policy_identity=profile['policy_identity']))))),
                    ('short_roster',lambda v:v['inputs'].update(roster=h._write_raw(root/'short.csv',b'product_id\nDCE.P\n'))),
                    ('wrong_clock',lambda v:v['artifacts'].update(clock_domains=write('wrong_clock.json',
                        dict(domains,input_completion=dict(domains['input_completion'],source_completed_at='2026-10-20T15:00:00+08:00'))))),
                    ('wrong_inventory',lambda v:v['artifacts'].update(epoch_inventory=write('wrong_inventory.json',
                        [dict(r,last_date='2026-10-19') if r['epoch']==a else r for r in snap['_inventory']]))),
                ):
                    bad = deepcopy(batch_manifest)
                    mutate(bad)
                    with self.assertRaises(ValueError):m.restore_composed(write('batch/'+name+'.json',bad))
                object_path = source_journal.objects/(receipt['payload_sha256']+'.json')
                original_object = object_path.read_bytes()
                object_path.chmod(0o644)
                object_path.write_bytes(b'{}\n')
                try:
                    with self.assertRaises(ValueError):m.restore_composed(bb)
                finally:object_path.write_bytes(original_object)


if __name__ == '__main__':
    unittest.main()
