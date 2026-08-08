# Stage215 全体空头入场前趋势特征双盲验证实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不向视觉审阅者泄漏交易身份和结果的前提下，补齐并审计当前正式 C9/15万全部 64 笔空头的开仓前五交易日分钟数据，完成双盲 15 分钟K线标注、冻结揭盲统计和 Stage216 中文结果记录。

**Architecture:** 准备脚本负责冻结 64 笔空头总体、精确月合约分钟数据补充、五日前视窗、匿名映射和无泄漏图片；统计脚本只在标签文件全部冻结后加载密封映射与结果。两名独立 agent 只获得匿名图片目录、标签手册和各自输出路径，第三名仅获得分歧图片；最终独立 agent 审查数据、代码、盲态和结论。

**Tech Stack:** Python 3.11 (`.py311/bin/python`)、pandas、NumPy、Matplotlib Agg、Pillow、SciPy、pytest、vn.py 本地数据库、标准库 hashlib/json/pathlib。

## Global Constraints

- 设计唯一依据为 `research/lines/futures_trend_stage819_intraday_rules/stages/20260808_stage214_all_short_preentry_blind_validation_design.md`，实现不得修改其窗口、标签、统计门槛或结论分级。
- 正式版本固定为 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，只使用 `requested_start_month == "2020-01"`。
- 候选总体必须是全部 64 笔空头；主结果为 `aggregate_r >= 2.0`。
- 主图只含 `[D-5, D-1]` 五个完整官方交易日，完整排除 `D0`；不显示成交量。
- 分钟数据只允许精确月合约；优先本地 Stage861、全仓库 exact-contract raw cache、vn.py 本地分钟数据库，再使用已有合法下载入口。禁止主连替代、跨月拼接、插值、前向填充和伪造K线。
- 数据目标为 64/64；少于 60 笔可分析样本时不得揭盲下有效/无效结论，必须继续补数或报告基础设施不足。
- 三笔 `risk_amount=0` 事件必须追溯冻结原始风险字段，不能由最终盈亏反推。
- 匿名图隐藏合约、日期、绝对价格、收益、R、赢家状态、退出信息和原始排名；第一根收盘归一为 100。
- 两名审阅者必须相互独立且看不到 `blind_mapping.csv`、事件账本、Stage213 标签与对方标签。
- 视觉可靠性门槛为原始一致率 `>= 0.80` 且 Cohen's kappa `>= 0.60`。
- 主有效性八项闸门按 Stage214 原文逐项判断；不扫描替代窗口、阈值、品种子集或 R 门槛。
- 不修改正式策略、正式配置、AI池、趋势/震荡策略代码、实盘、CTP/SimNow、邮件、launchd 或任何订单入口。
- 所有实现采用 TDD：生产函数之前先写测试并确认因缺失行为正确失败。
- Stage216 结果完成后必须由未参与实现和视觉标注的独立 agent 审阅；影响结果的问题必须修复重跑。

---

## 文件结构

- Create: `research/lines/futures_trend_stage819_intraday_rules/tools/stage214_all_short_blind_prepare.py`
  - 冻结空头总体、补数、来源清单、五日窗口、匿名映射、归一化、制图和泄漏审计。
- Create: `research/lines/futures_trend_stage819_intraday_rules/tools/stage214_all_short_blind_stats.py`
  - 校验双盲标签、计算一致性、裁决联表、主统计、稳健性、缺口边界和机器决策。
- Create: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py`
  - 验证事件总体、窗口、匿名、补数优先级、来源哈希、图形无泄漏。
- Create: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_stats.py`
  - 验证标签协议、kappa、Fisher/OR/区间、留一、敏感性和门槛决策。
- Create at runtime: `research/lines/futures_trend_stage819_intraday_rules/outputs/stage214_all_short_preentry_blind_validation/`
  - 保存清单、密封映射、匿名图片、标签、统计与报告。
- Create after verified run: `research/lines/futures_trend_stage819_intraday_rules/stages/20260808_stage216_all_short_preentry_blind_validation_result.md`
  - 中文记录真实补数、双盲、统计、独立复核、结论和反思。

