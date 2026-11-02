#!/usr/bin/env python3
"""Publish an explicit operator cash review; the live actor consumes it later.

This entry has no CTP login/query, bank-transfer, SMTP or order operation. It
reads existing qualified evidence through the manual component. Writing a
record does not credit account equity or mutate the active funding bundle.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
from qmt_roll_weekly19_funding import OPERATOR_CASH_ASSERTION
from qmt_roll_weekly19_local_backend import LocalEvidenceBackend,private_json
from qmt_roll_weekly19_manual_cash import (
 manual_cash_status,prepare_operator_review,write_and_publish_operator_review,
)

ROOT=Path(__file__).resolve().parents[2]

def parser():
 p=argparse.ArgumentParser(description='Weekly19 operator cash verification; no connection or transfer')
 p.add_argument('--action',choices=['status','confirm'],required=True)
 p.add_argument('--execution-profile',choices=[PROFILE.profile_key],required=True)
 p.add_argument('--context-file',type=Path,required=True)
 p.add_argument('--release-manifest',type=Path,required=True)
 p.add_argument('--activation-receipt',type=Path,required=True)
 p.add_argument('--production-qualification-evidence',type=Path,required=True)
 p.add_argument('--review-input',type=Path)
 p.add_argument('--operator-id',default='')
 p.add_argument('--review-id',default='')
 p.add_argument('--confirm',default='')
 return p

def _output(value):
 print(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False))

def _blocked(reason):
 _output(dict(status='blocked',blockers=[reason]));return 2

def main(argv=None):
 args=parser().parse_args(argv)
 # Reject incomplete confirmations before opening even the private context.
 if args.action=='confirm'and(not args.review_input or not args.operator_id.strip()or not args.review_id.strip()
   or args.confirm!=OPERATOR_CASH_ASSERTION):
  return _blocked('manual_cash_explicit_operator_confirmation_required')
 paths=[args.context_file,args.release_manifest,args.activation_receipt,args.production_qualification_evidence]
 if args.review_input is not None:paths.append(args.review_input)
 if any(not path.is_absolute()or '..'in path.parts for path in paths):
  return _blocked('manual_cash_absolute_paths_required')
 try:
  config=private_json(args.context_file)
  backend=LocalEvidenceBackend(config,repo_root=ROOT,release_manifest=args.release_manifest,
   activation_receipt=args.activation_receipt,qualification_evidence=args.production_qualification_evidence,preview=False)
  backend.context_file=args.context_file
  now=datetime.now(ZoneInfo('Asia/Shanghai'))
  if args.action=='status':result=manual_cash_status(backend,now=now)
  else:
   review=private_json(args.review_input)
   envelope=prepare_operator_review(backend,review,operator_id=args.operator_id,review_id=args.review_id,now=now)
   result=write_and_publish_operator_review(backend,envelope)
  _output(result);return 0
 except (ValueError,KeyError,TypeError,OSError,RuntimeError)as exc:
  # Exceptions can include private raw data or operator notes. The component's
  # safe status endpoint supplies detail; do not echo arbitrary exception text.
  return _blocked('manual_cash_request_blocked:'+type(exc).__name__)

if __name__=='__main__':raise SystemExit(main())
