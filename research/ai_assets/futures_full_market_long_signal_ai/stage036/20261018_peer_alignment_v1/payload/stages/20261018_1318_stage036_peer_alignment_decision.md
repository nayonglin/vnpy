# Stage036：同行对应信息未通过，结束本包并转向跨日政策母体

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-18 13:18 CST。
- 工作区：`/Users/mac/Desktop/fian`；分支：`codex/ai-training-data-expansion`；沿用 HEAD `4f42805c2c71f8492a44a6876a82672f410f44df`。
- 性质：Stage033–035固定信息实验的root决策及本地复现保存；不是正式A/B候选、晋升或实盘资格。重要突破：否。

## 结论

接受Stage034输入与Stage035计算，接受Stage037独立复算；**否决本次固定同行对应特征作为高质量做多筛选或增加投注的依据**。20个预设门只有3真17假。停止20日相关系数/一个q/Ridge/OPEN/DAY标签这个固定包，不扫相关窗、lag、peer池、null seed、阈值或模型救参。

本次实际108次模型拟合，一次完整运行；并非重新跑旧010/024/029。累计真实模型拟合288次（72+108+108；小fixture拟合另列），现金账户回测仍0次。当前目标未完成，goal保持active。

## 外部调研与判断

实际核对Bennett等[lead-lag网络原作者论文](https://arxiv.org/abs/2201.08283)和[作者GitHub README](https://raw.githubusercontent.com/stefanosbennett/mlj-lead-lag/main/README.md)。其股票关系预测提供可证伪方法参考，不证明国内期货long小损加注能赚钱；本次并未照搬其模型或声明因果传导。

后续目标一致性由独立Stage038在未读035/037新成绩时设计。root核对[Original Turtle规则发布页](https://www.tradingblox.com/originalturtles/originalturtlerules.htm)、[原作者长期趋势论文摘要](https://arxiv.org/abs/1404.3274)及[pysystemtrade breakout源码](https://raw.githubusercontent.com/pst-group/pysystemtrade/master/systems/provided/rules/breakout.py)。判断：停止继续堆DAY OHLC派生变量，优先建立跨日、有完整持仓/退出/换月/成熟时钟的政策母体。55/20/2N为待另行冻结的参考建议，不冒称原Turtle精确复刻、窄止损成果或有盈利优势。经典规则存在历史选择风险，不能称完全未见假说。

## 实际变更与固定参数

新增034上下文数据生成器/6项有限因果测试、035实验生成器/4项行为测试、037独立复算器和证据；正式策略及其配置修改/删除0。

033协议在034数据和035成绩之前冻结。保留007原始标签：次源日同epoch开盘入场，0.25ATR20风险、4R获利顶、DAY退出、基础0.2R和压力1R成本代理；没有换用029去顶标签。

新增q由u−1的其他family冲击与u−21..u−2的20日相关系数组成，排除own/_F同族。ALIGNED为真实对应，SHUFFLED为固定SHA排序的相同peer值多重集，COMMON的q为0；全体共享18列和pooled q标准化，Ridge alpha=1、截距。主比较ALIGNED−SHUFFLED保持19槽容量，COMMON有效18维需披露。

年度2015–2026扩展训练，3 scope×12年×3 arm=108fits。训练只用严格成熟标签；held group同时从训练、peer关系和market摘要排除。score>0一次固定选择，不topN或调阈值。60源日moving-block bootstrap、2000次、seed20261018只描述固定预测不确定性，不包含研究选择/重训/真实现金风险。

## 输入、实际运行与独审

034保留全部194709条ready及541未知标签，每scope为194709×9 `<f8`；不是用D是否有价筛输入。main四个market摘要778836个标量匹配009，最大误差6.66e−16。仅允许1e−12内rho浮点越界修正，非交易/预测裁剪。完整源日历5587日用于时钟，4074源日用于2010–2026-10-16报告。

035唯一实际运行：session44639，chunk `eb3402`→`bbde30`，exit0，2026-10-18 13:06:38–13:07:34 CST，55.520969秒。没有失败重启、pilot、参数扫描、SQL、行情下载或现金回测。保存108个模型及36组训练sequence_index/权重，训练ID可由绑定表精确恢复。

037独立复算：输入492个预选scope-cell，另检查全矩阵schema/有限值/身份及main摘要；不是全q独立重建。实际模型复算session37687，`dcca9c`→`5d979a`，exit0，17.469294秒。108训练身份/权重、969654预测、6组正规方程、56个scope/period报告、8个daily、2组CI和20门全部相符；C/I/M=0/0/0。预测最大误差2.22e−16，daily3.55e−15，总数值7.11e−15。独审0fit/SQL/金融/作者计算函数导入。

## 结果：均为日等权、机会等权的归一价格代理

2020年至今主scope、相同identified样本：

| 项目 | 均值识别下界 | 均值识别上界 |
| --- | ---: | ---: |
| COMMON | -0.000147693875 | 0.001620289680 |
| ALIGNED | -0.000378689313 | 0.001252985886 |
| SHUFFLED | -0.000133468682 | 0.001356529835 |
| ALIGNED−COMMON | -0.000367303794 | -0.000230995439 |
| ALIGNED−SHUFFLED | -0.000288108899 | -0.000060655682 |

ALIGNED自身下界CI为[-0.002830523353,0.000769486561]；压力1R下界均值-0.005956229546。两项paired均值识别区间在历史上均负，但其**上界端点的bootstrap CI跨0**，不能声称已证明稳定有害或所有跨品种信息无用。COMMON没有显式own lag shock，q可能重建遗漏的自身滞后，不能解释为超出完整own history的新信息，更不是因果传导。

ALIGNED选中701条已知/360日期/83family，另22条未知保留；已知选择率0.006524754、全部ready选择率0.006704128。support门2个通过；2020–2025完整年份两项paired下界各只有1/6年为正。held0自身和两pair均负；held1只有A−SHUFFLED正，其自身与A−COMMON仍负，不选择组别救结论。

选中certain profit-only88、双触31，target-first fraction识别区间[0.125534950,0.169757489]，**不是现金胜率**。未知、双触不能当负标签或0结果。

- 期末权益、总收益、最大回撤、Sharpe、总滑点、真实成交次数、真实胜率：全部N/A。
- 新增账户回测结果0；修改/删除历史结果0；CTP/订单/撤单/邮件/部署0。

## 复现绑定与保存

- 033协议SHA `6328b2429106028531916050982bcf57f033285366a745f2f08a29a308a2556b`。
- 034manifest SHA `2a3abe55eabf0fba5bb5d749fb4343d1bf341e3d217b93619554ab11bf98d990`。
- 035manifest SHA `073526fb3439f42b744519b6a7cb7c4a2931d8169e36c040513d27bc44962c51`；terminal `30d7d00de27e1f5b9d1aa07a793802f20e9e4e4f62e1411b608ab1c3990edb36`。
- 037receipt SHA `aa3aa439ebf37abb69a117493128dd8133e5773e72ed320cef5822c43c155770`；inventory `4df4bd3f4889f2c58e88a7be93ef028cc2e3e3ef52db42131059a7818cd31932`。
- 038独立设计SHA `769fddd904963fc7befc860fe5934221f6a361b041b2734e6bcd8a6618cf7edf`；它是建议，不是已实施成绩。

按freeze材料skill仅将033/034/035/036/037及038的小设计与显式必要资产登记至stage036独立目录；不重复复制已归档009大输入，不复制原始OHLC、DB、audit路径、env或秘密。登记终端、manifest和精确index闭包另留outputs/stage036_local_registration，成功前不在本记录捏造登记完成。只本地精确git add，不commit/push。

## 下一步、过拟合和继续价值

先完成本包本地保存与LINE/registry更新。跨日参考政策需独立复核并另冻结唯一合同，再一次执行真实epoch状态机和研究级现金建模。不能让生产资格要求变成所有研究回放的无限硬门；已有vendor规格可作为有版本、来源与局限的研究假设，净收益/DD必须在明确本金、同期预算、整数手、费用、保证金及缺失处理后才有含义。不能把单事件R简单相加称账户净值。

用户刚询问三重滤网：其“方向/回调/触发”结构有启发，暂不直接增加指标或实验矩阵；本次没有实施它或以其名称救本包。完整用户目标仍保留全市场全品种、long-only、高质量AI、窄损及加注，参考政策不是终点。

开始反思：预声明单包降低了新增结果选参风险，但反复DAY代理有目标错配风险。结束反思：本包未按成绩调参，仍不能抹去累计研究选择与非PIT重建风险。继续优化本包：否；继续完整目标：是，建立跨日政策和可解释账户证据比继续堆派生变量更直接。禁止宣称AI有效、可以加注或goal完成。

合入建议：root在登记闭包核验后统一更新本线LINE/registry。根memory/back_log不追加例行负结果，其他研究线不修改。
