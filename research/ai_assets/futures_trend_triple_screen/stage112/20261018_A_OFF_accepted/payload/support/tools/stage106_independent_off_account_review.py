"""Narrow raw-usage date reader for frozen095; never replay an account.

Numerical imports remain behind the original actual-terminal boundary. Only a
copied usage.signal_date becomes a strict ISO day, after original raw/export
and actual-identity checks. No clock, value, payload or frozen source is edited.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import re

LINE=Path(__file__).resolve().parents[1]
BASE=LINE/'tools/stage095_independent_off_account_review.py'
BASE_SHA='be688b02314b7c9d5a23d21f3cf0575e9d66a6e1f7a8a5b8c80ebcd627426b6f'
OUT=LINE/'outputs/stage106_off_financial_audit'
BINDINGS={
    BASE:BASE_SHA,
    LINE/'outputs/stage095_off_financial_audit/A_OFF/7cf2c2bffdc34d8cbd926693aa75dd10/audit_failure.json':
        '2771b9f5edfd77ed1e25ffc4fd9fdaacbfaea48ce7bfc3dd1a44f361be0cc09c',
    LINE/'outputs/stage105_A_OFF_independent_financial_review/review_receipt.json':
        '8ecee989eb9a4acbe751e7abd7fefed14ff327c42ad141ee842445e900274f6a',
    LINE/'outputs/stage104_A_OFF_actual_completion/root_actual_completion.json':
        'fd6272aeeb94b8546008224d54479aeab5e5e11d2cf5e73439c110b097f17944',
    LINE/'stages/20261018_0742_stage106_A_mother_date_reader_contract.md':
        'd7e00776a317c6b350cbec24b007be4429b06150d42561eef0690de2d78064d9',
}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def bound_bytes(path,pin):
    path=Path(path).absolute()
    assert path.is_file() and not any(p.is_symlink() for p in (path,*path.parents))
    raw=path.read_bytes();assert sha(raw)==pin, ('reader lineage changed',str(path))
    return raw


def strict_iso_day(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value):
        raise ValueError('reader_requires_strict_ISO_day')
    try:date.fromisoformat(value)
    except ValueError as error:raise ValueError('reader_invalid_calendar_day') from error
    return value


def signal_day(value,pd):
    if isinstance(value,str):return strict_iso_day(value)
    if isinstance(value,pd.Timestamp):
        if value.tzinfo is not None or value!=value.normalize():
            raise ValueError('reader_signal_Timestamp_requires_naive_midnight')
        return strict_iso_day(value.date().isoformat())
    raise ValueError('reader_signal_day_type_rejected')


def adapt_exports(result,pd):
    """Keep all four other original objects and every non-day usage value."""
    trades,usage,clock,hashes,identity=result
    if 'signal_date' not in usage:raise ValueError('reader_usage_signal_date_missing')
    copied=usage.copy(deep=True)
    copied['signal_date']=copied.signal_date.map(lambda value:signal_day(value,pd))
    return trades,copied,clock,hashes,identity


def check_csv_days(export):
    # These exact CSVs have already passed the original raw/export SHA check.
    # Validate their day labels; never rewrite or weaken either plan match.
    for name in ('entry_candidates.csv','rollover_shape_same_volume.csv'):
        with (Path(export)/name).open(encoding='utf-8-sig',newline='') as stream:
            rows=csv.DictReader(stream)
            if 'date' not in (rows.fieldnames or []):raise ValueError('reader_CSV_day_column_missing:'+name)
            for row in rows:strict_iso_day(row['date'])


def frozen_reader():
    lineage={}
    for path,pin in BINDINGS.items():
        raw=bound_bytes(path,pin);lineage[str(path)]=dict(sha256=pin,bytes=len(raw))
    own=Path(__file__).resolve();raw=own.read_bytes()
    lineage[str(own)]=dict(sha256=sha(raw),bytes=len(raw))
    spec=importlib.util.spec_from_file_location('stage106_private_frozen095',BASE)
    base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    original=base.raw_exports
    def raw_exports(payload,export,arm,cp,a33,pd):
        result=original(payload,export,arm,cp,a33,pd)
        check_csv_days(export)
        return adapt_exports(result,pd)
    base.raw_exports=raw_exports
    base.OUT=OUT
    return base,lineage


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit',action='store_true',required=True)
    parser.add_argument('--arm',choices=('A_OFF','B_OFF'),required=True)
    parser.add_argument('--completion-evidence',type=Path,required=True)
    parser.add_argument('--completion-evidence-sha256',required=True)
    args=parser.parse_args(argv)
    base,lineage=frozen_reader()
    evidence_raw=bound_bytes(args.completion_evidence,args.completion_evidence_sha256)
    evidence=json.loads(evidence_raw);export=base.terminal_schema(evidence,args.arm)
    if args.arm=='A_OFF':
        assert str(args.completion_evidence.absolute())==str(LINE/'outputs/stage104_A_OFF_actual_completion/root_actual_completion.json')
        assert args.completion_evidence_sha256==BINDINGS[args.completion_evidence.absolute()]
    try:
        result,path=base.audit(evidence,args.completion_evidence.absolute(),args.completion_evidence_sha256,export)
    except BaseException as error:
        base.write(OUT/args.arm/evidence['run_id']/'reader_failure_lineage.json',dict(
            status='reader_audit_failed_no_accepted_result',reader_bindings=lineage,error=repr(error),
            completion_evidence_path=str(args.completion_evidence.absolute()),
            completion_evidence_sha256=args.completion_evidence_sha256,financial_replays=0,production_qualified=False))
        raise
    document=base.read(path)
    document.update(reader_adapter_bindings=lineage,original_algorithm_receipt=dict(path=str(path),sha256=sha(path.read_bytes())),
        reader_policy='copy usage.signal_date only after frozen raw-export and identity validation; strict ISO strings or naive midnight Timestamp',
        frozen_accounting_algorithms_changed=False,prior105_reader_failure_preserved=True,financial_replays=0)
    dest=path.parent/'reader_account_checks.json';base.write(dest,document)
    print(json.dumps(dict(status=document['status'],arm=args.arm,receipt_path=str(dest),receipt_sha256=sha(dest.read_bytes())),ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
