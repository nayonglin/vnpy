"""One integration group; real320/321/322/131, synthetic data and clock only."""
from datetime import date,datetime,timedelta,timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

TOOLS=Path(__file__).resolve().parent
def load(name):
    p=TOOLS/name
    if not p.exists():return None
    s=importlib.util.spec_from_file_location('test325_'+p.stem,p)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class IntegrationTiny(unittest.TestCase):
    def test_observe_is_unfunded_and_receipt_controls_continuous_forward_commit(self):
        # Breaks on calling cash in observe mode, trusting caller receipt time,
        # selector before current-D own equity, or publishing a late seal.
        m=load('stage325_forward_caller.py');self.assertIsNotNone(m,'new caller wiring missing')
        c=m._components();core=c.core
        names=core.COMMON+[v+'_missing' for v in core.COMMON]
        model=dict(scope='main',cutoff='2023-01-01',feature_names=names,coef=[0.]*52,intercept=1.)
        scaler=dict(scope='main',cutoff='2023-01-01',feature_names=names,
            common=dict(columns=core.COMMON,mean=[0.]*26,scale=[1.]*26))
        dates=[(date(2030,1,1)+timedelta(days=i)).isoformat() for i in range(24)]
        products=['DCE.P']+['DCE.X'+str(i).zfill(3) for i in range(97)]
        epoch='DCE.P.203005'
        econ={epoch:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,
            round_lot=1,tick_size=.1,vendor_margin_rate=.1)}
        def snapshot(u,confirmed=True,development=False):
            states={}
            for e in (epoch,'GFEX.NEW.203006'):
                w=core.WilderState()
                for j in range(u+1):w.append(j,dict(open=100.,high=101.,low=99.,close=100.,volume=10000.,close_oi=10.,quality_status='accepted'))
                states[e]=w  # exact326 current-u WilderState shape, same injected core
            class Market:
                def bar(self,e,j):
                    if e not in states or j>u:return None
                    return dict(open=100.,high=101.,low=99.,close=100.,volume=10000.)
                def indicator(self,e,j):return dict(N=2.,low20=99.,run=21+j)
            return dict(schema='stage325_received_snapshot_v1',development_only=development,frozen_at=None,
                u_index=u,u_date=dates[u],dates=dates[:u+2] if confirmed else dates[:u+1],economics=econ,
                products=products,series_by_epoch=states,market=Market(),source='synthetic',version='v1/u'+str(u),
                source_receipt=dict(synthetic=True,snapshot_version='v1/u'+str(u)),
                received_at='1999-01-01T00:00:00Z',clock=dict(source_completed_at=dates[u]+'T15:00:00Z',
                D_open_at=dates[u+1]+'T01:00:00Z' if confirmed else None),
                D_context=dict(confirmed=True,D_index=u+1,D_date=dates[u+1]) if confirmed else dict(confirmed=False))
        class Clock(datetime):
            values=[]
            @classmethod
            def now(cls,tz=None):
                value=cls.values.pop(0)
                return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(tz or timezone.utc)
        def clock(values):Clock.values=list(values);return patch.object(c.journal,'datetime',Clock)
        def times(day):return [day+'T16:00:00Z',day+'T16:01:00Z',day+'T16:02:00Z',day+'T16:03:00Z',day+'T16:04:00Z']
        with tempfile.TemporaryDirectory() as temp:
            identity=m.make_policy_identity(model,scaler,frozen_at=None)
            journal=c.journal.ForwardJournal(Path(temp)/'observe',identity)
            with clock(times(dates[20])):
                out=m.process_snapshot(snapshot(20,False,True),model=model,scaler=scaler,journal=journal,
                    policy_identity=identity,mode='observe_only')
            self.assertEqual(len(out['observations']['mothers']),98)
            self.assertTrue(any(r['status']=='unsupported_product' for r in out['observations']['statuses']))
            self.assertFalse(out['active']);self.assertIsNone(out['states'])
            self.assertFalse(any(r['selected'] for r in out['selection']['choices']))
            self.assertEqual(out['clock']['status'],'not_frozen')
            self.assertEqual(out['input_receipt']['recorded_at'],dates[20]+'T16:00:00+00:00')
            self.assertNotEqual(out['input_receipt']['recorded_at'],'1999-01-01T00:00:00Z')
            json.dumps(out,allow_nan=False)
            self.assertTrue(any(v is None for r in out['scores'] for v in r['raw26']))
            self.assertTrue(any(sum(r['design52'][26:])>0 for r in out['scores']))
            self.assertEqual(out['instrument_evidence'][epoch]['contract_multiplier'],10.)
            self.assertEqual(out['counts']['new_state_calls'],0)
            self.assertEqual(out['counts']['advance_D_calls'],0);self.assertEqual(out['counts']['seal_u_calls'],0)
            with self.assertRaises(ValueError):
                m.process_snapshot(snapshot(20,False,True),model=model,scaler=scaler,journal=journal,
                    policy_identity=identity,mode='future',states={})
            kernel=load('stage131_contract_choice_kernel.py')
            states={scenario:c.paper.new_state(scenario=scenario,account_id='integration_'+scenario,start_u=20,base_kernel=kernel)
                    for scenario in ('base','stress')}
            before={s:c.paper.export_state(v) for s,v in states.items()}
            identity=m.make_policy_identity(model,scaler,frozen_at='2030-01-20T12:00:00Z')
            journal=c.journal.ForwardJournal(Path(temp)/'future',identity)
            with clock(times(dates[20])):
                first=m.process_snapshot(snapshot(20),model=model,scaler=scaler,journal=journal,
                    policy_identity=identity,mode='future',states=states,base_kernel=kernel)
            self.assertTrue(first['active']);self.assertEqual(first['clock']['status'],'timely_forward_decision')
            self.assertEqual(first['counts']['seal_u_calls'],2)
            self.assertEqual(first['counts']['advance_D_calls'],0)
            self.assertTrue(all(s['phase']=='awaiting_D' for s in first['states'].values()))
            self.assertEqual({s:c.paper.export_state(v) for s,v in states.items()},before)
            proposal=[r for r in journal.entries() if r['kind']=='decision_proposal'][-1]
            self.assertFalse(proposal['payload']['active'])
            unfrozen=m.make_policy_identity(model,scaler,frozen_at=None)
            unfrozenjournal=c.journal.ForwardJournal(Path(temp)/'notfrozen',unfrozen)
            with clock(times(dates[21])):
                nofreeze=m.process_snapshot(snapshot(21),model=model,scaler=scaler,journal=unfrozenjournal,
                    policy_identity=unfrozen,mode='future',states=first['states'],base_kernel=kernel)
            self.assertEqual(nofreeze['clock']['status'],'not_frozen')
            self.assertEqual(nofreeze['counts']['advance_D_calls'],0)
            self.assertEqual(nofreeze['states'],first['states'])
            other=m.make_policy_identity(model,scaler,frozen_at='2030-01-20T11:00:00Z')
            otherjournal=c.journal.ForwardJournal(Path(temp)/'otherpolicy',other)
            with clock(times(dates[21])),self.assertRaises(ValueError):
                m.process_snapshot(snapshot(21),model=model,scaler=scaler,journal=otherjournal,
                    policy_identity=other,mode='future',states=first['states'],base_kernel=kernel)
            with clock(times(dates[21])):
                second=m.process_snapshot(snapshot(21),model=model,scaler=scaler,journal=journal,
                    policy_identity=identity,mode='future',states=first['states'],base_kernel=kernel)
            self.assertTrue(second['active']);self.assertEqual(second['counts']['advance_D_calls'],2)
            self.assertEqual(second['states']['base']['daily'][-1]['equity'],999450.)
            self.assertEqual(second['states']['stress']['daily'][-1]['equity'],998850.)
            self.assertEqual(second['states']['base']['pending'][0]['allocated_risk'],.0025*999450.)
            self.assertEqual(second['states']['stress']['pending'][0]['allocated_risk'],.0025*998850.)
            latejournal=c.journal.ForwardJournal(Path(temp)/'crossed',identity)
            late=[dates[21]+'T16:00:00Z',dates[21]+'T16:01:00Z',dates[22]+'T00:59:59Z',dates[22]+'T01:00:00Z',dates[22]+'T01:00:01Z']
            with clock(late):
                crossed=m.process_snapshot(snapshot(21),model=model,scaler=scaler,journal=latejournal,
                    policy_identity=identity,mode='future',states=first['states'],base_kernel=kernel)
            self.assertFalse(crossed['active']);self.assertEqual(crossed['clock']['status'],'late_decision')
            self.assertTrue(all(s['phase']=='awaiting_u' and not s['pending'] for s in crossed['states'].values()))
            self.assertEqual(crossed['states']['base']['daily'][-1]['equity'],999450.)
            self.assertEqual(crossed['status'],'state_gap')
            self.assertEqual(latejournal.entries()[-1]['kind'],'state_gap')
            unknownjournal=c.journal.ForwardJournal(Path(temp)/'unknown',identity)
            with clock(times(dates[20])):
                unknown=m.process_snapshot(snapshot(20,False),model=model,scaler=scaler,journal=unknownjournal,
                    policy_identity=identity,mode='future',states=states,base_kernel=kernel)
            self.assertFalse(unknown['active']);self.assertEqual(unknown['clock']['status'],'D_clock_unknown')
            self.assertEqual(unknown['counts']['seal_u_calls'],0)
            self.assertEqual(unknown['states'],states)
            changed=dict(model,intercept=2.)
            with self.assertRaises(ValueError):
                m.process_snapshot(snapshot(20),model=changed,scaler=scaler,journal=journal,
                    policy_identity=identity,mode='future',states=states,base_kernel=kernel)
            self.assertEqual(kernel.ref.NATIVE_QUERIES,0)

if __name__=='__main__':unittest.main()
