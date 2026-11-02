"""Conditional original-runtime/cash fixtures. No broker, SMTP or production proof."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta
from pathlib import Path
import json,sys,unittest
from unittest.mock import patch
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'));sys.path.insert(0,str(ROOT/'tests'))
import qmt_roll_weekly19_funding as funds
import qmt_roll_weekly19_runtime as runtime
from test_weekly19_runtime import fixture,broker,envelope,receipt,ACCOUNT,RELEASE,NOW
try:import qmt_roll_weekly19_friday_advice as advice
except ModuleNotFoundError:advice=None


def make_bundle(holiday=False,two=False,cash=None):
 day='2026-10-29'if holiday else'2026-10-30'
 at=datetime.fromisoformat(day+'T15:15:00+08:00')
 calendar,epochs,bars,metadata=fixture()
 if holiday:calendar.remove('2026-10-30')
 if two:
  epochs=pd.concat([epochs,epochs.assign(vt_symbol='fu2612.SHFE',contract_epoch_id='fu2612-physical')],ignore_index=True)
  for row in bars.values():row['fu2612.SHFE']=replace(next(iter(row.values())),symbol='fu2612')
 baseline=broker(day=day,now=at-timedelta(minutes=1))
 raw=json.loads(baseline['account']['raw_payload']);raw.update(query_last_seen=True,query_error_rows=0)
 baseline['account']=envelope(raw)
 if cash is None:cash=funds.begin_cash_observation(funds.initial_state(ACCOUNT,RELEASE,day),baseline['account'],at-timedelta(minutes=1))
 snapshot=broker(balance='120000.00',available='0.00',day=day,now=at)
 obj=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,metadata,calendar,epochs,snapshot,None,cash,clock=lambda:at)
 obj.warmup([bars[d]for d in sorted(bars)if d<day])
 decision=obj.process_completed_day(day,bars[day],receipt(day),snapshot,cash)
 state=obj.export_state()
 bundle=dict(schema='weekly19.pipeline-state.v1',revision=0,account_key=ACCOUNT,material_release_id=RELEASE,
  runtime_mode='preview',funding=deepcopy(obj.confirmed_cash_state),runtime=state,decision=deepcopy(decision),decision_state=deepcopy(state))
 return bundle,obj


def with_cash(bundle,obj,cash,snapshot,now):
 obj.clock=lambda:now
 obj.reconcile_broker_snapshot(snapshot,cash)
 result=deepcopy(bundle);result['funding']=deepcopy(cash);result['runtime']=obj.export_state()
 return result


def confirm(bundle,obj,amount='10000.00',equity='130000.00'):
 rid=next(iter(bundle['funding']['requests']));at=NOW+timedelta(minutes=1)
 cashflow=envelope(dict(schema='weekly19.bank-cashflow.v1',source_kind='broker_cashflow_receipt',account_key=ACCOUNT,
  material_release_id=RELEASE,request_id=rid,trading_day='2026-10-30',occurred_at=at.isoformat(),receipt_id='bank-1',
  Amount=amount,Direction='deposit',Status='completed'))
 snap=broker(balance=equity,available='0.00',now=at)
 raw=json.loads(snap['account']['raw_payload']);raw['Deposit']=amount;snap['account']=envelope(raw)
 cash=funds.confirm_topup(bundle['funding'],rid,cashflow,snap['account'],at)
 return with_cash(bundle,obj,cash,snap,at),snap,at


class FridayAdviceTest(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(advice,'friday advice helper missing')
 def test_holiday_thursday_native_batch_gets_canonical_friday_advice_without_rerun(self):
  bundle,obj=make_bundle(holiday=True);before=deepcopy(bundle)
  self.assertTrue(bundle['decision']['funding_admitted_ids']);self.assertIsNone(bundle['decision']['funding_recommendation'])
  account=broker(balance='120000.00',day='2026-10-29',now=NOW)['account']
  with patch.object(obj.strategy,'on_bars',side_effect=AssertionError('no strategy rerun')):
   result=advice.refresh_friday_advice(bundle,account,NOW)
  self.assertEqual(bundle,before);self.assertEqual(result['status'],'ready',result)
  self.assertTrue(result['recommendation']['actionable']);self.assertEqual(result['recommendation']['amount_fen'],3000000)
  self.assertEqual(result['source_bindings']['original_target_date'],'2026-10-29')
  request=next(iter(result['funding']['requests'].values()));self.assertEqual(request['target_week_end'],'2026-10-30')
  self.assertEqual(result['funding']['reserve_remaining_fen'],15000000);self.assertEqual(result['funding']['confirmed_topup_fen'],0)
  self.assertEqual(result,advice.refresh_friday_advice(bundle,account,NOW))
  committed=with_cash(bundle,obj,result['funding'],broker(balance='120000.00',day='2026-10-29',now=NOW),NOW)
  replay=advice.refresh_friday_advice(committed,account,NOW)
  self.assertEqual(replay['advice_id'],result['advice_id']);self.assertEqual(replay['recommendation'],result['recommendation'])
  self.assertEqual(replay['original_offer_remaining_fen'],result['original_offer_remaining_fen'])
 def test_normal_friday_does_not_add_request_and_unpaid_changed_gap_is_proven_replaced(self):
  bundle,obj=make_bundle();old=deepcopy(bundle);account=broker(balance='130000.00',now=NOW)['account']
  result=advice.refresh_friday_advice(bundle,account,NOW)
  self.assertEqual(bundle,old);self.assertEqual(result['recommendation']['amount_fen'],2000000)
  self.assertTrue(result['recommendation']['actionable']);self.assertEqual(len(result['funding']['requests']),2)
  oldrid=next(iter(old['funding']['requests']))
  self.assertEqual(result['funding']['retirements'][oldrid]['reason'],'superseded_current_gap')
  committed=with_cash(bundle,obj,result['funding'],broker(balance='130000.00',now=NOW),NOW)
  again=advice.refresh_friday_advice(committed,account,NOW)
  self.assertEqual(again['funding'],result['funding']);self.assertEqual(again['advice_id'],result['advice_id'])
 def test_same_friday_request_is_idempotent_and_never_renews_expiry(self):
  bundle,_=make_bundle();result=advice.refresh_friday_advice(bundle,broker(balance='120000.00')['account'],NOW)
  self.assertEqual(len(result['funding']['requests']),1)
  self.assertEqual(result['funding']['requests'],bundle['funding']['requests'])
 def test_fully_confirmed_first_id_consumes_entire_original_portfolio_batch(self):
  bundle,obj=make_bundle(two=True);ids=bundle['decision']['funding_admitted_ids'];self.assertEqual(len(ids),2)
  self.assertEqual(len(next(iter(bundle['funding']['requests'].values()))['admitted_entry_ids']),1)
  paid,snapshot,at=confirm(bundle,obj,amount='30000.00',equity='150000.00')
  later=at+timedelta(minutes=1);snapshot=broker(balance='120000.00',now=later)
  raw=json.loads(snapshot['account']['raw_payload']);raw['Deposit']='30000.00';snapshot['account']=envelope(raw)
  result=advice.refresh_friday_advice(paid,snapshot['account'],later)
  self.assertEqual(result['recommendation']['status'],'duplicate_admission');self.assertFalse(result['recommendation']['actionable'])
  self.assertEqual(len(result['funding']['requests']),1);self.assertEqual(result['funding']['confirmed_topup_fen'],3000000)
 def test_partial_confirmation_never_creates_or_increases_current_batch_offer(self):
  bundle,obj=make_bundle(two=True);partial,snap,at=confirm(bundle,obj)
  later=at+timedelta(minutes=1);snap=broker(balance='100000.00',now=later)
  raw=json.loads(snap['account']['raw_payload']);raw['Deposit']='10000.00';snap['account']=envelope(raw)
  result=advice.refresh_friday_advice(partial,snap['account'],later)
  self.assertFalse(result['recommendation']['actionable']);self.assertEqual(result['recommendation']['amount_fen'],0)
  self.assertEqual(len(result['funding']['requests']),1);self.assertEqual(result['original_offer_remaining_fen'],2000000)
 def test_equity_recovery_retires_old_offer_without_debt_or_fake_credit(self):
  bundle,_=make_bundle();result=advice.refresh_friday_advice(bundle,broker(balance='150000.00')['account'],NOW)
  self.assertFalse(result['recommendation']['actionable']);self.assertEqual(result['recommendation']['amount_fen'],0)
  self.assertEqual(next(iter(result['funding']['retirements'].values()))['reason'],'equity_recovered')
  self.assertEqual(result['funding']['reserve_remaining_fen'],15000000)
 def test_unknown_deposit_and_missing_close_day_are_blocked_without_any_cash_change(self):
  bundle,_=make_bundle(holiday=True);before=deepcopy(bundle)
  for delta in (dict(day='2026-10-30'),dict(day='2026-10-29',Deposit='1.00')):
   snap=broker(balance='120000.00',day=delta.pop('day'),now=NOW)
   raw=json.loads(snap['account']['raw_payload']);raw.update(delta);snap['account']=envelope(raw)
   result=advice.refresh_friday_advice(bundle,snap['account'],NOW)
   self.assertEqual(result['status'],'blocked');self.assertFalse(result['recommendation']['actionable'])
   self.assertEqual(result['recommendation']['amount_fen'],0);self.assertEqual(result['funding'],bundle['funding'])
  self.assertEqual(bundle,before)
 def test_validated_expired_offer_is_retired_and_never_renews_same_batch(self):
  initial,_=make_bundle();cash=deepcopy(initial['funding']);rid=next(iter(cash['requests']))
  # Conditional legacy expiry fixture. Rebuild actual runtime provenance from
  # this already-valid cash state; do not edit the committed decision snapshot.
  cash['requests'][rid]['expires_at']=(NOW+timedelta(seconds=10)).isoformat();funds.validate_state(cash)
  bundle,_=make_bundle(cash=cash);later=NOW+timedelta(seconds=11)
  result=advice.refresh_friday_advice(bundle,broker(balance='120000.00',now=later)['account'],later)
  self.assertEqual(result['status'],'ready',result)
  self.assertEqual(result['funding']['retirements'][rid]['reason'],'expired_superseded')
  self.assertEqual(result['recommendation']['status'],'duplicate_admission')
  self.assertEqual(len(result['funding']['requests']),1);self.assertFalse(result['recommendation']['actionable'])
 def test_missing_initial_cash_observation_and_old_week_source_are_blocked(self):
  bundle,_=make_bundle(holiday=True,cash=funds.initial_state(ACCOUNT,RELEASE,'2026-10-29'))
  result=advice.refresh_friday_advice(bundle,broker(day='2026-10-29',now=NOW)['account'],NOW)
  self.assertEqual(result['status'],'blocked');self.assertEqual(result['funding'],bundle['funding'])
  bundle,_=make_bundle();at=NOW+timedelta(days=7)
  result=advice.refresh_friday_advice(bundle,broker(now=at)['account'],at)
  self.assertEqual(result['status'],'blocked');self.assertEqual(result['funding'],bundle['funding'])
 def test_stale_wrong_source_invalid_admission_and_nonfriday_never_change_cash(self):
  bundle,_=make_bundle();before=deepcopy(bundle)
  cases=[]
  bad=deepcopy(bundle);bad['decision']['data_receipt_sha256']='0'*64;cases.append((bad,broker()['account'],NOW))
  bad=deepcopy(bundle);bad['decision']['funding_admitted_ids'].append('invented-native');cases.append((bad,broker()['account'],NOW))
  cases.append((bundle,broker(now=NOW-timedelta(minutes=6))['account'],NOW))
  cases.append((bundle,broker()['account'],NOW+timedelta(days=1)))
  for source,account,at in cases:
   result=advice.refresh_friday_advice(source,account,at)
   self.assertIn(result['status'],('blocked','not_friday'));self.assertFalse(result['recommendation']['actionable'])
   self.assertEqual(result['funding'],source['funding'])
  self.assertEqual(bundle,before)
if __name__=='__main__':unittest.main()
