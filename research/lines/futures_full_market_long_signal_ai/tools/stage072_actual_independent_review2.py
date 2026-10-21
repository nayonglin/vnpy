"""One complete saved-artifact audit, not a new fit/cash run or native replay."""
import os
for key in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS']:
    os.environ[key]='1'
import argparse,hashlib,io,json,time,traceback
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from stage072_actual_cash_adapter import bound,compare,numeric,csv,review_account,ERRORS
from stage072_actual_fit_checks import table,label_checks,check_fits
from stage072_actual_native_checks import review_native
from stage072_actual_cash_diagnostics import review_cash_diagnostics

LINE=Path(__file__).resolve().parents[1]
EXPECTED={
    'labels':('outputs/stage070_narrow_policy_cash/labels/manifest.json','23fcf336abc9b9a2a405f5372333264bb82c03e8e82409310c66ed7c423f748a'),
    'fit':('outputs/stage071_settlement_narrow_fit/experiment/manifest.json','c4e4fd57d647553ab6ee69b8e433ecef1f6444800afdbce7a729ec5e29acb4a1'),
    'cash':('outputs/stage070_narrow_policy_cash/cash/manifest.json','a75a8ac21d3ef9dc03914a4825be54d64085e0d8e79496f7fdab66275f8f9b03')}
HELPERS=['stage072_actual_independent_review2.py','stage072_actual_fit_checks.py','stage072_actual_native_checks.py',
         'stage072_actual_cash_adapter.py','stage072_actual_cash_core.py','stage072_actual_cash_diagnostics.py']

def bind(path):
    path=Path(path).resolve();raw=path.read_bytes()
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def safe(value):
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [safe(v) for v in value]
    if isinstance(value,np.generic):return value.item()
    return value

def write(path,value):
    with path.open('x') as stream:json.dump(safe(value),stream,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);stream.write('\n')

def progress(out,name,value):
    write(out/(name+'.json'),value);print(json.dumps({'phase':name,'completed':True},ensure_ascii=False),flush=True)

def validate_fit_root_chain(manifest,authorization,execution,manifest_binding,output):
    """071 omits top-level authorization; root persisted the exact separate chain."""
    assert authorization['schema']=='stage069_exact_root_authorization_v1'
    assert authorization['stage']=='fit' and authorization['authorized_by']=='root' and authorization['exact_source_authorized'] is True
    assert authorization['protocol_sha256']==manifest['protocol']['sha256']
    assert authorization['output']==output
    assert authorization['input_bindings']==manifest['input_bindings']
    assert sorted(authorization['source_bundle'],key=lambda b:b['path'])==sorted(manifest['source_bundle'],key=lambda b:b['path'])
    assert execution['fit_manifest']==manifest_binding and execution['fit_terminal']==manifest['terminal']
    assert execution['actual_starts']==1 and execution['auto_retries']==0 and execution['exit_code']==0 and execution['session_id']==47352
    assert execution['model_fits_attempted']==execution['model_fits_completed']==12 and execution['native_queries']==execution['new_cash']==0

def closure():
    manifests={};bindings={}
    for role,(name,sha) in EXPECTED.items():
        item=bind(LINE/name);assert item['sha256']==sha,(role,'final manifest SHA')
        m=json.loads(bound(item));assert m['status']=='completed' and m['mode']=='actual'
        bindings[role]=item;manifests[role]=m
        for item in m['source_bundle']:bound(item)
        if role=='fit':
            auth_binding={'path':str(LINE/'outputs/stage069_settlement_narrow_joint_protocol/fit_root_authorization.json'),'bytes':4509,'sha256':'fafc047316d8eb2cd24c9dca19708b842518b3e3c0194f5691d975ac0c770cd0'}
            run_binding={'path':str(LINE/'outputs/stage069_settlement_narrow_joint_protocol/fit_execution_receipt.json'),'bytes':951,'sha256':'a9d455380c8c3236551846898cc99bcb14050b46f187ec7d8a63d8b71780ee51'}
            auth=json.loads(bound(auth_binding));run=json.loads(bound(run_binding))
            validate_fit_root_chain(m,auth,run,bindings[role],str(Path(bindings[role]['path']).parent))
        else:
            bound(m['authorization'])
        terminal=json.loads(bound(m['terminal']))
        assert terminal['status']=='completed' and terminal['exit_code']==0
        artifacts=m['artifacts'].values() if isinstance(m['artifacts'],dict) else m['artifacts']
        for item in artifacts:bound(item)
        assert m['protocol']['sha256']=='0418566cd9b624fb5a985448b3b0d4c94dbef56280feffd49bce09e1c5bf2dde'
    l,f,c=manifests['labels'],manifests['fit'],manifests['cash']
    assert f['actual_fit_calls_completed']==12 and f['prediction_rows']==966084 and f['native_source_queries']==0
    assert c['new_cash_accounts']==24 and c['native_source_queries']==1 and c['actual_model_fit_calls']==0
    assert l['mother_rows']==399252 and l['native_source_queries']==1 and l['actual_model_fit_calls']==0
    assert c['input_bindings']['fit_manifest']==bindings['fit'] and c['input_bindings']['narrow_manifest']==bindings['labels']
    assert c['input_bindings']['predictions']==f['predictions']
    for role in ['wide_labels','narrow_labels']:assert c['input_bindings'][role]==f['input_bindings'][role]
    assert f['input_bindings']['narrow_labels']==l['labels_narrow'] and f['input_bindings']['ohlc_proxy']==l['ohlc_proxy']
    return manifests,bindings

