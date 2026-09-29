"""Read-only, offline full-universe factor diagnostics; never repairs inputs.

Run with repository .py311/bin/python -I. Outputs are confined to this unique
stage prefix. Tests below concern diagnostic algebra, not provider truth.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


REPO = Path('/Users/bytedance/Desktop/person/vnpy')
SOURCE = REPO / 'examples/stock_backtesting/qmt357/data/downloads/history_20191001_20260928'
PREFIX = Path(__file__).with_suffix('')
EXPECTED_SHA = 'fa1422b5e64016b61e3804bf3ccdffc2c4feb957f2ef94d892964ef75634377f'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quantum(value):
    """One displayed decimal unit, not a claim about vendor rounding policy."""
    return float(Decimal(1).scaleb(Decimal(str(value)).as_tuple().exponent))


def ratio_interval(current, previous, current_q, previous_q):
    # Conservative one-ULP uncertainty for each displayed factor value.
    if previous <= previous_q or current <= current_q:
        return float('nan'), float('nan')
    return ((current-current_q)/(previous+previous_q),
            (current+current_q)/(previous-previous_q))


def overlap(a, b):
    return max(a[0], b[0]) <= min(a[1], b[1])


def factor_price_compatible(previous_close, raw_reference, step_bounds):
    if any(not np.isfinite(x) or x <= 0 for x in step_bounds):
        return None
    implied_reference = (previous_close/step_bounds[1], previous_close/step_bounds[0])
    return overlap(implied_reference, (raw_reference-.005000001, raw_reference+.005000001))


def self_check():
    assert overlap(ratio_interval(2., 1., 1e-6, 1e-6), ratio_interval(.4, .2, 1e-6, 1e-6))
    assert not overlap(ratio_interval(99.787353,119.960317,1e-6,1e-6), ratio_interval(.781647,.781647,1e-6,1e-6))
    assert factor_price_compatible(10., 9., (10/9,10/9))
    assert factor_price_compatible(10., 9.99, (10/9.994,10/9.994))
    assert not factor_price_compatible(10., 9.98, (10/9.994,10/9.994))
    assert quantum('0.781647') == 1e-6
    assert quantum('1.000000') == 1e-6


def serialize_frame(frame):
    return json.loads(frame.to_json(orient='records', date_format='iso'))


def main():
    self_check()
    assert sha(SOURCE/'source_panel.parquet') == EXPECTED_SHA
    output_json = PREFIX.with_suffix('.json')
    if output_json.exists():
        raise FileExistsError('Do not overwrite a completed audit')
    panel = pd.read_parquet(SOURCE/'source_panel.parquet')
    known_rows = json.loads((SOURCE/'final_factor_audit.json').read_text())['rows']
    known = {(r['vt_symbol'],r['date']):r for r in known_rows}
    stocks = {vt:part.sort_values('date') for vt,part in panel.groupby('vt_symbol') if vt != '000300.SSE'}
    assert len(stocks) == 420
    pair_rows, daily_rows, inventories = [], [], []
    for number,(vt,stock) in enumerate(sorted(stocks.items()),1):
        code = ('sh.' if vt.endswith('.SSE') else 'sz.')+vt[:6]
        factor_path = SOURCE/'raw'/f'factors_{code}_2026-09-28.parquet'
        factor = pd.read_parquet(factor_path).sort_values('dividOperateDate').reset_index(drop=True)
        assert factor.empty or factor.code.eq(code).all()
        assert not factor.dividOperateDate.duplicated().any()
        factor['date'] = pd.to_datetime(factor.dividOperateDate)
        for key,col in [('b','backAdjustFactor'),('f','foreAdjustFactor'),('a','adjustFactor')]:
            factor[key] = pd.to_numeric(factor[col],errors='raise')
            factor[key+'_q'] = factor[col].map(quantum)
            assert np.isfinite(factor[key]).all() and factor[key].gt(0).all()
        inventories.append(dict(vt_symbol=vt,rows=len(factor),first_date=str(factor.date.min().date()),
            last_date=str(factor.date.max().date()),sha256=sha(factor_path),
            back_adjust_exact_equal_rows=int(factor.b.eq(factor.a).sum()),
            fore_last=float(factor.f.iloc[-1]),back_first=float(factor.b.iloc[0])))
        for i in range(1,len(factor)):
            curr,prev = factor.iloc[i],factor.iloc[i-1]
            bi = ratio_interval(curr.b,prev.b,curr.b_q,prev.b_q)
            fi = ratio_interval(curr.f,prev.f,curr.f_q,prev.f_q)
            compatible = overlap(bi,fi)
            pair_rows.append(dict(vt_symbol=vt,event_date=curr.date,previous_event_date=prev.date,
                back_previous=prev.b,back_current=curr.b,fore_previous=prev.f,fore_current=curr.f,
                adjust_previous=prev.a,adjust_current=curr.a,
                back_ratio=curr.b/prev.b,fore_ratio=curr.f/prev.f,adjust_ratio=curr.a/prev.a,
                back_fore_scale_previous=prev.b/prev.f,back_fore_scale_current=curr.b/curr.f,
                ratio_interval_compatible=compatible,back_changed=curr.b!=prev.b,fore_changed=curr.f!=prev.f,
                in_panel_date_range=stock.date.min() <= curr.date <= stock.date.max()))
        raw = pd.concat([pd.read_parquet(p) for p in sorted((SOURCE/'raw').glob(f'bars_{code}_*.parquet'))],ignore_index=True)
        raw['date'] = pd.to_datetime(raw.date)
        raw = raw.sort_values('date').reset_index(drop=True)
        assert raw.code.eq(code).all() and not raw.date.duplicated().any()
        daily = stock.merge(raw[['date','preclose','tradestatus']],on='date',validate='one_to_one')
        assert len(daily) == len(stock)
        daily['preclose'] = pd.to_numeric(daily.preclose)
        daily = pd.merge_asof(daily.sort_values('date'),factor[['date','b','f','a','b_q','f_q','a_q']],on='date',direction='backward')
        daily[['b','f','a']] = daily[['b','f','a']].fillna(1.)
        daily[['b_q','f_q','a_q']] = daily[['b_q','f_q','a_q']].fillna(0.)
        assert daily.b.eq(daily.adj_factor).all(), vt
        for col in ['close','b','f','a','b_q','f_q','a_q']:
            daily['previous_'+col] = daily[col].shift()
        daily['back_changed'] = daily.b.ne(daily.previous_b)
        daily['fore_changed'] = daily.f.ne(daily.previous_f)
        daily['reference_changed'] = ~np.isclose(daily.preclose,daily.previous_close,atol=1e-8,rtol=0)
        daily['explicit_action'] = daily.cash_dividend.ne(0)|daily.split_ratio.ne(1)
        candidates = daily.loc[daily.previous_close.notna() & (daily.back_changed|daily.fore_changed|daily.reference_changed|daily.explicit_action)]
        for r in candidates.itertuples(index=False):
            bi = ratio_interval(r.b,r.previous_b,r.b_q,r.previous_b_q)
            fi = ratio_interval(r.f,r.previous_f,r.f_q,r.previous_f_q)
            simple_ref = (r.previous_close-r.cash_dividend)/r.split_ratio
            cash_ref_compatible = abs(simple_ref-r.preclose) <= .005000001
            b_ref = factor_price_compatible(r.previous_close,r.preclose,bi)
            f_ref = factor_price_compatible(r.previous_close,r.preclose,fi)
            identity_compatible = overlap(bi,fi)
            old = known.get((vt,r.date.strftime('%Y-%m-%d')), {})
            if old:
                classification = old['diagnostic_classification']
            elif not identity_compatible:
                classification = 'additional_back_fore_step_incompatibility'
            elif not r.explicit_action and (r.back_changed or r.fore_changed or r.reference_changed):
                classification = 'additional_unmodeled_reference_or_factor_event'
            elif not cash_ref_compatible:
                classification = 'explicit_cash_split_reference_incompatible'
            elif b_ref is False or f_ref is False:
                classification = 'explicit_action_factor_reference_incompatible'
            else:
                classification = 'cash_split_reference_and_factor_compatible'
            daily_rows.append(dict(vt_symbol=vt,date=r.date,is_member=bool(r.is_member),
                previous_close=r.previous_close,preclose=r.preclose,close=r.close,tradestatus=r.tradestatus,
                cash_dividend=r.cash_dividend,split_ratio=r.split_ratio,explicit_action=bool(r.explicit_action),
                back_previous=r.previous_b,back_current=r.b,fore_previous=r.previous_f,fore_current=r.f,
                adjust_previous=r.previous_a,adjust_current=r.a,
                back_ratio=r.b/r.previous_b,fore_ratio=r.f/r.previous_f,adjust_ratio=r.a/r.previous_a,
                raw_reference_ratio=r.previous_close/r.preclose,
                back_implied_reference=r.previous_close/(r.b/r.previous_b),
                fore_implied_reference=r.previous_close/(r.f/r.previous_f),
                cash_split_implied_reference=simple_ref,cash_split_reference_residual=simple_ref-r.preclose,
                back_changed=bool(r.back_changed),fore_changed=bool(r.fore_changed),reference_changed=bool(r.reference_changed),
                ratio_interval_compatible=identity_compatible,back_reference_compatible=b_ref,fore_reference_compatible=f_ref,
                cash_split_reference_compatible=cash_ref_compatible,prior_24_gap=bool(old),
                classification=classification,announcement_url=old.get('announcement_url','')))
        if number%50==0:
            print(f'audited {number}/420',flush=True)
    pairs = pd.DataFrame(pair_rows)
    daily = pd.DataFrame(daily_rows)
    anomalies = daily.loc[daily.classification.ne('cash_split_reference_and_factor_compatible')]
    output_map = {'factor_pairs':pairs,'event_checks':daily,'anomalies':anomalies,'factor_inventory':pd.DataFrame(inventories)}
    for key,frame in output_map.items():
        frame.to_parquet(Path(str(PREFIX)+'_'+key+'.parquet'),index=False)
    in_range = pairs.loc[pairs.in_panel_date_range]
    known24 = daily.loc[daily.prior_24_gap]
    assert len(known24)==24
    summary = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),source_sha256=EXPECTED_SHA,
        script_sha256=sha(Path(__file__)),stock_count=len(stocks),raw_factor_rows=sum(r['rows'] for r in inventories),
        adjacent_factor_pairs=len(pairs),adjacent_pair_incompatibilities=int((~pairs.ratio_interval_compatible).sum()),
        in_panel_range_factor_pairs=len(in_range),in_panel_range_pair_incompatibilities=int((~in_range.ratio_interval_compatible).sum()),
        back_adjust_value_mismatches=sum(r['rows']-r['back_adjust_exact_equal_rows'] for r in inventories),
        event_candidates=len(daily),explicit_actions=int(daily.explicit_action.sum()),
        candidate_classifications=daily.classification.value_counts().to_dict(),
        known_24_classifications=known24.classification.value_counts().to_dict(),
        daily_ratio_incompatibilities=int((~daily.ratio_interval_compatible).sum()),
        explicit_cash_split_reference_incompatibilities=int((daily.explicit_action & ~daily.cash_split_reference_compatible).sum()),
        explicit_back_reference_incompatibilities=int((daily.explicit_action & daily.back_reference_compatible.eq(False)).sum()),
        explicit_fore_reference_incompatibilities=int((daily.explicit_action & daily.fore_reference_compatible.eq(False)).sum()),
        known24=serialize_frame(known24),additional_anomalies=serialize_frame(anomalies.loc[~anomalies.prior_24_gap]),
        raw_pair_incompatibilities_in_panel_range=serialize_frame(in_range.loc[~in_range.ratio_interval_compatible]),
        outputs={key:str(Path(str(PREFIX)+'_'+key+'.parquet')) for key in output_map},
        tests=dict(algebra_self_checks='pass',panel_back_factor_equals_raw_asof=True,all_420_raw_security_identity=True,known_24_reproduced=True),
        assumptions=['Back/fore ratio compatibility is conditional on same cumulative multiplicative adjustment convention, not proof of provider correctness.',
            'Factor intervals use +/- one displayed decimal unit as a conservative sensitivity check, not verified vendor rounding bounds.',
            'Raw reference allows +/- half-cent exchange rounding; previous traded close is taken as observed.',
            'Cash/split formula (prior close - gross cash)/share multiplier is conditional on no rights contribution, differentiated-reference adjustment or other capital action.',
            'No cash/share inference, factor replacement, quote adjustment, network or backtest is performed.'])
    assert sha(SOURCE/'source_panel.parquet')==EXPECTED_SHA
    output_json.write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in summary.items() if key not in ['known24','additional_anomalies','raw_pair_incompatibilities_in_panel_range']},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
