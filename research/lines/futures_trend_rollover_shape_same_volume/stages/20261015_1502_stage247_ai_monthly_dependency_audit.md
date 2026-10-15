# Stage247 正式 AI 月更资源与本机就绪审计

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：day；用户询问当前仓库与电脑是否具备正式 AI 选品所需资源，以及 11 月能否生成 2026-10-30 月池。
- 记录时间：2026-10-15 15:02 Asia/Shanghai。
- 当前仓库：`/Users/mac/Desktop/fian`，HEAD `00d6a2f5f`。
- 实际验收研究目录：`/Users/mac/Documents/Codex/fian-research-20261014`，冻结 HEAD `77538e394167c290d5f2923f4d08931b9bbd7c4f`。
- 阶段性质：依赖、资源完整性及历史推断复现审计；非重要突破，不触发 A/B，不晋升或激活生产。

## 结论

已恢复并核验的既有核心资源未发现丢失，2026-09-30 正式月池已在本机成功重算并与 m0008 一致到浮点误差。但不能据此声称“桌面仓库全部就绪”或“11 月自动月更已获保证”：

1. 桌面仓库没有 `.vntrader/database.db`、`.vntrader/vt_setting.json`、`examples/portfolio_backtesting/backtest_outputs`。资源实际在另一研究目录及回放 worktree。
2. 桌面 `.py311` 与正式依赖锁不同；成功复算用的是恢复目录的 `.py311` 和随包 vendor。
3. 本机没有 SOP 的 stable production root、生产签名/激活/数据回执目录或 7 个正式 launchd 任务。仓库 CURRENT 的历史 `active` 标记不能替代本机生产安装。
4. 10 月 30 日尚未到来。未来需补齐并验收日线、主力映射和交易日历，重新生成 Stage183 特征源，再运行 Stage182。此次没有重跑 Stage183 全源回放、认证外部行情账号或执行生产发布流程。

## 外部调研与判断

