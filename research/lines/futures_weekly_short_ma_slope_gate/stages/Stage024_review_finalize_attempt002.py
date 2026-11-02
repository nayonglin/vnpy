"""Read-only final CI/source binding; no test, broker or production execution."""
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,subprocess,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[4];D=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cp=D/'Stage024_selected_attempt001.json';lp=D/'Stage024_implementation_lock.json';sp=D/'Stage024_review_root_source_review.json';tp=D/'Stage024_review_root_locked_attempt001.json'
c=json.loads(cp.read_bytes());l=json.loads(lp.read_bytes());s=json.loads(sp.read_bytes());t=json.loads(tp.read_bytes());checks=[]
def ck(name,cond):
 checks.append(dict(name=name,passed=bool(cond)))
 if not cond:raise AssertionError(name)
ck('CI_pin',sha(cp)=='49c0697747023e17659fbb49c8404174f4b640f92322ed72a163cee550e25302')
ck('lock_pin',sha(lp)=='22f65abf799c64e2f7c54c11f5764b3b27395d9da94bd4c9e49eb18e7087f0b0')
ck('96_suites_298_sources',c['suite_count']==96 and c['critical_file_count']==l['critical_file_count']==298)
ck('CI_success_offline_zero_drift',c['exit_code']==0 and c['critical_source_changed']==[]and c['source_sha256_before']==c['source_sha256_after']and c['accepted_offline_only']is True and c['production_qualified']is False and c['financial_replay']is False and c['ctp_protocol_login_attempted']is False)
ck('zero_actual_native_api',all(type(c[k])is int and c[k]==0 for k in ['actual_order_api_called_count','actual_send_order_api_called_count','actual_cancel_order_api_called_count']))
ck('CI_and_lock_map',l['source_sha256']==c['source_sha256_after']and len(l['source_sha256'])==298 and l['CI_sha256']==sha(cp)and l['source_unchanged_since_CI']is True and l['production_qualified']is False)
actual={}
for name,pin in l['source_sha256'].items():
 p=Path(name);ck('safe_source_path:'+name,not p.is_absolute()and '..'not in p.parts and not name.endswith('.env')and 'vt_setting.json'not in name and 'smtp.local'not in name)
 actual[name]=sha(R/p);ck('current_source:'+name,actual[name]==pin)
ck('reviewed_source_subset_matches',all(actual.get(name)==pin for name,pin in s['source_files_sha256'].items()))
ck('76_targeted_13_independent_green',t['status']=='OFFLINE_COMPONENT_TESTS_PASS'and t['reported_total_test_invocations']==76 and t['independent_test_invocations']==13 and not t['source_drift']and all(r['exit_code']==0 for r in t['runs']))
xpath=Path(c['junit_path']);raw=xpath.read_bytes();ck('JUnit_no_external_entities',b'<!DOCTYPE'not in raw and b'<!ENTITY'not in raw);cases=list(ET.fromstring(raw).iter('testcase'))
counts=dict(tests=len(cases),failures=sum(q.find('failure')is not None for q in cases),errors=sum(q.find('error')is not None for q in cases),skipped=sum(q.find('skipped')is not None for q in cases))
ck('JUnit_2405_clean',counts==dict(tests=2405,failures=0,errors=0,skipped=0))
ck('CI_JSON_counts_match_JUnit',c['counts']==counts)
refs=[cp,lp,sp,tp,D/'Stage024_review_root_source_review.md',D/'Stage024_review_root_findings_attempt001.json',xpath,Path(c['log_path']),Path(__file__),D/'Stage024_review_finalize_attempt001_failed.md']
for run in t['runs']:refs.append(R/run['log'])
for suffix in ['peak','hedge','stale_week','terminal']:
 refs.extend([D/f'Stage024_review_root_{suffix}_probe_attempt001.py',D/f'Stage024_review_root_{suffix}_probe_attempt001.log'])
