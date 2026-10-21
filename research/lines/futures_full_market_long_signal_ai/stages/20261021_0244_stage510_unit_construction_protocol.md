# Stage510 原现金政策单位持仓状态与原料构造协议

时间：2026-10-21 02:44 CST；非重要突破，futures_full_market_long_signal_ai。

原目标仍是全市场高质量做多/更高收益更低回撤/小止损加注，独立正式C9。上一507只有事后完整路径必要时钟，不能拿其closed与strict-prefix筛训练。新对象必须按131/157时间前推单位机会路径，真实账户资金/占用/qty/reduction仍由后续现金实验判定。

两项设计纠正：129标签遇missing即unknown停、现金则stale延后强退；489causal投影只有2020+966740行，不能因header完整就当全1552456。两点在实际前发现，本次不重跑旧流程。改用466全metadata14个身份/事前资格字段＋466全mother＋132native＋既有economic/calendar各一次；native重算N/low20/uclose/capacity。0原129/489/505/COMMON/score/SQL/API/下载。

保留全98产品/95族/六所、399252母含186400无子、1552456子（实际有子97/94），不缩范围。入场资格在u给出，D才判开盘、stale取消与同bar stop。持仓缺价保留stale/deferred，首可用bar强退优先；存活close更新max(SL0,ownlow20)，source lifecycle与commonK取早、原u anchor不变。当前riskset不看nextbar/futurefilled/exit。

原始可见state与未来退出原料物理分区。保存baseline exit和每个t请求的t+1/首可用open之两场景SELL quote组成与available_at，不算数值Δ/R，不训练/现金。本轮有历史价格读取和未来outcome原料构造，不能声称完全没有未来信息；未来原料不准回流X/风险集。D缺价的两分支按现金同deferred规则，相同值才是规则可知结果，不能未知填零。存在bar但quote失败必须unknown，不向后挑更有利日。

未来训练先选事前K已过cohort，再保留价格/终态未知，不仅挑快止损closed；下一learner方向是一次原policy改进，不直接做递归最优停止。本轮并未授权reward/fit/cash或风险加注。

调研：原论文https://arxiv.org/abs/1712.09705、https://arxiv.org/abs/0710.3640和作者https://github.com/mludkov/mlOSP/ 支持继续vs停止对象与算法方法，不证明期货alpha。新参数仅构造性字段/分区，无策略新增/修改/删除。本轮期末权益、收益、DD、Sharpe、滑点、交易次数、胜率N/A；累计505fit/274完成cash+1旧partial不变。

开始过拟合风险是（长期同历史择题），按收益调参否；继续价值是（防止对象偷换和未来筛选，保存可复用原料避免重复native读取）。实际后独立review再判断构造性，不自动拟合。

协议：/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage510_continuation_unit_construction_protocol/protocol.json；SHA256 f19257726a1ff8d43b2609e65e4a2b1ae63ed650d4ca6112055caafb4c93f1b8。
