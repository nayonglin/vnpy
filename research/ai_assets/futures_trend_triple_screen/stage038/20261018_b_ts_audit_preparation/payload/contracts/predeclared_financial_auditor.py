"""Independent B_TS audit preparation; no actual outputs before terminal evidence.

The accepted cash/inventory/identity algorithms remain frozen in Stage030/033.
This module adds an independent scalar B final-budget and timing check, then
waits for root to supply exact final source/schema pins and a real completion.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
SOURCE=LINE/'outputs/stage036_b_ts_account/B_TS'
OUT=LINE/'outputs/stage038_independent_account_review'
INHERITED_033=LINE/'tools/stage033_independent_checkpoint_account_review.py'
INHERITED_033_SHA='940ab1180392c7ca3a6cceef15b3bb33f3d37d6510c48f86b9e7c109b7205cbf'
INHERITED_030_SHA='3fe153c379b95b67aa1f083381b55786c1afb85efd5896f035d91c4eb55dac15'
RUNNER=LINE/'tools/stage036_run_b_ts_checkpoint.py'
PROTOCOL=LINE/'stages/20261018_0333_stage035_b_ts_execution_contract.md'
BUDGET_CONTRACT=LINE/'stages/20261018_0330_stage035_b_ts_budget_design_review.md'
# Populated only from root's final reviewed implementation, never guessed from
# a running process, draft file or historical C account.
FROZEN_RUNNER_SHA='34563257e25e49b19c9631e06cd9107fc26cfd954713739e01a1bf67d574ff43'
FROZEN_ALPHA_SHA={'stage028_ordered_strategy.py':'d4f870355796c98625031f233dfba31f97db10422c894076acf436279f141c48',
    'stage028_ordered_engine.py':'f7d7450495bb09407dc85ce6fe73fd700b2732a2e57dc8f6185abf199967af23',
    'stage035_b_ts_pricing.py':'d45e8a5b4b7503a33c137df7decbd56947c2d1df77b7c73c5e7524326ae1018f',
    'stage035_b_ts_strategy.py':'fc357eb4a44a384d816acaff5fadaa99d91dfc7f8ec8fbd22954c9ca3837b09e'}
FROZEN_SCHEMA='stage036_raw_account_checkpoint_v1'
FROZEN_RESULT_SCOPE='offline_standalone_initial_triple_screen_B_TS_vs_reused_A0_attempt2'
EXECUTION_REVIEW=LINE/'outputs/stage035_independent_review/review_receipt.json'
EXECUTION_REVIEW_SHA='10c74fc9105b0ab937966817ef420b59f10c774c75a7ae42d4288ccc826c5d0c'
ACTUAL_AUDIT_AUTHORIZED=False
NEW_SIGNALS={'long_triple_screen','short_triple_screen'}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()


def frozen_033():
    assert digest(INHERITED_033)==INHERITED_033_SHA,'accepted Stage033 source changed'
    spec=importlib.util.spec_from_file_location('stage038_frozen_033',INHERITED_033)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module.BASE_SHA==INHERITED_030_SHA
    return module


def replaced_exact(source,before,after,count):
    assert source.count(before)==count,('inherited adapter source pattern changed',before,source.count(before),count)
    return source.replace(before,after)


def make_bound_audit():
    """Controlled in-memory identity adapters; accepted source files never change.

    Only explicit arm/attempt/schema/protocol/new-alpha labels are replaced.
    No arithmetic, cash/position logic, source guard or financial gate is cut.
    """
    assert digest(INHERITED_033)==INHERITED_033_SHA
    assert digest(EXECUTION_REVIEW)==EXECUTION_REVIEW_SHA
    review=json.loads(EXECUTION_REVIEW.read_text())
    assert review['independent_review']is True and review['status']=='limited_B_code_and_real_native_composition_pass'
    assert review['p0_findings']==review['p1_findings']==review['p2_findings']==0
    assert review['final_sources_sha256']['stage036_run_b_ts_checkpoint.py']==FROZEN_RUNNER_SHA
    for name in('stage035_b_ts_pricing.py','stage035_b_ts_strategy.py'):
        assert review['final_sources_sha256'][name]==FROZEN_ALPHA_SHA[name]
    source=INHERITED_033.read_text()
    edits=[("'C_TS'","'B_TS'",3),
        ('stage031_run_ordered_checkpoint.py','stage036_run_b_ts_checkpoint.py',2),
        ('stage031_raw_account_checkpoint_v1','stage036_raw_account_checkpoint_v1',1),
        ('stage031_raw_checkpoint_manifest_v1','stage036_raw_checkpoint_manifest_v1',1),
        ('stage031_engine_validation_seal_v1','stage036_engine_validation_seal_v1',1),
        ('stage031_run_context_v1','stage036_run_context_v1',1),
        ("row['attempt']==2","row['attempt']==1",1),
        ("prov['attempt']==summary['attempt']==2","prov['attempt']==summary['attempt']==1",1),
        ("prov['alpha_changed_from_Stage028']is False","prov['alpha_changed_from_Stage028']is True",1),
        ('original_u_close_quantity_and_stop_frozen','u_trigger_priced_quantity_and_original_u_stop_frozen',1),
        ('20261018_0234_stage028_conditional_execution_contract.md','20261018_0333_stage035_b_ts_execution_contract.md',1),
        ('before the 110 run-time reads','before the run-time reads',1)]
    for edit in edits:source=replaced_exact(source,*edit)
    bound=ModuleType('stage038_bound_stage033');bound.__file__=__file__
    exec(compile(source,str(INHERITED_033),'exec'),bound.__dict__)
    bound.SOURCE=SOURCE;bound.OUT=OUT;bound.RUNNER=RUNNER
    bound.PROTOCOL=LINE/'stages/20261018_0338_stage036_b_ts_checkpoint_contract.md'
    bound.FROZEN_RUNNER_SHA=FROZEN_RUNNER_SHA;bound.FROZEN_MODULES=FROZEN_ALPHA_SHA
    bound.FROZEN_PAYLOAD_SCHEMA=FROZEN_SCHEMA
    bound.PARENT_RUNNER_SHA='3af932bdbde9ae607c507ff8630dde0a0b03f190ca88be94fa43ce5910b0b860'
    original_raw=bound.raw_export_equivalence
    def b_raw_equivalence(base,source,payload,bindings,prov,summary):
        bindings=original_raw(base,source,payload,bindings,prov,summary)
        assert prov['final_B_budget_clamp_enabled']is True and prov['original_native_quantity_policy_preserved']is False
        assert bound.json_projection(payload['ordered'])==bound.read(source/'ordered_audits.json')
        bindings['B_signal_budget_review']=b_artifact_review(bound,payload)
        return bindings
    bound.raw_export_equivalence=b_raw_equivalence
    inherited_base_path=bound.BASE
    assert digest(inherited_base_path)==INHERITED_030_SHA
    base_source=inherited_base_path.read_text()
    base_edits=[("'C_TS'","'B_TS'",2),
        ("row['setup_day']<row['signal_day']","row['setup_day']<=row['signal_day']",1),
        ("assert len(match)==1,('ordinary_flat_not_unknown_fallback',row['trade_id'])",
         "assert False,('B ordinary flat initial fallback is prohibited',row['trade_id'])",1),
        ('observed_native_selected','observed_B_selected',1)]
    for edit in base_edits:base_source=replaced_exact(base_source,*edit)
    base=ModuleType('stage038_bound_stage030');base.__file__=__file__
    exec(compile(base_source,str(inherited_base_path),'exec'),base.__dict__)
    base.SOURCE=SOURCE;base.OUT=OUT;base.SCOPE=FROZEN_RESULT_SCOPE
    base.NAMES+=['actual_trade_identities.csv','entry_contract_used.md','run_context.json','export_success.json',
        'stage035_b_ts_pricing.py','stage035_b_ts_strategy.py']
    base.audit_provenance=lambda source,evidence,hashes:bound.provenance_audit(base,source,evidence,hashes)
    return bound,base,dict(stage033=[dict(before=a,after=b,occurrences=c)for a,b,c in edits],
        stage030=[dict(before=a,after=b,occurrences=c)for a,b,c in base_edits])


def b_artifact_review(bound,payload):
    """Exact source-field projection; every budget is traced to its u snapshot."""
    decisions=payload['ordered']['decision'];candidates=payload['frames']['entry_candidates'].copy()
    candidates['date']=candidates.date.astype(str).str[:10]
    canonical_timing=[];canonical_budget=[];admitted={};serial=0
    for row in decisions:
        assert row['arm']=='B_TS'and row['baseline_fallback']is False
        signal=str(row.get('signal')or'');intent=row.get('intent_id')
        unknown=row.get('cancel_reason')in('weekly_unknown','fi_unknown')
        canonical_timing.append(dict(arm=row['arm'],product=row['product'],signal_day=row['signal_day'],
            execution_day=row.get('execution_day'),setup_day=row.get('setup_day'),intent_id=intent,
            signal=signal,baseline_fallback=row['baseline_fallback'],unknown=unknown))
        if 'b_ts_final_budget_volume_before'not in row:continue
        serial+=1;prefix='b_ts_final_budget_';field=lambda key:row[prefix+key]
        direction=row['direction'];assert signal==direction+'_triple_screen'
        matches=candidates.loc[candidates.date.eq(row['signal_day'])&candidates.product_vt_symbol.eq(row['product'])&
            candidates.contract_vt_symbol.eq(row['contract'])&candidates.direction.eq(direction)&candidates.signal.eq(signal)]
        assert len(matches)==1,('B original candidate snapshot not unique',row['signal_day'],row['product'])
        candidate=matches.iloc[0]
        T=field('trigger');size=field('contract_size');tick=field('pricetick')
        for key,value in [('b_ts_trigger',T),('b_ts_trigger_price',T),('planned_entry_price',T),
            ('stop_price',field('stop_price')),('risk_per_contract',field('risk_per_contract')),
            ('margin_per_contract',field('margin_per_contract')),('selected_volume',field('volume_after'))]:
            same(candidate[key],value,'B candidate frozen '+key)
        same(candidate.signal_close,row['signal_close'],'original signal close retained')
        for key,value in row.items():
            if key.startswith(prefix):
                actual=candidate[key]
                if value is None:assert bound.missing(actual)
                elif isinstance(value,(float,int)):same(actual,value,'B decision/candidate '+key)
                else:assert str(actual)==str(value),('B decision/candidate metadata changed',key)
        canonical_budget.append(dict(arm='B_TS',signal=signal,signal_day=row['signal_day'],product=row['product'],
            original_status='opened',rank=field('original_rank'),stable_order=serial,
            volume_before=field('volume_before'),volume_after=field('volume_after'),trigger=T,
            stop=field('stop_price'),size=size,margin_ratio=field('margin_ratio'),original_min_risk=max(tick*size,1.),
            risk_per_contract=field('risk_per_contract'),margin_per_contract=field('margin_per_contract'),
            risk_amount=field('risk_amount'),limited_balance=field('limited_balance'),
            single_trade_capital_limit=field('single_trade_capital_limit'),budget_equity_u=field('equity_u'),
            reserved_margin_before=field('reserved_margin_before'),min_position_size=field('min_position_size'),
            max_position_size=field('max_position_size'),cluster_name=field('cluster_name'),
            gross_margin_before=field('gross_margin_before'),gross_cluster_margin_before=field('gross_cluster_margin_before'),
            original_contracts_by_risk=candidate.contracts_by_risk,original_contracts_by_margin=candidate.contracts_by_margin,
            original_contracts_by_single=candidate.contracts_by_single_trade_cap,broker_on=field('broker_enabled'),
            broker_multiplier=field('broker_margin_multiplier'),broker_cap_ratio=field('broker_cap_ratio'),
            cluster_on=field('cluster_enabled'),cluster_cap_amount=field('cluster_cap_amount'),
            cluster_reserved_margin_before=field('cluster_reserved_margin_before'),candidate_status=row['candidate_status'],
            skip_reason=row.get('skip_reason',''),predicted_risk_T=field('predicted_risk_T'),predicted_margin_T=field('predicted_margin_T'),
            reported_final_limits={key:field('contracts_by_'+label)for key,label in
                [('risk','risk'),('margin','margin'),('single','single'),('broker','broker'),('cluster','cluster')]}))
        if int(field('volume_after'))>0:
            assert intent and intent not in admitted
            admitted[intent]=row
    canonical_budget.sort(key=lambda row:(row['signal_day'],row['rank'],row['stable_order']))
    timing=audit_b_timing(canonical_timing);budget=audit_b_budget_rows(canonical_budget)
    for row in payload['ordered']['execution']:
        assert row['arm']=='B_TS'and row['native_signal']in NEW_SIGNALS
        assert row['intent_id']in admitted
        source=admitted[row['intent_id']]
        same(row['quantity'],source['b_ts_final_budget_volume_after'],'B executed frozen final q')
        same(row['trigger'],source['b_ts_final_budget_trigger'],'B executed frozen T')
        same(row['forecast_risk_amount'],source['b_ts_final_budget_predicted_risk_T'],'B event frozen T risk')
        same(row['forecast_margin_amount'],source['b_ts_final_budget_predicted_margin_T'],'B event frozen T margin')
    for row in payload['ordered']['fill']:
        assert row['arm']=='B_TS'and row['intent_id']in admitted
        source=admitted[row['intent_id']]
        for key,value in source.items():
            if key.startswith('b_ts_'):assert row[key]==value,('B fill lost frozen budget',key)
    flat=candidates.loc[candidates.entry_context.eq('flat_entry')]
    assert flat.signal.isin(NEW_SIGNALS).all(),'native initial labels leaked into B'
    assert not flat.candidate_status.eq('opened').any(),'B ordinary flat fallback opened'
    settings=payload['actual'][0]['actual']
    assert settings['fixed_size']==0 and settings['stage830_broker_margin_multiplier']==1.65
    for row in canonical_budget:
        assert row['min_position_size']==settings['min_position_size']and row['max_position_size']==settings['max_position_size']
    return dict(timing=timing,final_budget=budget,
        initial_signal_labels=sorted(NEW_SIGNALS),unknown_baseline_fallback_allowed=False,
        source_checked_generic_entry_filters=True,source_checked_generic_OI_mode='volume-OI then OI then regular',
        fixed_size=0,original_commission_parameters_preserved=True,
        model_domain_limit='new signal label changes same_signal feature distribution; frozen model/19 numeric features do not establish unseen-category calibration',
        raw_market_histories_recomputed=False)


def number(row,key,positive=False):
    value=float(row[key]);assert math.isfinite(value),(key,'nonfinite')
    assert value>0 if positive else value>=0,(key,'invalid domain')
    return value


def integer(row,key,positive=False):
    value=number(row,key,positive);assert value==int(value),(key,'noninteger')
    return int(value)


def same(a,b,label):
    assert math.isclose(float(a),float(b),rel_tol=1e-11,abs_tol=1e-7),(label,a,b)


def audit_b_timing(rows):
    """Canonical rows are bound to exact final B artifact fields after review."""
    seen=set();intent_rows=0;unknown_rows=0
    for row in rows:
        assert row['arm']=='B_TS'and row['baseline_fallback']is False
        key=(row['signal_day'],row['product']);assert key not in seen,('duplicate B observation',key);seen.add(key)
        if row.get('unknown'):
            unknown_rows+=1;assert not row.get('intent_id')and not row.get('signal'),('B unknown fallback',key)
        if row.get('intent_id'):
            intent_rows+=1
            assert row['setup_day']<=row['signal_day']<row['execution_day'],('B setup/signal/execute chronology',key)
            assert row['signal']in NEW_SIGNALS,('native signal leaked into B',key)
    return dict(observation_rows=len(rows),intent_rows=intent_rows,unknown_rows=unknown_rows,
        baseline_fallback_rows=0,same_day_preparation_permitted=True)


def audit_b_budget_rows(rows):
    """Scalar final-q recomputation using original admitted gross prefixes.

    This is an audit-only canonical representation, not a strategy allocator.
    Final adapters must prove each field comes from the frozen u sizing/plan.
    """
    gross=defaultdict(float);cluster_gross=defaultdict(float);last_order={}
    checked=[];reduced=zero=0
    for row in rows:
        assert row['arm']=='B_TS'and row['signal']in NEW_SIGNALS
        assert row['original_status']=='opened'
        day=row['signal_day'];rank=integer(row,'rank',True);serial=integer(row,'stable_order')
        order=(rank,serial)
        assert day not in last_order or last_order[day]<=order,'B admitted order changed'
        last_order[day]=order
        a=integer(row,'volume_before',True);q=integer(row,'volume_after')
        T=number(row,'trigger',True);S=number(row,'stop',True);size=number(row,'size',True)
        mr=number(row,'margin_ratio',True);min_risk=number(row,'original_min_risk',True)
        rho=max(abs(T-S)*size,min_risk);margin=T*size*mr
        same(row['risk_per_contract'],rho,'T risk');same(row['margin_per_contract'],margin,'T margin')
        R=number(row,'risk_amount');L=number(row,'limited_balance');K=number(row,'single_trade_capital_limit')
        E=number(row,'budget_equity_u',True);B=number(row,'reserved_margin_before')
        lo=integer(row,'min_position_size',True);hi=integer(row,'max_position_size',True);assert hi>=lo
        P=gross[day];ck=(day,row['cluster_name']);Pc=cluster_gross[ck]
        same(row['gross_margin_before'],P,'gross admitted prefix')
        same(row['gross_cluster_margin_before'],Pc,'gross same-cluster prefix')
        n_risk=math.floor(R/rho);n_base_margin=math.floor(L/margin);n_single=math.floor(K/margin)
        assert integer(row,'original_contracts_by_risk')==n_risk,'T pricing risk count mismatch'
        assert integer(row,'original_contracts_by_margin')==n_base_margin,'T pricing margin count mismatch'
        assert integer(row,'original_contracts_by_single')==n_single,'T pricing single count mismatch'
        limits=dict(risk=n_risk,margin=math.floor(max(0.,L-P)/margin),single=n_single,max_position=hi)
        if row['broker_on']:
            b=number(row,'broker_multiplier',True);c=number(row,'broker_cap_ratio')
            limits['broker']=math.floor(max(0.,E*c/b-B-P)/margin)
        if row['cluster_on']:
            C=number(row,'cluster_cap_amount');H=number(row,'cluster_reserved_margin_before')
            limits['cluster']=math.floor(max(0.,C-H-Pc)/margin)
        if 'reported_final_limits'in row:
            for key,value in row['reported_final_limits'].items():
                if value is None:assert key not in limits
                else:assert int(value)==limits[key],('B reported final integer cap differs',key,value,limits[key])
        expected=max(0,min([a,*limits.values()]));expected=0 if 0<expected<lo else expected
        assert q==expected,('final B quantity not contractual min',row['product'],q,expected,limits)
        assert q<=a;reduced+=q<a;zero+=q==0
        if q==0:assert row['candidate_status']=='filtered'and row['skip_reason']=='b_ts_final_budget_zero'
        else:assert row['candidate_status']=='conditional_pending'
        same(row['predicted_risk_T'],q*rho,'frozen predicted risk T')
        same(row['predicted_margin_T'],q*margin,'frozen predicted margin T')
        # Crucial: original a is reserved in the conservative prefix even if
        # q is reduced or zero. No candidate/slot is refilled here.
        gross[day]+=a*margin;cluster_gross[ck]+=a*margin
        checked.append(dict(day=day,product=row['product'],a=a,q=q,gross=P,limits=limits))
    return dict(admitted_rows=len(rows),reduced_rows=reduced,zero_rows=zero,
        reallocated_budget_or_slots=False,independent_scalar_rows=checked)


def fixture_row(product='a.SHFE',rank=1,a=12,R=1200.,T=111.,S=99.,margin=111.,gross=0.,gross_cluster=0.,q=10):
    return dict(arm='B_TS',signal='long_triple_screen',signal_day='2026-01-06',product=product,
        original_status='opened',rank=rank,stable_order=rank,volume_before=a,volume_after=q,
        trigger=T,stop=S,size=10.,margin_ratio=margin/(T*10.),original_min_risk=1.,
        risk_per_contract=abs(T-S)*10.,margin_per_contract=margin,risk_amount=R,limited_balance=100000.,
        single_trade_capital_limit=100000.,budget_equity_u=100000.,reserved_margin_before=0.,
        min_position_size=1,max_position_size=500,cluster_name=product,gross_margin_before=gross,
        gross_cluster_margin_before=gross_cluster,original_contracts_by_risk=math.floor(R/(abs(T-S)*10.)),
        original_contracts_by_margin=math.floor(100000./margin),original_contracts_by_single=math.floor(100000./margin),
        broker_on=True,broker_multiplier=1.65,broker_cap_ratio=1.,cluster_on=False,
        cluster_cap_amount=30000.,cluster_reserved_margin_before=0.,candidate_status='conditional_pending'if q else'filtered',
        skip_reason=''if q else'b_ts_final_budget_zero',predicted_risk_T=q*abs(T-S)*10.,predicted_margin_T=q*margin)


def self_test():
    # Do not call any old suite/fixture or load a strategy/model/market source.
    assert digest(INHERITED_033)==INHERITED_033_SHA
    rows=[fixture_row()];r=audit_b_budget_rows(rows);assert r['reduced_rows']==1
    rows=[fixture_row('a.SHFE',1,2,R=120.,margin=15000.,q=1),
        fixture_row('b.SHFE',2,2,margin=15000.,gross=30000.,q=2),
        fixture_row('c.SHFE',3,2,margin=15000.,gross=60000.,q=0)]
    for row in rows:row['cluster_on']=True
    r=audit_b_budget_rows(rows);assert[r['q']for r in r['independent_scalar_rows']]==[1,2,0]
    wrong=[dict(row)for row in rows];wrong[2]['gross_margin_before']=45000.
    try:audit_b_budget_rows(wrong)
    except AssertionError:pass
    else:raise AssertionError('recycled prefix was accepted')
    timing=[dict(arm='B_TS',product='a.SHFE',setup_day='2026-01-06',signal_day='2026-01-06',execution_day='2026-01-07',
        intent_id='B.1',signal='long_triple_screen',baseline_fallback=False,unknown=False)]
    assert audit_b_timing(timing)['intent_rows']==1
    wrong=[dict(timing[0],baseline_fallback=True)]
    try:audit_b_timing(wrong)
    except AssertionError:pass
    else:raise AssertionError('B native fallback was accepted')
    # Compile only the exact source adapters; no accepted old fixture is called.
    make_bound_audit()
    assert digest(RUNNER)==FROZEN_RUNNER_SHA
    assert all(digest(LINE/'tools'/name)==value for name,value in FROZEN_ALPHA_SHA.items())
    return dict(status='B_final_source_field_adapters_bound_finite_nonfinancial_fixtures_passed_wait_execution_review',
        new_fixture_groups=3,old_fixture_suites_rerun=0,financial_replays=0,actual_B_outputs_accessed=False,
        inherited_033_sha256=INHERITED_033_SHA,wrapper_sha256=digest(__file__))


def main():
    parser=argparse.ArgumentParser(description=__doc__);action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--self-test',action='store_true');action.add_argument('--completion-evidence',type=Path)
    args=parser.parse_args()
    if args.self_test:result=self_test()
    else:
        assert all((FROZEN_RUNNER_SHA,FROZEN_ALPHA_SHA,FROZEN_SCHEMA,FROZEN_RESULT_SCOPE)), 'final_B_source_and_schema_not_yet_pinned'
        assert ACTUAL_AUDIT_AUTHORIZED,'root_actual_terminal_followup_not_yet_authorized'
        bound,base,adapters=make_bound_audit()
        result=base.run(args.completion_evidence)
        result.update(stage='Stage038',arm='B_TS',attempt=1,source_scope='Stage036 B_TS attempt1 only',
            wrapper_sha256=digest(__file__),review_script_sha256=digest(__file__),
            inherited_stage033_sha256=INHERITED_033_SHA,baseline_algorithm_sha256=INHERITED_030_SHA,
            exact_runner_sha256=FROZEN_RUNNER_SHA,frozen_B_modules_sha256=FROZEN_ALPHA_SHA,
            controlled_in_memory_consumer_adapters=adapters,checkpoint_review=base._stage033_checkpoint_review)
        bound.supplementary_risk_and_holding_review(base,result)
        result['confidence_limit']='single fixed independent B historical path; existing selection bias and new same_signal model-feature domain; no multistart/OOS/cost qualification'
        OUT.mkdir(exist_ok=True,parents=True);bound.write(OUT/'account_checks.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
