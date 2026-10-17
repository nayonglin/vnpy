"""Four-session, offline review of the exact Stage016 research correction."""
from __future__ import annotations
import csv
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[5]
LINE = ROOT / 'research/lines/futures_trend_triple_screen'
OUT = Path(__file__).resolve().parent
SOURCE = LINE / 'outputs/stage016_source859_qualification'
FIELDS = ('open', 'high', 'low', 'close', 'volume', 'open_oi', 'close_oi')
EXPECTED_SUMMARY = '0db3b3fbe4696b8bcc867460e1e81800f51a2f68e652bb5621e10bccaeb8cabd'
R018 = LINE / 'outputs/stage018_independent_review/review_receipt.json'
R018_SHA = 'b7820471cc7d84963251182b8d10cf26e82cfc009a45e70ac9a7184ab39cd0cf'
EXPECTED_COUNTS = {('cu2010.SHFE', '2020-08-27'): (284, 283, 181),
                   ('fu2205.SHFE', '2022-03-30'): (225, 225, 0),
                   ('AP210.CZCE', '2022-04-06'): (225, 225, 0),
                   ('cu2507.SHFE', '2025-06-11'): (1, 1, 284)}


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def read(path): return json.loads(Path(path).read_text())


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def stamp(value):
    value = datetime.fromisoformat(str(value))
    assert value.tzinfo is None and value.second == value.microsecond == 0
    return value


def vals(row, prefix=''): return {name: Decimal(str(row[prefix + name])) for name in FIELDS}


def grid_for(symbol, day):
    day = datetime.fromisoformat(day)
    grid = []
    if not symbol.startswith('AP'):
        length = 120 if symbol.startswith('fu') else 240
        start = day - timedelta(days=1) + timedelta(hours=21)
        grid.extend(start + timedelta(minutes=i) for i in range(length))
    for hours, minutes, length in ((9, 0, 75), (10, 30, 60), (13, 30, 90)):
        start = day + timedelta(hours=hours, minutes=minutes)
        grid.extend(start + timedelta(minutes=i) for i in range(length))
    return grid


def aggregate(data):
    return dict(zip(FIELDS, (data[0]['open'], max(x['high'] for x in data),
                            min(x['low'] for x in data), data[-1]['close'],
                            sum((x['volume'] for x in data), Decimal(0)),
                            data[0]['open_oi'], data[-1]['close_oi'])))


