import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools/stage016_macro_path.py'


def module():
    assert TOOL.exists(), 'macro path implementation missing'
    spec = importlib.util.spec_from_file_location('test_macro_path', TOOL)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def context(m, day='2022-02-08'):
    row = {'decision_date':day, 'source_date':'2022-02-07', 'coverage_status':'available'}
    row.update(dict(zip(m.macro().RAW_FEATURES, [0.1,-0.2,1.1,0.8,-0.3])))
    return pd.DataFrame([row])


def test_enrichment_preserves_current_account_and_uses_direction():
    m = module()
    event = {'decision_date':'2022-02-08','direction':'short','margin_to_equity_before':0.371}
    result = m.enrich_event(event,context(m))
    assert result['margin_to_equity_before'] == 0.371
    assert result['directional_cffex_equity_momentum_20d'] == -0.1
    assert result['directional_cffex_rates_momentum_20d'] == 0.2
    assert result['cffex_equity_vol_ratio_20_120'] == 1.1
    assert 'source_date' not in event
    assert result['source_date'] == '2022-02-07'


def test_enrichment_rejects_missing_or_same_day_source():
    m = module()
    event = {'decision_date':'2022-02-08','direction':'long'}
    with pytest.raises(RuntimeError):
        m.enrich_event(event,context(m).iloc[:0])
    altered = context(m)
    altered['source_date'] = event['decision_date']
    with pytest.raises(RuntimeError):
        m.enrich_event(event,altered)


def test_worker_bootstrap_keeps_site_imports_out():
    module()
    code = 'import runpy,sys; m=runpy.run_path(' + repr(str(TOOL)) + "); m['pipeline']().configured(123); assert 'numpy' not in sys.modules and 'xgboost' not in sys.modules"
    result = subprocess.run([sys.executable,'-I','-S','-B','-c',code],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr


def test_pipeline_is_new_entry_and_uses_frozen_parent_without_mutating_it():
    m = module()
    parent = m.pipeline()
    assert parent.STAGE == 'stage016_macro_path'
    assert parent.OUTPUT == ROOT/'artifacts/stage016_macro_path'
    assert parent.FREEZE == ROOT/'stages/stage016_input_freeze.json'
    assert parent.__file__ == str(TOOL)
    fresh = m.load('stage009_full_path_replay')
    assert fresh.STAGE == 'stage009_full_path_replay'
    assert fresh.__file__ != parent.__file__


@pytest.mark.parametrize('tamper',[None,'macro','source','account','prediction'])
def test_parent_audit_rebuilds_all_fifteen_features_and_predictions(tamper):
    m = module()
    batch = m.load('stage004_label_batch')
    formal = json.loads((batch.REFERENCE/'receipt.json').read_text())['formal_identity']
    raw = batch.read_frame(batch.REFERENCE/'entry_candidates.csv')
    candidates = raw.loc[raw.candidate_index.eq(241)].copy()
    candidates['estimated_equity'] = 500000
    candidates['total_margin_in_use_before'] = 100000
    event = batch.load_history().build_features(candidates,formal).iloc[0].to_dict()
    ctx = context(m,event['decision_date'])
    ctx['source_date'] = (pd.Timestamp(event['decision_date'])-pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    event = m.enrich_event(event,ctx)
    prediction = {'cutoff':event['decision_date'][:7]+'-01', 'status':'predicted', 'skip':True,
                  'return_marginal':-0.1, 'drawdown_marginal':-0.2}
    records = pd.DataFrame([{**event,**prediction}])
    candidates['candidate_status'] = 'skipped'
    candidates['skip_reason'] = 'research_xgb_predicted_harm'
    candidates['is_opened'] = 0
    calls = []
    def predictor(current):
        calls.append(current)
        assert current['margin_to_equity_before'] == 0.2
        assert current['source_date'] == ctx.source_date.iloc[0]
        assert all(name in current for name in m.macro().FEATURES)
        return prediction
    if tamper == 'macro':
        records[m.macro().FEATURES[0]] = 123.0
    elif tamper == 'source':
        records['source_date'] = records['decision_date']
    elif tamper == 'account':
        records['margin_to_equity_before'] = 0.0
    elif tamper == 'prediction':
        records['return_marginal'] = -0.5
    if tamper is not None:
        with pytest.raises((RuntimeError,AssertionError)):
            m.validate_decisions(candidates,records,formal,predictor,ctx)
    else:
        result = m.validate_decisions(candidates,records,formal,predictor,ctx)
        assert result['skip_count']==1 and len(calls)==1
