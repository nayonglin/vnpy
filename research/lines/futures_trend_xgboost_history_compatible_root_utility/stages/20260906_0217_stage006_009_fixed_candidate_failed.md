# Stage006-009固定模型完整C失败

- line_id：`futures_trend_xgboost_history_compatible_root_utility`。
- 时间：2026-09-06 02:05完成训练，02:06冻结并启动完整C，02:14得到结果，02:16验证，02:17记录。
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`。
- 是否重要突破：否。真实模型C已运行，但不满足收益提升且回撤降低，固定候选不晋级。
- reviewer：0。用户要求只在有价值版本出现后启动；本候选明确失败，不做无意义审核。

## 版本与参数

- 代码变更新增/修改/删除：均无，执行上轮已经实现并测试的Stage006、008、009。新增本轮冻结输入、训练产物、唯一C回放、研究记录及当前线状态；不修改既有科学输入和回放结果。
- 模型参数新增/修改/删除：均无。10项共同连续特征；收益边际/回撤边际两个`XGBRegressor`；80棵树、深度2、learning_rate0.05、min_child_weight20、lambda10、alpha1、subsample1、colsample1、hist、单线程、seed20260905、base_score0、平方损失。
- 月初扩展窗口，决策日与生命周期结束日均严格早于月初，至少60成熟标签。训练折内分别计算均值及总体标准差并逆变换；双预测严格小于0才跳过。固定FU、样本不足月份及其他策略规则不变。
- 依赖固定XGBoost3.2.0、sklearn1.8.0、pandas2.3.3、numpy2.4.4；未升级、未网格调参、未选特征或年份。
- C复用冻结正式LR/C9入口及前置候选snapshot，只在非FU根开仓前做过滤。使用C自己的当前账户特征；不是A事件ID查表，不把反事实标签相加成策略收益。
- 同一完整区间2020-01-02至2026-08-28、本金150,000；手续费仍为继承的研究假设0，不是真实全成本；不把此回测称为实盘表现。

## 全量训练

- Stage005唯一完整快照为`artifacts/stage005_label_collection/20260906_020434_393264/summary.json`，274闭合全量合格、2删失为空；此前部分快照没有被用于历史训练。
- 命令：`.py311/bin/python -B research/lines/futures_trend_xgboost_history_compatible_root_utility/tools/stage006_training_campaign.py --snapshot research/lines/futures_trend_xgboost_history_compatible_root_utility/artifacts/stage005_label_collection/20260906_020434_393264/summary.json`。
- 80月状态齐全，66训练月、14未训练月，共132个回归头；276个A事件的原生UBJSON保存/加载前后预测零差异，网络尝试0。
- 实际首个训练月2021-03-01，60样本。真实同日未成交撤单0/0标签按冻结规则计入；此前2021-04已有65成熟事件是剔除撤单后的保守资格口径，不代表合同规定4月才能启动。
- A事件诊断有82次建议跳过，首次2021-06-24；该表不是C，也不是策略收益。
- 训练产物`artifacts/stage006_monthly_fit/`；`summary.json` SHA256 `47233d0678590e45d3c9caebb8eaa9f094466578e0fc52066a5e3864931e0ccf`，`model_index.json` SHA256 `aeb3039105e635e4346f12443a86e6e2f923f230ddc0ef734a31d3856e638e1b`。

## 唯一完整C

- 命令顺序：`.py311/bin/python -B research/lines/futures_trend_xgboost_history_compatible_root_utility/tools/stage009_full_path_replay.py --freeze`，成功后同入口`--run`，各执行一次。
- 冻结文件`stages/stage009_input_freeze.json`；1830项输入，文件合同SHA256 `6303151c184ee6ec19198c951b83e5da287afb1786516c2e8e3831be203fd016`，运行时合同SHA256 `04396eb74da1ed4812b0eabcc94e28cd2a64f90a1839d08ace6630faf2149e1e`。
- 真实C决策284次、跳过86次；首次干预2021-06-24 candidate163。A事件诊断82与真实C86不同是路径改变后候选/状态改变，不能用前者替代C。
- 父进程从C候选重建10特征及事件身份，再独立加载同月模型复算每项分数和动作，逐值一致；首次干预前daily/trades/positions/candidates与A一致。全部日历匹配。
- 完整C真实回放1次，回放内训练0、网络0、标签值读取0、CTP0、账户查询0、订单API0、生产写入0。正式LR仍按冻结身份加载一次。
- 产物：`artifacts/stage009_full_path_replay/summary.json`，SHA256 `a37003b02e59958d40dd9cadc32f5d0a2a9f1890e81e81996fb942e977201b4b`；`workers/C/receipt.json` SHA256 `20222318968925499fa48cb20e48a6a097546b0feb84ad761e37fedd951f7a9e`。8张表及逐项模型决策均归档在`workers/C/`。

## 完整指标

| 指标 | 冻结A，未重跑 | 固定模型C |
| --- | ---: | ---: |
| 期末权益 | 12,226,270.60 | 5,612,182.60 |
| 总收益 | 8050.8471% | 3641.4551% |
| 最大回撤 | -45.9216% | -42.7586% |
| Sharpe | 1.683943 | 1.606647 |
| 总滑点 | 1,100,560 | 419,850 |
| 手续费 | 0 | 0 |
| 成交记录数 | 655 | 490 |
| 非零损益日胜率 | 54.2419% | 53.8111% |

- C比A少6,614,088.00期末权益，总收益少4409.3920个百分点，最大回撤绝对值仅降低3.1629个百分点。`primary_gate_passed=false`，`valuable_candidate_verified=false`。
- 成交记录数不是闭合逐笔交易数，胜率是非零损益日口径，不冒充交易胜率。
- 执行摘要`status=passed`只表示执行/验算合格，不是策略合格。固定候选决策为`fixed_candidate_failed_no_parameter_rescue`。

## 既有曲线年度诊断

只消费已完成的A/C日表，没有新增回放、模型拟合或选择最优年度；年度收益为该年净损益除以前一年末权益，2020起点150,000。

| 年度 | A收益率 | C收益率 | C减A净损益金额 |
| --- | ---: | ---: | ---: |
| 2020 | 108.2744% | 108.2744% | 0.00 |
| 2021 | 479.6141% | 426.0341% | -167,390.00 |
| 2022 | 7.0210% | -0.7192% | -138,955.60 |
| 2023 | -4.7835% | -14.4419% | -142,930.00 |
| 2024 | 318.1506% | 172.7085% | -3,459,660.00 |
| 2025 | 69.1955% | 50.9556% | -3,399,171.20 |
| 2026至8月28日 | -6.3463% | -2.3400% | 694,018.80 |

- 2021-2025五个完整干预年度C收益率均低于A；2026未完整，不能用该年的少亏替代年度门。金额差有前期复利和仓位路径影响，不能直接归因为该年被过滤交易的独立贡献。
- 原曲线`broker10_margin_to_equity_pct`峰值A100.8156%、C69.4838%；降风险不等于双目标成功，该值也不是现实券商保证金核验。
- 主门已失败，未启动双倍滑点真实重跑、年度冷启动、现实手续费/TCA或reviewer，节省不合格候选的晋级成本。

## 验证、边界与后续

- 相关回归测试162 passed in 16.96s（本线144、上游18）。测试命令沿用上一阶段完整命令；没有为本结果改实现或用例。
- 收尾再次核验1830项当前输入、原A科学输入、C回执和8份压缩解码产物，全部通过。训练、C、汇总、批次及测试进程均已退出；run.lock不存在，私有runtime剩余0。
- 只读生产目录`/Users/bytedance/Desktop/person/vnpy_production_live`仍干净，HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`。未改其他研究线、registry、根历史总账；共享脏文件保持原样，未提交、推送、部署或真实交易。
- 下一步仅利用冻结标签/C做低成本结构归因，区分目标不一致、预测能力不足、策略干预后的状态分布变化；先形成可证伪假设，不扫描本候选的阈值、参数、年份或品种。总目标未达到。

## 调研与开始/结束反思

- 本轮复核[XGBoost官方模型IO](https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html)、[官方v3.2.0源码](https://github.com/dmlc/xgboost/blob/v3.2.0/python-package/xgboost/sklearn.py)、[sklearn目标变换](https://scikit-learn.org/stable/modules/generated/sklearn.compose.TransformedTargetRegressor.html)。判断：原生保存和训练折内变换解决复现与变换泄漏风险，不保证策略收益；本次完整C正好证明实现正确也可能策略失败。
- 开始是否过拟合：本轮不是按收益调参，继续已有冻结计划；整个长周期反复历史研究仍有选择偏差。
- 结束是否过拟合：没有用本次结果救参、删样本或缩区间，但不能由此宣称模型已经排除过拟合；证据只是开发期月度前向验证，非未见样本。
- 开始是否值得继续：是，完整训练和C是目标的直接缺口，本轮已实际完成并得到否定结果。
- 结束是否值得继续：继续晋级此固定版本否，收益显著恶化且跨年一致落后；对结构失败做一次低成本、可证伪归因是，不能把无限参数搜索当成持续研究。reviewer保持0。
