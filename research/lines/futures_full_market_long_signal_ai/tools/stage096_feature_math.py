"""Independent deterministic092 feature math, without author model imports."""
import numpy as np

def canonical_bag(sequence):
    q=np.asarray(sequence,dtype=np.float64)
    assert q.ndim==3 and q.shape[1:]==(20,4)and np.isfinite(q).all()
    # Structured key order preserves all four values as one observation.
    order=np.lexsort(tuple(q[:,:,j]for j in (3,2,1,0)),axis=1)
    return np.take_along_axis(q,order[:,:,None],axis=1)

def mapping():
    rng=np.random.default_rng(20261018)
    return rng.normal(size=(91,128)),rng.uniform(0,2*np.pi,size=128)

def channel_stats(sequence,weights):
    q=np.asarray(sequence,dtype=np.float64);w=np.asarray(weights,dtype=np.float64)
    assert q.shape==(len(w),20,4)and np.isfinite(q).all()and np.isfinite(w).all()and (w>0).all()
    if not len(w):return dict(mean=[0.]*4,var=[0.]*4,scale=[1.]*4,finite_count=[0]*4)
    values=q.reshape(-1,4);wp=np.repeat(w/20,20);means=[];variances=[];scales=[]
    for j in range(4):
        v=values[:,j]
        if np.all(v==v[0]):m=float(v[0]);variance=0.
        else:
            m=float(np.sum(wp*v)/wp.sum());variance=float(np.sum(wp*(v-m)**2)/wp.sum())
        means.append(m);variances.append(variance);scales.append(np.sqrt(variance)if variance>0 else 1.)
    return dict(mean=means,var=variances,scale=scales,finite_count=[len(values)]*4)

def head(common,tensor,indices,common_stats,sequence_stats,arm,W,b):
    assert arm in ('ORDER','BAG')
    x=np.asarray(common,dtype=np.float64);idx=np.asarray(indices,dtype=int)
    assert x.shape==(len(idx),26)and (idx>=-1).all()and (idx<len(tensor)).all()
    missing=~np.isfinite(x);mean=np.asarray(common_stats['mean']);scale=np.asarray(common_stats['scale'])
    z=(np.where(missing,mean,x)-mean)/scale;seen=idx>=0
    history=np.zeros((len(idx),20,4),dtype=float)
    if seen.any():
        q=np.asarray(tensor[idx[seen]],dtype=np.float64)
        if arm=='BAG':q=canonical_bag(q)
        history[seen]=(q-np.asarray(sequence_stats['mean']))/np.asarray(sequence_stats['scale'])
    rff_input=np.column_stack([z[:,:11],history.reshape(len(idx),80)])
    phi=np.sqrt(2/128)*np.cos(rff_input@(W/np.sqrt(91))+b)
    result=np.column_stack([z,missing.astype(float),(~seen).astype(float),phi])
    assert result.shape==(len(idx),181)and np.isfinite(result).all()
    return result
