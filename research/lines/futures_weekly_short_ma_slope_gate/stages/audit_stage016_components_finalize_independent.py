"""Source-bound offline component gates only; never qualifies real providers."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[4];STAGES=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,v):
    assert not p.exists(),str(p)
    p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--attempt',required=True);a=ap.parse_args();assert re.fullmatch('[0-9]{3}',a.attempt)
    base='stage016_components_independent_final_attempt'+a.attempt;attempt=STAGES/(base+'.json');assert not attempt.exists()
    components=['broker_provider_v2','friday_report']
    funding_receipt=STAGES/'stage016_funding_v2_independent_review.json';previous_funding=json.loads(funding_receipt.read_text())
    assert previous_funding['status']=='PASS_OFFLINE_COMPONENT_WITH_LIMITATIONS' and previous_funding['tests']==95
    for q,h in previous_funding['source_files_sha256'].items():assert sha(q)==h,q
    outputs={c:STAGES/('stage016_'+c+'_independent_review.json')for c in components};md=STAGES/'20261031_stage016_three_components_independent_review.md'
    assert not any(p.exists()for p in [*outputs.values(),md])
    names=['qmt_roll_weekly19_funding.py','qmt_roll_weekly19_funding_store.py','qmt_roll_weekly19_broker_evidence.py',
      'run_ctp_stage174_readonly_probe.py','qmt_roll_official_live_broker_account_snapshot.py',
      'qmt_roll_official_live_late_retry_fill.py','qmt_roll_official_execution_profile.py','qmt_roll_weekly19_friday_report.py']
    files=[ROOT/'examples/portfolio_backtesting'/n for n in names]
    files += [ROOT/'tests'/n for n in ['test_weekly19_external_funding.py','test_weekly19_broker_evidence.py','test_weekly19_friday_report.py','test_stage174_query_bundle.py','test_official_live_broker_account_snapshot.py']]
    files += [Path(__file__),*[STAGES/n for n in ['audit_stage016_funding_independent.py','audit_stage016_funding_v2_independent.py','audit_stage016_provider_report_independent.py','audit_stage016_openat_independent.py']]]
    before={str(p):sha(p)for p in files};cmd=[str(ROOT/'.py311/bin/python'),'-B']
    def unit(pattern):return cmd+['-m','unittest','discover','-s','tests','-p',pattern,'-v']
    specs=[('broker_provider_v2','author',unit('test_weekly19_broker_evidence.py'),31),
      ('broker_provider_v2','stage174_regression',unit('test_stage174_query_bundle.py'),22),
      ('broker_provider_v2','account_regression',unit('test_official_live_broker_account_snapshot.py'),25),
      ('broker_provider_v2','independent',cmd+[str(STAGES/'audit_stage016_provider_report_independent.py'),'provider'],11),
      ('friday_report','author',unit('test_weekly19_friday_report.py'),20),
      ('friday_report','independent',cmd+[str(STAGES/'audit_stage016_provider_report_independent.py'),'report'],13)]
    results=[]
    for component,label,command,minimum in specs:
        log=STAGES/(base+'_'+component+'_'+label+'.log');assert not log.exists()
        v=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        log.write_text(v.stdout);m=re.search(r'Ran (\d+) tests in ([0-9.]+)s',v.stdout)
        result=dict(component=component,label=label,argv=command,exit_code=v.returncode,tests=int(m[1])if m else None,
          seconds=float(m[2])if m else None,log=str(log),log_sha256=sha(log));results.append(result)
        if v.returncode or not m or int(m[1])<minimum or not v.stdout.rstrip().endswith('OK'):
            write_new(attempt,dict(status='FAILED_TEST_ATTEMPT',results=results,source_files_sha256_before=before,
              source_files_sha256_after={str(p):sha(p)for p in files},financial_runs=0,real_CTP_connections=0,real_SMTP_calls=0))
            print(json.dumps({'status':'FAILED_TEST_ATTEMPT','failed':result,'attempt':str(attempt)}));return 1
    after={str(p):sha(p)for p in files}
    if after!=before:
        write_new(attempt,dict(status='SOURCE_DRIFT_DURING_TESTS',results=results,before=before,after=after));return 1
    now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();n=sum(x['tests']for x in results)
    suites={c:[x for x in results if x['component']==c]for c in components};counts={c:sum(x['tests']for x in suites[c])for c in components}
    new_tests=n;counts['funding_v2']=previous_funding['tests'];n+=previous_funding['tests']
    write_new(attempt,dict(schema='stage016_source_bound_component_tests_v1',status='PASS_OFFLINE_TESTS',created_at=now,
      tests=n,new_tests=new_tests,previously_accepted_funding_tests=95,previous_funding_receipt_sha256=sha(funding_receipt),component_tests=counts,results=results,source_files_sha256=before,source_hashes_before_after_equal=True,
      real_CTP_connections=0,bank_calls=0,real_SMTP_calls=0,financial_runs=0))
    initial=STAGES/'stage016_components_independent_findings_attempt001.json';findings=json.loads(initial.read_text())['findings']
    for f in findings:f.update(resolution='CLOSED_BY_IMPLEMENTER_AND_INDEPENDENT_REGRESSION',unresolved=False)
    text=f"""# Stage016 三组件独立复审

