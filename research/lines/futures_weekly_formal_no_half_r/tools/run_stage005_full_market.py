"""Stage005 固定周线指标/三模块关闭，全市场与同数据19品种对照；只读输入、严格分钟、异常不接受绩效。"""
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os,sqlite3,sys,time,subprocess
ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r'
SOURCE=Path('/Users/mac/Desktop/fian')
DATA=LINE/'outputs/stage005_data'
VENDOR=Path('/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor')
os.chdir(ROOT);sys.path[:0]=[str(ROOT),str(VENDOR),str(ROOT/'examples/portfolio_backtesting'),str(Path(__file__).parent)]
os.environ.update(TZ='Asia/Shanghai',OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED='0',OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED='0',
    OFFICIAL_LIVE_SIGNAL_INPUT_DIR=str(LINE/'outputs/empty_signals'),OFFICIAL_LIVE_OUTPUT_DIR=str(LINE/'outputs/empty_signals'),MPLCONFIGDIR='/private/tmp/weekly-research-mpl')
time.tzset()
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--arm',choices=['E','F'],required=True);parser.add_argument('--attempt',required=True);args=parser.parse_args()
    out=LINE/'outputs'/(args.arm+'_attempt'+args.attempt)
    if (out/'terminal.json').exists():raise ValueError('completed_output_exists')
    out.mkdir(parents=True,exist_ok=True)
    data_manifest=json.loads((DATA/'completed_manifest.json').read_text())
    for path,digest in data_manifest['files'].items():
        if sha(path)!=digest:raise ValueError('completed_data_digest_changed:'+path)
    from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
    identity=asdict(assert_official_checkout_matches_active_material(ROOT))
    if identity!=asdict(assert_official_checkout_matches_active_material(SOURCE)):raise ValueError('identity_drift')
    import pandas as pd
    from vnpy.trader.setting import SETTINGS
    SETTINGS['log.active']=False
    import vnpy_sqlite.sqlite_database as sqlite_driver
    if not sqlite_driver.db.is_closed():sqlite_driver.db.close()
    sqlite_driver.db.init(str(DATA/'daily.sqlite'))
    import vnpy.trader.database as database_module
    database_module.database=sqlite_driver.SqliteDatabase()
    actual_database_list=sqlite_driver.db.execute_sql('pragma database_list').fetchall()
    if Path(actual_database_list[0][2]).resolve()!=(DATA/'daily.sqlite').resolve():raise ValueError('actual_database_binding_mismatch')
    dump(out/'actual_database_binding.json',dict(database_list=actual_database_list,expected=str(DATA/'daily.sqlite')))
    import contract_metadata as cm
    cm.ALL_FUTURES_CONTRACT_METADATA_PATH=DATA/'metadata.csv'
    import replay_audit_helpers as audit
    from qmt_roll_official_strategy_material_resolver import load_active_material_release,assert_runtime_materials_match_checkout,verify_material_file
    active=load_active_material_release(ROOT/'official_strategy_materials/CURRENT.json',repo_root=ROOT)
    accepted=json.loads((SOURCE/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/accepted_common_patch_manifest.json').read_text())
    for name,digest in accepted['source_files'].items():
        if sha(ROOT/name)!=digest:raise ValueError('source_changed:'+name)
    for row in active.manifest['files']:
        name=str(row.get('source_path',''))
        if row.get('role') not in {'runtime_code','strategy_config','operational_config'} or name.startswith('promotion_source:') or name in audit.ALLOWED_PATCHES or name=='skills/futures-live-execution-sop/SKILL.md':continue
        verify_material_file(ROOT/name,row)
    import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
    import main_contract_mapping as mm
    from weekly_adapter import completed_weeks,weekly_strategy_class
    mapping=DATA/'mapping.csv'
    original_overrides=s901.build_official_live_strategy_overrides
    def overrides():
        result={**original_overrides(),'mapping_csv_path':str(mapping)}
        if args.arm=='F':result['product_universe_csv_path']=str(DATA/'universe.csv')
        if args.arm in {'E','F'}:result.update(enable_stage847_half_r_stop_retry=False,enable_stage827_intraday_c2_stop=False,enable_ai_product_pool_filter=False)
        return result
    from stage005_sessions import install_open_anchor_adapter
    install_open_anchor_adapter(overrides())
    s901.build_official_live_strategy_overrides=overrides
    s901.ALL_FUTURES_MAPPING_PATH=mapping
    products=mm.load_product_universe_symbols(overrides()['product_universe_csv_path'])
    metadata=mm.build_contract_metadata(mapping_path=mapping,supported_symbols=products)
    calendar=sorted(pd.read_csv(mapping).date.unique())
    weeks=completed_weeks(calendar)
    engines=[];original_engine=s901.s847.Stage847StopRetryEngine
    class Engine(original_engine):
        def __init__(self,*a,**kw):super().__init__(*a,**kw);engines.append(self)
    s901.s847.Stage847StopRetryEngine=Engine
    original_profile=s901.s847._c9_profile
    if args.arm in {'E','F'}:
        def profile(metadata):
            p=dict(original_profile(metadata));p['strategy_cls']=weekly_strategy_class(p['strategy_cls'],weeks);return p
        s901.s847._c9_profile=profile
    s901.s847.QmtRollPortfolioStrategyStage847C9StopRetry.stage827_require_complete_minutes=True
    inputs={str(p):sha(p) for p in [DATA/'daily.sqlite',mapping,s901.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,s901.s861.FULL_MINUTE_BARS_PATH,DATA/'metadata.csv',DATA/'universe.csv',DATA/'completed_manifest.json',*Path(__file__).parent.glob('*.py')]}
    for receipt in json.loads((DATA/'daily_download_progress.json').read_text()):
        if receipt.get('status')!='complete':continue
        path=receipt['raw_path'];digest=receipt['raw_sha256']
        if sha(path)!=digest:raise ValueError('daily_raw_source_changed:'+path)
        inputs[path]=digest
    inputs[str(DATA/'daily_download_progress.json')]=sha(DATA/'daily_download_progress.json')
    sys.path.append('/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/tools')
    from stage249_prepare_replay import verify_patch
    original_minute_loader=s901._load_stage861_full_minute_bars
    proofs=sorted((LINE/'outputs/minute_probe').glob('*_proof.json'))+sorted((LINE/'outputs/minute_patches').glob('*/*_proof.json'))+sorted((LINE/'outputs/stage003_minute_patches').glob('*/*_proof.json'))+sorted((LINE/'outputs/stage005_minute_patches').glob('*/*_proof.json'))
    minute_patches=[]
    for proof in proofs:
        parquet=proof.with_name(proof.name.replace('_proof.json','.parquet'))
        verified=verify_patch(parquet,proof)
        inputs[str(parquet)]=sha(parquet);inputs[str(proof)]=sha(proof)
        raw=Path(verified['source']['raw_path'])
        if sha(raw)!=verified['source']['source_sha256']:raise ValueError('patch_raw_source_changed')
        inputs[str(raw)]=sha(raw);minute_patches.append(parquet)
    def augmented_loader(symbols):
        data=original_minute_loader(symbols)
        values=['open','high','low','close','volume','open_oi','close_oi']
        for parquet in minute_patches:
            patch=pd.read_parquet(parquet);patch=patch.loc[patch.vt_symbol.isin(symbols)].copy()
            patch['bar_datetime']=pd.to_datetime(patch.bar_datetime);patch['bar_date']=pd.to_datetime(patch.bar_date)
            existing=data.set_index(['vt_symbol','bar_datetime'])
            new=patch.set_index(['vt_symbol','bar_datetime'])
            common=existing.index.intersection(new.index)
            if len(common):
                import numpy as np
                a=existing.loc[common,values].to_numpy(float);b=new.loc[common,values].to_numpy(float)
                if not np.allclose(a,b,rtol=0,atol=1e-8):raise ValueError('completed_minute_source_overlap_conflict:'+str(parquet))
            patch=patch.loc[~pd.MultiIndex.from_frame(patch[['vt_symbol','bar_datetime']]).isin(existing.index)]
            data=pd.concat([data,patch],ignore_index=True)
        if data.duplicated(['vt_symbol','bar_datetime']).any():raise ValueError('overlay_duplicate_minute')
        return data.sort_values(['vt_symbol','bar_datetime']).reset_index(drop=True)
    catalog_root=LINE/'outputs/stage003_anchor_catalog'
    catalog_manifest=json.loads((catalog_root/'manifest.json').read_text())
    if not catalog_manifest['source_files_unchanged'] or sha(catalog_root/'catalog.csv')!=catalog_manifest['catalog_sha256']:raise ValueError('anchor_catalog_changed')
    for path,digest in catalog_manifest['source_files'].items():
        if sha(path)!=digest:raise ValueError('catalog_source_changed:'+path)
        inputs[path]=digest
    inputs[str(catalog_root/'catalog.csv')]=sha(catalog_root/'catalog.csv');inputs[str(catalog_root/'manifest.json')]=sha(catalog_root/'manifest.json')
    def catalog_loader(symbols):
        data=augmented_loader(symbols)
        catalog=pd.read_csv(catalog_root/'catalog.csv');catalog=catalog.loc[catalog.vt_symbol.isin(symbols)].copy()
        catalog['bar_datetime']=pd.to_datetime(catalog.bar_datetime);catalog['bar_date']=pd.to_datetime(catalog.bar_date)
        old=pd.MultiIndex.from_frame(data[['vt_symbol','bar_datetime']]);new=pd.MultiIndex.from_frame(catalog[['vt_symbol','bar_datetime']])
        # Existing immutable cache has priority. Catalog only supplies previously missing keys.
        catalog=catalog.loc[~new.isin(old)]
        data=pd.concat([data,catalog],ignore_index=True)
        if data.duplicated(['vt_symbol','bar_datetime']).any():raise ValueError('anchor_catalog_duplicate')
        return data.sort_values(['vt_symbol','bar_datetime']).reset_index(drop=True)
    s901._load_stage861_full_minute_bars=catalog_loader
    # Pin all legacy proxy CSV/JSON inputs, not just the principal minute file.
    historical=json.loads((SOURCE/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/C_final/input_manifest.json').read_text())
    for name,digest in historical.items():
        if name=='.vntrader/database.db':continue
        path=SOURCE/name
        if sha(path)!=digest:raise ValueError('historical_input_changed:'+name)
        inputs[str(path)]=digest
    dump(out/'input_manifest.json',inputs)
    dump(out/'preflight.json',dict(identity=identity,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),arm=args.arm,
        start='2020-01-01',end='2026-10-22',strict_minutes=True,source_files=accepted['source_files'],
        requested_changes=['full market 91 product families, no AI selection' if args.arm=='F' else 'same-data original 19 control'],universe_products=products,universe_product_count=len(products),
        preserved=['canonical first-minute execution anchor','daily mark and execution','daily extreme risk stops','capital 150000','41 observed bars','target_contract_only','original 19 control or full91 predeclared universe'],
        python=sys.executable,production_qualified=False,send_order_api_called_count=0,cancel_order_api_called_count=0))
    started=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();state='failed';err=None;captured={};actual=[]
    try:
        with audit.capture_actual_settings(Engine) as actual,audit.capture_execution_proxy_usage(Engine) as captured:
            combined,frames,spec=s901._run_live_c9(metadata,pd.Timestamp('2020-01-01'),pd.Timestamp('2026-10-22'))
        if len(actual)!=1 or actual[0]['actual']['enable_stage847_half_r_stop_retry'] is not False:raise ValueError('half_r_flag_mismatch')
        if actual[0]['actual']['enable_stage827_intraday_c2_stop'] or actual[0]['actual']['enable_ai_product_pool_filter']:raise ValueError('C2_or_AI_not_disabled')
        if engines[0].strategy.ai_product_pool_load_status!='disabled' or engines[0].strategy.ai_product_pool_eval_dates:raise ValueError('AI_was_loaded')
        if captured['minute_requests'] or not frames['intraday_events'].empty or not frames['stop_retry_events'].empty or not frames['c2_events'].empty:raise ValueError('disabled_intraday_module_produced_events')
        clock=audit.canonical_trade_enums(pd.DataFrame(captured['trades']))
        frames['trades']=audit.attach_trading_dates(audit.canonical_trade_enums(frames['trades']),clock)
        scope='weekly_half_r_c2_ai_off_'+('full91' if args.arm=='F' else 'same_data_original19')
        for name,frame in [('daily',combined),*frames.items(),('execution_clock',clock),('internal_equity_daily',pd.DataFrame(captured['equity'])),('execution_proxy_usage',pd.DataFrame(captured['usage'])),('minute_scan_requests',pd.DataFrame(captured['minute_requests']))]:
            if not len(frame.columns):frame=pd.DataFrame(columns=['date','vt_symbol','event','reason'])
            frame['result_scope']=scope;frame['profile']='research_'+args.arm
            frame.to_csv(out/(name+'.csv'),index=False)
        dump(out/'effective_parameters.json',s901._json_safe(dict(spec=asdict(spec),sizes=metadata['sizes'],slippages=metadata['slippages'],rates=metadata['rates'])))
        metrics=s901.s650._metrics(combined,spec.capital,1.)
        metrics.update(arm=args.arm,result_scope=scope,start='2020-01-01',end='2026-10-22',actual_start=str(combined.date.min())[:10],actual_end=str(combined.date.max())[:10],production_qualified=False)
        if args.arm in {'E','F'}:
            strategy=engines[0].strategy
            pd.DataFrame(strategy.weekly_readiness).to_csv(out/'weekly_readiness.csv',index=False)
            pd.DataFrame([dict(vt_symbol=s,**row) for s,am in strategy.ams.items() for row in am.completed]).to_csv(out/'weekly_bars.csv',index=False)
            dump(out/'weekly_coverage.json',dict(symbols=len(strategy.ams),max_week_count=max(am.max_count for am in strategy.ams.values()),
                symbols_ever_ready=sum(am.max_count>=am.size for am in strategy.ams.values()),rejected_incomplete_weeks=sum(len(am.rejected) for am in strategy.ams.values())))
        # Accept no stale held/traded day. Source dates were snapshotted independently.
        from daily_coverage import daily_coverage_gaps
        with sqlite3.connect(f'file:{DATA/"daily.sqlite"}?mode=ro',uri=True) as db:gaps=daily_coverage_gaps(frames['positions'].to_dict('records'),db)
        zero_volume=[]
        with sqlite3.connect(f'file:{DATA/"daily.sqlite"}?mode=ro',uri=True) as db:
            for row in frames['positions'].to_dict('records'):
                if not any(float(row[k]) for k in ['start_pos','end_pos','trade_count']):continue
                code,exchange=row['vt_symbol'].split('.')
                volume=db.execute("select volume from dbbardata where symbol=? and exchange=? and interval='d' and substr(datetime,1,10)=?",(code,exchange,str(row['date'])[:10])).fetchone()
                if volume is None or not float(volume[0])>0:zero_volume.append(dict(vt_symbol=row['vt_symbol'],date=str(row['date'])[:10],volume=None if volume is None else volume[0]))
        dump(out/'data_quality.json',dict(held_or_traded_daily_gaps=gaps,held_or_traded_zero_volume=zero_volume,captured_bar_failures=captured['failures']))
        if zero_volume:raise ValueError('held_or_traded_daily_zero_volume')
        if gaps:raise ValueError('held_or_traded_daily_coverage_missing')
        dump(out/'metrics.json',s901._json_safe(metrics))
        state='completed_pending_independent_review'
    except BaseException as e:
        err=repr(e);raise
    finally:
        dump(out/'actual_strategy_settings.json',s901._json_safe(actual))
        dump(out/'execution_audit.json',captured)
        if args.arm in {'E','F'} and engines:
            strategy=engines[0].strategy
            pd.DataFrame(strategy.weekly_readiness).to_csv(out/'weekly_readiness_on_exit.csv',index=False)
            dump(out/'weekly_coverage_on_exit.json',dict(symbols=len(strategy.ams),max_week_count=max(am.max_count for am in strategy.ams.values()),symbols_ever_ready=sum(am.max_count>=am.size for am in strategy.ams.values()),rejected_incomplete_weeks=sum(len(am.rejected) for am in strategy.ams.values())))
        bad=[p for p,digest in inputs.items() if sha(p)!=digest]
        dump(out/'postflight.json',dict(inputs_unchanged=not bad,mismatches=bad))
        if bad:state='rejected_input_changed'
        dump(out/'terminal.json',dict(status=state,error=err,started_at=started,completed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),production_qualified=False,order_api_count=0))
    print(json.dumps(s901._json_safe(metrics),ensure_ascii=False))
if __name__=='__main__':main()
