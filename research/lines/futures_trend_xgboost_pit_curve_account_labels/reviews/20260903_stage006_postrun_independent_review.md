# Stage006 一次性冻结 development run 独立 post-run 评审

- 评审日期：2026-09-03（Asia/Shanghai）
- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 结果目录：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_xgboost_pit_curve_account_labels/artifacts/stage006_dual_ranker_development_oos/frozen_run`
- 评审性质：只读已发布结果、授权、消费回执和冻结身份审计
- 决策：`CONFIRM_STAGE006_FAIL_STOP_NO_TRUE_ENGINE_NO_HOLDOUT`
- allowed：`false`
- 严重度：`P0/P1/P2/P3 = 0/0/0/0`

## 结论

Stage006 一次性冻结 development OOS run 的技术、身份、授权消费、标签访问、scope 和 artifact bundle 完整可信；独立复算的九个效果门与 `effect_qualification.json` 一致，最终效果资格明确失败。发布 decision `stage006_dual_ranker_development_oos_fail_stop_no_true_engine_no_holdout` 正确。

这是一个有效且应保留的负结果，不是无效运行。必须按预注册 fail-stop：不允许 true-engine A/C、不允许 holdout、不允许第二次训练、调参、删月/删品种、改变 selector 或其他结果后救援，也不得宣称收益提升。

## Findings

### P0（0）

未发现 P0。

### P1（0）

未发现 P1。

### P2（0）

未发现 P2。

### P3（0）

未发现 P3。效果门失败是预注册规则下的研究结论，不是实现或产物缺陷，因此不计 severity finding。

## 1. Artifact manifest 与单次发布

- `artifact_manifest.json` SHA256：`3bbea68279d526b02cf3768088de91a7d39faeb18b0d0825dd77a7575527942d`。
- manifest 声明语义为覆盖结果目录内除 manifest 自身外的全部文件。
- 独立递归枚举得到非 manifest 文件 `64` 个；manifest 条目也是 `64` 个，路径集合精确相等，无缺失、无额外文件。
- 对 64 个条目逐一复算 size 和 SHA256，差异数为 `0`。
- Stage006 artifact 根目录只存在冻结 `training_contract.json`、`runtime_identity.json`、一份 `run_authorization.json`、一份 `authorization_consumption.json` 和一个 `frozen_run/`；没有第二结果目录、残留 partial/execution 目录或替代授权消费回执。
- 授权生成于 `02:18:00+08:00`，消费回执生成于 `02:19:35+08:00`，结果目录发布于 `02:19:36+08:00`，时序与先授权、后消费、再原子发布一致。

## 2. 授权与消费

- run authorization SHA256：`ba2622a276011b2e06615726e77155171ba6bc279a125a050a91df744df4f845`，与运行收据和消费回执记录精确一致。
- authorization、consumption、run receipt 的 nonce 都为同一唯一 64 位小写 hex：`a546439b79dcd5035c6c06fe70b32f5c9d90eb25d1a2c6847c9e29c2c0f858f0`。
- 三者 scope 精确为 `one_frozen_stage006_development_run_only_no_holdout_no_production_no_ctp_no_orders`。
- `authorization_consumption.json` SHA256：`bdc485bdb66ddda8c67ec20c9516c400ffcda911d6b4346443cb89def47b3fb6`；其 JSON 与 `run_receipt.authorization_consumption` 逐字段相等。
- artifact 根目录匹配 `authorization_consumption*.json` 的文件数精确为 `1`，scope audit 的入口调用数也精确为 `1`。
- runner/tests SHA256 仍为 `3dd5bd70875994924c291741e144244a021c8465b67504a2a414a691c824eaac` / `fd5ca6151525b42248fa154de247a1702417cbb13ddf89cd05b3fe1c3399d031`，与授权绑定身份一致。

## 3. 折、预测、模型与 seal

- `fold_audit.csv` 为 `17` 行、17 个唯一测试月；训练月数精确为 `18..34`；测试行合计 `151`；PIT violation 全为 `0`。
- `ordered_oos_predictions.csv` 为 `151` 行、17 个唯一月份；`monthly_arm_selections.csv` 为 `17` 行、17 个唯一月份。
- primary 模型文件精确 `34` 个，`model_manifest.json` 的 primary count/key/size/SHA 与实际文件逐项一致。
- repeat model hash 精确 `34` 个，key 与 primary 完全相同；每个 repeat SHA 与对应 primary UBJ SHA 相等。
- 总 fit count=`68`，由 `34 primary + 34 repeat` 构成；无 extra fit。
- 两头逐折 repeat prediction 最大绝对差均为 `0.0`；两头每折 primary/repeat 模型 SHA 均一致；技术门中的 `prediction_determinism`、`model_byte_determinism`、`test_scores_nonconstant` 全为 true。
- pre-effect seal 精确 `17` 个。逐 seal 复核 exact keys、test date、seal 前标签读取 `0`、主模型 SHA、repeat SHA、分月原始 prediction CSV bytes SHA、pre-effect selection canonical JSON SHA，差异数均为 `0`；`fold_audit` 记录的 seal SHA 也全部匹配实际文件。
- `frozen_estimator_and_params_exact=true`。结合绑定 runner 的生产路径固定传入 `XGBRanker`、训练结果 estimator audit 和冻结参数精确门，可确认本次实际 estimator/params 技术门通过。

## 4. 三点 runtime/input/auth identity

- `runtime_identity_audit.json`：`checkpoint_count=3`，检查点为训练前、全部模型后、效果评价后；`passed=true`、`all_runtime_identities_exact=true`。
- 三点均为 Darwin/arm64、CPython 3.11.15、XGBoost 3.2.0；Python executable、`xgboost/__init__.py`、`libxgboost.dylib` 的路径/大小/SHA 保持一致。
- `input_identity_audit.json`：`checkpoint_count=3`、`passed=true`、`all_checkpoint_identities_exact=true`；三个 checkpoint 的 identity digest 唯一值为 `512de8ee3e9fab0cf80a2471e46a099470014a4abfb26c59be6004d35c8e0403`。
- 三次身份均绑定同一 authorization SHA、nonce、scope 和六个 bound file identities；未发现训练前后输入或代码身份漂移。

## 5. 标签访问审计

`label_access_audit.json` 与 `technical_qualification.json.label_access_audit` 精确一致：

- 初始成熟标签打开：`115`
- 测试标签在自身 seal 前打开：`0`
- 测试标签在自身 seal 后打开及用于效果：`151/151`
- 聚合 development/reconciliation CSV 数据行解析：`0/0`
- 同折或更早折训练、预处理、调参、candidate selection、tie-break 使用测试标签：全部 `0`
- holdout feature prediction、label read、generate、training、effect：全部 `0`

本 post-run 评审只读取冻结结果 bundle 中已发布的审计和效果 CSV，没有读取任何真实 per-job `label.json` 或 aggregate label 数据行。

## 6. Execution scope

`execution_scope_audit.json` 的 counts 与 expected 逐键精确相等，`passed=true`：

- authorized entrypoint=`1`
- primary/repeat/total fits=`34/34/68`
- parameter searches=`0`
- early stopping runs=`0`
- extra fits=`0`
- holdout predictions=`0`
- holdout label reads or generations=`0`
- production writes=`0`
- CTP connections=`0`
- order API calls=`0`
- unexpected artifacts/commands=`0/0`

## 7. 九个效果门独立复算

从 `monthly_arm_selections.csv` 独立读取 17 月 Arm C replacement 与 realized delta，按冻结 contract 重新计算，未调用 runner 的 effect evaluator：

- replacement months：`8`
- replacement years：`[2023, 2024]`
- total return delta：`-0.10596712219705573`
- total drawdown improvement：`-0.029383673739694305`
- leave-best-out return delta：`-0.13913129819254122`
- leave-best-out drawdown improvement：`-0.06689690950170868`
- 2023 return/drawdown：`-0.02589369581866796 / -0.008643798131113711`
- 2024 return/drawdown：`-0.08007342637838777 / -0.020739875608580594`
- replacement joint-positive rate：`0.125`

九门结果：

- `minimum_replacement_months=true`
- `required_replacement_years=true`
- `total_return_delta_positive=false`
- `total_drawdown_improvement_positive=false`
- `leave_best_out_return_delta_positive=false`
- `leave_best_out_drawdown_improvement_positive=false`
- `each_year_return_delta_nonnegative=false`
- `each_year_drawdown_improvement_nonnegative=false`
- `active_joint_positive_rate=false`

独立复算与 `effect_qualification.json` 的布尔门完全相等，连续指标差异均小于 `1e-15`。因此效果门为 `2 true + 7 false`，`effect_pass=false` 没有歧义。

## 8. 最终 decision 与 fail-stop

- 结果 `decision.json` SHA256：`b2deae261f47c9b5b0cb656be305b83cdf475ba926efa86185dec2803ec1971d`。
- `technical_pass=true`、`effect_pass=false`。
- decision 精确为 `stage006_dual_ranker_development_oos_fail_stop_no_true_engine_no_holdout`。
- decision 中 holdout predictions、holdout labels read、production writes、CTP connections、order API calls 均为 `0`。
- 按预注册，效果任一必要门失败就必须停止；当前七门失败，不能进入 true-engine 或 holdout，不能通过二次训练或结果后改规则救援。

## 过拟合与继续价值

- 过拟合判断：本次 post-run 审计本身不是过拟合，只复算冻结结果，没有训练、调参、筛选子样本或改变门槛。若依据这次负结果再调参、删月份/品种、改 A/B/C 或重跑，将构成明显的 development 结果后适配风险。
- 继续价值判断：不应继续这条冻结 Stage006 模型进入 true-engine 或 holdout；有价值的后续仅是封存该负结果，作为双 ranker 结构未通过 development OOS 的可复验反例。任何新结构必须另立研究问题、冻结新预注册并重新独立预审，不能复用本授权或将本次失败包装成收益改进。

## 决策边界

运行结果技术完整且效果失败，decision 为 `CONFIRM_STAGE006_FAIL_STOP_NO_TRUE_ENGINE_NO_HOLDOUT`，`allowed=false`。不创建任何新 authorization；不授权二次 Stage006 run、调参/补救运行、true-engine、holdout、模型晋级、收益提升声明、生产写、CTP、实盘或订单。
