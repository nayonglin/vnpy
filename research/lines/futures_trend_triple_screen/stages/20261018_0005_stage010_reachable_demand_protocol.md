# Stage010 无资金持仓可达上界与批量需求合同

- line_id：futures_trend_triple_screen；冻结时间：2026-10-18 00:05 CST。
- 目的：一次生成当前固定C0的初始OPEN、可能换月OPEN、普通CLOSE anchor需求；不运行金融账户、不算手数/权益/PnL，不改alpha，不按收益筛需求。
- 前置：Stage005初始事件与全局batch日历、Stage004覆盖cache、A0实际setting及其来源保持原SHA；Stage008的345行另有独立资格，不修改旧cache。

## 源码依据与判断

沿用Stage009已核官方TqSdk多序列历史流资料及本次重新核对的[文档](https://doc.shinnytech.com/tqsdk/latest/usage/backtest.html)、[GitHub源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/backtest/backtest.py)。需求语义以本仓库固定源码为准：Stage502给已见缺bar合约生成当日carry；策略_same_day_bar可读该carry；_handle_rollover在取得old_bar后先平旧、再判断是否重开。delay5首次为0、第6次due，目标变化重置，回到持有合约清pending。

只按“有真实bar的持仓日”取CLOSE会漏carry期间退出。本阶段保留可选退出的继续持有分支，但在必然发出的平旧指令后，于下一global batch移除旧合约分支；不把全部旧主一直扩到期末。新合约重开忽略形态/资金限制作为保守上界，但必须有当日目标真实bar；不要求AM41 inited，不用周门删换月重开。

## 最小枚举合同

1. 种子：Stage005 c0_allowed的非terminal初始事件，按execution_trade_date加入可能持有合约；固定reverse_on_opposite_signal=false、两种add=false，否则拒绝本简化合同。
2. 抽象状态只含product/held_contract/pending_target/elapsed；不含资金、数量、收益、胜负或账户风险。忽略可选退出，不影响未来所有原始初始种子的加入；相同状态合并。
3. 每个真实全局batch先应用前日计划的平旧/重开，再加入初始种子。mapping为空时发出可能平旧、分支次日终止；mapping等于持仓时清pending。不同目标按真实0—5计数推进，第6次及以后due即发旧CLOSE，次日终止旧分支；有当日真实目标bar时把新合约分支安排在次日。目标缺真实bar只平旧，不重开。
4. 对每个可达持仓日保守收集下一global batch的CLOSE anchor（包括carry日），初始/换月OPEN均收集完整下一batch session，末日未生效需求单列pending。先前真实入场证明旧合约已被engine见过，不伪造旧真实日线。
5. 需求按vt_symbol/filldate去重，full_session优先于anchor；与Stage004冻结覆盖表join，新增状态不能擅改原覆盖。目标filldate缺真实日线、carry或期后anchor单列，不能当作已可下载、已可撮合。该表是过近似必要数据上界，不能冒称实际交易集合。
6. 只执行一次枚举，输出demand.csv/gaps.csv/summary/input_manifest及有界状态诊断；不重跑原指标流/周表、账户或原始分钟清洗。若发现合同与源码不符，应保存失败，不用alpha变更救它。

## 验收与后续

少量合同测试覆盖首日0/第6日due、目标重置/映射回原、carry CLOSE、先平旧后次batch重开、种子跨映射及terminal；独立agent审语义与固定真实哨兵，不再重复全指标流。全部需求不能通过仅靠覆盖计数声称价格合格；真正新增分钟另走Stage011资格与append-only overlay。

过拟合判断：否，本次只按既定交易规则保守枚举数据需求，不调整策略或使用PnL。继续价值：是，生成一张有终止边界的批量清单，尽快取得真实C0结果；若清单仍含不可能获得的carry anchor，要单列其约束，不能无限补不存在数据。
