"""Three synthetic allocator groups; no actual signals/native/cash or old suite."""
import ast
import importlib.util
import itertools
import math
from pathlib import Path
import types
import unittest
from unittest.mock import patch

PATH=Path(__file__).with_name('stage312_joint_integer_allocator.py')
if PATH.exists():
    spec=importlib.util.spec_from_file_location('tiny312',PATH)
    engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
else:engine=None


def candidate(name,lot=1,score=.5,d=900.,capacity=2,u=0):
    return dict(event_id=name,product_id='X.'+name,family_id='X.'+name,reference_epoch='X.'+name+'.202001',
        N_u=4*d,u_close=100.,entry_capacity_qty=capacity,u_index=u,u_date='d'+str(u),score=score)


def economics(rows,risks=None,margins=None,lots=None):
    return {r['reference_epoch']:dict(contract_multiplier=1.,round_lot=(lots or {}).get(r['event_id'],1),
        risk=(risks or {}).get(r['event_id'],1000.),margin=(margins or {}).get(r['event_id'],1000.),fee=25.) for r in rows}


def legacy_reserve(candidates,equity,F0,M0,econ,scenario,policy='NARROW'):
    raw=[(.0025*equity/econ[c['reference_epoch']]['risk'],c,econ[c['reference_epoch']]) for c in candidates]
    R=sum(a*e['risk'] for a,c,e in raw);M=sum(a*e['margin'] for a,c,e in raw)
    scale=min(1.,max(0.,.02*equity-F0)/R if R else 1.,max(0.,.25*equity-M0)/M if M else 1.)
    result=[]
    for a,c,e in raw:
        t=a*scale;lot=e['round_lot'];original=int(math.floor(t/lot))*lot
        result.append(dict(c,unit_risk_u=e['risk'],unit_margin_u=e['margin'],unit_fee_reserve_u=e['fee'],
            u_equity=equity,existing_risk=F0,existing_buffered_margin=M0,target_qty_unscaled=a,joint_scale=scale,
            target_qty_prefloor=t,qty_cap=min(original,c['entry_capacity_qty']),round_lot=lot,original_qty_cap=original,
            allocated_risk=t*e['risk'],allocated_buffered_margin=t*e['margin'],allocated_fee=t*e['fee'],budget_state='reserved'))
    return result


reserve_capped=legacy_reserve


def tiny_run(signals,market,dates,economics,scenario,account_id,start,end,initial=1e6,prepared=None,*,policy='NARROW'):
    source=signals if prepared is None else prepared;budgets=[]
    for u in range(start-1 if start>0 else 0,end):
        budgets.extend(reserve_capped(source.get(u,[]),initial,17000.,247000.,economics,scenario,policy))
    return dict(budgets=budgets)


def exhaustive(problem):
    feasible=[]
    for k in itertools.product(*(range(u+1) for u in problem['upper'])):
        if sum(a*x for a,x in zip(problem['A'],k))<=problem['risk_cap'] and sum(b*x for b,x in zip(problem['B'],k))<=problem['margin_cap']:
            feasible.append((sum(c*x for c,x in zip(problem['C'],k)),k))
    return max(feasible)


