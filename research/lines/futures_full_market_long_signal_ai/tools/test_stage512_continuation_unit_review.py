"""New synthetic reviewer checks only; no inherited payload or author import."""
import importlib.util
import copy
from pathlib import Path
import tempfile
import unittest
import numpy as np

P=Path(__file__).with_name('stage512_continuation_unit_review.py')
spec=importlib.util.spec_from_file_location('independent512',P)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class ReviewerTests(unittest.TestCase):
    def test_quote_uses_tick_direction_fee_and_unknown(self):
        e=dict(tick_size=.3,contract_multiplier=10)
        self.assertEqual(m.independent_quote(100,e,'base')[:3],
                         ('observed_research_quote',99.6,2.))
        self.assertEqual(m.independent_quote(100,e,'stress')[:3],
                         ('observed_research_quote',99.,6.))
        self.assertEqual(m.independent_quote(.1,dict(tick_size=1,contract_multiplier=10),
                                           'stress')[0],'nonpositive_adverse_fill')

    def test_calendar_never_fills_unavailable_K_with_zero(self):
        d=['2019-12-31','2020-01-02','2020-01-03']
        self.assertEqual(m.nominal_K('X.A.202002',d)[1:3],(1,'2020-01-02'))
        self.assertEqual(m.nominal_K('X.A.201912',d)[3],'before_calendar_blocked')
        self.assertEqual(m.nominal_K('X.A.202003',d)[1:],(None,None,'after_calendar_pending'))

    def test_force_priority_is_cash_not129_label_path(self):
        self.assertEqual(m.expected_force('a','b',4,4,'old'),'lifecycle_exit')
        self.assertEqual(m.expected_force('a','b',3,4,'old'),'old')

    def test_future_nearest_open_cannot_change_riskset(self):
        states=[dict(t_index=1,riskset=1,current_native_valid=1,open=100),
                dict(t_index=2,riskset=0,current_native_valid=0,open=None)]
        self.assertEqual(m.expected_voluntary(states,3,90),{1:(3,90)})
        self.assertEqual(m.expected_voluntary(states),{1:(None,None)})
        self.assertEqual(states[0]['riskset'],1)

    def toy_path(self):
        p=dict(participation_state='entered',u_index=0,entry_index=1,
               u_action_eligible=1,entry_reference=100.,SL0=98.,N_u=8.,
               low20_u=90.,anchor_epoch='anchor',effective_lifecycle_index=10,
               terminal_state='closed_complete_bar_model',exit_index=3,
               exit_reference=91.,terminal_reason='research_deferred_liquidation',
               state_count=2,riskset_count=1,stale_count=1)
        s=dict(t_index=1,entry_index=1,entry_reference=100.,N_u=8.,SL0=98.,
               boundary_in=98.,boundary_next=98.,previous_mark=100.,mark=102.,
               age_source_days=1,current_native_valid=1,open=100.,high=103.,low=99.,
               close=102.,volume=1000.,low20_t=90.,mark_state='native_close',
               canonical_reference='anchor',stale_days=0,deferred=0,force_next=None,
               riskset=1,next_planned_index=2)
        missing=copy.deepcopy(s);missing.update(t_index=2,previous_mark=102.,
               age_source_days=2,current_native_valid=0,open=None,high=None,low=None,
               close=None,volume=None,low20_t=None,mark_state='stale',stale_days=1,
               deferred=1,force_next='research_deferred_liquidation',riskset=0,
               next_planned_index=3)
        return p,[s,missing],dict(bar=dict(open=91.,low=80.))

    def test_chain_retains_stale_then_forces_at_first_valid_open(self):
        p,s,t=self.toy_path()
        self.assertEqual(m.validate_states(p,s,t,3),
                         dict(states=2,riskset=1,stale=1,force=1))
        s[1]['riskset']=1
        with self.assertRaisesRegex(AssertionError,'risk set'):
            m.validate_states(p,s,t,3)

    def test_chain_rolling_low_boundary_is_not_monotonic_ratchet(self):
        p,s,_=self.toy_path();s=s[:1]
        s[0]['low20_t']=101.;s[0]['boundary_next']=101.
        newer=copy.deepcopy(s[0]);newer.update(t_index=2,boundary_in=101.,
               boundary_next=99.,previous_mark=102.,mark=105.,age_source_days=2,
               open=104.,high=106.,low=103.,close=105.,low20_t=99.,next_planned_index=3)
        p.update(terminal_state='open_right_censored',exit_index=None,
                 exit_reference=None,terminal_reason=None,riskset_count=2,stale_count=0)
        s.append(newer)
        m.validate_states(p,s,None,2)
        s[1]['boundary_next']=101.
        with self.assertRaisesRegex(AssertionError,'next own boundary'):
            m.validate_states(p,s,None,2)

    def test_sparse_reader_reads_rows_and_missing_day_without_array_load(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'new_toy.npz'
            np.savez(p,epochs=np.array(['X.A.202001','X.B.202001'],dtype='U40'),
                     offsets=np.array([0,2,3]),days=np.array([1,3,2]),
                     values=np.arange(15.).reshape(3,5),valid=np.array([True,True,False]),
                     N=np.array([1.,2.,3.]),low20=np.array([5.,6.,7.]),run=np.array([20,21,1]))
            r=m.StoredNativeRanges(p,max_bytes=10000)
            got=r.day_row('X.A.202001',3)
            self.assertEqual(got['N'],2.)
            self.assertEqual(got['values'].tolist(),[5,6,7,8,9])
            self.assertIsNone(r.day_row('X.A.202001',2))
            self.assertLess(r.bytes_read,10000)
            self.assertGreater(len(r.ranges),0)
            r.close()

    def test_sparse_reader_refuses_compressed_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'new_compressed.npz';np.savez_compressed(p,days=np.arange(3))
            with self.assertRaises(AssertionError):m.StoredNativeRanges(p)


if __name__=='__main__':unittest.main()