### Task 1: 冻结 64 笔空头、五日窗口和数据补充审计

**Files:**
- Create: `research/lines/futures_trend_stage819_intraday_rules/tools/stage214_all_short_blind_prepare.py`
- Create: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py`

**Interfaces:**
- Consumes: Stage208 的 `build_trading_calendar()`、`assign_trading_day()`、`resample_15m()`、`discover_contract_cache_paths()`。
- Produces: `build_short_events(closed_lots: pd.DataFrame, enforce_expected_counts: bool = True) -> pd.DataFrame`
- Produces: `select_preentry_days(entry_day: pd.Timestamp, calendar: pd.DatetimeIndex) -> list[pd.Timestamp]`
- Produces: `resolve_risk_zero_events(events: pd.DataFrame, closed_lots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]`
- Produces: `merge_minute_sources(events, calendar, stage861_path, cache_paths, database) -> tuple[pd.DataFrame, pd.DataFrame]`
- Produces: `build_data_gap_audit(events, minutes, calendar) -> pd.DataFrame`

- [ ] **Step 1: 写事件总体失败测试**

测试夹具包含两个空头事件、一个多头事件和一个非 `2020-01` 事件，断言只聚合空头、按 `open_trade_id` 聚合、零风险保留为 `aggregate_r=NaN`，并包含 `outcome_ge_2r`、`outcome_profitable`、`entry_year`。生产实现尚不存在时测试必须因导入文件或函数缺失失败。

- [ ] **Step 2: 运行 RED**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py::test_build_short_events_keeps_all_short_events_and_zero_risk -v
```

Expected: FAIL，原因是模块或 `build_short_events` 不存在。

- [ ] **Step 3: 实现最小事件聚合**

实现读取 `requested_start_month == "2020-01"`，以 `open_trade_id/vt_symbol/direction/entry_date/entry_price` 聚合 `realized_pnl/risk_amount/lot_count/exit_date`，只保留 direction 大小写归一后为 short，校验总事件 309、空头 64，并保留零风险事件。

- [ ] **Step 4: 写严格五日窗口和补数优先级失败测试**

用 8 个工作日夹具断言开仓日只返回其前 5 日且不含开仓日；用同一合约同一时间戳的 `stage861/local_cache/vnpy_database` 三来源夹具断言优先级为 Stage861 > local cache > database，且不同时间戳取并集、不跨合约。

- [ ] **Step 5: 实现窗口与来源合并**

复用 Stage208 夜盘映射和 15 分钟聚合。为每行保留 `minute_source_kind`、`minute_source_path`、`source_priority`；按 `vt_symbol + bar_datetime` 去重。vn.py 查询固定使用精确 `symbol/exchange`、`Interval.MINUTE` 和每个事件 `[D-5 20:00 前缓冲, D0 00:00)` 的范围，不查询连续合约。

- [ ] **Step 6: 写来源哈希、覆盖和零风险审计失败测试**

断言来源清单含 `vt_symbol/source/path/row_count/min_datetime/max_datetime/sha256`；覆盖清单将五日齐全标为 `complete`、四日标为 `partial`、零日标为 `missing`；零风险无法由冻结字段统一重建时保持 `unresolved`，不得用 `realized_pnl` 反推。

- [ ] **Step 7: 实现来源清单与缺口审计**

哈希使用每个源文件原始字节 SHA256；数据库行使用稳定 CSV 序列化哈希。`data_gap_audit.csv` 每事件记录目标日、实际日、缺失日、尝试来源和 R 状态。

- [ ] **Step 8: 运行 Task 1 测试并提交**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py -v
git add research/lines/futures_trend_stage819_intraday_rules/tools/stage214_all_short_blind_prepare.py research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py
git commit -m "feat: add stage214 all-short data preparation"
```

Expected: Task 1 全部测试 PASS，0 failed。

### Task 2: 生成匿名归一化图片并自动审计泄漏

**Files:**
- Modify: `research/lines/futures_trend_stage819_intraday_rules/tools/stage214_all_short_blind_prepare.py`
- Modify: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py`

