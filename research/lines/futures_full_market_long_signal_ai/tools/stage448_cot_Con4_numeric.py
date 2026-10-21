"""Fixed two-field COT source projection. Actual run requires root's code-bound authorization."""
import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.dont_write_bytecode = True
from stage407_cot_parse_year import FIXED_MAPPING, _dates

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE / 'outputs/stage448_cot_Con4_numeric'
OUT = ROOT / 'actual_run1'
SCOPE = {'path': str(LINE / 'outputs/stage447_cot_concentration_root_decision/next_scope.json'),
         'bytes': 5073, 'sha256': 'ff5b700ac93499739a09d4afb1c6680af1864f86015db563d833bd327b190760'}
LEFT = 'Conc_Net_LE_4_TDR_Long_All'
RIGHT = 'Conc_Net_LE_4_TDR_Short_All'


def numeric(token):
    if token is None or not token.strip():
        return None, 'missing'
    try:
        value = Decimal(token.strip())
    except InvalidOperation:
        return None, 'malformed'
    if not value.is_finite():
        return None, 'nonfinite'
    if value < 0 or value > 100:
        return None, 'out_of_range'
    return value, 'reported_finite_0_to_100'


def pair(left, right):
    lval, lstatus = numeric(left)
    rval, rstatus = numeric(right)
    reasons = [side + ':' + status for side, value, status in
               [('long', lval, lstatus), ('short', rval, rstatus)] if value is None]
    con = None
    if not reasons:
        if lval + rval == 0:
            reasons.append('denominator_zero')
        else:
            con = float((lval - rval) / (lval + rval))
    return {'long_pct': float(lval) if lval is not None else None,
            'short_pct': float(rval) if rval is not None else None, 'Con4Net_All': con,
            'long_parse_status': lstatus, 'short_parse_status': rstatus, 'unknown_reasons': reasons}


def parse_member(stream, year, source, member, expected_header):
    """One CSV pass; retain only fixed eight codes and seven exact raw tokens."""
    date_header = 'Report_Date_as_MM_DD_YYYY' if year <= 2012 else 'Report_Date_as_YYYY-MM-DD'
    fields = ['Market_and_Exchange_Names', 'As_of_Date_In_Form_YYMMDD', date_header,
              'CFTC_Contract_Market_Code', 'FutOnly_or_Combined', LEFT, RIGHT]
    reader = csv.reader(stream)
    header = next(reader)
    assert header == expected_header
    assert all(header.count(name) == 1 for name in fields)
    positions = {name: header.index(name) for name in fields}
    reverse = {code: channel for channel, code in FIXED_MAPPING.items()}
    origins, scanned = [], 0
    previous_line = reader.line_num
    for tokens in reader:
        first_line, previous_line = previous_line + 1, reader.line_num
        if not tokens or not any(x.strip() for x in tokens):
            continue
        scanned += 1
        selected = {name: tokens[index] if index < len(tokens) else None for name, index in positions.items()}
        code = (selected['CFTC_Contract_Market_Code'] or '').strip()
        if code not in reverse:
            continue
        dates = _dates({'asof_yymmdd': selected['As_of_Date_In_Form_YYMMDD'],
                        'report_date': selected[date_header]})
        origins.append({'source_zip': source, 'source_year': year, 'member': member,
                        'line_number': first_line, 'last_line_number': reader.line_num,
                        'original_row_tokens_sha256': hashlib.sha256(json.dumps(tokens, sort_keys=True,
                           separators=(',', ':'), ensure_ascii=True).encode('ascii')).hexdigest(),
                        'channel': reverse[code], 'asof': dates['date'], 'asof_status': dates['status'],
                        'row_shape_matches_header': len(tokens) == len(header), 'tokens': selected})
    return origins, scanned


