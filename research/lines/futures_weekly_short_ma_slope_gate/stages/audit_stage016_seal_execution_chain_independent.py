"""Seal independent offline execution-chain evidence; no implementation writes."""
from pathlib import Path
import ast,datetime,hashlib,json
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[4];D=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda name:json.loads((D/name).read_text())
verification=read('stage016_execution_chain_independent_locked_attempt002.json')
assert verification['tests']==94 and verification['failures']==verification['errors']==0 and verification['source_unchanged']
for p,s in verification['source_after'].items():assert sha(ROOT/p)==s,p
root_review=read('stage016_root_increment_independent_review.json');runtime_review=read('stage016_runtime_data_v6_independent_review.json')
prior_root=read('stage016_root_increment_admitted_source_freeze.json')
for p,s in prior_root.items():assert sha(ROOT/p)==s,p
pipeline='examples/portfolio_backtesting/qmt_roll_weekly19_live_pipeline.py'
def asts(path,names):
 tree=ast.parse((ROOT/path).read_text());return {node.name:hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest() for node in ast.walk(tree)if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))and node.name in names}
prior_pipeline=asts(pipeline,root_review['pipeline_scoped_function_ast_sha256'])
assert prior_pipeline==root_review['pipeline_scoped_function_ast_sha256']
for p,items in root_review['helper_ast_sha256'].items():assert asts(p,items)==items,p
for name in ['qmt_roll_weekly19_runtime.py','qmt_roll_weekly19_data.py','qmt_roll_weekly19_data_update.py','qmt_roll_official_live_execution_ledger.py']:
 p='examples/portfolio_backtesting/'+name
 assert sha(ROOT/p)==runtime_review['locked_component_source_sha256'][name],name
