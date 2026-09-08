# Stage228 实盘真实账户仓位计算

- line_id：futures_trend_stage819_intraday_rules
- 当前模式：day
- 记录时间：2026-09-08 11:40（北京时间）
- 工作区/分支：.worktrees/live-broker-account-sizing / codex/live-broker-account-sizing
- 基线：生产只读核对提交 d492ee072aa5a9d71477235d79f17d2a5db59db3；不修改生产工作区。
- 阶段性质：用户授权的实盘风险口径修复，不优化策略 alpha，不生成回测。
- 是否重要突破：否。
- 是否触发A/B：否；不改信号、参数搜索或历史回测。

## 外部调研与判断

- [LEAN buying power](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/buying-power) 将购买力校验与仓位计算区分。
- [GitHub SecurityPortfolioManager](https://github.com/QuantConnect/Lean/blob/master/Common/Securities/SecurityPortfolioManager.cs) 使用账户组合价值、已占保证金计算剩余购买力。
- [vn.py CTP gateway](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py) 的账户回调区分 Balance 与 Available；本改动使用 reqid 匹配的原始账户字段，不从旧 accounts.csv 反推。
- 判断：保留当前信号和初始止损规则；实盘风险预算应以已验证的券商账户状态为资金事实源。不能把券商允许开仓当成风险预算已正确，也不能在不可变 payload 哈希和授权绑定后修改手数。

## 已确认设计和执行计划

- [x] 从生产基准创建独立分支，保留原工作区所有未提交改动。
- [x] 运行现有 Stage905 基线：LANGUAGE=zh_CN 下 36 passed、4 subtests passed。默认英文环境有既有中文枚举断言差异，未改测试或业务来绕过。
- [x] TDD：独立纯计算函数，用真实权益、Available、CurrMargin、冻结资金及产品占用计算风险预算和手数。
- [x] 只读数据源：从已有 reqid 匹配的 CTP 账户和持仓响应生成脱敏资金快照，绑定查询代号和 manifest；旧快照不提供可信资金时新增仓位 fail-closed。
- [x] Stage905 在不可变哈希和入 spool 之前确定数量，保留影子数量和完整计算审计；缺少新鲜账户、精确匹配信号风险或完整身份时禁止开仓。
- [x] 保持重试最多一次且不扩大根仓位风险；实时平仓不受开仓资金缺失阻断；哈希后不改数量，最终提交仍保留券商资金/可开量硬门。
- [x] 集成测试覆盖资金减少/增加、冻结、持仓占用、非法值、老快照、缺失信号、重试、重复检测和不可变委托哈希。
- [x] 独立工程评审与回归；不连接 CTP，不做 smoke，不改 launchd、manifest、授权或生产激活。

## 参数与边界

- 使用真实账户全户权益作为当前 C9 的资金事实源；保留正式策略已有 sizing 上限和风险约束，不自动将 15w 标签当作真实余额或新增资金上限。
- 修改的是已发布冻结信号的执行手数，不让实盘资金反向重跑影子信号或改变信号选择；profile 的 capital=150000 仍是版本身份，不是本次执行定量资金。
- 每手风险仍按完整初始止损距离计算，不因 0.5R 快速止损翻倍开仓。
- 资金预算 `max(0, min(Available, min(Balance, existing_equity_cap) * 0.9 - CurrMargin - frozen))`；Available 已含冻结约束，不再次从 Available 重复减冻结。原 min_risk_per_trade=1000、权益上限100万元及信号风险倍率保留；实际可开不足1手时为0，不强制1手。
- 同次检测只生成一个可执行新增仓位；已入 spool 的业务身份不重新定量、不换 ID 绕过哈希冲突。前次有副作用的委托必须终态可对账，资金查询必须覆盖前次状态变更后才能计算下一笔。
- Stage931 用当前物理报单价、最新原始账户和持仓再次校验风险上限及合约乘数；只拒绝、不偷偷缩量/增量。不能因为券商 MaxOrderVolume 足够，就跳过风险预算。
- 独立评审发现真实/影子手数不同会影响日线全平与止损后影子对齐，因此同时补齐可证明的全平语义；不推断部分平仓比例、不放宽既有 exact-close 门。
- 先解析保护限价和 tick 吸附，再计算风险手数；Stage905 定量价与最终 payload 价一致。NaN 风险开关不得降级为关闭；risk cluster 必须绑定实际目标品种。
- 已占保证金和冻结从券商读取；候选合约保证金估算沿用冻结信号的费率，不能称为券商精确新开保证金率，提交前保留券商 MaxOrderVolume 硬门。
- 不以事后账户快照回填历史下单状态，不宣称本阶段验证了真实成交。
- 无回测；期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率均不适用。

## 中间验证

- 12:04 左右：账户快照、定量、Stage174/905/941、spool、授权和 Stage931 执行门相关16个测试文件：440 passed、575 subtests passed。
- Stage260 profile / Stage901 AI policy 既有回归：37 passed、2 subtests passed。
- 同 generation 持仓读取、合约乘数不匹配、reconciliation 后资金查询水位等回归均先观察到 red，再修正至 green。
- 全平与已发委托资金释放的新增闭环仍在独立评审及最终回归中，以阶段末最终验证为准。

## 上线前不可省略的限制

- 此分支是本地修改，未 commit/push、未部署或激活、未连接 CTP、未下单；生产 checkout 仍为 d492ee072aa5a9d71477235d79f17d2a5db59db3，tracked 状态干净。
- 旧 sent 缺新定量审计、原账户绑定或可证明终态时拒绝新增仓位；不能删除/跳过旧 spool、按日期忽略或伪造 reconciliation。部署前需按实盘 SOP 明确迁移和对账证据。
- 重定量日线全平需要唯一策略归属 root/epoch/net，未归属成交或手工等量替换仓位禁止平仓。Stage260/905 仅规划，明确标记 final_broker_trade_coverage_required；发送前强制重新核对券商成交、订单、持仓覆盖。
- 当前新增 full-close 执行证明仅支持上海时区当自然日、全部今仓、单个物理委托。跨日持仓、今昨拆单、历史成交覆盖不足仍 fail-closed；这意味着该分支不能直接作为完整跨日实盘版本上线。不得将该限制隐藏成“已完成全平生产闭环”。
- 原实时0.5R止损路径、最多一次重试及旧 exact-close 门保留；新增 full-close guard 不扩大部分平仓权限。旧持仓迁移、跨日归属证明及上线观察需要单独验收。

## 最终验证与评审收口

- 2026-09-08 12:35（北京时间）收口记录：22个相关测试文件最终总回归 **633 passed、577 subtests passed**，25.70秒，退出码0。
- 命令环境：`LANGUAGE=zh_CN OFFICIAL_LIVE_OUTPUT_DIR="$PWD/.test-output" QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1 .py311/bin/python -m pytest -q`；仅执行本地单元/集成测试，使用模拟券商回调，不运行策略回测。
- 覆盖：Stage174查询快照、真实定量、Stage901影子对齐、Stage260、Stage905、Stage941、spool、授权、Stage931最终状态/资金/归属门、成交记账，以及新 sent reconciliation。
- 新增持久化 sent 终态证明，精确绑定 payload/lease/state revision、账户/查询 generation、订单集合与 ledger/hash 水位；同一 SQLite 事务写 proof 与 `sent→reconciled`，不改变 schema。不必等新开仓意图才对账；当天归档证明后，次日查询不再包含昨日订单也不会重新卡住。错误proof、状态并发变化和事务崩溃均不产生半写终态。
- 独立工程评审提出的定量后改价、NaN风险开关静默删除、cluster错配、sent永久阻断/跨日持续性均已补 red-green 测试并修复。
- 归属审查另指出跨日、拆单及历史成交覆盖仍不能可靠证明；本阶段保留明确拒绝并列为上线前阻塞，不用扩大权限来伪装解决。
- Python编译检查与 `git diff --check` 通过。环境未安装ruff，未安装新工具或声称通过ruff。
- 交付状态：独立工作区本地补丁完成；未 commit/push，未进行生产激活。原工作区未提交改动不包含在本分支中，未修改原工作区。

## 反思

- 开始：不过拟合；修正事实源和执行风险约束，没有观察回测后调阈值。
- 继续价值：有；实盘与理论账户存在仓位/收益/费用差异，不能共用影子风险资金。
- 结束：不过拟合；没有参数搜索、回测择优或 alpha 改动，只修资金事实源、不可变风险预算和副作用证据闭环。
- 是否有价值继续：是；本地真实账户定量已验证，但正式激活前必须完成旧spool/旧持仓迁移审核及跨日归属与拆单全平证明，不应直接部署此分支。
