"""Synthetic carry-in sources only; no real account, CTP, mail or qualification."""
import copy,json,hashlib,inspect,sys,unittest
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
from tests.test_weekly19_runtime import fixture,broker,envelope,ACCOUNT,RELEASE,SYMBOL
import qmt_roll_weekly19_runtime as runtime
import qmt_roll_weekly19_funding as funds
try:import qmt_roll_weekly19_adoption as adoption
except ModuleNotFoundError:adoption=None
NOW=datetime(2026,11,2,9,5,tzinfo=ZoneInfo('Asia/Shanghai'));DECISION='d'*64

def sources():
 calendar,frame,bars,meta=fixture();frame['contract_epoch_id']='SHFE.RB.202612';frame['contract_yyyymm']='202612'
 snapshot=broker(balance='170000.00',available='160000.00',positions=[dict(vt_symbol=SYMBOL,direction='long',volume=2)],now=NOW,day='2026-11-02')
 account_raw=json.loads(snapshot['account']['raw_payload']);account_raw.update(query_last_seen=True,query_error_rows=0,CurrMargin='10000.00',PositionProfit='0.00');snapshot['account']=envelope(account_raw)
 common=dict(account_key=ACCOUNT,material_release_id=RELEASE,observed_at=NOW.isoformat(),trading_day='2026-11-02',generation_uuid='fixture-query',query_reqid=2,query_complete=True)
 snapshot['orders']=envelope(dict(common,schema='weekly19.ctp-orders.v1',source_kind='ctp_order_query',orders=[]));snapshot['provenance']=dict(raw_capture=dict(sha256='a'*64))
 native=[dict(BrokerID='9999',InvestorID='fixture-account',TradingDay='20261102',InstrumentID='rb2612',ExchangeID='SHFE',PosiDirection='2',HedgeFlag='1',PositionDate=str(i+1),Position=1,OpenCost=v,PositionCost=999999.) for i,v in enumerate([1000.,970.])]
 raw=envelope(dict(common,schema='weekly19.ctp-carry-in-positions.v1',source_kind='ctp_position_query',native_positions=native,normalized_positions_sha256=snapshot['positions']['raw_sha256'],raw_capture_sha256='a'*64))
 quoted=envelope(dict(schema='weekly19.contract-metadata.v1',source_kind='tqsdk_quote_capture',observed_at=(NOW-timedelta(minutes=20)).isoformat(),quotes=[dict(vt_symbol=SYMBOL,instrument_id='SHFE.rb2612',ins_class='FUTURE',volume_multiple=10.,price_tick=1.,expire_datetime=datetime(2026,12,31,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp(),delivery_year=2026,delivery_month=12)]))
 decision=dict(schema='weekly19.operator-carry-in-decision.v1',account_key=ACCOUNT,material_release_id=RELEASE,operator_decision_id=DECISION,management_start_date='2026-11-02',completed_day='2026-10-30',adoption_scope='all_current_positions_new_management_cohort',broker_account_raw_sha256=snapshot['account']['raw_sha256'],broker_positions_raw_sha256=snapshot['positions']['raw_sha256'],raw_carry_in_positions_sha256=raw['raw_sha256'],contract_metadata_raw_sha256=quoted['raw_sha256'])
 cash=funds.begin_cash_observation(funds.initial_state(ACCOUNT,RELEASE,'2026-11-02'),snapshot['account'],NOW,opening_equity_mode='operator_existing_account_v1',operator_decision_id=DECISION)
 return calendar,frame,bars,meta,snapshot,raw,quoted,decision,cash

class AdoptionTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(adoption,'pure carry-in source validator missing')
 def seed(self,values):
  c,f,b,m,s,r,q,d,cash=values
  return adoption.build_carry_in_seed(operator_decision=d,broker_snapshot=s,raw_position_evidence=r,contract_metadata_evidence=q,metadata=m,now=NOW)
 def bootstrap(self,values,seed=None,batches=None):
  c,f,b,m,s,r,q,d,cash=values
  return runtime.bootstrap_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,m,c,f,s,cash,carry_in_seed=self.seed(values) if seed is None else seed,warmup_batches=[b[day] for day in sorted(b)] if batches is None else batches,clock=lambda:NOW)
 def test_raw_open_cost_is_only_price_source_not_position_cost_or_operator_price(self):
  v=sources();seed=self.seed(v);row=seed['positions'][0]
  self.assertEqual((row['volume'],row['aggregate_open_cost'],row['aggregate_entry_price']),(2,'1970','98.5'))
  self.assertFalse(seed['production_qualified']);self.assertEqual(seed['historical_open_date'],None)
  v[7]['entry_price']=1.
  with self.assertRaises(ValueError):self.seed(v)
 def test_source_sha_quantity_and_native_direction_cannot_be_forged(self):
  for mutation in ['sha','quantity','direction','cost','capture']:
   v=sources();raw=json.loads(v[5]['raw_payload'])
   if mutation=='sha':v[5]['raw_sha256']='0'*64
   elif mutation=='capture':raw['raw_capture_sha256']='f'*64
   elif mutation=='quantity':raw['native_positions'][0]['Position']=2
   elif mutation=='direction':raw['native_positions'][0]['PosiDirection']='1'
   else:raw['native_positions'][0]['OpenCost']=0
   if mutation!='sha':v[5].update(envelope(raw));v[7]['raw_carry_in_positions_sha256']=v[5]['raw_sha256']
   with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.seed(v)
 def test_real_metadata_size_tick_and_native_instrument_are_bound(self):
  for key,value in [('volume_multiple',11.),('price_tick',2.),('instrument_id','SHFE.rb2712'),('ins_class','FUTURE_OPTION')]:
   v=sources();raw=json.loads(v[6]['raw_payload']);raw['quotes'][0][key]=value;v[6].update(envelope(raw));v[7]['contract_metadata_raw_sha256']=v[6]['raw_sha256']
   with self.subTest(key=key),self.assertRaises(ValueError):self.seed(v)
 def test_nonterminal_orders_and_stale_position_cohort_reject_before_bootstrap(self):
  v=sources();raw=json.loads(v[4]['orders']['raw_payload']);raw['orders']=[dict(status='working')];v[4]['orders']=envelope(raw)
  with self.assertRaises(ValueError):self.seed(v)
  v=sources();raw=json.loads(v[5]['raw_payload']);raw['generation_uuid']='foreign';v[5].update(envelope(raw));v[7]['raw_carry_in_positions_sha256']=v[5]['raw_sha256']
  with self.assertRaises(ValueError):self.seed(v)
 def test_bootstrap_actual_nonflat_source_creates_complete_real_layers_without_intents(self):
  v=sources();actor=self.bootstrap(v);state=actor.strategy.states['rb.SHFE'];layer=state.layers[0]
  self.assertEqual((actor.strategy.get_pos(SYMBOL),actor.strategy.get_target(SYMBOL),state.active_volume()),(2,2,2))
  self.assertEqual(layer.entry_price,98.5);self.assertTrue(layer.entry_price_synced);self.assertEqual(layer.kind,'base')
  self.assertEqual((state.entry_date,layer.entry_date),('2026-11-02','2026-11-02'));self.assertEqual(state.bars_since_entry,0)
  self.assertEqual((layer.highest_price,layer.lowest_price,layer.max_profit_pct),(101.,101.,0.))
  self.assertLess(layer.stop_price,101.);self.assertGreater(layer.stop_price,0.)
  self.assertEqual(actor.broker_equity,170000.);self.assertEqual(actor.strategy.settled_balance,170000.)
  self.assertEqual(actor.engine.intents,[]);self.assertEqual(actor.fills,{});self.assertEqual(actor.days,{})
  self.assertEqual(actor.warmup_cursor,'2026-10-30');self.assertEqual(actor.last_processed_day,'')
  self.assertEqual(actor.export_state()['input_cursor'],'2026-10-30');self.assertIn(SYMBOL,actor.position_identities)
  self.assertIsNone(actor.carry_in_receipt['historical_open_date']);self.assertIsNone(actor.carry_in_receipt['prior_extrema'])
 def test_bootstrap_is_deterministic_and_durable_restore_does_not_recreate_layer(self):
  v=sources();seed=self.seed(v);a=self.bootstrap(v,seed);b=self.bootstrap(v,seed);saved=a.export_state();self.assertEqual(saved,b.export_state())
  c,f,bars,m,s,r,q,d,cash=v;restored=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,m,c,f,s,saved,cash,clock=lambda:NOW)
  self.assertEqual(restored.export_state(),saved);self.assertEqual(len(restored.strategy.states['rb.SHFE'].layers),1)
  changed=copy.deepcopy(s);raw=json.loads(changed['positions']['raw_payload']);raw['positions'][0]['volume']=3;changed['positions']=envelope(raw)
  with self.assertRaises(runtime.RuntimeContractError):restored.reconcile_broker_snapshot(changed,cash)
 def test_normal_constructor_still_rejects_unknown_nonzero_positions(self):
  c,f,b,m,s,r,q,d,cash=sources()
  with self.assertRaisesRegex(runtime.RuntimeContractError,'unprotected_broker_position'):
   runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,m,c,f,s,None,cash,clock=lambda:NOW)
 def test_seed_hash_opening_operator_identity_and_incomplete_week_fail_closed(self):
  v=sources();seed=self.seed(v);seed['positions'][0]['aggregate_entry_price']='1'
  with self.assertRaises(ValueError):self.bootstrap(v,seed)
  v=sources();v[8]['opening_equity']['operator_decision_id']='e'*64
  with self.assertRaises(ValueError):self.bootstrap(v)
  v=sources();batches=[v[2][day] for day in sorted(v[2]) if day!='2026-10-28']
  with self.assertRaises(ValueError):self.bootstrap(v,batches=batches)
 def test_reconcile_cannot_drop_immutable_opening_equity_or_double_count_carry_pnl(self):
  v=sources();a=self.bootstrap(v);before=a.export_state();cash=copy.deepcopy(v[8]);cash.pop('opening_equity')
  with self.assertRaises(funds.FundingError):a.reconcile_broker_snapshot(v[4],cash)
  self.assertEqual(a.export_state(),before);self.assertEqual(a.broker_equity,170000.)
 def test_known_cutover_equity_initializes_new_peak_and_estimate_baselines(self):
  a=self.bootstrap(sources())
  self.assertEqual(a.strategy.portfolio_equity_high_water,170000.)
  self.assertEqual(a.strategy.portfolio_volatility_budget_last_equity,170000.)
  self.assertEqual(a.strategy.portfolio_overheat_cooldown_equity_history,[])
  self.assertEqual(a.strategy.portfolio_volatility_budget_return_history,[])
  a.strategy.estimated_equity=150000.;a.strategy._refresh_portfolio_drawdown_state()
  self.assertAlmostEqual(a.strategy.portfolio_drawdown_pct,20000/170000)
  self.assertGreater(a.strategy.portfolio_drawdown_pct,a.strategy.risk_cluster_heat_gate_drawdown_start_pct)
 def test_only_speculation_positions_have_an_existing_native_execution_route(self):
  for flag in ['2','3','5','6','7','9']:
   v=sources();raw=json.loads(v[5]['raw_payload'])
   for row in raw['native_positions']:row['HedgeFlag']=flag
   v[5].update(envelope(raw));v[7]['raw_carry_in_positions_sha256']=v[5]['raw_sha256']
   with self.subTest(flag=flag),self.assertRaises(ValueError):self.seed(v)
 def test_night_native_next_trading_day_and_terminal_alias_preserve_wall_management_date(self):
  v=sources();night=NOW.replace(hour=21)
  for key in ['account','positions','orders']:
   raw=json.loads(v[4][key]['raw_payload']);raw.update(trading_day='2026-11-03',observed_at=night.isoformat())
   if key=='orders':raw['orders']=[dict(status='all_traded')]
   v[4][key]=envelope(raw)
  raw=json.loads(v[5]['raw_payload']);raw.update(trading_day='2026-11-03',observed_at=night.isoformat(),normalized_positions_sha256=v[4]['positions']['raw_sha256'])
  for row in raw['native_positions']:row['TradingDay']='20261103'
  v[5].update(envelope(raw));v[7].update(broker_account_raw_sha256=v[4]['account']['raw_sha256'],broker_positions_raw_sha256=v[4]['positions']['raw_sha256'],raw_carry_in_positions_sha256=v[5]['raw_sha256'])
  seed=adoption.build_carry_in_seed(operator_decision=v[7],broker_snapshot=v[4],raw_position_evidence=v[5],contract_metadata_evidence=v[6],metadata=v[3],now=night)
  cash=funds.begin_cash_observation(funds.initial_state(ACCOUNT,RELEASE,'2026-11-02'),v[4]['account'],night,opening_equity_mode='operator_existing_account_v1',operator_decision_id=DECISION)
  actor=runtime.bootstrap_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,v[3],v[0],v[1],v[4],cash,carry_in_seed=seed,warmup_batches=[v[2][d] for d in sorted(v[2])],clock=lambda:night)
  self.assertEqual(actor.strategy.states['rb.SHFE'].entry_date,'2026-11-02');self.assertEqual(actor.broker_snapshot,v[4])
  v[7]['management_start_date']='2026-11-03'
  with self.assertRaises(ValueError):adoption.build_carry_in_seed(operator_decision=v[7],broker_snapshot=v[4],raw_position_evidence=v[5],contract_metadata_evidence=v[6],metadata=v[3],now=night)
 def test_short_carry_uses_original_weekly_stop_and_actual_aggregate_cost(self):
  v=sources();raw=json.loads(v[4]['positions']['raw_payload']);raw['positions'][0]['direction']='short';v[4]['positions']=envelope(raw)
  native=json.loads(v[5]['raw_payload']);native['normalized_positions_sha256']=v[4]['positions']['raw_sha256']
  for row in native['native_positions']:row['PosiDirection']='3'
  v[5].update(envelope(native));v[7].update(broker_positions_raw_sha256=v[4]['positions']['raw_sha256'],raw_carry_in_positions_sha256=v[5]['raw_sha256'])
  a=self.bootstrap(v);layer=a.strategy.states['rb.SHFE'].layers[0]
  self.assertEqual(a.strategy.get_pos(SYMBOL),-2);self.assertEqual(layer.entry_price,98.5);self.assertGreater(layer.stop_price,101.)
  self.assertEqual(layer.max_profit_pct,0.);self.assertEqual(a.broker_equity,170000.);self.assertEqual(a.engine.intents,[])
 def test_cutover_must_use_latest_prior_session_and_real_forward_calendar(self):
  v=sources();v[7]['completed_day']='2026-10-23'
  with self.assertRaises(ValueError):self.bootstrap(v,batches=[v[2][d] for d in sorted(v[2]) if d<='2026-10-23'])
  v=list(sources());v[0]=[d for d in v[0] if d<='2026-11-02']
  with self.assertRaises(ValueError):self.bootstrap(v)
 def test_first_bootstrap_cannot_mix_same_operator_with_another_account_baseline(self):
  v=sources();raw=json.loads(v[4]['account']['raw_payload']);raw['observed_at']=(NOW-timedelta(seconds=1)).isoformat()
  other=funds.begin_cash_observation(funds.initial_state(ACCOUNT,RELEASE,'2026-11-02'),envelope(raw),NOW,opening_equity_mode='operator_existing_account_v1',operator_decision_id=DECISION)
  v[8].clear();v[8].update(other)
  with self.assertRaises(ValueError):self.bootstrap(v)
 def test_restore_keeps_initial_reference_but_accepts_current_real_equity_change(self):
  v=sources();a=self.bootstrap(v);saved=a.export_state();fresh=copy.deepcopy(v[4]);raw=json.loads(fresh['account']['raw_payload']);raw['Balance']='169000.00';fresh['account']=envelope(raw)
  restored=runtime.build_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,v[3],v[0],v[1],fresh,saved,v[8],clock=lambda:NOW)
  self.assertEqual(restored.broker_equity,169000.);self.assertEqual(restored.strategy.portfolio_equity_high_water,170000.)
  self.assertEqual(restored.confirmed_cash_state['opening_equity'],v[8]['opening_equity']);self.assertEqual(restored.strategy.states['rb.SHFE'].layers[0].entry_price,98.5)

if __name__=='__main__':unittest.main()
