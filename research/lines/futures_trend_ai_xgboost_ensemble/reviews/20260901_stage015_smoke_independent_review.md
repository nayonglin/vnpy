# Stage015 smoke campaign 独立审查

## 结论

- `VERDICT: PASS`
- 问题计数：`P0=0 / P1=0 / P2=0`
- 执行决定：`ALLOW_FULL_DEVELOPMENT_BATCH`
- 授权边界：只允许在同一 campaign identity 下续跑冻结的355个development任务；不授权修改任务、特征、模型参数或门槛，不授权训练模型、生成sealed holdout标签、接入shadow/实盘或修改生产目录。

## 审查对象与边界

- campaign：`campaign_20260901T191852+0800_76524`
- campaign路径：`research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage015_development_label_batch/campaign_20260901T191852+0800_76524`
- 冻结runner SHA256：`f4033547169feaa33c04ade69c58403a4a8b05717abff4517328fcbef2e1f9b4`
- 预注册SHA256：`196db9f677df15238a97218efcfe810cb216b45df1114ffecc5bf8f6cfd7b76a`
- 测试文件SHA256：`a3013683fd7a01ab1165f02e447c82eb1e1f48e47ff6bc7ffa36ca2ed6e0b448`
- 本次只审查身份、固定四job、A/A、决策前payload、entry signal边界、三路对账、进程隔离、600秒门、发布边界及receipt绑定。未比较、解释或利用四个部分标签的收益、回撤或方向，不据此建议修改模型或门槛。
- 这是冻结本地实物审计，不是新策略研究，因此未引入外部资料或另跑策略回测。

## 分级问题

### P0

无。

### P1

无。

### P2

无。决策前五类payload按预注册只保留归一化SHA而不保存全量历史副本；本次以冻结runner、worker完整执行输入合同、worker receipt和当前输出绑定交叉验证，符合既定紧凑产物合同，不单列为缺陷。

## 实物核验

### 1. campaign与执行输入身份：PASS

- `campaign_identity.json`共`2,232`个清单条目、`2,231`个唯一物理文件；reviewer对当前文件逐一重算，缺失`0`、大小或SHA漂移`0`。
- `file_contract_sha256`与`contract_sha256`均可从当前清单和runtime独立重算一致；campaign文件合同为`4c374c8869abfe17a6234b82b136ba36f6795e77ead97929328f3bc0ee21557f`。
- 冻结runner当前SHA与campaign清单一致；生产HEAD为`d492ee072aa5a9d71477235d79f17d2a5db59db3`，生产工作树及workspace `vnpy`核心状态在冻结runtime中均为空。
- 四个worker各自的执行输入合同均由`1,866`个唯一物理文件组成；reviewer按对应eligibility重建四份合同，均与各自receipt中的`execution_file_contract_sha256`逐值一致。

### 2. 固定四job与eligibility：PASS

- `jobs.csv`固定为`351`个main加`4`个A2 sentinel，共`355`个development任务；eval范围为`2022-04-29 -> 2025-06-30`。
- 当前仅有四个输出目录，且集合精确等于：`20220429_R10`、`20220429_R10_A2`、`20220531_R10`、`20220531_R12`。
- eligibility文件恰为`351`份并与351个main任务一一对应；全量audit中rank10均相对正式eligibility零改动，rank11..18均只改目标月正式rank10行。
- 固定四job中，前三个rank10/A2相对正式eligibility零改动；`20220531_R12`只改`2022-05-31:rank10`一行，目标产品与`jobs.csv`一致。

### 3. A/A确定性：PASS

- `20220429_R10`与`20220429_R10_A2`的八个正式输出逐文件SHA一致：`summary`、`label`、`curve`、`combined`、`trades`、`entry_candidates`、`entry_risk`、`trade_events`。
- worker receipt因PID、TMP和时间不同而预期不同，未错误纳入A/A业务输出比较。

### 4. 决策前payload：PASS

- 活跃月`20220531_R10`与`20220531_R12`的决策前五类归一化SHA全部一致：`curve`、`trades`、`entry_candidates`、`entry_risk`、`trade_events`。
- 五个键集合完整，独立比较结果与`smoke_receipt.json`中的`active_predecision_gates`一致。
- 冻结实现按执行日期切分，并额外用AI快照信号日约束entry语义，不再把eval日产生、下一交易日执行的诊断误判为决策前漂移。

