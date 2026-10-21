"""Tail-only: inherit eight completed cash audits, never reread native/old flows.

Closes exported annual/family/samebook tables, original paired CI and dual gate,
and B/C economic equivalence/unique chosen-month cash bridge. No fit or replay.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.util
import io
import json
from pathlib import Path
import time
import traceback
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('tail500_pure',TOOLS/'stage500_member_identity_cash_review.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
LINE=v.LINE
CORE_SHA='b450b36cf42ac60293009fbaeb5582907cc55579263ec6d79b4d876b42d4fd42'
BOOKS_SHA='2e4f360d173dcb82d4360c88e93adfcf8475617e5d25daad9d5f9714c56b439d'


def source_bundle():
    return sorted([v.binding(TOOLS/name) for name in [Path(__file__).name,
        'test_stage500_member_identity_tail_review.py','stage500_member_identity_cash_review.py']],key=lambda b:b['path'])


def canonical_ids(protocol):
    controls=protocol['cash_contract_inherited_exact']['control_accounts_reused'];result={}
    for c in controls:
        assert c['account_id']=='NARROW_VOLUNTARY_RESELECT_'+c['window']+'_'+c['cost']
        assert 'stage157_voluntary_cash' in c['directory']
        result['A',c['window'],c['cost']]=c['account_id']
    assert len(result)==4
    for arm in v.ARMS:
        for window in v.WINDOWS:
            for cost in v.COSTS:result[arm,window,cost]=f'NARROW_{arm}_{window}_{cost}'
    return result


def compare_fields(actual,expected,label):
    for field,val in expected.items():
        if val is None:assert actual[field]=='',(label,field,'null')
        elif isinstance(val,(bool,str)):assert str(actual[field]).lower()==str(val).lower(),(label,field)
        else:v.compare(float(actual[field]),val,label+'.'+field)


def daily_logs(frame):
    path=np.r_[1000000.,frame.equity.to_numpy(float)]
    unknown=frame.ever_insolvent.astype(str).str.lower().isin(['true','1']).any()
    return None if unknown or not np.isfinite(path).all() or (path<=0).any() else np.log(path[1:]/path[:-1])


def cash_equivalence(r,root,daily,ids):
    report=[]
    for window in v.WINDOWS:
        for cost in v.COSTS:
            left,right=(v.ARMS[0],window,cost),(v.ARMS[1],window,cost)
            da,db=daily[left],daily[right];assert da.date.tolist()==db.date.tolist()
            a=r.path_table(root/ids[left]/'fills.csv.gz');b=r.path_table(root/ids[right]/'fills.csv.gz')
            fields=['event_id','epoch','date','side','reason']
            def align(frame):
                frame=frame.copy();frame['_occurrence']=frame.groupby(fields,sort=False).cumcount()
                return frame.set_index(fields+['_occurrence']).sort_index()
            a,b=align(a),align(b);identity=a.index.tolist()==b.index.tolist();qty=False;differences={}
            if identity:
                qty=np.array_equal(pd.to_numeric(a.qty).to_numpy(float),pd.to_numeric(b.qty).to_numpy(float))
                for col in ['reference_price','fill_price','fee','slippage','realized_gross']:
                    d=np.abs(pd.to_numeric(a[col]).to_numpy(float)-pd.to_numeric(b[col]).to_numpy(float));differences[col]=float(d.max()) if len(d) else 0.
            equity=float(np.max(np.abs(da.equity.to_numpy(float)-db.equity.to_numpy(float))))
            growth=float(np.max(np.abs(np.diff(np.r_[1000000.,da.equity.to_numpy(float)])-np.diff(np.r_[1000000.,db.equity.to_numpy(float)]))))
            report.append(dict(window=window,cost=cost,fill_identity_order_ignored_equal=identity,filled_qty_exact_equal=bool(qty),
                fill_identity_fields=fields+['_occurrence'],fill_counts=[len(a),len(b)],max_abs_fill_money_differences=differences,
                max_daily_equity_abs_difference=equity,max_daily_equity_growth_amount_abs_difference=growth,
                economic_equivalent_at_RMB_1e_8=bool(identity and qty and all(x<=1e-8 for x in differences.values()) and equity<=1e-8),
                account_prefix_not_an_economic_ID=True,float_lastbit_not_alpha=True))
    return report


def choice_cash_bridge(r,h,root,ids):
    choices={a:r.table(h['arms'][a]['choices_main_binding']) for a in v.ARMS}
    a,b=choices[v.ARMS[0]],choices[v.ARMS[1]]
    assert len(a)==len(b)==161014 and a.event_id.tolist()==b.event_id.tolist()
    changed=a.chosen_action_id.ne(b.chosen_action_id);rows=[]
    for pos in np.flatnonzero(changed.to_numpy()):
        aa,bb=a.iloc[pos],b.iloc[pos]
        event=dict(mother_event_id=aa.event_id,u_date=aa.u_date,product_id=aa.product_id,
            B_chosen_action_id=aa.chosen_action_id,C_chosen_action_id=bb.chosen_action_id,
            B_chosen_epoch=aa.chosen_epoch,C_chosen_epoch=bb.chosen_epoch,accounts=[])
        for window in v.WINDOWS:
            for cost in v.COSTS:
                for arm,choice in [(v.ARMS[0],aa),(v.ARMS[1],bb)]:
                    folder=root/ids[arm,window,cost];budgets=r.path_table(folder/'reservations.csv.gz');fills=r.path_table(folder/'fills.csv.gz')
                    budgets=budgets.loc[budgets.event_id.eq(choice.chosen_action_id)];fills=fills.loc[fills.event_id.eq(choice.chosen_action_id)]
                    event['accounts'].append(dict(arm=arm,window=window,cost=cost,
                        budgets=budgets[[c for c in ['budget_id','budget_kind','budget_state','D_state','D_qty','qty_cap','u_date','execution_date'] if c in budgets]].to_dict('records'),
                        fill_rows=len(fills),filled_qty=float(pd.to_numeric(fills.qty).sum())))
        rows.append(event)
    return dict(changed_main_choices=int(changed.sum()),selected_flag_changes=int(a.selected.ne(b.selected).sum()),rows=rows,
        only_existing_derived_new_choices_and_ledgers=True,argmax_recomputed=False,source_model_validation_separate498=True)


def review(r,p,h,cm,core,books,out):
    root=Path(cm['terminal']['path']).parent;ids=canonical_ids(p)
    summaries=r.path_table(root/'account_summaries.csv.gz');assert len(summaries)==12
    reports=r.path_doc(root/'diagnostics.json');daily={};metrics={}
    for key,name in ids.items():
        part=summaries.loc[summaries.arm.eq(key[0])&summaries.window.eq(key[1])&summaries.cost.eq(key[2])];assert len(part)==1
        row=part.iloc[0];assert row.account_id==name
        summary={k:None if row[k]=='' else float(row[k]) for k in ['ending_equity','total_return_pct','max_drawdown_pct','sharpe','fills']}
        summary['account_id']=name;metrics[key]=summary
        if key[0]=='A':
            c=next(c for c in p['cash_contract_inherited_exact']['control_accounts_reused'] if c['window']==key[1] and c['cost']==key[2]);b=c['ledgers_relative_to_directory']['daily']
            frame=r.table(dict(path=str(Path(c['directory'])/b['file']),bytes=b['bytes'],sha256=b['sha256']))
        else:frame=r.path_table(root/name/'daily.csv.gz')
        v.number(frame,['equity']);daily[key]=frame
    annual=r.path_table(root/'annual_slices.csv.gz');paired_annual=r.path_table(root/'paired_annual.csv.gz')
    expected_annual_rows=0
    for key,name in ids.items():
        expected=reports[name]['annual_slices'];expected_annual_rows+=len(expected)
        saved=annual.loc[annual.account_id.eq(name)].sort_values('year');assert len(saved)==len(expected)
        for actual,wanted in zip(saved.to_dict('records'),expected):compare_fields(actual,wanted,'annual '+name)
    assert len(annual)==expected_annual_rows
    v.write(out/'annual_export_phase.json',dict(accounts=12,rows=expected_annual_rows,source='core verified diagnostics; old A canonical identity from495 not summary display field',core_annual_arithmetic_not_rerun=True))
    through=r.path_table(root/'same_book_through_2025.csv.gz');assert len(through)==12
    for row in through.to_dict('records'):
        key=row['arm'],row['window'],row['cost'];assert row['account_id']==ids[key]
        d=daily[key].loc[daily[key].date.le('2025-12-31')];path=np.r_[1000000.,d.equity.to_numpy(float)]
        v.compare([float(row['ending_equity']),float(row['total_return_pct']),float(row['max_drawdown_pct'])],
            [path[-1],(path[-1]/1000000.-1)*100,(path/np.maximum.accumulate(path)-1).min()*100],'samebooks2025')
        assert row['new_account'].lower()==row['capital_reset'].lower()==row['year_end_liquidation'].lower()=='false'
    v.write(out/'samebook_export_phase.json',dict(accounts=12,new_accounts=0,capital_resets=0,source='same saved daily curves, no liquidation'))
    fy=r.path_table(root/'family_year_including_zero.csv.gz');totals=r.path_table(root/'family_total_including_zero.csv.gz')
    keys=['arm','window','cost','family_id'];cols=['net_equity_contribution','fee','slippage','fill_count','filled_qty']
    v.number(fy,cols);v.number(totals,cols);a=fy.groupby(keys)[cols].sum().sort_index();b=totals.set_index(keys).sort_index()
    assert a.index.tolist()==b.index.tolist() and len(b)==12*95
    for col in cols:v.compare(b[col],a[col],'family export totals '+col)
    v.write(out/'family_export_phase.json',dict(own_family_year_cash_checks_inherited=True,total_grid_rows=len(b),families=95,accounts=12,core_family_arithmetic_not_rerun=True))
    indices={w:np.load(io.BytesIO(r.read(b)),allow_pickle=False) for w,b in p['statistics']['bootstrap_indices'].items()}
    comp=r.path_table(root/'comparisons.csv.gz');distributions=r.path_table(root/'bootstrap_distributions.csv.gz');assert len(comp)==12 and len(distributions)==2000
    decision=r.path_doc(root/'decision.json');held=r.doc(h['held_gate_binding'])['contrasts'];gates={};points={}
    stale=any(x['stale_days']>0 for x in reports.values())
    # Verified account summary/capacity semantics are inherited; only saved gate inputs read.
    flags=summaries.execution_unknown.astype(str).str.lower();assert flags.isin(['true','false','1','0']).all()
    unknown=flags.isin(['true','1']).any();wealth=all(daily_logs(d) is not None for d in daily.values())
    for contrast,(active,baseline) in v.CONTRASTS.items():
        points[contrast]=[]
        for window in v.WINDOWS:
            for cost in v.COSTS:
                sa,sb=metrics[active,window,cost],metrics[baseline,window,cost]
                stats,draw=v.paired(daily[active,window,cost],daily[baseline,window,cost],indices[window])
                saved=comp.loc[comp.contrast.eq(contrast)&comp.window.eq(window)&comp.cost.eq(cost)];assert len(saved)==1;s=saved.iloc[0]
                q=dict(contrast=contrast,window=window,cost=cost,active_total_return_pct=sa['total_return_pct'],reference_total_return_pct=sb['total_return_pct'],
                    ending_equity_difference=sa['ending_equity']-sb['ending_equity'],return_percentage_point_difference=sa['total_return_pct']-sb['total_return_pct'],
                    drawdown_percentage_point_difference=None if sb['fills']==0 else sa['max_drawdown_pct']-sb['max_drawdown_pct'],
                    **(stats or dict(ci95_low=None,ci95_high=None,mean_daily_log_difference=None,cumulative_log_difference=None)))
                compare_fields(s,q,'paired '+contrast)
                obs=pd.to_numeric(distributions[contrast+'_'+window+'_'+cost].replace('',np.nan));v.compare(obs,draw,'all2000 draws '+contrast+' '+window+' '+cost,1e-12,1e-10)
                points[contrast].append(q)
                ar={x['year']:x for x in reports[sa['account_id']]['annual_slices']};br={x['year']:x for x in reports[sb['account_id']]['annual_slices']}
                py=paired_annual.loc[paired_annual.contrast.eq(contrast)&paired_annual.window.eq(window)&paired_annual.cost.eq(cost)];assert len(py)==len(ar)
                for row in py.to_dict('records'):
                    aa,bb=ar[row['year']],br[row['year']]
                    for field,col in [('return_percentage_point_difference','return_pct'),('growth_amount_difference','cash_growth'),('drawdown_percentage_point_difference','max_drawdown_pct')]:v.compare(float(row[field]),aa[col]-bb[col],'paired annual '+field)
                v.write(out/('CI_'+contrast+'_'+window+'_'+cost+'_phase.json'),dict(point=q,draws_checked=2000,original_indices_reused=True))
        gates[contrast]=v.gate(points[contrast],held[contrast],wealth=wealth,stale=stale,execution_unknown=unknown)
        for field in ['nominal_pass','cash_nominal_pass','held_known_nominal_pass']:assert decision['contrasts'][contrast][field]==gates[contrast][field]
    assert decision['nominal_pass']==(gates['C_minus_A']['nominal_pass'] and gates['C_minus_B']['nominal_pass'])
    for flag in ['alpha_proved','causal_identification','historical_first_seen_PIT_proved','full_market_mechanism_proved','member_is_end_investor_proved','legal_member_identity_continuity_proved','increased_betting_qualified','production_qualified','goal_complete']:assert decision[flag] is False
    v.write(out/'paired_gate_phase.json',dict(points=points,gates=gates,nominal_pass=decision['nominal_pass'],draws_per_cell=2000,original_block_length=252,CI_conditional_not_blind=True))
    equivalent=cash_equivalence(r,root,daily,ids);v.write(out/'C_minus_B_economic_equivalence.json',equivalent)
    bridge=choice_cash_bridge(r,h,root,ids);v.write(out/'C_minus_B_choice_cash_link.json',bridge)
    return dict(inherited_core_accounts=8,core_counts=core['counts'],tail_completed=True,annual_export_rows=expected_annual_rows,
        samebook_accounts=12,family_total_rows=len(b),paired_CI_cells=12,draws_each=2000,nominal_pass=decision['nominal_pass'],gates=gates,
        C_minus_B_economic_equivalence=equivalent,C_minus_B_choice_cash_link=bridge,
        source_model_held_argmax_scope_not_repeated=True,source_model_held_review_separate498=True,
        native_cache_reads=0,native_SQL=0,predictive_fits=0,strategy_cash_replays=0,core_account_reviews_repeated=0)


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['protocol','handoff','cash-manifest','core-receipt','all-books-phase','authorization']:
        ap.add_argument('--'+name,required=True);ap.add_argument('--'+name+'-sha256',required=True)
    ap.add_argument('--output',required=True);args=ap.parse_args(argv)
    out=Path(args.output).resolve();assert LINE/'outputs/stage500_member_identity_cash_review' in out.parents and not out.exists()
    r=v.Reader();docs={};bindings={}
    for name in ['protocol','handoff','cash_manifest','core_receipt','all_books_phase','authorization']:
        b=v.binding(getattr(args,name));assert b['sha256']==getattr(args,name+'_sha256');bindings[name]=b;docs[name]=r.doc(b)
    p,h,cm,core,books,auth=(docs[k] for k in ['protocol','handoff','cash_manifest','core_receipt','all_books_phase','authorization'])
    assert bindings['protocol']['sha256']==v.PROTOCOL_SHA and bindings['core_receipt']['sha256']==CORE_SHA and bindings['all_books_phase']['sha256']==BOOKS_SHA
    assert core['core_cash_accounts_completed']==8 and core['core_material_findings']==dict(P0=0,P1=0,P2=0) and core['complete_cash_review'] is False
    assert books['new_books']==8 and len(books['accounts'])==8 and v.same(core['all_books_phase'],bindings['all_books_phase'])
    bundle=source_bundle();expected=dict(schema='stage500_exact_root_tail_review_authorization_v1',authorized_by='root',stage='tail_only',
        protocol_sha256=v.PROTOCOL_SHA,output=str(out),actual_run_limit=1,max_native_cache_reads=0,max_native_SQL=0,max_fit=0,max_strategy_cash_replays=0,max_core_account_reviews=0)
    assert all(auth.get(k)==value for k,value in expected.items())
    for key in ['handoff','cash_manifest','core_receipt','all_books_phase']:assert v.same(auth[key+'_binding'],bindings[key])
    assert auth['source_bundle']==bundle and v.same(h['protocol_binding'],bindings['protocol']) and cm['status']=='completed'
    assert v.same(cm['metadata']['handoff'],bindings['handoff']) and v.same(cm['metadata']['protocol'],bindings['protocol'])
    r.register(cm['artifacts']);out.mkdir(parents=True);start=time.monotonic();status='failed';error=None
    v.write(out/'started.json',dict(bindings=bindings,source_bundle=bundle,started_at=datetime.now(timezone.utc).isoformat(),tail_only=True,core8_audit_checkpoint_inherited=True))
    try:
        result=review(r,p,h,cm,core,books,out)
        # Bounded completeness means requested tables only; no unused raw books/cache sweeps.
        assert source_bundle()==bundle
        forbidden=['native_store_cache','common26.npz','child_scores.csv','stage129_contract_choice_dataset','normalized_scopes']
        assert not any(any(token in path for token in forbidden) for path in r.reads)
        receipt=dict(schema='stage500_member_identity_final_cash_review_v1',completed_cash_scope=True,completed_model_source_scope=False,
            inherited_core_receipt=bindings['core_receipt'],inherited_all_books_phase=bindings['all_books_phase'],tail=result,
            cash_scope_material_findings=dict(P0=0,P1=0,P2=0),current_reads_by_path=dict(r.reads),tail_max_abs_errors=v.ERRORS,
            cumulative_native_cache_reads=2,current_native_cache_reads=0,current_core_replays=0,original_Y_COMMON_scores156_source_reads=0,
            current_fit=0,current_strategy_cash_replays=0,current_native_SQL=0,source_model_held_argmax_must_be_combined_separately=True,
            two_previous_reviewer_failures_preserved=True,historical_adaptive_CI_not_blind=True,alpha_proved=False,
            increased_betting_qualified=False,production_qualified=False,goal_complete=False)
        v.write(out/'review_receipt.json',receipt);status='completed';print(json.dumps(dict(status=status,output=str(out),cash_scope_P0=0,P1=0,P2=0)),flush=True)
    except BaseException as exc:
        error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc());v.write(out/'failure.json',error);raise
    finally:v.write(out/'terminal.json',dict(status=status,elapsed_seconds=time.monotonic()-start,error=error,reads_by_path=dict(r.reads),
        native_cache_reads=0,native_SQL=0,fit=0,strategy_cash_replays=0,core_account_reviews=0,automatic_retry=False))


if __name__=='__main__':main()
