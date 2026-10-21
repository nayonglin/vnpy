"""Twelve fixed AM41 asof transformations, no future data, fit or labels."""
import math
import numpy as np
import talib

FEATURE_NAMES=('trend_energy20','trend_energy40','efficiency20','efficiency40','return_std20','return_std5_std20',
               'ma5_ma20_atr14','ma20_ma40_atr14','atr14_close','rsi6_abs_centered','volume5_volume20','oi_symmetric_change20')


def _number(value,zero=False):
    if isinstance(value,(bool,np.bool_)):raise ValueError('boolean_is_not_numeric_input')
    try:result=float(value)
    except (TypeError,ValueError):raise ValueError('invalid_numeric_input') from None
    if not math.isfinite(result) or result<0 or (result==0 and not zero):raise ValueError('invalid_numeric_sign_or_nonfinite')
    return result


def compute_features(history):
    """Consume exactly the qualified same-epoch41 prefix; identity external.

    Zero denominators map to0 only for known valid inputs. Missingness raises;
    panel construction must retain the row as unknown, never impute it as0.
    """
    if not isinstance(history,list) or len(history)!=41:raise ValueError('requires_exact_AM41')
    if talib.get_compatibility()!=0 or talib.get_unstable_period('ATR')!=0 or talib.get_unstable_period('RSI')!=0:
        raise ValueError('TA_Lib_nondefault_global_state')
    clean=[]
    for row in history:
        if not isinstance(row,dict) or any(k not in row for k in ('open','high','low','close','volume','close_oi')):raise ValueError('missing_OHLCV_OI')
        r={k:_number(row[k],zero=k in ('volume','close_oi')) for k in ('open','high','low','close','volume','close_oi')}
        if r['high']<max(r['open'],r['close']) or r['low']>min(r['open'],r['close']) or r['high']<r['low']:raise ValueError('invalid_OHLC_geometry')
        clean.append(r)
    close=np.array([r['close'] for r in clean],dtype='float64');high=np.array([r['high'] for r in clean]);low=np.array([r['low'] for r in clean])
    volume=np.array([r['volume'] for r in clean]);oi=np.array([r['close_oi'] for r in clean])
    returns=np.log(close[1:]/close[:-1]);r20=returns[-20:];r40=returns
    atr=float(talib.ATR(high,low,close,timeperiod=14)[-1]);rsi=float(talib.RSI(close,timeperiod=6)[-1])
    def ratio(n,d):return 0. if d==0 else float(n/d)
    values=[ratio(abs(r20.sum()),np.sqrt(np.square(r20).sum())),ratio(abs(r40.sum()),np.sqrt(np.square(r40).sum())),
            ratio(abs(r20.sum()),np.abs(r20).sum()),ratio(abs(r40.sum()),np.abs(r40).sum()),
            float(r20.std(ddof=0)),ratio(returns[-5:].std(ddof=0),r20.std(ddof=0)),
            ratio(abs(close[-5:].mean()-close[-20:].mean()),atr),ratio(abs(close[-20:].mean()-close[-40:].mean()),atr),
            ratio(atr,close[-1]),abs(rsi-50.)/50.,ratio(volume[-5:].mean(),volume[-20:].mean()),ratio(oi[-1]-oi[-21],oi[-1]+oi[-21])]
    if not all(math.isfinite(v) for v in values):raise ValueError('nonfinite_feature_output')
    return dict(zip(FEATURE_NAMES,values))
