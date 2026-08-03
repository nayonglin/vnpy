# Stage211：Stage935 AI 池月更路径分叉根因

- 时间：2026-08-03 19:05（Asia/Shanghai）
- 研究线：`futures_trend_stage819_intraday_rules`
- 是否重要突破：是，定位到 2026-08-03 新 AI 池未发布的直接生产根因
- 本阶段性质：只读取证与设计，不运行回测，不连接 CTP，不修改正式 eligibility

## 调研与判断结论

### 外部调研

Pandas 官方时间序列与 `reindex` 文档说明，稀疏数据应对齐到明确索引后再按业务语义处理缺失项。该参考支持显式统一数据源/索引，不支持强制指定一个源数据并未证明存在的月末日期。

- https://pandas.pydata.org/docs/user_guide/timeseries.html
- https://pandas.pydata.org/docs/reference/api/pandas.Series.reindex.html

### 本地生产证据

1. Stage935 于 18:20 执行，状态为 `monthly_ai_pool_update_blocked`。
2. Stage183 子命令退出码为 0，其 stdout 显示回测产物写入 production-live `official-live` 隔离目录。
3. 隔离目录的新 `daily.csv`、`position_changes.csv` 与 `entry_candidate_snapshots.csv` 最大日期均为 `2026-08-03`，包含 `2026-07-31`。
4. Stage183 摘要和 Stage182 输入路径却指向 release 下的 `backtest_outputs`；该目录解析到仓库历史输出，旧源最大日期为 `2026-07-21`。
5. Stage182 因读取旧源生成 `source_max_date=2026-07-21`、`eval_date=2026-06-30`，Stage935 随后以 `stage182_eval_date_not_expected` 和 `stage182_combined_missing_recent_eval_dates` 拒绝发布。

结论：底层原因是 `run_qmt_alignment_backtest.OUTPUT_DIR` 遵循 `OFFICIAL_LIVE_OUTPUT_DIR`，而 Stage183 摘要和 Stage182 source path 仍使用静态 `PROJECT_DIR/backtest_outputs`，导致同一生产任务写新目录、读旧目录。不是磁盘不足、调度未执行、行情只到 7 月 21 日或模型无法生成 7 月池。

## 设计决策

采用方案 A：Stage183 声明真实 artifact root；Stage182 显式接收 source/output dir；Stage935 在隔离目录生成和校验候选，通过后才原子发布正式 AI 池。禁止通过关闭生产隔离、复制半成品回旧目录或强制 `--eval-date` 掩盖路径问题。

详细设计：`docs/superpowers/specs/2026-08-03-stage935-ai-pool-source-path-consistency-design.md`。

## 过拟合与继续价值反思

- 是否过拟合：否。本阶段没有调整模型、特征、阈值或产品名单；修复的是可复现的生产路径一致性缺陷。
- 是否值得继续：是。当前缺陷会让每个月更在新产物已经生成时仍读取旧文件，直接阻断正式 AI 池更新；修复后仍保留全部 fail-closed 门禁。

## 回测字段

本阶段未运行回测，因此期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率均不新增、不修改、不删除。

## 后续

在用户审阅书面规格后，按 TDD 编写实施计划并在隔离候选实现；完成测试与独立审查后，仍须等待生产 PID 自然归零并通过 Stage174/Stage948 门禁才允许安装。
