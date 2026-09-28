# AI选品XGBoost账户组合上下文研究线

## 研究线身份

- `line_id`：`futures_trend_xgboost_account_context`
- 创建时间：2026-09-02 11:07 CST
- 当前状态：Stage001标签前可行性失败并闭线；冻结实际损益源不能覆盖完整rank10..18候选组合上下文，未训练、未回测
- 上游反证：`futures_trend_ai_xgboost_ensemble` Stage017已关闭原九特征/账户边际标签族
- 线上基准：`ai_top10_plus_fu_official_live_v1`
- 冻结release：`m0005_20260901T165450+0800_1961d98ccb2b`
- 研究目标：在保持正式逻辑回归主体不变的前提下，用XGBoost识别第10席位候选与正式Top9之间的非线性组合关系；最终候选必须同时提高全周期收益、降低最大回撤
- 隔离边界：只写本研究线目录及总索引；不修改生产目录、正式AI池、CTP、邮件、launchd或订单链路

## 第一性原理判断

Stage017已经证明，目标单位导致的单叶退化可以修复，但原九项特征即使学出大量树分裂，也没有稳定地同时改善账户边际收益和回撤。该失败不能再用scaler、树参数、阈值、rank、年份或品种修补。

本线只验证一个不同的结构性假设：Stage015标签衡量的是“候选替换正式rank10后，在完整账户中的边际结果”，而原九项输入主要描述单个候选相对rank10的质量，没有显式描述候选与正式Top9的组合关系。若缺失变量确实是账户组合上下文，则加入严格PIT的Top9交互特征后，固定浅树双回归头应在同一冻结development OOS门槛下表现出稳定增量。

## 方案选择

- 采用：正式逻辑回归保留Top9，XGBoost只在rank10..18中挑战第10席；模型使用原九项候选质量特征加六项账户组合上下文特征。
- 否决：把正式108项特征全部交给XGBoost。39个development月份不足以支持108维树模型，极易记忆月份和偶然阈值。
- 否决：继续做入场meta-label。`futures_trend_signal_quality_ai` Stage236及当前C9 Stage015的purged OOS均已证明现有入场质量特征跨年不稳定。
- 否决：直接把协方差变成仓位缩放。方向协方差风险预算及候选边际风险贡献两条独立研究线已在真实引擎中失败。
- 否决：神经网络。当前独立月份和标签规模太小，新增容量没有可辩护的数据基础。

## 冻结数据身份

- 正式完整排序：`research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv`
  - SHA256：`b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0`
- 原九项标签前面板：`research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage014_prelabel_feature_contract/prelabel_feature_panel.csv`
  - SHA256：`e8272438cd69fe784b236ac91763f4ec0da71d2b711cd38b576c5e66d237f5fd`
- 正式108项特征复现样本：`research/lines/futures_trend_ai_score_attribution/artifacts/stage001_20260731/training_samples.csv`
  - SHA256：`92f36b6647cae9d8db04b0a1351749f9103a1988799dbb8dff0ad1d350d1d431`
- 冻结逐日品种损益源：`/Users/bytedance/Library/Application Support/qmt-roll-stage179/production-live/official-live/qmt_roll_stage183_ai_source_floor35_position_changes_2020_2026_04.csv`
  - SHA256：`17c81f2dbb30f836b544161c3fc4d4bd6415151d89b8f8937378739e868c21aa`
- development账户边际标签：沿用Stage015冻结文件，SHA256 `39e969783adc2ac54f771cf03e685a4cec45ce09adeb2d1eefc6ca54ef2cbce2`
- development对账：沿用Stage015冻结文件，SHA256 `d595547fa81906093c0fd530acbfa5d0f2b7c3fe489987efa79da304b977eb95`
- sealed holdout：`2025-07-31`至`2026-06-30`，Stage000/001/002/003均不得读取标签值；未来任何解封都需要新的预注册、独立复核和用户批准。

## 冻结十五项输入

保留Stage017九项，不修改定义：

1. `formal_probability_delta_vs_rank10`
2. `formal_rank_distance`
3. `pnl120_z_delta_vs_rank10`
4. `pnl60_z_delta_vs_rank10`
5. `sharpe60_z_delta_vs_rank10`
6. `positive_day60_z_delta_vs_rank10`
7. `opened60_z_delta_vs_rank10`
8. `slippage60_z_delta_vs_rank10`
9. `drawdown60_z_delta_vs_rank10`

只新增以下六项，不做标签后筛选：

