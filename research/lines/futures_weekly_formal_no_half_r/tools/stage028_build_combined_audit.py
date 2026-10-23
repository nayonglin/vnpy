"""Join frozen read-only Stage028 audits; never invokes a backtest or mutates inputs."""
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv
import hashlib
import json

LINE = Path(__file__).resolve().parents[1]
OUT = LINE / 'outputs/stage028_combined_audit_v1'
ART = LINE / 'artifacts/stage028_per_episode_review.md'
STATS = LINE / 'outputs/stage028_2015_2020_trade_audit'
KLINE = LINE / 'outputs/stage028_2015_2020_kline_audit'
MAIN = LINE / 'outputs/stage028_2015_2020_mapping_audit'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def index(rows, key):
    result = {}
    for r in rows:
        if not r[key] or r[key] in result:
            raise ValueError('empty_or_duplicate_join_key:' + key)
        result[r[key]] = r
    return result


def label(v):
    if v in {'PASS_INDEPENDENT_AGREEMENT', 'PASS_agreement'}:
        return '独立一致'
    if 'CONFLICT' in v:
        return '有冲突'
    if 'INSUFFICIENT' in v:
        return '证据不足'
    return v


def number(v):
    return f'{float(v):,.2f}'.rstrip('0').rstrip('.')


