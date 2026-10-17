"""Descriptive source utility only: zero financial replays, zero model fits."""
import json
from pathlib import Path
import re

import pandas as pd

LINE=Path(__file__).resolve().parents[1]
SOURCE=LINE/'outputs/stage267_clean_training_source'


def main():
    candidates=pd.read_csv(SOURCE/'source_entry_candidate_snapshots.csv')
    trades=pd.read_csv(SOURCE/'source_trades.csv')
    daily=pd.read_csv(SOURCE/'source_daily.csv')
    coverage=pd.read_csv(SOURCE/'product_coverage.csv')
    positions=pd.read_csv(SOURCE/'source_position_changes.csv',usecols=['date','vt_symbol','net_pnl'])
    positions['product_vt_symbol']=positions.vt_symbol.map(lambda v:re.sub(r'\d+','',v))
    product=positions.groupby(['date','product_vt_symbol'],as_index=False).net_pnl.sum()
    for frame in [candidates,trades,daily,coverage,product]:
        frame['year']=pd.to_datetime(frame.date).dt.year
    rows=[]
    for year,cv in coverage.groupby('year'):
        pnl=product.loc[product.year.eq(year)]
        rows.append(dict(year=int(year),source_candidate_rows=int(candidates.year.eq(year).sum()),
            source_trade_rows=int(trades.year.eq(year).sum()),nonzero_product_pnl_days=int(pnl.net_pnl.ne(0).sum()),
            net_pnl=float(daily.loc[daily.year.eq(year),'net_pnl'].sum()),
            mapped_product_days=int(cv.mapped.sum()),real_main_bar_product_days=int(cv.real_main_bar.sum()),
            strict_120_raw_history_ready_product_days=int(cv.warmup_complete.sum()),
            eligible_observed_product_days=int(cv.observed.sum()),held_missing_product_days=int(cv.held_bar_missing.sum())))
    pd.DataFrame(rows).to_csv(SOURCE/'source_opportunity_by_year.csv',index=False)
    summary=dict(source_opportunity_by_year=rows,
        primary_coverage_policy='Mapped main has actual current clean bar AND every one of last120 source calendar dates has a real bar for that exact epoch; no held missing bar today.',
        coverage_vs_strategy='This is deliberately stricter than original AM120 count of last120 observed bars: absent/no-trade/quarantined dates do not disappear from qualification calendar.',
        first_2010_2014_trade_count=int(trades.year.lt(2015).sum()),
        years_2015_2018_trade_count=int(trades.year.between(2015,2018).sum()),
        nonzero_pnl_is_not_necessarily_valid_label=True,
        model_fits=0,financial_replays=0,
        limits=['Snapshot of fixed current18 products, not a survivorship-free all-market source.',
            'An original-AM120 source is not proof all pairwise140-derived statistics are mature.',
            'Strict coverage differences from Stage263 can remove prior keys; no causal comparison of model performance.',
            'Account shares capital/slots/risk memory across products; source PNL is conditional strategy output, not isolated per-product alpha.'])
    (SOURCE/'source_utility_description.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(pd.DataFrame(rows).to_string(index=False))


if __name__=='__main__':main()