def read_calendar(binding):
    x=np.load(io.BytesIO(bound(binding)),allow_pickle=False)
    if x.dtype.kind in 'iu':return [str(int(v))[:4]+'-'+str(int(v))[4:6]+'-'+str(int(v))[6:8] for v in x]
    return x.astype('datetime64[D]').astype(str).tolist()

def attribution(predictions,fit,books):
    rows=[]
    for policy in ['WIDE','NARROW']:
        for cutoff in ['2020-01-01','2023-01-01']:
            group={a:predictions.loc[predictions.policy.eq(policy)&predictions.cutoff.eq(cutoff)&predictions.arm.eq(a)].set_index('event_id') for a in ['COMMON','SETTLEMENT','OHLC_PROXY']}
            base=group['COMMON']
            for arm,frame in group.items():
                assert frame.index.tolist()==base.index.tolist()
                coef=json.loads((Path(fit['predictions']['path']).parent/'cells'/policy/cutoff/arm/'portable_model.json').read_text())['coef'][-1]
                rows.append(dict(policy=policy,cutoff=cutoff,arm=arm,rows=len(frame),selected=int(frame.selected.sum()),scalar_coefficient=coef,
                    action_disagreements_vs_COMMON=int(frame.selected.ne(base.selected).sum()),
                    max_abs_score_difference_vs_COMMON=float(abs(frame.score-base.score).max()),mean_abs_score_difference_vs_COMMON=float(abs(frame.score-base.score).mean())))
    signatures=[]
    for policy in ['WIDE','NARROW']:
        for w in ['primary_2020','cold_2023']:
            for cost in ['base','stress']:
                a=books[f'{policy}_SETTLEMENT_{w}_{cost}'];b=books[f'{policy}_COMMON_{w}_{cost}']
                # Account/root names differ by construction; compare actual economic transactions.
                columns=['event_id','date','side','qty','reference_price','fill_price','fee','slippage','reason']
                af=pd.read_csv(a/'fills.csv.gz',dtype=str,keep_default_na=False)[columns].reset_index(drop=True)
                bf=pd.read_csv(b/'fills.csv.gz',dtype=str,keep_default_na=False)[columns].reset_index(drop=True)
                signatures.append(dict(policy=policy,window=w,cost=cost,SETTLEMENT_fills=len(af),COMMON_fills=len(bf),exact_economic_fill_signature_equal=af.equals(bf),
                    first_different_row=None if af.equals(bf) else next((i for i in range(min(len(af),len(bf))) if not af.iloc[i].equals(bf.iloc[i])),min(len(af),len(bf)))))
    return {'prediction_activity_and_information_increment':rows,'cash_fill_signature_comparison':signatures}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();sources=[bind(Path(__file__).with_name(n)) for n in HELPERS]
    write(out/'actual_started.json',{'started_at':datetime.now(timezone.utc).isoformat(),'review_startups':1,'sources':sources,'not_a_strategy_run':True})
    try:
        manifests,bindings=closure();l,f,c=[manifests[k] for k in ['labels','fit','cash']]
        progress(out,'final_input_closure',bindings)
        bridge=json.loads(bound(c['input_bindings']['market_protocol']));calendar=read_calendar(bridge['calendar'])
        economics=json.loads(bound(bridge['economic_projection']))['instruments']
        frames={name:table(f['input_bindings'][role]) for name,role in [('WIDE','wide_labels'),('NARROW','narrow_labels')]}
        result=label_checks(frames,calendar,economics);progress(out,'all_labels_checked',result)
        raw=review_native(l['artifacts']['finite_native_cases.json.gz'],'labels')
        cashraw=next(a for a in c['artifacts'] if Path(a['path']).name=='finite_native_cases.json.gz')
        native={'label_cases':raw,'cash_cases':review_native(cashraw,'cash'),'native_sql':0,'full_native_replay':False};progress(out,'finite_native_checked',native)
        mask=bind(LINE/'outputs/stage072_joint_independent_review/source_bounded/research_mask.csv.gz')
        assert mask['sha256']=='9b97774c72db4110fc352d199573c239695bc0d7add98efd659f87cde5e937de'
        predictions,fitreport=check_fits(f,frames,mask,out);progress(out,'all_models_predictions_checked',fitreport)
        cashdir=Path(bindings['cash']['path']).parent;protocol=json.loads(bound(c['protocol']));accounts=[];summaries={};books={}
        for policy,k in [('WIDE',2.),('NARROW',.25)]:
            base=frames[policy].copy()
            base['planned_execution_date']=[calendar[int(u)+1] if int(u)+1<len(calendar) else '' for u in base.u_index]
            for arm in ['COMMON','SETTLEMENT','OHLC_PROXY']:
                selected=predictions.loc[predictions.policy.eq(policy)&predictions.arm.eq(arm),['event_id','score']]
                assert len(selected)==161014 and not selected.event_id.duplicated().any()
                sig=base.merge(selected,on='event_id',how='left',sort=False,validate='one_to_one')
                sig['potential']=(sig.label_history_ready20.eq(1)&sig.score.gt(0)).astype(int)
                sig=sig.set_index('event_id',drop=False)
                for window in protocol['finance']['windows']:
                    for cost in ['base','stress']:
                        name=f"{policy}_{arm}_{window['id']}_{cost}";directory=cashdir/name
                        checked=review_account(directory,cost,window,protocol,sig,economics,calendar,k)
                        accounts.append(checked);summaries[name]=checked['summary'];books[name]=directory
        assert len(accounts)==24;progress(out,'all_cash_ledgers_checked',accounts)
        diag=review_cash_diagnostics(cashdir,summaries);progress(out,'all_cash_diagnostics_CI_gates_checked',diag)
        disclosure=json.loads((cashdir/'budget_and_tick_disclosure.json').read_text())
        for d in disclosure['policy_tick']:
            z=frames[d['policy']];numeric(z,['tick_size']);ready=z.label_history_ready20.eq(1)
            assert d['ready_rows']==int(ready.sum()) and d['known_tick_rows']==int((ready&z.tick_size.gt(0)).sum())
            assert d['stop_distance_below_tick']==int((ready&z.R0_points.lt(z.tick_size)).sum())
        activity=attribution(predictions,f,books);progress(out,'information_attribution',activity)
        receipt={'schema':'stage072_actual_independent_review_v1','completed':True,'C':0,'I':0,'M':0,'input_manifests':bindings,'sources':sources,
            'label_counts':result,'model_fits_reviewed':12,'predictions_reviewed':966084,'cash_accounts_reviewed':24,
            'numeric_max_errors':ERRORS,'independence':{'author_core_imports':0,'model_fits':0,'strategy_replays':0,'native_sql':0,'downloads':0,
                'whole_db_h5_hashes':0,'source067_normalized_four_column_reads':1,'source067_state_review_repeated':False},
            'information_attribution':activity,'nominal_gates':diag['nominal_gates'],'any_historical_stale':diag['any_historical_stale'],
            'computations_accepted_for_research_model_only':True,'alpha_accepted':False,'full_goal_complete':False}
        write(out/'review_receipt.json',receipt)
        write(out/'actual_terminal.json',{'completed':True,'exit_code':0,'review_startups':1,'complete_reviews':1,'elapsed_seconds':time.monotonic()-start,'fit':0,'cash':0,'native_sql':0,'downloads':0})
        print(json.dumps({'completed':True,'C':0,'I':0,'models':12,'predictions':966084,'cash_accounts':24,'elapsed_seconds':time.monotonic()-start}),flush=True)
    except BaseException as error:
        write(out/'actual_terminal.json',{'completed':False,'exit_code':1,'review_startups':1,'complete_reviews':0,'elapsed_seconds':time.monotonic()-start,'error':str(error),'traceback':traceback.format_exc(),'fit':0,'cash':0,'native_sql':0,'downloads':0})
        raise

if __name__=='__main__':main()
