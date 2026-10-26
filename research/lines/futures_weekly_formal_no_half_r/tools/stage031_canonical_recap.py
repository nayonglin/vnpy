"""Display-only Stage030 B/W adapter; execute canonical pure functions in memory.

No strategy imports, network client, data downloads, account or production access.
Canonical source stays unchanged; its full SHA256 is retained in each output.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sqlite3
import subprocess
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / 'research/lines/futures_weekly_formal_no_half_r'
RENDERER = ROOT / 'research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py'
REPORT = LINE / 'artifacts/stage030_comparison'
DATA = LINE / 'outputs/stage029_latest_data/data_approved'
DEFAULT_OUTPUT = LINE / 'artifacts/stage031_recap'
SOURCE_HEAD = '59e58f271df58451869c9da3d66f0de750f3b013'
SOURCE_RUNS = {'weekly': LINE / 'outputs/stage030_weekly_attempt001', 'baseline': LINE / 'outputs/R_attempt003'}
FUNCTIONS = {'_json_safe', '_date_index', '_window_dates', '_context_daily', '_weekly_from_daily',
             '_monthly_from_daily', '_trading_day_bars_from_daily', '_monthly_window',
             '_add_moving_averages', '_period_coordinates', '_records', '_html'}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_canonical_renderer(path: Path) -> SimpleNamespace:
    """Load original AST function bodies only; never import its strategy/Tq modules."""
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS]
    if {n.name for n in nodes} != FUNCTIONS:
        raise ValueError('canonical function contract is incomplete')
    env = dict(np=np, pd=pd, html=html, json=json, math=math, datetime=datetime,
               get_plotlyjs=get_plotlyjs, Any=Any, MA_PERIODS=(5,10,20,40),
               DAILY_PRE=300, DAILY_POST=50, INTRADAY_PRE=5, INTRADAY_POST=5,
               MONTHLY_PRE=10, MONTHLY_POST=10, WEEKLY_MA_WARMUP_WEEKS=45,
               MONTHLY_MA_WARMUP_MONTHS=45, TRADING_DAY_MA_WARMUP_DAYS=1230,
               OFFICIAL_LIVE_ALIAS='研究源，非正式生产', OFFICIAL_LIVE_VERSION='Stage030 frozen B/W')
    safe_tree = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(safe_tree), str(path), 'exec'), env)
    return SimpleNamespace(**env)


def create_new_output(path: Path, source_roots: list[Path]) -> None:
    path = path.resolve()
    if any(path == s.resolve() or s.resolve() in path.parents or path in s.resolve().parents for s in source_roots):
        raise ValueError('output overlaps frozen source')
    path.mkdir(parents=True, exist_ok=False)


def _trade_number(value: Any) -> int:
    return int(str(value).rsplit('.', 1)[-1])


def episodes_from_frozen(rounds: pd.DataFrame, terminal: pd.DataFrame,
                         fills: pd.DataFrame, role: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use native flat-to-flat report identity and attach its actual fill markers."""
    selected = rounds.loc[rounds.role.eq(role)].copy()
    remain = terminal.loc[terminal.role.eq(role)].copy()
    fills = fills.copy()
    fills['_number'] = fills.trade_id.map(_trade_number)
    if fills.trade_id.duplicated().any():
        raise ValueError('duplicate source trade ID')
    output = []
    used = set()
    for source in selected.itertuples(index=False):
        part = fills.loc[fills.vt_symbol.eq(source.vt_symbol) &
                         fills._number.between(_trade_number(source.entry_trade_id), _trade_number(source.exit_trade_id))].sort_values('_number')
        if len(part) != int(source.fill_count):
            raise ValueError(f'fill count mismatch: {source.entry_trade_id}')
        opens = part.loc[part.offset.eq('开')]
        closes = part.loc[~part.offset.eq('开')]
        if opens.empty or closes.empty or part.iloc[0].trade_id != source.entry_trade_id or part.iloc[-1].trade_id != source.exit_trade_id:
            raise ValueError('missing round endpoint fill')
        if not math.isclose(float(opens.volume.sum()), float(source.opened_volume), abs_tol=1e-8):
            raise ValueError('opened volume mismatch')
        if not math.isclose(float(closes.volume.sum()), float(source.opened_volume), abs_tol=1e-8):
            raise ValueError('closed volume mismatch')
        if used.intersection(part.trade_id):
            raise ValueError('fill belongs to multiple closed rounds')
        used.update(part.trade_id)
        entry = float(np.average(opens.price, weights=opens.volume))
        weighted_exit = float(np.average(closes.price, weights=closes.volume))
        price_move = (weighted_exit / entry - 1.) * 100.
        pnl = float(source.net_pnl)
        result = 'profit' if pnl > 0 else ('loss' if pnl < 0 else 'flat')
        symbol, exchange = source.vt_symbol.split('.',1)
        product = re.match(r'[A-Za-z]+', symbol).group(0) + '.' + exchange
        partial = [dict(trade_id=str(f.trade_id),date=str(f.trading_date)[:10],
                        execution_datetime=str(f.datetime),price=float(f.price),volume=float(f.volume),
                        reason='' if pd.isna(f.exit_reason) else str(f.exit_reason))
                   for f in closes.iloc[:-1].itertuples(index=False)]
        output.append(dict(result_rank=len(output)+1,result_type=result,is_tail=0,draw_intraday=0,
            lot_id=str(source.entry_trade_id),lot_count=len(closes),open_trade_id=str(source.entry_trade_id),
            close_trade_id=str(source.exit_trade_id),vt_symbol=str(source.vt_symbol),product=product,
            direction=str(source.direction),entry_date=str(source.entry_trading_date),exit_date=str(source.exit_trading_date),
            entry_execution_datetime=str(source.entry_execution_datetime),exit_execution_datetime=str(source.exit_execution_datetime),
            entry_price=entry,exit_price=float(closes.iloc[-1].price),weighted_exit_price=weighted_exit,
            price_change_pct=price_move,price_change_label=f'标的原始涨跌 {price_move:+.2f}%（非账户收益）',
            volume=float(source.opened_volume),realized_pnl=pnl,r_multiple=np.nan,
            selection_basis='完整native合约轮；冻结净损益；R缺确切口径保持N/A',
            holding_calendar_days=(pd.Timestamp(source.exit_trading_date)-pd.Timestamp(source.entry_trading_date)).days,
            exit_reason=str(closes.iloc[-1].exit_reason),signal='冻结源，不重生成信号',
            profit_r_threshold=np.nan,loss_r_threshold=np.nan,partial_markers=partial,
            fill_count=int(source.fill_count)))
    # Terminal evidence is a separate ledger: no fictional close or R is added.
    for row in remain.itertuples(index=False):
        entry = fills.loc[fills.trade_id.eq(row.entry_trade_id)]
        if len(entry) != 1 or entry.iloc[0].vt_symbol != row.vt_symbol:
            raise ValueError('terminal entry identity mismatch')
    return pd.DataFrame(output), remain


