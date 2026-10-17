"""Register compact Stage265 download/quality evidence, never market data.

No commit, push, model, database import, production release, or orders.
"""
from pathlib import Path
import json
import sys

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
OUT = LINE / 'outputs/stage265_deep_daily'
sys.path.insert(0, str(ROOT / 'examples/portfolio_backtesting'))
from qmt_roll_ai_artifact_registry import AiArtifact, register_experiment_artifacts


def main():
    evidence = [
        'data_catalog.json', 'README.md', 'current_contract_source_census.csv', 'primary_integrity.json',
        'rqalpha/bundle_download_status.json', 'rqalpha/full_market_inventory_summary.json',
        'czce/rqalpha_independent_audit.json', 'czce/rqalpha_independent_count_reconciliation.json',
        'czce/work_fullmarket_summary.json', 'czce/work_fullmarket_raw_bind_check.json',
        'czce/other_exchanges_independent_review.json',
        'dce/official_fullmarket_manifest.json', 'dce/official_fullmarket_verification.json',
        'dce/independent_review_stage265_dce_rq.json',
        'dce/independent_review_stage265_dce_rq_verdict.json',
        'other_exchanges/official_reference_catalog.json',
        'other_exchanges/official_self_validation.json',
        'other_exchanges/latest_trade_date_census.json',
        'other_exchanges/independent_global_catalog_review.json',
        'tq_latest/current_futures_catalog.json', 'tq_latest/recent_download_status.json',
        'tq_latest/independent_review_stage265_tq_tail.json',
        'tq_latest/independent_review_stage265_tq_tail_empty_quotes.json',
        'tq_latest/independent_review_stage265_tq_tail_verdict.json',
        'tq_latest/independent_review_stage265_tq_tail_freeze.json',
    ]
    artifacts = [AiArtifact(OUT / name, 'evidence/' + str(Path(name).with_suffix('')),
        'qualification_evidence', True, 'full_market_daily_raw_layers_v1') for name in evidence]
    for source in sorted((LINE / 'tools').glob('*stage265*.py')):
        artifacts.append(AiArtifact(source, 'contracts/' + source.stem,
            'feature_contract', True, 'full_market_daily_raw_layers_v1'))
    for source in sorted((LINE / 'stages').glob('20261017_*_stage265_*.md')):
        artifacts.append(AiArtifact(source, 'records/' + source.stem,
            'decision_asset', True, 'full_market_daily_raw_layers_v1'))
    # Explicit raw/cache declarations: no entity is copied or staged for these.
    for name in ['rqalpha/rqbundle_202610.tar.bz2', 'rqalpha/futures.h5',
                 'rqalpha/instruments.pk', 'rqalpha/trading_dates.npy',
                 'dce/official_fullmarket_daily.csv']:
        artifacts.append(AiArtifact(OUT / name, 'local_raw/' + Path(name).name,
            'cache_or_visualization', False, 'vendor_native_raw_only'))
    result = register_experiment_artifacts(repo_root=ROOT, line_id=LINE.name,
        stage='stage265', run_id='20261017_full_market_daily', artifacts=artifacts)
    print(json.dumps({'manifest': str(result.manifest_path),
        'copied_files': len(result.copied_logical_names), 'staged_files': len(result.staged_paths),
        'raw_market_files_copied': 0, 'commit_push_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
