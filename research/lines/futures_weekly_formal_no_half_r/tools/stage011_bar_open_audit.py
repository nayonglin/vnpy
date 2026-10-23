"""Reconcile the declared next-bar open model against real contract daily OHLCV."""
import math
import pandas as pd


def local(value):
    stamp=pd.Timestamp(value)
    if pd.isna(stamp):raise ValueError('missing_model_timestamp')
    return stamp.tz_convert('Asia/Shanghai').tz_localize(None) if stamp.tzinfo else stamp


def audit_bar_open_records(trades,anchor_requests,daily_lookup,calendar,read_counts):
    from stage005_sessions import canonical_open_timestamp
    price_bad=data_bad=clock_bad=0;details=[];cache={}
    for origin,events,time_fields in [('trade',trades,['execution_datetime']),('anchor_request',anchor_requests,['actual_time','expected_start'])]:
        for event in events:
            reasons=[];symbol=str(event.get('vt_symbol',''));day=str(event.get('trading_date',''))[:10]
            detail=dict(origin=origin,trade_id=str(event.get('trade_id','')),vt_symbol=symbol,trading_date=day)
            try:
                key=(symbol,day)
                if key not in cache:cache[key]=list(daily_lookup(symbol,day))
                rows=cache[key]
                if len(rows)!=1:
                    data_bad+=1;reasons.append('missing_or_duplicate_daily_row')
                else:
                    row={name:float(rows[0][name]) for name in ['open','high','low','close','volume']}
                    detail['daily_ohlcv']=row
                    good=all(math.isfinite(v) and v>0 for v in row.values())
                    good=good and row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high']
                    if not good:data_bad+=1;reasons.append('invalid_daily_ohlcv')
                    price=float(event['price']);detail['modeled_price']=price
                    if not math.isfinite(price) or abs(price-row['open'])>1e-8:
                        price_bad+=1;reasons.append('daily_open_price_mismatch')
                expected=local(canonical_open_timestamp(symbol,day,calendar));detail['modeled_session_open_clock']=str(expected)
                for field in time_fields:
                    if local(event[field])!=expected:
                        clock_bad+=1;reasons.append('modeled_clock_mismatch:'+field)
            except (ValueError,TypeError,KeyError,OverflowError) as error:
                data_bad+=1;reasons.append('invalid_daily_record:'+type(error).__name__)
            detail['reasons']=reasons;details.append(detail)
    reads={name:int(read_counts.get(name,0)) for name in ['minute_reads','proxy_reads']}
    accepted=not(price_bad or data_bad or clock_bad or any(reads.values()))
    return dict(schema='stage011_daily_bar_open_acceptance_v1',accepted=accepted,
        verdict='PASS_DECLARED_BAR_OPEN_MODEL' if accepted else 'REJECT_BAR_OPEN_MODEL',
        **reads,daily_price_mismatch_count=price_bad,daily_data_invalid_count=data_bad,modeled_clock_mismatch_count=clock_bad,
        trade_count=len(trades),anchor_request_count=len(anchor_requests),details=details,
        execution_model='declared_daily_bar_open_next_bar_v1',minute_quote_confirmed=False,
        note='Contract daily opens are the primary execution model. Calendar timestamps are modeled; spread, depth, queues and within-bar execution are not verified.')
