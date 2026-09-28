# Stage002独立复核

- 复核时间：2026-09-04 16:20 CST
- reviewer：独立只读sub-agent `01a06b78-11eb-7b33-9911-159fa4072b79`
- 范围：Stage002预注册、授权receipt、runner、测试、Stage001/Stage002冻结产物。
- 禁止事项：未修改文件，未重跑Stage002或pytest，未连接CTP/券商，未执行生产写入。
- 最终建议：`PASS`，认可`stage002_base_margin_residual_development_oos_fail_close_no_true_engine`。

## 发现

### P0

- 无发现。

### P1

- 无发现。

### P2：运行次数与副作用字段不是独立运行遥测

- `allowed_run_count=1`只被校验，authorization nonce没有耐久消费事件账本；final目录存在可阻止正常入口再次发布，但不能单凭产物证明此前没有失败、重试或直接函数调用。
- `logistic_fit_count=50`、`scaler_fit_count=50`和`xgboost_fit_count=100`由fold数推导；`true_engine_run_count`、`ctp_connection_count`、`order_api_call_count`和`production_write_count`在summary中直接赋值为0，并非拦截器或事件账本计数。
- 静态调用链未发现CTP、订单、true-engine或生产写入路径，因此该限制不影响数值fail-close，但这些字段不得表述为已由独立运行遥测证明的精确计数。
- 代码位置：`tools/stage002_base_margin_development_oos.py:471`、`:560`、`:834`、`:853`。

### P3：预注册测试区间文字错误

- 预注册第26行写`2022-03..2026-05`；冻结`fold_plan.csv`首折实际为`2022-04-29`，末折为`2026-05-29`。
- runner严格消费事前冻结的50折、900行，没有删月或泄漏；这是记录文字错误，不改变实验身份。保留预注册原文，不做事后修订。

## 独立核验

- LR `decision_function`同时用于训练和预测`base_margin`；XGBoost参数与预注册一致，每折重复fit两次。
- 独立复算`score_a == sigmoid(raw_margin)`和`score_b == sigmoid(raw_margin + correction)`，最大绝对误差均为`2.22e-16`。
- 50折、900行、每月18品种、固定`fu.SHFE`模型行0；用1,616个全局交易日重建label end，PIT违规0。
- 60日贡献、零起点最大回撤、Top10 membership、logloss、Rank IC、leave-best和年度聚合独立复算一致，最大路径误差`2.91e-11`。
- 19项授权绑定SHA全部匹配；Stage001和Stage002 manifest均无缺失、哈希错误或额外文件。
- 客观失败：仅`33/50`折有split、仅`5`个变更月/`2`年、leave-best return delta为`-46,670`、2025年度return delta为`-20,550`。

## 结论边界

- `PASS`只认可当前模型形状失败、不得进入true engine的结论。
- 不认可“精确只运行一次”或“所有副作用计数均有运行时遥测证明”的更强表述。
- 全部结果仍是高风险development OOS，sealed holdout为0；当前形状应冻结，不允许参数救援。
