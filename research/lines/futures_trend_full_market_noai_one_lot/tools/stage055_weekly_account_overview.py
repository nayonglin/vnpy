"""Readonly weekly-long candidate overview with an explicitly bound A baseline.

Reuse Stage042 validation and its Stage032 AST plot; never replay finance.
"""
import argparse
import html
import importlib.util
import json
import math
import os
from pathlib import Path

BASE_SOURCE=Path(__file__).with_name('stage042_account_overview.py')
_spec=importlib.util.spec_from_file_location('weekly_overview_stage042',BASE_SOURCE)
base=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(base)
BASELINE_COMMIT='87487e32d36a443942f612ac7eeef71ede9ea46a'
WEEKLY_POLICY=dict(periods=[5,10,20,40],comparison='ma5>ma10>ma20>ma40',
    source='causal_main_unadjusted_accepted_clean',signal_phase='completed_week_at_signal_close',
    execution_phase='completed_week_strictly_before_fill_day',minimum_valid_weeks=40,
    missing_week='fail_closed_do_not_drop',applies_to='all_long_open_including_rollover',
    exclude_env_probe=True,shorts_and_all_closes_unchanged=True)
WEEKLY_FILES=('weekly_main_features.csv','weekly_signal_audit.csv','weekly_execution_audit.csv')
WEEKLY_DISCLOSURE=('周线开多候选：仅所有开多（含移仓重开、旧单重挂）增加MA5>MA10>MA20>MA40严格排列；'
    '不足40周、均线相等、缺失或坏周一律拒绝开多，不删除坏周来压缩样本。'
    '门槛使用品种未复权因果主力完成周收盘（accepted-clean），换月价差仍可能影响排列。'
    'canonical逐笔K线保留实际合约/背景主力拼接的原显示合同，图上周MA未必与门槛序列一致；不修改图上MA数组来追门槛。'
    '真实门槛值见weekly_signal_audit.csv、weekly_execution_audit.csv及trades.csv中的stage051_weekly_signal_snapshot和stage051_weekly_open_snapshot。'
    '信号收盘可用当天刚完成周，实际开盘仅可用严格早于成交日的完成周，且同时核原信号授权。'
    '空头开仓、全部平仓及env_probe环境输入不加周线限制；组合现金路径仍可间接改变空头成交。'
    '只加开仓门，不因周线转弱强平已有多仓。保留原生风险预算、开盘复核、无AI、无品种数上限和每品种最多1手。'
    '日线近似及全部原研究边界继续有效。')
COMPARISON_FIELDS=(('initial_capital','初始资金','元'),('end_balance','期末权益','元'),
    ('total_return','总收益','%'),('max_ddpercent','最大回撤','%'),('sharpe_ratio','Sharpe',''),
    ('payoff_ratio','净盈亏比',''),('profit_factor','盈利因子',''),('win_rate_pct','净胜率','%'),
    ('completed_episodes','完整交易','笔'),('total_trade_count','成交次数','笔'),
    ('total_commission','手续费','元'),('total_slippage','滑点','元'))


def check_output(source,parent,baseline,output):
    base.check_output(source,parent,output);base.check_output(baseline,parent,output)
    base.require(Path(source).resolve()!=Path(baseline).resolve(),'baseline_is_candidate')


def parent_hashes(parent):
    summary=json.loads((parent/'summary.json').read_text())
    hashes=summary.get('artifact_sha256',{})
    base.require('index.html' in hashes,'parent_artifact_binding_missing')
    for name,expected in hashes.items():
        base.require(base.sha(base.safe_member(parent,name))==expected,'parent_artifact_hash_mismatch:'+name)
    return hashes


def comparison_rows(a,c):
    rows=[]
    for key,label,unit in COMPARISON_FIELDS:
        av,cv=a.get(key),c.get(key)
        # Optional absent statistics stay absent; never fabricate zero.
        for value in (av,cv):
            base.require(value is None or (not isinstance(value,bool) and isinstance(value,(int,float))
                and math.isfinite(value)),'invalid_comparison_metric:'+key)
        rows.append(dict(key=key,label=label,unit=unit,baseline=av,candidate=cv,
            delta=cv-av if av is not None and cv is not None else None))
    return rows


