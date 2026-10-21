"""Three synthetic214 fixtures; no accepted training caches, targets or fits."""
import importlib.util
import io
import math
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('fixture_stage214',Path(__file__).with_name('stage214_training_domain_probe.py'))
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)

CALENDAR=['2018-12-28','2019-01-02','2019-01-03','2019-02-01','2019-02-04']


def synthetic_frame():
    epochs=['201903','201902','201904','201904','201812']
    products=['DCE.a','DCE.a','DCE.a_F','DCE.a_F','DCE.b']
    indexes=[1,0,3,4,4]
    weights=[0.12345678901234568,1./3.,math.pi,1.e-7,2.]
    rows=[]
    for i,(month,product,u,weight) in enumerate(zip(epochs,products,indexes,weights)):
        rows.append(dict(sequence_index=i*3,action_id='a'+str(i),product_id=product,
            family_id=product.removesuffix('_F'),u_date=CALENDAR[u],u_index=u,
            reference_epoch=product+'.'+month,u_action_eligible=1,
            label_known_date='2019-03-01',sample_weight=weight))
    return pd.DataFrame(rows,columns=probe.READ_COLUMNS)


class TrainingDomainFixtures(unittest.TestCase):
    def test_fixed_156_gate_all_calendar_edges_and_sentinel_priority(self):
        cases=[(1,'DCE.a.201903','admissible','D_before_K'),
               (2,'DCE.a.201903','inadmissible','D_on_or_after_K'),
               (0,'DCE.a.201902','inadmissible','D_on_or_after_K'),
               (3,'DCE.a.201904','admissible','K_after_calendar_D_before_target'),
               (4,'DCE.a.201904','unknown','next_source_session_unknown'),
               (4,'DCE.a.201812','inadmissible','K_before_calendar_blocked')]
        for u,epoch,state,reason in cases:
            with self.subTest(u=u,epoch=epoch):
                actual=probe.action_gate(u,epoch,CALENDAR)
                self.assertEqual((actual['partition'],actual['gate_reason']),(state,reason))
        pending=probe.action_gate(3,'DCE.a.201904',CALENDAR)
        self.assertIsNone(pending['K_index']);self.assertEqual(pending['K_target_date'],'2019-03-01')
        self.assertEqual(probe.action_gate(2,'DCE.a.201903',CALENDAR)['D_index'],3)
        after_sample=probe.action_gate(0,'DCE.a.202701',CALENDAR)
        self.assertTrue(after_sample['K_after_sample_end']);self.assertEqual(after_sample['partition'],'admissible')
        for invalid in (-1,5,1.5,True):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                probe.action_gate(invalid,'DCE.a.201903',CALENDAR)

    def test_exact_cached_weights_and_training_identity_fail_closed(self):
        original=synthetic_frame()
        exported=original.to_csv(index=False,float_format='%.17g')
        cached=pd.read_csv(io.StringIO(exported),dtype=str,keep_default_na=False,float_precision='round_trip')
        restored=probe.validate_frame(cached,'main','2020-01-01',5,CALENDAR)
        np.testing.assert_array_equal(restored.sample_weight.to_numpy(),original.sample_weight.to_numpy())
        corruptions=[('sample_weight','0'),('u_action_eligible','0'),('u_index','1.5'),
                     ('u_date','2019-01-03'),('label_known_date','2020-01-01'),
                     ('reference_epoch','DCE.b.201903'),('family_id','DCE.a_F')]
        for field,value in corruptions:
            changed=cached.copy();changed.loc[0,field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                probe.validate_frame(changed,'main','2020-01-01',5,CALENDAR)
        changed=cached.copy();changed.loc[1,'sequence_index']='0'
        with self.assertRaises(ValueError):probe.validate_frame(changed,'main','2020-01-01',5,CALENDAR)
        with self.assertRaises(ValueError):probe.validate_frame(cached.assign(net_R_stress=999),'main','2020-01-01',5,CALENDAR)

    def test_full_partition_old_mass_group_conservation_and_bounded_anchors(self):
        original=synthetic_frame();summary,groups,support,anchors=probe.probe_frame(
            original,'main','2020-01-01',5,CALENDAR,[0,2,4])
        self.assertEqual([summary[s+'_rows'] for s in probe.PARTITIONS],[2,2,1])
        expected={'admissible':math.fsum(original.sample_weight.iloc[[0,2]]),
                  'inadmissible':math.fsum(original.sample_weight.iloc[[1,4]]),
                  'unknown':float(original.sample_weight.iloc[3])}
        for state,mass in expected.items():
            self.assertEqual(summary[state+'_old_weight_mass'],mass)
            self.assertEqual(summary[state+'_weight_fraction'],mass/math.fsum(original.sample_weight))
        self.assertEqual(summary['old_weight_mass'],math.fsum(original.sample_weight))
        self.assertEqual([a['sequence_index'] for a in anchors],[0,6,12])
        self.assertEqual([a['partition'] for a in anchors],['admissible','admissible','inadmissible'])
        self.assertEqual(len(groups['year']),2);self.assertEqual(len(groups['family']),2)
        self.assertEqual(len(groups['product']),3)
        self.assertFalse(support['old_weights_recomputed']);self.assertFalse(support['old_weights_renormalized'])
        for check in support['checks']:
            self.assertTrue(check['count_fields_exact'])
            self.assertTrue(all(abs(v)<=check['weight_roundoff_tolerance'] for v in check['weight_residuals'].values()))
        with self.assertRaises(ValueError):
            probe.probe_frame(original,'main','2020-01-01',5,CALENDAR,[5])


if __name__=='__main__':unittest.main()
