"""Four finite DAY-proxy behavior tests; no model or financial engine."""
import hashlib
import importlib.util
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest
from datetime import date,timedelta

import pandas as pd

SOURCE=Path(__file__).with_name('stage009_day_proxy_dataset.py')


def calendar(n=28):return [(date(2020,1,1)+timedelta(days=i)).isoformat() for i in range(n)]


def bar(epoch,day,**kw):
    ex,prod,month=epoch.split('.')
    result=dict(contract_epoch_id=epoch,exchange=ex,product=prod,contract_yyyymm=month,
        trade_date=day,open=100.,high=102.,low=98.,close=100.,volume=10.,quality_status='accepted')
    result.update(kw);return result


def opportunity(epoch,u,D,event='e1',status='observed_long_research_opportunity'):
    ex,prod,_=epoch.split('.')
    return dict(event_id=event,product_id=ex+'.'+prod,exchange=ex,product=prod,u_date=u,
        reference_epoch=epoch if status.startswith('observed') else '',planned_execution_date=D,status=status,direction='long')


class DayProxyDatasetTest(unittest.TestCase):
    def module(self):
        self.assertTrue(SOURCE.is_file(),'new DAY proxy dataset builder is not implemented')
        spec=importlib.util.spec_from_file_location('stage009_tested',SOURCE)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

    def test_same_epoch_21_bar_formulas_and_flat_location(self):
        m=self.module();cal=calendar();epoch='SHFE.CU.202005'
        rows=[bar(epoch,d) for d in cal[:22]]
        data,stats=m.build_dataset(pd.DataFrame([opportunity(epoch,cal[20],cal[21])]),cal,rows,scope_end=cal[-1])
        r=data.iloc[0];self.assertEqual(r.feature_ready,1);self.assertAlmostEqual(r.atr20,4.)
        expected=dict(r1_atr=0.,r5_atr=0.,r20_atr=0.,body_atr=0.,range_atr=1.,close_location=.5,
            gap_atr=0.,compression5_20=1.,log_volume_ratio20=0.,breakout20_atr=-.5,atr_pct=.04)
        for key,value in expected.items():self.assertAlmostEqual(r[key],value,places=12)
        varied=[bar(epoch,d,close=100.+i,open=99.+i,high=102.+i,low=98.+i,volume=10.+i) for i,d in enumerate(cal[:22])]
        v,_=m.build_dataset(pd.DataFrame([opportunity(epoch,cal[20],cal[21])]),cal,varied,scope_end=cal[-1])
        r=v.iloc[0];self.assertAlmostEqual(r.r1_atr,.25);self.assertAlmostEqual(r.r5_atr,5/(math.sqrt(5)*4))
        self.assertAlmostEqual(r.r20_atr,20/(math.sqrt(20)*4));self.assertAlmostEqual(r.log_volume_ratio20,math.log(30/19.5))
        flat=[bar(epoch,d,open=100.,high=100.,low=100.,close=100.) for d in cal[:22]]
        z,_=m.build_dataset(pd.DataFrame([opportunity(epoch,cal[20],cal[21])]),cal,flat,scope_end=cal[-1])
        self.assertEqual(z.iloc[0].feature_ready,0);self.assertEqual(z.iloc[0].history_state,'zero_or_nonfinite_atr')

    def test_DAY_interval_equality_budget_and_unknown_states(self):
        m=self.module();D='2020-02-03'
        cases=[(dict(open=100.,high=103.,low=99.,close=100.),(-1.,-1.,0)),
            (dict(open=100.,high=104.,low=100.,close=102.),(4.,4.,0)),
            (dict(open=100.,high=103.,low=100.,close=102.),(2.,2.,0)),
            (dict(open=100.,high=104.,low=99.,close=102.),(-1.,4.,1))]
        for prices,expected in cases:
            x=m.day_label(dict(prices,quality_status='accepted'),D=D,scope_end=D,atr20=4.)
            self.assertEqual(x['label_identified'],1);self.assertEqual(x['label_known_date'],D)
            self.assertEqual((x['gross_lower'],x['gross_upper'],x['path_ambiguous']),expected)
            self.assertAlmostEqual(x['proxy_lower'],expected[0]-.2);self.assertAlmostEqual(x['proxy_upper'],expected[1]-.2)
        for row,date_value,atr,state in [(None,D,4.,'missing_D'),(None,'2020-02-04',4.,'right_censored'),
            (dict(open=0,high=1,low=0,close=0,quality_status='accepted'),D,4.,'invalid_D_prices'),
            (dict(open=.1,high=.2,low=.05,close=.1,quality_status='accepted'),D,4.,'nonpositive_stop')]:
            x=m.day_label(row,D=date_value,scope_end=D,atr20=atr)
            self.assertEqual(x['label_state'],state);self.assertEqual(x['label_identified'],0)
            self.assertEqual(x['label_known_date'],'');self.assertIsNone(x['proxy_lower'])

    def test_market_lag_F_mean_own_family_exclusion_and_missing(self):
        m=self.module();cal=calendar(3)
        rows=[]
        for prod,r in [('L',100.),('L_F',300.),('CU',-1.),('AL',3.),('ZN',5.)]:
            ex='DCE' if prod.startswith('L') else 'SHFE'
            rows.append(dict(u_date=cal[0],family_id=ex+'.'+prod.removesuffix('_F'),feature_ready=1,r1_atr=r,label_identified=0))
        rows.append(dict(u_date=cal[0],family_id='DCE.BAD',feature_ready=0,r1_atr=99999.,label_identified=1))
        for family in ('DCE.L','SHFE.CU'):
            rows.append(dict(u_date=cal[1],family_id=family,feature_ready=1,r1_atr=-1e8,label_identified=0))
        frame=m.add_market_features(pd.DataFrame(rows),cal)
        l=frame.loc[(frame.u_date==cal[1])&(frame.family_id=='DCE.L')].iloc[0]
        self.assertAlmostEqual(l.market_lag_median_r1,3.);self.assertAlmostEqual(l.market_lag_breadth,2/3)
        self.assertAlmostEqual(l.market_lag_iqr_r1,3.);self.assertEqual(l.market_lag_missing,0)
        cu=frame.loc[(frame.u_date==cal[1])&(frame.family_id=='SHFE.CU')].iloc[0]
        self.assertAlmostEqual(cu.market_lag_median_r1,5.);self.assertAlmostEqual(cu.market_lag_iqr_r1,98.5)
        first=frame.iloc[0];self.assertEqual(first.market_lag_missing,1);self.assertEqual(first.market_lag_median_r1,0)
        altered=pd.DataFrame(rows);altered.loc[altered.u_date==cal[1],'r1_atr']=1e99
        other=m.add_market_features(altered,cal)
        self.assertEqual(frame.loc[frame.u_date==cal[1],m.MARKET_FEATURES].to_dict('records'),other.loc[other.u_date==cal[1],m.MARKET_FEATURES].to_dict('records'))

    def test_sqlite_prefix_missing_D_gap_epoch_and_all_rows_retained(self):
        m=self.module();cal=calendar(27);epoch='CZCE.SM.202501';other='CZCE.SM.201501'
        rows=[bar(epoch,d) for d in cal[:21]]+[bar(epoch,cal[22],open=110.,high=111.,low=109.,close=110.)]
        ops=pd.DataFrame([opportunity(epoch,cal[20],cal[21]),opportunity(epoch,cal[21],cal[22],event='e2',status='no_accepted_observation'),
            opportunity(epoch,cal[25],cal[26],event='e3',status='no_accepted_observation')])
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'fixture.sqlite'
            with sqlite3.connect(p) as db:
                db.execute('CREATE TABLE daily_bars('+','.join(k+' '+('REAL' if k in ('open','high','low','close','volume') else 'TEXT') for k in rows[0])+')')
                db.executemany('INSERT INTO daily_bars VALUES('+','.join('?' for _ in rows[0])+')',[tuple(r.values()) for r in rows])
            before=hashlib.sha256(p.read_bytes()).hexdigest()
            data,stats=m.build_from_sqlite(ops,cal,p,scope_end=cal[-1])
            self.assertEqual(len(data),3);self.assertEqual(data.iloc[0].feature_ready,1);self.assertEqual(data.iloc[0].label_state,'missing_D')
            self.assertEqual(data.iloc[1].history_state,'no_reference_observation');self.assertEqual(stats['sql_queries'],1)
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),before)
            future=rows+[bar(epoch,cal[24],volume=1e15,open=1e8,high=1e8,low=1e8,close=1e8)]
            changed,_=m.build_dataset(ops,cal,future,scope_end=cal[-1])
            for f in [*m.OWN_FEATURES,*m.MARKET_FEATURES,'feature_ready','label_state','proxy_lower','proxy_upper']:
                a,b=data.iloc[0][f],changed.iloc[0][f]
                self.assertTrue((pd.isna(a) and pd.isna(b)) or a==b,f)
            gap=[bar(epoch,d) for i,d in enumerate(cal[:22]) if i!=10]
            g,_=m.build_dataset(pd.DataFrame([opportunity(epoch,cal[21],cal[22])]),cal,gap,scope_end=cal[-1])
            self.assertEqual(g.iloc[0].feature_ready,0);self.assertEqual(g.iloc[0].history_state,'source_calendar_gap_rewarm')
            separated=[bar(other,d) for d in cal[:20]]+[bar(epoch,cal[20])]
            s,_=m.build_dataset(pd.DataFrame([opportunity(epoch,cal[20],cal[21])]),cal,separated,scope_end=cal[-1])
            self.assertEqual(s.iloc[0].feature_ready,0);self.assertEqual(s.iloc[0].history_state,'insufficient_same_epoch_history')


if __name__=='__main__':unittest.main()
