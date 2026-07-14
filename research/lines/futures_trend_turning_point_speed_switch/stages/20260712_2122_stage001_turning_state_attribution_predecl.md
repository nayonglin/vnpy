# Stage001 严格 T-1 转折状态归因预声明

- line_id：`futures_trend_turning_point_speed_switch`
- 当前模式：`day`
- 记录时间：`2026-07-12 21:22 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：只读归因预声明；未运行回测、未查看本线状态收益
- 是否重要突破：否
- 是否触发A/B：否；只有本文件全部硬门通过后才允许实现唯一 canary

## 外部调研与判断

- `Momentum Turning Points` 支持把慢趋势与快趋势的 correction/rebound 分开，但论文的月频股票权重不能迁移为本地商品动作。
- `Dynamic Momentum Learning` 覆盖期货动态速度，但分类器和权重自由度过高，本线不使用机器学习、阈值搜索或周期搜索。
- 重叠事件窗不能按独立样本做普通 t 检验；本线预先使用产品与 20 个交易日日期块的双向聚类 bootstrap。
- 独立历史审计确认：固定快慢腿、固定 NAV 混合、全周期实时止损、alignment-break 全平、账户暂停和相邻 MA 阈值补丁均已有反证。本线唯一新增问题是“已有持仓中首次出现 slow aligned + fast opposite 是否跨时期预示后续不利路径”。
- 我的判断：只值得完成一次冻结口径的只读归因；未过门后扫描确认天数、周期、方向或动作没有价值。

## 冻结输入

- 只使用 current C9 的单一权威 `2020-01` A 路径，不把其他冷启动起点复制成独立样本。
- `daily` SHA256：`c4b0615dd3b1aca78385b07265b3dbf049f17e7be6a537ac455302c0ef4ca2c3`。
- `trades` SHA256：`99308e60f2eca5976c9e6faa6110f4255698028c09a8a9c07b4452fb83950907`。
- `positions` SHA256：`eed8341159215b5f9e473294b7df3eccfb930fb2cd04531d8aa876fbb4719a39`。
- `entry_candidates` SHA256：`fba876eb645b1b0488bd30ac60e2c3c98d471ffcf91fb9490cd189352c8f45e1`。
- actual-contract 明文 close/return panel SHA256：`f7309d2ea3709731c2cbcebd8bf6b57e92309ec20367a885426421da86b04da9`，共 `116,445` 行；明确禁止读取同目录旧的 `988,754` 行 `.csv.gz`。
- 所有输入必须为普通文件、非 symlink，并在运行前、运行后各校验一次路径、大小、mtime_ns 和 SHA；漂移即 fail-close。
- `candidate_status=opened` 不能作为成交证据。真实仓位和成交只认 `positions + trades`；候选表只用于匹配入场时冻结的 `target_risk_amount/stop_distance/size`。

## 冻结事件合同

- 行动日为 `t`；状态只能使用 actual contract 在 `t` 前一完整全市场交易日的 close，强制 `asof_date < t`。
- actual contract 必须恰有截至 `asof_date` 连续 40 个全市场交易日的 close；缺口、短窗口、连续/主力合约拼接、旧新合约代换、零填充和 neutral fallback 全部禁止。
- 慢多：`MA5 > MA10 > MA20 > MA40`；慢空反向。快多：`MA3 > MA6 > MA12 > MA24`；快空反向；其余为 neutral。
- 主事件：`t` 开始前已有非零仓位，慢速与该仓位同向，快速度在同一实际合约、同一逻辑持仓 episode 内首次从“非反向”变为完全反向。
- 新开仓成交日、换月新合约首个可观察状态、首个可观察状态已是 opposite、状态不可用、当日开盘前无仓位均不得成为主事件。
- 同一逻辑持仓 episode 最多一个主事件；连续 opposite、恢复后再次 opposite 均不得重复计数。自然平仓或反向后才开始新 episode。
- 逻辑 episode 以产品和方向定义；同方向换月保持同一逻辑 episode，但换月前后 actual contract 分别计算状态，禁止跨合同拼 MA。
- `concordant` 参考组：慢速同向且快速同向的合格状态日，每个逻辑 episode、每个固定 20 交易日日期块只保留最早一行，避免每日重复放大样本。
- 状态覆盖另报全部合格 position-day 的 `concordant/neutral/turning-opposite` 频率、opposite episode 长度和恢复时间，但这些描述量不得用于改确认天数。

## 冻结 outcome 与成本合同

- 主 outcome：从执行日 `t` 开始、最多未来 5 个全市场交易日、且不超过 A 的自然退出/反向日的方向有符号路径，换算为该 episode 入场风险 `R`。
- 主 outcome 的起始价固定为信号已知时的 `t-1` actual-contract close；终点为第 5 个行动日 close，若 actual contract 更早平仓/换月则用真实平仓成交价截断。它衡量状态预测力，不冒充 canary 从 `t` 开盘起可避免的精确 PnL。
- 辅助 outcome：1 日只作诊断；20 日只作方向确认；另报自然退出前剩余净 PnL/R、累计路径 MAE/MFE、基准回撤区间贡献。
- `R` 只允许来自与真实首次开仓匹配的冻结候选 `target_risk_amount` 和 `stop_distance`。无法唯一匹配的 episode 标记 unavailable，禁止用全样本中位数、账户资金或未来亏损回填。
- 价格方向标签与实际净 PnL/R 分开输出；统计主门使用方向有符号 5 日 `R`，经济门使用实际 positions 的净 PnL/R 静态减仓代理。
- 静态减仓代理固定为：事件时持仓 `V` 手，保留 `ceil(0.5*V)`，释放 `floor(0.5*V)`；`V=1` 为可见但不可执行的 no-op。
- 静态代理从 `t` 后第一个完整交易日算到自然退出；`t` 日 PnL 只诊断，不把开盘前已经发生的 gap 或当日无法精确拆分的路径冒充可避免收益。
- 静态代理只按释放比例缩放上述 baseline 路径，不重算复利、后续订单、保证金或 AI 选择，因此即使通过也不能替代真引擎回测。
- 增量成本使用基准真实成交的同合同、后备同产品每手滑点与手续费；缺失则 fail-close。经济门按该行动成本的 `2x` 扣减，不因“未来少一次平仓”抵扣成本。

## 冻结硬门

### 覆盖与样本

- T-1 actual-contract 特征覆盖 `>=95%`。
- 5 日和 20 日 outcome 覆盖均 `>=90%`；`2018-2020`、`2021-2023`、`2024-冻结终点` 任一段不得 `<85%`；opposite 与 concordant 覆盖差不得超过 `5pp`。
- 至少 `120` 个唯一 opposite onset、`60` 个独立事件日、`12` 个产品；多头和空头各 `>=30`。
- 任一产品占比 `<=20%`，任一年占比 `<=25%`。
- 实际可减仓事件至少 `60` 个、`12` 个产品，且三段各至少 `15` 个；否则不允许真引擎。

### 跨周期与统计

- 固定三段为 `2018-2020`、`2021-2023`、`2024-冻结终点`；每段至少 `30` 个事件、`6` 个产品，三段 5 日均值必须全部不利。
- 至少六个年份各有 `>=10` 个事件，其中至少 `5/6` 年的 5 日均值不利；多头、空头也必须分别不利。
- opposite 相对 concordant 的 5 日均值差必须 `<= -0.25R`，中位差必须 `<= -0.10R`。
- 固定随机种子 `20260712`、`20,000` 次产品与 20 交易日日期块双向 pigeonhole bootstrap；双侧 95% 区间上界必须 `<0`。普通 iid t 检验不参与决策。

### 经济性与集中度

- 静态减仓代理扣除 `2x` 增量成本后，在三段必须分别为正。
- 聚合保守下界必须至少覆盖 `2x` 增量执行成本。
- 避免的负 PnL 至少为被削减正右尾的 `1.5` 倍。
- 改善最大的前五事件不得贡献总正改善的 `40%` 以上。

## 唯一后续 canary

- 只有上述所有硬门同时通过，才允许另行预声明并实现一个 canary：已有持仓首次出现严格 T-1 `slow aligned + fast opposite` 时，在下一现有日级可执行时点一次性把当前实际仓位降至 `ceil(50%)`。
- 剩余仓位完全沿用 C9；同一逻辑 episode 内不恢复、不反手、不运行快腿、不影响新开仓或 AI 池；自然平仓/反向后才重置。
- Stage001 若只在某个 horizon、年份、方向、产品或 neutral 子集有效，或者结果似乎支持多个动作，均直接关闭本线，不选择替代动作。

## 回测/归因参数

- 数据区间：权威 A 路径的 `2020-01` 至 `2026-06-29`；预热只用于特征，不进入样本。
- 账户规模：`150,000`，仅用于核对 A 身份；归因以 `R` 为主。
- 成本口径：基准 positions 已含成本；静态代理额外扣 `2x` 冻结执行成本。
- 样本过滤：仅上述事件合同，不做年份、品种、方向、AI rank 或手数特供。
- 策略/归因口径：只读，不生成订单、不修改正式版。

## 结果

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：N/A（未运行回测）。
- 其他关键指标：N/A（预声明后才允许计算）。

## 过拟合反思

- 运行前判断：否；周期、事件、唯一动作和所有硬门均在看结果前冻结。
- 主要风险：旧 Stage356 周期重复使用、每日状态伪装独立样本、重叠 horizon、换月拼接，以及看完结果后换动作。
- 控制：单一路径、episode 去重、双向聚类 bootstrap、actual-contract T-1 fail-close 和任一门失败即关闭。

## 继续价值反思

- 运行前判断：有，但只值得 Stage001 一次。
- 原因：这是旧固定快慢组合与全平退出实验未直接回答的持仓后转折问题；若失败即可低成本关闭，不应消耗真引擎搜索预算。

## 合入建议

- 更新本线 `LINE.md`：是，标记统计合同已冻结。
- 更新 `research/registry.md`：否，研究线状态未发生跨阶段结论变化。
- 根目录 `memory.md/back_log.md`：否，尚无回测或重要路线结论。

## 资料

- https://people.duke.edu/~charvey/Research/Published_Papers/P158_Momentum_turning_points.pdf
- https://arxiv.org/abs/2106.08420
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3167271
