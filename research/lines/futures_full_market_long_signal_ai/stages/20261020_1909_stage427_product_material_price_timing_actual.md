# Stage427：RB/HC坏消息到铁矿下一开盘之后的时段诊断

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-20 19:09 CST。
- 工作区：`/Users/mac/Desktop/fian`；沿用当前分支，不改正式策略、账户或生产环境。
- 阶段性质：426预先冻结的一次历史纯X与价格时段诊断；不是策略回测、不是新预测模型。
- 是否重要突破：否。是否触发正式A/B：否。

## 调研与事前问题

426协议已由root于19:04冻结，绑定原研究 [He/Wang/Zhang2023](https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.22440) 及[作者公开全文入口](https://www.researchgate.net/publication/371550940_The_predictability_of_iron_ore_futures_prices_A_product-material_lead-lag_effect)。原研究的收盘到收盘、月/日定义和可正可负权重并不等于本项目下一开盘long-only可实现收益；本次只检验一个直接反证：固定RB/HC坏消息是否还在铁矿下一开盘之后保留支持做多/不做识别的稳定对应。

本次没有继续网络检索。此前424泛投入产出图的NO-GO保留；此实验由426的明确国内链条论文另立固定假说，没有展开六所产业图、改lag或做收益择优。

## 实际改动与参数

- 新增脚本：`tools/stage427_product_material_timing.py`。
- 唯一实际输出：`outputs/stage427_product_material_timing/actual_run1/`。
- 修改/删除旧脚本、模型、正式配置、止损、风险、费用：无。
- 特征：`q=.5*(min(log(C_RB,u/C_RB,u−1),0)+min(log(C_HC,u/C_HC,u−1),0))`，u日代表合约自身相邻两日，不能拼接不同代表合约。
- 仅DCE.I适用；其他97产品395,178母行保留，q为structurally_not_applicable的0，不当真实源证据。I缺任一来源就是unknown；双方非负是合法已知0。
- I时段事实沿同一u所选epoch取u−1/u/D=u+1真实bar：gap=`log(O_D/C_u)`、after_open=`log(C_D/O_D)`、total=`log(C_D/C_u)`、own_u=`log(C_u/C_prev)`。
- 两era：2015-07-01至2020-12-31；2021-01-01至2026-10-16。所有统计同一joint支持域，所有非joint日保留，不作为交易资格mask。
- partial correlation只控制own_u，经3×3协方差计算，不声称控制COMMON52或因果识别。
- 非循环252个完整交易日期块、2000次、seed20261020；先在完整era日期网格抽索引，再在每次样本内部选择joint行。每era七项统计共用同一索引；保存索引digest、全部replicates和undefined计数。

## 验证和真实运行

一个小toy先RED（缺实现，exit1）再GREEN（exit0），覆盖同epoch换月、不用缺日上一个bar、q合法0/unknown、收益分解、partial covariance、非循环块及固定seed重现。未跑旧suite。

唯一actual终端session **22012**，启动一次、完成一次，exit0，耗时 **5.560671458秒**，完成于`2026-10-20T11:07:40.951093+00:00`。原129母体一次metadata读，原132缓存一次打开，`epochs/offsets/days/values/valid`各一次。母体399,252行、4,074日、98产品、95family、六所完整保留。输入stat前后完全一致，未重hash原110MB缓存或19MB母表。

实际动作CSV读0、Y读0、SQL0、API0、下载0、fit0、现金回测0、前瞻D0、原账户修改0。累计454fit/246cash及1旧partial不变。

## 源支持与固定统计结果

- 全4,074个I母日，q已知3,051，负值1,676，合法0为1,375，未知1,023；主要早期HC未有代表，缺失不补0。
- 论文期1,343个日格，q全known，价格/own/q joint1,279，非joint64。
- 后续期1,400个日格，qknown1,396、missing4，joint1,377，非joint23。
- 所有17个自然年2010—2026点统计与源状态数保留；2026是不完整年，不用于2021—2025完整年通过数。

| 固定诊断 | 论文期 | 后续期 |
| --- | ---: | ---: |
| gap partial correlation | 0.121619 | 0.037314 |
| after-open partial correlation | 0.018432 | 0.035850 |
| after-open partial corr 252日块95%CI | [-0.037241,0.048749] | [-0.015846,0.095987] |
| total partial correlation | 0.048787 | 0.043851 |
| after-open均值：q已知0减q负值 | -0.00057998 | -0.00194780 |
| 同一均值差95%CI | [-0.00299839,-0.00002928] | [-0.00451219,-0.00004622] |

均值差是日志收益量，后续期约-19.48bp，仅为同支持域描述差异，不含交易费用，也不是资金收益。partial corr和分组均值控制口径不同，不能择取其中正值证明过滤有效。

2021—2025同时具正after-open partial corr和正分组均值差的完整年 **0/5**。2024均值差为正但partial corr为负；2021/2022/2025虽partial corr为正但均值差为负，不能选其中一项过门。收益分解恒等式已在实现逐known行检查1e−12；最大实际误差见`results.json`。

426三个数值条件全部false：两era两统计同时为正失败；后续期两个CI下界均为正失败；至少2/3完整年同时两统计正失败。`independent_review_complete=False`仍留给428，`financial_authorized=False`；作者没有把自己的计算声明为独审通过。

## 结论和限制

**该固定RB/HC坏消息→I下一开盘之后包没有达到进入金融试验的门槛。** 当前不训练offset、不跑现金，不按本结果反转符号、改lag/期限/回报定义、筛年份/品种、扫阈值或缩止损/加注。

论文期的gap相关大于after-open，说明原close-close统计和下一开盘后的问题不同；不能据此断言所有效应都已被gap耗尽，后续期证据更弱，且分组均值方向与事前预期不符。此处是一个固定链条、固定时段反证，不能推断全市场信息无用或所有lead-lag失败。

历史源完成与收到时刻未获当年PIT证明；仅同epoch历史重建。日线无盘内路径，未推论止损可实现性、真实成交或账户净值。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数和胜率均N/A，不能把本次相关性诊断冒称新的策略绩效。

## 产物、独审和反思

- `source_day_features.csv.gz`：4,074日RB/HC原价/epoch/返回值/状态/q。
- `I_price_timing_facts.csv.gz`：4,074日I原价/epoch/缺失/时段事实。
- `mother_projection.csv.gz`：全399,252母行q及适用状态。
- `results.json`、`bootstrap_replicates.json`、`receipt.json`、`terminal.json`、`manifest.json`。
- 已交独立428一次新小facts/stat/代码审查；不回读原cache或重跑actual、原suite。最终root裁决应结合其真实结果。

运行前：有很高历史多轮择题风险；固定独立论文链条、坏消息定义与一日时段反例，减少本次新增自由度。一次现有源诊断有价值，扩网络/大下载工程无价值。

运行后：新增按结果调参过拟合否，没有救参；历史适应性风险仍是。继续此固定包的金融后继价值否；继续原全市场高质量做多完整目标价值是，目标尚未达到。不改LINE/registry/根memory或back_log，不做Git/生产/CTP/邮件/定时任务。
