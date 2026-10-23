"""Read-only ledger/statistics tests; never invoke report main or financial replay."""
from pathlib import Path
import json,tempfile,unittest
import pandas as pd
try:
    import stage008_build_artifacts as report
except ImportError:
    report=None


def trades(rows):
    return pd.DataFrame([dict(trade_id=f'T{i+1}',vt_symbol='x2501.TEST',direction=d,offset=o,
        price=p,volume=v,datetime=t) for i,(d,o,p,v,t) in enumerate(rows)])


def effective(rate=0.):
    return dict(sizes={'x2501.TEST':10.},slippages={'x2501.TEST':1.},rates={'x2501.TEST':rate})


class ReportTests(unittest.TestCase):
    def api(self):self.assertIsNotNone(report,'Stage008 report implementation missing')
    def test_fifo_partial_closes_allocate_both_slippage_and_fees(self):
        self.api()
        t=trades([('多','开',100,2,'2025-01-01T09:00:00+08:00'),('空','平',110,1,'2025-01-02T09:00:00+08:00'),('空','平',95,1,'2025-01-03T09:00:00+08:00')])
        segments,s=report.fifo_segments(t,effective(.001))
        self.assertEqual(len(segments),2);self.assertAlmostEqual(segments.net_pnl.iloc[0],77.9)
        self.assertAlmostEqual(segments.net_pnl.iloc[1],-71.95)
        self.assertAlmostEqual(s['closed_net_pnl'],5.95);self.assertEqual(s['open_quantity'],0.)
        self.assertAlmostEqual(s['total_slippage'],40.);self.assertAlmostEqual(s['total_commission'],4.05)
        self.assertEqual(s['winning_segments'],1);self.assertEqual(s['losing_segments'],1)
    def test_fifo_uses_actual_clock_not_shuffled_csv_or_trading_date(self):
        self.api()
        t=trades([('空','开',100,1,'2025-01-01T21:00:00+08:00'),('多','平',90,1,'2025-01-02T21:00:00+08:00')])
        clock=t[['trade_id','vt_symbol','direction','offset','price','volume']].copy()
        clock['execution_datetime']=t.datetime
        t=t.iloc[::-1].copy();t['trading_date']=['2020-01-01','2030-01-01']
        segments,s=report.fifo_segments(t,effective(),clock=clock)
        self.assertEqual(segments.entry_trade_id.tolist(),['T1']);self.assertEqual(s['closed_net_pnl'],80.)
    def test_unmatched_or_overclose_rejected(self):
        self.api()
        for rows in [[('空','平',100,1,'2025-01-01T09:00:00')],
                     [('多','开',100,1,'2025-01-01T09:00:00'),('空','平',110,2,'2025-01-02T09:00:00')]]:
            with self.assertRaises(ValueError):report.fifo_segments(trades(rows),effective())
    def test_bad_clock_identity_missing_metadata_or_quantity_rejected(self):
        self.api();t=trades([('多','开',100,1,'2025-01-01T09:00:00')])
        with self.assertRaises(ValueError):report.fifo_segments(t,dict(sizes={},rates={},slippages={}))
        bad=t.copy();bad.volume=0
        with self.assertRaises(ValueError):report.fifo_segments(bad,effective())
        clock=t.copy();clock['execution_datetime']=clock.datetime;clock.price=999
        with self.assertRaises(ValueError):report.fifo_segments(t,effective(),clock=clock)
    def test_open_inventory_mtm_deducts_unallocated_entry_cost(self):
        self.api();t=trades([('多','开',100,2,'2025-01-01T09:00:00')])
        segments,s=report.fifo_segments(t,effective(),terminal_marks={'x2501.TEST':110.})
        self.assertEqual(len(segments),0);self.assertEqual(s['open_quantity'],2.)
        self.assertEqual(s['open_unrealized_net'],180.);self.assertEqual(s['ledger_net_pnl'],180.)
        self.assertIsNone(s['win_rate_pct']);self.assertIsNone(s['profit_factor'])
    def test_native_product_is_case_preserving_and_closed_to_frozen19(self):
        self.api();self.assertEqual(report.native_product('CF501.CZCE',{'CF.CZCE'}),'CF.CZCE')
        with self.assertRaises(ValueError):report.native_product('eb2501.DCE',{'CF.CZCE'})
    def test_annual_compounds_previous_equity_and_marks_terminal_ytd(self):
        self.api()
        d=pd.DataFrame(dict(date=pd.to_datetime(['2025-12-30','2025-12-31','2026-01-02']),
            account_equity=[180000.,200000.,190000.],net_pnl=[30000.,20000.,-10000.],
            trade_count=[1,1,1],slippage=[1.,2.,3.],commission=[0.,0.,0.]))
        rows=report.annual_rows(d,'G',report.classify_g({'accepted':False,'verdict':'REJECT_EXECUTION_ZERO_VOLUME'}))
        self.assertAlmostEqual(rows[0]['return_pct'],100/3);self.assertEqual(rows[1]['starting_equity'],200000.)
        self.assertAlmostEqual(rows[1]['return_pct'],-5.);self.assertEqual(rows[1]['period'],'2026 YTD')
        self.assertTrue(all('DIAGNOSTIC' in r['performance_classification'] for r in rows))
    def test_rejected_g_never_gains_valid_performance_or_qualified_counts(self):
        self.api();status=report.classify_g({'accepted':False,'verdict':'REJECT_EXECUTION_ZERO_VOLUME'})
        self.assertFalse(status['valid_performance_accepted']);self.assertFalse(status['production_qualified'])
        self.assertIsNone(status['qualified_executable_trade_count']);self.assertIsNone(status['qualified_executable_product_count'])
        self.assertIn('DIAGNOSTIC',status['performance_classification'])
    def test_positive_minute_audit_without_review_is_still_conditional(self):
        self.api();s=report.classify_g({'accepted':True,'verdict':'PASS_POSITIVE_EXECUTION_MINUTES'})
        self.assertFalse(s['valid_performance_accepted']);self.assertIn('PENDING',s['performance_classification'])
    def test_review_binding_is_exact_and_rejection_wins(self):
        self.api();path=Path('/private/tmp/G_attempt001');audit={'accepted':True,'verdict':'PASS_POSITIVE_EXECUTION_MINUTES'}
        review=dict(schema='stage008_independent_review_v1',g_attempt_path=str(path),verdict='REJECT_EXECUTION_ZERO_VOLUME')
        s=report.classify_g(audit,review,path);self.assertFalse(s['valid_performance_accepted'])
        review['g_attempt_path']='/private/tmp/G_attempt002'
        with self.assertRaises(ValueError):report.classify_g(audit,review,path)
    def test_review_pass_remains_offline_and_does_not_qualify_counts(self):
        self.api();path=Path('/private/tmp/G_attempt001')
        review=dict(schema='stage008_independent_review_v1',g_attempt_path=str(path),verdict='PASS_OFFLINE_RESEARCH')
        s=report.classify_g({'accepted':True,'verdict':'PASS_POSITIVE_EXECUTION_MINUTES'},review,path)
        self.assertTrue(s['valid_performance_accepted']);self.assertFalse(s['production_qualified'])
        self.assertIsNone(s['qualified_executable_trade_count']);self.assertEqual(s['promotion_decision'],'NO_PROMOTION')
        s=report.classify_g({'accepted':False,'verdict':'REJECT_EXECUTION_ZERO_VOLUME'},review,path)
        self.assertFalse(s['valid_performance_accepted'])
    def test_artifact_existing_bytes_never_overwritten(self):
        self.api()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'old.png';p.write_bytes(b'frozen')
            with self.assertRaises(FileExistsError):report.require_new_outputs([p])
            self.assertEqual(p.read_bytes(),b'frozen')
    def test_e9_reviewed_fifo_and_full_ledger_conservation(self):
        self.api()
        line=next((p for p in Path(__file__).resolve().parents if p.name=='futures_weekly_formal_no_half_r'),
            Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r'))
        p=line/'outputs/E_attempt009'
        if not p.exists():self.skipTest('E9 private reviewed ledger unavailable')
        products=set(json.loads((p/'preflight.json').read_text())['universe_products'])
        ledger=report.load_ledger(p,'E',products)
        s=ledger['fifo_stats'];self.assertEqual(s['closed_segments'],54)
        self.assertEqual(s['winning_segments'],24);self.assertEqual(s['losing_segments'],29);self.assertEqual(s['breakeven_segments'],1)
        self.assertAlmostEqual(s['payoff_ratio'],2.599166,places=5);self.assertAlmostEqual(s['profit_factor'],2.151034,places=5)
        self.assertEqual(s['open_quantity'],0.);self.assertAlmostEqual(s['ledger_net_pnl'],185420.,places=6)
        self.assertAlmostEqual(ledger['metrics']['end_equity'],335420.,places=6)
        self.assertEqual(ledger['metrics']['modeled_fill_count'],108)
        self.assertEqual(ledger['metrics']['modeled_traded_product_count'],17)
        self.assertEqual(ledger['metrics']['pool_product_count'],19)


    def test_zero_fill_ledger_reports_zero_counts_not_a_false_winner(self):
        self.api()
        t=pd.DataFrame(columns=['date','vt_symbol','event','reason'])
        segments,s=report.fifo_segments(t,effective(),clock=t.copy())
        self.assertEqual(len(segments),0);self.assertEqual(s['closed_segments'],0)
        self.assertEqual(s['ledger_net_pnl'],0.);self.assertEqual(s['open_quantity'],0.)
        self.assertIsNone(s['win_rate_pct']);self.assertIsNone(s['profit_factor'])
    def test_nonpositive_equity_is_preserved_with_undefined_sharpe(self):
        self.api()
        d=pd.DataFrame(dict(date=pd.to_datetime(['2026-01-02','2026-01-05']),
            account_equity=[150000.,-15000.],net_pnl=[0.,-165000.],trade_count=[0,1],slippage=[0.,1.],commission=[0.,0.]))
        m=report.curve_metrics(d)
        self.assertEqual(m['end_equity'],-15000.);self.assertAlmostEqual(m['max_dd_pct'],-110.)
        self.assertIsNone(m['sharpe']);self.assertEqual(m['nonpositive_equity_days'],1)

if __name__=='__main__':unittest.main()
