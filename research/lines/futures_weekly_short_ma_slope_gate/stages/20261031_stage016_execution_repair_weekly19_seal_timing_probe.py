"""Read-only timing instrumentation for the exact offline seal fixture."""
import functools,inspect,json,time,threading
from pathlib import Path
import pytest
PROBE=Path('/private/tmp/weekly19_seal_timing_probe.jsonl');LOCK=threading.Lock()
@pytest.fixture(autouse=True)
def probe(request,monkeypatch):
 if request.node.name!='test_authorized_spool_factory_to_seal_and_next_day_close':return
 import run_qmt_roll_stage931_official_live_ctp_submit_adapter as module
 def emit(record):
  with LOCK:
   with PROBE.open('a')as handle:handle.write(json.dumps(record,sort_keys=True)+'\n')
 for name in ('_final_pre_send_snapshot_epoch','_final_order_query_epoch','_final_position_query_epoch','_final_open_account_funds_query_epoch','_final_open_max_order_volume_query_epoch','_post_reprice_final_state_gate'):
  original=getattr(module,name)
  def make(fn,label):
   @functools.wraps(fn)
   def wrapped(*args,**kw):
    started=time.monotonic();rows=next((v for v in args if isinstance(v,dict)and '_ctp_last_query_monotonic'in v),{})
    interval=inspect.signature(fn).parameters.get('query_interval_seconds')
    record=dict(function=label,started=started,max_wait_seconds=kw.get('max_wait_seconds'),hard_deadline=kw.get('hard_deadline_monotonic'),last_query=rows.get('_ctp_last_query_monotonic'),effective_interval=kw.get('query_interval_seconds',None if interval is None else interval.default),module_interval=module.CTP_QUERY_INTERVAL_SECONDS)
    try:
     result=fn(*args,**kw);record.update(confirmed=result.get('confirmed'),blockers=result.get('blockers'),reqid=result.get('reqid'),requested_at=result.get('requested_at_monotonic'),reported_elapsed=result.get('elapsed_seconds'));return result
    finally:record['elapsed']=time.monotonic()-started;emit(record)
   return wrapped
  monkeypatch.setattr(module,name,make(original,name))
