"""Synthetic projection-only adversarial checks; no Runtime construction/API."""
from pathlib import Path
from copy import deepcopy
import sys,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
import qmt_roll_weekly19_live_pipeline as subject
from qmt_roll_weekly19_runtime import _encode,_pack_section
class FillSourceProjection(unittest.TestCase):
 def bundle(self,evidence=None,archive=None):
  plan=dict(offset='close',close_lifecycle_id='life',vt_symbol='ru2701.SHFE',direction='short',target_date='2026-10-30',next_execution_day='2026-11-02',intent_id='intent',exit_reason='long_base_stop')
  good=dict(trade_id='t1',raw_sha256='a'*64,signal_order_id='o1',trading_day='2026-11-02',execution_datetime='2026-11-02T09:00:00+08:00',volume=3,price=15000.)
  life=dict(symbol='ru2701.SHFE',order_ids=['o1'],volume=3,filled=3,status='completed',fill_evidence=[good]if evidence is None else evidence)
  state=dict(close_lifecycles={'life':life},fills={'t1':dict(first_raw_sha256='a'*64,semantic_sha256='b'*64)}if archive is None else archive)
  engine=dict(order_intents={'o1':plan},order_filled={'o1':3})
  return dict(decision={'trading_date':'2026-11-02'},runtime=dict(engine=_pack_section(_encode(engine)),runtime=_encode(state)))
 def unpack(self,bundle):
  from qmt_roll_weekly19_runtime import _decode
  return _decode(bundle['runtime']['runtime'])
 def replace_state(self,bundle,state):bundle['runtime']['runtime']=_encode(state);return bundle
 def test_real_bound_archive_row_projects_once(self):
  rows=subject._daily_risk_rows(self.bundle());self.assertEqual(len(rows),1);self.assertEqual(rows[0]['filled_volume'],3);self.assertEqual(rows[0]['fill_trading_dates'],['2026-11-02'])
 def test_unknown_trade_id_cannot_supply_today(self):
  b=self.bundle();s=self.unpack(b);s['close_lifecycles']['life']['fill_evidence'][0]['trade_id']='not_archived'
  with self.assertRaises(ValueError):subject._daily_risk_rows(self.replace_state(b,s))
 def test_wrong_actual_raw_hash_cannot_supply_today(self):
  b=self.bundle();s=self.unpack(b);s['close_lifecycles']['life']['fill_evidence'][0]['raw_sha256']='f'*64
  with self.assertRaises(ValueError):subject._daily_risk_rows(self.replace_state(b,s))
 def test_duplicate_same_trade_is_not_independent_fill_evidence(self):
  b=self.bundle();s=self.unpack(b);s['close_lifecycles']['life']['fill_evidence']*=2
  with self.assertRaises(ValueError):subject._daily_risk_rows(self.replace_state(b,s))
 def test_no_actual_fill_archive_is_not_complete_coverage(self):
  with self.assertRaises(ValueError):subject._daily_risk_rows(self.bundle(archive={}))
 def test_completed_legacy_unknown_date_not_silently_omitted(self):
  rows=subject._daily_risk_rows(self.bundle(evidence=[]));self.assertTrue(rows,'legacy unknown execution date must remain explicit, not become proven empty updates');self.assertNotEqual(rows[0]['fill_date_coverage'],'complete')
if __name__=='__main__':unittest.main()
