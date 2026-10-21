# Stage200：相邻真实合约月价格偏离的单次源资格协议

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-19 18:47 CST，协议先于任何新X投影冻结于2026-10-19 18:42:03 CST。
- 工作区/分支：`/Users/mac/Desktop/fian` / `codex/ai-training-data-expansion`；独立全市场做多研究，不改变正式月池或生产。
- 非重要突破；这一步仅纯X资格，不触发正式A/B。完整目标仍是更高收益、更低回撤、全市场高质量做多，再分别验证窄止损与加注，尚未达成。
- 上一goal轮为progress：198完成历史去重、199完成主源/开源核查并提供负证据、200单假说冻结。中断后确认201仅新fixture已写、源码及actual目录尚不存在，当前恢复实现，不是重跑旧数据或模型。

## 调研与判断

198确认实际尝试过期限单日收益对tenor的线性梯度（049—056），以及同步相关×滞后冲击；COMMON52保存近前两点basis及其前值、peer无序收益摘要和期限跨度，没有保存query相对相邻月份的当前价格局部偏离。旧收益斜率改二次项、把一日basis-momentum重命名都不推荐。

[Boons/Prado作者论文页](https://onlinelibrary.wiley.com/doi/10.1111/jofi.12738)讨论basis-momentum与期货曲线/中介风险；它不是本静态局部特征的收益证明。[Bianchi等原论文](https://arxiv.org/pdf/2308.00383)的curvature多空策略在更高成本情景转负，强证据在slope-spread且部分来自空头腿，不能背书本线long-only首触退出。[RBA研究](https://www.rba.gov.au/publications/rdp/2017/2017-03.html)支持期限风险溢价跨商品/时间变化，不能推出固定曲率方向。

[GitHub作者实现](https://github.com/stefan-jansen/machine-learning-for-trading/blob/main/case_studies/cme_futures/03_financial_features.py)可借鉴同日原价/null处理，但等距二阶差分不能直接用于不等合约月距；本轮不复制其×12缩放或把其展示当期限校准。199主源共两轮7查询，已收口，不扩下载/克隆/依赖。

判断：新q在数学上可以超出COMMON52保存的信息，但价格弯曲也可能来自季节性、非流动性或测量，经济独立和做多预测性均未知。值得一次不看盈亏的现有输入覆盖/几何检查；当前不凭文献、漂亮覆盖或更复杂模型直接启动训练。

## 唯一固定问题与数据时钟

每个exact `product_id/u_date`，只取129已有、当日finite positive `u_close`且完整YYYYMM合约月首严格晚于u的quote。129静态源码表明invalid u bar在`u_close`赋值前return，而history_ready/economics/未来label检查在其后；不再以这些未来/交易状态过滤quote池。

对入池query q，按完整月序数 `m=12*YYYY+MM−1` 找严格相邻的较早L和较晚R，定义：

`q_raw=log(Fq)−[(mR−mq)*log(FL)+(mq−mL)*log(FR)]/(mR−mL)`。

同一product/u若pool出现重复名义月则整组unknown，不任挑一条；端点、缺价、非正价、query未入池均保留unknown，不外推、不填0、不跨品种、不看未来补quote。月坐标只是交割月代理，不能称精确到期或法定账户截止。q是dimensionless log chord偏离，不是年化二阶导、无套利估值偏差或库存冲击。

输入由已接受129绑定：全1,552,456 action与399,252 mother/98代码/95family/六所均保留；action仅白名单10列identity/u_close，mother仅7列identity。禁止读取收益、标签、实际成交、进出场、未来价格或SQL，禁止重hash旧大库；输入继承SHA与尺寸、读取前后stat，新产物记录独立binding。

输出全域q向量、action身份/邻月/间隔/状态、完整mother含no child、年份/产品/状态覆盖，以及少量按稳定身份取的机械anchor。覆盖统计不看盈亏、不据最差/最好年份或品种修规则，不拿跨子月重复当独立经验。

## 实现、验证与终止边界

201补纯X脚本及少量新fixture；验证不等月距、log-affine为0、共同乘价格单位不变、缺价/端点/重复月闭合、全身份及nochild。构造既有COMMON不变但局部q改变的几何见证，仅证明非冗余，不能称真实alpha。202独立只核关键源码/fixture及实际小summary、coverage与有限anchor，不再全行重审旧价格或模型，不为小展示问题反复跑。

唯一actual由root在源码冻结、核心预审通过后启动一次。预算 `1 projection / 0 fit / 0 cash / 0 selection / 0 SQL / 0 download`。协议本身不授权金融；source接受后若值得继续，须另冻结单一完整信息实验。197已确认130 COMMON52模型/全域分数、156/157共同K main选择/四本资金可复用，不重训/重放旧控制。

后续若使用q，候选训练内标准化、缺设计0的均值插补须事前确定，不追加新的可学习来源missing；该处理仍不保证无隐式可用率代理。不扫符号、窗口、年份/品种、模型或风险来救旧登记/会员/曲率包。

## 记录与反思

本协议只新增q定义与纯X输出规格，没有修改/删除旧参数、代码或回测。新增/修改/删除回测结果均0；期末权益、总收益、最大回撤、Sharpe、滑点、交易次数和胜率均N/A。实际训练/现金仍累计421/226；source actual尚未启动。`production_qualified=false`，无晋级或加注资格。

开始是否新增收益驱动过拟合：否，不看盈亏/不新择阈值；历史反复择题与档案PIT代理风险：是。继续价值：是，仅限这一次有界几何/覆盖证伪；直接训练或用已失败收益斜率换名重开：否。结束反思待203实际源决定，不预先签通过或盈利。

协议：[protocol.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage200_local_curve_qualification_protocol/protocol.json)，4439B，SHA `944f1b91312898d55d99b96995d665d737f64f41caa23115fadaf167fb0aa180`。
