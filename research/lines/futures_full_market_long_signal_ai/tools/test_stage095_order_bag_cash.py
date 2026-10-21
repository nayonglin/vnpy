"""Only new ORDER/BAG adapter/paired-gate fixtures; no native data or actual account."""
import importlib.util
from pathlib import Path
import unittest
import json
import tempfile
import numpy as np
import pandas as pd

PATH=Path(__file__).with_name('stage095_order_bag_cash.py')


def module():
    if not PATH.exists():return None
    s=importlib.util.spec_from_file_location('test095_target',PATH);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


class NewCashBehavior(unittest.TestCase):
    def setUp(self):
        self.m=module();self.assertIsNotNone(self.m,'Stage095 implementation is missing')

    def test_main_only_full_mother_unknown_and_missing_never_gate(self):
        rows=[]
        for i in range(2):
            rows.append(dict(event_id='e'+str(i),product_id='P.X',family_id='P.X',u_date='2020-01-0'+str(i+1),u_index=i,
                reference_epoch='P.X2001',label_history_ready20=1,N_u=1.,low20_u=90.,u_close=100.,history_run=20,lifecycle_index=99,
                label_state='open_right_censored'))
        labels=pd.DataFrame(rows);pred=labels[['event_id','product_id','family_id','u_date','u_index','reference_epoch']].copy()
        pred['scope']='main';pred['policy']='NARROW';pred['arm']='ORDER';pred['cutoff']='2020-01-01'
        pred['score']=[1.,-1.];pred['history_ready20']=1;pred['selected']=[1,0];pred['sequence_missing']=1
        signals=self.m.make_signals(labels,pred,'ORDER')
        self.assertEqual(len(signals),2);self.assertEqual(signals.potential.tolist(),[1,0])
        bad=pred.copy();bad['scope']='holdout_0'
        with self.assertRaisesRegex(ValueError,'main'):
            self.m.make_signals(labels,bad,'ORDER')

    def good_points(self):
        return [dict(window=w,cost=c,return_percentage_point_difference=1.,
            drawdown_percentage_point_difference=0.,ci95_low=.001,
            active_total_return_pct=1.,reference_total_return_pct=0.,
            identification='observed_cash_comparison')
            for w in ('primary_2020','cold_2023') for c in ('base','stress')]

    def good_held(self):
        return {'groups':{g:{'nominal_pass':True,'status':'supported',
            'unknown_differential_selected_events':0} for g in ('holdout_0','holdout_1')}}

    def test_nominal_relative_win_does_not_pass_when_order_still_loses(self):
        points=self.good_points(); held=self.good_held()
        self.assertEqual(self.m.continuation_gate(points,held,False)['status'],'supported_research_model_only')
        for value in (-1.,0.,float('nan')):
            bad=[dict(p) for p in points];bad[0]['active_total_return_pct']=value
            gate=self.m.continuation_gate(bad,held,False)
            self.assertFalse(gate['ORDER_own_returns_positive_in_all_four'])
            self.assertFalse(gate['cash_nominal_pass'])
            self.assertEqual(gate['status'],'unsupported')

    def test_all_four_new_contrast_windows_and_held_unknown_are_distinct(self):
        points=self.good_points();held=self.good_held()
        bad=[dict(p) for p in points];bad[-1]['drawdown_percentage_point_difference']=-.01
        self.assertEqual(self.m.continuation_gate(bad,held,False)['status'],'unsupported')
        self.assertEqual(self.m.continuation_gate(points,held,True)['status'],'unknown_historical_stale')
        held['groups']['holdout_0']['status']='unknown'
        held['groups']['holdout_0']['unknown_differential_selected_events']=1
        self.assertEqual(self.m.continuation_gate(points,held,False)['status'],'unknown_differential_held_outcome')
        with self.assertRaisesRegex(ValueError,'four'):
            self.m.continuation_gate(points[:-1],held,False)

    def test_empty_reference_dd_not_automatic_pass(self):
        pts=[dict(window=w,cost=c,active_total_return_pct=1.,return_percentage_point_difference=1.,drawdown_percentage_point_difference=None,ci95_low=.1,identification='observed_cash_comparison') for w in ('primary_2020','cold_2023') for c in ('base','stress')]
        h={'groups':{g:{'nominal_pass':True,'status':'supported','unknown_differential_selected_events':0} for g in ('holdout_0','holdout_1')}}
        self.assertEqual(self.m.continuation_gate(pts,h,False)['status'],'unknown_empty_reference_DD')

    def test_bootstrap_rejects_wrong_calendar_width_before_statistics(self):
        a=pd.DataFrame(dict(date=['2020-01-01','2020-01-02'],equity=[1000001.,1000002.],ever_insolvent=[False,False]))
        with self.assertRaisesRegex(ValueError,'index'):
            self.m.paired_statistics(a,a,np.array([[0,1,2]]))

    def test_missing_mismatch_rejected_without_future_label_filter(self):
        rows=[]
        for arm in ('BAG','ORDER'):
            for i in range(2):
                rows.append(dict(event_id='e'+str(i),arm=arm,sequence_missing=i))
        pred=pd.DataFrame(rows)
        self.m.validate_shared_missing(pred)
        pred.loc[(pred.arm=='ORDER')&(pred.event_id=='e0'),'sequence_missing']=1
        with self.assertRaisesRegex(ValueError,'shared'):
            self.m.validate_shared_missing(pred)

    def test_unfilled_signal_label_uncertainty_does_not_invent_cash_exposure(self):
        pts=[dict(window=w,cost=c,active_total_return_pct=1.,return_percentage_point_difference=1.,drawdown_percentage_point_difference=0.,ci95_low=.1,identification='observed_cash_comparison') for w in ('primary_2020','cold_2023') for c in ('base','stress')]
        held={'groups':{g:{'nominal_pass':True,'status':'supported','unknown_differential_selected_events':0} for g in ('holdout_0','holdout_1')}}
        gate=self.m.continuation_gate(pts,held,False,signal_unknown_main=True)
        self.assertEqual(gate['status'],'supported_research_model_only')
        self.assertTrue(gate['signal_unknown_main'])
        pts[1]['ci95_low']=0.
        self.assertEqual(self.m.continuation_gate(pts,held,False,signal_unknown_main=True)['status'],'unsupported')

    def test_authorization_rejection_does_not_create_output(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'not-created';protocol=Path(d)/'protocol.json';protocol.write_text('{}')
            auth=Path(d)/'auth.json';auth.write_text('{}')
            args=SimpleNamespace(protocol=str(protocol),protocol_sha256='0'*64,authorization=str(auth),output=str(output))
            with self.assertRaisesRegex(ValueError,'protocol'):
                self.m.authorize(args)
            self.assertFalse(output.exists())

    def test_known_nonparticipation_is_separate_from_unknown_signal_outcomes(self):
        labels=pd.DataFrame(dict(event_id=['cancel','open'],family_id=['P.X','P.X'],
            u_date=['2020-01-01','2020-01-02'],label_state=['known_nonparticipation','open_right_censored'],
            label_known_date=['',''],net_R_stress=[np.nan,np.nan]))
        predictions=pd.DataFrame(dict(event_id=['cancel','open','cancel','open'],
            arm=['BAG','BAG','ORDER','ORDER'],selected=[0,0,1,1]))
        report,states=self.m.main_signal_diagnostics(labels,predictions,'2026-10-16')
        self.assertEqual(report['unknown_differential_selected_events'],1)
        self.assertEqual(report['known_nonparticipation_differential_selected_events'],1)
        self.assertEqual(int(states.action_disagreements.sum()),2)

    def test_fit_terminal_rejects_thirteenth_attempt_even_when_twelve_complete(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            def bound(name,obj):
                file=path/name;file.write_text(json.dumps(obj));return self.m.ref.file_binding(file)
            scalar=dict(path='fixture',bytes=1,sha256='0'*64)
            narrow_terminal=bound('narrow_terminal.json',dict(status='completed',exit_code=0,
                completed_label_rows=399252,native_source_queries=1,new_cash_accounts=0))
            fit_terminal=bound('fit_terminal.json',dict(status='completed',exit_code=0,
                actual_fit_calls_attempted=13,actual_fit_calls_completed=12,native_source_queries=0,cash_replays=0))
            inputs={role:dict(scalar) for role in ('narrow_labels','narrow_manifest','market_protocol','predictions_main','held_diagnostic')}
            narrow=dict(schema='stage070_narrow_labels_v1',status='completed',mode='actual',mother_rows=399252,
                protocol={'sha256':self.m.kernel.PROTOCOL_SHA},labels_narrow=scalar,input_bindings={'market_protocol':scalar},terminal=narrow_terminal)
            fit=dict(schema='stage094_crossday_order_fit_v1',status='completed',mode='actual',protocol={'sha256':self.m.PROTOCOL_SHA},
                protocol_sha256=self.m.PROTOCOL_SHA,actual_fit_calls_completed=12,native_source_queries=0,cash_replays=0,
                prediction_rows=644056,predictions_main=scalar,held_diagnostic=scalar,
                input_bindings={'narrow_labels':scalar,'narrow_manifest':scalar},terminal=fit_terminal)
            with self.assertRaisesRegex(ValueError,'terminal'):
                self.m.validate_cash_manifests(narrow,fit,inputs)


if __name__=='__main__':unittest.main()
