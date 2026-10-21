"""One new integration group using real342/339/325, synthetic bars only."""
from copy import deepcopy
from datetime import date,timedelta,datetime,timezone
import importlib.util
from pathlib import Path
import tempfile
import unittest

TOOLS=Path(__file__).resolve().parent
def load(name):
    spec=importlib.util.spec_from_file_location('tiny357_'+name,TOOLS/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


class DailyComposeTiny(unittest.TestCase):
    def test_exact_float_checkpoint_dual_domains_clock_and_unfunded_observe(self):
        m=load('stage357_daily_collect_compose');caller=load('stage325_forward_caller');core=caller._components().core
        dates=[];d=date(2026,9,1)
        while d<=date(2026,10,21):
            if d.weekday()<5:dates.append(d.isoformat())
            d+=timedelta(days=1)
        previous=dates.index('2026-10-19');u=previous+1
        a,b,q='DCE.P.202703','DCE.P.202705','DCE.Q.202703'
        symbols={a:'DCE.p2703',b:'DCE.p2705',q:'DCE.q2703'}
        values=dict(open=100.,high=101.,low=99.,close=100.,volume=10000.,close_oi=10.)
        w=core.WilderState()
        for j in range(previous+1):w.append(j,dict(values,quality_status='accepted'))
        states={a:w.to_dict(),q:w.to_dict()}
        inventory=[dict(epoch=e,product_id=e.rsplit('.',1)[0],rows=previous+1,last_index=previous,
            last_date='2026-10-19',has_current_bar=True) for e in states]
        inventory.append(dict(epoch=b,product_id='DCE.P',rows=2,last_index=previous-2,
            last_date=dates[previous-2],has_current_bar=False))
        products=['DCE.P','DCE.P_F','DCE.Q','DCE.Q_F','DCE.R','DCE.R_F','DCE.S']+['DCE.X'+str(i).zfill(3) for i in range(91)]
        economics={a:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,
            round_lot=1.,tick_size=None,vendor_margin_rate=.2,listed_date='2020-01-01')}
        def raw(day,v):
            ns=int(datetime.fromisoformat(day+'T00:00:00+08:00').timestamp())*10**9
            return dict(row_index=0,raw_ns=None,timestamp_state='timestamp_unknown',raw_datetime_type='float64',
                raw_datetime_literal=repr(float(ns)),values=dict(v,datetime=float(ns)))
        raw_items={symbols[a]:dict(symbol=symbols[a],source_version='tqsdk/synthetic',fresh_ready=True,
            dtypes={'datetime':'float64'},rows=[raw('2026-10-19',values),raw('2026-10-20',dict(values,high=105.,close=104.)),
            raw('2026-10-21',dict(values,high=100000.,close=99999.))],
            receipt=dict(recorded_at='2026-10-20T08:00:00+00:00',entry_hash='synthetic-a'),raw={'sha256':'a'}),
            symbols[b]:dict(symbol=symbols[b],source_version='tqsdk/synthetic',fresh_ready=True,
                dtypes={'datetime':'float64'},rows=[raw('2026-10-20',values)],
                receipt=dict(recorded_at='2026-10-20T08:00:00+00:00',entry_hash='synthetic-b'),raw={'sha256':'b'}),
            symbols[q]:dict(symbol=symbols[q],source_version='tqsdk/synthetic',fresh_ready=True,
                dtypes={'datetime':'float64'},rows=[raw('2026-10-20',values)],
                receipt=dict(recorded_at='2026-10-20T08:00:00+00:00',entry_hash='synthetic-q'),raw={'sha256':'q'})}
        overlay=[dict(contract_epoch_id=a,trade_date='2026-10-19',native_values=dict(values,symbol=symbols[a]),
                      canonical_values=values,units_status='canonical_normalized')]
        sessions=[]
        for symbol in symbols.values():
            sessions.extend([dict(symbol=symbol,trade_date='2026-10-20',state='operational_regular_schedule',
                session_end='2026-10-20T15:15:00+08:00'),dict(symbol=symbol,trade_date='2026-10-21',
                state='operational_regular_schedule',first_open='2026-10-20T21:00:00+08:00')])
        kwargs=dict(warmup_states=states,epoch_inventory=inventory,dates=dates,calendar={v:True for v in dates},
            identity_map={v:k for k,v in symbols.items()},products=products,economics=economics,
            prior_overlay=overlay,sessions=sessions,clock_contract=m.CLOCK_CONTRACT,source_receipt={'synthetic':True},core=core)
        before=deepcopy((states,inventory,raw_items,overlay))
        composed=m.compose_snapshot(raw_items,**kwargs);snap=composed['snapshot']
        self.assertEqual((states,inventory,raw_items,overlay),before)
        self.assertEqual(snap['incremental_audit']['appended_rows'],2)
        self.assertAlmostEqual(snap['warmup_state'][a]['N'],2.2,places=14)
        self.assertEqual(snap['warmup_state'][b]['run'],1)
        self.assertIsNone(snap['market'].bar(q,u));self.assertEqual(snap['warmup_state'][q],states[q])
        domains=composed['clock_domains']
        self.assertEqual(set(domains['input_completion']['epochs']),{a,b})
        self.assertEqual(domains['execution_deadline']['epochs'],[a])
        self.assertEqual(snap['clock']['source_completed_at'],'2026-10-20T15:15:00+08:00')
        self.assertEqual(snap['clock']['D_open_at'],'2026-10-20T21:00:00+08:00')
        self.assertTrue(any(r['reason']=='units_unconfirmed_product' for r in composed['normalization_audit']['rejections']))
        missing=deepcopy(sessions)
        next(r for r in missing if r['symbol']==symbols[b] and r['trade_date']=='2026-10-20')['state']='unknown'
        unknown=m.compose_snapshot(raw_items,**dict(kwargs,sessions=missing))
        self.assertIsNone(unknown['snapshot']['clock']['source_completed_at'])
        self.assertEqual(unknown['snapshot']['clock']['D_open_at'],snap['clock']['D_open_at'])
        unresolved=m.compose_snapshot(raw_items,**dict(kwargs,economics={}))
        self.assertIn(a,unresolved['clock_domains']['execution_deadline']['eligibility_unknown_epochs'])
        conflict=deepcopy(raw_items);conflict[symbols[a]]['rows'][0]['values']['volume']+=1
        quarantined=m.compose_snapshot(conflict,**kwargs)
        self.assertEqual(quarantined['normalization_audit']['overlap_conflicts'],[symbols[a]])
        self.assertIsNone(quarantined['snapshot']['market'].bar(a,u))
        names=core.COMMON+[v+'_missing' for v in core.COMMON]
        model=dict(scope='main',cutoff='2023-01-01',feature_names=names,coef=[0.]*52,intercept=1.)
        scaler=dict(scope='main',cutoff='2023-01-01',feature_names=names,
            common=dict(columns=core.COMMON,mean=[0.]*26,scale=[1.]*26))
        with tempfile.TemporaryDirectory() as temp:
            identity=caller.make_policy_identity(model,scaler,frozen_at=None)
            journal=caller._components().journal.ForwardJournal(Path(temp)/'model',identity)
            result=m.observe_composed(composed,model=model,scaler=scaler,journal=journal,policy_identity=identity,caller=caller)
        self.assertEqual(result['result']['counts']['mother_count'],98)
        self.assertFalse(result['result']['active']);self.assertIsNone(result['result']['states'])
        self.assertTrue(all(result['result']['counts'][k]==0 for k in ('new_state_calls','advance_D_calls','seal_u_calls','new_fit','SQL')))
        classify=caller._components().journal.evaluate_clock
        base=dict(frozen_at='2026-10-20T00:00:00+00:00',source_completed_at=snap['clock']['source_completed_at'],
            D_open_at=snap['clock']['D_open_at'])
        self.assertEqual(classify(**base,received_at='2026-10-20T07:00:00+00:00',decision_sealed_at=None)['status'],'received_before_completion')
        self.assertEqual(classify(**base,received_at='2026-10-20T13:00:00+00:00',decision_sealed_at=None)['status'],'late_input')
        with self.assertRaises(ValueError):m.check_collection_window('2026-10-20T15:14:59+08:00')
        with self.assertRaises(ValueError):m.check_collection_window('2026-10-20T21:00:00+08:00')
        m.check_collection_window('2026-10-20T15:15:00+08:00')


if __name__=='__main__':unittest.main()
