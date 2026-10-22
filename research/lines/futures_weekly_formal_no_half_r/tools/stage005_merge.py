"""批量合并已验收的真实分钟层：与逐层首值优先/绝对1e-8冲突规则等价。"""
import numpy as np
import pandas as pd
KEYS=['vt_symbol','bar_datetime']
def merge_verified_layers(base,patches,values):
 if base.duplicated(KEYS).any():raise ValueError('base_duplicate_minute')
 pieces=[base]
 for patch in patches:
  if patch.duplicated(KEYS).any():raise ValueError('patch_duplicate_minute')
  pieces.append(patch)
 joined=pd.concat(pieces,ignore_index=True)
 first=joined.drop_duplicates(KEYS,keep='first')
 repeated=joined.loc[joined.duplicated(KEYS,keep=False),KEYS+list(values)]
 if len(repeated):
  reference=first[KEYS+list(values)].rename(columns={v:v+'_reference' for v in values})
  pair=repeated.merge(reference,on=KEYS,how='left',validate='many_to_one')
  if not np.isclose(pair[list(values)].to_numpy(float),pair[[v+'_reference' for v in values]].to_numpy(float),rtol=0,atol=1e-8,equal_nan=False).all():raise ValueError('completed_minute_source_overlap_conflict')
 return first.sort_values(KEYS).reset_index(drop=True)
