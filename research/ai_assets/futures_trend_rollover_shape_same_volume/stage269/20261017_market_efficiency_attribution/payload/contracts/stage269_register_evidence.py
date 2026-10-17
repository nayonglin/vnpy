"""Register derived evidence; raw OHLC, DBs and visual caches stay local."""
from pathlib import Path
import json
import sys
import pandas as pd

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage269_market_efficiency_validation'
sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
from qmt_roll_ai_artifact_registry import AiArtifact,register_experiment_artifacts


def main():
    evidence=OUT/'evidence'
    evidence.mkdir(exist_ok=True)
    f=pd.read_csv(OUT/'analysis/joined_daily.csv')
    cols=['date','net_pnl','slippage','account_equity','c3_active_products','broker10_margin_to_equity_pct',
        'source_present','daily_return','label_end','label_status','label_mature','future20_return',
        'future20_cash','future20_profit','past60_return','past60_vol','normalized_future20_return',
        'future20_slippage','future20_cash_extra_slippage','future20_return_extra_slippage',
        'market_er60','raw_market_er60','gate_pass','coverage_ratio','active_products','valid_products',
        'commodity_er60','sector_equal_er60','outside_pool_er60','own_pool_er60','market_er20','market_er120',
        'market_vol60','direction_breadth60','market_corr60','er60_expanding_pct','regime','gate_reasons']
    f[cols].to_csv(evidence/'decision_daily.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.read_csv(OUT/'market/market_daily.csv').to_csv(evidence/'market_daily.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    artifacts=[]
    for folder,role in [('analysis','decision_asset'),('evidence','decision_asset'),('review','qualification_evidence')]:
        for path in sorted((OUT/folder).iterdir()):
            if path.is_file() and path.name!='joined_daily.csv':
                artifacts.append(AiArtifact(path,folder+'/'+path.stem,role,True,'stage268_frozen_ER60_future20_v1'))
    for name in ['market_summary.json','product_sectors.json','coverage_precheck.json','coverage_by_product.csv',
                 'coverage_by_year_product.csv','coverage_by_year_sector.csv']:
        path=OUT/'market'/name
        artifacts.append(AiArtifact(path,'market/'+path.stem,'feature_contract',True,'stage268_frozen_ER60_future20_v1'))
    for path in sorted((LINE/'tools').glob('*stage269*.py')):
        artifacts.append(AiArtifact(path,'contracts/'+path.stem,'feature_contract',True,'stage268_frozen_ER60_future20_v1'))
    for path in sorted((LINE/'stages').glob('20261017_*_stage269_*.md')):
        artifacts.append(AiArtifact(path,'records/'+path.stem,'decision_asset',True,'stage268_frozen_ER60_future20_v1'))
    for name in ['figure_manifest.json','visual_check.json']:
        artifacts.append(AiArtifact(OUT/'figures'/name,'figures/'+Path(name).stem,'qualification_evidence',True,'stage269_figures_v1'))
    for path in sorted((OUT/'figures').glob('*.png')):
        artifacts.append(AiArtifact(path,'figures/'+path.stem,'cache_or_visualization',False,'stage269_figures_v1'))
    result=register_experiment_artifacts(repo_root=ROOT,line_id=LINE.name,stage='stage269',
        run_id='20261017_market_efficiency_attribution',artifacts=artifacts)
    print(json.dumps(dict(manifest=str(result.manifest_path),saved_files=len(result.copied_logical_names),
        financial_replays=0,raw_market_files_copied=0,commit_push_calls=0),ensure_ascii=False))


if __name__=='__main__':
    main()
