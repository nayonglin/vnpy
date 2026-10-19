"""Budget artifact acceptance is a read-only check of completed frozen fixtures."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

import pandas as pd

HERE=Path(__file__).resolve().parent
ENTRY=HERE/'stage044_validate_budget_artifacts.py'


class BudgetArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(ENTRY.exists(),'native budget artifact validator is not implemented')
        spec=importlib.util.spec_from_file_location('budget_artifact_fixture',HERE/'test_stage001_frozen_recap.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        self.fixture=mod.FrozenRecapTest(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.source=self.fixture.source;self.root=self.fixture.root
        import stage044_validate_budget_artifacts
        self.module=stage044_validate_budget_artifacts
        self.counter=0
        meta=pd.read_csv(self.source/'contract_metadata.csv');meta['product']='rb';meta['exchange']='SHFE';meta['pricetick']=1;meta['product_vt_symbol']='rb.SHFE'
        extra=pd.DataFrame([dict(vt_symbol=f'test{i}2201.SHFE',product=f'test{i}',exchange='SHFE',size=10,pricetick=1,product_vt_symbol=f'test{i}.SHFE') for i in range(92)])
        pd.concat([meta,extra],ignore_index=True).to_csv(self.source/'contract_metadata.csv',index=False)
        trades=pd.read_csv(self.source/'trades.csv');trades['signal']=['long_case2','','short_case3'];trades['commission']=0.;trades['slippage']=0.
        trades['signal_datetime']=['2018-01-02T00:00:00','2018-02-02T00:00:00','2019-01-02T00:00:00']
        trades['stage041_open_budget']=[20.,None,20.];trades['stage041_entry_risk']=[20.,None,20.]
        snapshots=[];audits=[]
        for row in trades.itertuples(index=False):
            if row.offset!='open':snapshots.append('{}');continue
            snapshot=dict(snapshot_id='signal-'+row.trade_id,contract_vt_symbol=row.vt_symbol,product_vt_symbol='rb.SHFE',direction=row.direction,signal=row.signal,signal_datetime=row.signal_datetime,entry_context='flat_entry',risk_mode='regular',target_risk_amount=20.,risk_per_contract=20.,stop_price=row.price-2 if row.direction=='long' else row.price+2,risk_ratio=.01,risk_multiplier=1.,portfolio_overheat_cooldown_scale=1.,directional_30d_risk_boost_multiplier=1.,limited_balance=1000000.,min_risk_per_trade=20.,max_risk_per_trade=20.,effective_capital_usage_ratio=1.,sizing_equity=1000000.)
            encoded=json.dumps(snapshot,sort_keys=True);snapshots.append(encoded)
            audits.append(dict(date=row.date,order_id='order-'+row.trade_id,vt_symbol=row.vt_symbol,direction=row.direction,volume=1,signal_snapshot=encoded,allowed=True,filled=True,trade_id=row.trade_id,one_lot_risk=20.,opening_budget=20.,opening_equity=1000000.,reserved_margin=0.,open_price=row.price,stop_price=snapshot['stop_price'],size=10,pricetick=1,reason=''))
        trades['stage041_signal_snapshot']=snapshots;trades.to_csv(self.source/'trades.csv',index=False)
        pd.DataFrame(audits).to_csv(self.source/'open_budget_audit.csv',index=False)
        pd.DataFrame([dict(vt_symbol='rb1901.SHFE',direction='long',entry_trade_id='o1',exit_trade_id='c1',entry_date='2018-01-03',exit_date='2018-02-05',entry_price=100.,exit_price=110.,gross_pnl=100.,cost=0.,net_pnl=100.,signal='long_case2')]).to_csv(self.source/'closed_episodes.csv',index=False)
        pd.DataFrame([dict(vt_symbol=vt,deadline='2021-01-29') for vt in pd.concat([meta,extra]).vt_symbol]).to_csv(self.source/'lifecycle_deadlines.csv',index=False)
        (self.source/'residual_open_positions.json').write_text(json.dumps([dict(vt_symbol='rb1901.SHFE',direction='short',volume=1)]))
        metrics=json.loads((self.source/'summary.json').read_text())
        metrics.update(completed_episodes=1,residual_open_positions=1,position_count_limit_removed=True,performance_certifiable=True,native_risk_budget_restored=True,one_lot_is_maximum_not_fixed=True,next_open_risk_recheck=True,actual_open_budget_violations=0,open_budget_checks=2,open_budget_rejections=0,max_actual_products=1,analysis_end='2020-12-31',last_fill_date='2019-01-03',universe_product_count=93,mode='daily-proxy',boundaries=['供需过滤按研究授权停用。'])
        (self.source/'summary.json').write_text(json.dumps(metrics))
        self.rebuild()

    def rebuild(self,parameters=None):
        self.fixture.freeze();manifest=json.loads((self.source/'manifest.json').read_text())
        manifest['parameters'].update(fixed_size=0,min_position_size=1,max_position_size=1,max_concurrent_positions=93)
        manifest['parameters'].update(parameters or {})
        for key in ('native_risk_budget_restored','one_lot_is_maximum_not_fixed','next_open_risk_recheck','position_count_limit_removed'):manifest[key]=True
        (self.source/'manifest.json').write_text(json.dumps(manifest))
        self.counter+=1;self.recap=self.root/f'recap-{self.counter}'
        self.fixture.module.render_bundle(self.source,self.recap)

    def test_full_fixture_passes_without_forcing_actual_products_above_four(self):
        result=self.module.validate(self.source,self.recap)
        self.assertEqual(result['episodes'],1)
        self.assertEqual(result['actual_opens_budget_checked'],2)
        self.assertEqual(result['actual_open_budget_violations'],0)
        self.assertEqual(result['max_actual_products'],1)
        self.assertEqual(result['configured_product_capacity'],93)
        self.assertTrue(result['javascript_syntax_checked'])
        self.assertGreater(result['ma_points_independently_checked'],0)

    def test_oversized_actual_open_fails_even_if_summary_says_zero_violations(self):
        trades=pd.read_csv(self.source/'trades.csv');trades.loc[trades.trade_id.eq('o1'),'stage041_entry_risk']=21.
        trades.to_csv(self.source/'trades.csv',index=False);self.rebuild()
        with self.assertRaisesRegex(ValueError,'budget'):
            self.module.validate(self.source,self.recap)

    def test_source_capacity_must_be_exactly_ninety_three(self):
        self.rebuild(parameters={'max_concurrent_positions':4})
        with self.assertRaisesRegex(ValueError,'capacity'):
            self.module.validate(self.source,self.recap)

    def test_audit_must_bind_every_actual_open_to_the_same_signal_snapshot(self):
        audit=pd.read_csv(self.source/'open_budget_audit.csv');audit.loc[0,'signal_snapshot']='{}'
        audit.to_csv(self.source/'open_budget_audit.csv',index=False);self.rebuild()
        with self.assertRaisesRegex(ValueError,'snapshot'):
            self.module.validate(self.source,self.recap)

    def test_two_actual_open_lots_for_one_product_are_rejected(self):
        trades=pd.read_csv(self.source/'trades.csv')
        extra=trades.iloc[0].copy();extra['trade_id']='o3';extra['date']='2018-01-04';extra['datetime']='2018-01-04 09:00:00'
        trades=pd.concat([trades.iloc[:1],extra.to_frame().T,trades.iloc[1:]],ignore_index=True)
        trades.to_csv(self.source/'trades.csv',index=False)
        metrics=json.loads((self.source/'summary.json').read_text());metrics['total_trade_count']=4
        (self.source/'summary.json').write_text(json.dumps(metrics));self.rebuild()
        with self.assertRaisesRegex(ValueError,'one_lot_position'):
            self.module.validate(self.source,self.recap)

    def test_hash_closed_chart_with_wrong_MA_is_rejected(self):
        records=json.loads((self.recap/'records.json').read_text())
        records[0]['daily']['ma5'][-1]+=1
        payload=json.dumps(records,ensure_ascii=False,separators=(',',':'))
        (self.recap/'records.json').write_text(payload)
        page=(self.recap/'index.html').read_text();prefix,tail=page.split('const records=',1)
        _,end=json.JSONDecoder().raw_decode(tail)
        (self.recap/'index.html').write_text(prefix+'const records='+payload+tail[end:])
        summary=json.loads((self.recap/'summary.json').read_text())
        for name in ('records.json','index.html'):summary['artifact_sha256'][name]=self.fixture.module.sha256(self.recap/name)
        (self.recap/'summary.json').write_text(json.dumps(summary))
        with self.assertRaisesRegex(ValueError,'MA_mismatch'):
            self.module.validate(self.source,self.recap)

    def test_manifest_values_must_match_source_and_record_not_just_ids(self):
        path=self.recap/'chart_manifest.csv';frame=pd.read_csv(path);frame.loc[0,'entry_price']=99.
        frame.to_csv(path,index=False)
        summary=json.loads((self.recap/'summary.json').read_text());summary['artifact_sha256']['chart_manifest.csv']=self.fixture.module.sha256(path)
        (self.recap/'summary.json').write_text(json.dumps(summary))
        with self.assertRaisesRegex(ValueError,'manifest'):
            self.module.validate(self.source,self.recap)

    def set_precise_signal_budget(self,*,exceed=False):
        target=32146.359636085206
        budget=math.nextafter(target,math.inf) if exceed else target
        trades=pd.read_csv(self.source/'trades.csv',float_precision='round_trip')
        audit=pd.read_csv(self.source/'open_budget_audit.csv',float_precision='round_trip')
        for index,row in trades[trades.offset.eq('open')].iterrows():
            snapshot=json.loads(row.stage041_signal_snapshot)
            snapshot.update(target_risk_amount=target,min_risk_per_trade=target,max_risk_per_trade=target)
            encoded=json.dumps(snapshot,sort_keys=True)
            trades.loc[index,'stage041_open_budget']=budget;trades.loc[index,'stage041_signal_snapshot']=encoded
            audit.loc[audit.trade_id.eq(row.trade_id),'opening_budget']=budget
            audit.loc[audit.trade_id.eq(row.trade_id),'signal_snapshot']=encoded
        trades.to_csv(self.source/'trades.csv',index=False);audit.to_csv(self.source/'open_budget_audit.csv',index=False)
        self.rebuild();return target

    def test_seventeen_digit_frozen_csv_is_parsed_exactly_like_json(self):
        target=self.set_precise_signal_budget()
        self.assertTrue(hasattr(self.module,'read_frozen_csv'),'missing exact frozen CSV reader')
        trades=self.module.read_frozen_csv(self.source/'trades.csv')
        self.assertEqual(trades.iloc[0].stage041_open_budget,target)
        result=self.module.validate(self.source,self.recap)
        self.assertEqual(result['actual_open_budget_violations'],0)

    def test_genuinely_one_ulp_above_signal_budget_is_still_rejected(self):
        self.set_precise_signal_budget(exceed=True)
        with self.assertRaisesRegex(ValueError,'budget'):
            self.module.validate(self.source,self.recap)

    def test_hash_closed_page_with_invalid_javascript_is_rejected(self):
        path=self.recap/'index.html';path.write_text(path.read_text()+'<script>const = ;</script>')
        summary=json.loads((self.recap/'summary.json').read_text());summary['artifact_sha256']['index.html']=self.fixture.module.sha256(path)
        (self.recap/'summary.json').write_text(json.dumps(summary))
        with self.assertRaisesRegex(ValueError,'JavaScript'):
            self.module.validate(self.source,self.recap)


if __name__=='__main__':unittest.main()
