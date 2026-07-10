# Stage177 lc AI池拦截根因与底层原理审计

## 基本信息

- 时间：2026-07-10 20:01 CST
- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 当前正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 当前正式 AI 池截面：`2026-06-30`
- 阶段性质：只读模型血缘、运行时 membership、数值复算与设计边界审计
- 是否重要突破：否
- 是否触发 A/B：否
- 是否连接 CTP：否
- 下单/撤单 API 次数：`0/0`

## 外部调研与判断

- Microsoft Qlib 的 PIT 设计强调历史决策只能使用当时可见数据；本次据此检查月末截面、标签截止和历史 membership，而不是用 7 月结果反推 6 月模型：https://github.com/microsoft/qlib
- scikit-learn 的时序验证原则要求训练样本先于测试样本；本仓采用自定义窗口，不是 `TimeSeriesSplit`，因此还需单独检查未来 60 日标签是否跨入测试区间：https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- 判断：`lc` 拦截必须拆成两层。运行时层只做月度白名单 membership；上游模型层才负责把 18 个品种打分并选 Top8。不能把运行时的 `score=0/rank=0` 占位误读成模型真的给 lc 打零分。

## 运行前反思

- 是否过拟合：否。只复核固定模型、固定 2026-06-30 截面和固定 2026-07-10 候选，不改 TopN、阈值、品种或特征。
- 是否还有价值继续做：是。需要区分正常排名淘汰、数据缺失、日期错配、方向开关和实现异常，才能判断是否应服从闸门。

## 结论先行

- `lc2609.GFEX short_case1a` 被拦截的直接原因是：产品键 `lc.GFEX` 不在 2026-06-30 正式 eligibility membership 中。
- `lc` 没有丢数据，也没有被硬资格过滤。它完整进入 18 品种评分横截面，模型概率 `0.4921115223`，排名 `14/18`。
- 正式池只取模型 Top8，再固定补 `fu.SHFE` 为第 9 个卫星；Top8 分界是 `SM.CZCE=0.5888919392`。lc 比分界低 `0.0967804170`，因此正常落选。
- 运行时拦截在当前规则下正确；但这不等于模型已经证明本次 lc 空头会亏损。模型预测的是“该品种未来 60 个交易日对源趋势策略的净贡献能否进入当月横截面上半区”，不是本次方向胜率。

## 当前正式运行时链路

1. `qmt_roll_official_live_config.py` 把当前 C9/15万的 AI eligibility 指向 Stage182 combined CSV。
2. 策略初始化时读取指定 strategy 的 `eval_date/product_vt_symbol` membership。
3. 2026-07-10 候选使用严格早于交易日的最近月度截面，即 `2026-06-30`。
4. lookup 使用产品键 `lc.GFEX`，不是合约键 `lc2609.GFEX`。
5. 该产品不在 6 月30日九行 eligibility 中，`ai_product_pool_allowed=0`。
6. short 开关、`short_case1a` 白名单和 2 手 sizing 都已通过，随后才命中 `ai_product_pool_blocked`。

目标候选实际字段：

- `date=2026-07-10`
- `product_vt_symbol=lc.GFEX`
- `contract_vt_symbol=lc2609.GFEX`
- `direction=short`
- `signal=short_case1a`
- `selected_volume=2`
- `passed_initial_filter=1`
- `candidate_status=skipped`
- `skip_reason=ai_product_pool_blocked`
- `ai_product_pool_entry_effective_date=2026-07-10`
- `ai_product_pool_signal_date=2026-06-30`

## AI池的底层原理

### 1. 它不是价格方向模型

- Stage183 先用一个不带 AI product pool 的旧 `floor35` 源策略做 200,000 元回放。
- 源策略输出每个品种每天的净贡献、滑点、换手、持仓变化，以及候选/开仓/相关性闸门等诊断。
- 因此 AI 池学的是“当前哪些品种更适合这套趋势系统”，不是预测 lc 明天涨还是跌，也不是基本面模型。

### 2. 特征

- 每个品种分别计算过去 `20/60/120` 个交易日特征。
- 每个窗口 36 个，共 `108` 个：
  - PnL、波动、Sharpe-like、最差/最好日、回撤；
  - 滑点、换手、交易次数、持仓变化；
  - 候选数、开仓数、手数；
  - 相关性闸门、pairwise/volume tilt、入场前组合状态；
  - breakout、多空排列、RSI、loss streak。

### 3. 标签

- 每月取最后一个交易日形成 18 品种横截面。
- 对每个品种计算随后 60 个交易日源策略 `net_pnl` 总贡献。
- 在当月 18 个品种内做横截面排名；处于上半区记为 `1`，下半区记为 `0`。
- 越靠近横截面两端的样本权重越高。

### 4. 模型与本次训练

- 模型：`StandardScaler + LogisticRegression`。
- 正则强度：`C=0.20`。
- 当前训练：1,350 行、75 个月、18 品种、108 特征。
- live eval date：`2026-06-30`。
- training label cutoff：`2026-03-31`。
- 3月31日训练标签使用 4月1日至6月30日的 60 个交易日；6月30日自身不参加训练。
- 6月30日 live 特征只使用该日及之前的滚动数据，7月数据不进入该截面特征。
- 只读重训概率与持久化 CSV 最大误差 `5.55e-17`，说明本次模型数值可复现。
- 将 Stage183 源在内存中截断到 2026-06-30 后重算，与读取更新至 7月10日源的 18 个概率最大差为 `0.0`；7月数据没有改写 6月30日排名。

### 5. 选池

