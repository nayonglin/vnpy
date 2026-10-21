# Stage115：batch003 实际 runtime／两份数据资格独立复核

- 时间：2026-10-18 08:10（Asia/Shanghai）；研究线 `futures_trend_triple_screen`。
- 重要突破版本：否。本次仅审已终态数据批次，不修改策略、金融源或任何 frozen 产物。
- 独立审查者：`accepted_delta_review`；未参与109实现。
- 结论：P0=0、P1=0、P2=0。有限接受两个已 published 的研究数据交付及其外部运行环境身份；不代表金融回测通过或生产资格。
- 新增／修改／删除经济参数：均无；新增金融结果：无。期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均为 N/A（本次禁止读取 B 途中 PnL）。

## 固定身份与真实终态

原 B_OFF owner 为 `81ffc8f704ce4c5eb701e97e0397b12a`，owner SHA `ce61dcf3cbe0696cfbc12f1ebcf0f12436ee0dfb84662623e91fce36ec957efb`。owner、context、preflight、readiness 与原100 scope review 的路径／SHA 均与 a167 manifest 绑定一致。本次只读历史 immutable 闭包，不调用 `load_owner`、不读 current wait／活动 audit，不通过 ps 或工具轮询 B。

外部 runtime manifest：`outputs/stage109_provider_runtime_selection/sessions/a167b50d9fa6437bbaf764a0ed5c6eeb/manifest.json`，SHA `beb4d8b2535d7dc24b102504a494bd2576548d5794ce38936ab620b762a2b024`。其111 review SHA 为 `394879ddf698d5bb6d20cc54e62fb433e376977f78c70a9e0ecaea72df89bfb0`，原100 review SHA 为 `347210330499f0e08c8a8cf5e3ac94c49698d1fcf04b84e8d8f20cc40cfc0c3f`。

root 提供的真实工具终态为 launcher session95182／chunk d3b39b／exit1；本次独立核了本地 launcher_terminal 与 closed journal。同一批次 journal status=`blocked`，error=`ValueError:request_not_current_owner_wait`，provider connections=2／上限4，两项 events 均 `published=true`。两份 packet 各自原087 parent／worker terminal 均 exit0，分别耗时16.566秒、17.286秒。故 driver 的后续 exit1 保留，但不能把它说成金融进程失败，也不能反向把两份已经合格的交付说成失败。

未保存 stack，因此无法独立定位具体 raising 行。root 于08:01:50观察前4 response 已存在且进入 CF005 Mar12，只作为 root 观察继承；本审查没有轮询或据此宣称全局 RAM commit 成功。

## 两份实际数据的接受范围

| request digest | 精确 scope | 权利／条数 | delivery receipt SHA |
|---|---|---|---|
| d3877eb65bfc7f8ac2304141da971ae8012a0fb61cbe1b32722debeece2080be | jm2005.DCE，2020-03-10 | full_session 225 | e1d227123a8066b9d2faad483151b805659b4d8754db9f7d9dd27a1b76bc97b9 |
| 08dc30017c54bdee9ab526a211a9aaff65eddc228092cf287837db61408be772 | jm2005.DCE，2020-03-11 | full_session 225 | f3fb83941183e539b80be06d67f9a0d8dd135d2b4a3c25740303d32b3580b254 |

两者 R=225、E=0、M=225，source seven values 的 raw／delivery 完全相同，两个包无重复 key，共450个 full-session key；没有 anchor-only 数据升权。所有450条完成证明均为真实 observed_later_serial_kline，successor 至少晚1分钟，时间／symbol 与请求精确相等。

独立只读调用原021 `_read_delivery`，两份原始 `parse_result` 均 accepted、fixture_only=false，response 指向同一真实 receipt 路径／SHA。raw／proof／preflight／parent／worker／request／daily reference／receipt source fingerprints 和输出CSV都核同 bytes SHA；没有向 response 写入任何内容。

