# Stage470：固定年度成熟更新的 fit/selection 实现与最小检查

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-20 23:25 CST。
- 工作区 `/Users/mac/Desktop/fian`；沿用 `codex/ai-training-data-expansion`，无新 worktree/branch/commit/push。
- 阶段性质：469冻结协议的实现准备，非重要突破。独立研究对照，未接正式C9；未启动实际训练/现金。

## 调研与判断

实施前重新读取本线registry/LINE顶部、469协议与中文stage，协议SHA为 `f62281e099200e065785b61cc89a47a2111fe7d3dbf2ec60102b167b0708d4f6`。同步复核 [Qlib任务生成器](https://github.com/microsoft/qlib/blob/main/qlib/workflow/task/gen.py) 与 [sklearn时间分割](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)。只采用时间扩窗与防泄漏的结构约束；变长退出标签仍以原130的 `u_date<Jan1` 且 `label_known_date<Jan1` 为严格门，不照搬固定行gap，不增加调参维度。

我的判断：本次有可检验的单一差异，即原目标经验进入估计的年度时钟；若改变特征、标签、频率或筛选规则，就无法把结果归因于该时钟。故直接调用原130的成熟门、family哈希、union/day权重、52列design与finite_stats；直接调用原156的完整共同K、正分、month/action和ordinary/F家族优先级选择。

## 本次变更与边界

- 新增 `tools/stage470_annual_mature_fit_select.py` 和唯一 `tools/test_stage470_annual_mature_fit_select.py`；未修改旧文件、LINE、registry、正式/CTP/邮件/调度或原四前瞻账。
- 固定七年度×main/holdout_0/holdout_1；2020/2023六个模型及当年分数直接复用；2021/22/24/25/26最多15新fit。Ridge(alpha=1, fit_intercept=True, solver=cholesky)、原COMMON52、原129 first-exit stress Y不变。没有373 October20模型回填。
- 新增参数只含已冻结的annual Jan1时钟；修改只含部署打分更新时钟；删除参数0。每新年度数值权重/scaler按该年度成熟集重算，规则未改。
- 原129动作以原130字段、156字段和现金16字段并集进行唯一usecols流；数据进入完整训练投影后，held诊断与selected_actions均使用同一内存。COMMON原NPZ单次读入字节同时保存本次复现copy并解包一次。旧130 child_scores唯一流只保留年度2020/2023分数。原母表完整399252×七identity投影保留，原1552456动作、98产品/95family不缩母体。
- 每个新fit保存训练身份/精确权重、union组、scaler、portable/joblib、正规方程、预测checkpoint及completed.json；完整fit和selection分别保存checkpoint，禁止为报告重训。
- `cutoff` 和新增 `deployment_fold_cutoff` 继续为2020/2023；`training_cutoff` 单独写年度Jan1。跨年全部信号先拼接交现金端，不能据年度切账/清仓/重置资本。
- 与471现金作者确认 `cash_handoff.json` 使用 `protocol_binding`、`fit_manifest_binding`、`main_choices_binding`、`held_diagnostic_binding`、`full_mothers_projection_binding`、`selected_actions_binding`、`calendar_binding`、`boundaries_binding`，均为path/bytes/SHA；母投影七identity完整，selected动作16字段ID齐全。先最终manifest，后handoff绑定它，避免SHA环；现金只读本次派生输入。

## 最小 fixture 终态

唯一命令：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/test_stage470_annual_mature_fit_select.py --output research/lines/futures_full_market_long_signal_ai/outputs/stage470_annual_mature_fit_select/fixture1`。

2026-10-20 23:24 CST实际exit0，3项检查全部通过，0失败/0真实数据读/0实际模型fit/0现金；耗时0.756207秒。检查包括成熟相等边界、held补集、fake-dispatch精确15新与6复用、年映射及跨年deployment cutoff连续。没有运行旧大suite或fixture估计器。精确sourcebundle在 `outputs/stage470_annual_mature_fit_select/fixture1/fixture_terminal.json`，核心脚本SHA `45de7a301c560fea819c493c68679489807af0bc381867bd3dd96c254dcb1c5c`，fixture脚本SHA `511a169d2d94e931599f4bb3e4aa635391d555943f362e39813af92686558c67`。

当前无新增/修改/删除回测结果；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A。累计466实际fit/254完成现金及1旧partial不变。

## 反思与下一步

开始/结束按本次结果调参过拟合：否，因为只实现已冻结时钟，未读取实际Y/COMMON/成绩且未调新参数；长期同史择题风险仍是，最小fixture不构成alpha证据。继续价值：是，有条件地完成一次固定协议实际，能够检验及时成熟经验是否改善原学习对象；当前工程检查不能证明收益或更低回撤。

下一步由root绑定精确sourcebundle与本fixture终态并授权唯一actual；本agent当前不自行启动15fit。随后最多四候选账和一次独立综合审查，财务指标届时才可报告。无需更新LINE/registry或根memory/back_log；由root统一合入状态。
