from __future__ import annotations

from collections import Counter
from datetime import date
from functools import lru_cache
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'stages/20260906_1401_stage046_dynamic_exit_source_contract.md'
METADATA = ('calendar', 'collection_plan', 'nontradable_guard_days', 'quality_blockers')
CONTRACT_PATHS = ('path', 'expected_minutes_path', 'daily_reference_path', 'sessions_path', 'audit_path')


@lru_cache(None)
def load(name):
    spec = importlib.util.spec_from_file_location('dynamic046_' + name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def collect_inputs():
    source = load('stage037_calendar_window').SOURCE
    raw = (source.CACHE / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != source.SOURCE_MANIFEST_SHA:
        raise RuntimeError('dynamic_source_manifest_changed')
    manifest = json.loads(raw)
    files = {'dynamic_source_manifest': source.CACHE / 'manifest.json',
        'dynamic_source_request': source.CACHE / 'request.json', 'dynamic_exit_contract': CONTRACT,
        'dynamic_exit_tool': Path(__file__).resolve(), 'dynamic_exit_test': ROOT / 'tests/test_stage046_dynamic_exit_source.py'}
    for key in METADATA:
        files['dynamic_source_' + key] = source.safe_path(source.CACHE, manifest[key + '_path'])
    for symbol, entry in source.unique_entries(manifest).items():
        for key in CONTRACT_PATHS:
            files[f'dynamic_contract/{symbol}/{key}'] = source.safe_path(source.CACHE, entry[key])
    for name in ('stage035_next_window', 'stage036_full_minute_source', 'stage037_calendar_window'):
        files['dynamic_dependency/' + name] = ROOT / 'tools' / (name + '.py')
    for name in ('stage081_market_data.py', 'stage082_market_data.py', 'stage085_full_history.py'):
        files['dynamic_producer/' + name] = source.CACHE_LINE / 'tools' / name
    return dict(sorted(files.items()))


class DynamicExitSource:
    def __init__(self, files, database, calendar, *, cache=None, expected_source_sha256=None):
        self.clock = load('stage037_calendar_window')
        self.source = self.clock.SOURCE
        directory = Path(cache) if cache is not None else self.source.CACHE
        if directory.is_symlink() or not directory.is_dir():
            raise RuntimeError('dynamic_source_directory_changed')
        self.cache = directory.resolve()
        self.files = {}
        for identity in files.values():
            path = str(Path(identity['path']).resolve())
            if path != identity['path'] or (path in self.files and self.files[path] != identity):
                raise RuntimeError('dynamic_source_binding_identity')
            self.files[path] = dict(identity)
        self.used = {}; self.contracts = {}; self.windows = []; self.request_count = 0
        self.source_sha = expected_source_sha256 or self.source.SOURCE_MANIFEST_SHA
        self.manifest = json.loads(self._read(self._path('manifest.json'), self.source_sha))
        self.entries = self.source.unique_entries(self.manifest)
        metadata = {}
        for key in METADATA:
            raw = self._read(self._path(self.manifest[key + '_path']), self.manifest[key + '_sha256'])
            metadata[key] = json.loads(raw)
        if metadata['nontradable_guard_days']['days'] != self.manifest['nontradable_guard_days']:
            raise RuntimeError('dynamic_source_guard_inventory')
        self.guards = {(row['vt_symbol'], row['bar_date']) for row in self.manifest['nontradable_guard_days']}
        source_days = [row['date'] for row in metadata['calendar']['rows'] if row['trading']]
        days = list(calendar)
        for values in (source_days, days):
            if (not values or values != sorted(set(values))
                    or any(not isinstance(day, str) or date.fromisoformat(day).isoformat() != day for day in values)):
                raise RuntimeError('dynamic_source_calendar_invalid')
        if days != [day for day in source_days if days[0] <= day <= days[-1]]:
            raise RuntimeError('dynamic_source_calendar_mismatch')
        self.next_day = dict(zip(days, days[1:]))
        for entry in self.entries.values():
            for key in CONTRACT_PATHS:
                self._bound(self._path(entry[key]))
        self.database = Path(database)
        self.database_identity = dict(files['source_database'])
        original = Path(self.database_identity['path'])
        if (self.database.is_symlink() or self.database.resolve() == original.resolve()
                or (original.exists() and self.database.samefile(original))):
            raise RuntimeError('dynamic_source_requires_private_database_copy')
        self._check_database()

    def _path(self, relative):
        raw = self.cache / relative
        resolved = self.source.safe_path(self.cache, relative)
        path = raw
        while path != self.cache:
            if path.is_symlink():
                raise RuntimeError('dynamic_source_symlink_changed')
            path = path.parent
            if path == path.parent and path != self.cache:
                raise RuntimeError('dynamic_source_path_outside_cache')
        return resolved

    def _bound(self, path):
        identity = self.files.get(str(path))
        if identity is None:
            raise RuntimeError('dynamic_source_not_bound:' + str(path))
        return identity

    def _read(self, path, expected_sha=None):
        identity = self._bound(path)
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('dynamic_source_file_changed:' + str(path))
        raw = path.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
        if len(raw) != identity['size'] or digest != identity['sha256'] or (expected_sha and digest != expected_sha):
            raise RuntimeError('dynamic_source_file_changed:' + str(path))
        self.used[str(path)] = dict(identity)
        return raw

    def _check_database(self):
        if not self.database.is_file() or self.database.is_symlink():
            raise RuntimeError('dynamic_source_database_changed')
        raw = self.database.read_bytes()
        if len(raw) != self.database_identity['size'] or hashlib.sha256(raw).hexdigest() != self.database_identity['sha256']:
            raise RuntimeError('dynamic_source_database_changed')

    def _frame(self, entry, path_key, sha_key):
        import pandas as pd

        path = self._path(entry[path_key])
        raw = self._read(path, entry[sha_key])
        return pd.read_csv(io.BytesIO(raw), compression='gzip' if path.suffix == '.gz' else None)

    def _load_contract(self, symbol):
        if symbol not in self.entries:
            raise RuntimeError('dynamic_source_contract_missing:' + symbol)
        entry = self.entries[symbol]
        if entry['status'] != 'complete':
            raise RuntimeError('dynamic_source_contract_not_complete:' + symbol)
        self._check_database()
        raw = self._frame(entry, 'path', 'sha256')
        expected = self._frame(entry, 'expected_minutes_path', 'expected_minutes_sha256')
        frame = self.source.normalize(raw, expected, symbol)
        expected['bar_datetime'] = self.source.WINDOW.parse_clock(expected.bar_datetime)
        if len(frame) != entry['rows']:
            raise RuntimeError('dynamic_source_row_count_mismatch:' + symbol)
        reference = self._frame(entry, 'daily_reference_path', 'daily_reference_sha256')
        if reference.bar_date.duplicated().any():
            raise RuntimeError('dynamic_source_duplicate_daily_reference')
        reference = reference.set_index('bar_date')[self.source.VALUES].to_dict('index')
        self._read(self._path(entry['sessions_path']), entry['sessions_sha256'])
        self._read(self._path(entry['audit_path']))
        with self.source.readonly_database(self.database) as connection:
            baseline = self.source.daily_reference(connection, symbol)
        parity = {}
        for day, portion in frame.groupby('bar_date', sort=True):
            aggregate, status = self.source.aggregate_day(portion)
            provider, original = reference.get(day), baseline.get(day)
            parity[day] = (status != 'untraded_nonflat' and self.source.same_values(aggregate, provider)
                and self.source.same_values(aggregate, original) and self.source.same_values(provider, original))
        self.contracts[symbol] = (frame, expected, parity)

    def __call__(self, intent, fill_date):
        self.request_count += 1
        day, symbol, quantity = intent['decision_date'], intent['vt_symbol'], intent['volume']
        if (not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or not math.isfinite(quantity)
                or quantity <= 0 or quantity != int(quantity)):
            raise RuntimeError('dynamic_exit_quantity_invalid')
        if (not isinstance(day, str) or date.fromisoformat(day).isoformat() != day
                or self.next_day.get(day) != fill_date):
            raise RuntimeError('dynamic_exit_calendar_invalid')
        if symbol not in self.contracts:
            self._load_contract(symbol)
        frame, expected, parity = self.contracts[symbol]
        result = self.clock.qualify_from_clock(frame, expected, day, fill_date, quantity, parity,
            {guard_day for contract, guard_day in self.guards if contract == symbol})
        self.windows.append({'decision_date': day, 'fill_date': fill_date, 'vt_symbol': symbol,
            'requested_volume': quantity, **result})
        if result['status'] != 'source_proxy_qualified_not_execution':
            raise RuntimeError(f"dynamic_exit_not_qualified:{symbol}:{day}:{result['status']}")
        return {'price': result['first_open'], 'first_time': result['first_time'], 'fill_date': fill_date,
            'source': 'stage046_dynamic_full_minute', 'qualification': dict(self.windows[-1])}

    def verify_used_inputs(self):
        for path, identity in list(self.used.items()):
            original = Path(path)
            if original.is_relative_to(self.cache):
                original = self._path(original.relative_to(self.cache))
            self._read(original, identity['sha256'])
        self._check_database()

    def receipt(self):
        statuses = Counter(row['status'] for row in self.windows)
        return {'source_manifest_sha256': self.source_sha, 'source_global_coverage_complete': self.manifest['coverage_complete'],
            'request_count': self.request_count, 'qualified_count': statuses['source_proxy_qualified_not_execution'],
            'loaded_contracts': sorted(self.contracts), 'window_status_counts': dict(statuses),
            'used_source_file_count': len(self.used), 'database_sha256': self.database_identity['sha256'],
            'A_observation_table_used': False}