refs.append(D/'Stage024_review_root_adversarial_attempt001.py')
result=copy.deepcopy(s);result.pop('limits',None)
result.update(schema='stage024.independent.offline-acceptance.v1',generated_at_utc=datetime.now(timezone.utc).isoformat(),status='PASS_WITH_LIMITATIONS',accepted=True,scope='complete locked Stage024 source and final offline engineering acceptance only',final_full_ci_acceptance=True,full_ci_pending=False,source_qualified=False,actual_account_initialized=False,activated=False,installed=False,promoted_master=False,ci_source_commit=c['source_commit'],observed_head_at_review=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),review_binds='Exact source bytes; a later source/release commit and actual production evidence require release/delivery-chain binding.',source_files_sha256=actual,critical_file_count=298,suite_count=96,full_CI=dict(path=str(cp),sha256=sha(cp),JUnit_path=str(xpath),JUnit_sha256=sha(xpath),counts=counts,passed=2405,source_drift=[]),implementation_lock=dict(path=str(lp),sha256=sha(lp)),evidence_files_sha256={str(p):sha(p)for p in refs},checks=checks,check_count=len(checks),failures=[],findings=[],severity_counts=dict(P0=0,P1=0,P2=0),targeted_test_note='76 targeted invocations include13 independent and63 author component/equivalence tests. Do not add them to the overlapping full selected CI count.',limitations=[
'Final offline engineering acceptance is not proof that m4 material has been frozen/qualified/installed/activated or a real position adopted.',
'Synthetic test authorities only exercise conditional semantics; private JSON/hash consistency is not real broker/provider authenticity.',
'Actual fixed vendor metadata, fresh new-source native broker evidence and final production qualification/manifest/activation/exact stable HEAD/runtime/data/scheduler require separate actual evidence.',
'The09:04 old-source unqualified diagnostic cannot be re-stamped or have producer hashes relabeled to qualify the new source.',
'No new financial replay, parameter search or out-of-sample evidence is asserted. Existing research limitations remain.',
'Root future documentation/release manifests and real external captures are excluded to avoid hash cycles.'],adapter_attempt_history=['Finalizer attempt001 stopped before writing a final receipt: independent JUnit derived passed count was compared against JSON total-key tests. Both showed2405; attempt002 uses the actual tests/failures/errors/skipped schema. No test/source/CI data changed or reran.'])
out=D/'Stage024_review_acceptance.json';ck('new_receipt_path',not out.exists());result['check_count']=len(checks);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
md=D/'Stage024_review_acceptance.md';md.write_text('# Stage024 最终离线独立验收\n\nPASS_WITH_LIMITATIONS，accepted=true；剩余P0/P1/P2均0。完整96套件2405通过、0失败/错误/跳过，独立解析JUnit与CI摘要一致；298项critical实物SHA逐项等于CI before、after和最终implementation lock，无漂移。\n\n另76次定向调用全绿，含13项独立反例/正例和63项作者组件/equivalence测试；与完整CI有重叠，不相加冒充更多unique tests。原三项P1、RED与独立断言保留：接管E0高水位、unsupported hedge类型、旧一周保护源已修复并原脚本复跑通过。AtomicCutover验证cash+保护runtime同笔保存，重复不重建，失败无半状态。最终汇总适配器曾误比较passed与tests键，未写最终回执；按CI原格式更正，未重跑CI/金融或改源码。\n\n接受用户授权下的明确新管理cohort：真实E0保留，E0−150000仅为启动前盈余，R150000/T0守恒；成本来自同源原生OpenCost与已核乘数/手数，不造历史开仓日期、peak或旧保护。默认空仓入口和未来原来源、现金、行情及执行闸门保留，初始化不产生decision、订单或邮件。\n\n仅离线工程验收，不代表m4已冻结、实际provider已qualified、真实仓位已接管或生产已安装/激活。真实新source捕获、metadata、qualification/manifest/activation、stable HEAD、runtime/data readiness与scheduler仍须实际证据；旧9:04诊断不能重贴为新来源。不新增自动银行和最终日结解析要求。未连接CTP/SMTP、未金融回放、未订单/撤单或生产/Git index修改。\n\n过拟合：否，只审确定性迁移边界，无alpha调参；继续有价值：是，后续按真实新source与生产资格链推进。\n')
print(json.dumps(dict(receipt=str(out),sha256=sha(out),markdown_sha256=sha(md),checks=len(checks),CI_counts=counts,critical_count=298,status=result['status'],production_qualified=False)))
