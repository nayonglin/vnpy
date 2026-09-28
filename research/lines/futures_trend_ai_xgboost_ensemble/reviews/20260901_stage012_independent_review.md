# Stage012 首个活跃边际月份账户标签探针独立只读审查

- 复核时间：2026-09-01 18:17 CST
- 唯一复核对象：`LATEST.json -> attempt_20260901T181032+0800_58383`
- 旧 attempt：明确排除，不参与本文件任何最终结论
- 总体结论：`PASS_WITH_P2`，`P0=0 / P1=0 / P2=5`
- 门结论：`ALLOW_COVERAGE_STUDY_ONLY`

## 发现

### P0

- 无。

### P1

- 无。

### P2-1：机器身份门没有自动交叉比较四臂归一化运行时合同

- `stage012_active_account_slot_probe.py:656-663`的身份总门检查共同`file_contract_sha256`、单臂before/after稳定性、receipt及临时目录唯一性，但没有把四臂`python/sys.path/packages/repository/environment/startup_hooks`归一化后做机器交叉比较。
- reviewer独立去除各臂预期不同的`TMPDIR/MPLCONFIGDIR`后，四份运行时合同逐值一致；因此不影响本 attempt 的PASS。
- 后续批量覆盖研究应把该比较固化为门，避免运行时身份漂移仅靠人工发现。

### P2-2：Stage011物理读取全列后才收窄为四个活动字段

- `stage011_marginal_slot_activity_qualification.py:162-164`先读取源CSV全部24列，再裁为`experiment_arm/offset/date/vt_symbol`。
- 后续选择算法只消费这四列；`performance_columns_consumed=[]`，reviewer独立按活动规则复算得到同一首个合格月份和候选，未发现PnL、收益、回撤、Sharpe、滑点或其他绩效后验参与选择。
- “只按活动选择且未看绩效”成立；为强化最小读取合同，建议改为`read_csv(..., usecols=USED_TRADE_COLUMNS)`。

### P2-3：诊断行足以解释机制，但尚未形成逐事件、逐金额闭环

- `entry_candidates/entry_risk/trade_events/trades/curve`原始行能够解释`ru`被替换后，`OI`短信号被规则拒绝、`au`开仓以及账户级仓位预算对`AP/fu`的后续传导。
- 当前`report.md`主要汇总行数和标签，没有机器可检验的“候选事件、成交、手续费/滑点、日PnL各项之和 = 账户标签delta”对账表。
- 这不阻断标签覆盖率/稀疏性研究；批量标签进入XGBoost训练前，应补精确差额reconciliation。

### P2-4：全排名恢复源止于2026-07，不能外推为当前m0005全月覆盖

- Stage009冻结全排名共55个月，范围为`2022-01-28..2026-07-31`；m0005虽含`2026-08-31`正式Top10，但Stage009没有该月完整rank11..18。
- 本次目标月为2022-05，不受影响。后续覆盖研究须明确止于2026-07，或为2026-08单独恢复并冻结完整18席排名。

### P2-5：summary窗口标签已修正，但curve仍保留旧结束日

- 四臂`summary.csv.window_label`均为真实窗口`2018-01-01_to_2022-06-30`；但四臂`curve.csv.window_label`的1,090行仍全部为`2018-01 independent start to 2026-05-29`。
- `stage012_active_account_slot_probe.py:430`只重写summary的`window_label`，未同步重写curve字段。
- curve真实日期仍为`2018-01-02..2022-06-30`，该展示字段不参与逐值门和标签计算，因此不影响本次PASS；批量覆盖产物应统一修正，避免审计窗口被误读。

## 身份完整性与稳定性

