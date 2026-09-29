"""Variant-owned snapshots; baseline validation is reused without mutating it."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re

import pandas as pd

from examples.stock_backtesting.qmt357.data import _normalise, _summary
from .config import ROOT


DATA_DIR = ROOT / 'data/snapshots'


def _data_root():
    if any(p.is_symlink() for p in (DATA_DIR, *DATA_DIR.parents)):
        raise ValueError('Variant snapshot path must not contain a symlink')
    return DATA_DIR.resolve()


def _snapshot_path(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', name):
        raise ValueError('Snapshot name must be a single safe directory name')
    path = _data_root() / name
    if path.is_symlink() or path.resolve().parent != _data_root():
        raise ValueError('Snapshot escapes the independent variant data directory')
    return path


def prepare_snapshot(source, name, universe_mode='historical'):
    target = _snapshot_path(name)
    if target.exists():
        raise FileExistsError(f'Snapshot already exists: {target}')
    if universe_mode not in {'historical', 'static_snapshot', 'custom'}:
        raise ValueError('Invalid universe_mode')
    source = Path(source).resolve(strict=True)
    if source.suffix.lower() not in {'.csv', '.parquet'} or not source.is_file():
        raise ValueError('Source must be CSV or parquet')
    content = source.read_bytes()
    frame = (pd.read_parquet(io.BytesIO(content)) if source.suffix.lower() == '.parquet'
             else pd.read_csv(io.BytesIO(content), dtype={'vt_symbol': str}))
    attrs = json.loads(json.dumps(frame.attrs, ensure_ascii=False, allow_nan=False))
    membership = attrs.get('membership_source', '')
    if not isinstance(membership, str):
        raise ValueError('membership_source must be text')
    declared = attrs.get('historical_membership_verified') is True and bool(membership.strip())
    panel = _normalise(frame)
    panel_bytes = panel.to_parquet(index=False)
    manifest = dict(schema_version=1, snapshot_name=name,
        created_at_utc=datetime.now(timezone.utc).isoformat(), source_path=str(source),
        source_sha256=hashlib.sha256(content).hexdigest(), panel_file='panel.parquet',
        panel_sha256=hashlib.sha256(panel_bytes).hexdigest(), universe_mode=universe_mode,
        historical_membership_verified=declared and universe_mode == 'historical',
        membership_verification_basis='source_declaration' if declared else 'unverified',
        membership_source=membership, source_metadata=attrs,
        provider=attrs.get('provider', 'user_supplied'),
        data_limitations=attrs.get('data_limitations', []),
        execution_semantics=attrs.get('execution_semantics', {}),
        price_basis='unadjusted_execution_prices_with_separate_adj_factor', volume_unit='shares',
        cash_dividend_unit='cash_per_pre_event_share',
        split_ratio_semantics='post_event_shares_per_pre_event_share',
        corporate_action_policy='Held unexplained factor changes must fail; factors never imply shares or cash.',
        **_summary(panel))
    _data_root().mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    (target / 'panel.parquet').write_bytes(panel_bytes)
    (target / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2,
        allow_nan=False) + '\n', encoding='utf-8')
    return target


def load_snapshot(path):
    path = Path(path)
    if path.is_symlink() or path.resolve().parent != _data_root():
        raise ValueError('Snapshot must be directly inside independent variant data directory')
    path = _snapshot_path(path.name)
    if any((path / f).is_symlink() for f in ['manifest.json', 'panel.parquet']):
        raise ValueError('Snapshot files must not be symlinks')
    metadata = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    if (metadata.get('schema_version') != 1 or metadata.get('panel_file') != 'panel.parquet'
            or metadata.get('snapshot_name') != path.name):
        raise ValueError('Invalid snapshot manifest identity')
    content = (path / 'panel.parquet').read_bytes()
    if hashlib.sha256(content).hexdigest() != metadata.get('panel_sha256'):
        raise ValueError('Snapshot panel SHA256 mismatch')
    panel = _normalise(pd.read_parquet(io.BytesIO(content)))
    if any(metadata.get(k) != v for k, v in _summary(panel).items()):
        raise ValueError('Snapshot manifest summary mismatch')
    return panel, metadata
