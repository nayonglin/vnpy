# Stage249：正确性回放的交易日分钟补数与来源闭环

记录时间：2026-10-15 16:35（Asia/Shanghai）；本文件由数据准备子任务独立维护，不改 LINE、registry 或根 memory。状态：strict_final 最终实际数据访问闭环已于 17:06 完成，数据输入保持冻结。

本次不是策略突破版本，而是正确性与可复验性修复。未新增、修改或删除 alpha、资金、止损、AI 月池或品种参数。正式身份仍为 `m0008_20261008T204054+0800_2a7420a9f955`，规则 `stage037_stage034_long_short_mirror_hard_block_v1`，C9 15 万，静态基础宇宙 19 品种；正式 manifest 不得为允许修复代码而改写。比较窗口冻结为 2020-01-01 至 2026-10-14。

是否过拟合：否。任务由统一交易日时段、实际 entry 扫描后缀与 ordinary 开平仓首分钟决定，不按 PnL 或回撤挑选样本。是否值得继续：是。普通成交首锚与夜盘归属会改变真实执行价格，未闭合的分钟来源不能支持严格回放结论。

## 调研与判断

TqSdk 官方 `get_kline_serial` 支持最多 10000 根（https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html），官方代码为 https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py 。采用每合约独立 serial，不用多合约对齐 serial；每批覆盖最多 14 个自然日跨度，快照为最后请求自然日次日 08:00。仍逐原任务裁片、检查完整网格、最早/最晚边界、完成时间及源 SHA，批量改变只影响补数效率。

日历合同与修复源码的 `qmt_roll_intraday_execution.session_minutes` 逐分钟交叉断言。日盘 225 分钟；允许前一交易日夜盘、周五至周一连接及周六凌晨片段；较长节假日间隔不虚构前夜；保留 2020 夜盘暂停规则。不能用旧 Stage246 的“每自然日必须含 225 根日盘”去拒绝独立夜盘/凌晨片段。

## 数据与解释器

- 基线：`/Users/mac/.codex/worktrees/formal-2020-replay/fian`。
- 修复：`/Users/mac/.codex/worktrees/formal-correctness-replay/fian`。
- Python：`/Users/mac/.codex/worktrees/formal-2020-replay/fian/.py311/bin/python`。
- 凭据只从 `/Users/mac/Documents/Codex/fian-research-20261014/.vntrader/vt_setting.json` 读取，不输出凭据或异常正文。
- 本线 Stage249 独立输出根：修复工作区 `research/lines/futures_trend_rollover_shape_same_volume/outputs/stage249_correctness_replay`。
- Stage861 原 cache SHA：`e78af805778ca7af7976d0b6d79b3248dda756aafd8c26fa98c0e59f7b9560b9`。
- 优先复用 Stage246 `entry_minute_download` 已验收 parquet；原 Stage861 中缺来源证明的片段，即使网格齐全，也刷新完成快照。

## 已有证据

1. 基线实际开仓要求 1229 个自然日时段，980 段可与 Stage246 来源逐值确认；其余 249 段需要新证明。它比只查网格的 212 段多 37 段。
2. 旧路径三分片在 2025-08-22 遇单次 `SSLError`，全组 fail-stop，返回码 1/-15/-15。没有重试风暴。逐 proof 重算已完成 207/249 段、26490 分钟、零错误，42 段进入新队列。
3. 10000 根单连接探针成功。四个独立合约、480 分钟、OHLC/volume/open_oi/close_oi 共 3360 个数值与已验收 1000 根快照精确一致。周六凌晨 cu2104 的独立 60 根探针通过。
4. 新队列含旧 42 段、第一轮新增 15 段、全部 ordinary 首锚新增 188 分钟，共 245 段、211 自然日、96 批。稳定批次分三 shard，各 32 批，最多三路行情会话；每 worker 首个失败即停止，全组联动停止。
5. 第三轮实际扫描 503 条，对应 314 entry keys、1212 个后缀片段、104220 分钟；ordinary 首锚 536 个。与在途计划逐分钟去重后新增 18 个首分钟，初次从旧完成 raw 快照复用 1 个；其余将在当前 10000 根 raw 完成后再复用，仍缺才下载。
6. 独立 reviewer 用同一 Python 重跑 31 项数据测试全绿，独立重算 207 段、480 根等价探针、60 根周末探针均通过；源代码审计暂未见阻塞问题。原 cache 1380860 行 CSV 内存 roundtrip 的七个行情字段没有数值变化。

