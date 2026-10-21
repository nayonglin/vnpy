"""Post-result description of saved numeric trees and predictions; no fitting."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
FIT=OUT.parent/'stage053_maturity_information_fit/experiment/manifest.json'
EXPECTED='04268bb8c6f183139443b0e94d2eb51741c079d722c2987439fe37f81e085f8f'
raw=FIT.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED
manifest=json.loads(raw);trees=[]
for record in manifest['fits']:
    item=record['portable_model'];b=Path(item['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==item['sha256']
    model=json.loads(b);assert model['feature_names'][52]=='q'
    count=sum(not node['is_leaf'] and node['feature_idx']==52 for tree in model['trees'] for node in tree)
    total=sum(not node['is_leaf'] for tree in model['trees'] for node in tree)
    trees.append(dict(fit_id=record['fit_id'],scope=record['scope'],cutoff=record['cutoff'],arm=record['arm'],q_splits=int(count),all_splits=int(total),trees=len(model['trees'])))
agreements=[]
for scope in ['main','holdout_0','holdout_1']:
    item=manifest['predictions'][scope];b=Path(item['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==item['sha256']
    prediction=pd.read_csv(item['path'],usecols=['event_id','arm','cutoff','score','selected'])
    for cutoff,rows in prediction.groupby('cutoff'):
        p={arm:group.set_index('event_id').sort_index() for arm,group in rows.groupby('arm')}
        for a,barm in [('COMMON','SHUFFLED'),('ALIGNED','COMMON'),('ALIGNED','SHUFFLED')]:
            left,right=p[a],p[barm];assert left.index.equals(right.index)
            delta=left.score.to_numpy()-right.score.to_numpy()
            agreements.append(dict(scope=scope,cutoff=cutoff,comparison=a+'_vs_'+barm,rows=len(left),
                exact_score_equal=int(np.equal(left.score,right.score).sum()),
                exact_score_agreement=float(np.equal(left.score,right.score).mean()),
                score_agreement_atol_1e12=float(np.isclose(left.score,right.score,rtol=0,atol=1e-12).mean()),
                action_equal=int(np.equal(left.selected,right.selected).sum()),
                action_agreement=float(np.equal(left.selected,right.selected).mean()),
                max_abs_score_difference=float(np.abs(delta).max())))
byarm={arm:dict(q_splits=sum(r['q_splits'] for r in trees if r['arm']==arm),
    all_splits=sum(r['all_splits'] for r in trees if r['arm']==arm),fits=sum(r['arm']==arm for r in trees)) for arm in ['COMMON','ALIGNED','SHUFFLED']}
receipt=dict(schema='stage055_saved_q_slot_description_v1',purpose='Post-result explanation only, no new model or strategy selection',
    fit_manifest_sha256=EXPECTED,q_feature_index_zero_based=52,tree_splits=trees,by_arm=byarm,prediction_action_agreements=agreements,
    model_fit_calls=0,cash_replays=0,sql_queries=0,design_changed=False)
with (OUT/'q_slot_description.json').open('x') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2);stream.write('\n')
print(json.dumps(dict(by_arm=byarm,comparisons=len(agreements),common_shuffled_all_scores_exact=all(r['exact_score_agreement']==1 for r in agreements if r['comparison']=='COMMON_vs_SHUFFLED'))))
