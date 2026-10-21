# Stage134：固定选月版本的条件排序归因

- line_id：futures_full_market_long_signal_ai；时间2026-10-18 22:32 CST。非突破，纯归因不触发正式A/B/C。上一goal turn分类为进展：133实际1.55m动作、6fit、8cash及独审完整闭环，fixed unsupported并非任务完成。当前累计391fit/118cash。

## 调研与判断

[Daniel等原论文](https://arxiv.org/abs/0810.1922)支持使用同约束随机策略做比较，[QuantConnect官方](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures)与[LEAN源码](https://github.com/QuantConnect/Lean/blob/master/Common/Securities/Future/FutureFilterUniverse.cs)区分当时合约集合和具体合约选择。采用同候选/同风险/同成本原理，不搬海外参数或把随机名次当无条件显著性。两独立设计/复用输入已读，不再扩大预审循环。

本轮先固定原B的事前family-u赢家/exact product与正分合格集合S，再移除S内排序。R+为均匀S，Rall为均匀全部事前E（仅标签诊断）；K为同B赢家产品canonical∈S才交易，失格不让F补位。K不是旧A，不能把这种分解冒称B-A完整因果分解。原B账户不重跑，不复制其事后成交/资金/占仓状态，各控制自己的现金递推。

## 固定实施

135复用130所有既有评分/129标签，计算精确条件均值与未知概率质量（0随机重复也能做单动作），没有新模型或label。全399252母、98目录/95family/六所及全部前向未知保留；完整原B表+每control/selected母行override表示同一完整人口，不写21份重复大表。未选中proposal仅作为原B诊断来源，不冒充控制交易动作。

136只新增MAX_VOLUME_POS一条规则和RANDOM_POS_00至19共20条随机政策，各两起点两成本=84账户。u原日量排序、并列epoch/id；随机minSHA256(version,seed,exact product,u,epoch)，不含成本/窗口/现金/未来标签，跨窗口/成本共用。20用于有限参照分布，不挑seed、不额外加样本、经验名次不是p值。原.25N/20low/anchor、1%往返容量、本金100w、risk .0025/.02/margin .25/buffer1.1/u预留D减量都不变。

缓存110MB完整逐日OHLCV/N/low20/valid/run已在，薄bar/indicator接口适配；0SQL/下载/新fit-label/大库hash/正式策略/生产/Git操作。原AI B四账本直接引用，原133 unsupported仍有效。新增账户只为排序的非线性财富/DD归因，不能用单动作平均R替代。137独立复用通过的132/102纯函数，只核新增选择和账本；展示dtype和全空可选列等价，不为小格式问题重开全审查。

主描述为2020 stress AI与固定20政策平均dailylog之差及原252日2000块CI，并列报告全部seed分布、cold2023/base和最大量规则。CI只条件于20路径；任何必需seed破产/非正财富则不丢seed或epsilon修复，log不可识别，CNY账本保留。held仅既有分数的机会诊断，不跑现金。

## 记录与反思

本次新参数仅控制policy/hash盐/seeds0..19/最大量固定tie，无策略alpha、风险、止损、成本变动。当前新增权益/收益/DD/Sharpe/滑点/交易次数/胜率均N/A；实际84完成后逐项记录，不预填成绩。

开始/结束按本轮收益调参否；同史择题过拟合风险是。继续价值是：先识别AI是否真的会排序，避免把动作支持扩张误作AI能力；仍朝全市场更高收益更低回撤目标推进，不加注。停止当前固定包救参，不禁止这次不改B的机制归因。

协议：outputs/stage134_month_ranking_protocol/protocol.json，20790B SHA 25ad088a36d4aa3a022e7da7e818902e62b1c7c922b85aae3c31ad960c780e62。135/136每阶段绑定最终代码/源数据后一次actual，失败保留；不重训、重跑原AI或旧资格。
