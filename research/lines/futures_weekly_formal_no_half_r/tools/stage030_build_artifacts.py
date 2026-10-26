"""Read-only Stage030 baseline/daily-profit/weekly-profit ledger comparison.

Uses the frozen Stage029 report's pure accounting functions, never a strategy or
engine. It cannot create an acceptance, run a replay, repair inputs, or promote.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import stage029_build_artifacts as old

# Frozen Stage029 R_attempt003: compact sorted relative-file-name -> SHA256 JSON.
BASELINE_SNAPSHOT_SHA256 = 'e242ed8ed99f90139dec4faf6ae9c63e639b4deda95edec13dd6102000f348d1'
CAPITAL, POOL, FLAGS, EXECUTION_MODEL = old.CAPITAL, old.POOL, old.FLAGS, old.EXECUTION_MODEL
sha, verify_sources, snapshot_dir = old.sha, old.verify_sources, old.snapshot_dir
ordered_fills, inventory_accounting = old.ordered_fills, old.inventory_accounting
annual_rows, product_rows, slice_rows = old.annual_rows, old.product_rows, old.slice_rows
ROLES = ('baseline', 'daily', 'weekly')
LABELS = {'baseline':'base weekly technical exits', 'daily':'daily close profit>5% half once',
          'weekly':'weekly close profit>5% half once'}


def snapshot_identity(snapshot, directory):
    directory = Path(directory).resolve()
    relative = {str(Path(p).relative_to(directory)):digest for p,digest in snapshot.items()}
    return hashlib.sha256(json.dumps(relative, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_profit_acceptance(ledger, frequency):
    proof = ledger['acceptances'].get('profit_half_acceptance.json')
    expected = dict(schema='stage030_profit_half_acceptance_v1', accepted=True, frequency=frequency,
        threshold=.05, exit_ratio=.5, threshold_comparison='strict_gt',
        profit_basis='actual_synced_native_contract_weighted_entry_price', quantity_rule='floor_half_keep_at_least_one',
        once_per_native_contract_round=True, technical_exits_frequency='weekly', execution_model=EXECUTION_MODEL)
    if not isinstance(proof, dict):
        raise ValueError('profit_half_acceptance_required:'+frequency)
    for key,value in expected.items():
        if type(proof.get(key)) is not type(value) or proof[key] != value:
            raise ValueError('profit_half_contract:'+frequency+':'+key)
    for key in ['trigger_count', 'executed_trigger_count', 'terminal_pending_trigger_count', 'one_lot_skipped_count']:
        if type(proof.get(key)) is not int or proof[key] < 0:
            raise ValueError('profit_half_nonnegative_integer_required:'+frequency+':'+key)
    if proof['trigger_count'] != proof['executed_trigger_count']+proof['terminal_pending_trigger_count']:
        raise ValueError('profit_half_trigger_execution_pending_conservation:'+frequency)
    if proof.get('invariant_failures') != []:
        raise ValueError('profit_half_invariant_failures:'+frequency)
    sources = proof.get('source_files_sha256')
    if not isinstance(sources, dict) or not sources:
        raise ValueError('profit_half_nonempty_source_files_sha256_required:'+frequency)
    if not {'stage030_profit5_half.py', 'test_stage030_profit5_half.py'}.issubset({Path(p).name for p in sources}):
        raise ValueError('profit_half_adapter_and_behavior_test_sources_required:'+frequency)
    for path,digest in sources.items():
        if not Path(path).is_absolute() or not isinstance(digest, str) or len(digest) != 64:
            raise ValueError('profit_half_invalid_source_binding:'+frequency)
        if ledger['sources'].get(str(Path(path).resolve())) != digest:
            raise ValueError('profit_half_source_not_bound_to_input_manifest:'+str(path))
    verify_sources(sources)
    return proof


def validate_configuration(ledger, frequency):
    path = Path(ledger['path'])/'actual_profit_half_configuration.json'
    if str(path) not in ledger['attempt_snapshot']:
        raise ValueError('profit_half_configuration_required:'+frequency)
    value = json.loads(path.read_text())
    expected = dict(research_profit_half_enabled=True, research_profit_half_frequency=frequency,
        research_profit_half_threshold=.05, research_profit_half_ratio=.5)
    if not isinstance(value, dict) or set(value) != set(expected) or any(type(value[k]) is not type(v) or value[k] != v for k,v in expected.items()):
        raise ValueError('profit_half_configuration_mismatch:'+frequency)
    return value


def validate_comparison(ledgers):
    base = ledgers['baseline']
    for name in ['profit_half_acceptance.json', 'actual_profit_half_configuration.json']:
        if str(Path(base['path'])/name) in base['attempt_snapshot']:
            raise ValueError('baseline_profit_half_must_be_absent:'+name)
    for group in ['setting', 'actual']:
        if any('profit_half' in k for k in base['settings'][0][group]):
            raise ValueError('baseline_profit_half_marker_must_be_absent')
    differences = {}
    for role in ['daily', 'weekly']:
        arm = ledgers[role]
        if not base['daily'].date.equals(arm['daily'].date):
            raise ValueError('same_requested_and_actual_window_calendar_required:'+role)
        for key in ['start', 'end', 'identity', 'execution_model', 'minute_quote_confirmed', 'universe_products', 'ready_need', 'storage_capacity']:
            if base['preflight'].get(key) != arm['preflight'].get(key):
                raise ValueError('same_preflight_contract_required:'+role+':'+key)
        if base['preflight']['start'] != '2015-01-01' or base['preflight']['end'] != '2026-10-26':
            raise ValueError('stage030_fixed_requested_window_required')
        if base['database_sha256'] != arm['database_sha256']:
            raise ValueError('same_database_snapshot_required:'+role)
        differences[role] = {}
        for group in ['setting', 'actual']:
            left,right = base['settings'][0][group],arm['settings'][0][group]
            diffs = {key:{'baseline':left.get(key), role:right.get(key)} for key in sorted(set(left)|set(right)) if left.get(key) != right.get(key) or (key in left) != (key in right)}
            differences[role][group] = diffs
            if diffs:
                raise ValueError('undeclared_setting_or_marker_changes:'+role+':'+group+':'+','.join(diffs))
        if base['effective'] != arm['effective']:
            raise ValueError('same_effective_parameters_required:'+role)
        arm['profit_half_configuration'] = validate_configuration(arm, role)
        arm['profit_half'] = validate_profit_acceptance(arm, role)
    return differences


def plot(ledgers, path):
    os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/weekly-research-mpl')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    fig,(top,bottom)=plt.subplots(2,1,figsize=(13,8),sharex=True,gridspec_kw={'height_ratios':[2,1]})
    for role,color in zip(ROLES,['#2467a6','#cc7430','#388663']):
        d=ledgers[role]['daily']
        top.plot(d.date,d.account_equity,lw=1.4,color=color,label=LABELS[role])
        peak=np.maximum.accumulate(np.r_[CAPITAL,d.account_equity.to_numpy()])[1:]
        bottom.plot(d.date,(d.account_equity/peak-1)*100.,lw=1.1,color=color)
    top.axhline(CAPITAL,color='#888',lw=.7,ls='--');top.legend(frameon=False,fontsize=9)
    top.set_ylabel('Modeled equity (CNY)');top.yaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:,.0f}'))
    bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Exchange trading date')
    for ax in [top,bottom]:
        ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
    dates=ledgers['baseline']['metrics']
    fig.suptitle('OFFLINE RESEARCH / NO PROMOTION / INDEPENDENT REVIEW PENDING\n'+
        'Original19; CNY150,000 each; all technical indicators and stops weekly; RSI / short case2 off\n'+
        f"{dates['actual_start']} to {dates['actual_end']}; zero commissions; fixed slippage; daily-open model",fontsize=10.5,fontweight='bold')
    fig.text(.5,.014,'Only new profit-taking frequency differs; strict price profit >5%, floor half once per native contract round. Actual broker margin 1.65x.',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.025,1,.9]);fig.savefig(path,dpi=170);plt.close(fig)


def rename_exclusive(source, destination):
    """Atomically publish a directory without replacing even an existing empty directory."""
    libc=ctypes.CDLL(None,use_errno=True)
    if hasattr(libc,'renamex_np'):
        method=libc.renamex_np;method.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_uint]
        result=method(os.fsencode(source),os.fsencode(destination),4)  # macOS RENAME_EXCL
    elif hasattr(libc,'renameat2'):
        method=libc.renameat2;method.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint]
        result=method(-100,os.fsencode(source),-100,os.fsencode(destination),1)  # RENAME_NOREPLACE
    else:
        raise RuntimeError('atomic_exclusive_directory_rename_unavailable')
    if result:
        code=ctypes.get_errno();raise OSError(code,os.strerror(code),str(destination))


def build_artifacts(baseline_dir, daily_dir, weekly_dir, out_dir, figure):
    inputs=[Path(p).resolve() for p in [baseline_dir,daily_dir,weekly_dir]]
    out_dir,figure=Path(out_dir).resolve(),Path(figure).resolve()
    if len(set(inputs)) != 3:
        raise ValueError('three_distinct_input_directories_required')
    old.validate_output_paths(out_dir,figure,inputs)
    if snapshot_identity(snapshot_dir(inputs[0]),inputs[0]) != BASELINE_SNAPSHOT_SHA256:
        raise ValueError('baseline_must_be_identical_frozen_R003')
    # All three have Stage029 weekly exits and RSI/short2 disabled. The old
    # report's baseline role described a different historical RSI-enabled arm.
    ledgers={role:old.load_ledger(path,'candidate') for role,path in zip(ROLES,inputs)}
    for role,ledger in ledgers.items():
        ledger['role']=role
    differences=validate_comparison(ledgers)
    tool_paths=[Path(__file__).resolve(),Path(__file__).with_name('test_stage030_report_builder.py').resolve(),
        Path(old.__file__).resolve(),Path(old.__file__).with_name('test_stage029_report_builder.py').resolve()]
    sources={str(p):sha(p) for p in tool_paths}
    for ledger in ledgers.values():
        for path,digest in ledger['sources'].items():
            if path in sources and sources[path] != digest:
                raise ValueError('comparison_conflicting_source_hash:'+path)
            sources[path]=digest
    annual=[row for ledger in ledgers.values() for row in annual_rows(ledger)]
    products=[row for ledger in ledgers.values() for row in product_rows(ledger)]
    slices=[row for ledger in ledgers.values() for row in slice_rows(ledger)]
    arms={role:dict(attempt_path=l['path'],label=LABELS[role],actual_strategy_class=l['settings'][0]['strategy_class'],
        metrics=l['metrics'],accounting=l['accounting'],risk=l['risk'],database_sha256=l['database_sha256'],
        acceptance_files=sorted(l['acceptances']),profit_half=l.get('profit_half'),profit_half_configuration=l.get('profit_half_configuration'),
        terminal_open_positions=l['opened'].to_dict('records')) for role,l in ledgers.items()}
    baseline=ledgers['baseline']
    summary=dict(schema='stage030_readonly_three_arm_comparison_v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        status='DERIVED_PENDING_INDEPENDENT_REVIEW',independent_review_verdict=None,production_qualified=False,
        promotion_decision='NO_PROMOTION',financial_replays=0,arms=arms,parameter_differences=differences,
        comparisons={role:{key:ledgers[role]['metrics'][key]-baseline['metrics'][key] for key in ['end_equity','total_return_pct','max_dd_pct']} for role in ['daily','weekly']},
        contract=dict(requested_start='2015-01-01',requested_end='2026-10-26',actual_asof=baseline['metrics']['actual_end'],
            capital=CAPITAL,pool=sorted(POOL),execution_model=EXECUTION_MODEL,technical_exits_frequency='weekly',
            profit_basis='actual_synced_native_contract_weighted_entry_price',threshold=.05,threshold_comparison='strict_gt',exit_ratio=.5,
            once_per_native_contract_round=True,quantity_rule='floor_half_keep_at_least_one',
            commission='zero',slippage='fixed source effective_parameters',actual_margin_multiplier=1.65,legacy_broker10_multiplier=1.1,
            baseline_snapshot_sha256=BASELINE_SNAPSHOT_SHA256),
        limitations=['Repeated historical sample and multiple research iterations; fixed 5%/50% controls do not constitute PIT, OOS, or promotion evidence.',
            'Static original19, zero commission, fixed slippage, daily-open fills; spread/depth/queue/capacity qualification absent.',
            'Stage028 source disputes, accepted-observation week gaps and historical main mapping timestamp limitations remain.',
            'Full contract rounds do not merge rollover contracts. Open rounds retain partial realized PnL; terminal inventory is marked, never forcibly closed.',
            'Profit triggers and modeled fills are distinct; terminal pending profit targets remain unexecuted. Next-open gaps can realize less than 5%.',
            'Accepted replay gates and accounting derivation are not an independent result review.'],source_files_sha256=sources)
    out_dir.parent.mkdir(parents=True,exist_ok=True)
    if not figure.is_relative_to(out_dir):
        figure.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.stage030_report_',dir=out_dir.parent) as temporary:
        temp=Path(temporary);tables=temp/'tables';tables.mkdir();pic=temp/'equity_drawdown.png'
        for name,rows in [('annual.csv',annual),('products.csv',products),('slices_2015_2019_2020.csv',slices)]:
            pd.DataFrame(rows).to_csv(tables/name,index=False)
        pd.DataFrame([dict(role=role,label=LABELS[role],**l['metrics'],
            **{'fifo_'+k:v for k,v in l['accounting']['closed_fifo'].items()},
            **{'round_'+k:v for k,v in l['accounting']['complete_contract_rounds'].items()},**l['risk'],
            open_remaining_net_mtm=l['accounting']['open_remaining_net_mtm'],open_round_net_mtm=l['accounting']['open_round_net_mtm'],
            profit_half_trigger_count=l.get('profit_half',{}).get('trigger_count',0),
            profit_half_executed_trigger_count=l.get('profit_half',{}).get('executed_trigger_count',0),
            profit_half_terminal_pending_trigger_count=l.get('profit_half',{}).get('terminal_pending_trigger_count',0),
            profit_half_one_lot_skipped_count=l.get('profit_half',{}).get('one_lot_skipped_count',0)) for role,l in ledgers.items()]).to_csv(tables/'summary.csv',index=False)
        for name,key in [('closed_fifo_segments.csv','segments'),('complete_contract_rounds.csv','rounds'),('terminal_open_rounds.csv','opened')]:
            pd.concat([l[key].assign(role=role) for role,l in ledgers.items()],ignore_index=True).to_csv(tables/name,index=False)
        for role,l in ledgers.items():
            l['daily'][['date','account_equity','net_pnl','slippage','commission','trade_count']].to_csv(tables/(role+'_daily.csv'),index=False)
        plot(ledgers,pic)
        summary['output_files_sha256']={str(out_dir/p.name):sha(p) for p in sorted(tables.glob('*.csv'))}
        summary['output_files_sha256'][str(figure)]=sha(pic)
        (tables/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        manifest=dict(schema='stage030_report_delivery_manifest_v1',comparison_sha256=sha(tables/'comparison.json'),
            files_sha256={**summary['output_files_sha256'],str(out_dir/'comparison.json'):sha(tables/'comparison.json')},
            self_hash_excluded=True,independent_review_verdict=None)
        (tables/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        verify_sources(sources)
        for l in ledgers.values():
            if snapshot_dir(l['path']) != l['attempt_snapshot']:
                raise ValueError('attempt_file_set_or_bytes_changed:'+l['path'])
        old.validate_output_paths(out_dir,figure,inputs)
        if figure.is_relative_to(out_dir):
            target=tables/figure.relative_to(out_dir);target.parent.mkdir(parents=True,exist_ok=True)
            os.link(pic,target);rename_exclusive(tables,out_dir)
        else:
            os.link(pic,figure)
            try:
                rename_exclusive(tables,out_dir)
            except Exception:
                figure.unlink();raise
    return dict(status='DERIVED_PENDING_INDEPENDENT_REVIEW',outputs=[str(out_dir),str(figure)],financial_replays=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ['baseline-dir','daily-dir','weekly-dir','out-dir','figure']:
        parser.add_argument('--'+flag,type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build_artifacts(args.baseline_dir,args.daily_dir,args.weekly_dir,args.out_dir,args.figure),ensure_ascii=False))


if __name__ == '__main__':
    main()
