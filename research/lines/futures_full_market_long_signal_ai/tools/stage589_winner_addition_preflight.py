"""Frozen592v2 necessary support bound only; import performs no input I/O."""
from __future__ import annotations
import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
from types import SimpleNamespace
import time
import numpy as np
import pandas as pd

PROTOCOL_SHA='6f7dbff2b321af3953c38ad05e1544338480e3bdaeacb82112453c978ab2ec20'
LINE=Path(__file__).resolve().parents[1]
SIGNAL_NUM=['u_index','D_index','potential','score','N_u','u_close','lifecycle_index','effective_lifecycle_index','entry_capacity_qty']
POSITION_NUM=['qty','entry_fill','multiplier','margin_rate','risk_per_lot','mark','stale_days']
DAILY_NUM=['equity','initial_risk','buffered_margin','open_positions','stale_positions']
NUM_TOL=1e-8


def helpers_from_raw(sources):
    """Compile only exact bound pure definitions, never old entrypoints/imports."""
    env=dict(np=np,pd=pd,math=math,Decimal=Decimal,ROUND_CEILING=ROUND_CEILING,
             ROUND_FLOOR=ROUND_FLOOR,defaultdict=defaultdict)
    keep={
        'stage042_cross_session_experiment.py':set('SCENARIOS MARGIN_BUFFER finite positive floor_lot qualified_economics select_family_candidates margin_rate fee_at adverse_quote organize'.split()),
        'stage070_policy_kernel.py':{'POLICIES','policy_k','unit_estimate'},
        'stage156_voluntary_choices.py':{'cutoff_for'}}
    for name,wanted in keep.items():
        tree=ast.parse(sources[name],filename=name);nodes=[];found=set()
        for node in tree.body:
            names={node.name} if isinstance(node,ast.FunctionDef) else {t.id for t in node.targets if isinstance(t,ast.Name)} if isinstance(node,ast.Assign) else set()
            if names&wanted:nodes.append(node);found.update(names&wanted)
        if found!=wanted:raise ValueError('original pure definitions incomplete '+name)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),name,'exec'),env)
    return SimpleNamespace(**env)


def liquidation_profit(positions,econ,scenario,helpers):
    value=0.
    for p in positions:
        sell=helpers.adverse_quote(p['mark'],'SELL',econ,scenario)['fill_price']
        value+=p['qty']*(p['multiplier']*(sell-p['entry_fill'])-
            helpers.fee_at(p['entry_fill'],econ,scenario)-helpers.fee_at(sell,econ,scenario))
    return value


def calculate_upper(equity,family_risk,total_risk,margin,signal,econ,scenario,helpers):
    unit=helpers.unit_estimate(signal['u_close'],signal['N_u'],econ,scenario,'NARROW')
    r,m,f=unit['risk_per_lot'],unit['buffered_margin_per_lot'],unit['fee_roundtrip_per_lot']
    lot=float(econ['round_lot']);cap=float(signal['entry_capacity_qty'])
    if not all(math.isfinite(v) for v in [equity,family_risk,total_risk,margin,r,m,f,lot,cap]):raise ValueError('nonfinite upper input')
    if min(r,m,lot)<=0 or lot!=int(lot) or cap<0 or cap!=int(cap) or cap%lot:raise ValueError('invalid unit/lot/cap')
    hf=max(0.,.0025*equity-family_risk);hr=max(0.,.02*equity-total_risk);hm=max(0.,.25*equity-margin)
    parts=[hf/r,hr/r,hm/m];raw=min(parts)
    qty=min(helpers.floor_lot(raw,int(lot)),int(cap))
    near=cap>=lot and math.isclose(raw/lot,1.,rel_tol=1e-12,abs_tol=1e-12)
    return dict(H_family=hf,H_total=hr,H_margin=hm,unit_risk=r,unit_margin=m,unit_fee=f,
        family_qty_upper=parts[0],total_qty_upper=parts[1],margin_qty_upper=parts[2],
        raw_upper=raw,round_lot=int(lot),entry_capacity_qty=int(cap),qty_upper=qty,numeric_boundary=bool(near))


def select_original_winners(signals,economics,helpers):
    potential,_=helpers.organize(signals)
    return {int(u):helpers.select_family_candidates(rows,set(),economics,cash=True)[0] for u,rows in potential.items()}


def scope_signals(signals,days,helpers):
    if len(days)<2:raise ValueError('account calendar too short')
    s=signals.loc[signals.u_date.ge(days[0])&signals.u_date.lt(days[-1])].copy()
    if not s.u_date.isin(days[:-1]).all():raise ValueError('signal u absent from saved calendar')
    if not s.cutoff.eq(s.u_date.map(helpers.cutoff_for)).all():raise ValueError('original per-u cutoff mismatch')
    return s


