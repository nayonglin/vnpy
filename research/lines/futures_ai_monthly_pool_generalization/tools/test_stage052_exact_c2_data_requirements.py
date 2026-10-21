import copy
import unittest
from stage052_exact_c2_data_requirements import extract_window_requirements,aggregate_requirements
REASON='c2_order_or_fill_unknown_without_minute_path'

def fixture(roll=False):
    row=dict(exchange='SHFE',product='AU',product_vt_symbol='AU.SHFE',eval_date='2021-07-30',first_unknown_day='2021-08-02',first_unknown_reason=REASON)
    state=dict(contract='SHFE.AU.202112',direction='long',entry_price=100.,stop_price=90.,qty=2,bars_since_entry=0)
    rec=dict(bar=dict(open=100.,high=111.,low=89.,close=100.,volume=100),c2_guard_tick=1.,economics=dict(tick=.5),anchor=dict(execution_datetime='2021-08-02T00:00:00',logical_bar_label_not_physical=True),native_for_execution_tick='au2112.SHFE')
    new=dict(contract='SHFE.AU.202112',signal_day='2021-07-30')
    pending=dict(kind='roll',contract='SHFE.AU.202110',new=new) if roll else dict(kind='open',contract='SHFE.AU.202112',signal_day='2021-07-30')
    legs=[dict(kind='close',contract='SHFE.AU.202110',trading_day='2021-08-02',price=95,qty=2,rollover=True)] if roll else []
    legs.append(dict(kind='open',contract='SHFE.AU.202112',trading_day='2021-08-02',price=100.,qty=2,rollover=roll))
    path=dict(path_id=0,trace=[dict(day='2021-07-30',status='known',pending=pending),dict(day='2021-08-02',status='trajectory_unknown',state=state,unknown_reasons=[REASON])],episodes=[dict(episode_id=0,signal_day='2021-07-01' if roll else '2021-07-30',snapshot=dict(risk_currency=200.),tape=legs)])
    case=dict(sessions={'2021-08-02':dict(target_contract='SHFE.AU.202202',contracts={'SHFE.AU.202112':rec})})
    meta={'SHFE.AU.202112':dict(order_book_id='AU2112',exchange='SHFE',trading_hours='vendor_snapshot_not_session_qualification')}
    return row,case,dict(paths=[path]),meta

class ExactC2RequirementTests(unittest.TestCase):
    def test_held_epoch_wins_over_current_representative_and_time_is_not_invented(self):
        x=fixture();before=copy.deepcopy(x);r=extract_window_requirements(*x)[0]
        self.assertEqual(x,before);self.assertEqual(r['contract_epoch_id'],'SHFE.AU.202112')
        self.assertEqual(r['asof_target_epoch'],'SHFE.AU.202202');self.assertTrue(r['held_differs_from_asof_target'])
        self.assertEqual(r['source_trade_date'],'2021-08-02');self.assertEqual(r['source_logical_anchor_datetime'],'2021-08-02T00:00:00')
        self.assertFalse(r['physical_session_verified']);self.assertEqual(r['metadata_order_book_id_hint'],'AU2112')
        self.assertEqual(r['configured_guard_tick'],1.);self.assertEqual(r['effective_fill_tick'],.5)
    def test_roll_uses_actual_open_leg_and_preserves_original_episode_and_layer_signal_dates(self):
        r=extract_window_requirements(*fixture(True))[0]
        self.assertEqual(r['entry_kind'],'roll');self.assertEqual(r['episode_signal_day'],'2021-07-01')
        self.assertEqual(r['layer_signal_day'],'2021-07-30');self.assertEqual(r['source_day_fill_leg_count'],2)
    def test_missing_state_is_unknown_not_representative_substitution(self):
        x=fixture();x[2]['paths'][0]['trace'][1]['state']=None;r=extract_window_requirements(*x)[0]
        self.assertEqual(r['extraction_status'],'exact_held_state_unknown');self.assertEqual(r['contract_epoch_id'],'')
    def test_missing_exact_contract_record_does_not_select_other_contract(self):
        x=fixture();x[1]['sessions']['2021-08-02']['contracts']={};r=extract_window_requirements(*x)[0]
        self.assertEqual(r['extraction_status'],'exact_held_record_missing');self.assertEqual(r['contract_epoch_id'],'SHFE.AU.202112')
    def test_changed_original_first_unknown_fails(self):
        x=fixture();x[0]['first_unknown_day']='2021-08-03'
        with self.assertRaisesRegex(ValueError,'first_unknown'):extract_window_requirements(*x)
    def test_actual_source_open_leg_is_required_not_pending_open(self):
        x=fixture();x[2]['paths'][0]['episodes'][0]['tape']=[];r=extract_window_requirements(*x)[0]
        self.assertEqual(r['extraction_status'],'source_entry_leg_unidentified')
    def test_dedup_data_key_keeps_distinct_entry_states_and_all_window_maps(self):
        a=extract_window_requirements(*fixture())[0];x=fixture();x[0]['eval_date']='2021-06-30';x[2]['paths'][0]['trace'][1]['state']['stop_price']=85.;b=extract_window_requirements(*x)[0]
        demands,states=aggregate_requirements([a,b]);self.assertEqual(len(demands),1);self.assertEqual(len(states),2)
        self.assertEqual(demands[0]['window_path_mappings'],2);self.assertEqual(demands[0]['state_variants'],2)
    def test_metadata_nan_hint_is_unknown_not_non_json_number(self):
        x=fixture();x[3]['SHFE.AU.202112']['order_book_id']=float('nan');r=extract_window_requirements(*x)[0]
        self.assertEqual(r['metadata_order_book_id_hint'],'')

    def test_metadata_absence_stays_empty_hint(self):
        x=fixture();x[3].clear();r=extract_window_requirements(*x)[0]
        self.assertEqual(r['metadata_order_book_id_hint'],'');self.assertFalse(r['broker_symbol_qualified'])

if __name__=='__main__':unittest.main()
