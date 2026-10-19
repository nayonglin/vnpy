# Stage053 周线开多门独立预运行审查

- line_id：futures_trend_full_market_noai_one_lot；记录时间：2026-10-19 19:19 CST。
- 工作树/分支：/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian；codex/full-market-noai-one-lot。
- 阶段性质：独立代码、时序、数据合同和无金融回放集成审查；不改实现、LINE、registry或其他研究线；无生产读取。
- 基准：87487e32d36a443942f612ac7eeef71ede9ea46a；A源manifest SHA256：a8696e2b73b25399251d1efc46e47dfd49f89d23bfc80f6bc1f33bfdbe5237c3。
- 结论：**PASS_WITH_LIMITS，无P0/P1阻断，可以按Stage052预登记冻结代码后只跑一次C；本结论不证明收益或正式资格。**
- 是否重要突破：否；是否触发正式晋级：否。A/C研究纪律沿用Stage052，B单独不能形成完整策略。

## 调研与判断

已独立查阅[pandas官方resample文档](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.resample.html)与[backtesting.py官方resample_apply源码](https://github.com/kernc/backtesting.py/blob/master/backtesting/lib.py)。判断：右侧周期标签只能辅助避免提前公布，仍须独立完整日历和开盘/收盘相位。本实现满足此结构，原始因果主力换月价差应作为研究边界保留，不能用后验复权或参数搜索掩盖。

## 代码、逻辑和数据审查

1. Stage050 87—98行先使用独立交易日历确定自然周最后会话，再连接该日mapping指定主力的同日close；未按同日OI重选，未拿目标合约自己的40周历史冒充品种主力。observation_date必须早于对应会话。实际独立日历范围2005-01-04至2027-12-31，覆盖行情截止2026-10-16之后，因此本次末周未由截断行情倒推完成。
2. Stage050 113—145行只接受有效映射、正有限close/volume、非execution-only周末价。坏周保持NaN并留在40个有会话周窗口中，不dropna、ffill或替换合约；至少40根有效周close，严格MA5>MA10>MA20>MA40，相等拒绝。整周休市不伪造周K。这里定义是周close均线，不要求周内每日OHLC完整；周末close缺失会阻断，符合已写明合同。
3. Stage050 152—170行收盘查询允许末会话<=signal_date，开盘查询严格要求末会话<fill_date。Stage502先cross_delayed_orders再on_bars，双相位使周五开盘不能读取当天周五收盘；已完成周可在周五收盘信号中使用。未来价格/映射扰动、历史prefix和假期末会话测试通过。
4. Stage051真实long定仓与_open_position均加门；原native flat/reverse/rollover调用都通向这两个动态派发方法。env_probe直接返回父类定仓，未改变共用环境统计。short定仓和_open_position直接沿用父类。
5. Stage051真实成交只筛Offset.OPEN与Direction.LONG。Direction.LONG+Offset.CLOSE是空头买平，直接沿用父类。未成交层绑定不可变WeeklyEntryAuthorization，校验原始signal_date/layer/品种/合约/方向/信号，实际开盘再次检查最新完成周；reissue datetime不替代原日期。拒绝调用既有未成交意向清理，保留真实持仓事实。
6. 新strategy MRO中WeeklyLongEntryMixin在NativeRiskBudgetSizingMixin之前；新engine MRO中WeeklyLongExecutionMixin在OpeningRiskBudgetMixin之前。周线通过后继续执行原039/041风险预算、1手cap、开盘风险、生命周期和CleanExecution闸门；不能把native定仓0手复活。已有多仓不会仅因周线转弱被强平。
7. Stage052相对Stage040的金融路径差异仅增加周线提供器、策略/引擎mixin、政策披露和证据输出。数据加载、overlay资格、费用、生命周期、2014热身、100万、2015-01-01至2026-10-16、无AI、不加仓、无4产品限制、日线近似停用C2/C9与供需过滤均继承。新增集成测试对build_settings与A manifest参数逐键比较相同；本审查实际复跑通过。
8. 新源码和测试hash见同名JSON，写记录前再次核对未变化；旧039/040/041对基准git diff为空。052冻结周表、信号/成交周证据以及源码hash/快照，支持金融运行后独立重算。

## 独立验证

- 独立运行本线原有全套166 tests：25.724秒，OK。
- 根任务随后新增052三项集成，本审查独立复跑3 tests：0.055秒，OK。覆盖真实052 FeeStrategy/Engine MRO+050原始周close多头通过成交并保留预算证据、空头周排列拒绝不留幽灵意向，以及A参数逐键一致。合计169项不同测试本审查均实际执行。
- 额外实际断言：策略/引擎MRO顺序、START/END/CAPITAL与040一致、独立calendar末日2027-12-31。JSON保存具体MRO和6个源码/测试SHA256。
- 环境说明：另行导入核验初次受工作树日志写权限失败，尝试/tmp时被原项目runtime guard拒绝；未绕过guard。随后在工作树根目录以获批日志写权限规范重跑，3项集成及断言通过。没有安装依赖或调用金融run。

## 结果与剩余边界

本阶段新增/修改/删除金融回测结果均无；候选期末权益、收益、回撤、Sharpe、滑点、成交次数、胜率均未产生，不填推测值。新增策略参数仅固定周门政策，不修改原native参数。

非阻断边界：原价因果主力拼接存在换月价差；日线近似/静态费用及非历史PIT限制继承；完整calendar按本地源接受，不等于历史公告时点认证；空头虽未加门，组合资金/持仓路径可间接改变其成交。合成测试及静态审查不能代替全量真实成交、账本、数据与置信度复核，也不能认定跨周期稳健或生产认证。

## 反思与后续

- 开始/结束过拟合判断：否，固定通用5/10/20/40、严格排列，无收益选参；但提出于看过历史基线之后，存在后验选择偏差，完整样本仍为研究内证据。
- 开始/结束继续价值判断：是，可用一次固定C回放证伪慢趋势过滤，检验机会损失与费用后路径；无论收益如何均不追加阈值追逐。
- 下一步：根任务冻结代码/协议后运行唯一新C目录；本独立agent随后复核全量真实long open的两份周证据、native预算、周价/映射时序、费用、账户/逐笔账本、残仓及A/C年度差异，再决定是否交付。
- 合入建议：本阶段仅新增本stage markdown/JSON；不更新LINE/registry/root总账，不提交git或更改实现。
