# Stage678：COMMON52＋K 2015起连续回测与曲线

- line_id：futures_full_market_long_signal_ai；day；记录2026-10-21 14:45 CST；branch codex/ai-training-data-expansion；非重要突破，非正式A/B/C。
- 变更：新增2015 cutoff main Ridge1，原52特征/目标/权重/风险/止损/K/成本不变；原2020/2023 scores复用，2015起账户连续，不拼接旧曲线；旧结果无修改/删除。
- 参数：2015-01-05—2026-10-16、2862来源日、100万、单族0.25%/总2%、buffered margin25%/1.1、0.25N、原1%容量，base/stress两账。
- 基础：期末3,213,991.97；总收益221.3992%；最大回撤−13.6025%；Sharpe0.8642；总滑点332,605.04；闭合1850笔；净胜率12.1081%；3703成交记录。
- 压力：期末2,219,976.27；总收益121.9976%；最大回撤−11.7818%；Sharpe0.8491；总滑点395,693.62；闭合1462笔；净胜率12.4487%；2940成交记录。
- 675唯一actual100.613372秒/1fit2cash/0SQL下载重试旧账。2015训练91804行/1192日/50族，maxu2014-12-30/maxknown2014-12-31；完整1312061动作/280476母/5246选中。
- 676唯一完整独审168.206785秒/C-I-M0-0-0，0fit/solve/策略回放；两账完整会计/成本/容量/逐年/曲线通过。实际browser导出PNG1600×1000并视觉核对，未重跑金融。
- 未知：execution_unknown两账true；capacity unknown50/30、entry unknown5/2，历史stale9/6、期末stale0/0、各2open；非strict PIT/正式/加注资格。629 false/inconclusive保留。
- 调研：官方TimeSeriesSplit与原作者GitHub；判断须双成熟时钟，不能现有2020模型倒填2015。新增结果后调参过拟合否；同史风险高；本次延展有价值已完成，继续作为对照是，重复/加注否。完整goal active未完成。
- 累计588fit/296完成cash及1旧partial；无正式/生产/CTP/邮件/Git或其他线修改，普通阶段不写根总账。
- 输出：[报告](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage678_common52_2015_extension_root_decision/report.md)；[PNG](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage677_2015_equity_delivery/equity_curve_2015.png)；[交互图](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage677_2015_equity_delivery/equity_curve_2015.html)；[逐日数据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage677_2015_equity_delivery/equity_and_drawdown.csv)；[年度数据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage677_2015_equity_delivery/annual_slices.csv)。
- TODO：day先交付曲线，保留同版本对照；后续新机制须独立且事前冻结，不自动扫参。