def number(frame,columns):
    for name in columns:
        if name not in frame:raise ValueError('missing column '+name)
        frame[name]=pd.to_numeric(frame[name],errors='raise')
    return frame


def true_false(value):
    if value=='True':return True
    if value=='False':return False
    raise ValueError('unknown boolean '+str(value))


def state_empty(value):
    if value=='':return True
    if value in ('None','nan','NaN'):raise ValueError('unresolved state token')
    return False


def close(a,b):return math.isfinite(a) and math.isfinite(b) and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-6)


def evaluate_account(spec,signals,daily,positions,economics,helpers,old_summary):
    account,scenario=spec['account_id'],spec['scenario']
    if daily.date.duplicated().any() or daily.date.tolist()!=sorted(daily.date.tolist()):raise ValueError('duplicate/unsorted account calendar')
    if any(set(f.account_id)!={account} or set(f.scenario)!={scenario} for f in [daily,positions] if len(f)):raise ValueError('OWN account/scenario differs')
    if positions[['date','root_id']].duplicated().any().any():raise ValueError('duplicate position root-date')
    days=daily.date.tolist();ds=daily.set_index('date').to_dict('index')
    if not positions.date.isin(days).all():raise ValueError('position date outside OWN calendar')
    by_day={day:g.to_dict('records') for day,g in positions.groupby('date',sort=False)}
    scoped=scope_signals(signals,days,helpers);winners=select_original_winners(scoped,economics,helpers)
    date_by_u={int(k):g.u_date.iloc[0] for k,g in scoped.groupby('u_index')}
    if any(g.u_date.nunique()!=1 for _,g in scoped.groupby('u_index')):raise ValueError('u clock differs')
    counts=Counter();rows=[]
    for u,chosen in winners.items():
        day=date_by_u[u];d=ds[day];ps=by_day.get(day,[]);families=defaultdict(list)
        for p in ps:families[p['family_id']].append(p)
        problems=[]
        risk=sum(p['qty']*p['risk_per_lot'] for p in ps)
        margin=sum(1.1*p['qty']*p['mark']*p['multiplier']*p['margin_rate'] for p in ps)
        if len(ps)!=d['open_positions'] or not close(risk,d['initial_risk']) or not close(margin,d['buffered_margin']):problems.append('position_daily_reconciliation')
        if sum(p['mark_state']=='stale' for p in ps)!=d['stale_positions']:problems.append('stale_count_reconciliation')
        try:insolvent=true_false(d['ever_insolvent'])
        except ValueError:insolvent=False;problems.append('insolvency_state_unknown')
        for c in chosen:
            counts['original_family_winner']+=1;held=families.get(c['family_id'],[])
            if not held and not problems:continue
            row=dict(account_id=account,scenario=scenario,u_date=day,u_index=u,event_id=c['event_id'],family_id=c['family_id'],epoch=c['reference_epoch'],root_ids='|'.join(p['root_id'] for p in held),eligibility_reason='',state='',qty_upper=None,net_profit=None,E=d['equity'],F0_family=None,F0_all=d['initial_risk'],M_all=d['buffered_margin'])
            rows.append(row);counts['held_family_winner']+=bool(held)
            def finish(state,reason):row.update(state=state,eligibility_reason=reason)
            if problems:finish('unknown',';'.join(problems));continue
            if not all(p['epoch']==c['reference_epoch'] for p in held):finish('ineligible','original_winner_epoch_differs');continue
            counts['same_epoch_repeat']+=1
            e=economics[c['reference_epoch']]
            if insolvent or d['equity']<=0 or d['initial_risk']>.02*d['equity'] or d['buffered_margin']>.25*d['equity']:
                finish('ineligible','original_insolvency_or_over_cap');continue
            try:
                if c['D_index']!=u+1 or c['effective_lifecycle_index']!=c['lifecycle_index']:raise ValueError('D_or_effective_K_clock')
                if c['D_index']>=c['lifecycle_index']:finish('ineligible','original_lifecycle');continue
                D=days[days.index(day)+1]
                if e.get('listed_date') and D<e['listed_date']:finish('ineligible','original_listed_date');continue
                if any(p['mark_state'] not in ('native_close','stale') for p in held):raise ValueError('mark_state_unknown')
                if any(p['mark_state']=='stale' or p['stale_days']>0 for p in held):finish('ineligible','candidate_stale');continue
                if any(not state_empty(p['force_next']) or not state_empty(p['reduce_to_next']) for p in held):finish('ineligible','candidate_force_or_reduce');continue
                if d['stale_positions']>0:raise ValueError('other_stale_valuation_affects_bound')
                if not all(close(p['mark'],c['u_close']) and close(p['multiplier'],float(e['contract_multiplier'])) for p in held):raise ValueError('native_mark_or_multiplier_mismatch')
                if not all(all(math.isfinite(p[n]) for n in POSITION_NUM) and min(p['qty'],p['entry_fill'],p['multiplier'],p['mark'])>0 for p in held):raise ValueError('invalid_position_input')
                profit=liquidation_profit(held,e,scenario,helpers);row['net_profit']=profit
                if not math.isfinite(profit) or abs(profit)<=NUM_TOL:raise ValueError('net_profit_numerical_unknown')
                if profit<0:finish('ineligible','net_profit_nonpositive');continue
                counts['profitable_eligible']+=1
                family_risk=sum(p['qty']*p['risk_per_lot'] for p in held);row['F0_family']=family_risk
                bound=calculate_upper(d['equity'],family_risk,d['initial_risk'],d['buffered_margin'],c,e,scenario,helpers);row.update(bound)
                if bound['numeric_boundary']:row['qty_upper']=None;raise ValueError('quantity_numeric_boundary_unknown')
                finish('positive_upper' if bound['qty_upper']>=bound['round_lot'] else 'zero_upper','single_candidate_optimistic_upper')
            except (ValueError,KeyError,TypeError,OverflowError) as exc:
                row['qty_upper']=None;finish('unknown',str(exc))
    counts.update(Counter(r['state'] for r in rows))
    support=[dict(year=k[0],month=k[1],family_id=k[2],state=k[3],rows=v) for k,v in sorted(Counter((r['u_date'][:4],r['u_date'][:7],r['family_id'],r['state']) for r in rows).items())]
    positive=[r for r in rows if r['state']=='positive_upper']
    coverage=dict(years=sorted({r['u_date'][:4] for r in positive}),months=sorted({r['u_date'][:7] for r in positive}),families=sorted({r['family_id'] for r in positive}),max_upper_quantity=max([r['qty_upper'] for r in positive],default=0),sum_upper_quantity=sum(r['qty_upper'] for r in positive),quantity_disclosure='hypothetical per-u optimistic bounds; sum is not executable added lots or trades across days')
    return rows,dict(account_id=account,window=spec['window'],scenario=scenario,first_date=days[0],last_date=days[-1],scope_signal_rows=len(scoped),cutoffs=dict(Counter(scoped.cutoff)),counts=dict(counts),support_by_month_family=support,positive_coverage=coverage,original_A_unknown={k:old_summary[k] for k in ['execution_unknown','any_historical_stale','entry_execution_unknown','capacity_unknown_roots']},no_first_modeled_divergence=counts['positive_upper']==0 and counts['unknown']==0)


