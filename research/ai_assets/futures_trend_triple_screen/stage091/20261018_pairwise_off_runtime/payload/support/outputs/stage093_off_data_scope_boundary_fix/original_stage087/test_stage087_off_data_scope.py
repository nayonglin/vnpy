"""Three finite owner/qualification/lifecycle contracts; no network or account run."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
OUT = TOOLS.parent / 'outputs/stage087_off_data_scope_implementation'
OUT.mkdir(parents=True, exist_ok=True)
import stage022_run_c0_qualified_wait as runtime
saved_output = runtime.OUTPUT
try:
    runtime.OUTPUT = OUT
    runtime.configure_runtime(Path(tempfile.mkdtemp(prefix='runtime_', dir=OUT)))
finally:
    runtime.OUTPUT = saved_output
import pandas as pd
import stage002_local_minute_overlay as old
import stage021_blocking_data_gate as gate

try:
    scope = importlib.import_module('stage087_off_data_scope')
    provider = importlib.import_module('stage087_off_data_provider')
except ModuleNotFoundError as error:
    if error.name not in {'stage087_off_data_scope', 'stage087_off_data_provider'}:
        raise
    scope = provider = None


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


class ScopeContracts(unittest.TestCase):
    def fixture(self, folder, arm='A_OFF'):
        account = folder / 'accounts' / arm
        account.mkdir(parents=True, exist_ok=True)
        runner = folder / 'runner.py';runner.write_text('# finite fixture runner\n')
        preflight = dict(source_bindings={str(runner): dict(sha256=sha(runner), bytes=runner.stat().st_size)})
        write(account / 'preflight_used.json', preflight)
        write(account / 'run_context.json', dict(arm=arm, attempt=1, run_id='finite_'+arm,
            output_directory=str(account), writer='stage065_account_checkpoint.py',
            source_bindings=preflight['source_bindings']))
        write(account / 'readiness.json', dict(schema='fixture_only_not_financial_readiness'))
        now = datetime.now(timezone.utc).isoformat()
        sources = {str(TOOLS/name): sha(TOOLS/name) for name in
            ['stage087_off_data_scope.py', 'stage087_off_data_provider.py', 'stage021_blocking_data_gate.py',
             'stage022_run_c0_qualified_wait.py']}
        document = dict(schema='stage087_off_owner_v1', arm=arm, attempt=1, run_id='finite_'+arm,
            account_output=str(account), wait_root=str(account/'data_wait'), runner_path=str(runner), runner_sha256=sha(runner),
            engine_pid=98765, process_identity='finite controlled process --run --arm '+arm,
            run_started_at=now, source_fingerprints=sources, cache_receipts=[], fixture_only=True)
        for label,name in [('run_context','run_context.json'),('preflight','preflight_used.json'),('execution_readiness','readiness.json')]:
            document[label+'_path']=str(account/name);document[label+'_sha256']=sha(account/name)
        owner_path = folder / (arm+'_fixture_owner.json');write(owner_path, document)
        owner = scope.load_owner(owner_path, sha(owner_path), _observer=lambda pid:document['process_identity'], _allow_fixture=True)
        return owner, document

    def waiting(self, owner, request):
        path = Path(owner.document['wait_root'])/('request_'+request['request_sha256'])/'request.json'
        write(path, request)
        write(path.with_name('request_fingerprint.json'), dict(request_path=str(path),
            request_sha256=request['request_sha256'],request_file_sha256=sha(path)))
        write(path.parent.parent/'audit.json', [dict(status='waiting_for_independent_data', request_path=str(path),
            request_sha256=request['request_sha256'],request_file_sha256=sha(path),
            started_at=datetime.now(timezone.utc).isoformat(),wait_seconds_max=1800)])
        return scope.read_actual_request(owner, path, sha(path))

    def test_owner_same_digest_and_current_identity_fail_closed(self):
        self.assertIsNotNone(scope, 'new OFF owner/current-request scope is absent')
        before={name:sha(TOOLS/name) for name in ('stage044_qualified_wait_driver.py','stage037_b_ts_request_provider.py',
            'stage041_exact_daily_request_provider.py','stage051_generic_exact_daily_recovery.py','stage052_generic_daily_source_resolver.py')}
        with tempfile.TemporaryDirectory(dir=OUT,prefix='owner_') as temp:
            folder=Path(temp)
            with patch.object(scope,'OUTPUT_ROOT',folder/'scope'):
                a,ad=self.fixture(folder,'A_OFF');b,bd=self.fixture(folder,'B_OFF')
                request=dict(schema=gate.REQUEST_SCHEMA,request_sequence=1,execution_trade_date='2022-05-31',active_orders=[],requirements=[])
                request['request_sha256']=gate.request_sha256(request)
                ca=self.waiting(a,request);cb=self.waiting(b,request)
                self.assertEqual(ca['digest'],cb['digest'])
                self.assertNotEqual(scope.request_directory(a,ca),scope.request_directory(b,cb))
                with self.assertRaises(ValueError):scope.read_actual_request(a,cb['path'],cb['file_sha'])
                with self.assertRaises(ValueError):scope.read_actual_request(a,ca['path'],'0'*64)
                with patch.object(a,'observer',lambda pid:'different PID start / args'):
                    with self.assertRaises(ValueError):scope.read_actual_request(a,ca['path'],ca['file_sha'])
                context=Path(ad['run_context_path']);prior=context.read_bytes();context.write_bytes(prior+b' ')
                with self.assertRaises(ValueError):scope.read_actual_request(a,ca['path'],ca['file_sha'])
                context.write_bytes(prior)
                audit=Path(ad['wait_root'])/'audit.json';write(audit,[dict(status='qualified_delivery_pointer_accepted')])
                with self.assertRaises(ValueError):scope.read_actual_request(a,ca['path'],ca['file_sha'])
                with self.assertRaises(ValueError):provider.run_once(a,folder/'missing_packet')
        self.assertEqual(before,{name:sha(TOOLS/name) for name in before})
        write(OUT/'test1.json',dict(same_digest_separate_owners=True,wrong_owner_pid_run_sha_wait_rejected=True,
            provider_rejects_fixture_owner=True,old_sources_unchanged=before,financial_replays=0))

    def test_real021_joint_local_cache_rights_and_atomic_old_values(self):
        self.assertIsNotNone(scope, 'new OFF independent local qualification is absent')
        calendar=pd.DatetimeIndex(['2022-05-30','2022-05-31'])
        symbols=['fu2209.SHFE','rb2210.SHFE'];sources={};contexts=[]
        for symbol,kind in zip(symbols,['full_session','anchor']):
            grid=old.session_grid(symbol,'2022-05-31',calendar)
            stamps=list(grid)+[grid[-1]+pd.Timedelta(minutes=1)]
            native,exchange=symbol.split('.')
            sources[symbol]=pd.DataFrame(dict(vt_symbol=symbol,bar_datetime=stamps,
                open=100.,high=101.,low=99.,close=100.,volume=1.,open_oi=10.,close_oi=11.,
                bar_id=range(len(stamps)),tq_symbol=exchange+'.'+native,source_row_number=range(2,len(stamps)+2)))
            contexts.append(dict(target=dict(vt_symbol=symbol,execution_trade_date='2022-05-31',requirement_kind=kind),
                grid=grid,daily=dict(open=100.,high=101.,low=99.,close=100.,volume=float(len(grid)),open_oi=10.,close_oi=11.)))
        class Engine:
            def _stage827_order_context(self,order,bar):return None
        summaries=[]
        with tempfile.TemporaryDirectory(dir=OUT,prefix='local_') as temp:
            folder=Path(temp)
            with patch.object(scope,'OUTPUT_ROOT',folder/'scope'):
                owner,_=self.fixture(folder)
                for conflict in (False,True):
                    engine=Engine();engine.datetime=pd.Timestamp('2022-05-31')
                    orders=[SimpleNamespace(vt_symbol=s,vt_orderid='FIXTURE.'+str(i),offset=SimpleNamespace(name=k))
                        for i,(s,k)in enumerate(zip(symbols,['OPEN','CLOSE']))]
                    engine.active_limit_orders={o.vt_orderid:o for o in orders};engine.bars={s:object()for s in symbols}
                    existing=sources[symbols[0]].iloc[:1][gate.FIELDS].copy();existing['minute_source']='retained_non859'
                    if conflict:existing.loc[existing.index[0],'high']=102.
                    original={symbols[0]:existing};engine.strategy=SimpleNamespace(stage827_minute_by_symbol=original,
                        available_trade_dates=calendar)
                    seen=[]
                    def resolver(request):
                        current=self.waiting(owner,request)
                        for context,target in zip(contexts,request['requirements']):context['target']=target
                        # Explicit independently checked tiny references, not a market signature.
                        result=scope.qualify_local_sources(owner,current,contexts,sources,scope.Bindings())
                        self.assertEqual(result['status'],'accepted')
                        self.assertFalse(current['path'].with_name('response.json').exists())
                        receipt=Path(result['receipt_path']);scope.gate_parser(current,receipt,result['receipt_sha256'])
                        seen.append(result)
                        return gate.QualifiedDelivery(receipt,result['receipt_sha256'])
                    audit=[]
                    with gate.qualified_wait_scope(Engine,resolver,audit) as g:
                        if conflict:
                            with self.assertRaisesRegex(ValueError,'old_value_conflict'):g.ensure(engine,orders[0],engine.bars[symbols[0]])
                            self.assertFalse(g.dynamic_full);self.assertNotIn(symbols[1],engine.strategy.stage827_minute_by_symbol)
                        else:
                            g.ensure(engine,orders[0],engine.bars[symbols[0]])
                            self.assertEqual(len(g.dynamic_full),345);self.assertEqual(len(g.dynamic_anchor),1)
                            self.assertFalse(g.qualified((symbols[1],contexts[1]['grid'][0]),'full_session'))
                    summaries.append(dict(conflict=conflict,events=audit))
                    # Independent requalification must not reuse same-owner decision artifacts in this fixture.
                    import shutil
                    shutil.rmtree(scope.request_directory(owner,dict(digest=seen[0]['request_sha256'])))
                incomplete={s:f.iloc[:1].copy()for s,f in sources.items()}
                request=dict(schema=gate.REQUEST_SCHEMA,request_sequence=10,execution_trade_date='2022-05-31',active_orders=[],requirements=[])
                for context in contexts:
                    target=deepcopy(context['target']);request['requirements'].append(target)
                request['request_sha256']=gate.request_sha256(request);current=self.waiting(owner,request)
                result=scope.qualify_local_sources(owner,current,contexts,incomplete,scope.Bindings())
                self.assertEqual(result['status'],'needs_provider');self.assertFalse(current['path'].with_name('response.json').exists())
                bad=sources[symbols[0]].copy();bad.loc[0,'high']=103.
                with self.assertRaisesRegex(ValueError,'conflict'):
                    scope.qualify_local_sources(owner,current,contexts,{symbols[0]:[sources[symbols[0]],bad],symbols[1]:sources[symbols[1]]},scope.Bindings())
                with self.assertRaises(ValueError):scope.read_cached_receipt(owner,current,dict(receipt_path=str(TOOLS.parent/'outputs/stage075_source859_isolation_implementation/x.json'),receipt_sha256='0'*64),scope.Bindings())
                old_digest='6873f0a1930106a91bb35355efbf2e9843ddcd9f05aa3ebf1ebf105806ab3730'
                old_receipt=TOOLS.parent/('outputs/stage052_generic_daily_source_resolver/request_'+old_digest+'/delivery_receipt.json')
                cache=scope.read_cached_receipt(owner,current,dict(receipt_path=str(old_receipt),
                    receipt_sha256='274190b95b9c1ff18cdee2743730ddec0a89b6ad4f035e108f69f269701327bf'),scope.Bindings())
                self.assertEqual(len(cache['data']),345)
                self.assertEqual(len(cache['proof']),345)
                self.assertFalse(cache['commit_inheritance'])
                self.assertEqual(cache['origin_request_sha256'],old_digest)
                real_target=dict(vt_symbol='fu2209.SHFE',execution_trade_date='2022-05-31',requirement_kind='full_session',
                    required_timestamps=[t.isoformat()for t in old.session_grid('fu2209.SHFE','2022-05-31',calendar)],
                    missing_or_unqualified_timestamps=[t.isoformat()for t in old.session_grid('fu2209.SHFE','2022-05-31',calendar)],existing_source_timestamps=[])
                real_request=dict(schema=gate.REQUEST_SCHEMA,request_sequence=11,execution_trade_date='2022-05-31',
                    active_orders=[dict(order_id='FIXTURE.NEW.191',vt_symbol='fu2209.SHFE',requirement_kind='full_session')],requirements=[real_target])
                real_request['request_sha256']=gate.request_sha256(real_request);real_current=self.waiting(owner,real_request)
                real=cache['data'].sort_values('bar_datetime')
                reference=dict(open=float(real.open.iloc[0]),high=float(real.high.max()),low=float(real.low.min()),
                    close=float(real.close.iloc[-1]),volume=float(real.volume.sum()),open_oi=float(real.open_oi.iloc[0]),close_oi=float(real.close_oi.iloc[-1]))
                result=scope.qualify_local_sources(owner,real_current,[dict(target=real_target,
                    grid=old.session_grid('fu2209.SHFE','2022-05-31',calendar),daily=reference)],{},scope.Bindings(),cached=[cache])
                self.assertEqual(result['status'],'accepted')
                self.assertNotEqual(result['request_sha256'],old_digest)
        write(OUT/'test2.json',dict(real021=True,cases=summaries,full_keys=345,anchor_keys=1,
            actual_cache191_origin=cache['origin_request_sha256'],actual_cache191_rows=len(cache['data']),
            actual_cache191_proofs=len(cache['proof']),cache191_not_commit_inheritance=not cache['commit_inheritance'],
            new_fixture_request_digest=result['request_sha256'],fixture075_rejected=True,financial_replays=0))

    def test_fake_child_terminal_daily_budget_no_retry_and_bootstrap(self):
        self.assertIsNotNone(scope, 'new bounded OFF provider chain is absent')
        with tempfile.TemporaryDirectory(dir=OUT,prefix='child_') as temp:
            folder=Path(temp)
            with patch.object(scope,'OUTPUT_ROOT',folder/'scope'):
                owner,_=self.fixture(folder)
                first=old.session_grid('fu2209.SHFE','2022-05-31',pd.DatetimeIndex(['2022-05-30','2022-05-31']))[0].isoformat()
                target=dict(vt_symbol='fu2209.SHFE',execution_trade_date='2022-05-31',requirement_kind='anchor',
                    required_timestamps=[first],missing_or_unqualified_timestamps=[first],existing_source_timestamps=[])
                request=dict(schema=gate.REQUEST_SCHEMA,request_sequence=1,execution_trade_date='2022-05-31',
                    active_orders=[dict(order_id='FIXTURE.CLOSE',vt_symbol='fu2209.SHFE',requirement_kind='anchor')],requirements=[target])
                request['request_sha256']=gate.request_sha256(request);current=self.waiting(owner,request)
                packet=scope.request_directory(owner,current)/'daily_packet';packet.mkdir(parents=True)
                daily=dict(vt_symbol='fu2209.SHFE',trade_date='2022-05-31',requirement_kind='anchor',
                    open=100.,high=101.,low=99.,close=100.,volume=1.,open_interest=10.)
                manifest=dict(schema='stage087_provider_packet_v1',family='daily',owner_sha256=owner.sha256,
                    owner_path=str(owner.path),request_path=str(current['path']),request_file_sha256=current['file_sha'],
                    request_sha256=current['digest'],daily_targets=[daily],fixture_only=True)
                write(packet/'packet_manifest.json',manifest);write(packet/'preflight.json',dict(source_fingerprints={}))
                journal=dict(provider_connections=3,max_provider_connections=4)
                calls=[]
                def fake_child(argv,timeout):
                    calls.append(argv);attempt=packet/'network_attempt1';attempt.mkdir()
                    raw=pd.DataFrame([dict(id=i,datetime=pd.Timestamp(day,tz='Asia/Shanghai').tz_convert('UTC').value,
                        open=100.,high=101.,low=99.,close=100.,volume=1.,open_oi=10.,close_oi=11.)
                        for i,day in enumerate(['2022-05-31','2022-06-01','2022-06-02'])])
                    rawpath=attempt/'raw/SHFE/fu2209.csv';rawpath.parent.mkdir(parents=True);raw.to_csv(rawpath,index=False)
                    _,q,a,_=scope.deps().generic.ordinary_raw_evidence(raw.to_dict('records'),'fu2209.SHFE','2022-05-31',
                        dict(open=100.,high=101.,low=99.,close=100.,volume=1.,open_oi=10.))
                    pd.DataFrame([q]).to_csv(attempt/'qualified_daily.csv',index=False)
                    pd.DataFrame([a]).to_csv(attempt/'target_qualification.csv',index=False)
                    write(attempt/'worker_receipt.json',dict(status='completed_all_targets_qualified',accepted=True,
                        provider_connections_attempted=1,TqSim_created=True,owner_sha256=owner.sha256,
                        request_sha256=current['digest'],automatic_retry=False,financial_replays=0,model_fits=0,orders=0,cancels=0,
                        broker_or_ctp_connections=0,fixture_only=True))
                    write(attempt/'parent_receipt.json',dict(status='worker_terminal',exit_code=0,hard_kill=False,
                        all_inputs_unchanged=True,owner_sha256=owner.sha256,request_sha256=current['digest'],preflight_sha256=sha(packet/'preflight.json'),
                        elapsed_seconds=1.,automatic_retry=False,
                        artifact_sha256={str(p.relative_to(attempt)):sha(p)for p in attempt.rglob('*')if p.is_file()}))
                    return {},dict(subprocess_pid=123,subprocess_returncode=0,terminal_observed=True)
                terminal=scope.run_provider_connection(owner,current,packet,journal,remaining_seconds=900,_invoke=fake_child)
                self.assertEqual(journal['provider_connections'],4);self.assertEqual(len(calls),1)
                self.assertEqual(terminal['new_daily_provider_connections'],1)
                _,q,_,_=scope.read_scoped_daily(owner,current,packet,'fu2209.SHFE',scope.Bindings())
                self.assertEqual(q['trade_date'],'2022-05-31')
                # The same true-structured raw is requalified only for a later actual target;
                # no second connection, invented fit or unchanged old target claim.
                later=deepcopy(request);later['request_sequence']=2;later['execution_trade_date']='2022-06-01'
                later['requirements'][0]['execution_trade_date']='2022-06-01'
                later['request_sha256']=gate.request_sha256(later)
                later_current=self.waiting(owner,later)
                six=dict(open=100.,high=101.,low=99.,close=100.,volume=1.,open_oi=10.)
                with patch.object(scope,'query_daily_six',return_value=six):
                    _,later_q,_,check=scope.recover_scoped_daily(owner,later_current,'fu2209.SHFE',scope.Bindings())
                self.assertEqual(later_q['trade_date'],'2022-06-01')
                self.assertEqual(check['source_origin_request_sha256'],current['digest'])
                self.waiting(owner,request)
                with self.assertRaises(ValueError):scope.run_provider_connection(owner,current,packet,journal,remaining_seconds=900,_invoke=fake_child)
                self.assertEqual(len(calls),1)
                other=packet.with_name('another');other.mkdir();write(other/'packet_manifest.json',manifest);write(other/'preflight.json',{})
                with self.assertRaises(ValueError):scope.run_provider_connection(owner,current,other,dict(provider_connections=0,max_provider_connections=4),remaining_seconds=839,_invoke=fake_child)
                def failed_child(argv,timeout):return {},dict(subprocess_pid=124,subprocess_returncode=1,terminal_observed=True)
                with self.assertRaises(ValueError):scope.run_provider_connection(owner,current,other,dict(provider_connections=0,max_provider_connections=4),remaining_seconds=900,_invoke=failed_child)
                self.assertFalse((other/'terminal_observed.json').exists())
                with patch.object(owner,'observer',lambda pid:'PID changed'):
                    with self.assertRaises(ValueError):scope.run_provider_connection(owner,current,other,dict(provider_connections=0,max_provider_connections=4),remaining_seconds=900,_invoke=fake_child)
                with self.assertRaises(ValueError):provider.run_once(owner,packet)
                minute=packet.with_name('minute_packet');minute.mkdir()
                refs=scope.request_directory(owner,current)/'daily_references.json'
                write(refs,dict(contexts=[dict(target=target,daily=six)],source_fingerprints={}))
                m=dict(manifest,family='minute',daily_references_path=str(refs),daily_references_sha256=sha(refs))
                write(minute/'packet_manifest.json',m);write(minute/'preflight.json',dict(source_fingerprints={}))
                attempt=minute/'network_attempt1';attempt.mkdir()
                pd.DataFrame([dict(vt_symbol='fu2209.SHFE',bar_datetime=first,open=100.,high=101.,low=99.,close=100.,
                    volume=1.,open_oi=10.,close_oi=11.)]).to_csv(attempt/'raw_completed_minutes.csv',index=False)
                pd.DataFrame([dict(vt_symbol='fu2209.SHFE',bar_datetime=first,successor_time=(pd.Timestamp(first)+pd.Timedelta(minutes=1)).isoformat(),
                    completed=True,method='observed_later_serial_kline')]).to_csv(attempt/'completion_evidence.csv',index=False)
                write(attempt/'worker_receipt.json',dict(status='all_target_minutes_completed',accepted=True,
                    provider_connections_attempted=1,TqSim_created=True,owner_sha256=owner.sha256,request_sha256=current['digest'],
                    automatic_retry=False,financial_replays=0,model_fits=0,orders=0,cancels=0,broker_or_ctp_connections=0))
                write(attempt/'parent_receipt.json',dict(status='worker_terminal',exit_code=0,hard_kill=False,elapsed_seconds=1.,
                    automatic_retry=False,all_inputs_unchanged=True,owner_sha256=owner.sha256,request_sha256=current['digest'],
                    preflight_sha256=sha(minute/'preflight.json'),
                    artifact_sha256={str(p.relative_to(attempt)):sha(p)for p in attempt.rglob('*')if p.is_file()}))
                mt=dict(terminal,parent_receipt_sha256=sha(attempt/'parent_receipt.json'),preflight_sha256=sha(minute/'preflight.json'),
                    new_daily_provider_connections=0,new_minute_provider_connections=1)
                write(minute/'terminal_observed.json',mt)
                accepted=scope.review_packet(owner,current,[minute],[sha(minute/'terminal_observed.json')])
                self.assertFalse(current['path'].with_name('response.json').exists())
                audit=Path(owner.document['wait_root'])/'audit.json';waiting_bytes=audit.read_bytes()
                write(audit,[dict(status='qualified_delivery_pointer_accepted')])
                with self.assertRaises(ValueError):scope.publish_reviewed(owner,current,accepted['receipt_path'],accepted['receipt_sha256'])
                self.assertFalse(current['path'].with_name('response.json').exists());audit.write_bytes(waiting_bytes)
                scope.publish_reviewed(owner,current,accepted['receipt_path'],accepted['receipt_sha256'])
                self.assertTrue(current['path'].with_name('response.json').exists())
                self.assertTrue(scope.numeric_runtime_is_frozen())
        write(OUT/'test3.json',dict(fake_children_only=True,parent_true_zero_required=True,daily_counts_in_four=True,
            ordinary_daily_actual_id_time_successor_checked=True,later_actual_day_reuses_same_snapshot=True,
            minute_independent_review_before_fixture_pointer=True,changed_current_wait_no_publish=True,
            no_automatic_retry=True,low_budget_and_pid_change_no_launch=True,fixture_provider_rejected=True,
            network_connections=0,financial_replays=0,model_fits=0))


if __name__=='__main__':unittest.main(verbosity=2)
