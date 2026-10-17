"""Persist selected Stage267 reproducibility assets; no raw market redistribution."""
from pathlib import Path
import json
import sys

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
SOURCE=LINE/'outputs/stage267_clean_training_source'
SAMPLES=LINE/'outputs/stage267_monthly_samples_final'
REVIEW=LINE/'outputs/stage267_independent_review'
sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
from qmt_roll_ai_artifact_registry import AiArtifact,register_experiment_artifacts


def main():
    artifacts=[]
    selected_source=['README.md','source_summary.json','preflight.json','final_targeted_validation.json',
        'source_utility_description.json','source_opportunity_by_year.csv','source_daily.csv',
        'contract_epoch_identity.csv','pairwise_input_audit.csv','real_bar_fill_audit.csv','deferred_missing_real_bar_orders.csv']
    selected_sample=['sample_summary.json','feature_contract.json','all_sample_contract.csv',
        'qualified_samples.csv','informative_samples.csv','monthly_counts.csv','annual_sample_counts.csv']
    for directory,names,prefix in [(SOURCE,selected_source,'source'),(SAMPLES,selected_sample,'monthly')]:
        for name in names:
            artifacts.append(AiArtifact(directory/name,prefix+'/'+Path(name).stem,'decision_asset',True,'stage267_monthly108_strict120_60_v1'))
    for path in sorted(REVIEW.glob('*')):
        if path.is_file() and path.suffix in ['.json','.md','.csv']:
            artifacts.append(AiArtifact(path,'independent_source/'+path.stem+'_'+path.suffix[1:],'qualification_evidence',True,'stage267_source_v1'))
    for path in sorted((LINE/'tools').glob('*stage267*')):
        if path.is_file() and path.suffix in ['.py','.md','.json']:
            artifacts.append(AiArtifact(path,'contracts/'+path.stem+'_'+path.suffix[1:],'feature_contract',True,'stage267_source_v1'))
    for path in sorted((LINE/'stages').glob('20261017_*_stage267_*.md')):
        artifacts.append(AiArtifact(path,'records/'+path.stem,'decision_asset',True,'stage267_source_v1'))
    validation=LINE/'outputs/stage267_monthly_tool_validation/tool_validation.json'
    artifacts.append(AiArtifact(validation,'validation/monthly_tool','qualification_evidence',True,'stage267_source_v1'))
    result=register_experiment_artifacts(repo_root=ROOT,line_id=LINE.name,stage='stage267',
        run_id='20261017_clean_source_monthly_sample_census',artifacts=artifacts)
    print(json.dumps(dict(manifest=str(result.manifest_path),saved_files=len(result.copied_logical_names),
        raw_market_files_copied=0,source_big_position_csv_copied=0,commit_push_calls=0),ensure_ascii=False))


if __name__=='__main__':main()
