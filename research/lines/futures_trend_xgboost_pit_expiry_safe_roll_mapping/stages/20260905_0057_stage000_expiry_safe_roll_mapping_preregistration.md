# Stage000 PIT到期安全换月映射预注册

- 时间：2026-09-05 00:57 CST
- line_id：`futures_trend_xgboost_pit_expiry_safe_roll_mapping`
- 是否重要突破：否；这是V2失败后新立的结构数据资格线，不是模型或收益版本。
- 用户授权：后续研究操作默认授权；本线仍禁止生产、CTP和订单操作。

## 上游事实

- V2唯一执行固定为56,272条路径、1,046个qid、20段、1,125,440个leg；56,266条完整，6条`return_bar_missing`。
- 6条失败归并为2个事件：`wr2310.SHFE`到期日2023-10-16后在2023-10-17无bar；`RS511.CZCE`到期日2025-11-14后在2025-11-17无bar。
- V2冻结manifest SHA256：`f2a4cf72f0bddeb7fc103bc30714f6fc3380bc7f099bda2a16f57efb667797fd`。
- 冻结源已包含`asof_contract_catalog.csv.gz`的`product_vt_symbol/expire_date`，以及日线的`volume/open_interest`；不需要重连TqSdk或重建行情。

## 外部调研与判断

- TqSdk官方Quote字段把`expire_datetime`定义为合约到期具体日，主连实际交易需使用当时的`underlying_symbol`：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html>、<https://doc.shinnytech.com/tqsdk/latest/usage/backtest.html>。
- QuantConnect官方把`LastTradingDay`和`OpenInterest`列为不同映射模式，并允许按到期范围过滤Futures chain：<https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures>。
- LEAN官方GitHub示例在选择具体合约前设置expiry filter：<https://github.com/QuantConnect/Lean/blob/master/Algorithm.Python/BasicTemplateFuturesHistoryAlgorithm.py>。
- 判断：到期资格必须先于流动性排序；下一日bar只能验证结果，不能参与选择。仅用未来vendor mapping或下一日bar补洞会产生前视偏差，明确禁止。

## 冻结选择合同

1. 样本、窗口、global calendar和分区完全复用V2：56,272候选、1,046 qid、20个close-to-close身份段；cutoff 1,256行仍隔离。
2. 每段原始合约仍按V2选择：首段使用query date冻结`main_contract_vt`，后续段使用previous date的vendor主力映射。
3. 读取该合约catalog到期日；若`expire_date >= return_date`，原样保留，不允许为了流动性主动换约。
4. 仅当`expire_date < return_date`时触发到期fallback。候选必须同品种、在mapping date存在日bar、catalog到期日不早于return date。
5. fallback只用mapping date可见字段排序：`open_interest`降序、`volume`降序、`expire_date`升序、`contract_vt_symbol`升序；数值缺失或非有限的候选不得入选。
6. previous/return bar存在只在选约完成后做硬验收；不得据此回头改选。未来vendor mapping、未来bar存在、close/收益/标签均不得进入选择器。
7. 每段必须记录`selection_reason`、原始/最终合约、原始/最终到期日、mapping date、return date与fallback rank证据。

## 硬门

- 输入身份与manifest全部稳定；只允许读取catalog身份/到期字段和bars身份/volume/open_interest，close列读取数必须为0。
- 56,272路径、1,046 qid、1,125,440段不变；不得删除V2的6条失败行。
- 所有最终合约`expire_date >= return_date`，mapping date严格早于return date。
- 所有previous/return bar存在；路径失败0。
- `wr` canary必须从`wr2310.SHFE`换到存续合约，`RS` canary必须从`RS511.CZCE`换到存续合约；V2已通过的`sc` canary仍完整。
- 所有非到期触发段保持原始合约，禁止广泛重写vendor映射。
- close读取、收益计算、标签读取、fit、predict、回测、holdout、CTP、订单和生产写入全部为0。

## 决策语义

- 任一硬门失败：`stage001_expiry_safe_roll_mapping_fail_close_no_labels`，本线关闭且不救参。
- 全部通过：`stage001_expiry_safe_roll_mapping_pass_allow_roll_label_generator_preregistration_only`。
- 通过不授权读取close、生成标签、训练XGBoost、策略回测、A/B、shadow或上线。

## 过拟合反思

- 运行前判断：否。
- 原因：到期日门是交易可行性不变量，排序字段和tie-break在打开候选数据前冻结；没有效果反馈。

## 继续价值反思

- 运行前判断：有。
- 原因：若普适合同通过，可在不牺牲样本的情况下建立可执行标签路径；若失败，也能直接关闭该选约机制，避免把错误带入XGBoost。
