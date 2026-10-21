# Stage071 固定结算信息×止损模型：实现交接（0实际）

- 研究线：`futures_full_market_long_signal_ai`；时间：2026-10-18 16:38 CST；重要突破：否。
- 仅新增本阶段模型源码、合成测试、实现交接输出及本记录；不修改 LINE、registry、其他研究线或旧模型。
- 科学协议：Stage069，SHA `0418566cd9b624fb5a985448b3b0d4c94dbef56280feffd49bce09e1c5bf2dde`。新增实际拟合/SQL/资金账户均 `0`；当前没有研究成功或晋级结论。

## 调研与判断

沿已冻结069的一手参考，并核对 [scikit-learn Ridge 官方文档](https://scikit-learn.org/dev/modules/generated/sklearn.linear_model.Ridge.html)及[维护者 Ridge 源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/linear_model/_ridge.py)。加权 Ridge 的截距不应正则化；本实现同时保留带独立截距的55维增广正规方程供外部验证。研究判断没有变化：同宽信息比较需要完全相同的成熟行、权重、共同尺度和观测缺失；窄宽比较仍是正确重训后模型/政策包的比较，不能解释为纯止损因果效应。

## 固定实现与接口

- `tools/stage071_settlement_narrow_fit.py`：33,783 bytes，SHA `0a0a96baae5f971151845997ca2133b5e7d5d8cec31ecef85b21e9c192945910`。
- `tools/test_stage071_settlement_narrow_fit.py`：12,451 bytes，SHA `383e0b535305e7effce8124820dc314f8ac2c3f65ac79eed73f856bc07317ff0`。
- 12拟合固定为 COMMON/SETTLEMENT/OHLC_PROXY × WIDE/NARROW × 2020/2023；Ridge alpha1、intercept、cholesky，未增加参数、阈值或选择窗。
- 两政策分别使用自己的 `closed_complete_bar_model`、`u_date<cutoff` 且 `label_known_date<cutoff` 行和原生 `net_R_stress`。先在本训练集对同family真实entry/exit闭区间计算唯一性，再u均衡，整体均值1。没有使用删失/测试行做权重。
- 54槽为26共同X、26缺失indicator、共同external_missing、单scalar。原053共同X保留2N单位。每policy/cutoff三臂共用训练身份、权重和预处理；两信息scalar各半权共同拟合尺度，缺失标量标准化后0；COMMON的scalar直接严格0。
- 根收据 `source_acceptance.json`（SHA `e278ad70de958220ebcd3b4ef670bc29dd12c205b84cd3a658f5af5fcfe169fc`）另行接受历史重建假设；不修改067 `training_accepted/feature_available/strict_pit_accepted=0`。实际入口会验证receipt源绑定、两rule状态和mask193817/2020+106957/合法零6624，并用070同v代理逐行核身份、C/N、范围及代理公式。未知规则/F和冲突保持缺失。
- 2020模型仅预测2020—2022，2023模型预测2023以后；每policy/arm包含完整161014行，合计966084行，禁止未来标签状态筛分数。仅ready20且score>0请求。
- 预测文件固定为 `outputs/stage071_settlement_narrow_fit/experiment/predictions.csv.gz`，列：sequence_index/event_id/product_id/family_id/u_date/u_index/reference_epoch/policy/arm/cutoff/history_ready20/selected/score。070 cash复用同分数完成2020连续时钟更新与2023冷启。
- 四个policy/cutoff各存一份 `normalized_inputs.npz`（训练与预测base53、两标准scalar、y、weights、sequence），由本cell三模型复用；另存训练身份/权重、预测身份、scaler。12模型各保留joblib、portable系数及增广正规方程，无12份common盲复制。
- 实际入口要求精确root授权，绑定源码/tests、冻结协议、所有输入和fresh输出；拒绝未授权、错绑定和既有目录；失败保留，不自动重试。实现不导入任何SQL/native reader、下载或旧金融重跑。

## RED/GREEN与执行交接

初始6项RED：实现不存在；新增完整proxy身份检查先观察到缺失u_index被错误放行，再修复为明确拒绝。最终7项合成检查全部通过，含严格成熟/全母体前向预测、闭区间并发权重、共享54槽/合法零与缺失、重建mask冲突、独立portable全预测和正规方程、接受收据精确绑定及授权fail-closed。合成拟合只使用测试自造12行，不使用实际训练样本。

命令：

```text
.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p test_stage071_settlement_narrow_fit.py -v
```

最终日志及精确source bundle/实际入口模板见 `outputs/stage071_settlement_narrow_fit/implementation/{synthetic_green.txt,implementation_handoff.json}`。070标签尚待root授权和一次运行；本阶段没有运行实际输入加载或fit。root另派独立静态审阅，审阅与精确授权完成前不得运行实际。

## 指标与反思

本次新增/修改/删除金融回测结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均 N/A。旧参数和成绩没有改删。

开始与结束是否新增过拟合：**否，限冻结科学合同的实现与合成验证**；没有根据历史金融结果新增搜索。既有择题偏差和历史重建/PIT限制仍保留。继续是否有价值：**是**，该实现为一次固定信息/政策证伪提供可独立核验资产；是否有alpha仍须实际结果及独立全面审阅，当前未达目标。后续TODO：独审；070一次新标签；root精确授权12fit；070共享一次native的24账户；独立核验实际数据、逻辑、预算与置信度。不得救参。
