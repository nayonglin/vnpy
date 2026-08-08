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