def terminal_fill_table(fills: pd.DataFrame, terminal: pd.DataFrame) -> pd.DataFrame:
    actual = fills.copy()
    actual['_number'] = actual.trade_id.map(_trade_number)
    parts = []
    for row in terminal.itertuples(index=False):
        part = actual.loc[actual.vt_symbol.eq(row.vt_symbol) &
                          actual._number.ge(_trade_number(row.entry_trade_id))].copy()
        if len(part) != int(row.fill_count):
            raise ValueError('terminal fill count mismatch')
        opened = float(part.loc[part.offset.eq('开'),'volume'].sum())
        closed = float(part.loc[~part.offset.eq('开'),'volume'].sum())
        if not math.isclose(opened,float(row.opened_volume),abs_tol=1e-8) or not math.isclose(opened-closed,abs(float(row.end_pos)),abs_tol=1e-8):
            raise ValueError('terminal volume mismatch')
        part['terminal_entry_trade_id'] = row.entry_trade_id
        part['terminal_observation_no_final_exit'] = True
        parts.append(part.drop(columns='_number'))
    return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()


def exact_epoch_bars(database: Path, physical: pd.DataFrame, vt_symbol: str,
                     entry_date: str, exit_date: str) -> tuple[pd.DataFrame, str]:
    """Bind the entry's physical epoch before querying native symbols reused after ten years."""
    source = physical.loc[physical.vt_symbol.eq(vt_symbol)].copy()
    source['date'] = pd.to_datetime(source.date).dt.normalize()
    entry, exit_ = pd.Timestamp(entry_date).normalize(), pd.Timestamp(exit_date).normalize()
    matches = source.loc[source.date.eq(entry), 'contract_epoch_id'].drop_duplicates()
    if len(matches) != 1:
        raise ValueError(f'entry physical epoch ambiguous: {vt_symbol} {entry_date}')
    epoch_id = str(matches.iloc[0])
    epoch = source.loc[source.contract_epoch_id.eq(epoch_id)].sort_values('date')
    if epoch.date.duplicated().any():
        raise ValueError('duplicate physical-epoch daily key')
    if not epoch.date.eq(exit_).any():
        raise ValueError(f'exit missing from entry physical epoch: {vt_symbol} {exit_date}')
    symbol, exchange = vt_symbol.split('.',1)
    with sqlite3.connect(f'file:{database.resolve()}?mode=ro',uri=True) as connection:
        bars = pd.read_sql_query("SELECT datetime AS date, open_price AS open, high_price AS high, low_price AS low, close_price AS close, volume, open_interest AS close_oi FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' AND datetime>=? AND datetime<? ORDER BY datetime",connection,
            params=(symbol,exchange,str(epoch.date.min().date()),str((epoch.date.max()+pd.Timedelta(days=1)).date())))
    bars['date'] = pd.to_datetime(bars.date).dt.normalize()
    if bars.date.duplicated().any():
        raise ValueError('duplicate sqlite daily key')
    bars = bars.loc[bars.date.isin(epoch.date)].reset_index(drop=True)
    check = epoch.merge(bars,on='date',suffixes=('_physical','_sqlite'),validate='one_to_one')
    if len(check) != len(epoch):
        raise ValueError('physical epoch / sqlite date-key mismatch')
    for column in ['open','high','low','close','volume']:
        if column in epoch and not np.allclose(check[column+'_physical'],check[column+'_sqlite'],rtol=1e-12,atol=1e-8,equal_nan=False):
            raise ValueError(f'physical epoch / sqlite {column} mismatch')
    if not bars.date.eq(entry).any() or not bars.date.eq(exit_).any():
        raise ValueError('entry/exit daily sqlite endpoint missing')
    if not ((bars.high >= bars[['open','close','low']].max(axis=1)) & (bars.low <= bars[['open','close','high']].min(axis=1)) & (bars[['open','high','low','close']]>0).all(axis=1)).all():
        raise ValueError('invalid real daily OHLC')
    return bars, epoch_id