def load_bundle(source,parent,baseline):
    b=base.load_bundle(source,parent);baseline=Path(baseline).resolve()
    m=b['manifest'];c=b['metrics'];f=b['facts']
    for identity in (m,c):
        base.require(identity.get('long_weekly_filter') is True,'weekly_filter_required')
        base.require(identity.get('weekly_policy')==WEEKLY_POLICY,'weekly_policy_mismatch')
        base.require(identity.get('baseline_commit')==BASELINE_COMMIT,'baseline_commit_mismatch')
    base.require(c.get('actual_long_weekly_violations')==0,'weekly_open_violations')
    for name in WEEKLY_FILES:base.require(name in f['source_hashes'],'weekly_evidence_unbound:'+name)
    a_manifest=json.loads((baseline/'manifest.json').read_text());a_sha=base.sha(baseline/'manifest.json')
    base.require(m.get('baseline_run_manifest_sha256')==a_sha,'baseline_manifest_mismatch')
    base.require(a_manifest['run_id']==baseline.name,'baseline_run_id_mismatch')
    a_bound=base.verify_hashes(baseline,a_manifest);a=json.loads((baseline/'summary.json').read_text())
    for identity in (a_manifest,a):
        base.require(identity.get('long_weekly_filter') is not True,'baseline_already_weekly')
        for flag in (*base.BUDGET_FLAGS,'position_count_limit_removed'):
            base.require(identity.get(flag) is True,'baseline_budget_policy:'+flag)
        base.require(identity.get('mode')=='daily-proxy','baseline_mode_mismatch')
    base.require(a_manifest['parameters']==m['parameters'],'baseline_parameters_mismatch')
    for key in ('analysis_start','analysis_end','initial_capital'):
        base.require(a[key]==c[key],'baseline_interval_or_capital_mismatch:'+key)
    for key in ('start','end'):
        base.require(a_manifest.get(key)==m.get(key),'baseline_manifest_interval_mismatch:'+key)
    for name in ('market_daily.csv','mapping.csv','contract_metadata.csv','code_snapshot/stage039_risk_budget_candidate.py','code_snapshot/stage041_open_risk.py'):
        if name in a_bound:base.require(a_bound[name]==f['source_hashes'].get(name),'baseline_input_changed:'+name)
    p_hashes=parent_hashes(b['parent'])
    f.update(weekly_policy=dict(WEEKLY_POLICY),weekly_disclosure=WEEKLY_DISCLOSURE,long_weekly_filter=True,
        baseline_commit=BASELINE_COMMIT,baseline_directory=str(baseline),baseline_run_id=a_manifest['run_id'],
        baseline_manifest_sha256=a_sha,baseline_hashes=a_bound,baseline_metrics=a,
        comparison=comparison_rows(a,c),comparison_interpretation='同参数、同区间冻结A/C描述性比较，不作为晋级结论；未做多起点或样本外验证。',
        parent_artifact_sha256=p_hashes,generator_sha256=base.sha(Path(__file__)),overview_adapter_sha256=base.sha(BASE_SOURCE))
    b.update(baseline=baseline,baseline_manifest=a_manifest)
    return b


