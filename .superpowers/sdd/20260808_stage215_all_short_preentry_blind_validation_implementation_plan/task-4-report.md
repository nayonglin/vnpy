# Task 4 报告：真实补数、匿名 case 生成与映射封存

## STATUS

**READY**

- 冻结空头事件：`64/64`。
- 五个官方交易日分钟数据完整：`64/64`。
- reviewer case：`64/64`。
- 匿名图：`64/64`。
- 图片集合与 reviewer manifest：一致。
- 盲态泄漏审计：通过，`violations=[]`。
- 阻断项：无。
- 未读取或使用 Stage213 标签；本任务只接触 Task4 controller 输入和本任务生成物。

## 调研与独立判断

- 在线复核了 TqSdk 官方 `TqBacktest`/`get_kline_serial(..., 60)` 历史回放文档，以及 `shinnytech/tqsdk-python` GitHub 仓库。
- 仓库已有 Stage859/Stage900 使用同一接口补 exact-contract 分钟缺口的实现和成功记录。
- 独立判断：继续复用当前合法授权下的 `TqBacktest + 1m K线` 是本任务最可靠的真实补数路径；没有理由使用主连替代、跨月拼接、插值、前填充或删样本。
- 参考：<https://doc.shinnytech.com/tqsdk/latest/advanced/backtest.html>；<https://github.com/shinnytech/tqsdk-python>。

## 真实覆盖与补数过程

首次运行 prepare 的结果：

- `complete=56`
- `partial=5`
- `missing=3`
- `analyzable_event_count=56`
- prepare 按设计非零退出：`analyzable_event_count_below_60`

来源顺序严格按设计执行：

1. Stage861 冻结分钟文件；
2. 全仓库 exact-contract raw cache；
3. 本地 vn.py 1 分钟数据库；
4. 仓库现有合法授权 TqSdk `TqBacktest` 回放入口。

首轮 8 个事件缺口及处理：

| open_trade_id | 精确合约 | 初始状态 | 缺失官方交易日 | Stage861 / raw cache / vn.py DB | 授权回放结果 |
| --- | --- | --- | --- | --- | --- |
| BACKTESTING.19 | CF005.CZCE | partial | 2020-03-06 | 缺该日目标行 | 225 根，成功 |
| BACKTESTING.57 | SM009.CZCE | partial | 2020-07-10 | 缺该日目标行 | 225 根，成功 |
| BACKTESTING.58 | SA009.CZCE | partial | 2020-07-13 | 缺该日目标行 | 345 根，成功 |
| BACKTESTING.363 | lh2303.DCE | partial | 2022-12-08 | 缺该日目标行 | 225 根，成功 |
| BACKTESTING.551 | ru2509.SHFE | partial | 2025-03-28 | Stage861 从 2025-03-31 起，缺该日 | 345 根，成功 |
| BACKTESTING.587 | FG601.CZCE | missing | 2025-10-29、10-30、10-31、11-03、11-04 | 五日均无目标行 | 每日 345 根，全部成功 |
| BACKTESTING.589 | FG601.CZCE | missing | 2025-10-29、10-30、10-31、11-03、11-04 | 与 BACKTESTING.587 同一精确合约/日期集合 | 复用同一批真实补数，全部成功 |
| BACKTESTING.630 | FG609.CZCE | missing | 2026-06-16、06-17、06-18、06-22、06-23 | 五日均无目标行 | `345/345/225/345/345` 根，全部成功 |

共发起 `15` 个唯一 exact-contract/date 请求，`15/15` 成功，取得并导入本地 vn.py 分钟数据库 `4,695` 根真实 1 分钟 K。每份原始 CSV 均通过：

- 精确 `vt_symbol` 一致；
- 日期一致；
- 时间戳无重复；
- OHLC 非空且 high/low 关系合法；
- 原始路径、行数、首末时间、SHA256、补数时间和质量结论已记录。

最终 `data_gap_audit.csv`：`complete=64`，没有 residual minute gap。

核心证据：

- `authorized_tqsdk_backfill_status.csv`
- `authorized_tqsdk_source_audit.csv`
- `authorized_tqsdk_raw/*/*.csv`
- `minute_source_manifest.csv`
- `data_gap_audit.csv`

## R 状态

- `resolved=61`
- `unresolved=3`
- 保持 unresolved 的三笔：
  - `BACKTESTING.166 / lh2109.DCE / 2021-04-12`
  - `BACKTESTING.265 / SA205.CZCE / 2021-12-29`
  - `BACKTESTING.589 / FG601.CZCE / 2025-11-05`
