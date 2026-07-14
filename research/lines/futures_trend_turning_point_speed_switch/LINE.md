# 趋势策略转折点速度切换研究线

- line_id: `futures_trend_turning_point_speed_switch`
- 创建时间: `2026-07-12 21:03 CST`
- 当前模式: `day`
- 资产/策略: 商品期货趋势 / 当前 C9 15w 独立研究分支
- 当前状态: Stage001 严格 T-1 turning-state 归因已完成并关闭；不允许写真引擎 canary
- 当前基准: `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 独立性: 只写本研究线目录；不改正式实盘、CTP、邮件、launchd、AI 月池或其他研究线

## 研究目标

- 每个验证起点保留正式 A 至少 `70%` 的收益，同时严格降低历史最大回撤。
- `2022-01` 与 `2022-07` 起点还必须严格缩短最长水下期。
- 不接受靠统一降风险、现金稀释、同向卫星、候选相关性缩手或年份/品种补丁换平滑。

## 结构性假设

- 趋势策略的核心损失机制之一是转折点滞后：慢信号仍沿原方向时，快信号已进入 correction 或 rebound。
- 当前 C9 的 `0.5R stop/retry once` 处理价格触发后的执行，但不显式刻画快慢趋势速度分歧。
- 若产品级快慢状态在严格 T-1 下能跨年份识别后续不利路径，则可以研究“信号速度切换/风险释放节奏”；若只能解释2022或依赖未来路径，本线在归因阶段关闭。

## 与既有失败路线的区别

- Stage356 是固定快/慢 MA 策略和固定 NAV 权重混合，已反证；本线不重跑固定快/慢组合，也不扫周期或权重。
- Stage024/029 是账户或 regime hard pause，已反证；本线先看产品级方向转折，不用账户回撤、连败或年份决定状态。
- MRC Stage001 是同日候选相关风险缩手，已反证；本线不使用协方差、RC、候选 rank 或手数 scale。
- 全市场 veto、OI、仓单、期限结构、xsmom/carry、储备金、同向卫星均不在本线重复。

## 冻结信号族

- 慢/正式速度：当前策略既有 `5/10/20/40` 日 MA 结构，不修改。
- 快速度：历史 Stage356 已事前定义的 `3/6/12/24` 日 MA 结构；不扫描相邻周期。
- 每个状态只使用 concrete contract 在决策时点前已经完成的日线；行动日 `t` 只能使用 `<=t-1` 数据。
- 快多：`MA3 > MA6 > MA12 > MA24`；快空：`MA3 < MA6 < MA12 < MA24`；其余为 neutral。
- 对当前正式持仓方向：快信号同向为 concordant，反向为 turning-opposite，neutral 单列；不得把未来 MFE/MAE、未来收益、回撤谷底或2022标签作为输入。

## 验证顺序

1. 外部一手论文/GitHub 调研，确认转折点与多速度组合的理论边界。
2. 审计 current C9 已验证明细、actual-contract T-1 日线覆盖和可安全实现 hook。
3. Stage001 只读归因：覆盖、状态频率、未来1/5/20日有符号收益、closed-lot PnL、回撤贡献和分年/分时期稳定性。
4. 由独立 agent 复核数据、未来函数、聚合、样本量、逻辑、置信度和 bug。
5. 只有预声明归因门全部通过，才允许另写真引擎 canary 预声明；否则本线关闭。
6. 每次真引擎回测后必须再拉独立 agent 全面复核；影响结果的问题先修复并原口径重跑，不影响结果的 P2/P3 写入本线日志。

## Stage001 最终结论

- 冻结区间：`2020-01-02 -> 2026-06-29`；五份输入 SHA 前后完全一致。
- current C9 已有持仓严格 T-1 状态 `1,529/1,529` 可用，`269` 个逻辑 episode、`304` 个 concordant references。
- 状态交叉表只有 `concordant/neutral`；所有 `fast opposite` 行为 `0`，因此主事件 onset 也是 `0`。
- 首轮独立 review 的截止日 P1 已修复并原口径重跑；最终 review `P0=0/P1=0/P2=1`，P2 仅为本记录尚未收口，结论置信度 `99%`。
- 机械决策 `CLOSE_LINE`、`canary_allowed=false`。零事件不是换月、episode 去重、风险字段缺失或未来函数造成。
- 不得改 MA 周期、确认天数、方向、年份、产品或动作来制造样本；不得实现 50% 减仓 canary。

## 反过拟合边界

- 不扫描 `2/4/8/16`、`4/8/16/32`、`6/12/24/48` 或任何相邻周期。
- 不按2022、产品、方向、月份、AI rank、手数、账户状态选择是否启用。
- 不根据 Stage001 结果选择“连续1/2/3天确认”、fast权重、减仓比例、反手或重进次数。
- Stage001 若只在单一时期有效，不写真引擎。
- 真引擎候选若出现，必须是单一、低自由度、可解释的状态动作；失败后不救参。

## 当前 TODO

- 本线已关闭，无策略实验 TODO。
- 保留工具、测试、输入/代码 manifest、状态表、gate matrix 和独立复核结论供查重。
- 后续只能另开结构不同的新研究线，不得在本线做参数救援。

## 外部资料

- https://www.sciencedirect.com/science/article/pii/S0304405X23001034
- https://www.aeaweb.org/conference/2021/preliminary/powerpoint/ihbRDkeH
- https://arxiv.org/abs/2106.08420
- https://github.com/pst-group/pysystemtrade
- https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
