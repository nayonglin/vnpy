from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from statistics import median
import hashlib,json,tempfile,time,sys
sys.path.insert(0,str(Path.cwd()/'examples/portfolio_backtesting'))
from qmt_roll_official_live_tick_stream import TickStreamPipeline
from qmt_roll_official_live_tick_types import DurableTickCursor
import qmt_roll_weekly19_quote_spool as quote
class Clock:
 def epoch_ns(self):return time.time_ns()
 def monotonic_ns(self):return time.monotonic_ns()
 def clock_domain_id(self):return 'explicit-offline-benchmark-clock'
clock=Clock();count=50000;source=Path(quote.__file__);before=hashlib.sha256(source.read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(prefix='weekly19-quote-scale-',dir='/private/tmp')as d:
 path=Path(d)/'fixture-journal';pipe=TickStreamPipeline(feed_session_id='literal-offline-scale-feed',journal_segment_path=path,clock=clock,max_buffer_ticks=count+10,writer_batch_size=256)
 pipe.start()
 try:
  tick=SimpleNamespace(vt_symbol='rb2701.SHFE',symbol='rb2701',exchange='SHFE',datetime=datetime.now(timezone.utc),last_price=4000.,bid_price_1=3999.,ask_price_1=4000.,bid_volume_1=10,ask_volume_1=10)
  for i in range(count):
   pipe.capture_ingress(tick)
   if(i+1)%500==0:assert pipe.wait_until_durable(i+1,timeout_seconds=5)
  if not pipe.wait_until_durable(count,timeout_seconds=5):
   from dataclasses import asdict
   snap=pipe.durable_snapshot();record=dict(schema='weekly19.quote-scale-burst-failure.v1',offline_fixture_only=True,production_qualified=False,framed_tick_requested=count,queue_capacity=pipe.queue_capacity,source_sha256=before,snapshot=dict(last_ingress_sequence=snap.last_ingress_sequence,durable_ingress_sequence=snap.durable_ingress_sequence,dropped_tick_count=snap.dropped_tick_count,queue_capacity=snap.queue_capacity,stream_ready=snap.stream_ready,gap=str(snap.gap),writer_fault=str(snap.writer_fault)),financial_replay=False,order_api_called_count=0)
   Path('research/lines/futures_weekly_short_ma_slope_gate/stages/stage016_quote_scale_50000_burst_failure.json').write_text(json.dumps(record,indent=2,default=str));print(json.dumps(record,default=str));raise RuntimeError('literal_burst_not_durable_see_preserved_snapshot')
  snapshot=pipe.durable_snapshot();assert snapshot.gap is None and snapshot.writer_fault is None
  cursor=DurableTickCursor(snapshot.feed_session_id,snapshot.durable_ingress_sequence,snapshot.durable_journal_byte_offset,snapshot.journal_schema)
  quote._QUOTE_CACHE.clear();start=time.perf_counter();row=quote._latest_quote(path,cursor,tick.vt_symbol);cold=time.perf_counter()-start
  cached=[]
  for _ in range(5):
   start=time.perf_counter();result=quote._latest_quote(path,cursor,tick.vt_symbol);cached.append(time.perf_counter()-start);assert result==row
  assert hashlib.sha256(source.read_bytes()).hexdigest()==before
  record=dict(schema='weekly19.quote-scale-benchmark.v1',offline_fixture_only=True,production_qualified=False,financial_replay=False,
   source_sha256=before,producer_mode='paced batches of500 within unchanged8192 ingress bound',framed_tick_count=count,journal_bytes=path.stat().st_size,cold_decode_seconds=cold,cached_prefix_rehash_seconds=cached,
   cached_median_seconds=median(cached),integrity='actual full committed prefix rehashed on every cached call',
   ctp_protocol_login_attempted=False,order_api_called_count=0,send_order_api_called_count=0,cancel_order_api_called_count=0)
  out=Path('research/lines/futures_weekly_short_ma_slope_gate/stages/stage016_quote_scale_50000_benchmark.json');out.write_text(json.dumps(record,indent=2));print(json.dumps(record,sort_keys=True))
 finally:pipe.shutdown(timeout_seconds=10)
