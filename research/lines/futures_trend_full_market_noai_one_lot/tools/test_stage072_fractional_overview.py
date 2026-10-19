"""0.5% multi-lot overview: N trust anchor, no legacy budget claim, unchanged curves."""
import importlib.util,json,shutil,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class FractionalOverviewTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue((HERE/'stage072_fractional_overview.py').exists(),'fractional overview missing');self.mod=load('stage072_fractional_overview')
        F=load('test_stage042_account_overview').OverviewContractTest;F.setUpClass();self.f=F('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.source,self.parent,self.root=self.f.source,self.f.parent,self.f.base
        self.f.manifest['parameters'].update(min_position_size=1,max_concurrent_positions=93)
        self.f.metrics.update(long_weekly_filter=True,weekly_policy=dict(self.mod.WEEKLY_POLICY));self.f.manifest.update(long_weekly_filter=True,weekly_policy=dict(self.mod.WEEKLY_POLICY));self.f.freeze()
        self.baseline=self.root/'baseline_N';shutil.copytree(self.source,self.baseline);bm=json.loads((self.baseline/'manifest.json').read_text());bm['run_id']='baseline_N';(self.baseline/'manifest.json').write_text(json.dumps(bm))
        digest=self.mod.base.sha(self.baseline/'manifest.json')
        self.patches=[patch.object(self.mod,'BASELINE_SHA',digest),patch.object(self.mod.frac,'BASELINE_SHA',digest)]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        for item in (self.f.manifest,self.f.metrics):item.update(**self.mod.frac.FRACTIONAL_FLAGS,fractional_risk_policy=dict(self.mod.frac.FRACTIONAL_POLICY),baseline_commit=self.mod.frac.BASELINE_COMMIT)
        self.f.manifest['baseline_run_manifest_sha256']=digest;self.f.manifest['parameters'].update(stage068_risk_fraction=.005,max_position_size=2147483647);self.freeze()

    def freeze(self):
        self.f.freeze();(self.parent/'index.html').write_text('canonical fractional parent')
        p=json.loads((self.parent/'summary.json').read_text());p['artifact_sha256']={'index.html':self.mod.base.sha(self.parent/'index.html')};(self.parent/'summary.json').write_text(json.dumps(p))

    def test_strict_new_policy_N_only_comparison_and_same_plot(self):
        b=self.mod.load_bundle(self.source,self.parent,self.baseline);fig,plot=self.mod.make_plot(b);direct,_=self.mod.base.make_plot(b);self.assertEqual(fig.to_json(),direct.to_json())
        page=self.mod.make_page(b,plot,self.root/'out')
        for text in ('0.5%','5000','基线N','整手','不加仓','不作为晋级结论') :self.assertTrue(text in page,text)
        self.assertNotIn('原风险预算后最多1手',page);self.assertNotIn('全市场无AI风险预算最多一手',page);self.assertEqual(b['facts']['baseline_manifest_sha256'],self.f.manifest['baseline_run_manifest_sha256'])

    def test_wrong_fraction_legacy_one_lot_and_unapproved_parameter_changes_rejected(self):
        self.f.metrics['fractional_risk_policy']={**self.mod.frac.FRACTIONAL_POLICY,'risk_fraction':.0005};self.freeze()
        with self.assertRaisesRegex(ValueError,'fractional_risk_policy'):self.mod.load_bundle(self.source,self.parent,self.baseline)
        self.f.metrics['fractional_risk_policy']=dict(self.mod.frac.FRACTIONAL_POLICY);self.f.metrics['one_lot_is_maximum_not_fixed']=True;self.freeze()
        with self.assertRaisesRegex(ValueError,'legacy_one_lot'):self.mod.load_bundle(self.source,self.parent,self.baseline)
        self.f.metrics['one_lot_is_maximum_not_fixed']=False;self.f.manifest['parameters']['risk_ratio']=.02;self.freeze()
        with self.assertRaisesRegex(ValueError,'parameter_changes'):self.mod.load_bundle(self.source,self.parent,self.baseline)

    def test_N_hash_tamper_and_png_only_literal_changes(self):
        self.f.manifest['baseline_run_manifest_sha256']='0'*64;self.freeze()
        with self.assertRaisesRegex(ValueError,'baseline_N_manifest'):self.mod.load_bundle(self.source,self.parent,self.baseline)
        function,proof=self.mod.png_function();self.assertTrue(callable(function));self.assertTrue(proof['only_declared_text_literals_changed']);self.assertEqual(set(proof['literal_changes']),set(self.mod.PNG_LITERALS))

    def test_complete_fixture_render_binds_source_and_png_without_old_cap_label(self):
        out=self.root/'overview';f=self.mod.generate(self.source,self.parent,self.baseline,out)
        for name,digest in f['artifact_sha256'].items():self.assertEqual(self.mod.base.sha(out/name),digest)
        self.assertGreater((out/'equity_drawdown.png').stat().st_size,1000);self.assertEqual(f['generator_sha256'],self.mod.base.sha(HERE/'stage072_fractional_overview.py'))
        self.assertFalse(f['strategy_rerun']);self.assertTrue(f['png_adapter']['only_declared_text_literals_changed'])
        with self.assertRaises(ValueError):self.mod.generate(self.source,self.parent,self.baseline,out)

if __name__=='__main__':unittest.main()
