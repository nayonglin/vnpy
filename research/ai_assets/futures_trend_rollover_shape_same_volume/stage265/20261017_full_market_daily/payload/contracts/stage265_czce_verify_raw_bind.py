"""Verify every accepted cell directly against original CSV row and vendor column."""
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

LINE=Path(__file__).resolve().parents[1]
OUT=LINE/'outputs/stage265_deep_daily'
SUFFIX={'open':'open','high':'high','low':'low','close':'cl','volume':'vol','open_interest':'oi'}


def main():
    checked=0;cells=0;keys=set();inputs={}
    for output in sorted((OUT/'czce').glob('work_*_fullmarket_bars.csv')):
        table=output.name.removeprefix('work_').removesuffix('_fullmarket_bars.csv')
        source={}
        for f,suffix in SUFFIX.items():
            path=OUT/f'opensource/work_{table}_data_{suffix}.raw'
            source[f]=list(csv.DictReader(path.open(encoding='utf-8-sig',newline='')))
        inputs[output.name]=hashlib.sha256(output.read_bytes()).hexdigest()
        for row in csv.DictReader(output.open(encoding='utf-8-sig',newline='')):
            key=row['contract_epoch_id'],row['date']
            if key in keys:raise AssertionError('duplicate_epoch_date')
            keys.add(key)
            positions=json.loads(row['source_field_rows'])
            for field in SUFFIX:
                original=source[field][positions[field]-2]
                assert original['']==row['date']
                raw=original[row['vendor_contract']]
                assert raw.strip() and float(raw)==float(row[field]),(row,field)
                cells+=1
            product,digits=re.fullmatch(r'([A-Z]+)([0-9]{3,4})\.CZC',row['vendor_contract']).groups()
            delivery=row['contract_yyyymm'];modulus=10 if len(digits)==3 else 100
            assert int(delivery[:4])%modulus==int(digits[:-2])
            assert delivery[-2:]==digits[-2:]
            assert row['product']==product+'.CZCE'
            assert row['contract_epoch_id'].endswith('@'+delivery)
            assert '2010-01-01'<=row['date']<='2026-10-16'
            checked+=1
    report={'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'status':'all_accepted_cells_match_raw_coordinates',
        'accepted_rows_checked':checked,'field_cells_checked':cells,'duplicate_epoch_dates':0,'source_input_sha256':inputs,
        'limits':'Direct cell/identity representation verification only; does not certify source vendor, exchange listing, data license, complete lifecycle, or time-clock compatibility.',
        'database_writes':0,'training_runs':0,'backtest_runs':0}
    (OUT/'czce/work_fullmarket_raw_bind_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='source_input_sha256'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
