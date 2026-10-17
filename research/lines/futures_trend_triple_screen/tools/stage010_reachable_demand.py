"""Pure abstract may-hold closure and minute demand; no financial engine."""
from __future__ import annotations
import argparse
import ast
from collections import Counter,defaultdict
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import time
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_trend_triple_screen'
PROJECT=ROOT/'examples/portfolio_backtesting'
OUTPUT=LINE/'outputs/stage010_reachable_demand'
PROTOCOL=LINE/'stages/20261018_0005_stage010_reachable_demand_protocol.md'
SIGNALS=LINE/'outputs/stage005_potential_signal_demand'
COVERAGE=LINE/'outputs/stage004_minute_coverage'
A0=LINE/'outputs/stage001_first_screen/A0_attempt2'
STRATEGY=PROJECT/'qmt_roll_portfolio_strategy.py'
MAPPING=PROJECT/'backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv'
STAGE008=LINE/'outputs/stage008_oi_requalification/requalification.json'
STAGE008_REVIEW=LINE/'outputs/stage008_independent_review/review_receipt.json'
sys.path.insert(0,str(PROJECT))
from qmt_roll_intraday_execution import session_minutes


def sha256(path):
    result=hashlib.sha256()
    with Path(path).open('rb')as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):result.update(chunk)
    return result.hexdigest()


