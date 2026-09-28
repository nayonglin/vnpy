# Stage001到期安全换月映射资格通过

- 时间：2026-09-05 01:14 CST
- line_id：`futures_trend_xgboost_pit_expiry_safe_roll_mapping`
- 是否重要突破：是，数据语义层重要突破；首次在不删样本、不读close的前提下让全量产品级20段路径完整，但尚不是收益或模型突破。
- 决策：`stage001_expiry_safe_roll_mapping_pass_allow_roll_label_generator_preregistration_only`。
- 授权：`20260905_stage001_execution_authorization.json`，nonce `be372d50-9d95-4531-ad5f-7a5f8943b821`已消费；唯一`--run`退出码0，不重跑。

## 调研与判断

- TqSdk官方提供合约到期日和主连映射身份；QuantConnect/LEAN把到期过滤与主力映射作为不同约束，支持先做生命周期资格再选具体合约。
- 本线冻结规则只在原合约`expire_date < return_date`时触发，使用mapping date持仓量、成交量、到期日、代码排序；return date bar只做事后硬验收，不参与选约。
- 判断：该规则解决了V2的结构到期断点，证明产品级换月标签路径可构造；但`RS607`选择日成交量为0，说明“到期安全”不等于“可成交安全”，暂不直接进入标签值生成。

## 唯一执行结果

- 全部13道门禁通过；输入前后SHA与mtime稳定。
- 路径：56,272行、1,046个qid，全部有效；分段1,125,440行，失败0。
- 到期fallback：6个leg、2个独立事件；非到期leg全部保持原始vendor合约。
- fallback候选数最小/中位/最大：`3 / 3 / 11`。
- 最终换月事件29,360次，较V2的29,361次少1次：`wr`首段提前选入后续合约，使相邻段不再重复计为换月。
- `sc`稳定canary通过；`wr`和`RS`到期canary均通过。

## Fallback明细

1. `wr2310.SHFE -> wr2401.SHFE`：mapping date 2023-10-13，return date 2023-10-17；新合约到期2024-01-15，持仓73、成交65，前后bar均存在。
2. `RS511.CZCE -> RS607.CZCE`：5条路径共享mapping date 2025-11-14与return date 2025-11-17；新合约到期2026-07-14，持仓6、成交0，前后bar均存在。
- 同日其他RS存续候选：`RS609`持仓2/成交0，`RS608`持仓1/成交1。当前冻结排序正确选择持仓更高的`RS607`，但零成交暴露可执行性风险。

## 产物与验证

- manifest SHA256：`9f768fc6de7ccd3eb240c29f0444249bd333356d756b137197dc78e4f5f44d76`。
- summary SHA256：`6f994dd88896781a7f1af9e9760890540445dc8539a6349ae416b82bcf37283f`。
- fallback SHA256：`e94a2647392dafe4fa611a8373dcfb141f32cb87fbf7af443a1b7d9d340c08a0`。
- legs SHA256：`db2fcffc24053cbb5c540a699bc47f19149d54eeb66aa2b57057707f346a92da`。
- `--verify-only`：8个artifact、7个输入，`errors=[]`、`verified=true`。
- 跨线回归：`82 passed`；本线runner/core/tests均`py_compile`通过。
- 唯一执行有一条pandas mixed-type DtypeWarning，来源是V2 `failure_reason`空值与字符串混合；字段解析和全部门禁均正确，冻结代码不因警告重跑。

## 研究边界与指标

- bars只打开身份、interval、volume、open_interest；catalog只打开合约、品种、expire_date。
- close读取0、收益计算0、标签读取0、fit 0、predict 0、策略回测0、sealed holdout 0。
- CTP连接0、订单API 0、生产写入0；正式逻辑回归和线上版本未改。
- 本阶段没有回测，因此期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率均未产生。
- 无回测结果，按规则不需要独立回测reviewer。

## 过拟合反思

- 运行后判断：否。
- 原因：规则和tie-break在查看候选流动性前冻结；结果后没有改为选择`RS608`、删除RS样本或降低门槛，零成交风险被原样保留。

## 继续价值反思

- 运行后判断：本线目标已完成并封存；整体方向仍有价值，但需先补独立成交安全资格。
- 原因：完整路径是生成产品标签的必要条件，不是充分条件。零成交fallback若直接读取close，会把不可执行或陈旧报价写入标签，污染XGBoost训练目标。

## 后续

- 本线不重跑、不修改已冻结排序。
- 另立PIT成交安全资格线，优先复用既有正式容量原则；在没有事前统一规则前，不授权roll-aware close标签生成。
