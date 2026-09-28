# Stage003 joint ranker development OOS 训练前独立评审

- 评审日期：2026-09-03（Asia/Shanghai）
- line_id：`futures_trend_xgboost_pit_physical_positioning_context`
- 评审对象：`stages/20260903_0318_stage003_joint_ranker_development_oos_preregistration.md`
- 预注册 SHA256：`859d060217e6ef381170d439086ec0d7097d2c18152f2c0ff0aaacb78124cbea`
- 决策：`BLOCK_STAGE003_IMPLEMENTATION`
- 严重度：`P0/P1/P2/P3 = 0/0/2/1`

## 结论

Stage003 的无标签样本、PIT 折、六特征、joint relevance、单头 32 树、LR/XGB 等权 percentile selector、物理 split 门、153 行标签预算、11 项双目标效果门和数据复用停止规则整体设计自洽，独立复算的全部行数、月份、折序列和冻结文件身份均匹配。

但当前预注册尚不能直接作为单义 TDD 合同：一次性 authorization 只给出 scope、nonce 和“绑定全部 SHA”，没有冻结 exact bound keys、授权 decision、canonical 路径和原子单次消费语义；pre-effect seal 虽声明保存 selection、特征顺序、qid 和训练行身份，却在开标签前只明确复核 seal 与模型/预测 SHA，没有要求用实际 payload 重新计算这些关键摘要。两项均属于训练前必须修复的 P2，否则实现可在不违反文字表面的情况下留下重复授权或标签开放前选择身份不受绑定的缺口。

因此不允许 Stage003 实现，不创建 authorization。修订只能收紧与结果无关的治理语义，不得读取任何标签值、训练、改变样本/参数/selector/效果门或查看 holdout。

## Findings

### P0（0）

未发现 P0。

### P1（0）

未发现 P1。

### P2-1：一次性 authorization 缺少 exact 绑定和原子消费合同

预注册第 154-155 行要求最终 review 通过后申请“绑定全部 SHA”、64-hex nonce、`scope=one_new_stage003_development_oos_run_only` 的一次性 authorization；技术门第 121、128 行要求 authorization 身份精确且入口调用一次。这些目标正确，但没有冻结以下机器语义：

- authorization 的唯一 canonical 路径、consumption receipt 路径和结果目录；
- authorization `decision` 的精确字符串和顶层 exact keys；
- `bound_files` 的 exact key 集合及每个绝对路径，包括当前预注册、当前独立预审/decision、未来机器合同、runner、tests、runtime identity 和最终实现 review；
- nonce 必须是 JSON string 且匹配小写 `[0-9a-f]{64}`，不得由 bool/number 冒充；
- 固定 consumption 路径必须在任何标签打开、模型 fit 或数据准备前以不可覆盖的原子 create-once 方式消费，并 fsync file/directory；
- 已存在 consumption/result 时必须在消费或副作用前拒绝；串行重试及并发竞争只能一个成功；生产入口不得允许调用者覆盖 authorization/consumption/result 路径或 estimator factory。

当前“入口调用恰好 1 次”是运行后自报计数，不能替代不可重复消费原语。Stage006 已证明单路径原语正确但顶层可改路径仍能重复消费；Stage003 不能把该关键设计留给实现者自由选择。

必须修订：在预注册和未来机器合同中写出上述 exact schema、路径、顺序和并发 fail-closed 规则，并要求恶意反例测试。修复前不能授权 TDD 实现。

### P2-2：pre-effect seal 的开标签复核未覆盖全部实际 payload

预注册第 112 行要求 active fold seal 保存模型、预测、选择、特征顺序、qid、训练行身份与 SHA；但第 113 行 `effect_open` 只明确“重新复核 seal 及模型/预测 SHA”后开本月标签。以下内容没有被冻结为开标签前的强复核：

- A/B/C selection 和 tie-break 的 canonical payload SHA；
- 六项 feature order；
- qid 数组、组边界和排序后的训练行 job identity；
- 主模型与重复模型各自实际 bytes；
- exact seal keys、每个摘要的 64 位小写 hex 类型、canonical serialization；
- 4 个 fallback seal 的 exact schema、日期、reason 和 label-read-zero 证明。

仅验证模型/预测不能证明“选择”和“训练行身份”在测试标签打开前已经不可变。如果 seal 或内存 payload 在 write/fsync 后被替换，文字合同允许实现只核验模型/预测后继续读取标签，削弱同折盲态和 selector 不看标签的核心证据。