def make_context(renderer: SimpleNamespace, row: Any, mapping: pd.DataFrame,
                 exact: pd.DataFrame) -> tuple[pd.DataFrame,list[pd.Timestamp]]:
    """Canonical window selection, with exact-only I/O injected into its globals."""
    env = renderer._context_daily.__globals__
    env['_contract_daily'] = lambda symbol: exact.copy() if symbol == row.vt_symbol else (_ for _ in ()).throw(ValueError('proxy context prohibited'))
    env['_daily_from_existing_minute_files'] = lambda *a,**k: pd.DataFrame()
    local_mapping = mapping.copy()
    local_mapping['main_contract_vt'] = row.vt_symbol
    daily, intraday = renderer._context_daily(row,local_mapping,{},allow_daily_download=False,
        allow_noncritical_daily_gaps=True,data_end=pd.Timestamp('2026-10-26'))
    holding = set(pd.to_datetime(mapping.loc[mapping['product'].str.lower().eq(row.product.split('.')[0].lower()) &
        mapping.exchange.eq(row.vt_symbol.split('.')[1]) & mapping.date.between(pd.Timestamp(row.entry_date),pd.Timestamp(row.exit_date)),'date']))
    gaps = sorted(holding - set(daily.date))
    if gaps:
        raise ValueError(f'held-period exact-contract gap {row.open_trade_id}: {gaps[:3]}')
    if daily.context_fallback.any():
        raise ValueError('proxy context prohibited')
    return daily,intraday


