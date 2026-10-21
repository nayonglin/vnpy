"""One new integration group: checkpoint continuation, gap reset, no carry."""
from copy import deepcopy
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

TOOLS=Path(__file__).resolve().parent

def load(name):
    path=TOOLS/name
    if not path.exists():return None
    spec=importlib.util.spec_from_file_location('test339_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class IncrementalTiny(unittest.TestCase):
    def test_checkpoint_is_not_reseeded_and_unknown_or_missing_never_becomes_current(self):
        # Catches replay/reseed of old history, quote carry, unknown->accepted,
        # an absent prior-u epoch retaining mature N, or observe calling cash.
        adapter=load('stage339_incremental_snapshot.py')
        self.assertIsNotNone(adapter,'new incremental adapter missing')
        caller=load('stage325_forward_caller.py');c=caller._components();core=c.core
        days=[];day=date(2026,9,1)
        while day<=date(2026,10,16):
            if day.weekday()<5 and not date(2026,10,1)<=day<=date(2026,10,7):days.append(day.isoformat())
            day+=timedelta(days=1)
        previous=len(days)-1;dates=days+['2026-10-19'];u=previous+1
        products=['DCE.P','DCE.P_F','DCE.Q','DCE.Q_F','DCE.R','DCE.R_F','DCE.S']+['DCE.X'+str(i).zfill(3) for i in range(91)]
        a,b,unknown,missing,new=('DCE.P.202703','DCE.P.202705','DCE.Q.202703','DCE.R.202703','DCE.P.202707')
        bar=dict(open=100.,high=101.,low=99.,close=100.,volume=10000.,close_oi=10.,quality_status='accepted')
        states={}
        for epoch in (a,unknown,missing):
            w=core.WilderState()
            for j in range(previous+1):w.append(j,bar)
            states[epoch]=w.to_dict()
        inventory=[dict(epoch=e,product_id=e.rsplit('.',1)[0],rows=previous+1,
            last_index=previous,last_date=days[-1],has_current_bar=True) for e in states]
        inventory.append(dict(epoch=b,product_id='DCE.P',rows=8,last_index=previous-2,
            last_date=days[-3],has_current_bar=False))
        economics={a:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,
            round_lot=1,tick_size=.1,vendor_margin_rate=.1)}
        receipt=dict(status='completed',canonical_rows_accepted=True,binding=dict(sha256='synthetic-overlay'))
        source=dict(checkpoint='synthetic331',normalized='synthetic337',development_only=True)
        def row(e,**changes):
            result=dict(contract_epoch_id=e,trade_date='2026-10-19',
                canonical_values=dict(open=100.,high=105.,low=99.,close=104.,volume=200.,close_oi=None),
                identity_state='known_explicit',date_mapping_state='operational_midnight_label',
                units_status='canonical_normalized',canonical_quality_status='accepted',
                model_input_eligible=True,source_receipt=dict(entry_hash='synthetic-row'))
            result.update(changes);return result
        rows=[row(a),row(b),row(new),row(unknown,units_status='provider_raw_units_unverified'),
            row(None,identity_state='unknown',model_input_eligible=False),
            row('GFEX.NEW.202703'),row(a,trade_date='2026-10-16')]
        before=deepcopy((states,inventory,rows,economics))
        kwargs=dict(dates=dates,previous_u_date='2026-10-16',u_date='2026-10-19',products=products,
            economics=economics,calendar_confirmation=dict(confirmed=True,u_date='2026-10-19',u_index=u,proof='synthetic-calendar'),
            normalization_receipt=receipt,source_receipt=source,core=core)
        snapshot=adapter.build_incremental_snapshot(states,inventory,rows,**kwargs)
        self.assertEqual((states,inventory,rows,economics),before)
        self.assertAlmostEqual(snapshot['warmup_state'][a]['N'],2.2,places=14)
        self.assertEqual(snapshot['warmup_state'][a]['run'],previous+2)
        self.assertEqual(snapshot['warmup_state'][b]['run'],1)
        self.assertIsNone(snapshot['warmup_state'][b]['N'])
        self.assertEqual(snapshot['warmup_state'][new]['run'],1)
        self.assertEqual(len(snapshot['warmup_state'][new]['history']),1)
        self.assertEqual(snapshot['warmup_state'][unknown],states[unknown])
        self.assertEqual(snapshot['warmup_state'][missing],states[missing])
        self.assertIsNone(snapshot['market'].bar(missing,u))
        self.assertIsNone(snapshot['market'].bar(unknown,u))
        self.assertFalse(isinstance(snapshot['series_by_epoch'][missing],core.WilderState))
        self.assertEqual(snapshot['incremental_audit']['appended_rows'],3)
        self.assertEqual(snapshot['incremental_audit']['unsupported_product_rows'],1)
        self.assertTrue(any('units_status' in r['reasons'] for r in snapshot['_row_dispositions']))
        self.assertIsNone(snapshot['clock']['source_completed_at']);self.assertIsNone(snapshot['clock']['D_open_at'])
        self.assertFalse(snapshot['D_context']['confirmed'])
        names=core.COMMON+[v+'_missing' for v in core.COMMON]
        model=dict(scope='main',cutoff='2023-01-01',feature_names=names,coef=[0.]*52,intercept=1.)
        scaler=dict(scope='main',cutoff='2023-01-01',feature_names=names,
            common=dict(columns=core.COMMON,mean=[0.]*26,scale=[1.]*26))
        with tempfile.TemporaryDirectory() as temp:
            identity=caller.make_policy_identity(model,scaler,frozen_at=None)
            journal=c.journal.ForwardJournal(Path(temp)/'observe',identity)
            result=caller.process_snapshot(snapshot,model=model,scaler=scaler,journal=journal,
                policy_identity=identity,mode='observe_only')
        self.assertEqual(len(result['observations']['mothers']),98)
        self.assertEqual({r['reference_epoch'] for r in result['scores']},{a,b,new})
        main=next(r for r in result['scores'] if r['reference_epoch']==a)
        self.assertAlmostEqual(main['N_u'],2.2,places=14)
        self.assertEqual(main['score'],1.)
        self.assertTrue(any(r['product_id']=='DCE.S' and r['status']=='no_accepted_observation' for r in result['observations']['mothers']))
        self.assertFalse(result['active']);self.assertIsNone(result['states'])
        self.assertTrue(all(result['counts'][k]==0 for k in ('new_state_calls','advance_D_calls','seal_u_calls','new_fit','SQL')))
        json.dumps(result,allow_nan=False)
        # A persisted second new day continues mature N, but an unknown first
        # day makes the recovered epoch restart rather than silently carry.
        again=adapter.build_incremental_snapshot(snapshot['warmup_state'],snapshot['_inventory'],
            [row(a,trade_date='2026-10-20',canonical_values=dict(open=104.,high=106.,low=103.,close=105.,volume=200.,close_oi=0.)),
             row(unknown,trade_date='2026-10-20')],**dict(kwargs,dates=dates+['2026-10-20'],
                previous_u_date='2026-10-19',u_date='2026-10-20',
                calendar_confirmation=dict(confirmed=True,u_date='2026-10-20',u_index=u+1,proof='synthetic-calendar')))
        self.assertAlmostEqual(again['warmup_state'][a]['N'],2.24,places=14)
        self.assertEqual(again['warmup_state'][unknown]['run'],1)
        self.assertIsNone(again['warmup_state'][unknown]['N'])
        self.assertIsNone(again['market'].bar(new,u+1))
        with self.assertRaises(ValueError):
            adapter.build_incremental_snapshot(states,inventory,rows,**dict(kwargs,
                normalization_receipt=dict(status='completed',canonical_rows_accepted=False)))
        with self.assertRaises(ValueError):
            adapter.build_incremental_snapshot(states,inventory,[row(a),row(a)],**kwargs)
        with self.assertRaises(ValueError):
            adapter.build_incremental_snapshot(states,inventory,rows,**dict(kwargs,
                calendar_confirmation=dict(confirmed=False)))

if __name__=='__main__':unittest.main()
