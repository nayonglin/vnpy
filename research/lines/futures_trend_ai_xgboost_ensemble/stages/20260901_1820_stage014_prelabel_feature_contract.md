# Stage014：账户边际XGBoost标签前特征合同

## 阶段信息

- 预注册时间：2026-09-01 18:20 CST
- 是否重要突破版本：否；完整标签生产前的防过拟合合同
- 当前线上：m0005 `ai_top10_plus_fu_official_live_v1`，生产HEAD `d492ee072...`
- 本阶段不读取任何账户反事实标签值，不回测、不训练模型、不连接CTP、不调用订单API

## 候选方案与决定

- 否决全108项：51个月组仅为108特征的`0.47`倍，树模型容易记住偶然阈值。
- 否决标签后挑特征：会把同一批账户标签同时用于特征选择和评估，产生自适应泄漏。
- 采用9项标签前合同：正式逻辑回归概率相对rank10差、rank距离，以及正式代码早已固定的7个simple-score分量的月内z-score相对rank10差。

## 冻结特征

1. `formal_probability_delta_vs_rank10`
2. `formal_rank_distance`
3. `pnl120_z_delta_vs_rank10`
4. `pnl60_z_delta_vs_rank10`
5. `sharpe60_z_delta_vs_rank10`
6. `positive_day60_z_delta_vs_rank10`
7. `opened60_z_delta_vs_rank10`
8. `slippage60_z_delta_vs_rank10`
9. `drawdown60_z_delta_vs_rank10`

- 7个结构分量严格来自正式`add_simple_score`既有输入：`net_pnl_sum_120d/net_pnl_sum_60d/net_pnl_sharpe_like_60d/pnl_positive_day_mean_60d/opened_count_sum_60d/slippage_sum_60d/net_pnl_drawdown_60d`。
- 对`membership_locked_top19_plus_fixed_fu`月份，正式score不重新解释为当期概率，概率差保留缺失值，由XGBoost原生missing路径处理；不增加月份补丁。
- 不纳入T18未来活动、Stage012单月收益、品种名称、年份/月序、标签期交易或任何标签派生统计。

## 数据与拆分门

1. m0005 summary记录的两个源文件当前SHA必须逐项一致。
2. 重建51个月×18品种原始特征，每月必须恰18行；与旧冻结1368行×108特征重合部分最大误差不超过`1e-9`。
3. 与Stage013完整计划连接后必须恰459行、每月rank10..18完整。
4. 首39个月为development；最后12个月为sealed holdout。模型、阈值和臂定义冻结前，任何报告和训练代码不得读取holdout标签值。
5. 目标模型固定为两个浅树XGBRegressor，分别预测`delta_return`与`delta_drawdown_improvement`；不把二者加权成一个事后效用。
6. A为正式LR rank10；B为XGB双头直接选择；C保留正式Top9，仅当同一challenger两个OOS预测都大于0才替换rank10，否则保持A。

## 过拟合与继续价值（运行前）

- 是否过拟合：否。特征由正式既有结构和第一性原理在标签生成前冻结；但样本仍小，后续必须浅树、单一参数组、严格PIT和封存留出。
- 是否值得继续：是。该合同把“同时接入逻辑回归和XGBoost”落成可部署的最小交互，而不是再次用XGBoost重排整个Top10。

