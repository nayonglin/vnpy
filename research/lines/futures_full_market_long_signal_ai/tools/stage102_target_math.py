"""Independent fixed budget-target math. No author imports, fitting or inputs."""
import numpy as np
F=.0025

def targets(y,c,evaluated):
    y=np.asarray(y,float);c=np.asarray(c,float);evaluated=np.asarray(evaluated,bool)
    assert y.shape==c.shape==evaluated.shape and y.ndim==1
    a=np.full(len(y),np.nan);z=a.copy();wealth=a.copy();g=a.copy()
    state=np.full(len(y),'not_evaluated',dtype=object)
    rows=np.flatnonzero(evaluated)
    for i in rows:
        if not np.isfinite(c[i]) or c[i]<0:state[i]='invalid_cost';continue
        with np.errstate(over='ignore',invalid='ignore',divide='ignore'):
            a[i]=1./(1.+8.*c[i])
        if not np.isfinite(a[i]) or a[i]<=0 or a[i]>1:state[i]='invalid_a';continue
        if not np.isfinite(y[i]):state[i]='invalid_raw_target';continue
        with np.errstate(over='ignore',invalid='ignore'):z[i]=a[i]*y[i]
        if not np.isfinite(z[i]):state[i]='invalid_z';continue
        with np.errstate(over='ignore',invalid='ignore'):wealth[i]=1.+F*z[i]
        if not np.isfinite(wealth[i]) or wealth[i]<=0:state[i]='nonpositive_wealth_factor';continue
        with np.errstate(over='ignore',invalid='ignore',divide='ignore'):g[i]=np.log1p(F*z[i])/F
        if not np.isfinite(g[i]):state[i]='invalid_log_target';continue
        state[i]='valid'
    return dict(evaluated=evaluated,a=a,z=z,L=z.copy(),G=g,wealth=wealth,state=state,valid=(state=='valid'))

def head52(raw,scaler):
    raw=np.asarray(raw,float);m=np.asarray(scaler['mean'],float);s=np.asarray(scaler['scale'],float)
    assert raw.ndim==2 and raw.shape[1]==26 and m.shape==s.shape==(26,) and np.isfinite(m).all() and np.isfinite(s).all() and (s>0).all()
    finite=np.isfinite(raw)
    return np.column_stack([np.where(finite,(raw-m)/s,0.),(~finite).astype(float)])
