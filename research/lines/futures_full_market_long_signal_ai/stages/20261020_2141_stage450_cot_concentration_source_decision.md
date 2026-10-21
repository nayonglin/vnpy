# Stage450：新增集中度数值来源接受，尚未取得训练或收益资格

- line_id：futures_full_market_long_signal_ai；root决策：2026-10-20 21:41 CST。
- **完成一项不同信息输入：2010—2025原COT最大四名交易者净多/净空集中度，两项13360原数值、6680完整记录全部可解析，并独立复核通过。仅source-only接受，不是alpha或重要突破。**
- 用户完整目标仍是六所全市场全部98品种95家族高质量做多、提高成本后收益并降低回撤，再验证窄止损与增加投注；当前goal active未达成。本字段只在原8个有实物映射品种适用，完整研究母体未缩小。

## 本次改动和实际执行

444冻结一次header/血缘探查；445核旧路径；446实际只读一个原2010header，191列中24个集中度列，16年既存schema均有同24列，完整header的日期列名有差异。447判定该信息不等同旧分类净仓，只允许固定Con4Net_All两原字段数值投影，不扫描24列。

448按冻结scope与code由root单次启动，session72928 exit0；16原ZIP各一次bytes+同读SHA/bytes校验，16CSV各一数据pass，只投影8固定映射。既有原档复用，无新增网络下载、市场API、SQL、价格/Y/score、模型训练或资金回测。449独立审查单次完成，原源仅点核3个预定anchor，未重跑448或重扫16原包。

原2010header先读1次，数值阶段16原包各读1次，独审3包各读一次；这些是不同验证目的，未隐藏成整个goal只有16次原包读取。所有原数据、既有模型/账户、正式C9、月度池与生产均未修改。

新增研究字段仅两项原百分比及固定Con4比率；原策略/模型/风险参数增改删0；回测结果新增/修改/删除0。累计实际fit460、完整现金250与1旧未完整尝试保持不变。本轮权益、总收益、最大回撤、Sharpe、滑点、费用、交易次数、胜率均N/A。

## 数值和身份结果

| 项目 | 实际结果 |
| --- | ---: |
| 原来源年份 | 2010—2025，16年 |
| 固定映射通道 | 8 |
| 共同持仓统计日期 | 835 |
| 完整日期×通道槽 | 6680 |
| 两项原token | 13360 |
| 原比例均有限且0—100 | 13360/13360 |
| 已知Con4 | 6680/6680 |
| 生产/训练可用时钟已确认 | 0（未应用） |

通道：CZCE.CF, CZCE.SR, DCE.C, DCE.M, DCE.Y, SHFE.AG, SHFE.AU, SHFE.CU。这835个是持仓统计日期，不等于835个已确认发布事件；6680行也不等于6680个独立训练样本。

固定字段为`Conc_Net_LE_4_TDR_Long_All`和`Conc_Net_LE_4_TDR_Short_All`；Con=(L−S)/(L+S)，原数值范围分别校验0—100，分母必须>0。合法单端0可得到±1；两端相等且正时Con=0，不能当缺失；双0留unknown。实际全域Con范围[-0.686021505376, 0.355191256831]。完整grid无因known删槽、无缺值填0、无冲突挑选known。

每行保留原code/市场名/asof/报告family、ZIP成员/原行号/原选中tokens和完整原行hash。所有`publication_available_at=null`、`strict_firstseen=false`，408只保留绑定未应用。不能拿原持仓日提前给模型看，今日下载的年度ZIP也不证明历史首发版本。

## 为什么值得继续，但尚无alpha

所核旧014/256与048最终q主要是MM净持仓及变化；旧048虽然计算PMPU指标，也不等于已同域金融实测它。407 mapped/canonical只存五原量及H/MM，未存集中度值。445结论限定于所核路径，未声称整个仓库永远没人研究过集中度。

固定组内总净仓可以不变、组内仓位分布却变得集中，最大四名的份额随之改变，因此它不是旧净仓总数的代数改名。这个数学区别仍不能证明条件预测力或中国做多收益。

[CFTC官方定义](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm)说明gross/net和最大4/8区别、不按商业类别区分，多空排行可能不同人，不能冒称“基金实时资金流”。[2023原论文](https://www.management-review.org/uploads/pdf/paper/mr_2023_42-3_jul_02eng.pdf)检验美国周频与数周风险溢价，不证明当前中国窄损策略；[CFTC白银原研究](https://www.cftc.gov/sites/default/files/idc/groups/public/@newsroom/documents/file/silverfuturesmarketreport0508.pdf)也提醒集中度与价格方向没有简单必然关系。[GitHub维护者代码](https://github.com/NDelventhal/cot_reports/blob/main/cot_reports/cot_reports.py)仅用于核年度ZIP/CSV格式，本次未运行下载器或安装依赖。

## 独立复核与限制

449逐6680行、13360原token、835×8完整grid、128个年度×通道统计和所有时钟边界独立重建。三个预先指定原档anchor为2010-01-05 corn002602、2017-01-03 copper085692、2025-12-30 silver084691；原七项token、行号和完整行hash全部匹配。最大Decimal比率误差1.0101010101E-16，remaining_core_problems=0。

这是新派生算术全核+三个原源点核，其他原包继承407/448冻结绑定，不能说16包所有原值又独立解析一次。正确数值不等于严格历史PIT、独立训练经验、传导机制已验证、或可交易净收益。

## 反思与下一步

本轮按新收益调参过拟合：否（未读新收益）；长期自适应择题风险：高，字段新不会将旧检验次数清零。继续一次固定新信息实验有价值，扫描24列、改方向/窗口或加大投注没有依据。

下一步先处理408既有延迟、修订和未知的发布时间边界，再为原全市场研究基准冻结一项Con4增量对照；模型、原目标、执行、止损、仓位和成本不能同时更改。普通发布规则若仅属回溯假设必须明示，不用asof抢跑。旧MM/PMPU净标量、GE、HGB和Weather/WASDE失败包保持关闭。新训练/金融/加注当前均未授权；收益和回撤尚无本轮改善证据。

源数据：/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage448_cot_Con4_numeric/actual_run1/Con4Net_All_2010_2025.jsonl

root决策及精确绑定：/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage450_cot_concentration_source_decision/decision.json

独审收据：/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage449_cot_Con4_source_review/actual_run1/review_receipt.json