def make_records(renderer: SimpleNamespace, episodes: pd.DataFrame,
                 daily: dict[str,pd.DataFrame], dates: dict[str,list[pd.Timestamp]]):
    empty = pd.DataFrame(columns=['vt_symbol','bar_datetime','trading_day','open','high','low','close','volume'])
    records, manifest = renderer._records(episodes,daily,dates,empty)
    for record,row in zip(records,episodes.itertuples(index=False)):
        positions = dict(zip(record['daily']['date'],record['daily']['x']))
        markers = []
        for marker in row.partial_markers:
            if marker['date'] not in positions:
                raise ValueError('partial fill outside exact daily chart')
            markers.append({**marker,'x':positions[marker['date']]})
        record['meta'].update(partial_markers=markers,
            entry_execution_datetime=row.entry_execution_datetime,exit_execution_datetime=row.exit_execution_datetime,
            partial_marker_count=len(markers),source_fill_count=row.fill_count,
            physical_epoch_id=getattr(row,'physical_epoch_id',None),r_multiple=None,
            missing_15m_dates=[pd.Timestamp(d).date().isoformat() for d in dates[row.open_trade_id]])
    manifest['intraday_missing_days'] = [len(r['meta']['missing_15m_dates']) for r in records]
    manifest['missing_15m_dates'] = [r['meta']['missing_15m_dates'] for r in records]
    manifest['partial_marker_count'] = [len(r['meta']['partial_markers']) for r in records]
    manifest['physical_epoch_id'] = [r['meta']['physical_epoch_id'] for r in records]
    manifest['r_multiple'] = None
    manifest['episode_id'] = manifest['open_trade_id']
    manifest['entry_trade_id'] = manifest['open_trade_id']
    return renderer._json_safe(records),manifest


# This extension adds only real partial-fill markers to the canonical traces.
# It does not implement any candles, period selection, layout, axes, or zoom.
PARTIAL_MARKER_EXTENSION = r'''<script>
(function(){const original=Plotly.react;Plotly.react=function(target,traces,layout,config){
if(target==='chart'&&typeof filtered!=='undefined'&&filtered[active]){
const r=filtered[active],markers=r.meta.partial_markers||[],existing=traces.find(t=>t.name==='同源成交价格');
if(markers.length&&existing)traces.push({type:'scatter',mode:'markers',name:'真实部分平仓',
x:markers.map(m=>m.x),y:markers.map(m=>m.price),xaxis:existing.xaxis,yaxis:existing.yaxis,
marker:{symbol:'diamond',size:10,color:'#d97706'},customdata:markers.map(m=>[m.trade_id,m.date,m.volume,m.reason]),
hovertemplate:'%{customdata[0]}<br>%{customdata[1]}<br>价格=%{y}<br>手数=%{customdata[2]}<br>%{customdata[3]}<extra>真实部分平仓</extra>'});}
return original.call(this,target,traces,layout,config);};})();
</script>'''


def canonical_html(renderer: SimpleNamespace, records: list[dict], summary: dict) -> str:
    page = renderer._html(records,summary)
    page, count = re.subn(r'</div><script>(\s*const records=)',
        lambda match: '</div>'+PARTIAL_MARKER_EXTENSION+'<script>'+match.group(1),page,count=1)
    if count != 1:
        raise ValueError('canonical script boundary changed')
    navigation = "<script>const requestedEpisode=new URLSearchParams(location.search).get('episode');if(requestedEpisode){const requestedIndex=filtered.findIndex(r=>r.meta.open_trade_id===requestedEpisode);if(requestedIndex>=0){active=requestedIndex;refreshSelect();render();}}</script>"
    return page.replace('</body></html>',navigation+'</body></html>')


