"""Save compact Stage266 decision evidence; raw markets/DBs remain local."""
import json
from pathlib import Path
import sys

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage266_clean_daily'
REVIEW=LINE/'outputs/stage266_independent_validation'
sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
from qmt_roll_ai_artifact_registry import AiArtifact,register_experiment_artifacts


def main():
    full=json.loads((OUT/'stage266_units_evidence.json').read_text())
    compact={k:full[k] for k in ['generated_at','scope','script_sha256','metadata_safety',
        'rq_h5_sha256','rq_metadata_sha256','h5_parity_by_exchange_year','official_overlap',
        'old_tq_overlap','main_database_written','new_downloads','new_tq_subscriptions','backtests','training_runs']}
    compact.update(old_tq_file_count=len(full['old_tq_files']),official_source_count=len(full['official_source_bindings']),
        complete_evidence_dependency='See unit_contract.evidence_bindings for local full evidence SHA; no source prices copied')
    (OUT/'unit_calibration_compact.json').write_text(json.dumps(compact,ensure_ascii=False,indent=2)+'\n')
    delta=json.loads((REVIEW/'final_monotonic_delta_review.json').read_text())
    delta={k:v for k,v in delta.items() if k!='deleted_row_evidence'}
    (OUT/'final_delta_compact.json').write_text(json.dumps(delta,ensure_ascii=False,indent=2)+'\n')
    # Compact full-store metadata, not OHLC/quantity time series.
    selected=[
        ('README.md','decision_asset'),('dataset_manifest.json','decision_asset'),
        ('contract.json','feature_contract'),('unit_contract.json','feature_contract'),
        ('unit_calibration_compact.json','qualification_evidence'),
        ('final_delta_compact.json','qualification_evidence'),
        ('stage266_units_verification.json','qualification_evidence'),
        ('stage266_units_report.md','qualification_evidence'),
        ('stage266_units_quarantine.csv','feature_contract'),('price_conflict_quarantine.csv','feature_contract'),
        ('protected_integrity.json','qualification_evidence'),
        ('feature_dependency_clarification.json','feature_contract'),
        ('reader_semantics_erratum.json','feature_contract'),('reader_semantics_erratum.md','feature_contract'),
        ('czce_reader_mapping_availability_304_final.json','qualification_evidence'),
        ('czce_reader_year_product_month_summary_final.json','qualification_evidence'),
    ]
    artifacts=[AiArtifact(OUT/p,'evidence/'+str(Path(p).with_suffix('')),role,True,'stage266_clean_daily_v1') for p,role in selected]
    for name in ['independent_review_summary.json','csv_export_validation.json',
        'excluded_conservation_validation.json','september_TQ_RQ_overlap.json','independent_reader_review.json',
        'coverage_by_exchange_year.csv','coverage_by_exchange_year_product.csv']:
        artifacts.append(AiArtifact(REVIEW/name,'review/'+str(Path(name).with_suffix('')),
            'qualification_evidence',True,'stage266_clean_daily_v1'))
    for p in sorted((LINE/'tools').glob('*stage266*.py')):
        artifacts.append(AiArtifact(p,'contracts/'+p.stem,'feature_contract',True,'stage266_clean_daily_v1'))
    for p in sorted((LINE/'stages').glob('20261017_*_stage266_*.md')):
        artifacts.append(AiArtifact(p,'records/'+p.stem,'decision_asset',True,'stage266_clean_daily_v1'))
    for p in [OUT/'clean_daily.sqlite',OUT/'excluded_observations.csv.gz',OUT/'source_disagreements.csv.gz',
        OUT/'stage266_units_evidence.json',OUT/'stage266_units_exceptions.json',OUT/'csv_inventory.json',
        REVIEW/'final_monotonic_delta_review.json']:
        artifacts.append(AiArtifact(p,'local_dependencies/'+p.name,'cache_or_visualization',False,'source_preserved_local'))
    result=register_experiment_artifacts(repo_root=ROOT,line_id=LINE.name,stage='stage266',
        run_id='20261017_clean_daily_accuracy',artifacts=artifacts)
    print(json.dumps(dict(manifest=str(result.manifest_path),saved_files=len(result.copied_logical_names),
        raw_market_files_copied=0,model_fits=0,commit_push_calls=0),ensure_ascii=False))


if __name__=='__main__':main()
