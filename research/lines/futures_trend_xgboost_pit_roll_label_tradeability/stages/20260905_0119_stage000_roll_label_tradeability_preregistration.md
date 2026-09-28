# Stage000 PIT换月标签可成交性资格预注册

- 时间：2026-09-05 01:19 CST
- line_id：`futures_trend_xgboost_pit_roll_label_tradeability`
- 是否重要突破：否；这是标签值生成前的独立可执行性审计，不是模型或收益版本。
- 用户授权：后续研究操作默认授权；生产、CTP和订单继续禁止。

## 上游事实

- 到期安全线已冻结56,272路径、1,046 qid、1,125,440段，全部endpoint bar存在、到期覆盖和因果选择通过。
- 6个fallback中，`wr2401`在选择日持仓73/成交65，`RS607`持仓6/成交0；因此bar存在不等于可成交。
- 上游manifest SHA256：`9f768fc6de7ccd3eb240c29f0444249bd333356d756b137197dc78e4f5f44d76`。

## 调研与判断

- 仓库既有Stage565容量审计把单次订单量/日成交量最大1%和持仓/OI最大1%作为硬容量原则；旧全市场可交易池的近期中位成交量门也为100。
- 对最小1手订单，两个1%原则分别等价于执行日`volume >= 100`、`open_interest >= 100`。这是任何实际仓位的必要下界，不依赖账户规模或收益结果。
- QuantConnect官方容量文档按成交后的市场成交量估算可用容量；LEAN官方`VolumeShareSlippageModel`按订单/总成交量占比计算冲击，并对零或负bar volume采用最大冲击：<https://www.quantconnect.com/docs/v2/lean-engine/statistics/capacity>、<https://github.com/QuantConnect/Lean/blob/master/Common/Orders/Slippage/VolumeShareSlippageModel.cs>。
- CME官方交易者指南把volume和open interest作为描述期货流动性的核心维度：<https://www.cmegroup.com/education/files/a-traders-guide-to-futures.pdf>。
- 判断：先把价格观测有效性与执行容量分开。正成交/正持仓只证明close不是明显陈旧；100/100门证明最小1手不超过既有1%容量线。

## 冻结审计合同

1. 复用上游全部56,272路径和1,125,440段，不删行、不改合约、不重排fallback。
2. 对每个leg的selected contract，连接previous date与return date的`volume/open_interest`；只读身份、成交量和持仓量，不读close。
3. 价格观测质量：每个endpoint必须`volume > 0`且`open_interest > 0`。任一为0/缺失/非有限，则该leg的close标签质量不合格。
4. 执行事件只包括：首段previous date入场；相邻leg合约变化日同时平旧/开新；末段return date退出。持仓不变的中间日不重复计订单容量。
5. 每个执行腿按最小1手审计，要求当日`volume >= 100`且`open_interest >= 100`；换月日旧/新合约分别审计1手。
6. 记录每个事件的角色、日期、合约、volume、OI、订单/成交量占比、持仓/OI占比与失败原因。
7. endpoint质量和执行容量只做资格判断，禁止用结果改选合约、缩短窗口、提前退出、删除产品或读取close。

## 硬门

- 输入manifest与SHA稳定；上游路径/leg计数和身份不变。
- 所有endpoint必须匹配唯一bar身份；future selection/reselection仍为0。
- `price_observation_quality_gate`：全量leg两端均正成交、正持仓。
- `minimum_one_lot_capacity_gate`：全部入场、roll close、roll open、退出事件满足100/100。
- `wr`和`RS`已知fallback必须进入事件审计，不得绕过。
- close读取、收益计算、标签读取、fit、predict、回测、holdout、CTP、订单和生产写入全部为0。

## 决策语义

- 全部硬门通过：`stage001_roll_label_tradeability_pass_allow_roll_label_value_preregistration_only`。
- 任一质量或容量门失败：`stage001_roll_label_tradeability_fail_close_no_label_values`。
- 失败不授权改阈值救援；后续只能基于失败结构另立候选宇宙或策略执行语义研究线。

## 过拟合反思

- 运行前判断：否。
- 原因：规则来自既有容量门和一手数量恒等式，且在全量流动性分布打开前冻结。

## 继续价值反思

- 运行前判断：有。
- 原因：该审计会直接回答“完整路径是否可形成真实可交易标签”，避免把数据可用性误当alpha。
