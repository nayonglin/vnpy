"""One frozen564 PMI residual-head experiment; root alone launches actual once.

Reuse accepted compact A predictions/labels; no original52 refit or old SQL/raw read.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import traceback
import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent
LINE = TOOLS.parent
PROTOCOL_SHA = '38ccfa3add609a40c969eeb4e16d625fcf91d09b853417a1a3b7fe2f2c650cb6'
_spec = importlib.util.spec_from_file_location('pmi567_helpers538', TOOLS/'stage538_sector_residual_fit.py')
old = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(old)
select156 = old.select156
binding, small_json, write_json, write_frame = old.binding, old.small_json, old.write_json, old.write_frame
read_table_once = old.read_table_once
MACRO = ['u_index', 'u_date', 'macro_available', 'report_month', 'NO', 'FG', 'reason', 'pair_source_id', 'publication_upper', 'eligible_u_index']
LABELS = ['label_state', 'participation_state', 'net_R_stress', 'label_known_date']
FORWARD = select156.SCORE_FIELDS + LABELS
TRAIN = ['sequence_index', 'action_id', 'family_id', 'u_date', 'u_index', 'u_action_eligible', 'label_state', 'label_known_date', 'net_R_stress', 'sample_weight', 'Ahat']
CHOICE = select156.IDENTITY + ['proposed_action_id', 'proposed_epoch', 'proposed_score', 'chosen_action_id', 'chosen_action_sequence_index', 'chosen_epoch', 'anchor_epoch', 'score', 'selected', 'selection_state', 'scope', 'cutoff', 'arm', 'policy', 'old_chosen_action_id', 'old_chosen_epoch', 'voluntary_policy_version', 'account_deadline_certified']
SIMPLE = lambda b: {k:b[k] for k in ('path', 'bytes', 'sha256')}


def clean_forward(frame):
    """Explicit whitelist: old sector B_offset/C_offset are never model inputs."""
    return frame.loc[:, FORWARD].copy()


def aggregate_reports(train, macro, cutoff):
    if train.empty or train.action_id.duplicated().any(): raise ValueError('empty/duplicate accepted training')
    if not (train.u_action_eligible.eq(1) & train.label_state.eq('closed_complete_bar_model') & train.u_date.lt(cutoff) & train.label_known_date.ne('') & train.label_known_date.lt(cutoff)).all():
        raise ValueError('original mature training domain differs')
    nums = train[['sample_weight','net_R_stress','Ahat']].to_numpy(float)
    if not np.isfinite(nums).all() or (nums[:,0] <= 0).any(): raise ValueError('invalid old weights/residual inputs')
    ids = train.u_index.to_numpy(int)
    if (ids < 0).any() or (ids >= len(macro)).any() or not np.array_equal(train.u_date.to_numpy(), macro.u_date.to_numpy()[ids]):
        raise ValueError('training source-u does not match macro calendar')
    active = macro.iloc[ids].reset_index(drop=True); available = active.macro_available.eq(1).to_numpy()
    selected = train.loc[available].reset_index(drop=True)
    fields = active.loc[available, ['report_month','NO','FG','pair_source_id']].reset_index(drop=True)
    selected = pd.concat([selected, fields], axis=1)
    columns = ['report_month','row_count','source_days','families','original_weight_sum','residual_R','NO','FG','pair_source_ids']
    if selected.empty: return pd.DataFrame(columns=columns)
    if selected.report_month.eq('').any() or not np.isfinite(selected[['NO','FG']].to_numpy(float)).all():
        raise ValueError('available macro has missing month/pair')
    selected['weighted_residual'] = selected.sample_weight*(selected.net_R_stress-selected.Ahat)
    groups = selected.groupby('report_month', sort=True)
    if (groups[['NO','FG']].nunique() != 1).any().any(): raise ValueError('one report has differing available feature values')
    result = groups.agg(row_count=('action_id','size'), source_days=('u_date','nunique'), families=('family_id','nunique'), original_weight_sum=('sample_weight','sum'), weighted_residual=('weighted_residual','sum'), NO=('NO','first'), FG=('FG','first')).reset_index()
    result['residual_R'] = result.weighted_residual/result.original_weight_sum
    sources = groups.pair_source_id.agg(lambda s: json.dumps(sorted(set(s)), ensure_ascii=False)).rename('pair_source_ids').reset_index()
    return result.merge(sources, on='report_month', validate='one_to_one')[columns]


def report_support(months):
    values = months[['NO','FG']].to_numpy(float)
    mean = values.mean(axis=0) if len(values) else np.array([np.nan,np.nan])
    scale = values.std(axis=0, ddof=0) if len(values) else np.array([np.nan,np.nan])
    passed = len(values) >= 36 and np.isfinite(values).all() and np.isfinite(scale).all() and (scale > 0).all()
    return dict(M=len(values), years=int(months.report_month.str[:4].nunique()) if len(months) else 0,
                mean=[float(x) if np.isfinite(x) else None for x in mean], scale=[float(x) if np.isfinite(x) else None for x in scale],
                equal_report_weight_sum=1. if len(values) else 0., effective_equal_report_count=len(values), support_pass=bool(passed))


def fit_head(months, arm):
    support = report_support(months)
    if not support['support_pass']: raise ValueError('all-fold support must pass before any actual head fit')
    y = months.residual_R.to_numpy(float); a = float(y.mean())
    head = dict(arm=arm, a=a, M=len(y), lambda_fixed=1., loss_weight_sum=1., features=['NO','FG'], support=support)
    if arm == 'C':
        z = (months[['NO','FG']].to_numpy(float)-np.array(support['mean']))/np.array(support['scale'])
        G = z.T@z/len(y); rhs = z.T@(y-a)/len(y); beta = np.linalg.solve(G+np.eye(2), rhs)
        df = float(np.trace(np.linalg.solve(G+np.eye(2), G)))
        if not np.allclose(z.mean(axis=0), 0., atol=1e-12) or not np.isclose(np.trace(G), 2., atol=1e-10) or not 0 <= df <= 1+1e-10:
            raise ValueError('center/scale or effective df bound differs')
        head.update(beta=beta.tolist(), G=G.tolist(), rhs=rhs.tolist(), effective_slope_df=df,
                    feature_mean=support['mean'], feature_scale=support['scale'])
    elif arm != 'B': raise ValueError('only B/C new heads')
    return head


def predict_delta(macro, head):
    available = macro.macro_available.eq(1).to_numpy(); delta = np.zeros(len(macro), float)
    delta[available] = head['a']
    if head['arm'] == 'C':
        z = (macro.loc[available,['NO','FG']].to_numpy(float)-np.array(head['feature_mean']))/np.array(head['feature_scale'])
        delta[available] += z@np.array(head['beta'])
    if not np.isfinite(delta).all(): raise ValueError('nonfinite offset')
    return delta


def apply_delta(base, delta, available):
    """No arithmetic at unavailable rows, retaining even signed zero A bit patterns."""
    score = np.array(base, float, copy=True); mask = np.asarray(available, bool)
    score[mask] = score[mask]+np.asarray(delta, float)[mask]
    if not np.array_equal(score[~mask].view(np.uint64), np.asarray(base,float)[~mask].view(np.uint64)):
        raise ValueError('missing macro is not bitwise A fallback')
    return score


def monthly_diagnostics(report, daily, macro):
    day = daily.merge(macro[['u_date','report_month','macro_available']], on='u_date', how='left', validate='many_to_one')
    if day.macro_available.isna().any(): raise ValueError('diagnostic source-u absent from full macro calendar')
    day['u_month'] = day.u_date.str[:7]
    agg = dict(mean_delta_R=('delta_R','mean'), source_days=('u_date','size'), known_source_days=('delta_R','count'), unknown_family_u=('unknown_family_u','sum'), known_family_u=('known_family_u','sum'))
    monthly = day.groupby(['scope','contrast','u_month'], sort=True).agg(**agg).reset_index()
    context = day.groupby(['scope','contrast','report_month','macro_available'], sort=True, dropna=False).agg(**agg).reset_index()
    annual = monthly.assign(year=monthly.u_month.str[:4]).groupby(['scope','contrast','year'], sort=True).agg(mean_delta_R=('mean_delta_R','mean'), calendar_months=('u_month','size'), unknown_family_u=('unknown_family_u','sum')).reset_index()
    means = {}; eras = []
    for (scope, contrast), part in monthly.groupby(['scope','contrast'], sort=True):
        mean = part.mean_delta_R.mean()
        means.setdefault(scope,{})[contrast] = dict(equal_calendar_month_mean_increment_R=float(mean) if np.isfinite(mean) else None, calendar_months=len(part), known_months=int(part.mean_delta_R.notna().sum()), unknown_family_u=int(part.unknown_family_u.sum()))
        if scope == 'main':
            for name, lo, hi in [('2020_2022','2020-01','2022-12'),('2023_2026','2023-01','2026-12')]:
                subset = part.loc[part.u_month.between(lo,hi)]; v = subset.mean_delta_R.mean()
                eras.append(dict(scope=scope, contrast=contrast, era=name, equal_calendar_month_mean_increment_R=float(v) if np.isfinite(v) else None, calendar_months=len(subset), unknown_family_u=int(subset.unknown_family_u.sum())))
    gate = True
    for contrast in ('C_minus_A','C_minus_B'):
        held = [means.get(s,{}).get(contrast,{}).get('equal_calendar_month_mean_increment_R') for s in ('holdout_0','holdout_1')]
        gate &= all(v is not None and np.isfinite(v) and v >= 0 for v in held) and any(v is not None and v > 0 for v in held)
        segments = [r['equal_calendar_month_mean_increment_R'] for r in eras if r['contrast'] == contrast]
        gate &= len(segments) == 2 and all(v is not None and np.isfinite(v) and v >= 0 for v in segments)
    report.update(schema='stage567_pmi_actual_chosen_action_diagnostic_v1', calendar_month_groups=means, main_era_means=eras, nominal_cash_prerequisite=bool(gate),
                  primary_aggregation='full family-u then known-source-day mean then calendar u-month mean then equal calendar months',
                  unresolved_policy='different unresolved action remains NaN, never replaced0; all conditional known-support means retain counts',
                  full_policy_cash_qualified=False)
    return report, day, monthly, annual, context


def descriptive_ci(monthly):
    months = sorted(monthly.u_month.unique()); n = len(months); rng = np.random.default_rng(567)
    starts = rng.integers(0, n, size=(2000, (n+11)//12)); indexes = ((starts[:,:,None]+np.arange(12))%n).reshape(2000,-1)[:,:n]
    result = dict(method='circular moving calendar-month block bootstrap', block_months=12, draws=2000, seed=567, paired_same_indices=True, calendar_months=n, known_support_only=True, formal_pvalue=False, scopes={})
    result['index_sha256'] = hashlib.sha256(indexes.astype('<i8').tobytes()).hexdigest()
    for scope in ('main','holdout_0','holdout_1'):
        result['scopes'][scope] = {}
        for contrast in ('C_minus_A','C_minus_B'):
            vals = monthly.loc[monthly.scope.eq(scope)&monthly.contrast.eq(contrast)].set_index('u_month').mean_delta_R.reindex(months).to_numpy(float)
            if not np.isfinite(vals).all(): result['scopes'][scope][contrast] = dict(status='unresolved_month_no_CI'); continue
            samples = vals[indexes].mean(axis=1); limits = np.quantile(samples,[.025,.975])
            result['scopes'][scope][contrast] = dict(status='descriptive', mean=float(vals.mean()), lower95=float(limits[0]), upper95=float(limits[1]))
    return result


def source_bundle():
    return [binding(TOOLS/n) for n in ('stage567_pmi_residual_fit.py','test_stage567_pmi_residual_fit.py','stage538_sector_residual_fit.py','stage130_contract_choice_fit.py','stage071_settlement_narrow_fit.py','stage156_voluntary_choices.py')]


def run(args):
    output = Path(args.output).resolve(); pb = binding(args.protocol)
    if pb['sha256'] != PROTOCOL_SHA or args.protocol_sha256 != PROTOCOL_SHA: raise ValueError('frozen564 protocol differs')
    protocol = small_json(pb)
    if protocol['schema'] != 'stage564_frozen_pmi_incremental_v1': raise ValueError('wrong protocol schema')
    if output.exists() or LINE/'outputs/stage567_pmi_residual_fit' not in output.parents: raise ValueError('fresh567 actual output required')
    jb = binding(args.join_manifest); jm = small_json(jb)
    if jm['schema'] != 'stage565_pmi_causal_join_v1' or SIMPLE(jm['protocol']) != SIMPLE(pb): raise ValueError('565 join does not share exact564')
    jt = small_json(jm['terminal'])
    if jt['status'] != 'completed' or jt['exit_code'] != 0: raise ValueError('565 is not completed')
    output.mkdir(parents=True); start = time.monotonic(); sources = source_bundle(); attempted = completed = 0; artifacts = {}
    write_json(output/'actual_started.json', dict(status='started', started_utc=datetime.now(timezone.utc).isoformat(), protocol=pb, join_manifest=jb, source_bundle=sources, no_A_refit_or_cash=True))
    def event(name, obj):
        with (output/name).open('a') as f: f.write(json.dumps(obj,ensure_ascii=False)+'\n'); f.flush()
    def finish(status, extra):
        terminal = dict(status=status, exit_code=0, attempted=attempted, completed=completed, base_refits=0, cash=0, SQL=0, downloads=0, automatic_retry=False, elapsed_seconds=time.monotonic()-start, goal_complete=False, **extra)
        artifacts['terminal'] = write_json(output/'actual_terminal.json',terminal)
        manifest = dict(schema='stage567_pmi_residual_fit_v1', status=status, protocol=pb, join_manifest=jb, source_bundle=sources, actual_fit_calls_attempted=attempted, actual_fit_calls_completed=completed, base_refits=0, cash_replays=0, downloads=0, native_source_queries=0, goal_complete=False, production_qualified=False, **artifacts)
        write_json(output/'manifest.json', manifest); return terminal
    try:
        cache = protocol['accepted_old_cache']; accepted = small_json(cache['manifest'])
        for key in ('mothers_forward','forward_base_compact','choices_main','choices_holdout'):
            if SIMPLE(cache[key]) != SIMPLE(accepted[key]): raise ValueError('accepted538 role binding differs '+key)
        calendar = small_json(protocol['source_inputs']['calendar'])
        macro = read_table_once(jm['calendar_u_macro'],MACRO,['u_index','macro_available','NO','FG','eligible_u_index'])
        if len(calendar) != 5587 or len(macro) != len(calendar) or not np.array_equal(macro.u_index.to_numpy(),np.arange(len(calendar))) or macro.u_date.tolist() != calendar or not macro.macro_available.isin([0,1]).all():
            raise ValueError('full565 source calendar differs')
        if not np.isfinite(macro.loc[macro.macro_available.eq(1),['NO','FG']].to_numpy(float)).all(): raise ValueError('available macro pair nonfinite')
        macro_b = write_frame(output/'macro_consumed.csv.gz', macro); artifacts['macro_consumed'] = macro_b
        aggregated = {}; records = []; all_supported = True
        for fold in cache['folds']:
            scope, cutoff = fold['scope'], fold['cutoff']
            train = read_table_once(fold['train_compact'],TRAIN,['sequence_index','u_index','u_action_eligible','net_R_stress','sample_weight','Ahat'])
            if len(train) != fold['training_check']['training_rows']: raise ValueError('accepted training row count differs')
            if scope != 'main' and train.family_id.map({f:old.base130.family_group(f) for f in train.family_id.unique()}).eq(int(scope[-1])).any(): raise ValueError('held-family training leakage')
            months = aggregate_reports(train,macro,cutoff); support = report_support(months); all_supported &= support['support_pass']
            folder = output/'folds'/scope/cutoff; folder.mkdir(parents=True)
            mb = write_frame(folder/'training_report_means.csv.gz',months); aggregated[(scope,cutoff)] = months
            records.append(dict(scope=scope,cutoff=cutoff,train_compact=fold['train_compact'],training_report_means=mb,original_training_rows=len(train),original_training_dates=int(train.u_date.nunique()),supported_training_rows=int(months.row_count.sum()),support=support))
            print(json.dumps(dict(phase='support_aggregated',scope=scope,cutoff=cutoff,M=support['M'],passed=support['support_pass'])),flush=True)
            del train
        artifacts['support_preflight'] = write_json(output/'support_preflight.json',dict(all_folds_supported=bool(all_supported),folds=records))
        if not all_supported: return finish('stopped_insufficient_support',dict(reason='any_fold_M_below36_or_nonpositive_scale',nominal_cash_prerequisite=False))
        heads = {}; deltas = {}; offset_frames = []
        for record in records:
            scope, cutoff = record['scope'], record['cutoff']; months = aggregated[(scope,cutoff)]
            for arm in ('B','C'):
                attempted += 1; event('fit_attempts.jsonl',dict(attempt=attempted,scope=scope,cutoff=cutoff,arm=arm))
                head = fit_head(months,arm); head.update(scope=scope,cutoff=cutoff,training_report_means=record['training_report_means'])
                completed += 1; heads[(scope,cutoff,arm)] = head
                artifacts[f'head_{scope}_{cutoff}_{arm}'] = write_json(output/'folds'/scope/cutoff/(arm+'_head.json'),head)
                deltas[(scope,cutoff,arm)] = predict_delta(macro,head)
                event('fit_completed.jsonl',dict(completed=completed,scope=scope,cutoff=cutoff,arm=arm))
            if heads[(scope,cutoff,'B')]['a'] != heads[(scope,cutoff,'C')]['a']: raise ValueError('B/C shared intercept differs')
            offset = macro.loc[macro.u_date.ge(cutoff)&(macro.u_date.lt('2023-01-01') if cutoff=='2020-01-01' else macro.u_date.le(protocol['scope']['forward_end']))].copy()
            offset['scope'] = scope; offset['cutoff'] = cutoff; ix = offset.u_index.to_numpy(int)
            for arm in ('B','C'): offset[arm+'_offset'] = deltas[(scope,cutoff,arm)][ix]
            offset_frames.append(offset)
        artifacts['daily_offsets'] = write_frame(output/'daily_offsets.csv.gz',pd.concat(offset_frames,ignore_index=True))
        artifacts['fold_records'] = write_json(output/'fold_records.json',records)
        forward = clean_forward(read_table_once(cache['forward_base_compact'],FORWARD,['sequence_index','mother_sequence_index','u_index','u_action_eligible','score','net_R_stress']))
        if len(forward) != 1933480 or forward.duplicated(['scope','action_id']).any() or not np.isfinite(forward.score).all(): raise ValueError('full positive/negative forward scores differ')
        for fold in cache['folds']:
            if int((forward.scope.eq(fold['scope'])&forward.cutoff.eq(fold['cutoff'])).sum()) != fold['prediction_children']: raise ValueError('full own-fold forward shrunk')
        actions = forward[['action_id',*LABELS]].drop_duplicates('action_id').copy()
        main_ids = set(forward.loc[forward.scope.eq('main'),'action_id']); held_ids = set(forward.loc[forward.scope.ne('main'),'action_id'])
        if main_ids != held_ids or len(actions) != len(main_ids) or len(forward) != 2*len(main_ids): raise ValueError('main/held full child coverage differs')
        parents = read_table_once(cache['mothers_forward'],select156.IDENTITY,['sequence_index','u_index'])
        if len(parents) != 161014 or parents.event_id.duplicated().any(): raise ValueError('complete forward mothers differ')
        A = []
        for key in ('choices_main','choices_holdout'):
            prior = read_table_once(cache[key],CHOICE,['sequence_index','u_index','proposed_score','chosen_action_sequence_index','score','selected'])
            A.append(prior.loc[prior.arm.eq('A')].copy()); del prior
        all_choices = [pd.concat(A,ignore_index=True)]; selection_records = []; forward_counts = []
        family_group = {f:old.base130.family_group(f) for f in parents.family_id.unique()}
        for scope in protocol['scope']['scopes']:
            children = forward.loc[forward.scope.eq(scope)].copy(); u = children.u_index.to_numpy(int)
            if (u<0).any() or (u>=len(calendar)).any() or not np.array_equal(children.u_date.to_numpy(),macro.u_date.to_numpy()[u]): raise ValueError('forward source-u mismatch')
            if scope != 'main' and not children.family_id.map(family_group).eq(int(scope[-1])).all(): raise ValueError('forward held-family scope differs')
            pp = parents if scope=='main' else parents.loc[parents.family_id.map(family_group).eq(int(scope[-1]))]
            parent_rows = pp.to_dict('records'); available = macro.macro_available.to_numpy()[u] == 1
            for arm in ('B','C'):
                delta = np.zeros(len(children))
                for cutoff in protocol['scope']['cutoffs']:
                    mask = children.cutoff.eq(cutoff).to_numpy(); delta[mask] = deltas[(scope,cutoff,arm)][u[mask]]
                scores = apply_delta(children.score.to_numpy(float),delta,available)
                cf = children[select156.SCORE_FIELDS].copy(); cf['score'] = scores
                columns = cf.columns.tolist()
                score_rows = (dict(zip(columns,values)) for values in cf.itertuples(index=False,name=None))
                result = old.select_scope(parent_rows,score_rows,calendar,protocol['scope']['forward_end'],scope,arm)
                chosen = pd.DataFrame(result['choices']); all_choices.append(chosen)
                selection_records.append(dict(scope=scope,arm=arm,summary=result['summary']))
                forward_counts.append(dict(scope=scope,arm=arm,score_rows=len(scores),old_nonpositive=int((children.score<=0).sum()),new_nonpositive=int((scores<=0).sum()),macro_unavailable=int((~available).sum()),bitwise_fallback=True))
                print(json.dumps(dict(phase='selection_complete',scope=scope,arm=arm,parents=len(chosen),selected=int(chosen.selected.sum()))),flush=True)
                del cf,result,chosen
            del children
        choices = pd.concat(all_choices,ignore_index=True)
        for kind,part in [('main',choices.loc[choices.scope.eq('main')]),('held_union',choices.loc[choices.scope.ne('main')])]:
            if len(part) != 161014*3 or part.duplicated(['arm','event_id']).any(): raise ValueError('three-arm parent population differs '+kind)
            for arm in old.ARMS:
                if set(part.loc[part.arm.eq(arm),'event_id']) != set(parents.event_id): raise ValueError('parent identities shrunk '+kind)
        unavailable = ~macro.macro_available.eq(1).to_numpy()
        for scope,part in choices.groupby('scope',sort=True):
            aa = part.loc[part.arm.eq('A')].set_index('event_id')
            for arm in ('B','C'):
                cc = part.loc[part.arm.eq(arm)].set_index('event_id').reindex(aa.index); missing = unavailable[aa.u_index.to_numpy(int)]
                if not aa.loc[missing,'chosen_action_id'].eq(cc.loc[missing,'chosen_action_id']).all(): raise ValueError('missing macro changed old A action')
        report,daily,annual_u,linked = old.diagnostics(choices,actions,protocol['scope']['forward_end'])
        report,day,monthly,annual,context = monthly_diagnostics(report,daily,macro)
        for name,frame in [('choices_main',choices.loc[choices.scope.eq('main')]),('choices_holdout',choices.loc[choices.scope.ne('main')]),('held_daily',day),('calendar_monthly',monthly),('calendar_annual',annual),('held_annual_u_equal',annual_u),('source_report_context',context)]:
            artifacts[name] = write_frame(output/(name+'.csv.gz'),frame)
        compact = ['event_id','family_id','u_index','u_date','scope','arm','chosen_action_id','selected','diagnostic_value_R',*LABELS]
        artifacts['diagnostic_linked'] = write_frame(output/'diagnostic_linked.csv.gz',linked[compact])
        artifacts['selection_records'] = write_json(output/'selection_records.json',selection_records)
        artifacts['held_diagnostic'] = write_json(output/'held_diagnostic.json',report)
        if report['nominal_cash_prerequisite']: artifacts['descriptive_CI'] = write_json(output/'descriptive_CI.json',descriptive_ci(monthly))
        else: artifacts['descriptive_CI'] = write_json(output/'descriptive_CI.json',dict(status='not_run_failed_fixed_nominal_gate',new_resampling=0))
        if attempted != 12 or completed != 12 or sources != source_bundle(): raise ValueError('twelve new heads/source identity not preserved')
        summary = dict(status='completed',attempted=attempted,completed=completed,base_refits=0,cash=0,SQL=0,downloads=0,registered_products=98,registered_families=95,forward_mothers=161014,full_forward_score_rows=len(forward),training_compact_reads=6,forward_compact_reads=1,A_choice_file_reads=2,old_sector_offsets_consumed=False,forward_score_checks=forward_counts,nominal_cash_prerequisite=report['nominal_cash_prerequisite'],full_policy_cash_qualified=False,goal_complete=False)
        artifacts['summary'] = write_json(output/'summary.json',summary)
        return finish('completed',dict(nominal_cash_prerequisite=report['nominal_cash_prerequisite']))
    except BaseException as error:
        if not (output/'actual_terminal.json').exists(): write_json(output/'actual_terminal.json',dict(status='failed',exit_code=1,attempted=attempted,completed=completed,base_refits=0,cash=0,SQL=0,downloads=0,automatic_retry=False,error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),elapsed_seconds=time.monotonic()-start))
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('protocol','protocol-sha256','join-manifest','output'): p.add_argument('--'+key,required=True)
    p.add_argument('--actual',action='store_true'); args = p.parse_args(argv)
    if not args.actual: p.error('root-only actual requires explicit --actual')
    print(json.dumps(run(args),ensure_ascii=False),flush=True)

if __name__ == '__main__': main()
