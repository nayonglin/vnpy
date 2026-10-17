"""Observed CZCE product-source matrix; no guessed listing/expiry or coverage."""
import csv
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

LINE=Path(__file__).resolve().parents[1]
OUT=LINE/'outputs/stage265_deep_daily/czce'
MONTHLY='https://www.czce.com.cn/cn/rootfiles/2025/07/04/1750859895384730-1750859895409197.pdf'
PL_PRIMARY='https://www.czce.com.cn/cn/gyjys/jysdt/ggytz/webinfo/2025/07/1750860251945899.htm'
PL_REPORT='https://www.czce.com.cn/cn/content_file/gyjys/qhscyjcs/cgxc/2026/4/077939e9d8fc4ad088cd76a52ed8d3a0.pdf'
NAMES=dict(x.split(':') for x in 'AP:苹果 CF:棉花 CJ:红枣 CY:棉纱 FG:玻璃 JR:粳稻 LR:晚籼稻 MA:甲醇 OI:菜籽油 PF:短纤 PK:花生 PL:丙烯 PM:普通小麦 PR:瓶片 PX:对二甲苯 RI:早籼稻 RM:菜籽粕 RS:油菜籽 SA:纯碱 SF:硅铁 SH:烧碱 SM:锰硅 SR:白糖 TA:PTA UR:尿素 WH:优质强筋小麦 ZC:动力煤'.split())


def main():
    summary=json.loads((OUT/'work_fullmarket_summary.json').read_text())
    rows=[]
    meta=summary['actual_metadata_product_codes']
    accepted=summary['accepted_by_product']
    for code in sorted(set(NAMES)|{p.split('.')[0] for p in meta}):
        product=code+'.CZCE'
        bars=accepted.get(product,{})
        rows.append({'product':product,'product_name':NAMES.get(code,'原始历史代码，未改名'),
            'official_catalog_evidence_status':'official_monthly_2025_06_product' if code in NAMES and code!='PL' else 'official_report_supports_PL_listing_2025_07_22' if code=='PL' else 'historical_vendor_code_preserved_not_current_catalog',
            'official_catalog_source':MONTHLY if code in NAMES and code!='PL' else PL_REPORT if code=='PL' else 'unknown',
            'work_snapshot_metadata_rows':meta.get(product,0),'work_complete_six_field_rows':bars.get('rows',0),
            'work_complete_contract_epochs':bars.get('epochs',0),'work_complete_first_date':bars.get('first_date','unknown'),'work_complete_last_date':bars.get('last_date','unknown'),
            'product_level_listing_date_from_these_inventory_sources':'unknown' if code!='PL' else '2025-07-22 (product-level only)',
            'per_contract_listing_or_expiry_unknown':True,'2019_to_2026_work_snapshot_coverage':'none_snapshot_2018_04_26',
            'all_historical_contracts_2010_to_2026_certified':False})
    with (OUT/'source_product_inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    report={'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'exchange':'CZCE','requested_all_market_date_scope':['2010-01-01','2026-10-16'],
        'official_catalog_known_products':sorted(NAMES),'official_catalog_known_count':len(NAMES),
        'official_catalog_boundary':'26 products enumerated in official 2025-06 monthly report, plus PL listing confirmed by official 2025 service-economy report published 2026-04. This is a documented source inventory, not an assertion that no later product listing exists.',
        'official_products_not_in_2018_work_snapshot':sorted(set(NAMES)-set(summary['downloaded_product_tables'])),
        'source_urls':[MONTHLY,PL_PRIMARY,PL_REPORT],
        'source_acquisition_note':'Primary PDF monthly content was read using web open; full PDF is not downloaded/hashed locally. PL official report search extract supports 2025-07-22 listing; a direct web open timed out. No official per-contract date was inferred from these catalog pages.',
        'products':rows,'universe_completeness_status':'not_certified_pending_all_market_daily_source_and_exchange_listing_crosscheck',
        'normal_http_archive_probe_receipt':'official_archive_probe_requests.json',
        'source_decisions':[{'source':'CZCE official yearly ZIP','decision':'3 ordinary public HTTPS GET probes (2010,2015,2025 path families) returned 412 HTML; not data-unavailable proof; no bypass attempted'},
            {'source':'ildhj0116/Work','decision':'Pinned 2018-04-26 CSV snapshot with verified Git blobs; use isolated raw/coverage evidence only; no vendor data redistribution rights established'},
            {'source':'SubjectNoi/daily-future-and-option-China','decision':'Inspected saved repository tree contains DCE/SHFE but no CZCE; cannot fill CZCE contracts'},
            {'source':'AKShare get_futures_daily','decision':'Inspected official source wrapper uses exchange static endpoints. Code support is not independent old-contract data; the same CZCE HTTP limitation applies'},
            {'source':'Sina/main continuous/paid vendor skills','decision':'Not accepted as full old-contract evidence. A supported API or README cannot prove archived real-contract coverage; paid/registration/trial routes not used'}],
        'database_writes':0,'training_runs':0,'backtest_runs':0,'minute_downloads':0}
    (OUT/'source_product_inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('official_catalog_known_count','official_products_not_in_2018_work_snapshot','universe_completeness_status')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
