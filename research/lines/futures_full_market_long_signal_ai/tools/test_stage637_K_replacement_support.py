"""Six synthetic structural cases, no historical rows or execution replay."""
import importlib.util
from pathlib import Path
import unittest

SOURCE=Path(__file__).with_name('stage637_K_replacement_support.py')


def module():
    assert SOURCE.exists(),'new637 implementation absent'
    s=importlib.util.spec_from_file_location('new637',SOURCE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def fixture():
    dates=['2022-12-01','2022-12-02','2023-01-03','2023-01-04','2023-02-01','2023-03-01']
    def sig(event,u,D,epoch,K,source,cutoff):
        return dict(event_id=event,mother_event_id='mother_'+event,action_sequence_index='1',product_id='X',family_id='X',
            u_date=dates[u],u_index=str(u),D_index=str(D),reference_epoch=epoch,anchor_epoch='X.202301',N_u='4',low20_u='90',u_close='100',
            entry_capacity_qty='100',u_gross_capacity_qty='200',score='.2',cutoff=cutoff,source_lifecycle_index=str(source),
            voluntary_boundary_index=str(K),effective_lifecycle_index=str(min(K,source)),lifecycle_index=str(min(K,source)),
            effective_boundary_origin='voluntary_calendar' if K<source else 'same_source_and_voluntary' if K==source else 'source_lifecycle',
            K_date=dates[K],K_state='in_calendar',K_target_date=dates[K],potential='1',label_history_ready20='1',history_run='20')
    old=sig('old',0,1,'X.202303',3,5,'2020-01-01');new=sig('new',2,3,'X.202304',4,5,'2023-01-01')
    p=dict(account_id='acct',scenario='base',date=dates[2],root_id='acct_old',event_id='old',family_id='X',product_id='X',
        epoch=old['reference_epoch'],qty='2',mark_state='native_close',stale_days='0',force_next='lifecycle_exit',reduce_to_next='',
        risk_per_lot='10',multiplier='10',_u_qty_reconciled=True)
    daily=dict(equity='1000000',initial_risk='20',buffered_margin='100',ever_insolvent='False',stale_positions='0',stale_zero_equity='False',unresolved_zero_equity='False')
    buy=dict(p,date=dates[1],side='BUY',qty='2',reason='new_entry',budget_id='acct_old',reference_price='100',fill_price='101',capacity_state='known_within_cap')
    reservation=dict(event_id='old',budget_id='acct_old',u_date=dates[0],execution_date=dates[1],budget_kind='new_entry',round_lot='1',D_qty='2')
    canon=dict(reference_state='found',reference_epoch=old['anchor_epoch'])
    return p,old,new,daily,buy,reservation,[],dates,canon


class New637(unittest.TestCase):
    def test_strict_K_actual_root_and_D_fact_do_not_create_newlot_qualification(self):
        m=module();args=fixture();u=m.evaluate_u(*args);self.assertEqual(u['u_plan_state'],'supported')
        self.assertEqual(u['replacement_qty'],'unknown');self.assertEqual(u['newroot_reservation'],'unknown')
        p=args[0];sell=dict(args[4],date=args[7][3],side='SELL',reason='lifecycle_exit')
        d=m.observe_D(p,args[7][3],[sell],[],True);self.assertEqual(d['D_observation_state'],'observed_full_lifecycle_close')
        bad=list(args);bad[0]=dict(p,root_id='acct_mother_old')
        self.assertEqual(m.evaluate_u(*bad)['u_plan_state'],'unknown')

    def test_equal_and_earlier_source_lifecycle_are_known_blocked(self):
        m=module()
        for source in (3,2):
            args=list(fixture());old=dict(args[1],source_lifecycle_index=str(source),effective_lifecycle_index=str(source),lifecycle_index=str(source),
                effective_boundary_origin='same_source_and_voluntary' if source==3 else 'source_lifecycle');args[1]=old
            self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'known_false')

    def test_missing_changed_canonical_and_nonfront_anchor_are_distinguished(self):
        m=module();args=list(fixture());self.assertNotEqual(args[0]['epoch'],args[1]['anchor_epoch'])
        self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'supported')
        args[-1]=dict(reference_state='missing',reference_epoch='');self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'unknown')
        args[-1]=dict(reference_state='found',reference_epoch='X.202302');self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'known_false')

    def test_numeric_zero_reduction_and_optional_missing_reservation_header(self):
        m=module();args=list(fixture());args[6]=[dict(budget_kind='new_entry',event_id='unrelated')]
        self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'supported')
        args[0]=dict(args[0],reduce_to_next='0');self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'known_false')
        args= list(fixture());args[6]=[dict(budget_kind='existing_position_reduction',event_id='old',target_existing_qty='0')]
        self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'known_false')

    def test_no_intent_same_epoch_and_independent_entry_cutoff(self):
        m=module();args=list(fixture());self.assertNotEqual(args[1]['cutoff'],args[2]['cutoff'])
        self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'supported')
        args[2]=None;args[-1]=None;self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'known_false')
        self.assertEqual(m.evaluate_u(*args)['canonical_state'],'not_requested')
        args=list(fixture());args[2]=dict(args[2],reference_epoch=args[0]['epoch']);args[-1]=None
        self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'known_false')

    def test_partial_mixed_missing_D_never_rewrites_u_and_capacity_unknown_is_retained(self):
        m=module();args=fixture();p=args[0];self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'supported')
        sell=dict(args[4],date=args[7][3],side='SELL',reason='lifecycle_exit',capacity_state='execution_capacity_unknown')
        full=m.observe_D(p,args[7][3],[sell],[],True)
        self.assertEqual(full['D_observation_state'],'observed_full_lifecycle_close');self.assertIn('execution_capacity_unknown',full['D_old_capacity_states_json'])
        partial=m.observe_D(p,args[7][3],[dict(sell,qty='1')],[dict(p,date=args[7][3],qty='1')],True)
        self.assertEqual(partial['D_observation_state'],'known_false')
        mixed=m.observe_D(p,args[7][3],[dict(sell,reason='risk_margin_joint_reduction')],[],True)
        self.assertEqual(mixed['D_observation_state'],'known_false')
        self.assertEqual(m.observe_D(p,args[7][3],[],[],False)['D_observation_state'],'unknown')
        self.assertEqual(m.evaluate_u(*args)['u_plan_state'],'supported')


if __name__=='__main__':unittest.main()
