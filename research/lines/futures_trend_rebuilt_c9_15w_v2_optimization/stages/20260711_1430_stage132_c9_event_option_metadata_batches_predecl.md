# Stage132 当前 C9 真实事件期权 metadata 原子分批采集预声明与实施计划

> **执行要求：** 本阶段只采集 Stage131 冻结事件在各自历史入场日可见的期权合约 metadata。先做 10 事件 canary，硬门通过后才允许续跑全部 365 事件；不获取 premium/bar/bid-ask，不选择 strike/DTE，不回测收益，不修改策略或实盘。

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`day`
- 预声明时间：`2026-07-11 14:30 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage131 后的授权历史 metadata 采集与覆盖审计；不是策略候选
- 是否重要突破：待 365 个事件终态与覆盖结果
- 是否触发 A/B：否；本阶段固定 `ready_for_option_strategy_ab=false`

## 外部调研与判断

- TqSdk 官方 API 文档说明，`TqApi(..., backtest=TqBacktest(...))` 会进入历史回放模式并由 `TqBacktest` 推进指定区间；`query_options(underlying_symbol, expired=False)` 用于查询当前时点未下市期权。
- TqSdk 官方 GitHub 当前最新 release 高于本机版本，但本阶段冻结已被 Stage130 真实探针验证的本机 `tqsdk=3.9.4`，不在采集中途升级依赖。
- 本地 Stage118 已验证同文件系统临时产物经严格审计后用 `os.replace` 原子发布；Stage132 复用该原则，但按 event/attempt 目录发布，失败尝试保留且不覆盖成功缓存。
- 我的判断：顺序单会话比并发共享 API 更可复算；逐事件独立 `TqBacktest` 比一条长回放更能固定 PIT 时点。metadata 只解决“当时有哪些合约”，不解决 premium、流动性、报价可得性或保护效果。

## 冻结输入

- Stage131 query events：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage131_c9_event_targeted_option_acquisition_manifest/rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest_query_events_stage131_c9_event_targeted_option_acquisition_manifest_v1.csv`
- SHA256：`7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a`
- 文件大小/行数：`100190 bytes / 365 rows`
- Stage131 manifest SHA256：`63184047a307e0e5e9ce1406fa8ddb614fff4635ad22885fd936d63dcfea9f1c`
- 固定列：`event_id/vt_symbol/tqsdk_underlying/product_vt_symbol/entry_date/query_start/query_end/query_expired_as_of_entry/...`
- 输入硬门：365 行；event_id 唯一且可由 `sha256(vt_symbol|entry_date)` 重算；`query_expired_as_of_entry=false`；query_start/query_end 与 entry_date 同日；不得读取 Stage847 收益、winner、2022 结果标签或资金曲线。

## 方案比较与裁决

1. **顺序单事件 + 原子 attempt（采用）**：每个事件创建独立 `TqApi(TqSim(), TqBacktest(entry_date))`，获取后关闭；失败影响只限单事件，可断点续跑，PIT 边界最清晰。
2. **多进程/多会话并发（暂不采用）**：预计更快，但会增加限流、认证、会话资源和非确定性风险；当前顺序估算约 16 分钟，没有必要承担复杂度。
3. **单一长回放批量查询（否决）**：回放推进与 query 时点容易错位，一个连接失败会放大到全部事件，也难以证明每条请求的历史上下文。

## 固定批次与 canary

