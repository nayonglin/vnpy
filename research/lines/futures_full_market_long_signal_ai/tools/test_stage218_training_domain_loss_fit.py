"""Only new loss-domain mass/global preflight/no-action semantics; zero fits."""
import importlib.util
import math
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('fixture_stage218',Path(__file__).with_name('stage218_training_domain_loss_fit.py'))
fit=importlib.util.module_from_spec(spec);spec.loader.exec_module(fit)


class DomainLossFixtures(unittest.TestCase):
    def test_fixed_domain_weights_preserve_relative_mass_and_do_not_recompute(self):
        calendar=['2018-12-28','2019-01-02','2019-01-03','2019-02-01','2019-02-04']
        weights=np.array([.1,.3,.6])
        mask,new,report=fit.domain_weights([1,3,0],['DCE.a.201903','DCE.a.201904','DCE.a.201902'],weights,calendar)
        np.testing.assert_array_equal(mask,[True,True,False])
        np.testing.assert_array_equal(new,weights[:2]*(math.fsum(weights)/math.fsum(weights[:2])))
        self.assertEqual(report['weight_uniform_factor'],2.5)
        self.assertEqual(math.fsum(new),math.fsum(weights))
        self.assertTrue(report['ready']);self.assertFalse(report['uniqueness_recomputed'])
        self.assertEqual(report['retained_rows'],2);self.assertEqual(report['excluded_rows'],1)
        self.assertAlmostEqual(report['retained_old_effective_sample_size'],report['candidate_effective_sample_size'])
        self.assertNotEqual(report['old_effective_sample_size'],report['candidate_effective_sample_size'])
        _,_,empty=fit.domain_weights([0],['DCE.a.201902'],[1.],calendar)
        _,_,unknown=fit.domain_weights([4],['DCE.a.201904'],[1.],calendar)
        self.assertFalse(empty['ready']);self.assertFalse(unknown['ready']);self.assertEqual(unknown['gate_unknown_rows'],1)
        np.testing.assert_array_equal(weights,[.1,.3,.6])

    def test_any_one_of_six_failed_support_prevents_every_fit_side_effect(self):
        cells=[dict(scope=s,cutoff=c,domain=dict(ready=True)) for s in fit.SCOPES for c in fit.CUTOFFS]
        called=[]
        value=fit.gated_fits(dict(ready=True,cells=cells),lambda:called.append('six_fits') or 17)
        self.assertEqual(value,17);self.assertEqual(called,['six_fits'])
        for index in range(6):
            changed=[dict(r,domain=dict(ready=i!=index)) for i,r in enumerate(cells)]
            self.assertIsNone(fit.gated_fits(dict(ready=True,cells=changed),lambda:self.fail('fit before all preflights')))
        for changed in (cells[:5],cells[:5]+[cells[0]]):
            self.assertIsNone(fit.gated_fits(dict(ready=True,cells=changed),lambda:self.fail('incomplete fold fit')))
        self.assertIsNone(fit.gated_fits(dict(ready=False,cells=cells),lambda:self.fail('global support rejected')))

    def test_main_identity_stops_cash_despite_new_score_magnitudes(self):
        records=[]
        for i in range(2):
            records.append(dict(sequence_index=i,event_id='p'+str(i),product_id='DCE.a',family_id='DCE.a',
                u_date='2020-01-02',u_index=2500+i,reference_epoch='DCE.a.202005',anchor_epoch='DCE.a.202005',
                chosen_action_id='a0' if i==0 else '',chosen_action_sequence_index=100 if i==0 else -1,
                chosen_epoch='DCE.a.202005' if i==0 else '',selected=int(i==0),score=0.2 if i==0 else np.nan))
        control=pd.DataFrame(records);candidate=control.iloc[::-1].copy();candidate['score']=[99.,777.]
        same=fit.selection_identity(candidate,control)
        self.assertTrue(same['identical_actions']);self.assertFalse(same['cash_eligible'])
        self.assertEqual(same['reason'],'no_action_change')
        changed=candidate.copy();idx=changed.index[changed.sequence_index.eq(0)][0]
        changed.loc[idx,['chosen_action_id','chosen_action_sequence_index','chosen_epoch']]=['a1',101,'DCE.a.202006']
        different=fit.selection_identity(changed,control)
        self.assertEqual(different['changed_parent_rows'],1);self.assertTrue(different['cash_eligible'])
        broken=control.copy();broken.loc[0,'anchor_epoch']='DCE.a.202006'
        with self.assertRaises(ValueError):fit.selection_identity(broken,control)


if __name__=='__main__':unittest.main()
