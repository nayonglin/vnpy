"""Only new actual-producer identity and durable-export recovery boundaries."""
from copy import deepcopy
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

# Reuse the tiny real-827 producer fixture, without running its old test suite.
import test_stage028_ordered_engine as producer
import pandas as pd
import stage031_run_ordered_checkpoint as runner


def real_synthetic_payload():
    target=producer.engine()
    symbol='AP605.CZCE'
    target.strategy.ts_pending_intents=[producer.intent()]
    target.strategy.synthetic_symbol=symbol
    target.strategy.stage827_minute_by_symbol[symbol]=producer.minutes(symbol,{
        1:dict(open=100.0,high=102.0,low=98.0,close=100.0)})
    target.cross_delayed_orders()
    trades=target.get_all_trades()
    assert len(trades)==2 and trades[1].intraday_episode_id==trades[0].vt_tradeid
    identities=runner.actual_trade_identities(trades)
    clock=[dict(trade_id=t.vt_tradeid,vt_symbol=t.vt_symbol,direction=t.direction.value,
        offset=t.offset.value,price=float(t.price),volume=float(t.volume),engine_datetime=str(t.datetime),
        execution_datetime=str(t.execution_datetime),trading_date=str(t.trading_date),exit_reason=getattr(t,'exit_reason',''))for t in trades]
    return dict(trades=clock,usage=deepcopy(target.trade_usage_rows),equity=[],minute_requests=[],anchor_requests=[],failures=[]),identities


class ActualProducerIdentity(unittest.TestCase):
    def test_real_827_synthetic_missing_usage_identity_uses_actual_trade(self):
        capture,identities=real_synthetic_payload()
        self.assertNotIn('signal_datetime',capture['usage'][1])
        self.assertNotIn('signal_order_id',capture['usage'][1])
        clock,usage=runner.build_execution_clock(capture,identities)
        self.assertEqual(clock.signal_datetime.tolist(),['2026-01-06T00:00:00']*2)
        self.assertEqual(clock.signal_order_id.nunique(),1)
        self.assertEqual(clock.iloc[1].intraday_episode_id,identities[0]['trade_id'])
        self.assertEqual(usage.iloc[1].signal_order_id,clock.iloc[0].signal_order_id)
        self.assertNotIn('signal_datetime',capture['usage'][1])

    def test_actual_identity_conflicts_missing_parent_and_wrong_day_rejected(self):
        capture,identities=real_synthetic_payload()
        mutations=[]
        wrong=deepcopy(capture);wrong['usage'][0]['signal_datetime']='2026-01-05';mutations.append((wrong,identities))
        wrong=deepcopy(identities);wrong[1]['intraday_episode_id']='missing';mutations.append((capture,wrong))
        wrong=deepcopy(identities);wrong[1]['trading_date']='2026-01-08';mutations.append((capture,wrong))
        wrong=deepcopy(identities);wrong[0]['signal_datetime']=None;mutations.append((capture,wrong))
        wrong=deepcopy(identities);wrong[1]['execution_datetime']=datetime(2026,1,7,8);mutations.append((capture,wrong))
        for c,i in mutations:
            with self.subTest(case=len(i)),self.assertRaises(ValueError):runner.build_execution_clock(c,i)


class DurableCheckpoint(unittest.TestCase):
    def test_exact_dataframe_checkpoint_recovers_after_export_failure_and_rejects_external_or_tamper(self):
        with tempfile.TemporaryDirectory()as folder,patch.object(runner,'OUTPUT',Path(folder)/'owned'):
            output=runner.OUTPUT/'C_TS';output.mkdir(parents=True)
            (output/'runner_used.py').write_bytes(Path(runner.__file__).read_bytes())
            context=runner.new_run_context(output,datetime.now().astimezone())
            runner.prior.atomic_json(output/'run_context.json',context)
            capture,identities=real_synthetic_payload()
            frame=pd.DataFrame({'date':pd.to_datetime(['2026-01-07']),'net_pnl':[0.1],
                                'trade_count':pd.Series([2],dtype='int64')})
            payload=dict(combined=frame,frames={'trades':pd.DataFrame(capture['trades']).assign(datetime=[row['engine_datetime']for row in capture['trades']])},capture=capture,
                actual_trade_identities=identities,ordered=dict(decision=[],fill=[],execution=[],pending=[]),actual=[],
                parameters={},spec={'capital':{}},preflight={},input_fingerprints={},run_context=context)
            manifest=runner.save_raw_checkpoint(output,payload)
            self.assertFalse((output/'checkpoint/validation_seal.json').exists())
            with self.assertRaisesRegex(ValueError,'unsealed'):runner.load_sealed_checkpoint(output)
            runner.seal_checkpoint(output,manifest,dict(runner.ENGINE_VALIDATION,fixture_only=True))
            loaded,receipt=runner.load_sealed_checkpoint(output)
            pd.testing.assert_frame_equal(loaded['combined'],frame,check_exact=True)
            self.assertEqual(loaded['combined'].net_pnl.iloc[0].hex(),frame.net_pnl.iloc[0].hex())
            for name in('protocol_used.md','entry_contract_used.md','plan_used.md','holding_contract_used.md',
                         'data_stack_manifest.json','stage028_ordered_strategy.py','stage028_ordered_engine.py','preflight_used.json'):
                (output/name).write_text('{}')
            failure=output/'run_failure.json';failure.write_text('{"error":"original postprocess failure"}')
            original_failure=failure.read_bytes()
            first=runner.reserve_export_destination(output)
            def broken_metrics(*args):raise RuntimeError('postprocess sentinel')
            with patch.object(runner.prior,'read_data_stack',side_effect=AssertionError('no whole-data qualification')),                 patch.object(producer.native.s827.Stage827IntradayC2Engine,'run_backtesting',side_effect=AssertionError('no replay')):
                with self.assertRaisesRegex(RuntimeError,'postprocess sentinel'):
                    runner.export_checkpoint(output,first,metrics_function=broken_metrics,export_only=True)
                runner.write_json(first/'export_failure.json',{'error':'postprocess sentinel'})
                restored,_=runner.load_sealed_checkpoint(output)
                clock,usage=runner.build_execution_clock(restored['capture'],restored['actual_trade_identities'])
                self.assertEqual(len(clock),2)
                second=runner.reserve_export_destination(output)
                summary=runner.export_checkpoint(output,second,metrics_function=lambda *args:{'fixture':True},export_only=True)
            self.assertNotEqual(first,second)
            self.assertEqual(summary['financial_replays_this_export_process'],0)
            self.assertEqual(summary['result_origin'],'same_engine_sealed_account_snapshot')
            self.assertEqual(failure.read_bytes(),original_failure)
            self.assertTrue((first/'export_failure.json').exists())
            self.assertEqual(runner.sha256(output/'checkpoint/raw_account.pkl.gz'),manifest['raw_sha256'])
            with self.assertRaises(FileExistsError):runner.reserve_export_destination(output)
            with self.assertRaisesRegex(ValueError,'owned'):runner.load_sealed_checkpoint(Path(folder)/'outside')
            raw=output/'checkpoint/raw_account.pkl.gz';raw.write_bytes(raw.read_bytes()+b'x')
            with patch.object(runner.pickle,'loads',side_effect=AssertionError('must not deserialize')):
                with self.assertRaisesRegex(ValueError,'sha'):runner.load_sealed_checkpoint(output)

if __name__=='__main__':unittest.main()
