"""Only the new B owner/schema and sealed-only export boundary."""
from copy import deepcopy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import test_stage028_ordered_engine as producer
import pandas as pd

SOURCE=Path(__file__).with_name('stage036_run_b_ts_checkpoint.py')

def load_runner():
    if not SOURCE.is_file():return None
    spec=importlib.util.spec_from_file_location('stage036_fixture_runner',SOURCE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def tiny_actual_producer(runner):
    engine=producer.engine();symbol='AP605.CZCE'
    engine.strategy.ts_pending_intents=[producer.intent()]
    engine.strategy.synthetic_symbol=symbol
    engine.strategy.stage827_minute_by_symbol[symbol]=producer.minutes(symbol,{1:dict(open=100.,high=102.,low=98.,close=100.)})
    engine.cross_delayed_orders();actual=engine.get_all_trades()
    assert len(actual)==2 and actual[1].intraday_episode_id==actual[0].vt_tradeid
    clock=[dict(trade_id=t.vt_tradeid,vt_symbol=t.vt_symbol,direction=t.direction.value,offset=t.offset.value,
        price=float(t.price),volume=float(t.volume),engine_datetime=str(t.datetime),execution_datetime=str(t.execution_datetime),
        trading_date=str(t.trading_date),exit_reason=getattr(t,'exit_reason',''))for t in actual]
    capture=dict(trades=clock,usage=deepcopy(engine.trade_usage_rows),equity=[],minute_requests=[],anchor_requests=[],failures=[])
    return capture,runner.actual_trade_identities(actual)

class BOwnedCheckpoint(unittest.TestCase):
    def test_b_manifest_real_identity_and_c_owner_cannot_mix(self):
        runner=load_runner();self.assertIsNotNone(runner,'B checkpoint runner is not implemented')
        with tempfile.TemporaryDirectory()as folder,patch.object(runner,'OUTPUT',Path(folder)/'owned'):
            output=runner.OUTPUT/'B_TS';output.mkdir(parents=True)
            (output/'runner_used.py').write_bytes(SOURCE.read_bytes());context=runner.new_run_context(output,datetime.now().astimezone())
            self.assertEqual((context['arm'],context['attempt'],context['writer']),('B_TS',1,'stage036_run_b_ts_checkpoint.py'))
            runner.prior.atomic_json(output/'run_context.json',context)
            capture,identities=tiny_actual_producer(runner)
            manifest=runner.save_raw_checkpoint(output,dict(run_context=context,capture=capture,actual_trade_identities=identities))
            runner.seal_checkpoint(output,manifest,dict(runner.ENGINE_VALIDATION,fixture_only=True))
            payload,binding=runner.load_sealed_checkpoint(output)
            self.assertEqual(payload['schema'],'stage036_raw_account_checkpoint_v1')
            clock,usage=runner.build_execution_clock(payload['capture'],payload['actual_trade_identities'])
            self.assertEqual(len(clock),2);self.assertEqual(clock.signal_order_id.nunique(),1)
            with self.assertRaisesRegex(ValueError,'owned'):runner.load_sealed_checkpoint(runner.OUTPUT/'C_TS')
            path=output/'checkpoint/raw_manifest.json';broken=json.loads(path.read_text());broken['arm']='C_TS';path.write_text(json.dumps(broken))
            with patch.object(runner.pickle,'loads',side_effect=AssertionError('C mix must fail before deserialize')):
                with self.assertRaises(ValueError):runner.load_sealed_checkpoint(output)

    def test_b_failed_export_uses_same_sealed_raw_without_engine_or_data_reload(self):
        runner=load_runner();self.assertIsNotNone(runner,'B checkpoint runner is not implemented')
        with tempfile.TemporaryDirectory()as folder,patch.object(runner,'OUTPUT',Path(folder)/'owned'):
            output=runner.OUTPUT/'B_TS';output.mkdir(parents=True)
            (output/'runner_used.py').write_bytes(SOURCE.read_bytes());context=runner.new_run_context(output,datetime.now().astimezone())
            runner.prior.atomic_json(output/'run_context.json',context)
            capture,identities=tiny_actual_producer(runner)
            frame=pd.DataFrame({'date':pd.to_datetime(['2026-01-07']),'net_pnl':[.1],'trade_count':[2]})
            payload=dict(combined=frame,frames={'trades':pd.DataFrame(capture['trades']).assign(datetime=[x['engine_datetime']for x in capture['trades']])},
                capture=capture,actual_trade_identities=identities,ordered=dict(decision=[],fill=[],execution=[],pending=[]),actual=[],parameters={},
                spec={'capital':{}},preflight={},input_fingerprints={},run_context=context)
            manifest=runner.save_raw_checkpoint(output,payload);runner.seal_checkpoint(output,manifest,dict(runner.ENGINE_VALIDATION,fixture_only=True))
            for name in('protocol_used.md','entry_contract_used.md','plan_used.md','holding_contract_used.md','data_stack_manifest.json',
                         'stage028_ordered_strategy.py','stage028_ordered_engine.py','preflight_used.json',*runner.FROZEN_MODULES):
                if name!='runner_used.py':(output/name).write_text('{}')
            failure=output/'run_failure.json';failure.write_text('{"error":"old pure export sentinel"}');old=failure.read_bytes()
            first=runner.reserve_export_destination(output)
            def fail(*a):raise RuntimeError('metrics sentinel')
            with patch.object(runner.prior,'read_data_stack',side_effect=AssertionError('no market reload')),patch.object(producer.native.s827.Stage827IntradayC2Engine,'run_backtesting',side_effect=AssertionError('no replay')):
                with self.assertRaisesRegex(RuntimeError,'metrics sentinel'):runner.export_checkpoint(output,first,metrics_function=fail,export_only=True)
                (first/'export_failure.json').write_text('{"error":"metrics sentinel"}')
                second=runner.reserve_export_destination(output);result=runner.export_checkpoint(output,second,metrics_function=lambda*a:{'fixture':True},export_only=True)
            self.assertEqual(result['arm'],'B_TS');self.assertEqual(result['financial_replays_this_export_process'],0)
            self.assertEqual(runner.sha256(output/'checkpoint/raw_account.pkl.gz'),manifest['raw_sha256'])
            self.assertEqual(failure.read_bytes(),old);self.assertTrue((first/'export_failure.json').exists())
            with self.assertRaises(FileExistsError):runner.reserve_export_destination(output)

if __name__=='__main__':unittest.main()
