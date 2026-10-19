"""Frozen weekly candidate display contracts; no financial replay."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

TOOLS=Path(__file__).parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,TOOLS/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

class WeeklyOverviewTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue((TOOLS/'stage055_weekly_account_overview.py').exists(),'weekly display adapter is missing')
        self.mod=load('stage055_weekly_account_overview')
        fixture=load('test_stage042_account_overview').OverviewContractTest
        fixture.setUpClass();self.fixture=fixture('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.source=self.fixture.source;self.parent=self.fixture.parent;self.base=self.fixture.base
        self.baseline=self.base/'baseline';shutil.copytree(self.source,self.baseline)
        bm=json.loads((self.baseline/'manifest.json').read_text());bm['run_id']='baseline'
        (self.baseline/'manifest.json').write_text(json.dumps(bm))
        self.metrics=self.fixture.metrics;self.manifest=self.fixture.manifest
        self.metrics.update(payoff_ratio=2.5,profit_factor=1.2,win_rate_pct=33.3,total_trade_count=2,total_commission=1.2,total_slippage=2.0,
            long_weekly_filter=True,weekly_policy=dict(self.mod.WEEKLY_POLICY),baseline_commit=self.mod.BASELINE_COMMIT,actual_long_weekly_violations=0)
        self.metrics['boundaries']=['周线边界 <script>alert(1)</script>']
        self.manifest.update(long_weekly_filter=True,weekly_policy=dict(self.mod.WEEKLY_POLICY),baseline_commit=self.mod.BASELINE_COMMIT,
            baseline_run_manifest_sha256=self.mod.base.sha(self.baseline/'manifest.json'))
        for name in self.mod.WEEKLY_FILES:(self.source/name).write_text('fixture\n')
        self.freeze()

    def freeze(self):
        self.fixture.freeze()
        (self.parent/'index.html').write_text('frozen canonical recap')
        p=json.loads((self.parent/'summary.json').read_text());p['artifact_sha256']={'index.html':self.mod.base.sha(self.parent/'index.html')}
        (self.parent/'summary.json').write_text(json.dumps(p))

    def test_weekly_labels_comparison_and_exact_reused_plot(self):
        b=self.mod.load_bundle(self.source,self.parent,self.baseline)
        fig,plot=self.mod.base.make_plot(b);page=self.mod.make_page(b,plot,self.base/'out')
        direct,_=self.mod.base.make_plot(self.mod.base.load_bundle(self.source,self.parent))
        self.assertEqual(fig.to_json(),direct.to_json());self.assertEqual(fig.layout.xaxis.matches,'x2')
        for value in ('周线开多候选','MA5&gt;MA10&gt;MA20&gt;MA40','A 基线','C 周线候选','净盈亏比','盈利因子','日线近似','原生风险预算','不足40周','不作为晋级结论'):
            self.assertTrue(value in page,value)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',page);self.assertNotIn('<script>alert(1)</script>',page)
        self.assertEqual(b['facts']['comparison'][1]['candidate'],95)
        self.assertEqual(b['facts']['baseline_manifest_sha256'],self.manifest['baseline_run_manifest_sha256'])
        for value in ('品种未复权因果主力完成周收盘','图上周MA未必与门槛序列一致','stage051_weekly_signal_snapshot','stage051_weekly_open_snapshot'):
            self.assertTrue(value in page,value)
        for name in (*self.mod.WEEKLY_FILES,'trades.csv'):
            self.assertTrue('../test_run/'+name in page,name)

    def test_policy_missing_or_lookahead_rejected(self):
        self.metrics['weekly_policy']={**self.mod.WEEKLY_POLICY,'execution_phase':'same_day_close'};self.freeze()
        with self.assertRaisesRegex(ValueError,'weekly_policy'):self.mod.load_bundle(self.source,self.parent,self.baseline)
        self.metrics['weekly_policy']=dict(self.mod.WEEKLY_POLICY);self.manifest['long_weekly_filter']=False;self.freeze()
        with self.assertRaisesRegex(ValueError,'weekly_filter'):self.mod.load_bundle(self.source,self.parent,self.baseline)

    def test_baseline_binding_parameters_and_tamper_rejected(self):
        self.manifest['baseline_run_manifest_sha256']='0'*64;self.freeze()
        with self.assertRaisesRegex(ValueError,'baseline_manifest'):self.mod.load_bundle(self.source,self.parent,self.baseline)
        self.manifest['baseline_run_manifest_sha256']=self.mod.base.sha(self.baseline/'manifest.json')
        self.manifest['parameters']={**self.manifest['parameters'],'risk_ratio':.3};self.freeze()
        with self.assertRaisesRegex(ValueError,'baseline_parameters'):self.mod.load_bundle(self.source,self.parent,self.baseline)
        self.manifest['parameters'].pop('risk_ratio');self.freeze()
        (self.baseline/'daily.csv').write_text('changed')
        with self.assertRaisesRegex(ValueError,'source_hash_mismatch'):self.mod.load_bundle(self.source,self.parent,self.baseline)

    def test_budget_parent_and_output_isolation(self):
        self.metrics['next_open_risk_recheck']=False;self.freeze()
        with self.assertRaisesRegex(ValueError,'budget_policy'):self.mod.load_bundle(self.source,self.parent,self.baseline)
        self.metrics['next_open_risk_recheck']=True;self.freeze()
        (self.parent/'index.html').write_text('changed')
        with self.assertRaisesRegex(ValueError,'parent_artifact'):self.mod.load_bundle(self.source,self.parent,self.baseline)
        for out in (self.baseline,self.baseline/'child',self.source,self.parent,self.base):
            with self.assertRaises(ValueError):self.mod.check_output(self.source,self.parent,self.baseline,out)

    def test_fixture_generation_binds_outputs_and_inputs(self):
        output=self.base/'weekly_overview'
        f=self.mod.generate(self.source,self.parent,self.baseline,output)
        self.assertFalse(f['strategy_rerun']);self.assertFalse(f['market_download']);self.assertFalse(f['production_access'])
        for name,digest in f['artifact_sha256'].items():self.assertEqual(self.mod.base.sha(output/name),digest)
        self.assertGreater((output/'equity_drawdown.png').stat().st_size,1000)
        self.assertEqual(f['generator_sha256'],self.mod.base.sha(TOOLS/'stage055_weekly_account_overview.py'))
        self.assertEqual(f['overview_adapter_sha256'],self.mod.base.sha(TOOLS/'stage042_account_overview.py'))
        with self.assertRaisesRegex(ValueError,'output_already_exists'):self.mod.generate(self.source,self.parent,self.baseline,output)

if __name__=='__main__':unittest.main()
