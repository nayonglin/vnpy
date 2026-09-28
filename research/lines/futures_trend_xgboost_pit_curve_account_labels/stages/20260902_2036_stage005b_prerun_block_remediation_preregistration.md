# Stage005B 批量前BLOCK治理修复预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 记录时间：2026-09-02 20:36 CST
- 上游review：`reviews/20260902_stage005_prerun_rereview.md`
- 上游结论：`BLOCK_STAGE005_BATCH`，`P0/P1/P2/P3=0/2/1/0`
- 本阶段是否运行回测：否
- 本阶段是否创建run authorization：否
- 本阶段是否创建campaign：否

## 开始判断

- 是否过拟合：否。三个问题均为状态机、授权和金额表示治理，不涉及样本、品种、rank、策略或模型效果。
- 是否值得继续：是。P1会让失败attempt误判完成或让批量授权被重放，必须在任何270任务运行前关闭；P2会让标签派生字段口径不一致。

## 冻结修复

1. Attempt顺序：每个start receipt写入campaign内显式递增`attempt_sequence`；gate按sequence而不是attempt_id字符串判断最新状态。sequence缺失、非正、重复、active attempt不是最新或end合同不一致均fail closed。
2. 原子追加：attempt与授权消费回执使用文件创建模式`x`，并发重名或重复消费直接失败，不允许先检查再覆盖。
3. 单campaign授权：Stage005 run authorization必须精确声明`scope=one_new_stage005_campaign_only`和64位十六进制`campaign_nonce`。
4. 授权消费：`prepare_campaign`在创建campaign前原子写入唯一消费回执，绑定authorization SHA、nonce、scope和campaign_id；消费后不得创建第二个campaign。worker/resume必须验证消费回执与当前campaign一致。
5. 金额delta：`net_pnl_delta`与`slippage_delta`统一先把左右两个操作数各自按`0.000001`量化，再相减。

## TDD反例

- 同一秒中，旧attempt为较大PID且complete、新attempt为较小PID且failed；最终gate必须返回false并识别新failed为最后状态。
- authorization bindings全部正确但`scope=unlimited_campaigns`；必须拒绝。
- 同一个authorization nonce消费一次后，第二次消费必须原子失败；消费回执只允许绑定一个campaign。
- `0.0000006 - 0`的金额delta必须为`0.000001`，不得保留二进制浮点原值。

## 不变量与停止规则

- Stage005A v2输入、成功smoke、post-run review、266 main + 4 A2、35 development月和12 sealed holdout月合同不变。
- 不改策略、资金、成本、持仓或模型；不运行标签任务、训练、holdout、CTP或订单。
- 修复后fresh测试和py_compile通过，只能再次请求独立review；review未给`ALLOW_STAGE005_BATCH`前不得创建authorization。
