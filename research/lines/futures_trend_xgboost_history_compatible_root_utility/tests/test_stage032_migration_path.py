import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT/'tools/stage032_migration_path.py'


def module():
    assert TOOL.exists(), 'migration path implementation missing'
    spec = importlib.util.spec_from_file_location('test_path032',TOOL)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def context(m,event):
    row = {key:event[key] for key in ['decision_date','product_vt_symbol','contract_vt_symbol']}
    row.update(source_date=(pd.Timestamp(event['decision_date'])-pd.Timedelta(days=1)).strftime('%Y-%m-%d'),
        window_start=(pd.Timestamp(event['decision_date'])-pd.Timedelta(days=8)).strftime('%Y-%m-%d'))
    row.update(dict(zip(m.migration().FEATURES,[.1,-.2])))
    return pd.DataFrame([row]).set_index(['decision_date','contract_vt_symbol'],drop=False)


@pytest.mark.parametrize('direction',['long','short'])
def test_actual_contract_context_preserves_current_account_without_direction_flip(direction):
    m = module()
    event = dict(decision_date='2022-02-08',product_vt_symbol='rb.SHFE',contract_vt_symbol='rb2205.SHFE',
        direction=direction,margin_to_equity_before=.371)
    result = m.enrich_event(event,context(m,event))
    assert result['margin_to_equity_before'] == .371
    assert result[m.migration().FEATURES[0]] == .1
    assert result[m.migration().FEATURES[1]] == -.2
    assert result['window_start'] < result['source_date'] < result['decision_date']
    assert 'source_date' not in event


@pytest.mark.parametrize('kind',['missing','contract','product','future','duplicate_enrichment'])
def test_runtime_missing_or_invalid_context_blocks(kind):
    m = module()
    event = dict(decision_date='2022-02-08',product_vt_symbol='rb.SHFE',contract_vt_symbol='rb2205.SHFE')
    ctx = context(m,event)
    if kind == 'missing':
        ctx = ctx.iloc[:0]
    elif kind == 'contract':
        event['contract_vt_symbol'] = 'rb2210.SHFE'
    elif kind == 'product':
        event['product_vt_symbol'] = 'au.SHFE'
    elif kind == 'future':
        ctx['source_date'] = event['decision_date']
    else:
        event['window_start'] = '2022-01-31'
    with pytest.raises((ValueError,RuntimeError)):
        m.enrich_event(event,ctx)


def test_worker_bootstrap_has_no_site_import_before_sandbox():
    module()
    code = 'import runpy,sys; m=runpy.run_path('+repr(str(TOOL))+ "); m['pipeline']().configured(123); assert 'numpy' not in sys.modules and 'xgboost' not in sys.modules"
    result = subprocess.run([sys.executable,'-I','-S','-B','-c',code],capture_output=True,text=True)
    assert result.returncode == 0,result.stderr


def test_isolated_pipeline_routes_new_worker():
    m = module()
    parent = m.pipeline()
    assert parent.STAGE == 'stage032_migration_path'
    assert parent.OUTPUT == ROOT/'artifacts/stage032_migration_path'
    assert parent.FREEZE == ROOT/'stages/stage032_input_freeze.json'
    assert parent.__file__ == str(TOOL)
    assert m.load('stage009_full_path_replay').STAGE == 'stage009_full_path_replay'


@pytest.mark.parametrize('tamper',[None,'feature','source','window','account','prediction'])
def test_parent_rebuilds_current_c_features_time_evidence_and_actions(tamper):
    m = module()
    batch = m.load('stage004_label_batch')
    formal = json.loads((batch.REFERENCE/'receipt.json').read_text())['formal_identity']
    raw = batch.read_frame(batch.REFERENCE/'entry_candidates.csv')
    candidates = raw.loc[raw.candidate_index.eq(241)].copy()
    candidates['estimated_equity'] = 500000
    candidates['total_margin_in_use_before'] = 100000
    event = batch.load_history().build_features(candidates,formal).iloc[0].to_dict()
    ctx = context(m,event)
    event = m.enrich_event(event,ctx)
    prediction = dict(cutoff=event['decision_date'][:7]+'-01',status='predicted',skip=True,
        return_marginal=-.1,drawdown_marginal=-.2)
    records = pd.DataFrame([{**event,**prediction}])
    candidates['candidate_status'] = 'skipped'
    candidates['skip_reason'] = 'research_xgb_predicted_harm'
    candidates['is_opened'] = 0
    calls = []
    def predictor(current):
        calls.append(current)
        assert current['margin_to_equity_before'] == .2
        assert all(name in current for name in m.migration().FEATURES)
        return prediction
    changes = {'feature':(m.migration().FEATURES[0],123.),'source':('source_date',event['decision_date']),
        'window':('window_start',event['source_date']),'account':('margin_to_equity_before',0.),
        'prediction':('return_marginal',-.5)}
    if tamper:
        key,value = changes[tamper]
        records[key] = value
        with pytest.raises((RuntimeError,AssertionError)):
            m.validate_decisions(candidates,records,formal,predictor,ctx)
    else:
        result = m.validate_decisions(candidates,records,formal,predictor,ctx)
        assert result['skip_count'] == 1 and len(calls) == 1
