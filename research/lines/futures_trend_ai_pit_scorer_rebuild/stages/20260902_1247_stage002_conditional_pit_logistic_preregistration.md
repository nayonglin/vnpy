# Stage002 条件PIT逻辑回归基线预注册

- line_id：`futures_trend_ai_pit_scorer_rebuild`
- 记录时间：2026-09-02 12:47 CST
- 阶段性质：数据边界修复后的正式同构逻辑回归基线
- 是否重要突破：否；本阶段不选择候选、不运行策略回测
- 证据等级：`fixed_current_design_universe_only`
- 生产/CTP/订单影响：0

## 唯一变化

相对旧正式评分器，只允许以下三项数据修复：

1. 删除不足60个未来交易日的标签样本。
2. 在每个fold中仅使用`future_label_end_date < test_start`的训练样本。
3. 按`max(官方上市日, 首条有效OHLC日)`先过滤当月品种，再计算future-rank、二分类target和sample weight。

模型、108项历史滚动特征、`StandardScaler + LogisticRegression(C=0.20, solver=lbfgs, max_iter=3000, random_state=42)`、720/180自然日窗口与180自然日步长均保持不变。

## 冻结输入

- 旧samples SHA256=`4cbc9952a1dac4373ac1901f958b914ac1d3495e56873c21cc6187548a60311d`。
- 旧daily SHA256=`9af514a3a5ab7ca4d982a31bd758522c32c4dec792f1b1819abb5462a391efcd`。
- 旧window metrics SHA256=`869d634e1e56b99cac6f28cf4e0108942c104648b4cedd91fc8ee9961fee0da3`。
- Stage001 sample boundary SHA256=`5c3a5d5484869b126face7bd9ed24ae4cc6d0f2e5d3ee75d5d6f8604552cda87`。
- Stage001 fold audit SHA256=`0632a9b33dd86660a34ca8f838888a19794271344cf3e1f64df3a1317893a470`。
- Stage001 listing audit SHA256=`e968fefc17954239d7acf92b5800489536b3f32610b481fd5a51b17b30102823`。
- Stage001 universe audit SHA256=`cb4de4e24af6264da503f39723bc358bfbff5e3c0990db6c77aecbd1aa03e2c1`。
- Stage001 summary SHA256=`9a95f0ea82236a311dd140652ec21cb75160f92f39050b8197a7d817d67da688`。

## 冻结数据与fold合同

- 特征列仅取旧samples中以`_20d/_60d/_120d`结尾、且不以`future_/target_/sample_weight_`开头的108列；不得看结果删特征。
- target固定为当月PIT合资格横截面`future_net_pnl_60d`排名高于中点；weight固定为距中点绝对值并clip到`[0.20, 0.60]`。
- 测试窗口沿用旧9个calendar fold；完成过滤后仍要求train行数`>=180`、test行数`>=45`、train/test target均有两类，不满足的fold机械删除。
- 训练和StandardScaler只能看到本fold净化后的train；测试标签只用于阶段后评估。
- 所有有效fold独立拟合两遍；预测、scaler与系数必须确定性一致。

## 技术通过门

1. 冻结输入运行前后SHA一致。
2. 特征恰108项，任何feature名不得以未来或标签字段开头。
3. 有效fold不少于7、OOS月份不少于40。
4. train/test中未上市样本、非完整60日标签均为0。
5. 每fold训练标签结束日严格早于测试开始日，PIT违规0。
6. 两次训练最大预测差、scaler差、系数差均不超过`1e-12`。
7. 概率有限且位于`[0,1]`，每月候选唯一且不少于10。
8. 原XGBoost研究线sealed holdout标签读取0，策略回测0，CTP/订单0。

## 效果解释边界

- 本阶段会报告AUC、月均Rank IC、Top10未来净利润代理及尾部分位，但这些指标不设晋级门，也不得解释为组合收益或回撤。
- Stage008既有证据已经表明产品贡献代理与真实账户边际结果相关性很弱；本阶段只建立公平基线身份。
- 技术门通过后，仅允许Stage003用同一clean samples、同一fold和单一冻结XGBoost参数做预测层A/B/C；不得根据本阶段指标挑特征或改C值。

## 运行前反思

- 是否过拟合：本阶段**否**；数据修复规则来自时间因果和上市事实，模型参数完全继承正式逻辑回归。
- 是否值得继续：**是**；若连同构LR都不能在净化fold上稳定重建，XGBoost没有公平接入基础。

