# Stage588 BDI单新斜率实验结案：有正向线索，固定晋级门未通过

- line_id：futures_full_market_long_signal_ai；模式day；时间2026-10-21 06:55 CST；分支codex/ai-training-data-expansion。非重要突破；独立正式C9月池，无生产A/B发布。
- 接受587独立全面审查的研究算术；关闭585这个精确BDI公式/头/筛选包，0资金回测。完整全市场高质量long、窄损及增加投注目标active，未达到。

## 调研与判断

579给原额度内同epoch重复信号的新批次加仓条件GO，明确浮盈不释放旧冻结F0、D.low不能取消更早的开盘加仓；580当前SGX绝对变化不能证明领先紧接夜盘，NO_GO；581历年同月与126动量不同但223已设计否决，未有足够新支持重开。root选择BDI作为这轮唯一新增信息，不同时实施三路线。

[原作者Bakshi等BDI增长研究](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1747345)及[原作者副本](https://signaltradinggroup.com/wp-content/WhitePapers/Baltic%20Dry%20Index%20as%20a%20Predictor.pdf)索引支持三公历月定义，SSRN直接403不冒称全文读通；[2013原作者新研究](https://www.mdpi.com/2227-7072/1/3/62)不是本窄损策略证明。[2024原作者中国期货预测BDI](https://www.sciencedirect.com/science/article/pii/S027553192400240X)不能倒过来引用。[AKShare维护者源码](https://github.com/akfamily/akshare/blob/main/akshare/index/index_spot.py)仅作真实获取通路；[Baltic最终变更公告](https://www.balticexchange.com/en/data-services/Circulars/market-announcements-/category-a/2018/circular-08-18---changes-to-the-baltic-dry-index--bdi-.html)约束2018-03-01定义断点。

我的判断：运价同时包含运输需求与船队供给，不能认定BDI上涨就应做多。新源与旧52/PMI有区别，本次出现条件正向线索；然而既定完整门未过，不能因主样本正或失败很小就改判稳定优势。六个新增斜率均负，约−0.02258至−0.03832，是原52之后的条件残差关系，不是普遍做空/做多法则或因果证明。

## 数据及整体准确性

582唯一公开GET HTTP200，852412B/4127行；583全源核及发行人原始披露固定锚点支持level整体：2016最低290、2021最高5650、年末2217三项精确。2016年均673.532258与披露673、2020均1067.845238与1066、2021均2943.38与2943的差保留，不强修；开年1366与首已存报价1374的口径差也不凑精确。数据不是逐日官方认证或历史首发PIT。原raw/name/价格均保留，未改坏年。

2006–10偏周频、2011后偏日频；2坏年、2周末隔离。仅price/date参与，混单位zdf不用。月内先选最后候选；若该endpoint在已冻结冲突名单则unknown，不退前。缺月清旧q，跨2009Jul/2018Mar制度段unknown，不插值/跨月carry。245来源月：233已知q、6跨段、4缺base、1冲突、1未完整；5587源u中4718有q，最大完整endpoint距月末9天（如年末假期，非假定每天都有报价）。

每个u仅用前完整公历月m的g=log(P_m/P_m−3)，u严格晚于m末，完整中国u后才到D。当前历史可知只是保守条件重建，英国同日值未回贴此前中国夜盘。今天新日线不是历史研究前置，只有原独立前向账依对应D收盘。

## 版本变更与固定参数

新增586隔离core/runner/8个必要小fixture；原52/训练目标与原权重算法/选月顺序/K/止损/risk/资本/成本均不改。A原预测冻结；B=A+known域残差常数；C=B结构加一条train-only标准化BDI斜率，常数也受lambda1惩罚。缺失B=C=A位级一致。fit用原w在known训练子集sum1；来源月等权只用于诊断，不能混说fit月等权。新增固定参数3公历月、60成熟来源月下限、lambda1，无收益后调参；旧参数修改/删除0。

两cutoff2020-01-01/2023-01-01×三scope×B/C共12小head，原训练月117/153，各fold先统一通过preflight再solve。原Ahat/Y/weight直接复用538紧凑缓存，不重读COMMON、334MBactions或native库。全98产品95family、161014前向母、1933480scope子保留，负分和无动作保留；966084完整三臂选择，不把重复scope或多个family复制的q算独立样本。

## 实际结果

唯一actual session75136，一启动一完成/exit0/79.473902秒，12新head，0原52重训、0A回放、0cash/SQL/新下载/CI。训练6指六文件各一次，A_choices2指两个既有输入文件各一次，不是重复回测。

以下是82个u日历月、family-u后等u再等月的已知支持**机会stressR增量**，不是账户收益率或权益变化；不同动作未明值不填0。

| 范围 | C−原模型A | C−同域校准B | 差动作未知CA/CB |
| --- | ---: | ---: | ---: |
| 主样本 | +0.001254418826 | +0.001257028790 | 2 / 2 |
| 跨品种留出0 | +0.002038052728 | +0.002049239022 | 1 / 1 |
| 跨品种留出1 | -0.000041246093 | +0.000191642252 | 1 / 1 |

主2020–22 C−B=+0.002295362142R，2023+ +0.000444420079R；主两期C−A也正。原B−A三个scope均负；不能据此去掉常数/改控制救分。八门7真1假，失败项held1 C−A=−0.000041246093R。其幅度小，也不提供改门理由；没有bootstrap统计显著性证明，更不能说BDI已让资金收益下降或上升。

**财务指标：期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A；本轮没有资金回测。** 4445个主C被选机会不是4445笔实际成交。新数据/模型也不证明0.25N止损损失上界或加大投注安全。

## 独立审查与结论

587唯一独审session57909，一启动一完成/exit0/49.850819秒，6137项核对、0失败，Critical/Important/Minor=0/0/0；核原源月q/时钟、12头原w/scaler/正规方程、全域选择/缺失fallback/诊断/8门。0模型、A或资金回放，0SQL/GET，各原数据只读一次；核对次数不是独立经验数量。

算术接受，策略筛选不通过。BDI源与投影保留作新观测，当前精确公式/窗口/头/控制及其资金后继关闭；不改符号、窗、lag、端点、常数、交互、learner、品种、stop/risk来救。正向已知支持只是线索，未知和同史选择风险保留，没有未碰过的OOS或稳定赚钱结论。

## 输出和下一步

- [机器决策](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage588_bdi_fixed_residual_root_decision/decision.json)、[实际manifest](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage586_bdi_residual_fit/actual_run1/manifest.json)、[完整机会诊断](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage586_bdi_residual_fit/actual_run1/held_diagnostic.json)、[全年度](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage586_bdi_residual_fit/actual_run1/calendar_annual.csv.gz)、[全family-year含零](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage586_bdi_residual_fit/actual_run1/family_year_including_zero.csv.gz)。2026仅到10月16日，年度切片不等于独立冷启动。
- [月源投影](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage586_bdi_residual_fit/actual_run1/source_months.csv.gz)、[全日历输入](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage586_bdi_residual_fit/actual_run1/calendar_u_bdi.csv.gz)、[独审接受摘要](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage587_bdi_fixed_residual_independent_review/actual_run1/acceptance_summary.json)、[全审查](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage587_bdi_fixed_residual_independent_review/actual_run1/review.json)。

下一步：按579先只测原家族/组合剩余风险预算是否容得一手同epoch重复赢家信号；若无实质机会则不建多批次引擎；有机会才冻结开盘/日内时序和独立新批次现金反证。保持原总风险，非加注资格。 这与BDI改参无关，也不直接扩大下注。没有实际可做空间就停止该执行草案，不为几笔微小差异铺引擎。

## 开始与结束反思

运行前过拟合风险：是且高，同一历史持续择题；新收益后救参：否。结束过拟合风险仍高，未把7/8改成及格或拿主正均值宣布突破。继续精确BDI包：否；这次新观测验证有价值：是（已得到改变下一行动的证据）；继续完整目标：是。累计547实际fit/282完成cash及1旧partial，目标active未完成。

root统一更新LINE/registry；普通负结果不追加根memory/back_log，不commit/push，不动正式/生产/CTP/邮件/调度。
