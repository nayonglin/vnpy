# Stage000打分日固定实际合约标签资格预注册

- 时间：2026-09-05 01:42 CST
- line_id：`futures_trend_xgboost_pit_query_date_fixed_contract_labels`
- 是否重要突破：否；这是新的标签执行语义资格审计，不是模型或收益版本。
- 用户授权：后续研究操作默认授权；生产、CTP和订单继续禁止。

## 上游事实

- 原固定主力合约标签有`3,788`条`exit_bar_missing`，换月感知路径又因低流动性使`1,849/56,272`条路径不可直接交易。
- 上一线失败集中于少数产品，但禁止按已知失败产品名单事后删除；必须使用所有产品一致的query-date规则。
- 冻结候选窗口仍为`56,272`行、`1,046`个qid，entry为query date下一全市场交易日，label end为第21个全市场交易日，持有期20个return leg。

## 外部调研与判断

- QuantConnect官方individual-contract研究示例先按expiry过滤，再按open interest选择具体合约，并明确关闭fill-forward：<https://www.quantconnect.com/docs/v2/research-environment/datasets/futures/individual-contracts>。
- QuantConnect官方futures universe文档把期限过滤和按open interest选择真实合约作为标准合约链操作：<https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures>。
- XGBoost官方ranking测试以qid/group划分每个查询组，组大小由group pointer定义，因此不同query date保留不同候选数在接口上成立：<https://github.com/dmlc/xgboost/blob/master/tests/python/test_ranking.py>。
- 判断：选择日在query date收盘、入场在下一交易日，可以只使用当时可见信息；固定同一实际合约持有20日，避免未来主力映射决定标签路径。

## 冻结选择合同

1. 输入候选窗口固定`56,272`行/`1,046` qid，不按上一线失败品种、年份或结果删行。
2. 对每个query date，历史窗口固定为截至当日且包含当日的最近20个全市场交易日；缺失bar按不合格计数。
3. 同一产品的候选实际合约必须同时满足：
   - catalog产品身份一致；
   - `expire_date >= label_end`；
   - query date存在日bar且`volume >= 100`、`open_interest >= 100`；
   - 最近20个全市场交易日至少18日同时`volume >= 100`、`open_interest >= 100`。
4. 合格合约固定排序：query-date `open_interest`降序、`volume`降序、`expire_date`升序、`vt_symbol`升序；rank 1为唯一选择。
5. `selection_source_date`必须等于query date；任何query date之后的bar、未来主力映射或未来执行质量不得参与选择。
6. 被选合约从entry date固定持有到label end，20个leg全部使用同一合约，不发生roll_close或roll_open。

## 冻结资格门

- 输入manifest、文件SHA、候选窗口身份与计数稳定。
- 每个qid至少保留`30`个选择成功的产品；`1,046/1,046` qid都必须保留。30来自既有全市场数据资格下界，不按本次结果调整。
- 每条保留路径20个leg的previous/return bar唯一存在，且所有端点`volume > 0`、`open_interest > 0`。
- 每条保留路径只产生entry和exit两个最小1手事件；二者均要求`volume >= 100`、`open_interest >= 100`。
- 所有选择的合约到期日覆盖label end，选择只读query date及更早数据，future selection rows为0。
- `close`读取、收益计算、标签读取、fit、predict、回测、holdout、CTP、订单和生产写入全部为0。

## 决策语义

- 全部硬门通过：`stage001_query_date_fixed_contract_pass_allow_label_value_preregistration_only`。
- 任一硬门失败：`stage001_query_date_fixed_contract_fail_close_no_label_values`。
- 失败后禁止重跑、改18/20、降100/100或30、换排序、删品种/年份、缩20日持有期或按失败明细救援。

## 过拟合反思

- 运行前判断：否。
- 原因：选择规则只来自既有容量、覆盖和到期约束，且在读取新固定路径的未来流动性结果前冻结。

## 继续价值反思

- 运行前判断：有。
- 原因：该语义直接回答“能否用query-date可执行合约构造无换月、无前视的XGBoost标签”；通过前不触碰收益。
