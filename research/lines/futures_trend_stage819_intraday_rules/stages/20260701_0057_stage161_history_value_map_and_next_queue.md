# Stage161 历史正式路线价值图与当前重建版下一步队列

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-07-01 00:57 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：从根目录 `memory.md`、`back_log.md` 和 Stage154-160 当前重建版证据做总账收束；不新增回测、不连接 CTP、不调用订单 API
- 是否重要突破：否；属于路线收束和后续执行队列定义
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：按用户此前“不要搜索了”的约束，本阶段不做外网/GitHub 搜索；只使用本仓库 `memory.md`、`back_log.md`、`research/registry.md`、Stage154-160 记录和当前输出。
- 我的判断：旧正式版达到当时水平，不是靠一个神奇参数，而是靠四类结构叠加：`PIT AI 选品`、`Stage372 recovery/margin 治理`、`Stage819/C9 进攻右尾能力`、`实盘执行 fail-closed 工程纪律`。当前重建版应继承这些结构，但不能试图用日级权益代理或局部参数扫描把 C9 风险尾“调没”。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不新增回测
- 账户规模：不新增口径；引用当前 C9/15w、Stage156/157/160 既有输出
- 成本口径：不新增成本假设
- 样本过滤：只做历史账本与当前阶段证据映射
- 策略/归因口径：历史价值图 + 当前重建版下一步队列

## 历史版本价值图

| 类别 | 关键阶段 | 历史证据 | 当前结论 |
| --- | --- | --- | --- |
| 防守正式骨架 | Stage526 -> Stage372 | Stage372/20w `official_live_stage372_20w_recovery_sleeve` 代表结果 `8,728,285 / 4264.1425% / -38.6713% / Sharpe 1.6279`；它靠正式 AI、连败严重档、受限 recovery sleeve、保证金治理形成防守参照 | 继续作为 legacy previous live default 和风险对照；不能用 C9 单臂替代对照 |
| AI 选品 | Stage404、Stage784、Stage280/281 | Stage404 关闭 AI 后收益保留仅 `7.3613%`；Stage784 在 Stage777 上 AI-off 收益/回撤全输；Stage280 修复 `eval_date` 同日生效 bug 后旧权威逐日一致 | AI 不是可有可无。当前只做 PIT、漂移、池内外归因，不做 no-AI、topN、品种黑名单救参 |
| recovery 线索 | Stage421 | all-cases recovery 全周期看强，回撤降到 `-28.6384%`、收益保留 `83.1334%`，但多起点和近期窗口失败 | 只保留为 forward/paper 强线索，不接当前正式，不按 case/品种/年份救 |
| 进攻候选链 | Stage777 -> Stage813 -> Stage819 | Stage777/813/819 证明 AM41/OI/旧 AI/RSI/资金口径有右尾价值；Stage819 30w 年度正收益 `8/9`，但 Stage824 对 Stage372 同窗口显示回撤胜仅 `5/42`、DD40 失败 `18` | 这条链是 C9 上游进攻材料，不是防守替代材料；当前优化优先风险尾而不是继续放大右尾 |
| C9 日内骨架 | Stage847/C9、Stage898/899/900 | C9 继承 Stage819，冻结 C2 intraday stop、broker10 cap、`0.5R` stop/retry once；Stage900/898 清零旧 entry-day 分钟缺口，但 Stage896/899 仍有 `-56%/-58%` 回撤尾 | C9 stop/retry 是当前唯一应保留的日内骨架；不要扫 R 倍数、重试次数、月份、品种、方向、窗口 |
| 实盘执行工程 | Stage901、927-934 | C9/15w 只改部署资金，不改 C9 逻辑；真实执行必须 read-only、dry-run、账户/持仓对账、Stage927 arming、kill switch、TCA/fail-closed | 当前优化要把 Stage160 healthcheck 固化成 gate，防 profile/AI/order API/pending drift |

## 当前重建版证据映射

- Stage155：当前重建版 AI ON/OFF 消融显示 AI ON 仍明显优于 AI OFF；AI ON 正收益 `9/9`，收益胜 `8/9`、回撤胜 `9/9`、Sharpe 胜 `8/9`。这与 Stage404/784 的历史结论一致。
- Stage156：三臂年度基准显示 C9 是当前收益/Sharpe 最强臂：C9 正收益 `9/9`、中位收益 `126.1993%`、中位 Sharpe `1.2246`；Stage372 仍是防守参照但当前重建版年度口径收益较弱。
- Stage157：C9 stop/retry 的优势主要不来自 event-day 稳定盈利，而来自后续路径/复利/持仓参与；不能按 final_state、品种、方向直接过滤。
- Stage158：C9 比 C4 回撤更深时，有相当部分是高峰值后百分比回吐，而非绝对权益一定低于 C4；C9 最大回撤窗口内 stop/retry 事件合计仅 `2`、retry_failed 为 `0`。
- Stage159：简单日级 heat/high-water 账户层代理不推广；heat90/heat80 触发太少，高水位保护损收益和 Sharpe，说明日级权益缩放不是正确优化面。
- Stage160：当前 live C9 关键路径 `8 PASS / 3 WARN / 0 FAIL`，未发现 P0/P1 逻辑 bug；P2 是 broker10 cap 仅覆盖 flat_entry、C9 合成成交 datetime 语义、Stage901 全局状态依赖。

