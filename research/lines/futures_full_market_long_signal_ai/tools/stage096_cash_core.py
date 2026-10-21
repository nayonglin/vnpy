"""Independent cash arithmetic only; canonical output adapter is bound after042 stabilizes.

No strategy simulation, SQL, estimation, source-data scanning or author imports.
"""
import math
import numpy as np
import pandas as pd


def replay_fill_cash(fills, initial=1_000_000.):
    """Replay saved transactions; BUY futures opens do not spend their notional."""
    required={'date','side','root','qty','fill','multiplier','fee','slippage'}
    assert required<=set(fills)
    positions={};roots={};daily={};cash=float(initial);realized=0.;fees=0.;slippage=0.
    previous=''
    for row in fills.to_dict('records'):
        day=str(row['date']);assert day>=previous;previous=day
        root=str(row['root']);qty=float(row['qty']);price=float(row['fill']);mult=float(row['multiplier'])
        fee=float(row['fee']);slip=float(row['slippage'])
        assert np.isfinite([qty,price,mult,fee,slip]).all()
        assert qty>0 and qty==math.floor(qty) and price>0 and mult>0 and fee>=0 and slip>=0
        side=str(row['side']).lower()
        if side in ('buy','open','long_open'):
            assert root not in positions and root not in roots,root
            positions[root]={'qty':qty,'entryfill':price,'multiplier':mult}
            roots[root]={'initial_qty':qty,'entryfill':price,'multiplier':mult,'realized_gross':0.,
                         'fees':fee,'slippage':slip,'entry_date':day,'exit_date':None,'closed':False}
            gross=0.
        elif side in ('sell','close','long_close'):
            assert root in positions,root
            p=positions[root];assert p['multiplier']==mult and qty<=p['qty'],root
            gross=qty*mult*(price-p['entryfill']);p['qty']-=qty
            roots[root]['realized_gross']+=gross;roots[root]['fees']+=fee;roots[root]['slippage']+=slip
            if p['qty']==0:
                roots[root]['closed']=True;roots[root]['exit_date']=day;del positions[root]
        else:
            raise AssertionError('unrecognized canonical fill side: '+side)
        realized+=gross;fees+=fee;slippage+=slip;cash=float(initial)+realized-fees
        daily[day]={'cash':cash,'cum_realized_gross':realized,'cum_fees':fees,'cum_slippage':slippage}
    for value in roots.values():value['net']=value['realized_gross']-value['fees']
    return pd.DataFrame.from_dict(daily,orient='index',columns=['cash','cum_realized_gross','cum_fees','cum_slippage']),roots,positions


def fill_days_to_daily(fill_daily,dates,initial=1_000_000.):
    """Do not alter market observations; only carry the cumulative accounting state."""
    frame=fill_daily.reindex(dates).ffill()
    if 'cash' not in frame:frame['cash']=float(initial)
    frame['cash']=frame['cash'].fillna(float(initial))
    for column in ['cum_realized_gross','cum_fees','cum_slippage']:
        if column not in frame:frame[column]=0.
        frame[column]=frame[column].fillna(0.)
    return frame


def verify_saved_quantities(fills,position_days,dates,roots):
    """Match every saved remaining quantity to cumulative transactions, not another engine."""
    fill_groups={str(day):rows for day,rows in fills.groupby('date',sort=False)}
    position_groups={str(day):rows for day,rows in position_days.groupby('date',sort=False)}
    book={};checks=0
    for day in dates:
        if day in fill_groups:
            for row in fill_groups[day].to_dict('records'):
                root=str(row['root']);side=str(row['side']).lower();qty=float(row['qty'])
                book[root]=book.get(root,0.)+(qty if side in ('buy','open','long_open') else -qty)
                assert book[root]>=0,root
                if book[root]==0:del book[root]
        actual={}
        if day in position_groups:
            rows=position_groups[day];assert not rows.root.duplicated().any()
            for row in rows.to_dict('records'):
                root=str(row['root']);actual[root]=float(row['qty'])
                assert abs(float(row['entryfill'])-roots[root]['entryfill'])<1e-9
                assert float(row['multiplier'])==roots[root]['multiplier'];checks+=1
        assert book==actual,(day,book,actual)
    return checks


def position_totals(positions,dates):
    """Compute cash-independent valuations from saved remaining positions."""
    if positions.empty:
        return pd.DataFrame(0.,index=dates,columns=['unrealized','margin','buffered_reserve','initial_risk','stale_zero_adjustment'])
    required={'date','qty','entryfill','mark','multiplier','margin_rate','risk_perlot','mark_state'}
    assert required<=set(positions)
    p=positions.copy()
    assert np.isfinite(p[['qty','entryfill','mark','multiplier','margin_rate','risk_perlot']].to_numpy(float)).all()
    assert (p.qty>0).all() and (p.multiplier>0).all()
    p['unrealized']=p.qty*p.multiplier*(p.mark-p.entryfill)
    p['margin']=p.qty*p.multiplier*p.mark*p.margin_rate
    p['buffered_reserve']=1.10*p['margin']
    p['initial_risk']=p.qty*p.risk_perlot
    p['stale_zero_adjustment']=np.where(p.mark_state.eq('stale'),-p.qty*p.multiplier*p.mark,0.)
    columns=['unrealized','margin','buffered_reserve','initial_risk','stale_zero_adjustment']
    return p.groupby('date')[columns].sum().reindex(dates).fillna(0.)


def summary_metrics(equity,roots,initial=1_000_000.,insolvent=False):
    values=np.asarray(equity,dtype=float);assert np.isfinite(values).all() and len(values)>0
    chain=np.concatenate([[float(initial)],values]);peak=np.maximum.accumulate(chain)
    drawdown=chain/peak-1.;returns=np.divide(chain[1:],chain[:-1],out=np.full(len(values),np.nan),where=chain[:-1]>0)-1.
    if insolvent or np.any(chain<=0):sharpe=None
    else:
        standard=returns.std(ddof=1) if len(returns)>1 else np.nan
        sharpe=float(returns.mean()/standard*np.sqrt(252)) if np.isfinite(standard) and standard>0 else None
    closed=[r for r in roots.values() if r['closed']]
    return {'ending_equity':float(values[-1]),'total_return':float(values[-1]/initial-1.),
            'max_drawdown':float(drawdown.min()),'sharpe':sharpe,'closed_trades':len(closed),
            'win_rate':float(np.mean([r['net']>0 for r in closed])) if closed else None,
            'open_roots':sum(not r['closed'] for r in roots.values())}