时间：{now}；line_id=futures_weekly_short_ma_slope_gate；新迁移树只新增独审stage/反例，不改实现、原Stage014、生产、Git index/commit。没有金融、真实CTP/银行/SMTP或订单调用。

结论：三个组件PASS_OFFLINE_COMPONENT_WITH_LIMITATIONS，组件未解决P0/P1/P2均0。资金V2 {counts['funding_v2']}、provider及既有只读查询/账户回归 {counts['broker_provider_v2']}、报告/outbox {counts['friday_report']}，共{n} tests GREEN/exit0。其中新执行{new_tests}，资金95项复用先前独审且逐项重核其源SHA，未无故重跑。完整命令、秒数、关闭后日志SHA及源码前后相同证明见{attempt.name}。计数是组件测试运行数，不是独立经济样本。所有账户/银行/native回报/transport均手工fake，production_qualified=false；真实provider/最终日切/到账E2E/全生产链未接受。

资金V2：建议不是债务，真实E>=floor时pending不额外阻开，部分到账达到floor不强补旧余款，未用R继续场外；未知Deposit/Withdraw仍拒。当前gap不同只能request_refresh_required不可操作，完整现金链退休旧cap后新attempt。退休不复活R/不删receipt，原admission confirmed或recovery-retired跨source/generation不重补；过期请求可收齐名义日切链后retire，不延长expiry。独审从Git09e7e07e8实际V1源码造partial账本，验证旧身份/现金/request/receipt全保留、revision+1的单CAS升级、旧同版WAL恢复、变异迁移/降级拒绝；25旧安全反例+15 V2/首创锁反例独立通过。V1源码与旧接受证据不改。

Provider：5 mandatory直接语义源publish/load同时绑定，wrong/missing及额外declared代码pin逐项核验；raw reqid/connection generation/last/error/查询与native时间/金额/名义TradingDay/私有artifact绑定。Balance已含MTM，不再加PositionProfit；真实fill价量取native，OrderSysID唯一映rawOrder和ledger intent，不能用caller completed_volume。SHFE1/3/4映business close并保留broker_offset/native flag，唯一原始order/trade方向与flag必须一致；未知enum拒绝。银行query sent和callback独立fresh，原生发生不得晚于承载callback。默认require_production_qualification=true以及final day-close缺源门仍实际阻断；collector/instrument仅fake reqQryTransferSerial、异常恢复验证，不是真实银行/CTP取证。

报告：独审旧30k/E100k实际gap50k仍可操作的P1已修；公开funding函数无修改重核当前E/R/本周native IDs/source/request/rid/cap，金额变化或source漂移只核对不可操作，缺actionable不默认true。正例确认当前合法绑定30k建议确实actionable=true，排除全阻断假通过；此字段是条件建议，不是实际委托资格。旧pending无新rec仍展示、E恢复不欠款、过周旧source不当本周信号、过期/stale/rawhash/foreign currency/身份等边界通过。

Outbox：preview不调用transport；release/week一次，uncertain或发后最终状态未写完保持sending/unknown、不盲重试；明确blocked_before_send可重试。全路径逐dir O_NOFOLLOW、0700/0600、flock/fsync保留。两个并发caller首次创建锁必须安全；发送器全是假函数，真实邮件服务/全局生产资格/outbox接线未验收。

