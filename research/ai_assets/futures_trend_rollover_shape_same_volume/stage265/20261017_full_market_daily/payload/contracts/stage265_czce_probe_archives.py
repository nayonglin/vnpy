"""Record ordinary public official archive GETs; never bypass a site challenge."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

OUT=Path(__file__).resolve().parents[1]/'outputs/stage265_deep_daily/czce'
URLS=[
('2010','https://www.czce.com.cn/cn/exchange/datahistory2010.zip'),
('2015','https://www.czce.com.cn/cn/DFSStaticFiles/Future/2015/FutureDataHistory.zip'),
('2025','https://www.czce.com.cn/cn/DFSStaticFiles/Future/2025/ALLFUTURES2025.zip'),
]
log=[]
for year,url in URLS:
    path=OUT/f'official_archive_probe_{year}.raw'
    if path.exists():
        continue
    entry={'year':year,'url':url,'method':'GET','auth':'none','automatic_retries':0,'accessed_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
    try:
        with requests.get(url,timeout=(10,25),stream=True) as response:
            body=bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body)>64*1024*1024:
                    raise ValueError('archive_above_size_cap')
            path.write_bytes(body)
            entry.update(http_status=response.status_code,response_url=response.url,bytes=len(body),sha256=hashlib.sha256(body).hexdigest(),content_type=response.headers.get('content-type',''),zip_magic=body[:4]==b'PK\x03\x04',path=path.name)
    except (requests.RequestException,ValueError) as exc:
        entry.update(error_type=type(exc).__name__,error=str(exc)[:300])
    log.append(entry)
    (OUT/'official_archive_probe_requests.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(entry,ensure_ascii=False),flush=True)
