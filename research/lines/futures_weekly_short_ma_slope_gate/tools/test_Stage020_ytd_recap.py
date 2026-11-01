import importlib.util,json,tempfile,unittest
from pathlib import Path
import pandas as pd

HERE=Path(__file__).resolve().parent
def subject():
 spec=importlib.util.spec_from_file_location('ytd_recap_under_test',HERE/'Stage020_ytd_recap.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class AnnualRecapAdapterTests(unittest.TestCase):
 def fixture(self,short=False):
  return pd.DataFrame([
   dict(trade_id='BACKTESTING.1',order_id='BACKTESTING.1',datetime='2026-01-23 21:00:00+08:00',trading_date='2026-01-26',vt_symbol='a2605.DCE',direction='空'if short else'多',offset='开',price=100.,volume=3,exit_reason=''),
   dict(trade_id='BACKTESTING.2',order_id='BACKTESTING.2',datetime='2026-01-30 09:00:00+08:00',trading_date='2026-01-30',vt_symbol='a2605.DCE',direction='多'if short else'空',offset='平',price=90. if short else 110.,volume=3,exit_reason='frozen_exit')]),pd.DataFrame([dict(vt_symbol='a2605.DCE',opened_on='2026-01-26',closed_on='2026-01-30',trade_ids="['BACKTESTING.1', 'BACKTESTING.2']",net_pnl=180.)])
 def test_net_profit_uses_frozen_round_and_both_fill_costs(self):
  m=subject();fills,rounds=self.fixture();r=m.normalize_rounds(rounds,fills,{'a2605.DCE':10},{'a2605.DCE':2},{'a2605.DCE':0})
  self.assertEqual(r.iloc[0].net_pnl,180.)
  self.assertEqual(r.iloc[0].gross_pnl,300.);self.assertEqual(r.iloc[0].cost,120.)
 def test_trading_date_preserved_for_friday_night_execution(self):
  m=subject();fills,rounds=self.fixture();r=m.normalize_rounds(rounds,fills,{'a2605.DCE':10},{'a2605.DCE':2},{'a2605.DCE':0})
  self.assertEqual(r.iloc[0].entry_trading_date,'2026-01-26');self.assertIn('2026-01-23',r.iloc[0].entry_execution_datetime)
 def test_residual_or_unpaired_fill_is_never_silently_dropped(self):
  m=subject();fills,rounds=self.fixture();fills.loc[2]=dict(fills.iloc[0],trade_id='BACKTESTING.3',order_id='BACKTESTING.3')
  with self.assertRaises(ValueError):m.normalize_rounds(rounds,fills,{'a2605.DCE':10},{'a2605.DCE':2},{'a2605.DCE':0})
 def test_gross_or_mismatched_round_pnl_rejected(self):
  m=subject();fills,rounds=self.fixture();rounds.loc[0,'net_pnl']=300.
  with self.assertRaises(ValueError):m.normalize_rounds(rounds,fills,{'a2605.DCE':10},{'a2605.DCE':2},{'a2605.DCE':0})
 def test_short_underlying_move_stays_negative(self):
  m=subject();fills,rounds=self.fixture(short=True);r=m.normalize_rounds(rounds,fills,{'a2605.DCE':10},{'a2605.DCE':2},{'a2605.DCE':0})
  self.assertEqual(r.iloc[0].direction,'short');self.assertAlmostEqual(r.iloc[0].price_move_pct,-10.)
 def test_output_isolation(self):
  m=subject()
  for path in [m.RUN,m.LINE/'artifacts/stage019_2026_ytd',m.ROOT/'research/lines/futures_trend_winner_trade_forensics/outputs/test']:
   with self.subTest(path=path),self.assertRaises(ValueError):m.require_output(path)
 def test_incomplete_or_tampered_delivery_is_rejected(self):
  m=subject()
  with tempfile.TemporaryDirectory()as temp:
   p=Path(temp)/'receipt.json';p.write_text(json.dumps({'accepted':True,'delivery_files_sha256':{}}))
   with self.assertRaises(ValueError):m.verify_delivery(p)
 def test_market_context_must_match_original_run_input_hashes(self):
  m=subject()
  with tempfile.TemporaryDirectory()as temp:
   root=Path(temp);pins={}
   for name in ['daily.sqlite','physical_epoch_daily.csv','metadata.csv','mapping.csv','receipt.json']:
    p=root/name;p.write_text(name);pins[str(p)]=m.sha(p)
   m.verify_market_inputs(pins,root)
   (root/'physical_epoch_daily.csv').write_text('different candles')
   with self.assertRaises(ValueError):m.verify_market_inputs(pins,root)
 def test_admitted_minute_csv_tamper_is_rejected(self):
  m=subject()
  with tempfile.TemporaryDirectory()as temp:
   root=Path(temp);data=root/'qualified.csv';data.write_text('first');r=root/'qualification.json'
   r.write_text(json.dumps(dict(accepted=True,failures=[],qualified_csv=str(data),qualified_csv_sha256=m.sha(data),input_files_sha256={})))
   expected=m.sha(r);m.verify_minute_source(data,r,expected_receipt_sha256=expected)
   data.write_text('changed')
   with self.assertRaises(ValueError):m.verify_minute_source(data,r,expected_receipt_sha256=expected)

if __name__=='__main__':unittest.main()