- [scikit-learn 官方模型持久化说明](https://scikit-learn.org/stable/model_persistence.html)：跨版本加载训练模型不受支持，依赖版本应保留。判断：不能只凭 Python 包可导入就认定可复现；本次核对了实际版本，并真实加载固定模型及重算月池。
- [vn.py 官方依赖声明](https://github.com/vnpy/vnpy/blob/master/pyproject.toml)：用于确认环境审计范围，不据上游最新版本升级本地冻结环境。
- [TqSDK 官方 GitHub 下载器](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/tools/downloader.py)：下载有认证及具体数据功能权限边界。判断：本机凭据字段存在不等于未来数据供应与专业下载权限已验证。TqAuth 官方网页本次抓取超时，不将其当成功访问的证据。

## 正式身份与文件验收

- 策略：`ai_top10_plus_fu_official_live_v1`；ruleset：`stage037_stage034_long_short_mirror_hard_block_v1`；C9/15万。
- 物料：`m0008_20261008T204054+0800_2a7420a9f955`。
- source commit：`2a7420a9f9550ab912b5c4a302a61acc5740b04c`。
- release commit：`334d18f069de06df3aa7728203e942e3ecb94ce9`。
- manifest SHA256：`94b6936ab4b338430981f4c2f7e0f4ff38f24534c32f1d16722c8d1367d89474`。
- 恢复目录 `assert_official_checkout_matches_active_material()` 通过；当前 5 个 AI 物料能通过正式 resolver 读取。
- 原始交接包位置：`/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014`。运行包内 `tools/verify_bundle.py`：`verified_files=12590; sha256=passed; symlink=none`。
- 恢复目录原始日线目录 `downloaded_futures/tqsdk_daily_2010_2026_04` 与包内副本逐文件比较：4,044 个 CSV（含辅助 CSV），缺失 0，SHA256 变化 0。交接说明的 4,041 个合约 CSV 与此口径不同。
- 固定 pairwise joblib 及 summary 与交接包 SHA256 一致。真实加载 `SelectionPairwiseRuntimeModel` 成功，19 个模型输入特征，零向量 predict_proba 冒烟输出有限值；此冒烟不代表真实候选准确率。

## 两份月度特征源

源目录：`/Users/mac/Documents/Codex/fian-research-20261014/research_inputs/monthly_ai_reference_20261014`。

| 文件 | 行数/列数 | 日期范围 | SHA256 |
| --- | --- | --- | --- |
| `qmt_roll_stage183_ai_source_floor35_position_changes_2020_2026_04.csv` | 475540 / 15 | 2020-01-02 至 2026-10-08 | `28040df656218a5eafd23200d7a4e24bc475c92743351d10a79bb23ea59be687` |
| `qmt_roll_stage183_ai_source_floor35_entry_candidate_snapshots_2020_2026_04.csv` | 1052 / 272 | 2020-01-02 至 2026-09-01 | `f838186527b1453923635bda31ec8e1656a0bdacfec633a6b85f2cda8e3b26a0` |

两个 SHA256 均与正式 m0008 summary 记录的训练源完全一致。候选源是事件表，最后记录日早于日线结束日不能单独证明丢失；本次只证明其字节与正式使用源一致，没有重跑底层事件生成作独立逻辑验证。

月度模型是现场训练的 `StandardScaler + LogisticRegression(C=0.20, random_state=42)`，108 个滚动特征由上述源 CSV 计算，非依赖另一个缺失的月度模型权重文件。固定 pairwise 排序模型是不同依赖，已另行加载验收。

## 实际历史重算

运行目录为恢复研究 checkout；使用其 `.py311/bin/python`，设置 `PYTHONDONTWRITEBYTECODE=1`，`PYTHONPATH` 包含该 checkout 和交接包 `vendor`。执行：

```sh
.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py \
  --source-prefix qmt_roll_stage183_ai_source_floor35 \
  --source-dir research_inputs/monthly_ai_reference_20261014 \
  --output-dir /Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage247_ai_dependency_audit/reproduced_20260930 \
  --seed-combined-eligibility official_strategy_materials/ai_top10_plus_fu_official_live_v1/releases/m0008_20261008T204054+0800_2a7420a9f955/payload/ai/stage182/combined_eligibility.csv
```

- eval date：2026-09-30；source max date：2026-10-08；训练标签 cutoff：2026-07-07；未来标签间隔 60 交易日。
- 训练 78 个月、1,404 行，108 个特征，评分 18 个品种，正式输出 11 行。
- 品种、排名、策略及非数值字段完全一致；最新池所有列一致；最大数值差 `7.024381076803365e-13`。
- 顺序为 `cu.SHFE, SM.CZCE, lh.DCE, si.GFEX, au.SHFE, SA.CZCE, rb.SHFE, CF.CZCE, sp.SHFE, FG.CZCE, fu.SHFE`。
- 这是历史推断复算，不是新的绩效回测；期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均不适用。

## 运行环境与数据位置

| 依赖 | 成功复算的恢复环境 | 桌面仓库环境 |
| --- | --- | --- |
| NumPy | 2.4.4 | 2.2.3 |
| pandas | 2.3.3 | 2.2.3 |
| scikit-learn | 1.8.0 | 1.6.1 |
| TqSDK | 3.9.4 | 3.10.2 |

恢复环境另有 SciPy 1.17.1、joblib 1.5.3、TA-Lib 0.6.8；这些已检查依赖与随包锁文件相符，`pip check` 无破损依赖。磁盘空闲约 641 GiB。

- 恢复目录数据库：1,001,048 条日线，最晚 2026-10-13。
- `/Users/mac/.codex/worktrees/formal-2020-replay/fian/.vntrader/database.db`：1,001,334 条日线，最晚 2026-10-14。这是 Stage246 单独补数后的工作区，不应与恢复目录数据混称为一份。
- 两库 SQLite 内仅有 22,770 条 1m 数据，不能代表正式 CSV 分钟缓存的全覆盖。AI 月更底层 Stage183 与正式 C9 分钟回测不是同一运行任务。
- 恢复目录天勤用户名/密码字段非空且非明显占位符，仅确认字段存在，未在本次验证认证、到期日或未来数据权限。未输出任何秘密。
- 初次从桌面导入触发 HOME `.vntrader` 权限失败：根因是桌面没有恢复数据库和运行目录。另一次直接执行恢复目录脚本缺 `PYTHONPATH` 导致找不到 vnpy；按交接文档配置后 Stage182 通过。Stage183 只读导入还会默认写日志，本次仅在审计进程中设置 `SETTINGS['log.file']=False` 后通过；未修改持久配置。

## 10 月 30 日月池的日期边界

用明确标记的合成日期序列调用 Stage182 与 Stage935 的纯日期函数；不伪造行情，不写入源 CSV，不使用 `--allow-incomplete-month`：

| 合成探针的最新源日期 | Stage182 默认 eval date | Stage935 预期 eval date |
| --- | --- | --- |
| 2026-10-30 | 2026-09-30 | 2026-09-30 |
| 2026-11-02，且序列包含 10-30 | 2026-10-30 | 2026-10-30 |

因此，必须进入 11 月首个已完成交易日，通过数据就绪闸门，并更新交易日历、日线/映射和 Stage183 源，才会按现有规则自然选到 10-30。11-02 只是该日历边界示例，最终日期以实际权威交易日历和 Stage922/935 解析结果为准。不能只把电脑日期改到 11 月，或直接用目前停在 10-08 的参考源冒充 10-30。

本机没有生产 stable root `/Users/bytedance/Desktop/person/vnpy_production_live`，没有本机 `~/Library/Application Support/qmt-roll-stage179/production-live/`，launchctl 和 LaunchAgents/Daemons 中没有正式 `c9-production-live-*` 标签或月更 plist。其他 cron 是否存在未核实（沙箱拒绝 crontab 读取），不影响正式 SOP 所需 launchd 未安装的结论。

即使生成新候选池，正式生效仍需不可变物料资格验证、发布、安装和同日数据回执闭环；生成候选不等于切换正式池。

## 独立复核

独立 agent `host_readiness` 核查宿主状态，并独立使用 CSV/Decimal 重比 11 行资格、排名及分数，最大差 `7.025e-13`；重新计算两源 SHA256，均匹配重算和正式 summary。复核同意把结论限定为“已核验的既有核心资源未发现缺失、历史池可复现”，不能声称全部依赖已验收或未来自动月更保证成功。

## 本次变更与输出

- 新增：本阶段记录、隔离审计 summary、日期边界探针结果、Stage182 历史复算 5 个产物。
- 正式策略、配置、参数、模型、CURRENT、AI 物料新增/修改/删除：均无。
- 新增/修改/删除绩效回测结果：均无。
- 输出根：`research/lines/futures_trend_rollover_shape_same_volume/outputs/stage247_ai_dependency_audit/`。
- 主要文件：`audit_summary.json`、`date_boundary_probe.json`、`reproduced_20260930/`。
- CTP 连接、send/cancel/order API、邮件、生产安装：均未执行。

## 反思与 TODO

- 运行前/后是否新增过拟合：否。只核验冻结文件、运行依赖及固定历史月份，未改参数、排名或筛选收益。此结论不评价既有策略本身的过拟合风险。
- 运行前/后是否有继续价值：是。已区分迁移完整性、研究可复算与生产自动化三种状态，避免把目录未绑定误判为文件丢失，或把历史复算成功误判为生产就绪。
- 下一步：固定使用已验收环境；完成最新日线/映射与 Stage183 全源再生验收；11 月以实际完成交易日重新更新并验收 10-30 候选。若需要自动生产，再单独完成正式安装与发布闭环。
- 同线已有 Stage246 工作，本次只写唯一 stage 与隔离输出；不改 LINE、registry、memory 或 back_log。
