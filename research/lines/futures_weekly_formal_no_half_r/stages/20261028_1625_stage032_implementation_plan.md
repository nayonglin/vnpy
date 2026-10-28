# Stage032 周底仓日K加仓实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在Stage029未减半版本增加独立归属的日K两连涨1手加仓，按用户2026-10-28新指令回测2020年至今。
**Architecture:** 研究线内新适配器与新入口；加仓有独立信号、成本、固定止损、归属、计数与逐笔账本，共享真实账户资金/净仓/强平。已冻结Stage029/030/031源码与输入不改。先核验新增日线，再同源跑A未加仓和C加仓。
**Tech Stack:** 仓库.py311/bin/python、vnpy、vnpy_portfoliostrategy、pandas、SQLite、matplotlib。
**Spec:** `20261028_1533_stage032_daily_addon_design.md`；其中2015—2026-10-26区间已由本次用户回复“回测20年至今”覆盖，改为2020-01-01至最新可核验已完成交易日（预期2026-10-28）。用户此回复视为同意既有明确规则、同时修正日期范围；不再重复征求实施许可。

## Global Constraints

- 只新增本线文件；不改旧数据、旧源码、LINE/registry、其他研究线、正式物料或生产。
- 原19、15万、周MA5/10/20无MA40；short_case2/RSI/全部AI/MACD/0.5R/C2/原加仓/减半关闭。
- 两天close严格高于各自前收；次日同约open加1；stop=min两信号日low固定；日close严格跌破→次日open退出。
- 逐品种每个周多头逻辑持仓最多实际加2次、最多1笔，pending上锁；退出当日收盘可重计；roll随平、名额继承、日涨重计；账户安全先于加仓。
- 底仓技术规则不改，共享资金反馈允许改变实际手数；分离计账不得漏风险或改变底仓止损。
- 每次回测后新独立agent复核数据/逻辑/结果/置信度/bug；不因结果救参。

## Review Focus

1. 多/空、同原生合约、CZCE年代、缺日、零量、跨换月数据不能混为两连涨。
2. 父净仓reconcile、目标覆盖、开盘成本同步不得吸收加仓或误平底仓。
3. pending取消/拒绝不计次数；真实退出后才重计；加仓开仓日也能产生收盘止损。
4. 底仓退出/部分强平/roll与日止损冲突只平真实余量，完整资金风险可见。
5. 真实加仓归属与FIFO分离，但总PnL、成本、净仓和日权益精确守恒，不能把代理overlay当金融回测。

## Task 1: 最新数据准入（独立data agent）
**Files:** 新增tools/stage032_latest_data.py、对应test；outputs/stage032_latest_data/data_approved。
**Interfaces:** 输出旧runner所需daily.sqlite、mapping.csv、metadata.csv、physical_epoch_daily.csv、physical_epochs.csv、receipt.json、source_manifest.json；data_ready、date_end、单边volume/收盘OI、历史主力非PIT边界显式。
- [ ] 写追加/不覆盖旧行、重复冲突、截止未完成拒绝测试并运行RED。
- [ ] 新工具复用批准快照，仅追加准入新日/合约，GREEN。
- [ ] SHA旧输入未变；最新交易日19mapping、老仓与新主力数据完整；缺失则具体阻断。

## Task 2: 独立加仓策略适配器（实现agent）
**Files:** 新增tools/stage032_daily_addon.py、test_stage032_daily_addon.py。
**Interfaces:** `daily_addon_strategy_class(base, weeks, calendar, epoch_lookup, enabled=True)`返回已包装Stage029v2的策略；`daily_addon_engine_class(base)`返回所需引擎包装（若无扩展仍提供原类）；`audit_daily_addon(strategy, frames=None)`返回accepted和所有状态/次数/归属验证。策略导出`daily_addon_events/decisions/rounds/allocations/snapshots/guard_failures`列表；关闭模块必须精确等价。
- [ ] 先写实质性时序、计数、独立止损、归属/强平/换月/资金测试，确认RED再实现。
- [ ] 封装Stage029v2，独立daily缓存与cohort；真实fills才记次、stop固定。
- [ ] 实际成交归属、成本同步、净target、预留保证金、所有风险统计与强平接入；不重启旧加仓全局锁盈。
- [ ] 测试GREEN，输出运行命令和设计裁决，不改其他任务文件/不commit。

## Task 3: 同源双臂入口及会计报告（root）
**Files:** 新增tools/run_stage032_daily_addon.py、stage032_build_artifacts.py及对应测试；独有attempt输出与artifacts/stage032。
**Interfaces:** CLI --arm A/C --data-dir --end YYYY-MM-DD --attempt；start固定2020-01-01。独立入口复用Stage029审计，不覆盖冻结runner。报告消费daily/trades/clock/positions/effective settings+addon allocations。
- [ ] runner参数/截止/输出不可覆盖等测试先RED；新入口GREEN。
- [ ] 禁用模块与未包装A相同数据的候选/成交/日权益等价核验；设置变化只有日期、mapping及新元数据。
- [ ] 数据和逻辑预审通过后跑A/C，所有attempt包括失败均保留；每次策略回放后独立review。
- [ ] 逐笔净PnL守恒、真实风险×1.65、成本、胜率/平均盈亏比/PF、年度/加仓第一次第二次/拒绝统计；图表A/C同轴。

## Task 4: 独立结果审查与交付
**Files:** stage032_*review.md/json、中文最终stage、delivery_manifest；必要来源/输出绑定。
- [ ] 新独立agent复算同约同epoch信号与实际fills、固定stop、计数、父仓退出及风险、会计/统计/图表/输入哈希。
- [ ] 有bug先写失败回归再修；不改策略规则救结果，失败attempt保留。
- [ ] 跑研究线适当全回归；有已知全仓环境失败明确记载，不假称全CI绿。
- [ ] 中文结果记录必填指标、分钟时间、开始/结束过拟合与继续价值判断；A/C不自动晋级。
- [ ] 旧3603绑定零改，diff检查，唯一新文件commit，工作树干净；不推送/合并/激活。
