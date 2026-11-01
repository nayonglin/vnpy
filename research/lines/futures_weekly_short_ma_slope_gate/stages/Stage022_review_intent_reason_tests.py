"""Independent intent metadata tests; facade only, no broker/runtime replay."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
from copy import deepcopy
import importlib.util,sys,unittest
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[4];EX=ROOT/'examples/portfolio_backtesting';sys.path.insert(0,str(EX));import qmt_roll_weekly19_runtime as subject

class IntentReasonIsolation(unittest.TestCase):
 symbol='ru2701.SHFE';day='2026-11-02'
 def event(self,**changes):
  d=dict(date=self.day,datetime=self.day,vt_symbol=self.symbol,product_vt_symbol='ru.SHFE',position_direction='long',offset='Close',reason='long_base_stop',volume=5,price=15000.)
  d.update(changes);return d
 def collect(self,events,*,direction=None):
  rt=SimpleNamespace(calendar=[self.day,'2026-11-03'],account='a'*64,release='independent-component-fixture',revision=0,sizing_contexts={},current_receipt_hash='b'*64,confirmed_cash_state={'revision':0,'receipts':{}},broker_snapshot={'account':{'raw_sha256':'c'*64}},epoch_lookup={(self.symbol,self.day):'SHFE.ru.202701'})
  identity=dict(position_epoch_id='p',root_position_id='r',position_cycle_id='c');rt._position_identity=lambda *args:dict(identity);rt._latest_week=lambda *args:'2026-10-30';rt._open_ready=lambda:False
  metadata=dict(sizes={self.symbol:10},priceticks={self.symbol:5},rates={},slippages={},source_symbol_by_contract={self.symbol:'ru.SHFE'});rt.metadata=metadata;engine=subject.IntentEngine(rt,metadata);rt.engine=engine
  rt._attach_close_intent=lambda order:engine.order_intents[order].update(close_lifecycle_id='independent-fixture-life')
  engine.datetime=datetime.fromisoformat(self.day).replace(tzinfo=ZoneInfo('Asia/Shanghai'))
  strategy=SimpleNamespace(trade_event_diagnostics=deepcopy(events),update_order=lambda *args:None,pos_data={self.symbol:5},get_pos=lambda *args:5)
  engine.send_order(strategy,self.symbol,direction or subject.Direction.SHORT,subject.Offset.CLOSE,15000.,5)
  return engine.intents[0]
 def unknown(self,events):
  p=self.collect(events);self.assertIn('exit_reason',p);self.assertIn(p['exit_reason'],('',None));return p
 def test_current_close_reason_is_saved(self):
  p=self.collect([self.event()]);self.assertEqual(p['exit_reason'],'long_base_stop')
 def test_previous_day_reason_never_leaks(self):
  p=self.unknown([self.event(date='2026-10-30',datetime='2026-10-30',reason='rollover_close')]);self.assertEqual(p['intent_kind'],'risk_close')
 def test_same_day_open_event_is_not_a_close_reason(self):self.unknown([self.event(offset='Open',reason='long_case2')])
 def test_foreign_contract_reason_never_leaks(self):self.unknown([self.event(vt_symbol='rb2701.SHFE')])
 def test_wrong_original_position_direction_is_unknown(self):self.unknown([self.event(position_direction='short',reason='short_base_stop')])
 def test_different_current_close_reasons_are_ambiguous(self):self.unknown([self.event(),self.event(reason='long_prev2day_stop')])
 def test_later_irrelevant_diagnostic_does_not_mask_matching_close(self):
  p=self.collect([self.event(),self.event(offset='RiskSizing',reason='long_tighter_initial_stop_adjust')]);self.assertEqual(p['exit_reason'],'long_base_stop')
 def test_empty_diagnostics_remains_unknown(self):self.unknown([])
 def test_short_position_buy_close_maps_short_reason(self):
  p=self.collect([self.event(position_direction='short',reason='short_base_stop')],direction=subject.Direction.LONG);self.assertEqual(p['exit_reason'],'short_base_stop')
if __name__=='__main__':unittest.main()
