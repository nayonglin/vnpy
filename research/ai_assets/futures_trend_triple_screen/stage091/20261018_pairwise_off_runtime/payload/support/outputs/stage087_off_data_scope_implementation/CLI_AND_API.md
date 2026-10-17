# Stage087 确切接口（已实现，当前无真实owner）

Scope入口：tools/stage087_off_data_scope.py；provider入口：tools/stage087_off_data_provider.py。
均用 .py311/bin/python。下列占位符不是已生成owner或已启动PID，不应原样执行。

## 真实owner

root在实际runner启动/run_context存在且观察ps -ww lstart+args之后签不可变JSON，交付绝对path与SHA。
schema=stage087_off_owner_v1；必需arm(A_OFF|B_OFF)、attempt=1、run_id、account_output、wait_root、runner_path、runner_sha256、engine_pid、process_identity、run_started_at、source_fingerprints、fixture_only=false。
account_output固定LINE/outputs/stage065_pairwise_off_account/<arm>，wait_root=account_output/data_wait，runner_path固定tools/stage065_run_pairwise_off.py。
run_context_path/run_context_sha256、preflight_path/preflight_sha256、execution_readiness_path/execution_readiness_sha256均为实际绝对path/SHA；context.writer=stage065_account_checkpoint.py，金融runner从context/preflight.source_bindings取。
data_scope_review_path/data_scope_review_sha256必须是未来真正独立review：independent_review=true、p0_findings=p1_findings=0、source_bindings恰两个087新文件绝对path→{sha256,bytes}。实现者本receipt不满足该独立门，不能拿来开跑。
source_fingerprints必须含两个087文件、021、022、087合同及实际新输入；context/preflight也必须显式绑定两个087源。所有文件不可变。
可选cache_receipts=[{receipt_path,receipt_sha256}]：root精确白名单旧052/048/043/046独立交付；只对实际target匹配才重资格，不继承commit。可选cache_daily_packets=[{packet_dir,terminal_sha256}]：明确既有087普通daily来源，可跨owner只读继承原origin；同owner成功daily snapshot自动按实际后续日重资格。075fixture始终拒绝。

## CLI

scope --role resolve --owner OWNER --owner-sha256 SHA --request ACTUAL_REQUEST --request-file-sha256 SHA
scope --role review --owner OWNER --owner-sha256 SHA --request ACTUAL_REQUEST --request-file-sha256 SHA --packet-dir PACKET --terminal-sha256 SHA
scope --role drive --owner OWNER --owner-sha256 SHA --batch-id batch001 --max-connections 4 --budget-seconds 3600

provider --role prepare --owner OWNER --owner-sha256 SHA --request ACTUAL_REQUEST --request-file-sha256 SHA --family daily --symbols EXACT_MISSING_SYMBOL [SYMBOL...]
provider --role prepare --owner OWNER --owner-sha256 SHA --request ACTUAL_REQUEST --request-file-sha256 SHA --family minute --daily-references OWNED_REFERENCES --daily-references-sha256 SHA
provider --role run --owner OWNER --owner-sha256 SHA --packet-dir PACKET
内部worker只由parent创建：--role worker --owner OWNER --owner-sha256 SHA --packet-dir PACKET --parent-pid ACTUAL_PARENT_PID。

每个CLI stdout末行为JSON；拒绝exit1/status=blocked；成功exit0。resolve输出accepted/needs_daily/needs_provider（均带request_sha256）；review只accepted或拒绝；drive可正常paused_budget_or_four_connections/stopped_no_current_wait/paused_batch_budget，真实错误blocked。provider准备无网络，run才单次正常API；没有任意output/provider脚本/fixture开关CLI。

## 小API

scope.load_owner(path,sha256) -> Owner
scope.read_actual_request(owner,request_path,request_file_sha256) -> {request,path,file_sha,digest,wait,inputs}
scope.resolve_actual(owner,current) -> JSON result
provider.prepare_packet(owner,current,*,family,packet_index=0,daily_references_path=None,daily_references_sha256=None,symbols=None) -> prepared result
scope.review_packet(owner,current,packet_dirs,terminal_sha256s) -> accepted result
scope.publish_reviewed(owner,current,receipt_path,receipt_sha256) -> response path/SHA
scope.drive(owner,batch_id,*,max_connections=4,budget_seconds=3600) -> bounded journal

命名空间固定outputs/stage087_off_data_scope/<arm>/<run_id>/request_<digest>/{daily_packet,minute_packet,review,daily_references.json}，batch journal在同owner/batches/<batch_id>。同digest跨arm不共享decision/receipt/pointer。
原schema不变：request stage021_exact_execution_minute_request_v1；独立minute receipt stage021_independent_minute_delivery_v1；pointer stage022_delivery_pointer_v1。
新provider schema：stage087_provider_packet_v1、stage087_provider_preflight_v1、stage087_provider_actual_tool_terminal_v1。terminal仅driver真实Popen.wait/communicate returncode0＋parent0/inputs不变后创建；独立reader不写pointer。
每batch4连接含daily，840—3600批budget/840 reserve；原金融1800/7200权威时钟仍在原022/runner，不重置。provider570/600和一次attempt无自动retry。
