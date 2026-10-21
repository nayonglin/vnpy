"""Stage015 fixed long-only OPEN versus CONFIRM execution attribution (no models)."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pandas as pd

LINE = Path(__file__).resolve().parents[1]
PROTOCOL = LINE / 'outputs/stage015_entry_confirmation_protocol/protocol.json'
PROTOCOL_SHA = '73c991c2ed2c4d4dbc77147705b6f09d834e63c05d7a8b0f614a902c1b6ec5e9'
IDENTITIES = ['event_id','product_id','product','exchange','u_date','reference_epoch',
              'planned_execution_date','status','direction']
PAIR_FIELDS = ['open_lower','open_upper','confirm_lower','confirm_upper','paired_lower','paired_upper']
COORDINATES = ['b','h','l','c']
CI_COLUMNS = ['confirm_lower','confirm_upper','open_lower','open_upper','paired_lower','paired_upper',
              'participation_lower','participation_upper','stress_confirm_lower','stress_paired_lower',
              'stress_paired_upper','unfilled_right_tail_lower','unfilled_right_tail_upper','fill_rate']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n')


def asset(path, role, required=True):
    path = Path(path).resolve(); raw = path.read_bytes()
    return dict(path=str(path), sha256=sha(raw), bytes=len(raw), role=role,
                reproducibility_required=required)


def read_bound(binding):
    raw = Path(binding['path']).read_bytes()
    if sha(raw) != binding['sha256'] or ('bytes' in binding and len(raw) != binding['bytes']):
        raise ValueError('source binding changed: '+binding['path'])
    return raw


def finite_mean(values):
    values = np.asarray(values, dtype=float); values = values[np.isfinite(values)]
    return float(values.mean()) if len(values) else None


def policy_intervals(b, h, l, c, fee):
    """Closed-form continuous-price marginal bounds and valid same-path difference outer bounds."""
    if not all(math.isfinite(v) for v in (b,h,l,c,fee)) or fee < 0:
        raise ValueError('nonfinite normalized path or negative cost')
    if l > min(0.,c) or h < max(0.,c) or l > h:
        raise ValueError('invalid normalized OHLC path')
    sl, pt = l <= -1., h >= 4.
    a = (-1.,4.) if sl and pt else (-1.,-1.) if sl else (4.,4.) if pt else (c,c)
    if b <= 0.:
        k = a; state = 'gap_open'; fill = 1
    elif b > h:
        k = (0.,0.); state = 'not_filled'; fill = 0
    else:
        state = 'intraday_trigger'; fill = 1; s, t = b-1., b+4.
        if l > s:
            k = (4.,4.) if h >= t else (c-b,c-b)
        elif h >= t:
            k = (-1.,4.)
        elif c <= s:
            k = (-1.,-1.)
        else:
            k = (-1.,c-b)
    a = (a[0]-fee,a[1]-fee)
    k = (k[0]-fee*fill,k[1]-fee*fill)
    delta = (0.,0.) if state == 'gap_open' else (k[0]-a[1],k[1]-a[0])
    return dict(trigger_state=state, confirm_fill=fill, open_lower=a[0], open_upper=a[1],
                confirm_lower=k[0], confirm_upper=k[1], paired_lower=delta[0], paired_upper=delta[1])


def build_events(opportunities, features, audit, calendar, *, successor_calendar=None):
    """One exact-identity merge; absolute prices are consumed and never included in the result."""
    if calendar != sorted(set(calendar)) or not calendar:
        raise ValueError('calendar must be increasing and unique')
    for name, frame in [('opportunity',opportunities),('feature',features),('audit',audit)]:
        if frame.event_id.duplicated().any():
            raise ValueError('duplicate '+name+' event identity')
    if len(opportunities) != len(features):
        raise ValueError('outer row count changed')
    for key in IDENTITIES:
        if not opportunities[key].reset_index(drop=True).equals(features[key].reset_index(drop=True)):
            raise ValueError('opportunity/feature identity conflict: '+key)
    frame = features[IDENTITIES+['family_id','feature_ready','history_state','label_identified',
                               'label_state','label_known_date']].copy().reset_index(drop=True)
    if frame.duplicated(['product_id','u_date']).any() or not frame.u_date.isin(calendar).all():
        raise ValueError('duplicate product day or date outside source calendar')
    if not frame.direction.eq('long').all() or not (frame.exchange+'.'+frame['product']).eq(frame.product_id).all():
        raise ValueError('invalid long product identity')
    if not frame.family_id.eq(frame.product_id.str.removesuffix('_F')).all():
        raise ValueError('family mapping differs')
    identity_calendar = calendar if successor_calendar is None else successor_calendar
    if identity_calendar != sorted(set(identity_calendar)) or not set(calendar)<=set(identity_calendar):
        raise ValueError('full identity calendar must contain the report scope')
    successors = dict(zip(identity_calendar,identity_calendar[1:]))
    if not frame.planned_execution_date.eq(frame.u_date.map(successors).fillna('')).all():
        raise ValueError('D is not original exact source-calendar successor')
    for key in ['feature_ready','label_identified']:
        if not frame[key].astype(str).isin(['0','1']).all():
            raise ValueError('invalid binary flag '+key)
        frame[key] = frame[key].astype('int8')
    known = frame.label_identified.eq(1)
    if (known & frame.feature_ready.ne(1)).any():
        raise ValueError('known label without ready history')
    if not frame.loc[known,'label_known_date'].eq(frame.loc[known,'planned_execution_date']).all():
        raise ValueError('known label has wrong maturity')
    if frame.loc[~known,'label_known_date'].ne('').any():
        raise ValueError('unknown label has fabricated maturity')
    audit_index = audit.set_index('event_id',verify_integrity=True)
    if not audit_index.index.isin(frame.event_id).all():
        raise ValueError('audit contains foreign event')
    for key in ['u_date','reference_epoch','planned_execution_date']:
        expected = frame.set_index('event_id')[key].reindex(audit_index.index)
        if not expected.equals(audit_index[key]):
            raise ValueError('audit identity conflict: '+key)
    ready_index = frame.index[known]
    ids = frame.loc[ready_index,'event_id']
    if not ids.isin(audit_index.index).all():
        raise ValueError('identified event lacks exact audit path')
    paths = audit_index.reindex(ids)
    def number(series):
        return pd.to_numeric(series.replace('',np.nan),errors='raise').to_numpy(dtype=float)
    F = number(paths.ideal_entry_F); H = number(paths.D_high); L = number(paths.D_low); C = number(paths.D_close)
    r = number(paths.risk_distance); B = number(opportunities.loc[ready_index,'high'])
    atr = number(features.loc[ready_index,'atr20'])
    if not np.isfinite(np.column_stack([F,H,L,C,r,B,atr])).all():
        raise ValueError('identified path is not finite')
    if (r <= 0).any() or (F-r <= 0).any() or (np.minimum.reduce([F,H,L,C,B]) <= 0).any():
        raise ValueError('identified path violates positive prices/risk/OPEN stop')
    if (L > np.minimum(F,C)).any() or (H < np.maximum(F,C)).any():
        raise ValueError('identified OHLC invalid')
    if not np.allclose(r,.25*atr,rtol=2e-14,atol=1e-12):
        raise ValueError('risk distance differs from frozen u ATR')
    coords = np.column_stack([(B-F)/r,(H-F)/r,(L-F)/r,(C-F)/r])
    for j,key in enumerate(COORDINATES):
        frame[key] = np.nan; frame.loc[ready_index,key] = coords[:,j]
    frame['evaluation_state'] = np.where(frame.feature_ready.eq(0),'not_feature_ready',frame.label_state)
    frame.loc[known,'evaluation_state'] = 'identified'
    frame['trigger_state'] = 'unknown'; frame['confirm_fill'] = np.nan
    for key in PAIR_FIELDS+['stress_'+k for k in PAIR_FIELDS]:
        frame[key] = np.nan
    values=[]; stress=[]
    for b,h,l,c in coords:
        values.append(policy_intervals(b,h,l,c,.2)); stress.append(policy_intervals(b,h,l,c,1.))
    for key in ['trigger_state','confirm_fill',*PAIR_FIELDS]:
        frame.loc[ready_index,key] = [v[key] for v in values]
    for key in PAIR_FIELDS:
        frame.loc[ready_index,'stress_'+key] = [v[key] for v in stress]
    for key in ['lower','upper']:
        expected=number(features.loc[ready_index,'proxy_'+key])
        if not np.allclose(frame.loc[ready_index,'open_'+key],expected,rtol=0,atol=2e-10):
            raise ValueError('OPEN does not reproduce accepted009 proxy '+key)
    frame['open_width'] = frame.open_upper-frame.open_lower
    frame['confirm_width'] = frame.confirm_upper-frame.confirm_lower
    frame['paired_width'] = frame.paired_upper-frame.paired_lower
    frame['family_group'] = frame.family_id.map(lambda s:int(hashlib.sha256(s.encode()).hexdigest(),16)%2).astype('int8')
    # This p is the main-cohort ex-post diagnostic, never an entry-time feature.
    p = frame.loc[known].groupby('u_date').confirm_fill.mean()
    frame['day_p'] = np.nan; frame.loc[known,'day_p'] = frame.loc[known,'u_date'].map(p)
    for prefix in ['', 'stress_']:
        lo,hi = participation_bounds(frame.loc[known],frame.loc[known,'day_p'].to_numpy(float),prefix)
        frame[prefix+'participation_lower'] = np.nan; frame[prefix+'participation_upper'] = np.nan
        frame.loc[known,prefix+'participation_lower'] = lo
        frame.loc[known,prefix+'participation_upper'] = hi
    nofill = known & frame.confirm_fill.eq(0)
    for side in ['lower','upper']:
        frame['unfilled_right_tail_'+side] = np.nan
        frame.loc[known,'unfilled_right_tail_'+side] = np.where(nofill[known],np.maximum(frame.loc[known,'open_'+side],0),0)
    if len(frame) != len(opportunities) or frame.loc[~known,PAIR_FIELDS].notna().any().any():
        raise AssertionError('outer/unknown preservation failed')
    return frame


def participation_bounds(frame, p, prefix=''):
    al = frame[prefix+'open_lower'].to_numpy(float); au = frame[prefix+'open_upper'].to_numpy(float)
    kl = frame[prefix+'confirm_lower'].to_numpy(float); ku = frame[prefix+'confirm_upper'].to_numpy(float)
    gap = frame.trigger_state.eq('gap_open').to_numpy(); nofill = frame.confirm_fill.eq(0).to_numpy()
    lo = np.where(gap,(1-p)*al,np.where(nofill,-p*au,kl-p*au))
    hi = np.where(gap,(1-p)*au,np.where(nofill,-p*al,ku-p*al))
    return lo,hi


def daily_metrics(events, calendar):
    known = events.loc[events.label_identified.eq(1)].copy()
    columns = PAIR_FIELDS+['stress_'+k for k in PAIR_FIELDS]
    if known.empty:
        return pd.DataFrame(index=pd.Index(calendar,name='u_date'),columns=columns+['fill_rate','identified_rows',
            'participation_lower','participation_upper','stress_participation_lower','stress_participation_upper',
            'participation_cost_residual','unfilled_right_tail_lower','unfilled_right_tail_upper'],dtype=float)
    p = known.groupby('u_date').confirm_fill.mean(); pp = known.u_date.map(p).to_numpy(float)
    for prefix in ['', 'stress_']:
        lo,hi=participation_bounds(known,pp,prefix)
        known[prefix+'participation_lower']=lo; known[prefix+'participation_upper']=hi
    # Recompute no-fill opportunity costs with the common denominator, not only the chosen rows.
    nofill = known.confirm_fill.eq(0).to_numpy()
    fill = known.confirm_fill.to_numpy(float)
    for side in ['lower','upper']:
        payoff=known['open_'+side].to_numpy(float)
        known['unfilled_right_tail_'+side]=np.where(nofill,np.maximum(payoff,0),0)
        known['filled_open_positive_'+side]=np.where(~nofill,np.maximum(payoff,0),0)
    known['fill_rate']=fill
    known['gap_rate']=known.trigger_state.eq('gap_open').astype(float)
    known['intraday_trigger_rate']=known.trigger_state.eq('intraday_trigger').astype(float)
    known['not_fill_rate']=nofill.astype(float)
    known['participation_cost_residual']=.2*(pp-fill)
    known['participation_stress_cost_residual']=1.*(pp-fill)
    optional=[k for k in ['open_width','confirm_width','paired_width'] if k in known]
    numbers=columns+['participation_lower','participation_upper','stress_participation_lower','stress_participation_upper',
        'fill_rate','gap_rate','intraday_trigger_rate','not_fill_rate','participation_cost_residual',
        'participation_stress_cost_residual','unfilled_right_tail_lower','unfilled_right_tail_upper',
        'filled_open_positive_lower','filled_open_positive_upper']+optional
    daily=known.groupby('u_date')[numbers].mean()
    daily['identified_rows']=known.groupby('u_date').size()
    daily=daily.reindex(calendar);daily.index.name='u_date'
    if daily.participation_cost_residual.abs().max() > 1e-12:
        raise AssertionError('date-matched fee did not cancel')
    for side in ['lower','upper']:
        if not np.allclose(daily['participation_'+side],daily['stress_participation_'+side],rtol=0,atol=2e-12,equal_nan=True):
            raise AssertionError('matched participation bounds changed with common per-fill fee')
    return daily


def bootstrap_intervals(daily, columns):
    array=daily[columns].to_numpy(float);n=len(array)
    if n == 0:
        raise ValueError('empty source calendar for bootstrap')
    block=min(60,n);blocks=math.ceil(n/block);rng=np.random.default_rng(20261018)
    samples=np.full((2000,len(columns)),np.nan);index_hash=hashlib.sha256()
    for repeat in range(2000):
        start=rng.integers(0,n-block+1,size=blocks)
        index=(start[:,None]+np.arange(block)[None,:]).ravel()[:n]
        index_hash.update(index.astype('<i8').tobytes())
        chosen=array[index];finite=np.isfinite(chosen);den=finite.sum(axis=0)
        samples[repeat]=np.divide(np.where(finite,chosen,0.).sum(axis=0),den,
            out=np.full(len(columns),np.nan),where=den>0)
    metrics={}
    for j,col in enumerate(columns):
        sample=samples[:,j];sample=sample[np.isfinite(sample)]
        ci=np.quantile(sample,[.025,.975]).tolist() if len(sample) else [None,None]
        metrics[col]=dict(mean=finite_mean(array[:,j]),ci95_lower=ci[0],ci95_upper=ci[1],
            finite_source_days=int(np.isfinite(array[:,j]).sum()),finite_bootstrap_replicates=len(sample))
    return dict(block_length=60,effective_block_length=block,repetitions=2000,seed=20261018,
        source_grid_days=n,common_indices_sha256=index_hash.hexdigest(),metrics=metrics,
        uncertainty_scope='fixed historical ideal continuous DAY proxies; excludes researcher selection and real execution uncertainty')


def cohort_counts(frame):
    known=frame.loc[frame.label_identified.eq(1)];ready=frame.feature_ready.eq(1)
    unknown=frame.loc[ready & frame.label_identified.eq(0)]
    fills=known.loc[known.confirm_fill.eq(1)];nofill=known.loc[known.confirm_fill.eq(0)]
    return dict(all_outer_rows=len(frame),feature_ready_rows=int(ready.sum()),identified_rows=len(known),
        ready_unknown_rows=len(unknown),unknown_label_states=dict(Counter(unknown.label_state)),
        evaluation_states=dict(Counter(frame.evaluation_state)),trigger_states=dict(Counter(frame.trigger_state)),
        confirm_fill_rows=len(fills),confirm_fill_dates=fills.u_date.nunique(),confirm_fill_families=fills.family_id.nunique(),
        not_fill_rows=len(nofill),not_fill_dates=nofill.u_date.nunique(),not_fill_families=nofill.family_id.nunique(),
        open_ambiguous_rows=int(known.open_width.gt(0).sum()),confirm_ambiguous_rows=int(known.confirm_width.gt(0).sum()),
        paired_outer_nonsingleton_rows=int(known.paired_width.gt(0).sum()),
        no_fill_conditional_positive_open_lower=finite_mean(np.maximum(nofill.open_lower,0)),
        no_fill_conditional_positive_open_upper=finite_mean(np.maximum(nofill.open_upper,0)),
        unknown_trigger='not inferred from missing D or censoring; no payoff/maturity imputed')


def positive(value):
    return value is not None and math.isfinite(value) and value>0


def report_events(events, calendar):
    scopes={'main':events,'family_0':events.loc[events.family_group.eq(0)],'family_1':events.loc[events.family_group.eq(1)]}
    reports={};daily_frames={}
    for scope,frame in scopes.items():
        full=daily_metrics(frame,calendar);annual={}
        for year in range(2010,2027):
            g=frame.loc[frame.u_date.str.startswith(str(year))]
            day=full.loc[full.index.str.startswith(str(year))]
            annual[str(year)]=dict(cohort=cohort_counts(g),date_equal_means={c:finite_mean(day[c]) for c in day},
                source_grid_days=len(day),no_identified_days=int(day.identified_rows.isna().sum()))
        report={'annual':annual}
        for period,start in [('all_2010','2010-01-01'),('primary_2020','2020-01-01')]:
            g=frame.loc[frame.u_date.ge(start)];day=full.loc[full.index>=start]
            report[period]=dict(cohort=cohort_counts(g),date_equal_means={c:finite_mean(day[c]) for c in day},
                source_grid_days=len(day),no_identified_days=int(day.identified_rows.isna().sum()))
            daily_frames[scope+'_'+period]=day
            if scope=='main':
                report[period]['bootstrap']=bootstrap_intervals(day,CI_COLUMNS)
        reports[scope]=report
    primary=reports['main']['primary_2020'];whole=reports['main']['all_2010'];ci=primary['bootstrap']['metrics']
    gates={
        'primary_fill_dates_at_least_60':primary['cohort']['confirm_fill_dates']>=60,
        'primary_fill_families_at_least_8':primary['cohort']['confirm_fill_families']>=8,
        'primary_confirm_lower_ci_positive':positive(ci['confirm_lower']['ci95_lower']),
        'primary_paired_lower_ci_positive':positive(ci['paired_lower']['ci95_lower']),
        'primary_participation_lower_ci_positive':positive(ci['participation_lower']['ci95_lower']),
        'all_2010_confirm_lower_positive':positive(whole['date_equal_means']['confirm_lower']),
        'all_2010_paired_lower_positive':positive(whole['date_equal_means']['paired_lower']),
        'all_2010_participation_lower_positive':positive(whole['date_equal_means']['participation_lower']),
        'same_mask_cost_1R_primary_confirm_lower_positive':positive(primary['date_equal_means']['stress_confirm_lower']),
        'four_complete_years_paired_lower_positive':sum(positive(reports['main']['annual'][str(y)]['date_equal_means']['paired_lower']) for y in range(2020,2026))>=4,
        'partial_2026_confirm_lower_positive':positive(reports['main']['annual']['2026']['date_equal_means']['confirm_lower'])}
    for group in (0,1):
        for metric in ['confirm_lower','paired_lower']:
            gates[f'family_{group}_primary_{metric}_positive']=positive(reports[f'family_{group}']['primary_2020']['date_equal_means'][metric])
    assert len(gates)==15
    return dict(schema='stage018_entry_confirmation_metrics_v1',scopes=reports,gates=gates,
        quality_screen_pass=all(gates.values()),entry_increment_detected=gates['primary_paired_lower_ci_positive'],
        aggregation='common identified products equally weighted within u, then source-calendar date equal; no-event dates NaN',
        family_groups='fixed heterogeneity groups, not trained holdouts; participation p computed within each reported cohort',
        cost_basis='0.2R base and 1R stress research budgets per filled policy; not actual fees/slippage/PnL',
        paired_bounds='gap exact0; others valid outer bounds, not claimed globally sharp',
        real_economic_labels_ready=False,financial_ready=False,production_qualified=False),daily_frames


def load_inputs(protocol_path, protocol_sha):
    ppath=Path(protocol_path).resolve();raw=ppath.read_bytes()
    if protocol_sha != PROTOCOL_SHA or sha(raw)!=PROTOCOL_SHA:
        raise ValueError('frozen015 protocol hash differs')
    protocol=json.loads(raw);read_bound(protocol['spec'])
    for key in ['inherited_data_review','inherited_result_review']:
        read_bound(protocol[key])
    review=json.loads(read_bound(protocol['inherited_data_review']))
    if review.get('qualified_for_fixed_proxy_experiment') is not True:
        raise ValueError('inherited011 lacks fixed proxy qualification')
    m4=json.loads(read_bound(protocol['opportunity_manifest']));m9=json.loads(read_bound(protocol['feature_label_manifest']))
    if m9['opportunity_manifest']['sha256'] != protocol['opportunity_manifest']['sha256']:
        raise ValueError('004/009 manifest closure differs')
    if review['data_manifest']['sha256'] != protocol['feature_label_manifest']['sha256']:
        raise ValueError('011 is not bound to the supplied009 manifest')
    original=Path(protocol['opportunity_manifest']['path']).parent/'product_day_opportunities.csv.gz'
    ob=dict(path=str(original),**m4['artifacts'][original.name])
    use4=IDENTITIES+['high']
    use9=IDENTITIES+['family_id','feature_ready','history_state','label_identified','label_state','label_known_date',
                     'atr20','gross_lower','gross_upper','proxy_lower','proxy_upper']
    usea=['event_id','u_date','reference_epoch','planned_execution_date','ideal_entry_F','risk_distance','D_high','D_low','D_close']
    frames=[]
    for label,binding,columns in [('004',ob,use4),('009',m9['feature_label_csv'],use9),('audit',m9['audit_paths'],usea)]:
        compressed=read_bound(binding)
        frames.append(pd.read_csv(io.BytesIO(compressed),compression='gzip',usecols=columns,dtype=str,keep_default_na=False))
        print(json.dumps(dict(progress='loaded_'+label,rows=len(frames[-1]))),flush=True)
    calendar=m9['source_calendar_scope_dates']
    if calendar[0] != '2010-01-04' or calendar[-1] != '2026-10-16' or len(calendar)!=4074:
        raise ValueError('source calendar scope changed')
    calendar_raw=read_bound(m9['source_calendar'])
    values=np.load(io.BytesIO(calendar_raw),allow_pickle=False)
    if values.ndim!=1 or values.dtype.kind not in ('i','u'):
        raise ValueError('source identity calendar must be YYYYMMDD integers')
    identity_calendar=[]
    for value in values:
        text=f'{int(value):08d}'
        identity_calendar.append(text[:4]+'-'+text[4:6]+'-'+text[6:])
    if [d for d in identity_calendar if '2010-01-01'<=d<='2026-10-16'] != calendar:
        raise ValueError('report scope differs from full identity calendar')
    if len(frames[0])!=399252 or len(frames[1])!=399252:
        raise ValueError('original399252 outer rows missing')
    bindings=dict(protocol=asset(ppath,'feature_contract'),spec=dict(protocol['spec'],role='feature_contract',reproducibility_required=True),
        opportunity_manifest=dict(protocol['opportunity_manifest'],role='feature_contract',reproducibility_required=True),
        feature_label_manifest=dict(protocol['feature_label_manifest'],role='feature_contract',reproducibility_required=True),
        inherited_data_review=dict(protocol['inherited_data_review'],role='qualification_evidence',reproducibility_required=True),
        inherited_result_review=dict(protocol['inherited_result_review'],role='qualification_evidence',reproducibility_required=True),
        original_caches=[dict(v,role='cache_or_visualization',reproducibility_required=False,external_ignored=True)
            for v in [ob,m9['feature_label_csv'],m9['audit_paths'],m9['source_calendar']]],
        raw_database='not read or rehashed; no raw OHLC included in new event table')
    return frames,calendar,identity_calendar,protocol,bindings


def execute(args):
    out=Path(args.output).resolve()
    if out.exists():
        raise FileExistsError('refuse to overwrite or repeat the frozen experiment: '+str(out))
    out.mkdir(parents=True,exist_ok=False)
    began=datetime.now().astimezone().isoformat();clock=time.monotonic();status='failed';error=None
    try:
        (opportunities,features,audit),calendar,identity_calendar,protocol,bindings=load_inputs(args.protocol,args.protocol_sha256)
        write_json(out/'protocol.json',protocol);write_json(out/'input_bindings.json',bindings)
        write_json(out/'source_calendar_dates.json',dict(dates=calendar,role='feature_contract',reproducibility_required=True))
        events=build_events(opportunities,features,audit,calendar,successor_calendar=identity_calendar)
        expected_ready=int(features.feature_ready.astype(int).sum());expected_known=int(features.label_identified.astype(int).sum())
        if int(events.feature_ready.sum())!=expected_ready or int(events.label_identified.sum())!=expected_known:
            raise AssertionError('original cohort changed')
        events.to_csv(out/'event_intervals.csv.gz',index=False,float_format='%.17g',compression={'method':'gzip','mtime':0})
        print(json.dumps(dict(progress='event_intervals_written',rows=len(events),feature_ready=expected_ready,identified=expected_known)),flush=True)
        metrics,daily=report_events(events,calendar)
        metrics['all_outer_counts']=cohort_counts(events)
        metrics['original009_counts']=dict(rows=len(features),ready=expected_ready,identified=expected_known)
        write_json(out/'metrics.json',metrics)
        for name,frame in daily.items():
            frame.to_csv(out/('daily_'+name+'.csv'),index=True,float_format='%.17g')
        status='completed'
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc)
        raise
    finally:
        write_json(out/'actual_terminal.json',dict(schema='stage018_actual_terminal_v1',status=status,
            command=sys.argv,started_at=began,finished_at=datetime.now().astimezone().isoformat(),
            elapsed_seconds=time.monotonic()-clock,exit_code=0 if status=='completed' else 1,error=error,
            python=sys.executable,python_version=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,
            source=asset(Path(__file__),'feature_contract'),role='qualification_evidence',reproducibility_required=True,
            attempts=2,completed_full_experiment=1 if status=='completed' else 0,
            model_fits=0,SQL_queries=0,financial_runs=0,network_calls=0,downloads=0))
    event_asset=asset(out/'event_intervals.csv.gz','decision_asset')
    event_asset.update(rows=len(events),columns=list(events))
    artifacts=[asset(p,'decision_asset' if p.name.startswith(('event_intervals','daily_','metrics')) else
        'qualification_evidence' if p.name=='actual_terminal.json' else 'feature_contract') for p in sorted(out.iterdir()) if p.is_file()]
    evidence_files=[asset(p,'qualification_evidence') for p in sorted(out.parent.glob('test_*')) if p.is_file()]
    evidence_files += [asset(p,'qualification_evidence') for p in sorted(out.parent.glob('compile_*')) if p.is_file()]
    failure_assets=[asset(p,'feature_contract' if p.suffix=='.py' else 'qualification_evidence')
        for p in sorted((out.parent/'failed_attempt1_snapshot').iterdir()) if p.is_file()]
    failure_assets.append(asset(out.parent/'calendar_boundary_diagnosis.json','qualification_evidence'))
    write_json(out/'manifest.json',dict(schema='stage018_entry_confirmation_experiment_v1',status=status,
        role='qualification_evidence',reproducibility_required=True,source=asset(Path(__file__),'feature_contract'),
        test=asset(Path(__file__).with_name('test_stage018_entry_confirmation_experiment.py'),'feature_contract'),
        protocol=bindings['protocol'],source_bindings=bindings,artifacts=artifacts,test_compile_evidence=evidence_files,
        prior_failed_attempt_evidence=failure_assets,attempts=2,completed_full_experiment=1,
        event_intervals=event_asset,source_calendar_dates=asset(out/'source_calendar_dates.json','feature_contract'),
        counts=metrics['all_outer_counts'],quality_screen_pass=metrics['quality_screen_pass'],
        entry_increment_detected=metrics['entry_increment_detected'],label_only_columns=[c for c in events if c not in
            IDENTITIES+['family_id','family_group','feature_ready','history_state']],
        no_absolute_OHLC=True,all_D_coordinates_and_outcomes_are_label_only=True,
        qualified_for_fixed_proxy_experiment='awaiting_independent019_result_review',
        real_economic_labels_ready=False,financial_ready=False,production_qualified=False,
        model_fits=0,SQL_queries=0,financial_runs=0,network_calls=0,downloads=0))
    return dict(status=status,output=str(out),quality_screen_pass=metrics['quality_screen_pass'],
                entry_increment_detected=metrics['entry_increment_detected'],model_fits=0,financial_runs=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',default=str(PROTOCOL));parser.add_argument('--protocol-sha256',default=PROTOCOL_SHA)
    parser.add_argument('--output',required=True)
    print(json.dumps(execute(parser.parse_args()),ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
