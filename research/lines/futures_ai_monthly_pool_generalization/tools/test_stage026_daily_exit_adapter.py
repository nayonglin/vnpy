import copy
import unittest
from stage026_daily_exit_adapter import decide_daily_exit, source_binding


def fixture(direction='long', qty=4):
    h=[{'open':100.,'high':101.,'low':99.,'close':100.} for _ in range(41)]
    return dict(state=dict(direction=direction,qty=qty,entry_price=100.,stop_price=90. if direction=='long' else 110.,max_profit_pct=0.,highest_price=100.,lowest_price=100.,prev2day_stop_price=None,rsi_partial_exit_done=False,bars_since_entry=1,contract='fixture.X',target_contract='fixture.X',pending_roll=False),history=h,bar=copy.deepcopy(h[-1]),rsi_value=50.,ma_long_prev_value=95. if direction=='long' else 105.)

class DailyAdapterTests(unittest.TestCase):
    def test_low_touch_is_not_close_stop(self):
        x=fixture(); x['bar']['low']=80.; x['history'][-1]=dict(x['bar'])
        r=decide_daily_exit(**x); self.assertIsNone(r['request']);self.assertEqual(r['status'],'known_decision')
    def test_close_stop_only_queues_next_session(self):
        x=fixture();x['bar']=dict(open=100.,high=101.,low=88.,close=89.);x['history'][-1]=dict(x['bar'])
        r=decide_daily_exit(**x);self.assertEqual(r['request']['reason'],'long_base_stop'); self.assertEqual(r['request']['reduce_qty'],4);self.assertEqual(r['request']['execution_timing'],'next_valid_session_open_required');self.assertNotIn('fill_price',r['request']); self.assertEqual(r['proposed_state']['qty'],4)
    def test_prior_profit_lock_updated_before_close_test(self):
        x=fixture();x['state']['max_profit_pct']=.03;x['bar']=dict(open=100.,high=101.,low=99.,close=100.5);x['history'][-1]=dict(x['bar']); r=decide_daily_exit(**x)
        self.assertEqual(r['proposed_state']['stop_price'],101.); self.assertEqual(r['request']['reason'],'long_base_stop')
    def test_prev2day_has_priority(self):
        x=fixture();x['state']['bars_since_entry']=2;x['state']['stop_price']=100.5;x['history'][-3]['low']=100.;x['history'][-3]['open']=100.;x['history'][-2]['low']=100.;x['history'][-2]['open']=100.
        r=decide_daily_exit(**x);self.assertEqual(r['request']['reason'],'long_prev2day_stop')
    def test_rsi_partial_skips_ma(self):
        x=fixture();x['rsi_value']=96.;x['ma_long_prev_value']=101.; r=decide_daily_exit(**x)
        self.assertEqual(r['request']['reason'],'long_rsi_partial_exit_half');self.assertEqual(r['request']['reduce_qty'],2);self.assertTrue(r['proposed_state']['rsi_partial_exit_done']);self.assertEqual(r['proposed_state']['qty'],4)
    def test_one_lot_no_partial_then_ma(self):
        x=fixture(qty=1);x['rsi_value']=96.;x['ma_long_prev_value']=101.;r=decide_daily_exit(**x)
        self.assertEqual(r['request']['reason'],'long_ma_stop');self.assertFalse(r['proposed_state']['rsi_partial_exit_done'])
    def test_short_partial_mirror(self):
        x=fixture('short',3);x['rsi_value']=4.;x['ma_long_prev_value']=99.;r=decide_daily_exit(**x)
        self.assertEqual(r['request']['reason'],'short_rsi_partial_exit_half');self.assertEqual(r['request']['reduce_qty'],1)
    def test_rsi_strict_and_done(self):
        x=fixture();x['rsi_value']=95.;self.assertIsNone(decide_daily_exit(**x)['request']);x['rsi_value']=96.;x['state']['rsi_partial_exit_done']=True;self.assertIsNone(decide_daily_exit(**x)['request'])
    def test_atr_mid_updates_stop_before_trigger(self):
        x=fixture();x['history']=[dict(open=100.,high=100.5,low=99.5,close=100.) for _ in range(41)];x['bar']=dict(open=100.,high=115.,low=99.,close=105.);x['history'][-1]=dict(x['bar']);r=decide_daily_exit(**x)
        self.assertAlmostEqual(r['proposed_state']['stop_price'],107.);self.assertEqual(r['request']['reason'],'long_base_stop')
    def test_input_not_mutated(self):
        x=fixture();saved=copy.deepcopy(x);decide_daily_exit(**x);self.assertEqual(x,saved)
    def test_roll_is_explicitly_unsupported(self):
        for field,val in [('target_contract','other.X'),('pending_roll',True)]:
            x=fixture();x['state'][field]=val;r=decide_daily_exit(**x);self.assertEqual(r['status'],'unsupported_roll_contract');self.assertIsNone(r['request'])
    def test_invalid_inputs_fail_before_source(self):
        for mutate in [lambda x:x['state'].update(qty=1.5),lambda x:x['state'].update(qty=True),lambda x:x['state'].update(bars_since_entry=-1),lambda x:x.update(rsi_value=float('nan')),lambda x:x['history'].pop(),lambda x:x['bar'].update(low=102.),lambda x:x['state'].update(stop_price=0.),lambda x:x['state'].update(pending_roll='False')]:
            x=fixture();mutate(x)
            with self.assertRaises(ValueError):decide_daily_exit(**x)
    def test_binding_is_frozen_not_runtime_import(self):
        b=source_binding();self.assertEqual(b['release_id'],'m0008_20261008T204054+0800_2a7420a9f955');self.assertGreaterEqual(len(b['method_ast_sha256']),13);self.assertFalse(b['settings']['enable_profit_giveback_stop'])

if __name__=='__main__':unittest.main()
