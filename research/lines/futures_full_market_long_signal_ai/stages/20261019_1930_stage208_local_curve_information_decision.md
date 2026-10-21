# Stage208：局部相对便宜信息的固定实验结案

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 19:30 CST。
- 工作区 `/Users/mac/Desktop/fian`，分支 `codex/ai-training-data-expansion`。
- **接受本轮计算与账本算术，关闭固定 q / COMMON53 / Ridge / K 包，unsupported。** 不是重要突破，不晋级、不加注；全市场高质量做多的完整目标保持 active。
- 本阶段仅汇总已有小产物，新增训练、预测、选择、现金、SQL均0。全轮新增6个实际模型和4本实际现金；旧130模型、156主选择和157四账本直接复用。累计427 fit / 230 cash。

## 调研和判断

本轮沿用Stage198/199已完成的互联网与GitHub调研。[Bianchi等原文](https://arxiv.org/pdf/2308.00383)中的曲率spread成本后结果并不直接支持此处long-only规则；[作者GitHub](https://github.com/stefan-jansen/machine-learning-for-trading/blob/main/case_studies/cme_futures/03_financial_features.py)只提供特征构造参考。root基于原COMMON不能代数恢复的同标的三点相对价格，仅批准一次低先验证伪，没有把论文当收益保证。

判断：六折训练方向一致仍没有转化为品种留出和资金增量。否决的是这个固定配置，不能外推成所有期限结构信息或所有AI无效。

## 版本、参数及结果变更

- 新增：COMMON52后仅加同exact product、同观察日、严格相邻名义月份的log价格弦残差q；负值表示局部便宜。该折有限q加权标准化，缺失设计0，无新missing输入，共53维。
- 原Ridge alpha=1、intercept、cholesky；main/held0/held1各2020/2023截止，共6模型。原成熟first-exit stress R、权重和COMMON scaler不变。
- 六个q系数全部严格负后才完成1,933,480条child-model分数和同K选择。全量母体保留，不按q可用性或未来结果筛样本。
- 新现金4本：100万元，0.25N初始止损，单family计划风险0.25%、总风险2%、buffered margin cap25%、buffer1.1、参与率1%；原手续费、tick滑点、anchor、整数预算和K不改。
- 窗口2020连续、2023独立起算，各base/stress，均截至2026-10-16。新增回测结果4；修改/删除旧结果0；修改/删除既有参数0。
- 训练和held使用原首次退出target，不是K截断价值或资金收益。均值插补可能有隐式可用性交互，未因果隔离纯数值信息。

## 资金结果

金额为元。已闭合交易与fills不同；胜率按净PnL计算。

| 版本 | 窗口/成本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 已闭合交易 | 净胜率 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 新CURVE53 | 2020基础 | 2,178,251.36 | 117.825136% | -13.546843% | 0.912910 | 1,377 | 12.926652% |
| 旧157复用 | 2020基础 | 2,229,270.22 | 122.927022% | -15.627420% | 0.978453 | 1,295 | 12.200772% |
| 新CURVE53 | 2020压力 | 1,423,082.18 | 42.308218% | -12.654460% | 0.607323 | 982 | 12.729124% |
| 旧157复用 | 2020压力 | 1,528,419.71 | 52.841971% | -11.359301% | 0.787447 | 952 | 12.079832% |
| 新CURVE53 | 2023独立基础 | 1,713,541.09 | 71.354109% | -12.519651% | 1.135724 | 535 | 13.644860% |
| 旧157复用 | 2023独立基础 | 1,825,436.55 | 82.543655% | -9.902149% | 1.320956 | 494 | 12.955466% |
| 新CURVE53 | 2023独立压力 | 1,407,591.34 | 40.759134% | -12.709684% | 0.943136 | 445 | 13.258427% |
| 旧157复用 | 2023独立压力 | 1,526,645.82 | 52.664582% | -6.422761% | 1.223020 | 422 | 13.033175% |

| 窗口/成本 | 新/旧手续费 | 新/旧滑点归因 | 新/旧fills |
| --- | ---: | ---: | ---: |
| 2020基础 | 61,238.64 / 52,034.78 | 165,029.50 / 140,259.04 | 2,755 / 2,592 |
| 2020压力 | 74,287.82 / 68,710.29 | 183,062.84 / 167,960.05 | 1,968 / 1,912 |
| 2023独立基础 | 23,433.91 / 20,778.45 | 61,173.95 / 53,623.57 | 1,071 / 990 |
| 2023独立压力 | 40,093.66 / 36,269.18 | 92,258.73 / 83,952.08 | 896 / 849 |

滑点已体现在成交价，不能再次扣除。新四本净胜率略升、交易与费用归因增加、收益均降、3/4回撤更深，是共同现金路径结果，没有证明收益差全由成本导致。完整年度、family含零、容量、尾部及原始账本绑定见[Stage206执行记录](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_1923_stage206_local_curve_information_cash_execution.md)和其manifest。

## 事前门与不确定性

| 窗口/成本 | 收益差pp | DD差pp，正为变浅 | 每日日log增量95% CI |
| --- | ---: | ---: | --- |
| 2020基础 | -5.101886 | +2.080577 | [-0.00017272396110, +0.00016823827051] |
| 2020压力 | -10.533753 | -1.295159 | [-0.00017372230429, +0.00009614156186] |
| 2023独立基础 | -11.189546 | -2.617502 | [-0.00028532408623, +0.00015211078682] |
| 2023独立压力 | -11.905448 | -6.286922 | [-0.00024656350541, +0.00008087969229] |

四CI使用原070的2000次、252日块索引，未重新生成或加epsilon，全部跨零。没有稳定正增量证据，也不能把负点估计写成显著为负。窗口共享历史，多轮择题后的条件区间不是新盲OOS。

held0/held1已知equal-u增量为+0.002263041394377146R / -0.0008020094736690167R；各有7条distinct未知，同动作未识别23/31条已披露。两组均严格正且distinct未知0的事前门失败，不能将未知填0或用现金覆盖held失败。程序与独立重算门均nominal_pass=false。

新四本容量未知roots为38/18/6/1、入场执行未知4/2/0/0；2020基础/压力有9/6个stale日，2023两本0。旧控制也有未知及continuous stale。审查接受研究账本算术，没有补齐首次发布PIT或真实订单簿成交证明。0.25N计划止损不是跳空损失上界，不能据此加注。

## 独立审查与次数

- Stage205唯一6fit，120.816378秒；Stage206唯一4book，27.8627175秒，0SQL、旧现金重放和新标签。
- Stage207模型阶段独立核六折q统计/正规方程、全部预测、K选单及held，core blocker0；最大预测误差1.7763568394002505e-15。旧COMMON数学继承接受资格，不重训控制。
- Stage207现金续审28.034348秒，逐新四本核现金、费滑、手数、持仓、预算、native容量、K、年度family统计及四CI/冻结门，core blocker0。0fit、现金、SQL、旧大输入hash及重复模型/预测审查。
- cash1审查在最前收据适配失败：actual使用old_control_cash_replays，financial使用old_control_book_replays，尚未读cache/账本。失败源和终态保留，仅修分支与fresh cash2路径，新增一个定向fixture先红后绿；cash2续审通过。这不是第二次回测或交易逻辑修改。
- root报告生成曾在重复cost字段处中止，未生成结果或改索引；直接改用本简明报告。该文档适配没有模型、预测或现金执行。

## 反思与后续

- 开始/结束是否有过拟合风险：**是**。同一历史上的多轮择题仍有选择风险；本轮先冻结且未按结果救参，不等于消除风险。
- 继续固定q/53/Ridge/K包是否有价值：**否**。按204关闭，不换符号、邻距、年份、品种、缺失mask、模型、窗口、阈值、止损或投注救参。
- 继续完整目标是否有价值：**是**。下一步暂停弱特征串行续包，先区分原first-exit条件均值、同K/成本/成交条件下的单信号价值、重叠持仓和整数预算下的组合现金目标。目标不同尚不能证明标签错误或定位失败原因。
- [Stage209提案](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage209_objective_alignment_proposal/proposal.json)只读六份小报告，结合[Smart Predict then Optimize原文](https://arxiv.org/abs/1710.08005)、[作者GitHub](https://github.com/paulgrigas/SmartPredictThenOptimize)及[CME止损说明](https://www.cmegroup.com/content/dam/cmegroup/education/files/a-traders-guide-to-futures.pdf)，提出可识别机制与可比控制的必要条件；不直接上SPO、不复活旧log代理、不现在重标K。
- TODO：下一协议仅变一个结构轴，完整保留成熟时钟、unknown/cancel/no-fill/open。若只是正单位变换，或差异仅未知/不可执行/不改实际动作，则在新fit/cash前停止。两臂都成交且闭合的样本受选择和资本路径影响，本轮不追加此偏置扫描。
- 普通负结果更新本线LINE/registry，不追加根memory.md/back_log.md；无正式策略、生产、部署或Git发布动作。完整goal仍active。

## 精确证据

- [冻结协议204](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage204_local_curve_information_protocol/protocol.json)
- [模型manifest205](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage205_local_curve_information_fit/actual_run1/manifest.json)
- [现金manifest206](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage206_local_curve_information_cash/actual_run1/manifest.json)
- [模型与预测独审207](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage207_local_curve_information_review/model_forecast_selection1/review_receipt.json)
- [现金独审207](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage207_local_curve_information_review/cash2/review_receipt.json)
- [root结构化决策208](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage208_local_curve_information_decision/decision.json)
