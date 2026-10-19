"""Quantity-aware matching for one active entry per exact contract/direction.

Completed episodes are entire opening fills, never individual contracts or
partial exits. Fees and slippage are fill-total cash amounts.
"""
import json,math
import pandas as pd

COLUMNS=['vt_symbol','direction','entry_date','exit_date','entry_price','exit_price',
    'volume','original_open_volume','closed_volume','remaining_volume','gross_pnl','cost','net_pnl',
    'signal','entry_trade_id','open_trade_id','exit_trade_id','close_trade_ids']

def integer_volume(value):
    if isinstance(value,bool):raise ValueError('invalid_trade_volume')
    try:n=float(value)
    except (ValueError,TypeError,OverflowError):raise ValueError('invalid_trade_volume')
    if not math.isfinite(n) or n<=0 or n!=int(n):raise ValueError('invalid_trade_volume')
    return int(n)

def closed_ledger(trades,metadata):
    active={};closed=[];seen=set()
    for raw in trades.to_dict('records'):
        r=dict(raw);volume=integer_volume(r['volume']);identity=str(r['trade_id'])
        if identity in seen:raise RuntimeError('duplicate_trade_id:'+identity)
        seen.add(identity);r['trade_id']=identity
        for field in ['price','commission','slippage']:
            r[field]=float(r[field])
            if not math.isfinite(r[field]) or (r[field]<=0 if field=='price' else r[field]<0):raise ValueError('invalid_trade_'+field)
        if r['direction'] not in ('long','short') or r['offset'] not in ('open','close'):raise ValueError('invalid_trade_side')
        side=r['direction'] if r['offset']=='open' else ('short' if r['direction']=='long' else 'long')
        key=(r['vt_symbol'],side)
        if r['offset']=='open':
            if key in active:raise RuntimeError('multiple_entries_without_close')
            active[key]=dict(entry=r,original=volume,remaining=volume,segments=[])
            continue
        if key not in active:raise RuntimeError('unmatched_close')
        item=active[key];entry=item['entry']
        if volume>item['remaining']:raise RuntimeError('close_exceeds_actual_remaining_volume')
        entry_cost=(entry['commission']+entry['slippage'])*volume/item['original']
        exit_cost=r['commission']+r['slippage']
        sign=1 if side=='long' else -1
        gross=(r['price']-entry['price'])*sign*float(metadata[key[0]]['size'])*volume
        segment=dict(vt_symbol=key[0],direction=side,entry_trade_id=entry['trade_id'],open_trade_id=entry['trade_id'],
            exit_trade_id=identity,entry_date=entry['date'],exit_date=r['date'],entry_price=entry['price'],exit_price=r['price'],
            volume=volume,gross_pnl=gross,entry_cost=entry_cost,exit_cost=exit_cost,cost=entry_cost+exit_cost,
            net_pnl=gross-entry_cost-exit_cost,signal=entry.get('signal',''))
        item['segments'].append(segment);item['remaining']-=volume
        if item['remaining']:continue
        pieces=item['segments'];gross=sum(x['gross_pnl'] for x in pieces)
        cost=entry['commission']+entry['slippage']+sum(x['exit_cost'] for x in pieces)
        closed.append(dict(vt_symbol=key[0],direction=side,entry_date=entry['date'],exit_date=r['date'],
            entry_price=entry['price'],exit_price=sum(x['exit_price']*x['volume'] for x in pieces)/item['original'],
            volume=item['original'],original_open_volume=item['original'],closed_volume=item['original'],remaining_volume=0,
            gross_pnl=gross,cost=cost,net_pnl=gross-cost,signal=entry.get('signal',''),entry_trade_id=entry['trade_id'],
            open_trade_id=entry['trade_id'],exit_trade_id=identity,close_trade_ids=json.dumps([x['exit_trade_id'] for x in pieces])))
        del active[key]
    residual=[]
    for item in active.values():
        r=dict(item['entry']);fraction=item['remaining']/item['original']
        r.update(volume=item['remaining'],original_open_volume=item['original'],closed_volume=item['original']-item['remaining'],
            remaining_volume=item['remaining'],original_commission=r['commission'],original_slippage=r['slippage'],
            commission=r['commission']*fraction,slippage=r['slippage']*fraction,realized_segments=item['segments'])
        residual.append(r)
    return pd.DataFrame(closed,columns=COLUMNS),residual
