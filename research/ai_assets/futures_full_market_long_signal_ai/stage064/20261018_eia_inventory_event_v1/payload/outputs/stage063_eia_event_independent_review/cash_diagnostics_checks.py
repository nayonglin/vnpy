"""Independent saved-fill diagnostics adapted from independent055 only."""
import gzip,json
import numpy as np
import pandas as pd
from cash_adapter import compare,bound

def independent_cash_diagnostics(directory,summary,all_families):
    daily=pd.read_csv(directory/'daily.csv.gz');fills=pd.read_csv(directory/'fills.csv.gz')
    positions=pd.read_csv(directory/'position_days.csv.gz');diag=summary['diagnostics']
    initial=float(summary['initial_capital']);eq=daily.equity.to_numpy(float);prior=initial;years=[]
    for year,rows in daily.groupby(daily.date.str[:4],sort=True):
        x=np.r_[prior,rows.equity.to_numpy(float)];r=next(t for t in diag['annual_slices'] if t['year']==year)
        for field,value in [('starting_equity',prior),('ending_equity',x[-1]),('cash_growth',x[-1]-prior),
            ('max_drawdown_pct',(x/np.maximum.accumulate(x)-1).min()*100)]:compare(r[field],value,'annual_'+field)
        if prior>0:compare(r['return_pct'],(x[-1]/prior-1)*100,'annual_return_pct')
        else:assert r['return_pct'] is None
        assert r['source_days']==len(rows) and r['partial']==(year=='2026')
        assert r['continuous_account_slice'] is True and r['independent_cold_start'] is False
        prior=float(x[-1]);years.append(year)
    assert len(years)==len(diag['annual_slices'])
    # Reconstruct attribution directly from fills and marked surviving holdings.
    family_set=set(fills.family_id) if 'family_id' in fills else set()
    if 'family_id' in positions:family_set|=set(positions.family_id)
    records=[]
    for family in sorted(family_set):
        f=fills.loc[fills.family_id.eq(family)]
        fg=f.groupby('date')[['realized_gross','fee']].sum().reindex(daily.date,fill_value=0.)
        z=positions.loc[positions.family_id.eq(family)] if 'family_id' in positions else pd.DataFrame()
        unreal=z.groupby('date').unrealized.sum().reindex(daily.date,fill_value=0.) if len(z) else pd.Series(0.,index=daily.date)
        contribution=fg.realized_gross.to_numpy()-fg.fee.to_numpy()+np.diff(np.r_[0.,unreal.to_numpy()])
        yearly=pd.DataFrame(dict(year=daily.date.str[:4],value=contribution,fee=fg.fee.to_numpy())).groupby('year').sum()
        for year,row in yearly.iterrows():records.append(dict(family_id=family,year=year,net_equity_contribution=row.value,fee=row.fee))
    expected=pd.DataFrame(records,columns=['family_id','year','net_equity_contribution','fee']).sort_values(['family_id','year'])
    grid=pd.MultiIndex.from_product([sorted(all_families),sorted(years)],names=['family_id','year'])
    expected=expected.set_index(['family_id','year']).reindex(grid,fill_value=0.).reset_index()
    actual=pd.read_csv(directory/'family_year_contributions.csv.gz',dtype={'year':str}).sort_values(['family_id','year'])
    assert actual[['family_id','year']].to_records(index=False).tolist()==expected[['family_id','year']].to_records(index=False).tolist()
    for col in ['net_equity_contribution','fee']:compare(actual[col],expected[col],'family_year_'+col)
    compare(expected.net_equity_contribution.sum(),eq[-1]-initial,'family_year_total_equity_change')
    for record in diag['family_year_concentration']:
        rows=expected.loc[expected.year.eq(record['year'])];wins=rows.loc[rows.net_equity_contribution.gt(0)].sort_values('net_equity_contribution',ascending=False)
        losses=rows.loc[rows.net_equity_contribution.lt(0)].sort_values('net_equity_contribution')
        wp=wins.net_equity_contribution.sum();lp=-losses.net_equity_contribution.sum()
        compare(record['gross_positive_contributions'],wp,'concentration_positive');compare(record['gross_negative_contributions'],lp,'concentration_negative')
        if wp:
            assert record['largest_winning_family']==wins.iloc[0].family_id
            compare(record['largest_winner_share'],wins.iloc[0].net_equity_contribution/wp,'concentration_largest')
            compare(record['top5_winner_share'],wins.head(5).net_equity_contribution.sum()/wp,'concentration_top5')
        if lp:
            assert record['largest_losing_family']==losses.iloc[0].family_id
            compare(record['largest_loser_share'],-losses.iloc[0].net_equity_contribution/lp,'concentration_loser')
    assert diag['stale_days']==int(daily.stale_positions.gt(0).sum())
    for field,col,method in [('max_stale_notional','stale_notional','max'),('minimum_stale_zero_equity','stale_zero_equity','min'),('minimum_all_open_zero_equity','unresolved_zero_equity','min')]:
        compare(diag[field],getattr(daily[col],method)(),'cash_diagnostics_'+field)
    log=np.diff(np.log(np.r_[initial,eq])) if np.all(eq>0) and not summary['ever_insolvent'] else None
    if log is not None:compare(diag['cumulative_log_growth'],log.sum(),'cash_log_growth')
    saved=pd.read_csv(directory/'daily_log_growth.csv.gz')
    if log is not None:compare(saved.daily_log_growth,log,'daily_log_growth')
    else:assert saved.daily_log_growth.isna().all()
    return daily