- 批次大小固定 `10`，共 `37` 批；顺序为 canary 10 条在前，其余按 event_id 升序。
- canary 选择不看 metadata/收益结果：先按交易所取最新 entry_date 事件各一条，再从剩余事件按 event_id 升序补到 10 条。
- canary 固定覆盖 `CZCE/DCE/GFEX/SHFE`、`9` 个产品和 `2018/2020/2022/2025/2026`，只验证 extracted/empty/failure 路径，不用于外推 365 条覆盖率。
- canary event_id：
  - `3734ac5af36029dd053580b4fad920d86d52b0b75a004451933639740e6a7707`
  - `b13e8f7de7837203b0d80c8e01c30290633b2f8bfb97038e8c0e28ec84069a91`
  - `69989dc6767a65b044ea3e1144ced85e993f684e427aa3d647add80da79f58a9`
  - `183c0046ccaa1726d6b1145c4b31f9c947a6f9b8d8d59465021fb5eff84a00af`
  - `00a1c59abb9ac9f1c27af02916c2b8ed12ea05ca0f73d8396ddee9b98dc9dec7`
  - `00be208c04f58cb91a64725106c79807fccf30b64c276ac88778df32d1271fa2`
  - `014a6683b4ac65ea3ede26ddc94657263b42f749b3a724afcd80c8114a8b5793`
  - `0152ff95a1dd4cd827a5f30b04a427e27f6bea6eecca567f84a06c6500a4b311`
  - `01616f42cee547655a1fc0e8a690d110a413e5b7efb5564dcee115f02132238c`
  - `0168ddc1fecf2a42778e6a163eec0b3056c536ac02c79b7543f6e0e7897f1529`
- canary 硬门：10/10 都有可验证 attempt manifest 与唯一 cacheable 终态；不得出现 authentication_failed/timeout/query_failed/integrity_failed；至少 1 条 extracted，以实际验证 untouched + normalized 路径；凭证泄露、订单 API、CTP/live 变更均为 0。cacheable 终态只允许 `extracted/empty_chain/underlying_not_in_option_catalog`，第三类必须有精确 vendor GraphQL 目录缺失证据并继续保留在 365 分母。任一失败则停止，不自动更换 canary 或继续全量。

## 每事件历史查询语义

- `start_dt = entry_date 00:00:00`，`end_dt = entry_date 23:59:59`，时区语义固定 Asia/Shanghai。
- 每事件独立 `TqApi(TqSim(), backtest=TqBacktest(start_dt, end_dt), auth=TqAuth(...), disable_print=True)`。
- 调用 `query_options(tqsdk_underlying, expired=False)`；不传 strike、option_class、exercise month/year，不按保护方向过滤 metadata。
- 非空 symbol list 才调用 `query_symbol_info(symbols)`；不得调用 quote、K线、tick、Greeks、下单或账户接口。
- 每事件最长 `60s`，包含 `api.close()` 资源释放；一次运行只产生一个新 attempt。只有最终验证器通过的 cacheable terminal 可跳过，失败/不完整/旧 producer lineage 缺失 attempt 后续可重试但不得覆盖。

## 终态与 fail-close

- `extracted`：option symbol 非空，untouched/normalized metadata、schema、request/status/manifest 全部落盘并通过逐项 hash、symbol 集合和字段审计。
- `empty_chain`：`query_options` 无异常且返回空列表；保存 request、空 symbol list、status、manifest。只表示历史时点查询为空，不自动解释为交易所未上市。
- `underlying_not_in_option_catalog`：仅当脱敏错误同时包含 GraphQL operation、`instrument_id` 和 `contains non-existent instrument`，且该 underlying 来自已通过 Stage131 hash/schema 的真实交易事件时成立；保存原失败证据，metadata 覆盖计 0，不改写成 empty_chain，也不从分母删除。
- `authentication_failed`：认证/权限错误，属于全局停止条件，不计 empty。
- `timeout`：超过 60s，属于失败终态；不发布 extracted/empty cache。
- `query_failed`：其他异常，错误消息脱敏后落盘；不发布 extracted/empty cache。
- `integrity_failed`：API 返回与 symbol/metadata/schema/hash 对不上；不发布成功缓存。
- 每个 attempt 必有且只有一个终态；汇总不得静默丢行。只有 `extracted/empty_chain/underlying_not_in_option_catalog` 是 cacheable terminal，其中 catalog-missing 必须在缓存校验时重做精确错误分类。

## 原子目录与数据合同

