"""Exactly four new tiny Stage233 behaviors; no original data, fitting or cash."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

P=Path(__file__).with_name('stage233_K_payoff_measurement.py')
S=importlib.util.spec_from_file_location('stage233_tiny',P)
m=importlib.util.module_from_spec(S); S.loader.exec_module(m)
CAL=['2020-01-30','2020-01-31','2020-02-03','2020-02-04','2020-02-05']


def raw(state='closed_complete_bar_model',exit_index=2,unknown=None,epoch='DCE.A.202003'):
    names=['sequence_index','action_sequence_index','action_id','mother_sequence_index','mother_event_id',
           'product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible',
           'D_index','label_history_ready20','participation_state','label_state','filled','trade_label_known',
           'entry_index','entry_date','exit_index','exit_date','unknown_index','unknown_date','label_known_date',
           'label_known_phase','participation_known_date','participation_known_phase','last_path_index','cancel_reason',
           'exit_reason','N_u','R0_points','cash_risk_unit','multiplier','tick_size','entry_reference']
    r=dict.fromkeys(names,'')
    r.update(sequence_index='0',action_sequence_index='0',action_id='a',mother_sequence_index='0',mother_event_id='p',
             product_id='DCE.A',family_id='DCE.A',u_date=CAL[0],u_index='0',reference_epoch=epoch,
             anchor_epoch=epoch,u_action_eligible='1',D_index='1',label_history_ready20='1',
             participation_state='filled',label_state=state,filled='1',trade_label_known=str(int(state=='closed_complete_bar_model')),
             entry_index='1',entry_date=CAL[1],participation_known_date=CAL[1],
             participation_known_phase='after_all_source_close',last_path_index='4',
             N_u='8',R0_points='2',cash_risk_unit='20',multiplier='10',tick_size='1',entry_reference='100')
    if state=='closed_complete_bar_model':
        r.update(exit_index=str(exit_index),exit_date=CAL[exit_index],label_known_date=CAL[exit_index],
                 label_known_phase='after_all_source_close',exit_reason='stop_boundary')
    if unknown is not None:r.update(unknown_index=str(unknown),unknown_date=CAL[unknown])
    for s,fill,fee,slip in [('base','101','2','10'),('stress','103','6','30')]:
        r.update({s+'_entry_fill':fill,s+'_entry_fee_per_lot':fee,s+'_entry_slippage_per_lot':slip,
                  'net_pnl_'+s+'_per_lot':'-24.000000000000004' if state=='closed_complete_bar_model' else '',
                  'net_R_'+s:'-1.2000000000000002' if state=='closed_complete_bar_model' else '',
                  'net_R_common2N_'+s:'-0.15000000000000002' if state=='closed_complete_bar_model' else ''})
    return r


def native(O=110.,tick_valid=True):
    return dict(epochs=np.array(['DCE.A.202003']),offsets=np.array([0,5]),days=np.arange(5),
                values=np.array([[100,111,80,100,100]]*2+[[O,max(O,111),min(O,80),O,100]]+
                                [[100,111,80,100,100]]*2,float),valid=np.array([True,True,tick_valid,True,True]))


class TestStage233(unittest.TestCase):
    def measure(self,r,n=None,end=CAL[-1]):
        self.assertTrue(callable(getattr(m,'measure_action',None)),'new K payoff behavior is not implemented')
        return m.measure_action(r,CAL,end,native() if n is None else n)

    def test_copy_cancel_and_full_identity_counts(self):
        r=raw(exit_index=1); out,ev=self.measure(r)
        self.assertEqual(out['branch'],'copy_before_K');self.assertIsNone(ev)
        for s in ['base','stress']:
            self.assertEqual(out['K_'+s+'_net_R'],r['net_R_'+s])
            self.assertEqual(out['K_'+s+'_net_pnl_per_lot'],r['net_pnl_'+s+'_per_lot'])
            self.assertEqual(out['K_'+s+'_known_date'],CAL[1])
        cancelled=raw('known_nonparticipation');cancelled.update(filled='0',entry_index='',entry_date='',
          cancel_reason='stale_boundary_at_open',participation_state='known_nonparticipation')
        out,_=self.measure(cancelled)
        self.assertEqual(out['policy_reward'],'0');self.assertEqual(out['policy_known_date'],CAL[1])
        self.assertEqual(out['K_stress_net_R'],'')
        mother=[dict(sequence_index='0',event_id='p',product_id='DCE.A',family_id='DCE.A',u_date=CAL[0],u_index='0',reference_epoch='DCE.A.202003'),
                dict(sequence_index='1',event_id='p_nochild',product_id='DCE.B',family_id='DCE.B',u_date=CAL[0],u_index='0',reference_epoch='')]
        result=m.measure_rows(mother,[r],CAL,CAL[-1],native())
        self.assertEqual(len(result['labels']),1);self.assertEqual(len(result['mothers']),2)
        self.assertEqual(result['mothers'][1]['child_count'],0)
        broken=dict(r,mother_event_id='wrong')
        with self.assertRaises(ValueError):m.measure_rows(mother,[broken],CAL,CAL[-1],native())

    def test_forced_open_fees_clock_and_mapping(self):
        out,ev=self.measure(raw())
        self.assertEqual(out['branch'],'quote_K')
        self.assertAlmostEqual(float(out['K_base_net_pnl_per_lot']),76.)
        self.assertAlmostEqual(float(out['K_stress_net_R']),1.4)
        self.assertEqual(out['K_stress_known_date'],CAL[2])
        self.assertEqual(out['K_stress_known_phase'],'after_all_source_close')
        self.assertEqual(out['K_stress_exit_reason'],'K_deadline_open')
        self.assertEqual(out['exit_reason'],'stop_boundary')
        self.assertEqual(ev['flat_row'],2);self.assertEqual(ev['native_open'],110.)
        self.assertEqual(ev['K_base_sell_fee_per_lot'],2.)
        self.assertEqual(ev['K_base_sell_slippage_per_lot'],10.)
        with self.assertRaises(ValueError):self.measure(raw(),native(tick_valid=False))

    def test_cost_scenario_infeasibility_is_separate(self):
        r=raw();r.update(N_u='.4',R0_points='.1',cash_risk_unit='1',tick_size='.1',entry_reference='.2',
                        base_entry_fill='.3',stress_entry_fill='.5',base_entry_slippage_per_lot='1',stress_entry_slippage_per_lot='3')
        out,ev=self.measure(r,native(.2))
        self.assertEqual(out['K_base_known'],1);self.assertEqual(out['K_stress_known'],0)
        self.assertEqual(out['K_stress_state'],'unknown_K_cost');self.assertEqual(out['K_stress_net_R'],'')
        self.assertNotEqual(out['K_base_net_R'],'');self.assertEqual(ev['K_stress_sell_fill'],'')

    def test_unknown_prefix_pending_and_blocked_policy(self):
        for k in [1,2]:
            out,ev=self.measure(raw('path_or_execution_unknown',unknown=k))
            self.assertEqual(out['K_base_known'],0);self.assertEqual(out['policy_reward'],'');self.assertIsNone(ev)
        after,ev=self.measure(raw('path_or_execution_unknown',unknown=3))
        self.assertEqual(after['K_base_known'],1);self.assertEqual(ev['timing_state'],'unknown_after_K')
        pending,_=self.measure(raw('open_right_censored',epoch='DCE.A.202004'))
        self.assertEqual(pending['timing_state'],'open_K_pending');self.assertEqual(pending['K_stress_net_R'],'')
        blocked=raw(epoch='DCE.A.202002');out,ev=self.measure(blocked)
        self.assertEqual(out['branch'],'nonprimary_noaction');self.assertEqual(out['policy_known_date'],CAL[0])
        self.assertEqual(out['K_base_net_R'],'');self.assertIsNone(ev)


if __name__=='__main__':unittest.main()
