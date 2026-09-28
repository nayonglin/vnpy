# Stage000 物理供需与会员持仓PIT覆盖预注册

## 阶段身份

- `line_id`：`futures_trend_xgboost_pit_physical_positioning_context`
- 冻结时间：2026-09-03 02:50 CST
- 线上逻辑回归基准：`m0005_20260901T165450+0800_1961d98ccb2b`
- 本阶段：Stage000合同冻结；下一阶段只允许运行一次Stage001无标签覆盖审计。
- 研究目标：保留线上逻辑回归排序A不变，审计基差、仓单和会员持仓是否能够作为彼此独立于旧价格/曲线/账户特征的PIT信息家族，供未来低复杂度XGBoost排序器研究。
- 隔离边界：不修改正式release、生产checkout、CTP、持仓、订单、邮件或定时任务；Stage001不读取收益/回撤标签，不训练模型，不运行策略回测，也不读取sealed holdout。

## 调研结论与假设

- 商品期货basis与库存/便利收益及风险溢价存在经济联系，但论文中的统计关系不等于当前候选池可交易alpha。参考：<https://www.nber.org/papers/w13249>。
- XGBoost Learning to Rank要求把同一决策月的候选作为同一`qid`查询组；只有覆盖门通过后，未来阶段才允许讨论按月组内排序。参考：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- 冻结假设：基差与会员持仓的非线性交互可能补充线上逻辑回归未表达的实物供需和资金定位信息；仓单只在同一机械门下合格时才可入模，不能因为经济叙事而放宽覆盖要求。
- 已披露的先验勘察：冻结前做过一次只读、无标签的schema与覆盖勘察，观察到基差和会员持仓覆盖明显高于仓单。因此Stage001是数据工程复验和正式准入门，不是未见数据上的独立验证，也不提供任何收益有效性证据。

## 冻结输入

- A排序面板：`research/lines/futures_trend_xgboost_pit_market_context_after_listing/artifacts/stage001_market_context_coverage/ranked_a_panel.csv`，SHA256=`1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2`。
- 基差2020-2022：`examples/portfolio_backtesting/backtest_outputs/external_supply_demand_cache/supply_demand_basis_20200101_20221231.csv`，SHA256=`d32bac39fd9c4ce057291768bbb9032520469127c90b9ef13caf810611c6796a`。
- 基差2023-2026：`examples/portfolio_backtesting/backtest_outputs/external_supply_demand_cache/supply_demand_basis_20230101_20260417.csv`，SHA256=`150b1f13c07bb02a3ce410e46fec4d4b5c491930c77a9133fd601f3f93f19170`。
- 仓单2020-2022：`examples/portfolio_backtesting/backtest_outputs/external_supply_demand_cache/supply_demand_warehouse_20200101_20221231.csv`，SHA256=`86d6964ee422c909376faf130ae53a1bac9800d59a8e7a0180ab52835b39349f`。
- 仓单2023-2026：`examples/portfolio_backtesting/backtest_outputs/external_supply_demand_cache/supply_demand_warehouse_20230101_20260417.csv`，SHA256=`1385b1ff9effad4c0bf103d042123d46b20694a84e2df582be18fb6b4643796c`。
- 会员持仓原始表：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_combined_raw_stage080_member_rank_2022_backfill_feasibility_v1.csv`，SHA256=`9b22de83f4530859bcb440e016ab89017d5e453f1660dd4b841aa792ce43afbf`。
- 输入身份必须在运行前后逐文件一致；任一SHA漂移立即失败，不发布部分结果。

## Stage001数据合同

- 固定面板身份：`797`行、`47`个`eval_date`、`18`个`product_vt_symbol`；只读取`eval_date/product_vt_symbol/pit_logistic_probability/window_id/a_rank/role`六列。
- 外生源只读取代码中冻结的白名单列；即使输入文件带有收益或回撤字段，也不得读取。
- 所有外生数据按产品映射，记录日为`feature_date`，最早可用日固定为`feature_date + 1 calendar day`，即严格T+1。
- 在每个`eval_date`只允许向后寻找最近已可见记录；`eval_date - feature_date`必须位于`[1, 7]`自然日。超过7日直接标记不可用，不前向填充、不跨产品填充、不补0。
- 基差家族固定原始量：`dom_basis_rate`、`near_basis_rate`。
- 仓单家族固定原始量：仓单数量、当日变化和按原始日序列计算的20期变化和；本阶段只审覆盖，不决定其可入模形式。
- 会员持仓家族固定原始量：Top20多空持仓净比例、多空持仓变化净比例、成交/多空总持仓压力比例；优先使用品种汇总行，否则对该品种当日可用行求和。

## 冻结覆盖门

- 单家族行覆盖率必须`>= 0.50`。
- 家族活跃月定义：当月rank10该家族可用，且`a_rank > 10`的挑战者至少2行可用。
- 单家族47个月活跃月必须`>= 24`。
- 前18个开发月中活跃月必须`>= 12`。
- 2022、2023、2024、2025、2026每个出现年份的活跃月都必须`>= 4`。
- 至少2个家族同时合格，且`basis`必须合格；任一外生家族覆盖率必须`>= 0.95`。
- 仓单不合格不会单独杀死本线，但只能保留为诊断字段；只有通过全部单家族门的家族才允许进入Stage002特征预注册。
- PIT来源日期违规必须为0；双跑DataFrame必须逐值一致；gzip时间戳固定，工件manifest必须可复算。
- 通过决策固定为`stage001_physical_positioning_coverage_pass_ready_for_feature_preregistration`；失败决策固定为`stage001_physical_positioning_coverage_fail_stop_no_features`。

## 结果隔离与后续边界

- Stage001通过只授权编写Stage002特征合同，不自动授权特征实现、标签读取、XGBoost训练、参数搜索、策略回测、真实引擎或holdout。
- Stage002若获准，只能保留线上逻辑回归A排序，并使用合格外生家族相对rank10的少量连续差值；禁止产品、交易所、年份、月份编码，禁止按Stage001覆盖结果新增缺失指示器或利用XGBoost原生缺失分支暗中识别品种。
- 后续训练规格必须在读取任何标签前冻结`qid`、时间切分、成熟期、模型参数、selector、重复性、效果门和停止规则，并经过独立预审。
- 任何未来模型只有在development OOS同时改善收益目标和回撤目标、通过分年与leave-best-out门后，才可能申请真实策略A/B；这仍不等于正式接入。

## 开始反思

- 是否正在过拟合：**Stage001本身否**，因为它不访问结果标签，只做冻结数据的可用性和PIT审计；但覆盖已经被先验勘察过，因此不能把其通过率当作新的统计证据。若因仓单覆盖不足而改年龄、门槛或缺失处理，则会构成结果后救援。
- 是否值得继续：**有条件地是**。基差和会员持仓属于旧价格/曲线/账户特征之外的经济信息，先用一次无标签硬门判断可用性成本低；如果不足两个家族合格，本线立即停止。

