"""Exact traded-contract weekly overview; explicit original-A and previous-main-C.

Reuse frozen Stage055/042 display functions through an isolated policy namespace.
No shared module globals, plotting code or financial source are changed.
"""
import argparse,html,json,os
from pathlib import Path
from types import FunctionType
import stage055_weekly_account_overview as old

WEEKLY_POLICY={**old.WEEKLY_POLICY,'source':'exact_traded_contract_unadjusted_accepted_clean'}
WEEKLY_FILES=('weekly_contract_features.csv','weekly_signal_audit.csv','weekly_execution_audit.csv')
PREVIOUS_MAIN_COMMIT='12f9d3500305ad0da47e092c8c39177459d228ec'
WEEKLY_DISCLOSURE=('合约周线候选：仅开多含移仓/旧单重挂新增MA5>MA10>MA20>MA40，使用当前交易合约自身accepted-clean未复权完成周收盘，不用主力连续或其他合约补历史。'
    '不足40周、缺周、坏周或均线相等均不开多，坏周保留在MA窗口。信号收盘可用当天刚完成周，实际开盘仅用严格早于成交日的完成周，并核原信号授权。'
    '逐笔周K改为交易合约自身OHLC/MA；其余周期保留canonical实际合约/背景主力上下文原合同，不能混作合约周线证据。'
    '门槛值见weekly_signal_audit.csv、weekly_execution_audit.csv、trades.csv的stage059_weekly_signal_snapshot与stage059_weekly_open_snapshot。'
    '不因周线走弱强平；空头开仓、全部平仓及env_probe不增此条件，组合现金路径可间接改变空头成交。保留原生风险预算、开盘复核、最多1手、无AI、无品种数上限及全部日线近似边界。')


def delegated(function):
    """Invoke original function bytecode with isolated source-policy constants."""
    namespace={**function.__globals__,'WEEKLY_POLICY':WEEKLY_POLICY,'WEEKLY_FILES':WEEKLY_FILES,
        'WEEKLY_DISCLOSURE':WEEKLY_DISCLOSURE,'__file__':__file__}
    return FunctionType(function.__code__,namespace,function.__name__,function.__defaults__,function.__closure__)


def check_output(source,parent,baseline,previous,output):
    old.check_output(source,parent,baseline,output);old.base.check_output(previous,parent,output)
    old.base.require(len({Path(p).resolve() for p in (source,baseline,previous)})==3,'comparison_sources_not_distinct')


def load_bundle(source,parent,baseline,previous):
    b=delegated(old.load_bundle)(source,parent,baseline);f=b['facts'];previous=Path(previous).resolve()
    pm=json.loads((previous/'manifest.json').read_text());p=json.loads((previous/'summary.json').read_text());digest=old.base.sha(previous/'manifest.json')
    for identity in (b['manifest'],b['metrics']):
        old.base.require(identity.get('previous_weekly_main_commit')==PREVIOUS_MAIN_COMMIT,'previous_main_commit_mismatch')
        old.base.require(identity.get('previous_weekly_main_manifest_sha256')==digest,'previous_main_manifest_mismatch')
    bound=old.base.verify_hashes(previous,pm)
    old.base.require(pm['run_id']==previous.name,'previous_main_run_id_mismatch')
    for identity in (pm,p):
        old.base.require(identity.get('long_weekly_filter') is True and identity.get('weekly_policy')==old.WEEKLY_POLICY,'previous_main_weekly_policy_mismatch')
        for flag in (*old.base.BUDGET_FLAGS,'position_count_limit_removed'):
            old.base.require(identity.get(flag) is True,'previous_main_budget_policy:'+flag)
    old.base.require(pm['parameters']==b['manifest']['parameters'],'previous_main_parameters_mismatch')
    for key in ('analysis_start','analysis_end','initial_capital'):old.base.require(p[key]==b['metrics'][key],'previous_main_interval_mismatch:'+key)
    f.update(previous_main_directory=str(previous),previous_main_manifest_sha256=digest,previous_main_hashes=bound,
        previous_main_metrics=p,previous_main_comparison=old.comparison_rows(p,b['metrics']),previous_main_commit=PREVIOUS_MAIN_COMMIT,
        weekly_adapter_sha256=old.base.sha(Path(old.__file__)))
    b.update(previous_main=previous,previous_main_manifest=pm)
    return b


def make_page(b,plot,output):
    page=delegated(old.make_page)(b,plot,output).replace('周线开多候选','合约周线候选').replace('C 周线候选','C 合约周线候选')
    f=b['facts'];esc=html.escape
    rows=''.join('<tr><td>'+esc(r['label'])+'</td><td>'+esc('未提供' if r['baseline'] is None else f'{r["baseline"]:,.4f}{r["unit"]}')+
        '</td><td>'+esc('未提供' if r['candidate'] is None else f'{r["candidate"]:,.4f}{r["unit"]}')+'</td></tr>' for r in f['previous_main_comparison'])
    section=('<section class="policy"><h2>上一主力周线版本 vs 合约周线候选</h2><p>固定同参数/区间，仅描述冻结差异，不作为晋级结论。下图仅当前合约周线候选。</p>'
        '<div style="overflow-x:auto"><table style="width:100%;text-align:right;border-spacing:12px"><thead><tr><th>指标</th><th>上一主力周线版本</th><th>当前合约周线候选</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
        '<p>上一主力周线 manifest SHA256：'+f['previous_main_manifest_sha256']+'；交付 commit：'+PREVIOUS_MAIN_COMMIT+'</p></section>')
    marker='<section class="cards">';old.base.require(page.count(marker)==1,'base_cards_contract_changed')
    return page.replace(marker,section+marker,1)


def verify_unchanged(b):
    delegated(old.verify_unchanged)(b);f=b['facts']
    old.base.require(old.base.sha(b['previous_main']/'manifest.json')==f['previous_main_manifest_sha256'],'previous_main_changed')
    old.base.require(old.base.verify_hashes(b['previous_main'],b['previous_main_manifest'])==f['previous_main_hashes'],'previous_main_changed')
    old.base.require(old.base.sha(Path(old.__file__))==f['weekly_adapter_sha256'],'stage055_dependency_changed')


def generate(source,parent,baseline,previous,output):
    source,parent,baseline,previous,output=(Path(p).resolve() for p in (source,parent,baseline,previous,output))
    check_output(source,parent,baseline,previous,output);b=load_bundle(source,parent,baseline,previous)
    fig,plot=old.base.make_plot(b);page=make_page(b,plot,output);verify_unchanged(b)
    output.mkdir(parents=True);old.base.save_png(b,output)
    (output/'index.html').write_text(page);(output/'figure.json').write_text(fig.to_json())
    old.base.pd.DataFrame({'date':b['d'].date,'equity':b['equity'],'high_watermark':b['peak'],
        'drawdown_amount':b['dd_amount'],'drawdown_pct':b['dd_pct']}).to_csv(output/'equity_drawdown.csv',index=False)
    verify_unchanged(b);f=b['facts'];f['artifact_sha256']={p.name:old.base.sha(p) for p in output.iterdir() if p.is_file()}
    f['artifact_bytes']={p.name:p.stat().st_size for p in output.iterdir() if p.is_file()}
    (output/'summary.json').write_text(json.dumps(f,ensure_ascii=False,indent=2)+'\n');return f


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','parent','baseline','previous-main','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();f=generate(a.source,a.parent,a.baseline,a.previous_main,a.output)
    print(json.dumps({k:f[k] for k in ('run_id','points','end_equity','source_manifest_sha256','artifact_sha256')},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