def main():
    receipt_path = OUT / 'review_receipt.json'
    assert not receipt_path.exists(), 'existing review receipt must remain frozen'
    assert sha(SOURCE / 'summary.json') == EXPECTED_SUMMARY
    summary = read(SOURCE / 'summary.json')
    inputs = read(SOURCE / 'input_manifest.json')
    assert len(inputs) == 65
    for path, digest in inputs.items(): assert sha(path) == digest, path
    for name, digest in summary['artifact_sha256'].items(): assert sha(SOURCE / name) == digest, name
    assert summary['all_inputs_unchanged'] is True
    assert sha(R018) == summary['stage018_independent_review_sha256'] == R018_SHA
    reviewed018 = read(R018)
    assert reviewed018['qualified_research_data'] and reviewed018['required_AP210_accepted']
    assert reviewed018['qualified_precise_sessions'] == 39 and reviewed018['AP210_qualified_minutes'] == 225
    assert reviewed018['p0_findings'] == reviewed018['p1_findings'] == 0
    for path, digest in reviewed018['source_fingerprints'].items(): assert inputs[path] == digest
    sessions = read(SOURCE / 'session_qualification.json')
    bysession = {(x['vt_symbol'], x['trading_date']): x for x in sessions}
    assert len(bysession) == len(sessions) == summary['qualified_full_sessions'] == 4
    assert set(bysession) == set(EXPECTED_COUNTS)
    allowed = {}; grids = {}; reference = {}; session_checks = []
    for key, session in bysession.items():
        symbol, day = key; grid = grid_for(*key); grids[key] = grid
        assert grid == [stamp(x) for x in session['expected_timestamps']]
        assert len(grid) == session['expected_minutes']
        assert inputs[session['reference_source_path']] == session['reference_source_sha256']
        assert inputs[session['daily_source_path']] == session['daily_source_sha256']
        selected = {}
        for row in rows(session['reference_source_path']):
            moment = stamp(row['bar_datetime'])
            if row['vt_symbol'] != symbol or moment not in set(grid): continue
            assert moment not in selected
            values = vals(row)
            assert all(value.is_finite() for value in values.values())
            assert min(values[name] for name in ('open','high','low','close')) > 0
            assert values['low'] <= min(values['open'], values['close']) <= max(values['open'], values['close']) <= values['high']
            assert min(values[name] for name in ('volume','open_oi','close_oi')) >= 0
            selected[moment] = values
        assert set(selected) == set(grid)
        daily = [x for x in rows(session['daily_source_path']) if x['trade_date'][:10] == day]
        assert len(daily) == 1
        computed = aggregate([selected[moment] for moment in grid])
        assert computed == vals(daily[0])
        for moment in grid:
            full_key = symbol, moment
            assert full_key not in allowed
            allowed[full_key] = key; reference[full_key] = selected[moment]
        session_checks.append(dict(vt_symbol=symbol, trading_date=day, complete_rows=len(grid),
            seven_csv_fields_exact=True, aggregate={name:str(value) for name,value in computed.items()}))
    assert len(allowed) == 1500
    # The second named fu completed source is a literal byte duplicate, not an
    # alternative set of prices silently selected against the first source.
    sources011 = read(LINE / 'outputs/stage011_needed_local_completed/source_manifest.json')
    alt = [x for x in sources011['sources'] if x['source_id'] == 'local_0528']
    assert len(alt) == 1 and alt[0]['status'] == 'accepted_source_bytes'
    fu_reference = bysession['fu2205.SHFE','2022-03-30']['reference_source_sha256']
    assert sha(alt[0]['path']) == alt[0]['sha256'] == fu_reference

    # Select just the four real grids from immutable old files. No old full
    # price qualification or account reconstruction is performed.
    old_values = {}; old_sources = {}; old_origins = {}
    pattern = '^(' + '|'.join(re.escape(symbol) for symbol,_ in bysession) + '),'
    for item in summary['existing_sources']:
        path = Path(item['path'])
        assert inputs[str(path)] == item['sha256']
        with path.open(encoding='utf-8-sig') as stream: columns = next(csv.reader(stream))
        result = subprocess.run(['rg', '-e', pattern, str(path)], capture_output=True, text=True)
        assert result.returncode in (0,1)
        for row in csv.DictReader(io.StringIO(result.stdout), fieldnames=columns):
            key = row['vt_symbol'], stamp(row['bar_datetime'])
            if key not in allowed: continue
            assert key not in old_values
            old_values[key] = vals(row)
            old_sources[key] = row.get('minute_source', 'previously_qualified_overlay')
            old_origins[key] = str(path)
    assert len(old_values) == 1035
    base = summary['existing_sources'][0]['path']
    assert sha(base) == summary['original_base_sha256'] == '5c06124fac52ff37a19d1abe89f6f6a80d36b8ece874eb647286377317289189'
    correction_rows = rows(SOURCE / 'corrections.csv'); append_rows = rows(SOURCE / 'append_only.csv')
    corrections = {}; appended = {}; field_diffs = Counter()
    for row in correction_rows:
        key = row['vt_symbol'], stamp(row['bar_datetime'])
        assert key in old_values and key not in corrections
        assert old_origins[key] == base and old_sources[key] == row['old_source'] == 'stage859_tqsdk_backtest'
        assert vals(row, 'old_') == old_values[key]
        updated = vals(row, 'new_')
        assert updated == reference[key] and updated != old_values[key]
        assert updated['open'] == old_values[key]['open'] and updated['open_oi'] == old_values[key]['open_oi']
        assert row['reference_source_id'] == bysession[allowed[key]]['reference_source_id']
        assert row['reference_source_sha256'] == bysession[allowed[key]]['reference_source_sha256']
        field_diffs.update(name for name in FIELDS if updated[name] != old_values[key][name])
        corrections[key] = updated
    for row in append_rows:
        key = row['vt_symbol'], stamp(row['bar_datetime'])
        assert key in allowed and key not in old_values and key not in appended and key not in corrections
        assert vals(row) == reference[key]
        assert row['minute_source'] == 'stage016_reviewed_completed_append'
        assert row['reference_source_id'] == bysession[allowed[key]]['reference_source_id']
        assert row['reference_source_sha256'] == bysession[allowed[key]]['reference_source_sha256']
        appended[key] = vals(row)
    assert len(corrections) == summary['actual_replacement_keys'] == 734
    assert len(appended) == summary['append_only_keys'] == 465
    changed = set(corrections) | set(appended)
    assert len(changed) == 1199 and not set(corrections) & set(appended)
    corrected = {**old_values, **corrections, **appended}
    assert corrected == reference and set(corrected) == set(allowed)
    unchanged859 = [key for key in old_values if old_sources[key] == 'stage859_tqsdk_backtest' and key not in corrections]
    non859 = [key for key in old_values if old_sources[key] != 'stage859_tqsdk_backtest']
    assert len(unchanged859) == 1 and len(non859) == 300
    assert all(corrected[key] == old_values[key] for key in non859 + unchanged859)
    for key, (scope, replacements, additions) in EXPECTED_COUNTS.items():
        old859 = sum(allowed[k] == key and old_sources[k] == 'stage859_tqsdk_backtest' for k in old_values)
        assert old859 == scope == bysession[key]['source859_scope_keys']
        assert sum(allowed[k] == key for k in corrections) == replacements == bysession[key]['actual_corrections']
        assert sum(allowed[k] == key for k in appended) == additions == bysession[key]['append_only_minutes']

    sys.path.insert(0, str(LINE / 'tools'))
    import stage016_source859_qualification as module
    h = module.old; pd = h.pd
    calendar = pd.DatetimeIndex(sorted({row['date'] for row in rows(h.MAPPING)}))
    anchors = rows(h.A0 / 'execution_anchor_requests.csv'); scans = rows(h.A0 / 'minute_scan_requests.csv')
    used = {(row['vt_symbol'], stamp(row['expected_start'])) for row in anchors}
    for row in scans:
        requested = [t.to_pydatetime() for t in h.session_grid(row['vt_symbol'], row['trading_date'], calendar)
                     if t >= h.local_timestamp(row['requested_start'])]
        assert len(requested) == int(row['expected_bar_count'])
        used.update((row['vt_symbol'], moment) for moment in requested)
    assert (len(anchors),len(scans),len(used)) == (535,501,106731)
    assert not changed & used
    assert summary['a0_path_equivalence']['changed_keys'] == 1199
    assert summary['a0_path_equivalence']['intersection_count'] == 0 and summary['a0_path_equivalence']['path_equivalent']
    before = rows(LINE / 'outputs/stage015_daily_recovered_minute_delta/demand_readiness.csv')
    after = rows(SOURCE / 'demand_readiness.csv')
    before = {(x['vt_symbol'],x['execution_trade_date']):x for x in before}
    after = {(x['vt_symbol'],x['execution_trade_date']):x for x in after}
    assert before.keys() == after.keys() and len(before) == 28268
    for key, row in after.items():
        if key not in bysession:
            assert all(row[name] == value for name,value in before[key].items())
            assert row['stage016_affected_full'] == 'False'
            assert row['stage016_price_qualification'] == 'inherited_outside_this_review_scope'
            assert row['stage016_physical_missing_after'] == row['stage016_anchor_present_after'] == ''
        else:
            assert row['requirement_kind'] == 'full_session' and row['stage016_affected_full'] == 'True'
            assert row['stage016_price_qualification'] == 'completed_reference_qualified'
            assert row['stage016_physical_missing_after'] == '0' and row['stage016_anchor_present_after'] == 'True'
            assert row['ready_after'] == 'True'
    assert sum(x['ready_after']=='True' for x in before.values()) == 20191
    assert sum(x['ready_after']=='True' for x in after.values()) == 20193

    # One pure fake applies the real four-session delta and deliberately raises
    # inside the context, checking both transformation and finally restoration.
    existing_frame = pd.DataFrame([dict(vt_symbol=symbol,bar_datetime=moment,
        minute_source=old_sources[symbol,moment],**{k:float(v)for k,v in values.items()})
        for (symbol,moment),values in old_values.items()])
    existing_frame['bar_date'] = pd.to_datetime(existing_frame.bar_datetime).dt.normalize()
    corrections_frame = module.normal(pd.read_csv(SOURCE/'corrections.csv'))
    append_frame = module.normal(pd.read_csv(SOURCE/'append_only.csv'))
    qualified = module.QualifiedDelta(corrections_frame,append_frame,
        {(symbol,pd.Timestamp(moment))for symbol,moment in allowed},True,True)
    def original_loader(symbols): return existing_frame.loc[existing_frame.vt_symbol.isin(symbols)].copy()
    sentinels = [object(),object(),object()]
    names = ('_FULL_MINUTE_BY_SYMBOL_CACHE','_FULL_MINUTE_BY_SYMBOL_CACHE_SYMBOLS','_LAST_MINUTE_AUDIT')
    fake = SimpleNamespace(_load_stage861_full_minute_bars=original_loader,**dict(zip(names,sentinels)))
    class DeliberateAbort(Exception): pass
    try:
        with module.temporary_qualified_minute_delta(fake,qualified):
            applied = fake._load_stage861_full_minute_bars(sorted({x[0]for x in allowed}))
            assert len(applied) == 1500 and applied.bar_date.notna().all()
            assert (applied.bar_date == applied.bar_datetime.dt.normalize()).all()
            actual = {(row.vt_symbol,row.bar_datetime.to_pydatetime()):vals(row._asdict())for row in applied.itertuples(index=False)}
            assert actual == reference
            for name in names: setattr(fake,name,object())
            raise DeliberateAbort()
    except DeliberateAbort: pass
    assert fake._load_stage861_full_minute_bars is original_loader
    assert all(getattr(fake,name)is sentinel for name,sentinel in zip(names,sentinels))

    fingerprints = dict(inputs)
    fingerprints[alt[0]['path']] = alt[0]['sha256']
    for path in SOURCE.iterdir():
        if path.is_file(): fingerprints[str(path)] = sha(path)
    checks = dict(reviewed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        status='four_precise_sessions_and_actual_delta_review_pass',p0_findings=0,p1_findings=0,
        qualified_research_source859_delta=True,source_summary_sha256=EXPECTED_SUMMARY,
        original_input_hashes_checked=65,input_bytes_hashed=sum(Path(p).stat().st_size for p in inputs),
        old_full_price_audit_repeated=False,precise_session_checks=session_checks,
        full_reference_minutes=1500,source859_scope_keys=735,actual_replacements=734,append_only_minutes=465,
        unchanged_source859_keys=1,non859_unchanged_keys=300,deleted_keys=0,
        replaced_field_difference_counts=dict(field_diffs),open_or_openOI_changes=0,
        all_changed_keys=1199,A0_anchor_requests=535,A0_scan_requests=501,A0_actual_read_keys=106731,
        changed_key_intersection_A0_reads=0,unchanged_scope_keys_intersect_A0_reads=len((set(old_values)-set(corrections))&used),
        original_loader_and_three_cache_objects_restored_after_fake_exception=True,
        real_delta_applied_to_pure_fake_complete_grid=True,appended_bar_dates_present=True,
        independent_consumer_qualification_and_summary_binding_checked=True,
        stage018_actual_receipt_sha256=R018_SHA,stage018_failed_017_identity_reused=False,
        unchanged_readiness_outside_four_sessions=28264,
        inherited_physical_ready_before=20191,inherited_physical_ready_after=20193,
        inherited_ready_is_global_price_qualification=False,
        source_fingerprints=fingerprints,financial_replays=0,network_calls=0)
    write(OUT/'delta_checks.json',checks)
    report = '''# Stage016 精确四会话source859增量独立复核

仅审四个固定完整session与1199个实际变更键，无下载、账户或旧全量价格重验。65个原输入约1.006GB只做SHA复核，全部相同；八个构建产物SHA、summary身份和018实际通过receipt均匹配。fu2205另一个具名completed来源local_0528与local_0527为字节相同文件，未发现两个具名来源的价差。

四个独立时段网格及参考完整性均通过，合计1500分钟；每个参考的OHLCV、首openOI、末closeOI用Decimal独立聚合，与原CSV七字段精确一致。cu2010/2020-08-27：283替换+181新增；fu2205/2022-03-30：225替换；AP210/2022-04-06：225替换；cu2507/2025-06-11：1替换+284新增。

734个替换全部逐键对应原base中的source859，七项old值与原字节一致；new值与精确completed参考一致，open/openOI均未变。735个source859范围键中1键本已相同，未制造修正。465个新增与base及002/011/015旧键均无覆盖；完整结果1500键全等参考，无删除。另300个非859旧键全部保值。原FG209及其他范围没有被放行。

按已验A0的535条anchor和501条scan几何重建106731个实际读取键；1199个实际变更键交集为0。该因果证据支持复用原A0，不以全局覆盖数量替代数据真值。继承readiness的其余28264行原字段不变，四行新增价格资格显式标注；20191→20193是物理ready数量，绝非全局价格资格。

消费门显式使用018实际receipt b7820471…39cd0cf，并绑定五项provider资产SHA；不覆盖或借用017失败身份。最终独立receipt钉住016 summary完整SHA。实际delta在一个纯fake loader中应用为完整1500行，append.bar_date齐全；随后故意在上下文内抛异常，原loader和三个缓存对象均按身份恢复。此检查没有创建金融引擎。运行时仍逐键检查旧source/旧七值，独立资格缺失即拒绝。

结论：qualified_research_source859_delta=true，仅授权这四个精确会话的研究增量资格。原base和叠加源均未改，不等于全source859、全剩余路径或C3就绪，不授权生产/日线fallback/新金融attempt。金融累计仍4次尝试、1次完成，C0无alpha结论。

过拟合：否，来源缺陷及固定full需求决定范围，未看PnL或改参数。继续价值：是，四个受影响完整扫描日取得completed价格资格；后续应在各自冻结合同内处理其他缺口，不扩大本receipt的结论。
'''
    (OUT/'independent_review.md').write_text(report)
    receipt = dict(reviewed_at=checks['reviewed_at'],reviewer='first_screen_independent',
        status='limited_stage016_precise_source859_delta_review_pass',p0_findings=0,p1_findings=0,
        qualified_research_source859_delta=True,source_summary_sha256=EXPECTED_SUMMARY,
        qualified_full_sessions=4,qualified_sessions=[dict(vt_symbol=k[0],trading_date=k[1])for k in sorted(bysession)],
        source859_scope_keys=735,actual_replacement_keys=734,append_only_keys=465,actual_changed_keys=1199,
        non859_existing_keys_changed=0,open_or_openOI_changes=0,deleted_keys=0,
        A0_actual_read_keys=106731,changed_key_intersection_A0_reads=0,A0_replay_reuse_for_exact_delta_valid=True,
        all_original_input_hashes_unchanged=True,stage018_independent_review_sha256=R018_SHA,
        original_loader_and_three_caches_restored_after_fake_exception=True,
        inherited_ready_not_global_price_qualification=True,source_fingerprints=fingerprints,
        review_artifact_sha256={name:sha(OUT/name)for name in ('review_delta.py','delta_checks.json','independent_review.md')},
        financial_replays=0,network_calls=0,downloads=0,original_source_writes=0,
        full_source859_globally_qualified=False,C0_attempt3_authorized=False,
        execution_fallback_authorized=False,production_qualified=False,
        financial_attempts_cumulative_unchanged=4,financial_completed_cumulative_unchanged=1,
        C0_alpha_verdict='not_evaluable',overfitting=False,continued_value=True)
    write(receipt_path,receipt)
    try:
        # Exercise the real consumer with the exact just-issued summary/review
        # pins; it rechecks original fingerprints and the two actual delta CSVs.
        consumed = module.read_qualified_delta(SOURCE/'summary.json',EXPECTED_SUMMARY,receipt_path,sha(receipt_path))
        assert consumed.review_accepted and consumed.all_four_sessions_qualified
        assert len(consumed.corrections)==734 and len(consumed.appended)==465 and len(consumed.allowed_keys)==1500
    except BaseException:
        receipt_path.unlink(missing_ok=True)
        raise
    print(json.dumps({key:receipt[key]for key in ('status','qualified_research_source859_delta','qualified_full_sessions','actual_replacement_keys','append_only_keys','changed_key_intersection_A0_reads')},ensure_ascii=False))
    print('review_receipt_sha256='+sha(receipt_path))


if __name__ == '__main__': main()
