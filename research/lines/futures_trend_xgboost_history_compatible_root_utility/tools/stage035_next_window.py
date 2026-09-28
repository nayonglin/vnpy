from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import importlib.util
import json
import math
import traceback
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
STAGE = 'stage035_next_window'
OUTPUT = ROOT / 'artifacts' / STAGE
SOURCE = ROOT / 'artifacts/stage034_fill_inventory'
CONTRACT = ROOT / 'stages/20260906_0852_stage035_next_window_contract.md'
FREEZE = ROOT / 'stages/stage035_input_freeze.json'
VALUES = ['open','high','low','close','volume']


def inventory_tool():
    spec=importlib.util.spec_from_file_location('window_inventory034',ROOT/'tools/stage034_fill_inventory.py')
    value=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def evaluate(bars, day, next_day, night, quantity):
    if not next_day:
        return {'status':'no_next_calendar_day','window':None,'bar_count':0}
    available = pd.Timestamp(day) + pd.Timedelta(hours=15)
    windows = [('night',pd.Timestamp(day)+pd.Timedelta(hours=21))] if night else []
    windows.append(('day',pd.Timestamp(next_day)+pd.Timedelta(hours=9)))
    for name,start in windows:
        end=start+pd.Timedelta(minutes=5)
        frame=bars[bars.bar_datetime.ge(start)&bars.bar_datetime.lt(end)].loc[:,['bar_datetime',*VALUES]].copy()
        if frame.empty:
            continue
        frame=frame.drop_duplicates().sort_values('bar_datetime',kind='stable')
        result={'window':name,'start':start.isoformat(),'end_exclusive':end.isoformat(),'bar_count':len(frame)}
        if frame.bar_datetime.duplicated().any():
            return {**result,'status':'conflicting_minute_rows'}
        first=frame.iloc[0]
        result.update(first_time=first.bar_datetime.isoformat(),last_time=frame.bar_datetime.iloc[-1].isoformat())
        if first.bar_datetime <= available:
            return {**result,'status':'fill_before_observation_available'}
        values=[float(first[column]) for column in VALUES]
        if not all(math.isfinite(value) for value in values):
            return {**result,'status':'nonfinite_first_bar'}
        open_,high,low,close,volume=values
        if min(open_,high,low,close)<=0 or low>min(open_,close) or high<max(open_,close) or low>high or volume<0:
            return {**result,'status':'invalid_first_bar'}
        result.update(first_open=open_,first_volume=volume,requested_volume=quantity)
        return {**result,'status':'proxy_supported' if volume>=quantity else 'first_bar_volume_insufficient'}
    return {'status':'window_missing','window':None,'bar_count':0}


def night_products(path):
    matches=[]
    for node in ast.parse(path.read_text()).body:
        if isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='NIGHT_SESSION_PRODUCTS' for target in node.targets):
            matches.append(ast.literal_eval(node.value))
    if len(matches)!=1 or not isinstance(matches[0],set) or not all(isinstance(x,str) for x in matches[0]):
        raise ValueError('window_night_product_source_invalid')
    return matches[0]


def parse_clock(values):
    parsed=pd.to_datetime(values,errors='raise')
    if parsed.isna().any():
        raise ValueError('window_minute_timestamp_missing')
    if parsed.dt.tz is not None:
        parsed=parsed.dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
    return parsed


def collect_inputs():
    upstream=inventory_tool()
    files=upstream.collect_inputs()
    files.update(window_runner=Path(__file__).resolve(),window_contract=CONTRACT,
        window_tests=ROOT/'tests/test_stage035_next_window.py',inventory_summary=SOURCE/'summary.json',
        inventory_manifest=SOURCE/'input_manifest.json',inventory_freeze=upstream.FREEZE)
    for name in ('inventory.json.gz','holding_cost_states.json.gz','root_population.csv','monthly_population.csv'):
        files['inventory_output_'+name]=SOURCE/name
    return dict(sorted(files.items()))


def configured():
    runner=inventory_tool().configured()
    runner.STAGE=STAGE
    runner.collect_input_files=collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT=len(collect_inputs())
    return runner


