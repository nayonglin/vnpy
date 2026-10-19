import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'research/lines/futures_trend_full_market_noai_one_lot/tools'))
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False
from stage086_run_fractional_risk import FeeStrategy
root=Path.cwd();line=root/'research/lines/futures_trend_full_market_noai_one_lot';protocol=json.loads((line/'outputs/run_20261020_contract_weekly_risk05_v2/protocol.json').read_text());p=protocol['parameters'];pairs=dict(x.split('=') for x in p['risk_cluster_map'].split(','));import pandas as pd
meta=pd.read_csv(line/'outputs/inputs/contract_metadata.csv');products=sorted(meta.product_vt_symbol.unique());instance=object.__new__(FeeStrategy);instance.risk_cluster_map=p['risk_cluster_map'];instance.source_symbol_by_contract=dict(zip(meta.vt_symbol,meta.product_vt_symbol));clusters={v:instance._risk_cluster_for_symbol(v) for v in products}
r=dict(products=len(products),unique_clusters=len(set(clusters.values())),product_cluster=clusters,enable_risk_cluster_heat_gate_effective=p.get('enable_risk_cluster_heat_gate',FeeStrategy.enable_risk_cluster_heat_gate),heat_deleverage=p.get('enable_risk_cluster_heat_deleverage',FeeStrategy.enable_risk_cluster_heat_deleverage),use_daily_snapshot=p.get('risk_cluster_heat_deleverage_use_daily_snapshot',FeeStrategy.risk_cluster_heat_deleverage_use_daily_snapshot),class_mro=[x.__name__ for x in FeeStrategy.__mro__],native_source_sha256=hashlib.sha256((root/'examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py').read_bytes()).hexdigest())
r['unmapped_products']=[p for p,c in clusters.items() if not c];r['nonempty_unique_clusters']=len(set(c for c in clusters.values() if c));r['nonempty_cluster_product_unique']=len([c for c in clusters.values() if c])==r['nonempty_unique_clusters'];assert r['products']==93 and r['nonempty_cluster_product_unique']
assert r['enable_risk_cluster_heat_gate_effective'] is False
print(json.dumps(r,indent=2));Path('/private/tmp/stage088_effective_cluster_check.json').write_text(json.dumps(r,indent=2))
