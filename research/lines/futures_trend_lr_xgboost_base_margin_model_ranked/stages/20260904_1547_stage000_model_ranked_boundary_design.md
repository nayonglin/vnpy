# Stage000 正式模型排名层base-margin残差合同

- line_id：`futures_trend_lr_xgboost_base_margin_model_ranked`
- 记录时间：2026-09-04 15:47 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：前一无标签合同失败后的结构纠正新线；未读标签、未训练、未回测。
- 是否重要突破：否。
- 是否触发A/B：是；只冻结未来A/B，Stage001不执行模型。

## 调研与判断

- XGBoost官方说明`base_margin`可以使用已有模型的raw margin，logistic任务必须传log-odds：<https://xgboost.readthedocs.io/en/stable/tutorials/intercept.html>。
- XGBoost官方预测文档确认训练和预测均支持逐样本`base_margin`：<https://xgboost.readthedocs.io/en/stable/prediction.html>。
- 正式policy源码SHA256=`c68ca17f7088eac0c61f66c01fee1e2b34c973e2307cadf8a2026b9ab95f32a5`，在前一Stage001之前已存在，明确冻结：模型排名数`10`、固定产品`fu.SHFE`、总发布数`11`。
- 正式Stage182 runner SHA256=`ca15504e946e39fe6c5b0180e5bdf07bf38749973ceedd2085ba77480e3c9edc`，明确先从模型分数中选择10个非fu，再追加固定fu；发布时fixed fu通过left merge保留，因此没有模型特征和`model_ai_rank`。
- 我的判断：前一失败是研究合同把发布所有权误当模型所有权，不是数据或效果失败。只有把10个模型行与固定卫星同时写成硬门，才可独立重启无标签资格审计。

## 与前一闭线的隔离

- 前一线`futures_trend_lr_xgboost_base_margin_residual`保持失败关闭，不修改其Stage000、final或决策。
- 本线不得把前一final当通过证据，必须重新读取冻结源并独立重算77个月特征和50个PIT折。
- 只读复用前一线因果特征实现，冻结SHA256=`930c81fca2de049983c75c7470873e781b086a208993f9817fb04fd3649ef15f`；运行前后必须一致。
- 只读复用前一线基础身份/原子发布工具，冻结SHA256=`6f315ecb5ca63f0fbf83495119226c65da397c2a5dbbf7ef8cefa80a9c34c2bd`；不得调用其失败门评估或读取其final。

## 冻结输入与模型

- m0005、Stage183两源、旧76月特征面板和最新池身份沿用前一线Stage000的精确SHA，另新增正式policy与两个只读上游工具SHA。
- A/B模型、108项特征、正式二分类目标与样本权重、XGBoost 32棵深度1浅树参数均与前一Stage000一致，不因边界纠正而改变。
- 模型域固定18品种；发布域固定10个model-ranked + 1个fixed fu。固定fu不作为训练行、候选、标签或模型效果行。

## Stage001硬门

1. 全部冻结输入和只读工具运行前后SHA一致，前一final路径不得被读取。
2. policy精确为`ranked=10`、`fixed=fu.SHFE`、`total=11`，runner源码与m0005 manifest一致。
3. 正式训练面板精确77个月/1386行/每月18品种/108项有限特征；旧76个月/1368行逐值误差`<=1e-10`。
4. 最新发布池精确11行：10行`model_ranked`、1行`fixed_fu`；model-ranked行108项全部非空，fixed fu的108项全部为空且`model_ai_rank`为空。
5. 只对10个model-ranked行做特征逐值比较，行数精确10，最大误差`<=1e-10`。
6. 60交易日label-end精确77行、缺失0；active/effect folds精确50，训练月24..74，PIT违规0。
7. 禁止列、标签值、fit/predict、回测、CTP、订单和生产写入全部为0；输出只原子发布到本线。

通过：`stage001_model_ranked_boundary_contract_pass_allow_stage002_preregistration_only`。

失败：`stage001_model_ranked_boundary_contract_fail_close_no_labels`。失败后闭线，不再修改10+1、容差、月份、品种、窗口或折数。

## 回测记录占位

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 过拟合反思

- 运行前判断：Stage001否；未来Stage002高风险。
- 原因：所有门只来自既有正式代码和无标签结构；但历史期已被观察，不能形成独立效果证明。

## 继续价值反思

- 运行前判断：有，限Stage001。
- 原因：修正的是模型/发布层所有权，不是效果阈值；完整独立审计通过前仍不得读取标签。
