# Stage019：018确认入场代码与实际结果的唯一独立审查

line_id=`futures_full_market_long_signal_ai`；2026-10-18 12:16 CST；审查人ema_financial_overall_review，未写018。先读registry/LINE、冻结015及017有限数学证据；只写本文和`outputs/stage019_entry_confirmation_review/`，016及其他源不改。非重要突破。

## 裁定

**接受018在015固定连续理想代理合同下的计算；不通过高质量筛查，不认定已发现确认入场增量。Critical/Important/Minor=0/0/0，无待修项、最小修复N/A。** 不是实际金融策略审计或数据重新定价，也不证明CONFIRM真实更差。冻结源码480行与测试127行均逐行阅读；随后仅一次独立全表数值审查，没有调用、导入018入口或复用其计算函数。

源SHA `e50126b4833b21005b775e41209c89e9a762b705159762f3b8bd2233c37aacb2`；测试SHA `dfb0b92833bbd37097458ef0ec9f17fffe58c98532c9c21e9d1fdf0c025cfd6c`；015 protocol SHA `73c991c2ed2c4d4dbc77147705b6f09d834e63c05d7a8b0f614a902c1b6ec5e9`。018最终manifest SHA `0d0bce1477ca430f85f1720005715f73318e6199a152bcfbad61d1847e018b8f`，events SHA `a61cf6718b1179fab6bf824ab8ba6cbc93485a53361ed0e4240987e56f91bf6a`。完整绑定见审查receipt。

## 真实执行和验证范围

018第三尝试12:12:59—12:13:24，24.905924秒，exit0；累计attempts=3、completed_full_experiment=1。前两次分别因完整源日历后继被报告区间截断、归一化浮点触边与原价不一致而在输入断言退出，失败快照及终态保留，不能写成一次无失败启动。最终4 tests GREEN、compile两源的真实记录已读；本轮不再运行作者tests。

019独立脚本实际session **71787**，`3dfdb3 → 67e33e → a4ba87`，exit0，**12.742710秒**。纯Python/pandas/NumPy读取已绑定gzip缓存、4074日历及小证据；0 SQL、0大DB hash、0下载/provider、0 fit、0金融。终态最小结论已先发root，之后才写本文。

- 全399252事件身份、原顺序、98产品/4074源日期、真实epoch、原D、long方向、family去终端_F和hash%2分组完全一致。所有未ready/未知保留；194709 ready，194168可评价，541 ready未知=460 missing_D+81右删失。尾部D可以为10/19，但报告日期仍截至10/16，未知不补成熟日期。
- 对全部194168可评价行回指004 u.high、009 ATR/OPEN gross及audit原价；重算7个布尔触边位、closeR与四坐标，再独立重算基础和压力两政策区间及配对外界。确认3行归一化OPEN触边与原价谓词不同；原价结果全部吻合已接受009。没有epsilon、tick吸附或改策略阈值。
- 23055 gap行按共享同一路径差精确0；72309日内确认行保留入场前low可能性，收盘必穿stop分支独立核对；98804确定未触发行CONFIRM真0且不收费。205084不可评价行的数值列为空，未冒充未触发或0结果。
- 六份daily文件全单元与NaN mask重算一致；三个cohort各17年度及2010+/2020+的计数、日期等权均值、区间宽度、未触发右尾成本均核一致。每u p以同cohort共同已识别分母计算，主表逐行p也全核。group只是事前hash异质性，不叫训练留出。0.2R与1R同p成本在每日抵消，两边matched participation区间一致。
- 两段源日历保留空日期。独立用区间前缀和与有效计数重算60日×2000移动block bootstrap，共享index SHA一致；全部报告CI最大绝对差`2.4424906541753444e-15`。事件/日统计最大差`8.881784197001252e-16`，没有丢空日再拼新日历。15门全部重算一致。
- 所有D坐标、原价比较位、填单状态及结果区间列在manifest明确为label_only；输出无原始绝对OHLC，不能把归一化D信息回填u特征。小上游manifest/receipt/spec闭合另以真实bytes/SHA确认。

## 结果与置信度

主区间2020+有107844 ready/107437已识别，407未知；源日历1643日、可评价1642日。CONFIRM填单53250行、1642日、87family，按日等权填单率49.6674%。仅样本日期/family两门为真，其他13门为假。

| 2020+固定代理量 | 结果 |
| --- | ---: |
| CONFIRM边际均值区间 | [-0.401270616, +0.086140717] R/机会 |
| 同路径配对外界均值 | [-0.322316342, +0.273532279] R/机会 |
| 配对lower 95%CI | [-0.352973372, -0.281091929] |
| 配对upper 95%CI | [+0.252770163, +0.298193358] |
| 同参与率差均值外界 | [-0.414278956, +0.126848657] |
| 1R压力CONFIRM lower均值 | -0.798609555 |

配对外界横跨0；“lower统计量的CI为负”**不是“真实差异CI全负”**，无法据此证明确认更差。高成本下相对OPEN的优势可来自少成交省预算；同参与率差成本抵消，不能把省交易次数冒充质量增量。quality_screen=false、entry_increment_detected=false仅是未达到预声明稳健门，不是所有确认入场、AI或真实市场均无效。

## Declined to judge及继承边界

交root裁定且不新增阻塞：真实tick/跳价/排队/容量/费用和经济PnL；配对外界是否全局最紧；不同setup、未来泛化或所有AI alpha；原日线大库的逐价重新认证。017的742有限网格+5具名oracle只是数学佐证，不把它外推到离散真实交易。继承015/017已实核的[Backtrader原作者源](https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py)及[官方执行说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)：open越过阈值与盘中触达须区分；本轮未重复外搜，没有把模拟器假设当中国期货成交证明。

无新/改/删策略参数或回测结果；权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率N/A。financial_ready/real_economic_labels_ready/production_qualified均false。开始与结束新增过拟合**否**：固定一轮审查、不按结果挑边界或救参，历史研究选择偏差仍在。继续价值**本次审查是、继续挽救本固定筛查包否**：已可归档可信负筛查结论，保留路径未识别的诚实界限；不以数学一致性冒称发现高质量做多或加注依据。
