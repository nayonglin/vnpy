import math
def daily_coverage_gaps(rows,database):
    cache={};gaps=[]
    for row in rows:
        if not any(float(row[k]) for k in ['start_pos','end_pos','trade_count']):continue
        symbol,exchange=row['vt_symbol'].split('.')
        key=(symbol,exchange)
        if key not in cache:
            cache[key]={str(dt)[:10]:float(close) for dt,close in database.execute(
                "select datetime,close_price from dbbardata where symbol=? and exchange=? and interval='d'",key)}
        day=str(row['date'])[:10];actual=cache[key].get(day)
        reason=None
        if actual is None:reason='missing_held_or_traded_daily_bar'
        elif not math.isfinite(actual) or actual<=0:reason='invalid_real_daily_close'
        elif abs(actual-float(row['close_price']))>1e-8:reason='mark_differs_from_real_close'
        if reason:gaps.append({**row,'real_close':actual,'reason':reason})
    return gaps