- `CURRENT.json`指向`m0005_20260901T165450+0800_1961d98ccb2b`及`ai_top10_plus_fu_official_live_v1`；生产HEAD与`origin/master`均为`d492ee072aa5a9d71477235d79f17d2a5db59db3`，生产工作树干净。
- 四臂before/after manifest各含`1,873`个文件，合计`377,285,811` bytes；四臂文件清单逐值相同，共同文件合同为`281b6e194605ef17d1df8dabb83608d575b661c4e01f541f31feeb6f6e6fc059`。
- reviewer重新计算全部1,873个文件的SHA256，漂移数为`0`；各臂before/after manifest逐值相同。
- 身份闭包包含m0005完整release、`CURRENT.json`、生产portfolio代码、workspace vnpy core、vnpy_portfoliostrategy、解释器和distribution metadata，以及冻结数据库、全量分钟K、主力映射、合约元数据、产品全集、Stage009-012脚本/输入和eligibility。
- 冻结数据库SHA256为`ecbe812bd092ec8cedbd00d8b4b3ec2b1fa9311034dc8379fc6981033405eaf3`，SQLite采用delete journal、无WAL且`integrity_check=ok`。
- 全量分钟K为`201,354,181` bytes，SHA256=`8e861633b08a82819a668c30c6799e2098d2beaa6863698351145018ea586784`。
- 主力映射SHA256=`89c8ae7e66e67def7f2b9626a166d0d6582c30fe2e08ee6cf39808951146d851`；合约元数据SHA256=`24a3573e847e024411b13a3a3b775791ded57563b0a68b717d1065078201635a`；产品全集SHA256=`72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`。

### Python启动身份专项

identity manifest确实纳入并哈希以下有效启动输入：

| 身份键 | 实际路径/模块 | SHA256 |
| --- | --- | --- |
| `python_sitecustomize` | 仓库根`sitecustomize.py` | `7d950bb52b83c833c6c76ec9892833c205f014518aadf3649f8396055ce408ff` |
| `python_site_pth/0/_editable_impl_vnpy.pth` | 当前`.py311` site-packages | `d3ab4b13fe1b92d017e3e806c18eb5bc2864f9eed21b8ee9c2648c6351ab861d` |
| `python_site_pth/0/distutils-precedence.pth` | 当前`.py311` site-packages | `2638ce9e2500e572a5e0de7faed6661eb569d1b696fcba07b0dd223da5f5d224` |
| `python_startup_module/_distutils_hack` | 实际加载的`_distutils_hack/__init__.py` | `df81e6bcba34ee3e3952f776551fb669143b9490fdd6c4caeb32609f97e985b4` |

- `_editable_impl_vnpy.pth`实际指向仓库根；`distutils-precedence.pth`会启动`_distutils_hack`，其被加载模块也已单独入manifest。
- `sitecustomize.py`及其导入的workspace `vnpy`代码均已进入身份闭包；未加载`usercustomize`，故其缺席不是漏项。
- 结论：Stage010 P1指出的Python启动输入缺口已在本 attempt 实质关闭。

## Stage011活动选择复核

- 源commit为`6750783fe7aab92e6dbdd6820fa212e2e53ea353`，源payload SHA256为`f53d31c4a66a72840ef897a4738530572812116651c9e5fda9b693a30108795e`；ranking、预注册和activity audit哈希均与`selection.json`一致。
- reviewer仅使用声明的四个活动字段独立重算：从`2022-04-29`起，第一个满足“rank10至少开仓1次且至少两个低排名候选各开仓至少1次”的月份确为`2022-05-31 -> 2022-06-30`。
- 机械结果为基线`rank10 ru.SHFE`，候选`rank12 OI.CZCE`、`rank13 au.SHFE`；活动次数分别为`1/1/2`。
- 结论：Stage011只按活动选择，未看绩效，且没有用本次四臂结果反向挑月或挑候选。

## Eligibility逐字段复核

- A eligibility与m0005正式eligibility全表`634/634`行、所有字段逐值一致。
- C12与A全表逐单元格比较，仅`2022-05-31, score_rank=10`这一行的`score_type/product/score`变化：`ru.SHFE -> OI.CZCE`，rank保持10。
- C13同样仅该目标月rank10行的`score_type/product/score`变化：`ru.SHFE -> au.SHFE`，rank保持10。
- 除目标行外，C12/C13其余所有行和字段均与A逐值一致；固定`fu.SHFE`、其他席位及其他月份均未变化。
- 结论：四臂干预真实且严格限定为2022-05-31第10席位替换。

## A/A与决策日前路径

