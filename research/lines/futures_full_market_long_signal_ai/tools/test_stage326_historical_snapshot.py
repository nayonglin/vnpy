"""One warmup group with hand-checked tiny arrays; no actual cache/SQL/cash."""
from datetime import date, timedelta
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np


class HistoricalWarmupTiny(unittest.TestCase):
    def test_cached_Wilder_continuation_and_missing_current_quote(self):
        # Catches reseeding cached N, dropping run-head seed, carrying a stale
        # epoch to u, or accepting SQL/cache disagreement as a valid snapshot.
        path=Path(__file__).with_name('stage326_historical_snapshot.py')
        self.assertTrue(path.exists(), 'historical snapshot adapter is not implemented')
        spec=importlib.util.spec_from_file_location('stage326_tiny',path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        core=m.load_core()
        dates=[(date(2026,10,1)+timedelta(days=i)).isoformat() for i in range(28)]
        values=np.array([[100.,101.,99.,100.,1000.] for _ in range(26)])
        values[20,1:3]=[110.,90.]
        N=np.array([np.nan]*19+[2.,2.9,2.855,2.81225,2.7716375,2.733055625,2.69640284375])
        low=np.array([np.nan]*19+[99.]+[90.]*6)
        s=SimpleNamespace(days=np.arange(26),values=values,accepted=np.ones(26,bool),
                          valid=np.ones(26,bool),N=N,low20=low,run=np.arange(1,27))
        with self.subTest('cached_N_seed_and_checkpoint_resume_are_separate'):
            state,evidence=m.warmup_epoch('DCE.C.203001',s,25,close_oi=123.,core=core)
            exported=state.to_dict()
            self.assertEqual(exported['N'],2.69640284375)
            self.assertEqual(exported['seed'],40.)
            self.assertEqual(exported['run'],26)
            self.assertEqual(exported['last_close'],100.)
            self.assertEqual(exported['history'][0]['day'],5)
            self.assertTrue(all(v['close_oi'] is None for v in exported['history'][:-1]))
            self.assertEqual(exported['history'][-1]['close_oi'],123.)
            restored=core.WilderState.from_dict(json.loads(json.dumps(exported,allow_nan=False)))
            restored.append(26,dict(open=100.,high=101.,low=99.,close=100.,volume=1000.,quality_status='accepted',close_oi=None))
            self.assertAlmostEqual(restored.to_dict()['N'],2.6615827015625,places=14)
            replay=core.WilderState.from_dict(evidence['checkpoint_before_window'])
            for r in evidence['tail']:
                replay.append(r['day'],dict(zip(('open','high','low','close','volume'),r['values']),
                    quality_status='accepted' if r['accepted'] else 'invalid',close_oi=r['close_oi']))
            replayed=replay.to_dict()
            # Hand-entered decimal cache levels need not share the final ULP
            # of repeated binary arithmetic; actual cached N is kept verbatim.
            self.assertAlmostEqual(replayed.pop('N'),exported['N'],places=14)
            expected=dict(exported);expected.pop('N')
            np.testing.assert_allclose(np.asarray([r['N'] for r in replayed['history']],float),
                np.asarray([r['N'] for r in expected['history']],float),rtol=0,atol=1e-14,equal_nan=True)
            for r in replayed['history']:r.pop('N')
            for r in expected['history']:r.pop('N')
            self.assertEqual(replayed,expected)
        with self.subTest('run_start_seed_does_not_use_prior_gap_close'):
            g=SimpleNamespace(days=np.arange(23),values=np.tile([100.,101.,99.,100.,1000.],(23,1)),
                accepted=np.r_[True,False,np.ones(21,bool)],valid=np.r_[True,False,np.ones(21,bool)],
                N=np.r_[np.nan,np.nan,np.full(19,np.nan),2.,2.],
                low20=np.r_[np.full(21,np.nan),99.,99.],run=np.r_[1,0,np.arange(1,22)])
            g.values[0,3]=10000.
            state,_=m.warmup_epoch('DCE.C.203001',g,22,core=core)
            self.assertEqual(state.to_dict()['seed'],40.)
            self.assertEqual(state.to_dict()['N'],2.)
            self.assertEqual(state.to_dict()['run'],21)
        with self.subTest('complete_domain_stale_epoch_and_exact_same_day_join'):
            stale=SimpleNamespace(**{k:getattr(s,k)[:-1] for k in ('days','values','accepted','valid','N','low20','run')})
            rows=[dict(contract_epoch_id='DCE.C.203001',trade_date=dates[25],open=100.,high=101.,
                low=99.,close=100.,volume=1000.,close_oi=None,quality_status='accepted',source_id='tiny',source_locator='tiny')]
            snap=m.assemble_snapshot({'DCE.C.203001':s,'DCE.C_F.203001':stale},dates,{},
                ['DCE.C','DCE.C_F','SHFE.MISSING'],rows,snapshot_date=dates[25],core=core)
            self.assertEqual(snap['products'],['DCE.C','DCE.C_F','SHFE.MISSING'])
            self.assertNotIn('DCE.C_F.203001',snap['warmup_state'])
            self.assertIsNone(snap['market'].bar('DCE.C_F.203001',25))
            self.assertEqual(snap['market'].bar('DCE.C.203001',25)['close'],100.)
            self.assertEqual(snap['D_context']['D_date'],dates[26])
            self.assertTrue(snap['development_only'])
            self.assertIsNone(snap['frozen_at'])
            self.assertIsNone(snap['clock']['source_completed_at'])
            self.assertIsNone(snap['clock']['D_open_at'])
            bad=[dict(rows[0],close=101.)]
            with self.assertRaises(ValueError):
                m.assemble_snapshot({'DCE.C.203001':s},dates,{},['DCE.C'],bad,snapshot_date=dates[25],core=core)


if __name__=='__main__':
    unittest.main()
