# Stage498：具名披露信息的来源、12头、完整选择与held独立复核

- line_id：`futures_full_market_long_signal_ai`；2026-10-21 02:06 CST；非重要突破。本代理未编写496/497作者实现，仅写独立reviewer；先读registry与本线现状，按495及root精确授权运行。
- 唯一actual session **93151**，真实工具 **exit0**，elapsed **132.999285875秒**；无自动retry、无审查器失败续跑。source/model/forward/held四phase全部完成并逐段持久化。
- 已核scope的实质P0/P1/P2均0。**不含现金核、native cache或旧A账；现金由独立500审查，不能将其范围写成本审查器认证。**

## 外部调研与自己的判断

494附录已核[上期所披露原文](https://www.shfe.com.cn/content/cxxc/7wsxx.pdf)、[官方公布标准](https://www.shfe.cn/reports/tradedata/dailyandweeklydata/dailyranking/decl/202401/t20240117_331641.html)、[维护者原代码](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/cot.py)和[经纪订单流原作者摘要](https://arxiv.org/abs/1108.1632)。本次不重复联网或下载；取舍是姓名与数量的原配对不同于匿名HHI，但不能据此识别最终客户或聪明钱。

尤其2013年规则统一前，部分品种可能含具名非期货公司会员；本包全历史只称交易所报告标签，不声称每个token都是经纪会员。不据会员类型更改样本、别名或模型。时钟仍是165的前一完整源日研究lag，不认证首发PIT。

## 来源与输入范围

独立核新170803个source scope稀疏贡献/时钟/身份，165413条来源可见action，966740条完整forward outcome。原规范162只开**固定首3物理scope行**，逐原名/ID、原side vector SHA、两侧总量与signed/gross贡献独算锚定；不是第二次完整规范源或原1.26GB raw认证。其余旧163全向量/原文解析资格明确继承。

核精确epoch、u紧前v、唯一scope、披露gross为正与规范和为1，未将未上榜者真实持仓设为0。来源实际仅SHFE/INE；完整六所98产品95family母体与missing/nochild仍保留。

原129和旧COMMON本轮均0重扫。目标值与原COMMON的原值资格/单次投影索引实现继承已接受链；本次用新来源可见COMMON切片、冻结52模型/scaler逐值核训练预测和残差，并核新两处forward Y拷贝自洽。**不把新拷贝自洽说成原129/COMMON全原值第二次独审。**

## 12头独立证书

B共同来源常数/匿名signed量差，C在冻结B残差上按原signed token输入，参数受`1'β=0`及`B'WZβ=0`约束；未在forward减匿名投影。各cutoff/scope只从本训练域建词表，held标签补集、严格成熟与共同eligible/K/source域逐身份核过。权重独立重建family-u区间union及uniqueness，随后sum1；是条件head权重重算，不是原52数字。

独立核全部12头正规方程、零空间基正交与全null覆盖、约束/df/trace、所有残差及冻结B系数，0 estimator.fit或重新求预测系数。source sparse流1，旧130分数流1；最大全部标量差 **2.273736754e−13**（年度覆盖质量累计），新前向score最大差4.44e−16，choice分数最大差1.78e−15；身份/资格/选择ID保持严格。

| cell | 训练行动 | 词表p | 约束秩 | 新增有效df |
| --- | ---: | ---: | ---: | ---: |
| main/2020 | 36726 | 261 | 3 | 0.022715286800 |
| main/2023 | 64191 | 384 | 3 | 0.020978992264 |
| held0/2020 | 21466 | 253 | 3 | 0.023407054549 |
| held0/2023 | 36260 | 350 | 3 | 0.021738917298 |
| held1/2020 | 15260 | 210 | 3 | 0.020065906139 |
| held1/2023 | 27931 | 357 | 3 | 0.018732867874 |

有效df很低而非0，说明这是强收缩规格；p个参数仍计入，不冒称仅估1个参数。不能从本固定头弱变化推断全部具名表征无效，也不因此结果后提高容量救分。

## 完整forward、选择与身份增量

一次原130分数流 **1933480行**，独立重建全部9张A/B/C×main/held选择。main A逐ID等于accepted156，held A绝对winner也独立重建，未仅继承旧held winner。完整161014主母及两个held共161014母保留。

逐值核220948条来源score bridge，以及全域年度产品/family来源可见/缺失、known/OOV质量与nochild报表。main每臂72480条可应用head、37994条有源但不在共同准入域fallbackA、856266条无源fallbackA，共966740主子行；两held合计同域。

root收到现金六位相同现象后，本代理只用刚生成的**6份新独算expected choice checkpoint**补充小摘要，无原source、旧score或模型重跑。该额外读取单列在摘要，不伪称仍为原内存统计；范围是共同选中/共同提案分数，不是全candidate score极值。

| scope | 母行 | B/C选中 | chosen变化 | selected变化 | 换月 | 共同chosen分数差范围(R) |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| main | 161014 | 4272/4272 | 1 | 0 | 1 | −0.000109285～+0.000192280 |
| held0 | 64077 | 2023/2023 | 0 | 0 | 0 | −0.000167155～+0.000182076 |
| held1 | 96937 | 3708/3708 | 0 | 0 | 0 | −0.000331659～+0.000396370 |

main确有一次换月，不能根据现金相同宣称所有信号动作完全不变。为何该换月未改变现金，需要500在其已有账本范围连接预算/成交事实；本审查器不追加现金回放、强制一手反事实或机会成本标签。

## held及置信边界

三对照×两个held的全部日/年known与unknown独算通过。C-B两held动作全同，等u已知差均0、不同动作未知0；同选中但自身未知26/39个仍保留，配对相消不等于其单笔收益已知。C-A两held已知等u差分别 **−0.000834372661R / +0.000396062947R**，不同动作未知 **2/1**；B-A相同。不能用负/正平均忽略未知或拼成未见泛化证明。

本阶段接受已核来源派生、头、全选择和held算术。没有认证八本现金/12CI、原始市场执行、容量、跳空封顶、法律身份连续、首发PIT或跨未来泛化。所有金融晋级门和主stress严格DD改善仍由root结合500结果裁决。

## 结果、变更与反思

本阶段新增实现仅独立reviewer/test及审查产物；新增/修改/删除策略参数和金融回测结果0。审查器3项toy一次通过0.021秒，未重复作者7/8/4项测试。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率、金融CI全部N/A：本阶段不是另一次现金回测，不复制497结果冒充本scope认证。

开始/结束新增收益后调参过拟合：否；长期同史适应性风险：是且高。继续一次固定对象的独立核验有价值且已完成；扩大lambda/词表/两侧token/交互/lag/stop/risk救这个包无价值。固定强收缩身份头未产生广泛选项变化，不等于具名信息普遍无效。完整全市场高质量long/窄损加注目标未完成。

原494正文/绑定、LINE/registry、正式C9、生产/CTP/邮件/launchd/Git未改。cash500范围独立，root需合并两张有边界收据，不能签无范围全scope0/0/0。

## 产物

- `outputs/stage498_member_identity_independent_review/actual_run1/review_receipt.json`：34918B，SHA`0dc57914545020231c09769da92f2c2a7b3863d1b1090a05f3e2012ea178f793`。
- `terminal.json`：16145B，SHA`8782583b7116f24f4b70f8658ae0d39227a1a3728da86c8d1812a00cccf464ae`。
- `C_minus_B_choice_effect_from_independent_checkpoints.json`：2521B，SHA`2250469b044d9f5b23e3c9a55b2e515cdf57295d271b12aa1907498ea5d75b04`。
- 四phase报告、每cell证书、原规范prefix anchor、独立expected九张choice和`execution_handle.json`均在同一actual目录。
