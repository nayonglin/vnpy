"""Private locked CAS store for weekly19 funding; standard library, no network.

Every commit journals the complete next state before replacing state.json. A
restart replays only the immediate next revision. All path components are opened
with O_NOFOLLOW, files are private 0600 and the final parent must be private.
Checksum verifies accidental corruption, not authenticity against the same user.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

from qmt_roll_weekly19_funding import FundingError, _canonical, _time, _hash, _parse, upgrade_funding_state, validate_state


class FundingStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        if not self.path.is_absolute() or self.path.name in ('', '.', '..') or '..' in self.path.parts:
            raise FundingError('store_absolute_safe_path_required')
        self.name = self.path.name
        self.lock_name = self.name + '.lock'
        self.journal_name = self.name + '.journal'

    @contextmanager
    def _locked(self):
        directory = None
        lock_fd = None
        try:
            directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
            for part in self.path.parent.parts[1:]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            info = os.fstat(directory)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise FundingError('store_private_parent_required')
            lock_fd = self._open_lock(directory)
            self._private_file(lock_fd)
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield directory
        except OSError as exc:
            raise FundingError('store_path_or_io_invalid') from exc
        finally:
            if lock_fd is not None:
                os.close(lock_fd)
            if directory is not None:
                os.close(directory)

    def _open_lock(self,directory):
        # macOS can return ENOENT when concurrent openat(O_CREAT) races the
        # first creation. Exclusive create has an atomic EEXIST result; only
        # then open the existing inode WITHOUT O_CREAT. A removed inode retries
        # from exclusive create, never via an absolute-path fallback.
        for _ in range(8):
            try:
                return os.open(self.lock_name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,
                               0o600,dir_fd=directory)
            except FileExistsError:
                try:
                    return os.open(self.lock_name,os.O_RDWR|os.O_NOFOLLOW,dir_fd=directory)
                except FileNotFoundError:
                    continue
            except FileNotFoundError:
                continue
        raise FundingError('store_lock_create_race_exhausted')

    @staticmethod
    def _private_file(fd):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise FundingError('store_private_regular_file_required')

    def _read(self, directory, name):
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
        except FileNotFoundError:
            return None
        with os.fdopen(fd, 'rb') as stream:
            self._private_file(stream.fileno())
            payload = stream.read(16_000_001)
        if len(payload) > 16_000_000:
            raise FundingError('store_payload_too_large')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise FundingError('store_duplicate_json_key')
                result[key] = value
            return result
        try:
            record = json.loads(payload, object_pairs_hook=unique)
            state = record['state']
            if record['schema'] != 'weekly19.funding-store.v1':
                raise FundingError('store_schema_invalid')
            if record['state_sha256'] != hashlib.sha256(_canonical(state)).hexdigest():
                raise FundingError('store_checksum_mismatch')
            validate_state(state)
            return state
        except (ValueError, KeyError, TypeError, UnicodeError) as exc:
            if isinstance(exc, FundingError):
                raise
            raise FundingError('store_payload_invalid') from exc

    @staticmethod
    def _record(state):
        validate_state(state)
        return _canonical(dict(schema='weekly19.funding-store.v1', state=state,
                               state_sha256=hashlib.sha256(_canonical(state)).hexdigest()))

    def _atomic(self, directory, name, state):
        # Refuse a destination symlink/hardlink even though rename would replace it.
        try:
            current = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
        except FileNotFoundError:
            current = None
        if current is not None:
            try:
                self._private_file(current)
            finally:
                os.close(current)
        temp_name = '.' + name + '.' + uuid.uuid4().hex
        fd = None
        try:
            fd = os.open(temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            with os.fdopen(fd, 'wb') as stream:
                fd = None
                stream.write(self._record(state))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, name, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            if fd is not None:
                os.close(fd)
            try:
                os.unlink(temp_name, dir_fd=directory)
            except FileNotFoundError:
                pass

    @staticmethod
    def _same_identity(left, right):
        return all(left[key] == right[key] for key in
                   ('account_key', 'material_release_id', 'cold_start_date', 'initial_trading_fen', 'reserve_initial_fen'))

    @staticmethod
    def _forward_ledger(current, following, *, strict_manual_parent=False):
        if current==following: return
        if current['schema']=='weekly19.external-funding.v1':
            if following!=upgrade_funding_state(current):
                raise FundingError('store_explicit_v2_migration_required')
        elif following['schema']!='weekly19.external-funding.v2' or following.get('migration')!=current.get('migration'):
            raise FundingError('store_schema_downgrade_or_migration_rewrite')
        new_manual=[row for key,row in following.get('manual_cash_reviews',{}).items()if key not in current.get('manual_cash_reviews',{})]
        if strict_manual_parent and len(new_manual)>1:
            raise FundingError('store_one_manual_review_per_commit_required')
        if strict_manual_parent and new_manual:
            raw=_parse(new_manual[0],'weekly19.operator-cash-review.v1','operator_manual')
            if (raw['before_funding_revision']!=current['revision'] or raw['before_funding_sha256']!=_hash(current)
                    or raw['before_checkpoint']!=current['cashflow_checkpoint']):
                raise FundingError('store_manual_review_parent_mismatch')
        if any(following.get('manual_cash_reviews',{}).get(key)!=row for key,row in current.get('manual_cash_reviews',{}).items()):
            raise FundingError('store_manual_review_ledger_rollback')
        if current['schema']=='weekly19.external-funding.v2':
            if any(following['retirements'].get(rid)!=proof for rid,proof in current['retirements'].items()):
                raise FundingError('store_retirement_ledger_rollback')
            for key,attempts in current['request_attempts'].items():
                if following['request_attempts'].get(key,[])[:len(attempts)]!=attempts:
                    raise FundingError('store_request_attempt_rollback')
        if (following['reserve_remaining_fen'] > current['reserve_remaining_fen']
                or following['confirmed_topup_fen'] < current['confirmed_topup_fen']
                or any(following['receipts'].get(key) != row for key, row in current['receipts'].items())
                or any(following['admitted_entries'].get(key) != row for key, row in current['admitted_entries'].items())
                or following['day_rolls'][:len(current['day_rolls'])] != current['day_rolls']):
            raise FundingError('store_ledger_rollback_forbidden')
        old_cp = current['cashflow_checkpoint']
        new_cp = following['cashflow_checkpoint']
        if old_cp is not None:
            if (new_cp is None or new_cp['trading_day'] < old_cp['trading_day']
                    or _time(new_cp['observed_at']) < _time(old_cp['observed_at'])):
                raise FundingError('store_checkpoint_rollback_forbidden')
            if new_cp['trading_day'] == old_cp['trading_day']:
                new_manual=[row for key,row in following.get('manual_cash_reviews',{}).items()if key not in current.get('manual_cash_reviews',{})]
                reviewed_withdrawal=any(row['after_checkpoint']==new_cp for row in new_manual)
                if ((new_cp['withdraw_fen'] != old_cp['withdraw_fen']and not reviewed_withdrawal)
                        or new_cp['deposit_fen'] - old_cp['deposit_fen']
                        != following['confirmed_topup_fen'] - current['confirmed_topup_fen']):
                    raise FundingError('store_checkpoint_cashflow_invalid')
            elif len(following['day_rolls']) <= len(current['day_rolls']):
                raise FundingError('store_day_roll_evidence_missing')
        for rid, request in current['requests'].items():
            other = following['requests'].get(rid)
            mutable = {'confirmed_fen', 'status', 'active_baseline', 'confirmed_before_active_day_fen'}
            if (other is None or any(other.get(key) != value for key, value in request.items() if key not in mutable)
                    or other['confirmed_fen'] < request['confirmed_fen']):
                raise FundingError('store_ledger_rollback_forbidden')

    def _recover(self, directory):
        current = self._read(directory, self.name)
        journal = self._read(directory, self.journal_name)
        if journal is None:
            return current
        if current is None:
            if journal['revision'] != 0:
                raise FundingError('journal_revision_without_initial_state')
        elif journal == current:
            pass
        elif journal['revision'] != current['revision'] + 1 or not self._same_identity(current, journal):
            raise FundingError('journal_revision_or_identity_invalid')
        if current is not None:
            self._forward_ledger(current, journal, strict_manual_parent=True)
        self._atomic(directory, self.name, journal)
        os.unlink(self.journal_name, dir_fd=directory)
        os.fsync(directory)
        return journal

    def create(self, state):
        validate_state(state)
        if state['revision'] != 0:
            raise FundingError('initial_revision_required')
        with self._locked() as directory:
            if self._recover(directory) is not None:
                raise FundingError('store_already_exists')
            self._atomic(directory, self.journal_name, state)
            self._atomic(directory, self.name, state)
            os.unlink(self.journal_name, dir_fd=directory)
            os.fsync(directory)

    def load(self):
        with self._locked() as directory:
            current = self._recover(directory)
            if current is None:
                raise FundingError('store_missing')
            return current

    def commit(self, expected_revision: int, state: dict):
        validate_state(state)
        if type(expected_revision) is not int:
            raise FundingError('revision_conflict')
        with self._locked() as directory:
            current = self._recover(directory)
            if current is None or current['revision'] != expected_revision:
                raise FundingError('revision_conflict')
            if state == current:
                return
            if state['revision'] != current['revision'] + 1:
                raise FundingError('next_revision_required')
            if not self._same_identity(current, state):
                raise FundingError('store_identity_change_forbidden')
            self._forward_ledger(current, state, strict_manual_parent=True)
            self._atomic(directory, self.journal_name, state)
            self._atomic(directory, self.name, state)
            os.unlink(self.journal_name, dir_fd=directory)
            os.fsync(directory)
