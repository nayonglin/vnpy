"""Only new one-lot reservation boundaries; tiny synthetic inputs, no actual I/O."""
import importlib.util
from pathlib import Path
import unittest


SOURCE=Path(__file__).with_name('stage080_one_lot_prefilter.py')
if SOURCE.exists():
    spec=importlib.util.spec_from_file_location('stage080_under_test',SOURCE)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
else:
    m=None


def candidate(event='a',N=4.,price=100.):
    return dict(event_id=event,reference_epoch='X.A.203001',N_u=N,u_close=price)


ECON={'X.A.203001':dict(contract_multiplier=1.,round_lot=1.,tick_size=None,vendor_margin_rate=.2)}


class OneLotBoundaries(unittest.TestCase):
    def ready(self):
        self.assertIsNotNone(m,'isolated one-lot prefilter implementation required')

    def reserve(self,candidates,held_risk=0.,held_margin=0.):
        self.ready()
        return m.reserve_batch(candidates,1_000_000.,held_risk,held_margin,ECON,'base','NARROW')

    def test_single_family_one_lot_unreachable_retains_raw_target_and_zero_joint_input(self):
        row=self.reserve([candidate(N=10000.)])[0]
        self.assertEqual(row['event_id'],'a')
        self.assertEqual(row['prefilter_reasons'],'single_risk')
        self.assertAlmostEqual(row['raw_target_qty_unscaled'],2500./2504.02)
        for field in ('joint_input_qty_unscaled','target_qty_unscaled','target_qty_prefloor','qty_cap',
                      'allocated_risk','allocated_buffered_margin','allocated_fee'):
            self.assertEqual(row[field],0.)

    def test_remaining_total_risk_one_lot_unreachable(self):
        row=self.reserve([candidate()],held_risk=19995.)[0]
        self.assertEqual(row['prefilter_reasons'],'remaining_total_risk')
        self.assertEqual(row['remaining_total_risk_u'],5.)
        self.assertEqual(row['qty_cap'],0)

    def test_remaining_buffered_margin_one_lot_unreachable(self):
        row=self.reserve([candidate()],held_margin=249990.)[0]
        self.assertEqual(row['prefilter_reasons'],'remaining_margin')
        self.assertEqual(row['remaining_buffered_margin_u'],10.)
        self.assertEqual(row['qty_cap'],0)

    def test_only_reachable_candidates_enter_joint_scale_and_every_row_survives(self):
        candidates=[candidate(str(k)) for k in range(20)]+[candidate('unreachable',N=10000.)]
        rows=self.reserve(candidates)
        self.assertEqual([r['event_id'] for r in rows],[str(k) for k in range(20)]+['unreachable'])
        self.assertTrue(all(abs(r['joint_scale']-.4)<1e-12 for r in rows))
        self.assertEqual([r['qty_cap'] for r in rows],[199]*20+[0])
        self.assertAlmostEqual(sum(r['allocated_risk'] for r in rows),20000.)
        self.assertEqual(rows[-1]['prefilter_eligible'],0)

    def test_no_exclusions_matches_every_original_reservation_field(self):
        self.ready()
        candidates=[candidate('a'),candidate('b')]
        old=m.kernel.reserve_batch(candidates,1_000_000.,0.,0.,ECON,'base','NARROW')
        new=self.reserve(candidates)
        for a,b in zip(old,new):
            for field,value in a.items():self.assertEqual(b[field],value,field)
        self.assertTrue(all(r['prefilter_eligible']==1 for r in new))

    def test_D_open_quantity_can_only_reduce_own_u_cap(self):
        self.ready()
        row=self.reserve([candidate(str(k)) for k in range(20)])[0]
        quantity,unit=m.kernel.execution_quantity(row,200.,ECON['X.A.203001'],'base','NARROW')
        self.assertEqual(row['qty_cap'],199)
        self.assertEqual(quantity,123)
        self.assertLess(quantity,row['qty_cap'])
        self.assertAlmostEqual(unit['risk_per_lot'],5.04)


if __name__=='__main__':unittest.main()
