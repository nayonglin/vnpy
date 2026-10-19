"""0.5% account-equity risk overview, with the user's exact-contract N baseline.

Strict new financial-source adapter; original Plotly AST and PNG drawing nodes
are reused. Only two declared PNG text constants are changed in a new namespace.
"""
import argparse,ast,copy,hashlib,html,json
from datetime import datetime
from pathlib import Path
from types import FunctionType
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import stage042_account_overview as base
import stage055_weekly_account_overview as compare
import stage071_fractional_recap as frac
from stage062_contract_weekly_overview import WEEKLY_POLICY

BASELINE_SHA=frac.BASELINE_SHA
PNG_LITERALS={'全市场无AI｜风险预算最多一手｜整体资金与回撤':'全市场无AI｜每笔总权益0.5%风险｜整体资金与回撤',
    '｜风险预算恢复/开盘复核｜日线近似｜含':'｜0.5%权益风险/开盘整单复核｜日线近似｜含'}
DISCLOSURE=frac.NOTE+' 原N为用户指定基线，取消1手上限但没有取消资金、保证金和native数量减量约束。'
make_plot=base.make_plot


def png_function():
    path=Path(base.__file__);tree=ast.parse(path.read_text());original=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='save_png');adapted=copy.deepcopy(original);counts={key:0 for key in PNG_LITERALS}
    class TextOnly(ast.NodeTransformer):
        def visit_Constant(self,node):
            if isinstance(node.value,str) and node.value in PNG_LITERALS:
                counts[node.value]+=1;node.value=PNG_LITERALS[node.value]
            return node
    TextOnly().visit(adapted);base.require(all(value==1 for value in counts.values()),'PNG_literal_contract_changed')
    reverse={value:key for key,value in PNG_LITERALS.items()};restored=copy.deepcopy(adapted)
    class Restore(ast.NodeTransformer):
        def visit_Constant(self,node):
            if isinstance(node.value,str) and node.value in reverse:node.value=reverse[node.value]
            return node
    Restore().visit(restored);base.require(ast.dump(restored)==ast.dump(original),'PNG_nontext_AST_changed')
    namespace=dict(base.__dict__);exec(compile(ast.fix_missing_locations(ast.Module(body=[adapted],type_ignores=[])),str(path),'exec'),namespace)
    digest=lambda node:hashlib.sha256(ast.dump(node).encode()).hexdigest()
    return namespace['save_png'],dict(source_sha256=base.sha(path),literal_changes=PNG_LITERALS,original_ast_sha256=digest(original),adapted_ast_sha256=digest(adapted),only_declared_text_literals_changed=True)


