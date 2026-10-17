"""Freeze the approved Stage257 multicycle protocol before any economic replay."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT/'research/lines/futures_trend_rollover_shape_same_volume'
DESIGN = LINE/'stages/20261016_1236_stage257_multicycle_experiment_design.md'
FU = 'fu.SHFE'
SEED = 20261016


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()


def rng(family, path_id, evaluated):
    month = int(evaluated[:7].replace('-', ''))
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence([SEED,257,family,path_id,month])))


def iid_draw(universe, k, path_id, evaluated):
    u = sorted(set(universe))
    if len(u)!=len(universe) or not 0<=k<=len(u): raise ValueError('invalid_universe_or_width')
    return sorted(rng(1,path_id,evaluated).choice(u,size=k,replace=False).tolist())


def turnover_draw(universe, k, previous, retain, path_id, evaluated):
    u,p = set(universe),set(previous)
    eligible_previous,outside = sorted(u&p),sorted(u-p)
    low,high = max(0,k-len(outside)),min(k,len(eligible_previous))
    if not low<=retain<=high: raise ValueError(f'infeasible_turnover:{evaluated}:{path_id}:{low}<={retain}<={high}')
    generator=rng(2,path_id,evaluated)
    kept=generator.choice(eligible_previous,size=retain,replace=False).tolist()
    added=generator.choice(outside,size=k-retain,replace=False).tolist()
    return sorted(kept+added)


def account_plan(windows):
    accounts,aliases={},{}
    def add(w,pool_id,kind,path_id=None):
        key=f"{w['window_id']}__{pool_id}"
        accounts[key]=dict(window_id=w['window_id'],pool_id=pool_id,start=w['start'],end=w['end'],kind=kind,path_id=path_id)
        return key
    for w in windows:
        if w['policy_phase']=='common_pre_ai_only':
            key=add(w,'COMMON_PRE_AI','common_pre_ai')
            for pool_id in ['AI_FAIR']+[f'RANDOM_{i:03d}' for i in range(1,50)]:
                aliases[f"{w['window_id']}__{pool_id}"]=key
            continue
        add(w,'AI_FAIR','ai_fair')
        n=199 if w['group'] in ['historical_full','ai_primary'] else 49
        for i in range(1,n+1):add(w,f'RANDOM_{i:03d}','random_monthly',i)
        if w['group']=='ai_primary':
            for i in range(1,200):add(w,f'TURNOVER_{i:03d}','turnover_matched',i)
        if w['group'] in ['historical_full','ai_primary']:add(w,'LEGACY_AI','legacy_ai')
    return accounts,aliases


def json_write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def csv_read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=LINE/'outputs/stage257_multicycle')
    args=parser.parse_args();out=args.output.resolve()
    if out.exists() and any(out.iterdir()): raise SystemExit('refuse_to_overwrite_experiment')
    original=LINE/'outputs/stage256_random10_ai'
    old=json.loads((original/'experiment_manifest.json').read_text())
    if sha(original/'experiment_manifest.json')!='b3b1e2d392d91f29df018c33599e2271818b327b07d06f6b2db0d9255b098d79':raise ValueError('old_manifest_changed')
    preflight_path=LINE/'outputs/stage257_multicycle_design/historical_pool_preflight.json'
    if sha(preflight_path)!='45fb2484d17ce174734134dbd35f9395ac429ca9f0de0b2030f678ef4f4c3308':raise ValueError('preflight_changed')
    preflight=json.loads(preflight_path.read_text());source=Path(old['source_pool'])
    assert sha(source)==old['source_pool_sha256']==preflight['sources']['official_pool_sha256']
    assert sha(preflight['sources']['mapping_file'])==preflight['sources']['mapping_sha256']
    with sqlite3.connect(f"file:{ROOT/'.vntrader/database.db'}?mode=ro",uri=True) as con:
        latest=con.execute("select max(datetime) from dbbardata where interval='d'").fetchone()[0]
    assert latest[:10]=='2026-10-14'
    assert sha(old['minute_csv'])==old['minute_cache_sha256']
    source_rows=csv_read(source);columns=list(source_rows[0]);by_date={}
    for r in source_rows:by_date.setdefault(r['eval_date'],[]).append(r)
    universe=sorted(old['non_fu_universe']);assert len(universe)==18 and FU not in universe
    common=sorted(universe)+[FU]
    qualified={};previous_u=set();previous_ai=None
    for row in preflight['monthly_57']:
        d=row['eval_date'];u=set(row['U_members']);a=set(row['effective_ai_nonfu'])
        assert previous_u<=u<=set(universe) and a<=u and len(a)==row['K']
        assert not row['data_gaps'] and row['fu']['structural_eligible']
        assert a=={r['product_vt_symbol'] for r in by_date[d] if r['product_vt_symbol']!=FU}&u
        if d>='2024-12-31':assert u==set(universe) and len(a)==10
        qualified[d]=dict(eval_date=d,effective_signal_trade_date=row['effective_signal_trade_date'],
            U_members=sorted(u),K=len(a),AI_members=sorted(a),
            ai_retained=None if previous_ai is None else len(previous_ai&a))
        previous_u,previous_ai=u,a
    assert len(qualified)==57 and next(iter(qualified))=='2022-01-28'
    windows=csv_read(LINE/'outputs/stage257_multicycle_design/proposed_windows.csv')
    for w in windows:
        w['duration_years']=int(w['duration_years']);w['complete_duration']=w['complete_duration']=='True'
    assert len(windows)==33
    accounts,aliases=account_plan(windows);assert len(accounts)==1955 and len(aliases)==200
    policies={};pool_members={}
    pool_members['COMMON_PRE_AI']={'2019-12-31':common}
    pool_members['AI_FAIR']={'2019-12-31':common,**{d:q['AI_members']+[FU] for d,q in qualified.items()}}
    for path_id in range(1,200):
        key=f'RANDOM_{path_id:03d}';f=Path(old['accounts'][key]['pool_file'])
        assert sha(f)==old['accounts'][key]['pool_sha256']
        old_groups={}
        for r in csv_read(f):
            if r['eval_date']>='2024-12-31':old_groups.setdefault(r['eval_date'],[]).append(r['product_vt_symbol'])
        assert len(old_groups)==22
        memberships={'2019-12-31':common}
        matched={'2019-12-31':common};previous=None
        for d,q in qualified.items():
            if d in old_groups:
                members=sorted(set(old_groups[d])-{FU});assert len(members)==q['K'] and set(members)<=set(q['U_members'])
            else:members=iid_draw(q['U_members'],q['K'],path_id,d)
            memberships[d]=members+[FU]
            if previous is None:
                t=sorted(rng(2,path_id,d).choice(q['U_members'],size=q['K'],replace=False).tolist())
            else:t=turnover_draw(q['U_members'],q['K'],previous,q['ai_retained'],path_id,d)
            matched[d]=t+[FU];previous=set(t)
        pool_members[key]=memberships;pool_members[f'TURNOVER_{path_id:03d}']=matched
    (out/'pools').mkdir(parents=True);(out/'accounts').mkdir();(out/'logs').mkdir();(out/'frozen_inputs').mkdir()
    matrix=[]
    for key,memberships in pool_members.items():
        if key=='AI_FAIR':kind='ai_fair';policy='stage257_ai_fair_effective_width_v1'
        elif key=='COMMON_PRE_AI':kind='common_pre_ai';policy='stage257_common_pre_ai_fu_v1'
        elif key.startswith('RANDOM_'):kind='random_monthly';policy='stage257_random_monthly_effective_width_v1'
        else:kind='turnover_matched';policy='stage257_random_turnover_effective_width_v1'
        rows=[]
        for d,members in memberships.items():
            assert len(members)==len(set(members)) and members[-1]==FU
            originals={r['product_vt_symbol']:r for r in by_date[d]}
            template=by_date[d][0]
            for rank,product in enumerate(members,1):
                value=dict(template,strategy=policy,eval_date=d,product_vt_symbol=product,score_rank=str(rank),top_n=str(len(members)),
                    score=str(originals.get(product,{}).get('score','0.0')) if key=='AI_FAIR' else '0.0',
                    score_type='stage257_frozen_source_membership_common_PIT_mask' if key=='AI_FAIR' else 'stage257_research_membership_not_model_score')
                rows.append(value);matrix.append(dict(pool_id=key,eval_date=d,product=product,nonfu_width=len(members)-1))
        destination=out/'pools'/f'{key}.csv'
        with destination.open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rows)
        policies[key]=dict(pool_file=str(destination),pool_sha256=sha(destination),policy_id=policy,kind=kind,
            path_id=int(key.split('_')[-1]) if key.startswith(('RANDOM_','TURNOVER_')) else None)
    legacy=out/'pools/LEGACY_AI.csv';shutil.copyfile(source,legacy)
    policies['LEGACY_AI']=dict(pool_file=str(legacy),pool_sha256=sha(legacy),policy_id=source_rows[0]['strategy'],kind='legacy_ai',path_id=None)
    for run_id,account in accounts.items():
        account.update({k:policies[account['pool_id']][k] for k in ['pool_file','pool_sha256','policy_id']})
        account['output']=str(out/'accounts'/run_id)
    with (out/'frozen_monthly_members.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=matrix[0]);writer.writeheader();writer.writerows(matrix)
    json_write(out/'qualified_months.json',qualified)
    shutil.copyfile(preflight_path,out/'historical_pool_preflight.json')
    params=json.loads(Path(old['parameters_reference_path']).read_text())
    universe_source=Path(params['spec']['overrides']['product_universe_csv_path'])
    shutil.copyfile(universe_source,out/'frozen_inputs/universe.csv')
    runtime_path=LINE/'outputs/stage251_half_r_ab/data_preparation/runtime_overlay.json'
    calendar_path=LINE/'outputs/stage251_half_r_ab/C_final/daily.csv'
    json_write(out/'experiment_manifest.json',dict(schema_version=1,stage=257,status='frozen_before_performance',
        frozen_at=datetime.now().astimezone().isoformat(),root=str(ROOT),start='2020-01-01',end='2026-10-14',capital=150000,
        first_ai_eval_date='2022-01-28',first_ai_signal_date='2022-02-07',master_seed=SEED,numpy_version=np.__version__,
        source_pool=str(source),source_pool_sha256=sha(source),reference_settings_path=old['reference_settings_path'],
        parameters_reference_path=old['parameters_reference_path'],minute_csv=old['minute_csv'],minute_cache_sha256=old['minute_cache_sha256'],
        runtime_overlay_path=str(runtime_path),runtime_overlay_sha256=sha(runtime_path),baseline_root='/Users/mac/.codex/worktrees/formal-2020-replay/fian',
        old_stage256_manifest=str(original/'experiment_manifest.json'),old_stage256_manifest_sha256=sha(original/'experiment_manifest.json'),
        preflight_path=str(out/'historical_pool_preflight.json'),preflight_sha256=sha(out/'historical_pool_preflight.json'),
        qualification_path=str(out/'qualified_months.json'),qualification_sha256=sha(out/'qualified_months.json'),
        universe_source=str(universe_source),universe_source_sha256=sha(universe_source),frozen_universe=str(out/'frozen_inputs/universe.csv'),
        database_sha256=sha(ROOT/'.vntrader/database.db'),mapping_path=preflight['sources']['mapping_file'],mapping_sha256=preflight['sources']['mapping_sha256'],
        accepted_calendar_daily=str(calendar_path),accepted_calendar_daily_sha256=sha(calendar_path),
        design_path=str(DESIGN),design_sha256=sha(DESIGN),freezer_sha256=sha(Path(__file__)),
        membership_matrix_sha256=sha(out/'frozen_monthly_members.csv'),non_fu_universe=universe,fixed_product=FU,
        policies=policies,windows=windows,accounts=accounts,aliases=aliases,expected_account_count=1955,expected_logical_account_count=2151,
        full_random_count=199,rolling_random_count=49,turnover_random_count=199,
        random_protocol={'iid_prior_to_20241231':'PCG64(SeedSequence([20261016,257,1,path_id,YYYYMM])); sorted U; choice K without replacement',
            'iid_from_20241231':'exact Stage256 frozen memberships, all199; complete U18/K10 verified',
            'turnover':'PCG64(SeedSequence([20261016,257,2,path_id,YYYYMM])); initial choose K; thereafter choose retained first, then outside previous; all sorted',
            'window_reuse':'same calendar month membership across all windows; fresh cash/account/engine',
            'common_aliases':'4 common pre-AI windows each have one real replay and50 explicitly equivalent labels; not random evidence'},
        primary_window='ai_inception_20220207_20261014',primary_endpoint='end_equity',strong_support_max_random_ge_ai=9,
        data_policy='Existing immutable minutes; any material execution gap=>diagnostic comparison; do not drop products, paths or resample',
        shared_history_policy='static18 plus fixed fu before first AI; original engine listing/AM gates, no extra monthly delay',
        strategy_policy='Stage251 C accepted correctness overlay, halfR off; C2/pairwise/long tilt unchanged; zero commission/model slippage',
        promotion_eligible=False))
    print(json.dumps({'output':str(out),'accounts':len(accounts),'aliases':len(aliases),'policies':len(policies),
        'monthly_member_rows':len(matrix),'manifest_sha256':sha(out/'experiment_manifest.json')},ensure_ascii=False))


if __name__=='__main__':main()
