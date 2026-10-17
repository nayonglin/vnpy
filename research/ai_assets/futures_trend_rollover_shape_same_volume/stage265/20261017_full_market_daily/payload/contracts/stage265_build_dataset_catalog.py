"""Publish a local entry point for downloaded full-market daily source layers.

This catalog does not merge price/quantity semantics or qualify training data.
It uses frozen download receipts and the complete current-contract census.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path

LINE = Path(__file__).resolve().parents[1]
BASE = LINE / 'outputs/stage265_deep_daily'


def load(relative):
    return json.loads((BASE / relative).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    history = load('rqalpha/full_market_inventory_summary.json')
    audit = load('czce/rqalpha_independent_audit.json')
    bundle = load('rqalpha/bundle_download_status.json')
    recent = load('tq_latest/recent_download_status.json')
    current = load('tq_latest/current_futures_catalog.json')
    official = load('other_exchanges/official_reference_catalog.json')
    census = load('other_exchanges/latest_trade_date_census.json')
    dce = load('dce/official_fullmarket_normalization.json')
    product_count = sum(value['datasets'] > 0 for value in history['by_product'].values())
    current_set = set(current['symbols'])
    observed = {}
    for item in census['products']:
        exchange = item['exchange']
        zero = set(item['zero_trade_contracts'])
        for symbol in item['contracts']:
            observed[exchange + '.' + symbol] = {
                'source': 'official_daily_or_monthly', 'last_observed_date': census['trade_date'],
                'status': 'official_no_trade_missing_prices' if symbol in zero else 'official_daily_observation',
            }
    for symbol, item in recent['items'].items():
        if item['status'] != 'downloaded':
            raise ValueError('incomplete recent source: ' + symbol)
        observed[symbol] = {'source': 'tqsdk_ordinary_daily',
            'last_observed_date': item['last_date'],
            'status': 'raw_daily_observations' if item['rows'] else 'ready_empty_no_trade_price_observed'}
    missing = sorted(current_set - set(observed))
    if missing:
        raise ValueError('current contract source not downloaded: ' + ','.join(missing))
    if history['real_contracts_with_dataset'] != audit['real_delivery_datasets']:
        raise ValueError('independent real-contract count differs')
    rows = [{'symbol': symbol, 'exchange': symbol.split('.')[0],
             'in_current_directory': symbol in current_set, **observed[symbol]}
            for symbol in sorted(observed)]
    with (BASE / 'current_contract_source_census.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    inputs = [
        'rqalpha/bundle_download_status.json', 'rqalpha/full_market_inventory_summary.json',
        'czce/rqalpha_independent_audit.json', 'czce/rqalpha_independent_count_reconciliation.json',
        'dce/official_fullmarket_manifest.json', 'dce/official_fullmarket_verification.json',
        'dce/independent_review_stage265_dce_rq_verdict.json',
        'other_exchanges/official_reference_catalog.json', 'other_exchanges/official_self_validation.json',
        'other_exchanges/latest_trade_date_census.json',
        'tq_latest/current_futures_catalog.json', 'tq_latest/recent_download_status.json',
        'current_contract_source_census.csv',
    ]
    for optional in [
        'tq_latest/independent_review_stage265_tq_tail.json',
        'tq_latest/independent_review_stage265_tq_tail_empty_quotes.json',
        'czce/other_exchanges_independent_review.json',
        'primary_integrity.json',
    ]:
        if (BASE / optional).exists():
            inputs.append(optional)
    scope_rows = sum(x['rows_in_scope'] for x in audit['exchange_counts'].values())
    catalog = {
        'generated_at': datetime.now().astimezone().isoformat(),
        'line_id': LINE.name, 'scope': 'six domestic futures exchanges; all real futures delivery contracts, including historical retired families and monthly-average F contracts',
        'target_start': '2010-01-01', 'latest_complete_trading_day': '2026-10-16',
        'download_status': 'sources_downloaded_and_current_contract_directory_fully_accounted',
        'training_qualification': False,
        'historical_library': {'source': 'RQAlpha public 202610 bundle',
            'raw_daily_path': 'rqalpha/futures.h5', 'metadata_path': 'rqalpha/futures_metadata.json',
            'calendar_path': 'rqalpha/trading_dates.npy',
            'real_delivery_datasets': history['real_contracts_with_dataset'],
            'historical_product_codes_with_data': product_count,
            'metadata_product_codes_including_no_data_pre2010': len(history['product_codes']),
            'rows_2010_through_20260930': scope_rows,
            'source_archive_bytes': (BASE / 'rqalpha/rqbundle_202610.tar.bz2').stat().st_size,
            'source_archive_sha256': bundle['archive_sha256'],
            'by_exchange': history['by_exchange'],
            'candidate_lifetime_calendar_missing_raw_days_2010_onward': sum(x['missing_target_raw_observations'] for x in history['by_exchange'].values()),
            'coverage_limit': 'against this vendor metadata/calendar, not an exchange-certified proof of every historical listing',
        },
        'official_crosscheck_layers': {
            'SHFE_INE_CFFEX': {'source_count': official['source_count'],
                'source_bytes_including_stage264_reuse': official['source_bytes_including_stage264_reuse'],
                'unique_daily_rows': official['ordinary_accepted_rows'],
                'catalog': 'other_exchanges/official_reference_catalog.json'},
            'DCE': {'normalization': 'dce/official_fullmarket_normalization.json',
                'data': 'dce/official_fullmarket_daily.csv', 'raw_packages': 229,
                'date_scope': '2006-2022', 'unique_daily_rows': dce['unique_valid_rows'],
                'contract_epochs': dce['contract_count'],
                'data_sha256': dce['normalized_unique_sha256']},
            'CZCE_backup': {'data_tables': [str(p.relative_to(BASE)) for p in sorted((BASE / 'czce').glob('work_*_fullmarket_bars.csv'))],
                'summary': 'czce/work_fullmarket_summary.json',
                'status': 'local GitHub archival crosscheck, not official licensed production source'},
        },
        'latest_market_census': {'directory_count': len(current_set),
            'directory_by_exchange': dict(Counter(s.split('.')[0] for s in current_set)),
            'missing_source_contracts': missing, 'extra_recent_expired_contracts': sorted(set(observed) - current_set),
            'census_path': 'current_contract_source_census.csv',
            'tqsdk_downloaded_symbols': len(recent['items']),
            'tqsdk_empty_symbols': sorted(s for s, x in recent['items'].items() if x['rows'] == 0),
            'future_or_incomplete_daily_rows_excluded': sum(x['future_or_incomplete_rows_excluded'] for x in recent['items'].values()),
        },
        'quality_contract': {
            'raw_preserved': True, 'units_converted': False, 'cross_source_prices_blended': False,
            'zero_volume': 'raw flat or blank prices do not count as observed traded candles or AM120 history',
            'invalid_positive_volume_ohlc_2010_onward': audit['quality_issue_reasons']['positive_volume_invalid_ohlc_geometry'],
            'candidate_listing_conflict_rows': audit['quality_issue_reasons']['before_candidate_listing'],
            'pre_2010_calendar_conflict': '214 raw rows on 2006-01-26/27 absent from vendor calendar; raw retained and outside primary scope',
            'quantity_contract': 'source/year dependent volume units and closing OI; source disputes kept separate',
            'point_in_time': 'ex-post archives do not establish contemporaneous publication bytes',
            'licenses': 'download access is not blanket commercial authorization; raw files stay local and are not redistributed',
        },
        'source_receipts': [{'path': p, 'bytes': (BASE / p).stat().st_size, 'sha256': sha(BASE / p)} for p in inputs],
        'safety': {'main_database_writes': 0, 'production_changes': 0, 'new_minute_downloads': 0,
            'financial_backtests': 0, 'model_fits': 0, 'order_api_calls': 0},
    }
    (BASE / 'data_catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'history_contracts': history['real_contracts_with_dataset'],
        'products_with_data': product_count, 'history_rows_in_scope': scope_rows,
        'current_directory': len(current_set), 'missing_current_sources': missing,
        'catalog': str(BASE / 'data_catalog.json')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
