# Stage096 冻结模型重评

时间：2026-10-21 00:06，北京时间；非重要突破，0fit、0模型加载。固定060b七模型/原训练prior，4738行81月概率float64 bits不变，最新2026-09-30研究评分77品种。

只将095标签证据接到旧概率；成熟月份等权fullN Brier相对原训练prior改善上下界2020—2026仍全部跨0，稳健正下界年度数0。因本轮robust标签未变，monthly_loss_bounds.csv及annual_loss_bounds.csv与077逐字相同。2026只有6成熟月；这些是缺失标签识别上下界，不是置信区间、独立forward OOS或交易收益。

模板summary中的new_identified_scored_rows=8是相对060b原标签；这8来自上一轮075，本轮相对075/077新增为0。单独comparison_baseline_clarification.json保留明确基准，不覆盖原运行收据。

调研判断沿用[官方sklearn评价](https://scikit-learn.org/stable/modules/calibration.html)与[维护者损失源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/metrics/_classification.py)：可复算损失不认证校准或盈利。结论NO_PROMOTION，usable_for_trading=False。097独立按每row候选0/1枚举重算。

新增/修改/删除参数0；没有用1374标签重训，正式未改。权益、收益、回撤、Sharpe、滑点、交易次数、胜率N/A。开始及结束新增按成绩择参过拟合否；继续核准确标签有价值，重复重训同数据/扩大模型搜索无价值。
