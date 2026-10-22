# Stage004 周线：关闭0.5R、C2及AI选品，2020年至今回测

- 记录时间：2026-10-22 21:52 CST；line_id=futures_weekly_formal_no_half_r；day模式；重要突破：否。分支codex/weekly-no-half-r-20261022，沿用Stage002已验收周线实现。正式m0008/Stage037/15万，远端master已用SSH核验仍为e41a0a01d。仅研究，不涉及生产资格/CTP/定时任务。
- 用户指定三项全部关闭；D=周线+halfR=False+C2=False+AI product filter=False。对照C为上轮周线halfR=False、C2/AI=True；A为原正式日指标对照。相对C只有C2和AI两项有效参数差异，半R原已关闭。
- 原基础池19品种全部可过AI资格门，不扩大全市场；fu只是基础池普通品种，不再有AI固定排名。AI load_status=disabled/0快照；82条候选的AI enabled均0、allowed均1、分数/排名0、月池signal_date空，未使用AI选品。
- 全部技术指标仍为完整周，41观察周门槛、周期数值、方向约束、资金/风险预算、当日价格止损、真实首分钟成交、逐日盯市及5交易日换月保持。正式策略源码修改0。新增参数0，删除参数0；C2和AI开关True→False，半R继承False。新增独立runner/成交锚补缺工具，原A/C输出与源缓存不覆盖。
- 请求2020-01-01—2026-10-22，实际1647交易日2020-01-02—2026-10-22，初始本金150000。手续费沿用正式回测0、正式滑点保留；不能当含真实手续费和流动性冲击的生产结果。新增有效全窗结果D1个；旧结果修改0、删除0。

## 完整结果（独立逐笔重建）

| 指标 | A正式对照 | C上一版周线 | D三项全关周线 |
| --- | ---: | ---: | ---: |
| 期末权益 | 2,250,195 | 252,800 | 323,250 |
| 总收益 | 1400.1300% | 68.5333% | 115.5000% |
| 最大回撤 | -49.0705% | -15.0662% | -16.3402% |
| Sharpe（252日样本标准差） | 1.362404 | 0.704659 | 0.729030 |
| 总滑点 | 605,850 | 5,450 | 7,360 |
| 总成交次数（开平分别计） | 817 | 72 | 100 |
| 闭合FIFO匹配段 | 414 | 36 | 50 |
| 匹配段胜率（双边滑点后） | 30.1932% | 38.8889% | 44.0000% |
| 手数加权胜率 | 23.4051% | 34.7826% | 40.8654% |
| 期末未平手数 | 0 | 0 | 0 |

- D比C期末权益增加70450元、收益增加46.9667个百分点，回撤恶化1.2740个百分点，Sharpe仅增加0.024370。收益增加伴随保证金活跃日148→300、平均保证金占权益2.347974%→4.674902%，不能只把增加归因于更强alpha。
- 2020/2021不如C，2022—2025优于C，2026截至10-22收益D-7.6138%/C-7.5753%，改进非逐年占优。2025 D+33.9394%/C+6.7104%是显著贡献期。年度表和权益回撤图见artifacts/stage003_annual_results.csv、stage003_equity_drawdown.png。

## 数据和独立review

- 最终D_attempt011。前10次因缺真实成交锚退出，均不计完整绩效。两个盘中模块均关闭，所以minute_scan及halfR/C2/intraday事件全部0；但100次真实成交首分钟锚仍严格校验，禁止旧价或日线open代替。
- 本机冻结完整CSV提取42369个09:00/21:00候选，零冲突/非法；只填原缓存缺键，D实际用了其中20个唯一锚，逐个回原CSV核价格及原冻结SHA。原目录与所有旧proof未修改。
- 另从15份上轮已验收Tq原快照派生762个单分钟task，保留parent proof SHA及earliest/latest/snapshot边界。其余实际缺锚才用Tq只读请求1000根已完成快照，每片仅取实际缺失1分钟。
- 独审6508输入SHA0差；90份分钟proof共357575行原raw、SHA、快照边界、旧parent身份核对0差。overlay重复/冲突0。100成交锚0差；436实际持仓/成交合约日日线0缺0差；权益重建最大残差1.17e-10、每日成本和持仓数量核对通过。
- 23677根周线逐条回SQLite重新聚合0差。102日无满足41周的映射目标，ready目标中位3/映射中位17，历史覆盖限制延续，不能据此评价所有周线策略。
- 原周线/会计/成交回归8+62=70项通过；不是全仓测试。独立审查见stage003_independent_review.md及stage004_independent_audit.json。
- raw metrics的label/note及deployable_pass为继承来源元数据，不能当实际开关或生产资格；D实际身份以arm/result_scope、参数表、AI候选及0事件审计为准。