def review_native(cash,signals,calendar,experiment):
    audit=json.loads(gzip.decompress(bound(cash['excluded_raw_audit'])));assert audit['sql_queries']==0 and audit['raw_ohlc'] is True
    checked=[];all_signals=signals['COMMON_EVENT']
    for case in audit['cases']:
        s=all_signals.loc[case['event_id']];assert case['epoch']==s.reference_epoch
        history=[r for r in case['bars'] if r['date']<=case['u_date']]
        assert len(history)==int(s.history_run) and all(not r.get('native_missing') and r['valid_positive_volume'] for r in history)
        N=None;trs=[];previous=None
        for r in history:
            tr=r['high']-r['low'] if previous is None else max(r['high']-r['low'],abs(r['high']-previous),abs(r['low']-previous))
            trs.append(tr)
            if len(trs)==20:N=sum(trs)/20
            elif len(trs)>20:N=(19*N+tr)/20
            previous=r['close']
        assert len(history)>=20
        compare([N,min(r['low'] for r in history[-20:]),history[-1]['close']],[s.N_u,s.low20_u,s.u_close],'finite_native_N_low20_close',atol=1e-9,rtol=1e-11)
        local={r['date']:r for r in case['bars'] if not r.get('native_missing') and r.get('valid_positive_volume')}
        entry=s.planned_execution_date
        native_fills=0
        for directory in sorted((experiment/'cash').iterdir()):
            fills=pd.read_csv(directory/'fills.csv.gz')
            rows=fills.loc[fills.event_id.eq(case['event_id'])]
            for fill in rows.itertuples(index=False):
                if fill.date not in local:continue
                bar=local[fill.date]
                if fill.side=='BUY':
                    assert fill.date==entry
                    compare(fill.reference_price,bar['open'],'native_entry_open',atol=1e-9,rtol=1e-12);native_fills+=1
                elif fill.reason in ['gap_stop','research_deferred_liquidation','risk_margin_joint_reduction','liquidity_reference_changed','lifecycle_exit','observation_exit_requested']:
                    compare(fill.reference_price,bar['open'],'native_exit_open',atol=1e-9,rtol=1e-12);native_fills+=1
                elif fill.reason=='stop_boundary':
                    assert bar['open']>fill.reference_price and bar['low']<=fill.reference_price
                    native_fills+=1
        checked.append(dict(kind=case['kind'],event_id=case['event_id'],continuous_warmup_rows=len(history),total_local_bars=len(case['bars']),local_fill_prices_checked=native_fills))
    return dict(cases=checked,raw_copied=False,full_native_strategy_replay=False)
