"""Small runner boundary tests; no frozen runtime or financial replay."""
from datetime import datetime
from enum import Enum
import importlib.util
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

MODULE=Path(__file__).with_name('stage028_run_ordered.py')
spec=importlib.util.spec_from_file_location('stage028_run_ordered',MODULE)
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class Offset(Enum): OPEN='open'
class Direction(Enum): LONG='long'; SHORT='short'

class RunnerBoundaries(unittest.TestCase):
    def test_intent_qualification_is_full_open_without_registering_order(self):
        calls=[]
        gate=SimpleNamespace(ensure=lambda *args:calls.append(args))
        qualify=runner.build_qualification_callback({'gate':gate},Offset,Direction)
        engine=SimpleNamespace(active_limit_orders={})
        bar=object()
        item=dict(intent_id='i-1',contract='x.DCE',direction=1,trigger=101.0,
                  plan=dict(volume=3))
        qualify(engine,item,bar)
        self.assertEqual(engine.active_limit_orders,{})
        stub=calls[0][1]
        self.assertIs(calls[0][0],engine)
        self.assertIs(calls[0][2],bar)
        self.assertIs(stub.offset,Offset.OPEN)
        self.assertIs(stub.direction,Direction.LONG)
        self.assertEqual((stub.vt_orderid,stub.volume,stub.traded),('TS.INTENT.i-1',3,0))
        self.assertEqual(stub.status,'conditional_not_order')

    def test_invalid_or_unbound_intent_fails_closed(self):
        qualify=runner.build_qualification_callback({},Offset,Direction)
        with self.assertRaisesRegex(RuntimeError,'gate_not_bound'):
            qualify(object(),{},object())
        qualify=runner.build_qualification_callback({'gate':object()},Offset,Direction)
        for direction,volume in [(0,1),(1,0),(1,1.5)]:
            with self.assertRaises(ValueError):
                qualify(object(),dict(intent_id='i',contract='x.DCE',direction=direction,
                                     trigger=101.0,plan=dict(volume=volume)),object())

    def test_engine_replacement_restores_on_failure(self):
        original=type('Original',(),{})
        replacement=type('Replacement',(),{})
        module=SimpleNamespace(Stage847StopRetryEngine=original)
        with self.assertRaisesRegex(RuntimeError,'probe'):
            with runner.replace_engine_class(module,replacement):
                self.assertIs(module.Stage847StopRetryEngine,replacement)
                raise RuntimeError('probe')
        self.assertIs(module.Stage847StopRetryEngine,original)

    def test_actual_calendar_requires_complete_ordered_identity(self):
        runner.validate_daily_calendar(['2020-01-02','2020-01-03'],['2020-01-02','2020-01-03'])
        for dates in (['2020-01-02'],['2020-01-03','2020-01-02'],['2020-01-02','2020-01-02']):
            with self.assertRaisesRegex(ValueError,'actual_daily_calendar'):
                runner.validate_daily_calendar(dates,['2020-01-02','2020-01-03'])

    def test_capture_collects_audits_even_when_run_raises(self):
        class Engine:
            def new_bars(self,stamp):raise RuntimeError('bar fail')
            def calculate_result(self):return 'done'
        original_new_bars=Engine.new_bars
        original_calculate=Engine.calculate_result
        engine=Engine()
        engine.strategy=SimpleNamespace(ts_decision_audit=[{'decision':'blocked'}],ts_fill_audit=[])
        engine.ts_execution_audit=[{'event':'qualified'}]
        with self.assertRaisesRegex(RuntimeError,'bar fail'):
            with runner.capture_ordered_engine(Engine) as captured:
                engine.new_bars(datetime(2020,1,2))
        self.assertEqual(captured['decision'],[{'decision':'blocked'}])
        self.assertEqual(captured['execution'],[{'event':'qualified'}])
        self.assertEqual(captured['fill'],[])
        self.assertIs(Engine.new_bars,original_new_bars)
        self.assertIs(Engine.calculate_result,original_calculate)


    def test_pending_projection_handles_real_dataframe_and_bar_without_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            previous_output=runner.prior.OUTPUT
            try:
                runner.prior.OUTPUT=Path(folder)/'output'
                runner.prior.configure_runtime(Path(folder)/'shared')
            finally:runner.prior.OUTPUT=previous_output
            import pandas as pd
            from vnpy.trader.constant import Exchange,Interval
            from vnpy.trader.object import BarData
            bar=BarData(symbol='m2501',exchange=Exchange.DCE,datetime=datetime(2025,1,2),
                        interval=Interval.DAILY,open_price=100,high_price=102,low_price=99,
                        close_price=101,gateway_name='TEST')
            history=pd.DataFrame({'close':[99.0,101.0]})
            prior_history=history.copy(deep=True)
            item=dict(arm='C_TS',intent_id='pending',product='m.DCE',contract='m2501.DCE',
                      direction=1,trigger=103.0,rank=2,plan=dict(target_bar=bar,history=history,
                      volume=3,direction='long',signal='long_test',target_contract='m2501.DCE',
                      sizing=dict(selected_volume=3,stop_price=98.0,risk_per_contract=50.0,
                                  margin_per_contract=1000.0,estimated_equity=150000.0,native_object=history)))
            class Engine:
                def new_bars(self,stamp):raise RuntimeError('timeout sentinel')
                def calculate_result(self):return None
            engine=Engine()
            engine.strategy=SimpleNamespace(ts_pending_intents=[item],ts_decision_audit=[],ts_fill_audit=[])
            with self.assertRaisesRegex(RuntimeError,'timeout sentinel'):
                with runner.capture_ordered_engine(Engine)as captured:engine.new_bars(datetime(2025,1,3))
            json.dumps(runner.json_safe(captured),allow_nan=False)
            snapshot=captured['pending'][0]['frozen_plan']
            self.assertEqual(snapshot['sizing']['stop_price'],98.0)
            self.assertEqual(snapshot['volume'],3)
            self.assertEqual(snapshot['signal_history_rows'],2)
            self.assertNotIn('history',snapshot)
            self.assertNotIn('target_bar',snapshot)
            self.assertIs(item['plan']['target_bar'],bar)
            self.assertIs(item['plan']['history'],history)
            self.assertTrue(history.equals(prior_history))

if __name__=='__main__':unittest.main()
