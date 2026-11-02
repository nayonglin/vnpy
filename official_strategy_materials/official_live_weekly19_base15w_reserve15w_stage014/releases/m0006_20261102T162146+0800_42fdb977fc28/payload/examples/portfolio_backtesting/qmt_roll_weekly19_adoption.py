"""Pure source-bound carry-in record, never operator-cost or production authority.

The owner verifies the private startup authorization and provider authority first.
This module independently checks raw packet hashes, cost arithmetic and metadata;
it does not connect, persist, submit or invent historical management state.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal,InvalidOperation
import hashlib,json,re
import qmt_roll_weekly19_funding as funds

class AdoptionError(ValueError):pass
SCOPE='all_current_positions_new_management_cohort'
DECISION_FIELDS={'schema','account_key','material_release_id','operator_decision_id','management_start_date','completed_day','adoption_scope','broker_account_raw_sha256','broker_positions_raw_sha256','raw_carry_in_positions_sha256','contract_metadata_raw_sha256'}
def _require(value,reason):
 if not value:raise AdoptionError('weekly19_carry_in_'+reason)
def _hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def _sha(value):_require(isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value),'sha256_required');return value
def _day(value):
 try:_require(isinstance(value,str) and date.fromisoformat(value).isoformat()==value,'date_required');return value
 except (ValueError,TypeError):raise AdoptionError('weekly19_carry_in_date_required') from None
def _decimal(value,*,positive=False):
 try:
  _require(not isinstance(value,bool),'numeric_bool_forbidden');v=Decimal(str(value));_require(v.is_finite() and (v>0 if positive else v>=0),'finite_positive_number_required');return v
 except (InvalidOperation,ValueError,TypeError):raise AdoptionError('weekly19_carry_in_finite_number_required') from None
def _text(v):return format(v.normalize(),'f')
def _integer(v):_require(type(v) is int and v>=0,'native_integer_required');return v

def build_carry_in_seed(*,operator_decision,broker_snapshot,raw_position_evidence,contract_metadata_evidence,metadata,now):
 """Validate source facts; quantities/costs are never taken from the operator.

 ``contract_metadata_evidence`` is the already fixed-reference capture envelope;
 its outer file reference is checked by the caller, not conferred by this seed.
 """
 d=deepcopy(operator_decision);_require(isinstance(d,dict) and set(d)==DECISION_FIELDS,'operator_decision_fields_invalid')
 _require(d['schema']=='weekly19.operator-carry-in-decision.v1' and d['adoption_scope']==SCOPE,'operator_decision_scope_invalid')
 for key in ('operator_decision_id','account_key','broker_account_raw_sha256','broker_positions_raw_sha256','raw_carry_in_positions_sha256','contract_metadata_raw_sha256'):_sha(d[key])
 _require(isinstance(d['material_release_id'],str) and bool(d['material_release_id']),'release_required')
 completed=_day(d['completed_day']);management=_day(d['management_start_date']);at=funds._time(now).astimezone(funds.SHANGHAI)
 _require(completed<=management<=at.date().isoformat(),'management_or_completed_day_in_future')
 identity=dict(account_key=d['account_key'],material_release_id=d['material_release_id'])
 account=funds._parse(broker_snapshot['account'],'weekly19.ctp-account.v1','ctp_account_callback');funds._broker(broker_snapshot['account'],identity,at)
 positions=funds._parse(broker_snapshot['positions'],'weekly19.ctp-positions.v1','ctp_position_query')
 carry=funds._parse(raw_position_evidence,'weekly19.ctp-carry-in-positions.v1','ctp_position_query')
 quoted=funds._parse(contract_metadata_evidence,'weekly19.contract-metadata.v1','tqsdk_quote_capture')
 orders=funds._parse(broker_snapshot['orders'],'weekly19.ctp-orders.v1','ctp_order_query')
 for raw in (positions,carry,orders):
  _require(all(raw.get(k)==account.get(k) for k in ('account_key','material_release_id','trading_day','generation_uuid')),'source_cohort_mismatch')
  age=(at-funds._time(raw['observed_at'])).total_seconds();_require(raw.get('query_complete') is True and 0<=age<=funds.MAX_SNAPSHOT_AGE_SECONDS,'query_stale_or_incomplete')
 _require(d['account_key']==account['account_key'] and d['material_release_id']==account['material_release_id'],'operator_account_or_release_mismatch')
 _require(management<=_day(account['trading_day']),'management_broker_trading_day_mismatch')
 _require(isinstance(orders.get('orders'),list) and all(isinstance(r,dict) and r.get('status') in {'filled','all_traded','cancelled','rejected'} for r in orders['orders']),'unresolved_broker_orders')
 for key,actual in [('broker_account_raw_sha256',broker_snapshot['account']['raw_sha256']),('broker_positions_raw_sha256',broker_snapshot['positions']['raw_sha256']),('raw_carry_in_positions_sha256',raw_position_evidence['raw_sha256']),('contract_metadata_raw_sha256',contract_metadata_evidence['raw_sha256'])]:_require(d[key]==actual,'operator_source_sha_mismatch')
 _require(carry.get('normalized_positions_sha256')==broker_snapshot['positions']['raw_sha256'],'normalized_position_binding_mismatch')
 capture=broker_snapshot.get('provenance',{}).get('raw_capture',{}).get('sha256');_sha(capture);_require(carry.get('raw_capture_sha256')==capture,'raw_capture_binding_mismatch')
 quote_age=(at-funds._time(quoted['observed_at'])).total_seconds();_require(0<=quote_age<=86400,'contract_metadata_stale_or_future')
 _require(isinstance(quoted.get('quotes'),list),'contract_metadata_quotes_required');quotes={}
 for q in quoted['quotes']:
  symbol=q.get('vt_symbol');_require(symbol not in quotes and symbol in metadata['vt_symbols'],'contract_metadata_symbol_invalid')
  code,exchange=symbol.split('.');_require(q.get('instrument_id')==exchange+'.'+code and q.get('ins_class')=='FUTURE','native_contract_identity_mismatch')
  size=_decimal(q['volume_multiple'],positive=True);tick=_decimal(q['price_tick'],positive=True)
  _require(size==size.to_integral_value() and size==_decimal(metadata['sizes'][symbol],positive=True) and tick==_decimal(metadata['priceticks'][symbol],positive=True),'contract_size_or_tick_mismatch')
  year=_integer(q['delivery_year']);month=_integer(q['delivery_month']);_require(1900<=year<=2200 and 1<=month<=12,'explicit_delivery_month_required')
  digits=re.search(r'(\d+)$',code);_require(digits is not None and len(digits.group()) in (3,4),'native_delivery_code_invalid')
  native=digits.group();_require(int(native[-2:])==month and int(native[:-2])==year%(10 if len(native)==3 else 100),'native_delivery_month_mismatch')
  _require(_decimal(q['expire_datetime'],positive=True)>Decimal(str(at.timestamp())),'contract_expired_or_expiry_missing')
  quotes[symbol]=dict(size=size,tick=tick,contract_yyyymm=f'{year:04d}{month:02d}')
 _require(isinstance(positions.get('positions'),list) and isinstance(carry.get('native_positions'),list),'positions_required')
 normalized={};products=set()
 for row in positions['positions']:
  symbol=row.get('vt_symbol');direction=row.get('direction');volume=row.get('volume')
  _require(symbol in metadata['vt_symbols'] and direction in ('long','short') and type(volume) is int and volume>0 and symbol not in normalized,'unsupported_or_hedged_normalized_position')
  product=metadata['source_symbol_by_contract'][symbol];_require(product in metadata['product_symbols'] and product not in products,'multiple_contracts_one_product_unsupported');products.add(product)
  normalized[symbol]=(direction,volume)
 aggregate={};native_keys=set()
 for row in carry['native_positions']:
  _require(isinstance(row,dict),'native_position_object_required');volume=_integer(row.get('Position'))
  if volume==0:continue
  _require(row.get('BrokerID')==account['BrokerID'] and row.get('InvestorID')==account['AccountID'],'native_position_account_mismatch')
  _require(str(row.get('TradingDay'))==account['trading_day'].replace('-',''),'native_position_trading_day_mismatch')
  direction={'2':'long','3':'short'}.get(str(row.get('PosiDirection')));_require(direction is not None,'unknown_native_position_direction')
  _require(str(row.get('PositionDate')) in {'1','2'},'unknown_native_position_date')
  # The existing gateway/sender route is Speculation1 only. Do not adopt a
  # hedge identity the actual close transport cannot preserve.
  _require(str(row.get('HedgeFlag'))=='1','unsupported_native_hedge_execution_route')
  symbol=str(row.get('InstrumentID'))+'.'+str(row.get('ExchangeID'));_require(symbol in normalized and symbol in quotes,'native_position_or_metadata_missing')
  key=(symbol,direction,str(row['PositionDate']),str(row['HedgeFlag']));_require(key not in native_keys,'duplicate_native_position_row');native_keys.add(key)
  cost=_decimal(row.get('OpenCost'),positive=True)
  if symbol not in aggregate:aggregate[symbol]=dict(direction=direction,volume=0,open_cost=Decimal(0))
  a=aggregate[symbol];_require(a['direction']==direction,'hedged_native_position_unsupported');a['volume']+=volume;a['open_cost']+=cost
 _require(set(aggregate)==set(normalized),'native_normalized_position_set_mismatch')
 rows=[]
 for symbol,a in sorted(aggregate.items()):
  _require((a['direction'],a['volume'])==normalized[symbol],'native_normalized_quantity_mismatch')
  q=quotes[symbol];price=a['open_cost']/(Decimal(a['volume'])*q['size']);_require(price>0 and price.is_finite(),'aggregate_cost_invalid')
  rows.append(dict(vt_symbol=symbol,product_vt_symbol=metadata['source_symbol_by_contract'][symbol],direction=a['direction'],volume=a['volume'],aggregate_open_cost=_text(a['open_cost']),aggregate_entry_price=_text(price),contract_size=int(q['size']),pricetick=_text(q['tick']),contract_yyyymm=q['contract_yyyymm']))
 body=dict(schema='weekly19.carry-in-seed.v1',account_key=d['account_key'],material_release_id=d['material_release_id'],management_start_date=management,completed_day=completed,operator_decision=deepcopy(d),positions=rows,raw_position_evidence=deepcopy(raw_position_evidence),contract_metadata_evidence=deepcopy(contract_metadata_evidence),source_bindings=dict(account_raw_sha256=broker_snapshot['account']['raw_sha256'],positions_raw_sha256=broker_snapshot['positions']['raw_sha256'],orders_raw_sha256=broker_snapshot['orders']['raw_sha256'],raw_capture_sha256=capture),historical_open_date=None,prior_stop=None,prior_extrema=None,verified_historical_strategy_pnl=False,authorization_semantics='sourcebound_record_not_operator_signature_or_production_authority',production_qualified=False)
 return dict(body,seed_sha256=_hash(body))

def validate_carry_in_seed(seed,*,broker_snapshot,metadata,now):
 _require(isinstance(seed,dict) and seed.get('seed_sha256')==_hash({k:v for k,v in seed.items() if k!='seed_sha256'}),'seed_checksum_invalid')
 rebuilt=build_carry_in_seed(operator_decision=seed['operator_decision'],broker_snapshot=broker_snapshot,raw_position_evidence=seed['raw_position_evidence'],contract_metadata_evidence=seed['contract_metadata_evidence'],metadata=metadata,now=now)
 _require(rebuilt==seed,'seed_source_or_metadata_changed');return rebuilt