必须修订：active fold 在 label store `_load` 前必须用实际 primary/repeat model bytes、ordered prediction rows、selection、feature order、qid 和 ordered training job identities 逐项重算 SHA，与 exact-key seal 精确比较；所有摘要必须为 64-hex string。seal 必须唯一、不可覆盖、同目录临时写入并 file/directory fsync。任何一类 payload/摘要/extra key 篡改均须在标签读取计数增加前拒绝。fallback seal 也需 exact schema 和不读 label 的独立反例。

### P3-1：零替换时两项中位数门的输出语义未定义

效果门要求实际替换月收益和回撤改善中位数均 `>=0`，同时最少替换 5 月。若实际替换为 0，前置门必然失败，但中位数本身是空集合，当前未规定 artifact 中写 `null`、NaN 还是其他值，也未规定对应两个 gate 必须为 JSON `false`。这不会导致错误放行，只影响机器输出一致性。

建议修订时明确：空替换集合的两个 median metric 写 `null`，两个 gate 写严格 JSON `false`；所有 11 个 gate 必须是 bool，最终 `passed` 为 11 项逻辑与，禁止 `NaN` 或真值转换。

## 冻结输入与表头核验

### 本线 Stage002

- Stage002 manifest SHA256：`41cfef41f6e4555f4886c5ec71be92637a02250ce1a50ff7499c7b31cc8557ce`，与预注册一致。
- manifest 声明 8 个工件，输出目录除 manifest 自身外实际 8 个文件；路径集合和逐文件 SHA 全部匹配。
- `model_eligible_feature_panel.csv` SHA256：`12b1e6afc5b4411e0cbab9b9ea59a6137eefcd7358decd69d2c327cae1407547`。
- `month_eligibility.csv` SHA256：`26ee18e1bf9268c2bef98ac6e5138cd35a75589327443bf911ab9eef9f019853`。
- Stage002 summary SHA256：`13b81dd8b0ee111a022568ceb5a4a76ea88f59e626623c2c305c34af2cc1cf7f`；15/15 技术门通过，218 行、35 月、六特征、warehouse 特征 0，label/fit/backtest/CTP/order 均为 0/false。

### 旧线 metadata、header 与 SHA

- full split SHA256：`a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1`；只读取 `eval_date,next_eval_date,product_vt_symbol,a_rank,split` 元数据列。
- development jobs SHA256：`7ee2062e9700d1c1e8800f42ce8dd0ba75470e4953e30c099c37741aed39b8f3`；只读取任务键、job type/id 和 eligibility identity。
- Stage003 summary SHA256：`b44e21dc5070675b23c03a26973cc76f4ad8c93d79c6add7be4fd480cd945c0a`；266 main + 4 A2，35 development 月，sealed holdout 12 月/108 行，标签值读取 false。
- Stage005 decision SHA256：`1cffbfcf0872de9c2a0256071de95ca4a750a72b74025865a1beb8b18fe8a111`；decision/passed 正确，job counts 精确 `266+4=270`，attempt complete，holdout/模型/CTP/order/unexpected 均为 0。
- Stage005 manifest SHA256：`526f945c2e7523b78076331a2473a606f6f8ce775a0a8ac7850dcd593a31eedf`。
- Stage005 post-run review/decision SHA256：`d1933474704dfa116bb88ca5c32465c686166f5541755081e559af9db5816d32` / `d35d46f90614e3c8a4c59510b05de845afedae5a1db8c8ca1a17913fad1fc6b0`，P0/P1/P2=0/0/0。
- `development_labels.csv` SHA256：`b4e5f7f638298ff1bd572b378ae096345273488df67c5b5386ba776deec3798d`；只读取首行，14 列表头与预注册一致，数据行解析 0。
- `reconciliation.csv` SHA256：`f964992306202c2589a6ff20962aa10144beca58fa393a93dc650b543073b75c`；只读取首行，18 列表头与预注册一致，数据行解析 0。

## 样本、split 与折序列独立复算

使用 Stage002 218 行无标签特征左连接 old Stage003 指定 metadata 列：

- 218 行全部一对一匹配；缺失/重复为 0。
- development：`153` 行、`26` 个活跃月。
- sealed holdout feature：`65` 行、`9` 个活跃月；仅计数，未预测、未读取标签。
- 153 development 行全部一对一匹配 main jobs，job_id 唯一；4 个 A2 和其余 `113` 个 development main 均不在资格子集。
- 初始成熟集：`13 qid / 62 行 = 13 rank10 + 49 challengers`。
- 13 个 active OOS 月与预注册日期逐项一致；4 个 fallback 月精确为 `2023-12-29, 2024-02-29, 2024-05-31, 2024-10-31`。
- 13 折训练 qid：`13,14,15,16,17,18,19,20,21,22,23,24,25`。
- 13 折训练行：`62,69,75,82,88,94,100,107,114,122,130,138,145`。
- 13 折测试行：`7,6,7,6,6,6,7,7,8,8,8,7,8`，合计 `91`；每折恰有 1 个 rank10 和至少 5 个挑战者。
- 每折训练仅使用先前 active 且 `eval_date < test`、`next_eval_date <= test` 的行；fallback 月不提供训练标签。最终唯一标签预算 `62+91=153` 自洽。

