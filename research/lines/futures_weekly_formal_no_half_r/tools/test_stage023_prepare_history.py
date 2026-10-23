"""Pure data assembly tests: no engine, market API, credentials or financial replay."""
import hashlib,importlib.util,sqlite3,tempfile,unittest
from pathlib import Path
import pandas as pd
try:
 import stage023_prepare_history as h
except ImportError:
 h=None

class PrepareHistoryTests(unittest.TestCase):
 def api(self):
  self.assertIsNotNone(h,'stage023 assembler not implemented');return h
 def epoch(self,year='201505',listed='2014-08-08',delisted='2015-05-15'):
  return dict(contract_epoch_id='CZCE.SM.'+year,exchange='CZCE',product='SM',contract_yyyymm=year,listed_date=listed,delisted_date=delisted,maturity_date=delisted,metadata_status='verified_fixture')
 def clean(self,day='2015-01-05'):
  return dict(contract_epoch_id='CZCE.SM.201505',exchange='CZCE',product='SM',source_symbol='SM1505',contract_yyyymm='201505',trade_date=day,open=6000.,high=6050.,low=5900.,close=5950.,volume=20.,close_oi=101.,open_oi=999.,open_interest=999.,quality_status='accepted',source_id='fixture',source_locator='row1',volume_factor=.5,oi_factor=.5)
 def rows(self):
  mod=self.api();idx=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE']);return mod.clean_bars(pd.DataFrame([self.clean()]),idx,['SM.CZCE'])[0]
 def test_clean_close_oi_never_open_oi_or_scaled_twice(self):
  a=self.rows().iloc[0];self.assertEqual(a.vt_symbol,'SM505.CZCE');self.assertEqual(a.volume,20.);self.assertEqual(a.close_oi,101.)
 def test_zero_volume_cannot_be_accepted(self):
  mod=self.api();row=self.clean();row['volume']=0
  with self.assertRaisesRegex(ValueError,'invalid_daily'):
   mod.clean_bars(pd.DataFrame([row]),mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE']),['SM.CZCE'])
 def test_ohlc_outside_high_low_rejected(self):
  mod=self.api();row=self.clean();row['close']=6100
  with self.assertRaisesRegex(ValueError,'invalid_daily'):
   mod.clean_bars(pd.DataFrame([row]),mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE']),['SM.CZCE'])
 def test_nonaccepted_row_not_imported(self):
  mod=self.api();row=self.clean();row['quality_status']='quarantine';bars,rejected=mod.clean_bars(pd.DataFrame([row]),mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE']),['SM.CZCE']);self.assertEqual(len(bars),0)
 def test_native_decade_disambiguated_by_physical_epoch(self):
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch(),self.epoch('202505','2024-05-20','2025-05-19')]),['SM.CZCE']);self.assertEqual(mod.bind_epoch('SM505.CZCE','2015-01-05',index)['contract_epoch_id'],'CZCE.SM.201505');self.assertEqual(mod.bind_epoch('SM505.CZCE','2025-01-06',index)['contract_epoch_id'],'CZCE.SM.202505')
 def test_known_lifecycle_out_of_bounds_rejected(self):
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE'])
  with self.assertRaisesRegex(ValueError,'epoch'):
   mod.bind_epoch('SM505.CZCE','2015-05-19',index,explicit='CZCE.SM.201505')
 def test_ambiguous_native_identity_rejected(self):
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch(),self.epoch('202505','2014-05-20','2025-05-19')]),['SM.CZCE'])
  with self.assertRaisesRegex(ValueError,'ambiguous'):
   mod.bind_epoch('SM505.CZCE','2015-01-05',index)
 def test_unknown_future_full_lifecycle_keeps_explicit_real_identity(self):
  mod=self.api();e=dict(contract_epoch_id='SHFE.AU.202701',exchange='SHFE',product='AU',contract_yyyymm='202701',listed_date=None,delisted_date=None,maturity_date=None,metadata_status='symbol_only');index=mod.epoch_index(pd.DataFrame([e]),['au.SHFE']);got=mod.bind_epoch('au2701.SHFE','2026-10-15',index,explicit='SHFE.AU.202701');self.assertIsNone(got['listed_date']);self.assertEqual(got['lifecycle_status'],'observed_bar_identity_known_full_lifecycle_unknown')
 def test_existing_clean_key_conflict_fails_not_old_first(self):
  mod=self.api();a=self.rows();b=a.copy();b.loc[0,'close_oi']=102
  with self.assertRaisesRegex(ValueError,'conflict'):mod.merge_bars([a,b])
 def test_identical_overlap_deduplicated_and_counted(self):
  mod=self.api();a=self.rows();got,n=mod.merge_bars([a,a.copy()]);self.assertEqual(len(got),1);self.assertEqual(n,1)
 def test_mapping_conflict_fails(self):
  mod=self.api();a=pd.DataFrame([dict(date='2026-10-23',continuous_symbol_vt='SM.CZCE',main_contract_vt='SM701.CZCE')]);b=a.copy();b.loc[0,'main_contract_vt']='SM705.CZCE'
  with self.assertRaisesRegex(ValueError,'mapping_conflict'):mod.merge_mapping(a,b)
 def test_missing_main_is_not_silently_dropped(self):
  mod=self.api();mapping=pd.DataFrame([dict(date='2015-01-05',continuous_symbol_vt='SM.CZCE',main_contract_vt='SM505.CZCE'),dict(date='2015-01-06',continuous_symbol_vt='SM.CZCE',main_contract_vt='SM505.CZCE'),dict(date='2015-01-05',continuous_symbol_vt='AP.CZCE',main_contract_vt='')]);got=mod.missing_main(mapping,self.rows(),['SM.CZCE','AP.CZCE'],'2015-01-01','2026-10-23');self.assertEqual(got[['date','main_contract_vt']].to_dict('records'),[{'date':'2015-01-06','main_contract_vt':'SM505.CZCE'}])
 def test_database_copy_isolates_old_contract_but_preserves_sentinels(self):
  mod=self.api()
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'source.sqlite';dst=Path(d)/'new.sqlite';db=sqlite3.connect(src);db.execute('create table dbbardata(id integer primary key,symbol text,exchange text,datetime text,interval text,volume real,turnover real,open_interest real,open_price real,high_price real,low_price real,close_price real)');db.execute('create unique index bar_key on dbbardata(symbol,exchange,datetime,interval)');db.executemany('insert into dbbardata values(?,?,?,?,?,?,?,?,?,?,?,?)',[(1,'SM505','CZCE','2015-01-05 00:00:00','d',999,0,999,6000,6050,5900,5950),(2,'SM505','CZCE','2015-01-06 00:00:00','d',888,0,888,6000,6050,5900,5950),(3,'a1505','DCE','2015-01-05 00:00:00','d',77,0,33,3000,3100,2900,3050),(4,'SM505','CZCE','2015-01-05 09:00:00','1m',66,0,22,6000,6050,5900,5950),(5,'SM','CZCE','2015-01-05 00:00:00','d',55,0,11,6000,6050,5900,5950)]);db.commit();db.close();before=hashlib.sha256(src.read_bytes()).hexdigest();old=mod.snapshot_database(src,dst,self.rows(),['SM.CZCE']);self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(),before);db=sqlite3.connect(dst);self.assertEqual(db.execute("select volume,open_interest from dbbardata where symbol='SM505' and interval='d'").fetchall(),[(20.,101.)]);self.assertEqual(db.execute("select id,volume from dbbardata where id in (3,4,5) order by id").fetchall(),[(3,77.),(4,66.),(5,55.)]);db.close();self.assertEqual(len(old),2)
 def test_output_database_must_not_overwrite_prior_output(self):
  mod=self.api()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'prior.sqlite';p.write_bytes(b'frozen')
   with self.assertRaisesRegex(ValueError,'exists'):mod.snapshot_database(p,p,self.rows(),['SM.CZCE'])
   self.assertEqual(p.read_bytes(),b'frozen')

 def probe_fixture(self,d,corrupt=False):
  import json
  p=Path(d);raw=p/'raw.csv';df=pd.DataFrame([dict(datetime=pd.Timestamp('2015-01-05',tz='Asia/Shanghai').value,id=1,open=6000.,high=6050.,low=5900.,close=5950.,volume=20.,open_oi=999.,close_oi=101.,symbol='CZCE.SM505',duration=86400)]);df.to_csv(raw,index=False);selected=df.copy();selected['vt_symbol']='SM505.CZCE';selected['date']='2015-01-05'
  if corrupt:selected.loc[0,'close_oi']=102.
  selected.to_csv(p/'daily_probe.csv',index=False);hashes={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['raw.csv','daily_probe.csv']};receipt=dict(status='latest_daily_ready',raw_daily_interval_seconds=86400,original_inputs_unchanged=True,contract_statuses=[dict(vt_symbol='SM505.CZCE',status='fetched',raw_path=str(raw),raw_sha256=hashes['raw.csv'],snapshot_at='2015-01-05T19:00:00+08:00')],output_files_sha256=hashes);(p/'probe_receipt.json').write_text(json.dumps(receipt));return p
 def test_probe_must_match_raw_close_oi(self):
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE'])
  with tempfile.TemporaryDirectory() as d:
   path=self.probe_fixture(d,True)
   with self.assertRaisesRegex(ValueError,'raw_mismatch'):mod.probe_bars(path,index,['SM.CZCE'],{})
 def test_probe_true_close_oi_with_raw_provenance(self):
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE'])
  with tempfile.TemporaryDirectory() as d:
   path=self.probe_fixture(d);files={};rows=mod.probe_bars(path,index,['SM.CZCE'],files);self.assertEqual(rows.close_oi.tolist(),[101.]);self.assertEqual(rows.volume.tolist(),[20.]);self.assertIn(str((path/'raw.csv').resolve()),files)
 def test_unapproved_supplement_not_accepted(self):
  import json
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE'])
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'supp.csv';self.rows().to_csv(p,index=False);policy=Path(d)/'policy.json';policy.write_text(json.dumps({'approved':False}))
   with self.assertRaisesRegex(ValueError,'approval'):mod.approved_supplement(p,policy,index,['SM.CZCE'],{})
 def test_cross_decade_gap_recorded_without_splicing(self):
  mod=self.api();a=self.rows();b=a.copy();b.loc[0,'date']='2025-01-06';b.loc[0,'contract_epoch_id']='CZCE.SM.202505';b.loc[0,'contract_yyyymm']='202505';got=mod.native_epoch_gaps(pd.concat([a,b],ignore_index=True));self.assertEqual(len(got),1);self.assertGreater(got.iloc[0].observed_gap_days,366)
 def test_same_native_two_epochs_same_day_rejected(self):
  mod=self.api();a=self.rows();b=a.copy();b.loc[0,'contract_epoch_id']='CZCE.SM.202505'
  with self.assertRaisesRegex(ValueError,'conflict'):mod.merge_bars([a,b])

 def test_complete_assembly_exports_missing_gate_and_keeps_source_immutable(self):
  import json
  mod=self.api()
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);clean=p/'clean.sqlite';base=p/'base.sqlite';raw=p/'raw_evidence.csv';raw.write_text('real frozen source\n');(p/'archive').mkdir();(p/'archive/official.json').write_text('archived official raw\n');digest=hashlib.sha256(raw.read_bytes()).hexdigest()
   db=sqlite3.connect(clean);pd.DataFrame([self.epoch()]).to_sql('contracts',db,index=False);pd.DataFrame([self.clean()]).to_sql('daily_bars',db,index=False);pd.DataFrame([dict(source_id='fixture',family='fixture',path=str(raw),sha256=digest,bytes=raw.stat().st_size,raw_path='archive/official.json')]).to_sql('sources',db,index=False);db.close();manifest=p/'clean_manifest.json';manifest.write_text(json.dumps({'database':{'path':str(clean),'sha256':hashlib.sha256(clean.read_bytes()).hexdigest()},'receipts':[]}))
   db=sqlite3.connect(base);db.execute('create table dbbardata(id integer primary key,symbol text,exchange text,datetime text,interval text,volume real,turnover real,open_interest real,open_price real,high_price real,low_price real,close_price real)');db.execute("insert into dbbardata values(1,'SM505','CZCE','2015-01-05 00:00:00','d',999,0,999,6000,6050,5900,5950)");db.commit();db.close();mapping=p/'mapping.csv';pd.DataFrame([dict(date='2015-01-05',continuous_symbol_vt='SM.CZCE',main_contract_vt='SM505.CZCE')]).to_csv(mapping,index=False);target=p/'target.csv';pd.DataFrame([dict(date='2015-01-06',continuous_symbol_vt='SM.CZCE',main_contract_vt='SM505.CZCE')]).to_csv(target,index=False);metadata=p/'metadata.csv';metadata.write_text('vt_symbol,volume_multiple\nSM.CZCE,5\n');before=hashlib.sha256(base.read_bytes()).hexdigest();out=p/'out';receipt=mod.assemble_history(clean,manifest,base,mapping,metadata,target,[],out,['SM.CZCE']);self.assertFalse(receipt['data_ready']);self.assertEqual(receipt['units'],'single_sided_volume_close_oi');self.assertEqual(hashlib.sha256(base.read_bytes()).hexdigest(),before);lookup=pd.read_csv(out/'physical_epoch_daily.csv');self.assertEqual(lookup[['vt_symbol','date','contract_epoch_id']].to_dict('records'),[{'vt_symbol':'SM505.CZCE','date':'2015-01-05','contract_epoch_id':'CZCE.SM.201505'}]);miss=pd.read_csv(out/'missing_main.csv');self.assertEqual(miss.date.tolist(),['2015-01-06']);source=json.loads((out/'source_manifest.json').read_text());self.assertIn(str((out/'receipt.json').resolve()),source['files']);self.assertIn(str(raw.resolve()),source['files']);self.assertIn(str((p/'archive/official.json').resolve()),source['files'])
   nt=p/'nt';nt.mkdir();csv,policy,missing=self.no_trade_fixture(nt);f=pd.read_csv(csv);f['date']='2015-01-06';f.to_csv(csv,index=False);raw=Path(f.iloc[0].source_path);r=pd.read_csv(raw);r['date']='2015-01-06';r.to_csv(raw,index=False);f['source_sha256']=mod.sha(raw);f.to_csv(csv,index=False);pol=json.loads(policy.read_text());pol['known_no_trade_sha256']=mod.sha(csv);pol['files']={str(raw):mod.sha(raw)};policy.write_text(json.dumps(pol));out2=p/'out_with_no_trade';second=mod.assemble_history(clean,manifest,base,mapping,metadata,target,[],out2,['SM.CZCE'],known_no_trade=csv,no_trade_policy=policy);self.assertEqual(second['known_no_trade_main'],1);self.assertEqual(second['unknown_missing_main'],0);self.assertEqual(second['accepted_rows'],1);self.assertTrue(pd.read_csv(out2/'missing_main.csv').empty);self.assertEqual(len(pd.read_csv(out2/'physical_epoch_daily.csv')),1)
   with sqlite3.connect(out2/'daily.sqlite') as db:self.assertEqual(db.execute('select count(*) from dbbardata').fetchone()[0],1)

 def test_old_known_metadata_century_does_not_break_2014_import(self):
  mod=self.api();old=self.epoch('199907','1998-07-01','1999-07-15');index=mod.epoch_index(pd.DataFrame([old,self.epoch()]),['SM.CZCE']);self.assertEqual(mod.bind_epoch('SM505.CZCE','2015-01-05',index)['contract_epoch_id'],'CZCE.SM.201505')
 def test_listed_and_delisted_day_are_inclusive(self):
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch('201505','2014-08-08','2015-05-19')]),['SM.CZCE']);self.assertEqual(mod.bind_epoch('SM505.CZCE','2015-05-19',index)['contract_epoch_id'],'CZCE.SM.201505')
 def test_approved_field_map_uses_tq_not_old_quantity(self):
  import json
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE'])
  with tempfile.TemporaryDirectory() as d:
   base=self.probe_fixture(d);raw=base/'raw.csv';row=self.rows().iloc[0].to_dict();row['source_path']=str(raw);row['source_sha256']=hashlib.sha256(raw.read_bytes()).hexdigest();row['admission_reason']='predeclared audited raw quote';mapping={k:'tq_'+k for k in ['open','high','low','close','volume','close_oi']}
   for key,value in mapping.items():row[value]=row[key]
   row['volume']=999.;row['close_oi']=999.;supp=base/'approved.csv';pd.DataFrame([row]).to_csv(supp,index=False);policy=base/'policy.json';policy.write_text(json.dumps(dict(approved=True,policy_id='fixed_fixture',units='single_sided_volume_close_oi',supplement_sha256=hashlib.sha256(supp.read_bytes()).hexdigest(),files={str(raw):row['source_sha256']},field_map=mapping)));got=mod.approved_supplement(supp,policy,index,['SM.CZCE'],{});self.assertEqual(got.volume.tolist(),[20.]);self.assertEqual(got.close_oi.tolist(),[101.]);self.assertEqual(got.admission_reason.tolist(),['predeclared audited raw quote'])

 def test_raw_four_digit_CZCE_year_must_match_physical_epoch(self):
  mod=self.api();row=self.rows().iloc[0].to_dict();row.update(date='2025-01-06',contract_epoch_id='CZCE.SM.202505',contract_yyyymm='202505');raw=pd.DataFrame([dict(datetime=pd.Timestamp('2025-01-06',tz='Asia/Shanghai').value,id=1,open=6000.,high=6050.,low=5900.,close=5950.,volume=20.,open_oi=999.,close_oi=101.,symbol='CZCE.SM1505',duration=86400)])
  with self.assertRaisesRegex(ValueError,'identity_mismatch'):mod._raw_check(row,raw)

 def test_each_raw_quote_field_nan_or_infinity_rejected(self):
  mod=self.api();row=self.rows().iloc[0].to_dict()
  for field in ['open','high','low','close','volume','close_oi']:
   for invalid in [float('nan'),float('inf')]:
    with self.subTest(field=field,invalid=invalid):
     value=dict(datetime=pd.Timestamp('2015-01-05',tz='Asia/Shanghai').value,id=1,open=6000.,high=6050.,low=5900.,close=5950.,volume=20.,open_oi=999.,close_oi=101.,symbol='CZCE.SM1505',duration=86400);value[field]=invalid
     with self.assertRaisesRegex(ValueError,'raw_nonfinite'):mod._raw_check(row,pd.DataFrame([value]))

 def no_trade_fixture(self,d,volume=0):
  import json
  mod=self.api();base=Path(d);raw=base/'no_trade_raw.csv';row=dict(vt_symbol='SM505.CZCE',date='2015-01-05',contract_epoch_id='CZCE.SM.201505',source_contract_epoch_id='CZCE.SM.201505',physical_identity_status='known_vendor_inclusive_lifecycle',zero_volume=volume,source_path=str(raw),source_locator='original receipt row 1',admission_reason='audited real zero-volume mapped main');pd.DataFrame([dict(vt_symbol=row['vt_symbol'],date=row['date'],contract_epoch_id=row['contract_epoch_id'],volume=volume)]).to_csv(raw,index=False);row['source_sha256']=mod.sha(raw);csv=base/'known.csv';pd.DataFrame([row]).to_csv(csv,index=False);policy=base/'policy.json';policy.write_text(json.dumps(dict(approved=True,purpose='classification_only_no_OHLC_OI_consumption',policy_id='fixture_no_trade',known_no_trade_sha256=mod.sha(csv),files={str(raw):mod.sha(raw)},volume_field='zero_volume')));missing=pd.DataFrame([dict(date=row['date'],continuous_symbol_vt='SM.CZCE',main_contract_vt=row['vt_symbol'],reason='no_positive_accepted_physical_daily')]);return csv,policy,missing
 def test_approved_no_trade_missing_OHLC_OI_only_classifies_not_bar(self):
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE'])
  with tempfile.TemporaryDirectory() as d:
   csv,policy,missing=self.no_trade_fixture(d);known,unknown=mod.approved_no_trade(csv,policy,index,['SM.CZCE'],{},missing);self.assertEqual(len(known),1);self.assertEqual(known.zero_volume.tolist(),[0]);self.assertEqual(known.classification.tolist(),['known_no_trade_main_not_bar']);self.assertTrue(unknown.empty);self.assertNotIn('close',known.columns)
 def test_no_trade_nonzero_or_nonfinite_volume_rejected(self):
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE'])
  for invalid in [1,-1,float('nan'),float('inf')]:
   with self.subTest(volume=invalid),tempfile.TemporaryDirectory() as d:
    csv,policy,missing=self.no_trade_fixture(d,volume=invalid)
    with self.assertRaisesRegex(ValueError,'no_trade_not_zero'):mod.approved_no_trade(csv,policy,index,['SM.CZCE'],{},missing)
 def test_no_trade_subset_retains_unknown_missing(self):
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE'])
  with tempfile.TemporaryDirectory() as d:
   csv,policy,missing=self.no_trade_fixture(d);missing=pd.concat([missing,missing.assign(date='2015-01-06')],ignore_index=True)
   known,unknown=mod.approved_no_trade(csv,policy,index,['SM.CZCE'],{},missing);self.assertEqual(len(known),1);self.assertEqual(unknown.date.tolist(),['2015-01-06'])
 def test_no_trade_duplicate_keys_rejected(self):
  import json
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE'])
  with tempfile.TemporaryDirectory() as d:
   csv,policy,missing=self.no_trade_fixture(d);frame=pd.read_csv(csv);pd.concat([frame,frame],ignore_index=True).to_csv(csv,index=False);p=json.loads(policy.read_text());p['known_no_trade_sha256']=mod.sha(csv);policy.write_text(json.dumps(p))
   with self.assertRaisesRegex(ValueError,'no_trade_duplicate_key'):mod.approved_no_trade(csv,policy,index,['SM.CZCE'],{},missing)
 def test_no_trade_raw_nonzero_or_nonfinite_volume_rejected(self):
  import json
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE'])
  for invalid in [1,-1,float('nan'),float('inf')]:
   with self.subTest(raw_volume=invalid),tempfile.TemporaryDirectory() as d:
    csv,policy,missing=self.no_trade_fixture(d);frame=pd.read_csv(csv);raw=Path(frame.iloc[0].source_path);r=pd.read_csv(raw);r.loc[0,'volume']=invalid;r.to_csv(raw,index=False);frame.loc[0,'source_sha256']=mod.sha(raw);frame.to_csv(csv,index=False);p=json.loads(policy.read_text());p['known_no_trade_sha256']=mod.sha(csv);p['files']={str(raw):mod.sha(raw)};policy.write_text(json.dumps(p))
    with self.assertRaisesRegex(ValueError,'no_trade_raw_not_zero'):mod.approved_no_trade(csv,policy,index,['SM.CZCE'],{},missing)
 def test_no_trade_policy_classification_purpose_required(self):
  import json
  mod=self.api();index=mod.epoch_index(pd.DataFrame([self.epoch()]),['SM.CZCE'])
  with tempfile.TemporaryDirectory() as d:
   csv,policy,missing=self.no_trade_fixture(d);p=json.loads(policy.read_text());p.pop('purpose');policy.write_text(json.dumps(p))
   with self.assertRaisesRegex(ValueError,'no_trade_policy_invalid'):mod.approved_no_trade(csv,policy,index,['SM.CZCE'],{},missing)

 def structural_fixture(self,d):
  import json
  mod=self.api();base=Path(d);a=self.epoch('201805','2017-05-16','2018-04-30');a.update(contract_epoch_id='SHFE.FU.201805',exchange='SHFE',product='FU');b=self.epoch('201905','2018-07-16','2019-04-30');b.update(contract_epoch_id='SHFE.FU.201905',exchange='SHFE',product='FU');index=mod.epoch_index(pd.DataFrame([a,b]),['fu.SHFE']);rows=[]
  for day in ['2018-05-02','2018-05-03','2018-05-04','2018-05-07','2018-05-08','2018-05-09','2018-05-10']:rows.append(dict(vt_symbol='fu1805.SHFE',date=day,source_contract_epoch_id='SHFE.FU.201805',classification_reason='fu1805_after_delisting_frozen_mapping'))
  for day in ['2018-06-29','2018-07-02','2018-07-03','2018-07-04','2018-07-05','2018-07-06','2018-07-09','2018-07-10','2018-07-11','2018-07-12','2018-07-13']:rows.append(dict(vt_symbol='fu1905.SHFE',date=day,source_contract_epoch_id='SHFE.FU.201905',classification_reason='fu1905_official_termination_relisting_gap'))
  raw=base/'absence.csv';pd.DataFrame(rows).assign(source_key_absent=True).to_csv(raw,index=False);frame=pd.DataFrame(rows).assign(source_path=str(raw),source_sha256=mod.sha(raw),source_locator='audited original H5 exact native/date absence');csv=base/'structural.csv';frame.to_csv(csv,index=False);policy=base/'policy.json';policy.write_text(json.dumps(dict(approved=True,purpose='classification_only_invalid_frozen_mapping',policy_id='structural_fixture',structural_unavailable_sha256=mod.sha(csv),files={str(raw):mod.sha(raw)},approved_keys=rows)));missing=frame[['date','vt_symbol']].rename(columns={'vt_symbol':'main_contract_vt'}).assign(continuous_symbol_vt='fu.SHFE',reason='no_positive_accepted_physical_daily');return csv,policy,missing,index
 def test_structural_18_only_classification_no_fake_zero_or_bar(self):
  mod=self.api()
  with tempfile.TemporaryDirectory() as d:
   csv,policy,missing,index=self.structural_fixture(d);known,unknown=mod.approved_structural_unavailable(csv,policy,index,['fu.SHFE'],{},missing);self.assertEqual(len(known),18);self.assertTrue(unknown.empty);self.assertNotIn('volume',known.columns);self.assertNotIn('close',known.columns);self.assertEqual(set(known.classification),{'structural_unavailable_frozen_mapping_not_bar'})
 def test_structural_source_not_absent_rejected(self):
  import json
  mod=self.api()
  with tempfile.TemporaryDirectory() as d:
   csv,policy,missing,index=self.structural_fixture(d);frame=pd.read_csv(csv);raw=Path(frame.iloc[0].source_path);r=pd.read_csv(raw);r.loc[0,'source_key_absent']=False;r.to_csv(raw,index=False);frame['source_sha256']=mod.sha(raw);frame.to_csv(csv,index=False);p=json.loads(policy.read_text());p['structural_unavailable_sha256']=mod.sha(csv);p['files']={str(raw):mod.sha(raw)};policy.write_text(json.dumps(p))
   with self.assertRaisesRegex(ValueError,'structural_source_absence'):mod.approved_structural_unavailable(csv,policy,index,['fu.SHFE'],{},missing)
 def test_structural_policy_cannot_classify_key_outside_missing(self):
  mod=self.api()
  with tempfile.TemporaryDirectory() as d:
   csv,policy,missing,index=self.structural_fixture(d)
   with self.assertRaisesRegex(ValueError,'structural_missing_key_set'):mod.approved_structural_unavailable(csv,policy,index,['fu.SHFE'],{},missing.iloc[1:])
 def test_structural_policy_must_pin_exact18_approval_keys(self):
  import json
  mod=self.api()
  with tempfile.TemporaryDirectory() as d:
   csv,policy,missing,index=self.structural_fixture(d);p=json.loads(policy.read_text());p['approved_keys']=p['approved_keys'][:-1];policy.write_text(json.dumps(p))
   with self.assertRaisesRegex(ValueError,'structural_approved_keys'):mod.approved_structural_unavailable(csv,policy,index,['fu.SHFE'],{},missing)

 def test_approved_legacy_zero_classification_never_binds_new380(self):
  import json
  mod=self.api()
  with tempfile.TemporaryDirectory() as d:
   csv,policy,missing=self.no_trade_fixture(d);frame=pd.read_csv(csv);frame['vt_symbol']='fu1905.SHFE';frame['date']='2018-05-11';frame['contract_epoch_id']='NONTRADABLE_LEGACY_FU180.201905';frame['source_contract_epoch_id']='SHFE.FU.201905';frame['physical_identity_status']='legacy_FU180_or_termination_buffer_not_new380_classification_only';raw=Path(frame.iloc[0].source_path);pd.DataFrame([dict(vt_symbol='fu1905.SHFE',date='2018-05-11',source_contract_epoch_id='SHFE.FU.201905',volume=0)]).to_csv(raw,index=False);frame['source_sha256']=mod.sha(raw);frame.to_csv(csv,index=False);p=json.loads(policy.read_text());p['known_no_trade_sha256']=mod.sha(csv);p['files']={str(raw):mod.sha(raw)};p['legacy_identity_exclusions']=frame[['vt_symbol','date','contract_epoch_id','source_contract_epoch_id']].to_dict('records');policy.write_text(json.dumps(p));missing['main_contract_vt']='fu1905.SHFE';missing['date']='2018-05-11';known,unknown=mod.approved_no_trade(csv,policy,{'by_id':{},'by_native':{}},['fu.SHFE'],{},missing);self.assertEqual(len(known),1);self.assertTrue(unknown.empty);self.assertEqual(known.iloc[0].contract_epoch_id,'NONTRADABLE_LEGACY_FU180.201905')

if __name__=='__main__':unittest.main()
