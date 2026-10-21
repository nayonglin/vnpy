# Stage135：真实B_OFF已消费数据的独立复用层设计与实施边界

line_id=futures_trend_triple_screen；2026-10-18 09:49 CST。root基于133真实终态及134已提取gate事实设计，134正式收据完成并绑定后才允许actual freeze。不是新策略参数、金融臂/readiness或生产发布；同分支，无worktree。

## 决策与调研判断

原B_OFF已因原7200预算实际失败，不能以partial账户恢复完整绩效。固定策略不改，仅为避免重复等待同样数据创建可复用层。调研继承121/123，无新策略alpha或网上经验结论；接口依据原061/021实际源码与134失败projection。原061 freeze硬绑定063/B_TS/stage036，不可直接喂065事实，也不伪装旧schema；其FrozenDelta/等值append/完整与anchor权利组合数学仍可作为通用数据容器复用。

新增`tools/stage135_accepted_off_wait_delta.py`和`tools/test_stage135_accepted_off_wait_delta.py`。只冻结本次159个真实commit，不合并/重存/重审既有061的190个包；未来runner可按固定顺序叠加两个独立数据层并compose两次资格，老层完整继承。旧数据/旧源码/失败/预算全部保留。

## 固定接口与实现

1. `freeze_off_delta(*, snapshot_path, snapshot_sha256, review_path, review_sha256, output)`。必须绑定134最终独立收据与原audit_only_snapshot实际SHA、owner/schema、root133真实exit1、065 context/capture/failure/preflight和基底stack/原两anchor来源；不把134 `new_data_qualification=false`偷换成已签新数据层资格。
2. 每个commit须严格匹配原resolver accepted pointer、request canonical/file fingerprint、response、021 receipt/完整源闭包、request sequence与原input_fingerprints、old_keys_changed=0；数据解析消费同一已hash bytes。可复用061 `_read_delivery_bytes`及无副作用工具，不调用其旧terminal验证器。只收159个实际commit；failed CF505 prepare-only明确excluded，不读取其raw、不签权限。
3. 交付标准独立目录：source_run_snapshot.json（真实134/133/065身份，不能假造063）、accepted_deliveries.json、overlay.csv、rights.csv、manifest.json，不覆盖原物。数据容器/manifest可兼容原061通用DATA schema及load_accepted_delta要求，builder明确stage135、实际B_OFF/run_id，声明compatible_data_schema_only，不得声称旧061原freeze接受此终态。source_fingerprints只绑定实际消费/必要身份，不因projection含7663个旧源就重hash全市场。
4. 每key七值跨receipt冲突拒绝，full/anchor权利精确合并，float17g/round-trip；manifest计数须等于134已审范围36391唯一键、36345full、46anchor-only、159delivery，baseline stack及继承anchor身份只引用；无独立新层review不得被当作可用金融数据。原061load所需独立review格式可复用，但review必须实际独立生成，不能自己签自己的dataset。

## 有界实施与验收

作者先读registry/133/134实际schema、134正式receipt、061/021。只写上述两源及唯一中文Stage136/outputs136，root拥有135设计及LINE；不改旧文件/registry/Git，不构建新runner，不下载/训练/金融。沿用户自主授权，不再询问执行方式或额外许可。

先用tiny synthetic已签bytes写两个有意义组合测试RED→GREEN：①身份/终态/schema/receipt与hash后重开毒化拒绝，fixture与真实owner不可混淆；②两个相交scope、七值冲突、full/anchor精确权利、失败request排除、原容器只读load与append/compose，旧值不改。fixture不写真实134收据，不冒称有真实资格。只运行新增两方法，不重跑旧suite。源及actual候选freeze完成后root组织一次独立代码+实际冻结数据审查，不额外做循环micro review。

actual候选freeze是独立一步，必须134最终receipt和本builder有限GREEN通过；它仍是pending independent review，随后一次独立审查同时核新代码与actual数据产物。只有新manifest取得独立数据资格后，未来才讨论金融入口/有限新attempt。当前不启动新账户、不扩大1800/7200/840，不把数据成功当alpha。

本次新增/修改/删除策略参数与完整回测结果均0；权益/收益/DD/Sharpe/滑点/交易数/胜率N/A。开始/结束新增过拟合：否，只按实际消费资格复用，不看PnL或扫参；继续价值：是，这一步直接减少后续重复等待，但不能变成无限数据审查。目标active、production_qualified=false。
