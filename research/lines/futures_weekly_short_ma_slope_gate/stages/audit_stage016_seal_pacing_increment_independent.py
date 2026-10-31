"""Seal only pacing and new 931 pin; preserve prior review unchanged."""
from pathlib import Path
import ast,datetime,hashlib,json
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[4];D=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda n:json.loads((D/n).read_text())
oldpath=D/'stage016_execution_chain_independent_review.json';assert sha(oldpath)=='99bf6d1fa19f535229a194fade43034c4dd14fee341fe884aa102b3b1eece4ab';old=read(oldpath.name)
source='examples/portfolio_backtesting/run_qmt_roll_stage931_official_live_ctp_submit_adapter.py';current=sha(ROOT/source);assert current=='ac3176c8752fd49c8527953deed6a2bef8ff1e9305327dfe86b33136f4e06c10'
other={f:s for f,s in old['source_files_sha256'].items()if f!=source}
for f,s in other.items():assert sha(ROOT/f)==s,f
manifest_path=D/'20261031_stage016_execution_selected_repair_manifest.json';manifest=json.loads(manifest_path.read_text())
for item in manifest['files']:assert sha(ROOT/item['path'])==item['sha256'],item['path']
tree=ast.parse((ROOT/source).read_text());all_ast={n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()for n in ast.walk(tree)if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))and n.name in manifest['current_931_function_ast_sha256']}
assert all_ast==manifest['current_931_function_ast_sha256']
assert all(all_ast[name]==value for name,value in old['current_931_function_ast_sha256'].items())
for n in ['stage016_pacing_family_independent_attempt003.json','stage016_pacing_boundaries_independent_attempt001.json','stage016_pacing_targeted_independent_attempt001.json']:
 v=read(n);assert v['exit_code']==0 and v['source_unchanged']