def resolve_slot(asof, channel, code, origins):
    row = {'asof': asof, 'channel': channel, 'market_code': code, 'observed_origins': origins,
           'publication_available_at': None, 'strict_firstseen': False,
           'clock408': 'retained_not_yet_applied'}
    if not origins:
        values = pair(None, None)
        values['unknown_reasons'].append('no_original_row_for_fixed_code_asof')
    elif len({x['original_row_tokens_sha256'] for x in origins}) != 1:
        values = {'long_pct': None, 'short_pct': None, 'Con4Net_All': None,
                  'long_parse_status': 'conflicting_original_rows', 'short_parse_status': 'conflicting_original_rows',
                  'unknown_reasons': ['conflicting_original_rows']}
    else:
        values = pair(origins[0]['tokens'][LEFT], origins[0]['tokens'][RIGHT])
        if any(not x['row_shape_matches_header'] for x in origins):
            values['unknown_reasons'].append('row_shape_differs_from_header')
        if any((x['tokens']['FutOnly_or_Combined'] or '').strip() != 'FutOnly' for x in origins):
            values['unknown_reasons'].append('report_family_not_FutOnly')
        if any(x['asof'] != asof for x in origins):
            values['unknown_reasons'].append('asof_conflict')
        if values['unknown_reasons']:
            values['Con4Net_All'] = None
    return {**row, **values, 'status': 'known_Con' if values['Con4Net_All'] is not None else 'explicit_unknown'}


def bind(path, body):
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def read_bound(spec):
    body = Path(spec['path']).read_bytes()
    assert bind(Path(spec['path']), body) == spec, 'Bound input changed: ' + spec['path']
    return body