def write_json(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


@dataclass(frozen=True,order=True)
class State:
    product: str
    held_contract: str
    pending_target: str=''
    elapsed: int=0


def advance(state,target,delay):
    """Return retained state or mandatory-close marker, without price/PnL."""
    if not target:return None,True
    if target==state.held_contract:return State(state.product,state.held_contract),False
    elapsed=state.elapsed+1 if state.pending_target==target else 0
    if elapsed>=delay:return None,True
    return State(state.product,state.held_contract,target,elapsed),False


def enumerate_demand(calendar,mapping,seeds,real,delay):
    calendar=list(calendar);positions={day:index for index,day in enumerate(calendar)}
    initial=defaultdict(set);demand={};pending={};state_counts=[];transitions=[]
    def emit(symbol,product,signal_date,fill_date,reason,signal_carry=False):
        if not fill_date:
            key=(symbol,product,signal_date,reason)
            pending[key]=dict(vt_symbol=symbol,product_vt_symbol=product,signal_date=signal_date,
                execution_trade_date='',reason=reason,status='terminal_pending_not_executed')
            return
        key=(symbol,fill_date)
        if key not in demand:
            demand[key]=dict(vt_symbol=symbol,product_vt_symbol=product,execution_trade_date=fill_date,
                requirement_kind='anchor',need_initial_open=False,need_rollover_open=False,
                need_possible_close=False,signal_carry_possible=False,first_signal_date=signal_date,
                last_signal_date=signal_date,event_contributions=0)
        row=demand[key];row['event_contributions']+=1
        row['first_signal_date']=min(row['first_signal_date'],signal_date)
        row['last_signal_date']=max(row['last_signal_date'],signal_date)
        row['signal_carry_possible']|=bool(signal_carry)
        if reason in ['initial_open','rollover_open']:
            row['requirement_kind']='full_session';row['need_'+reason]=True
        else:row['need_possible_close']=True
    for seed in seeds:
        fill=seed['execution_trade_date'];day=seed['signal_date']
        if fill and fill not in positions:raise ValueError('initial_execution_outside_global_calendar')
        if fill and day in positions and positions[fill]!=positions[day]+1:
            raise ValueError('initial_execution_is_not_next_global_batch')
        emit(seed['vt_symbol'],seed['product_vt_symbol'],day,fill,'initial_open')
        if fill:initial[fill].add(State(seed['product_vt_symbol'],seed['vt_symbol']))
    states=set();scheduled=set();mandatory=Counter();roll_seeds=set()
    for index,day in enumerate(calendar):
        # scheduled contains retained states and prior batch reopen plans only.
        # A mandatory close never puts its old state into this set.
        states=scheduled|initial[day];scheduled=set()
        next_day=calendar[index+1]if index+1<len(calendar)else''
        state_counts.append(dict(date=day,abstract_states=len(states),held_contracts=len({state.held_contract for state in states})))
        for state in sorted(states):
            emit(state.held_contract,state.product,day,next_day,'possible_close',
                (state.held_contract,day)not in real)
            target=mapping.get(day,{}).get(state.product,'')
            retained,due=advance(state,target,delay)
            if not due:
                scheduled.add(retained)
                continue
            reason='missing_mapping'if not target else'rollover_due'
            mandatory[reason]+=1
            can_reopen=bool(target and(target,day)in real)
            transitions.append(dict(signal_date=day,execution_trade_date=next_day,product_vt_symbol=state.product,
                old_contract=state.held_contract,target_contract=target,reason=reason,
                old_signal_real_bar=(state.held_contract,day)in real,target_signal_real_bar=(target,day)in real,
                reopen_upper_bound=can_reopen,old_branch_removed_at_next_batch=bool(next_day)))
            if can_reopen:
                emit(target,state.product,day,next_day,'rollover_open')
                if next_day:
                    scheduled.add(State(state.product,target));roll_seeds.add((target,next_day))
    diagnostics=dict(mandatory_close_states=sum(mandatory.values()),mandatory_reasons=dict(mandatory),
        unique_rollover_open_seeds=len(roll_seeds),peak_abstract_states=max(row['abstract_states']for row in state_counts),
        final_abstract_states=state_counts[-1]['abstract_states']if state_counts else 0,
        state_days=sum(row['abstract_states']for row in state_counts),state_counts=state_counts,transitions=transitions)
    return demand,list(pending.values()),diagnostics


def settings_contract(actual):
    # Read defaults as syntax only: never import or instantiate a strategy.
    defaults={}
    for node in ast.parse(STRATEGY.read_text()).body:
        if isinstance(node,ast.ClassDef)and node.name=='QmtRollPortfolioStrategy':
            for item in node.body:
                if isinstance(item,ast.AnnAssign)and isinstance(item.target,ast.Name):
                    try:defaults[item.target.id]=ast.literal_eval(item.value)
                    except (ValueError,TypeError):pass
    selected={key:actual.get(key,defaults.get(key))for key in [
        'reverse_on_opposite_signal','enable_add_position','enable_donchian_add_position','enable_post_entry_quality_add',
        'rollover_delay_trading_days','rollover_reopen_enabled','enable_rollover_shape_same_volume_reopen',
        'rollover_shape_history_mode','trade_start_date']}
    if any(selected[key]is not False for key in ['reverse_on_opposite_signal','enable_add_position',
        'enable_donchian_add_position','enable_post_entry_quality_add']):raise ValueError('extra_entry_path_unsupported')
    if selected['rollover_delay_trading_days']!=5 or selected['rollover_reopen_enabled']is not True:
        raise ValueError('frozen_rollover_contract_changed')
    if selected['enable_rollover_shape_same_volume_reopen']is not True or selected['rollover_shape_history_mode']!='target_contract_only':
        raise ValueError('frozen_shape_contract_changed')
    if selected['trade_start_date']!='2020-01-01':raise ValueError('initial_flat_trade_start_changed')
    return selected


def audit():
    if OUTPUT.exists():raise FileExistsError('existing_reachable_enumeration_refusing_repeat')
    OUTPUT.mkdir(parents=True,exist_ok=False);began=time.monotonic()
    write_json(OUTPUT/'attempt_started.json',dict(started_at=datetime.now().astimezone().isoformat(),
        financial_replays=0,network_calls=0,indicator_streams_repeated=0))
    try:
        sig_summary=json.loads((SIGNALS/'summary.json').read_text())
        sig_review_path=LINE/'outputs/stage005_independent_review/review_receipt.json'
        sig_review=json.loads(sig_review_path.read_text())
        if sig_review['p0_findings']or sig_review['p1_findings']:raise ValueError('initial_event_review_not_passed')
        if sha256(SIGNALS/'summary.json')!=sig_review['source_summary_sha256']:raise ValueError('reviewed_initial_summary_changed')
        cov_summary=json.loads((COVERAGE/'summary.json').read_text())
        for name in ['c0_potential_initial_events.csv','global_engine_calendar.csv']:
            if sha256(SIGNALS/name)!=sig_summary['artifacts'][name]:raise ValueError('frozen_initial_input_changed')
        if sha256(COVERAGE/'session_coverage.csv.gz')!=cov_summary['artifact_sha256']['session_coverage.csv.gz']:
            raise ValueError('frozen_coverage_changed')
        prior=json.loads((SIGNALS/'input_manifest.json').read_text())
        paths=[Path(__file__),PROTOCOL,SIGNALS/'summary.json',SIGNALS/'input_manifest.json',sig_review_path,
            SIGNALS/'c0_potential_initial_events.csv',SIGNALS/'global_engine_calendar.csv',COVERAGE/'summary.json',
            COVERAGE/'session_coverage.csv.gz',MAPPING,A0/'actual_strategy_settings.json',A0/'effective_parameters.json',
            STRATEGY,PROJECT/'qmt_roll_intraday_execution.py',
            PROJECT/'analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay.py',
            PROJECT/'analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac.py',STAGE008,STAGE008_REVIEW]
        inputs={str(path):sha256(path)for path in paths}
        for path in [MAPPING,STRATEGY,A0/'actual_strategy_settings.json',A0/'effective_parameters.json']:
            if str(path)in prior:
                expected=prior[str(path)]
                if isinstance(expected,dict):expected=expected['sha256']
                if inputs[str(path)]!=expected:raise ValueError('fixed_strategy_or_mapping_changed')
        actual=json.loads((A0/'actual_strategy_settings.json').read_text())[0]['actual'];contract=settings_contract(actual)
        metadata=set(json.loads((A0/'effective_parameters.json').read_text())['contract_sizes'])
        events=pd.read_csv(SIGNALS/'c0_potential_initial_events.csv',dtype=str,keep_default_na=False)
        if not events.c0_allowed.str.lower().eq('true').all():raise ValueError('unfiltered_c0_seed')
        seeds=events[['signal_date','product_vt_symbol','vt_symbol','execution_trade_date']].to_dict('records')
        full_calendar=pd.to_datetime(pd.read_csv(SIGNALS/'global_engine_calendar.csv').date)
        if full_calendar.duplicated().any()or not full_calendar.is_monotonic_increasing:raise ValueError('global_calendar_invalid')
        calendar=[day.strftime('%Y-%m-%d')for day in full_calendar if pd.Timestamp(contract['trade_start_date'])<=day<=pd.Timestamp(sig_summary['end'])]
        mapping_frame=pd.read_csv(MAPPING,usecols=['date','continuous_symbol_vt','main_contract_vt'],dtype=str,keep_default_na=False)
        products=set(events.product_vt_symbol)
        mapping=defaultdict(dict)
        for row in mapping_frame.loc[mapping_frame.continuous_symbol_vt.isin(products)&mapping_frame.date.isin(calendar)].itertuples():
            if row.main_contract_vt and row.main_contract_vt not in metadata:raise ValueError('mapping_contract_outside_metadata')
            if row.continuous_symbol_vt in mapping[row.date]:raise ValueError('duplicate_mapping_product_day')
            mapping[row.date][row.continuous_symbol_vt]=row.main_contract_vt
        columns=['vt_symbol','product_vt_symbol','date','real_daily_present','expected_minutes','available_minutes',
            'missing_minutes','anchor_present','complete','local_candidate_paths']
        coverage=pd.read_csv(COVERAGE/'session_coverage.csv.gz',usecols=columns)
        if coverage.duplicated(['vt_symbol','date']).any():raise ValueError('duplicate_cached_coverage')
        real=set(zip(coverage.loc[coverage.real_daily_present,'vt_symbol'],coverage.loc[coverage.real_daily_present,'date']))
        demand,pending,diagnostics=enumerate_demand(calendar,mapping,seeds,real,5)
        frame=pd.DataFrame(demand.values()).sort_values(['execution_trade_date','vt_symbol'])
        frame=frame.merge(coverage.rename(columns={'date':'execution_trade_date','product_vt_symbol':'cached_product'}),
            on=['vt_symbol','execution_trade_date'],how='left',validate='one_to_one',indicator=True)
        if not frame._merge.eq('both').all():raise ValueError('reachable_demand_outside_cached_bound')
        if not frame.product_vt_symbol.eq(frame.cached_product).all():raise ValueError('product_identity_disagreement')
        frame=frame.drop(columns=['_merge','cached_product'])
        frame['coverage_satisfied']=frame.complete.where(frame.requirement_kind.eq('full_session'),frame.anchor_present)
        frame['required_minutes']=frame.expected_minutes.where(frame.requirement_kind.eq('full_session'),1).astype(int)
        frame['missing_required_minutes']=frame.missing_minutes.where(frame.requirement_kind.eq('full_session'),(~frame.anchor_present).astype(int)).astype(int)
        frame['fill_bar_class']=frame.real_daily_present.map({True:'real_daily_bar',False:'carry_or_missing_real_bar'})
        frame['source_validation_required']=~frame.coverage_satisfied
        # Frozen Stage004 coverage stays unchanged.  Stage008 is a separately
        # qualified local candidate, not silently merged into this availability.
        candidate=json.loads(STAGE008.read_text());review=json.loads(STAGE008_REVIEW.read_text())
        if candidate['accepted']is not True or review.get('p0_findings')or review.get('p1_findings'):
            raise ValueError('stage008_candidate_not_qualified')
        frame['stage008_independently_qualified_candidate']=frame.vt_symbol.eq(candidate['vt_symbol'])&frame.execution_trade_date.eq(candidate['target_trading_date'])
        frame.to_csv(OUTPUT/'demand.csv',index=False)
        gaps=frame.loc[~frame.coverage_satisfied].copy();gaps.to_csv(OUTPUT/'gaps.csv',index=False)
        pd.DataFrame(pending).to_csv(OUTPUT/'terminal_pending.csv',index=False)
        pd.DataFrame(diagnostics.pop('state_counts')).to_csv(OUTPUT/'state_counts.csv',index=False)
        pd.DataFrame(diagnostics.pop('transitions')).to_csv(OUTPUT/'mandatory_transitions.csv',index=False)
        if not all(sha256(path)==value for path,value in inputs.items()):raise ValueError('input_changed_during_enumeration')
        write_json(OUTPUT/'input_manifest.json',inputs)
        result=dict(status='completed_pure_reachable_demand_pending_independent_review',elapsed_seconds=time.monotonic()-began,
            network_calls=0,financial_replays=0,account_engines=0,strategy_initializations=0,outcome_fields_read=0,
            indicator_streams_repeated=0,weekly_tables_repeated=0,model_fits=0,source_writes=0,
            cache_or_overlay_written=False,execution_fallback_enabled=False,production_qualified=False,
            all_inputs_unchanged=True,calendar_batches=len(calendar),initial_seed_events=len(seeds),
            initial_seed_nonterminal_events=sum(bool(seed['execution_trade_date'])for seed in seeds),
            settings_contract=contract,diagnostics=diagnostics,required_sessions=len(frame),
            requirement_kind_counts={str(key):int(value)for key,value in frame.requirement_kind.value_counts().items()},
            complete_required_sessions=int(frame.coverage_satisfied.sum()),gap_sessions=len(gaps),
            gap_required_minutes=int(gaps.missing_required_minutes.sum()),gap_contracts=int(gaps.vt_symbol.nunique()),
            gap_full_sessions=int(gaps.requirement_kind.eq('full_session').sum()),gap_anchor_sessions=int(gaps.requirement_kind.eq('anchor').sum()),
            gap_real_daily_sessions=int(gaps.real_daily_present.sum()),gap_carry_or_missing_real_sessions=int((~gaps.real_daily_present).sum()),
            signal_carry_possible_sessions=int(frame.signal_carry_possible.sum()),terminal_pending_demands=len(pending),
            stage008_qualified_candidates_in_demand=int(frame.stage008_independently_qualified_candidate.sum()),
            coverage_scope='Frozen Stage004 base+Stage002 only. Stage008 qualified rows are annotated, not merged.',
            interpretation=['Overapproximate necessary data bound, not actual trades; optional exits/shape/funds omitted.',
                'Mandatory closes remove old states at next global batch; no ever-main-to-end expansion.',
                'All reachable holding days contribute possible CLOSE anchors, including carry overapproximation.',
                'Missing real daily fill bars and terminal events are constraints, not automatic download requests.',
                'Coverage counts do not qualify prices; every added source requires Stage011 qualification.'])
        result['artifact_sha256']={path.name:sha256(path)for path in OUTPUT.iterdir()if path.is_file()}
        write_json(OUTPUT/'summary.json',result)
        print(json.dumps({key:result[key]for key in ['status','required_sessions','gap_sessions','gap_full_sessions','gap_anchor_sessions','gap_required_minutes','gap_carry_or_missing_real_sessions']}))
    except BaseException as error:
        write_json(OUTPUT/'enumeration_failure.json',dict(error_type=type(error).__name__,error=str(error),network_calls=0,financial_replays=0))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--enumerate',action='store_true',required=True);parser.parse_args();audit()