初始2P1+3P2和attempt001失败保留在stage016_components_independent_findings_attempt001.json及其引用日志，最终逐项close，不抹失败。Mac27.0并发首次openat(O_CREAT)同名锁的探针20次6失败，对照不同名/绝对路径/安全O_EXCL创建后打开已有文件各20次0失败。实现保留安全边界避开该平台路径，资金和outbox独立并发反例通过；未预建锁掩盖，未修改系统，也不声称所有文件系统/掉电情形已证明。[Python锁文档](https://docs.python.org/3.11/library/fcntl.html)、[os.replace](https://docs.python.org/3.11/library/os.html#os.replace)、[同类问题上游源码修复](https://github.com/entireio/cli/commit/9c18f31b23a62749b804718125b17c236420a28a)只作参考，本机反例为主要证据；未升级运行库。

条件接受：上游必须提供真实稳定的native admission，仅在新信号批次建议；真实source authority须另证账户/release/原始现金流/权威日切/完整性，不可用自洽hash或verified字段替代；state CAS成功持久化后才能发布/放新开；broker Available/保证金/报价/交易时段/持仓与全局资格门仍独立。平仓/减风险不能误经open资金门。未知款、退休旧付款晚到、过期到账和跨日缺链保持blocked。银行流水若无native request ID，caller选request_id只是输入，不是原始因果证明；真实adapter必须另证BankSerial对原请求归属，不得将退休旧付款并入新request。

当前没有accepted capture authority、最终cashflow statement parser或真实到账E2E，全部组件/formatter都仍production_qualified=false。默认闸门实际阻断，不把永久block说成资金生产功能完成。没有金融新结果，历史NO_PROMOTION及风险保留。对这些SHA下已测离线守恒/恢复/一致性/报告边界置信度较高；真实来源、实际到账与生产全链未建立置信度。开始/结束过拟合：组件审查否，不看收益不扫参；原历史选择风险仍在。继续价值：是，下一步是真实证据与全消费者/新release资格，不是凭测试绿灯晋升。
"""
    md.write_text(text)
    evidence={str(p):sha(p)for p in [funding_receipt,attempt,md,initial,STAGES/'stage016_provider_report_independent_attempt001.json',STAGES/'stage016_provider_report_independent_attempt001.log',STAGES/'stage016_openat_independent_probe.json']}
    groups={'funding_v2':['DARWIN_FIRST_OPENAT_LOCK'],'broker_provider_v2':['PROVIDER_DIRECT_SOURCE_CLOSURE','PROVIDER_UNKNOWN_FILL_ENUM','BANK_QUERY_CALLBACK_FRESHNESS'],'friday_report':['REPORT_STALE_ADVICE','DARWIN_FIRST_OPENAT_LOCK']}
    for c in components:
        write_new(outputs[c],dict(schema='stage016_'+c+'_independent_component_review_v2',created_at=now,component=c,
          scope='source_bound_offline_component_only',status='PASS_OFFLINE_COMPONENT_WITH_LIMITATIONS',review_completed=True,
          accepted_for_offline_component=True,accepted_for_real_provider=False,accepted_for_real_cash_E2E=False,
          accepted_for_production_qualification=False,production_qualified=False,P0=0,P1=0,P2=0,failures=[],tests=counts[c],
          suites=suites[c],source_files_sha256=before,source_hashes_before_after_equal=True,
          closed_findings=[f for f in findings if f['id']in groups[c]],initial_findings_sha256=sha(initial),
          evidence_files_sha256=evidence,chinese_review=str(md),chinese_review_sha256=sha(md),
          preserved_v1_checkpoint='09e7e07e8',preserved_provider_v1_checkpoint='1231a7fa6',
          qualification_missing=['accepted actual source authority','final day-close cashflow parser and complete chain','actual bank serial to original request correlation','real funding/mail/execution E2E and new production release/activation/install'],
          actions=dict(financial_runs=0,real_CTP_connections=0,real_bank_calls=0,real_SMTP_calls=0,real_order_calls=0,
            production_writes=0,implementation_writes_by_reviewer=0,Git_index_changes_by_reviewer=0,commits_by_reviewer=0),
          auditor_source_sha256=sha(__file__)))
    for p,h in {**before,**evidence}.items():assert sha(p)==h,p
    print(json.dumps({'status':'PASS_OFFLINE_COMPONENT_WITH_LIMITATIONS','tests':n,'counts':counts,
      'production_qualified':False,'receipts':{str(p):sha(p)for p in outputs.values()},'chinese_review_sha256':sha(md),
      'attempt':str(attempt),'attempt_sha256':sha(attempt)},ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
