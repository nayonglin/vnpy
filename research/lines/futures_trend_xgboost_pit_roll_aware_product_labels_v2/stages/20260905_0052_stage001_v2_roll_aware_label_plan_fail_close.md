# Stage001 V2换月感知产品标签路径失败闭线

- 时间：2026-09-05 00:52 CST
- line_id：`futures_trend_xgboost_pit_roll_aware_product_labels_v2`
- 是否重要突破：否；manifest技术阻塞已修复，但完整路径硬门被2个独立到期边界事件证伪。
- 决策：`stage001_v2_roll_aware_label_plan_fail_close_no_labels`。
- 授权：`20260905_stage001_v2_execution_authorization.json`，nonce `80d49c0e-a7c0-4c07-8c9e-b3e9d3d21b7f`已消费；唯一`--run`退出码2，不重跑。

## 调研与判断

- TqSdk官方Quote字段把`expire_datetime`定义为合约到期具体日，当前冻结`asof_contract_catalog.csv.gz`已保留该字段归一化后的`expire_date`：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html>。
- QuantConnect官方资料把最后交易日和持仓量变化列为两种不同的连续合约映射模式，并允许按到期区间过滤合约：<https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures>。
- GitHub上的LEAN官方示例同样先按到期区间过滤Futures chain，再选择可交易合约：<https://github.com/QuantConnect/Lean/blob/master/Algorithm.Python/BasicTemplateFuturesHistoryAlgorithm.py>。
- 我的判断：失败不是行情漏档，也不是XGBoost问题，而是“仅按T-1主力映射”没有加入下一段最后交易日资格。不能事后删除6行或降低全量完整门，后续若继续必须另立线并使用事前已知的生命周期元数据。

## 唯一执行结果

- source path manifest：13个artifact全部通过；V1 bundle：10个artifact、9个输入全部通过。
- 基础/候选/cutoff：`57,528 / 56,272 / 1,256`行；候选`1,046`个qid，与预注册完全一致。
- 路径：56,272行，其中56,266行有效、6行无效；分段1,125,440行；换月事件29,361次。
- 通过门：upstream manifest、输入身份、分区、路径身份、`sc` canary、零副作用。
- 失败门：完整路径、PIT映射、bar存在；统一失败原因为`return_bar_missing=6`。
- `sc.INE` canary通过：2024-01-31的首合约`sc2403.INE`，路径跨月并完整到2024-03-08。

## 两个独立失败事件

1. `wr.SHFE`：2023-10-13信号的首段仍选`wr2310.SHFE`；catalog到期日为2023-10-16，2023-10-17无bar，而主力映射在2023-10-16已经切到`wr2401.SHFE`。
2. `RS.CZCE`：5条路径在2025-11-14仍按映射选`RS511.CZCE`；catalog到期日正是2025-11-14，2025-11-17无bar，主力映射到2025-11-17才切为`RS607.CZCE`。

## 产物与验证

- manifest SHA256：`f2a4cf72f0bddeb7fc103bc30714f6fc3380bc7f099bda2a16f57efb667797fd`。
- summary SHA256：`ab605d61fe2a26314fa8e351d00e829929392052f6b4b10055eb509954a6ea57`。
- failures SHA256：`32fe160cb4693af6766b626087980aacc2a5644cf9a36f1eedd9114e325dbd05`。
- `--verify-only`：9个artifact、7个输入，`errors=[]`、`verified=true`。
- 回归：相关测试`74 passed`；V2 runner、测试、冻结原runner和core均`py_compile`通过。

## 研究边界与指标

- close值读取0、收益计算0、标签读取0、fit 0、predict 0、策略回测0、sealed holdout 0。
- CTP连接0、订单API 0、生产写入0；正式逻辑回归与线上版本未改。
- 本阶段没有回测，因此期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率均未产生，不得沿用历史数值。
- 无回测结果，按规则不需要独立回测reviewer。

## 过拟合反思

- 运行后判断：否。
- 原因：合同、样本、20日窗口、canary与全量硬门均在执行前冻结；失败后没有删6行、缩窗口或按结果改门。

## 继续价值反思

- 运行后判断：有，但本V2线无继续价值并立即关闭。
- 原因：`expire_date`已在冻结源中，两个失败事件均由“所选合约到期日早于return date”完整解释；可另立数据资格线做普适生命周期门，不应在本线救参。

## 后续

- 本线禁止重跑、补洞、删除失败样本或生成标签。
- 若继续，另立到期感知映射资格线：默认保留当前映射，仅当映射合约不能覆盖下一return date时，使用映射日可见流动性和事前已知到期日选择下一合格合约；先做身份/流动性资格审计，不读close、不算标签。