first_path=Path('/private/tmp/weekly19_selected_final_attempt001.json');first=json.loads(first_path.read_text());assert first['suite_count']==88 and first['counts']==dict(tests=2254,failures=2,errors=0,skipped=0)and first['critical_source_changed']==[]
first_copy=D/'stage016_pacing_original_full_selected_observed.json';first_copy.write_bytes(first_path.read_bytes())
now=datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
md=D/'20261031_stage016_pacing_increment_independent_review.md'
md.write_text(f'''# Stage016 查询节拍修复增量独审

时间：{now}。line_id=futures_weekly_short_ma_slope_gate。PASS_OFFLINE_INCREMENT_WITH_LIMITATIONS；实际来源、最终statement和production资格仍false。旧整链独审JSON 99bf6d1f…逐字不改，本记录只增量绑定当前931源码及查询等待边界；不是新的金融回放。

## 观察、确定发现与原因界限

root首轮完整CI的88套件2254项为2252通过/2失败，critical281项前后无漂移；不是全绿。两个失败分别为seal的final_order_query_pacing_timeout，以及历史C9 AI fixture未显式绑定旧身份触发weekly disabled。后者只补测试中的C9 profile和历史AI material，正式weekly guard和配置未放宽。作者此前精准重跑/加probe的seal曾通过，原始失败没有逐次monotonic轨迹，因此不能确定宣称原CI失败由本竞态造成；仅可说行为时序相容。

作者先对order/position/common三处用scripted clock确认双读跨next_allowed误超时。独审继续发现trade和position-detail两处遗漏：last=.1、next1.2、clock .2→1.199999→1.200001、budget8秒，仍在0 API时报pacing_timeout。独审attempt001为3测试2失败1通过。扩展attempt002又确认trade首次poll跨过允许点和deadline后仍发1次FakeApi查询：clock .2→1.200001，budget.5即deadline.7；4测试3失败1通过。两次失败时931 SHA均为e3fc8a10427f387195d0c0f8ed4f7c28ec47fdb43ed1971943620963e548597a，实际测试前后相同。原脚本/日志/JSON全部保留。

当前作者修复五个family循环，每轮用同一now判断允许时刻及remaining，保留1.1秒默认节拍、至少1秒门、原预算和sender/授权；trade新增post-pacing真实deadline门，在reqid/API之前阻断已经逾期的新查询。

## 独立复验与哈希

- 原独立v2反例4例全绿，旧trade/detail误超时及晚查询均关闭。
- 新独立五helper时钟测试7例全绿：四类查询跨允许时刻、直接跨过deadline、等待过程中deadline先到、order/position的min1s和harddeadline、common helper的节拍及真实超时。
- 精确运行作者9个新增回归和首次失败的seal case，10例20.413秒全绿，0跳过，源码前后无漂移。

本增量共21次成功调用，不是全局去重总数，不与旧97或作者137相加冒称完整CI通过。root修复后完整88套件重跑结果由root另行封存，本记录不声称其已通过。

当前整931 SHA为ac3176c8752fd49c8527953deed6a2bef8ff1e9305327dfe86b33136f4e06c10。五helper AST已精确绑定；此前七个quota/native/deferred关键函数AST逐一完全相同。旧独审源map中除931之外全部实际文件哈希仍相同。没有原13604整931字节快照，不声称已独立证明全文件在五函数之外逐字不变，也不借用旧V6整文件身份。新source需要当前完整CI/正式source qualification另验。

## 保留边界

本轮scope内P0/P1/P2未修复数为0，但真实capture authority、最终cash-day-close解析、自动TransferSerial producer、真实CTP/银行/SMTP/订单验证、不可变release/activation/master及生产安装仍未建立。native partial fill领先旧四查询的剩余child仍需真实source reconciliation；不承诺同batch自动继续。所有测试为本地FakeApi/合成callback epoch，查询计数只是fixture计数，绝不当真实provider资格。

本次不调alpha或风控参数，不构成新过拟合；继续价值在消除可确定复现的误超时和越deadline只读查询。原Stage014经济NO_PROMOTION及研究局限保留。无新增回测结果，金融指标N/A。未修改作者实现、旧审查、Git/index、生产，未连接任何外部服务。
''')
names=['audit_stage016_pacing_family_independent.py','audit_stage016_pacing_family_independent_v2.py','stage016_pacing_family_independent_attempt001.json','stage016_pacing_family_independent_attempt001.log','stage016_pacing_family_independent_attempt002.json','stage016_pacing_family_independent_attempt002.log','stage016_pacing_family_independent_attempt003.json','stage016_pacing_family_independent_attempt003.log','audit_stage016_pacing_boundaries_independent.py','stage016_pacing_boundaries_independent_attempt001.json','stage016_pacing_boundaries_independent_attempt001.log','stage016_pacing_targeted_independent_attempt001.json','stage016_pacing_targeted_independent_attempt001.log','stage016_pacing_targeted_independent_attempt001.xml','stage016_pacing_original_full_selected_observed.json','20261031_stage016_execution_selected_repair_manifest.json','20261031_2023_stage016_execution_selected_repair.md','stage016_execution_chain_independent_review.json']
rec=dict(schema='stage016.independent-pacing-increment-review.v1',recorded_at=now,line_id='futures_weekly_short_ma_slope_gate',status='PASS_OFFLINE_INCREMENT_WITH_LIMITATIONS',accepted=True,failures=[],open_findings=[],severity_open=dict(P0=0,P1=0,P2=0),fixed_findings=[dict(id='PACING_FALSE_TIMEOUT_FAMILY',severity='P1',scope='five same-now wait loops; independent trade/detail failures and author three-helper RED preserved'),dict(id='PACING_LATE_TRADE_QUERY',severity='P1',scope='post-pacing actual deadline zero-FakeApi gate')],source_qualified_by_real_capture=False,statement_finality_qualified=False,production_qualified=False,real_ctp_connected=False,real_bank_cashflow_verified=False,real_smtp_sent=False,real_order_submitted=False,financial_replays=0,git_index_modified=False,master_promoted=False,production_installed=False,prior_execution_chain_receipt_sha256=sha(oldpath),prior_whole_931_sha256=old['source_files_sha256'][source],current_whole_931_sha256=current,old_receipt_unchanged=True,prior_931_pin_not_reused_for_current_source=True,other_prior_source_hashes_same=True,current_source_files_sha256=dict(other,**{source:current,'tests/test_stage931_ctp_readiness.py':sha(ROOT/'tests/test_stage931_ctp_readiness.py'),'tests/test_stage947_production_support_launcher.py':sha(ROOT/'tests/test_stage947_production_support_launcher.py')}),current_931_function_ast_sha256=all_ast,seven_prior_quota_native_deferred_ast_unchanged=True,old_13604_whole_source_snapshot_available=False,full_file_non_pacing_delta_independently_proven=False,verification=dict(independent_tests=11,targeted_author_boundary_and_original_seal_tests=10,total_successful_test_invocations=21,failures=0,errors=0,skipped=0,source_drift=False,counts_not_globally_deduplicated=True),first_complete_selected=dict(suites=88,tests=2254,passed=2252,failures=2,source_drift=False,exact_original_seal_failure_cause_proven=False),full_selected_after_repair='ROOT_OWNED_NOT_CLAIMED_BY_THIS_INCREMENT',author137_not_counted_as_independent_run=True,evidence_files_sha256={n:sha(D/n)for n in names},external_first_ci_evidence_sha256={str(Path('/private/tmp')/('weekly19_selected_final_attempt001'+suffix)):sha(Path('/private/tmp')/('weekly19_selected_final_attempt001'+suffix))for suffix in ('.json','.log','.xml')},chinese_record_sha256=sha(md),production_blockers=old['production_blockers'],limitations=old['limitations']+['Original first CI seal lacks monotonic trace; exact causal attribution remains unknown','No original 13604 whole931 snapshot; only current whole pin and prior seven AST equivalence are proven'],overfitting=False,continuing_value=True)
p=D/'stage016_pacing_increment_independent_review.json';p.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n');print(p);print(sha(p));print(md);print(sha(md))
