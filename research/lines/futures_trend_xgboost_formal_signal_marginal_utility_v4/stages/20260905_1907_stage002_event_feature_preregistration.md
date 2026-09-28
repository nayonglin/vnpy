# Stage002 正式事件与12特征资格预注册

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v4`
- 记录时间：2026-09-05 19:07 CST
- 是否重要突破：否；是否启动reviewer：否。
- 上游：V4 Stage001真实双冷worker预检已通过；V3失败证据封存。

## 固定实验

- 假设保持原始正式信号账户边际效用定义：LR选品、C9定方向，未来XGBoost只过滤根事件。
- 本阶段仅A基准；无B/C、标签、拟合、预测或绩效选择。
- 正式身份：m0005、`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`、150000元。
- 起止：2020-01-02至2026-08-28；A1/A2各一次独立冷回放。
- 事件：动态LR模型行、flat_entry/opened/is_opened=1；固定fu卫星继续运行但不进入模型事件。
- 12特征：formal_rank_percentile、formal_score_margin_to_cutoff、directional_rsi、directional_ma_gap、directional_ma_slope、open_interest_change_pct、stop_distance_pct、portfolio_drawdown_pct、margin_to_equity_before、active_positions_fraction、same_direction_correlation、loss_streak。
- 逐bytes复用V2特征工具；不调整样本、阈值、时间区间、成本或策略参数。
- 资格门继承V2/V3：总事件>=150；2023/2024/2025各>=24；多空各>=40；品种>=15；每特征>=2个值、至少8项>=10个值；无缺失和未来列；身份唯一；双worker数值误差<=1e-12。

## 实现与执行

- 只修改本线；用独立加载的V3研究模块复用已测试的沙箱、manifest、claim、回执和发布协议。
- 新入口绑定V4路径和1458项输入；V3源文件与其claim均不修改。
- 唯一行为修正：两个派生文件重定向从metadata开始持续到`_run_live_c9`结束；回放前后都验证内容，finally恢复原始Path。
- 沙箱持续限制网络及外部写入，私有数据库副本和空setting继续使用。
- 每worker正式A回放恰好一次，返回live spec资金必须为15w。
- 只发布无标签事件特征和安全回执，组合绩效和交易输出不发布。
- 实现/测试完成后冻结输入合同；claim独占创建，失败证据永久保留。
- 任一数据/特征/一致性门失败则停止本形状，不按结果救参。

## 调研判断

- 已通过GitHub读取XGBoost官方`doc/tutorials/model.rst`，确认特征和监督目标应由经济问题定义：https://github.com/dmlc/xgboost/blob/master/doc/tutorials/model.rst。
- 当前改动仅使既定事件能够被可靠提取；模型价值仍须由后续时间顺序样本外账户路径证明。
- 原web工具本轮鉴权失败，使用GitHub原始文件只读请求完成资料核查。

## 反思与记录

- 运行前过拟合判断：本次没有按收益调整参数；研究整体因历史反复观察仍有高风险，历史结果只算开发证据。
- 继续价值：是；准备链已经通过，下一步能直接检验样本是否足够。
- 新增参数：仅V4路径和输入合同；策略参数修改/删除：无。
- 回测结果新增/修改/删除：执行前均无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：本阶段不发布绩效，只报告事件资格。
- 下一步：合格后形成单事件接受/跳过的反事实标签合同，再做模型开发；真正晋级保留新增前向证据要求。
