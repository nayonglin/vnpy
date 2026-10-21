"""Six frozen666 synthetic behavior classes; no historical input or actual fit."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent

def load(test):
    path=HERE/'stage667_esr_quantity_kernel.py'
    test.assertTrue(path.exists(),'ESR kernel implementation missing')
    spec=importlib.util.spec_from_file_location('esr667_fixture',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def row(period,my='2020/2021',sales='10',kind='Standard',number=1):
    return dict(source_row=str(number),period_end_date=period,commodityId='10',myDefinition=my,mycoTypeName=kind,weekNumber='1',netSales=sales)

def sources(m,rows):
    return m.prepare_sources({10:pd.DataFrame(rows)},[dict(commodity_id=10,MY_start_month=9)],dict(blackout_period_end_ranges=[]))

class ClockAndLatestGroup(unittest.TestCase):
    def test_dst_inclusive_cutoff_and_latest_invalid_is_not_skipped(self):
        m=load(self)
        self.assertEqual(m.assumed_available_at('2020-03-05').isoformat(),'2020-03-19T00:00:00-04:00')
        self.assertEqual(m.assumed_available_at('2020-10-22').isoformat(),'2020-11-05T00:00:00-05:00')
        s=sources(m,[row('2020-09-03'),row('2020-09-10',kind='MY Ending',number=2)])
        mp=m.build_calendar_map(['2020-09-16','2020-09-17','2020-09-24'],s)
        self.assertEqual(mp.report_period.tolist(),['','2020-09-03','2020-09-10'])
        self.assertEqual(mp.period_valid.tolist(),[False,True,False])
        self.assertEqual(mp.weekly_group.tolist(),['','2020-09-03','2020-09-10'])

class MYAndBlackout(unittest.TestCase):
    def test_multiple_my_rows_blackout_and_phase_use_original_group(self):
        m=load(self)
        rr=[row('2020-09-03',sales='-5'),row('2020-09-10',kind='MY Ending',number=2),row('2020-09-10',my='2021/2022',kind='MY Starting',number=3),row('2020-09-17',number=4),row('2020-09-24',my='2019/2020',number=5)]
        s=m.prepare_sources({10:pd.DataFrame(rr)},[dict(commodity_id=10,MY_start_month=9)],dict(blackout_period_end_ranges=[['2020-09-17','2020-09-17']]))
        self.assertEqual(len(s),5)
        self.assertEqual(s.period_valid.tolist(),[True,False,False,False,False])
        self.assertAlmostEqual(float(s.iloc[0].phase),2/365)
        self.assertEqual(float(s.iloc[0].netSales),-5.)
        self.assertEqual(s.iloc[0].netSales_literal,'-5')
        leap=sources(m,[row('2020-02-29',my='2019/2020')])
        self.assertAlmostEqual(float(leap.iloc[0].phase),181/366)

class PrefixScale(unittest.TestCase):
    def test_strict_source_prefix_median_and_zero_unsupported(self):
        m=load(self)
        s=sources(m,[row('2020-09-03',sales='-10'),row('2020-09-10',sales='30',number=2),row('2020-09-17',sales='999999',number=3)])
        p=m.prefix_scales(s,'2020-09-25')['10']
        self.assertEqual(p['scale'],20.)
        self.assertEqual(p['prefix_rows'],2)
        # Midnight NY on 09-17 is 12:00 CN, after the midnight-CN cutoff.
        self.assertFalse(m.prefix_scales(s,'2020-09-17')['10']['supported'])
        zero=sources(m,[row('2020-09-03',sales='0')])
        self.assertFalse(m.prefix_scales(zero,'2020-10-01')['10']['supported'])

class HierarchicalWeightsAndTransfer(unittest.TestCase):
    def test_week_equal_groups_sources_and_group_exclusion_before_weights(self):
        m=load(self)
        frame=pd.DataFrame(dict(report_period=['w1']*5+['w2'],economic_group=['corn','soy_complex','soy_complex','soy_complex','upland_cotton','corn'],commodity_id=[10,14,14,15,27,10],sample_weight=[2.,1.,3.,4.,8.,1.],sourcevalid=[True]*6))
        w=m.source_group_weights(frame)
        np.testing.assert_allclose(w,[1/3,1/24,1/8,1/6,1/3,1.],rtol=0,atol=1e-14)
        wx=m.source_group_weights(frame,'soy_complex')
        np.testing.assert_allclose(wx,[.5,0,0,0,.5,1.],rtol=0,atol=1e-14)
        self.assertAlmostEqual(float(w.sum()),2.)

class NestedEquationsAndFallback(unittest.TestCase):
    def test_raw_interactions_scaling_normal_equations_and_bitwise_A(self):
        m=load(self)
        n=12;a=np.linspace(-1,2,n);phase=np.arange(n)/15.;q=np.linspace(-2,1,n)
        t=pd.DataFrame(dict(Ahat=a,phase=phase,Q=q,sourcevalid=[True]*n,sample_weight=np.ones(n),report_period=['w'+str(i//3) for i in range(n)],economic_group=['corn','soy_complex','upland_cotton']*4,commodity_id=[10,14,27]*4,net_R_stress=a+.4+q*.2))
        events=[];heads=m.fit_heads(t,'main','2020-01-01',on_fit=events.append)
        self.assertEqual(events,['B','C'])
        np.testing.assert_array_equal(heads['B']['feature_mean'],heads['C']['feature_mean'][:5])
        np.testing.assert_array_equal(heads['B']['feature_scale'],heads['C']['feature_scale'][:5])
        for arm,h in heads.items():
            beta=np.r_[h['intercept'],h['coef']];g=np.asarray(h['G']);rhs=np.asarray(h['rhs']);pen=np.diag([0.]+[1.]*(len(beta)-1))
            np.testing.assert_allclose((g+pen)@beta,rhs,rtol=0,atol=1e-12)
        p=t.iloc[:2].copy();p['sourcevalid']=[False,True];pred=m.predict(p,heads['C'])
        self.assertEqual(pred[0].view(np.uint64),a[0].view(np.uint64))
        excluded=m.fit_heads(t.loc[t.economic_group.ne('upland_cotton')],'transfer_corn','2020-01-01',excluded_group='corn')
        self.assertFalse(excluded['B']['supported'])
        sf=sources(m,[row('2020-09-03',sales='-10')]);mp=m.build_calendar_map(['2020-09-17'],sf)
        ff=pd.DataFrame(dict(family_id=['DCE.C','OTHER'],u_index=[0,0],u_date=['2020-09-17']*2,score=[0.,-0.]))
        features=m.feature_rows(ff,mp,{'10':dict(scale=10.,supported=True)},[dict(family_id='DCE.C',commodity_id=10,economic_group='corn')])
        self.assertEqual(features.sourcevalid.tolist(),[True,False]);self.assertAlmostEqual(features.Q.iloc[0],np.arcsinh(-1))
        self.assertEqual(features.weekly_group.tolist(),['2020-09-03']*2)

class UnknownAndWeeklyBootstrap(unittest.TestCase):
    def test_same_unknown_pair_is_zero_and_missing_weeks_stay_missing(self):
        m=load(self)
        values,known,sameunknown=m.paired_contribution(['x','x','','x'],['x','y','','z'],[np.nan,np.nan,0.,1.],[np.nan,2.,0.,np.nan])
        np.testing.assert_array_equal(known,[True,False,True,False]);self.assertEqual(values[0],0.)
        self.assertTrue(np.isnan(values[1]));self.assertEqual(sameunknown.tolist(),[True,False,False,False])
        ix=m.shared_bootstrap_indices(80);np.testing.assert_array_equal(ix,m.shared_bootstrap_indices(80))
        self.assertEqual(ix.shape,(2000,80));np.testing.assert_array_equal((ix[:,1:52]-ix[:,:51])%80,np.ones((2000,51),int))
        result=m.conditional_ci([1.,np.nan],m.shared_bootstrap_indices(2))
        self.assertEqual(result['known_groups'],1);self.assertEqual(result['missing_groups'],1);self.assertEqual(result['point'],1.)

if __name__=='__main__':unittest.main(verbosity=2)