class TestStage312(unittest.TestCase):
    def require(self):
        self.assertIsNotNone(engine,'new312 allocator behavior is missing')
        return engine

    def problem(self,rows,econ,E=1e6,F0=17000.,M0=247000.):
        m=self.require();old=legacy_reserve(rows,E,F0,M0,econ,'stress')
        return m.build_problem(old,E,F0,M0,econ),old

    def test_joint_integer_lot_net_value_and_two_resource_greedy_counterexample(self):
        m=self.require();rows=[candidate('A'),candidate('B',score=.1)];econ=economics(rows,lots={'A':2})
        p,old=self.problem(rows,econ);answer=m.solve_problem(p)
        self.assertEqual([r['qty_cap'] for r in old],[0,1])
        self.assertEqual(answer['k'],[1,1]);self.assertEqual(answer['n'],[2,1]);self.assertEqual(answer['objective'],990000000)
        self.assertEqual((answer['objective'],tuple(answer['k'])),exhaustive(p))
        self.assertEqual(p['C'],[900000000,90000000])  # fee is not subtracted twice.
        rows=[candidate('A',score=4.,d=1.,capacity=1),candidate('B',score=5.,d=1.,capacity=1),candidate('C',score=1.9,d=1.,capacity=1)]
        econ=economics(rows,risks={'A':2.,'B':3.,'C':1.},margins={'A':3.,'B':1.,'C':2.})
        p,_=self.problem(rows,econ,E=2000.,F0=36.,M0=497.);answer=m.solve_problem(p)
        self.assertEqual(answer['k'],[0,1,1]);self.assertEqual(answer['objective'],6900000)
        self.assertEqual((answer['objective'],tuple(answer['k'])),exhaustive(p))

    def test_lex_permutation_decimal_ceil_floor_and_zero_feasible(self):
        m=self.require();rows=[candidate('Z',capacity=1),candidate('A',capacity=1)];econ=economics(rows)
        p,_=self.problem(rows,econ,E=400000.,F0=7000.,M0=99000.);answer=m.solve_problem(p)
        self.assertEqual([v['event_id'] for v in p['variables']],['A','Z']);self.assertEqual(answer['k'],[1,0])
        reverse,_=self.problem(list(reversed(rows)),econ,E=400000.,F0=7000.,M0=99000.)
        self.assertEqual(m.solve_problem(reverse)['k'],answer['k'])
        self.assertEqual((answer['objective'],tuple(answer['k'])),exhaustive(p))
        econ=economics(rows,risks={'A':1000.0000001,'Z':1000.0000001})
        p,_=self.problem(rows,econ,E=400000.,F0=7000.,M0=99000.)
        self.assertEqual(p['A'],[1000000001,1000000001]);self.assertEqual(p['single_risk_cap'],1000000000)
        self.assertEqual(m.solve_problem(p)['k'],[0,0])
        p['C']=[-1,-1];p['upper']=[1,1]
        self.assertEqual(m.solve_problem(p)['k'],[0,0])  # no full-upper shortcut for negative objective.
        # Decimal/grid .1*3=.3 is feasible; final float .1*3 must not exceed the own .3 cap.
        rows=[candidate('A',d=.01,capacity=3)];econ=economics(rows,risks={'A':.1},margins={'A':.1})
        p,old=self.problem(rows,econ,E=120.,F0=0.,M0=0.);answer=m.solve_problem(p)
        self.assertEqual(answer['n'],[3])
        with self.assertRaisesRegex(RuntimeError,'float_single'):
            m.apply_solution(old,p,answer)

    def test_private_callback_trigger_F0_D_buffer_and_failure_evidence(self):
        m=self.require();rows=[candidate('A'),candidate('B',score=.1)];econ=economics(rows,lots={'A':2})
        single=candidate('S',u=1);econ.update(economics([single]))
        base=types.SimpleNamespace(run_cash_account=tiny_run,reserve_capped=legacy_reserve)
        payload={0:rows,1:[single],2:[]};dates=['d0','d1','d2','d3']
        book=m.run_cash_account(payload,None,dates,econ,'stress','one',1,3,base_kernel=base)
        self.assertEqual(len(book['allocation_audit']),3)
        self.assertEqual([r['u_index'] for r in book['allocation_audit']],[0,1,2])
        self.assertEqual([r['mode'] for r in book['allocation_audit']],['joint_integer','legacy_single_family','legacy_empty'])
        self.assertIs(tiny_run.__globals__['reserve_capped'],legacy_reserve)
        self.assertTrue(book['allocation_implementation']['original_code_identity_preserved'])
        first=book['allocation_audit'][0]
        self.assertEqual(first['held_F0'],17000.);self.assertEqual(first['problem']['risk_cap'],3000000000)
        self.assertEqual(book['allocation_audit'][1]['old_rows'],book['allocation_audit'][1]['actual_rows'])
        self.assertEqual(first['old_rows'][1]['allocated_risk'],1500.)
        self.assertEqual(first['actual_rows'][1]['allocated_risk'],1000.)
        # Execute the unchanged070 pure D function code with synthetic quote inputs.
        parsed=ast.parse(PATH.with_name('stage070_policy_kernel.py').read_text())
        node=next(v for v in parsed.body if isinstance(v,ast.FunctionDef) and v.name=='execution_quantity')
        namespace=dict(unit_estimate=lambda *a:dict(risk_per_lot=1200.,buy=dict(fill_price=100.,fee_per_lot=0.)),
            margin_rate=lambda *a:1.,floor_lot=lambda v,L:int(math.floor(v/L))*L)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<unchanged070D>','exec'),namespace)
        D=namespace['execution_quantity'];e=dict(contract_multiplier=1.,round_lot=1)
        self.assertEqual(D(first['old_rows'][1],100.,e,'stress','NARROW')[0],1)
        self.assertEqual(D(first['actual_rows'][1],100.,e,'stress','NARROW')[0],0)
        another=m.run_cash_account(payload,None,dates,econ,'stress','two',1,3,base_kernel=base)
        self.assertEqual(another['allocation_diagnostics']['batch_calls'],3)
        self.assertIsNot(another['allocation_audit'],book['allocation_audit'])
        limited=types.SimpleNamespace(status=1,success=False,message='synthetic_limit',x=None,fun=None,
            mip_dual_bound=None,mip_gap=None,mip_node_count=0)
        with patch.object(m,'milp',return_value=limited):
            with self.assertRaises(Exception) as caught:
                m.run_cash_account(payload,None,dates,econ,'stress','fail',1,3,base_kernel=base)
        failed=caught.exception.allocation_audit[-1]
        self.assertEqual(failed['status'],'failed');self.assertIn('problem',failed)
        self.assertEqual(failed['solver_stages'][0]['status'],1)
        with self.assertRaises(ValueError):m.run_cash_account(payload,None,dates,econ,'stress','missing',1,3)


if __name__=='__main__':unittest.main()
