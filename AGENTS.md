## 工作模式

1. 有需要你可以使用多agent模式，由你来决策

## 并行研究记录模式

1. 开始任何研究前，先读取 `research/registry.md`，确认本次所属 `line_id`。如果没有对应研究线，先在回复中说明拟新增研究线，并创建 `research/lines/<line_id>/LINE.md`。
2. 日常研究和回测记录优先写入对应研究线目录，不再让多个方向同时追加根目录大文件：
   - 阶段记录：`research/lines/<line_id>/stages/YYYYMMDD_HHMM_stageNNN_short_slug.md`
   - 当前线状态：`research/lines/<line_id>/LINE.md`
   - 模板：`research/templates/stage_record.md`
3. 根目录 `memory.md` 和 `back_log.md` 保留为历史总账与重要合入摘要；只有重要突破、路线废弃、正式候选、跨线合并、记录体系迁移这几类事件才追加。
4. 多个 worktree / agent 并行时，每个工作区只修改自己的 `research/lines/<line_id>/`。不要修改其他研究线目录；不要频繁改 `research/registry.md`，由合入者统一更新。
5. 如果同一条研究线也被多个工作区并行推进，只写唯一 stage 文件，暂不改该线 `LINE.md`，避免同线冲突；合入时再整理。
6. 合入时先读各线 stage 文件，再更新 `LINE.md`、`research/registry.md`，最后按需要把摘要追加到根目录 `memory.md` / `back_log.md`。

## 研究与决策原则

1. 对我提的所有优化都要辩证思考，追求事物的本质和第一性原理，而不是我说什么就是什么；你要有自己的判断。
2. 所有代码和策略设计都应该从“能穿越周期”去设计，不要过拟合。
3. 应用 Michael Polanyi 默会知识理论，让输出模拟人类无法用语言描述的经验累积的直觉判断。
4. 先读取当前仓库的。
5. 当前仓库带了 `python3` 和 `vnpy` 环境，使用 `.py311/bin/python` 作为解释器。
6. 做任何研究和尝试之前，都应该先从网上和 GitHub 看看有没有可参考的资料、代码、策略；不是一定要完全复制，你要有自己的判断，可以复制、否决或结合。每次回答都要明确告诉我你的调研和判断结论。
7. 每一次跑完回测数据，都应该拉一个独立的agent对你的结果，数据，逻辑，置信度，bug进行全面的review，明确会影响到回测结果的问题要修复，不影响结果的可以先不修复，但要在log文件记录好

## 回测记录要求

1. 所有回测都要把当前版本变更、回测参数和回测结果记录到对应研究线的 stage 文件中；重要合入摘要再追加到根目录 `back_log.md`。
2. 以上记录都要用中文，并简单说明本次版本的改动内容，包括但不限于：
   - 改动的时间点，具体到分钟级别
   - 是否是重要突破版本
   - 改动的简单总结
   - 新增的参数
   - 修改的参数
   - 删除的参数
   - 新增的回测结果
   - 修改的回测结果
   - 删除的回测结果
   - 期末权益 `1,610,900`
   - 总收益 `705.45%`
   - 最大回撤 `-54.93%`
   - Sharpe `0.661`
   - 总滑点 `100`
   - 总交易次数 `1000`
   - 胜率
   - 后续规划和 TODO

## A/B 与策略隔离

1. 当你判断某个新策略版本“有价值、可能接入正式版本、需要与第 78 正式基准结合或做 A/B 实验”时，先读取并遵循 `skills/version-ab-experiment/SKILL.md`；不是所有新版本都触发，纯归因、监控、明显低价值想法不触发。
2. 趋势策略和震荡策略必须保持代码、配置、回测入口、输出命名的隔离；当前它们是两条独立策略路线。震荡策略研究不得修改第 78 正式趋势策略及其配置。只有当震荡策略本身独立跑出稳定、可复验、低过拟合的效果后，才允许讨论与第 78 趋势策略结合、A/B 实验或组合接入。

## 期货官方实盘/CTP/SimNow 虚拟盘 SOP

1. 当用户要求运行或解释官方实盘版本、当前实盘候选、每日影子盘、SimNow/券商测试虚拟盘、CTP/SimNow通路、Phase B委托草案/提交前闸门、1手报撤smoke order、AI池月更、`review`风险层级、每日对账或“今天/今晚/下个交易时段是否需要交易”时，先读取并遵循 `skills/futures-live-execution-sop/SKILL.md`。
2. 该 skill 只约束执行纪律与SOP，不用于优化策略alpha；若同时涉及新策略版本或A/B实验，仍需遵循 `skills/version-ab-experiment/SKILL.md`。
3. 从 2026-06-05 起，虚拟盘和实盘前流程默认只认 Stage372 20万口径：`official_live_stage372_20w_recovery_sleeve`。Stage653 20万原版和 Stage78-1 50万入口只作为历史/研究对照，不得作为当前实盘默认执行路径；旧30万入口继续只作历史对照。
4. CTP 实盘/虚拟盘连接前必须先确认 env 与 runtime：实盘生产前置使用 `ctp_live.local.env`，不要误用默认读取 `ctp_broker_test.local.env` 的 broker-test shell；macOS 生产前置必须让 `vnpy_ctp/api/libs` 的正式 framework 优先于 `.py311/lib` 的 `v6.7.7_MacOS_CP` 评测 framework。若出现 `4040 CTP:API Front shake hand err: decode err`、`Decrypt handshake data failed`、只读 gate 长时间 `front_connected=false` 或 vn.py native segfault，先按 `skills/futures-live-execution-sop/SKILL.md` 的 CTP runtime guard 排查，不得跳过只读账户/持仓 gate 直接报单。

## 每次开始与结束都要反思

1. 每次开始运行和运行完，都要反思我们现在做的事情是不是在过拟合；明确告诉我，是或否，以及原因逻辑是什么。
2. 每次开始运行和运行完，都要反思我们现在做的事情是不是还有价值继续做下去；明确告诉我，是或否，以及原因逻辑是什么。

