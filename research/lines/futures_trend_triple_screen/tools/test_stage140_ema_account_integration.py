"""Three bounded native integration compositions; no real account/provider."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
import ast
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timedelta
import json
import shutil
from types import SimpleNamespace
from unittest.mock import patch

TOOLS=Path(__file__).resolve().parent
sys.path.insert(0,str(TOOLS))


def module(name):
    if name in sys.modules:return sys.modules[name]
    path=TOOLS/(name+'.py')
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value)
    return value


_ARTIFACT=None
_ARTIFACT_BUILD_STARTED=False
_TEMPS=[]
NATIVE_EVIDENCE=TOOLS.parent/'outputs/stage145_ema_native_financial_integration'


def numerical():
    # Only constructors/helpers are reused; no old test methods are executed.
    return module('test_stage127_ema_limit_strategy')


def report_native(fixtures,engine,profile,metadata,daily):
    """Use the original847 report statements, not another PnL formula."""
    native=fixtures.native
    tree=ast.parse(Path(native.__file__).read_bytes())
    run=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='_run_profile')
    body=next(n for n in run.body if isinstance(n,ast.Try)).body
    first=next(i for i,n in enumerate(body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='daily'for t in n.targets))
    last=next(i for i,n in enumerate(body)if isinstance(n,ast.Return))
    env={**native.__dict__,**dict(engine=engine,profile=profile,metadata=metadata,daily_df=daily,
        spec=profile['spec'],START=fixtures.pd.Timestamp(fixtures.NEXT),END=fixtures.pd.Timestamp('2026-01-08'))}
    exec(compile(ast.Module(body=body[first:last],type_ignores=[]),native.__file__,'exec'),env)
    return env['combined'],env['frames']


def native_artifact():
    global _ARTIFACT,_ARTIFACT_BUILD_STARTED
    if _ARTIFACT is not None:return _ARTIFACT
    if _ARTIFACT_BUILD_STARTED:raise RuntimeError('native fixture already failed; refusing a second engine')
    _ARTIFACT_BUILD_STARTED=True
    fixtures=numerical();pd=fixtures.pd;native=fixtures.native
    cp=module('stage140_ema_checkpoint');runner=module('stage140_run_ema_account')
    import stage031_run_ordered_checkpoint as shared
    import stage021_blocking_data_gate as gate
    evidence=NATIVE_EVIDENCE
    evidence.mkdir(parents=True,exist_ok=True)
    root=Path(tempfile.mkdtemp(prefix='fixture_native_',dir=evidence)).resolve()
    contracts=['AP605.CZCE','au2606.SHFE','rb2605.SHFE','cu2606.SHFE','cu2607.SHFE']
    products=['AP.CZCE','au.SHFE','rb.SHFE','cu.SHFE']
    setting=fixtures.settings(root,contracts=contracts,products=products)
    setting.update(capital_base=150000.,risk_ratio_volume_open_interest_surge=.005,risk_ratio_of_total_assets=.005,
        max_capital_usage_ratio=.2,max_single_trade_capital_usage_ratio=.1,max_concurrent_positions=4,
        short_entry_enabled=True,ma5_extreme_filter_enabled=False,short_ma5_slope_filter_enabled=False,wick_chop_filter_enabled=False,
        rollover_reopen_enabled=True,enable_rollover_shape_same_volume_reopen=True)
    meta=fixtures.metadata(contracts,products);formal=fixtures.runtime.capture_formal_profile(fixtures.s901,meta,
        pd.Timestamp(fixtures.runtime.START),pd.Timestamp(fixtures.runtime.END))
    holder={}
    profile,engine_cls=fixtures.adapter().build_ema_account_profile(formal,fixtures.NATIVE,fixtures.ENGINE,
        weekly=fixtures.Weekly(),fi={(fixtures.DAY,c):dict(ready=True,fi2=-1.)for c in contracts},
        next_days={fixtures.DAY:fixtures.NEXT,fixtures.NEXT:'2026-01-08'},ema_lookup=fixtures.lookup(contracts),
        qualify=shared.build_qualification_callback(holder,native.s827.Offset,native.s827.Direction))
    integration=cp.write_json(root/'fixture_integration.json',dict(fixture_only=True,source_bindings={}))
    source={str(p):dict(sha256=cp.asset(p).sha256,bytes=cp.asset(p).bytes)for p in (TOOLS/'stage140_ema_checkpoint.py',TOOLS/'stage140_run_ema_account.py')}
    protocol=cp.write_bytes(root/'fixture_protocol.md',b'# fixture-only source snapshot protocol\n')
    data={str(protocol.path):dict(sha256=protocol.sha256,bytes=protocol.bytes)}
    preflight=dict(schema=cp.PREFLIGHT_SCHEMA,account_id=cp.ACCOUNT_ID,mechanism_id=cp.MECHANISM_ID,attempt=1,fixture_only=True,
        account_root=str(root/'EMA_LIMIT'),source_bindings=source,data_bindings=data,capital=150000,
        reference_calendar=[fixtures.NEXT,'2026-01-08'],active_parameter_identity=dict(strategy_version='fixture_only'))
    readiness=cp.write_json(root/'fixture_readiness.json',dict(schema=cp.READINESS_SCHEMA,account_id=cp.ACCOUNT_ID,
        mechanism_id=cp.MECHANISM_ID,attempt=1,fixture_only=True,global_attempt=12,issued_by='fixture_only',
        fixture_execution_authorized=True,financial_execution_authorized=False,source_bindings=source,data_bindings=data,
        preflight_sha256=__import__('hashlib').sha256(cp.json_bytes(preflight)).hexdigest(),
        integration_review_path=str(integration.path),integration_review_sha256=integration.sha256,integration_review_bytes=integration.bytes))
    run=cp.start_run(preflight=preflight,readiness=readiness,started_at='2026-01-01T00:00:00+08:00',global_attempt=12)
    engine=engine_cls({});engine.capital=150000.;engine.datetime=datetime.fromisoformat(fixtures.DAY)
    engine.vt_symbols=contracts
    for name in ('sizes','priceticks','rates','slippages'):setattr(engine,name,meta[name])
    engine.bars={c:fixtures.bar(c)for c in contracts};engine.output=lambda _:None
    keys=set()
    with ExitStack()as stack:
        captured=stack.enter_context(fixtures.runtime.capture_engine(engine_cls))
        ema=stack.enter_context(runner.capture_ema(engine_cls,run))
        qualified=stack.enter_context(gate.qualified_wait_scope(engine_cls,lambda *_:(_ for _ in()).throw(AssertionError('fixture resolver should not run')),[],
            qualified_existing_keys=keys,qualified_anchor_existing_keys=keys));holder['gate']=qualified
        engine.add_strategy(profile['strategy_cls'],setting);strategy=engine.strategy;strategy.trading=True
        if strategy.ema_limit_run_id!=run.run_id:raise AssertionError('run id was not injected by real add_strategy')
        for contract in contracts:
            manager=strategy.ams[contract]
            for i in range(manager.size):
                close=70+24*i/manager.size
                manager.update_bar(fixtures.bar(contract,datetime.fromisoformat(fixtures.DAY)-timedelta(days=manager.size-i),
                    close,close+1,close-1,close))
        strategy._generate_signal=lambda *_:strategy._signal_result('',True,False,100.,100.,100.,100.,'regular',False,rsi_value=50.)
        engine.bars={c:fixtures.bar(c,low=90. if c.startswith('cu') else 96.)for c in contracts}
        strategy.on_bars(engine.bars)
        engine.datetime=datetime.fromisoformat(fixtures.NEXT)
        engine.bars={c:fixtures.bar(c,fixtures.NEXT,high=104.,low=88.)for c in contracts}
        def minutes(day):
            frames={}
            for i,c in enumerate(contracts):
                grid=native.s827.execution.session_minutes(c,day,strategy.available_trade_dates)
                frame=pd.DataFrame(dict(vt_symbol=c,bar_datetime=grid,open=100.,high=100.,low=100.,close=100.,volume=1000.,open_oi=100.,close_oi=100.))
                if day==fixtures.NEXT:
                    observations=([(103,105,99,104,1000),(100,100,98,99,1000),(103,104,97,99,1000)]if i==0 else
                        [(90,92,88,90,1000)]if i==1 else [(101,102,99,100,0)]if i==2 else [(103,104,99,100,1000)])
                    for j,values in enumerate(observations):frame.loc[j,['open','high','low','close','volume']]=values
                    if i==2:frame['volume']=0.
                frames[c]=frame;keys.update((c,stamp)for stamp in grid)
            strategy.stage827_minute_by_symbol=frames
            return frames
        physical=minutes(fixtures.NEXT);engine.cross_delayed_orders()
        # A genuine held contract uses the native rollover planner/order path.
        strategy._handle_rollover(strategy.states['cu.SHFE'],'cu2607.SHFE',engine.bars)
        strategy.rebalance_portfolio(engine.bars)
        engine.update_daily_close(engine.bars,engine.datetime)
        strategy.estimated_equity=strategy._estimate_equity(engine.bars)
        equity=[dict(date=fixtures.NEXT,estimated_equity=strategy.estimated_equity,settled_balance=strategy.settled_balance)]
        engine.datetime=datetime.fromisoformat('2026-01-08')
        engine.bars={c:fixtures.bar(c,'2026-01-08',high=101.,low=99.)for c in contracts}
        minutes('2026-01-08');engine.cross_delayed_orders();engine.update_daily_close(engine.bars,engine.datetime)
        strategy.estimated_equity=strategy._estimate_equity(engine.bars)
        daily=engine.calculate_result()
        equity.append(dict(date='2026-01-08',estimated_equity=strategy.estimated_equity,settled_balance=strategy.settled_balance))
    captured['equity']=equity
    combined,frames=report_native(fixtures,engine,profile,meta,daily)
    context,_=cp.load_context(run)
    parameters=dict(spec=asdict(profile['spec']),contract_sizes=meta['sizes'],rates=meta['rates'],slippages=meta['slippages'],priceticks=meta['priceticks'])
    payload=dict(combined=combined,frames=frames,capture=captured,actual_trade_identities=ema['actual_trade_identities'],
        ema={k:ema[k]for k in ('decision','fill','execution','budget','pending')},actual=[dict(actual={**setting,
            'margin_ratio_overrides':strategy.margin_ratio_overrides,'default_margin_ratio':strategy.default_margin_ratio})],parameters=parameters,
        spec=asdict(profile['spec']),input_fingerprints={},run_context=context,preflight=preflight)
    raw=cp.save_raw(run,payload)
    validation=dict(cp.VALIDATION,fixture_only=True,actual_daily_count=2)
    with unittest.TestCase().assertRaisesRegex(ValueError,'validation_not_passed'):
        cp.seal_raw(run,raw,{**validation,'engine_returned':False})
    cp.seal_raw(run,raw,validation)
    # A real serializer failure leaves exactly the same sealed native raw.
    metrics=__import__('analyze_qmt_roll_stage650_stage526_200k_capital_reality_check')
    with patch.object(metrics,'_metrics',side_effect=ValueError('fixture deliberate export failure')):
        with unittest.TestCase().assertRaisesRegex(ValueError,'deliberate export failure'):
            cp.export_sealed(run,run.output/'exports/export_001')
    raw_before=cp.asset(raw.path)
    original_runner=module('stage065_run_pairwise_off')
    with patch.object(runner,'prepare_ema',side_effect=AssertionError('export-only entered prepare')),\
        patch.object(original_runner,'run_profile_once',side_effect=AssertionError('export-only entered native')) ,\
        patch.object(fixtures.joblib,'load',side_effect=AssertionError('export-only loaded model')):
        summary=runner.main(['--export-only','--run-context',str(run.output/'run_context.json'),'--run-context-sha256',cp.asset(run.output/'run_context.json').sha256,
            '--destination',str(run.output/'exports/export_002')])
    if cp.asset(raw.path)!=raw_before:raise AssertionError('raw changed during export-only')
    _ARTIFACT=dict(run=run,payload=payload,summary=summary,export=run.output/'exports/export_002',raw=raw,
        engine=engine,physical=physical,fixture_native_engine_instances=1,checkpoint=cp)
    return _ARTIFACT


class EmaAccountIntegrationTest(unittest.TestCase):
    def required(self,name):
        self.assertTrue((TOOLS/(name+'.py')).exists(),name+' not implemented')
        return module(name)

    def test_layer_order_and_exact_rights(self):
        runner=self.required('stage140_run_ema_account')
        fixtures=numerical();pd=fixtures.pd
        import stage061_accepted_wait_delta as accepted
        import stage071_source859_isolation as isolation
        import stage016_source859_qualification as correction
        import stage002_local_minute_overlay as old
        def frame(stamp,price,source):
            return old.normal_times(pd.DataFrame([dict(vt_symbol='x.TEST',bar_datetime=stamp,
                open=price,high=price+1,low=price-1,close=price,volume=5.,open_oi=6.,close_oi=7.,minute_source=source)]))
        key=lambda n:('x.TEST',pd.Timestamp('2020-01-02T09:0'+str(n)))
        bad=frame(key(1)[1],10.,isolation.SOURCE859)
        old_frame=frame(key(0)[1],10.,'fixture_old_190')
        new_frame=pd.concat([frame(key(1)[1],11.,'fixture_new159'),frame(key(2)[1],11.,'fixture_anchor')],ignore_index=True)
        before=old_frame.copy(deep=True)
        d190=accepted.FrozenDelta(old_frame,frozenset([key(0)]),frozenset([key(0)]),{},dict(fixture_only=True))
        d159=accepted.FrozenDelta(new_frame,frozenset([key(1)]),frozenset([key(1),key(2)]),{},dict(fixture_only=True))
        empty=bad.iloc[:0].copy();qualified=correction.QualifiedDelta(empty,empty,set(),True,True)
        original=lambda symbols:bad.copy(deep=True)
        saved=[object(),set(['old']),object()]
        engine=SimpleNamespace(_load_stage861_full_minute_bars=original,**dict(zip(accepted.CACHE_NAMES,saved)))
        args=dict(overlay=empty,qualified=qualified,anchor_data=empty,anchor_keys=set(),delta190=d190,delta159=d159,
            completed_keys=frozenset([key(0)]),isolation_audit=[])
        with runner.ema_minute_scope(engine,**args)as added:
            result=engine._load_stage861_full_minute_bars(['x.TEST'])
            self.assertEqual(result.sort_values('bar_datetime').close.tolist(),[10.,11.,11.])
            full,anchor=runner.compose_ema_rights(lambda *_:True,lambda *_:False,added,set(),d190,d159)
            self.assertTrue(full(*key(1)));self.assertFalse(full(*key(2)));self.assertTrue(anchor(*key(2)))
        for name,value in zip(accepted.CACHE_NAMES,saved):self.assertIs(getattr(engine,name),value)
        self.assertIs(engine._load_stage861_full_minute_bars,original);pd.testing.assert_frame_equal(old_frame,before)
        with self.assertRaisesRegex(ValueError,'old_value_conflict'):
            with accepted.temporary_accepted_wait_delta(engine,d159),isolation.temporary_source859_isolation(engine,{key(0)},[]):
                engine._load_stage861_full_minute_bars(['x.TEST'])
        with self.assertRaisesRegex(RuntimeError,'fixture failure'):
            with runner.ema_minute_scope(engine,**args):raise RuntimeError('fixture failure')
        for name,value in zip(accepted.CACHE_NAMES,saved):self.assertIs(getattr(engine,name),value)
        # The accepted159 proof closure includes an explicitly bound .pkl.gz.
        # It must use031's existing explicit-format contract, not broaden022.
        with tempfile.TemporaryDirectory()as tmp:
            import hashlib
            proof=Path(tmp).resolve()/'qualification_proof.pkl.gz';proof.write_bytes(b'fixture-only compressed proof')
            recorder=fixtures.runtime.InputRecorder({})
            self.assertTrue(hasattr(runner,'delta_input_recorder'),'explicit accepted-delta recorder integration missing')
            view=runner.delta_input_recorder(recorder);view.record(proof)
            self.assertIs(view.files,recorder.files)
            self.assertEqual(recorder.files[str(proof)]['sha256'],hashlib.sha256(proof.read_bytes()).hexdigest())
            proof.write_bytes(b'changed proof')
            with self.assertRaisesRegex(ValueError,'consumed_input_changed_during_run'):recorder.verify()
        cp=self.required('stage140_ema_checkpoint')
        feature_root=TOOLS.parent/'outputs/stage142_ema_daily_qualification_and_features'
        try:
            lookup=runner.read_ema_features(cp.asset(feature_root/'feature_manifest.json'),cp.asset(feature_root/'handoff_receipt.json'))
        except Exception as error:
            self.fail('actual fixed142 reader must accept its qualified handoff: '+repr(error))
        self.assertEqual(len(lookup),116394)
        sample=lookup[('2020-12-30','AP101.CZCE')]
        self.assertTrue(sample['ready']);self.assertEqual(sample['positive_up_count'],0)
        self.assertIsNone(sample['mean_up']);self.assertGreater(sample['mean_down'],0)
        self.assertEqual(sum(x['ready'] for x in lookup.values()),96813)

    def test_native_return_raw_seal_export_and_recovery(self):
        checkpoint=self.required('stage140_ema_checkpoint')
        value=native_artifact();payload=value['payload'];run=value['run']
        self.assertTrue(run.fixture_only);self.assertEqual(value['fixture_native_engine_instances'],1)
        context=payload['run_context']
        self.assertIn('source_snapshot_manifest_path',context)
        snapshot=json.loads(checkpoint.read_asset(checkpoint.BoundAsset(Path(context['source_snapshot_manifest_path']),context['source_snapshot_manifest_sha256'],context['source_snapshot_manifest_bytes'])))
        self.assertEqual(set(snapshot['files']),set(context['source_bindings'])|set(context['data_bindings']))
        for original,item in snapshot['files'].items():
            saved=run.output/item['snapshot_path']
            self.assertEqual(saved.read_bytes(),Path(original).read_bytes())
        original,item=next(iter(snapshot['files'].items()));saved=run.output/item['snapshot_path'];valid=saved.read_bytes()
        try:
            saved.write_bytes(valid+b'\n# poisoned snapshot\n')
            with self.assertRaisesRegex(ValueError,'ema_asset_changed'):
                checkpoint.load_sealed(run)
        finally:saved.write_bytes(valid)

        restored,binding=checkpoint.load_sealed(run)
        self.assertEqual(binding['manifest']['raw_sha256'],value['raw'].sha256)
        self.assertTrue((run.output/'exports/export_001/export_failure.json').is_file())
        self.assertTrue((run.output/'exports/export_002/summary.json').is_file())
        filled=[x for x in restored['ema']['execution']if x['status']=='filled']
        self.assertTrue(any(x['invalid_stop_side_gap']for x in filled))
        self.assertTrue(any(x['status']=='expired_unfilled'for x in restored['ema']['execution']))
        self.assertTrue(all(run.run_id in x['economic_mother_id']for x in filled))
        self.assertTrue(restored['frames']['stop_retry_events'].shape[0]>0)
        self.assertEqual([t.price for t in value['engine'].get_all_trades()if t.vt_symbol=='AP605.CZCE'],[100.,98.,103.,98.])
        self.assertTrue(restored['frames']['rollover_shape_same_volume'].status.eq('targeted').any())
        self.assertEqual(value['summary']['source_raw_sha256'],value['raw'].sha256)
        with self.assertRaisesRegex(ValueError,'non_account_object|forbidden_engine'):
            checkpoint.save_failure(run,dict(engine=value['engine']),'fixture','forbidden')

    def test_independent_ledger_and_ema_evidence(self):
        review=self.required('stage140_independent_ema_review')
        value=native_artifact();pd=numerical().pd
        report=review._audit_payload(value['payload'],value['export'],value['summary'])
        self.assertGreater(report['retry_links'],0);self.assertGreater(report['roll_links'],0)
        self.assertEqual(report['EMA']['invalid_gap_mothers'],1)
        self.assertTrue(all(float(x)<1e-6 for x in report['residuals'].values()))
        for corruption in ('cost','inventory','mother','price','type','invalid_R','decision_missing','budget_quantity','risk_margin'):
            with self.subTest(corruption=corruption),tempfile.TemporaryDirectory()as tmp:
                payload=deepcopy(value['payload']);target=Path(tmp)/'export';shutil.copytree(value['export'],target)
                def table(name,frame):
                    if frame.empty and not len(frame.columns):frame=pd.DataFrame(columns=['date','vt_symbol','event','reason'])
                    (target/(name+'.csv')).write_bytes(frame.to_csv(index=False).encode('utf-8-sig'))
                if corruption=='cost':payload['combined'].loc[0,'commission']+=1;table('daily',payload['combined'])
                if corruption=='inventory':
                    payload['frames']['positions'].loc[0,'end_pos']+=1;table('positions',payload['frames']['positions'])
                if corruption=='mother':
                    row=next(x for x in payload['actual_trade_identities']if x.get('economic_mother_id'))
                    row['economic_mother_id']='corrupt-owner'
                    table('actual_trade_identities',pd.DataFrame(payload['actual_trade_identities']))
                    exported=pd.read_csv(target/'trades.csv');exported.loc[exported.trade_id.eq(row['trade_id']),'economic_mother_id']='corrupt-owner';table('trades',exported)
                if corruption in ('price','type','invalid_R'):
                    row=next(x for x in payload['ema']['execution']if x['status']=='filled'and(corruption!='invalid_R'or x['invalid_stop_side_gap']))
                    row[{'price':'fill_price','type':'direction','invalid_R':'actual_risk_amount'}[corruption]]=101. if corruption=='price' else 'long'if corruption=='type' else 1.
                    table('ema_execution_audit',pd.DataFrame(payload['ema']['execution']))
                if corruption=='decision_missing':
                    payload['ema']['decision']=[];table('ema_decision_audit',pd.DataFrame())
                if corruption=='budget_quantity':
                    payload['ema']['budget'][0]['ema_limit_final_budget_volume_after']=0
                    table('ema_budget_audit',pd.DataFrame(payload['ema']['budget']))
                if corruption=='risk_margin':
                    row=next(x for x in payload['ema']['execution'] if x['status']=='filled' and not x['invalid_stop_side_gap'])
                    row['actual_risk_amount']=999999999.;row['actual_margin_amount']=999999999.
                    table('ema_execution_audit',pd.DataFrame(payload['ema']['execution']))
                with self.assertRaises((AssertionError,ValueError,TypeError)):
                    review._audit_payload(payload,target,value['summary'])


if __name__=='__main__':unittest.main()