wrapper=read('stage016_stage907_forwarding_independent_attempt001.json');assert wrapper['exit_code']==0 and wrapper['source_unchanged']
assert sha(ROOT/'examples/portfolio_backtesting/run_qmt_roll_stage907_official_live_readonly_refresh_gate.py')==wrapper['source_after']
recovery=read('stage016_bridge_recovery_independent_attempt001.json');assert recovery['exit_code']==0 and recovery['source_unchanged']
assert sha(ROOT/'examples/portfolio_backtesting/qmt_roll_weekly19_session_bridge.py')==recovery['source_after']['examples/portfolio_backtesting/qmt_roll_weekly19_session_bridge.py']
now=datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
md=D/'20261031_stage016_execution_chain_independent_review.md'
md.write_text(f'''# Stage016 执行整链接线独立条件审查

记录时间：{now}。研究线 futures_weekly_short_ma_slope_gate。结论：PASS_OFFLINE_COMPONENTS_WITH_LIMITATIONS；只接受本次锁源离线技术边界，production_qualified=false、真实来源资格=false。用户已授权迁移和真正场外备用金安排，授权不等于技术资格。

本轮只读 LocalBackend、CLI、ExecutionService、Controller、SessionBridge 和实际 Stage931 API 边界；未修改作者实现、旧冻结证据或Git，未连接CTP/SMTP/银行/网络、未发单、未做金融回放。调研依据为当前源码、原生接口及既有独审原始证据；没有用网上新版本替换本机协议。

## 已确认与修复

发现1项P1：store在os.replace后目录fsync失败，Bridge无条件回滚actor，使磁盘新状态与内存旧状态分叉。原失败脚本和两次日志保留；首次unittest还顺带发现导入的fixture，相关作者fixture局部变量error未误报为实现bug。第二次隔离为1测试/1失败/0error。作者修复后独审4例通过：旧状态读回、新状态读回仍抛原错、读回失败poison、restore失败poison；不确定持久化不返回applied。当前桥SHA 4207284a4c2166d9f6e909e6895f1d0acdd0b007b523050327036a04e9d54474。

最终94次测试调用（78次直接接线作者测试、16次独审）15.137秒，0失败/0错误/0跳过。另3例纯Stage907命令构造通过，合计97次本轮最终验收调用；不是全局去重测试数。独审覆盖过期/漂移authority在runner前阻断、漂移后恢复文件仍撤权、同actor串行和publication互斥、绝对deadline与stop后不重启、typed quota绑定污染/foreign lease、真实partial fill父cap守恒，以及cash_sources伪金额/伪qualified不改变E或磁盘账本。Stage907仅验证参数转发和shell引用，未执行构造的命令。

## 接线结论

首次来源/生产manifest/qualification/activation/daily receipt/私有ledger/行情代次闸门位于连接前；当前实现不能由JSON的qualified或sender字段生成能力。旧material source与实际production HEAD分列，不能把祖先关系当精确HEAD资格。现金引用是待核实证据，只有实际provider和完整现金链可增加E。

同一Runtime actor贯穿会话；真实query/readiness等待不持actor锁，callback/store提交用同锁。当前owner的非cash_sources配置或文件权限变化会永久撤权，需新owner恢复。CLI时限同时限制runner存活与实际授权expiry；stop_pending不提前关桥。Controller纯发布的API零与并发执行器未知计数分开。

最终API边界核真实父delivery和子单remaining，不接受签100却风险50仍发100，也不允许拆小子单绕过父cap。typed私有quota reader证明实际lease/payload/service/connection/child全集；普通JSON列表不是等价能力。931七个quota/native/deferred函数AST逐项匹配18:57参考，当前整文件精确绑定13604c4d15bc5dc60002a78d1851d0b39e5ad4129783491e9815fa7fe4de4f16；不继承18:35旧V6整文件等价。

此前两封已接受组件证据不可变引用：runtime/data/V6审查69eee5fe…与root增量审查84ecb050…。本轮核实原9root文件、原runtime/data/updater/ledger哈希和9个支持/邮件函数AST仍精确相同；只增补新的session/API接线，未重复金融或无关整批测试。

## 必须保留的生产阻断与能力边界

- 无本轮实际已接纳capture authority registry、实际TD/MD原生样本、真实账户/成交恢复E2E；root报告TCP超时不是CTP身份验证。本审查没有亲自连接。
- 最终结算statement的vendor解析与现金最终性证据仍缺；raw settlement全文collector只证明原始chunk完整，不能证明最终日切。load_cashflow_day_close继续stub/fail-closed，跨TradingDay缺链不能增加E或新开，减风险路径保留。
- TransferSerial自动producer尚未安装；添加raw路径、邮件建议、余额恢复都不是实际到账证明。
- 第一child真实Trade领先旧四查询positions时，后续child明确requires_source_reconciliation；保持严格quote/state门，不保证同batch自动续发或无人工恢复。真实查询/受控恢复后才能重新取得完整来源。
- 尚未完成不可变新release、真实production qualification/activation、master readback或安装/loaded scheduler证明；这里的0项未修复scope内P0/P1/P2不等于生产review通过。
- 私有typed ledger逐record checksum不是抗同owner篡改的hashchain；实际源与宿主权限/资格证据仍必需。离线通过不证明真实延迟/可用性/容量。

本轮未调alpha、金额或阈值，不构成新的收益过拟合；Stage014同历史选择/零手续费/静态margin和容量局限保留，经济NO_PROMOTION不重写。继续有价值，因为资金真实性、数量守恒和崩溃一致性是固定策略执行前置。没有新增回测结果，金融指标均N/A。
''')
evidence_names=['stage016_execution_chain_independent_locked_attempt002.json','stage016_execution_chain_independent_locked_attempt002.log','stage016_execution_chain_independent_attempt001.log','audit_stage016_execution_chain_independent.py','stage016_bridge_atomicity_independent_finding_attempt001.json','audit_stage016_bridge_atomicity_independent.py','audit_stage016_bridge_atomicity_independent_v2.py','stage016_bridge_atomicity_independent_attempt001.log','stage016_bridge_atomicity_independent_attempt002.log','audit_stage016_bridge_recovery_independent.py','stage016_bridge_recovery_independent_attempt001.json','stage016_bridge_recovery_independent_attempt001.log','audit_stage016_stage907_forwarding_independent.py','stage016_stage907_forwarding_independent_attempt001.json','stage016_stage907_forwarding_independent_attempt001.log','20261031_stage016_execution_session_manifest.json','20261031_2002_stage016_execution_session_integration.md','stage016_runtime_data_v6_independent_review.json','stage016_root_increment_independent_review.json','stage016_root_increment_admitted_source_freeze.json']
sources=dict(verification['source_after'],**prior_root)
for name in ['qmt_roll_weekly19_data.py','qmt_roll_weekly19_data_update.py','qmt_roll_weekly19_friday_advice.py','qmt_roll_weekly19_friday_report.py','qmt_roll_weekly19_daily_receipt.py']:
 p='examples/portfolio_backtesting/'+name;sources[p]=sha(ROOT/p)
