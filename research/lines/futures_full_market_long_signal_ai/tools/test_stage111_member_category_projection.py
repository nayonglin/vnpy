"""Only new category/scope/lag semantics; all source tables are synthetic."""
import importlib.util
from pathlib import Path
import unittest
import copy
import pandas as pd

SOURCE=Path(__file__).with_name('stage111_member_category_projection.py')
def load():
    if not SOURCE.exists():return None
    s=importlib.util.spec_from_file_location('test111',SOURCE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def row(instrument,role,L,S,label=None,rank=None):
    text=label or ('期货公司' if role=='FC' else '非期货公司')
    return dict(INSTRUMENTID=instrument,RANK=(-1 if role=='FC' else 0) if rank is None else rank,
        PARTICIPANTABBR1=text,PARTICIPANTABBR2=text,PARTICIPANTABBR3=text,CJ2=L,CJ3=S,CJ2_CHG=None)
def pair(instrument,LN=8,SN=2,LF=12,SF=18):return [row(instrument,'FC',LF,SF),row(instrument,'NFC',LN,SN)]
def report(rows):return dict(report_date='20200102',o_cursor=rows)

class CategoryProjection(unittest.TestCase):
    def setUp(self):self.m=load();self.assertIsNotNone(self.m,'Stage111 source missing')
    def test_old_contract_inventory_sum_four_quantities_then_one_ratio(self):
        rows=pair('cu2001')+pair('cu2002',LN=2,SN=8,LF=18,SF=12)
        rows.append(dict(INSTRUMENTID='cu2003',RANK=1,PARTICIPANTABBR1='某期货公司会员',PARTICIPANTABBR2='某期货公司会员',PARTICIPANTABBR3='某期货公司会员'))
        p=self.m.project_report('20200102',report(rows));self.assertEqual(p['cu']['missing_reason'],'incomplete_or_conflicting_contract_scope')
        rows+=pair('cu2003',LN=4,SN=0,LF=2,SF=6)
        p=self.m.project_report('20200102',report(rows))['cu']
        self.assertEqual(p['observed'],1);self.assertEqual(p['scope'],'reported_actual_contract_set')
        self.assertEqual([p[k] for k in ['LN','SN','LF','SF']],[14,10,32,36]);self.assertAlmostEqual(p['scalar'],4/92)
        self.assertEqual(p['population_version'],'domestic_members')
    def test_missing_one_contract_pair_does_not_use_remaining_subset(self):
        p=self.m.project_report('20200102',report(pair('au2006')+[row('au2012','NFC',1,1)]))['au']
        self.assertEqual(p['observed'],0);self.assertIsNone(p['scalar'])
    def test_all_priority_no_double_count_and_no_fallback_when_incomplete(self):
        rows=pair('auall',LN=0,SN=0,LF=10,SF=10)+pair('au2006')
        p=self.m.project_report('20200102',report(rows))['au'];self.assertEqual(p['scalar'],0.)
        self.assertEqual(p['scope'],'product_all');self.assertEqual(p['LN'],0)
        q=self.m.project_report('20200102',report([row('auall','FC',10,10)]+pair('au2006')))['au']
        self.assertEqual(q['observed'],0);self.assertEqual(q['missing_reason'],'incomplete_or_conflicting_all_scope')
    def test_true_gross_zero_is_observed_but_missing_quantity_is_not_zero(self):
        p=self.m.project_report('20200102',report(pair('agall',0,0,0,0)))['ag'];self.assertEqual((p['observed'],p['scalar']),(1,0.))
        q=pair('agall',0,0,0,0);q[1]['CJ2']=None
        self.assertEqual(self.m.project_report('20200102',report(q))['ag']['observed'],0)
    def test_unknown_label_rank_or_report_date_stays_missing(self):
        new=pair('cuall')
        for r,text in zip(new,['期货公司会员/境外特殊经纪参与者','非期货公司会员/境外特殊非经纪参与者']):
            for j in (1,2,3):r['PARTICIPANTABBR'+str(j)]=text
        self.assertEqual(self.m.project_report('20200102',report(new))['cu']['population_version'],'members_and_overseas_special_participants')
        for change in ('label','rank','clock'):
            r=pair('cualL');o=report(r)
            if change=='label':r[1]['PARTICIPANTABBR2']='未知类别'
            if change=='rank':r[1]['RANK']=1
            if change=='clock':o['report_date']='20200103'
            p=self.m.project_report('20200102',o)['cu'];self.assertEqual(p['observed'],0);self.assertIsNone(p['scalar'])
    def test_strict_calendar_lag_missing_day_no_ffill_and_exact_SHFE_mapping(self):
        rows=[]
        for i,(day,product) in enumerate([('2020-01-02','SHFE.CU'),('2020-01-03','SHFE.CU'),('2020-01-06','SHFE.CU'),('2020-01-06','SHFE.CU_F'),('2020-01-06','DCE.CU')]):
            rows.append(dict(sequence_index=i,event_id='e'+str(i),product_id=product,family_id=product,u_date=day,u_index=i,reference_epoch=''))
        mother=pd.DataFrame(rows);days={'20200102':self.m.project_report('20200102',report(pair('cuall')))}
        p=self.m.project_mother(mother,days,{'20200102':{'status':'http_200'}})
        self.assertEqual(p.event_id.tolist(),mother.event_id.tolist());self.assertEqual(p.external_observed.tolist(),[0,1,0,0,0])
        self.assertEqual(p.loc[2,'v_date'],'2020-01-03');self.assertEqual(p.loc[2,'missing_reason'],'source_date_unavailable')

class SourceInterruptionAccounting(unittest.TestCase):
    def setUp(self):
        self.m=load()
        self.completion=dict(new_get_started=3575,new_get_finished=3573,recovery=dict(
            schema='stage116_interrupted_source_recovery_v1',interrupted_dates=['20231213','20231214'],
            interrupted_request_count=2,complete_terminal_statuses=3588,prior_finished=2893,
            resumed_started=680,resumed_finished=680))
        self.records=[dict(date=d,status='interrupted_unknown') for d in ['20231213','20231214']]
        self.receipt=copy.deepcopy(self.completion['recovery'])
    def test_two_interrupted_requests_remain_missing_without_fake_finishes(self):
        self.assertTrue(hasattr(self.m,'source_request_accounting_valid'),'honest interruption accounting is not supported')
        self.assertTrue(self.m.source_request_accounting_valid(self.completion,self.records,self.receipt))
        self.assertEqual(self.completion['new_get_finished'],3573)
    def test_disguised_success_or_dropped_unknown_date_is_rejected(self):
        self.assertTrue(hasattr(self.m,'source_request_accounting_valid'),'honest interruption accounting is not supported')
        for change in ('success','drop','finish','receipt'):
            c=copy.deepcopy(self.completion);r=copy.deepcopy(self.records);receipt=copy.deepcopy(self.receipt)
            if change=='success':r[0]['status']='http_200'
            if change=='drop':r.pop()
            if change=='finish':c['new_get_finished']=3575
            if change=='receipt':receipt['interrupted_dates']=['20231212','20231214']
            self.assertFalse(self.m.source_request_accounting_valid(c,r,receipt),change)
    def test_original_complete_source_still_valid(self):
        self.assertTrue(hasattr(self.m,'source_request_accounting_valid'),'honest interruption accounting is not supported')
        self.assertTrue(self.m.source_request_accounting_valid(dict(new_get_started=3575,new_get_finished=3575),[],None))

if __name__=='__main__':unittest.main()
