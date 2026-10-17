"""Stage253: describe frozen monthly memberships without fitting or replaying trades."""
import csv
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage253_ai_forensics/pool_membership'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    parameters = ROOT / 'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/A_final3/effective_parameters.json'
    overrides = json.loads(parameters.read_text())['spec']['overrides']
    source = Path(overrides['ai_product_pool_eligibility_path'])
    payload = source.read_bytes()
    rows = [r for r in csv.DictReader(payload.decode('utf-8-sig').splitlines()) if r['strategy'] == overrides['ai_product_pool_strategy']]
    groups = defaultdict(list)
    for row in rows:
        groups[row['eval_date']].append(row)
    dates = sorted(d for d in groups if d >= '2022-01-28')
    static = {r['product_vt_symbol'] for r in groups['2019-12-31']}
    assert len(static) == 18 and 'fu.SHFE' not in static
    counts = Counter()
    by_year = defaultdict(Counter)
    ranks = defaultdict(list)
    transitions = []
    previous = None
    for date in dates:
        snapshot = groups[date]
        selected = {r['product_vt_symbol'] for r in snapshot if r['product_vt_symbol'] != 'fu.SHFE'}
        assert len(snapshot) == 11 and len(selected) == 10 and selected <= static
        assert sorted(int(r['score_rank']) for r in snapshot) == list(range(1, 12))
        counts.update(selected)
        by_year[date[:4]].update(selected)
        for row in snapshot:
            if row['product_vt_symbol'] != 'fu.SHFE':
                ranks[row['product_vt_symbol']].append(int(row['score_rank']))
        if previous is not None:
            transitions.append({'eval_date':date,'new_entries':len(selected-previous),
                                'retained':len(selected&previous),'jaccard':len(selected&previous)/len(selected|previous),
                                'added':','.join(sorted(selected-previous)), 'removed':','.join(sorted(previous-selected))})
        previous=selected
    product_rows = [{'product':p,'selected_months':counts[p],'available_snapshot_count':len(dates),
                     'selection_fraction':counts[p]/len(dates),
                     'mean_rank_when_selected':statistics.mean(ranks[p]) if ranks[p] else None,
                     **{f'selected_{year}':counter[p] for year,counter in sorted(by_year.items())}}
                    for p in sorted(static,key=lambda p:(-counts[p],p))]
    for name,records in [('product_selection_frequency',product_rows),('monthly_turnover',transitions)]:
        with (OUT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    summary={'source':str(source),'source_sha256':hashlib.sha256(payload).hexdigest(),
             'snapshot_count':len(dates),'first_eval_date':dates[0],'last_eval_date':dates[-1],
             'static18':sorted(static),'forced_fu_months':len(dates),
             'selected_non_fu_per_month':10,'transition_count':len(transitions),
             'mean_new_products_per_month':statistics.mean(r['new_entries'] for r in transitions),
             'median_new_products_per_month':statistics.median(r['new_entries'] for r in transitions),
             'min_new_products_per_month':min(r['new_entries'] for r in transitions),
             'max_new_products_per_month':max(r['new_entries'] for r in transitions),
             'mean_jaccard':statistics.mean(r['jaccard'] for r in transitions),
             'product_frequency':product_rows,
             'interpretation':'Descriptive membership only. Not prediction accuracy, causal timing value, or a backtest of an alternative fixed pool. Calendar counts do not adjust for product listing dates.'}
    assert source.read_bytes()==payload
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    report=['# 冻结月池成员描述','',f'共{len(dates)}个模型月池，非fu每月10品种，fu为固定加入。相邻月平均更换{summary["mean_new_products_per_month"]:.2f}个品种，中位{summary["median_new_products_per_month"]:.1f}个。',
            '', '|品种|入选月数|占57个月比例|入选时平均排名|','|---|---:|---:|---:|']
    for row in product_rows:
        rank=f'{row["mean_rank_when_selected"]:.2f}' if row['mean_rank_when_selected'] is not None else '无'
        report.append(f'|{row["product"]}|{row["selected_months"]}|{row["selection_fraction"]:.1%}|{rank}|')
    report.extend(['','这些只是成员频率，不是准确率。入选频繁既可能反映稳定特性，也可能是长期品种暴露；尚无同宽固定池/随机池独立账户对照，不能据此证明动态AI时机有效。fu不是模型赢家，不能按其人工rank11/score纳入评分效果检验。'])
    (OUT/'report.md').write_text('\n'.join(report)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['static18','product_frequency']},ensure_ascii=False))

if __name__=='__main__':
    main()