每包 open、high、low、close、volume、open_oi、close_oi 的分钟聚合均与 pinned013 两条 qualified daily 相等，并核 target_qualification accepted。没有重聚合整个日线库。013本身是旧独立 schema，使用 `qualified_research_daily`，并无新式 `independent_review` 字段。

A0 disjointness 仅继承实际 pinned checks 的 intersection0 与其所绑定旧读集；未重跑旧 A0。当前两请求 E=0，跨包互斥；旧值保护继承原021严格 overlap／原子发布合同，不宣称本审查重建了运行中 engine RAM 的全部旧值或验证了其消费后的完整账本。不得将本收据扩大成新061 freeze、跨 owner／arm／request 资格或全局 cache 晋升。

## 外部 runtime 的独立闭合

a167 共12份真实解释器 sidecar：driver46179（父46177）；resolve46184／46292／46311；prepare46189／46361；run parent46198／46372；worker46211（父46198）／46380（父46372）；review46273／46387。除两 worker 外，子角色父进程均为46179。额外 resolve 的9c776780请求只核 runtime 身份，不接受它的数据资格。

每份 sidecar 的 argv、PID／PPID、manifest路径／SHA、owner、111／100 review 及源绑定均一致。五个数值模块 numpy／pandas／scipy／sklearn／joblib 的实际文件均位于原 FROZEN site-packages；SDK metadata／find_spec 选择为本机3.10.2，__init__、METADATA及原018五份SDK代码的SHA／bytes与 accepted pins 一致。实际 packet preflight 也记录3.10.2、原570／600秒、1连接、无 retry。真实 worker 的 TqSim_created、完成数据和终态与已核代码路径闭合。

sidecar 是启动时观察，`sdk_imported=false`、`credentials_read=false`、network0 只描述该时点，不能冒充SDK导入后的全依赖 attestation。尚未加载的第三方仅记解析路径，不能冒称完整 dependency freeze。本次审查自身没有 SDK import、凭证读取、网络调用或 provider 执行。

上述109外部运行环境通过其独立 manifest／sidecar 绑定，明确不属于旧金融 preflight 的原闭包；不能把原金融源闭包标签扩充成已经包含109。

## 命令、证据与限制

本次只执行本地只读 JSON／CSV／SHA 资格诊断和文档写入。最终只读资格命令 chunk645714，真实 exit0；涉及闭包95个唯一文件、29,584,553 bytes，包括请求明确绑定的 mapping／旧 reference 文件；没有扫描或重新 hash 全市场3157分钟源。

最初 reviewer harness 对旧013错误读取不存在的 `independent_review` 导致 KeyError／exit1；已保留原脚本与真实输出。仅修正本审查脚本，使其读取 pinned013真实 `reviewer`／`qualified_research_daily`／P0P1，再完成同范围只读验证。未修改数据或作者源，也不是重跑测试／provider。

证据均位于 `outputs/stage115_batch003_runtime_data_independent_review/`：

- `verification.json`：95项闭包 SHA／bytes、12个PID实际路径／角色、两个 scope 全部核对结果。
- `verify_two_closed_deliveries.py`／`initial_harness_schema_mismatch.py`：最终命令与最初字段错误脚本。
- `command_evidence.json`：实际命令、exit、原始观察输出和字段修正原因。
- `review_receipt.json`：独立有限接受收据，SHA `649ad19bc0900e42e5855bc43757ef6091b2481c3bb62ccc4e56c457b475d5d6`。

本次没有运行任何测试、provider、prepare、金融、模型／网络；没有读取 B 途中 PnL、轮询金融session47648或触碰正在运行的batch005；没有改作者源、frozen产物、LINE、registry、Git。后续金融完成后仍需独立完整账户审计；本次不授权启动金融或生产。

## 反思与后续

开始和结束判断均为：没有过拟合，因为本次只验证身份、终态、精确权利与七值，不选择策略或收益。继续做有价值，因为真实外部运行环境和已交付数据必须分别具备可审计身份，且必须保留driver失败与金融终态的区别。后续仅由root推进既定任务；本reviewer不自启新批次。
