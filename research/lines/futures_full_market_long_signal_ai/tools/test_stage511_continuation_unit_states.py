"""New synthetic continuation fixtures; no inherited payload or actual run."""
import importlib.util
import csv
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np

P = Path(__file__).with_name('stage511_continuation_unit_states.py')


class ContinuationUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('stage511_fixture', P)
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    def path(self, bars, **changes):
        action = dict(action_id='a', product_id='X.P', family_id='X.P',
                      reference_epoch='X.P.202011', anchor_epoch='X.P.202010',
                      u_index=0, u_action_eligible=1, N_u=8., low20_u=90.,
                      source_lifecycle_index=50, K_index=40,
                      K_state='in_calendar', listed_index=0)
        action.update(changes)
        return self.m.unit_path(action, bars,
            {k: 'X.P.202010' for k in range(len(bars))},
            end_index=len(bars)-1)

    def b(self, O=100., L=99., C=102., low20=90., N=8.):
        return dict(open=O, high=max(O,C)+1., low=L, close=C,
                    volume=1000., low20=low20, N=N, run=25,
                    previous_close=100.)

    def test_entry_same_bar_stop_has_no_surviving_close(self):
        result = self.path({0:self.b(),1:self.b(L=97.)})
        self.assertEqual(result['summary']['terminal_reason'], 'stop_boundary')
        self.assertEqual(result['summary']['exit_reference'], 98.)
        self.assertEqual(result['states'], [])

    def test_stale_retains_prior_mark_then_first_legal_open_forces_exit(self):
        result = self.path({0:self.b(),1:self.b(),2:None,
                            3:self.b(O=91., L=80.)})
        self.assertEqual([r['riskset'] for r in result['states']], [1,0])
        stale = result['states'][1]
        self.assertEqual((stale['mark'],stale['force_next']),
                         (102.,'research_deferred_liquidation'))
        self.assertIsNone(stale['close'])
        self.assertEqual(result['summary']['terminal_reason'],
                         'research_deferred_liquidation')
        self.assertEqual(result['summary']['exit_reference'], 91.)
        # A voluntary request at close1 also waits through missing day2.
        self.assertEqual(result['execution_observations'][0]['exit_index'],3)
        self.assertEqual(result['execution_observations'][0]['reference'],91.)

    def test_anchor_is_fixed_and_force_open_has_priority_over_stop(self):
        bars={0:self.b(),1:self.b(),2:self.b(O=110.,L=80.)}
        action=dict(action_id='a', product_id='X.P',family_id='X.P',
            reference_epoch='held',anchor_epoch='canonical',u_index=0,
            u_action_eligible=1,N_u=8.,low20_u=90.,source_lifecycle_index=20,
            K_index=19,K_state='in_calendar',listed_index=0)
        result=self.m.unit_path(action,bars,{0:'canonical',1:'new'},2)
        self.assertEqual(result['states'][0]['force_next'],
                         'liquidity_reference_changed')
        self.assertEqual(result['states'][0]['riskset'],0)
        self.assertEqual(result['summary']['exit_reference'],110.)
        self.assertEqual(result['summary']['terminal_reason'],
                         'liquidity_reference_changed')

    def test_boundary_uses_current_own_low20_and_can_decrease(self):
        result=self.path({0:self.b(),1:self.b(low20=101.,L=99.),
                          2:self.b(O=104.,L=103.,C=105.,low20=99.)})
        self.assertEqual([s['boundary_next'] for s in result['states']],
                         [101.,99.])
        self.assertEqual(result['states'][1]['boundary_in'],101.)

    def test_lifecycle_and_k_cancel_prospectively_without_reading_entry(self):
        self.assertEqual(self.path({0:self.b(),1:None},K_index=1)
                         ['summary']['participation_state'],'D_not_before_K')
        result=self.path({0:self.b(),1:self.b(),2:self.b()},K_index=2)
        self.assertEqual(result['states'][0]['force_next'],'lifecycle_exit')
        self.assertEqual(result['states'][0]['riskset'],0)
        self.assertEqual(result['summary']['exit_index'],2)

    def test_state_riskset_does_not_peek_next_bar_or_terminal(self):
        a=self.path({0:self.b(),1:self.b(),2:None})
        b=self.path({0:self.b(),1:self.b(),2:self.b(L=80.)})
        self.assertEqual(a['states'][0],b['states'][0])
        self.assertEqual(a['states'][0]['riskset'],1)
        self.assertNotEqual(a['summary']['terminal_state'],
                            b['summary']['terminal_state'])
        self.assertIsNone(a['execution_observations'][0]['reference'])
        self.assertEqual(b['execution_observations'][0]['reference'],100.)

    def test_ineligible_entry_unknown_and_open_censored_are_not_zero_outcomes(self):
        self.assertEqual(self.path({0:self.b(),1:None},u_action_eligible=0)
            ['summary']['participation_state'],'u_ineligible')
        unknown=self.path({0:self.b(),1:None})
        self.assertEqual(unknown['summary']['participation_state'],
                         'entry_execution_unknown')
        self.assertIsNone(unknown['summary']['exit_reference'])
        opened=self.path({0:self.b(),1:self.b()})
        self.assertEqual(opened['summary']['terminal_state'],'open_right_censored')
        self.assertIsNone(opened['summary']['exit_reference'])

    def test_sell_quote_components_follow_tick_floor_and_keep_unrepresentable_unknown(self):
        self.assertTrue(hasattr(self.m,'sell_quote'), 'new isolated SELL quote function missing')
        e=dict(contract_multiplier=10.,tick_size=.3)
        base=self.m.sell_quote(100.,e,'base')
        stress=self.m.sell_quote(100.,e,'stress')
        self.assertEqual((base['fill_price'],base['fee_per_lot']),(99.6,2.))
        self.assertEqual((stress['fill_price'],stress['fee_per_lot']),(99.,6.))
        self.assertAlmostEqual(base['slippage_per_lot'],4.)
        unknown=self.m.sell_quote(.1,dict(contract_multiplier=10.,tick_size=1.),'stress')
        self.assertEqual(unknown['quote_state'],'nonpositive_adverse_fill')
        self.assertIsNone(unknown['fill_price'])

    def test_tiny_full_constructor_conserves_nochild_and_isolates_future_observations(self):
        # Synthetic integration only: none of the historical source files open.
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            days=['2009-12-30','2009-12-31','2010-01-04','2010-01-05']
            # Real5587 calendar extends beyond the sample snapshot; preserve
            # that separation rather than accidentally firing sentinel expiry.
            np.save(folder/'calendar.npy',np.array(days+['2010-01-06'],dtype='datetime64[D]'))
            epoch='X.P.201003';group=int(hashlib.sha256(b'X.P').hexdigest(),16)%2
            econ={epoch:dict(economics_status='exact_epoch_metadata_snapshot',
                contract_multiplier=10.,round_lot=1,tick_size=.1)}
            (folder/'economics.json').write_text(json.dumps(dict(instruments=econ)))
            np.savez(folder/'native.npz',epochs=np.array([epoch]),offsets=np.array([0,4]),
                days=np.arange(4),values=np.array([[100.,103.,99.,102.,1000.]]*4),
                accepted=np.ones(4,dtype=bool),valid=np.ones(4,dtype=bool),
                N=np.full(4,8.),low20=np.full(4,90.),run=np.full(4,25))
            with gzip.open(folder/'mothers.gz','wt',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=self.m.MOTHER_FIELDS);writer.writeheader()
                for k,day in enumerate(days):
                    writer.writerow(dict(sequence_index=k,event_id='m'+str(k),product_id='X.P',
                        family_id='X.P',u_date=day,u_index=k,reference_epoch=epoch,
                        family_hash_group=group,child_count=int(k==0),
                        eligible_child_count=int(k==0),nochild=int(k!=0)))
            with gzip.open(folder/'metadata.gz','wt',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=self.m.META_FIELDS+['filled','label_state'])
                writer.writeheader();writer.writerow(dict(sequence_index=0,action_id='a',
                    mother_sequence_index=0,mother_event_id='m0',product_id='X.P',family_id='X.P',
                    reference_epoch=epoch,anchor_epoch=epoch,u_date=days[0],u_index=0,D_index=1,
                    u_action_eligible=1,u_ineligibility_reason='',family_hash_group=group,
                    filled='FUTURE_COLUMN_MUST_NOT_PARSE',label_state='FUTURE_COLUMN_MUST_NOT_PARSE'))
            protocol=dict(schema='synthetic_only',sample_end=days[-1],cutoffs=['2020-01-01','2023-01-01'],
                metadata_field_allowlist=self.m.META_FIELDS,mother_field_allowlist=self.m.MOTHER_FIELDS,
                domain=dict(native_epochs=1,native_rows=4,mothers=4,no_child_mothers=3,
                    policy_products=1,policy_families=1,exchanges=1,actions=1,
                    observed_child_products=1,observed_child_families=1),
                inputs={name:self.m.binding(folder/path) for name,path in dict(
                    calendar='calendar.npy',economics='economics.json',native_cache='native.npz',
                    mothers='mothers.gz',metadata='metadata.gz').items()})
            result=self.m.construct(protocol,folder/'result')
            self.assertEqual(result['domain']['nochild'],3)
            self.assertEqual(result['held_close_states'],3)
            self.assertEqual(result['decision_riskset_states'],3)
            self.assertEqual(result['terminal'],{'open_right_censored':1})
            with gzip.open(folder/'result/unit_states.csv.gz','rt',newline='') as f:
                states=list(csv.DictReader(f))
            self.assertEqual(len(states),3)
            self.assertTrue(all('exit_reference' not in row for row in states))
            with gzip.open(folder/'result/voluntary_exit_observations.csv.gz','rt',newline='') as f:
                obs=list(csv.DictReader(f))
            self.assertEqual([r['reference'] for r in obs],['100.0','100.0',''])
            self.assertEqual(obs[-1]['state'],'pending_no_legal_open')


if __name__ == '__main__':
    unittest.main()
