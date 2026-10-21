"""Independent pure-X identity bridge; no raw query or old DAY output reads."""
import io,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from stage096_cash_adapter import bound,compare

def review_alignment(manifest,mother,protocol):
    ids=pd.read_csv(io.BytesIO(bound(protocol['old_event_ids'])),compression='gzip',usecols=['event_id'],dtype=str,keep_default_na=False).event_id
    assert len(ids)==194709 and ids.is_unique and ids.ne('').all()and set(ids).issubset(set(mother.event_id))
    index=pd.Series(np.arange(len(ids)),index=ids)
    expected=mother.event_id.map(index).fillna(-1).to_numpy(np.int64)
    a=pd.read_csv(io.BytesIO(bound(manifest['alignment'])),compression='gzip',dtype=str,keep_default_na=False)
    assert len(a)==399252
    for c in ['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']:
        if c in ('sequence_index','u_index'):compare(pd.to_numeric(a[c]),mother[c],'alignment_current_'+c,atol=0,rtol=0)
        else:assert a[c].tolist()==mother[c].tolist()
    idx=pd.to_numeric(a.legacy_tensor_index).to_numpy(float);missing=pd.to_numeric(a.sequence_missing).to_numpy(float)
    assert np.isfinite(idx).all()and np.equal(idx,np.floor(idx)).all()and np.array_equal(idx,expected)and np.array_equal(missing,expected<0)
    assert np.array_equal(np.sort(expected[expected>=0]),np.arange(len(ids)))
    with np.load(io.BytesIO(bound(protocol['tensor'])),allow_pickle=False)as data:
        assert data.files==['ordered'];tensor=data['ordered'].copy()
    assert tensor.shape==(194709,20,4)and tensor.dtype==np.float32 and np.isfinite(tensor).all()
    fingerprint=hashlib.sha256(('\n'.join(mother.event_id)+'\n').encode()).hexdigest();assert manifest['full_mother_order_sha256']==fingerprint
    summary=json.loads((Path(manifest['alignment']['path']).parent/'summary.json').read_text())
    for k,v in dict(mother_rows=399252,legacy_tensor_rows=194709,sequence_observed=194709,sequence_missing=204543,full_mother_order_sha256=fingerprint,no_old_DAY_fields_read=True,tensor_read=False,native_source_queries=0,actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,downloads=0,whole_database_hashes=0).items():assert summary[k]==v,k
    return expected,tensor,dict(mother_rows=len(mother),legacy_rows=len(ids),sequence_observed=int((expected>=0).sum()),sequence_missing=int((expected<0).sum()),old_ID_parsed_columns=['event_id'],tensor_shape=list(tensor.shape),tensor_dtype=str(tensor.dtype),tensor_rebuilt=False,native_SQL=0,old_DAY_results_read=False,full_mother_order_sha256=fingerprint)
