# Stage204：相邻月份便宜方向的一次53槽信息证伪协议

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-19 19:04 CST；协议于2026-10-19 19:01:33 CST先于新fit/cash冻结。
- 分支：`codex/ai-training-data-expansion`，不新建分支/工作树。非重要突破；独立全市场AI研究，不是正式C9组合、发布或生产A/B/C。
- 完整目标仍是更高收益、更低回撤、全市场全品种高质量做多，再分别检验极小止损与加注。本协议不放大风险，不以低成本小包代替最终目标完成证据。

## 203源接受与继续判断

201唯一actual exit0、44.224015秒，完整1552456action/399252mother均留；1082980q可算、97个有行情代码全部有支持，98个目录代码/95family/六所及186400无child母体保留。202仅关键源/3个独立小fixture/完整小覆盖汇总/16机械anchor审查，剩余核心阻断0、anchor最大算术误差0；不冒称重新全行定价/PIT或流动性认证。203 decision SHA `bfc98101d298e96deff135362a329c3a5ab5ae9b61a708bac0197a1ff5a1c5f6`接受**纯X几何资格**，当前0新fit/cash，累计421/226。

198/199原论文与GitHub已核：旧期限收益线性梯度和一日basis变化不能换名重开；静态价格局部偏离不由COMMON52唯一决定。曲率多空文献较高成本负、且收益可能依赖short legs，故没有正向long-only外部背书，先验弱。root没有将覆盖通过当alpha置信提高，而是选择一次有限反证：相同标的不同交付时点的价格关系是可观察的新约束，query相对邻月便宜可能代表时点需求/风险承载差异，但也完全可能是合理季节/非流动性溢价，做多首次退出不改善即可否定。

这个继续判断比199的“暂不直接fit”更主动：新增训练只用于否定一个事前限定的便宜方向，不为弱题目铺系统/扫描参数。若训练方向已不稳就省去全部资金工程；不据漂亮几何强行相信收益。

## 唯一假说、模型与提前停止

假说：在既有COMMON52控制下，query相对严格相邻名义月份的q越低（越便宜），原首次退出`net_R_stress`条件期望越高；只检验一条线性、跨期/跨family同方向关系。

候选53槽=原130 COMMON52＋唯一q标准化值。本fold原训练权重下，仅finite q计算加权均值/总体方差，已知q标准化、缺失设计精确0；不加来源missing输入、不clip、不改原COMMON/scaler/样本、不按q缺失过滤动作。原COMMON自己仍含缺失/期限状态。这里检验q＋固定插补处理的总预测包，与固定纯52控制相比，**不声称数字与覆盖机制的因果隔离**；均值插补仍可有隐式availability代理。

同原130：alpha1/intercept/cholesky，main/held0/held1×2020/2023六fold。训练只原成熟129first-exit stress目标，u及known时钟严格早于cutoff；held按既有family哈希。六个COMMON scaler与原训练index/sample_weight表直接复用并匹配identity，不重训对照、不重算旧权重，不为共同K改标签。

必须先完成六fold q有限正方差预检，再各fit一次保存portable53、scaler、正规方程及精确计数。**六个q系数全部严格<0才允许前向预测/选择/现金。任一>=0或非有限，六fit后以completed_hypothesis_rejected正常结束、0预测/选择/现金。** 不将反向当新发现、翻sign、缩scope或refit救它。这个方向门不宣称全部曲线信息无效，只否定此有限便宜方向/线性包。

## 仅方向门通过后的预测与资金

候选完整main966740＋held union966740 child分数、main/held每域161014母全部保留，含q缺失、原资格不足和无child。相同原score>0，155共同K先过滤再母内argmax、普通/F固定family优先、anchor及K退出不变。

旧控制主域直接复用130模型/分数与156main K选择、157四本K现金，不预测/回放旧控制。197未找到纯52 held-K选择；新比较科学上必要时只对130既有held分数补同K选择，0fit/cash，不能借口补清单重算main或旧模型。held差沿130原target、family-u再等u；same action未知增量精确0但披露，distinct unknown不填0，原目标未被K截断，诊断不是资金收益。

最多4本候选独立资金：2020连续/2023独立冷启动×base/stress。100w初资、0.25N初损、单family0.25%/总风险2%、buffered margin25%且buffer1.1、1%参与、原tick/fee/slip/anchor/无固定止盈不变。132 native cache与旧131/157/191同K执行复用，0SQL/新价/分钟/旧资金重放。每本自身资金递推，不用独立事件R或事后匹配成交拼资金。

主2020 stress必须收益严格增、DD严格浅、配对日log CI下界>0；其余三本自身收益>0且收益/DD不比控制差，四个配对CI下界均>0；held0/1已知等u增量均严格正且distinct未知0。沿070同block-bootstrap索引；区间仅条件历史证据，不是累计多轮后的盲测p值。即使名义通过仍须独立多周期/真实执行与新样本，不能自动正式晋级/加注。

## 预算、独审与反思

本包预算：6新fit、0或4新现金、0旧fit/旧现金/源重投影/新label/SQL/下载/分钟。205实现只新增候选；206现金等方向门全过再实现，避免大概率无关工程；207独立审新数据、模型、实际预测/held/现金/费用滑点/预算/持仓/CI/bug/置信度，不重复老源资格或加旁路observer。actual均由root精确源码绑定后只启动一次。

任何资格/方向/金融门失败就关闭固定q/53/Ridge/K包，不换符号、窗口、邻月距离、品种/年份、模型/alpha、阈值、止损或风险救参。不得把错误修复变成不断重复经济试验。

开始是否有过拟合风险：**是**，新特征择题及已见历史反复使用存在选择风险；规则/方向/训练/预算事前固定、无成绩后救参只能限制，不能消除。继续价值：**是，仅这一有限证伪**；不因已有421fit而凑实验，方向不支持则0cash。结束反思在208实际结果后记录，不能预先签通过。

新增参数只有q输入及训练方向门；旧交易参数修改/删除0。新增/修改/删除回测结果目前0；权益/收益/DD/Sharpe/滑点/交易/胜率均N/A。累计421fit/226cash，goal active；完整稳定优势、窄损上界和加注资格均未完成。

协议[protocol.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage204_local_curve_information_protocol/protocol.json)13499B，SHA `b3a950dfb96333457f6a78f89796e07827a5758d0006eb43f71fad3cffd276ca`；205/207实现与预审进行中，尚未启动新模型actual。