### 5. entry signal边界：PASS

- 两个活跃job的目标期`entry_candidates`均非空，执行日期全部满足`eval_date < date <= next_eval_date`。
- `ai_product_pool_signal_date`无缺失且全部等于当前`eval_date=2022-05-31`；receipt记录的目标行数、非空信号数和当前CSV行数一致。
- receipt中的决策前信号日全部严格早于当前eval date，目标期信号日集合与当前CSV独立重算一致。

### 6. curve/combined/trades对账：PASS

- reviewer从四个job当前`label.json`、`curve.csv`、`combined.csv`和`trades.csv`独立复算：期末权益减基础权益、目标期净PnL、滑点、交易数及trade行数全部闭合。
- 四个job独立重算的最大绝对误差为`4.656612873077393e-10`，低于预注册阈值`1e-9`；与worker receipt逐项记录的误差差值为`0`。
- 六类紧凑payload的日期均在各自`(eval_date, next_eval_date]`内；summary和curve的`window_label`均与真实结束日一致。

### 7. runtime、PID、TMP/MPL隔离：PASS

- 四个worker PID互不相同，四份`TMPDIR`互不相同，四份`MPLCONFIGDIR`互不相同；路径均同时绑定campaign、job和唯一run id。
- 四份runtime只归一化预声明的job级环境字段后得到同一个SHA；其他环境、解释器、包、启动钩子、仓库状态未被归一化隐藏。
- 每份receipt的runtime自算SHA一致，`checkpoint_reused=false`、`completed_result_reused=false`；四个worker PID在审查时均已退出。

### 8. 600秒门：PASS

- 冻结runner设定`MAX_JOB_SECONDS=600.0`，父进程`subprocess.run(..., timeout=MAX_JOB_SECONDS)`覆盖完整worker进程；worker内部也在发布receipt前执行墙钟门。
- 四份worker receipt最大墙钟为`55.687765`秒；reviewer由唯一日志文件创建run时间戳到日志完成mtime独立估算的父进程最大完整时长为`56.715983`秒，均远低于600秒。

### 9. 训练标签与holdout隔离：PASS

- campaign中不存在`development_labels.csv`、聚合`reconciliation.csv`或模型文件；仅存在固定四job自己的`label.json`，因此尚未发布训练面板。
- `jobs.csv`中sealed holdout任务数为`0`；四个已有label job均属于固定smoke集合，且没有eval date达到或晚于holdout起点`2025-07-31`。
- `smoke_receipt.json`的`publishes_training_labels=false`与`sealed_holdout_label_count=0`均由当前目录实物独立验证，而非只采信自报字段。

### 10. smoke receipt绑定：PASS

- receipt的`campaign_id`、campaign文件合同、固定四job列表和decision均与当前campaign一致。
- 对每个job，receipt绑定的`worker_receipt_sha256`等于当前worker receipt；绑定的八份输出SHA映射等于worker receipt映射，也等于reviewer对当前输出文件的重算值。
- `progress.json`记录`smoke_passed`、完成`4/355`，decision为`stage015_smoke_pass_allow_full_development_batch`；不存在从其他campaign复制PASS而仍能通过当前输出绑定的证据。

## 验证

- 定向测试：`11 passed in 0.51s`。运行时禁用pytest仓库缓存并把临时目录放在`/private/tmp`，未生成新的研究产物。
- 审查前campaign全树摘要SHA为`88cfdbab0011cf40a785790a0619e7dbe7bcf04fcc8915be90191cb423150fe7`；落盘后应保持不变。

## 最终判断

- 过拟合：否。本次没有按部分标签值挑模型、任务、rank、特征或阈值，只审查冻结执行合同与可复现性。
- 是否值得继续：是。身份、确定性、边界、金额、隔离和发布门均闭合，继续补齐同一campaign的完整development标签具有明确价值。
- `ALLOW_FULL_DEVELOPMENT_BATCH`：允许复用四个已绑定完成job并继续其余冻结任务。完整批次仍须重新计算smoke gates、完成355个job的终态身份与对账门；任何campaign identity或当前四输出漂移都必须fail-closed。
