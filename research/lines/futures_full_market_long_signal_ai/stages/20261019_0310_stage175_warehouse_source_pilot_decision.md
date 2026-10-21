# Stage175：七日报仓单来源与转换接受，未新增训练资格或alpha

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-19 03:10 CST。
- 工作区：`/Users/mac/Desktop/fian`；沿用研究分支，不做Git/正式策略/生产/CTP/邮件操作。
- 阶段性质：独立来源可行性与数据转换；非重要突破，未触发正式候选A/B。此前目标turn为progress：真实恢复新源、12新fit/8新cash并独审；本turn新增七份原文及完整转换，没有重复旧金融。

## 调研与判断

[上期所日周数据入口](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/?query_params=dailystock)与[AKShare维护者详细源码](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/futures_warehouse_receipt.py)给出按日全表与JSON/HTML分支线索。未安装或直接消费其聚合值；171已发现异常填0/历史硬编码，不把成品接口当核验数据。按052已知calendar事前固定2025-11-13/14/17/18/19/20/21七日，包含格式切换，不依据收益挑日期或品种。

原文的仓单登记状态是价格/OI不能唯一恢复的观测，但不等于社会库存、真实供需全貌或看多信号。177只做一轮两query与两个官方open：2019接口候选PDF超时未重试，另上期所数据管理部WMS监管文章没有逐码字典。结论是此次未取得字典，非字典不存在；停止本批字典查找，不移植WMS采集切片为公开日报首发时钟。

## 新增与执行

172冻结协议后只发7次请求，7个HTTP200，原文共845,130B，首次源获取12.526406209秒，无重试/重抓。173新增保真规范脚本与7个有限fixture；原油列名alias在actual前补齐，7/7通过。真实转换只启动一次，0.323070332990秒exit0，3,736物理行全留。未改旧模型、标签、母体、账户参数、价格或旧结果。新增/修改/删除金融参数均无；无SQL、价格下载、训练或资金回放。

独立174先将7份原文各读一次并保留独立参考，再完整核173全部新输出一次，未import作者计算函数、未二次扫描7份raw。输出核耗时0.219514208962秒，C/I/M=0/0/0、errors=[]。核心核验包括3,736行、6,928数值单元、1,560表内检查、609相邻检查、7份schema/summary及文件绑定。测量行parse_failure为0；摘要每字段264个parse_failure来自保留的header/section文字，不是264条坏仓单。

## 可接受与未知边界

| 项目 | 本轮事实 | 判断 |
| --- | --- | --- |
| 日期/数值/原字段 | 七日报日期均对应，期号连续；原字段、明确0/缺失、span来源全保留 | 只接受本7日保真 |
| 旧JSON | 3×479=1,437行；每日23 VARID/31原类型组；WGHTUNIT1/2/3与WHTYPE1/2原码保留 | 不贴物理单位/类型释义，非字段缺失 |
| 新HTML | 4日共2,299行，每日33产品类型表，显式吨/千克/桶 | 已声明单位原样保留，不能外推全史 |
| 表内核对 | 1,488 arithmetic match、72 unknown；其中物理状态870 match、618 unknown_unit、70 tax叶分类unknown、2无leaf覆盖 | 不将旧码算术相等说成物理认证；不重复加小计/总计 |
| 相邻核对 | 543 arithmetic match、66 unknown；物理状态331 match、212 unknown_unit、66 coverage unknown | 跨格式与氧化铝厂库等覆盖变化不强拼 |
| 非原有OP/新行 | 新格式出现胶版印刷纸，旧格式无行；AO厂库明细范围变化 | 无行不补0，不取共同仓库交集偷换对象 |
| 时钟 | 旧update_date约15时，当前HTTP取得/归档日期已留 | 不证明历史首发、未修订或完整2014+连续性 |

366项独立普通总计原文诊断也吻合，属于上述算术范围的局部，不额外相加成新训练经验。当前七日source contract仍是显式单位才可称物理量。176提出的`F(cQv,cQw)=F(Qv,Qw)`只说明在共同正比例不变时可研究无量纲变化，不能把同码自动等同为同口径/同尺度，更不能补PIT。

## 金融结果与下一步

本阶段期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均**无新增（不适用，不填0）**；0新fit/0新cash，累计409fit/218cash。Stage170固定席位q包unsupported保持，不改HHI/lag/模型/K/止损/风险救参。六所399,252母行身份不变，本轮未投影仓单、更未因有源性删无仓单品种。

当前有限pilot结束，不重跑七日、不继续字典搜索、不凭七日数据立刻训练。下一步由178在任何新请求前给出与实际研究源日截止一致的固定全日期归档范围，复用已得原文、全表所有品种、不挑赢家年；再冻结唯一历史批次预算。归档可忠实保留未知代码，但不是172物理语义通过，也不是自动bulk或金融授权。若历史证据支持条件coded-registration研究，须另立同对象/同覆盖/同尺度与可得时钟假设，预定单项对照和失败终点，strictPIT仍false；若不能诚实说明则结束该信息包，不无限资格工程。窄损与加注仍未证明。

## 反思与记录

运行前/后新增按收益选参过拟合：**否**，本轮只用事前7日、全产品原表，没有新增金融结果；已有同史多轮择题与归档回填风险：**有**。继续重复本pilot或扩大字典查找：**否**，本轮价值已实现。继续完整全市场AI目标和一次固定历史归档判断：**是**，能检验真正新增观测的覆盖，不把数据工程冒称收益突破。完整goal保持active，未完成，不加注。

只更新本线LINE与registry；普通source进度不追加根memory/back_log。结构化决策：[decision.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage175_warehouse_pilot_decision/decision.json)（SHA256 `5fa28fd439ca77981140f6831d1101e9886459d56a5b364e2464907c7f79c116`）。原文、程序、独立review及176/177精确路径/hash均在decision references中；未运行全库老测试或旧金融回放。


## 178范围方案合入（2026-10-19 03:14 CST，未发新请求）

root已读178完整stage及plan核心范围/预算/复用元数据：2014-05-19—2026-10-16的052calendar全3018日，2798 JSON+220 HTML；复用9（172七日+104两个SHFE日），净新3009（2793 JSON+216 HTML）。104第三份CZCE XLS不冒充SHFE复用。未来日历到2027不拓展实际研究截止日。

接受此完整固定域为下一批范围方案，不声称3018日已取或历史单位已通过；下一轮一次冻结采集实现与预算后执行，512MiB新body/64MiB元数据/无自动重试/已成功不重抓。按已知均值净新body约277.39MiB只是估算。文件：[178计划](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage178_warehouse_history_plan/plan.json)，82071B SHA `06129933ce2c892d6855ae7ba499a63b36b1b4bc4503c0163e4ee9cbc83d69b8`；阶段：[178记录](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0312_stage178_warehouse_history_archive_plan.md)。无新增训练/金融或生产动作，不改变上文175决策SHA。
