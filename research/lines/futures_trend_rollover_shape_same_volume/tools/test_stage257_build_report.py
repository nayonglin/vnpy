"""Bounded fixtures only: no replay, downloads or real-account report generation."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import numpy as np
import pandas as pd

MODULE=Path(__file__).with_name('stage257_build_report.py')
if MODULE.exists():
    spec=importlib.util.spec_from_file_location('stage257_report',MODULE)
    report=importlib.util.module_from_spec(spec);spec.loader.exec_module(report)
else:
    report=None


def window(wid='primary',phase='ai_active_only',group='ai_primary',cohort='AI_inception'):
    return dict(window_id=wid,start='2022-02-07',end='2026-10-14',group=group,duration_years=1 if group=='1y' else 0,start_cohort=cohort,complete_duration=group!='YTD',policy_phase=phase)


def fixture_manifest(n=199,w=None):
    w=w or window();accounts={};aliases={}
    if w['policy_phase']=='common_pre_ai_only':
        rid=w['window_id']+'__COMMON_PRE_AI'
        accounts[rid]=dict(window_id=w['window_id'],pool_id='COMMON_PRE_AI',kind='common_pre_ai',start=w['start'],end=w['end'],path_id=None)
        aliases={w['window_id']+'__'+a:rid for a in ['AI_FAIR']+[f'RANDOM_{i:03d}' for i in range(1,n+1)]}
    else:
        for a in ['AI_FAIR']+[f'RANDOM_{i:03d}' for i in range(1,n+1)]:
            rid=w['window_id']+'__'+a
            accounts[rid]=dict(window_id=w['window_id'],pool_id=a,kind='ai_fair' if a=='AI_FAIR' else 'random_monthly',start=w['start'],end=w['end'],path_id=None if a=='AI_FAIR' else int(a[-3:]))
    return dict(windows=[w],accounts=accounts,aliases=aliases,capital=150000,primary_window=w['window_id'],full_random_count=199,rolling_random_count=49,turnover_random_count=199,strong_support_max_random_ge_ai=9,promotion_eligible=False)


def rows(m):
    result=[]
    for rid,a in m['accounts'].items():
        result.append(dict(run_id=rid,**a,status='complete',end_equity=200000 if a['kind']!='random_monthly' else 180000,total_return_pct=(200000/150000-1)*100 if a['kind']!='random_monthly' else 20.,max_dd_pct=-10.,sharpe=1.,strict_engine_and_data=True,path_data_incomplete=False,diagnostic_mode=False,independent_audit_status='PASS',total_slippage=100.,end_equity_2x_slippage_static=199900 if a['kind']!='random_monthly' else 179900,total_return_pct_2x_slippage_static=33.266 if a['kind']!='random_monthly' else 19.93,max_broker10_margin_to_equity_pct=30.,days_equity_nonpositive=0,fill_count=2))
    return pd.DataFrame(result)


class ImplementationExists(unittest.TestCase):
    def test_report_module_exists(self):
        self.assertIsNotNone(report,'Stage257 report implementation is not present')


@unittest.skipIf(report is None,'Implementation not present yet')
class ReportTests(unittest.TestCase):

    def test_initial_capital_loss_is_in_drawdown(self):
        d=pd.DataFrame(dict(date=['2025-01-02','2025-01-03'],account_equity=[120000.,135000.],net_pnl=[-30000.,15000.],slippage=[100.,50.]))
        stats=report.curve_statistics(d,150000.,'2025-01-01','2025-01-03')
        self.assertAlmostEqual(stats['max_dd_pct'],-20.)
        self.assertAlmostEqual(stats['max_dd_pct_2x_slippage_static'],-20.06666666666667)
        self.assertEqual(stats['end_equity_2x_slippage_static'],134850)

    def test_missing_random_prevents_b_and_q(self):
        m=fixture_manifest();r=rows(m);r.loc[r.index[-1],'status']='incomplete'
        s=report.window_comparison(m,m['windows'][0],r)
        self.assertFalse(s['sample_complete']);self.assertIsNone(s['b']);self.assertIsNone(s['q'])
        self.assertEqual(s['completed_random'],198)

    def test_primary_exact_199_and_ties_count_as_exceed(self):
        m=fixture_manifest();r=rows(m)
        # Select exactly ten random rows, not the AI row.
        r.loc[r.kind.eq('random_monthly'),'end_equity']=180000
        r.loc[r[r.kind.eq('random_monthly')].index[:10],'end_equity']=200000
        s=report.window_comparison(m,m['windows'][0],r)
        self.assertEqual(s['b'],10);self.assertAlmostEqual(s['q'],11/200)
        self.assertFalse(s['rank_gate']);self.assertEqual(s['random_n'],199)

    def test_49_window_is_descriptive_only(self):
        m=fixture_manifest(49,window('one','ai_active_only','1y','January'));r=rows(m)
        s=report.window_comparison(m,m['windows'][0],r)
        self.assertAlmostEqual(s['q'],1/50);self.assertIsNone(s['rank_gate'])
        self.assertEqual(s['evidence_role'],'rolling_descriptive_N49')

    def test_aliases_have_no_monte_carlo_sample_or_vote(self):
        m=fixture_manifest(49,window('common','common_pre_ai_only','1y','January'));r=rows(m)
        s=report.window_comparison(m,m['windows'][0],r)
        self.assertTrue(s['sample_complete']);self.assertEqual(s['random_n'],0)
        self.assertIsNone(s['q']);self.assertFalse(s['votes']);self.assertEqual(s['logical_label_count'],50)

    def test_stale_audit_rejected_including_sidecar(self):
        expected={'daily.csv':'daily','stage257_account_provenance.json':'sidecar','actual_strategy_settings.json':'settings'}
        audit=dict(run_id='x',experiment_manifest_sha256='manifest',status='PASS_DIAGNOSTIC',errors=[],source_hashes=dict(expected))
        self.assertEqual(report.audit_binding(audit,'x','manifest',expected),'PASS_DIAGNOSTIC')
        audit['source_hashes']['stage257_account_provenance.json']='old'
        self.assertEqual(report.audit_binding(audit,'x','manifest',expected),'stale')

    def test_diagnostic_does_not_become_strict_support(self):
        m=fixture_manifest();r=rows(m);r['diagnostic_mode']=True;r['strict_engine_and_data']=False;r['independent_audit_status']='PASS_DIAGNOSTIC'
        s=report.window_comparison(m,m['windows'][0],r)
        self.assertTrue(s['rank_gate']);self.assertFalse(s['strict_data_review_gate'])

    def test_nonfinite_endpoint_and_duplicate_ids_fail_closed(self):
        m=fixture_manifest();r=rows(m);r.loc[1,'end_equity']=np.nan
        with self.assertRaises(ValueError):report.window_comparison(m,m['windows'][0],r)
        with self.assertRaises(ValueError):report.window_comparison(m,m['windows'][0],pd.concat([rows(m),rows(m).iloc[:1]]))

    def test_only_pure_ai_full_six_cohorts_can_support(self):
        ws=[];comparisons=[]
        for year in (1,2,3):
            for c in ['January','June']:
                w=window(f'{year}_{c}','ai_active_only',f'{year}y',c);w['duration_years']=year;ws.append(w)
                comparisons.append(dict(**w,sample_complete=True,votes=True,return_delta_pp=1.,dd_depth_delta_pp=0.,sharpe_delta=0.,random_n=49))
        co=report.cohort_summary(ws,pd.DataFrame(comparisons));six=co[co.policy_phase.eq('ai_active_only')&co.start_cohort.ne('combined')]
        self.assertEqual(len(six),6);self.assertTrue(six.support_gate.all())
        comparisons[0]['return_delta_pp']=-1.
        co=report.cohort_summary(ws,pd.DataFrame(comparisons));self.assertFalse(co[co.policy_phase.eq('ai_active_only')&co.start_cohort.ne('combined')].support_gate.all())

    def test_ytd_never_votes(self):
        w=window('ytd','ai_active_only','YTD','January');m=fixture_manifest(49,w)
        self.assertFalse(report.window_comparison(m,w,rows(m))['votes'])

    def test_five_figures_fixed_order_even_without_results(self):
        w=window('missing','ai_active_only','1y','January')
        figs=report.standard_figures([w],{},pd.DataFrame(),pd.DataFrame(),{})
        self.assertEqual([f[0] for f in figs],['01_full_period','02_one_year','03_two_year','04_three_year','05_multicycle_summary'])

    def test_whole_report_stays_incomplete_when_audit_is_missing(self):
        m=fixture_manifest();r=rows(m);w=m['windows'][0]
        c=pd.DataFrame([report.window_comparison(m,w,r)])
        co=report.cohort_summary(m['windows'],c)
        r.loc[1,'independent_audit_status']='pending'
        d=report.decision_summary(m,r,c,co,True)
        self.assertEqual(d['status'],'INCOMPLETE');self.assertIsNone(d['primary_gates_satisfied'])

    def test_full_diagnostic_never_claims_strict_superiority(self):
        m=fixture_manifest();r=rows(m);r['diagnostic_mode']=True;r['strict_engine_and_data']=False
        c=pd.DataFrame([report.window_comparison(m,m['windows'][0],r)])
        co=report.cohort_summary(m['windows'],c)
        self.assertEqual(report.decision_summary(m,r,c,co,True)['status'],'COMPLETE_DIAGNOSTIC_ONLY')

    def test_extra_audit_source_cannot_be_silently_unbound(self):
        audit=dict(run_id='x',experiment_manifest_sha256='m',status='PASS',source_hashes={'daily.csv':'a','entry_risk.csv':'b'},errors=[])
        self.assertEqual(report.audit_binding(audit,'x','m',{'daily.csv':'a'}),'stale')

    def test_partial_random_curves_have_no_distribution_band(self):
        w=window('one','ai_active_only','1y','January');m=fixture_manifest(49,w)
        d=pd.DataFrame(dict(date=['2022-02-08'],account_equity=[140000.]))
        ai=w['window_id']+'__AI_FAIR';random=w['window_id']+'__RANDOM_001'
        b=report.make_bands(w,m,{ai:d,random:d})
        self.assertNotIn('median',b);self.assertEqual(b.AI_FAIR.iloc[0],150000.)
        with self.assertRaises(ValueError):report.make_bands(w,m,{ai:d,random:d.assign(date='2022-02-09')})

    def test_turnover_family_never_pools_with_iid(self):
        m=fixture_manifest();w=m['windows'][0]
        for i in range(1,200):
            k=f'primary__TURNOVER_{i:03d}'
            m['accounts'][k]=dict(window_id='primary',pool_id=f'TURNOVER_{i:03d}',kind='turnover_matched',start=w['start'],end=w['end'],path_id=i)
        r=rows(m);r.loc[r.kind.eq('turnover_matched'),'end_equity']=250000.
        iid=report.window_comparison(m,w,r);turn=report.window_comparison(m,w,r,'turnover_matched')
        self.assertEqual(iid['b'],0);self.assertEqual(turn['b'],199)
        self.assertEqual(iid['random_n'],199);self.assertEqual(turn['random_n'],199)

    def test_require_complete_does_not_write_partial_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);m=fixture_manifest();m['turnover_random_count']=0;mf=p/'experiment_manifest.json';mf.write_text(json.dumps(m))
            # Stop at the completion gate without policies, chart generation or source writes.
            cal=p/'calendar.csv';pd.DataFrame({'date':['2022-02-08']}).to_csv(cal,index=False)
            m['accepted_calendar_daily']=str(cal);mf.write_text(json.dumps(m));mh=report.digest(mf)
            with mock.patch.object(report,'FROZEN_MANIFEST_SHA',mh):
                with self.assertRaisesRegex(ValueError,'require-complete'):
                    report.build_report(p,p/'report',True)
            self.assertFalse((p/'report').exists())

    def test_static_five_images_are_standalone_and_chinese_table_is_readable(self):
        w=window('missing','ai_active_only','1y','January')
        with tempfile.TemporaryDirectory() as tmp:
            images=report.standard_static_images([w],{},pd.DataFrame(),pd.DataFrame(),{},Path(tmp))
            self.assertEqual(len(images),10)
            self.assertEqual(sum(p.suffix=='.svg' for p in images),5)
            self.assertTrue(all(p.read_bytes().startswith(b'\x89PNG') for p in images if p.suffix=='.png'))
            import xml.etree.ElementTree as ET
            self.assertTrue(all(ET.parse(p).getroot().tag.endswith('svg') for p in images if p.suffix=='.svg'))
        d=pd.DataFrame([dict(window_id='x',policy_phase='ai_active_only',sample_complete=False,strict_data_review_gate=False)])
        display=report.main_window_table(d)
        self.assertIn('窗口',display);self.assertNotIn('window_id',display)
        self.assertIn('随机中位收益 %',display);self.assertTrue(display['随机中位收益 %'].isna().all())
        self.assertEqual(display.iloc[0]['阶段'],'纯 AI 期')

    def test_cycle_cost_and_open_mtm_from_own_fills(self):
        t=pd.DataFrame([dict(trade_id='BT.1',vt_symbol='x.X',price=100.,volume=2,signed_volume=2,offset='Open',trading_date='2025-01-02'),dict(trade_id='BT.2',vt_symbol='x.X',price=110.,volume=1,signed_volume=-1,offset='Close',trading_date='2025-01-03')])
        p=pd.DataFrame([dict(date='2025-01-03',vt_symbol='x.X',end_pos=1,close_price=115)])
        closed,opened,cost=report.cycle_ledger(t,p,dict(contract_sizes={'x.X':10},rates={'x.X':0},slippages={'x.X':1}),'2025-01-03')
        self.assertEqual(len(closed),0);self.assertEqual(cost,30);self.assertEqual(opened[0]['net_mtm'],220)

if __name__=='__main__':unittest.main()