10. `candidate_top9_aggregate_corr_120d_delta_vs_rank10`
11. `candidate_top9_downside_corr_120d_delta_vs_rank10`
12. `candidate_top9_active_overlap_rate_120d_delta_vs_rank10`
13. `candidate_top9_joint_loss_rate_120d_delta_vs_rank10`
14. `top9_plus_candidate_drawdown_improvement_ratio_120d_vs_rank10`
15. `top9_plus_candidate_sharpe_improvement_120d_vs_rank10`

## 六项上下文特征的精确定义

对每个`eval_date=t`：

- 从冻结正式完整排序取得当期rank1..9产品集合`H_t`、正式rank10产品`b_t`和rank10..18候选`c`。
- 把逐合约`net_pnl`按正式代码的`product_from_contract`映射后，按`date, product_vt_symbol`求和；对冻结正式18品种按全局交易日历补齐，缺失组合填`0.0`。
- 窗口`D_t`严格取源文件中小于等于`t`的最后120个全局交易日，包含`t`。正式月池在收盘后形成并用于下一期，因此`t`日收盘数据可用；任何行使用`t`之后日期都视为PIT硬失败。
- 对`d in D_t`，单品种损益序列记为`p_j(d)`；Top9聚合序列为`h_t(d)=sum(p_j(d), j in H_t)`。
- 正式rank10作为唯一相对基准。所有新特征在rank10行必须精确为`0.0`，不做月内z-score、不做缺失插补。

定义函数：

- `corr(x,y)`：120日Pearson相关系数；两侧样本标准差必须大于0。
- `down_corr(x,h)`：只在`h(d)<0`的日期计算Pearson相关；负Top9日期必须至少20个且两侧标准差大于0。
- `overlap(x,h)=count(x!=0 and h!=0)/count(x!=0)`；候选活动日必须大于0。
- `joint_loss(x,h)=count(x<0 and h<0)/120`。
- `dd(x)=min(cumsum(x)-cummax(cumsum(x)))`，因此`dd<=0`。
- `sharpe(x)=mean(x)/std(x,ddof=1)*sqrt(252)`；标准差必须大于0，不扣无风险利率。
- `q_j=h_t+p_j`，`q_b=h_t+p_b`。

六项特征依次为：

1. `corr(p_c,h_t)-corr(p_b,h_t)`。
2. `down_corr(p_c,h_t)-down_corr(p_b,h_t)`。
3. `overlap(p_c,h_t)-overlap(p_b,h_t)`。
4. `joint_loss(p_c,h_t)-joint_loss(p_b,h_t)`。
5. `(dd(q_c)-dd(q_b))/abs(dd(q_b))`；`dd(q_b)`必须严格小于0，正值表示历史窗口回撤较rank10更浅。
6. `sharpe(q_c)-sharpe(q_b)`。

任一月份、任一rank10..18行不满足120日、20个Top9负收益日、活动日、非零标准差或有限值合同，Stage001整体停止。不得缩短窗口、填均值、补零非结构缺失、换相关系数、删月份、删品种或根据标签修改公式。

这些特征只是历史组合关系描述，不是可执行组合回测，也不等于因果收益。真实资本竞争、整数手、保证金、持仓延续和复利效应只能由后续同引擎A/C验证。

## 冻结模型与实验臂

- 训练范围：39个development月份，`2022-04-29`至`2025-06-30`，每月rank10..18共351行。
- OOS：最少24个训练月后逐月扩展，标签可用条件为`train_eval_date < test_eval_date`且`train_next_eval_date <= test_eval_date`；固定15折、135条OOS预测。
- 目标：Stage015的`return_delta`和`drawdown_improvement`两个独立回归头，不合成事后效用。
- 目标变换：每折、每目标仅在训练行拟合`StandardScaler(with_mean=True, with_std=True)`，预测后逆变换。
- XGBoost参数：完全沿用Stage017固定浅树参数，64棵树、深度2、学习率0.03、`min_child_weight=12`、`gamma=0.1`、`subsample=0.8`、`colsample_bytree=0.8`、`reg_alpha=1`、`reg_lambda=10`、`hist`、seed42、单线程。
- A：正式逻辑回归完整排序的rank10。
- B：十五项输入的双头XGBoost，在rank10..18中按两个预测的等权月内percentile选最高者。
- C：正式Top9不动；仅当B所选同一候选的逆变换`predicted_return_delta>0`且`predicted_drawdown_improvement>0`时替换rank10，否则保持A。
- 禁止：参数扫描、融合权重扫描、特征选择、替代target transform、阈值扫描、rank范围扫描、月份/年份/品种例外和结果后单调约束。

## 分阶段门禁

### Stage001：标签前特征可行性

