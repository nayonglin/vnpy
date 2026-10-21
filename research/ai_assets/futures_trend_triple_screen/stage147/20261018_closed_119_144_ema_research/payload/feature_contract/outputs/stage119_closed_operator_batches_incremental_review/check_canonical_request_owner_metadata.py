from pathlib import Path
import hashlib,json
B=Path('/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen')
O=B/'outputs/stage119_closed_operator_batches_incremental_review'
v=json.loads((O/'verification.json').read_bytes());measured=v['measured_bindings'];owner_sha='ce61dcf3cbe0696cfbc12f1ebcf0f12436ee0dfb84662623e91fce36ec957efb'
def js(path):
 path=Path(path);raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==measured[str(path)]['sha256'];return json.loads(raw)
scope_sha=v['source_bindings'][str(B/'tools/stage087_off_data_scope.py')]['sha256']
provider_sha=v['source_bindings'][str(B/'tools/stage087_off_data_provider.py')]['sha256']
rows=[]
for d in v['deliveries']:
 q=js(d['request']['path']);payload={k:x for k,x in q.items()if k!='request_sha256'}
 canonical=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
 assert canonical==q['request_sha256']==d['request_sha256']
 packet=Path(d['receipt']['path']).parents[1]/'minute_packet'
 terminal=js(packet/'terminal_observed.json');parent=js(packet/'network_attempt1/parent_receipt.json');worker=js(packet/'network_attempt1/worker_receipt.json')
 assert terminal['owner_sha256']==parent['owner_sha256']==worker['owner_sha256']==owner_sha
 assert terminal['driver_source_sha256']==scope_sha and terminal['provider_source_sha256']==provider_sha
 assert parent['provider_attempts_max']==1
 for doc in [parent,worker]:
  assert doc['orders']==doc['cancels']==doc['broker_or_ctp_connections']==doc['financial_replays']==0
  assert doc['old_CSV_or_DB_written']is False
 rows.append({'request_sha256':canonical,'canonical_digest_confirmed':True,'parent_worker_terminal_owner_bound':True,'terminal_exact_source_pins_confirmed':True,'one_attempt_no_economic_action':True})
final=[]
for f in json.loads((O/'frozen_terminal_inputs.json').read_bytes())['terminals']:
 if not f.get('present_at_freeze'):continue
 raw=Path(f['path']).read_bytes();h=hashlib.sha256(raw).hexdigest();final.append({'batch_id':f['batch_id'],'initial_sha256':f['sha256'],'final_sha256':h,'unchanged':h==f['sha256']})
assert all(x['unchanged']for x in final)
report={'schema':'stage119_remaining_canonical_identity_metadata_checks_v1','deliveries_checked':len(rows),'checks':rows,'terminal_final_checks':final,'network_provider_financial_tests':0,'price_recalculation':False}
(O/'canonical_identity_metadata.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'deliveries_checked':len(rows),'canonical_digest_and_owner_source_checks_passed':True,'terminal_count':len(final),'terminals_changed':0,'network_provider_financial_tests':0},ensure_ascii=False))