def load_bundle(source,parent,baseline):
    source,parent,baseline=(Path(p).resolve() for p in (source,parent,baseline));identity=json.loads((source/'manifest.json').read_text());bound=base.verify_hashes(source,identity);metrics=json.loads((source/'summary.json').read_text());frac.validate_policy(identity,metrics)
    base.require(identity['run_id']==source.name,'run_id_mismatch');base.require(identity.get('mode')==metrics.get('mode')=='daily-proxy','unsupported_mode')
    base.require(identity.get('long_weekly_filter') is True and metrics.get('long_weekly_filter') is True and identity.get('weekly_policy')==metrics.get('weekly_policy')==WEEKLY_POLICY,'exact_weekly_policy_mismatch')
    parent_summary=json.loads((parent/'summary.json').read_text());source_hash=base.sha(source/'manifest.json')
    base.require(parent_summary['source_manifest_sha256']==source_hash and parent_summary['backtest_metrics']==metrics,'parent_source_metrics_mismatch');parent_hashes=compare.parent_hashes(parent)
    baseline_hash=base.sha(baseline/'manifest.json');base.require(baseline_hash==identity['baseline_run_manifest_sha256']==BASELINE_SHA,'baseline_N_manifest_mismatch')
    bm=json.loads((baseline/'manifest.json').read_text());bb=base.verify_hashes(baseline,bm);bmetrics=json.loads((baseline/'summary.json').read_text())
    base.require(bm['run_id']==baseline.name and bm.get('weekly_policy')==bmetrics.get('weekly_policy')==WEEKLY_POLICY,'baseline_N_weekly_identity_mismatch')
    before,after=bm['parameters'],identity['parameters'];changes={key:(before.get(key),after.get(key)) for key in set(before)|set(after) if before.get(key)!=after.get(key)}
    base.require(changes=={'max_position_size':(1,2147483647),'stage068_risk_fraction':(None,.005)},'unapproved_parameter_changes')
    for key in ('analysis_start','analysis_end','initial_capital'):base.require(bmetrics[key]==metrics[key],'baseline_N_interval_mismatch:'+key)
    for key in ('start','end'):base.require(bm.get(key)==identity.get(key),'baseline_N_manifest_interval_mismatch:'+key)
    for name in ('market_daily.csv','mapping.csv','contract_metadata.csv','trading_calendar.csv'):
        if name in bb:base.require(bound.get(name)==bb[name],'shared_input_changed:'+name)
    d=pd.read_csv(source/'daily.csv',float_precision='round_trip');dates=pd.to_datetime(d.date,errors='raise');equity=pd.to_numeric(d.equity,errors='raise');capital=float(metrics['initial_capital'])
    base.require(len(d)>0 and len(d)==metrics['total_days'] and dates.is_monotonic_increasing and not dates.duplicated().any(),'daily_dates_or_count_invalid')
    base.require(d.date.iloc[-1]==metrics['analysis_end'] and dates.iloc[0]>=pd.Timestamp(metrics['analysis_start']),'daily_interval_mismatch')
    base.require(np.isfinite(equity).all() and np.isfinite(capital) and capital>0,'nonfinite_equity')
    base.require(np.allclose(equity,capital+d.net_pnl.cumsum(),rtol=0,atol=1e-5) and np.allclose(equity,d.balance,rtol=0,atol=1e-6),'equity_accounting_mismatch')
    peak=equity.cummax().clip(lower=capital);dd_amount=equity-peak;dd_pct=(equity/peak-1)*100
    for key,value in [('highlevel',peak),('drawdown',dd_amount),('ddpercent',dd_pct)]:base.require(np.allclose(d[key],value,rtol=0,atol=1e-7),'daily_metric_mismatch:'+key)
    for key,value in [('end_balance',equity.iloc[-1]),('total_return',(equity.iloc[-1]/capital-1)*100),('max_ddpercent',dd_pct.min()),('max_drawdown',dd_amount.min())]:frac.near(metrics[key],value,'source_summary_metric_mismatch:'+key)
    closed=pd.read_csv(source/'closed_episodes.csv',float_precision='round_trip');trades=pd.read_csv(source/'trades.csv',float_precision='round_trip');residual=json.loads((source/'residual_open_positions.json').read_text())
    base.require(len(closed)==metrics['completed_episodes'] and len(residual)==metrics['residual_open_positions'],'complete_or_residual_count_mismatch')
    if 'total_trade_count' in metrics:base.require(len(trades)==metrics['total_trade_count'],'trade_count_mismatch')
    trough=int(dd_pct.idxmin());indices=equity.loc[:trough][equity.loc[:trough].eq(peak.iloc[trough])].index;peak_date=d.date.iloc[int(indices[-1])] if len(indices) else 'initial_capital'
    facts=dict(run_id=identity['run_id'],start=d.date.iloc[0],end=d.date.iloc[-1],analysis_start=metrics['analysis_start'],points=len(d),initial_capital=capital,end_equity=float(equity.iloc[-1]),
        total_return_pct=metrics['total_return'],max_drawdown_pct=float(dd_pct.min()),max_drawdown_amount=float(dd_amount.min()),max_drawdown_peak_date=peak_date,max_drawdown_trough_date=d.date.iloc[trough],
        ending_drawdown_pct=float(dd_pct.iloc[-1]),sharpe_ratio=metrics['sharpe_ratio'],completed_episodes=len(closed),total_fills=len(trades),residual_open_positions=len(residual),
        residual_positions=residual,residual_open_dates=sorted({str(r.get('date') or r.get('datetime',''))[:10] for r in residual}),mode=metrics['mode'],source_boundaries=metrics.get('boundaries',[]),
        source_directory=str(source),parent_recap_directory=str(parent),source_manifest_sha256=source_hash,source_daily_sha256=bound['daily.csv'],source_summary_sha256=bound['summary.json'],source_hashes=bound,
        parent_recap_summary_sha256=base.sha(parent/'summary.json'),parent_artifact_sha256=parent_hashes,baseline_directory=str(baseline),baseline_manifest_sha256=baseline_hash,baseline_hashes=bb,
        baseline_commit=frac.BASELINE_COMMIT,baseline_metrics=bmetrics,comparison=compare.comparison_rows(bmetrics,metrics),fractional_risk_policy=frac.FRACTIONAL_POLICY,
        strategy_rerun=False,market_download=False,production_access=False,generator_sha256=base.sha(Path(__file__)),plot_source_sha256=base.sha(base.PLOT_SOURCE),
        dependency_sha256={name:base.sha(Path(__file__).with_name(name)) for name in ('stage042_account_overview.py','stage055_weekly_account_overview.py','stage062_contract_weekly_overview.py','stage071_fractional_recap.py')},
        created_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat())
    return dict(source=source,parent=parent,baseline=baseline,manifest=identity,baseline_manifest=bm,metrics=metrics,d=d,dates=dates,equity=equity,capital=capital,peak=peak,dd_amount=dd_amount,dd_pct=dd_pct,trough=trough,facts=facts)


