"""Private, explicit existing-account startup; no inferred historical ownership.

The immutable authorization limits the inventory scope. Fresh native broker
admission supplies every cash/cost value. Neither this file nor a user JSON
can grant production/source authority or authorize an order.
"""
from copy import deepcopy
import hashlib,json
import qmt_roll_weekly19_funding as funds
import qmt_roll_weekly19_broker_evidence as broker

MODE='operator_existing_account_v1'
class StartupError(ValueError):pass
def _require(ok,reason):
 if not ok:raise StartupError('weekly19_startup_'+reason)

def _reference(reference):
 _require(isinstance(reference,dict)and set(reference)=={'path','sha256'},'private_reference_invalid')
 funds._sha(reference['sha256'])
 raw=broker._safe_read(reference['path'],private=True)
 _require(hashlib.sha256(raw).hexdigest()==reference['sha256'],'private_reference_sha_mismatch')
 return broker._json(raw)

def load_startup_authorization(config):
 mode=config.get('initial_account_mode','exact_150k')
 _require(isinstance(mode,str)and mode in {'exact_150k',MODE},'mode_invalid')
 if mode=='exact_150k':
  _require('startup_authorization'not in config,'authorization_requires_explicit_mode')
  return None
 ref=config.get('startup_authorization');raw=_reference(ref)
 _require(isinstance(raw,dict)and set(raw)=={'schema','account_key','material_release_id','cold_start_date','completed_day',
  'adoption_scope','authorized_positions','contract_metadata','operator_authorization'},'authorization_fields_invalid')
 _require(raw['schema']=='weekly19.operator-existing-account.v1','authorization_schema_invalid')
 _require(raw['account_key']==config['account_key']and raw['material_release_id']==config['material_release_id']
  and raw['cold_start_date']==config['cold_start_date'],'authorization_identity_mismatch')
 funds._day(raw['cold_start_date']);funds._day(raw['completed_day'])
 _require(raw['completed_day']<raw['cold_start_date'],'completed_day_must_precede_management_start')
 _require(raw['adoption_scope']=='all_current_positions_new_management_cohort','scope_invalid')
 _require(isinstance(raw['operator_authorization'],dict)and set(raw['operator_authorization'])=={'source_kind','statement'}
  and raw['operator_authorization']['source_kind']=='explicit_user_message'
  and isinstance(raw['operator_authorization']['statement'],str)and bool(raw['operator_authorization']['statement'].strip()),'operator_authorization_required')
 positions=raw['authorized_positions'];_require(isinstance(positions,list),'authorized_positions_list_required')
 seen=set()
 for row in positions:
  _require(isinstance(row,dict)and set(row)=={'vt_symbol','direction','volume'},'authorized_position_fields_invalid')
  _require(isinstance(row['vt_symbol'],str)and row['direction']in {'long','short'}
   and type(row['volume'])is int and row['volume']>0 and row['vt_symbol']not in seen,'authorized_position_invalid')
  seen.add(row['vt_symbol'])
 packet=_reference(raw['contract_metadata'])
 _require(isinstance(packet,dict)and set(packet)=={'schema','envelope','producer_source_sha256','order_api_calls'}
  and packet['schema']=='Stage024.contract-metadata-capture.v1'and type(packet['order_api_calls'])is int
  and packet['order_api_calls']==0,'metadata_capture_invalid')
 funds._sha(packet['producer_source_sha256'])
 # The source-bound pure adoption builder validates the actual quote envelope.
 return dict(authorization=deepcopy(raw),operator_decision_id=ref['sha256'],contract_metadata_evidence=packet['envelope'])

def assert_startup_snapshot(policy,snapshot,*,account_key,material_release_id,now):
 broker.read_account_snapshot(snapshot['account'],expected_account_key=account_key,material_release_id=material_release_id,now=now)
 account=funds._parse(snapshot['account'],'weekly19.ctp-account.v1','ctp_account_callback')
 parsed={}
 for kind,source in [('positions','ctp_position_query'),('orders','ctp_order_query')]:
  raw=funds._parse(snapshot[kind],'weekly19.ctp-'+kind+'.v1',source)
  _require(all(raw.get(key)==account.get(key)and account.get(key)is not None for key in
   ('account_key','material_release_id','trading_day','generation_uuid','execution_profile')),'query_identity_mismatch')
  _require(raw.get('query_complete')is True and raw.get('query_last_seen')is True
   and type(raw.get('query_error_rows'))is int and raw['query_error_rows']==0
   and type(raw.get('query_reqid'))is int and raw['query_reqid']>0,'query_incomplete')
  _require(0<=(funds._time(now)-funds._time(raw.get('observed_at'))).total_seconds()<=300,'query_stale_or_future')
  _require(isinstance(raw.get(kind),list),'query_rows_invalid');parsed[kind]=raw[kind]
 rows=parsed['positions'];orders=parsed['orders']
 _require(all(isinstance(row,dict)and set(row)=={'vt_symbol','direction','volume'}
  and isinstance(row['vt_symbol'],str)and row['direction']in {'long','short'}
  and type(row['volume'])is int and row['volume']>0 for row in rows),'position_lots_or_shape_invalid')
 _require(not any(row['status']not in {'filled','all_traded','cancelled','rejected'}for row in orders),'working_orders_require_resolution')
 def ordered(values):return sorted(values,key=lambda row:(row['vt_symbol'],row['direction']))
 _require(ordered(rows)==ordered(policy['authorization']['authorized_positions']),'inventory_changed_since_operator_authorization')

def build_initial_carry_in_seed(policy,data,raw_positions,now):
 from qmt_roll_weekly19_adoption import build_carry_in_seed
 snapshot=data['broker_snapshot'];authorization=policy['authorization']
 assert_startup_snapshot(policy,snapshot,account_key=authorization['account_key'],material_release_id=authorization['material_release_id'],now=now)
 _require(data['receipt']['trading_date']==authorization['completed_day'],'completed_market_mismatch')
 decision=dict(schema='weekly19.operator-carry-in-decision.v1',account_key=authorization['account_key'],
  material_release_id=authorization['material_release_id'],operator_decision_id=policy['operator_decision_id'],
  management_start_date=authorization['cold_start_date'],completed_day=authorization['completed_day'],
  adoption_scope=authorization['adoption_scope'],broker_account_raw_sha256=snapshot['account']['raw_sha256'],
  broker_positions_raw_sha256=snapshot['positions']['raw_sha256'],raw_carry_in_positions_sha256=raw_positions['raw_sha256'],
  contract_metadata_raw_sha256=policy['contract_metadata_evidence']['raw_sha256'])
 return build_carry_in_seed(operator_decision=decision,broker_snapshot=snapshot,raw_position_evidence=raw_positions,
  contract_metadata_evidence=policy['contract_metadata_evidence'],metadata=data['metadata'],now=now)
