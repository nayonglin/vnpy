"""在任何Stage256绩效产生前冻结全部201账户的月池；不启动回测。"""
from __future__ import annotations
import argparse
from bisect import bisect_right
import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / 'research/lines/futures_trend_rollover_shape_same_volume'
UNIVERSE = sorted('AP.CZCE CF.CZCE FG.CZCE MA.CZCE OI.CZCE SA.CZCE SH.CZCE SM.CZCE jm.DCE lh.DCE lc.GFEX si.GFEX au.SHFE cu.SHFE hc.SHFE rb.SHFE ru.SHFE sp.SHFE'.split())
ROOT_SEED = 20261016
START, END = '2025-01-01', '2026-10-14'
DESIGN = LINE / 'stages/20261016_0100_stage256_random10_ai_experiment_design.md'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def random_memberships(universe, dates, path_id):
    if len(universe) != 18 or len(set(universe)) != 18 or 'fu.SHFE' in universe:
        raise ValueError('expected_18_distinct_non_fu')
    if not 1 <= path_id <= 199:
        raise ValueError('path_id_outside_preregistered_range')
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([ROOT_SEED, path_id])))
    return {d: sorted(rng.choice(sorted(universe), size=10, replace=False).tolist()) + ['fu.SHFE']
            for d in sorted(dates)}


