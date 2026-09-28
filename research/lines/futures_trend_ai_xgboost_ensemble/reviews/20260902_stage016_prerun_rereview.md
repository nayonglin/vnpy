# Stage016 最终运行前独立复审

## 结论先行

- 审查结论：`ALLOW_FROZEN_STAGE016_RUN`
- 严重度：`P0=0 / P1=0 / P2=0`
- 本授权仅允许一次冻结的 Stage016 development 运行，不授权读取 holdout、修改生产、连接 CTP 或调用订单API。
- 未运行真实入口、未读取 `development_labels.csv` 数据行、未生成运行产物、未修改文件。

## P0

无。

## P1

无。原三项P1均已关闭。

## P2

无。原两项P2均已关闭。

## 闭环复核

| 原问题 | 最终状态 | 证据 |
| --- | --- | --- |
| 技术失败仍评价或披露效果 | 已关闭 | `resolve_stage016_outcome` 在技术失败时直接返回；发布分支不包含预测、月选、模型或效果值 |
| 非有限值绕过 | 已关闭 | reconciliation、全部相对标签、selector预测、XGBoost原始预测及效果值均显式 `np.isfinite` fail-closed |
| review/runner/tests/合同身份未稳定绑定 | 已关闭 | 授权清单绑定五类文件；标签读取前、效果评价前、效果评价后共三次验证 |
| 输入或合同在效果评价期间漂移 | 已关闭 | 输入身份和冻结合同在训练后、效果评价后重新验证 |
| manifest/fsync/rename故障状态不明确 | 已关闭 | 文件及目录fsync、同目录rename、rename前清理、rename后异常隐藏quarantine均已实现并有故障注入 |
| 缺少holdout注入负测 | 已关闭 | 显式holdout标签注入测试确认 fail-closed |

关键实现位置：[runner:682](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/tools/stage016_frozen_dual_regressor_training.py:682)、[runner:1240](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/tools/stage016_frozen_dual_regressor_training.py:1240)、[runner:1282](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/tools/stage016_frozen_dual_regressor_training.py:1282)、[runner:1300](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/tools/stage016_frozen_dual_regressor_training.py:1300)、[runner:1034](/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/tools/stage016_frozen_dual_regressor_training.py:1034)。

## 文件身份

- runner SHA256：`b78bd1cb5e7b49ce49bff683a38f4d34656a6d88ac147fdd25bf285b38543847`
- tests SHA256：`1978d906b45ed9cf63666bfcba769daa7c7980a0dca77a16086df68e7d5cb00b`
- contract SHA256：`beac6e6a4947043e1250c989e91d196c3edd4446cc6db043b67f91db92d90e6e`
- preregistration SHA256：`ab56e31be4a49e45bea778ccbafb58bed5d2cd580480adff08f43b3edf47a8d8`

## 验证记录

- Stage016专项合成测试：`25 passed in 2.34s`
- 整条研究线合成测试：`123 passed in 15.08s`
- 静态检查：`python_ast=2 / json=1`，通过
- 静态调用顺序确认：授权检查 → 标签读取 → 授权复验 → 效果评价 → 第三次授权/输入/合同复验 → 发布
- `frozen_run`、partial及quarantine运行产物：均不存在

## 授权清单要求

本正文必须原样保存到：

`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_xgboost_ensemble/reviews/20260902_stage016_prerun_rereview.md`

保存后计算该 review 的 SHA256。随后生成的 `run_authorization.json` 必须满足：

- `decision` 精确为 `ALLOW_FROZEN_STAGE016_RUN`
- `review` 绑定上述固定路径及保存后的实际SHA
- `runner`、`tests`、`contract`、`preregistration` 分别绑定本复审列出的路径和SHA
- 授权文件自身SHA必须通过 `STAGE016_RUN_AUTHORIZATION_SHA256` 传入
- 任一文件路径、SHA或授权文件SHA变化，本授权立即失效，必须重新独立复审

## 最终判断

当前实现满足冻结预注册、PIT、holdout隔离、选择器、效果门、身份稳定和原子发布要求，允许执行一次 `ALLOW_FROZEN_STAGE016_RUN`。

过拟合风险仍然高，因为只有15个development OOS月；但此次运行规则和门槛已在标签前冻结。运行结果无论通过或失败均禁止调参救援，且通过也只授权后续development真实引擎A/C，不代表可读取holdout或上线。