- 先写纯函数与负例测试，再实现特征构造。
- 输出必须为51个月×9候选=`459`行；每月rank10..18完整。
- 六项新特征除合同要求的rank10精确零外全部有限，日期上界不晚于各自`eval_date`，重复运行逐值及SHA一致。
- 必须证明没有打开Stage015 development标签或sealed holdout标签。
- 只允许修复实现错误，不允许修改上述数学定义；可行性失败即关闭本线。

### Stage002：一次冻结development OOS

- Stage001冻结特征SHA后，另写训练合同并接受独立运行前复核。
- 技术门除Stage017既有确定性、PIT、模型/scaler发布门外，还要求至少一个新上下文特征产生非零split，且新C选择至少一个月份不同于Stage017；否则判定新机制未实际生效。
- 效果门完整复用Stage017九项：C替换月数`>=4`；覆盖2024和2025；总收益增量`>0`；总回撤改善`>0`；两项leave-best-out均`>0`；2024/2025各年两项目标均`>=0`；实际替换月双目标联合正比例`>=50%`。
- 任一门失败立即闭线：不跑真实引擎、不读holdout、不调公式或模型。
- 产生评估结果后必须由独立reviewer复算输入身份、PIT、模型、选择、九项门和全部发布SHA。

### Stage003：development全周期真引擎A/C

- 仅在Stage002全部通过后，另做真引擎预注册与独立授权；Stage000不授权运行。
- A必须逐日逐笔复现冻结正式基准；C只替换Stage002产生的OOS月份第10席，其他月份与A相同。
- 统一使用15万元、正式成本、保证金、整数手、相关性、最多4持仓和独立冷进程；输入身份必须覆盖分钟行情、主力映射、合约元数据、`sys.path`和每臂独立临时目录。
- 全周期晋级门：C总收益严格高于A，且总利润增量至少为`max(10000元, abs(A总利润)*1%)`；最大回撤至少改善`1.0`个百分点；Sharpe不低于A；最长水下期不增加；2024和2025各年收益增量均不为负，剔除贡献最好年份后总利润增量仍为正；2倍成本下仍同时提高总收益并降低最大回撤。
- 任一门失败立即闭线，不跑多起点、holdout或生产候选。

### Stage004及以后：仍非自动生产

- 即使development全周期A/C通过，也只能称为development候选，不能称为目标已达成。
- sealed holdout解封需要用户再次批准；通过后仍需独立reviewer、前向shadow和正式发布流程。
- 在holdout与前向证据完成前，不修改`vnpy_production_live`、正式release、CTP或订单链路。

## 外部调研与判断

- XGBoost论文：https://arxiv.org/abs/1603.02754
- XGBoost官方参数文档：https://xgboost.readthedocs.io/en/release_3.2.0/parameter.html
- XGBoost官方单调约束文档：https://xgboost.readthedocs.io/en/stable/tutorials/monotonic.html
- XGBoost GitHub：https://github.com/dmlc/xgboost
- scikit-learn时间序列拆分：https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- Roncalli风险预算材料：https://www.thierry-roncalli.com/download/risk-budgeting.pdf
- `pysystemtrade`组合构建参考：https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
- 判断：XGBoost的合理用途是学习少量、预声明、具备经济语义的非线性阈值和交互，不是用更大模型替代正式逻辑回归。组合相关特征有理论依据，但历史相关不等于未来分散化，必须通过冻结OOS与同引擎A/C共同证伪。

## 过拟合与继续价值

- 当前过拟合风险：高。相同39个development月份及15个OOS月份已经被Stage016/017观察过，本线属于自适应后续研究。
- 风险控制：Stage001未读取标签、未训练模型；失败后没有修改窗口、缺失值、月份、品种或公式，sealed holdout保持不可见。
- 是否值得继续：当前线否。实际损益源有27行零活动，六项预声明特征无法覆盖完整候选面板；继续补值或删样本只会制造选择偏差。
- 终止条件：已触发Stage001可行性失败，本线关闭，不进入Stage002/003。

## Stage001结果与闭线

- 决策：`stage001_account_context_prelabel_contract_fail_sparse_position_history_close_line`。
- 正式入口错误码：`candidate_activity_days_zero`；首个失败为`2022-04-29 / rank11 / lc.GFEX`。
- 459行中有27行、16个月、11个品种候选活动为0；4个月正式rank10活动也为0。
- 32行、19个月在Top9下行日上的候选标准差为0；`2025-10-31`仅18个Top9下行日，低于冻结20日门。
- 14项测试通过；未创建pass或临时输出，未读取账户标签、未训练、未回测、未连接CTP、未调用订单API。
- 禁止删除失败行、缩短120日窗口、把零活动当零相关、下调20日门或按月份/品种救援。未来若有覆盖所有候选的独立PIT日收益/持仓模拟源，必须另立研究线。