def dump_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=LINE / 'outputs/stage256_random10_ai')
    args = parser.parse_args()
    out = args.output.resolve()
    if (out / 'experiment_manifest.json').exists() or any((out / 'accounts').glob('*')):
        raise SystemExit('refuse_to_overwrite_frozen_experiment')
    ref = LINE / 'outputs/stage251_half_r_ab/C_final'
    params = json.loads((ref / 'effective_parameters.json').read_text())['spec']['overrides']
    source = Path(params['ai_product_pool_eligibility_path'])
    official_id = params['ai_product_pool_strategy']
    with source.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        columns, source_rows = reader.fieldnames, list(reader)
    assert set(r['strategy'] for r in source_rows) == {official_id}
    grouped = {}
    for row in source_rows:
        grouped.setdefault(row['eval_date'], []).append(row)
    dates = sorted(d for d in grouped if '2024-12-31' <= d <= END)
    assert len(dates) == 22 and dates[0] == '2024-12-31' and dates[-1] == '2026-09-30'
    universe_file = Path(params['product_universe_csv_path'])
    with universe_file.open(encoding='utf-8-sig') as f:
        eligible = {r['product_vt_symbol'] for r in csv.DictReader(f) if float(r['eligible']) == 1}
    assert eligible == set(UNIVERSE) | {'fu.SHFE'}
    assert {r['product_vt_symbol'] for r in grouped['2019-12-31']} == set(UNIVERSE)
    for d in dates:
        members = [r['product_vt_symbol'] for r in grouped[d]]
        assert len(members) == 11 and len(set(members)) == 11 and 'fu.SHFE' in members
        assert set(members) <= eligible

    # 仅验证过去日线/上市可用性，不基于未来分钟完整性筛除任何品种。
    preflight = []
    mapping_file = ROOT / 'examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv'
    with sqlite3.connect(f"file:{ROOT / '.vntrader/database.db'}?mode=ro", uri=True) as con:
        latest = con.execute("select max(datetime) from dbbardata where interval='d'").fetchone()[0]
        assert latest[:10] == END
        actual_bars = {(f'{symbol}.{exchange}', dt[:10]) for symbol, exchange, dt in con.execute(
            "select symbol,exchange,datetime from dbbardata where interval='d' and datetime >= '2023-12-31'")}
        mapped_history = {product: [] for product in eligible}
        with mapping_file.open(encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                product = row['continuous_symbol_vt']
                if product in mapped_history and (row['main_contract_vt'], row['date']) in actual_bars:
                    mapped_history[product].append(row['date'])
        for product in sorted(eligible):
            history = sorted(set(mapped_history[product]))
            if not history:
                raise ValueError(f'mapped_contract_daily_history_missing:{product}')
            for d in dates:
                lower = (datetime.fromisoformat(d) - timedelta(days=365)).date().isoformat()
                count = bisect_right(history, d) - bisect_right(history, lower)
                row = {'product': product, 'eval_date': d, 'past_365d_daily_count': count,
                       'history_first_date': history[0], 'eval_day_present': d in history,
                       'minimum_41_met': count >= 41}
                preflight.append(row)
                if not row['minimum_41_met'] or not row['eval_day_present']:
                    raise ValueError(f'point_in_time_daily_preflight:{row}')

    pools = out / 'pools'
    pools.mkdir(parents=True, exist_ok=True)
    (out / 'accounts').mkdir(exist_ok=True)
    (out / 'logs').mkdir(exist_ok=True)
    dump_json(out / 'universe_preflight.json', {
        'scope': 'fixed formal universe; main-mapping plus exact-contract local daily availability, not proof of historical metadata publication',
        'universe_file': str(universe_file), 'universe_sha256': sha(universe_file),
        'mapping_file': str(mapping_file), 'mapping_sha256': sha(mapping_file),
        'latest_daily': latest, 'checks': preflight, 'status': 'passed'})
    accounts = {}
    ids = ['AI_MONTHLY', 'AI_INITIAL_FIXED'] + [f'RANDOM_{i:03d}' for i in range(1, 200)]
    matrix = []
    initial = sorted(r['product_vt_symbol'] for r in grouped[dates[0]] if r['product_vt_symbol'] != 'fu.SHFE') + ['fu.SHFE']
    for account_id in ids:
        destination = pools / f'{account_id}.csv'
        path_id = int(account_id.split('_')[-1]) if account_id.startswith('RANDOM_') else None
        kind = 'random_monthly' if path_id else ('ai_monthly' if account_id == 'AI_MONTHLY' else 'ai_initial_fixed')
        policy_id = official_id if kind == 'ai_monthly' else f'stage256_{kind}_v1'
        if path_id:
            memberships = random_memberships(UNIVERSE, dates, path_id)
        elif kind == 'ai_initial_fixed':
            memberships = {d: initial for d in dates}
        else:
            memberships = {d: [r['product_vt_symbol'] for r in grouped[d]] for d in dates}
        if kind == 'ai_monthly':
            destination.write_bytes(source.read_bytes())
        else:
            rows = [dict(r, strategy=policy_id) for r in source_rows if r['eval_date'] < dates[0]]
            for d, members in memberships.items():
                template = grouped[d][0]
                for rank, product in enumerate(members, 1):
                    rows.append(dict(template, strategy=policy_id, eval_date=d,
                                     product_vt_symbol=product, score='0.0', score_rank=str(rank),
                                     top_n='11', score_type='research_membership_placeholder_not_model_score'))
            with destination.open('w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(rows)
        accounts[account_id] = {'pool_file': str(destination), 'pool_sha256': sha(destination),
                                'policy_id': policy_id, 'kind': kind, 'path_id': path_id}
        for d, members in memberships.items():
            for product in sorted(members):
                matrix.append({'account_id': account_id, 'eval_date': d, 'product': product})
    with (out / 'frozen_monthly_members.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['account_id', 'eval_date', 'product'])
        writer.writeheader()
        writer.writerows(matrix)
    minute = Path(json.loads((ref / 'opening_minute_coverage_summary.json').read_text())['minute_source'])
    minute_hash = sha(minute)
    assert minute_hash == '5c06124fac52ff37a19d1abe89f6f6a80d36b8ece874eb647286377317289189'
    manifest = {
        'schema_version': 1, 'frozen_at': datetime.now().astimezone().isoformat(),
        'stage': 256, 'status': 'preregistered_before_any_stage256_account',
        'start': START, 'end': END, 'capital': 150000, 'root': str(ROOT),
        'master_seed': ROOT_SEED, 'random_count': 199, 'expected_account_count': 201,
        'numpy_version': np.__version__, 'random_algorithm': 'PCG64(SeedSequence([20261016,path_id])); choice(sorted18,10,replace=False); sequential22months',
        'expected_eval_dates': dates, 'non_fu_universe': UNIVERSE, 'fixed_product': 'fu.SHFE',
        'minute_csv': str(minute), 'minute_cache_sha256': minute_hash,
        'reference_settings_path': str(ref / 'actual_strategy_settings.json'),
        'parameters_reference_path': str(ref / 'effective_parameters.json'),
        'source_pool': str(source), 'source_pool_sha256': sha(source),
        'design_path': str(DESIGN), 'design_sha256': sha(DESIGN),
        'freeze_tool_sha256': sha(Path(__file__)), 'accounts': accounts,
        'frozen_monthly_members_sha256': sha(out / 'frozen_monthly_members.csv'),
        'policy_scope': 'monthly gate only; half-R off; C2 and independent pairwise unchanged; no downloads',
        'primary_endpoint': 'ending_equity', 'strong_support_max_random_ge_ai': 9,
        'data_policy': 'any material execution coverage gap => entire comparison diagnostic; never drop/resample account',
    }
    dump_json(out / 'experiment_manifest.json', manifest)
    print(json.dumps({'output': str(out), 'account_count': len(accounts), 'matrix_rows': len(matrix),
                      'manifest_sha256': sha(out / 'experiment_manifest.json'), 'frozen_at': manifest['frozen_at']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
