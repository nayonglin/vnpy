"""Bounded offline identity/rule coverage, never an account-deadline engine.

Import performs no I/O. Only main() reads fixed small JSON inputs and optionally
one mother CSV identity projection. No prices, SQL, models or cash entrypoints.
The root starts the actual run once; a non-fresh output is always rejected.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
import traceback

LINE = Path(__file__).resolve().parents[1]
REPO = LINE.parents[2]
UPSTREAM = REPO / 'research/lines/futures_trend_rollover_shape_same_volume/outputs'
INPUTS = {
    'metadata': UPSTREAM / 'stage265_deep_daily/rqalpha/futures_metadata.json',
    'inventory': UPSTREAM / 'stage266_clean_daily/csv_inventory.json',
    'economics': LINE / 'outputs/stage041_minimum_cash_economics_sources/economic_projection.json',
    'account': LINE / 'outputs/stage152_non_delivery_account_contract/account_contract.json',
    'catalog': LINE / 'outputs/stage152_non_delivery_account_contract/rule_source_catalog.json',
    'overlay': LINE / 'outputs/stage153_non_delivery_source_decision/source_overlay.json',
}
MOTHERS = LINE / 'outputs/stage129_contract_choice_dataset/actual_run1/mothers.csv.gz'
IDENTITY_COLUMNS = ('sequence_index', 'event_id', 'product_id', 'reference_epoch', 'u_date', 'u_index')
EXCHANGES = {'SHFE', 'INE', 'DCE', 'CZCE', 'CFFEX', 'GFEX'}
COMMON_MISSING = ('historical_rule_effective_interval', 'source_publication_and_known_at',
                  'exact_contract_adjustment_scope', 'applicable_calendar_binding',
                  'broker_specific_cutoff_policy')


def normalize_instrument(item):
    """Same full-year identity contract as accepted265; short CZCE aliases unused."""
    maturity = date.fromisoformat(item['maturity_date'])
    ex, product = item['exchange'], item['underlying_symbol']
    match = re.fullmatch(r'([A-Z]+)([0-9]{4})(F?)', item.get('order_book_id', ''))
    if ex not in EXCHANGES or not match:
        raise ValueError('continuous_or_unresolved_identity')
    prefix, digits, suffix = match.groups()
    if product != prefix + ('_F' if suffix else '') or not 1 <= int(digits[-2:]) <= 12:
        raise ValueError('metadata_product_month_disagrees')
    years = [y for y in range(maturity.year-1, maturity.year+2) if y % 100 == int(digits[:2])]
    if not years:
        raise ValueError('unresolved_contract_year')
    year = min(years, key=lambda y: abs(y-maturity.year))
    return f'{ex}.{product}.{year:04d}{digits[-2:]}'


def classify_rule(product_id, nominal_month, catalog, overlay):
    """Describe source-supported candidates; never certify temporal applicability."""
    exchange, product = product_id.split('.', 1)
    variant = 'F' if product.endswith('_F') else 'ordinary'
    asset = ('financial_index' if product in {'IF', 'IH', 'IC', 'IM'} else 'financial_treasury') if exchange == 'CFFEX' else 'commodity'
    group, formula, grade = 'unclassified', 'unknown', 'unknown'
    delivery, temporal = 'unknown', 'historical_interval_and_known_at_unbound'
    scope_status = 'candidate_product_scope_not_certified'
    start_hint, notice_hint = None, None
    source_refs = []
    extra_missing = []
    if exchange == 'DCE' and product in {'L_F', 'PP_F', 'V_F'}:
        group, formula, delivery = 'DCE_F_cash_branch', 'cash_settlement_separate_from_market_fill', 'cash'
        grade, temporal = 'draft_or_broker_candidate_formal_body_missing', 'first_contract_and_formal_effectivity_candidate_only'
        extra_missing += ['formal_F_contract_and_first_applicable_contract', 'official_cash_settlement_values_and_fees']
        source_refs.append('overlay.DCE_F; overlay.source_bindings.dce_F_catalog')
    elif exchange == 'DCE' and variant == 'ordinary':
        group, formula, delivery = 'DCE_ordinary_physical', 'flat_before_first_delivery_month_trading_session', 'physical_candidate'
        grade = 'official_index_excerpt_original_body_missing'
    elif exchange == 'SHFE':
        group, formula, delivery = 'SHFE_physical_historical_T3', 'flat_after_close_T_minus_3_trading_days', 'physical_candidate'
        grade = 'official_index_excerpt_partial_product_and_version_scope'
        extra_missing.append('product_specific_rule_applicability')
    elif exchange == 'CZCE':
        group, formula, delivery = 'CZCE_natural_before_delivery_month', 'flat_before_first_delivery_month_trading_session', 'physical_candidate'
        grade = 'official_full_text_partial_historical_versions'
        extra_missing.append('effective_contract_ranges_and_successor_versions')
    elif exchange == 'INE' and product == 'EC':
        group, formula, delivery = 'INE_EC_cash', 'cash_settlement_separate_from_market_fill', 'cash'
        grade = 'official_historical_contract_partial_versions'
        extra_missing.append('official_cash_settlement_values_and_fees')
    elif exchange == 'INE' and product in {'SC', 'LU', 'NR', 'BC'}:
        group = 'INE_BC_2020_T3' if product == 'BC' else 'INE_SC_LU_NR_legacy_T8'
        delivery = 'physical_candidate'
        offset = 8 if product != 'BC' else 3
        grade = 'historical_and_current_official_endpoints_temporal_unbound'
        if product != 'SC':
            candidate = overlay.get('INE', {}).get('historical_cutpoint_candidate', {})
            transition = candidate.get('claimed_transition', {}).get(product, {})
            cutoff = str(candidate.get('claimed_first_contract_month', '')).replace('-', '')
            if nominal_month and re.fullmatch(r'\d{6}', cutoff) and transition:
                after = nominal_month >= cutoff
                offset = transition['2311_and_after_offset' if after else 'before_2311_offset']
                temporal = 'broker_candidate_2311_plus_not_official_known' if after else 'broker_candidate_pre_2311_not_official_known'
                notice_hint = candidate.get('claimed_announcement_date')
                start_hint = candidate.get('claimed_effective_date')
                grade = 'broker_candidate_cutpoint_plus_official_current_endpoint'
            else:
                temporal = 'transition_phase_unknown_without_bound_candidate'
            extra_missing.append('official_transition_notice_and_first_contract_scope')
        formula = f'flat_after_close_T_minus_{offset}_trading_days'
        if product != 'SC' and temporal == 'transition_phase_unknown_without_bound_candidate':
            formula = f'conditional_candidate_T_minus_{offset}_or_5_without_epoch_phase'
        source_refs.append('overlay.INE; overlay.source_bindings.ine_evidence')
    elif exchange == 'CFFEX' and product in {'IF', 'IH', 'IC', 'IM'}:
        group, formula, delivery = 'CFFEX_index_cash', 'cash_settlement_separate_from_market_fill', 'cash'
        grade = 'official_historical_contract_partial_product_versions'
        extra_missing.append('official_cash_settlement_values_and_fees')
    elif exchange == 'CFFEX' and product in {'TF', 'T', 'TS', 'TL'}:
        group, formula, delivery = 'CFFEX_treasury_unapproved_custody', 'flat_before_trading_session_immediately_preceding_delivery_month', 'physical_treasury'
        grade = 'official_notice_index_TF_T_scope_other_products_unbound'
        scope_status = 'TF_T_2018_representative_only' if product in {'TF', 'T'} else 'TS_TL_product_applicability_unbound'
        extra_missing.append('treasury_product_and_historical_custody_rule_scope')
    elif exchange == 'GFEX':
        group, delivery = 'GFEX_physical_candidate', 'physical_candidate'
        sources = overlay.get('GFEX', {}).get('all_five_products_retained', [])
        specific = next((s for s in sources if s.get('product') == product), {})
        grade = specific.get('grade', 'unknown')
        start_hint = specific.get('stated_rule_effective_from') or specific.get('initial_rule_effective_from')
        if product in {'SI', 'LC', 'PT', 'PD'}:
            formula = 'flat_before_first_delivery_month_trading_session'
        else:
            extra_missing.append('product_specific_delivery_identity_and_zero_clause')
        temporal = 'initial_source_hint_only_successor_versions_and_known_at_unknown'
        source_refs += ['overlay.GFEX.general_rule', 'overlay.GFEX.product.'+product]
        extra_missing.append('product_initial_rule_and_later_amendment_scope')
    for source in catalog.get('rows', []):
        if source.get('rule_id') == group:
            source_refs += source.get('source_urls', [])
            if source.get('source_url'):
                source_refs.append(source['source_url'])
    return dict(exchange=exchange, product_id=product_id, variant=variant, asset_class=asset,
                rule_group=group, delivery_class_candidate=delivery, candidate_formula=formula,
                candidate_formula_expressible=formula != 'unknown', evidence_grade=grade,
                source_refs=source_refs, temporal_applicability=temporal,
                temporal_applicability_official_known=False, product_scope_status=scope_status,
                candidate_rule_start_hint=start_hint, candidate_notice_date_hint=notice_hint,
                strict_account_cutoff_ready=False,
                required_missing_fields=list(COMMON_MISSING)+extra_missing)


def lifecycle_position(item, as_of):
    listed, ended = item.get('listed_date'), item.get('de_listed_date') or item.get('maturity_date')
    if listed and as_of < listed:
        return 'not_yet_listed_in_snapshot'
    if ended and as_of > ended:
        return 'ended_in_snapshot'
    return 'listed_not_ended_in_snapshot' if listed and ended else 'unknown_metadata_dates'


def build_epoch_coverage(metadata, inventory, economics, catalog, overlay, as_of):
    real = {}
    for item in metadata:
        try:
            epoch = normalize_instrument(item)
        except (ValueError, KeyError, TypeError):
            continue  # Continuous/unresolved records are not true epoch identities.
        if epoch in real:
            raise ValueError('duplicate normalized metadata epoch '+epoch)
        real[epoch] = item
    clean = {row['contract_epoch_id'] for row in inventory}
    if len(clean) != len(inventory):
        raise ValueError('duplicate clean inventory epoch')
    rows = {}
    for epoch in sorted(set(real) | clean):
        product, month = epoch.rsplit('.', 1)
        if not re.fullmatch(r'\d{6}', month):
            raise ValueError('full epoch month required')
        item, econ = real.get(epoch), economics.get(epoch, {})
        row = classify_rule(product, month, catalog, overlay)
        row.update(epoch=epoch, nominal_contract_month=month, metadata_present=item is not None,
                   has_clean_observations=epoch in clean, observation_state='directory_identity',
                   listed_date=item.get('listed_date') if item else None,
                   maturity_date=item.get('maturity_date') if item else None,
                   de_listed_date=item.get('de_listed_date') if item else None,
                   start_delivery_date=item.get('start_delivery_date') if item else None,
                   end_delivery_date=item.get('end_delivery_date') if item else None,
                   order_book_id=item.get('order_book_id') if item else None,
                   metadata_product_class=item.get('product') if item else None,
                   known_lifecycle_snapshot=econ.get('known_lifecycle_exit_boundary'),
                   lifecycle_source=econ.get('lifecycle_source'),
                   lifecycle_position_as_of=lifecycle_position(item or {}, as_of),
                   as_of=as_of, metadata_publication_status='2026_vendor_snapshot_not_historical_notice')
        if item is None:
            row['required_missing_fields'].append('exact_epoch_metadata_dates')
        rows[epoch] = row
    return rows


def project_mothers(mothers, coverage, catalog, overlay):
    for mother in mothers:
        identity = {name: str(mother.get(name, '')) for name in IDENTITY_COLUMNS}
        epoch, product = identity['reference_epoch'], identity['product_id']
        source = coverage.get(epoch) if epoch else None
        if source is None:
            row = classify_rule(product, None, catalog, overlay)
            row.update(metadata_present=None, has_clean_observations=None,
                       observation_state='no_reference_observation' if not epoch else 'reference_not_in_directory',
                       lifecycle_position_as_of='unknown_metadata_dates')
            row['required_missing_fields'].append('reference_epoch_observation' if not epoch else 'reference_identity_in_directory')
        else:
            row = dict(source)
            row['required_missing_fields'] = list(source['required_missing_fields'])
            row['observation_state'] = 'reference_identity_present' if product == source['product_id'] else 'reference_product_mismatch'
        row.update(identity)
        row['lifecycle_position_at_u'] = lifecycle_position(row, identity['u_date'])
        row['candidate_notice_at_u'] = ('candidate_notice_claim_later_than_u' if row.get('candidate_notice_date_hint') and identity['u_date'] < row['candidate_notice_date_hint'] else 'not_certified_at_u')
        row['strict_account_cutoff_ready'] = False
        yield row


class Summary:
    def __init__(self):
        self.counts = Counter()
        self.products = set()
        self.groups = {key: Counter() for key in ('exchange', 'variant', 'asset_class', 'rule_group',
            'evidence_grade', 'temporal_applicability', 'lifecycle_position_as_of')}

    def add(self, row):
        self.counts['rows'] += 1
        self.products.add(row['product_id'])
        for key in self.groups:
            self.groups[key][str(row[key])] += 1
        self.counts['candidate_formula_expressible'] += bool(row['candidate_formula_expressible'])
        self.counts['strict_account_cutoff_ready'] += bool(row['strict_account_cutoff_ready'])
        self.counts['no_reference_observation'] += row.get('observation_state') == 'no_reference_observation'
        self.counts['reference_not_in_directory'] += row.get('observation_state') == 'reference_not_in_directory'
        self.counts['reference_product_mismatch'] += row.get('observation_state') == 'reference_product_mismatch'
        self.counts['exact_metadata_missing'] += row.get('metadata_present') is False
        self.counts['no_clean_observations'] += row.get('has_clean_observations') is False
        self.counts['metadata_state_unknown_no_reference'] += row.get('metadata_present') is None
        if row['candidate_formula_expressible']:
            self.counts['candidate_expressible_but_temporal_uncertified'] += not row['temporal_applicability_official_known']

    def result(self):
        return dict(self.counts, product_codes=len(self.products), group_counts={k: dict(sorted(v.items())) for k, v in self.groups.items()})


def summarize(rows):
    summary = Summary()
    for row in rows:
        summary.add(row)
    return summary.result()


def read_mother_identities(path):
    """Single compressed stream; only six identity columns enter computation."""
    with gzip.open(path, 'rt', newline='') as stream:
        reader = csv.reader(stream)
        header = next(reader)
        positions = [header.index(name) for name in IDENTITY_COLUMNS]
        for cells in reader:
            yield {name: cells[index] for name, index in zip(IDENTITY_COLUMNS, positions)}


def write_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def binding(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=digest.hexdigest())


def write_csv(path, rows, fields):
    with gzip.open(path, 'xt', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(row.get(key), ensure_ascii=False) if isinstance(row.get(key), (list, dict)) else row.get(key) for key in fields})


def run(output, include_mothers=False, as_of='2026-10-16'):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    write_json(output/'started.json', dict(schema='stage154_started_v1', started_at=datetime.now(timezone.utc).isoformat(),
        output=str(output.resolve()), include_mothers=include_mothers, financial_work=False, auto_retry=False))
    try:
        inputs, bindings = {}, {}
        for name, path in INPUTS.items():
            raw = path.read_bytes()
            inputs[name] = json.loads(raw)
            bindings[name] = dict(path=str(path.resolve()), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        if inputs['account']['research_account'].get('accept_physical_delivery') is not False:
            raise ValueError('fixed non-physical research account required')
        if inputs['overlay']['schema'] != 'stage153_non_delivery_source_overlay_v1':
            raise ValueError('Stage153 overlay identity required')
        rows = build_epoch_coverage(inputs['metadata'], inputs['inventory'], inputs['economics']['instruments'], inputs['catalog'], inputs['overlay'], as_of)
        summary = summarize(rows.values())
        assert len(rows) == 10880 and summary['product_codes'] == 98 and summary['exact_metadata_missing'] == 18
        assert sum(row['metadata_present'] for row in rows.values()) == 10862
        assert sum(row['has_clean_observations'] for row in rows.values()) == 9520
        assert set(summary['group_counts']['exchange']) == EXCHANGES
        assert sum(row['metadata_present'] and row['variant'] == 'F' for row in rows.values()) == 42
        fields = list(next(iter(rows.values())))
        write_csv(output/'epoch_coverage.csv.gz', rows.values(), fields)
        reports = dict(directory=summary, as_of=as_of, strict_ready_is_not_candidate_expressibility=True,
            has_clean_observations_semantics='ever present in clean inventory; not an execution-day price assertion',
            per_epoch_account_cutoff_dates_generated=0, fit=0, cash=0, SQL=0, price_reads=0)
        if include_mothers:
            all_mothers, primary = Summary(), Summary()
            def projected():
                for row in project_mothers(read_mother_identities(MOTHERS), rows, inputs['catalog'], inputs['overlay']):
                    all_mothers.add(row)
                    if row['u_date'] >= '2020-01-01':
                        primary.add(row)
                    yield row
            mother_fields = list(IDENTITY_COLUMNS) + [key for key in fields if key not in IDENTITY_COLUMNS] + ['lifecycle_position_at_u', 'candidate_notice_at_u']
            write_csv(output/'mother_coverage.csv.gz', projected(), mother_fields)
            assert all_mothers.counts['rows'] == 399252
            reports.update(all_mothers=all_mothers.result(), mothers_2020_plus=primary.result(), mother_identity_columns=list(IDENTITY_COLUMNS))
            stat = MOTHERS.stat()
            bindings['mothers'] = dict(path=str(MOTHERS.resolve()), bytes=stat.st_size, mtime_ns=stat.st_mtime_ns,
                sha256_verification='inherited_129_not_rehashed; one identity projection stream')
        write_json(output/'coverage_summary.json', reports)
        terminal = dict(schema='stage154_terminal_v1', status='completed', exit_code=0, elapsed_seconds=time.monotonic()-started,
            directory_rows=len(rows), mother_rows=reports.get('all_mothers', {}).get('rows', 0), fit=0, cash=0, SQL=0, price_reads=0)
        write_json(output/'terminal.json', terminal)
        artifacts = [binding(output/name) for name in ('started.json', 'epoch_coverage.csv.gz', 'coverage_summary.json', 'terminal.json')]
        if include_mothers:
            artifacts.append(binding(output/'mother_coverage.csv.gz'))
        write_json(output/'manifest.json', dict(schema='stage154_rule_coverage_manifest_v1', inputs=bindings, artifacts=artifacts,
            implementation=binding(__file__), account_deadline_engine=False, strict_account_cutoff_ready=False,
            cumulative_fit=397, cumulative_cash=206, actual_authority='root launched once; no automatic retry'))
        return terminal
    except BaseException:
        if not (output/'terminal.json').exists():
            write_json(output/'terminal.json', dict(schema='stage154_terminal_v1', status='failed', exit_code=1,
                elapsed_seconds=time.monotonic()-started, traceback=traceback.format_exc(), auto_retry=False, fit=0, cash=0, SQL=0))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Fresh output directory; root launches actual once')
    parser.add_argument('--include-mothers', action='store_true', help='One full 399252-row identity projection, no labels/prices')
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.include_mothers), ensure_ascii=False))


if __name__ == '__main__':
    main()