## 最终验收与待办

- 逐 proof 核验任务身份、patch SHA、raw SHA、实际序列边界、完整网格和 raw→patch 七字段逐值一致；拒绝重叠与未请求分钟。
- 把新片段先合到独立 candidate cache；保留原有全部时间戳与列，仅替换明确键的行情/来源；原文件 SHA 必须保持不变。
- 对第三轮实际 entry 后缀与全部 ordinary 首锚分别做 candidate→Stage246 或 Stage249 完成快照来源闭环。
- 合并前通知主任务确认无引擎写缓存；按预期 SHA 原子合并、保留备份。正式严格回放后仍须按新实际路径重复访问闭环，不能只凭本轮计划推定路径稳定。
- 本子任务没有运行策略引擎，无新增回测收益、期末权益、最大回撤、Sharpe、胜率、滑点或交易次数；这些指标由主任务的严格回放及独立 review 另行记录。

## 2026-10-15 16:41 合入补记

全部 470 个补丁任务、33282 分钟完成；第三轮新增 18 个首锚中复用 5 个完成 raw、下载 13 个。候选 entry 来源 1212/1212（961 Stage246、251 Stage249），ordinary 首锚来源 536/536（98 Stage246、438 Stage249），缺口和错误均 0。

独立审计未复用实施者 verifier，实现 294 个 proof、232974 个行情数值 raw→patch→candidate 精确比较；1376083 个非补丁旧行所有列逐值未变，4777 个重叠旧行受保护列不变。最终新增 28505 个键、没有删除旧键；七个行情字段的全部重叠键变化数量为 0。

实际 cache SHA：`761ad13a8ed77bd5d143f01bd1dce59189f9f3c659d0f0e8f2d62ddaf8bdbe97`。来源 manifest SHA：`cc35119cd246102de716527ec3f1427649c40cd84e3ea674e476119205741e67`。合入报告 `outputs/stage249_correctness_replay/cache_merge_diagnostic3/merge_report.json`；最终 identity 与基线/备份验证在同目录 `applied_candidate_identity.json`。

本轮数据门完成仍不代表最终路径稳定：主任务接着运行 diagnostic_round4，按其实际 entry 后缀和 ordinary 首锚继续验收。继续补数仍非过拟合：只满足既定执行规则的数据依赖，不根据收益选择缺口。

## 2026-10-15 16:50 第四轮实际路径闭环补记

第四轮新增需求为 32 片段、1367 分钟，与独立 reviewer 重算的 entry/anchor 缺口 union 逐时间戳完全相等。8 个首分钟复用完成 raw，24 片段按 10 批三路下载，全部返回 0，无新增网络失败。

累计 502 个授权任务、34649 分钟、312 proofs。第四轮实际 entry 319 keys、1236 片段、106515 分钟全部有源证明（964 Stage246、272 Stage249）；ordinary 首锚 537 个全部有源证明（93 Stage246、444 Stage249）。独立审计 242543 个行情数值 raw→patch→candidate 精确一致；1375857 个非 patch 旧行全列不变，33508 个重叠旧行受保护列不变，新加 1141 个时间戳，0 旧键删除，7 行情字段重叠值变化均为 0。

16:50 实际缓存按预期 SHA 原子合入，最终 SHA `cc46709864db5b4d22f13673c02558c10d786d1f9846b9c11a2d3d8435974c22`；502 任务 manifest SHA `5bc7066004b39eb701a686925f885b5d8143e2a7ae8c436bc3526bab6d1f971c`。证据位于 `outputs/stage249_correctness_replay/cache_merge_diagnostic4` 和 `independent_candidate_diagnostic4_audit`。旧实际 cache `761ad13…` 备份通过；正式基线 `e78af805…` 仍未变。

