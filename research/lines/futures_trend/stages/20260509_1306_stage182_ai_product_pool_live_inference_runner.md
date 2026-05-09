# Stage182 AI品种池月度Live Inference Runner

- 时间：2026-05-09 13:06 CST
- 研究线：`futures_trend`
- 工作模式：day
- 阶段：Stage182
- 主题：补第78正式基准的月度 AI 品种池 live inference runner

## 外部调研与判断

- 参考资料：
  - Walk-forward validation 的核心原则是按时间顺序训练与预测，训练只用过去、预测未来，避免 look-ahead bias。
  - 金融时间序列中，模型训练和特征工程都必须遵循时间可得性；仅 walk-forward 还不够，标签窗口也要防止重叠泄露。
- 我的判断：
  - 第78当前 AI 品种池是月度 `eval_date` 刷新，不是每日刷新。
  - Live inference runner 应只生成独立候选文件，不默认覆盖正式 Stage78 eligibility 文件。
  - 训练样本应限制在“未来60日标签已经在 live eval date 之前完整可知”的历史月份，避免把近端未知标签喂给模型。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py`
- 修改脚本：无
- 删除脚本：无

## 新增参数

- `--eval-date`
  - 手动指定 live AI 池评估日期。
  - 若不指定，默认使用源数据里最后一个已完成月份的最后交易日。
- `--allow-incomplete-month`
  - 允许在当前未完成月份最后可用日期上强制打分。
  - 默认关闭，避免月中噪音进入月度池。

## 修改参数

- 无。

## 删除参数

- 无。

## 模型与防泄露口径

- 源模型：`product_suitability_wf_v1`
- 模型类型：正则化 Logistic Regression
- 特征：过去 20/60/120 日产品级趋势系统表现、候选信号质量、滑点、回撤、成交活跃度等共 `108` 个特征。
- live eval date：`2026-03-31`
- 源数据最大日期：`2026-04-21`
- 训练标签 cutoff：`2025-12-25`
- 防泄露逻辑：
  - live eval date 只使用该日期可得的滚动特征。
  - 训练样本只取 `eval_date <= 2025-12-25`，给未来 60 日标签留足完整观察窗口。
  - live eval date 自身不进入训练集。

## 输出结果

- 本阶段不做策略组合回测，只生成 live AI 池候选文件。
- 期末权益：未新增回测；Stage78参考为 `4,600,090`
- 总收益：未新增回测；Stage78参考为 `2200.0450%`
- 最大回撤：未新增回测；Stage78参考为 `-36.9907%`
- Sharpe：未新增回测；Stage78参考为 `1.2919`
- 总滑点：未新增回测；Stage78参考为 `260,110`
- 总交易次数：未新增回测；Stage78参考为 `779`
- 胜率：未新增统计

## Live AI池

`2026-03-31` live Top8 + FU satellite：

| rank | product | score |
| --- | --- | --- |
| 1 | `SH.CZCE` | `0.811128` |
| 2 | `jm.DCE` | `0.723222` |
| 3 | `cu.SHFE` | `0.682411` |
| 4 | `FG.CZCE` | `0.671463` |
| 5 | `SA.CZCE` | `0.633695` |
| 6 | `sp.SHFE` | `0.630572` |
| 7 | `ru.SHFE` | `0.605964` |
| 8 | `lh.DCE` | `0.560294` |
| 9 | `fu.SHFE` | `0.560293` |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_report_stage182_ai_product_pool_live_inference_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_summary_stage182_ai_product_pool_live_inference_v1.json`
- latest_pool：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_latest_pool_stage182_ai_product_pool_live_inference_v1.csv`
- live_eligibility：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
- combined_eligibility：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`

## 结论

- 本阶段结论：
  - 月度 live inference runner 已可生成独立 AI 品种池。
  - 当前默认不会覆盖 Stage78 官方 eligibility 文件。
  - 当前数据链最大日期为 `2026-04-21`，所以默认只能稳健生成 `2026-03-31` 已完成月份池。
- 是否进入下一步：是
- 下一步：
  - 将 Stage172 前向影子日报增加可选 `ai_product_pool_eligibility_path` 覆盖参数。
  - 先用 `combined_eligibility` 跑一版影子日报对比，不直接替换正式基准。
  - 后续每月收盘后执行该 runner，并人工审查最新池变化。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：
  - 本阶段没有新增交易规则、没有调参、没有根据收益挑选新池。
  - runner 只是把既有月度 AI 选品方法转成 live inference 流程，并加入更保守的标签 cutoff。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：
  - Stage78 的官方 AI 池最新只到 `2026-02-27`，实盘前必须补齐月度前向生成流程。
  - 独立输出而不覆盖正式文件，可以让我们先审查池变化，再决定是否接入影子盘。
