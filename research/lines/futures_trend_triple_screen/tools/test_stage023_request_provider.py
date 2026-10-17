"""Exact request bounds, purpose-specific quality and daily-reference gates."""
from pathlib import Path
import tempfile
import unittest
import pandas as pd
import stage021_blocking_data_gate as gate
import stage002_local_minute_overlay as old

try:import stage023_request_provider as module
except ImportError:module=None


def request(symbols,day,calendar,kind='full_session'):
    requirements=[]
    for symbol in symbols:
        grid=old.session_grid(symbol,day,calendar)
        stamps=[stamp.isoformat()for stamp in(grid if kind=='full_session'else grid[:1])]
        requirements.append(dict(vt_symbol=symbol,execution_trade_date=day,requirement_kind=kind,
            required_timestamps=stamps,missing_or_unqualified_timestamps=stamps,existing_source_timestamps=[]))
    result=dict(schema=gate.REQUEST_SCHEMA,request_sequence=1,execution_trade_date=day,
        requirements=requirements,active_orders=[dict(order_id=str(i),vt_symbol=s,requirement_kind=kind)for i,s in enumerate(symbols)])
    result['request_sha256']=gate.request_sha256(result);return result


class RequestProviderTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(module,'Stage023 not implemented')
        self.calendar=pd.to_datetime(['2020-08-11','2020-08-12','2020-08-13'])

    def test_packet_has_at_most8_and_never_claims_whole_request(self):
        value=request([f'AP20{i}.CZCE'for i in range(9)],'2020-08-12',self.calendar)
        selected,info=module.packet_targets(value,self.calendar,0)
        self.assertEqual(len(selected),8);self.assertEqual(info['packet_count'],2)
        self.assertFalse(info['covers_whole_request'])
        second,info=module.packet_targets(value,self.calendar,1);self.assertEqual(len(second),1)
        self.assertEqual(info['provider_start'],'2020-08-13T09:01:00')
        value['requirements'][0]['required_timestamps'].pop()
        value['request_sha256']=gate.request_sha256(value)
        with self.assertRaisesRegex(ValueError,'canonical_grid'):
            module.packet_targets(value,self.calendar,0)

    def test_missing_next_mapping_day_and_wrong_file_hash_refuse(self):
        value=request(['AP201.CZCE'],'2020-08-13',self.calendar,'anchor')
        with self.assertRaisesRegex(ValueError,'next_mapping_trade_date_missing'):
            module.packet_targets(value,self.calendar,0)
        with tempfile.TemporaryDirectory()as temporary:
            folder=Path(temporary)/('request_'+value['request_sha256']);folder.mkdir()
            path=folder/'request.json';old.write_json(path,value)
            old.write_json(folder/'request_fingerprint.json',dict(request_sha256=value['request_sha256'],
                request_file_sha256=old.sha256(path),request_path=str(path.resolve())))
            with self.assertRaisesRegex(ValueError,'request_file_sha'):
                module.read_request(path,'0'*64,fixture_root=Path(temporary))
            self.assertEqual(module.read_request(path,old.sha256(path),fixture_root=Path(temporary))[0]['request_sha256'],value['request_sha256'])

    def test_anchor_matches_raw_open_and_openOI_without_full_qualification(self):
        stamp=pd.Timestamp('2020-08-12 09:00')
        raw=pd.DataFrame([dict(vt_symbol='AP201.CZCE',bar_datetime=stamp,open=100.,high=101.,low=99.,close=100.,
            volume=1.,open_oi=20.,close_oi=21.)])
        proofs={('AP201.CZCE',stamp)}
        target=dict(vt_symbol='AP201.CZCE',execution_trade_date='2020-08-12',requirement_kind='anchor',
            required_timestamps=[stamp.isoformat()],daily_reference=dict(open=100.,open_oi=20.,high=1000.))
        check=module.qualify_target(raw,proofs,target)
        self.assertTrue(check['accepted']);self.assertEqual(check['qualification_kind'],'anchor_only_not_full_session')
        raw.loc[0,'open']=100.5
        self.assertFalse(module.qualify_target(raw,proofs,target)['accepted'])
        self.assertFalse(module.qualify_target(raw,set(),target)['accepted'])

    def test_rejected_or_uncompleted_daily_cannot_fallback(self):
        daily=pd.DataFrame([dict(trade_date='2020-08-12',**{name:1. for name in old.VALUES})])
        key=('AP201.CZCE','2020-08-12')
        with self.assertRaisesRegex(ValueError,'daily_not_completed'):
            module.choose_daily_reference(*key,'anchor',daily,{},set())
        with self.assertRaisesRegex(ValueError,'explicitly_rejected_daily'):
            module.choose_daily_reference(*key,'anchor',daily,{key:{name:1. for name in old.VALUES}},{key})
        ref,source=module.choose_daily_reference(*key,'full_session',None,{key:{name:1. for name in old.VALUES}},set())
        self.assertEqual(source,'reviewed_stage013_daily');self.assertEqual(ref['open'],1.)


if __name__=='__main__':unittest.main()
