# Stage001 候选边际风险贡献 A/C canary 预声明

- line_id：`futures_trend_candidate_marginal_risk_contribution`
- 当前模式：`day`
- 记录时间：`2026-07-12 18:31 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：结构性组合风险 sizing A/C canary 预声明
- 是否重要突破：否；结果未知
- 是否触发A/B：是，风险部署层只做 A/C，B 无独立 alpha

## 外部调研与判断

- Alexander/Fabozzi 2026 的 leave-one-out 风险分解说明，标准 component risk contribution 可以拆成自身风险与相关风险并保持严格可加总；raw incremental volatility 不可加总。
- Roncalli risk budgeting 给出 marginal volatility/component risk contribution 定义，并说明负相关不必然等于有效对冲。
- Ledoit/Wolf 2004 与 scikit-learn 官方实现支持有限样本下使用自动收缩协方差，避免手写和扫描 shrinkage。
- pysystemtrade 把 position sizing、correlation 和 diversification 分层，同时提醒 shrinkage 校准困难；本阶段只缩手，不使用 diversification multiplier 加杠杆。
- 我的判断：验证标准 RC sizing 有一般化价值；继续 absolute inflation、raw leave-one-out、2022 黑名单、窗口/阈值扫描没有价值。

参考：

- https://arxiv.org/abs/2604.10375
- https://www.thierry-roncalli.com/download/risk-budgeting.pdf
- https://www.sciencedirect.com/science/article/pii/S0047259X03000964
- https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html
- https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md

## A/C 与执行顺序

- A：当前 official AI + 当前 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- B：不适用；风险 sizing 层不能 standalone 交易。
- C：A + 当日候选标准 RC 缩手。
- hook 固定在 `super()._plan_flat_entry_candidates(day_contexts)` 完成后；此时 AI、现有同向相关门、selection、Stage830 broker10、增量保证金与并发门均已形成最终计划，但尚未逐个发出开仓。
- C 只处理 `candidate_status=opened` 且 `selected_volume>0` 的 `flat_entry`；Close、换月、已有仓、加仓、0.5R stop/retry、AI 和信号完全不改。
- 同日现有持仓和全部最终 opened 候选形成带方向现金名义暴露 `x`；候选按完整 batch 同时计算，结果不得依赖产品遍历顺序。
- `sigma_p=sqrt(x'Σx)`、`MRC_i=(Σx)_i/sigma_p`、`RC_i=x_i*MRC_i`、`IC_i=x_i^2*Σ_ii/sigma_p`、`CC_i=RC_i-IC_i`。
- `RC_i<=IC_i` 时 scale=`1`；`RC_i>IC_i>0` 时 scale=`IC_i/RC_i`。
- 整数化固定为 `max(1, floor(baseline_volume*scale))`，并强制 `after<=before`；不因缩手释放的名额递补其他候选。
- 缩手发生在现有风险门之后，只能进一步降低风险；现有 gate 字段保留为 MRC 前证据，实际 selected volume 和 reservation 使用 MRC 后手数。

## T-1 63 日数据合同（经独立审查修订）

- 产品全集固定为 current official AI 文件的 `19` 个产品，不使用 Stage137 赢家/输家标签。
- 独立审查后撤销主力连续收益输入：本地历史主力表缺逐日发布版本，不能给新特征提供严格PIT证据。主力映射 SHA256 `1b77f053...428` 只用于A baseline identity，不进入MRC收益矩阵。
- AI 固定：Stage182 current AI，SHA256 `fc50e035cd66b65e94261ef70476747daa94ae73071d0f4d7206ff7b644271fc`，`504` 行、`55` eval_date。
- 每个batch直接使用当日真实持仓合约和计划开仓合约的actual-contract日收益，不跨合约拼接；现有持仓方向以 `current_pos` 正负号为准。
- 日线主源固定只读 `.vntrader/database.db`，当前 SHA256 `59f0bd364253d7ec029cc183d48f161c15b9ee9af01075956924b4dad958f723`。
- 数据库缺失的 `fu2005/fu2009/fu2605` 固定从 Stage462 真实分钟文件取每个交易日最后一根日盘 bar；SHA256 分别 `f83b2937...d45 / cf8b826c...7d2 / ecfb330c...950`。
- 面板覆盖数据库/固定backfill中的actual contracts至 `2026-06-30`；每个合约首个close没有收益，禁止补零。
- 每次风险计算只允许 `date < candidate_local_date`，在所有当时持仓和候选合约的共同有效日期中取最后 `63` 行。
- 若某日共同有效观测不足 `63`、输入非有限、产品缺失或时点不闭合，该日整个 MRC batch 显式 `unavailable`，所有计划保持 A 手数；不得缩短到 57/40/32、补零或使用当前日。
- 已知静态边界：current-C9 2020锚点 `265` 个真实 would-open batch中 `264` 个actual-contract batch通过；`2021-04-09` 的 `lh2109.DCE` 只有 `58` 个共同有效日，必须按上述 unavailable no-op，不能造历史。

## 最小 canary

- 起点：`2020-01 / 2022-01 / 2022-07 / 2026-01`。
- 统一终点：`2026-06-30`。
- 账户：`150,000`。
- 成本：当前 metadata 1x 滑点/手续费；当前手续费字段为 0 时必须披露为收益上界。
- 先静态审计，再运行四锚点 A/C；不先跑 2x/3x 或逐半年 full。

## 冻结通过门

- A 四锚点逐项复现 Stage137 current-C9：权益、收益、回撤、Sharpe、滑点、交易数、胜率和水下期在预声明容差内。
- 输入源运行前后 SHA 不变；return panel、AI、mapping、数据库 query、Stage462 backfill 和关键代码 manifest 闭合。
- 每个 available batch 恰好 `63` 个 T-1 共同日期；current/future row 使用数为 `0`。
- batch 产品顺序置换后 RC、scale 和 after volume 完全一致。
- 所有局部计划和最终 candidate snapshot 均 `0 < after <= before`；不得放大、不得静默归零、不得递补。
- 四锚点均无破产，会计、持仓、保证金和 terminal 闭合；C broker10 峰值不得恶化。
- 四锚点收益保留均 `>=70%`。
- `2020-01/2022-01/2022-07` 最大回撤均严格改善。
- `2022-01/2022-07` 最长水下期均严格缩短。
- `2026-01` 最大回撤不得比 A 恶化超过 `1pp`。
- 任一门失败：`canary_pass=false`、full/cost stress 禁止，不改窗口、估计器、scale、floor/min1 或产品规则救参。

## 回测记录字段

- 每个 A/C 报告期末权益、总收益、最大回撤、Sharpe、总滑点、总手续费、总交易次数、非零日胜率、逐笔胜率、最长水下期、broker10 峰值。
- 报告 MRC batch/available/unavailable、缩手事件/手数、RC/IC/CC、观测日期跨度、产品数、顺序不变性和 source hash。
- 输出 normalized equity、absolute equity、drawdown 和 2022 focus 图。

## 运行前反思

- 是否过拟合：否，但存在模型估计误差风险。公式、63日、LedoitWolf、floor/min1、四锚点和 gate 均在结果前冻结，未使用 2022 品种标签。
- 是否有价值继续：是。旧协方差线没有测试这个语义，基础引擎已有天然 batch hook；一次 canary 能直接证伪。
