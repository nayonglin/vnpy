"""Fixed059 full-market EIA event cash comparison, root-authorized once.

Pure import/tests do not fit, query native SQL, or run research accounts. Old054
is used only for arm-independent cash diagnostics/logs/native-case extraction;
new EIA actions, arm names, source bindings and comparisons are explicit here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd


LINE=Path(__file__).resolve().parents[1]
PROTOCOL_SHA='ff1ecad21420681e8e1e8645be3da51172d35d4e24ef506ee3f88d2ed5e20158'
PLAN_BINDING=dict(path=str(LINE/'stages/20261018_1508_stage059_eia_full_market_implementation_plan.md'),sha256='e717d8ac9dfc53ff356e6866cb7393e180d629efd6b5e3bd998255e2b8f00677')
MARKET_PROTOCOL_BINDING=dict(path=str(LINE/'outputs/stage052_maturity_information_cash_protocol/protocol.json'),sha256='968fa3505143587950d65fe27db0aa376916b0f005ffc6219b2af880a7e6974c')
EXECUTION_LEDGER_PATH=LINE/'outputs/stage059_eia_full_market_protocol/execution_ledger.json'
HELPER_PATH=Path(__file__).with_name('stage054_maturity_cash_compare.py')
HELPER_SHA='f5f73732747b64b812e48c09202f5d52dcf3f59726e20e05e21ba616453884bd'
KERNEL_SHA='ca40a4cf7b761b34f70d973a943723601d0ecf5fc355da3559d5bcbeff36661d'
if hashlib.sha256(HELPER_PATH.read_bytes()).hexdigest()!=HELPER_SHA:
    raise ValueError('accepted arm-independent054 helper bytes changed')
_spec=importlib.util.spec_from_file_location('stage062_accepted054_helpers',HELPER_PATH)
helpers=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(helpers)
ref=helpers.ref
ARMS=('COMMON_EVENT','INVENTORY','PAST_SHAM')
REFERENCES=('COMMON_EVENT','PAST_SHAM')
OIL_FAMILIES=('INE.SC','INE.LU','SHFE.FU','SHFE.BU')
WINDOWS=(dict(id='primary_2020',start='2020-01-01',end='2026-10-16'),dict(id='cold_2023',start='2023-01-01',end='2026-10-16'))
circular_indices=helpers.circular_indices
daily_log_growth=helpers.daily_log_growth
safe=helpers.safe
write_json=helpers.write_json
SIGNAL_FIELDS=helpers.SIGNAL_FIELDS
PANEL_FIELDS=helpers.PANEL_FIELDS


def file_binding(path,role=None):
    result=ref.file_binding(path)
    if role:
        result.update(role=role,raw_ohlc=False,reproducibility_required=True)
    return result


def read_csv(binding,**kwargs):
    return pd.read_csv(io.BytesIO(ref.read_bound(binding)),compression='gzip' if binding['path'].endswith('.gz') else None,**kwargs)


def load_protocol(path,sha):
    binding=file_binding(path)
    if binding['sha256']!=sha or sha!=PROTOCOL_SHA:
        raise ValueError('fixed059 protocol SHA differs')
    protocol=json.loads(ref.read_bound(binding))
    if protocol['schema']!='stage059_eia_full_market_information_protocol_v1' or protocol['learner']['arms']!=list(ARMS):
        raise ValueError('new059 EIA arm identity differs')
    if protocol['learner']['fit_calls_once']!=6 or protocol['finance']['cash_accounts_once']!=12 or protocol['finance']['family_diagnostics']!=list(OIL_FAMILIES):
        raise ValueError('fixed finite budget/family diagnostics differ')
    if not protocol['finance']['diagnostic_groups_do_not_filter_training_or_trading']:
        raise ValueError('oil diagnosis cannot become a trading filter')
    expected=dict(initial_capital=ref.INITIAL,single_risk=ref.SINGLE_RISK,total_risk=ref.TOTAL_RISK,margin_budget=ref.MARGIN_CAP,margin_buffer=ref.MARGIN_BUFFER)
    if any(protocol['finance'][k]!=v for k,v in expected.items()) or protocol['finance']['cash_kernel_sha256']!=KERNEL_SHA:
        raise ValueError('fixed059 cash risk/kernel differs')
    if file_binding(Path(__file__).with_name('stage042_cross_session_experiment.py'))['sha256']!=KERNEL_SHA:
        raise ValueError('accepted042 kernel changed')
    ref.read_bound(protocol['proposal']);ref.read_bound(PLAN_BINDING)
    market_binding=file_binding(MARKET_PROTOCOL_BINDING['path'])
    if market_binding['sha256']!=MARKET_PROTOCOL_BINDING['sha256']:
        raise ValueError('market/economics-only052 bridge changed')
    market_protocol=json.loads(ref.read_bound(market_binding))
    if market_protocol['accepted_kernel']['sha256']!=KERNEL_SHA:
        raise ValueError('052 market bridge accepted a different cash kernel')
    return protocol,binding,market_protocol,market_binding


def load_fit_manifest(path,sha,protocol_binding):
    binding=file_binding(path)
    if binding['sha256']!=sha:
        raise ValueError('061 final manifest SHA differs')
    fit=json.loads(ref.read_bound(binding))
    if fit['schema']!='stage061_eia_event_fit_v1' or fit['status']!='completed' or fit.get('mode')!='actual':
        raise ValueError('061 actual final manifest required')
    if fit['protocol']!=protocol_binding or fit['actual_fit_calls_started']!=6 or fit['actual_fit_calls_completed']!=6:
        raise ValueError('061 protocol or six-fit terminal differs')
    terminal=json.loads(ref.read_bound(fit['terminal']))
    if terminal['status']!='completed' or terminal['exit_code']!=0 or terminal['actual_fit_calls_started']!=6 or terminal['actual_fit_calls_completed']!=6 or terminal['native_source_queries']!=0 or terminal['new_cash_accounts']!=0:
        raise ValueError('061 terminal must be complete six-fit and zero cash/SQL')
    source=json.loads(ref.read_bound(fit['source_import_manifest']))
    if source['schema']!='stage060_eia_import_manifest_v1' or source['status']!='completed':
        raise ValueError('complete060 source manifest required')
    if source['input_bindings']['protocol']['sha256']!=PROTOCOL_SHA:
        raise ValueError('060 source used a different EIA protocol')
    for key in ('event_map','report_features'):
        if any(fit['inputs'][key][k]!=source['artifacts'][key][k] for k in ('path','bytes','sha256')):
            raise ValueError('061 input differs from060 source '+key)
    return fit,binding,source


def validate_event_metadata(predictions,events):
    if events.u_date.duplicated().any() or events.report_id.duplicated().any():
        raise ValueError('source event map must be unique u/report')
    projected=predictions[['u_date','report_id','is_report_event','external_missing']].drop_duplicates()
    if projected.u_date.duplicated().any():
        raise ValueError('arms/families disagree on shared report timing or missingness')
    check=projected.merge(events[['u_date','report_id','external_missing']],on='u_date',how='left',validate='one_to_one',suffixes=('','_source'),indicator=True)
    event=check._merge.eq('both')
    if not check.is_report_event.eq(event.astype(int)).all():
        raise ValueError('predicted event gate differs from causal060 map')
    if not check.loc[event,'report_id'].eq(check.loc[event,'report_id_source']).all() or not check.loc[event,'external_missing'].eq(check.loc[event,'external_missing_source']).all():
        raise ValueError('report identity/missingness differs from060 source')
    if not check.loc[~event,'report_id'].fillna('').eq('').all() or not check.loc[~event,'external_missing'].eq(1).all():
        raise ValueError('non-event metadata must be common missing/no report')


def make_signals(labels,predictions,arm):
    """The only gate is known report event + u-ready20 + finite positive score."""
    fields=list(dict.fromkeys([c for c in PANEL_FIELDS if c in labels]+SIGNAL_FIELDS))
    base=labels[fields].copy()
    if base.event_id.duplicated().any() or base.duplicated(['product_id','u_date']).any():
        raise ValueError('duplicate full mother identity')
    chosen=predictions.loc[predictions.arm.eq(arm)].copy()
    expected=base.loc[base.u_date.ge('2020-01-01'),'event_id']
    if chosen.event_id.duplicated().any() or set(chosen.event_id)!=set(expected):
        raise ValueError('061 must preserve full2020+ prediction mother')
    identity=chosen.merge(base[['event_id','product_id','family_id','u_date','u_index','label_history_ready20']],on='event_id',validate='one_to_one',suffixes=('','_label'))
    for col in ('product_id','family_id','u_date','u_index'):
        if not identity[col].eq(identity[col+'_label']).all():
            raise ValueError('prediction/u identity differs '+col)
    if not identity.history_ready20.eq(identity.label_history_ready20).all() or not identity.is_report_event.isin([0,1]).all():
        raise ValueError('history readiness/event gate invalid')
    if not np.isfinite(identity.score).all():
        raise ValueError('061 full mother scores must be finite')
    action=identity.is_report_event.eq(1)&identity.label_history_ready20.eq(1)&np.isfinite(identity.score)&identity.score.gt(0)
    if not identity.selected.eq(action.astype(int)).all():
        raise ValueError('061 selected violates all-family report-event action')
    expected_cutoff=np.where(identity.u_date.lt('2023-01-01'),'2020-01-01','2023-01-01')
    if not identity.cutoff.eq(expected_cutoff).all():
        raise ValueError('prediction cutoff violates fixed two forward blocks')
    payload=chosen[['event_id','cutoff','score','is_report_event','report_id','external_missing']]
    result=base.merge(payload,on='event_id',how='left',validate='one_to_one',sort=False)
    result['is_report_event']=result.is_report_event.fillna(0).astype(np.int8)
    result['external_missing']=result.external_missing.fillna(1).astype(np.int8)
    result['report_id']=result.report_id.fillna('')
    result['potential']=(result.is_report_event.eq(1)&result.label_history_ready20.eq(1)&np.isfinite(result.score)&result.score.gt(0)).astype(np.int8)
    result['arm']=arm;result['D_index']=result.u_index+1
    return result


def run_accounts(signals_by_arm,market,dates,economics,*,runner=ref.run_cash_account,execution_kind='actual',counters=None):
    if set(signals_by_arm)!=set(ARMS):
        raise ValueError('new EIA three-arm signal map required')
    if counters is None:
        counters=dict(started=0,computed=0,completed=0)
    for arm in ARMS:
        signal=signals_by_arm[arm];prepared=ref.organize(signal)
        for scenario in ('base','stress'):
            for window in WINDOWS:
                start=int(np.searchsorted(dates,window['start']));end=int(np.searchsorted(dates,window['end'],side='right'))-1
                cell=dict(arm=arm,scenario=scenario,window_id=window['id'],requested_start=window['start'],requested_end=window['end'],
                    source_start=dates[start],source_end=dates[end],source_dates=end-start+1,account_id=arm+'__'+scenario+'__'+window['id'])
                counters['started']+=1
                if execution_kind=='actual':
                    print(json.dumps(dict(phase='cash_started',**cell,started_research_cash_accounts=counters['started'])),flush=True)
                book=runner(signal,market,dates,economics,scenario,cell['account_id'],start,end,ref.INITIAL,prepared)
                counters['computed']+=1
                yield cell,book


def paired_log_statistics(accounts,initial,indices):
    dates=accounts['INVENTORY'].date.tolist()
    if any(accounts[a].date.tolist()!=dates for a in ARMS) or indices.shape[1]!=len(dates):
        raise ValueError('paired source dates/bootstrap width differ')
    logs={};states={}
    for arm in ARMS:
        logs[arm],states[arm]=daily_log_growth(accounts[arm],initial)
    reports={};distributions={}
    for reference in REFERENCES:
        name='INVENTORY_minus_'+reference
        if states['INVENTORY']==states[reference]=='valid':
            difference=logs['INVENTORY']-logs[reference];distribution=difference[indices].mean(axis=1)
            low,high=np.quantile(distribution,[.025,.975])
            reports[name]=dict(status='valid',source_days=len(dates),mean_daily_log_difference=float(difference.mean()),cumulative_log_difference=float(difference.sum()),ci95_low=float(low),ci95_high=float(high))
        else:
            distribution=np.full(len(indices),np.nan)
            reports[name]=dict(status='survival_failure_no_log_repair',source_days=len(dates),mean_daily_log_difference=None,cumulative_log_difference=None,ci95_low=None,ci95_high=None)
        distributions[name]=distribution
    return reports,pd.DataFrame(distributions)


def exposure_signature(book):
    records=[]
    for table,kind,cols in [('open_episodes','terminal_open',['event_id','epoch','qty','entry_fill','last_mark','stale']),
        ('position_days','historical_stale',['event_id','epoch','date','qty','entry_fill','mark']),
        ('closed_episodes','closed_after_unknown_path',['event_id','epoch','entry_date','exit_date','initial_qty','entry_fill','net_pnl'])]:
        frame=pd.DataFrame(book.get(table,[]))
        if frame.empty:
            continue
        if table=='position_days':
            frame=frame.loc[frame.mark_state.eq('stale')]
        elif table=='closed_episodes':
            frame=frame.loc[frame.ever_stale.astype(bool)]
        for row in frame.to_dict('records'):
            records.append(safe(dict(kind=kind,**{c:row.get(c) for c in cols})))
    return sorted(records,key=lambda x:json.dumps(x,sort_keys=True))


def compare_unresolved_exposure(left,right):
    left_signature=exposure_signature(left);right_signature=exposure_signature(right)
    differential=left_signature!=right_signature
    return dict(differential_unresolved_exposure=differential,left_unresolved_records=len(left_signature),right_unresolved_records=len(right_signature),
        left_exposure_sha256=hashlib.sha256(json.dumps(left_signature,sort_keys=True).encode()).hexdigest(),
        right_exposure_sha256=hashlib.sha256(json.dumps(right_signature,sort_keys=True).encode()).hexdigest(),
        finite_R_bound=None,judgment='unknown' if differential else 'same_observed_unresolved_exposure',
        reason='Unresolved/open or historically stale differential exposure has no accepted finite payoff bound; zero-value scenarios are not universal bounds.')


def complete_family_year(family_year,all_families,years):
    index=pd.MultiIndex.from_product([sorted(all_families),sorted(years)],names=['family_id','year'])
    return family_year.set_index(['family_id','year'])[['net_equity_contribution','fee']].reindex(index,fill_value=0.).reset_index()


def oil_group_diagnostics(family_year,all_families):
    frame=family_year.copy()
    frame['diagnostic_group']=np.where(frame.family_id.isin(OIL_FAMILIES),'direct_oil','other_families')
    groups=frame.groupby(['diagnostic_group','year'],sort=True)[['net_equity_contribution','fee']].sum().reset_index()
    totals=frame.groupby('family_id',sort=True)[['net_equity_contribution','fee']].sum().reindex(sorted(all_families),fill_value=0.).reset_index()
    totals['diagnostic_group']=np.where(totals.family_id.isin(OIL_FAMILIES),'direct_oil','other_families')
    winners=totals.loc[totals.net_equity_contribution.gt(0)].sort_values('net_equity_contribution',ascending=False)
    positive=float(winners.net_equity_contribution.sum())
    report=dict(all_families=len(totals),direct_oil_families=list(OIL_FAMILIES),all_families_trade_eligible=True,
        grouping_is_attribution_only=True,strict_family_holdout=False,
        largest_winner=None if winners.empty else safe(winners.iloc[0].to_dict()),
        largest_winner_positive_contribution_share=None if not positive else float(winners.iloc[0].net_equity_contribution/positive),
        top5_positive_contribution_share=None if not positive else float(winners.head(5).net_equity_contribution.sum()/positive),
        caveat='A single family/report concentration supports only a local fact; no universal full-market qualification.')
    return report,groups,totals


def point_comparisons(summaries,daily_accounts,exposures):
    rows=[]
    for scenario in ('base','stress'):
        for window in ('primary_2020','cold_2023'):
            akey=('INVENTORY',scenario,window);a=summaries[akey]
            for reference in REFERENCES:
                bkey=(reference,scenario,window);b=summaries[bkey]
                al,ast=daily_log_growth(daily_accounts[akey],ref.INITIAL);bl,bst=daily_log_growth(daily_accounts[bkey],ref.INITIAL)
                unresolved=compare_unresolved_exposure(exposures[akey],exposures[bkey])
                rows.append(dict(scenario=scenario,window_id=window,contrast='INVENTORY_minus_'+reference,
                    return_percentage_point_difference=a['total_return_pct']-b['total_return_pct'],
                    drawdown_percentage_point_difference=a['max_drawdown_pct']-b['max_drawdown_pct'],
                    cumulative_log_growth_difference=float(al.sum()-bl.sum()) if ast==bst=='valid' else None,
                    survival_failure=ast!='valid' or bst!='valid',unresolved=unresolved,
                    all_open_zero_ending_equity_difference=a['all_open_long_zero_scenario_equity']-b['all_open_long_zero_scenario_equity']))
    return rows


def continuation_conditions(summaries,points,bootstrap):
    primary=[r for r in points if r['scenario']=='base' and r['window_id']=='primary_2020']
    nominal1=all(v['ci95_low'] is not None and v['ci95_low']>0 for v in bootstrap.values()) and all(
        not r['survival_failure'] and r['return_percentage_point_difference']>0 and r['drawdown_percentage_point_difference']>=0 for r in primary)
    uncertain1=any(r['unresolved']['differential_unresolved_exposure'] for r in primary)
    stress=summaries[('INVENTORY','stress','primary_2020')]
    cold=[r for r in points if r['window_id']=='cold_2023']
    nominal2=not stress['ever_insolvent'] and stress['total_return_pct']>0 and all(
        not r['survival_failure'] and r['cumulative_log_growth_difference']>0 and r['drawdown_percentage_point_difference']>=0 for r in cold)
    uncertain2=stress['unresolved_records']>0 or any(r['unresolved']['differential_unresolved_exposure'] for r in cold)
    survival1=any(r['survival_failure'] for r in primary)
    survival2=stress['ever_insolvent'] or any(r['survival_failure'] for r in cold)
    def status(nominal,uncertain,survival):
        return 'unsupported' if survival else 'unknown' if uncertain else 'supported' if nominal else 'unsupported'
    conditions=[dict(condition=1,status=status(nominal1,uncertain1,survival1),nominal_pass=bool(nominal1),reason='Both primary2020 base paired CI lower>0, return higher and DD not deeper; unresolved differential exposure cannot be assumed away.'),
        dict(condition=2,status=status(nominal2,uncertain2,survival2),nominal_pass=bool(nominal2),reason='INVENTORY self stress positive and survives; cold2023 both costs same positive direction and DD not deeper; unknown payoff has no invented finite bound.')]
    final='unsupported' if any(c['status']=='unsupported' for c in conditions) else 'unknown' if any(c['status']=='unknown' for c in conditions) else 'supported_information_candidate_only'
    return dict(conditions=conditions,decision=final,goal_complete=False,production_qualified=False,narrow_stop_qualified=False,increased_bet_qualified=False,
        diagnostic_reporting='all families, annual continuous slices, direct oil/other, concentration required; no extra training/eligibility gate')


def authorize(path,sha,protocol_binding,fit_binding,source_import_binding,source):
    binding=file_binding(path)
    if binding['sha256']!=sha:
        raise ValueError('root cash authorization SHA differs')
    auth=json.loads(ref.read_bound(binding))
    expected=dict(kind='stage062_cash_once',protocol_sha256=protocol_binding['sha256'],fit_manifest_sha256=fit_binding['sha256'],
        source_import_manifest_sha256=source_import_binding['sha256'],source_sha256=source['sha256'],cash_accounts=12,native_source_queries=1)
    if auth.get('authorized') is not True or any(auth.get(k)!=v for k,v in expected.items()):
        raise ValueError('explicit root-issued twelve-account/one-SQL authorization required')
    return binding


def source_availability_preflight(protocol_path,sha):
    protocol,binding,market_protocol,market_binding=load_protocol(protocol_path,sha)
    source_path=LINE/'outputs/stage060_eia_report_import/manifest.json'
    available=source_path.exists()
    return dict(protocol=binding,market_economics_bridge=market_binding,bridge_use='only042 load_all_inputs market/economics, never old model/score/action',
        source_import_manifest_exists=available,source_import_manifest=file_binding(source_path) if available else None,
        source_import_status=json.loads(source_path.read_bytes()).get('status') if available else 'not_yet_complete',
        mutable_execution_ledger_path=str(EXECUTION_LEDGER_PATH),mutable_execution_ledger_is_not_training_contract=True,
        native_source_queries=0,actual_fit_calls=0,actual_cash_accounts=0)


def execute(args):
    out=Path(args.output).resolve()
    if out.exists():
        raise FileExistsError('refuse overwrite/automatic rerun '+str(out))
    protocol,protocol_binding,market_protocol,market_binding=load_protocol(args.protocol,args.protocol_sha256)
    fit,fit_binding,source_import=load_fit_manifest(args.fit_manifest,args.fit_manifest_sha256,protocol_binding)
    source=file_binding(__file__,'experiment_source');tests=file_binding(Path(__file__).with_name('test_stage062_eia_event_cash_compare.py'),'new_behavior_contract_tests')
    auth=authorize(args.authorization,args.authorization_sha256,protocol_binding,fit_binding,fit['source_import_manifest'],source)
    out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();began=datetime.now(timezone.utc).isoformat();before=ref.NATIVE_QUERIES
    counters=dict(started=0,computed=0,completed=0);status='failed';error=None;summary_map={};daily_accounts={};exposures={}
    write_json(out/'actual_started.json',dict(status='started',started_at=began,source=source,tests=tests,authorization=auth,protocol=protocol_binding,
        fit_manifest=fit_binding,cash_accounts=12,native_source_queries=1,actual_model_fit_calls=0))
    try:
        write_json(out/'input_bindings.json',dict(protocol=protocol_binding,fit_manifest=fit_binding,source_import_manifest=fit['source_import_manifest'],
            predictions=fit['predictions'],inputs=fit['inputs'],market_economics_bridge=market_binding,bridge_use='only042 load_all_inputs market/economics; algorithm is059 EIA',
            accepted_cash_kernel=file_binding(Path(__file__).with_name('stage042_cross_session_experiment.py'),'accepted_cash_kernel'),
            reused_pure_helpers=file_binding(HELPER_PATH,'arm_independent_cash_diagnostics_logs_native_cases'),authorization=auth))
        write_json(out/'protocol.json',protocol)
        predictions=read_csv(fit['predictions'],keep_default_na=False,na_values=[''])
        predictions['report_id']=predictions.report_id.fillna('')
        if len(predictions)!=3*161014 or set(predictions.arm)!=set(ARMS) or predictions.duplicated(['event_id','arm']).any():
            raise ValueError('061 complete EIA prediction mother differs')
        event_map=read_csv(fit['inputs']['event_map'],keep_default_na=False,na_values=[''])
        validate_event_metadata(predictions,event_map)
        label_fields=list(dict.fromkeys(PANEL_FIELDS+SIGNAL_FIELDS))
        labels=read_csv(fit['inputs']['labels'],keep_default_na=False,na_values=[''],usecols=label_fields)
        labels['reference_epoch']=labels.reference_epoch.fillna('')
        if len(labels)!=399252 or labels.event_id.duplicated().any():
            raise ValueError('full399252 original049 labels required')
        if fit['inputs']['labels']['sha256']!=market_protocol['labels']['sha256']:
            raise ValueError('new061 labels differ from accepted full049 mother')
        signals_by_arm={arm:make_signals(labels,predictions,arm) for arm in ARMS}
        # The only actual native SQL is inside this accepted shared loader.
        panel,market,dates,economics,scope_dates,receipt=ref.load_all_inputs(market_protocol)
        check=panel.merge(labels[PANEL_FIELDS],on='event_id',how='outer',validate='one_to_one',suffixes=('_panel','_049'),indicator=True)
        if not check._merge.eq('both').all() or any(not check[c+'_panel'].eq(check[c+'_049'].fillna('')).all() for c in PANEL_FIELDS if c!='event_id'):
            raise ValueError('original full panel identity/reference changed')
        receipt.update(market_economics_bridge=market_binding,market_bridge_only=True,active_information_protocol=protocol_binding,new_native_SQL_for_all_twelve_accounts=1)
        write_json(out/'source_read_receipt.json',receipt)
        audit=helpers.NativeCases(labels,market,dates)
        coverage=[]
        for arm,signals in signals_by_arm.items():
            ref.write_table(out/('signals_'+arm+'.csv.gz'),signals,[])
            chosen=signals.loc[signals.potential.eq(1)].sort_values(['u_index','event_id'])
            if len(chosen):
                audit.add('first_selected_'+arm,chosen.event_id.iloc[0])
            table=signals.groupby('family_id').agg(mother_rows=('event_id','size'),event_rows=('is_report_event','sum'),selected=('potential','sum')).reset_index()
            table['arm']=arm;table['direct_oil_diagnostic_only']=table.family_id.isin(OIL_FAMILIES);coverage.append(table)
        ref.write_table(out/'all_family_signal_coverage.csv.gz',pd.concat(coverage,ignore_index=True),[])
        write_json(out/'signal_summary.json',dict(arms=list(ARMS),mother_rows_per_arm=399252,predictions_per_arm=161014,
            selected={a:int(s.potential.sum()) for a,s in signals_by_arm.items()},eligibility='all families; same report event+ready20+finite score>0',
            non_event_reference_rows_retained=True,oil_group_is_not_trading_filter=True,old053_models_or_scores_read=False))
        all_families=set(labels.family_id)
        for cell,book in run_accounts(signals_by_arm,market,dates,economics,counters=counters):
            directory=out/'cash'/cell['account_id'];directory.mkdir(parents=True)
            for name,columns in [('fills',['account_id','event_id','date','side','qty','fee']),('daily',['account_id','date','equity']),
                ('budgets',['account_id','event_id','u_date','execution_date','qty_cap','D_qty','D_state']),('position_days',['account_id','event_id','date','qty','mark']),
                ('closed_episodes',['account_id','event_id','net_pnl']),('open_episodes',['account_id','event_id','state','qty'])]:
                for row in book[name]:
                    row.update(account_id=cell['account_id'],window_id=cell['window_id'],arm=cell['arm'],scenario=cell['scenario'])
                ref.write_table(directory/(name+'.csv.gz'),book[name],columns)
            diagnostics,family_year=helpers.cash_diagnostics(book,ref.INITIAL)
            family_year=complete_family_year(family_year,all_families,sorted({r['date'][:4] for r in book['daily']}))
            oil_diagnostics,groups,totals=oil_group_diagnostics(family_year,all_families)
            ref.write_table(directory/'family_year_contributions.csv.gz',family_year,[])
            ref.write_table(directory/'all_family_contributions.csv.gz',totals,[])
            ref.write_table(directory/'direct_oil_other_year_contributions.csv.gz',groups,[])
            exposure={name:pd.DataFrame(book[name]) for name in ('open_episodes','position_days','closed_episodes')}
            signature=exposure_signature(exposure)
            write_json(directory/'unresolved_exposure.json',dict(records=signature,finite_R_bound=None,alternative_zero_is_not_universal_bound=True))
            # Keep only finite audit/state columns for pair comparisons; raw
            # account tables above retain all data and are the audit authority.
            exposures[(cell['arm'],cell['scenario'],cell['window_id'])]=exposure
            summary=dict(book['summary'],**cell,diagnostics=diagnostics,oil_and_other_diagnostics=oil_diagnostics,unresolved_records=len(signature),
                mark='native_close_not_settlement',fee_margin_specs='static_vendor_snapshot_fixed_scenario',strict_held_family_training=False)
            write_json(directory/'summary.json',summary)
            daily=pd.DataFrame(book['daily']);logs,log_status=daily_log_growth(daily,ref.INITIAL)
            logframe=daily[['date','equity']].copy();logframe['daily_log_growth']=np.nan if logs is None else logs;logframe['status']=log_status
            ref.write_table(directory/'daily_log_growth.csv.gz',logframe,[])
            key=(cell['arm'],cell['scenario'],cell['window_id']);summary_map[key]=summary;daily_accounts[key]=daily
            for fill in book['fills']:
                if fill['side']=='SELL' and fill['reason'] in ('gap_stop','research_deferred_liquidation','risk_margin_joint_reduction','liquidity_reference_changed','lifecycle_exit'):
                    audit.add('cash_'+fill['reason'],fill['event_id'],fill['date'])
            counters['completed']+=1
            print(json.dumps(dict(phase='cash_complete',account_id=cell['account_id'],completed_research_cash_accounts=counters['completed'],ending_equity=summary['ending_equity'],elapsed_seconds=time.monotonic()-start)),flush=True)
        if counters!=dict(started=12,computed=12,completed=12) or ref.NATIVE_QUERIES-before!=1:
            raise AssertionError('finite twelve-account/one-SQL budget differs')
        primary={a:daily_accounts[(a,'base','primary_2020')] for a in ARMS}
        indices=circular_indices(len(primary['INVENTORY']),2000,252,20261018)
        np.save(out/'bootstrap_indices.npy',indices,allow_pickle=False)
        bootstrap,distribution=paired_log_statistics(primary,ref.INITIAL,indices)
        distribution.insert(0,'replicate',np.arange(len(distribution),dtype=int))
        ref.write_table(out/'paired_bootstrap_distribution.csv.gz',distribution,[])
        write_json(out/'paired_bootstrap.json',dict(schema='stage062_shared_EIA_log_bootstrap_v1',method='circular_moving_block',block_length_source_days=252,repetitions=2000,seed=20261018,
            indices=file_binding(out/'bootstrap_indices.npy'),indices_array_sha256=hashlib.sha256(indices.tobytes(order='C')).hexdigest(),
            source_dates=primary['INVENTORY'].date.tolist(),contrasts=bootstrap,same_indices_all_contrasts=True,
            inference_limit='Resamples and families are not independent macro markets; repeated historical research remains selected.'))
        points=point_comparisons(summary_map,daily_accounts,exposures)
        write_json(out/'point_comparisons.json',points)
        write_json(out/'continuation_conditions.json',continuation_conditions(summary_map,points,bootstrap))
        write_json(out/'cash_summary.json',dict(accounts=list(summary_map.values()),independent_cold_start_accounts=12,annual_slices_are_not_extra_accounts=True,
            actual_model_fit_calls=0,goal_complete=False,production_qualified=False,narrow_stop_qualified=False,increased_bet_qualified=False))
        pd.DataFrame([{k:v for k,v in s.items() if k not in ('diagnostics','oil_and_other_diagnostics')} for s in summary_map.values()]).to_csv(out/'cash_summary.csv',index=False)
        (out/'excluded_raw_audit').mkdir();audit.export(out/'excluded_raw_audit/native_case_slices.json.gz')
        ref.assert_db_binding(market_protocol['database'])
        if file_binding(__file__)['sha256']!=source['sha256'] or file_binding(tests['path'])['sha256']!=tests['sha256']:
            raise ValueError('062 source/test bytes drifted during actual run')
        status='completed'
    except BaseException as exc:
        error=f'{type(exc).__name__}: {exc}';raise
    finally:
        terminal=dict(status=status,exit_code=0 if status=='completed' else 1,started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start,error=error,
            actual_model_fit_calls=0,started_research_cash_accounts=counters['started'],computed_research_cash_accounts=counters['computed'],completed_research_cash_accounts=counters['completed'],
            native_source_queries=ref.NATIVE_QUERIES-before,source=source,tests=tests,goal_complete=False,production_qualified=False,narrow_stop_qualified=False,increased_bet_qualified=False)
        write_json(out/'actual_terminal.json',terminal)
        def role(p):
            if p.name.startswith('signals_'):return 'full_mother_event_action_and_reference_linkage'
            if p.name in ('fills.csv.gz','daily.csv.gz','budgets.csv.gz','position_days.csv.gz','closed_episodes.csv.gz','open_episodes.csv.gz'):return 'complete_research_cash_ledger'
            if p.name in ('bootstrap_indices.npy','paired_bootstrap_distribution.csv.gz','paired_bootstrap.json'):return 'paired_shared_block_inference'
            if 'contributions' in p.name:return 'all_family_cash_attribution'
            return 'qualification_evidence' if p.name in ('actual_started.json','actual_terminal.json','source_read_receipt.json','input_bindings.json') else 'decision_asset'
        artifacts=[file_binding(p,role(p)) for p in sorted(out.rglob('*')) if p.is_file() and 'excluded_raw_audit' not in p.parts and p.name!='manifest.json']
        excluded=out/'excluded_raw_audit/native_case_slices.json.gz'
        write_json(out/'manifest.json',dict(schema='stage062_eia_event_cash_compare_v1',**terminal,protocol=protocol_binding,fit_manifest=fit_binding,
            source_import_manifest=fit['source_import_manifest'],market_economics_bridge=market_binding,bridge_use='only native market/economics; new algorithm and arms are059',
            reused_pure_helpers=file_binding(HELPER_PATH,'arm_independent_cash_diagnostics_logs_native_cases'),authorization=auth,terminal=file_binding(out/'actual_terminal.json'),artifacts=artifacts,
            excluded_raw_audit=dict(file_binding(excluded),raw_ohlc=True,reproducibility_required=False,role='excluded_first_cause_full_warmup_raw_native_audit') if excluded.exists() else None))
    return dict(status=status,output=str(out),**counters,native_source_queries=ref.NATIVE_QUERIES-before,actual_model_fit_calls=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('protocol','protocol-sha256','fit-manifest','fit-manifest-sha256','authorization','authorization-sha256','output'):
        parser.add_argument('--'+flag,required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False))


if __name__=='__main__':
    main()
