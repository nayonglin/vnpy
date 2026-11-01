"""Display-only, identity-bound explanations for the accepted 2026 recap.

No engine, broker, network client or production module is imported. The old
recap and every chart/financial field remain immutable. Evidence is joined
from actual close fill -> order anchor -> matching signal-day diagnostic.
"""
import argparse
import copy
from datetime import datetime
import html
import importlib.util
import json
from pathlib import Path
import re
import shutil
from zoneinfo import ZoneInfo

import pandas as pd

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('stage020_recap', HERE / 'Stage020_ytd_recap.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
LINE = base.LINE
SOURCE = LINE / 'artifacts/stage020_2026_ytd_recap_attempt002'
OUTPUT = LINE / 'artifacts/stage021_2026_exit_reasons'
SOURCE_MANIFEST_SHA = '86e1bdb5de1ac1a773a48ec7fd1b02e05b168cded8c809f67f1b7f55e2994489'
SOURCE_ACCEPTANCE_SHA = 'd0db1b146fcdbe409be4b79b93030880379cb5774848798b0ba38faa8bfcde2e'
FILES = dict(fills='trades.csv', anchors='execution_anchor_requests.csv', events='trade_events.csv',
             weekly='weekly_stop_audit.csv', rollover='rollover_shape_same_volume.csv')


def require_output(path):
    path = Path(path).resolve()
    base.require(path.parent == OUTPUT.parent.resolve() and
                 re.fullmatch(OUTPUT.name + r'(?:_attempt[0-9]{3})?', path.name), 'Only a new Stage021 output is allowed')
    base.require(not path.exists(), 'Preserve every prior output; choose a new attempt')


def read_evidence():
    tables = {key: pd.read_csv(base.RUN / name) for key, name in FILES.items()}
    settings = json.loads((base.RUN / 'actual_strategy_settings.json').read_text())
    base.require(isinstance(settings, list) and len(settings) == 1, 'Unique actual strategy settings required')
    tables['settings'] = settings[0]['setting']
    return tables


def one(frame, label):
    base.require(len(frame) == 1, 'Expected unique ' + label)
    return frame.iloc[0]


def number(value):
    return f'{float(value):,.4f}'.rstrip('0').rstrip('.')


def enrich(records, tables):
    result = copy.deepcopy(records)
    s = tables['settings']
    for record in result:
        m = record['meta']
        fill = one(tables['fills'].loc[tables['fills'].trade_id.eq(m['close_trade_id'])], 'actual close fill')
        base.require(fill.offset == '平' and fill.vt_symbol == m['vt_symbol'] and fill.exit_reason == m['exit_reason'], 'Close fill identity/reason mismatch')
        base.near(fill.price, m['exit_price'], 'Actual close fill price mismatch')
        base.near(fill.volume, m['volume'], 'Actual close fill volume mismatch')
        base.require(str(fill.datetime) == m['exit_execution_datetime'] and str(fill.trading_date) == m['exit_date'], 'Actual close clock mismatch')
        anchor = one(tables['anchors'].loc[tables['anchors'].order_id.eq(fill.order_id)], 'execution anchor')
        base.require(anchor.vt_symbol == fill.vt_symbol and str(anchor.trading_date) == str(fill.trading_date), 'Anchor identity mismatch')
        base.require(pd.Timestamp(anchor.actual_time) == pd.Timestamp(fill.datetime).tz_localize(None), 'Anchor actual clock mismatch')
        base.near(anchor.price, fill.price, 'Anchor close price mismatch')
        event = one(tables['events'].loc[tables['events'].vt_symbol.eq(fill.vt_symbol) &
                    tables['events'].date.eq(str(anchor.signal_date)) & tables['events'].reason.eq(fill.exit_reason)], 'actual exit event')
        base.near(event.volume, fill.volume, 'Signal event close volume mismatch')
        base.require(str(anchor.signal_date) < str(anchor.trading_date), 'Close signal must precede execution trading day')
        code = str(fill.exit_reason)
        x = dict(raw_code=code, fill_id=str(fill.trade_id), order_id=str(fill.order_id),
                 signal_date=str(anchor.signal_date), trading_date=str(fill.trading_date),
                 execution_datetime=str(fill.datetime), execution_price=float(fill.price),
                 planned_price=float(event.price), volume=float(fill.volume),
                 stop_price=None, trigger_close=None, kind=None, label=None, description=None, evidence=None)
        if code in {'long_base_stop', 'short_base_stop', 'long_prev2day_stop', 'short_prev2day_stop'}:
            is_long = code.startswith('long_')
            base.require(is_long == (m['direction'] == 'long'), 'Technical stop direction mismatch')
            audit = one(tables['weekly'].loc[tables['weekly'].vt_symbol.eq(fill.vt_symbol) &
                        tables['weekly'].date.eq(str(anchor.signal_date)) &
                        tables['weekly'].purpose.eq('close_confirmation') & tables['weekly'].triggered.eq(True)], 'weekly stop trigger')
            close, stop = float(audit.weekly_close), float(audit.stop_price)
            base.require(close <= stop if is_long else close >= stop, 'Recorded weekly stop trigger comparison failed')
            base.require(str(audit.week_end) == str(anchor.signal_date), 'Technical exit must be a fresh completed week')
            base.near(event.price, close, 'Technical signal price/weekly close mismatch')
            prev2 = 'prev2day' in code
            label = ('多头' if is_long else '空头') + ('前两周保护止损' if prev2 else '底仓止损')
            description = ('取前两根完整周K的' + ('最低价，保护线只上移' if is_long else '最高价，保护线只下移') + '；本周收盘越过保护线后退出。'
                           if prev2 else '本周收盘越过底仓当时有效的止损线，触发底仓退出；这条线可能已随持仓动态调整。')
            x.update(kind='technical_stop', label=label, description=description, trigger_close=close, stop_price=stop,
                     evidence=f'{audit.week_end} 周收盘 {number(close)} {"≤" if is_long else "≥"} 当时止损线 {number(stop)}。' +
                     ('原代码 prev2day 沿用旧名称，本版本实际为周线。' if prev2 else ''))
        elif code in {'long_risk_cluster_heat_deleverage', 'short_risk_cluster_heat_deleverage'}:
            base.require(s['enable_risk_cluster_heat_deleverage'] is True, 'Risk-cluster exit not enabled')
            threshold = float(s['risk_cluster_heat_deleverage_min_pressure'])
            x.update(kind='risk_cluster', label='风险组压力降仓',
                     description=f'所属风险组的标准化压力达到配置阈值 {threshold:g}，退出适用的持仓层；本轮底仓全部平掉。',
                     evidence=f'配置适用层：{s["risk_cluster_heat_deleverage_layer_kinds"]}；信号日计划平 {number(fill.volume)} 手，参考收盘 {number(event.price)}。原事件未封存当时的压力值，不反推补填。')
        elif code == 'forced_margin_deleverage':
            base.require(s['enable_forced_margin_deleverage'] is True, 'Forced margin exit not enabled')
            trigger, target, multiplier = (float(s['forced_margin_deleverage_' + k]) for k in ('trigger_ratio', 'target_ratio', 'broker_multiplier'))
            x.update(kind='forced_margin', label='组合保证金风控强制降仓',
                     description=f'组合模型保证金×{multiplier:g}÷交易权益超过 {trigger:.0%} 时，按规则优先削减占用较大的持仓，目标比例 {target:.0%}。',
                     evidence=f'本轮模型风控平掉 {number(fill.volume)} 手，信号日参考收盘 {number(event.price)}。这是回测策略的保证金风控；原事件未封存当时组合比例。')
        elif code == 'rollover_close':
            roll = one(tables['rollover'].loc[tables['rollover'].old_contract_vt_symbol.eq(fill.vt_symbol) &
                       tables['rollover'].date.eq(str(anchor.signal_date))], 'rollover diagnostic')
            x.update(kind='rollover', label='主力换月：平旧合约',
                     description='主力映射切换后，按换月规则平掉旧合约；是否开新合约另受开仓资格和资金约束。',
                     evidence=f'{fill.vt_symbol} → {roll.target_contract_vt_symbol}；新合约' +
                     ('未开仓' if float(roll.final_volume) == 0 else f'计划 {number(roll.final_volume)} 手') +
                     f'，原诊断：{roll.status} / {roll.reason}。')
        else:
            raise ValueError('Unknown exit reason; do not guess: ' + code)
        m['exit_explanation'] = x
    return result


HOOK = r'''<script>
(function(){
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const f=v=>Number(v).toLocaleString('zh-CN',{maximumFractionDigits:4});
 function facts(){
  const card=document.getElementById('exitReasonPanel'),field=document.getElementById('tradeFacts');
  if(typeof filtered==='undefined'||!filtered[active]){if(card)card.innerHTML='没有符合筛选条件的交易';if(field)field.innerHTML='';return null;}
  const m=filtered[active].meta,x=m.exit_explanation;
  if(field)field.innerHTML=`<b>${m.direction==='long'?'多头':'空头'} · ${f(m.volume)}手</b>　开仓 ${esc(m.entry_execution_datetime)} @ ${f(m.entry_price)}　→　平仓 ${esc(m.exit_execution_datetime)} @ ${f(m.exit_price)}<br>入场信号：${esc(m.signal)}；本轮滑点及手续费 ${f(m.round_cost)}元。<br>精确交割epoch：${esc(m.physical_epoch_id)}；日K前史 ${m.exact_pre_bars}/300、后史 ${m.exact_post_bars}/50（按真实上市历史与10月30日截断）。<br>${esc(m.minute_disclosure)}；缺交易日后分钟MA重新预热；可见MA40空值 ${m.intraday_ma40_warmup_missing_bars} 根。`;
  if(card)card.innerHTML=`<h2 style="margin:0 0 10px;font-size:20px">平仓原因：${esc(x.label)}</h2><p>${esc(x.description)}</p><p><b>当笔依据：</b>${esc(x.evidence)}</p><p><b>触发日：</b>${esc(x.signal_date)}　<b>成交交易日：</b>${esc(x.trading_date)}<br><b>实际成交：</b>${esc(x.execution_datetime)} @ ${f(x.execution_price)}，${f(x.volume)}手</p><p style="color:#667085;margin-bottom:0">原始原因：<code>${esc(x.raw_code)}</code> · ${esc(x.fill_id)}<br>触发规则按信号日判断；成交价取冻结的下一交易时段执行记录，可能与触发价不同。</p>`;
  return x;
 }
 const original=Plotly.react,purge=Plotly.purge;
 Plotly.react=function(target,traces,layout,config){
  if(target==='chart'){
   const x=facts();
   if(x){const m=filtered[active].meta,marker=traces.find(t=>t.name==='同源成交价格');
    if(marker){marker.text=[`开仓 ${esc(m.entry_execution_datetime)}<br>价格 ${f(m.entry_price)}`,`平仓：${esc(x.label)}<br>${esc(x.evidence)}<br>触发日 ${esc(x.signal_date)}<br>成交交易日 ${esc(x.trading_date)}<br>实际成交 ${esc(x.execution_datetime)} @ ${f(x.execution_price)}<br>原始原因 ${esc(x.raw_code)}`];marker.hovertemplate='%{text}<extra></extra>';}
    for(const a of layout.annotations??[])if(a.text==='平仓')a.text='平仓：'+x.label;
   }
  }
  return original.call(this,target,traces,layout,config);
 };
 Plotly.purge=function(target){if(target==='chart')facts();return purge.call(this,target);};
})();
</script>'''


def page(records, summary):
    renderer = base.library().load_canonical_renderer(base.RENDERER)
    old_hook = base.FACTS_HOOK
    try:
        base.FACTS_HOOK = HOOK
        result = base.page(renderer, records, summary)
    finally:
        base.FACTS_HOOK = old_hook
    tag = '<div id="tradeFacts" class="note"></div>'
    base.require(result.count(tag) == 1, 'Canonical facts insertion point changed')
    card = '<section id="exitReasonPanel" class="note" aria-live="polite" style="border:1px solid #c4b5fd;border-left:5px solid #7c3aed;background:#faf7ff;padding:16px 20px"></section>'
    # The dedicated card sits immediately above the charts, after selectors.
    marker = '<div id="metrics"'
    base.require(result.count(marker) == 1, 'Canonical metrics insertion point changed')
    result = result.replace(marker, card + marker, 1)
    rows = []
    for r in records:
        m, x = r['meta'], r['meta']['exit_explanation']
        cells = [m['vt_symbol'], '多' if m['direction'] == 'long' else '空', x['signal_date'], x['trading_date'], x['label'], x['evidence'], x['raw_code']]
        rows.append('<tr>' + ''.join('<td style="padding:8px;border-bottom:1px solid #e5e7eb">' + html.escape(str(v)) + '</td>' for v in cells) + '</tr>')
    table = '<details class="note"><summary>全部18轮平仓原因对照表</summary><div style="overflow:auto"><table style="border-collapse:collapse;width:100%;font-size:13px"><thead><tr>' + ''.join('<th>' + v + '</th>' for v in ['合约', '方向', '触发日', '成交交易日', '平仓原因', '当笔依据', '原始代码']) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div></details>'
    result = result.replace('</body>', table + '</body>', 1)
    base.require(not re.search(r'<script[^>]+src\s*=', result, re.I), 'External script forbidden')
    return result


def verify_source():
    manifest = SOURCE / 'generation_manifest.json'
    base.require(base.sha(manifest) == SOURCE_MANIFEST_SHA, 'Stage020 accepted generation manifest changed')
    g = json.loads(manifest.read_text())
    for p, want in g['source_files_sha256'].items():
        base.require(base.sha(p) == want, 'Stage020 frozen input changed: ' + p)
    for name, want in g['output_files_sha256'].items():
        base.require(Path(name).name == name and base.sha(SOURCE / name) == want, 'Stage020 output changed: ' + name)
    accepted = LINE / 'stages/Stage020_review_acceptance.json'
    base.require(base.sha(accepted) == SOURCE_ACCEPTANCE_SHA and json.loads(accepted.read_text())['accepted'] is True, 'Stage020 acceptance changed')
    for name in [*FILES.values(), 'actual_strategy_settings.json']:
        base.require(str(base.RUN / name) in g['source_files_sha256'], 'Exit evidence is outside accepted source: ' + name)
    base.verify_delivery()
    return {**g['source_files_sha256'], str(manifest): base.sha(manifest), str(accepted): base.sha(accepted),
            **{str(SOURCE / name): want for name, want in g['output_files_sha256'].items()},
            str(Path(__file__)): base.sha(__file__)}


def build(output=OUTPUT):
    output = Path(output)
    require_output(output)
    sources = verify_source()
    old = json.loads((SOURCE / 'records.json').read_text())
    records = enrich(old, read_evidence())
    summary = json.loads((SOURCE / 'summary.json').read_text())
    summary['page_title'] = '2026年19品种周线 C_R150｜18轮逐笔复盘 · 中文平仓原因'
    summary['exit_explanations_added'] = 18
    result = page(records, summary)
    # Assert the entire source object, including every OHLCV/MA/coordinate,
    # becomes byte-equivalent JSON data after removing only the new field.
    original = copy.deepcopy(records)
    for r in original:
        del r['meta']['exit_explanation']
    base.require(original == old and len(records) == 18, 'Display adapter altered source records')
    output.mkdir(parents=True)
    for name, value in [('records.json', records), ('summary.json', summary), ('exit_reasons.json', [r['meta']['exit_explanation'] for r in records])]:
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False))
    for name in ['chart_manifest.csv', 'closed_rounds.csv']:
        shutil.copyfile(SOURCE / name, output / name)
    (output / 'index.html').write_text(result)
    scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', result)
    base.require(len(scripts) == 3, 'Unexpected embedded script layout')
    for i, script in enumerate(scripts):
        (output / f'embedded_script_{i}.js').write_text(script)
    receipt = dict(schema='Stage021.exit-reason-display.v1', generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                   source_profile=base.SOURCE_PROFILE, source_files_sha256=sources,
                   output_files_sha256={p.name: base.sha(p) for p in output.iterdir() if p.is_file()},
                   old_records_identical_except_new_explanation=True, financial_replays=0, market_downloads=0,
                   strategy_changes=0, production_accesses=0, http_services_started=0,
                   browser_validation='BLOCKED_FILE_PROTOCOL_POLICY_NO_WORKAROUND', status='PENDING_STATIC_AND_INDEPENDENT_REVIEW')
    (output / 'generation_manifest.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    return dict(output=str(output), explained_rounds=len(records), html_bytes=(output / 'index.html').stat().st_size)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUTPUT)
    print(json.dumps(build(parser.parse_args().output), ensure_ascii=False))