def binding(path,raw):return dict(path=str(Path(path).resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def write_json(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


class BoundReader:
    def __init__(self):self.cache={};self.receipts=[]
    def read(self,b):
        path=b['path']
        if path not in self.cache:
            raw=Path(path).read_bytes()
            if binding(path,raw)!=b:raise ValueError('binding differs '+path)
            self.cache[path]=raw;self.receipts.append(dict(b,raw_reads=1))
        elif binding(path,self.cache[path])!=b:raise ValueError('conflicting binding '+path)
        return self.cache[path]
    def json(self,b):return json.loads(self.read(b))
    def table(self,b):return pd.read_csv(io.BytesIO(self.read(b)),compression='gzip',dtype=str,keep_default_na=False)


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',required=True);parser.add_argument('--protocol-sha256',required=True);parser.add_argument('--source-sha256',required=True);parser.add_argument('--output',required=True);args=parser.parse_args(argv)
    if args.protocol_sha256!=PROTOCOL_SHA:raise ValueError('frozen592v2 required')
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError('fresh output required; retain old attempt')
    if LINE/'outputs/stage589_winner_addition_preflight' not in out.parents:raise ValueError('isolated589 output required')
    self_path=Path(__file__).resolve();self_raw=self_path.read_bytes()
    if hashlib.sha256(self_raw).hexdigest()!=args.source_sha256:raise ValueError('reviewed source SHA differs')
    out.mkdir(parents=True);started=time.monotonic();reader=BoundReader();terminal=dict(status='running',new_fit=0,new_cash=0,A_replays=0,SQL=0,market_GET=0)
    write_json(out/'actual_started.json',dict(recorded_at=datetime.now(timezone.utc).isoformat(),protocol=args.protocol,source=binding(self_path,self_raw),**terminal))
    write_json(out/'actual_attempt.json',dict(attempt=1,actual_probe=True,new_fit=0,new_cash=0))
    try:
        pr=Path(args.protocol).read_bytes();pb=binding(args.protocol,pr)
        if pb['sha256']!=PROTOCOL_SHA:raise ValueError('protocol hash differs')
        protocol=json.loads(pr)
        if protocol['schema']!='stage592_frozen_winner_addition_upper_bound_v2':raise ValueError('protocol schema differs')
        source_raw={name:reader.read(b) for name,b in protocol['source_bindings'].items()};h=helpers_from_raw(source_raw)
        inputs=protocol['input_bindings'];am=reader.json(inputs['A_manifest']);mp=reader.json(inputs['market_protocol'])
        if am['signals']!=inputs['signals'] or mp['economic_projection']!=inputs['economic_projection']:raise ValueError('upstream binding differs')
        economics=reader.json(inputs['economic_projection'])['instruments'];signals=number(reader.table(inputs['signals']),SIGNAL_NUM)
        if set(signals.arm)!={'VOLUNTARY_RESELECT'} or set(signals.policy)!={'NARROW'}:raise ValueError('original voluntary signals required')
        if signals.event_id.duplicated().any():raise ValueError('duplicate signal event')
        all_rows=[];summaries=[]
        if len(protocol['accounts'])!=4 or len({s['account_id'] for s in protocol['accounts']})!=4:raise ValueError('exact four OWN accounts required')
        original={a['account_id']:a for a in am['accounts']}
        for spec in protocol['accounts']:
            old=original[spec['account_id']]
            if spec['daily']!=old['ledgers']['daily'] or spec['positions']!=old['ledgers']['positions'] or spec['summary']!=old['summary']:raise ValueError('OWN ledger binding differs')
            daily=number(reader.table(spec['daily']),DAILY_NUM);positions=number(reader.table(spec['positions']),POSITION_NUM);summary=reader.json(spec['summary'])
            rows,info=evaluate_account(spec,signals,daily,positions,economics,h,summary);all_rows.extend(rows);summaries.append(info)
            print(json.dumps(dict(account=spec['account_id'],counts=info['counts']),ensure_ascii=False),flush=True)
        table=pd.DataFrame(all_rows)
        if not table.empty:table=table.sort_values(['account_id','u_date','family_id','event_id'],kind='stable')
        table.to_csv(out/'candidate_bounds.csv.gz',index=False,compression='gzip')
        result=dict(schema='stage589_support_summary_v1',accounts=summaries,positive_upper=sum(s['counts'].get('positive_upper',0) for s in summaries),unknown=sum(s['counts'].get('unknown',0) for s in summaries),no_first_modeled_divergence=all(s['no_first_modeled_divergence'] for s in summaries),batch_neutral_condition_required=True,positive_is_not_joint_quantity_or_fill=True,original_A_unknown_not_cleared=True,financial_results=protocol['financial_results'],new_fit=0,new_cash=0,A_replays=0,SQL=0,market_GET=0,goal_complete=False)
        write_json(out/'support_summary.json',result)
        terminal.update(status='completed',exit_code=0,elapsed_seconds=time.monotonic()-started,candidate_rows=len(all_rows))
        write_json(out/'input_read_receipt.json',dict(inputs=reader.receipts,same_raw_read_hash_parse=True))
        write_json(out/'actual_terminal.json',terminal)
        outputs={p.name:binding(p,p.read_bytes()) for p in out.iterdir() if p.is_file()}
        fixture=Path(__file__).with_name('test_stage589_winner_addition_preflight.py')
        write_json(out/'manifest.json',dict(schema='stage589_preflight_manifest_v1',protocol=pb,input_bindings=inputs,accounts=protocol['accounts'],source_bindings={**protocol['source_bindings'],'stage589':binding(self_path,self_raw),'fixture':binding(fixture,fixture.read_bytes())},outputs=outputs,terminal=outputs['actual_terminal.json'],status='completed',new_fit=0,new_cash=0,A_replays=0,SQL=0,market_GET=0))
        return 0
    except BaseException as exc:
        terminal.update(status='failed',exit_code=1,error=repr(exc),elapsed_seconds=time.monotonic()-started)
        write_json(out/'input_read_receipt.json',dict(inputs=reader.receipts));write_json(out/'actual_terminal.json',terminal);raise


if __name__=='__main__':raise SystemExit(main())
