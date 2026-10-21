"""Clock classification and a small local append-only research journal.

No reception service, freeze creation, fitting, market reads or trading. Clock
classification is conditional on supplied source/session evidence; recorded_at
is local UTC reception time, not an exchange publication timestamp.
"""
from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path


def _time(value):
    if value is None:
        return None
    result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('explicit timezone required')
    return result.astimezone(timezone.utc)


def evaluate_clock(*, frozen_at, source_completed_at, received_at,
                   decision_sealed_at, D_open_at):
    """Keep forward observation separate from timely, executable decisions."""
    names = ('frozen_at', 'source_completed_at', 'received_at', 'decision_sealed_at', 'D_open_at')
    values = [_time(v) for v in (frozen_at, source_completed_at, received_at, decision_sealed_at, D_open_at)]
    freeze, complete, received, sealed, opened = values
    if received is not None and sealed is not None and sealed < received:
        raise ValueError('decision sealed before receipt')
    forward = freeze is not None and complete is not None and complete > freeze
    if freeze is None:
        status = 'not_frozen'
    elif complete is None:
        status = 'completion_clock_unknown'
    elif complete <= freeze:
        status = 'historical_before_freeze'
    elif received is None:
        status = 'receipt_clock_unknown'
    elif received < complete:
        status = 'received_before_completion'
    elif opened is None:
        status = 'D_clock_unknown'
    elif received >= opened:
        status = 'late_input'
    elif sealed is None:
        status = 'decision_not_sealed'
    elif sealed >= opened:
        status = 'late_decision'
    else:
        status = 'timely_forward_decision'
    return dict(status=status, forward_observation=forward,
        timely_decision=status == 'timely_forward_decision',
        no_forward_decision=status != 'timely_forward_decision',
        timestamps_utc={k: None if v is None else v.isoformat() for k, v in zip(names, values)},
        clock_provenance_certified=False)


def _canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _exclusive_file(path, raw):
    """Create immutable content, or verify an identical existing object."""
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        if Path(path).read_bytes() != raw:
            raise ValueError('existing object or policy identity has different content')
        return
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


class ForwardJournal:
    """One local stream per immutable policy identity; no silent corrections.

    append checks the small index chain and the current object, without hashing
    all old payloads on each new observation. entries is the explicit complete
    object-integrity read. A user with filesystem access can replace a whole
    journal; hashes are reproducibility evidence, not an external attestation.
    """

    def __init__(self, path, policy_identity):
        self.path = Path(path).resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        self.objects = self.path / 'objects'
        self.objects.mkdir(exist_ok=True)
        self.index = self.path / 'journal.jsonl'
        self.policy_hash = _digest(_canonical(policy_identity))
        metadata = _canonical(dict(schema='stage321_local_journal_v1',
            policy_identity=policy_identity, policy_sha256=self.policy_hash))
        policy_file = self.path / 'policy_identity.json'
        if not policy_file.exists() and self.index.exists() and self.index.stat().st_size:
            raise ValueError('policy identity missing for nonempty journal')
        _exclusive_file(policy_file, metadata)

    def _read_index(self, stream):
        stream.seek(0)
        rows, previous, keys = [], '0' * 64, set()
        for line in stream:
            try:
                if not line.endswith('\n'):
                    raise ValueError('torn index line')
                entry = json.loads(line)
                digest = entry['entry_hash']
                content = {k: v for k, v in entry.items() if k != 'entry_hash'}
                if (entry['sequence'] != len(rows) or entry['previous_entry_hash'] != previous
                        or entry['policy_sha256'] != self.policy_hash
                        or entry['key'] in keys or _digest(_canonical(content)) != digest
                        or not isinstance(entry['payload_sha256'], str)
                        or len(entry['payload_sha256']) != 64):
                    raise ValueError('index chain mismatch')
                recorded = _time(entry['recorded_at'])
                if recorded is None or (rows and recorded < _time(rows[-1]['recorded_at'])):
                    raise ValueError('index reception clock regressed')
            except (ValueError, TypeError, KeyError) as error:
                raise ValueError('invalid journal index: ' + str(error)) from error
            rows.append(entry)
            keys.add(entry['key'])
            previous = digest
        return rows

    def append(self, kind, payload, *, key):
        if not isinstance(kind, str) or not kind.strip() or not isinstance(key, str) or not key.strip():
            raise ValueError('nonempty record kind and idempotency key required')
        raw = _canonical(payload)
        payload_hash = _digest(raw)
        with self.index.open('a+', encoding='utf-8') as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            rows = self._read_index(stream)
            for old in rows:
                if old['key'] == key:
                    if old['kind'] != kind or old['payload_sha256'] != payload_hash:
                        raise ValueError('same key has different content; append a revision with a new key')
                    path = self.objects / (payload_hash + '.json')
                    if not path.exists() or path.read_bytes() != raw:
                        raise ValueError('existing journal object missing or changed; no silent repair')
                    return old
            now = datetime.now(timezone.utc)
            if rows and now < _time(rows[-1]['recorded_at']):
                raise ValueError('local reception clock regressed')
            entry = dict(sequence=len(rows), previous_entry_hash=rows[-1]['entry_hash'] if rows else '0' * 64,
                policy_sha256=self.policy_hash, kind=kind, key=key,
                payload_sha256=payload_hash, recorded_at=now.isoformat())
            entry['entry_hash'] = _digest(_canonical(entry))
            _exclusive_file(self.objects / (payload_hash + '.json'), raw)
            stream.seek(0, os.SEEK_END)
            stream.write(_canonical(entry).decode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
            return entry

    def entries(self):
        if not self.index.exists():
            return []
        with self.index.open('r', encoding='utf-8') as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
            rows = self._read_index(stream)
            result = []
            for entry in rows:
                path = self.objects / (entry['payload_sha256'] + '.json')
                try:
                    raw = path.read_bytes()
                    if _digest(raw) != entry['payload_sha256']:
                        raise ValueError('object hash mismatch')
                    payload = json.loads(raw)
                    if _canonical(payload) != raw:
                        raise ValueError('object canonical form mismatch')
                except (OSError, ValueError) as error:
                    raise ValueError('invalid journal object: ' + str(error)) from error
                result.append(dict(entry, payload=payload))
            return result
