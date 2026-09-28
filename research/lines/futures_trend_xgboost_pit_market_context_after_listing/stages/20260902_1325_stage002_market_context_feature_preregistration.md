# Stage002 上市后PIT市场上下文特征预注册

- line_id：`futures_trend_xgboost_pit_market_context_after_listing`
- 预注册时间：2026-09-02 13:25 CST
- 是否重要突破：否；无标签特征合同
- 策略回测/CTP/订单：`0/0/0`

## 单句假设

候选相对正式Top9与rank10的历史市场相关、下行依赖和组合路径差异，能提供旧108项策略执行/损益特征没有的紧凑PIT信息，并且可以在不读取未来标签时稳定构造。

## 冻结输入与样本

- Stage001 `ranked_a_panel.csv` SHA256=`1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2`。
- Stage001 `coverage_by_eval_product.csv` SHA256=`54eab60914d94dbf90f64b8cf266263eeaa8d17d29007e0c1849e8a0097f57b7`。
- Stage001 `month_activation_audit.csv` SHA256=`0f18589174f65ad3014797fcb2fe932480090c104b1667eec8e66b6a37871f93`。
- Stage001 `artifact_manifest.json` SHA256=`dd6bae8f310c2d061fe5caed876b43ffa8a1f32060099f441633e4e930ef00b7`；PIT收益继续使用Stage001已验证的`product_daily_returns.csv.gz`，SHA256=`ff31d1bdf3ea3d8a309060243d165e82b5e7a0a8e26d26ba17f4a0ec926056fa`。
- 样本只取43个`overlay_active=True`月份中窗口完整的rank10和挑战者，预期328行、43月，其中rank10 43行、挑战者285行，每月6至9行。
- Top9成员仍来自同月Stage003条件PIT LR A排序；任何不完整产品、四个非活跃月和其他A成员都保留在Stage001审计，不进入本阶段特征矩阵。

## 冻结计算

对每个活跃月`t`，取不晚于`t`的最后120个全局收益日。Top9九个产品的等权日收益记为`h`，A rank10日收益记为`b`，当前候选日收益记为`c`。要求每条序列120日完整、有限，且单日收益严格大于`-1`。

- `corr(x,h)`：Pearson相关；两侧样本标准差必须大于0。
- `down_corr(x,h)`：只在`h<0`日计算Pearson相关；Top9下跌日不少于20，且两侧标准差大于0。
- `vol(x)=std(x,ddof=1)*sqrt(252)`，必须大于0。
- `down_dev(x)=sqrt(mean(min(x,0)^2))*sqrt(252)`，必须大于0。
- `q_x=(9*h+x)/10`。
- `dd(q)=min(W/cummax([1,W])-1)`，其中`W=cumprod(1+q)`，因此`dd<=0`。
- `sharpe(q)=mean(q)/std(q,ddof=1)*sqrt(252)`，标准差必须大于0。

六项特征固定为：

1. `candidate_top9_corr_120d_delta_vs_rank10 = corr(c,h)-corr(b,h)`。
2. `candidate_top9_downside_corr_120d_delta_vs_rank10 = down_corr(c,h)-down_corr(b,h)`。
3. `candidate_volatility_120d_log_ratio_vs_rank10 = log(vol(c)/vol(b))`。
4. `candidate_downside_deviation_120d_log_ratio_vs_rank10 = log(down_dev(c)/down_dev(b))`。
5. `top9_plus_candidate_compound_drawdown_improvement_120d_vs_rank10 = dd(q_c)-dd(q_b)`；正值表示回撤更浅。
6. `top9_plus_candidate_sharpe_improvement_120d_vs_rank10 = sharpe(q_c)-sharpe(q_b)`。

rank10行以`c=b`按同一公式计算，六项必须逐位精确为0，不单独硬编码。禁止月内z-score、缺失插补、winsorize、标签后选特征或改公式。

## 预声明技术门

- 输出精确328行、43月、6项特征；rank10/挑战者精确43/285行，每月6至9行。
- 所有特征、基础统计和日期均有限；rank10六项精确0。
- 每项特征在挑战者总体至少10个唯一值、标准差大于`1e-12`；8个fold内每项均至少出现一个非零挑战者值。
- 所有月份Top9下跌日不少于20；窗口精确120日且末日不晚于`eval_date`；future rows used为0。
- 双跑逐值与发布SHA一致；Stage001及PIT收益输入运行前后身份稳定。
- 只按白名单读取Stage001排序/覆盖列和PIT收益列；未来标签、未来损益、sealed holdout文件读取0。

## 固定决策

- 全部门通过：`stage002_market_context_features_pass_ready_for_ranker_preregistration`。
- 任一门失败：`stage002_market_context_features_fail_stop_no_ranker`。
- 通过只授权Stage003预注册月分组XGBRanker；不授权训练、回测、holdout、生产、CTP或订单。

## 运行前反思

- 是否过拟合：本阶段**否**；公式由组合风险语义和Stage001覆盖事实决定，不读取效果标签。若看到特征分布后换窗口或删特征救援，则会转为**是**。
- 是否值得继续：**是**；这是确认新信息源实际非退化、可计算的必要门，成本远低于直接训练。
