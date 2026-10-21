# Stage037 逐日episode与真实参考账本接纳

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:32 CST；day。
- 本轮不是模型或收益突破。训练源halfR/retry=False、C2保留；正式源码、配置、AI池、CTP、调度未改。

## 接纳结果

Stage031局部roll helper、Stage034逐日entry episode driver与Stage036两个固定历史条件episode在声明范围内接纳。105项本线测试通过；独立Stage035的13自写case/86字面断言及8852项Decimal/来源/绑定审计合计8938检查0失败，未解决P0/P1/P2=0/0/0。独审包含所有211合成与120真实参考trace、84精确SQL键、4个AM41、独立Wilder RSI/MA20、4个来源分钟投影/首open/日聚合、静态手续费与JM不利tick fill；不以作者账本自证。

11固定合成case/12路径，9known3unknown。先pending参考open fill→新entry C2→完整日线decision；RSI只在partial fill后commit且不重启C2；roll等待与shape、oldclose/newopen、新C2 R和旧episode货币R分开；缺新anchor保留已成交旧腿，wholepath未知。D60 MTM与D60发平/D61fill分开成熟，59日不能冒充60日。finite分支不剪枝或合并。

## 两个固定历史条件episode

| 既定观察 | 初始货币R | 条件毛额 | 静态费额 | 条件净额 | 净额/R |
| --- | ---: | ---: | ---: | ---: | ---: |
| AU 2021-07-30 | 360 | -7920 | 40 | -7960 | -22.1111111111 |
| JM 2021-09-30 | 877.2 | -900 | 464.868 | -1364.868 | -1.5559370725 |

AU入场参考381.4，signal stop381.22，初始风险价差0.18；C2已confirm后普通close377.84发退出，下一session来源匹配首open377.44平。JM current-policy同分钟双触adverse-first，stop3224.69不利tick到3224.5；不认证真实tick先后。均保留负额与原始R，不为负结果clip亏损或加风险阈值。

两例各60source-day trace/2参考fill，D60分别2021-11-02和2021-12-30；固定成熟时钟达到，但historical_validated=False，qty2诊断、静态snapshot经济与外部target/anchor声明仍为条件。两者training_eligible=False、complete_monthly_source=False；4个参考fill不是4笔真实交易。账户期末权益、总收益率、最大回撤、Sharpe、总滑点、真实交易数、胜率均N/A，不能从两点外推正式绩效。

## 修复和证据保全

- 独审指出configured C2 guard与effective filltick混用；root先红后绿分离，缺guard未知。
- root发现未知trajectory snapshot暴露了假定持有的wholepath0值；先红后绿改为只显示recorded legs，whole gross/net/R和actual qty未知。
- 独审指出NaT/bool数值输入边界；先红后绿拒绝，原合法fixture数值不变。新synthetic与真实revalidated结果均字节一致，首跑及旧代码收据保留，不把重验算为新独立样本。
- 原synthetic运行收据缺直接kernel字段，21:30后验依赖校验另文件补充并与Stage014既有kernel SHA核对；Stage035另直接绑定kernel。没有回写原summary或假称其已含新字段。未来收据应执行时直接锁kernel。

模型/正式alpha参数新增修改删除无；研究参数为预先声明horizon、终点mode、显式anchor/path/guard/roll数量及经济合同。没有删除不利结果，无模型fit、正式训练标签、正式A/C、发布或订单。真实case首跑和同输入校验重验两轮，只是同2例。

## 下一步与研究判断

本线目标仍是双向趋势的月度品种适应性。当前driver没有普通退出后再次遇到fresh信号的新入场，不能将一笔entry机会的结果偷换为未来60日整个月度source。下一步先补连续fresh信号流/平仓后重入、每次新entry独立初始R及月内逐日聚合，再定义全候选asof宇宙、20/60/120输入和成熟/未知目标；新来源不是旧108的简单追加。真实18个C2双触未知仍保留，不能删除后重排。

本轮调研判断：官方vn.py实际tape/逐日损益与Backtrader执行语义仅作一般参照，本仓库的时钟由绑定MRO/AST决定；pending/actual、roll两腿、成本日和标签终点必须一致。相关官方链接见Stage033，源码与来源证据见Stage031/032/035/036。

开始/结束新增按真实收益选参过拟合：否，未调R阈值、费用、数量或按收益改源；历史witness支持选择及静态费用偏差仍在。开始/结束继续价值：是，真实参考账本已算通并保留负结果，但还没有模型预测力或收益改善证据。保持正式策略与本线研究隔离。

root仅更新本线LINE与registry一行，不追加根历史总账、不暂存提交、不部署。核心证据：当前Stage034 run、Stage035 summary/README及Stage036 revalidated_20261020_212602。