def run():
    if OUTPUT.exists():
        raise RuntimeError('window_campaign_already_exists')
    runner=configured();manifest=runner.build_input_manifest()
    runner.validate_frozen_input_contract(FREEZE,manifest)
    upstream=inventory_tool();original=upstream.configured()
    old_manifest=json.loads((SOURCE/'input_manifest.json').read_text())
    original.validate_frozen_input_contract(upstream.FREEZE,old_manifest)
    original.validate_current_input_manifest(old_manifest)
    summary=json.loads((SOURCE/'summary.json').read_text())
    if summary['status']!='inventory_reconciled_not_execution_or_model':
        raise ValueError('window_cost_source_not_qualified')
    for value in summary['outputs'].values():
        identity=value.get('compressed',value)
        if runner._file_identity(Path(identity['path']))!=identity:
            raise ValueError('window_inventory_output_changed')
        if 'raw_sha256' in value and hashlib.sha256(gzip.decompress(Path(identity['path']).read_bytes())).hexdigest()!=value['raw_sha256']:
            raise ValueError('window_inventory_raw_changed')
    batch=upstream.load('stage004_label_batch')
    OUTPUT.mkdir(mode=0o700);batch.write_json(OUTPUT/'input_manifest.json',manifest)
    try:
        states=json.loads(gzip.decompress((SOURCE/'holding_cost_states.json.gz').read_bytes()))
        states=[row for row in states if row['inventory_state_status']=='inventory_reconciled_holding']
        if len(states)!=summary['state_counts']['inventory_reconciled_holding']:
            raise ValueError('window_observation_count_changed')
        calendar=pd.read_csv(upstream.SOURCE/'workers/A/daily.csv.gz',usecols=['date']).date.tolist()
        next_date=dict(zip(calendar,calendar[1:]))
        symbols={symbol for row in states for symbol in row['contract_costs']}
        chunks=[];source_rows=0
        minute_path=Path(manifest['files']['full_minute_bars']['path'])
        for frame in pd.read_csv(minute_path,usecols=['vt_symbol','bar_datetime',*VALUES],chunksize=200000):
            source_rows+=len(frame)
            frame=frame[frame.vt_symbol.isin(symbols)].copy()
            frame['bar_datetime']=parse_clock(frame.bar_datetime)
            for name in VALUES:
                frame[name]=pd.to_numeric(frame[name],errors='coerce')
            selected=frame.bar_datetime.dt.hour.isin([9,21])&frame.bar_datetime.dt.minute.lt(5)
            chunks.append(frame[selected])
        data=pd.concat(chunks,ignore_index=True)
        groups={symbol:frame for symbol,frame in data.groupby('vt_symbol',sort=False)}
        empty=data.iloc[:0]
        code=Path(manifest['files']['production_portfolio/analyze_qmt_roll_stage501_asymmetric_entry_exit_execution.py']['path'])
        nights=night_products(code)
        results=[]
        for row in states:
            if len(row['contract_costs'])!=1:
                raise ValueError('window_actual_contract_ambiguous')
            symbol,cost=next(iter(row['contract_costs'].items()))
            day=row['date'];quantity=abs(float(cost['quantity']))
            result=evaluate(groups.get(symbol,empty),day,next_date.get(day),row['product_vt_symbol'] in nights,quantity)
            results.append({'date':day,'next_calendar_day':next_date.get(day),'product_vt_symbol':row['product_vt_symbol'],
                'vt_symbol':symbol,'actual_volume':quantity,**result})
        runner.validate_current_input_manifest(manifest)
        frame=pd.DataFrame(results)
        path=OUTPUT/'windows.csv';runner._write_bytes_exclusive(path,frame.to_csv(index=False).encode())
        counts=dict(Counter(row['status'] for row in results));passed=counts.get('proxy_supported',0)==len(results)
        result={'stage':STAGE,'status':'minute_proxy_coverage_passed_not_execution' if passed else 'minute_proxy_coverage_failed',
            'observation_count':len(results),'source_minute_rows':source_rows,'candidate_contract_count':len(symbols),
            'status_counts':counts,'window_counts':dict(Counter(row['window'] or 'missing' for row in results)),
            'all_observations_have_proxy_support':passed,'file_contract_sha256':manifest['file_contract_sha256'],
            'output':runner._file_identity(path),'new_download_count':0,'new_replay_count':0,'new_utility_label_count':0,
            'model_fit_predict_count':0,'reviewer_started':False}
        batch.write_json(OUTPUT/'summary.json',result);print(json.dumps(result),flush=True)
    except BaseException as exc:
        batch.write_json(OUTPUT/'failure.json',{'status':'failed','error':str(exc),'traceback':traceback.format_exc()})
        raise


def main():
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze',action='store_true');mode.add_argument('--run',action='store_true')
    args=parser.parse_args()
    if args.freeze:
        runner=configured();manifest=runner.build_input_manifest();runner.validate_input_manifest_payload(manifest)
        payload={key:manifest[key] for key in ('schema_version','stage','line_id','input_file_count','input_logical_key_sha256',
            'file_contract_sha256','runtime_contract_sha256')};payload['execution_authorized']=True
        inventory_tool().load('stage004_label_batch').write_json(FREEZE,payload);print(json.dumps(payload),flush=True)
    else:run()


if __name__=='__main__':main()
