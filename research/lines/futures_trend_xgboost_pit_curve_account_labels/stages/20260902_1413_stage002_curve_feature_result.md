# Stage002 PIT全曲线特征结果

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：研究隔离/标签前特征冻结
- 记录时间：2026-09-02 14:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：标签前特征矩阵与非退化审计
- 是否重要突破：否
- 是否触发A/B：是；未运行策略A/B

## 外部调研与判断

- Gorton、Hayashi、Rouwenhorst支持期限结构作为库存状态代理，但没有保证当前中国商品池、当前策略和当前成本下必然有效：<https://www.nber.org/papers/w13249>。
- XGBoost官方文档要求按查询组组织排名样本；当前每月候选天然形成组，但本阶段没有训练：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- 我的判断：六项曲线特征已证明可计算且有横截面差异；旧Stage073阈值失败仍有效，后续只能由账户边际标签决定是否有增量。

## 本次变更

- 新增脚本：`tools/curve_features.py`、`tools/stage002_curve_features.py`。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：固定8项相对rank10特征；曲线拟合至少3个合约。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2022-01-28`至`2025-11-28`。
- 账户规模：不适用，未运行账户。
- 成本口径：不适用，未回测。
- 样本过滤：47个月内全部rank10及以后候选，未按结果删行。
- 策略/归因口径：同日全曲线无阈值描述量相对rank10差值。

## 结果

- 决策：`stage002_curve_features_pass_ready_for_account_label_contract`。
- 技术门：`13/13`通过。
- 原始曲线描述量：797行；候选矩阵：374行/47月，其中rank10锚点47行、挑战者327行。
- 特征数：8；rank10全部逐位精确0；标签和阈值特征读取/创建均为0。
- 六项曲线差值在327个挑战者上均有327个唯一值、327行非零，并在8个fold中各有非零挑战者。
- 概率差有324个唯一值、326行非零；有1个挑战者与rank10概率并列，按原始事实保留。
- 特征总体标准差：概率差`0.122363`、rank距离`2.441251`、近远月basis差`0.627294`、全曲线斜率差`0.142913`、拟合RMSE差`0.015652`、OI HHI差`0.183261`、成交量HHI差`0.203924`、OI加权期限差`30.777159`。
- 双跑逐值一致；模型训练、策略回测、CTP和订单API均为0。
- 期末权益：不适用，未回测。
- 总收益：不适用，未回测。
- 最大回撤：不适用，未回测。
- Sharpe：不适用，未回测。
- 总滑点：不适用，未回测。
- 总交易次数：0。
- 胜率：不适用。

## 输出文件

- `raw_curve_descriptors.csv`：SHA256=`fceb1c075c34dab8a0a0f10842f2d141aff6961d2b58ee48e57e91b73f55b0b0`。
- `candidate_curve_feature_panel.csv`：SHA256=`9c57370ef9896ab9d64adadf2b8f3feb83e5873dba6a9bbffaad36de2670d7b3`。
- `feature_diagnostics.csv`：SHA256=`94d4ef30abd7307837f52ddbf73ed35a70f4376fb129a41029dfd67483057c94`。
- `stage002_summary.json`：SHA256=`16db41bcf756903302006e6444421161240f898b160eab62ea25342ddb30fc4e`。
- `artifact_manifest.json`：SHA256=`aefe27338abaac7a0c4204d4327824f7bc96e6338b6e4b7f2720bb86c1a49187`。
- 全线测试：`.py311/bin/python -m pytest research/lines/futures_trend_xgboost_pit_curve_account_labels/tests -q`，`10 passed`。

## 结论

- 本阶段结论：特征数据合同通过；只证明XGBoost可获得不同于旧108项损益特征的非退化输入。
- 是否进入下一步：取决于账户边际标签适配门。
- 下一步：只读冻结干净候选标签计划、任务数、A/A哨兵和身份门；通过后才预注册最小标签smoke。

## 过拟合反思

- 运行前判断：否，但同源Stage073带来较高先验风险。
- 运行后判断：否；没有读取任何未来或账户结果，也没有按诊断删改特征。
- 原因：8项合同在运行前固定，所有374行保留；本结果不评价方向和预测力。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但下一步价值完全受账户标签适配约束。
- 原因：数据层已排除覆盖和退化问题；若标签仍错位，继续训练没有意义。

## 合入建议

- 是否更新本线`LINE.md`：是。
- 是否更新`research/registry.md`：是。
- 是否追加根目录`memory.md/back_log.md`：否；未回测。