def make_page(bundle,plot,output):
    page=base.make_page(bundle,plot,output);f=bundle['facts'];esc=html.escape
    title='周线开多候选 · 日线近似 · 全市场原风险预算最多1手'
    old='<title>全市场无AI风险预算最多一手 · 资金与回撤</title>'
    base.require(page.count(old)==1,'base_title_contract_changed')
    page=page.replace(old,'<title>'+esc(title)+'</title>',1)
    page=page.replace('<h1>整体资金曲线与回撤</h1>','<h1>'+esc(title)+' · 资金与回撤</h1>',1)
    def fmt(value,unit,delta=False):
        if value is None:return '未提供'
        suffix='个百分点' if delta and unit=='%' else unit
        return (f'{value:+,.4f}' if delta else f'{value:,.4f}')+suffix
    rows=''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in (r['label'],fmt(r['baseline'],r['unit']),
        fmt(r['candidate'],r['unit']),fmt(r['delta'],r['unit'],True)))+'</tr>' for r in f['comparison'])
    links=' · '.join('<a href="'+esc(os.path.relpath(bundle['source']/name,Path(output).resolve()),quote=True)+'">'+esc(name)+'</a>' for name in (*WEEKLY_FILES,'trades.csv'))
    policy=('<section class="policy" id="weekly-policy">'+esc(WEEKLY_DISCLOSURE)+'<p>冻结周线依据：'+links+'</p></section>'
        '<section class="policy" id="baseline-comparison"><h2>A/C 冻结核心指标</h2><p>'+esc(f['comparison_interpretation'])+
        ' 下方曲线仅绘制C；A为未加本周线门的原风险预算基线。</p><div style="overflow-x:auto"><table style="width:100%;text-align:right;border-spacing:12px">'
        '<thead><tr><th>指标</th><th>A 基线</th><th>C 周线候选</th><th>C − A</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
        '<p>显式基线：'+esc(f['baseline_run_id'])+'；manifest SHA256：'+f['baseline_manifest_sha256']+'</p></section>')
    marker='<section class="cards">';base.require(page.count(marker)==1,'base_cards_contract_changed')
    return page.replace(marker,policy+marker,1)


def verify_unchanged(b):
    f=b['facts']
    for root,manifest,digest,bound in ((b['source'],b['manifest'],f['source_manifest_sha256'],f['source_hashes']),
        (b['baseline'],b['baseline_manifest'],f['baseline_manifest_sha256'],f['baseline_hashes'])):
        base.require(base.sha(root/'manifest.json')==digest,'input_manifest_changed_during_render')
        base.require(base.verify_hashes(root,manifest)==bound,'input_changed_during_render')
    base.require(base.sha(b['parent']/'summary.json')==f['parent_recap_summary_sha256'],'parent_changed_during_render')
    base.require(parent_hashes(b['parent'])==f['parent_artifact_sha256'],'parent_changed_during_render')
    for path,digest in ((Path(__file__),f['generator_sha256']),(BASE_SOURCE,f['overview_adapter_sha256']),
        (base.PLOT_SOURCE,f['plot_source_sha256'])):base.require(base.sha(path)==digest,'display_code_changed_during_render')


def generate(source,parent,baseline,output):
    source,parent,baseline,output=(Path(p).resolve() for p in (source,parent,baseline,output))
    check_output(source,parent,baseline,output);b=load_bundle(source,parent,baseline)
    fig,plot=base.make_plot(b);page=make_page(b,plot,output);verify_unchanged(b)
    output.mkdir(parents=True);base.save_png(b,output)
    (output/'index.html').write_text(page,encoding='utf-8');(output/'figure.json').write_text(fig.to_json(),encoding='utf-8')
    base.pd.DataFrame({'date':b['d'].date,'equity':b['equity'],'high_watermark':b['peak'],
        'drawdown_amount':b['dd_amount'],'drawdown_pct':b['dd_pct']}).to_csv(output/'equity_drawdown.csv',index=False)
    verify_unchanged(b);f=b['facts']
    f['artifact_sha256']={p.name:base.sha(p) for p in output.iterdir() if p.is_file()}
    f['artifact_bytes']={p.name:p.stat().st_size for p in output.iterdir() if p.is_file()}
    (output/'summary.json').write_text(json.dumps(f,ensure_ascii=False,indent=2)+'\n')
    return f


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','parent','baseline','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();print(json.dumps(generate(a.source,a.parent,a.baseline,a.output),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