主任务继续 diagnostic_round5，不能因第四轮门通过就声称新路径已经稳定。策略参数没有变，本轮继续只处理实际访问数据依赖。

## 2026-10-15 17:02 第五轮末端两首锚补记

第五轮实际 501 条入场扫描全部完整，独立源审计确认全部 106515 分钟一致；535 个 ordinary 首锚只缺 2 个平仓首分钟，无隐藏来源缺口。jm2305.DCE 的 2023-02-28 21:00 与 au2602.SHFE 的 2025-12-04 21:00 各补 1 分钟，其中 1 个从完成 raw 复用、1 个单连接下载。

两笔新真实 open 分别为 2014、954.5，与第五轮实际成交、fallback price 完全相等；实际 execution_clock 与 expected_start/new bar timestamp 也相同。原 anchor.actual_time 为空源于缺 verified minute，因此通过 trades.order_id→trade_id→execution_clock 关联验证实际时刻，未把空值当作等价。实施者与独立 reviewer 均逐值确认，证据 `candidate_cache_diagnostic5/two_anchor_equivalence.json` 和 `independent_candidate_diagnostic5_audit/independent_two_anchor_equivalence.json`。

累计 504 授权任务、34651 分钟、314 proofs。独立审计 242557 个 raw→patch→candidate 七字段值精确相等；仅新增 2 个键、旧键 0 删除，非 patch 旧行全部列未变。第五轮全部实际 entry/anchor 来源闭环通过。

17:01 原子合入、17:02 identity 核验完成。最终实际 cache SHA：`a9566e64c1165a5fd0e62bbae6191b522526646a081e724064876a24bc80a74e`，504 任务 manifest SHA：`1f9433b340c379e90830ba35a38d45626dfba6c42b0a2eee2652ab2bdb8fc0ff`。基线 `e78af805…` 未变，上一实际 cache `cc467098…` 备份正确。主任务可直接进入 strict_final；最终实际请求仍须重新独立验源。

## 2026-10-15 17:06 strict_final 实际访问终验

严格回放正常退出，`diagnostic_incomplete_minutes=false`。实际重新生成请求计划：501 条入场扫描、319 个交易日/合约 keys、1236 个时段片段、106515 分钟；535 个 ordinary 成交首锚。相对累计 504 个补丁任务新增缺口 0，两个实际访问集合去重共 106731 个分钟键。

实施者只读终验全部 complete：entry 1236/1236（964 Stage246 来源逐值一致，272 Stage249 来源逐值一致）；anchor 535/535（93 Stage246、442 Stage249）。完整网格、源 SHA、完成快照上下界及七字段逐值均通过，缺口 0、errors=[]。运行 provenance SHA `31b90ff59f31e55c60f29efeefaf588f6f3d73c38e6cb82fc332cb9423fe9358`，其 `minute_input_sha256` 与实际冻结 cache 均为 `a9566e64c1165a5fd0e62bbae6191b522526646a081e724064876a24bc80a74e`；运行内和终验前后输入均未变，基线仍为 `e78af805…`。

最终数据汇总：`outputs/stage249_correctness_replay/strict_final_source_validation/final_data_summary.json`。分集合证据为其下 `entry/cache_source_validation.json`、`anchor/cache_source_validation.json`；最终实际任务为 `strict_final_minute_plan/entry_all_segment_tasks.csv` 与 `anchor_all_segment_tasks.csv`。独立 reviewer 对最终实际来源与结果的审计另行归档；本文件仅总结数据准备与访问闭环。

结束反思：本次没有过拟合。新增片段只由冻结执行规则的实际时间依赖触发，没有按收益选数据、改窗口、改 alpha 或改正式 manifest。当前数据补数子任务是否值得继续主动扩大：否，冻结窗口与最终实际访问已经闭合；继续下载相同任务不增加证据。后续只有新的明确数据依赖或审计发现才应重开补数，策略/账户/统计结果继续由主任务及独立审计判断。