**Interfaces:**
- Produces: `build_blind_mapping(events: pd.DataFrame, seed: int = 21420260808) -> pd.DataFrame`
- Produces: `normalize_preentry_bars(bars15: pd.DataFrame) -> pd.DataFrame`
- Produces: `render_blind_chart(case_id, bars15, target_days, output_path) -> dict[str, object]`
- Produces: `audit_blind_artifacts(chart_dir, reviewer_manifest, sealed_mapping) -> dict[str, object]`
- Produces: `prepare(output_dir: Path = OUTPUT_DIR) -> dict[str, object]`

- [ ] **Step 1: 写确定性匿名映射与价格归一化失败测试**

断言相同种子和事件集合生成相同 `CASE-001..CASE-064` 映射；打乱输入行顺序不改变事件到 case 的映射；归一化后第一根 close 严格为 100，OHLC 使用同一比例且不改变高低关系。

- [ ] **Step 2: 运行 RED 并实现最小映射/归一化**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py -k 'blind_mapping or normalize' -v
```

Expected: FAIL 后实现；随机化前按 `open_trade_id` 稳定排序，再用局部 `random.Random(21420260808)` 洗牌。

- [ ] **Step 3: 写图片时间边界与身份泄漏失败测试**

生成一个包含 D-5 至 D0 的夹具，断言制图只消费 D-5 至 D-1、PNG 非空、审阅者 manifest 仅有 `case_id/chart_file/available_day_count/bar_count`。把合约、日期、R 或 `winner` 放入文件名、manifest 或 PNG 文本元数据时，审计必须失败。

- [ ] **Step 4: 实现无成交量匿名图和泄漏审计**

图题只显示 case ID；横轴只显示 `Day 1..Day 5`；纵轴显示 `Normalized price`；不写真实日期、合约、收益或绝对价格。用 Pillow 检查 PNG text chunks，用敏感 token 集合扫描文件名和审阅者 manifest。

- [ ] **Step 5: 实现 prepare 编排与不变量**

输出 `short_event_manifest.csv`、`minute_source_manifest.csv`、`data_gap_audit.csv`、密封 `blind_mapping.csv`、`reviewer_manifest.csv`、`blind_charts/*.png`、`prepare_decision.json`。若事件数不是 64、可分析数低于 60、图片集合不一致或泄漏审计失败，命令非零退出。

- [ ] **Step 6: 运行 Task 2 全测并提交**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py -v
git add research/lines/futures_trend_stage819_intraday_rules/tools/stage214_all_short_blind_prepare.py research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py
git commit -m "feat: add stage214 blind chart preparation"
```

Expected: Task 2 全部测试 PASS，0 failed。

### Task 3: 冻结标签协议、统计与决策引擎

**Files:**
- Create: `research/lines/futures_trend_stage819_intraday_rules/tools/stage214_all_short_blind_stats.py`
- Create: `research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_stats.py`

**Interfaces:**
- Produces: `validate_reviewer_labels(labels, expected_cases) -> None`
- Produces: `compute_agreement(labels_a, labels_b) -> dict[str, float]`
- Produces: `build_adjudicated_labels(labels_a, labels_b, adjudication) -> pd.DataFrame`
- Produces: `compute_primary_statistics(joined: pd.DataFrame) -> dict[str, object]`
- Produces: `compute_leave_one_out(joined, group_column) -> pd.DataFrame`
- Produces: `compute_gap_bounds(joined, unresolved) -> dict[str, object]`
- Produces: `evaluate_decision(metrics, agreement, year_loo, product_loo, gap_bounds) -> dict[str, object]`
- Produces: `reveal(output_dir: Path = OUTPUT_DIR) -> dict[str, object]`

- [ ] **Step 1: 写标签完整性、一致率和 kappa 失败测试**

夹具覆盖四个冻结标签、重复 case、缺失 case、非法标签、空理由和非法置信度；手算 4 例中 3 例相同，断言一致率 0.75，并用 `sklearn.metrics.cohen_kappa_score` 或手算列联期望验证 kappa。

- [ ] **Step 2: 运行 RED 并实现标签协议**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_stats.py::test_compute_agreement_matches_hand_checked_fixture -v
```

Expected: FAIL 后实现标签枚举、每 case 唯一、理由非空、置信度枚举和一致性统计。

- [ ] **Step 3: 写 Fisher、OR、精确区间与分布指标失败测试**

使用手工 `2×2` 表 `[[12, 8], [5, 39]]`，断言双侧 Fisher p 与 SciPy 一致，样本 OR 按 `12*39/(8*5)` 手算，风险差按 `12/20 - 5/44` 计算；精确条件 95% 区间使用 SciPy `odds_ratio(table, kind="conditional").confidence_interval(0.95)` 交叉核验，并同时披露条件 OR 与样本 OR。另断言同向组 R 中位数和盈利概率来自逐事件数据而非列联表。

- [ ] **Step 4: 实现主统计和裁决联表**

主信号仅 `trend_same_direction` 为阳性；其余可判断标签为阴性；`insufficient` 不进入完整样本主表但进入缺口边界。两审阅者相同时直接采用该标签，不同时必须存在第三方裁决且裁决 case 集合严格等于分歧集合。

- [ ] **Step 5: 写逐年留一、最高频品种剔除和门槛决策失败测试**

构造两年两品种夹具，断言每次仅剔除目标组；最高频品种有并列时按产品名升序选第一个并在结果中披露。分别构造八闸门全过、p 值失败、kappa 失败、逐年方向失败和最不利缺口翻转，断言 decision 分级严格对应 Stage214。

- [ ] **Step 6: 实现稳健性、边界和机器决策**

`decision.json` 逐项包含 `name/value/threshold/passed/evidence`；不得用总通过布尔值覆盖失败细节。未解析样本穷举四种 `signal × outcome` 组合的边界，记录最有利和最不利判定。

- [ ] **Step 7: 运行 Task 3 全测并提交**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_stats.py -v
git add research/lines/futures_trend_stage819_intraday_rules/tools/stage214_all_short_blind_stats.py research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_stats.py
git commit -m "feat: add stage214 blind validation statistics"
```

Expected: Task 3 全部测试 PASS，0 failed。

### Task 4: 实际补数、生成 64 个匿名 case 并封存映射

**Files:**
- Runtime outputs only under `research/lines/futures_trend_stage819_intraday_rules/outputs/stage214_all_short_preentry_blind_validation/`

**Interfaces:**
- Consumes: Tasks 1—2 的 `prepare()`。
- Produces: 数据与图片产物；不产生结果统计。

- [ ] **Step 1: 执行准备阶段**

```bash
.py311/bin/python research/lines/futures_trend_stage819_intraday_rules/tools/stage214_all_short_blind_prepare.py
```

- [ ] **Step 2: 若存在数据缺口，按 Stage214 顺序补数并重跑**

先检查精确合约的 vn.py 分钟数据库与 1747 份仓库 raw cache；仍缺时复用仓库已有合法下载工具和当前授权。每次补数后重新运行 prepare，直到 64/64 或所有合法来源的失败证据写入 `data_gap_audit.csv`。不得因下载权限失败而删样本。

- [ ] **Step 3: 验证准备产物**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py -v
.py311/bin/python - <<'PY'
from pathlib import Path
import pandas as pd
root = Path('research/lines/futures_trend_stage819_intraday_rules/outputs/stage214_all_short_preentry_blind_validation')
events = pd.read_csv(root / 'short_event_manifest.csv')
review = pd.read_csv(root / 'reviewer_manifest.csv')
charts = sorted((root / 'blind_charts').glob('CASE-*.png'))
assert len(events) == 64
assert len(review) == len(charts)
assert len(review) >= 60
assert review['case_id'].is_unique
print({'events': len(events), 'review_cases': len(review), 'charts': len(charts)})
PY
```

- [ ] **Step 4: 提交可审计清单和准备决策**

强制添加被输出 ignore 规则覆盖的 CSV/JSON/Markdown 小文件；PNG 只记录本地绝对路径、数量和 bundle SHA256，不提交大图。

### Task 5: 两名独立 agent 双盲标注与第三方分歧裁决

**Files:**
- Create at runtime: `blind_labels_reviewer_a.csv`
- Create at runtime: `blind_labels_reviewer_b.csv`
- Create at runtime: `blind_labels_adjudicated.csv`

**Interfaces:**
- Label columns: `case_id,label,confidence,visual_evidence`。
- Allowed labels: `trend_same_direction,range_or_compression,mixed_or_opposite,insufficient`。

- [ ] **Step 1: 冻结 12 个校准 case**

由准备脚本按同一固定种子输出 `calibration_cases.csv`，仅包含 case ID；两个 agent 均不可访问密封映射和结果。

- [ ] **Step 2: 并行派发两名独立审阅者**

每个 agent 使用 `fork_turns="none"`，只给匿名图片目录、Stage214 第七节标签定义、自己的输出文件路径和逐图 `view_image` 要求。两人不得读取仓库其他文件、文件历史、映射、事件清单、Stage213 或对方输出。

- [ ] **Step 3: 校准后冻结手册并完成全量独立标注**

校准只解决标签定义歧义，不查看结果；最终两份 CSV 各覆盖全部可分析 case，无重复、空理由或非法值。

- [ ] **Step 4: 计算分歧集合并派发第三名裁决者**

第三名 `fork_turns="none"`，只获得分歧 case 图片和同一冻结手册。裁决 CSV 必须严格覆盖分歧集合。

- [ ] **Step 5: 冻结标签哈希**

写入每份 CSV 的 SHA256 和完成时间；此后不得修改标签，只允许修复格式且必须保留修复前后哈希和原因。

### Task 6: 揭盲统计、Stage216 记录与独立终审

**Files:**
- Runtime outputs: `contingency.csv`、`summary_metrics.csv`、`year_leave_one_out.csv`、`product_leave_one_out.csv`、`decision.json`、`report.md`
- Create: `research/lines/futures_trend_stage819_intraday_rules/stages/20260808_stage216_all_short_preentry_blind_validation_result.md`

**Interfaces:**
- Consumes: Tasks 3—5 的冻结代码、密封映射、事件结果和标签哈希。
- Produces: 可审计统计、结论和独立复核记录。

- [ ] **Step 1: 揭盲并生成统计**

```bash
.py311/bin/python research/lines/futures_trend_stage819_intraday_rules/tools/stage214_all_short_blind_stats.py
```

- [ ] **Step 2: 运行完整测试与产物不变量审计**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_stats.py -v
git diff --check
```

- [ ] **Step 3: 写 Stage216 中文记录**

记录分钟级完成时间、补数来源与缺口、64 笔结果总体、标签一致性、列联表、八项闸门、逐年/品种/缺口敏感性、期末权益等不适用项、零订单/零 CTP、过拟合和继续价值判断。

- [ ] **Step 4: 派发独立终审 agent**

终审者不得是实现者、Reviewer A/B 或裁决者。提供 Stage214、Stage215、代码、测试输出、全部小型产物和图片 bundle hash；要求按 P0/P1/P2/P3 审查数据、盲态、统计、bug、结论和置信度。

- [ ] **Step 5: 修复影响结果的问题并重新执行**

所有 P0/P1 或终审认定会改变结果的问题按 TDD 修复、重新测试、重新 prepare/reveal；不影响结果的问题写入 Stage216 日志。

- [ ] **Step 6: 最终验证与提交**

```bash
.py311/bin/python -m pytest research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_prepare.py research/lines/futures_trend_stage819_intraday_rules/tests/test_stage214_all_short_blind_stats.py -q
git diff --check
git status --short
```

提交工具、测试、Stage215/216、小型 CSV/JSON/Markdown 审计产物；不更新 `LINE.md`、`research/registry.md` 或根目录总账，除非 Stage216 形成重要突破或路线废弃结论。

## 计划自审

- Stage214 的样本、时间、数据、盲态、标签、可靠性、统计、稳健性、结论分级和终审要求均有明确任务承接。
- 匿名准备与揭盲统计分成两个脚本；视觉审阅者无需也不得接触统计模块和密封映射。
- 所有生产函数均先有可观察行为的失败测试；人工标注步骤以集合完整性、独立性和哈希封存作为验收。
- 缺数路线明确为先补数、后边界分析，不存在因数据不足直接放弃整个实验的分支。