def _json(path: Path, data: Any, renderer: SimpleNamespace) -> None:
    path.write_text(json.dumps(renderer._json_safe(data),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def build(output: Path = DEFAULT_OUTPUT) -> dict:
    renderer = load_canonical_renderer(RENDERER)
    source_comparison = json.loads((REPORT/'comparison.json').read_text())
    source_delivery = json.loads((REPORT/'delivery_manifest.json').read_text())
    expected_hashes = {**source_comparison['source_files_sha256'],**source_comparison['output_files_sha256'],**source_delivery['files_sha256']}
    rounds = pd.read_csv(REPORT/'complete_contract_rounds.csv')
    terminal = pd.read_csv(REPORT/'terminal_open_rounds.csv')
    summary_rows = pd.read_csv(REPORT/'summary.csv').set_index('role')
    all_episodes,remainders = {},{}
    source_files = [RENDERER,REPORT/'comparison.json',REPORT/'delivery_manifest.json',REPORT/'complete_contract_rounds.csv',REPORT/'terminal_open_rounds.csv',REPORT/'summary.csv',DATA/'daily.sqlite',DATA/'physical_epoch_daily.csv',DATA/'mapping.csv']
    for role,run in SOURCE_RUNS.items():
        files = [run/n for n in ['trades.csv','metrics.json','daily.csv','effective_parameters.json','actual_database_binding.json','actual_strategy_settings.json','execution_clock.csv','input_manifest.json']]
        source_files.extend(files)
        all_episodes[role],remainders[role] = episodes_from_frozen(rounds,terminal,pd.read_csv(run/'trades.csv'),role)
        if len(all_episodes[role]) != int(summary_rows.loc[role,'round_count']) or len(remainders[role]) != 4:
            raise ValueError('closed/terminal count disagrees with frozen summary')
        if not math.isclose(all_episodes[role].realized_pnl.sum(),summary_rows.loc[role,'round_closed_net_pnl'],abs_tol=1e-6):
            raise ValueError('frozen closed PnL reconciliation failed')
    hashes = {str(p):sha256(p) for p in source_files}
    for path,digest in hashes.items():
        if path in expected_hashes and expected_hashes[path] != digest:
            raise ValueError(f'frozen source hash changed: {path}')
    symbols = set(pd.concat(list(all_episodes.values())).vt_symbol)
    physical_parts = []
    columns = ['vt_symbol','date','contract_epoch_id','open','high','low','close','volume']
    for chunk in pd.read_csv(DATA/'physical_epoch_daily.csv',usecols=columns,chunksize=100000):
        physical_parts.append(chunk.loc[chunk.vt_symbol.isin(symbols)])
    physical = pd.concat(physical_parts,ignore_index=True)
    mapping = pd.read_csv(DATA/'mapping.csv')
    mapping['date'] = pd.to_datetime(mapping.date).dt.normalize()
    mapping = mapping.drop_duplicates(['date','product','exchange'])
    create_new_output(output,[REPORT,DATA,*SOURCE_RUNS.values()])
    bundle = dict(schema='stage031_frozen_canonical_recap_v1',source_head=SOURCE_HEAD,
        canonical_renderer=str(RENDERER),canonical_renderer_sha256=hashes[str(RENDERER)],
        build_tools_sha256={str(Path(__file__).resolve()):sha256(Path(__file__).resolve()),
                            str(Path(__file__).with_name('test_stage031_canonical_recap.py')):sha256(Path(__file__).with_name('test_stage031_canonical_recap.py'))},
        source_files_sha256=hashes,financial_replays=0,market_downloads=0,production_accesses=0,
        strategy_changes=0,source_identity='Stage030 weekly W / frozen Stage029 R003 B',arms={})
    cache = {}
    for role,episodes in all_episodes.items():
        print(f'Building {role}: {len(episodes)} closed native rounds',flush=True)
        dest = output/role
        dest.mkdir()
        daily,dates,epochs,coverage = {},{},{},[]
        for row in episodes.itertuples(index=False):
            key = (row.vt_symbol,row.entry_date,row.exit_date)
            if key not in cache:
                exact,epoch_id = exact_epoch_bars(DATA/'daily.sqlite',physical,row.vt_symbol,row.entry_date,row.exit_date)
                context,intraday = make_context(renderer,row,mapping,exact)
                cache[key]=(exact,epoch_id,context,intraday)
            exact,epoch_id,context,intraday = cache[key]
            daily[row.open_trade_id]=context
            dates[row.open_trade_id]=intraday
            epochs[row.open_trade_id]=epoch_id
            coverage.append(dict(open_trade_id=row.open_trade_id,vt_symbol=row.vt_symbol,physical_epoch_id=epoch_id,
                real_history_start=str(exact.date.min().date()),real_history_end=str(exact.date.max().date()),
                exact_daily_rows=len(exact),listing_truncated_pre=bool((exact.date< pd.Timestamp(row.entry_date)).sum()<300),
                post_exit_real_days=int((exact.date>pd.Timestamp(row.exit_date)).sum()),
                ma40_chart_only_strategy_off=True,held_period_exact_coverage=True))
        episodes['physical_epoch_id']=episodes.open_trade_id.map(epochs)
        records,manifest=make_records(renderer,episodes,daily,dates)
        frozen_row=summary_rows.loc[role].to_dict()
        raw_metrics=json.loads((SOURCE_RUNS[role]/'metrics.json').read_text())
        label='W 周K收盘价格浮盈>5%减半' if role=='weekly' else 'B 不加5%止盈（研究对照）'
        summary=dict(schema='stage031_arm_canonical_recap_v1',episode_scope='all',rank_basis='realized_pnl',
            page_title=f'{label}：全{len(episodes)}个已平完整合约轮复盘',
            coverage_note='全部已平轮；橙色菱形为真实部分平仓。15分钟未提供。仅同物理合约epoch真实日线；上市前/到期后缺历史保持缺口。',
            footer_scope=f'{len(episodes)}已平轮；4个末未闭合轮见上级总目录，未伪造最终平仓。',
            source_label='冻结离线研究，非生产资格',source_version='Stage030 W / R003 B / 150000 / 2015-01-05—2026-10-26',
            source_warning='策略MA40关闭；图表MA40仅参考。图表自然周聚合不等于策略接受观察周MA（策略可能跳周）。日/月/30日MA真实历史不足保持空值；禁止跨十年同名native合约拼接。',
            frozen_metrics=frozen_row,source_raw_metrics=raw_metrics,closed_round_count=len(episodes),
            terminal_round_count=len(remainders[role]),profit_round_count=int(episodes.result_type.eq('profit').sum()),
            loss_round_count=int(episodes.result_type.eq('loss').sum()),flat_round_count=int(episodes.result_type.eq('flat').sum()),
            partial_marker_count=int(manifest.partial_marker_count.sum()),source_files_sha256=hashes,
            canonical_renderer_sha256=hashes[str(RENDERER)],source_head=SOURCE_HEAD,
            financial_replays=0,market_downloads=0,production_accesses=0,context_proxy_days=0,
            default_periods=['day30','daily'],periods=['day30','day10','monthly','weekly','daily','intraday'],
            intraday_status='unavailable_in_frozen_source_no_download',r_status='unknown_null',
            chart_week_basis='natural W-FRI chart aggregation, not accepted strategy observation weeks')
        if [summary[k] for k in ['profit_round_count','loss_round_count','flat_round_count']] != [int(frozen_row[k]) for k in ['round_wins','round_losses','round_flat']]:
            raise ValueError('result counts failed frozen reconciliation')
        manifest.to_csv(dest/'chart_manifest.csv',index=False)
        episodes.to_csv(dest/'selected_episodes.csv',index=False)
        remainders[role].to_csv(dest/'terminal_open_rounds.csv',index=False)
        terminal_fill_table(pd.read_csv(SOURCE_RUNS[role]/'trades.csv'),remainders[role]).to_csv(dest/'terminal_actual_fills.csv',index=False)
        pd.DataFrame(coverage).to_csv(dest/'exact_epoch_coverage.csv',index=False)
        _json(dest/'records.json',records,renderer)
        (dest/'index.html').write_text(canonical_html(renderer,records,summary),encoding='utf-8')
        summary['artifact_sha256']={p.name:sha256(p) for p in dest.iterdir() if p.is_file()}
        _json(dest/'summary.json',summary,renderer)
        bundle['arms'][role]=dict(closed_round_count=len(episodes),terminal_round_count=len(remainders[role]),
            frozen_metrics=frozen_row,partial_marker_count=summary['partial_marker_count'],
            exact_contract_proxy_days=0,minute_bars=0,index=str(dest/'index.html'))
    title='Stage031 周K 5%减半回撤逐笔复盘（冻结证据）'
    links=''.join(f'<li><a href="{role}/index.html">{label}：{bundle["arms"][role]["closed_round_count"]}已平轮</a> · <a href="{role}/chart_manifest.csv">图表清单</a> · <a href="{role}/records.json">图表数据</a></li>' for role,label in [('weekly','W 周收减半'),('baseline','B 不减半')])
    tables=''.join(f'<h2>{html.escape(role)}：4个末未闭合轮（非最终平仓）</h2>'+frame.to_html(index=False,border=0)+f'<p><a href="{role}/terminal_actual_fills.csv">末仓全部真实成交明细（无伪终平）</a></p>' for role,frame in remainders.items())
    page=f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>{title}</title><style>body{{font:15px system-ui;margin:28px;line-height:1.6;color:#17202a}}table{{border-collapse:collapse;font-size:12px}}th,td{{padding:6px;border:1px solid #ddd}}a{{color:#2563eb}}</style><h1>{title}</h1><p>源HEAD {SOURCE_HEAD}；150000初始资金，2015-01-05—2026-10-26。W最大回撤窗2018-02-27→2020-04-09；B峰2017-09-05→同谷。进入页面可用年份2018/2020与品种筛选，并核对原始成交日期；年份筛选按开仓年。</p><ul>{links}</ul><p>canonical六周期/默认30日K+日K/联动缩放保留。策略MA40关闭，图中MA40仅参考；自然周图与策略接受观察周不等同。15分钟源缺失；真实合约前后历史和MA预热不足保持空值，不代理、不拼十年同名合约、不下载。橙色菱形是原始部分平仓；标的涨跌未做方向调整，不能作为账户收益。无确切R统一N/A。</p><p>没有金融回放、策略改动、行情下载或生产访问。下表末仓仅保留已实现部分与剩余盯市，未伪造最终退出。</p>{tables}</html>'
    (output/'index.html').write_text(page,encoding='utf-8')
    _json(output/'summary.json',bundle,renderer)
    pd.concat([pd.read_csv(output/r/'chart_manifest.csv').assign(role=r) for r in SOURCE_RUNS]).to_csv(output/'chart_manifest.csv',index=False)
    _json(output/'source_hashes.json',hashes,renderer)
    artifact_hashes={str(p.relative_to(output)):sha256(p) for p in sorted(output.rglob('*')) if p.is_file()}
    _json(output/'delivery_manifest.json',dict(schema='stage031_recap_delivery_v1',files_sha256=artifact_hashes,self_hash_excluded=True),renderer)
    if {str(p):sha256(p) for p in source_files} != hashes:
        raise ValueError('source changed during display build')
    return bundle


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    if args.output.resolve()!=DEFAULT_OUTPUT.resolve():
        raise ValueError('this source adapter only writes its assigned new Stage031 bundle')
    result=build(args.output)
    print(json.dumps({'index':str(args.output/'index.html'),'arms':result['arms']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