def main(authorization_path):
    code_path = Path(__file__).resolve()
    code = bind(code_path, code_path.read_bytes())
    authorization = json.loads(Path(authorization_path).read_text())
    assert authorization == {'schema': 'stage448_numeric_actual_authorization_v1', 'authorized': True,
                             'code_sha256': code['sha256'], 'scope_sha256': SCOPE['sha256']}
    assert not OUT.exists(), 'One actual run only; do not replace existing run directory.'
    scope = json.loads(read_bound(SCOPE))
    assert scope['line_id'] == LINE.name and scope['project_fields'] == [LEFT, RIGHT]
    source = json.loads(read_bound(scope['inputs']['source_manifest407']))
    aggregate = json.loads(read_bound(scope['inputs']['aggregate407']))
    parsed = json.loads(read_bound(scope['inputs']['parsed_manifest407']))
    assert source['mapped_channels'] == aggregate['fixed_mapping_channels'] == FIXED_MAPPING
    read_bound(parsed['parser'])  # Bind the reused pure date parser; no downloader import.
    sources = {x['year']: x['body'] for x in source['year_requests']}
    years = sorted(parsed['years'], key=lambda x: x['year'])
    assert [x['year'] for x in years] == list(range(2010, 2026))
    dates = sorted({day for year in aggregate['source_year_stats'] for day in year['mapped_asof_dates']})
    assert len(dates) == 835 and len(FIXED_MAPPING) == 8
    OUT.mkdir(parents=True, exist_ok=False)  # Reserve the one run before original reads.
    groups, year_audits = defaultdict(list), []
    for year in years:
        tag, source_spec = year['year'], year['source_zip']
        assert source_spec == sources[tag]
        schema = json.loads(read_bound(year['outputs']['schema']))
        assert schema['source_zip'] == source_spec
        saved = [x for x in schema['members'] if 'original_header' in x]
        assert len(saved) == 1
        body = read_bound(source_spec)  # Exactly one bytes read, same bytes size/SHA and ZIP input.
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            members = [x for x in archive.infolist() if not x.is_dir()]
            assert len(members) == 1 and members[0].filename == saved[0]['member']
            with archive.open(members[0]) as raw:
                with io.TextIOWrapper(raw, encoding=saved[0]['encoding'], newline='') as text:
                    origins, scanned = parse_member(text, tag, source_spec, members[0].filename, saved[0]['original_header'])
        assert scanned == schema['identity_rows']
        assert len(origins) == schema['mapped_rows']
        for origin in origins:
            # Accepted407 sources had no unknown mapped dates; changed interpretation must stop, not invent a slot.
            assert origin['asof'] in dates, 'Unknown/out-of-grid mapped asof; stop without guessing publication/date.'
            groups[(origin['asof'], origin['channel'])].append(origin)
        year_audits.append({'year': tag, 'source_zip': source_spec, 'schema_binding': year['outputs']['schema'],
                            'ZIP_read_bytes_calls': 1, 'member_streams': 1, 'CSV_data_passes': 1,
                            'scanned_original_rows': scanned, 'retained_origins': len(origins), 'CRC_verified_to_EOF': True})
    rows = [resolve_slot(day, channel, code, groups.get((day, channel), []))
            for day in dates for channel, code in sorted(FIXED_MAPPING.items())]
    assert len(rows) == 6680
    table = defaultdict(Counter)
    token_status = Counter()
    rawtokens = 0
    for row in rows:
        stats = table[(row['asof'][:4], row['channel'])]
        stats['total'] += 1
        stats['knownpair'] += row['long_pct'] is not None and row['short_pct'] is not None
        stats['knownCon'] += row['Con4Net_All'] is not None
        reasons = row['unknown_reasons']
        for label, predicate in [('missing', any('missing' in x or 'no_original_row' in x for x in reasons)),
                                 ('denzero', 'denominator_zero' in reasons), ('outofrange', any('out_of_range' in x for x in reasons)),
                                 ('conflict', 'conflicting_original_rows' in reasons), ('unknown', bool(reasons))]:
            stats[label] += predicate
        for origin in row['observed_origins']:
            for name in (LEFT, RIGHT):
                token_status[numeric(origin['tokens'][name])[1]] += 1
                rawtokens += 1
    values = [row['Con4Net_All'] for row in rows if row['Con4Net_All'] is not None]
    destination = OUT / 'Con4Net_All_2010_2025.jsonl'
    data = ''.join(json.dumps(row, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n' for row in rows).encode('ascii')
    destination.write_bytes(data)
    receipt = {'schema': 'stage448_two_original_concentration_numeric_source_v1',
               'at': datetime.now(timezone.utc).isoformat(), 'code': code, 'scope': SCOPE, 'authorization': authorization,
               'date_parser': parsed['parser'], 'input_bindings': scope['inputs'],
               'clock408_reference_not_applied': scope['inputs']['clock408_reference_not_applied'],
               'output': bind(destination, data), 'grid_rows': len(rows), 'shared_position_dates': len(dates),
               'not_independent_publication_events_or_training_examples': True, 'original_year_audits': year_audits,
               'year_channel_stats': [{'year': year, 'channel': channel, **dict(counts)}
                                      for (year, channel), counts in sorted(table.items())],
               'rawtoken_count': rawtokens, 'rawtoken_parse_status_counts': dict(token_status),
               'Con4_range': [min(values), max(values)] if values else None,
               'execution_counts': {'original_ZIP_read_bytes': len(year_audits), 'original_member_streams': len(year_audits),
                   'original_CSV_data_passes': len(year_audits), 'old_mapped_canonical_row_reads': 0,
                   'network': 0, 'new_downloads': 0, 'market_API': 0, 'SQL': 0, 'price_Y_score_reads': 0,
                   'fit': 0, 'cash': 0, 'forward_D': 0, 'model_account_production_mutation': 0},
               'financial_qualified': False, 'publication_clock_applied': False, 'strict_firstseen': False}
    (OUT / 'receipt.json').write_text(json.dumps(receipt, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'receipt_path': str(OUT / 'receipt.json'), 'grid_rows': len(rows),
                      'knownCon': len(values), 'execution_counts': receipt['execution_counts']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', required=True, help='Root-issued exact code/scope authorization JSON')
    main(parser.parse_args().authorization)
