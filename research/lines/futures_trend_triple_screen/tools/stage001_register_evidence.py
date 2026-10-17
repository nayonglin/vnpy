"""Preserve selected reproducibility assets, excluding raw OHLC and big positions."""
from pathlib import Path
import hashlib
import gzip
import json
import shutil
import sys
import pandas as pd

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
OUT=LINE/'outputs'
sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
from qmt_roll_ai_artifact_registry import AiArtifact,register_experiment_artifacts


def main():
    artifacts=[]
    contract='triple_screen_stage001_completed_week_macd_v1'
    def add(path,name,role='decision_asset',required=True):
        artifacts.append(AiArtifact(path,name,role,required,contract))
    weekly=OUT/'stage001_weekly_features'
    evidence=OUT/'stage001_first_screen/evidence'
    evidence.mkdir(exist_ok=True)
    with (weekly/'weekly_daily.csv').open('rb') as source, (evidence/'weekly_daily.csv.gz').open('wb') as target:
        with gzip.GzipFile(filename='',mode='wb',fileobj=target,mtime=0) as compressed:
            shutil.copyfileobj(source,compressed)
    add(evidence/'weekly_daily.csv.gz','weekly/decision_states')
    for name in ['summary.json','coverage_by_year_product.csv']:
        add(weekly/name,'weekly/'+Path(name).stem,'feature_contract')
    trial=OUT/'stage001_first_screen'
    paths=json.loads((trial/'completed_arm_paths.json').read_text())
    if set(paths) not in ({'A0'},{'A0','C0'}):
        raise ValueError('invalid completed-arm map')
    complete_comparison=set(paths)=={'A0','C0'}
    if not complete_comparison and not any(trial.glob('C0*/run_failure.json')):
        raise ValueError('candidate is neither complete nor a recorded failed attempt')
    input_manifests={arm:json.loads((trial/folder/'input_manifest.json').read_text())
                     for arm,folder in paths.items()}
    # These exact inputs are declared by role; filenames do not infer importance.
    fixed_ai_inputs={
        'qmt_roll_full_market_structural_prefilter_eligible_full_market_structural_prefilter_v1.csv':
            ('structural_eligibility','decision_asset'),
        'qmt_roll_ai_product_pool_shadow_portfolio_eligibility_ai_product_pool_shadow_v1.csv':
            ('historical_monthly_eligibility','decision_asset'),
        'qmt_roll_ai_candidate_selection_pairwise_classifier_selection_pairwise_v2_risk_weighted.joblib':
            ('frozen_pairwise_model','model_artifact'),
    }
    for filename,(name,role) in fixed_ai_inputs.items():
        path=ROOT/'examples/portfolio_backtesting/backtest_outputs'/filename
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if any(m.get(str(path),{}).get('sha256')!=digest for m in input_manifests.values()):
            raise ValueError('AI evidence input changed or absent from completed arm: '+filename)
        add(path,'ai_inputs/'+name,role)
    for arm,folder in paths.items():
        source=trial/folder
        for name in ['metrics.json','summary.json','run_provenance.json','effective_parameters.json',
                     'actual_strategy_settings.json','weekly_gate_audit.csv','trades.csv','entry_candidates.csv',
                     'entry_risk.csv','input_manifest.json','execution_anchor_requests.csv','minute_scan_requests.csv']:
            add(source/name,arm+'/'+Path(name).stem)
        provenance=json.loads((source/'run_provenance.json').read_text())
        runner=source/'runner_used.py'
        if not runner.is_file() or hashlib.sha256(runner.read_bytes()).hexdigest()!=provenance['source_adapter_sha256']:
            raise ValueError('actual runner source snapshot missing or changed: '+arm)
        add(runner,arm+'/runner_used','feature_contract')
        daily=pd.read_csv(source/'daily.csv',usecols=['date','account_equity','net_pnl','slippage',
            'commission','trade_count','broker10_margin_to_equity_pct','c3_active_products'])
        daily.to_csv(evidence/f'{arm}_daily.csv',index=False)
        add(evidence/f'{arm}_daily.csv',arm+'/daily')
    experiment_names=['control_replication.json','completed_arm_paths.json','controller_receipt.json','decision.json']
    if complete_comparison:experiment_names.append('comparison.csv')
    for name in experiment_names:
        add(trial/name,'experiment/'+Path(name).stem)
    # Failed attempts are evidence, never alternative strategy results.
    for folder in sorted(trial.iterdir()):
        if folder.is_dir() and (folder/'run_failure.json').exists():
            add(folder/'run_failure.json','failed_attempts/'+folder.name,'qualification_evidence')
            add(folder/'attempt_started.json','failed_attempts/'+folder.name+'_started','qualification_evidence')
            if (folder/'runner_used.py').exists():
                add(folder/'runner_used.py','failed_attempts/'+folder.name+'_runner_used','feature_contract')
    for path in sorted((trial/'preflight').glob('*.json')):
        add(path,'preflight/'+path.stem,'qualification_evidence')
    for folder in ['stage001_design_review','stage001_signal_coverage','stage001_independent_review',
                   'stage002_independent_review']:
        for path in sorted((OUT/folder).rglob('*')):
            if path.is_file() and path.suffix in ['.json','.csv','.md']:
                relative=path.relative_to(OUT/folder)
                add(path,folder+'/'+str(relative.with_suffix(''))+'_'+path.suffix[1:],'qualification_evidence')
    # Preserve the overlay contract and audit evidence, never the raw minute prices.
    overlay=OUT/'stage002_local_minute_overlay'
    for path in sorted(overlay.rglob('*')):
        if path.is_file() and path.name!='overlay.csv' and path.suffix in ['.json','.csv','.md']:
            relative=path.relative_to(overlay)
            add(path,'stage002_overlay/'+str(relative.with_suffix(''))+'_'+path.suffix[1:],'qualification_evidence')
    for stage in ['stage001','stage002']:
        for path in sorted((LINE/'tools').glob('*'+stage+'*.py')):
            add(path,'contracts/'+path.stem,'feature_contract')
        for path in sorted((LINE/'stages').glob('*'+stage+'*.md')):
            add(path,'records/'+path.stem)
    png=trial/'comparison.png'
    if png.exists():
        figure_manifest=evidence/'figure_manifest.json'
        figure_manifest.write_text(json.dumps({'path':str(png),'sha256':hashlib.sha256(png.read_bytes()).hexdigest()},indent=2)+'\n')
        add(figure_manifest,'figures/manifest','qualification_evidence')
        add(png,'figures/comparison','cache_or_visualization',False)
    result=register_experiment_artifacts(repo_root=ROOT,line_id=LINE.name,stage='stage001',
        run_id='20261017_first_screen_increment',artifacts=artifacts)
    print(json.dumps(dict(manifest=str(result.manifest_path),saved_files=len(result.copied_logical_names),
        complete_comparison=complete_comparison,raw_market_files_copied=0,
        models_retrained=0,commit_push_calls=0),ensure_ascii=False))


if __name__=='__main__':main()
