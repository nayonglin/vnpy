"""Minimal authorized five-symbol read-only quote probe; no bar downloads/orders."""
import contextlib
from datetime import datetime
import io
import json
import logging
import math
from pathlib import Path
import signal
import time
from zoneinfo import ZoneInfo

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage265_deep_daily/tq_latest'


def timeout(signum,frame):raise TimeoutError('readonly_quote_deadline')


def main():
    from tqsdk import TqApi,TqAuth,TqSim
    report=json.loads((OUT/'recent_download_status.json').read_text())
    symbols=sorted(s for s,r in report['items'].items() if r.get('status')=='downloaded' and r.get('rows')==0)
    if len(symbols)!=5:raise ValueError('expected_exactly_five_current_empty_series')
    result={'requested_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'symbols':symbols,
        'probe':'one batch get_quote only; no kline subscriptions, downloads, broker connection or order calls',
        'bar_download_calls':0,'order_api_calls':0,'cancel_api_calls':0,'broker_connections':0,
        'limitations':'Snapshot describes only latest observable quote state; it does not establish zero volume on every historical day.'}
    config=json.loads((ROOT/'.vntrader/vt_setting.json').read_text())
    api=None;logging.disable(logging.CRITICAL)
    signal.signal(signal.SIGALRM,timeout);signal.alarm(60)
    try:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            api=TqApi(TqSim(),auth=TqAuth(config['datafeed.username'],config['datafeed.password']),
                      debug=False,disable_print=True,web_gui=False)
            quotes={}
            async def subscribe():
                for symbol in symbols:quotes[symbol]=api.get_quote(symbol)
            task=api.create_task(subscribe())
            observe_start=time.monotonic();until=observe_start+25;updates=0
            while time.monotonic()<until:
                if task.done() and task.exception():raise task.exception()
                ready=len(quotes)==5 and all(q.get('ins_class')=='FUTURE' and q.get('expire_datetime',0)>0 for q in quotes.values())
                if ready and time.monotonic()-observe_start>=10:break
                api.wait_update(deadline=time.time()+2)
                updates+=1
            fields=('datetime','ins_class','expired','instrument_name','exchange_id','instrument_id',
                'last_price','pre_close','pre_settlement','volume','open_interest','open','highest','lowest',
                'close','settlement','expire_datetime','create_datetime','delivery_year','delivery_month')
            result['quotes']={}
            for symbol,q in quotes.items():
                row={};nonfinite=[]
                for field in fields:
                    value=q.get(field,None)
                    if isinstance(value,float) and not math.isfinite(value):nonfinite.append(field);value=None
                    if type(value) in (str,int,float,bool,type(None)):row[field]=value
                row['nonfinite_fields']=nonfinite
                row['static_metadata_ready']=q.get('ins_class')=='FUTURE' and q.get('expire_datetime',0)>0
                result['quotes'][symbol]=row
            result['status']='snapshot_recorded'
            result['observation_seconds']=round(time.monotonic()-observe_start,3)
            result['wait_update_calls_after_subscription']=updates
            result['classification_limit']='Only the latest state observed after the bounded subscription is recorded; missing last trade price and zero volume do not prove historical daily non-trading.'
    except Exception as error:
        result.update(status='probe_failed',error_type=type(error).__name__)
    finally:
        signal.alarm(0)
        if api is not None:
            with contextlib.suppress(Exception),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                signal.alarm(8);api.close()
        signal.alarm(0)
    result['completed_at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    (OUT/'independent_review_stage265_tq_tail_empty_quotes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':main()
