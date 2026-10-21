# Stage433：固定浅层 HGB 的原52维六fold拟合与完整K选择实现

记录时间：2026-10-20 19:27 CST。研究线：`futures_full_market_long_signal_ai`。

## 本轮改动

本轮是实现准备，不是重要突破，也没有真实回测结果。新增 `tools/stage433_fixed_hgb_fit_select.py`，只将原130 Ridge估计器替换为432冻结的浅层HGB；训练行、原成熟目标、sample_weight、原fold scaler、52维设计、六fold、156正分/K日期/家族优先选择及98品种95家族母域均不改。完整原子分数域1933480行；main与heldunion各161014母事件。

新增参数是432已经冻结的历史053HGB参数，未据本轮结果调参：max_iter100、learning_rate0.05、leaf7、depth3、min_leaf100、L2=1、bins127、seed20261018；禁止early_stopping、warm_start与native NaN重解释。删除/修改旧目标、特征、风控、止损与成本参数：0。

实现复用296/285的已接受缓存输入读取、原130 design52和held原target诊断、原156全池K selector；不重算旧控制、不重hash旧大表、不读SQL、不生成新标签。逐fold保存joblib、真实52维特征名的便携树、训练摘要与64条portable预测一致性锚点。原子分数一次流读、按fold批量预测，完整保留原identity。任何真实失败终态保留，无自动重跑。

## 有限验证

唯一合成fixture先RED（433接口尚未存在），落实现后GREEN。1次toy fit单列，不计真实fit；验证52维非有限值标准化0及missing旗标、固定HGB/便携树预测一致、错误维度拒绝、K门排除高分近月和heldscope保留。此fixture不是盈利证据，也未复跑旧套件。

真实fit=0，真实cash=0，SQL=0，新标签=0，市场API=0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均不适用；尚未运行真实六fold及现金账本。root绑定源码并签发authorization后才能执行。

## 调研判断、过拟合与价值

依照432已冻结的NBER非线性交互、tabular树模型及sklearn官方参考，此次只检验一个固定模型替换是否改善原执行目标；海外股票/通用表格优势不是本期货窄止损alpha证据。过拟合风险：是，已有大量历史试验且没有新未触碰历史样本；本轮不搜索深度、叶数、seed或阈值，不能消除历史择题偏差。继续价值：有，原最终52维childtarget尚未做这一固定浅模型的精确对照，最多六fit与main改变后的四cash可反证该包；若失败即关闭此固定包，不救参。

## 后续

root冻结源码后真实六fit、原全域预测与完整K选择；只要main chosen_action_id改变，按432另行准入四个候选cash账户，held first-exit-R诊断不代替K现金估计量。随后435独立复核数据、逻辑、结果与置信度。正式C9、原四个前瞻paper账户、生产任务与投注均不变。

## 2026-10-20 19:35 CST：唯一真实运行完成补记

root启动的唯一实际session30061已exit0。`actual_run1/terminal.json`确认 completed，耗时118.922秒，fit_attempted=fit_completed=6；没有自动重跑。加上先前454次，累计真实fit460次；本阶段cash0，现金累计仍246次及1个旧未完成金融尝试，434现金结果另记，不能提前计为完成。

运行版本：sklearn1.6.1、numpy2.2.3、pandas2.2.3、joblib1.6.0；绑定432协议SHA45c93399f2d6552a77805c9ca5bce9568b8e32522a5b6cdf5c289de11dbe847d，原129/130数据至2026-10-16、原训练CSV与scaler不改。六fold训练行按原顺序247795、445475、171712、297404、76083、148071，各100轮。原training CSV各读1次（共6）、common1次、旧childscores1次（1933480行）、母表1次、控制choices2次、原成熟label只投影1次；新标签、旧控制重训、旧大表rehash、SQL、市场API均0。

全域1933480个子分数identity保留；main与held union完整母事件各161014个。main chosen_action_id改变4898，held改变7014。依预设仅意味着四cash操作准入；不是正收益或超越旧模型的证据，也不按此改变阈值。六fold共384个（每fold64个）训练锚点的sklearn与便携树预测最大误差0；**这不是1933480个前向分数的全域portable重算证明**。

held original first-exit-R诊断：holdout0已知等u均值增量+0.003842623754178989R，差异未知32；holdout1为-0.017261521461299542R，差异未知41。两个组unknown_R_bounds均null，整体不支持跨家族非伤害结论；该估计量不是K持有现金收益，依432不得把它用作提前cash veto。所有年份与未知原样保留。

本阶段无金融回测：期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均不适用。此时只能确认模型与完整选择已经产生，不能说明盈利改进、加注或实盘资格。后续由434唯一四cash及435一次独立复核决定此固定包去留。

运行后过拟合判断仍为“是”：固定单一模型没有消除历史多轮择题风险，不能据held好坏改参；继续价值为“有，完成预先约定四cash反证”，此后若失败不救本包。