## 调研、反思和决定

- 调研：[VeighNa官方GitHub撮合源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)。判断：关闭盘中风控不等于可以同时改成交模型，沿用本仓库已验收的先成交、后生成新信号与真实首分钟价格约束。
- 决策：RESEARCH_ONLY_NO_PROMOTION。D优于旧周线C的全窗收益，但Sharpe仅略好、回撤略差、暴露约翻倍，且无法分别归因C2与AI；未做独立起点、walk-forward或成本压力，不能替代正式版。
- 开始过拟合：否，用户预设模块消融、不搜索阈值。结束：本轮仍未按成绩调参，无新增调参过拟合证据；连续同窗研究存在选择偏差，不能宣称OOS。D未使用AI资格门，不再继承AI静态池边界的直接影响，但既有参数和品种的历史选择偏差仍在。
- 开始继续价值：是，检验三项关闭的联合效果。结束继续价值：有限但有，可作为周线研究候选进入预声明独立起点验证；不支持直接晋级或扫描参数救收益。本次只完成指定全窗，不追加新实验。
- TODO：保留本分支与原始证据；下一步若获用户指定，再另冻独立验证合同；不合入正式、不发布、不新建任务，订单/撤单API0。

## D所有尝试（上海程序时间）

| 尝试 | 开始 | 结束 | 状态 | 原始原因 |
| --- | --- | --- | --- | --- |
| D_attempt001 | 21:29:23 | 21:29:54 | 缺真实成交锚，拒绝成绩 | RuntimeError("ValueError: ValueError('intraday_open_anchor_missing:fu2109.SHFE:2021-06-21:2021-06-18 21:00:00')") |
| D_attempt002 | 21:31:36 | 21:32:10 | 缺真实成交锚，拒绝成绩 | RuntimeError("ValueError: ValueError('intraday_open_anchor_missing:au2206.SHFE:2022-03-15:2022-03-14 21:00:00')") |
| D_attempt003 | 21:34:13 | 21:34:53 | 缺真实成交锚，拒绝成绩 | RuntimeError("ValueError: ValueError('intraday_open_anchor_missing:ru2209.SHFE:2022-08-17:2022-08-16 21:00:00')") |
| D_attempt004 | 21:36:56 | 21:37:37 | 缺真实成交锚，拒绝成绩 | RuntimeError("ValueError: ValueError('intraday_open_anchor_missing:lh2305.DCE:2023-04-20:2023-04-20 09:00:00')") |
| D_attempt005 | 21:38:20 | 21:39:02 | 缺真实成交锚，拒绝成绩 | RuntimeError("ValueError: ValueError('intraday_open_anchor_missing:au2312.SHFE:2023-11-08:2023-11-07 21:00:00')") |
| D_attempt006 | 21:39:47 | 21:40:30 | 缺真实成交锚，拒绝成绩 | RuntimeError("ValueError: ValueError('intraday_open_anchor_missing:FG401.CZCE:2023-11-27:2023-11-24 21:00:00')") |
| D_attempt007 | 21:41:23 | 21:42:06 | 缺真实成交锚，拒绝成绩 | RuntimeError("ValueError: ValueError('intraday_open_anchor_missing:FG401.CZCE:2023-12-06:2023-12-05 21:00:00')") |
| D_attempt008 | 21:43:10 | 21:43:55 | 缺真实成交锚，拒绝成绩 | RuntimeError("ValueError: ValueError('intraday_open_anchor_missing:AP405.CZCE:2024-04-19:2024-04-19 09:00:00')") |
| D_attempt009 | 21:44:48 | 21:45:34 | 缺真实成交锚，拒绝成绩 | RuntimeError("ValueError: ValueError('intraday_open_anchor_missing:au2502.SHFE:2025-01-22:2025-01-21 21:00:00')") |
| D_attempt010 | 21:46:17 | 21:47:04 | 缺真实成交锚，拒绝成绩 | RuntimeError("ValueError: ValueError('intraday_open_anchor_missing:au2504.SHFE:2025-03-31:2025-03-28 21:00:00')") |
| D_attempt011 | 21:47:51 | 21:48:48 | 完整回放 | 无 |
