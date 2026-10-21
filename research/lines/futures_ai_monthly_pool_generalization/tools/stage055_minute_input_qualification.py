"""Qualify minute inputs under a frozen reference grid, not actual trading.

No C2 outcomes are computed or selected here. Exact source identities are
declared by the caller and must be independently checked against source data.
"""
import math
from datetime import date, datetime
import numpy as np
import pandas as pd
from stage018_finite_path_ledger import execution


def _identity(request):
    epoch=request.get('contract_epoch_id');day=request.get('source_trade_date')
    if not isinstance(epoch,str) or not epoch or not isinstance(day,str) or not day:raise ValueError('exact_identity_required')
    parts=epoch.split('.')
    if len(parts)!=3:raise ValueError('epoch_structure_invalid')
    exchange,product,month=parts
    if not exchange or not product.isalpha() or len(month)!=6 or not month.isdigit():raise ValueError('epoch_structure_invalid')
    datetime.strptime(month,'%Y%m')
    if date.fromisoformat(day).isoformat()!=day:raise ValueError('source_trade_date_requires_ISO_day')
    if exchange!=request.get('exchange') or product.upper()!=str(request.get('product','')).upper():raise ValueError('epoch_product_exchange_mismatch')
    return exchange,product,month,day


def reference_grid(request,calendar):
    """Bounded existing 2020+ reference policy; never expand its products here."""
    exchange,epoch_product,month,value=_identity(request)
    day=pd.Timestamp(value)
    if day<pd.Timestamp('2020-01-01'):raise ValueError('historical_session_policy_unsupported_before_2020')
    groups=execution.NIGHT_TO_23|execution.NIGHT_TO_01|execution.NIGHT_TO_0230|execution.DAY_ONLY
    names={name.upper():name for name in groups}
    product=str(request['product']).upper()
    if product not in names:raise ValueError('reference_session_product_unsupported')
    # This token selects a reference product schedule. It is not a broker symbol.
    token=names[product]+month[-4:]+'.'+exchange
    return execution.session_minutes(token,day,calendar)


def qualify_component(frame,expected,request,binding):
    result=dict(status='not_qualified',physical_session_verified=False,broker_symbol_qualified=False,
                reference_policy_grid_only=True,usable_for_trading=False,minute_path=None,
                real_tick_order_proven=False)
    try:_identity(request)
    except (ValueError,TypeError):return {**result,'status':'invalid_exact_identity'}
    for key in ['contract_epoch_id','source_trade_date']:
        if binding.get(key)!=request.get(key):return {**result,'status':'exact_identity_mismatch'}
        if key in frame:
            if frame[key].isna().any() or not frame[key].astype(str).eq(str(request.get(key))).all():
                return {**result,'status':'explicit_row_identity_mismatch'}
    if not binding.get('source_id') or not binding.get('identity_basis'):
        return {**result,'status':'source_identity_basis_missing'}
    required=['bar_datetime','open','high','low','close']
    if any(name not in frame for name in required):return {**result,'status':'minute_columns_missing'}
    if 'minute_source' in frame and frame.minute_source.fillna('__unspecified__').astype(str).nunique()>1:
        return {**result,'status':'mixed_source_components'}
    if 'minute_source' in frame and not frame.empty:
        component=frame.minute_source.fillna('__unspecified__').astype(str).iloc[0]
        if str(binding.get('component','__unspecified__'))!=component:return {**result,'status':'source_component_mismatch'}
    for key in ['entry_price','source_open','source_high','source_low','source_close']:
        value=request.get(key)
        try:valid=not isinstance(value,(bool,np.bool_)) and math.isfinite(float(value)) and float(value)>0
        except (ValueError,TypeError):valid=False
        if not valid:return {**result,'status':'invalid_source_prices'}
    expected=pd.DatetimeIndex(expected)
    if len(expected)==0 or expected.has_duplicates or not expected.is_monotonic_increasing or expected.isna().any():
        raise ValueError('invalid_expected_reference_grid')
    data=frame.copy()
    try:data['bar_datetime']=pd.DatetimeIndex([execution.local_timestamp(t) for t in data.bar_datetime])
    except (ValueError,TypeError):return {**result,'status':'invalid_timestamp'}
    if data.bar_datetime.isna().any():return {**result,'status':'invalid_timestamp'}
    if data.bar_datetime.duplicated().any():return {**result,'status':'duplicate_minute'}
    missing=len(set(expected)-set(data.bar_datetime));extra=len(set(data.bar_datetime)-set(expected))
    result.update(expected_minutes=len(expected),observed_minutes=len(data),missing_minutes=missing,unexpected_minutes=extra)
    if missing or extra:
        return {**result,'status':'incomplete_or_unexpected_grid' if extra else 'incomplete_grid'}
    data=data.sort_values('bar_datetime').reset_index(drop=True)
    try:
        if any(isinstance(v,(bool,np.bool_)) for v in data[['open','high','low','close']].to_numpy().flat):raise ValueError('bool')
        prices=data[['open','high','low','close']].astype(float)
    except (ValueError,TypeError):return {**result,'status':'invalid_ohlc'}
    if (not np.isfinite(prices.to_numpy()).all() or (prices<=0).any().any() or
        prices.low.gt(prices[['open','close']].min(axis=1)).any() or prices.high.lt(prices[['open','close']].max(axis=1)).any()):
        return {**result,'status':'invalid_ohlc'}
    aggregate=dict(open=float(prices.open.iloc[0]),high=float(prices.high.max()),low=float(prices.low.min()),close=float(prices.close.iloc[-1]))
    result['aggregate_ohlc']=aggregate
    if not all(math.isclose(aggregate[k],float(request['source_'+k]),rel_tol=0,abs_tol=1e-8) for k in aggregate):
        return {**result,'status':'daily_ohlc_mismatch'}
    if not math.isclose(aggregate['open'],float(request['entry_price']),rel_tol=0,abs_tol=1e-8):
        return {**result,'status':'entry_open_mismatch'}
    minute_path=[dict(bar_datetime=t.isoformat(),**{k:float(row[k]) for k in ['open','high','low','close']})
                 for t,row in zip(data.bar_datetime,prices.to_dict('records'))]
    return {**result,'status':'conditional_reference_input_qualified','minute_path':minute_path,
            'session_start':expected[0].isoformat(),'session_end_last_bar':expected[-1].isoformat()}
