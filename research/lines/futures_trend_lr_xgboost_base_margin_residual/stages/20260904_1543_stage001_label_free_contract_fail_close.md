# Stage001 m0005无标签合同失败关闭

- line_id：`futures_trend_lr_xgboost_base_margin_residual`
- 记录时间：2026-09-04 15:43 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：唯一冻结无标签正式身份、因果特征逐值和PIT折叠资格审计。
- 是否重要突破：否；形成了可信的前置失败和正式选品边界纠正，没有模型或收益证据。
- 是否触发独立reviewer：否；没有产生回测数据。
- 用户授权：用户要求继续XGBoost研究，并已授权数据源重建；本阶段严格限制为无标签审计。

## 调研与判断

- XGBoost官方文档确认`base_margin`可承接已有模型raw margin，logistic任务必须使用log-odds而不是概率：<https://xgboost.readthedocs.io/en/stable/tutorials/intercept.html>。
- XGBoost预测文档确认训练和预测均可传`base_margin`：<https://xgboost.readthedocs.io/en/stable/prediction.html>。
- 本地全仓没有机器学习意义的`base_margin`实现，残差结构具备独立性；但独立结构不等于可以跳过正式身份门。
- 本阶段判断：先验证m0005的真实模型边界、108项因果特征和60交易日PIT切分是必要的；失败后不得读取标签或fit。

## 版本变更

- 新增时间：2026-09-04 15:32至15:43 CST。
- 新增代码：`tools/causal_formal_features.py`、`tools/stage001_label_free_contract.py`。
- 新增测试：因果未来隔离、108项特征、60交易日label-end、整月PIT purge、禁止列、硬门、输出边界、原子发布和manifest复核，共20项。
- 新增参数：滚动窗`20/60/120`日；label horizon=`60`交易日；最少训练月=`24`；历史/最新逐值容差=`1e-10`；active folds最少`48`。
- 修改参数：无。
- 删除参数：无。
- 首次启动异常：冻结release导入`qmt_universe`时触发`.vntrader`回测守卫；异常发生在CSV解析、标签、模型和输出之前。
- 启动修复：只在冻结模块导入上下文内设置文档化的`QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1`，正常和异常路径均恢复原环境；新增2项测试后20项全通过。该作用域只允许读取CSV聚合，不连接数据库或运行回测。
- 实现SHA256：`causal_formal_features.py=930c81fca2de049983c75c7470873e781b086a208993f9817fb04fd3649ef15f`；`stage001_label_free_contract.py=6f315ecb5ca63f0fbf83495119226c65da397c2a5dbbf7ef8cefa80a9c34c2bd`。

## 冻结输入

- 当前指针SHA256：`f17c0f6bfeea4a08ec7c22a1eb63d4b51e4cfb2472f1ce07fac8ce2cc570b219`。
- m0005 manifest SHA256：`d62e58d01284e30b28054387592604862ffeff6e55a13c63192793e95bc55c21`。
- m0004/m0005正式LR源码SHA256：`7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4`，逐字节相同。
- m0004/m0005月更runner SHA256：`ca15504e946e39fe6c5b0180e5bdf07bf38749973ceedd2085ba77480e3c9edc`，逐字节相同。
- Stage182 summary SHA256：`e119fcdaddb16d173bf8737edd39e3241dc2b277ea96f908d6eeb71bf9bdd5c3`。
- 最新池SHA256：`9c28774c5f7d02de837a30408c93cd5ba9aa925e03280b1d9b294fbaaf70a814`。
- Stage183 position changes / entry snapshots SHA256：`17c81f2dbb30f836b544161c3fc4d4bd6415151d89b8f8937378739e868c21aa` / `f838186527b1453923635bda31ec8e1656a0bdacfec633a6b85f2cda8e3b26a0`。
- 旧正式特征面板SHA256：`92f36b6647cae9d8db04b0a1351749f9103a1988799dbb8dff0ad1d350d1d431`。
- 全部输入运行前后身份一致，mismatch=`0`。

## 审计结果

### 通过项

- 当前release/策略：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`，指针一致。
- 源日期：`2020-01-02..2026-09-01`。
- 训练截止：`2026-06-05`；训练面板`77`个月、`1,386`行、每月精确`18`品种、`108`项特征，非有限单元`0`。
- 旧正式面板：`76`个月、`1,368`行；108项最大绝对误差`1.4551915228366852e-11`，通过`1e-10`门。
- label-end计划：`77`行，缺失`0`；只使用全局交易日位置，不读取标签值。
- 严格PIT：active/effect-evaluable folds=`50/50`，训练月数`24..74`，泄漏行/折=`0/0`。
- manifest只读复核：`valid=true`、errors=`0`。

### 唯一失败项

- 冻结门要求m0005最新正式池`11`行全部与108项模型特征逐值对齐。
- 实际最新池有`10`行`selection_role=model_ranked`，均有`model_ai_rank`和108项特征；第11行`fu.SHFE`为`selection_role=fixed_fu`，`model_ai_rank`与108项模型特征均为空。
- 原因：正式系统是“LR从18品种排序选Top10，再独立追加固定fu卫星”，不是“LR对Top10+fu共11行打分”。Stage000把发布池行数误当模型打分行数。
- 冻结输出将身份不等记为`latest_pool_parity_max_abs_error=Infinity`；最终失败门仅`latest_pool_feature_parity`。

## 决策

- `stage001_m0005_causal_feature_or_pit_contract_fail_close_no_labels`。
- 本线关闭；Stage002/Stage003禁止实现或执行。
- 禁止在本线把最新池门从11行改成10行、排除`fu.SHFE`后重跑，或改容差、月份、品种、窗口和折数救援。
- 如果继续`base_margin`方向，必须另立研究线，从“18品种LR排序 + 固定fu卫星不参与模型”重新预注册输入和发布边界；不得复用本次final作为通过证据。

## 回测结果

- 新增回测结果：无。
- 修改回测结果：无。
- 删除回测结果：无。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 安全计数

- 禁止列读取：`0`。
- 未来标签值读取：`0`。
- 模型fit/predict：`0/0`。
- 策略回测：`0`。
- CTP连接：`0`。
- 订单API：`0`。
- 生产写入：`0`。
- 正式A、release和当前池：未改。

## 产物

- `artifacts/stage001_label_free_contract/summary.json`。
- `artifacts/stage001_label_free_contract/feature_contract.json`。
- `artifacts/stage001_label_free_contract/fold_plan.csv`。
- `artifacts/stage001_label_free_contract/input_identities.json`。
- `artifacts/stage001_label_free_contract/report.md`。
- `artifacts/stage001_label_free_contract/artifact_manifest.json`；manifest内5个payload文件SHA均复核通过。

## 过拟合反思

- 运行后判断：Stage001没有效果过拟合；在本线继续则会形成合同救援。
- 原因：没有查看标签或效果；但已经知道唯一失败来自固定fu，事后修改行数门并重跑会利用失败位置，破坏唯一冻结审计。

## 继续价值反思

- 当前研究线：没有，关闭。
- XGBoost总方向：仍有条件价值，因为LR `base_margin`残差尚未fit；但下一条线必须先正确建模正式Top10与固定fu的所有权边界，不能把本次失败改写为通过。

## 后续规划

- 不追加根目录`memory.md`或`back_log.md`，因为没有回测或正式候选。
- 不触发独立reviewer，因为没有回测数据。
- 若开启后续线，Stage000必须把模型评分面板固定为18品种、最新feature parity固定为10个`model_ranked`发布行，并把固定`fu.SHFE`列为发布层非模型卫星；仍须先做新的无标签合同，不得直接读标签。
