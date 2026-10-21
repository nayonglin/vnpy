# Stage440：原豆类状况信息的延迟开盘反证协议

- line_id：futures_full_market_long_signal_ai。本文件在438原条件全批提取与任何新价格响应读取之前固定。保留完整六所98品种母体；本项仅检验与进口大豆加工相关的DCE.M通道，不缩小完整目标、不作全市场成功认定。
- 使用原相邻报告soy GE差，q=前原报GE−本原报GE；固定q>0为恶化。corn只计来源，不看结果后选作物。没有市场预期调查，因此该差不是surprise。
- 历史可得假设：原Released日期后的纽约次日00:00，取第一全球交易日u的上海15:00截止后决策，D=u+1原同epoch开盘；夜盘开盘必须晚于源可得时刻。不能把中国当日较早夜盘算成发布后入场。历史首见仍未知，次日00只是操作假设。
- 一次来源若训练2017—22已知相邻差不足50、后期2023—25不足30或后期各年不足10，或者439留核心来源问题，根本不读价格。
- 核心检验是买入后的open→close反应，而非close→open gap。原同epoch u-1/u/D和全部未知保留；first-u多报告碰撞保留最后已知发布，其他标superseded，不重复相同价格收益当独立事件。
- 训练期/后期两项固定统计：q与after_open控制own_u的偏相关、恶化组减未恶化组after_open均值。两期均需正，后期252全局交易日块95%区间下界均正，并且后期三年至少两年两项同时正，才讨论另行冻结费用后现金实验。没通过不翻方向或换窗口/作物/阈值救参。

## 外部调研与自己的判断

- [Lehecka2014原论文](https://ageconsearch.umn.edu/record/168261/files/JARE_Apr2014__6_Lehecka_pp88-105.pdf)：本次只读到原论文检索摘要，全文请求403。美国1986—2012数据和close→open迅速反应支持关注可交易时机，不足以宣称中国延迟入场仍有alpha。
- [Bethlem等2023官方原文](https://new.scielo.br/j/resr/a/vcxYjcBRQYWDd6HL6Vq85WF/?ilang=pt_BR&lang=en)：方法3节回归ln(报告翌日November收盘价格水平)与ln(GE水平)、2008年二元断点；作者称断点由bestfit选取，DW=.1304。Newey-West修标准误没有把它变成样本外收益策略。拒绝把摘要的0.45弹性当作次日可赚0.45%利润，不复制其事后断点与价格水平拟合。
- [rOpenSci rnassqs维护者源码与说明](https://github.com/ropensci/rnassqs)：可作为QuickStats取数/字段参考，不能提供原发布版本首见证明。本次不安装、不新增数据下载，不用当前修订表覆盖原档。
- 结论：源可能含供给信息，信息价值与发布后可赚收益是两个不同命题。先做一次时机反证比新增复杂模型、分钟工程或调高风险有价值。

本阶段策略参数新增/修改/删除0。仅冻结待验信息方向/时钟/统计及停止合同。fit/现金回测/API/SQL/下载/未来D均0；权益、总收益、回撤、Sharpe、滑点、交易次数、胜率N/A。未授权actual，必须绑定438终态和439独审后由root签发一次执行。

开始新增按本次成绩调参过拟合：否；长期自适应择题高风险仍存在，后期也不冒称真正未见市场。继续价值：是，仅一次有界历史时机检验；未证明高收益低回撤、窄损或加注安全，完整目标active未达成。

协议：/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage440_crop_condition_timing_protocol/protocol.json
SHA256：8ef8794e51f857aa77cbc34dda4c6bef51b9ef1b94e30c59e04a2dd8d1a45c52
