"""Only source-scope, append/conflict and immutable-key contracts; no build."""
import unittest
import pandas as pd

try:import stage020_reviewed_provider_overlay as module
except ImportError:module=None


class ProviderOverlayTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module,'Stage020 not implemented')
        self.grid=pd.date_range('2022-04-06 09:00',periods=3,freq='min')
        self.source=pd.DataFrame([dict(vt_symbol='AP205.CZCE',bar_datetime=stamp,
            open=100.,high=101.,low=99.,close=100.,volume=10.,open_oi=20.,close_oi=21.)for stamp in self.grid])
        self.daily=dict(open=100.,high=101.,low=99.,close=100.,volume=30.,open_oi=20.,close_oi=21.)

    def test_only_explicit_partial_review_sessions_and_stage016_exclusion(self):
        targets=[dict(vt_symbol=s,execution_trade_date='2022-04-06')for s in ['AP205.CZCE','AP210.CZCE','FG205.CZCE']]
        reviewed=[dict(**target,accepted=True)for target in targets[:2]]
        quality=[dict(**target,accepted=True,completion_evidence_complete=True)for target in targets]
        review=dict(qualified_research_data=True,p0_findings=0,p1_findings=0,accepted_sessions=reviewed)
        selected,excluded=module.select_reviewed_targets(dict(targets=targets),review,dict(sessions=quality),
            {('AP210.CZCE','2022-04-06')})
        self.assertEqual([r['vt_symbol']for r in selected],['AP205.CZCE'])
        self.assertEqual([r['vt_symbol']for r in excluded],['AP210.CZCE'])
        self.assertNotIn('FG205.CZCE',[r['vt_symbol']for r in selected])

    def test_append_preserves_old_values_and_any_conflict_isolated(self):
        existing=self.source.iloc[:1].copy()
        added,audit=module.qualify_append_session({'reviewed':self.source},self.grid,self.daily,existing,set())
        self.assertEqual(audit['status'],'accepted');self.assertEqual(len(added),2)
        self.assertFalse(self.grid[0]in set(added.bar_datetime))
        changed=existing.copy();changed.loc[changed.index[0],'high']=102.
        rejected,audit=module.qualify_append_session({'reviewed':self.source},self.grid,self.daily,changed,set())
        self.assertTrue(rejected.empty);self.assertEqual(audit['reason'],'base_overlap_conflict')
        with self.assertRaisesRegex(ValueError,'stage016_owned_grid'):
            module.qualify_append_session({'reviewed':self.source},self.grid,self.daily,existing,
                {('AP205.CZCE',self.grid[1])})

    def test_new_keys_must_avoid_existing_A0_and_all_stage016_scope(self):
        existing=self.source.iloc[:1].copy();added=self.source.iloc[1:].copy()
        allowed=module.keys(self.source)
        module.assert_new_keys(added,existing,allowed,set(),set())
        for a0,owned in [({('AP205.CZCE',self.grid[1])},set()),(set(),{('AP205.CZCE',self.grid[1])})]:
            with self.assertRaises(ValueError):module.assert_new_keys(added,existing,allowed,owned,a0)
        with self.assertRaises(ValueError):module.assert_new_keys(self.source,existing,allowed,set(),set())


if __name__=='__main__':unittest.main()