def make_page(b,plot,output):
    namespace={**base.make_page.__globals__,'BUDGET_DISCLOSURE':DISCLOSURE};fn=FunctionType(base.make_page.__code__,namespace,base.make_page.__name__);page=fn(b,plot,output)
    replacements={'全市场无AI风险预算最多一手 · 资金与回撤':'合约自身周线 · 0.5%总权益风险 · 整手定仓资金与回撤',
        '整体资金曲线与回撤':'0.5%总权益风险 · 多手资金曲线与回撤',
        '全市场 · 无AI选品 · 原风险预算后最多1手 · 无4品种上限':'全市场 · 无AI选品 · 单笔总权益0.5%风险 · 整手向下定仓 · 无品种数上限'}
    for old,new in replacements.items():base.require(old in page,'overview_text_contract_changed:'+old);page=page.replace(old,new,1)
    rows=''.join('<tr>'+''.join('<td>'+html.escape(value)+'</td>' for value in (r['label'],'未提供' if r['baseline'] is None else f'{r["baseline"]:,.4f}{r["unit"]}',
        '未提供' if r['candidate'] is None else f'{r["candidate"]:,.4f}{r["unit"]}','未提供' if r['delta'] is None else f'{r["delta"]:+,.4f}'+('个百分点' if r['unit']=='%' else r['unit'])))+'</tr>' for r in b['facts']['comparison'])
    table=('<section class="policy"><h2>用户选定基线N → 新0.5%多手版本</h2><p>相同区间/本金/合约自身周门，仅按冻结风险定仓合同比较；不作为晋级结论。下图仅新版本。</p>'
        '<div style="overflow-x:auto"><table style="width:100%;text-align:right;border-spacing:12px"><thead><tr><th>指标</th><th>基线N</th><th>0.5%新版本</th><th>差值</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
        '<p>基线manifest SHA256：'+b['facts']['baseline_manifest_sha256']+'</p></section>')
    return page.replace('<section class="cards">',table+'<section class="cards">',1)


def verify_unchanged(b):
    f=b['facts']
    for root,m,digest,entries in ((b['source'],b['manifest'],f['source_manifest_sha256'],f['source_hashes']),(b['baseline'],b['baseline_manifest'],f['baseline_manifest_sha256'],f['baseline_hashes'])):
        base.require(base.sha(root/'manifest.json')==digest and base.verify_hashes(root,m)==entries,'source_or_baseline_changed')
    base.require(base.sha(b['parent']/'summary.json')==f['parent_recap_summary_sha256'] and compare.parent_hashes(b['parent'])==f['parent_artifact_sha256'],'parent_changed')
    base.require(base.sha(Path(__file__))==f['generator_sha256'] and base.sha(base.PLOT_SOURCE)==f['plot_source_sha256'],'display_source_changed')
    for name,digest in f['dependency_sha256'].items():base.require(base.sha(Path(__file__).with_name(name))==digest,'display_dependency_changed:'+name)


def generate(source,parent,baseline,output):
    source,parent,baseline,output=(Path(p).resolve() for p in (source,parent,baseline,output));base.check_output(source,parent,output);base.check_output(baseline,parent,output)
    b=load_bundle(source,parent,baseline);fig,plot=make_plot(b);page=make_page(b,plot,output);png,proof=png_function();b['facts']['png_adapter']=proof;verify_unchanged(b)
    output.mkdir(parents=True);png(b,output);(output/'index.html').write_text(page);(output/'figure.json').write_text(fig.to_json())
    pd.DataFrame({'date':b['d'].date,'equity':b['equity'],'high_watermark':b['peak'],'drawdown_amount':b['dd_amount'],'drawdown_pct':b['dd_pct']}).to_csv(output/'equity_drawdown.csv',index=False)
    verify_unchanged(b);f=b['facts'];f['artifact_sha256']={p.name:base.sha(p) for p in output.iterdir() if p.is_file()};f['artifact_bytes']={p.name:p.stat().st_size for p in output.iterdir() if p.is_file()}
    (output/'summary.json').write_text(json.dumps(f,ensure_ascii=False,indent=2)+'\n');return f


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','parent','baseline','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=generate(a.source,a.parent,a.baseline,a.output);print(json.dumps({k:r[k] for k in ('run_id','points','end_equity','artifact_sha256')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
