# Stage028：2015—2020 主力映射逐笔独立审计

冻结时间：2026-10-23T21:36:07.553920+08:00。结论：**记录中的主力使用和换月执行通过；全部历史主力选择准确性与PIT未证，不晋级。** 本轮不修改任何旧数据、策略或金融结果，不新跑回测。

覆盖2015—2020（含2020）全部407个窗内fill，以及201个实际入场cohort的完整生命周期；另纳入cu2102的2021-01-04退出trade408，合计408 fill、1,779持仓日行。主键用entry_trade_id与trade_id，可直接和stats/K线审计拼接。

## 主力身份从哪里来

主力不是用本次混合K线现算。旧历史映射来自Tq/KQ.m的TqContCalendar；SDK从continuous_table变更记录结合交易日历向后填充。已读本地SDK及[官方GitHub实现](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/calendar.py)。2015—2020原19产品27,778键与原始历史export、本线base、stage005全部一致；2019—2020的9,253键又与stage005同供应商新raw快照一致。三F系列的昨OI合成政策不在原19池内。

这证明已冻结供应商身份可追溯，**不证明历史主力全正确**。原2015—2020逐行最初取得时间与原始continuous_table响应SHA未找到。原文件summary记录2026-10-15 Stage173仅更新2026-10-01—10-14，不能把该时间当作历史行取得时间。信易[2026-09-15官方回复](https://forum.shinnytech.com/question/26536/)说明历史异常可能修订、目前不保历史版本及逐次修订日志；正常情况并非随意根据后续表现改选。本次PIT仍未证。

[Tq文档](https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html)采用量仓共同居前后的次交易日开盘更新。[RQ文档](https://www.ricequant.com/doc/rqdata/python/futures-mod)的88默认则有持仓1.1倍和切换约束，另有单独rule2。不能把“当天OI不是第一”判为Tq错选，也不能拿RQ不同定义直接否决Tq。

## 独立对照与6笔差异

我直接从SHFE原ZIP内XLS（解开合约合并单元格）、DCE jm原ZIP-CSV/XLSX-XML提取2014—2021全合约量仓，156,757行，包含零量及缺OHLC行；不依赖clean/normalized筛选，不推断单双倍数，排名在同品种同日共同倍数下不变。另直接读RQ原H5的1,244个物理合约261,067行，以及未复权88连续；以OHLC四价+量+收盘OI六字段精确匹配，独立反推主连实际标的。所有201入场信号日均可唯一反推，195与Tq相同（97.0149%），6不同：

| Episode / 入场trade_id | 信号日 | 冻结Tq main | 独立RQ88标的 |
| --- | --- | --- | --- |
| NE0025 / BACKTESTING.48 | 2016-02-05 | cu1603.SHFE | cu1604.SHFE |
| NE0032 / BACKTESTING.62 | 2016-03-18 | ru1605.SHFE | ru1609.SHFE |
| NE0052 / BACKTESTING.103 | 2016-12-02 | FG705.CZCE | FG701.CZCE |
| NE0086 / BACKTESTING.171 | 2018-01-05 | cu1802.SHFE | cu1803.SHFE |
| NE0114 / BACKTESTING.228 | 2018-11-30 | rb1901.SHFE | rb1905.SHFE |
| NE0169 / BACKTESTING.335 | 2020-03-27 | fu2005.SHFE | fu2009.SHFE |

六笔均有真实物理合约与生命周期记录，未发现确定的退市后/未上市开仓。五笔SHFE在信号日前一交易日仍为成交量第一、OI第二；FG705缺独立官方CZCE截面，RQ物理量仓和主连已并列保存。不同选择与供应商规则不同相容，**并未证实这六笔一定只是规则差异，更未证实谁错**。195一致也不是准确率或PIT证明。

全期291次已公布Tq切换的独立官方昨收诊断：106在原始截面有“双最大”支持，75昨收未同时最大，110无独立官方昨收截面证明。公开说明没有足够版本化历史日内触发细则，本轮不将日终排名自创成精确Tq重建算法；75保留为待解释差异，不能直接称75次错误。具体排名、全截面规模、来源ZIP/工作表/行号和SHA逐行落盘。

## 信号、成交和换月

201真实开仓、207个entry计划、224个空仓候选均匹配signal日Tq main，错配0。408个fill的signal/fill日在既有物理epoch上市—退市区间内，严格下一交易日同约真实正量日K开盘；114入场日在独立官方原截面能查到所选合约，其余有RQ物理记录。该结论限于记录中的可交易身份和执行，不能替代主力选择准确性。

两笔开仓在下一交易日main已经改变：trade62的2016-03-18信号选ru1605、03-21 fill日main为ru1609；trade228的2018-11-30信号选rb1901、12-03 fill日main为rb1905。两笔都继续按既定signal日原合约成交，符合冻结nextday合同，未偷偷改成fill日新主力。

1,779持仓日行中1,578仍为当日main；201非main行全部有解释：105 waiting、34 scheduled、21 due、41按前日订单当天退出。160条换月日志逐条核对交易日日历、当日目标main及5日计数；21个due旧仓全部在下一交易日退出，其中20标记rollover_close，1为2020-12-15 rb2101 trade393 forced_margin_deleverage。没有无法解释的非main持仓。

冻结主力全序列仍含18已知结构无效键及34旧FU180/新380同码隔离键，均未触及本cohort。另有719个日键与RQ88定义不同、475个无唯一RQ88独立标的证明；不能因18未触及就推导其余完全准确。RQ独立日历与冻结2015—2020的1,462交易日完全相同。

## 置信度与交付

记录中的主力身份/信号/5日换月机制置信度高；实际选择合理性有独立量仓和RQ主连支持，但只有中等置信度；完整历史主力准确性与原始PIT状态尚未证明。没有通过改源、改规则或新的收益回测消除这些未知。

[201入场逐笔主表](/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage028_2015_2020_mapping_audit/all_201_entry_episodes_main_audit.csv)含entry_trade_id、NE episode、signal/fill main、物理epoch、上市到期、官方/RQ排名、来源定位、换月和判决。[408笔完整成交表](/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage028_2015_2020_mapping_audit/all_201_entry_episodes_full_life_408_fills_mapping_audit.csv)和[所有持仓日](/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage028_2015_2020_mapping_audit/every_held_day_main_and_roll_policy.csv)可复核边界；[配套JSON](/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/stages/stage028_mapping_independent_review.json)及[audit manifest](/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage028_2015_2020_mapping_audit/audit_manifest.json)固定全部输入、代码和输出SHA。旧Stage023 review及181项绑定全部未变。

开始与结束判断：本轮固定范围只读审计，没有alpha搜参，不属于本轮过拟合；继续有价值，因为把账本内部一致、供应商差异、确定结构错误和未证PIT分别落到逐笔证据。不会因此宣称历史数据已经完全准确或取得OOS/实盘资格。
