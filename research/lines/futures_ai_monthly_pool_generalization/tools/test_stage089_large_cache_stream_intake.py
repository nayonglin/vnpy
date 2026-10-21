import hashlib,tempfile,unittest
from pathlib import Path
import pandas as pd
from stage089_large_cache_stream_intake import stream_file,qualify_snapshot

def spec():
 return {'rid':'r','native':'cf905.czce','day':'2019-03-08','previous':'2019-03-07','listed':'2018-01-01','delisted':'2019-05-31','epoch':'CZCE.CF.201905'}
def frame(times,provider='a'):
 return pd.DataFrame({'vt_symbol':['CF905.CZCE']*len(times),'bar_datetime':times,'open':['100']*len(times),'high':['101']*len(times),'low':['99']*len(times),'close':['100']*len(times),'minute_source':[provider]*len(times)})
def runframes(f,chunksize=2,specs=None):
 with tempfile.TemporaryDirectory() as d:
  p=Path(d)/'x.csv';f.to_csv(p,index=False);b=p.read_bytes();result=stream_file(p,[spec()] if specs is None else specs,chunksize)
  assert result['io']['payload_sha256']==hashlib.sha256(b).hexdigest() and result['io']['bytes_read']==len(b)
  return result
class StreamIntakeTests(unittest.TestCase):
 def test_one_stream_hash_with_small_chunks_and_provider_preservation(self):
  r=runframes(frame(['2019-03-07 21:00','2019-03-08 09:00','2019-03-08 15:00']))
  self.assertEqual(r['io']['chunks'],2);self.assertEqual(len(r['matched'][('r','a')]),3)
 def test_duplicate_across_chunk_boundary_is_preserved(self):
  r=runframes(frame(['2019-03-07 21:00','2019-03-08 09:00','2019-03-08 09:00']))
  self.assertEqual(len(r['matched'][('r','a')]),3);self.assertEqual(r['matched'][('r','a')].local_datetime.duplicated().sum(),1)
 def test_no_midnight_or_natural_day_shortcut(self):
  r=runframes(frame(['2019-03-07 21:00','2019-03-08 00:01','2019-03-08 15:01']))
  self.assertEqual(len(r['matched'][('r','a')]),2)
 def test_exact_native_not_product_and_lifetime_not_guessed(self):
  f=frame(['2019-03-08 09:00']*2);f.loc[1,'vt_symbol']='CF909.CZCE';s=spec();s['listed']='2019-03-08'
  f.loc[0,'bar_datetime']='2019-03-07 21:00';r=runframes(f,specs=[s]);self.assertEqual(len(r['matched'][('r','a')]),1);self.assertFalse(r['matched'][('r','a')].metadata_lifetime_valid.iloc[0])
 def test_provider_split_never_fills_missing_other_source(self):
  f=pd.concat([frame(['2019-03-07 21:00'],'a'),frame(['2019-03-08 09:00'],'b')],ignore_index=True);r=runframes(f)
  self.assertEqual(set(r['matched']),{('r','a'),('r','b')});self.assertEqual(len(r['matched'][('r','a')]),1)
 def test_invalid_native_timestamp_is_retained_without_assigning_day(self):
  r=runframes(frame(['bad','2019-03-08 09:00']));self.assertEqual(len(r['invalid_timestamp_rows']),1);self.assertEqual(r['invalid_counts'][('cf905.czce','a')],1)
 def test_blank_source_is_consistently_unspecified(self):
  r=runframes(frame(['2019-03-08 09:00'],''));self.assertIn(('r','__unspecified__'),r['matched'])
 def test_fullgrid_rejects_crosschunk_missing_night_and_duplicate(self):
  r=runframes(frame(['2019-03-08 09:00','2019-03-08 09:00']));p=r['matched'][('r','a')]
  req=dict(contract_epoch_id='CZCE.CF.201905',source_trade_date='2019-03-08',exchange='CZCE',product='CF',entry_price=100,source_open=100,source_high=101,source_low=99,source_close=100)
  binding=dict(contract_epoch_id=req['contract_epoch_id'],source_trade_date=req['source_trade_date'],source_id='a',identity_basis='fixture',component='a')
  expected=pd.DatetimeIndex(['2019-03-07 21:00','2019-03-08 09:00']);out=qualify_snapshot(p,expected,req,binding,0);self.assertEqual(out['status'],'duplicate_minute')
  out=qualify_snapshot(p.iloc[:1],expected,req,binding,0);self.assertEqual(out['status'],'incomplete_grid')
 def test_invalid_epoch_row_and_unassignable_time_cannot_qualify(self):
  r=runframes(frame(['2019-03-08 09:00']));p=r['matched'][('r','a')];req=dict(contract_epoch_id='CZCE.CF.201905',source_trade_date='2019-03-08',exchange='CZCE',product='CF');binding=dict(contract_epoch_id=req['contract_epoch_id'],source_trade_date=req['source_trade_date'],source_id='a',identity_basis='fixture',component='a')
  p.loc[:,'explicit_identity_valid']=False
  self.assertEqual(qualify_snapshot(p,pd.DatetimeIndex(['2019-03-08 09:00']),req,binding,0)['status'],'explicit_row_identity_mismatch')
  self.assertEqual(qualify_snapshot(p,pd.DatetimeIndex(['2019-03-08 09:00']),req,binding,1)['status'],'native_component_invalid_timestamp_unassignable')

 def test_wrapper_rejects_original_mixed_or_wrong_provider(self):
  req=dict(contract_epoch_id='CZCE.CF.201905',source_trade_date='2019-03-08',exchange='CZCE',product='CF',entry_price=100,source_open=100,source_high=101,source_low=99,source_close=100)
  binding=dict(contract_epoch_id=req['contract_epoch_id'],source_trade_date=req['source_trade_date'],source_id='a',identity_basis='fixture',component='a')
  p=runframes(frame(['2019-03-07 21:00','2019-03-08 09:00']))['matched'][('r','a')]
  expected=pd.DatetimeIndex(p.local_datetime)
  p.loc[1,'minute_source']='b'
  self.assertEqual(qualify_snapshot(p,expected,req,binding,0)['status'],'mixed_source_components')
  p.loc[:,'minute_source']='b'
  self.assertEqual(qualify_snapshot(p,expected,req,binding,0)['status'],'source_component_mismatch')
