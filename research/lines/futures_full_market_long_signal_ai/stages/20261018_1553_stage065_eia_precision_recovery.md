# Stage065：官方独立舍入的单次离线精度恢复

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-18 15:53 CST。
- 当前checkout `codex/ai-training-data-expansion`；来源修正，不是新策略参数或金融实验。是否重要突破：否。
- 开始判断：不是按成绩过拟合；新fit/现金成绩尚未发生时，发现原060对官方显示精度处理过严，修正有必要且有继续价值。root先停止仅下游控制链，原下载PID3442继续完整结束；未改060或059模型/成本/统计政策。

## 官方依据与冻结规则

[官方Table1](https://www.eia.gov/petroleum/supply/weekly/pdf/table1.pdf)脚注明确：`Differences and percent changes are calculated using unrounded numbers`，并说明独立舍入。因此“打印current−打印prior-inline”不必逐位等于打印Difference。继续采用官方公布的Difference，不自行重算或修改任何库存数值。这是量化测量相容性，不能重建未舍入真值，更不能独立证明历史首发字节PIT。

沿用057的论文/官方来源及GitHub维护方调研；精度修正另外由root在所有新模型成绩前写入 `outputs/stage059_eia_full_market_protocol/precision_input_amendment.json`，3035B、SHA `46946878f76d2b0a134bf274898868e622c4bded4d021a1add62116f8af3e729`。独立agent另核5份真实缓存、15个库存行支持此规则，不调用作者065函数。没有新抓PDF或CSV。

对每个库存行，按三个原始Decimal打印指数分别得到量化单位q，接受条件固定为：

`abs(current - prior_inline - published_Difference) <= (q_current + q_prior + q_Difference)/2`。

只有原060因算术残差拒绝、其余结构/日期/三个库存均合法且三行全部相容的report可以恢复；非算术拒绝和越界继续unknown。million barrels乘1000，流量下半表始终排除。没有市场阈值、模型参数或收益筛选；粗/细/混合打印精度使用同一机械规则。

## 新代码与TDD

- 新增 `tools/stage065_eia_precision_recovery.py`，16544B，SHA `3f9334595653cd825e4d7d2841db0492b6c0b77226645811e459877068e9c30e`。
- 新增 `tools/test_stage065_eia_precision_recovery.py`，6101B，SHA `170bb5123d3c4484ff03f1c6890914fe39d8e68bbc3bf7dafc28bbbfe8c4fdd6`。
- 5项新行为先RED后GREEN：真实2020-03-04三位小数病例保留官方785/−4340/−4008千桶Difference；动态打印精度与越界；日期错配/流量隔离；原拒绝资格与全身份保留/越界逐格审计；raw SHA漂移阻断。补充审计断言先见RED，再保留越界三个cell的残差和界。初次GREEN尝试有一处测试期望额外尾零的字符串格式失配，按数值0.006修正测试期望，未改恢复规则。只跑新测试、未跑旧suite；py_compile通过。
- 冻结060源码 `f40f1b...7d45e` 原字节不动，只复用其完整calendar、纽约可得时刻、中国u/nativeD、ordinal52、scalar/sham/superseded语义。

## 唯一actual授权、命令与结果

root授权文件 `authorization065.json`，1983B、SHA `78f7496ede502a8ad3ec90e52424eceb4f38b1c44defa83539b4354e8bf11bd7`，精确绑定上述065source/test和完整060 parent manifest `00a964468d6fc2cd272d522ae1343227df13b05e3a17dc216305c890a30ba923`。实际绝对命令、授权、parent、source/test SHA及终态保存为 `outputs/stage065_eia_precision_recovery/authorized_run_receipt.json`。

2026-10-18 15:51:12—15:51:13 CST，唯一离线actual exit0，核心1.402747秒（wrapper1.686471秒）。本任务 `offline_normalization=1 / new_network=0 / original060_source_actual_startups=1 / fit=0 / cash=0 / SQL=0`；没有重抓、重跑060或改写旧actual。

- 794个report和2382个三库存长表行全部保留；原596known/198unknown，恢复193份，最终789known/5unknown。
- 730个scalar可知、729个与past_sham共同可知；787唯一u、7superseded、1期末pending。2020+349个u中340共同信息可知；原060仅41，不把原显示精度缺失当成市场否定。
- 按年恢复：2016为1、2020为25、2021为32、2022为29、2023为32、2024为26、2025为27、2026为21，共193；其他年0。规范化年度完整覆盖见CSV。
- 保留5份unknown：2011-08-24/2022-01-20下载timeout；2019-07-03表头错周；2023-12-28三分量残差超显示舍入界；2025-12-29四位年属于原日期解析失败、不是精度恢复范围。没有顺手修小缺期。
- `recovery_audit.csv`含198个report审计和582个cell审计（194候选×3），579个相容cell恢复；越界三格保留false。保存每格原字符串、三quantum、残差、界、单位、原拒绝原因和恢复状态。

## 兼容接口、绑定与有限核验

`manifest.json`保留下游接受的 `stage060_eia_import_manifest_v1` schema，但明确 `producer=stage065_eia_precision_recovery / normalization_stage=stage065`，并完整绑定原060manifest/actual/source/tests、精度修正合同及065source/tests，不冒充060原结果。artifacts的calendar、normalized_stocks、report_features、event_map、coverage同role；event_map仍为全family统一的u_date/report_id/s/inventory_s/past_sham_s/external_missing接口。history_ready20继续由049机会提供。

恢复库存行 `value_status=known_precision_recovered`，保留原算术残差并新增打印舍入界/相容标志；两层source_bindings保留original_source_status、original_parse_status和原parse_error。source SHA与官方公布Difference均不改。

- 065 manifest：`41e3018e0a22ac0bd993f4f47518888af1b5f4347be5e673a9815bc7ebc5c8b6`。
- coverage：`de954c3339d60810c9c4f699028b120b48cc6fdd5152c2aa783ff0647465bf5a`。
- actual_terminal：`b4904f10a4612f4ff1d25cb19b06e2d6a108d7f33708b57bf78e9447038d03c8`。
- 运行授权receipt：`8b44fcee96bb340225fc7ffe4a66a62cffd8cf8f8da17006ff383b7a66a6d7bd`。

作者另做有限保存物核验：两个manifest所有artifact SHA/size闭包；原060manifest/源码未变；原known库存数值完全不变；794ordinal/3分量/787唯一u；共同缺失两槽0；所有sham donor在严格前52ordinal内且值匹配；u16:00严格晚于纽约日末可得，末端D为pending。receipt为 `final_local_verification.json`，明确不是独审、不重拟合/SQL/现金重放。

新增/修改/删除交易参数和回测成绩均无。期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。root在15:51:41另启动下游第一次6fit，属于后续061任务，不是本065训练成绩。

结束判断：新增按成绩过拟合否，显示精度规则有官方依据并对全部报告统一适用，历史研究选择风险仍在。继续一次固定信息证伪有价值；取得可用来源不意味着有alpha、真实盈利、更低回撤或窄损加注资格。下一步由root的061/062一次运行及063独审判断，不改窗口/seed/模型/止损救参。完整全市场long-only AI目标未完成。

本阶段只新增本线065目录与唯一stage记录，不改LINE/registry、根memory/back_log或其他研究线；原始HTML/CSV/PDF不登记Git，不做commit/push/生产。
