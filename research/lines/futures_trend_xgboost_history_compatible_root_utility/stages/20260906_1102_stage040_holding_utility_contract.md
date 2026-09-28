# Stage040 持仓样本与效用合同

- 时间：2026-09-06 11:02 CST；line_id：futures_trend_xgboost_history_compatible_root_utility；不是重要突破。沿用持续授权，限制在本线，不改生产、其他线、registry、根总账，不commit/push。
- 原目标不变：同一冻结A，2020-01-02至2026-08-28，150000本金，全周期收益提高且最大回撤下降。上一轮Stage039是工程进展，不是alpha。当前扩展已有特征与单次反事实回放，不重新做A0/E控制。

## 事前固定定义

1. 样本为Stage034全部inventory_reconciled_holding观察，不按未来结果、标签或年月品种筛选。原FU/未成交/待平/换月等不合格状态保持；使用实际成交成本，不修改原层同步bug。原完整276根库存和删失状态保留；1002观察不冒充1002独立交易。
2. 观察在原on_bars全部完成后，日线按当日15:00已知的研究假设。特征接口只接收当前观察、当前成交库存和此前至当前观察的账户权益峰值，不接收根结束日或执行窗口。9项：directional_unrealized_return=sign*(close/actual_cost-1)；directional_day_return=sign*(close/open-1)；day_range_fraction=(high-low)/close；directional_close_location=sign*(2*close-high-low)/(high-low)，平价bar取0；log_holding_bars=log1p(原state.bars_since_entry)；layer_stop_buffer=最小sign*(close-layer.stop_price)/close；portfolio_drawdown=equity/running_peak-1；margin_to_equity=margin/equity；loss_streak=原当前连续亏损数。
3. layer_stop_buffer只表达当前计划层止损距离，不称真实成交风险R；bars_since_entry保留原策略计数，不称实际持仓自然天数。不引入产品ID、年份、根ID、结束日或未来成交价作为模型输入。不按输出分布调尺度或窗口。
4. A为原路径；每个E从原完整起点重放，在且仅在该观察点通过Stage039模块平掉该产品实际仓位。其他订单、原规则后续重入和资源反馈继续运行，结束日固定原A根end_date。单次退出不是强制持有空仓至end_date，更不按事后最优退出取标签。
5. 标签窗口从观察日相同日终权益Q开始，含之后至原根end_date的日终账户路径；严格检查两臂观察日权益等于Q和日期相同。return_marginal=(A_end-E_end)/Q；drawdown_marginal=窗口A最大回撤-窗口E最大回撤，峰值从Q开始。成本已在净权益内，禁止再扣。两标签均负时代表继续持有在这两个局部指标均差于退出，零不视为负。局部回撤不等于全周期回撤，仍须真实C检验。
6. 根结束日仅离线用于标签成熟和分组，不进入决策接口；截止月首严格date<cutoff且end_date<cutoff。每根所有合格观察权重1/n，该根总权重1，禁止按观察数降低60个成熟根门。训练折内按这些权重计算每头均值和总体标准差；常量头预测训练均值。
7. 固定双回归头原80树/depth2/learning_rate0.05/min_child_weight20/lambda10/alpha1/full sampling/hist/1线程/seed20260905/base_score0。仅改变经济样本、9项持仓特征及根等权，不扫描模型。每月扩展训练，完整标签先齐再训练；未达到60成熟根原动作不变。唯一动作：两头逆变换预测严格负才退出。
8. 训练任务清单与特征分开：features.csv无未来字段；jobs.json保存标签生命周期、当前快照、库存和期望特征，只用于离线反事实。执行价格只在已提交订单撮合时由提供器访问Stage037固定A窗口。当前1002窗口只许可这些A单次反事实，不许可未来C新状态。
9. Stage041先按(date,product,contract)选择最早两个不同根及最早空头根的首个观察组成去重canary，再按同一时间排序推进全清单；不依盈亏选择。失败保存并停查，不静默重跑。最终C动态数据门必须另冻，未通过前不跑模型C。
10. A对C完整双目标通过后才进入原稳健性门，包括完整干预年份、滚动/独立起点、成本压力；只有有价值真实C并通过基础稳健性才拉reviewer。这里不单独构造无基底持仓的B。

## 实施检查

- 先合成测试RED/GREEN：真实/计划成本分离、多空、平价bar、未来字段不影响、非有限/错日/无资格阻断、严格月前、同根权重、缺日/锚点/非正权益拒绝。
- Stage040只读冻结观察和库存，生成9特征、分离的1002任务及80月库存，不生成历史标签或模型。输入与输出SHA独立留存，原Stage039控制摘要和当前输入需校验。Stage041另冻运行器及全部依赖。
- 新增参数：9特征、根等权、观察权益锚点、一次退出到原根结束日；修改参数：无旧合同追改；删除参数：无。新增回测结果：本阶段无；期末权益/收益/最大回撤/Sharpe/滑点/交易次数/胜率均不适用，原A保持不变。

## 调研判断与反思

- XGBoost官方Python API支持逐样本weight；ranking模式权重语义不同，本线使用回归而非ranking。[文档](https://xgboost.readthedocs.io/en/stable/python/python_api.html)
- scikit-learn官方_split.py的Group与TimeSeries切分分别处理分组和时间；本线持仓标签跨观察日，不能仅随机GroupKFold或固定行数gap，采用明确根成熟截止。[GitHub源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/model_selection/_split.py)
- 开始是否过拟合：本轮否，不看新效用后选特征、窗口或参数；长期历史多次研究选择偏差仍存在，历史walk-forward不是未触碰留出集。继续是否有价值：是，当前持仓已经提供实际浮盈与计划止损距离，与失败入场过滤不是同一经济动作，但收益未知，失败后不救参。
