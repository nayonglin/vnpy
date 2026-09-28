# Stage004 运行后独立复核

- 复核日期：2026-09-02 CST
- 模式：独立只读复核
- reviewer agent：`01a06122-2d19-78f2-9c36-5b61e9c0c165`
- 未重跑worker、未训练模型、未读取sealed holdout标签、未修改文件、未连接CTP或订单API
- **结论：`ALLOW_STAGE005_PREREG_ONLY`**
- **置信度：96%**

## 严重度

- P0：0项。未发现产物损坏、身份错绑、标签泄漏或生产污染。
- P1：0项。4个worker原始结果、A/A、同月决策前一致性和候选标签差异均有效。
- P2：2项。标准`--smoke`父进程未继承worker的QMT override，4个worker完成后验证失败；随后在同一campaign和同字节runner上只补跑validator，未重跑worker，但原父进程失败和恢复过程没有单独持久化回执。另有5项predecision只保留SHA而没有原始payload，`sealed_holdout_labels_zero/model_training_zero/ctp_and_order_api_zero`由validator直接置真，只有文件树和运行时旁证。
- P3：1项。会计合同按`1e-6`货币量化后误差为0，但直接JSON浮点相减最大残差为`1.3969838619e-9`；Stage005应明确量化顺序，避免与文字`<=1e-9`合同产生歧义。

## 身份与文件复算

- 成功campaign：`campaign_20260902T153215+0800_55582`；contract SHA256=`a4a5a4278bfdb4131a790fd80696e00d3aa8b760ea40b44732f8bf36007f3bac`。
- 任务合同共`270`个唯一job：`266 main + 4 A2`；开发集`35月/266行`，sealed holdout为`12月/108行`。
- 4份worker receipt及36个固定输出均存在；输出SHA mismatch=`0`，receipt SHA mismatch=`0`。
- runner SHA256=`8c8de4037e4bc64096b88a87a1a76a18a17033f2a9b16ce6c3aa3238fb1bc819`；源库和runtime DB SHA256均为`5845010108e73661557e723556520d7a3ea42dc6bca4bbe5d50ca3bd419d4cad`；空setting SHA256=`44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a`。
- 4个PID、TMPDIR和MPLCONFIGDIR均唯一；reuse true=`0`；归一化runtime SHA256=`61665d29c46e86755df4102bc67d7f516648082ca1d9bbe62ba56c6fef9316ed`；最大wall time=`59.294921208s < 600s`。
- 失败campaign `campaign_20260902T152555+0800_50243`已写`ABANDONED/reuse_forbidden`；`campaign_20260902T152724+0800_51724`已写`failure_receipt/reuse_forbidden`。成功树扫描320个文件，对两个失败campaign路径引用为0。

## A/A与边界复算

- `20220128_R10/R10_A2`八类输出逐字节相同：summary `8ac2e11a...70cf9`、label `fa6ba74a...a94e1`、curve `43e7ae34...287d2`、combined `3cd58f3b...a6907`、trades `c0b9f03a...f277b`、entry_candidates `eaa503e2...b0f058`、entry_risk `d46e5531...26e4d`、trade_events `b63eb21a...35bae`。
- `20220228_R10/R11`五项决策前SHA逐项相同：curve `6604c195...9401f`、trades `b02957a3...14c0`、entry_candidates `667bed44...c6e1`、entry_risk `9d9a00ba...b7ed`、trade_events `aedc4490...3af5`。
- 两个20220228任务的目标边界均为`14行/14个非空signal`，唯一signal_date=`2022-02-28`。
- R11相对R10：未来净利润和期末权益`+120,910`，未来收益`+2.5507046pp`，未来最大回撤改善`+1.3925030pp`，滑点`+3,420`，交易`+2`。这只证明标签可辨识，不证明模型或策略有效。

## 隔离与授权

- holdout未生成任务或标签；runtime setting为`{}`；没有模型、CTP连接或订单产物。
- `smoke_receipt.json`为16/16 true，决策`stage004_runtime_smoke_pass_allow_development_label_batch_preregistration`；该决策只允许下一阶段预注册。
- Stage005必须使用新orchestrator修复父进程环境和恢复留痕，持久化可复算的predecision证据及三项显式零计数，并写清货币量化顺序；修复前不得启动development batch。
- 过拟合判断：否。固定任务、硬门和比较对象均在标签值前冻结，失败后没有换样本或改策略参数。
- 继续价值：是，但仅限Stage005预注册。当前证据只证明标签生产机制可用，不是收益提高或回撤下降证据。