- 未从 realized PnL 或赢家身份反推 risk amount / aggregate R。
- 当前冻结输入没有可用于统一重建三笔原始风险基数的字段链，因此按设计保持 unresolved。

## 匿名图片与密封映射

- 图片绝对目录：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage819_intraday_rules/outputs/stage214_all_short_preentry_blind_validation/blind_charts`
- 图片数量：`64`
- bundle 算法：`sha256(sorted chart_file + NUL + file_sha256 + LF)`
- bundle SHA256：`dc3dd1c2314536ad8c167a9129e6c023c0eabdfc2318ecff1f31686d42aec058`
- 逐图哈希：`blind_chart_sha256.csv`
- bundle 描述：`blind_chart_bundle.json`
- 密封 controller 映射：`blind_mapping.csv`
- 审阅者清单：`reviewer_manifest.csv`
- PNG 未提交 Git。

## 验证命令与输出

### prepare

```text
.py311/bin/python research/lines/futures_trend_stage819_intraday_rules/tools/stage214_all_short_blind_prepare.py
```

最终输出：

```text
status=ready
event_count=64
analyzable_event_count=64
chart_count=64
chart_set_matches_reviewer_manifest=true
blind_artifact_audit.ok=true
blocking_reasons=[]
```

完整首轮失败和最终成功日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-prepare.log`

### prepare 单测

```text
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py -v
35 passed in 15.63s
```

