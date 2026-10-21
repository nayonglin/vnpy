"""Only synthetic Stage049 feature contracts; no native reads/fits/cash runs."""
import importlib.util
from pathlib import Path
import math
import unittest
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

core=load('stage042_synthetic_market_for049',HERE/'stage042_cross_session_experiment.py')
features=load('stage049_features_under_test',HERE/'stage049_maturity_features.py')

def fixture(extra_future=False):
    dates=pd.date_range('2020-12-01','2021-01-10' if extra_future else '2020-12-31').strftime('%Y-%m-%d').tolist()
    records=[]
    returns={'X.A.202101':-.01,'X.A.202102':0.,'X.A.202103':.01,'X.A.202104':0.,'X.A_F.202101':.4,'X.A_F.202102':-.4}
    for epoch,r in returns.items():
        for d in dates:
            c=100.*math.exp(r) if d=='2020-12-31' else 100.
            records.append(dict(contract_epoch_id=epoch,trade_date=d,open=100.,high=max(100.,c)+1.,low=min(100.,c)-1.,close=c,volume=10.,quality_status='accepted'))
    panel=pd.DataFrame([dict(event_id='e30',product_id='X.A',u_date='2020-12-31',reference_epoch='X.A.202104',status='observed_long_research_opportunity')])
    economics={e:dict(maturity_date='2020-01-01',known_lifecycle_exit_boundary='2020-01-01') for e in returns}
    return panel,records,dates,economics

class FeatureContracts(unittest.TestCase):
    def test_known_gradient_excludes_query_F_and_snapshot_expiry(self):
        # Catches query/F mixing, rolling-ATR substitution and static expiry pruning.
        panel,records,dates,econ=fixture()
        for bar in records:
            if bar['contract_epoch_id']=='X.A.202104' and bar['trade_date']=='2020-12-01':
                bar.update(high=120.,low=80.)
        frame,peers,summary=features.build_features(panel,core.Market.from_records(records,dates),dates,econ)
        self.assertEqual(len(frame),1)
        row=frame.iloc[0]
        self.assertEqual(row.peer_count,3)
        self.assertEqual(set(peers.peer_epoch),{'X.A.202101','X.A.202102','X.A.202103'})
        # Seed=(40+19*2)/20=3.9; eleven later TR=2. A rolling20 ATR is2.
        normalizer=(2.+1.9*(19./20.)**11)/100.
        self.assertAlmostEqual(row.normalizer,normalizer,places=13)
        # tau-day deviations (-30,1,29); numerator .59, denominator1742.
        self.assertAlmostEqual(row.q_aligned,215.35/1742./normalizer,places=11)
        self.assertAlmostEqual(row.tenor_span_years,59/365.,places=13)
        self.assertAlmostEqual(row.return_mean,0.,places=13)
        self.assertAlmostEqual(row.return_std,math.sqrt(.0002/3.),places=13)
        self.assertAlmostEqual(row.front_next_basis_u,.01,places=13)
        self.assertAlmostEqual(row.front_next_basis_prev,0.,places=13)
        self.assertAlmostEqual(row.front_next_tenor_span_years,31/365.,places=13)
        self.assertEqual(summary['module_native_queries'],0)
        # Reassigning query to the front month must not remove it from controls.
        panel['reference_epoch']='X.A.202101'
        front,_,_=features.build_features(panel,core.Market.from_records(records,dates),dates,econ)
        self.assertEqual(front.iloc[0].front_epoch,'X.A.202101')
        self.assertEqual(front.iloc[0].next_epoch,'X.A.202102')
        self.assertAlmostEqual(front.iloc[0].front_next_basis_u,.01,places=13)

    def test_hash_mapping_preserves_same_bag_and_replays_shuffled_q(self):
        # Catches altered value bags, forced derangement or unreplayable assignment.
        panel,records,dates,econ=fixture()
        frame,peers,_=features.build_features(panel,core.Market.from_records(records,dates),dates,econ)
        self.assertEqual(len(frame),1)
        self.assertEqual(peers.peer_epoch.tolist(),['X.A.202101','X.A.202102','X.A.202103'])
        self.assertEqual(peers.shuffle_rank.tolist(),[2,0,1])
        self.assertEqual(peers.shuffled_source_epoch.tolist(),['X.A.202102','X.A.202103','X.A.202101'])
        np.testing.assert_allclose(sorted(peers.log_return),sorted(peers.shuffled_log_return),atol=0.,rtol=0.)
        # Assigned r=(0,+.01,-.01), centered tau=(-30,1,29)/365.
        self.assertAlmostEqual(frame.iloc[0].q_shuffled,-102.2/34.84,places=11)
        self.assertEqual(frame.iloc[0].q_missing,0)
        self.assertFalse(any(c in peers.columns for c in ['open','high','low','close','volume']))

    def test_strict_previous_source_day_and_missing_rows_stay_unknown(self):
        # Catches last-available lookback and replacing missing q by numeric zero.
        panel,records,dates,econ=fixture()
        records=[r for r in records if not(r['contract_epoch_id']=='X.A.202103' and r['trade_date']=='2020-12-30')]
        panel=pd.concat([panel,pd.DataFrame([dict(event_id='absent',product_id='X.B',u_date='2020-12-31',reference_epoch='',status='no_accepted_observation')])],ignore_index=True)
        frame,peers,_=features.build_features(panel,core.Market.from_records(records,dates),dates,econ)
        self.assertEqual(len(frame),2)
        self.assertEqual(frame.event_id.tolist(),['e30','absent'])
        self.assertEqual(frame.q_missing.tolist(),[1,1])
        self.assertTrue(frame.q_aligned.isna().all())
        self.assertTrue(frame.q_shuffled.isna().all())
        self.assertEqual(frame.peer_count.tolist(),[2,0])
        self.assertEqual(set(peers.peer_epoch),{'X.A.202101','X.A.202102'})
        self.assertTrue(math.isnan(frame.iloc[1].normalizer))
        self.assertEqual(frame.iloc[1].front_next_missing,1)

    def test_future_prefix_and_future_liquidity_poison_do_not_change_features(self):
        # Catches lookahead membership, whole-life volume sorting or future normalization.
        panel,records,dates,econ=fixture(extra_future=True)
        whole,pwhole,_=features.build_features(panel,core.Market.from_records(records,dates),dates,econ)
        self.assertEqual(len(whole),1)
        past=[r for r in records if r['trade_date']<='2020-12-31'];past_dates=[d for d in dates if d<='2020-12-31']
        prefix,pprefix,_=features.build_features(panel,core.Market.from_records(past,past_dates),past_dates,econ)
        poisoned=[dict(r) for r in records]
        for r in poisoned:
            if r['trade_date']>'2020-12-31':r.update(open=9000.,high=9001.,low=8999.,close=9000.,volume=1e12)
        for d in dates:
            if d>'2020-12-31':poisoned.append(dict(contract_epoch_id='X.A.202105',trade_date=d,open=999.,high=1000.,low=998.,close=999.,volume=1e15,quality_status='accepted'))
        poison,ppoison,_=features.build_features(panel,core.Market.from_records(poisoned,dates),dates,econ)
        pd.testing.assert_frame_equal(whole,prefix,check_exact=True)
        pd.testing.assert_frame_equal(whole,poison,check_exact=True)
        pd.testing.assert_frame_equal(pwhole,pprefix,check_exact=True)
        pd.testing.assert_frame_equal(pwhole,ppoison,check_exact=True)

if __name__=='__main__':unittest.main()
