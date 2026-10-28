"""Publish a separate final-status figure from unchanged, reviewed Stage032 curves."""
from pathlib import Path
from contextlib import contextmanager
import argparse
import hashlib
import json
import os

os.environ.setdefault('MPLCONFIGDIR','/private/tmp/stage032-mpl')
import pandas as pd
from stage032_build_artifacts import plot


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextmanager
def reviewed_title():
    from matplotlib.figure import Figure
    original=Figure.suptitle
    def title(self,text,*args,**kwargs):
        text=text.replace('INDEPENDENT REVIEW PENDING','INDEPENDENT REVIEW PASSED WITH LIMITATIONS')
        return original(self,text,*args,**kwargs)
    Figure.suptitle=title
    try:
        yield
    finally:
        Figure.suptitle=original


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--review-sha256',required=True)
    parser.add_argument('--figure',type=Path,required=True)
    args=parser.parse_args()
    if sha(args.review)!=args.review_sha256:
        raise ValueError('independent_review_sha_mismatch')
    proof=json.loads(args.review.read_text())
    verdict=proof.get('verdict',proof.get('status',''))
    if not str(verdict).startswith('PASS'):
        raise ValueError('independent_PASS_required')
    receipt=args.figure.with_suffix('.receipt.json')
    if args.figure.exists() or receipt.exists():
        raise ValueError('refuse_visual_overwrite')
    report=json.loads((args.report/'comparison.json').read_text())
    ledgers={};inputs={str(args.review.resolve()):sha(args.review),str((args.report/'comparison.json').resolve()):sha(args.report/'comparison.json'),str(Path(__file__).resolve()):sha(__file__)}
    from stage032_build_artifacts import __file__ as report_source
    inputs[str(Path(report_source).resolve())]=sha(report_source)
    curve_sha={}
    for role in ['baseline','candidate']:
        path=args.report/(role+'_daily.csv')
        daily=pd.read_csv(path,parse_dates=['date'])
        ledgers[role]=dict(daily=daily,metrics=report['arms'][role]['metrics'])
        inputs[str(path.resolve())]=sha(path)
        points=[(day.strftime('%Y-%m-%d'),float(value)) for day,value in zip(daily.date,daily.account_equity)]
        curve_sha[role]=hashlib.sha256(json.dumps(points,separators=(',',':')).encode()).hexdigest()
    args.figure.parent.mkdir(exist_ok=True,parents=True)
    with reviewed_title():
        plot(ledgers,args.figure)
    if any(sha(name)!=digest for name,digest in inputs.items()):
        raise ValueError('visual_input_changed')
    receipt.write_text(json.dumps(dict(status='PASS_REVIEWED_CURVES_SAME_POINTS_TITLE_ONLY',verdict=verdict,financial_replays=0,strategy_parameter_changes=0,source_files_sha256=inputs,curve_points_sha256=curve_sha,figure_sha256=sha(args.figure),note='Separate figure; original pending-review report and figure remain byte-identical.'),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'figure':str(args.figure),'receipt':str(receipt),'financial_replays':0}))


if __name__=='__main__':
    main()
