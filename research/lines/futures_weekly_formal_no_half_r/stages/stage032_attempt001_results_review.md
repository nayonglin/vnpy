# Stage032 attempt001 独立金融结果审查：A会计通过，C归属失败

- line_id：`futures_weekly_formal_no_half_r`。
- 记录时间：2026-10-28 17:04（Asia/Shanghai）。独立审查者未参与策略实现、数据准备或预审。
- 结论：**A_PASS_BOUNDED_ACCOUNTING；C_INVALID_SLEEVE_OWNERSHIP**。剩余 P0=0、P1=1、P2=0。C attempt001不得进入有效A/C收益比较或晋级。
- 本轮未改策略/数据/账本/报告源码，未重跑金融策略，未重复400项测试，未下载行情、未访问生产。只保存本审查专属输出与阶段文件。
- 是否重要突破：否；本次发现真实归属与状态生命周期漏洞，预审通过与程序exit0均不能覆盖这一失败。

## 直接反证及影响

| 成交 | 合约/交易日 | 平仓前底仓+加仓 | 真实平仓 | 实际错误分配 |
| --- | --- | --- | --- | --- |
| BACKTESTING.315 | FG401.CZCE / 2023-12-11 | 10+1 | 11 | base 11、addon 0 |
| BACKTESTING.424 | SM505.CZCE / 2025-02-13 | 26+1 | 27 | base 27、addon 0 |
| BACKTESTING.489 | cu2509.SHFE / 2025-09-03 | 2+1 | 3 | base 3、addon 0 |

FG401的完整反证：2023-09-01 trade_events有计划开仓及同日forced_margin_deleverage 22手@1812，但trades没有当日真实成交；首次真实底仓为2023-11-27 BACKTESTING.310开10手@1731，12-08 BACKTESTING.314加仓86:1开1手@1898。12-08 addon events正确产生long_base_stop close_signal；12-11真实全平11手，却被旧队列以entry_price1812、forced_margin_deleverage归给base。旧未成交计划平仓占据队首，遗漏了真实addon的close_fill。

三个合约均形成base−1、addon+1的伪对冲末仓；addon状态仍为pending_close，即使真实合约净仓已经归零。报告在`unmatched_close:BACKTESTING.315`处正确拒绝。原生净仓与总权益仍守恒，不能说明真实加仓状态机正确。父pending_close_lots/reasons同样涉及该生命周期，因此原生exit_reason不能未经核验用作逐笔归因。需实现侧修复并新建attempt；禁止修CSV、删错误或放宽报告。

独立脚本中87条`missed_stop_exit`是上述孤儿addon被继续当成持仓的衍生检查失败，3条`orphan_addon_no_bar`亦来自这三个已到期合约；它们不是87个额外独立交易bug。

## 独立重算覆盖

1. A/C各自`terminal.json`均为completed_pending_independent_review且error=null，不能据此称金融审查通过。实际区间2020-01-02—2026-10-28，均1651个交易日；首日权益150000，预加载无财务状态，属于新账户回放。
2. A/C input_manifest均2628绑定，合并后2628个唯一绑定；本次逐文件SHA重算零缺失、零变化、零冲突。该结论是17:00前后当前冻结版核验时点，未来修复不能覆盖历史绑定。
3. 独立直接读取批准SQLite日K，逐笔校验全部464/596真实fills的同约open与正量，重建净库存和现金；A3417/C3326条财务活跃position行逐条核验raw close、前收、起末库存、费用、滑点、holding/trading PnL，逐日聚合及内部estimated_equity与外部权益均一致，终端cash+MTM一致。
4. C全部95个signal按原始同约物理年代日K验证前收、连续2日严格上涨、两日low固定stop；94个真实开仓均为1手、同约下一交易日open且open>stop。实际次数逐round≤2，51次roll记录继承实际次数；95个pending锁/退出后重数、94个开平状态、3098个snapshot的账本一致性检查完成。状态机与错误owner账本彼此一致仍不足以通过，必须以真实净仓零状态为终局反证。
5. 95个signal的原始保证金、signal equity、风险预算及各启用容量上限完成复算；94个实际开仓按冻结D2预算、记录的共享调整量复算开盘margin/risk及所有容量约束，通过。共享调整量算法本身沿用已通过的独立预审及代码阅读，本轮没有把记录值误称完整实时券商账户真值。该预算检查不能修复owner失败。
6. 1次未成交cancel留存，不消耗实际次数；C事件总计signal95、open_fill94、close_signal94、close_fill91、roll51、cancel1。close差额恰对应三个失败addon；无证据支持有效期末未平加仓。