- A1/A2的summary核心字段逐值一致。
- 去除仅用于标识实验臂的`profile/variant/experiment_arm/arm/label`后，A1/A2全期其余字段逐值一致：curve `1,090/1,090`、trades `451/451`、entry_candidates `400/400`、entry_risk `202/202`、trade_events `476/476`。
- 采用同一身份字段归一化，截至并包含决策日`2022-05-31`，A1/A2/C12/C13相对A1的其余字段均逐值一致：curve `1,069/1,069`、trades `444/444`、entry_candidates `389/389`、entry_risk `199/199`、trade_events `470/470`，曲线最大绝对误差为`0`。
- 四臂PID为`58390/58543/59575/59791`，`TMPDIR/MPLCONFIGDIR`各自唯一，receipt均声明`checkpoint_reused=false`。
- 四臂墙钟为`59.8278/58.9145/58.3355/57.6805`秒，均真实小于`600`秒。

## 标签独立重算

reviewer直接从四臂原始`curve.csv`重算基准权益、期末权益、未来收益和未来最大回撤，并结合原始交易结果核对PnL、滑点和交易数；与`account_labels.csv`最大绝对误差为`1.95e-16`，小于门限`1e-12`。

| 臂 | 基准权益 | 期末权益 | 目标期收益 | 目标期最大回撤 | 净PnL | 滑点 | 交易数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A1/A2 | 4,075,878.80 | 4,228,148.80 | 3.735881% | -8.284276% | 152,270 | 14,860 | 7 |
| C12 | 4,075,878.80 | 4,160,798.80 | 2.083477% | -8.108325% | 84,920 | 8,860 | 5 |
| C13 | 4,075,878.80 | 4,055,078.80 | -0.510319% | -8.082882% | -20,800 | 10,760 | 9 |

- C12相对A：收益`-1.652404pp`，最大回撤改善`+0.175951pp`。
- C13相对A：收益`-4.246201pp`，最大回撤改善`+0.201394pp`。
- 两个C臂相对A均产生大于`1e-12`的账户标签差异，因此“标签可识别”门真实通过。
- 两个C臂都没有同时提高收益并降低回撤；该月没有候选胜出证据。

## 门结论

| 审查门 | 结论 |
| --- | --- |
| `LATEST.json`绑定唯一新 attempt，旧 attempt 不参与结论 | PASS |
| m0005/生产HEAD/冻结数据库/全量分钟K/映射/元数据/产品全集/生产代码与运行时身份完整稳定 | PASS，附P2-1自动门加固建议 |
| 根`sitecustomize.py`、两个有效`.pth`、已加载`_distutils_hack`进入身份manifest | PASS |
| Stage011只按活动机械选择且未看绩效 | PASS，附P2-2最小读取建议 |
| C12/C13仅目标月rank10行字段变化 | PASS |
| A/A curve/trades/entry_candidates/entry_risk/trade_events逐值一致 | PASS |
| 决策日前五类路径逐值一致 | PASS |
| 标签可从原始产物独立重算 | PASS |
| 每臂冷启动墙钟不超过600秒 | PASS |
| summary/curve窗口展示合同一致 | P2-5，不阻断本次标签门 |
| 诊断支持机制归因 | PASS，附P2-3精确金额闭环要求 |
| 候选胜出 | NOT TESTED / 不允许推断 |

## 最终决定

`decision=stage012_account_label_identifiable_continue_coverage_study`只表示：在冻结身份、严格单席位干预、A/A和决策日前路径一致的前提下，账户级反事实标签可被识别，值得继续研究跨月覆盖率、零标签率、可识别率和运行预算。

该decision不表示C12或C13胜出，不表示XGBoost已有有效训练标签，更不表示收益提高、回撤降低、候选晋级、shadow/实盘接入或生产修改已获批准。允许进入的下一阶段仅为只读覆盖研究，并须遵守P2-4的月份边界；批量标签进入模型前还须关闭P2-1和P2-3。

## 反思

- 开始前过拟合判断：否。此次只读审查对象、月份、候选和门均已冻结，reviewer没有按绩效重新选样；继续价值：是，账户级标签身份与可复算性是XGBoost研究前的必要基础设施。
- 结束后过拟合判断：审查本身否；若依据2022-05这一个月选择品种、训练模型或宣称提高收益/降低回撤，则是明显过拟合。继续做覆盖研究仍有价值，但必须跨月、严格PIT、保留独立OOS，并先量化标签稀疏性和完成账户PnL差额闭环。
