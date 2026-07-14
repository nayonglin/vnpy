# Stage008 当前正式版重新基准与突破质量归因预声明

- line_id：`futures_trend_tight_stop_quality_sizing`
- 当前模式：`research / day`
- 记录时间：`2026-07-14 14:00 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：证据链重置、正式版基准回测与只读归因预声明
- 是否重要突破：否
- 是否触发A/B：否；Stage008 不修改策略仓位

## 用户目标与证据重置

- 目标：在不新增 AI 特征的前提下，寻找高质量、紧止损机会的可解释加仓逻辑；未来候选全周期收益保留至少 `70%`，同时降低最大回撤。
- 旧 Stage001-006 的阈值、图表、收益结论与晋级判断一律不作为 Stage008 假设输入。
- Stage004 修复后产物只用于确认严格执行适配器的已知审计点，不把其 `1.25/0.75`、水下门或质量定义继承到新实验。
- 当前正式基准重新从仓库入口读取：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，资本 `150,000`。

## 外部调研与判断

- AQR《A Century of Evidence on Trend-Following Investing》：趋势跟随在长历史、多市场和多种经济环境中有持续证据；因此不能用单一年份或单根 K 线解释质量。
  - https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing
- Pettersson《Time Series Momentum and Volatility States》：期货时间序列动量在低或下降波动状态下更强，为“趋势位置 + 波动状态”提供外部先验。
  - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2515685
- `pysystemtrade`：规则信号和头寸波动缩放应分层，不能把波动导致的仓位变化误称为 alpha。
  - https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
- Backtrader Donchian 实现：通道必须排除当前 bar，才能让当前价格真正突破前序区间。
  - https://gist.github.com/mementum/1adc2aea1102f222bfa8b93ef892aae8
- 我的判断：优先研究“前序区间极值附近的高路径效率趋势，同时短期波动未扩张且初始止损小于正常日噪音”，不研究单根蜡烛名称、产品黑名单或坏年份补丁。

## Stage008 冻结口径

1. 重新运行 `2020-01-01 -> 2026-06-30` 当前正式版，只跑一个起点。
2. 使用正式 AI 月池、broker10、增量保证金、正式成本和 `0.5R` 开仓日止损后一次重试；新增 AI 特征数必须为 `0`。
3. 根开仓必须等于上一真实交易日夜盘加当前交易日日盘的首个有效分钟 open；缺失即整轮 fail-close。
4. 账户权益必须由引擎成交、当日收盘盯市和成本重建；候选时点权益、高水位和回撤逐行对账。
5. 保存 daily、trades、entry candidates、entry risk、trade events、stop retry events、closed lots 和完整输入/输出 manifest。
6. 生成主策略绝对资金、NAV、回撤、年度 PnL、最差回撤区间及入场事件分布图。

## 冻结特征族

全部特征只能使用信号日收盘时已经完成的日线；下一交易日成交数据不得进入特征：

- `stop_atr14`：正式初始止损距离 / ATR14。
- `breakout_margin20_atr`：方向化信号日极值（多头用 high、空头用 low）相对前 `20` 根已完成 bar 极值的突破距离，再除 ATR14；前20根区间严格排除当前 bar。
- `close_margin20_atr`：方向化信号日 close 相对同一前20根通道的距离，仅用于识别盘中突破后收盘回落，不进入 Stage009 首轮候选条件。
- `directional_efficiency20`：方向化 `20` 日净位移 / 逐日绝对路径。
- `atr14_to_prior60_median`：当前 ATR14 / 前 `60` 个已完成 ATR14 的中位数。
- `directional_clv`、`adverse_wick_ratio`：信号 bar 的方向化收盘位置和逆向影线，仅作拒绝/假突破归因。

## 防过拟合合同

- 发现段固定为 `2020-2022`；Stage008 只允许输出该段的特征与后续闭合机会结果关系。
- `2023-2024` 为验证段，`2025-2026` 为封存段；在 Stage009 规则和权重写入预声明前，禁止输出这两段的特征收益分组。
- Stage009 最多使用 `stop_atr14 / breakout_margin20_atr / directional_efficiency20 / atr14_to_prior60_median` 中三个条件；不使用产品、方向、年份、月份、AI字段或账户回撤。
- 数值阈值只能采用有固定语义的 `0/0.5/1.0`，或发现段不看 PnL 的中位数/四分位；不得按收益搜索最优小数。
- 只允许一个冻结候选进入真实引擎；失败后不救阈值、不改倍率、不删样本。

## Stage008 完整性门

- 严格根开仓、账户权益、成本、成交、0.5R 重试、AI 月覆盖和 manifest 全部通过。
- closed-lot 毛利与 daily 净利加成本严格守恒；所有 open 均归入 flat-entry、retry 或 rollover，孤儿为 `0`。
- T-1 特征未来引用 `0`，覆盖 `>=95%`。
- 基准回测完成后必须拉独立 agent 全量复算；影响结果的问题修复后按原口径重跑。

## 运行前反思

- 过拟合：是，高。相同历史已被多次观察，所以本阶段只重建基准和固定特征，不允许产生策略参数。
- 继续价值：是。重新生成并独立复核当前正式版的严格事件级证据，是判断“高质量紧止损”是否真实存在的必要前提。
