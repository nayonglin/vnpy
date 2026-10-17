"""Stage254日期标签薄适配；复用Stage249账本算法，不运行策略/回测。"""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import pandas as pd
import stage249_summarize_replay as original


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    source=args.source.resolve();output=args.output.resolve()
    metrics_path=source/'metrics.json'
    metrics=json.loads(metrics_path.read_text())
    start=pd.Timestamp(metrics['start']).date().isoformat()
    # Date-only correction is valid because all economic rows are inside this run.
    daily=pd.read_csv(source/'daily.csv',usecols=['date'])
    assert len(daily)>0 and daily.date.min()>=start
    assert start>='2020-01-01'
    with redirect_stdout(io.StringIO()):
        original.main()
    summary_path=output/'summary.json'
    summary=json.loads(summary_path.read_text())
    old_start=summary['periods']['all']['start']
    assert old_start=='2020-01-01'
    summary['periods']['all']['start']=start
    summary['date_label_adapter']={
        'scope':'Only periods.all.start label is changed to metrics.start; economics and CSV outputs use the unmodified Stage249 helper.',
        'original_label':old_start,
        'corrected_label':start,
        'metrics_sha256':hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
        'stage249_helper_sha256':hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest(),
        'stage254_wrapper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    summary_path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='source_hashes'},ensure_ascii=False))

if __name__=='__main__':
    main()
