"""Six new605 behavior fixtures; no real labels/old suite/history."""
import unittest,math,copy
import stage607_wasde_report_residual as k

END='2026-10-16'
def source(month='2018-07',my='2018/19',x=0.):
 return dict(release_month=month,release_date=month+'-10',report_id='report-'+month,MY=my,x=x,eligible=True,reason='known_pair')
def row(action,u,y,known=None,**change):
 r=dict(action_id=action,sequence_index=action,mother_sequence_index='m'+action,mother_event_id='m'+action,product_id='DCE.C',family_id='DCE.C',reference_epoch='DCE.C.202009',u_date=u,u_index='0',u_action_eligible='1',label_state='closed_complete_bar_model',participation_state='bar_model_participation',net_R_stress=str(y),Ahat='0',label_known_date=known or u,sample_weight='123')
 r.update(change);return r
class ReportResidual605(unittest.TestCase):
 def test_release_DST_strict_MY_and_no_cross_month_carry(self):
  self.assertEqual(k.available('2020-03-06'),'2020-03-08T05:00:00+00:00')
  self.assertEqual(k.available('2020-03-07'),'2020-03-09T04:00:00+00:00')
  s=source('2020-03','2019/20');ss={'2020-03':s}
  self.assertFalse(k.source_for_u('2020-03-11',ss)['active'])
  self.assertTrue(k.source_for_u('2020-03-12',ss)['active'])
  self.assertFalse(k.source_for_u('2020-04-01',ss)['active'])
  self.assertTrue(k.training_MY_allowed('2018/19','2020-01-01'))
  self.assertFalse(k.training_MY_allowed('2019/20','2020-01-01'))
 def test_unequal_children_are_equal_u_then_equal_report_not_pooled_children(self):
  s=source();rows=[row('a','2018-07-13',0),row('b','2018-07-14',4),row('c','2018-07-14',4),row('d','2018-07-14',4)]
  reports,us=k.aggregate_reports(rows,{'2018-07':s},'2020-01-01',True,END)
  self.assertEqual(len(reports),1);self.assertEqual(reports[0]['target'],2.)
  self.assertEqual(reports[0]['known_child_rows'],4);self.assertEqual(reports[0]['known_u'],2)
 def test_calendar_centered_ridge_uses_report_sum1_not_allones(self):
  train=[dict(release_month=f'{y}-{m:02d}',MY=f'{y}/{str(y+1)[-2:]}',x=x,target=e) for y,m,x,e in [(2016,7,-1,1),(2017,7,1,3),(2016,8,-2,10),(2017,8,2,14)]]
  heads=k.fit_heads(train);self.assertEqual(heads['C']['status'],'supported')
  self.assertAlmostEqual(heads['C']['sigma'],math.sqrt(2.5));self.assertAlmostEqual(heads['C']['gamma'],math.sqrt(2.5)/2)
  scored=k.score_reports(train,heads)
  self.assertEqual([r['pred_B'] for r in scored],[2.,2.,12.,12.])
  for r,x in zip(scored,[-1,1,-2,2]):self.assertAlmostEqual(r['pred_C']-r['pred_B'],x/2)
  self.assertAlmostEqual(sum(r['loss_B'] for r in scored)/4,2.5);self.assertAlmostEqual(sum(r['loss_C'] for r in scored)/4,.625)
 def test_unseen_month_shared_A_and_zero_variance_is_unsupported(self):
  heads=dict(B=dict(status='supported',month_means={'07':2.}),C=dict(status='supported',month_centers={'07':0.},sigma=1.,gamma=1.))
  scores=k.score_reports([dict(release_month='2020-08',MY='2020/21',x=7.,target=3.)],heads)
  self.assertEqual(scores[0]['pred_B'],0.);self.assertEqual(scores[0]['pred_C'],0.);self.assertFalse(scores[0]['scored'])
  train=[dict(release_month=f'{y}-07',MY=f'{y}/{str(y+1)[-2:]}',x=1.,target=float(y)) for y in (2016,2017)]
  self.assertEqual(k.fit_heads(train)['C']['status'],'unsupported')
 def test_maturity_unknown_does_not_become_zero_and_boundary_MY_not_train(self):
  s=source('2020-07','2020/21');rows=[row('a','2020-07-13',2,END),row('b','2020-07-13',999,'2026-10-17'),row('c','2020-07-14',999,END,label_state='open_right_censored')]
  reports,us=k.aggregate_reports(rows,{'2020-07':s},'2020-01-01',False,END)
  self.assertEqual(len(reports),1);self.assertEqual(reports[0]['target'],2.);self.assertEqual(reports[0]['unknown_child_rows'],2)
  self.assertEqual(reports[0]['known_u'],1)
  reports,_=k.aggregate_reports([row('d','2019-07-13',5,'2019-08-01')],{'2019-07':source('2019-07','2019/20')},'2020-01-01',True,END)
  self.assertIsNone(reports[0]['target']);self.assertEqual(reports[0]['report_state'],'head_MY_boundary_excluded')
 def test_gate_checks_each_primary_MY_and_calendar_cycle_not_only_pooled_gain(self):
  ids=['2020/21','2021/22','2023/24','2024/25','2025/26'];rs=[]
  for i,my in enumerate(ids):rs.append(dict(MY=my,cutoff='2020-01-01' if i<2 else '2023-01-01',scored=True,loss_A=9.,loss_B=4.,loss_C=1.,delta_prediction=1.))
  heads={c:dict(C=dict(status='supported')) for c in ('2020-01-01','2023-01-01')}
  result=k.evaluate(rs,heads,True,END);self.assertTrue(result['gate']['passed'])
  self.assertEqual(result['descriptive_MY_bootstrap']['interval'],[3.,3.])
  rs[-1].update(loss_B=0.,loss_C=1.)
  self.assertFalse(k.evaluate(rs,heads,True,END)['gate']['passed'])
if __name__=='__main__':unittest.main()
