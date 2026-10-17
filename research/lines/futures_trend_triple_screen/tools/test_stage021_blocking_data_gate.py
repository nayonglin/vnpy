"""Synthetic waiting, exact qualification and restoration; no engine/provider."""
from pathlib import Path
from types import SimpleNamespace
from collections import OrderedDict
import tempfile
import unittest
import pandas as pd

try:import stage021_blocking_data_gate as module
except ImportError:module=None


class FakeParentEngine:
    def _stage827_order_context(self,order,bar):
        self.context_calls.append(order.vt_orderid);self.account_effects.append(order.vt_orderid)
        return {'order':order.vt_orderid}


class FakeInheritedEngine(FakeParentEngine):pass


def engine(cls=FakeInheritedEngine):
    result=cls();result.datetime=pd.Timestamp('2022-04-06')
    result.strategy=SimpleNamespace(available_trade_dates=pd.to_datetime(['2022-04-01','2022-04-06']),stage827_minute_by_symbol={})
    result.active_limit_orders=OrderedDict((key,SimpleNamespace(vt_orderid=key,vt_symbol=symbol,offset=offset,
        direction='LONG',price=100.,volume=1,status='SUBMITTING',traded=0))for key,symbol,offset in
        [('o1','AP205.CZCE','OPEN'),('o2','SM205.CZCE','CLOSE')])
    result.bars={symbol:object()for symbol in ['AP205.CZCE','SM205.CZCE']}
    result.context_calls=[];result.account_effects=[]
    return result


def delivery(request,folder,mode=None):
    rows=[dict(vt_symbol=item['vt_symbol'],bar_datetime=stamp,open=100.,high=101.,low=99.,close=100.,
        volume=10.,open_oi=20.,close_oi=21.)for item in request['requirements']for stamp in item['required_timestamps']]
    frame=pd.DataFrame(rows)
    if mode=='wrong_symbol':frame.loc[0,'vt_symbol']='WRONG.CZCE'
    path=(folder/'data.csv').resolve();frame.to_csv(path,index=False);digest=module.sha256(path)
    receipt=dict(schema='stage021_independent_minute_delivery_v1',independent_review=True,reviewer='synthetic_independent',
        qualified_research_data=mode!='unsigned',p0_findings=0,p1_findings=0,request_sha256=request['request_sha256'],
        data_path=str(path),data_sha256=digest,source_fingerprints={str(path):digest},accepted_requirements=[dict(
            vt_symbol=item['vt_symbol'],execution_trade_date=item['execution_trade_date'],requirement_kind=item['requirement_kind'],
            accepted_timestamps=item['required_timestamps'],accepted=True,completed_bars_and_daily_qualified=True)
            for item in request['requirements']])
    if mode=='wrong_request':receipt['request_sha256']='0'*64
    receipt_path=(folder/'review.json').resolve();module.write_json(receipt_path,receipt)
    result=module.QualifiedDelivery(receipt_path,module.sha256(receipt_path))
    if mode=='data_changed':path.write_text(path.read_text()+'\n')
    return result


class BlockingGateTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(module,'Stage021 not implemented')

    def test_two_orders_one_synchronous_resolver_then_original_each_once(self):
        target=engine();original_mapping=target.strategy.stage827_minute_by_symbol;calls=[];audit=[]
        old_frame=pd.DataFrame([dict(vt_symbol='AP205.CZCE',bar_datetime=pd.Timestamp('2022-04-06 09:00'),
            open=100.,high=101.,low=99.,close=100.,volume=10.,open_oi=20.,close_oi=21.)])
        original_mapping['AP205.CZCE']=old_frame
        original=FakeParentEngine._stage827_order_context
        with tempfile.TemporaryDirectory()as temporary:
            def resolve(request):
                self.assertEqual(target.account_effects,[]);self.assertEqual(target.context_calls,[])
                self.assertEqual(list(target.active_limit_orders),['o1','o2'])
                self.assertEqual(target.datetime,pd.Timestamp('2022-04-06'))
                self.assertEqual([(r['requirement_kind'],len(r['required_timestamps']))for r in request['requirements']],
                    [('full_session',225),('anchor',1)])
                self.assertEqual(module.request_sha256(request),request['request_sha256'])
                calls.append(request);return delivery(request,Path(temporary))
            with module.qualified_wait_scope(FakeInheritedEngine,resolve,audit):
                for order in target.active_limit_orders.values():target._stage827_order_context(order,target.bars[order.vt_symbol])
                self.assertEqual(len(target.strategy.stage827_minute_by_symbol['AP205.CZCE']),225)
                self.assertEqual(len(target.strategy.stage827_minute_by_symbol['SM205.CZCE']),1)
                self.assertIsNot(target.strategy.stage827_minute_by_symbol,original_mapping)
                self.assertIs(original_mapping['AP205.CZCE'],old_frame)
                self.assertEqual(len(old_frame),1)
                self.assertNotIn('SM205.CZCE',original_mapping)
            self.assertEqual(len(calls),1);self.assertEqual(target.context_calls,['o1','o2'])
            self.assertIs(target.strategy.stage827_minute_by_symbol,original_mapping)
            self.assertNotIn('_stage827_order_context',FakeInheritedEngine.__dict__)
            self.assertIs(FakeParentEngine._stage827_order_context,original)

    def test_unqualified_wrong_scope_or_hash_never_calls_original_and_restores(self):
        for mode in ['unsigned','wrong_request','wrong_symbol','data_changed']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory()as temporary:
                target=engine();mapping=target.strategy.stage827_minute_by_symbol
                with self.assertRaises(ValueError):
                    with module.qualified_wait_scope(FakeInheritedEngine,
                        lambda request:delivery(request,Path(temporary),mode),[]):
                        order=next(iter(target.active_limit_orders.values()))
                        target._stage827_order_context(order,target.bars[order.vt_symbol])
                self.assertEqual(target.context_calls,[]);self.assertEqual(target.account_effects,[])
                self.assertIs(target.strategy.stage827_minute_by_symbol,mapping)
                self.assertNotIn('_stage827_order_context',FakeInheritedEngine.__dict__)

    def test_old_value_conflict_and_resolver_exception_restore_local_method(self):
        class LocalEngine(FakeParentEngine):
            def _stage827_order_context(self,order,bar):return super()._stage827_order_context(order,bar)
        original=LocalEngine.__dict__['_stage827_order_context']
        with tempfile.TemporaryDirectory()as temporary:
            target=engine(LocalEngine)
            row=dict(vt_symbol='AP205.CZCE',bar_datetime=pd.Timestamp('2022-04-06 09:00'),
                open=100.,high=102.,low=99.,close=100.,volume=10.,open_oi=20.,close_oi=21.)
            target.strategy.stage827_minute_by_symbol['AP205.CZCE']=pd.DataFrame([row])
            mapping=target.strategy.stage827_minute_by_symbol
            with self.assertRaisesRegex(ValueError,'old_value_conflict'):
                with module.qualified_wait_scope(LocalEngine,lambda request:delivery(request,Path(temporary)),[]):
                    order=next(iter(target.active_limit_orders.values()))
                    target._stage827_order_context(order,target.bars[order.vt_symbol])
            self.assertEqual(mapping['AP205.CZCE'].iloc[0].high,102.)
            self.assertIs(LocalEngine.__dict__['_stage827_order_context'],original)
            with self.assertRaisesRegex(RuntimeError,'resolver_failed'):
                def fail(request):raise RuntimeError('resolver_failed')
                with module.qualified_wait_scope(LocalEngine,fail,[]):
                    target._stage827_order_context(order,target.bars[order.vt_symbol])
            self.assertIs(LocalEngine.__dict__['_stage827_order_context'],original)
            self.assertIs(target.strategy.stage827_minute_by_symbol,mapping)
            self.assertEqual(target.context_calls,[])

    def test_anchor_only_existing_qualification_never_grants_full_scan(self):
        target=engine();target.active_limit_orders.pop('o2');order=target.active_limit_orders['o1']
        grid=pd.date_range('2022-04-06 09:00',periods=75,freq='min').append(
            pd.date_range('2022-04-06 10:30',periods=60,freq='min')).append(
            pd.date_range('2022-04-06 13:30',periods=90,freq='min'))
        target.strategy.stage827_minute_by_symbol['AP205.CZCE']=pd.DataFrame([dict(vt_symbol='AP205.CZCE',
            bar_datetime=t,open=100.,high=101.,low=99.,close=100.,volume=10.,open_oi=20.,close_oi=21.)for t in grid])
        common=lambda symbol,stamp:stamp!=grid[0]
        anchor=lambda symbol,stamp:stamp==grid[0]
        def must_wait(request):raise RuntimeError('full_must_not_borrow_anchor_only')
        with self.assertRaisesRegex(RuntimeError,'full_must_not_borrow_anchor_only'):
            with module.qualified_wait_scope(FakeInheritedEngine,must_wait,[],qualified_existing_keys=common,
                qualified_anchor_existing_keys=anchor):
                target._stage827_order_context(order,target.bars[order.vt_symbol])
        order.offset='CLOSE'
        with module.qualified_wait_scope(FakeInheritedEngine,must_wait,[],qualified_existing_keys=common,
            qualified_anchor_existing_keys=anchor):
            target._stage827_order_context(order,target.bars[order.vt_symbol])
        self.assertEqual(target.context_calls,['o1'])


if __name__=='__main__':unittest.main()
