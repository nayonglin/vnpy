"""One Stage444-bound header probe; never parse original COT data rows."""
import ast
import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

LINE = Path('/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai')
OUT = LINE / 'outputs/stage446_cot_concentration_header/actual_run1'
SCOPE = LINE / 'outputs/stage444_cot_concentration_scope/scope.json'
COUNTS = {'metadata_json_file_reads': 0, 'existing_code_file_reads': 0,
          'own_script_reads': 0, 'original_zip_read_bytes_calls': 0,
          'zipfile_bytesio_instances': 0, 'original_member_open_calls': 0,
          'original_member_readline_calls': 0, 'original_data_rows_parsed': 0,
          'other_original_zip_reads': 0, 'mapped_or_canonical_row_reads': 0,
          'network': 0, 'downloads': 0, 'market_API': 0, 'SQL': 0,
          'price_Y_score_reads': 0, 'new_q_build': 0, 'fit': 0, 'cash': 0,
          'actual_forward_D': 0, 'test_suite': 0}


def binding(path, body):
    return {'path': str(path), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def read_bound(spec, kind):
    path = Path(spec['path'])
    COUNTS[kind] += 1
    body = path.read_bytes()
    actual = binding(path, body)
    assert actual == spec, (actual, spec)
    return body


def read_json(spec):
    return json.loads(read_bound(spec, 'metadata_json_file_reads'))


def main():
    assert not OUT.exists(), 'One actual run only; existing run must not be replaced.'
    scope_spec = {'path': str(SCOPE), 'bytes': 4599,
                  'sha256': 'b275a60e0210f62520687f39db501418bb1bebd334272f2f9213a3db6c5db64e'}
    scope = read_json(scope_spec)
    assert scope['line_id'] == LINE.name and not scope['financial_authorized']
    source = read_json(scope['inputs']['source_manifest407'])
    parsed = read_json(scope['inputs']['parsed_manifest407'])
    summary = read_json(scope['inputs']['source_summary407'])
    del source  # Bound metadata only; no downloader is imported or executed.
    schema_bindings = {x['path']: x for x in summary['schema_bindings']}
    year_schemas = []
    for year in sorted(parsed['years'], key=lambda x: x['year']):
        spec = year['outputs']['schema']
        assert schema_bindings[spec['path']] == spec
        schema = read_json(spec)
        assert schema['source_zip'] == year['source_zip'] and schema['year'] == year['year']
        members = [x for x in schema['members'] if 'original_header' in x]
        assert len(members) == 1
        year_schemas.append((year['year'], spec, schema['source_zip'], members[0]))
    assert [x[0] for x in year_schemas] == list(range(2010, 2026))
    origin = scope['one_original_header']
    assert origin == year_schemas[0][2]
    assert origin['bytes'] == 1004704
    assert origin['sha256'] == 'fef4827fbaa1a2a72ad3fe7ef0ca659ee4c85bc6857fdc096f4320b8a096322b'
    zip_bytes = read_bound(origin, 'original_zip_read_bytes_calls')
    COUNTS['zipfile_bytesio_instances'] += 1
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        text_members = [x for x in archive.infolist() if not x.is_dir() and x.filename.lower().endswith(('.txt', '.csv'))]
        assert len(text_members) == 1
        member = text_members[0]
        COUNTS['original_member_open_calls'] += 1
        with archive.open(member) as handle:
            COUNTS['original_member_readline_calls'] += 1
            header_bytes = handle.readline()
    encoding = year_schemas[0][3]['encoding']
    header_text = header_bytes.decode(encoding)
    header = next(csv.reader([header_text]))
    assert header == year_schemas[0][3]['original_header']
    # The exact spelling is observed in this header, not normalized or aliased.
    pattern = re.compile(r'^Conc_(Gross|Net)_LE_(4|8)_TDR_(Long|Short)_(All|Old|Other)$')
    fields = [{'name': name, 'index_zero_based': i, 'gross_or_net': hit[1],
               'largest_traders': int(hit[2]), 'side': hit[3], 'contract_group': hit[4]}
              for i, name in enumerate(header) if (hit := pattern.fullmatch(name))]
    assert len(fields) == 24 and len({x['name'] for x in fields}) == 24
    names = [x['name'] for x in fields]
    annual = []
    for year, spec, source_spec, saved_member in year_schemas:
        saved_header = saved_member['original_header']
        annual.append({'year': year, 'schema_binding': spec, 'source_zip_binding_metadata_only': source_spec,
                       'member': saved_member['member'], 'header_columns': len(saved_header),
                       'selected_fields': [x for x in saved_header if pattern.fullmatch(x)],
                       'missing_selected_fields': [x for x in names if saved_header.count(x) != 1],
                       'full_header_equal_to_observed_2010': saved_header == header})
    parser_spec = parsed['parser']
    aggregate_spec = summary['aggregation_script']
    parser_text = read_bound(parser_spec, 'existing_code_file_reads').decode('utf-8')
    aggregate_text = read_bound(aggregate_spec, 'existing_code_file_reads').decode('utf-8')
    constants = {n.targets[0].id: ast.literal_eval(n.value) for n in ast.parse(parser_text).body
                 if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                 and n.targets[0].id in ('FIELDS', 'EXTRA_IDENTITIES')}
    numeric_roles = ('pmpu_long', 'pmpu_short', 'mm_long', 'mm_short', 'open_interest')
    assert all(name not in sum(constants['FIELDS'].values(), []) + constants['EXTRA_IDENTITIES'] for name in names)
    assert '"original_numeric_fields": numbers' in parser_text
    assert '"pmpu_long", "pmpu_short", "mm_long", "mm_short", "open_interest"' in parser_text
    assert 'row = dict(original[0])' in aggregate_text
    assert 'Conc_' not in parser_text and 'Conc_' not in aggregate_text
    COUNTS['own_script_reads'] += 1
    own_path = Path(__file__).resolve()
    own_binding = binding(own_path, own_path.read_bytes())
    receipt = {'schema': 'stage446_bound_cot_concentration_header_probe_v1',
               'at': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'line_id': LINE.name,
               'scope_binding': scope_spec, 'script_binding': own_binding,
               'execution_counts_scope': 'This one probe invocation; earlier preflight used allowed text/code/schema metadata only and no original ZIP.',
               'execution_counts': COUNTS, 'original_zip_binding': origin,
               'original_member': {'name': member.filename, 'declared_uncompressed_bytes': member.file_size,
                                   'compressed_bytes': member.compress_size, 'declared_crc32': f'{member.CRC:08x}',
                                   'CRC_revalidated_this_probe': False, 'reason': 'header only; no EOF read'},
               'header': {'bytes': len(header_bytes), 'sha256': hashlib.sha256(header_bytes).hexdigest(),
                          'encoding_from_bound407_schema': encoding, 'raw_text': header_text,
                          'columns': header, 'column_count': len(header), 'readline_calls': 1,
                          'matches_bound2010_schema': True},
               'concentration_fields': fields, 'concentration_field_count': len(fields),
               'contract_groups': {group: [x['name'] for x in fields if x['contract_group'] == group]
                                   for group in ('All', 'Old', 'Other')},
               'existing_16_year_schema_check': annual,
               'all_16_year_schemas_have_all_24_exact_columns_once': all(not x['missing_selected_fields'] for x in annual),
               'all_16_full_headers_equal_to_2010': all(x['full_header_equal_to_observed_2010'] for x in annual),
               'existing_storage_static_code_evidence': {'parser_binding': parser_spec, 'aggregate_binding': aggregate_spec,
                  'parser_FIELDS': constants['FIELDS'], 'parser_EXTRA_IDENTITIES': constants['EXTRA_IDENTITIES'],
                  'numeric_value_roles': list(numeric_roles), 'mapped_stores_concentration_values': False,
                  'canonical_stores_concentration_values': False,
                  'basis': 'Bound parser stores five numeric roles, H/MM, identities and original-row token hash; bound aggregate copies mapped records. Header names live in schema; original values remain in raw ZIP only.',
                  'mapped_or_canonical_rows_opened': 0},
               'source_summary_binding': scope['inputs']['source_summary407'],
               'parsed_manifest_binding': scope['inputs']['parsed_manifest407'],
               'unknown_not_inferred': ['numeric nonmissingness', 'numeric coverage by market/date', 'release or first-seen clock',
                                       'strict PIT/vintage', 'independent information', 'long alpha', 'financial or production qualification'],
               'semantics_boundary': 'Largest reportable traders across categories; not Managed Money identity. All/Old/Other are distinct contract group headers, not three additive concentration ratios.',
               'financial_authorized': False, 'overfit_after': 'No new outcome/parameter selection; inherited adaptive topic-selection risk remains.',
               'value_after': 'Finite source/storage distinction is useful; no numeric parsing, q construction or financial experiment is authorized.'}
    assert receipt['all_16_year_schemas_have_all_24_exact_columns_once']
    OUT.mkdir(parents=True, exist_ok=False)
    body = (json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    (OUT / 'receipt.json').write_bytes(body)
    print(json.dumps({'receipt': binding(OUT / 'receipt.json', body), 'field_count': len(fields),
                      'schema_years': len(annual), 'full_headers_identical': receipt['all_16_full_headers_equal_to_2010'],
                      'execution_counts': COUNTS}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
