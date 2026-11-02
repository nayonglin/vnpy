"""One-shot private TQ instrument observation; no broker or order transport."""
from datetime import datetime
import argparse, hashlib, json, math, os
from pathlib import Path
import time

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--symbols-json',required=True)
    args=parser.parse_args()
    path=Path(args.output)
    assert path.is_absolute() and path.parent.is_dir() and not path.parent.is_symlink()
    assert path.parent.stat().st_mode & 0o777 == 0o700
    symbols=json.loads(args.symbols_json)
    assert isinstance(symbols,list) and symbols and len(set(symbols))==len(symbols)
    from vnpy.trader.setting import SETTINGS
    from tqsdk import TqApi,TqAuth,TqSim
    api=TqApi(TqSim(),auth=TqAuth(SETTINGS['datafeed.username'],SETTINGS['datafeed.password']),disable_print=True,debug=False)
    def forbidden(*args,**kwargs):raise RuntimeError('contract_metadata_order_api_forbidden')
    api.insert_order=forbidden;api.cancel_order=forbidden
    try:
        quotes={symbol:api.get_quote(symbol.split('.')[1]+'.'+symbol.split('.')[0])for symbol in symbols}
        deadline=time.monotonic()+60
        while not all(q.get('instrument_id') and q.get('volume_multiple') and q.get('price_tick') for q in quotes.values()):
            if time.monotonic()>=deadline:raise RuntimeError('real_contract_metadata_timeout')
            api.wait_update(deadline=time.time()+1)
        fields=('instrument_id','ins_class','volume_multiple','price_tick','expire_datetime','delivery_year','delivery_month')
        rows=[dict(vt_symbol=symbol,**{key:quote.get(key) for key in fields}) for symbol,quote in sorted(quotes.items())]
        for row in rows:
            assert row['ins_class']=='FUTURE' and row['instrument_id']==row['vt_symbol'].split('.')[1]+'.'+row['vt_symbol'].split('.')[0]
            for key in ('volume_multiple','price_tick','expire_datetime','delivery_year','delivery_month'):
                assert isinstance(row[key],(int,float)) and not isinstance(row[key],bool) and math.isfinite(row[key]) and row[key]>0
        raw=dict(schema='weekly19.contract-metadata.v1',source_kind='tqsdk_quote_capture',observed_at=datetime.now().astimezone().isoformat(),quotes=rows)
        payload=json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
        envelope=dict(raw_payload=payload,raw_sha256=hashlib.sha256(payload.encode()).hexdigest())
        capture=dict(schema='Stage024.contract-metadata-capture.v1',envelope=envelope,
            producer_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),order_api_calls=0)
        data=(json.dumps(capture,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb')as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        print(json.dumps(dict(status='real_contract_metadata_captured',path=str(path),sha256=hashlib.sha256(data).hexdigest(),contracts=len(rows),order_api_calls=0)),flush=True)
    finally:api.close()

if __name__=='__main__':main()