def main():
    if OUT.exists() or ART.exists():
        raise RuntimeError('immutable_output_already_exists')
    source_files = [
        STATS / 'episodes_entry_cohort_2015_2020.csv',
        STATS / 'episodes_exit_2015_2020.csv',
        STATS / 'statistics_summary.json',
        KLINE / 'per_episode_audit.csv',
        KLINE / 'per_trade_audit.csv',
        KLINE / 'scope_summary.json',
        MAIN / 'all_201_entry_episodes_main_audit.csv',
        MAIN / 'all_201_entry_episodes_full_life_408_fills_mapping_audit.csv',
        LINE / 'stages/stage028_stats_review.json',
        LINE / 'stages/stage028_kline_source_review.json',
        LINE / 'stages/stage028_mapping_independent_review.json',
        LINE / 'outputs/stage028_root_whole_week_audit.json',
        KLINE / 'signal_week_inputs.csv',
        Path(__file__).resolve(),
    ]
    before = {str(p): digest(p) for p in source_files}
    stats = index(read(source_files[0]), 'first_entry_trade_id')
    exits = index(read(source_files[1]), 'first_entry_trade_id')
    kline = index(read(KLINE / 'per_episode_audit.csv'), 'first_entry_trade_id')
    mapping = index(read(MAIN / 'all_201_entry_episodes_main_audit.csv'), 'entry_trade_id')
    assert set(stats) == set(kline) == set(mapping) and len(stats) == 201
    assert len(exits) == 200 and set(exits) < set(stats)
    kfills = index(read(KLINE / 'per_trade_audit.csv'), 'trade_id')
    mfills = index(read(MAIN / 'all_201_entry_episodes_full_life_408_fills_mapping_audit.csv'), 'trade_id')
    expected = {tid for row in stats.values() for tid in json.loads(row['fill_trade_ids'])}
    assert set(kfills) == set(mfills) == expected and len(expected) == 408
    raw_week_gaps = json.loads((LINE / 'outputs/stage028_root_whole_week_audit.json').read_text())['omissions']
    signal_weeks = read(KLINE / 'signal_week_inputs.csv')
    week_gaps = {tid: [] for tid in stats}
    for gap in raw_week_gaps:
        week_gaps[gap['entry_trade_id']].append(gap)
    def monday(text):
        day = datetime.fromisoformat(text).date()
        return (day - timedelta(days=day.weekday())).isoformat()
    ma_bounds = {}
    for tid in stats:
        ma = [monday(r['week_end']) for r in signal_weeks if r['trade_id'] == tid and int(r['rank_from_signal']) <= 21]
        ma_bounds[tid] = (min(ma), max(ma))
    joined = []
    for tid, row in stats.items():
        k, m = kline[tid], mapping[tid]
        assert row['vt_symbol'] == k['vt_symbol'] == m['vt_symbol']
        assert row['episode_id'] == m['episode_id']
        assert row['exit_date'] == m['exit_date']
        assert row['entry_signal_date'] == k['signal_date'] == m['entry_signal_date']
        assert row['entry_date'] == k['fill_trading_date'] == m['entry_date']
        assert row['last_exit_trade_id'] == k['exit_trade_id']
        assert set(json.loads(row['exit_trade_ids'])) == set(json.loads(k['exit_trade_ids']))
        assert set(json.loads(row['fill_trade_ids'])) == set(json.loads(m['fill_trade_ids']))
        assert row['closed_complete'] == 'True'
        r = {
            'episode_id': row['episode_id'], 'entry_trade_id': tid,
            'vt_symbol': row['vt_symbol'], 'product': row['product'],
            'direction': row['direction'], 'entry_signal_date': row['entry_signal_date'],
            'entry_date': row['entry_date'], 'exit_date': row['exit_date'],
            'entry_price': row['weighted_average_entry_price'],
            'exit_price': row['weighted_average_exit_price'],
            'opened_quantity': row['opened_quantity'], 'net_pnl': row['net_pnl'],
            'closed_by_2020_12_31': str(tid in exits),
            'entry_order_id': row['first_entry_order_id'],
            'exit_trade_ids': row['exit_trade_ids'], 'fill_trade_ids': row['fill_trade_ids'],
            'fill_count': row['fill_count'], 'exit_fill_count': row['exit_fill_count'],
            'price_verdict': k['price_verdict'], 'volume_verdict': k['volume_verdict'],
            'close_oi_verdict': k['close_oi_verdict'], 'kline_verdict': k['kline_verdict'],
            'main_evidence_verdict': m['entry_main_evidence_verdict'],
            'PIT_proven': m['PIT_proven'],
            'root_positive_whole_week_gaps': len(week_gaps[tid]),
            'root_ma21_positive_whole_week_gaps': sum(ma_bounds[tid][0] <= gap['week_monday'] <= ma_bounds[tid][1] for gap in week_gaps[tid]),
            'root_week_series_definition': 'INTENTIONALLY_NONCONSECUTIVE_ACCEPTED_WEEKS' if week_gaps[tid] else 'NO_RQ_POSITIVE_WHOLE_WEEK_GAP_FOUND_IN_CHECKED_RANGE',
        }
        # Retain all author-owned evidence rather than infer agreement from counts.
        r.update({'stats_' + key: val for key, val in row.items()})
        r.update({'kline_' + key: val for key, val in k.items()})
        r.update({'mapping_' + key: val for key, val in m.items()})
        joined.append(r)
    joined.sort(key=lambda r: int(r['episode_id'][2:]))
    assert sum(float(r['net_pnl']) for r in joined) == 279565
    assert sum(r['root_positive_whole_week_gaps'] > 0 for r in joined) == 13
    assert sum(r['root_ma21_positive_whole_week_gaps'] > 0 for r in joined) == 4
    assert sum(r['root_positive_whole_week_gaps'] for r in joined) == 34
    assert sum(r['root_ma21_positive_whole_week_gaps'] for r in joined) == 9
    assert sum(float(r['net_pnl']) for r in joined if r['closed_by_2020_12_31'] == 'True') == 283415
    after = {str(p): digest(p) for p in source_files}
    assert before == after
    OUT.mkdir(parents=True)
    master = OUT / 'all_201_episode_combined_review.csv'
    with master.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(joined[0]))
        writer.writeheader()
        writer.writerows(joined)
    lines = [
        '# 2015—2020逐笔交易与行情审计索引', '',
        '- 区间包含2020全年，按交易日划分。表中201轮为区间内入场、追踪到最终退出；其中200轮在2020年底前平完。NE0201铜在2021-01-04退出，故此表净利279,565与退出窗283,415不同。',
        '- 一轮=同一真实合约库存从0到有仓再归零；分批平仓合并，换月的新旧合约分轮。开、平价格为该轮成交数量加权价。零手续费与固定滑点沿用冻结回测。',
        '- 周序列按原合同只接受所有全市场交易日都有正量日K的周，并非连续自然周。13轮的已用存储周之间有33个不同合约周（34轮次周）存在RQ正量记录而整周未用；其中4轮MA21时间范围内合计9个跳周。下表最后一列=全部存储范围跳周数（其中MA21范围数）；零只表示已查RQ范围未发现。',
        '- 价/量/OI按该轮全部已审依赖日键给最保守分项结论。独立一致不等于PIT或真实成交证明；任何可信来源冲突、第二来源不足均保留。全部主力历史的当时可得性仍未证明。',
        f'- [完整逐笔CSV]({master})保留全部统计、K线、主力证据列；[K线分审]({LINE / "stages/stage028_kline_source_review.md"})、[主力分审]({LINE / "stages/stage028_mapping_independent_review.md"})、[统计分审]({LINE / "stages/stage028_stats_review.md"})提供定义及原始数据定位。', '',
        '| 周期/入场成交 | 合约/方向 | 信号日→开仓交易日 | 平仓交易日 | 开→平价格 | 手数 | 净利 | 价 / 量 / OI | 主力独立比对 | 跳周数（MA21） |',
        '|---|---|---|---|---:|---:|---:|---|---|---:|',
    ]
    for r in joined:
        direction = '多' if r['direction'] == 'long' else '空'
        lines.append('| ' + ' | '.join([
            r['episode_id'] + ' / ' + r['entry_trade_id'].split('.')[-1],
            r['vt_symbol'] + ' / ' + direction,
            r['entry_signal_date'] + ' → ' + r['entry_date'], r['exit_date'],
            number(r['entry_price']) + ' → ' + number(r['exit_price']),
            number(r['opened_quantity']), number(r['net_pnl']),
            ' / '.join(label(r[f]) for f in ['price_verdict', 'volume_verdict', 'close_oi_verdict']),
            {'REAL_LIFECYCLE_AND_INDEPENDENT_RQ88_AGREEMENT': '与RQ一致，PIT未证', 'REAL_LIFECYCLE_VENDOR_MAIN_DIFFERENCE_NOT_PROVEN_ERROR': '与RQ不同，谁错未证'}.get(r['main_evidence_verdict'], r['main_evidence_verdict']),
            str(r['root_positive_whole_week_gaps']) + '（' + str(r['root_ma21_positive_whole_week_gaps']) + '）',
        ]) + ' |')
    ART.parent.mkdir(parents=True, exist_ok=True)
    ART.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    manifest = {
        'schema': 'stage028_combined_audit_v1',
        'generated_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'financial_replays': 0, 'new_downloads': 0, 'data_or_strategy_mutations': 0,
        'episodes_entry_cohort': 201, 'closed_in_window_episodes': 200,
        'fills_full_cohort': 408, 'fills_in_window': 407,
        'nonconsecutive_week_entries': 13, 'nonconsecutive_ma21_entries': 4,
        'positive_whole_week_gaps_owner_count': 34, 'positive_whole_week_gaps_unique_count': 33,
        'positive_whole_week_gaps_in_ma21_span_owner_count': 9,
        'entry_cohort_eventual_net_pnl': 279565, 'closed_in_window_net_pnl': 283415,
        'source_files_sha256': before,
        'output_files_sha256': {str(p): digest(p) for p in [master, ART]},
        'join_assertions': 'unique entry trade; all201 same keys/symbols/exits; 408 exact fill union across all three audits; 200 exit-window subset; net PnL conserved; source SHA unchanged',
        'scope_limit': 'Observed dependencies of actual201 entries only. Rejected and unfilled candidate paths and counterfactual performance are not independently re-evaluated. PIT is not proven.',
        'promotion_verdict': 'NO_PROMOTION',
    }
    (OUT / 'join_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: manifest[k] for k in ['episodes_entry_cohort', 'closed_in_window_episodes', 'fills_full_cohort', 'fills_in_window', 'promotion_verdict']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