- 按模型概率降序；概率完全相同时才用 simple score 和产品代码打破平局。
- 取前 8 名。
- `fu.SHFE` 不在 18 品种模型 universe 中；若不在 Top8，则以第8名分数减 `1e-6` 的占位分固定加入，成为第 9 名。
- 当前正式九个成员：`ru, si, SA, FG, AP, au, jm, SM, fu`。

## lc 的数值归因

### 完整数据检查

- live 横截面有 18/18 品种，lc 在其中。
- lc 的 108 个模型特征缺失数：`0`。
- 非零特征：`93/108`。
- Stage183 position changes 中 lc 有 `5,351` 行，日期 `2023-07-21 -> 2026-07-10`。
- entry candidate snapshots 中 lc 有 `27` 行，日期 `2024-03-04 -> 2026-07-10`。
- 因此本次落选不是行情、合约映射或特征行缺失。

### 当前横截面关键数值

- 20日净贡献：`-40,320`
- 60日净贡献：`-53,340`
- 120日净贡献：`-178,740`
- 60日回撤：`-200,520`
- 60日滑点：`4,300`
- 60日候选/开仓/交易：`4/2/4`
- 模型概率：`0.4921115223`
- 模型排名：`14/18`
- simple score：`-3.5350800102`

透明 simple score 的 lc 分解：

- 120日 PnL：`-1.988671`
- 60日 PnL：`-0.532736`
- 60日 Sharpe-like：`+0.051782`
- 60日盈利日：`+0.080412`
- 60日开仓数：`+0.216466`
- 60日滑点：`-0.519095`
- 60日回撤：`-0.843238`
- 合计：`-3.535080`

说明：simple score 不是主模型输入，只是一个透明诊断和概率并列时的 tie-break；但它直观显示 lc 近期主要受负 PnL、深回撤和较高滑点拖累。

### 与第8名 SM 的精确模型差异

- `SM.CZCE` 概率：`0.5888919392`。
- lc 与 SM 的 logit 差：`-0.3909431298`。
- 按窗口聚合的精确差异：
  - 20日特征：`-0.714093`
  - 60日特征：`+0.659726`
  - 120日特征：`-0.336575`
- 解释：lc 的 60日组合状态有一部分正向抵消，但近期 20日不稳定和更长 120日亏损路径仍把总概率压到第14名。
- 单特征系数存在强相关和相互抵消，不能把某一个系数当成经济因果；窗口和特征族合计比单点解释更可靠。

## 需要辩证看的设计边界

1. **模型证据弱，不应把拦截解释成确定性判断。**
   - 存量 walk-forward：AUC `0.520300`、accuracy `0.534444`、月均 rank IC `0.050210`、与未来 PnL Spearman `0.025291`。
   - 这只是略高于随机的弱排序信号；它能成为固定组合规则，不等于能可靠判断单笔 lc 空头。
2. **存量验证不够严格。**
   - 自定义 walk-forward 没有对未来60日标签做 purge/embargo，训练窗口尾部标签可能延伸进测试期。
   - 当前 live inference 的 label cutoff 是防泄露的，但历史 OOS 指标不能视为严格无重叠证据。
3. **源策略与当前实盘存在代际错配。**
   - AI源是 200,000 元 floor35 旧策略，不是当前 Stage847-C9/15万；当前版本继承的是 `oldAI`。
   - 所以它更像历史风险治理层，不是针对当前 C9 的最优元模型。
4. **PIT universe 有历史零填充风险。**
   - 当前静态18品种被补成所有历史日期的完整网格；lc 在 2023 年上市前也以零状态进入训练横截面。
   - 产品代码本身不入模，因此不是对 lc 身份的直接惩罚，但会污染“零活动状态”的标签关系。
5. **目标是原始现金贡献，不是风险归一化收益。**
   - 标签会同时吸收品种波动、合约乘数、机会数和源策略 sizing，不能解释成纯粹的品种 alpha。

## 判断

- 运行时是否有 bug：当前证据下没有。membership、日期、产品键、short 开关和手数链路都一致。
- 当前拦截是否应遵守：是。它是固定正式策略的一部分；因单个 lc 信号手工绕过会破坏可复验边界并形成事后挑选。
- AI是否证明 lc 本次空头不好：否。它只给出弱的月度产品适配度 veto。
- 是否值得立即调 TopN/阈值把 lc 放进来：否。这会直接围绕今天的落选样本过拟合。
- 更有价值的下一步：只读重做“当前 C9 源 + PIT 上市时间 universe + 严格 purged/embargo walk-forward”的模型资格审计，再决定 AI veto 是否仍配得上正式闸门；不先改正式池。

## 版本与回测记录

- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增策略代码：无。
- 修改策略代码：无。
- 删除策略代码：无。
- 新增策略回测结果：无；本阶段只复算模型和既有 2026-06-30 推理。
- 修改策略回测结果：无。
- 删除策略回测结果：无。
- 期末权益/总收益/最大回撤/Sharpe/总滑点/交易次数/胜率：本阶段不新增策略回测，不适用。

## 主要输出

- 完整18品种评分：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_latest_pool_stage182_ai_product_pool_live_inference_v1.csv`
- 正式九品种 membership：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
- combined 历史 eligibility：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
- 模型 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_summary_stage182_ai_product_pool_live_inference_v1.json`
- Stage901 候选：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_entry_candidates_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`

## 运行后反思

- 是否过拟合：否。没有按 lc 当日结果修改规则，只复核现有模型与闸门。
- 是否还有价值继续做：是，但价值在模型资格和数据时序审计，不在围绕 lc 救参。
- 是否更新 LINE/registry/back_log：否。本阶段为日常实盘解释与只读模型法证，不改变正式版本或跨线结论。
