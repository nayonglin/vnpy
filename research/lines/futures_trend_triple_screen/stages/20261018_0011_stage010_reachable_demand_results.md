# Stage010 无资金持仓可达上界与批量分钟需求结果

- line_id：`futures_trend_triple_screen`
- 当前模式：纯抽象状态、零账户、零网络的数据需求枚举；`production_qualified=false`。
- 记录时间：2026-10-18 00:11 CST，读取时钟后记录。
- 工作区/分支：`/Users/mac/Desktop/fian` / `codex/ai-training-data-expansion`。
- 阶段性质：固定 C0 的初始 OPEN、可能换月 OPEN、普通 CLOSE 数据上界，不是实际交易或金融回测。
- 是否重要突破：否；形成一张有强制终止边界、可直接供批量补数使用的需求表。
- 是否触发A/B：本阶段不新增金融 A/B，不改 alpha、模型、周门、费用或正式执行合同。

## 外部调研与判断

- 参考资料：沿用 Stage009/010 的 [TqSdk 官方回放文档](https://doc.shinnytech.com/tqsdk/latest/usage/backtest.html)与 [GitHub 回放源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/backtest/backtest.py)；需求时序以本仓冻结源码为准。
- 本地依据：Stage502 `new_bars` 先撮合再调用策略、缺真实 bar 时给已见合约生成同日 carry；策略 `_same_day_bar` 可读 engine carry；`_handle_rollover` 先平旧后判断重开；delay5 首次 0、第六次 due，目标变化重置，回到持有合约清 pending。
- 我的判断：仅核真实持仓日会漏 carry 退出，全部旧主保留到期末又会制造过大上界。本阶段忽略可选退出以保留持有分支，但遇到必然平旧后于下一 global batch 删除旧分支，兼顾保守性与有限终点。全部清单仍是过近似数据上界，不能冒称实际交易集合。

## 本次变更

- 新增脚本：`tools/stage010_reachable_demand.py`、`tools/test_stage010_reachable_demand.py`。
- 修改脚本：无，Stage001/002/004/005/007/008 和正式源码不变。
- 删除脚本：无。
- 新增参数：独立 `--enumerate` 入口，已有输出拒绝覆盖；抽象状态仅 `product, held_contract, pending_target, elapsed`。
- 修改参数：无策略参数修改。固定断言 reverse、regular add、Donchian add 均关闭，并额外核对 post-quality add 的原默认值关闭，避免遗漏额外 OPEN 路径。
- 删除参数：无。
- 固定口径：`rollover_delay_trading_days=5`、换月重开及同量形态模块开启、`target_contract_only`，初始空仓、2020-01-01 起交易。

## 回测/归因参数

- 数据区间：2020-01-01—2026-10-14，Stage005 原全局 batch 日历中的 1,641 日。
- 账户规模：N/A；不含手数、资金、权益、收益、胜负或账户风险。
- 成本口径：N/A；未计算成交、费用或滑点。
- 样本过滤：复用 Stage005 `c0_allowed` 701 个原始初始事件，其中 700 个非 terminal 事件按实际 `execution_trade_date` 加入种子；另 1 个末日事件只列 pending。
- 策略/归因口径：先应用上一 batch 计划与当日初始种子，相同抽象状态合并。忽略形态与资金限制作为换月重开的保守上界，但要求信号日有目标真实 bar，不按周门删换月。普通 CLOSE 保守覆盖每个可达持仓日的下一 batch，包括 carry 日。
- 需求等级：同 `vt_symbol × execution_trade_date` 去重，`full_session` 优先于 `anchor`。初始/换月 OPEN 需要完整 session，普通 CLOSE 需要首分钟 anchor。
- 覆盖口径：只 join Stage004 已冻结 base＋Stage002 时间覆盖；不重新读分钟或重做清洗。Stage008 的 345 行只标记为独立已合格候选，不并入旧覆盖。
- 唯一实际命令：`.py311/bin/python research/lines/futures_trend_triple_screen/tools/stage010_reachable_demand.py --enumerate`，仅执行一次，退出码 0，主体用时 0.985 秒。

## 结果

- 期末权益：N/A。
- 总收益：N/A。
- 最大回撤：N/A。
- Sharpe：N/A。
- 总滑点：N/A。
- 总交易次数：N/A。
- 胜率：N/A。
- 其他关键指标：28,268 个唯一 session 需求，冻结覆盖满足 4,959 个、缺 23,309 个；所需缺分钟合计 281,335，不是全部缺口日的全日分钟总量。

| 需求等级 | 总需求 session | 已满足 | 缺口 session | 说明 |
| --- | ---: | ---: | ---: | --- |
| full_session | 1,162 | 391 | 771 | 700 初始 OPEN＋471 换月 OPEN，9 个 key 重合 |
| anchor | 27,106 | 4,568 | 22,538 | 与 OPEN 重合的 CLOSE 已按 full 优先合并 |
| 合计 | 28,268 | 4,959 | 23,309 | 等级已互斥去重，可相加 |

- 472 个抽象状态触发 mandatory 旧仓平仓，均为 rollover due；产生 471 个唯一换月重开种子。状态峰值仅 22，累计 state-day 27,796，期末 19 状态，没有把所有旧主合约扩张到期末。
- 20 个末日未生效需求单列 pending：不是已执行委托，也不回填成交。
- 缺口涉及 491 个合约；23,293 个缺口 fill 日有真实日线，另 16 个无真实 fill bar，全部是 fu 的 CLOSE anchor：fu2005 2020-04-07—15 中 7 个 batch；fu2009 2020-08-11—19 中 7 个 batch；fu2605 2026-05-06—07 中 2 个 batch。
- 这 16 个是可达上界中的 carry/缺真实日线约束，部分可能只是“每个持仓日均允许退出”的过近似；不能据此认定实际 C0 必须在那里成交，也不能直接当可下载或已可撮合数据。
- 13 个需求包含可能 carry 信号日。信号日是否真实 bar 与 fill 日是否真实 bar 分别记录，不用自然日或下一产品真实 bar 日替代 global batch。
- Stage008 已独立合格的 rb2010 2020-08-12 session 在需求中出现 1 次，只注释候选资格，原 Stage004 覆盖和缺口数字未被修改。
- 4 个 focused 契约测试 red→green 通过：首次 0/第六次 due；目标变化 reset 与回原清 pending；carry CLOSE、跨 mapping 种子与下一 batch 平旧重开；末日 pending 与 full 优先。
- 新增网络 0、金融回放 0、账户引擎 0、策略初始化 0、指标流重算 0、周表重算 0、PnL 字段读取 0、模型训练 0、源写入 0。输入全部前后 SHA 不变。
- 已请求独立 agent 核查语义、源绑定和固定真实哨兵；本记录写入时等待返回，不重复完整枚举或旧指标流。

## 输出文件

目录：`outputs/stage010_reachable_demand/`。

- report：本阶段记录。
- summary：`summary.json`。
- orders：N/A；`demand.csv` 是数据需求，不是实际委托。
- daily：N/A；无账户日权益。
- quality：`input_manifest.json`、`attempt_started.json`。
- 批量接口：`demand.csv`，必备列 `vt_symbol, execution_trade_date, requirement_kind`；附原因、signal carry、fill 真实 bar、冻结覆盖与缺口字段。
- 缺口清单：`gaps.csv`；已获得冻结覆盖的 key 不在此文件。路径候选或时间覆盖不能代替价格资格。
- 有界诊断：`state_counts.csv`、`mandatory_transitions.csv`、`terminal_pending.csv`。
- demand SHA256：`670766157d0ed3973080b793bedd88978dda0f8a44de07f243d773718f2dafba`。
- gaps SHA256：`5dc9a4000948f7f1ea4550cd5f63fbaff82462458b4d0cd6d96d03879041a4e4`。
- 其余输出指纹见 summary 的 `artifact_sha256`。Stage011 可使用该固定接口生成补数与资格计划。

## 结论

- 本阶段结论：已一次生成当前固定 C0 的有限可达数据上界，明确区分 771 个全 session 缺口与 22,538 个 anchor 缺口，避免逐缺口金融回放或下载整个旧主上界。
- 是否进入下一步：是，进入 Stage011 的本机源资格核查与批量补数计划；不自动合并行情或重跑账户。
- 下一步：先核已有 completed 源对需求的实际覆盖，沿正确 CSV/DB OI 语义验收；剩余可取真实 session 才制定一次性提供商批量计划。16 个无真实 fill bar 约束单列处理，不能补造分钟或偷偷启用日线 fallback。

## 过拟合反思

- 运行前判断：否，按已定规则枚举数据需求，不使用收益选择路径。
- 运行后判断：否，未改变 alpha 或参数，保守忽略退出/资金/形态限制并透明标注过近似；没有用结果缩窄需求或掩盖 carry 约束。
- 原因：本阶段是依赖闭包，不是策略绩效证据；后续仍需完整 C0 与独立审查才能讨论滤网效果。

## 继续价值反思

- 运行前判断：是，需要一次形成可供批量数据工作使用的清单。
- 运行后判断：是，接口与数量已明确且状态规模有界；下一步应直接补数/验收，避免再次重算旧信号或宽泛覆盖上界。
- 原因：既保留可能因账户变化出现的需求，又在 mandatoryclose 后终止旧分支，消除了无边界扩张与逐个金融重跑的主要低效来源。

## 合入建议

- 是否更新本线 `LINE.md`：由 root 汇总后统一更新，本任务未改。
- 是否更新 `research/registry.md`：由 root 决定，本任务未改。
- 是否追加根目录 `memory.md/back_log.md`：否，当前只是本线数据阶段，未形成正式候选晋级。
- 由 root 统一登记代码与小证据；本任务不登记资产、不并入 base/overlay、不启用 fallback、不授权 C0_attempt3。
# 独立复核补记（2026-10-18 00:25 CST）

`first_screen_independent`完成有限审查，P0/P1=0，receipt SHA为`58eef7e21536b372d3704eb012d0d7dba0118beccca4d0d920553ef9b73ebd32`。独立手算4个真实mapping边界与抽象状态一致，18个输入SHA未变，未重跑闭包/指标/账户；唯一键与full优先字段检查通过。16个无真实fill日仍为约束而非下载单。该结论接受条件上界及有限边界，不证明所有分支可成功撮合或价格已验收；不批准C0_attempt3。