完整日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-prepare-tests.log`

### brief 不变量

```text
{'events': 64, 'review_cases': 64, 'charts': 64}
```

已断言：事件数 64、reviewer 行数等于图片数、reviewer 行数不少于 60、case_id 唯一。

### 图片 hash 审计

```text
chart_count=64
all_file_hashes_valid=true
bundle_sha256=dc3dd1c2314536ad8c167a9129e6c023c0eabdfc2318ecff1f31686d42aec058
```

### Git 审计

- `git diff --cached --check`：通过。
- 核心 runtime artifact commit：`016d6dc9e`。
- commit 中包含 15 份原始精确月合约补数 CSV、完整 3.5MB `minute_source_manifest.csv`、全部小型审计/映射/decision/hash 文件。
- commit 中不包含 `blind_charts/*.png`。
- 严格排除了无关未跟踪文件 `examples/portfolio_backtesting/audit_qmt_roll_stage215_current_official_c9_full_cycle_integrity.py`。

## Concerns

1. `minute_source_manifest.csv` 约 3.5MB，因为现有 prepare 对每个发现的 raw cache 路径和每个目标 symbol 都记录尝试行；这是完整审计证据，但体积偏大。本任务没有把它当作生产代码 bug，也没有无测试改 prepare。
2. 本机 vn.py 数据库已导入 4,695 根补数 K；为避免机器绑定，15 份原始 CSV 和逐文件 SHA256 已一并提交，可在其他环境按 exact-contract/1m 重新导入。
3. 三笔 R unresolved 不阻断图片生成和分钟覆盖，但后续统计必须继续把它们当作 unresolved，除非从冻结原始风险字段按统一公式重建。
4. reviewer 交付只能包含 `reviewer_manifest.csv` 与 `blind_charts/`；`blind_mapping.csv`、`short_event_manifest.csv`、来源审计和结果字段必须继续留在 controller 侧。

## 过拟合与继续价值反思

- 结束判断：**不是过拟合**。本任务没有新增规则、参数、抽样或结果筛选，只按预注册边界补齐全部冻结样本的真实数据并做确定性匿名化；没有读取 Stage213 标签，也没有按盈亏决定补数优先级。
- 结束判断：**仍有价值继续**。64/64 的真实分钟覆盖消除了样本缺失边界，下一步双盲标注和统计可以在完整冻结总体上进行；Task4 本身到此已经完成，不应再继续扩展数据窗口或特征。

---

# Fix round1/5：完成态分钟质量修复（取代前文旧 READY）

## STATUS

**READY_AFTER_FIX1**

本节取代前文基于旧 rolling row 数据的 READY 判断。以下旧产物永久作废，不得进入盲标：

- 旧 raw：最初 15 份、共 4,695 行，全部为 `O=H=L=C` 且 `volume=0` 的未完成滚动行。
- 旧图片 bundle：`dc3dd1c2314536ad8c167a9129e6c023c0eabdfc2318ecff1f31686d42aec058`。
- 旧 runtime commit：`016d6dc9e` 中的 raw、图片 hash、decision 只保留历史法证意义。

作废证据：

- `superseded_rolling_row_audit.csv`
- `superseded_stage861_quality_audit.csv`
- 本地旧图目录：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage819_intraday_rules/outputs/stage214_all_short_preentry_blind_validation/superseded_blind_charts_dc3dd1c23145`

## 根因

1. 旧下载在 `klines.iloc[-1]` 时间变化时读取的仍是 `iloc[-1]`，即正在形成的 rolling row；因此得到 flat OHLC、零成交量。
2. 旧查询从目标自然日 `00:00` 开始，无法覆盖属于目标官方交易日的前一官方交易日晚盘。
3. 旧 prepare 只要某官方交易日出现任意一行就判覆盖，单行、缺夜盘和整日退化数据均会误判 complete。
4. Stage861 对若干同时间戳的坏行优先级高于新导入 DB，单纯导库无法替换坏 duplicate。
5. `aggregate_r=NaN` 时旧 outcome boolean 落成 False，混淆“未解析”和“结果为否”。

## TDD RED / GREEN

RED 日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix1-red.log`

RED 覆盖并按预期失败：

- unresolved R 必须输出 pandas nullable boolean `pd.NA`；
- 单行、缺夜盘、全日 flat+zero 不得 complete；
- decision 必须区分 chartable 和 result-analyzable；
- 授权 completed raw 必须覆盖已知退化 Stage861 duplicate；
- 完整授权查询证明节前无夜盘时允许受审计 session exception；
- 绝大多数 completed raw 加单个低优先级旧尾行仍应保持权威来源身份。

GREEN 日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix1-green.log`

各轮目标测试最终全部通过。

## 生产修复

- 新增逐 `vt_symbol/trading_day` 的 `minute_day_quality.csv`。
- 质量门至少检查：
  - 唯一时间戳；
  - OHLC 有限且关系合法；
  - 拒绝整日 `O=H=L=C && volume=0`；
  - 最小分钟数量；
  - 日盘/夜盘存在性；
  - 相邻可信日的分钟数量和首末时间覆盖；
  - 授权 completed query 对节前确无夜盘的显式例外。
- `data_gap_audit.csv` 只有五个目标日均 `quality_passed` 才标 complete，并记录 observed day、失败日和失败原因。
- `authorized_tqsdk_completed` raw 的 duplicate 优先级设为 4，高于 Stage861/local cache/DB。
- unresolved R 的 `outcome_ge_2r/outcome_profitable` 均为 nullable boolean `pd.NA`。
- decision 分为：
  - `chartable_event_count=64`
  - `result_analyzable_event_count=61`
- 三笔 unresolved R 继续进入 64 图和后续边界处理，但不计入结果可分析数。

## 完成态真实补数

完成态抽取统一使用：

- `TqBacktest`
- `get_kline_serial(..., duration_seconds=60)`
- 时间推进后读取 `iloc[-2]` 已完成 previous row
- 查询起点为目标日的前一官方交易日 `20:55`
- 查询终点覆盖目标日收盘后
- 按官方交易日归属拆分 exact-contract/date raw

结果：

- 首轮审查指定的 15 个 exact-contract/date：`15/15` 成功，完成态 `4,680` 行。
- 新质量门额外暴露的唯一坏/稀疏日期：`59/59` 成功，完成态 `17,820` 行。
- 合计授权完成态：`74/74` 个唯一 exact-contract/date，`22,500` 行。
- `authorized_tqsdk_source_audit.csv` 逐批记录接口、完成态语义、查询起止、raw path、精确合约、精确交易日、行数、首末时间、正成交量行数、日/夜盘、SHA256、完成时间和质量结论。
- 74 份 raw 已重新导入本地 vn.py 分钟数据库，同时由 prepare 直接作为最高优先级可审计来源读取。
- 认证值未输出、未写入日志或报告。

## 最终覆盖与图片

- 冻结事件：`64/64`
- chartable：`64/64`
- result-analyzable：`61/64`
- minute day quality：`305/305` passed
- reviewer manifest：`64`
- 新图片：`64`
- 图片集合一致：`true`
- blind artifact audit：`ok=true, violations=[]`
- blocking reasons：`[]`
- residual minute gaps：`0`
- R：`61 resolved / 3 unresolved`

新图片绝对目录：

`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage819_intraday_rules/outputs/stage214_all_short_preentry_blind_validation/blind_charts`

新 bundle SHA256：

`50a86ba06a06e3951c0783067a7bb50a89ac1ec24fa745729b08c9fe597f50cc`

`blind_chart_bundle.json` 明确记录其 supersedes 旧 `dc3dd1...`。新旧 PNG 均未提交 Git；只有新 64 图集合可交给盲标者。

## 验证

完整运行日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix1-runtime.log`

完整回归日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix1-regression.log`

最终验证：

```text
Stage208 + Stage214 prepare + Stage214 stats: 82 passed in 21.28s
py_compile: passed
git diff --check: passed
events=64
chartable=64
result_analyzable=61
quality_days=305/305
authorized_exact_dates=74/74
new_charts=64
superseded_charts=64
blind_audit={'ok': True, 'violations': []}
```

代码、测试与修复后 runtime evidence commit：`be3052f5b`。

## Concerns

1. `minute_source_manifest.csv` 约 4.7MB，因为完整记录授权 raw、Stage861、全仓库 cache 和 DB 的逐来源尝试；这是审计体积问题，不影响结果正确性。
2. session exception 只对占当天至少 80% 行的 `authorized_tqsdk_completed` 来源开放；普通缓存缺夜盘仍 fail closed。
3. 三笔 R 必须继续保持 unresolved，后续统计只能按预注册边界处理，不能把 nullable outcome 当 False。
4. reviewer 只能收到新 `blind_charts/` 和 `reviewer_manifest.csv`；controller raw、quality、mapping、outcome、旧图目录不得分发。
5. 本次没有运行策略回测，没有新增规则/参数/收益统计，因此不触发“回测后独立 agent 复核”；82 项回归覆盖 Stage208、prepare 和 stats 的代码兼容性。
6. 无关 Stage217 脚本和 stage 文件均未暂存、未提交。

## 反思

- 过拟合：**否**。修复只收紧数据完成态、session 和 nullable 语义，且对全部冻结样本统一执行；没有读取 Stage213 或盲标结果，没有按盈亏选择补数。
- 继续价值：**Task4 修复已完成，盲标可解除数据阻塞**。下一步有价值的是按密封边界交付新 reviewer surface；继续改窗口、质量阈值或合约集合没有必要。

# Fix round2/5：14:59 完成态与日级来源支配修复（取代 Fix1 bundle）

## STATUS

`READY_AFTER_FIX2`

Fix1 的 74 份授权 raw 中有 30 份止于 14:58；逐时间戳优先级随后从 Stage861、local cache 或 DB 补入 14:59，导致授权源自身不完整仍被最终日质量掩盖。Fix2 已把回放终点推进到最后目标日之后的下一官方交易日 09:02，使目标日 14:59 在 `iloc[-2]` 语义下被后续真实分钟显式 flush；合格授权日改为整日支配，低优先级来源不能再补任何时间戳。

## TDD RED / GREEN

RED 原始日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix2-red.log`

RED 稳定复现两项缺陷：

1. 合格授权日仍混入一根 Stage861 低优先级尾行，实际 `61` 行而不是纯授权 `60` 行。
2. 质量输出没有 `has_session_end_1459`，14:58 截止日未被明确拒绝。

GREEN 原始日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix2-green.log`

结果：新增两项回归 `2/2 passed`。

生产修复：

- `build_minute_day_quality()` 新增 `has_session_end_1459`；纯 `authorized_tqsdk_completed` 日缺 14:59 时追加 `missing_session_end_1459` 并 fail closed。
- `merge_minute_sources()` 先在授权源自身上运行日级质量；合格的 `(vt_symbol, trading_day)` 整日只保留授权源，再做时间戳去重。
- `authoritative_completed_source` 从“授权行占比至少 80%”收紧为“整日全部来自授权完成态”，删除 Fix1 对低优先级尾行的容忍。
- 旧 holiday-night 测试改为纯授权源；holiday-night 例外仍保留，但不再允许 DB 尾行混入。

## 74 份统一重抓与 DB 导入

重抓日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix2-redownload.log`

DB 导入日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix2-db-import.log`

结果：

- 实际目标去重为 `17` 个 exact-contract 合约批次，拆分为原冻结的 `74/74` 个 exact contract/date raw。
- `17/17` 合约批次成功，失败 `0`；`74/74` raw 均含真实完成态 14:59。
- 完成态分钟总数从 Fix1 的 `22,500` 增至 `22,530`，正好补齐原 30 个目标日各一根 14:59。
- 查询起点仍从首目标日前一官方交易日 20:55 开始；查询终点使用最后目标日的下一官方交易日 09:02，不使用自然日 `+1`。
- 每份 `authorized_tqsdk_source_audit.csv` 记录下一官方交易日、查询起止、`iloc[-2]` flush 语义、行数、首末时间、14:59、日/夜盘、SHA256 和完成时间。
- 74 份已重新写入 vn.py 分钟 DB；`authorized_tqsdk_db_import_audit.csv` 为 `74/74 saved`、合计 `22,530` 行。
- 认证值未打印、未写日志、未写报告。

## 日级支配、305 日质量与图片重生

prepare 日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix2-prepare.log`

支配审计日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix2-dominance-audit.log`

该完整日志保留了两个审计工具自身的早期失败：第一次把绝对输出路径错误地相对化到 `Path('.')`；第二次误要求全部 18 个相交 case 的图 hash 都变化。两者均发生在证明脚本层，未改变生产数据。最终口径按审查要求校正为 `16` 个 hash 改变、`2` 个确定性重生且像素相同，末行断言全部通过。

结果：

- minute day quality：`305/305 passed`，且 `305/305` 均含 14:59。
- Fix1 的 30 个 14:58 截止日：`30/30` 现在整日仅来自 `authorized_tqsdk_completed`。
- 30 日最终低优先级行数：`0`；14:59 来源全部为授权完成态。
- 30 日与 `18` 个 case 的五日窗口相交；其中审查指出的 `16/16` case 图 hash 已改变。
- `CASE-004`、`CASE-038` 也由新来源完整重生，但归一化后的像素确定性相同；单独记录在 `fix2_deterministic_unchanged_case_audit.csv`。
- frozen events `64/64`，chartable `64/64`，result-analyzable `61/64`，R 仍为 `61 resolved / 3 unresolved`。
- 新图 `64`，绝对目录：

`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage819_intraday_rules/outputs/stage214_all_short_preentry_blind_validation/blind_charts`

- 新 bundle SHA256：

`96164ffdfd4f73e71ff89b52dfd138d3775d81a97434667bca00d26d661e70c4`

- Fix2 bundle 明确 supersedes Fix1 `50a86ba0...`；历史无效 `dc3dd1...` 继续仅作法证标识。
- PNG 未提交 Git。

## superseded partial/mixed archive 修正

旧目录已从误导性的 `superseded_blind_charts_dc3dd1c23145` 重命名为：

`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage819_intraday_rules/outputs/stage214_all_short_preentry_blind_validation/superseded_blind_charts_partial_mixed_fix1`

该目录不是历史 `dc3dd1...` 的忠实快照：

- expected historical bundle：`dc3dd1c2314536ad8c167a9129e6c023c0eabdfc2318ecff1f31686d42aec058`
- actual observed partial/mixed bundle：`c866d84636d8ee8a897b6ac6cd31debcc88db46339c28be64301d3a46d2dd540`
- mismatched cases：`CASE-039.png`、`CASE-056.png`

完整记录在 `superseded_partial_mixed_chart_archive_audit.json`；该 archive 明确 `reviewer_eligible=false`。

## 验证

组合回归日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix2-regression.log`

结果：

```text
Stage208 + Stage214 prepare + Stage214 stats: 84 passed in 23.14s
```

最终验证日志：

`/Users/bytedance/Desktop/person/vnpy/.superpowers/sdd/20260808_stage215_all_short_preentry_blind_validation_implementation_plan/scratch/task-4-fix2-final-verify.log`

```text
py_compile: passed
prepare status: ready
quality days: 305/305
authorized exact dates: 74/74
authorized rows: 22,530
old truncated days dominant: 30/30
lower-priority tail rows: 0
changed review cases: 16/16
charts: 64/64
bundle: 96164ffdfd4f73e71ff89b52dfd138d3775d81a97434667bca00d26d661e70c4
blind audit: ok=true, violations=[]
git diff --check: passed
```

## Concerns

1. `minute_source_manifest.csv` 仍约 4.7MB，是逐来源尝试的完整审计证据，不影响正确性。
2. 三笔无冻结风险基准的 R 继续 unresolved；outcome 保持 nullable，禁止由盈亏反推。
3. reviewer 只能接收 Fix2 的 `blind_charts/` 和 `reviewer_manifest.csv`；controller raw、mapping、outcome、质量审计及 partial/mixed archive 均不得分发。
4. 支配门只对授权源自身通过完整质量后启用；不合格授权日不会获得日级权威身份。
5. 本轮没有运行策略回测、没有调整交易规则或参数；84 项是数据准备与统计兼容回归，不产生收益结论。
6. 无关 Stage217/218 脚本和 stage 文件保持未跟踪，未暂存、未提交。

## 反思

- 过拟合：**否**。Fix2 对全部冻结事件统一要求真实完成态 14:59 和整日单一权威来源，没有读取 Stage213/盲标结果，也没有按收益或图形选择日期。
- 继续价值：**Fix2 已闭合审查阻塞，继续价值仅在密封交付和独立 review**。继续改变 session 门、窗口或样本集合没有价值；下一步应由 Task4 review 验证新 bundle 和 30 日支配证据。
