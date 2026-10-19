"""Display source-contract tests; no strategy or financial replay."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE=Path(__file__).with_name('stage042_account_overview.py')

class OverviewContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('stage042',MODULE)
        cls.mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.mod)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.source=self.base/'test_run';self.source.mkdir()
        self.parent=self.base/'recap';self.parent.mkdir()
        (self.source/'daily.csv').write_text('date,equity,balance,net_pnl,highlevel,drawdown,ddpercent\n2024-01-02,90,90,-10,100,-10,-10\n2024-01-03,95,95,5,100,-5,-5\n')
        (self.source/'trades.csv').write_text('trade_id,price\n1,90\n2,95\n')
        (self.source/'closed_episodes.csv').write_text('episode_id,net_pnl\n1,5\n')
        (self.source/'residual_open_positions.json').write_text(json.dumps([{'vt_symbol':'IC202403.CFFEX','date':'2024-01-03'}]))
        (self.source/'evidence.txt').write_text('extra bound evidence')
        self.metrics=dict(total_days=2,analysis_start='2024-01-01',analysis_end='2024-01-03',initial_capital=100,end_balance=95,total_return=-5,max_ddpercent=-10,max_drawdown=-10,sharpe_ratio=-.1,completed_episodes=1,residual_open_positions=1,mode='daily-proxy',native_risk_budget_restored=True,one_lot_is_maximum_not_fixed=True,next_open_risk_recheck=True,position_count_limit_removed=True,boundaries=['fixture only'])
        self.manifest=dict(run_id='test_run',parameters=dict(fixed_size=0,max_position_size=1),mode='daily-proxy',native_risk_budget_restored=True,one_lot_is_maximum_not_fixed=True,next_open_risk_recheck=True,position_count_limit_removed=True)
        self.freeze()

    def freeze(self):
        (self.source/'summary.json').write_text(json.dumps(self.metrics))
        self.manifest['hashes']={p.name:self.mod.sha(p) for p in self.source.iterdir() if p.is_file() and p.name!='manifest.json'}
        (self.source/'manifest.json').write_text(json.dumps(self.manifest))
        (self.parent/'summary.json').write_text(json.dumps(dict(source_manifest_sha256=self.mod.sha(self.source/'manifest.json'),backtest_metrics=self.metrics)))

    def test_dynamic_facts_and_initial_capital_peak(self):
        bundle=self.mod.load_bundle(self.source,self.parent)
        f=bundle['facts']
        self.assertEqual(f['completed_episodes'],1);self.assertEqual(f['residual_open_positions'],1)
        self.assertEqual(f['residual_open_dates'],['2024-01-03'])
        self.assertEqual(f['max_drawdown_peak_date'],'initial_capital')
        self.assertEqual(f['start'],'2024-01-02');self.assertEqual(f['end'],'2024-01-03')
        self.assertIn('evidence.txt',f['source_hashes'])
        fig,plot=self.mod.make_plot(bundle)
        page=self.mod.make_page(bundle,plot,self.base/'out')
        self.assertIn('1笔完整交易',page);self.assertIn('期末1项',page)
        self.assertIn('2024-01-02—2024-01-03',page)
        self.assertFalse('3218笔' in page);self.assertFalse('期末12项' in page)
        self.assertIn('原生风险预算',page);self.assertIn('fixed_size=0',page)
        self.assertEqual(fig.layout.xaxis.matches,'x2')

    def test_any_bound_file_tamper_rejected(self):
        (self.source/'evidence.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError,'source_hash_mismatch'):self.mod.load_bundle(self.source,self.parent)

    def test_parent_cross_run_rejected(self):
        p=json.loads((self.parent/'summary.json').read_text());p['source_manifest_sha256']='0'*64
        (self.parent/'summary.json').write_text(json.dumps(p))
        with self.assertRaisesRegex(ValueError,'parent_manifest_mismatch'):self.mod.load_bundle(self.source,self.parent)

    def test_restored_policy_required(self):
        self.metrics['native_risk_budget_restored']=False;self.freeze()
        with self.assertRaisesRegex(ValueError,'budget_policy'):self.mod.load_bundle(self.source,self.parent)

    def test_count_mismatch_rejected(self):
        self.metrics['residual_open_positions']=2;self.freeze()
        with self.assertRaisesRegex(ValueError,'residual_count'):self.mod.load_bundle(self.source,self.parent)

    def test_episodes_mismatch_rejected(self):
        self.metrics['completed_episodes']=2;self.freeze()
        with self.assertRaisesRegex(ValueError,'episode_count'):self.mod.load_bundle(self.source,self.parent)

    def test_output_isolation(self):
        for output in (self.source,self.source/'child',self.parent/'child',self.base):
            with self.assertRaises(ValueError):self.mod.check_output(self.source,self.parent,output)

    def test_hash_path_escape_rejected(self):
        self.manifest['hashes']['../outside']='0'*64
        (self.source/'manifest.json').write_text(json.dumps(self.manifest))
        p=dict(source_manifest_sha256=self.mod.sha(self.source/'manifest.json'),backtest_metrics=self.metrics)
        (self.parent/'summary.json').write_text(json.dumps(p))
        with self.assertRaisesRegex(ValueError,'unsafe_hash_path'):self.mod.load_bundle(self.source,self.parent)

if __name__=='__main__':unittest.main()
