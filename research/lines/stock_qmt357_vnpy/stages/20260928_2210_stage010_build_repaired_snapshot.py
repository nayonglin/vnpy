"""Frozen Stage010 data experiment. No strategy execution or network access."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from examples.stock_backtesting.qmt357_commit4ac255e.repairs import apply_repairs
from examples.stock_backtesting.qmt357_commit4ac255e.data import prepare_snapshot
from examples.stock_backtesting.qmt357.history_download import audit_factor_gaps

VARIANT = REPO / 'examples/stock_backtesting/qmt357_commit4ac255e'
SOURCE = REPO / 'examples/stock_backtesting/qmt357/data/downloads/history_20191001_20260928'
EVIDENCE = VARIANT / 'data/factor_crosscheck'
STAGES = Path(__file__).parent
TARGET = VARIANT / 'data/repairs/stage010_repaired_v1'
SOURCE_SHA = 'fa1422b5e64016b61e3804bf3ccdffc2c4feb957f2ef94d892964ef75634377f'
SNAPSHOT = 'history_201910_20260928_repaired_v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def main():
    if TARGET.exists():
        raise FileExistsError('Never overwrite a data repair experiment')
    assert sha(SOURCE / 'source_panel.parquet') == SOURCE_SHA
    original = pd.read_parquet(SOURCE / 'source_panel.parquet')
    evidence = {}
    market = []
    for directory in sorted(EVIDENCE.glob('tencent_history_*')):
        receipt = directory / 'request_manifest.json'
        info = json.loads(receipt.read_text())
        evidence[str(receipt.relative_to(REPO))] = sha(receipt)
        for row in info['rows']:
            path = directory / row['file']
            assert sha(path) == row['sha256'], path
            evidence[str(path.relative_to(REPO))] = sha(path)
            payload = json.JSONDecoder().raw_decode(path.read_text().split('=',1)[1])[0]
            symbol, _, _, _, _, adjust = row['param'].split(',')
            assert payload['code'] == 0
            bars = payload['data'][symbol][('day' if not adjust else adjust+'day')]
            assert len(bars) == 640
            market.append(dict(symbol=symbol, adjust=adjust, file=str(path.relative_to(REPO)),
                closes={r[0]: float(r[2]) for r in bars}))

    audit_path = SOURCE / 'final_factor_audit.json'
    audit = json.loads(audit_path.read_text())
    evidence[str(audit_path.relative_to(REPO))] = sha(audit_path)
    pattern = STAGES / '20260928_2127_stage010_factor_pattern_audit_event_checks.parquet'
    events = pd.read_parquet(pattern)
    evidence[str(pattern.relative_to(REPO))] = sha(pattern)
    operations, crosschecks = [], []
    for event in audit['rows']:
        if event['diagnostic_classification'] != 'back_only_discontinuity_provider_anomaly_suspected':
            continue
        vt, date, prev = event['vt_symbol'], event['date'], event['previous_bar_date']
        if vt == '302132.SZSE':
            continue  # Documented code identity bridge, not a generic reset.
        assert event['previous_fore_factor'] == event['current_fore_factor']
        assert event['previous_close'] == event['current_preclose']
        assert event['cash_dividend'] == 0 and event['split_ratio'] == 1
        symbol = ('sh' if vt.endswith('.SSE') else 'sz') + vt[:6]
        selected = {}
        for adjust in ['', 'qfq', 'hfq']:
            candidates = [m for m in market if m['symbol'] == symbol and m['adjust'] == adjust
                          and date in m['closes'] and prev in m['closes']]
            assert candidates, (vt, date, adjust)
            selected[adjust] = candidates[0]
        raw, qfq = selected['']['closes'], selected['qfq']['closes']
        assert abs(raw[prev] - event['previous_close']) < 1e-9
        assert abs(raw[date] - event['close']) < 1e-9
        # Tencent's cent-rounded additive-adjusted price offset is unchanged.
        # This is an independent no-event price check, not its inferred factor.
        residual = (raw[date]-qfq[date]) - (raw[prev]-qfq[prev])
        assert abs(residual) < .010000001, (vt, date, residual)
        operations.append(dict(kind='factor_step', vt_symbol=vt, date=date,
            previous_factor=event['previous_factor'], current_factor=event['adj_factor'], desired_ratio=1.,
            reason='Both raw reference and fore factor show no event; independent Tencent raw/qfq offset unchanged; remove isolated back scale reset.',
            evidence=[m['file'] for m in selected.values()]))
        crosschecks.append(dict(vt_symbol=vt, date=date, raw_previous=raw[prev], raw_current=raw[date],
            qfq_previous=qfq[prev],qfq_current=qfq[date], offset_change=residual))
    assert len(operations) == 8

    event = events.loc[events.vt_symbol.eq('600837.SSE') & events.date.eq('2020-11-27')].iloc[0]
    assert event.cash_dividend == .28 and event.split_ratio == 1
    assert abs(event.previous_close - .28 - event.preclose) < 1e-9
    operations.append(dict(kind='factor_step', vt_symbol='600837.SSE', date='2020-11-27',
        previous_factor=float(event.back_previous), current_factor=float(event.back_current),
        desired_ratio=13.55/13.27, reason='Retain issuer-confirmed cash .28; remove additional back scale reset, using raw ex-reference ratio.',
        evidence=['https://epaper.cs.com.cn/zgzqb/html/2020-11/19/nw.D110000zgzqb_20201119_7-B017.htm',
                  'tencent_history_600837_002466/request_manifest.json']))
    event = next(e for e in audit['rows'] if e['vt_symbol'] == '002466.SZSE')
    operations.append(dict(kind='factor_move', vt_symbol='002466.SZSE', date='2020-01-02',
        actual_date='2019-12-26',previous_factor=event['previous_factor'],current_factor=event['adj_factor'],
        reason='Exchange-confirmed rights ex-date; move factor only, no free shares/cash; held rights event remains unsupported.',
        evidence=['https://docs.static.szse.cn/www/market/periodical/month/W020200121333627890099.html']))

    legacy = EVIDENCE / 'legacy_300114/factors.parquet'
    receipt = EVIDENCE / 'legacy_300114/receipt.json'
    assert sha(legacy) == json.loads(receipt.read_text())['sha256']
    for path in [legacy,receipt]:
        evidence[str(path.relative_to(REPO))] = sha(path)
    factors = pd.read_parquet(legacy)
    assert factors.code.eq('sz.300114').all()
    old_rows = original.loc[original.vt_symbol.eq('302132.SZSE') & original.date.lt('2025-02-17')]
    assert not old_rows.is_member.any()  # No pre-change new-code selection.
    operations.append(dict(kind='factor_prefix',vt_symbol='302132.SZSE',before='2025-02-18',
        expected_old=1.,bridge_factor=5.975678,
        factors=[[r.dividOperateDate,float(r.backAdjustFactor)] for r in factors.itertuples()],
        reason='Issuer-confirmed 300114→302132 identity continuity; restore legacy past factors, no share-count change.',
        evidence=[str(legacy.relative_to(REPO)),
            'https://disc.static.szse.cn/download/disc/disk03/finalpage/2025-02-15/cedb693a-f5ee-4463-9682-ea33d406b569.PDF']))

    action_file = STAGES / '20260928_2210_stage010_action_corrections.json'
    action_spec = json.loads(action_file.read_text())  # Required separately researched issuer-backed values.
    evidence[str(action_file.relative_to(REPO))] = sha(action_file)
    operations.extend(action_spec['operations'])
    unsupported = [dict(vt_symbol=d['vt_symbol'],date=d['date'],reason=d['reason'],evidence=d['evidence'])
                   for d in action_spec['decisions'] if d['decision'].startswith('unsupported_')]
    assert [(d['vt_symbol'],d['date']) for d in unsupported] == [('600515.SSE','2021-12-22')]
    corrected, changes = apply_repairs(original, operations)
    untouched = [c for c in original.columns if c not in ['adj_factor','cash_dividend','split_ratio']]
    pd.testing.assert_frame_equal(corrected[untouched], original[untouched])
    assert len(original) == 692961 and len(corrected) == len(original)
    specification = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),source_sha256=SOURCE_SHA,
        operations=operations,evidence_sha256=evidence,source_builder_sha256=sha(Path(__file__)),
        repair_code_sha256=sha(VARIANT/'repairs.py'), rule_selection='Data identities fixed before replay; no profit-based selection',
        rights_policy='No investor shares/cash inferred; unexplained held changes still fail',
        issuer_action_decisions=action_spec.get('decisions',[]))
    TARGET.mkdir(parents=True,exist_ok=False)
    write_json(TARGET/'repair_specification.json',specification)
    write_json(TARGET/'crosschecks.json',crosschecks)
    corrected.attrs = dict(original.attrs,repair_specification_sha256=sha(TARGET/'repair_specification.json'),
        repair_specification_path=str(TARGET/'repair_specification.json'),
        factor_repair_scope='8 back-only resets + 600837 cash-date reset + 002466 delayed rights date + 302132 legacy identity bridge',
        source_parent_sha256=SOURCE_SHA,
        unsupported_corporate_actions=unsupported,
        security_identity_bridge='302132 uses canonical id; before 2025-02-17 prices and factors belong to 300114; historical is_member remains false',
        data_limitations=list(original.attrs['data_limitations'])+['Only enumerated source anomalies repaired; remaining rights/reorganization events not economically modeled; differentiated reference prices need not equal individual cash entitlement'])
    corrected.to_parquet(TARGET/'source_panel.parquet',index=False)
    pd.DataFrame(changes).to_parquet(TARGET/'field_changes.parquet',index=False)
    gaps = audit_factor_gaps(corrected)
    gaps.to_parquet(TARGET/'remaining_factor_gaps.parquet',index=False)
    snapshot = prepare_snapshot(TARGET/'source_panel.parquet', SNAPSHOT)
    result = dict(source_sha256=sha(TARGET/'source_panel.parquet'),snapshot=str(snapshot),
        snapshot_sha256=sha(snapshot/'panel.parquet'),rows=len(corrected),operations=len(operations),
        changed_fields=len(changes),changes_by_field=pd.DataFrame(changes).field.value_counts().to_dict(),
        remaining_factor_gaps=len(gaps),original_source_unchanged=sha(SOURCE/'source_panel.parquet')==SOURCE_SHA)
    write_json(TARGET/'build_result.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
