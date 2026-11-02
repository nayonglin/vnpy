"""Private startup-policy boundary fixtures; no source authority or broker I/O."""
import copy,hashlib,json,os,sys,tempfile,unittest
from datetime import timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import qmt_roll_weekly19_startup as startup
from test_weekly19_external_funding import ACCOUNT,RELEASE,NOW,broker,envelope
AT=NOW.replace(month=11,day=2,hour=9,minute=1)
DAY='2026-11-02';GEN='synthetic-startup-generation';PROFILE='weekly19-15w-r150k'
POSITION=dict(vt_symbol='rb2701.SHFE',direction='long',volume=3)

def snapshot():
 common=dict(execution_profile=PROFILE,account_key=ACCOUNT,material_release_id=RELEASE,trading_day=DAY,observed_at=AT.isoformat(),generation_uuid=GEN,query_complete=True,query_last_seen=True,query_error_rows=0)
 return dict(account=broker(balance='167890.12',deposit='150000.00',at=AT,day=DAY,generation_uuid=GEN,execution_profile=PROFILE,
  Available='123456.00',CurrMargin='44434.12',PositionProfit='0.00',query_last_seen=True,query_error_rows=0),
  positions=envelope(dict(common,schema='weekly19.ctp-positions.v1',source_kind='ctp_position_query',query_reqid=8,positions=[copy.deepcopy(POSITION)])),
  orders=envelope(dict(common,schema='weekly19.ctp-orders.v1',source_kind='ctp_order_query',query_reqid=9,orders=[])))

def changed(packet,**updates):
 raw=json.loads(packet['raw_payload']);raw.update(updates);return envelope(raw)

class StartupPolicyTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.temp.cleanup);self.parent=Path(self.temp.name).resolve();self.parent.chmod(0o700)
  self.metadata=self.write('contracts.json',dict(schema='Stage024.contract-metadata-capture.v1',
   envelope=envelope(dict(schema='synthetic.contract-metadata.v1',production_qualified=False)),producer_source_sha256='a'*64,order_api_calls=0))
  self.authorization=dict(schema='weekly19.operator-existing-account.v1',account_key=ACCOUNT,material_release_id=RELEASE,cold_start_date=DAY,
   completed_day='2026-10-30',adoption_scope='all_current_positions_new_management_cohort',authorized_positions=[copy.deepcopy(POSITION)],
   contract_metadata=self.metadata,operator_authorization=dict(source_kind='explicit_user_message',statement='Synthetic operator decision; no real broker action.'))
  self.config=dict(initial_account_mode=startup.MODE,account_key=ACCOUNT,material_release_id=RELEASE,cold_start_date=DAY,startup_authorization=self.write('authorization.json',self.authorization))
 def write(self,name,obj):
  path=self.parent/name;payload=json.dumps(obj,sort_keys=True,separators=(',',':')).encode();path.write_bytes(payload);path.chmod(0o600)
  return dict(path=str(path),sha256=hashlib.sha256(payload).hexdigest())
 def load(self,authorization=None,**changes):
  cfg=copy.deepcopy(self.config)
  if authorization is not None:cfg['startup_authorization']=self.write('changed-authorization.json',authorization)
  cfg.update(changes);return startup.load_startup_authorization(cfg)
 def assert_snapshot(self,policy=None,data=None,**kw):
  args=dict(account_key=ACCOUNT,material_release_id=RELEASE,now=AT);args.update(kw)
  return startup.assert_startup_snapshot(policy or self.load(),data or snapshot(),**args)
 def test_default_exact_mode_is_none_and_cannot_hide_an_authorization_reference(self):
  self.assertIsNone(startup.load_startup_authorization({}));self.assertIsNone(startup.load_startup_authorization({'initial_account_mode':'exact_150k'}))
  with self.assertRaises(ValueError):self.load(initial_account_mode='exact_150k')
 def test_explicit_policy_is_digest_bound_and_does_not_claim_source_or_production_authority(self):
  before=copy.deepcopy(self.config);policy=self.load();self.assertEqual(self.config,before)
  self.assertEqual(policy['operator_decision_id'],self.config['startup_authorization']['sha256']);self.assertEqual(policy['authorization'],self.authorization)
  self.assertNotIn('source_qualified',policy);self.assertNotIn('production_qualified',policy)
  self.assertIsNone(self.assert_snapshot(policy))
 def test_cross_account_release_and_cold_start_authorizations_are_rejected(self):
  for change in (dict(account_key='b'*64),dict(material_release_id='other-release'),dict(cold_start_date='2026-11-03')):
   with self.subTest(change=change),self.assertRaises(ValueError):self.load(**change)
 def test_invalid_mode_and_nonhistorical_completed_day_are_rejected(self):
  for mode in ('unsupported',None,[],True):
   with self.subTest(mode=mode),self.assertRaises(ValueError):self.load(initial_account_mode=mode)
  for day in (DAY,'2026-11-03','not-a-day'):
   auth=dict(self.authorization,completed_day=day)
   with self.subTest(day=day),self.assertRaises(ValueError):self.load(auth)
 def test_changed_private_bytes_and_both_reference_digests_are_rejected(self):
  ref=dict(self.config['startup_authorization'],sha256='f'*64)
  with self.assertRaises(ValueError):self.load(startup_authorization=ref)
  auth=copy.deepcopy(self.authorization);auth['contract_metadata']['sha256']='f'*64
  with self.assertRaises(ValueError):self.load(auth)
  Path(self.config['startup_authorization']['path']).write_bytes(b'{}')
  with self.assertRaises(ValueError):self.load()
 def test_private_policy_and_nested_metadata_require_owner_only_regular_paths(self):
  for which in ('authorization','metadata'):
   ref=self.config['startup_authorization']if which=='authorization'else self.metadata;p=Path(ref['path']);p.chmod(0o644)
   try:
    with self.subTest(which=which),self.assertRaises(ValueError):self.load()
   finally:p.chmod(0o600)
  self.parent.chmod(0o755)
  try:
   with self.assertRaises(ValueError):self.load()
  finally:self.parent.chmod(0o700)
 def test_relative_symlink_and_hardlink_references_are_rejected(self):
  original=Path(self.config['startup_authorization']['path'])
  linked=self.parent/'linked.json';linked.symlink_to(original)
  with self.assertRaises(ValueError):self.load(startup_authorization=dict(self.config['startup_authorization'],path=str(linked)))
  with self.assertRaises(ValueError):self.load(startup_authorization=dict(self.config['startup_authorization'],path='authorization.json'))
  hard=self.parent/'hard.json';os.link(original,hard)
  with self.assertRaises(ValueError):self.load()
 def test_authorization_cannot_expand_inventory_or_forge_operator_and_metadata_packet(self):
  variants=[]
  for row in (dict(POSITION,volume=True),dict(POSITION,volume=0),dict(POSITION,direction='net')):
   variants.append(dict(self.authorization,authorized_positions=[row]))
  variants.append(dict(self.authorization,authorized_positions=[POSITION,POSITION]))
  variants.append(dict(self.authorization,adoption_scope='any_future_position'))
  variants.append(dict(self.authorization,operator_authorization=dict(source_kind='broker_automatic',statement='not operator')))
  for auth in variants:
   with self.subTest(auth=auth),self.assertRaises(ValueError):self.load(auth)
  packet=dict(schema='Stage024.contract-metadata-capture.v1',envelope={},producer_source_sha256='a'*64,order_api_calls=1)
  auth=dict(self.authorization,contract_metadata=self.write('bad-metadata.json',packet))
  with self.assertRaises(ValueError):self.load(auth)
 def test_changed_quantity_direction_unknown_inventory_and_duplicates_are_rejected(self):
  for rows in ([dict(POSITION,volume=4)],[dict(POSITION,direction='short')],[],[POSITION,dict(POSITION,vt_symbol='ag2701.SHFE')],[POSITION,POSITION]):
   data=snapshot();data['positions']=changed(data['positions'],positions=rows)
   with self.subTest(rows=rows),self.assertRaises(ValueError):self.assert_snapshot(data=data)
 def test_snapshot_quantity_must_be_integer_lots_not_bool_or_float_equality(self):
  auth=copy.deepcopy(self.authorization);auth['authorized_positions'][0]['volume']=1;policy=self.load(auth)
  for volume in (True,1.0):
   data=snapshot();data['positions']=changed(data['positions'],positions=[dict(POSITION,volume=volume)])
   with self.subTest(volume=volume),self.assertRaises(ValueError):self.assert_snapshot(policy=policy,data=data)
 def test_working_and_unknown_orders_block_but_terminal_orders_do_not_authorize_send(self):
  for status in ('accepted','working','pending','partially_filled','unknown'):
   data=snapshot();data['orders']=changed(data['orders'],orders=[dict(broker_order_id='synthetic-order',status=status)])
   with self.subTest(status=status),self.assertRaises(ValueError):self.assert_snapshot(data=data)
  for status in ('filled','all_traded','cancelled','rejected'):
   data=snapshot();data['orders']=changed(data['orders'],orders=[dict(broker_order_id='synthetic-order',status=status)])
   with self.subTest(status=status):self.assertIsNone(self.assert_snapshot(data=data))
 def test_stale_future_and_foreign_account_snapshot_are_rejected(self):
  for update in (dict(observed_at=(AT-timedelta(seconds=301)).isoformat()),dict(observed_at=(AT+timedelta(seconds=1)).isoformat()),dict(account_key='b'*64),dict(material_release_id='foreign')):
   data=snapshot();data['account']=changed(data['account'],**update)
   with self.subTest(update=update),self.assertRaises(ValueError):self.assert_snapshot(data=data)
 def test_positions_and_orders_must_share_account_release_and_current_query_generation(self):
  for kind in ('positions','orders'):
   for update in (dict(account_key='b'*64),dict(material_release_id='other-release'),dict(trading_day='2026-10-30'),dict(generation_uuid='previous-generation')):
    data=snapshot();data[kind]=changed(data[kind],**update)
    with self.subTest(kind=kind,update=update),self.assertRaises(ValueError):self.assert_snapshot(data=data)
 def test_positions_and_orders_must_be_complete_fresh_native_queries(self):
  for kind in ('positions','orders'):
   for update in (dict(query_complete=False),dict(query_last_seen=False),dict(query_error_rows=1),dict(observed_at=(AT-timedelta(seconds=301)).isoformat()),dict(observed_at=(AT+timedelta(seconds=1)).isoformat())):
    data=snapshot();data[kind]=changed(data[kind],**update)
    with self.subTest(kind=kind,update=update),self.assertRaises(ValueError):self.assert_snapshot(data=data)
