"""Three synthetic305 behaviors, never actualOI/actions/SQL or old suites."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

PATH=Path(__file__).with_name('stage305_month_pool_oi_source.py')
if PATH.exists():
    SPEC=importlib.util.spec_from_file_location('tiny305',PATH)
    SOURCE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(SOURCE)
else:SOURCE=None

DATES=['2010-01-04','2010-01-05','2010-01-06','2010-01-07']
UNITS=dict(canonical_quantity_unit='single_sided_contracts',cleaner_rule_approved=True,
    rqalpha=dict(rules=[dict(exchanges=['X'],start='2010-01-01',end='2099-12-31',volume_factor=1.,close_oi_factor=1.)]),
    old_tq=dict(volume_factor=1.,close_oi_factor=1.),recent_tq=dict(volume_factor=1.,close_oi_factor=1.),
    official=dict(accepted_regime_factors={'single':1.,'double':.5}))


def row(epoch,day,oi,volume=100.,factor=1.,source='rqalpha'):
    family='old_tq' if source.startswith('old_tq:') else 'rqalpha'
    return (epoch,'X',DATES[day],oi,volume,source,factor,factor,'accepted',family)


class TestStage305(unittest.TestCase):
    def functions(self):
        self.assertIsNotNone(SOURCE,'new305 source behavior is missing')
        return SOURCE.compile_native,SOURCE.pool_quantities,SOURCE.align_block

    def calculate(self,records,epochs,u):
        compile_native,pools,align=self.functions()
        ordered=sorted(records,key=lambda x:(x[0],x[2]))
        native,codes=compile_native(ordered,DATES,UNITS,expected_rows=len(ordered))
        q,state,summary=pools(native,codes,len(DATES))
        result=align(np.arange(len(u),dtype=np.int64),np.array(epochs,dtype=object),
            np.array(u,dtype=np.int64),native,q,state,0,len(DATES))
        return result,native,codes,summary

    def test_exact_previous_source_day_never_carries_or_uses_future(self):
        # A has no v=1 row. A/u2 must stay missing, even though A/v0 exists.
        a='X.A.201001';b='X.A.201002'
        records=[row(a,0,100.),row(a,2,900.),row(a,3,10.),
                 row(b,0,100.),row(b,1,400.),row(b,2,100.)]
        refs=[b,a,a,a];u=[1,2,3,0]
        (q,state,lag),_,_,_=self.calculate(records,refs,u)
        self.assertEqual(q[0],.5);self.assertTrue(np.isnan(q[1]));self.assertEqual(q[2],.9)
        self.assertTrue(np.isnan(q[3]));self.assertEqual(lag[1],-1)
        changed=[row(a,3,999999.) if r[0]==a and r[2]==DATES[3] else r for r in records]
        (later,_,_),_,_,_=self.calculate(changed,refs,u)
        np.testing.assert_array_equal(q,later)
        with self.assertRaises(ValueError):
            _,_,align=self.functions();native,codes=self.functions()[0](sorted(records),DATES,UNITS,len(records))
            nq,ns,_=self.functions()[1](native,codes,len(DATES))
            align(np.array([1]),np.array([a]),np.array([2]),native,nq,ns,0,len(DATES))

    def test_unknown_member_invalidates_whole_pool_zero_and_singleton_are_legal(self):
        records=[]
        pairs=[('A',0.,20.,1.),('B',10.,np.nan,1.),('C',10.,20.,np.nan),('D',0.,0.,1.),('E',10.,-1.,1.)]
        refs=[]
        for p,first,second,factor in pairs:
            a=f'X.{p}.201001';b=f'X.{p}.201002'
            records.extend([row(a,0,first),row(a,1,10.),row(b,0,second,factor=factor)])
            refs.append(a)
        records.extend([row('X.S.201001',0,7.,source='old_tq:S'),row('X.S.201001',1,7.)])
        refs.append('X.S.201001')
        # Nontraded month is outside P; its badOI does not poison the valid A pool.
        records.append(row('X.A.201003',0,np.nan,volume=0.))
        (q,state,_),native,codes,summary=self.calculate(records,refs,[1]*6)
        self.assertEqual(q[0],0.);self.assertEqual(state[0],1)
        self.assertTrue(np.isnan(q[1:5]).all());self.assertEqual(q[5],1.)
        self.assertGreaterEqual(summary['invalid_oi_or_unit_pools'],2)
        self.assertEqual(len(native['close_oi']),len(records))
        self.assertEqual(native['volume'].dtype,np.dtype('float64'))
        self.assertIn('unknown_or_inconsistent_unit',[r['state'] for r in codes['unit_results']])
        # Accepted, differently named source IDs share the canonical-unit pool.
        records=[row('X.M.201001',0,2.),row('X.M.201002',0,6.,source='old_tq:M'),row('X.M.201001',1,2.)]
        (q,_,_),_,_,_=self.calculate(records,['X.M.201001'],[1]);self.assertEqual(q[0],.25)

    def test_F_product_is_separate_and_old_delta_cannot_reconstruct_share(self):
        a='X.A.201001';b='X.A.201002';f='X.A_F.201001'
        world=[row(e,d,oi) for e,oi in [(a,100.),(b,100.),(f,900.)] for d in (0,1)]
        (first,_,_),_,_,_=self.calculate(world,[a,f],[1,1])
        np.testing.assert_array_equal(first,[.5,1.])
        other=[row(r[0],DATES.index(r[2]),900. if r[0]==b else r[3]) for r in world]
        (second,_,_),_,_,_=self.calculate(other,[a,f],[1,1])
        np.testing.assert_array_equal(second,[.1,1.])
        # A OI and both worlds' within-contract differences remain unchanged.
        self.assertEqual([r[3] for r in world if r[0]==a],[100.,100.])
        self.assertEqual([r[3] for r in other if r[0]==a],[100.,100.])


if __name__=='__main__':unittest.main()
