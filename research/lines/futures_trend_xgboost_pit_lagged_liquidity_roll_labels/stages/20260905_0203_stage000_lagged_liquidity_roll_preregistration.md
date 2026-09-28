# Stage000滞后流动性动态换约标签资格预注册

- 时间：2026-09-05 02:03 CST
- line_id：`futures_trend_xgboost_pit_lagged_liquidity_roll_labels`
- 是否重要突破：否；这是标签执行语义资格审计，不是模型或收益版本。
- 用户授权：后续研究操作默认授权；生产、CTP和订单继续禁止。

## 上游事实

- 打分日固定实际合约可成功选择`54,305/56,272`条路径，但未来有`3,615`条不合格。
- 固定合约容量失败事件`3,453`个，其中退出事件`3,429`个；首次价格失败`1,916`条，其中`1,889`条发生在第11至20个leg。
- 这说明主要障碍是20日持有期间流动性迁移，而不是query date候选宽度不足；禁止按失败品种或年份事后删样本。
- 冻结候选窗口仍为`56,272`行、`1,046`个qid，entry为query date下一全市场交易日，label end为第21个全市场交易日，持有期20个return leg。

## 外部调研与判断

- QuantConnect官方期货Security Master用映射模式选择连续合约的底层实际合约，并用`SymbolChangedEvent`处理合约变化：<https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-futures-security-master>。
- QuantConnect官方期货数据处理文档明确连续合约用于价格序列，交易时应处理映射后的实际合约：<https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/futures/handling-data>。
- TqSdk官方API把历史主连映射作为独立可查询数据：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html>。
- CME资料说明期货流动性会随换月迁移，成交量和持仓量是识别活跃合约的核心市场量：<https://www.cmegroup.com/market-data/files/cme-group-rolling-futures-indices-methodology.pdf>。
- 判断：按前一交易日持仓量优先、成交量次优选择下一交易日实际合约，能响应流动性迁移；但外部资料只支持机制合理性，不能替代本地PIT资格和后续OOS收益证据。

## 冻结选择合同

1. 输入候选窗口固定`56,272`行/`1,046` qid，不按已知失败产品、年份或结果删行。
2. 为每个产品和每个执行日建立唯一日级映射；`selection_date`必须精确等于执行日`previous_date`的前一全市场交易日。
3. 每个候选实际合约必须同时满足：
   - catalog产品身份一致；
   - selection date存在日bar；
   - selection-date `volume >= 100`且`open_interest >= 100`；
   - `expire_date >= return_date`。
4. 合格合约固定排序：selection-date `open_interest`降序、`volume`降序、`expire_date`升序、`vt_symbol`升序；rank 1为当日原始选择。
5. 产品级映射按执行日递增构造；一旦已选到某到期日，后续只允许选择相同或更晚到期日。若不存在合格的相同或更晚合约，映射明确缺失，不允许回滚近月。
6. query date之后产生的selection row可用于后续leg，但每条row只能使用对应执行日前一交易日信息；同日或未来selection均为硬失败。
7. 不使用vendor未来主力映射，不读取close，不根据previous/return端点质量重选。

## 冻结资格门

- 输入manifest、文件SHA、候选窗口身份与计数稳定。
- leg1有有效映射的候选构成研究宽度；`1,046/1,046` qid都必须保留，每qid至少`30`个候选。
- 每条保留路径必须精确产生20个leg；所有leg都有映射，到期覆盖return date，产品内到期月份不后退。
- 所有leg的previous/return bar唯一存在，且端点`volume > 0`、`open_interest > 0`。
- 每条路径的entry、roll_close、roll_open和exit执行事件均要求`volume >= 100`、`open_interest >= 100`；持有不变不产生交易事件。
- 所有selection date严格早于previous date且等于上一全市场交易日；same-day/future violation为0。
- `close`读取、收益计算、标签读取、fit、predict、回测、holdout、CTP、订单和生产写入全部为0。

## 决策语义

- 全部硬门通过：`stage001_lagged_liquidity_roll_pass_allow_label_value_preregistration_only`。
- 任一硬门失败：`stage001_lagged_liquidity_roll_fail_close_no_label_values`。
- 失败后禁止重跑、降100/100或30、改排序、允许向近月回滚、删品种/年份、缩20日持有期或按失败明细救援。

## 过拟合反思

- 运行前判断：否。
- 原因：选择机制在读取动态路径未来质量前冻结，参数来自既有一手1%容量合同和时间因果关系，不来自本次结果。

## 继续价值反思

- 运行前判断：有。
- 原因：这是对固定合约失败机制的最小结构性修正；若仍失败，将关闭该标签执行方向，而不是继续调阈值。
