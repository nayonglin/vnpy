# Stage139 已接受资金账本差异归因设计输入

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 23:08 CST；独立设计，非协议/实际结果，非重要突破。
- 已读registry、LINE末段、138、137一个账户收据及136一个账户的表头/首行；未读大actions或DB。
- 只设计复用旧AI4+新增84个已接受账本；新增fit/SQL/cash/标签/行情下载均0，累计391fit/202cash不变。纯归因不触发晋级A/B；133 unsupported、138八CI跨0及不加注边界不变。

建议只做一次严格回加的CNY会计桥，解释等权动作R与账户资金的错位。它能定位增长差记在哪些已成交root上，不能识别AI选月因果中介或创造新退出路径。

## 调研与判断

[Shapley原论文出版社条目](https://doi.org/10.1515/9781400881970-018)提供对称分配背景；出版社只有导言，全文镜像获取超时，未声称通读。以下公式是直接可验的二因素恒等式，取两种代入次序各一半，不借博弈论赋予因果解释。[Backtrader作者维护的期货盈亏代码](https://github.com/mementum/backtrader/blob/master/backtrader/comminfo.py)分别处理数量、价格、乘数、费用和保证金。采用其经济单位纪律，不复制策略。

我的判断：跨月raw手数混有N/单位初损/费用风险，不能直接叫加注。主分解采用初始冻结风险CNY与每风险单位实际贡献；raw数量只作辅助。分量依坐标选择而变，不是唯一经济原因。

## 全域、身份与窗口

共同domain固定root绑定的sourceB main selected全部4917个parent，实施先核对数量、唯一性；不按实际入场筛选。母键保留mother_event_id、family/product、u_index/u_date；root_id仅作账户内身份，不从其字符串猜母键。

每账户保留outsidewindow、knownreject、entry_execution_unknown、已成交状态。沿用绑定5587源calendar的u_index∈[start_index−1,end_index−1]，保留cold start前一源日预留，不能用u_date>=start截断。新入场reservation及无budget_kind拒绝行均保留；只排existing_position_reduction的新入场身份，减仓盈亏仍归原root。

四组各做AI−MAXVOL及AI−每个随机，共84配对；主展示2020/stress，其余三组并列，不选优，也不称四个独立市场实验。

## 先闭合root贡献

闭合root：C=net_pnl，交叉核对realized_gross−entry_fees−exit_fees。开放root：C=realized_gross−entry_fees−exit_fees+unrealized，包含此前减仓的已实现贡献。q=initial_qty并与初始BUY核对，不能用闭合后0或末端剩余qty；SELL归原root。

所有root的ΣC必须回到terminal_equity−initial_capital，并与daily gross/fee/unrealized核对，沿用137固定容差；不闭合先停，不设残差桶补平。滑点已在成交价内，禁止重复扣；margin、reservation、notional不算利润。closed/open、stale均保留。

无BUY的ledger_C=0只表示模型账本无头寸，每手或每风险收益仍未定义；现实执行未知不能补0。缺乏reservation/rejection/unknown证据时标完整性未知，不能仅凭closed/open无行认定已知拒绝。

## 参与层与对称二因素

逐共同domain母信号分成：双方未入场(账面差0)、仅AI入场(+C_AI)、仅对照入场(−C_ctl)、双方同月份入场、双方不同月份入场。单方贡献可正可负，不给未入场一边造单位收益。仅双方入场进入二因素。

同月份核对epoch/event_id/entry_date；不同月份须同母信号、同exact product。应一一对应时若多root/多action先报错，不任意撮合。同动作再标规范化路径相同/不同/不足判断；路径含日期、成交/reference价格、退出原因、每初始手费用、SELL占initial_qty比例、anchor请求及末端mark/state。不能按root_id或绝对qty判路径差。同动作但路径不同仍不是纯AI选月效应；路径相同也不消除执行未知。

双方已入场时，F=q×risk_per_lot，Y=C/F。risk_per_lot须为该root初始冻结值，与初始预算/BUY核对且未被后续预算覆盖，不能用末端剩余风险。q、单位风险、F须有限且>0，失败不fallback。

`ΔC=(F_A−F_B)×(Y_A+Y_B)/2+(Y_A−Y_B)×(F_A+F_B)/2`

两项分别叫“账面初始冻结风险份额项”“每风险单位实际贡献项”，在同月/不同月层各自汇总，逐母、分层、配对、账户验证回加。F不是最大亏损保证；Y包含实际减仓、费用和未实现，不是135独立动作net_R标签。

辅助可给p=C/q的同形数量恒等式：ΔC=Δq×平均p+Δp×平均q；跨月不将数量项解释为纯仓位价值，同精确动作也不称可复现的加注收益。不把F_A×Y_B或q_A×p_B当作可执行反事实，不嫁接另一账户的退出。

## 随机均值、未知与描述输出

先逐一完成20个配对，再平均20个CNY分量，其和等于AI增长−mean20随机增长；不能先平均F/Y再相乘。全部随机保留，不选中位/最佳/AI获胜子集，MAXVOL单列。本桥解释CNY终值差，不替换138日log CI，不新增bootstrap或显著性检验。

未知标记叠加于完整会计表：任一侧entry/capacity_unknown、ever_stale、terminal_open/stale、deferred/request等，并给对应CNY差。模型金额能精确分解，真实执行贡献仍未知；已知子集不是剔除未知后的可交易收益或下界，同动作不能据此声称未知已抵消。

最少交付：完整root/母信号桥、84配对分量、四组AI−mean20/MAXVOL摘要、闭合/身份/未知质量报告。摘要同时给正负金额与净差，净差近0不靠比例制造解释。

品种全量列示；按u_date分组只能叫“入场信号cohort年”，root整个生命周期贡献归其来源年，不能叫实际年度利润。实际年度利润从daily年边界权益差描述；若按root拆年度，需已有fills/position marks的日级已实现及未实现变动。尾部仅描述、保留全表，不删赢家、不据年度/品种/尾部新设过滤器。

## 反对意见、继续价值与反思

共同入场是资金路径之后的条件集合，分量受历史复利、占用、整数减仓、退出反馈影响。每风险单位项为正也可能混入路径/估值，风险份额项为正也不证明加风险有效。该桥不能证明全市场准入、全负分不参与或B−旧A全部价值。

值得继续一次：是。现成账本足以低成本区分参与差、风险权重与单位贡献，并发现漏open/重复成本等会计错误。若闭合后仍不能分开经济解释和路径反馈，应接受“描述已解释、因果未识别”并停止，不能为讲清故事增加训练或反事实重放。

开始和结束新增过拟合判断：否，无拟合/扫参/择优；历史反复择题和事后叙事偏误：仍是。继续这一次有限解释：是；继续种子/月份/风险/止损救参：否。全市场稳定高质量做多、极窄损与加注资格均未证明。

仅新增本stage；脚本、策略参数、既有结果均未改。4917域、F/Y和分层是待root冻结的归因控制。本次权益、收益、回撤、Sharpe、滑点、交易数、胜率未新增或重算，仍见138完整88表；没有139实际数值或实际结果独审。本文不授权fit/SQL/download/cash。不改LINE/registry/旧源/根总账，由root合入。
