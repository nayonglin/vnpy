"""Stage011 saved-ledger comparison; no strategy or financial engine imports."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import base64,html,json,math
import numpy as np
import pandas as pd
from stage009_accounting import bucket_curve,curve_metrics
from stage010_account_nav import project_curve,metrics as account_metrics
from stage009_contract import LINE,STARTS,CUTOFF,sha,load,atomic_json

OUT=LINE/'artifacts/stage011_uniform_risk_comparison'
VARIANTS=('A_old','A_new','C_old','C_new')
LABELS={'A_new':'A统一1.8%基础档','A_old':'A原分档风险','C_new':'C统一1.8%基础档','C_old':'C原分档风险'}
HTML_NAME='Stage011_统一普通风险_场外补资对比.html'


def require(value,label):
    if not value:raise ValueError('stage011_report:'+label)


def near(a,b):return np.allclose(a,b,rtol=1e-10,atol=1e-6,equal_nan=False)


def safe(value):
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    if isinstance(value,np.generic):return safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def summarize(raw,events,rounds,open_mtm,start,arm,version):
    require(version in {'uniform_risk','prior_risk'},'version')
    d=bucket_curve(raw,events,arm)
    # Both comparison arms have the same reserve mechanism. Never label the
    # old funded account as an idle account or assert its deposits are zero.
    d=project_curve(d,arm+'_R');m=account_metrics(d);wealth=curve_metrics(d)
    require(near(float(rounds['closed_net_pnl'])+float(open_mtm),m['real_trading_net_pnl']),'closed_open_real_PnL')
    margin=d.total_margin_exact.astype(float)*165/d.trading_account_equity.where(d.trading_account_equity.gt(0))
    exhausted=d.reserve_balance.le(1e-6)
    variant=arm+('_new' if version=='uniform_risk' else '_old')
    summary=dict(start=start,variant=variant,arm=arm,version=version,funding_mode='external_topup',observation_only=start=='2026-01-01',**m,
        wealth_end_equity=wealth['end_equity'],wealth_return_pct=wealth['total_return_pct'],wealth_max_dd_pct=wealth['max_dd_pct'],
        wealth_sharpe=wealth['sharpe'],wealth_returns_defined=wealth['sharpe_returns_defined'],nonpositive_total_equity_days=wealth['nonpositive_total_equity_days'],
        transfer_event_count=len(events),reserve_exhausted=bool(exhausted.any()),exhaustion_date=str(d.loc[exhausted,'date'].iloc[0]) if exhausted.any() else '',
        trading_margin_peak_pct=float(margin.max()) if margin.notna().any() else None,trading_margin_over100_days=int(margin.gt(100).sum()),
        open_round_net_mtm=float(open_mtm),**{'round_'+k:v for k,v in rounds.items()})
    d=d.assign(start=start,variant=variant,wealth_nav=d.total_account_equity/300000.,wealth_drawdown_pct=d.drawdown_pct)
    fields=['start','variant','date','raw_account_equity','net_pnl','trading_account_equity','reserve_balance','cumulative_transfer','transfer_amount',
        'total_account_equity','slippage','commission','trade_count','total_margin_exact','account_nav','balance_drawdown_pct','wealth_nav','wealth_drawdown_pct']
    return summary,d[fields]


def comparison(a,b):
    return 0 if math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6) else (1 if a>b else -1)


def pair_metrics(old,new,start,arm):
    row=dict(start=start,arm=arm,cohort='January' if start[5:7]=='01' else 'June',observation_only=start=='2026-01-01')
    for out,key in [('delta_account_growth_pp','account_growth_pct'),('delta_balance_max_dd_pp','balance_max_dd_pct'),('delta_balance_sharpe','balance_sharpe'),
        ('delta_real_trading_net_pnl','real_trading_net_pnl'),('delta_account_end_equity','account_end_equity'),('delta_deposits','total_transferred'),
        ('delta_wealth_return_pp','wealth_return_pct'),('delta_wealth_max_dd_pp','wealth_max_dd_pct'),('delta_wealth_sharpe','wealth_sharpe')]:
        row[out]=float(new[key])-float(old[key])
    require(near(row['delta_account_end_equity'],row['delta_real_trading_net_pnl']+row['delta_deposits']),'paired_cashflow_bridge')
    row.update(real_pnl_gate=comparison(new['real_trading_net_pnl'],old['real_trading_net_pnl'])>0,
        wealth_dd_gate=comparison(new['wealth_max_dd_pct'],old['wealth_max_dd_pct'])>=0,wealth_sharpe_gate=comparison(new['wealth_sharpe'],old['wealth_sharpe'])>=0)
    row['three_gate_pass']=all(row[k] for k in ['real_pnl_gate','wealth_dd_gate','wealth_sharpe_gate'])
    for prefix,m in [('old',old),('new',new)]:
        for key in ['account_end_equity','real_trading_net_pnl','total_transferred','off_account_reserve_end','wealth_max_dd_pct','wealth_sharpe']:
            row[prefix+'_'+key]=m[key]
    return row


def verify_map(mapping):
    for p,h in mapping.items():require(Path(p).is_file() and sha(p)==h,'source_changed:'+str(p))


def build(freeze_path=LINE/'stages/stage011_freeze.json',output=OUT):
    output=Path(output);require(not output.exists(),'output_exists_preserve_report')
    freeze=load(freeze_path);registry=load(LINE/'outputs/stage011_multistart/registry.json');prior=load(freeze['baseline_registry'])
    require(registry['freeze_sha256']==sha(freeze_path),'registry_freeze')
    require(set(registry['jobs'])==set(prior['jobs'])=={s+'|'+a for s in STARTS for a in ['A','C']},'exact46_new_old_jobs')
    require(all(j['status']=='validated' for j in registry['jobs'].values()),'all46_new_validated')
    require(registry.get('financial_engine_batch_complete') is True and registry.get('financial_replays_started')==46,'exact46_completed_financial_replays')
    sources={str(Path(freeze_path).resolve()):sha(freeze_path),str((LINE/'outputs/stage011_multistart/registry.json').resolve()):sha(LINE/'outputs/stage011_multistart/registry.json')}
    baseline_manifest=load(freeze['baseline_delivery_manifest']);require(sha(freeze['baseline_delivery_manifest'])==freeze['baseline_delivery_manifest_sha256'],'old_delivery_identity')
    sources[str(Path(freeze['baseline_registry']).resolve())]=freeze['baseline_registry_sha256']
    sources[str(Path(freeze['baseline_delivery_manifest']).resolve())]=freeze['baseline_delivery_manifest_sha256']
    summaries=[];daily=[];event_rows=[];parameter_deltas=[]
    for start in STARTS:
        for arm in ['A','C']:
            for version,job in [('prior_risk',prior['jobs'][start+'|'+arm]),('uniform_risk',registry['jobs'][start+'|'+arm])]:
                p=Path(job['path']);receipt=LINE/'stages'/('stage011_independent_receipts' if version=='uniform_risk' else 'stage009_independent_receipts')/f'{start}_{arm}.json'
                audit=load(receipt);require(audit['status']=='PASS_WITH_LIMITATIONS' and not audit['failures'],'signed_window_review_required')
                require(Path(audit['path']).resolve()==p.resolve(),'signed_window_path')
                for file in ['daily.csv','reserve_daily.csv','reserve_events.json','actual_strategy_settings.json','entry_risk.csv','effective_parameters.json']:
                    q=p/file;h=sha(q);require(h==job['files_sha256'][str(q)]==audit['source_files_sha256'][str(q)],'exact_source_file:'+file);sources[str(q)]=h
                sources[str(receipt.resolve())]=sha(receipt)
                raw=pd.read_csv(p/'daily.csv',float_precision='round_trip');events=load(p/'reserve_events.json')
                m,d=summarize(raw,events,audit['metrics']['rounds'],audit['metrics']['open_round_net_mtm'],start,arm,version)
                actual=pd.read_csv(p/'reserve_daily.csv',float_precision='round_trip')
                require(d.date.tolist()==actual.date.astype(str).str[:10].tolist(),'real_daily_calendar')
                for field in ['raw_account_equity','net_pnl','trading_account_equity','reserve_balance','cumulative_transfer','transfer_amount','total_account_equity']:
                    require(near(d[field],actual[field]),'real_financial_daily:'+field)
                m['source_path']=str(p);m['independent_receipt']=str(receipt);summaries.append(m);daily.append(d)
                for e in events:event_rows.append(dict(e,start=start,variant=m['variant']))
                if version=='uniform_risk':
                    old=load(Path(prior['jobs'][start+'|'+arm]['path'])/'actual_strategy_settings.json')[0]['actual']
                    now=load(p/'actual_strategy_settings.json')[0]['actual']
                    for k,v in freeze['risk_overrides'].items():
                        require(now[k]==v==.018,'actual_uniform_risk');parameter_deltas.append(dict(start=start,arm=arm,parameter=k,old=old[k],new=now[k]))
    summary=pd.DataFrame(summaries);curves=pd.concat(daily,ignore_index=True);si=summary.set_index(['start','variant'])
    require(len(summary)==92 and len(curves)==141996 and not curves.duplicated(['start','variant','date']).any(),'exact92_141996')
    for start,g in curves.groupby('start'):
        calendars=[tuple(x.date) for _,x in g.groupby('variant')]
        require(len(calendars)==4 and len(set(calendars))==1 and calendars[0][-1]==CUTOFF,'four_fresh_window_calendars')
    paired=pd.DataFrame([pair_metrics(si.loc[(s,a+'_old')],si.loc[(s,a+'_new')],s,a) for s in STARTS for a in ['A','C']])
    cohorts=[]
    for arm in ['A','C']:
        for cohort in ['January','June','combined']:
            for scope in ['complete_ge_1y','observation_lt_1y']:
                q=paired.loc[(paired.arm==arm)&(paired.observation_only==(scope=='observation_lt_1y'))]
                if cohort!='combined':q=q.loc[q.cohort==cohort]
                cohorts.append(dict(arm=arm,cohort=cohort,scope=scope,n=len(q),real_pnl_wins=int(q.real_pnl_gate.sum()),
                    wealth_dd_no_worse=int(q.wealth_dd_gate.sum()),wealth_sharpe_no_lower=int(q.wealth_sharpe_gate.sum()),three_gate_pass=int(q.three_gate_pass.sum()),
                    lower_deposit_windows=int(q.delta_deposits.lt(-1e-6).sum()),equal_deposit_windows=int(q.delta_deposits.abs().le(1e-6).sum()),higher_deposit_windows=int(q.delta_deposits.gt(1e-6).sum())))
    verify_map(sources);output.mkdir(parents=True)
    tables={'summary.csv':summary,'paired.csv':paired,'daily.csv':curves,'cohort_summary.csv':pd.DataFrame(cohorts),'reserve_events.csv':pd.DataFrame(event_rows),'actual_parameter_deltas.csv':pd.DataFrame(parameter_deltas)}
    for name,frame in tables.items():frame.to_csv(output/name,index=False)
    doc=dict(schema='stage011-uniform-risk-comparison-v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),status='INDEPENDENT_REVIEW_PENDING',
        freeze_sha256=sha(freeze_path),financial_source_head=freeze['source_head'],cutoff=CUTOFF,starts=list(STARTS),variants=list(VARIANTS),
        financial_replays=46,reused_baseline_financial_replays=46,variant_windows=92,paired_windows=46,daily_points=len(curves),complete_pairs_per_arm=22,observation_pairs_per_arm=1,
        risk_overrides=freeze['risk_overrides'],source_files_sha256=sources,promotion_decision='NO_PROMOTION',
        account_nav='E/150000: transferred deposits included; untransferred reserve excluded',wealth_nav='W/300000=(300000+true_trading_PnL)/300000',
        warning='Account growth/DD/Sharpe includes external deposits. Economic comparisons use actual PnL and equal-total-budget wealth metrics; no automatic promotion.')
    atomic_json(output/'comparison.json',safe(doc))
    atomic_json(output/'data_manifest.json',dict(files_sha256={str((output/n).resolve()):sha(output/n) for n in [*tables,'comparison.json']}))
    write_window_records(summary,paired,freeze)
    return dict(report=str(output),summary_rows=92,paired_rows=46,daily_points=len(curves))


def formatted(value,kind='money'):
    if value is None or pd.isna(value):return 'N/A'
    if kind=='pct':return f'{float(value):.2f}%'
    if kind=='ratio':return f'{float(value):.3f}'
    return f'{float(value):,.0f}'


def write_window_records(summary,paired,freeze):
    folder=LINE/'stages/stage011_windows';folder.mkdir(exist_ok=True)
    si=summary.set_index(['start','variant']);pi=paired.set_index(['start','arm'])
    fields=[('期末交易权益','account_end_equity','money'),('含入金账户增长','account_growth_pct','pct'),
        ('账户最大回撤','balance_max_dd_pct','pct'),('账户Sharpe','balance_sharpe','ratio'),
        ('真实交易净盈亏','real_trading_net_pnl','money'),('累计补资','total_transferred','money'),
        ('场外余款','off_account_reserve_end','money'),('同30万预算末财富','wealth_end_equity','money'),
        ('同预算收益','wealth_return_pct','pct'),('同预算最大回撤','wealth_max_dd_pct','pct'),('同预算Sharpe','wealth_sharpe','ratio'),
        ('总滑点','total_slippage','money'),('总手续费','total_commission','money'),('总成交次数','modeled_fill_count','money'),
        ('完整合约交易周期数','round_count','money'),('完整周期胜率','round_win_rate_pct','pct'),
        ('平均盈利','round_average_win','money'),('平均亏损绝对值','round_average_loss_abs','money'),
        ('盈亏比','round_payoff_ratio','ratio'),('Profit Factor','round_profit_factor','ratio'),('未平仓净MTM','open_round_net_mtm','money'),
        ('交易权益口径保证金峰值×1.65','trading_margin_peak_pct','pct'),('保证金超过100%天数','trading_margin_over100_days','money')]
    for start in STARTS:
        for arm in ['A','C']:
            old,new=si.loc[(start,arm+'_old')],si.loc[(start,arm+'_new')];p=pi.loc[(start,arm)]
            terminal=load(Path(new.source_path)/'terminal.json');t=datetime.fromisoformat(terminal['completed_at'])
            path=folder/f'{t:%Y%m%d_%H%M}_stage011_{arm}_{start.replace("-","")}.md'
            text=f'# Stage011 {arm}：{start}独立起点风险统一消融\n\n- line_id=futures_weekly_short_ma_slope_gate；运行完成时间{terminal["completed_at"]}；非重要突破，NO_PROMOTION。\n- 新增参数无；仅三项基础风险0.06/0.06/0.025→0.018；删除参数无。原OI×2、方向增强1.5/低量0.5、最低风险1000、资金/信号/风控/退出/执行保持。\n- 150,000交易＋150,000场外备用；每次有效新信号父sizing前按缺口补足，备用不回填。截止{CUTOFF}；实际{new.actual_start}—{new.actual_end}，{int(new.trading_days)}交易日。\n- 新金融仅本候选一次，旧同窗Stage009补资版精确复用；旧回测结果修改/删除均无。2026不足一年只观察。\n- 金融冻结HEAD={freeze["source_head"]}。新源{new.source_path}；旧源{old.source_path}；独审{new.independent_receipt}。\n\n|指标|旧分档补资版|新统一普通风险补资版|\n|---|---:|---:|\n'
            for label,field,kind in fields:text+='|'+label+'|'+formatted(old[field],kind)+'|'+formatted(new[field],kind)+'|\n'
            text+=f'\n真实净利严格提高={bool(p.real_pnl_gate)}，同总预算回撤不差={bool(p.wealth_dd_gate)}，Sharpe不低={bool(p.wealth_sharpe_gate)}，三门同时={bool(p.three_gate_pass)}；只是研究对比，不自动晋级。\n\n备用耗尽：旧{bool(old.reserve_exhausted)}（{old.exhaustion_date or "未耗尽"}），新{bool(new.reserve_exhausted)}（{new.exhaustion_date or "未耗尽"}）。\n\n账户净值E/15万含入金，真实交易盈亏与入金分列；同总预算W/30万不把内部转资作为盈利。调研判断沿冻结CME OI趋势确认及GitHub sizing参考，不能预设高风险档更优。运行前后过拟合风险仍有（反复同历史、窗口重叠）；固定三参数消融有验证价值，不扫参数/起点救参。零手续费、非完整上市/PIT历史证明、静态保证金×1.65、日线next-open及容量/券商购买力限制继承。后续：完整网格和独审汇总后判断，不凭单窗调规则。\n'
            if path.exists():require(path.read_text()==text,'immutable_window_record_changed')
            else:path.write_text(text)


def write_reports(folder,summary,paired,cohorts,figure_names,reviewed):
    state='独立复核通过（有局限）' if reviewed else '独立复核中'
    warning='净值E/150000含已入金、排除场外余款；账户增长/DD/Sharpe受入金影响。真实交易盈亏与补资分列；同30万总预算财富W=E+R用于无外部现金流的经济对比。'
    md=f'# Stage011：三类OI信号统一普通基础风险，对比原补资版\n\n{state}；NO_PROMOTION。截止2026-10-29，23独立起点，46新金融＋46冻结旧对照。2026年初不足一年只观察。\n\n唯一改动：持仓量骤增、放量且持仓量骤增、持仓量下降的基础风险6%/6%/2.5%→1.8%；OI确认×2、增强×1.5/低量×0.5等原规则保留。A无新增价格门，C仅空头底部20%；19品种、无加仓、无多头顶部/MA斜率过滤。\n\n{warning}\n\n'+cohorts.to_markdown(index=False)+'\n\n'
    headers=['起点','版本','期末交易权益','含入金增长','账户DD','账户Sharpe','真实交易净盈亏','累计入金','场外余款','W最大回撤','W Sharpe','滑点','成交次数','胜率','平均盈利','平均亏损','盈亏比','PF']
    rows=[];md+='|'+'|'.join(headers)+'|\n|'+'|'.join(['---']*len(headers))+'|\n'
    for _,m in summary.sort_values(['start','arm','version']).iterrows():
        vals=[m.start+('（观察）' if m.observation_only else ''),LABELS[m.variant],formatted(m.account_end_equity),formatted(m.account_growth_pct,'pct'),formatted(m.balance_max_dd_pct,'pct'),formatted(m.balance_sharpe,'ratio'),
            formatted(m.real_trading_net_pnl),formatted(m.total_transferred),formatted(m.off_account_reserve_end),formatted(m.wealth_max_dd_pct,'pct'),formatted(m.wealth_sharpe,'ratio'),formatted(m.total_slippage),str(int(m.modeled_fill_count)),
            formatted(m.round_win_rate_pct,'pct'),formatted(m.round_average_win),formatted(m.round_average_loss_abs),formatted(m.round_payoff_ratio,'ratio'),formatted(m.round_profit_factor,'ratio')]
        md+='|'+'|'.join(vals)+'|\n';rows.append('<tr data-start="'+m.start+'">'+''.join('<td>'+html.escape(v)+'</td>' for v in vals)+'</tr>')
    md+='\n调研与判断：CME Open Interest将OI用作趋势确认，不能证明较高基础风险必然更优；Backtrader官方GitHub的资金比例与整数手数实现提醒必须真实重新回放资金路径。https://www.cmegroup.com/education/lessons/open-interest ；https://github.com/mementum/backtrader/blob/master/backtrader/sizers/percents_sizer.py\n\n运行前后过拟合风险仍有：同历史反复研究、窗口高度重叠；本次固定三参数回归普通档，不扫参数或挑窗救参。统一风险有结构性验证价值；全窗负结果保留，不自动晋级。零手续费、缓存非完整上市/PIT证明、静态保证金×1.65、日线next-open和容量/券商真实购买力限制继承。\n\n本地离线HTML，未起HTTP。file://自动浏览器安全策略限制仍在，未声称交互验收。\n'
    (folder/'report.md').write_text(md)
    pics=[]
    titles=['2015年初至今：新旧账户净值与回撤','年初独立起点','年中独立起点','实际盈亏与同预算风险差','补资消耗与账户盈亏总览']
    for i,(name,title) in enumerate(zip(figure_names,titles),1):
        data=base64.b64encode((folder/name).read_bytes()).decode()
        pics.append(f'<section id="fig{i}"><h2>{title}</h2><img alt="{title}" src="data:image/png;base64,{data}"></section>')
    options='<option value="all">全部23个起点</option>'+''.join(f'<option value="{s}">{s}</option>' for s in STARTS)
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Stage011统一普通风险与原补资版比较</title><style>body{margin:0;background:#f3f6fa;color:#172235;font:16px/1.65 system-ui,-apple-system,sans-serif}main{max-width:1450px;margin:auto;padding:28px 22px}h1{font-size:28px}h2{font-size:21px}section,.note{background:#fff;padding:20px;border:1px solid #dce3ed;border-radius:14px;margin:18px 0}.note{background:#eaf2fd;border-left:5px solid #2467a6}img{display:block;width:100%;height:auto}.muted{font-size:14px;color:#526177}.scroll{overflow:auto}table{border-collapse:collapse;font-size:13px;white-space:nowrap;width:100%}th,td{padding:9px 12px;border-bottom:1px solid #e3e7ef;text-align:right}th{background:#edf2f8}td:first-child,td:nth-child(2){text-align:left}tr:nth-child(even){background:#f9fbfd}select{font:inherit;padding:6px}a{color:#16528b}nav a{margin-right:18px}</style><main><h1>Stage011 · 三类OI信号统一普通风险，沿用场外补资</h1>'''
    page+=f'<p class="muted">{state} · 截止2026-10-29 · 23起点 × A/C新旧两版 · NO_PROMOTION</p><div class="note">'+warning+'</div><p>仅将三类基础风险6% / 6% / 2.5%统一为1.8%。原OI确认×2、量价增强×1.5/低量×0.5及其他风控均保留。所有版本都是15万交易账户＋最多15万场外补资。</p><nav>'+''.join(f'<a href="#fig{i}">{t}</a>' for i,t in enumerate(titles,1))+'</nav>'
    page+=''.join(pics)+'<section><h2>全部窗口：真实盈亏和入金分列</h2><label>独立起点 <select id="startFilter">'+options+'</select></label><div class="scroll"><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>'
    page+='<section class="muted">固定23个起点独立回放至同截止，2026年初不足一年仅观察；重叠窗口不是独立统计样本或新OOS。历史/PIT、零手续费、静态保证金×1.65、日线next-open、容量与券商实时购买力限制继承。<br>仅固定消融，不扫参数救参；比较有价值，但不自动晋级。图片、表格与筛选脚本全部内嵌，不需要HTTP。自动file://交互未验收。<br>调研参考：<a href="https://www.cmegroup.com/education/lessons/open-interest">CME Open Interest</a>、<a href="https://github.com/mementum/backtrader/blob/master/backtrader/sizers/percents_sizer.py">Backtrader GitHub sizing</a>。</section></main><script>document.getElementById("startFilter").addEventListener("change",function(){document.querySelectorAll("tbody tr").forEach(r=>r.hidden=this.value!=="all"&&r.dataset.start!==this.value);});</script></html>'
    (folder/HTML_NAME).write_text(page)


def render(output=OUT,review=None):
    from stage011_plots import render_five
    output=Path(output);locked=load(output/'data_manifest.json')['files_sha256'];verify_map(locked)
    reviewed=review is not None
    if reviewed:
        r=load(review);require(r['status']=='PASS_WITH_LIMITATIONS' and not r['failures'],'independent_report_review')
        require(r['data_files_sha256']==locked,'exact_reviewed_data')
        verify_map(r['audited_code_sha256'])
    summary=pd.read_csv(output/'summary.csv',float_precision='round_trip');paired=pd.read_csv(output/'paired.csv',float_precision='round_trip');daily=pd.read_csv(output/'daily.csv',float_precision='round_trip');cohorts=pd.read_csv(output/'cohort_summary.csv')
    figures=render_five(summary,paired,daily,reviewed=reviewed);folder=output if reviewed else output/'review_pending';folder.mkdir(exist_ok=True)
    for name,fig in figures.items():fig.savefig(folder/name,dpi=160,bbox_inches='tight');fig.clear()
    write_reports(folder,summary,paired,cohorts,list(figures),reviewed)
    atomic_json(folder/'delivery_receipt.json',dict(status='PASS_WITH_LIMITATIONS' if reviewed else 'INDEPENDENT_REVIEW_PENDING',
        data_files_sha256=locked,figure_files_sha256={str((folder/n).resolve()):sha(folder/n) for n in figures},
        report_files_sha256={str((folder/n).resolve()):sha(folder/n) for n in [HTML_NAME,'report.md']},
        independent_review_sha256=sha(review) if reviewed else None,financial_replays=0,market_downloads=0,production_accesses=0,browser_interaction_verified=False,promotion_decision='NO_PROMOTION'))
    return dict(report=str(folder),reviewed=reviewed)


if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--mode',choices=['build','render'],required=True);a.add_argument('--output',type=Path,default=OUT);a.add_argument('--review',type=Path);a.add_argument('--freeze',type=Path,default=LINE/'stages/stage011_freeze.json');args=a.parse_args()
    print(json.dumps(safe(build(args.freeze,args.output) if args.mode=='build' else render(args.output,args.review)),ensure_ascii=False,indent=2))
