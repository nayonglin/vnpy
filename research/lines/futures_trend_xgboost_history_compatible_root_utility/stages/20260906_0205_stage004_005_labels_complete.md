# Stage004-005全量标签合格

- line_id：`futures_trend_xgboost_history_compatible_root_utility`。
- 时间：2026-09-05 23:06 CST启动第五批，2026-09-06 02:03退出；02:04全量汇总完成，02:05记录。是否重要突破：否，数据资格不是模型收益证据。
- 延续既有固定计划，本批真实单根S回放117次、全部通过，累计274/274；失败0，无未完成任务。2个期末删失标签保持空白。不修改或删除旧回放结果。
- 批次：`artifacts/stage004_label_batch/batches/0005/summary.json`。Stage004实现、1511项输入合同、274项计划、模型经济参数均未修改；最多3个私有沙箱worker。
- 完整快照：`artifacts/stage005_label_collection/20260906_020434_393264/summary.json`；SHA256 `c5a166ee35972197d411de197d64408fb605889ab630f94549bda71d16f10435`。
- 276行事件表：同目录`events.csv`，SHA256 `81d13eae9251e2ce502ab6f18f1c20f4f8a1774e002ec7e68cb52013e5f57bf5`。274 verified、0 pending、2 censored；`training_ready=true`。
- 压缩解码差异0、双目标重算差异0；首笔零成交分析表示重新核算1次且一致。保留原失败和恢复轨迹，没有重新跑首笔策略。
- 全部274组A/S的权益、总收益、最大回撤、Sharpe、滑点、手续费、成交记录数及非零日胜率在同目录`counterfactual_metrics.csv`，SHA256 `4135d332164e0392b12b0d388ec66dd20ded6de94b018ea8393858a4483c8851`。各S终点不同，禁止拼接或相加为模型收益。
- 冻结完整A仅作口径参照，本轮未重跑：本金150,000；2020-01-02至2026-08-28；期末权益12,226,270.60、总收益8050.8471%、最大回撤-45.9216%、Sharpe1.683943、总滑点1,100,560、手续费0、成交记录655、非零损益日胜率54.2419%。不是实盘收益；手续费0为继承的研究假设，非现实全成本。
- 参数新增/修改/删除均无。历史模型拟合0、完整模型C回放0、reviewer0；原标签批次与汇总均exit0。

## 接下来执行

1. 使用本次唯一完整快照运行Stage006既定月度训练，80月、10连续特征、双头浅树、至少60成熟事件、训练折目标变换和双负才跳过规则不变。
2. 全部模型产物成功后才冻结并运行Stage009完整C。C必须使用自身当前账户状态，不能使用A事件ID或A账户特征控制动作。
3. 仅全路径C双目标改善且通过事前基本稳健性门才启动reviewer；失败版本不启动，不按历史结果救参数。

## 调研与反思

- 本轮复核[XGBoost官方模型IO](https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html)、[v3.2.0官方GitHub推理实现](https://github.com/dmlc/xgboost/blob/v3.2.0/python-package/xgboost/sklearn.py)与[sklearn目标变换](https://scikit-learn.org/stable/modules/generated/sklearn.compose.TransformedTargetRegressor.html)。判断：原生模型保存和训练折内变换有助于复现、防止变换泄漏，但不能证明模型盈利；冻结本地3.2.0，不升级依赖。
- 开始及本数据节点是否按结果过拟合：否，固定任务顺序、样本、参数与判据均未改变；整体历史研究选择偏差仍然存在，不能称未见样本验证。
- 开始及本节点是否值得继续：是，274标签已齐全，应直接进入训练和完整C，不继续扩展机械资格工作。
- 研究隔离不变：不接CTP、不改正式环境、不修改其他研究线/registry/根总账，不提交或部署。总目标仍未达到。
