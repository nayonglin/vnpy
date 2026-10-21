"""Three synthetic source behaviors; no actual cache/actions or old suite."""
import importlib.util
import math
from pathlib import Path
import unittest
import numpy as np

p=Path(__file__).with_name('stage295_reopening_contribution_source.py')
s=importlib.util.spec_from_file_location('tiny295',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


def bars(n):return np.tile([100.,102.,98.,100.,10000.],(n,1))


class TestStage295(unittest.TestCase):
    def function(self,name):
        self.assertTrue(callable(getattr(m,name,None)),'fixed294 source behavior not implemented')
        return getattr(m,name)

    def test_exact21_same_epoch_current_u_noD_and_legal_zero(self):
        quantity=self.function('epoch_quantity');values=bars(22);days=np.arange(22);valid=np.ones(22,dtype=bool)
        q,state=quantity(days,values,valid)
        self.assertTrue(np.isnan(q[:20]).all());self.assertEqual(q[20],0.);self.assertEqual(state[20],1)
        values[5,0]=101.;q,_=quantity(days,values,valid)
        self.assertAlmostEqual(q[20],1/(4*math.sqrt(20)),places=14)
        values[21]=[900.,1000.,800.,950.,10000.]  # D cannot affect q_u.
        changed,_=quantity(days,values,valid);self.assertEqual(changed[20],q[20])
        values[20,0]=101.;current,_=quantity(days,values,valid)
        self.assertAlmostEqual(current[20],2/(4*math.sqrt(20)),places=14)
        # Hand reference uses the specified fsum20 and TR arithmetic, no N.
        v=bars(24);v[:,3]=100.+np.arange(24)*.1;v[:,1]=v[:,3]+2;v[:,2]=v[:,3]-2;v[:,0]=v[:,3]-.15
        actual,_=quantity(np.arange(24),v,np.ones(24,dtype=bool))
        for j in range(20,24):
            w=v[j-20:j+1];tr=[max(b[1]-b[2],abs(b[1]-a[3]),abs(b[2]-a[3])) for a,b in zip(w,w[1:])]
            expected=math.fsum(b[0]-a[3] for a,b in zip(w,w[1:]))/(math.sqrt(20)*(math.fsum(tr)/20))
            self.assertTrue(math.isclose(actual[j],expected,rel_tol=1e-10,abs_tol=1e-10))

    def test_gap_rewarm_invalid_history_and_zeroATR_remain_unknown(self):
        quantity=self.function('epoch_quantity');values=bars(43);days=np.r_[np.arange(21),np.arange(22,44)]
        q,_=quantity(days,values,np.ones(43,dtype=bool))
        self.assertTrue(np.isnan(q[21:41]).all());self.assertEqual(q[41],0.)
        flags=np.ones(43,dtype=bool);flags[10]=False
        q,_=quantity(np.arange(43),values,flags)
        self.assertTrue(np.isnan(q[20:31]).all());self.assertEqual(q[31],0.)
        flat=bars(21);flat[:,:4]=100.
        q,_=quantity(np.arange(21),flat,np.ones(21,dtype=bool));self.assertTrue(np.isnan(q).all())

    def test_action_sequence_epoch_and_u_alignment_no_cross_epoch_window(self):
        quantity=self.function('epoch_quantity');align=self.function('align_block')
        a=bars(22);a[5,0]=101.;b=bars(22)
        qa,sa=quantity(np.arange(22),a,np.ones(22,dtype=bool));qb,sb=quantity(np.arange(22),b,np.ones(22,dtype=bool))
        days=np.r_[np.arange(22),np.arange(22)];nq=np.r_[qa,qb];ns=np.r_[sa,sb];index={'X.A':(0,22),'X.B':(22,44)}
        seq=np.arange(4);refs=np.array(['X.B','X.A','X.A','X.B'],dtype=object);u=np.array([0,20,19,20])
        q,state,native=align(seq,refs,u,index,days,nq,ns,0)
        self.assertTrue(np.isnan(q[[0,2]]).all());self.assertEqual(q[3],0.);self.assertEqual(state[3],1)
        self.assertAlmostEqual(q[1],1/(4*math.sqrt(20)),places=14);self.assertEqual(native.tolist(),[22,20,19,42])
        with self.assertRaises(ValueError):align(np.array([0,2,1,3]),refs,u,index,days,nq,ns,0)
        with self.assertRaises(ValueError):align(seq,np.array(['MISSING']*4),u,index,days,nq,ns,0)


if __name__=='__main__':unittest.main()