## 可继续做的队列

### P0/P1：先做工程 gate，不改 alpha

1. 将 Stage160 healthcheck 固化为每日 shadow/临时信号前的只读 gate。
   - 证明 live profile 是 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
   - 证明 account/c3 capital 是 `150000/150000`。
   - 证明 AI 池文件存在、策略名有行、eval_date 与 PIT 语义正确。
   - 证明 C9 flags 为 `0.5R + max_retries=1 + broker10 cap + AI filter`。
   - 证明 Stage901 `order_api_called=false`，同时读取 `pending_orders`，不能只看 `signal_plan`。

2. 给 broker10 cap 的 `reverse_entry` 路径补 targeted test 或显式 guard。
   - 当前证据显示 Stage830/847/901 输出没有 `reverse_entry`，所以不是已复现 bug。
   - 但源码上 cap 只处理 `flat_entry`，基础策略默认 `reverse_on_opposite_signal=True`；未来触发 reverse path 时可能绕过 cap。

3. 给 C9 synthetic trade 输出补分钟触发时间字段的 TCA 对齐。
   - 当前日级 PnL/状态机没发现 P0/P1 错误。
   - 但 `TradeData.datetime=self.datetime` 与 `proxy_*` 时间并存，后续实盘复盘/TCA 容易误解。

### P2：只读归因，不写新规则

4. 做 C9/C4 大回撤窗口订单级归因。
   - 目标不是筛掉某个品种或月份，而是识别回撤窗口中是否有可提前看到的外生状态。
   - 如果只能用最终盈亏或历史特定日期解释，则停止。

5. 做 AI 池漂移/缺失值/排名归因。
   - 只解释“当前池为何与旧池不同”以及“被 AI 拦截候选是否仍低质”。
   - 不扫 topN，不用当前丢失文件的旧池名单倒推出规则。

### 停止/不重来

- 不关闭 AI。
- 不用 `2018-2019` 判断当前正式 AI 好坏。
- 不继续扫 `topN/maxpos/资金/RSI/OI/AM/训练窗/horizon`。
- 不救 C9 的 `R 倍数/重试次数/时段/品种/方向/月度窗口`。
- 不再推进 Stage159 这类日级权益缩放代理为正式候选。
- 不再救 no-follow 30m 降仓、确认后保本、DD30 主动半仓、forced margin 95->80、cap-only delayed restore 等已被真引擎反证路线。

## bug review 状态

- 已排除的 P0/P1：
  - live profile 指向错误。
  - live capital 未覆盖。
  - C9 `0.5R`/一次重试/AI/broker10 开关丢失。
  - AI PIT 同日泄漏回归。
  - Stage157 stop/retry 状态机异常。
  - Stage901 shadow 已调用订单 API。
- 尚需工程化的 P2：
  - broker10 cap reverse path guard/test。
  - C9 synthetic trade minute timestamp/TCA 输出。
  - Stage901 全局状态临时修改的 manifest/healthcheck 保护。

## 结果

- 期末权益：不新增回测
- 总收益：不新增回测
- 最大回撤：不新增回测
- Sharpe：不新增回测
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：本阶段形成 `5` 条可继续队列、`6` 类明确停止路线、`3` 个 P2 工程风险

## 输出文件

- report：本文件
- summary：无
- orders：无
- daily：无
- quality：引用 Stage160 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage160_current_live_logic_healthcheck_decision_stage160_current_live_logic_healthcheck_v1.json`

## 结论

- 本阶段结论：
  - 当前重建版延续原思路的方向，不是继续复刻旧中间产物，也不是继续回看调参，而是把历史证实有效的结构保住：PIT AI、C9 stop/retry、Stage372/C4/C9 对照、执行 fail-closed。
  - 当前最该做的是固定 healthcheck gate 和订单级 targeted test；如果要继续找 alpha/risk 改进，只能找入场前可见、真正外生、不会系统性砍 C9 右尾的信息。
  - 到目前为止，没有发现会导致当前 live C9 直接执行错版本、错资金、错 AI、错 stop/retry 的 P0/P1 bug。
- 是否进入下一步：是
- 下一步：
  - Stage162：把 Stage160 healthcheck 封装成可复用 gate，或者补一个每日 shadow 前的 dry-run 调用入口。
  - Stage163：为 broker10 cap reverse path 写最小 targeted test/guard，验证未来 reverse path 不会绕过 cap。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有新增规则、没有筛选历史坏窗口、没有根据回测结果调参数；它把历史经验压缩成约束和停止清单，降低后续过拟合概率。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：历史账本和当前 Stage155-160 已经足够说明哪些方向有效、哪些方向不该重来。继续价值从“找更好参数”转向“固定执行正确性”和“寻找真正外生风险信息”。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；等 Stage160 gate 或 reverse path guard 落地后更新
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；本阶段不是正式候选或重要合入
