# Stage473：固定年度成熟更新结案，历史研究不等新日线

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-20 23:58 CST；非重要突破。当前goal轮为progress：15新fit及4本新现金完成，一次独立合并审查接受；完整目标仍未达成。
- root最终判断：接受470—472的数据、模型、选择与研究现金算术，否决本469固定annual更新包。停止救此包；完整全市场高质量做多目标保持active。

## 用户疑问与时钟边界

历史研究无需等待今天/明天日线。469实验使用已经固定的截至2026-10-16历史资料；原四前瞻账户在u2026-10-20封存D2026-10-21，只有这些账户必须等D真实完整行情。此前将前瞻等待与历史研究混述不准确；不能以等日线代替当前研究推进。本轮无新下载、分钟、CTP或调度。

## 改动和真实财务结果

唯一策略变动：原2020/2023两cutoff更新改为固定每年Jan1严格成熟经验扩窗。52特征、Ridge alpha1、原129目标/130权重和缩放算法、common-K、正分选择、费用风险和0.25N初始止损均不变；删除参数0。年度只换新信号score，不清仓或重置资金。新增4候选现金结果，旧结果修改/删除0；控制严格复用157自身四账，不是其baseline_references旧131B。

初始100万，收益/DD/胜率单位%，滑点为CNY且已包含成交价；交易数为闭合root。C是本研究年度更新，A是原同对象两cutoff研究控制，不是正式C9收益。

| 窗口 | 成本 | A收益% | C收益% | A最大DD% | C最大DD% | C期末权益 | C Sharpe | C总滑点CNY | C闭合交易 | C净胜率% |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020连续 | base | 122.927022 | 87.687797 | -15.627420 | -19.374476 | 1,876,877.9700 | 0.810442 | 104,588.0080 | 1088 | 11.948529 |
| 2020连续 | stress | 52.841971 | 53.094530 | -11.359301 | -15.267314 | 1,530,945.3035 | 0.773873 | 157,701.0287 | 879 | 11.490330 |
| 2023冷启 | base | 82.543655 | 87.164209 | -9.902149 | -7.973572 | 1,871,642.0910 | 1.417760 | 47,874.6152 | 418 | 13.636364 |
| 2023冷启 | stress | 52.664582 | 57.463884 | -6.422761 | -5.678059 | 1,574,638.8440 | 1.322670 | 79,803.1354 | 379 | 13.192612 |

2020base少352,392.2485元、收益低35.239225pp、DD加深3.747056pp；主stress只多2,525.5935元而DD加深3.908013pp。2023两账分别多46,205.5365/47,993.0205元且DD较浅，不能替代主窗失败。四组原252日块/2000次配对平均日log增长差CI均跨0；主stress为[-0.000102953843256,+0.0000921261803445]，不能说有统计支持的稳定增量。逐年、费用/滑点、所有A/C完整指标、家族集中与情景详见[Stage471真实结果](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261020_2352_stage471_annual_mature_cash_actual_result.md)。

held0/1已知均值增量+0.001692745118R/+0.001011148950R，但异动作未知5/13、相同行动未决22/30保留，未有有限完整收益界；是first-exit诊断，非common-K现金泛化证明。四C执行未知、主窗历史stale/入场未知保留，gap>1R仍存在，不能签窄损封顶、加注或生产资格。本包失败也不只因为unknown：名义经济门已失败。

## 执行、故障与独立审查

470唯一实际315.189916秒/exit0，15新fit、6原模型复用；原actions与COMMON各一次，1933480新score，main915/held1192选择改变。全399252母表/1552456行动、六所98品种95家族保持；行动/标量数均非独立经验数。

471日期准备阶段失败时0现金、native1次，修YYYYMMDD适配后唯一11.814219秒四账全部完成。随后export重复mkdir失败，四raw保存；只修报告I/O，session20592严格reports-only/1.892933秒exit0，新cash/native/SQL=0。作者native累计2=失败准备1+完整四账共享1，独审另1；不能将报告恢复当资金重算，也不隐瞒额外缓存加载。原模型/四A无重训重放。累计481完成fit/258完成cash及1旧partial。

472同一持久审查进程532.035890秒/exit0；15新fit/6复用、1933480全分数和全选择、5542fills/10261预算、原价费用/持仓/整数预算、44年度切片/2090家族年格、8000原bootstrap值完成独立核对，C/I/M=0/0/0；最大现金算术差2.33e-10，0fit/现金重放/SQL/下载。root只核最终小文件SHA/终态/完整收据/代码交付绑定及经济门，没有第三次大表审计。完整[独审记录](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261020_2354_stage472_annual_mature_combined_independent_review.md)；收据SHA d161a3f5bf01468d2f3151242e9354493246b0749712fd9cae0ee1aa56f11c75。

## 调研判断、反思和下一步

沿本轮已核[Qlib官方扩窗实现](https://github.com/microsoft/qlib/blob/main/qlib/workflow/task/gen.py)和[TimeSeriesSplit官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)：时间顺序扩窗是合理实验设计，但不能保证alpha；变长退出标签仍需逐条known_date门，不能仅用固定gap。实际证据否决这个固定年度更新包，不能推广成“所有补充训练数据都无用”。

开始/结束本包结果后新增调参过拟合：否，频率/模型/风险与门在结果前固定、无救参；长期同史反复择题风险：是。继续本固定annual包：否，不改月/季/rolling/decay/alpha救它；继续全市场高质量做多原目标：是，但下一项须新增可证伪的信息或不同机制，并先查本线失败谱系，不能靠重训旧包或多一天行情翻案。

本记录没有授权下一轮新fit/cash，先确定独立的有价值问题。原四前瞻账户完整保留、仅其D真实外部时钟继续；不等日线才开始历史研究。`goal_complete=false`、`production_qualified=false`、`increased_betting_qualified=false`。未改正式、其他研究线、根memory/back_log、Git、CTP、邮件或launchd。

决策：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage473_annual_mature_root_decision/decision.json`；下一范围：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage473_annual_mature_root_decision/next_scope.json`。
