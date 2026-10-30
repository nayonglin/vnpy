import unittest
from test_stage009_plots import synthetic_bundle
from stage009_report import make_pairs,cohort_summary,require_complete


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.summary,cls.pairs,cls.daily=synthetic_bundle()

    def test_pair_scope_and_strict_equity_gate(self):
        p=make_pairs(self.summary)
        self.assertEqual(len(p),46)
        self.assertEqual(int(p.vote_eligible.sum()),44)
        self.assertEqual(int(p.observation_only.sum()),2)
        for arm in ['A','C']:
            self.assertEqual(len(p[p.arm.eq(arm)]),23)
        s=self.summary.copy();row=s.index[s.variant.eq('A_R')][0];control=s.loc[s.start.eq(s.loc[row,'start'])&s.variant.eq('A_idle')].iloc[0]
        for k in ['end_equity','max_dd_pct','sharpe']:s.loc[row,k]=control[k]
        self.assertFalse(make_pairs(s).iloc[0].equity_gate)

    def test_mature_and_observation_cohorts_never_mix(self):
        p=make_pairs(self.summary);c=cohort_summary(self.summary,p)
        self.assertEqual(len(c),12)
        for arm in ['A','C']:
            whole=c.loc[c.arm.eq(arm)&c.cohort.eq('combined')]
            mature=whole.loc[whole['sample'].eq('complete_ge_1y')].iloc[0]
            observation=whole.loc[whole['sample'].eq('observation_lt_1y')].iloc[0]
            self.assertEqual(mature.vote_windows,22);self.assertEqual(observation.vote_windows,0)
            self.assertEqual(observation.observation_windows,1)
            self.assertTrue(__import__('pandas').isna(observation.return_wins_rate_pct))

    def test_incomplete_or_duplicate_summary_is_rejected(self):
        for bad in [self.summary.iloc[:-1],__import__('pandas').concat([self.summary.iloc[:-1],self.summary.iloc[[0]]])]:
            with self.assertRaises(ValueError):make_pairs(bad)

    def test_partial_financial_batch_cannot_publish(self):
        jobs={str(i):dict(status='validated') for i in range(46)}
        r=dict(jobs=jobs,counts=dict(validated=46,failed=0,total=46),financial_engine_batch_complete=True,financial_replays_started=46)
        self.assertTrue(require_complete(r,92,46))
        for n,a in [(91,46),(92,45)]:
            with self.assertRaises(ValueError):require_complete(r,n,a)
        r['financial_engine_batch_complete']=False
        with self.assertRaises(ValueError):require_complete(r,92,46)


if __name__=='__main__':unittest.main()
