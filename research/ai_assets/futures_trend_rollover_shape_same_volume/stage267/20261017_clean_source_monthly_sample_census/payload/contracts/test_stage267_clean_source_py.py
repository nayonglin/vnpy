from pathlib import Path
import sqlite3
import pandas as pd
import unittest
import stage267_clean_source_adapter as source


def test_delivery_id_never_reuses_czce_three_digit_symbol():
    assert source.research_symbol('SM.CZCE', '201501') == 'SM201501.CZCE'
    assert source.research_symbol('SM.CZCE', '202501') == 'SM202501.CZCE'
    assert source.research_symbol('rb.SHFE', '201005') == 'rb201005.SHFE'


def test_exact_epoch_asof_preserves_dates_and_missing_opening_oi():
    frame = pd.DataFrame({'date': pd.to_datetime(['2014-12-30','2015-01-05','2015-01-06']),
                          'open_oi': [None]*3, 'close_oi': [12,15,18]})
    adapter = source.CleanSource.__new__(source.CleanSource)
    adapter.frames = {'SM201501.CZCE': frame}
    view = adapter.pairwise_bars('SM201501.CZCE', pd.Timestamp('2015-01-05'))
    assert view.date.tolist() == pd.to_datetime(['2014-12-30','2015-01-05']).tolist()
    assert view.open_oi.isna().all()
    assert view.close_oi.tolist() == [12,15]
    with unittest.TestCase().assertRaisesRegex(ValueError, 'missing_exact_epoch'):
        adapter.pairwise_bars('SM501.CZCE', pd.Timestamp('2025-01-05'))
    with unittest.TestCase().assertRaisesRegex(ValueError, 'stale_exact_epoch'):
        adapter.pairwise_bars('SM201501.CZCE', pd.Timestamp('2015-01-07'))


def test_prewarm_uses_real_contract_rows_including_before_main():
    cal = pd.bdate_range('2020-01-01', periods=145)
    counts = source.ready_dates(cal, cal, 140)
    assert not counts.iloc[138] and counts.iloc[139]
    # A missing day cannot become a fabricated zero-return bar.
    missing = source.ready_dates(cal.delete(140), cal, 140)
    assert not missing.iloc[140] and not missing.iloc[-1]


def test_metadata_renaming_keeps_original_economic_terms():
    info = pd.DataFrame([dict(research_symbol='SM201501.CZCE',native_symbol='SM501.CZCE',product_vt_symbol='SM.CZCE'),
                         dict(research_symbol='SM202501.CZCE',native_symbol='SM501.CZCE',product_vt_symbol='SM.CZCE')])
    old = {key:{'SM501.CZCE': value} for key,value in [('rates',0.0),('slippages',2.),('sizes',5),('priceticks',2.),('margin_ratios',.12),('metadata_sources','fixed')]}
    new = source.rename_metadata(old, info)
    assert len(new['vt_symbols']) == 2
    assert new['sizes'] == {'SM201501.CZCE':5,'SM202501.CZCE':5}
    assert new['margin_ratios']['SM201501.CZCE'] == .12
    assert new['source_symbol_by_contract']['SM202501.CZCE'] == 'SM.CZCE'


if __name__ == "__main__":
    suite = unittest.TestSuite(unittest.FunctionTestCase(fn) for name,fn in list(globals().items()) if name.startswith("test_") and callable(fn))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