rec=dict(schema='stage016.independent-execution-chain-review.v1',recorded_at=now,line_id='futures_weekly_short_ma_slope_gate',reviewer='independent_reviewer',status='PASS_OFFLINE_COMPONENTS_WITH_LIMITATIONS',accepted=True,accepted_scope='Current pinned offline component and process-local execution wiring only; not real source or production qualification',failures=[],open_findings=[],severity_open=dict(P0=0,P1=0,P2=0),fixed_findings=[dict(id='STAGE016_BRIDGE_POST_REPLACE_P1',severity='P1',status='FIXED_IN_PINNED_SOURCE',verification='4 independent recovery/poison tests; original RED evidence preserved')],source_qualified_by_real_capture=False,production_qualified=False,statement_finality_qualified=False,real_registry_created=False,real_ctp_connected=False,real_bank_cashflow_verified=False,real_smtp_sent=False,real_order_submitted=False,financial_replays=0,git_index_modified=False,master_promoted=False,production_installed=False,final_verification=dict(total_test_invocations=97,locked_chain_test_invocations=94,independent_chain_and_recovery=16,additional_independent_stage907=3,failures=0,errors=0,skipped=0,counts_are_not_globally_deduplicated=True,source_drift=False,author194_run_not_counted_as_reviewer_run=True,root_full_selected_not_claimed_by_this_receipt=True),source_files_sha256=sources,source_manifest_sha256=verification['manifest_sha256'],current_931_function_ast_sha256=verification['current_931_ast_sha256'],old_1835_whole_file_equivalence_claimed=False,prior_root_source_same_bytes=True,prior_support_pipeline_function_ast_same=True,prior_support_pipeline_function_ast_sha256=prior_pipeline,prior_runtime_data_hashes_same=True,source_policy='Actual files pinned, not cached prior V6 whole-file acceptance',evidence_files_sha256={n:sha(D/n) for n in evidence_names},chinese_record_sha256=sha(md),production_blockers=['No actual accepted new authority registry/capture/CTP E2E proof','Vendor final statement parser and final cash-day-close proof unavailable; day-close loader remains fail-closed','Automatic TransferSerial capture producer not installed','Partial native child fill before original four-query position snapshot requires real source reconciliation; same-batch automatic continuation unproven','Immutable release, actual qualification/activation/master readback/install and loaded scheduler not established'],limitations=['Offline synthetic authority fixtures do not prove production source authenticity','Current helper/file pins must be rebound after source changes','Per-record checksum/private typed reader is not a same-owner adversarial hashchain','No real latency, host readiness, capacity or broker acceptance proof','Stage014 economic NO_PROMOTION and original research limitations unchanged'],overfitting=False,continuing_value=True)
p=D/'stage016_execution_chain_independent_review.json';p.write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n');print(p);print(sha(p));print(md);print(sha(md))