- 根目录：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage132_c9_event_option_metadata_batches/`
- attempt 临时目录与最终目录必须在同一文件系统；写完后校验，再以 `os.replace(temp_dir, attempt_dir)` 发布。
- 每 attempt 文件：
  - `request.json`：event/input hash、SDK/Python 版本、历史窗口、参数和开始时间；不含凭证值。
  - `option_symbols.json`：query_options 返回的有序 symbol list。
  - `untouched_metadata.csv`：`query_symbol_info` DataFrame 的全部源列和值，不删列、不改名、不排序；它是 untouched API DataFrame snapshot，不冒充 wire-level raw payload。
  - `untouched_schema.json`：源列顺序和 pandas dtype。
  - `normalized_metadata.csv`：只做显式字段映射和时间/数值归一化。
  - `status.json`：唯一终态、行数、耗时、脱敏错误、hash 审计。
  - `manifest.csv` + detached SHA256：除 manifest/checksum 自身外逐文件 bytes/hash。
- normalized 最低字段：`option_symbol/underlying_symbol/option_class/expire_datetime/last_exercise_datetime/strike_price/expired/volume_multiple/price_tick`。
- request producer lineage 必须记录生成该 attempt 的 `tool_sha256/test_sha256/predecl_sha256`；缺任一项的旧 attempt 只保留法证，不得作为成功缓存。
- extracted 硬门：option_symbol 唯一、与 option_symbols 集合一致；underlying 全部等于请求标的；option_class 仅 CALL/PUT；strike/expiry 非空且合法；expired 不得为 true；untouched/normalized 行数一致；并从 untouched 重新 normalize 后逐列逐值与落盘 normalized 相等。
- catalog-missing 硬门：错误中提取出的唯一 non-existent instrument 必须逐字等于本 request 的 tqsdk_underlying；其他标的或多标的错误仍为 query_failed。

## 汇总与准入门

- 输出 batch_plan、attempt_status、event_terminal_status、coverage_by_year/product/exchange、source/lineage、manifest、decision、report。
- 365 事件必须全部有 cacheable terminal 才能称请求账本完整；任何 authentication/timeout/failure/integrity/missing 均保持不完整。catalog-missing 只闭合请求终态，不计入 metadata 覆盖。
- `request_ledger_completion_ratio = cacheable_events / 365`；`metadata_coverage_ratio = extracted_events / 365`；empty_chain/catalog-missing 单列且都不从分母删除。
- 本阶段无论覆盖率多少，`ready_for_option_strategy_ab=false`。下一阶段是否继续 premium 采集，必须由覆盖分布、上市年份和空链归因的独立 review 决定，不能按 2022 或策略盈亏删事件。

## TDD 计划

- [x] 写失败测试：冻结输入 hash/schema/event_id/query window 任一漂移必须 fail-close。
- [x] 写失败测试：canary 选择机械复现为固定 10 个 ID，批次总数固定 37。
- [x] 写失败测试：normalization 保留 untouched，正确处理秒/ns/datetime 三种 expiry，不把 datetime64[ns] 二次按秒解析。
- [x] 写失败测试：extracted/empty_chain/catalog-missing/auth/timeout/query/integrity 终态和 cacheability。
- [x] 写失败测试：attempt manifest 排除自身/checksum，bytes/hash 与 detached checksum 闭合。
- [x] 写失败测试：已有合法 cache 跳过；破损 cache 不跳过；失败 attempt 不覆盖。
- [x] 最小实现 plan、normalization、audit、attempt writer、resume、decision；网络层以 injected fetcher 测试。
- [x] plan-only 运行，复核 365/37/canary/source hash，订单/CTP/live 静态扫描为 0。
- [ ] 启用网络只跑 canary 10 条；独立 agent 审查 canary 代码、数据、终态、hash、凭证隔离。
- [ ] canary P0/P1 清零且硬门通过后续跑剩余 355；否则停止，不换样本救采集器。
- [ ] 全量结束后再拉独立 agent 复核 365 个终态和覆盖置信度。

## 14:45 canary 首轮实施注记

- 固定 10 条 canary 首轮结果：`3 extracted + 5 empty_chain + 2 query_failed`，程序按硬门停止，未继续剩余 355 条；认证失败、timeout、attempt integrity、凭证泄露、订单/CTP 均为 0。
- 两条失败固定为 `CZCE.MA809@2018-07-09`、`CZCE.SM009@2020-07-17`，错误均为 vendor GraphQL `instrument_id ... contains non-existent instrument`。
- 三位/四位别名诊断均失败；同期 `CF009/SR009/MA009` 也报相同目录错误，而 `SM101` 能正常返回空列表。由此否决“简单展开四位年份即可修复”的假设，归因为 vendor 历史期权关系目录缺口。
- 实施修正不换样本、不删事件、不改 extracted/empty 结果：新增独立 cacheable 终态 `underlying_not_in_option_catalog`，只接受精确三条件错误；原 query_failed attempt 永久保留，重试只新增 attempt_0002。
- 该修正属于数据源终态分类，不是收益救参；全量 metadata coverage 分子仍只计算 extracted，catalog-missing 继续计 0。

## 15:08 独立 review 与修复门

- 独立 agent `Locke` 对修正后 canary 终审：`P0=0/P1=2/P2=3`，数字置信度 `99.99%`、语义置信度 `97%`；明确不批准 remaining 355。
- P1-1：旧缓存验证只重跑字段合法性，没有证明 persisted normalized 逐值来自 untouched；已新增正值漂移反例（strike +1、expiry +1天、multiplier ×2）并要求重算逐列全等。
- P1-2：catalog-missing 旧分类只看错误关键词，没有把错误 instrument 绑定本次 request；已新增外部标的反例并要求唯一 instrument 逐字等于 requested underlying。
- P2-1：旧 60s 门不含 `api.close()`；已把 close 放入同一 wall-clock timeout 的 finally。
- P2-2：旧 decision 只写计数；已新增固定 365 分母的 request-ledger completion ratio 与 metadata coverage ratio。
- P2-3：旧 attempt request 没有 producer tool SHA；已新增 tool/test/predecl SHA，并让旧12个 attempt 因 lineage 缺失自动失去 cache 资格但永久保留。
- 额外 fail-close：malformed schema JSON 不得让审计器自身崩溃；先 RED 复现 UnboundLocalError，再初始化 comparison 状态并转绿。
- 最终 plan-only 又发现旧 invalid attempt 的 terminal 文本仍进入 coverage 分子，出现 completion `0` 但 metadata coverage `3/365` 的矛盾；新增反例后，所有 extracted/empty/catalog 分子均只统计 `cacheable=true`，其余统一进入 failure-or-missing。
- 修复后 Stage132 focused tests `19/19`；必须重跑同一固定 canary 10条并再次独立 review，P0/P1 清零前仍禁止 remaining 355。

## 15:25 第二轮增量 review 与最终数值全等修复

- 同一独立 agent 增量终审为 `P0=0/P1=1/P2=0`；catalog instrument、close timeout、固定分母 ratio、producer lineage 四项均关闭。
- 唯一剩余 P1：numeric comparison 使用 `np.isclose` 默认相对容差，`strike 3000.00 -> 3000.01` 会误判相等。原多字段 drift 测试会被 expiry/multiplier 变化掩盖，已拆为单变量 `+0.01` 反例并确认 RED。
- 修复：numeric persisted/recomputed 比较固定 `rtol=0.0, atol=0.0, equal_nan=True`，单变量反例和全部 focused tests 转绿。
- 为让最终 canary producer tool SHA 对应最终验证器，新增仅 `canary/all` canary 段可用的 `STAGE132_FORCE_CANARY_RETRY=1`；remaining 路径不接收 force。旧22 attempts 继续保留，最终同一10条再新增10个 attempt，不覆盖、不删样本。
- 最后一次 canary 仍必须经独立增量复核清零 P0/P1，方可执行 remaining 355。

## 运行前反思

- 过拟合：否。事件全集和 canary 选择都在看到 metadata 返回前冻结，不读取策略收益或 2022 标签；没有 strike/DTE/保护比例参数。
- 继续价值：有。metadata 是验证历史期权保护可行性的必要但不充分条件；顺序原子采集能把数据缺口从猜测变成逐事件证据。
- 停止边界：Stage132 不得顺手下载 bars/premium、算 IV/Greeks、选期权、做收益曲线或修改实盘。