## 六特征、qid 与标签目标

- Stage002 eligible panel 的末六列顺序与预注册精确一致，218 行全部有限。
- 禁止列覆盖 rank、产品、交易所、日期、年月、来源时间/年龄、可用性、warehouse、缺失指示器和历史结果；不留填补、缩放、winsorize、clip、符号翻转、分位变换、交互、PCA 或特征选择分支。
- `eval_date,a_rank,product_vt_symbol` 稳定 mergesort 和按月连续 qid 定义单义。
- return/drawdown delta 都以当月 rank10 为锚，dense ascending 后减 1，再取逐行 `min` 得到 joint relevance；真实并列保持同级，退化月 fail-stop，不允许删月或换目标。
- 测试标签明确禁止进入同折特征处理、训练、调参、selector 和 tie-break；标签只允许从固定 Stage005 campaign 的 main per-job JSON 读取。

## 模型、selector 与物理 split 门

- 单一 `XGBRanker`、19 个参数值、32 棵深度 2 的树、单 seed/CPU/线程、无搜索/early stopping/验证集/权重/自定义目标均已冻结。
- 13 primary + 13 repeat=`26` fits，预测差 `<=1e-12`、UBJ SHA 一致、每折测试分数至少 2 个唯一值，规则单义。
- 每个 primary 至少 1 个物理特征 split、全体至少 3 个不同物理特征，防止模型只复述 formal probability；失败即技术停止，不允许重跑择优。
- A 保留正式 rank10；B 为纯 XGB 诊断；C 为 LR/XGB 月内 average percentile 等权。排序与 tie-break 完整，禁止原始分数相加、学习权重、margin、产品/年份分支或看标签选 B/C。
- 4 个 fallback 月和非完整候选不可被 B/C 选；17 月效果序列必须完整并对 fallback/未替换写精确 0。

## 11 项效果门与数据复用

- 11 项门同时约束替换数量/年份/品种、收益与回撤总和、leave-best-out、逐年非负、联合命中率和两项目标中位数；全部为必要条件，B 不能救援 C。
- 互斥账户边际标签明确禁止聚合成可复利组合收益，禁止发布期末权益、策略总收益、组合最大回撤、Sharpe、滑点、交易次数或胜率。
- 预注册明确披露同一 35 月 development 标签已被其他特征假设使用，当前不是独立确认；即便全部通过也只可申请 development true-engine A/C 预注册，不能开 holdout。
- 若任一效果门失败，本六特征、joint maximin、单头 32 树、等权融合形状永久关闭，禁止调参、换标签/权重、删月/品种或改完整性救援。该停止规则有效限制结果后自由度。

## Runtime 与 fresh 测试

- runtime identity SHA256：`f0a469f5a8387ba8171be5b3e2c8c6b0d9fc0e8de7f5b0914e08ef4f327fddbc`。
- 当前只读重建匹配 Darwin/arm64、Python 3.11.15、numpy 2.4.4、pandas 2.3.3、scikit-learn 1.8.0、xgboost 3.2.0；Python、xgboost init 和 dylib 的 path/size/SHA 全部匹配。
- 本线全部现有无标签测试 fresh：`6 passed in 0.50s`。
- 未运行 Stage003 实现或训练入口，未读取任何 aggregate/reconciliation 数据行、per-job label、sealed holdout 标签或 Stage006 预测/效果明细，未训练、回测、连接 CTP 或调用订单。

## 过拟合与继续价值

- 过拟合判断：本次评审本身否，只使用无标签特征、metadata、header、SHA 和 runtime。未来实验风险高：development 只有 26 个 active 月、首折 13 qid，而且相同标签已被多次研究；任何失败后结构调整都属于数据窥探。
- 继续价值判断：修订两个 P2 后有且仅有一次冻结实验的价值。basis/member 假设、低复杂度 joint ranker 和严格双目标门具有可证伪性；若一次运行失败，不应继续在该 development 样本上优化。

## 决策边界

`P2=2`，decision 为 `BLOCK_STAGE003_IMPLEMENTATION`，`allowed=false`。只允许在不读取标签、不训练的前提下修订 authorization 与 seal/空集合机器语义并再次独立预审；不授权 TDD 实现、标签读取、模型训练、效果评价、回测、true-engine、holdout、production、CTP、实盘、订单或创建 authorization。