## 数值：A可用，C仅用于定位失败

| 项目 | A 未加仓 | C attempt001（已拒绝） |
| --- | ---: | ---: |
| 期末权益 | 1,259,840 | 2,410,910 |
| 总收益 | 739.893333% | 1507.273333% |
| 最大回撤 | −55.042917% | −46.636793% |
| Sharpe | 0.955173 | 1.140873 |
| 总滑点 | 81,020 | 145,450 |
| 手续费 | 0 | 0 |
| 原生实际fills | 464 | 596 |

A的原生完整同约flat-to-flat周期228个：赢109、亏118、平1，胜率47.8070%；平均盈利23,003.85，平均亏损15,427.97，平均盈亏比1.491049，Profit Factor1.377325，已平周期净收益686,920。期末4个未平合约，未平周期净MTM422,920；合计1,109,840，与期末权益减本金一致。该口径不跨换月强行合并logical cohort，不是成交次数或每日非零胜率。

C原生总账数字能重算，但owner会计不成立；独立脚本产生的C sleeve统计、末仓MTM不能发布为有效收益分析。不得基于这份C三项headline判断预声明收益/DD/Sharpe门槛通过，也不得把直接加仓贡献和资金路径影响相加后声称已解释收益提升。

## 物料和证据

- 失败adapter SHA256：`560232fcf1227a37f3d6c81613db422d6bdfff1472da4070e855eb87a77aadac`。
- 绑定旧源码副本：`outputs/stage032_attempt001_rejected_source/stage032_daily_addon.py`；runner和测试副本同目录，receipt列原路径与digest。审查JSON逐项重算副本SHA并记录原路径→副本映射，不以未来current源码代表本次失败版本。
- 本审查独有输出：`outputs/stage032_results_review/`内两个独立脚本、A/C原始SQL会计重算JSON、C规则审查JSON及2628绑定复验JSON。
- `stage032_attempt001_results_review.json`保存原始失败证据、结果及所有attempt输出/旧源码/审查输出SHA。原账本未改。

## 数据、置信度和推广边界

- 对A声明日K执行模型下会计正确性置信度高；对C失败判断置信度高，有可复算直接反证。对C alpha有效性不下结论，必须等待修复后的完整新attempt和新的结果独审。
- 本轮批准数据完整到2026-10-28，minute/proxy/AI读取为0；日K open并非真实可成交/容量/涨跌停订单证明。历史mapping和样本内开发不构成PIT/OOS；零手续费、静态元数据及供应商后续修订边界保留，不能声称“数据全准”。
- 实际配置风险量为静态交易所保证金×1.65；旧daily/metrics的broker10×1.1指标不能替代该口径，也不能当历史真实券商保证金。失败C不发布保证金优势结论。
- 外部调研复核vn.py官方组合回测源码及官方逐日盯市说明：持仓盈亏与交易盈亏减费用/滑点须逐日守恒；FIFO会计与独立sleeve归属是不同问题。采用这一原则独立重算，否决仅凭总权益相同放行。来源：https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py 及 https://github.com/vnpy/vnpy/blob/master/docs/community/app/cta_backtester.md 。
- 新增/修改/删除策略参数：均无。新增研究结果：上述A会计核验和C失败反证；历史结果不覆盖不删除。
- 开始/结束过拟合反思：本审查没有参数寻优，不属于新的拟合；策略本身仍是历史样本内研发，固定规则也不能产生OOS。
- 开始/结束继续价值：有，修复明确正确性bug并按同一冻结规则重跑有价值；收益比较和推广当前无效。修复不应被当作策略调参，也不应顺便搜索连涨天数/止损/手数。
- TODO：实现侧修队列生命周期及终局owner守恒闸门，新增最小回归；新attempt保留全部输入版本；由新独立结果agent全审后再比较。不推广、不启动生产。
