"""Exact-contract overview identity and comparison contracts; no financial replay."""
import importlib.util,json,shutil,unittest
from pathlib import Path
TOOLS=Path(__file__).parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,TOOLS/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class ContractOverviewTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue((TOOLS/'stage062_contract_weekly_overview.py').exists(),'exact-contract overview missing')
        self.mod=load('stage062_contract_weekly_overview');f=load('test_stage055_weekly_account_overview').WeeklyOverviewTest('runTest');f.setUp();self.addCleanup(f.doCleanups);self.f=f
        self.source,self.parent,self.baseline,self.root=f.source,f.parent,f.baseline,f.base
        self.previous=self.root/'previous_main';shutil.copytree(self.source,self.previous)
        pm=json.loads((self.previous/'manifest.json').read_text());pm['run_id']=self.previous.name;(self.previous/'manifest.json').write_text(json.dumps(pm))
        f.metrics.update(weekly_policy=dict(self.mod.WEEKLY_POLICY),previous_weekly_main_commit=self.mod.PREVIOUS_MAIN_COMMIT,previous_weekly_main_manifest_sha256=self.mod.old.base.sha(self.previous/'manifest.json'))
        f.manifest.update(weekly_policy=dict(self.mod.WEEKLY_POLICY),previous_weekly_main_commit=self.mod.PREVIOUS_MAIN_COMMIT,previous_weekly_main_manifest_sha256=self.mod.old.base.sha(self.previous/'manifest.json'))
        (self.source/'weekly_contract_features.csv').write_text('contract_vt_symbol\nfixture\n');f.freeze()

    def test_contract_policy_three_way_comparison_and_plot_unchanged(self):
        b=self.mod.load_bundle(self.source,self.parent,self.baseline,self.previous);fig,plot=self.mod.old.base.make_plot(b)
        direct,_=self.mod.old.base.make_plot(self.mod.old.base.load_bundle(self.source,self.parent));self.assertEqual(fig.to_json(),direct.to_json())
        page=self.mod.make_page(b,plot,self.root/'overview')
        for word in ('交易合约自身','不用主力连续','合约周线候选','上一主力周线版本','stage059_weekly_signal_snapshot','weekly_contract_features.csv','不作为晋级结论'):
            self.assertTrue(word in page,word)
        self.assertEqual(self.mod.old.WEEKLY_POLICY['source'],'causal_main_unadjusted_accepted_clean')
        self.assertEqual(b['facts']['previous_main_manifest_sha256'],self.f.manifest['previous_weekly_main_manifest_sha256'])

    def test_real_fixture_generate_binds_three_sources_and_outputs(self):
        out=self.root/'overview';f=self.mod.generate(self.source,self.parent,self.baseline,self.previous,out)
        self.assertEqual(f['generator_sha256'],self.mod.old.base.sha(TOOLS/'stage062_contract_weekly_overview.py'))
        self.assertEqual(f['weekly_adapter_sha256'],self.mod.old.base.sha(TOOLS/'stage055_weekly_account_overview.py'))
        for name,digest in f['artifact_sha256'].items():self.assertEqual(self.mod.old.base.sha(out/name),digest)
        self.assertGreater((out/'equity_drawdown.png').stat().st_size,1000)
        with self.assertRaisesRegex(ValueError,'output_already_exists'):self.mod.generate(self.source,self.parent,self.baseline,self.previous,out)

    def test_main_policy_and_previous_identity_tamper_rejected(self):
        self.f.metrics['weekly_policy']=dict(self.mod.old.WEEKLY_POLICY);self.f.freeze()
        with self.assertRaisesRegex(ValueError,'weekly_policy'):self.mod.load_bundle(self.source,self.parent,self.baseline,self.previous)
        self.f.metrics['weekly_policy']=dict(self.mod.WEEKLY_POLICY);self.f.manifest['previous_weekly_main_manifest_sha256']='0'*64;self.f.freeze()
        with self.assertRaisesRegex(ValueError,'previous_main_manifest'):self.mod.load_bundle(self.source,self.parent,self.baseline,self.previous)

    def test_previous_output_overlap_and_frozen_sources_protected(self):
        with self.assertRaises(ValueError):self.mod.check_output(self.source,self.parent,self.baseline,self.previous,self.previous/'nested')
        (self.previous/'trades.csv').write_text('changed')
        with self.assertRaisesRegex(ValueError,'source_hash'):self.mod.load_bundle(self.source,self.parent,self.baseline,self.previous)

if __name__=='__main__':unittest.main()
