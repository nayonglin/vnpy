import csv,json,re
from pathlib import Path
from datetime import datetime,date
from zoneinfo import ZoneInfo
from decimal import Decimal
import hashlib

home=Path('/Users/mac/Desktop/fian/weekly19-stop-reversal.local/research/lines')
line=home/'futures_weekly_two_close_momentum'
frozen=home/'futures_weekly19_stop_reversal/outputs'
base=frozen/'stage002_data/data_approved'
t=line/'outputs/stage033_s19_data/attempt002'
old='2026-11-03'; new='2026-11-04'
def csv_rows(path):
    with path.open() as f: yield from csv.DictReader(f)
def j(path): return json.loads(path.read_text())
def sha(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
request=j(t/'request.json')
assert (request['start'],request['end'])==(old,new)
continuous=j(t/'continuous_table.raw.json')
prior_mapping={r['continuous_symbol_vt']:r['main_contract_vt'] for r in csv_rows(base/'mapping.csv') if r['date']==old}
assert set(prior_mapping)==set(request['mains']) and len(prior_mapping)==19
def map_day(d,product):
    root,exchange=product.split('.')
    native,=list(sorted((x for x in continuous[f'{exchange}.{root}'] if x[0]<=d.replace('-','')),reverse=True))[0][1:]
    market,code=native.split('.')
    assert market==exchange and re.fullmatch(re.escape(root)+r'\d+',code)
    return f'{code}.{market}'
for product in prior_mapping:
    assert prior_mapping[product]==map_day(old,product)
    assert request['mains'][product]==map_day(new,product)
cal=[r['date'] for r in csv_rows(base/'forward_calendar.csv')]
assert cal[cal.index(old)+1]==new
assert date.fromisoformat(cal[cal.index(new)+2]).isocalendar().week==date.fromisoformat(new).isocalendar().week
assert cal[cal.index(new)+2]=='2026-11-06'

quotes=j(t/'provider/quotes.json')
assert set(quotes)==set(request['symbols']) and len(quotes)==27
specs=j(frozen/'stage003_D_20261103_attempt01/contract_settings.json')
epochs={r['vt_symbol']:r for r in csv_rows(base/'physical_epochs.csv') if r['contract_yyyymm']>='202611'}
history={(r['date'],r['vt_symbol']):r for r in csv_rows(base/'physical_epoch_daily.csv') if r['date']==old}
price=t/'provider/raw_daily.csv'
provider={(r['date'],r['vt_symbol']):r for r in csv_rows(price)}
assert len(provider)==len(list(csv_rows(price)))==54
assert set(provider)=={(d,s) for d in (old,new) for s in quotes}
fields=['open','high','low','close','volume']
epochs_seen=set()
stamps=set()
for symbol,quote in quotes.items():
    code,exchange=symbol.split('.')
    delivery=str(quote['delivery_year'])+f"{quote['delivery_month']:02d}"
    epoch=epochs[symbol]
    assert epoch['contract_epoch_id']==f"{exchange}.{code.rstrip('0123456789').upper()}.{delivery}"
    assert epoch['contract_yyyymm']==delivery
    assert epoch['observed_available_min']<=epoch['observed_available_max']<=old,(symbol,epoch)
    assert epoch['listed_unknown']=='True' or epoch['listed_date']<new
    assert epoch['delisted_unknown']=='True' or epoch['delisted_date']>=new
    assert epoch['forward_extension_allowed']=='True'
    assert quote['instrument_id']==f'{exchange}.{code}' and quote['ins_class']=='FUTURE'
    assert quote['volume_multiple']==specs['sizes'][symbol] and quote['price_tick']==specs['priceticks'][symbol]
    assert datetime.fromtimestamp(quote['expire_datetime'],ZoneInfo('Asia/Shanghai')).date()>=date.fromisoformat(new)
    assert epoch['contract_epoch_id'] not in epochs_seen
    epochs_seen.add(epoch['contract_epoch_id'])
    first,second=(provider[d,symbol] for d in (old,new))
    assert Decimal(second['id'])-Decimal(first['id'])==1
    assert history[old,symbol]['contract_epoch_id']==epoch['contract_epoch_id']
    assert all(Decimal(history[old,symbol][f])==Decimal(first[f]) for f in fields)
    for d,x in ((old,first),(new,second)):
        converted=datetime.fromtimestamp(float(Decimal(x['datetime'])/10**9),ZoneInfo('Asia/Shanghai'))
        assert converted.isoformat()==d+'T00:00:00+08:00'
        stamps.add(converted.isoformat())
        o,h,l,c,v,oi=[Decimal(x[f]) for f in fields+['close_oi']]
        assert all(x.is_finite() for x in (o,h,l,c,v,oi))
        assert 0<l<=min(o,c)<=max(o,c)<=h and v>=0 and oi>=0
        assert v==v.to_integral_value() and oi==oi.to_integral_value()
        assert all(p % Decimal(str(quote['price_tick']))==0 for p in (o,h,l,c))
for p in prior_mapping:
    assert int(Decimal(provider[new,request['mains'][p]]['volume']))>0
artifact_time=datetime.fromtimestamp(price.stat().st_mtime,ZoneInfo('Asia/Shanghai'))
assert artifact_time.date()==date.fromisoformat(new) and artifact_time.hour>=15
zero=[s for s in quotes if int(Decimal(provider[new,s]['volume']))==0]
assert zero==['SH611.CZCE']
fallback=line/'outputs/stage033_s19_annual_starts_20261103'
needed=set()
for year in range(2015,2027):
    terminal=j(fallback/str(year)/'terminal.json')
    assert not terminal['pending'] and not terminal['pending_reversals']
    needed.update(pos['symbol'] for pos in terminal['positions'].values())
assert all(int(Decimal(provider[new,s]['volume']))>0 for s in needed)
unchanged=sum(request['mains'][p]==v for p,v in prior_mapping.items())
result=dict(status='PASS_WITH_LIMITATIONS',target=new,provider_raw_file_mtime=artifact_time.isoformat(),daily_timestamp_labels=sorted(stamps),mains=len(prior_mapping),unchanged_mains=unchanged,changed_mains={p:[prior_mapping[p],v] for p,v in request['mains'].items() if v!=prior_mapping[p]},distinct_physical_epochs=len(epochs_seen),bars=len(provider),prior_ohlcv_exact=27,admitted_new_daily=len(quotes)-len(zero),zero_volume_excluded=zero,held_contract_union_count=len(needed),held_contracts=sorted(needed),min_admitted_volume=min(int(Decimal(provider[new,s]['volume'])) for s in quotes if s not in zero),min_main_volume=min(int(Decimal(provider[new,s]['volume'])) for s in request['mains'].values()),week_ends='2026-11-06',hashes={str(path.relative_to(t)):sha(path) for path in (t/'request.json',t/'continuous_table.raw.json',price,t/'provider/quotes.json')})
Path('/private/tmp/fian_stage033_tail_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
