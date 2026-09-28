# PIT方向一致延续效用标签线

- line_id：`futures_trend_xgboost_pit_directional_continuation_utility`
- 创建时间：2026-09-05 05:18 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 资产/策略：商品期货趋势 / 当前正式AI逻辑回归主体与未来XGBoost独立挑战线
- 当前状态：Stage001已唯一执行并fail-close，本线闭线；尚未读取未来收益、生成标签、训练、预测或回测，禁止重跑或同线救援。

## 核心假设

- 月度AI排名只决定可交易品种池，正式策略方向由逐日持仓状态与事件信号共同决定，不能伪造为月度唯一正式方向。
- 当前C9/15w最终合并设置为多空双开。可以在query date收盘后，用冻结策略的换月延续市场条件分别审查long/short，形成明确命名的`counterfactual_rollover_continuation_direction_proxy`：仅long通过为`+1`，仅short通过为`-1`，其余可观测但不满足延续条件时为`0`；数据不可观测必须保留为空，不得补`0`。
- 若方向代理具备足够横截面覆盖，后续标签只能从下一交易日开始，沿同一实际合约及T-1换月路径计算按`research_code_defined_cost_proxy`扣减后的方向一致效用与下行路径风险；未来路径符号不得参与方向定义。
- XGBoost只有在该经济标签合同通过后才有资格进入独立walk-forward研究；逻辑回归主体始终保留。

## 冻结边界

- Stage001只审计输入身份、query-date OHLC/精确AM41、方向代理覆盖、未来路径身份和研究成本元数据来源；不把零佣金/回测滑点写成历史真实费用。
- Stage001禁止读取未来close/收益/标签，禁止XGBoost或逻辑回归fit/predict，禁止策略回测、true engine、holdout、CTP、订单和生产写入。
- 任一关键覆盖门失败即闭线；不得补0、删品种/日期、缩短历史窗口、把同日收盘当成交价或使用未来收益补方向。

## 当前下一步

- Stage001共13项硬门，12项通过；唯一失败为`formal_action_direction_coverage`：正式动作日`2022-07-29`有50个可观测产品但long/short均为0，不能为未来效用标签提供事前方向。
- 本线不得删除该月、降低覆盖门、补造方向、修改AM41/公式、读取未来收益或重跑；不进入标签、XGBoost或回测阶段。
- XGBoost总研究目标若继续，必须另立研究线并重新定义独立经济对象；不得围绕已知失败日做事后适配。
