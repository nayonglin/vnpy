"""Create a new reviewed recap from verified records.json, without recalculating charts.

Usage: python stage020_review_finalizer.py PARENT_RECAP REVIEW.md NEW_OUTPUT
The optional REVIEW.json may bind source_manifest_sha256 and/or
parent_render_summary_sha256; supplied bindings must match. Review conclusions
are copied verbatim, never promoted automatically to a performance certificate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import pandas as pd

from stage001_frozen_recap import CANONICAL, REQUIRED, load_display_functions, sha256


def finalize(parent: Path, report: Path, output: Path) -> dict:
    parent, report, output = (Path(value).resolve() for value in (parent, report, output))
    if output == parent or parent in output.parents or output in parent.parents:
        raise ValueError('output_must_be_isolated_from_parent')
    if output.exists():
        raise FileExistsError(output)
    summary = json.loads((parent / 'summary.json').read_text(encoding='utf-8'))
    artifacts = summary['artifact_sha256']
    for required in ('records.json', 'residual_open_positions.json', 'chart_manifest.csv'):
        if required not in artifacts:
            raise ValueError('parent_artifact_not_bound:' + required)
    for name, digest in artifacts.items():
        if Path(name).name != name or not (parent / name).is_file() or sha256(parent / name) != digest:
            raise ValueError('parent_artifact_changed:' + name)
    source = Path(summary['source_directory']).resolve()
    if output == source or source in output.parents or output in source.parents:
        raise ValueError('output_must_be_isolated_from_source')
    source_manifest_hash = sha256(source / 'manifest.json')
    if source_manifest_hash != summary['source_manifest_sha256']:
        raise ValueError('source_manifest_changed')
    identity = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    names = list(REQUIRED)
    if (source / 'residual_open_positions.json').exists():
        names.append('residual_open_positions.json')
    for name in names:
        if identity['hashes'].get(name) != sha256(source / name):
            raise ValueError('source_hash_changed:' + name)
    metrics = json.loads((source / 'summary.json').read_text(encoding='utf-8'))
    if metrics != summary['backtest_metrics']:
        raise ValueError('source_metrics_changed')
    if Path(summary['canonical_renderer']).resolve() != CANONICAL or sha256(CANONICAL) != summary['canonical_renderer_sha256']:
        raise ValueError('canonical_renderer_changed')
    records = json.loads((parent / 'records.json').read_text(encoding='utf-8'))
    if len(records) != summary['chart_episodes']:
        raise ValueError('cache_record_count_changed')
    record_ids = [str(row['meta']['open_trade_id']) for row in records]
    chart_manifest = pd.read_csv(parent / 'chart_manifest.csv')
    if len(set(record_ids)) != len(record_ids) or set(record_ids) != set(chart_manifest['open_trade_id'].astype(str)):
        raise ValueError('cache_episode_identity_changed')
    residual = json.loads((parent / 'residual_open_positions.json').read_text(encoding='utf-8'))
    if residual != summary['residual_open_positions']:
        raise ValueError('residual_identity_changed')

    review_json = report if report.suffix.lower() == '.json' else report.with_suffix('.json')
    review_metadata = json.loads(review_json.read_text(encoding='utf-8')) if review_json.exists() else {}
    if not isinstance(review_metadata, dict):
        raise ValueError('review_metadata_must_be_object')
    if 'source_manifest_sha256' in review_metadata and review_metadata['source_manifest_sha256'] != source_manifest_hash:
        raise ValueError('review_source_binding_mismatch')
    parent_summary_hash = sha256(parent / 'summary.json')
    if 'parent_render_summary_sha256' in review_metadata and review_metadata['parent_render_summary_sha256'] != parent_summary_hash:
        raise ValueError('review_parent_binding_mismatch')
    for name, digest in review_metadata.get('files_hashes', {}).items():
        if identity['hashes'].get(name) != digest:
            raise ValueError('review_source_file_binding_mismatch:' + name)
    review_hash = sha256(report)

    metadata = pd.read_csv(source / 'contract_metadata.csv')
    trades = pd.read_csv(source / 'trades.csv')
    if metadata['vt_symbol'].duplicated().any():
        raise ValueError('duplicate_contract_metadata')
    if not set(trades['vt_symbol']).issubset(set(metadata['vt_symbol'])):
        raise ValueError('trade_contract_metadata_missing')
    if 'exchange' not in metadata:
        metadata['exchange'] = metadata['vt_symbol'].str.split('.').str[-1]
    if 'product_vt_symbol' in metadata:
        metadata['_product_key'] = metadata['product_vt_symbol'].astype(str)
    else:
        product = metadata['product'].astype(str) if 'product' in metadata else metadata['vt_symbol'].str.split('.').str[0].str.replace(r'\d+', '', regex=True)
        metadata['_product_key'] = product + '.' + metadata['exchange'].astype(str)
    traded = metadata[metadata['vt_symbol'].isin(trades['vt_symbol'])]
    facts = {
        'input_product_count':int(metadata['_product_key'].nunique()),
        'input_exchanges':sorted(metadata['exchange'].astype(str).unique().tolist()),
        'traded_product_count':int(traded['_product_key'].nunique()),
        'traded_exchanges':sorted(traded['exchange'].astype(str).unique().tolist()),
        'residual_quote_dates':[],
    }
    market = pd.read_csv(source / 'market_daily.csv', usecols=['vt_symbol', 'date'])
    market['date'] = pd.to_datetime(market['date'], errors='raise').dt.normalize()
    market = market[market['date'].le(pd.Timestamp(identity['end']).normalize())]
    last_quotes = market.groupby('vt_symbol')['date'].max()
    for row in residual:
        symbol = str(row['vt_symbol'])
        last_quote = last_quotes.get(symbol)
        facts['residual_quote_dates'].append({
            'vt_symbol':symbol, 'direction':str(row['direction']), 'volume':float(row['volume']),
            'last_quote_date':pd.Timestamp(last_quote).date().isoformat() if pd.notna(last_quote) else None,
        })
    display = [f"输入{facts['input_product_count']}品种/{len(facts['input_exchanges'])}所（{'、'.join(facts['input_exchanges'])}），实际成交{facts['traded_product_count']}品种/{len(facts['traded_exchanges'])}所（{'、'.join(facts['traded_exchanges'])}）"]
    if metrics.get('max_actual_products') is not None:
        facts['max_actual_products'] = metrics['max_actual_products']
        display.append(f"最大同时持仓品种{int(metrics['max_actual_products'])}")
    if metrics.get('last_fill_date') is not None:
        facts['last_fill_date'] = metrics['last_fill_date']
        display.append(f"末次成交{metrics['last_fill_date']}")
    if residual:
        details = []
        for item in facts['residual_quote_dates']:
            direction = {'long':'多', 'short':'空'}.get(item['direction'], item['direction'])
            last = item['last_quote_date'] or '缺失'
            details.append(f"{item['vt_symbol']}（{direction}{item['volume']:g}手，最后报价{last}）")
        display.append(f"{len(residual)}项残余仓位：" + '；'.join(details))
    else:
        display.append('期末无残余仓位')
    display.append('独立审查报告：' + report.name)
    if review_metadata.get('verdict') is not None:
        verdict = review_metadata['verdict']
        display.append('审查结论：' + (verdict if isinstance(verdict, str) else json.dumps(verdict, ensure_ascii=False)))
    summary['source_warning'] += ' 审查补充：' + '。'.join(display) + '。'
    summary['review_display_facts'] = facts
    summary['independent_review'] = {
        'path':str(report), 'sha256':review_hash,
        'metadata_path':str(review_json) if review_json.exists() else None,
        'metadata_sha256':sha256(review_json) if review_json.exists() else None,
        'source_binding_verified':bool(review_metadata.get('source_manifest_sha256') or review_metadata.get('files_hashes')),
        'metadata':review_metadata,
    }
    summary['parent_render_summary_sha256'] = parent_summary_hash
    summary['review_finalizer_sha256'] = sha256(Path(__file__))
    summary['serialized_records_reused'] = True
    # _html is the same canonical function; chart coordinates and bars are untouched.
    renderer = load_display_functions({})
    page = renderer._html(records, summary)
    output.mkdir(parents=True)
    for name in artifacts:
        if name not in ('summary.json', 'index.html'):
            shutil.copy2(parent / name, output / name)
    if report.suffix.lower() == '.json':
        shutil.copy2(report, output / 'independent_review.json')
        if report.with_suffix('.md').exists():
            shutil.copy2(report.with_suffix('.md'), output / 'independent_review.md')
    else:
        shutil.copy2(report, output / 'independent_review.md')
        if review_json.exists():
            shutil.copy2(review_json, output / 'independent_review.json')
    (output / 'index.html').write_text(page, encoding='utf-8')
    summary['artifact_sha256'] = {path.name:sha256(path) for path in output.iterdir() if path.name != 'summary.json'}
    (output / 'summary.json').write_text(json.dumps(renderer._json_safe(summary), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent', type=Path)
    parser.add_argument('review', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = finalize(args.parent, args.review, args.output)
    print(json.dumps({'run_id':result['run_id'], 'chart_episodes':result['chart_episodes'], 'facts':result['review_display_facts']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
