# Stage005：运行前独立审查（没有金融回测结果）

- 时间：2026-10-18 16:32 CST。
- 研究线：`futures_trend_full_market_noai_one_lot`。
- 审查者：独立 agent `preflight_review`；只读审查实现、输入、测试，未修改策略/源数据；仅新建本报告。
- 起点：master `e41a0a01d53b7256001e45e686acad53667ef7bf`；独立工作树 `codex/full-market-noai-one-lot`。
- 范围：Stage002 数据构建及加载、Stage003 候选覆盖、Stage004 执行/费用/账本、Stage001 冻结复盘适配器、三个测试文件、冻结输入 manifest；定点追踪正式继承代码和 canonical renderer。
- 金融回放次数：**0**；模型拟合次数：**0**；CTP/订单 API：**0**。本报告不是实际收益、回撤或晋级结果审查。
- 不是重要突破版本；属于数据与代码开跑前质量闸门。

## 结论与开跑闸门

**当前不允许运行金融回测。** 用户尚未回复分钟数据处理口径。即使后来选择日线代理，也必须明确接受供需 signal CSV 缺失带来的额外偏差，或先恢复身份匹配的冻结信号。不能把“分钟代理”自动扩展成“其他缺失正式过滤亦已获批准”。严格模式当前不具备 2015 年起全市场分钟 session 和分钟覆盖资格；完整日线并不能替代该资格。

未发现新增 P0。发现 3 项 P1，其中夜盘费用/交易日错位已由 root 修复并独立测试复核，另外 2 项为尚未满足的执行/证据闸门。发现 2 项 P2：HTML 可见边界披露和费用/账户集成验证范围。

## 发现与处置

### P1-1（已修复）：夜盘费用错误绑定自然日

初版 `stage004_run.py` 的 `FeeStrategy.update_trade` 及导出成交 `date` 使用 `trade.datetime.date()`。Stage827 引擎却已在 `calculate_result` 中按 `trade.trading_date` 记账。周五夜盘属于周一交易日，会造成平今手续费识别错误、费用落入前一自然日或周末、账户账本与汇总费用错位。

root 已增加 `accounting_date(trade)`，优先显式 trading_date，并用于同日手续费和成交 date；physical datetime 保留。独立复核新增 Friday 21:00 → Monday trading_date 合成用例通过。不得据此宣称真实手续费历史准确；费用仍是已披露静态快照。

### P1-2（未满足）：严格分钟模式缺少全市场/全历史交易时段合同和输入

`qmt_roll_intraday_execution.session_minutes` 只覆盖原正式小池，采用冻结 2020+ 时段，regex 不接受 `_F` 家族，尚不具备六所 93 品种、2015 年起历史制度变化的会话覆盖。Stage827 完整分钟/开盘锚点闸门仍为 true，缺失应停止；这是正确的 fail-closed 行为，不能关闭闸门冒称严格复现。

处置：继续等用户选择日线代理、补充分钟或只交付缺口；选择补分钟后仍须先补全并验证 session 合同。禁止在当前输入上运行 strict 后将部分回放当完整结果。

### P1-3（未满足）：正式供需过滤启用但缺身份匹配的冻结信号

本机缺 `supply_demand_signal_path` 指向的 signal CSV。上游 `_load_supply_demand_signals` 在路径不存在时只写日志并 return，不主动失败。因此开关继承为 true 不等于正式供需过滤被真实执行。

处置：恢复并 hash 冻结匹配信号，或由用户明确接受缺失供需过滤的研究近似，版本名、协议及可见 HTML 都必须披露。不得声称“其余正式规则完整复现”。

### P2-1：运行边界需要进入可见 HTML

审查时 `stage001_frozen_recap.py` 的 source_warning 已披露残余仓、背景代理、逐笔毛收益和费用口径，但没有将冻结 metrics.mode/boundaries 拼入页面。daily-proxy 关闭 C2/C9、静态非PIT规格、供需源缺失等只在 JSON/manifest 可查。建议将这些关键边界进入页面首部可见说明，防止读者把研究页当完整正式回放。此项不要求修改 canonical HTML 实现，只需适配器传入真实 warning。

### P2-2：现有测试证明合同，不证明真实账户结果

合成测试覆盖固定参数、全部空头 case、缺真实 bar 不成交、手续费函数、交易日绑定、数据映射、残余仓与冻结渲染合同。尚未用真实金融回放验证多品种同时成交、换月、真实残余仓、手续费/滑点与策略账户逐日一致。Stage004 已有逐日账户权益误差 <=1e-5、每笔 volume=1、同合约重复 open 及每产品日终绝对持仓合计 <=1 的后置断言。

后续实际运行须保留这些闸门，并独立复核成交顺序中的每产品手数、费用总额、剩余未平仓的 MTM 与 closed ledger。当前报告不能替代用户要求的“每次实际回测完成后另拉独立 agent 全面 review”。

## 数据与逻辑核验

- `source_manifest.json` SHA256：`60c1f64a5fb97d7be7ada5e6bfdd97005bf356d959daf5b497f5117544c3a761`；其中代码 hash 与当前 Stage002 相符，四个冻结 CSV 均由 load_source 重算校验通过。
- 93 个历史产品、4328 个合约 epoch、809279 根真实日线；截至 2026-10-16。六所均在集合内。此处“全市场”准确含义是 clean 源中接受且实际可观测的历史产品集合，不能据此证明所有交易所历史合约无缺失。
- 无 volume<=0、非正 OHLC 或负 close_oi；没有 observation_date>=effective_date 的映射。3056 个已映射产品日缺有效当日日线，保持缺失，不按当日可见性回选另一个合约。
- 主力选择采用上一源交易日 close_oi、volume 及稳定 epoch tie-break，只次日生效；不前填缺观测。尚未发现直接使用当日 OI/成交量或未来存活名单决定当日信号的问题。
- 从全历史取“曾被因果规则选中”的 epoch 用于 materialization，保留其完整可用预热和持仓历史；不是用未来收益筛选。上市、到期、乘数、费用、保证金与 tick 来自供应商快照，非历史公布时点/PIT 认证，残余历史制度偏差必须保留披露。
- 3705 个 exact-contract fee/tick、623 个 product fallback；2456 个按手费、1872 个按金额费。按手费用没有因为 engine rate=0 而丢失；open/close/close-today 显式分开，精确 instrument margin 优先于 product fee fallback 的 margin。future_info 中 generic product 行有 94 个，未见重复 product fallback 键。
- 正式信号/退出与账户/保证金风控仍通过完整 profile 继承；固定1手会绕过原按风险金额变手数的含义，不等风险、不等正式资金暴露。较低波动或回撤不能自动归因于 alpha 提升。
- 日线引擎只将当前真实 bars 传入 on_bars；缓存仅用于估值。延迟订单还需当前 history_data 的真实正成交量 bar，缺失不成交。未用 ffill 合成信号/成交。
- 期末未平仓不强平；完整交易图排除 residual/部分未完成 entry，单独写 residual_open_positions。账户收益含实际持仓 MTM；closed ledger 胜率按已完成净费交易；HTML 单笔按合约价差毛收益，已有明确说明。
- canonical `_context_daily` 对 product 使用 lower()，未发现曾怀疑的 metadata.product 大小写匹配 bug。
- 复盘适配器编译 canonical 纯显示函数 AST，不导入整个策略/下载入口；必需成员 hash、成交ID、交易区间和笔数验证、输出隔离与缺分钟说明已覆盖。实际交付仍需 JS parse 和浏览器默认周期/筛选/导航/缩放验证。

## 独立验证证据

- 独立运行 `unittest discover`：首次 13 项通过、3 项因沙箱不允许 vn.py 日志写入该工作树而报环境 PermissionError；提升为授权普通测试日志写入后原 16 项全部通过。
- 夜盘修复后再次独立运行：**17 tests / OK**，耗时约 1.7 秒；只用 synthetic fixture，没有调用 run(mode, output)、没有实际金融结果。
- `git diff --check`：通过（本线仍为未跟踪新目录，因此该命令并不等价于完整逐文件格式审计）。
- 调研与判断：本轮是已有实现独立复核，沿用主任务已查阅的 vn.py 官方/GitHub 材料；定点核对本仓实际 Stage502/827/847、portfolio backtesting 与 canonical Stage038，判断应复用真实成交路径与冻结展示合同，不另造撮合或补造分钟。

## 回测记录要求占位

期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：**均未运行，不适用，不填入任何示例数字**。新增/修改/删除金融回测结果：无。新增研究策略参数和执行变化以 Stage003/004 及 protocol 为准；本独立审查没有改参数。

## 反思与后续

- 开始及结束的过拟合判断：**否**，本轮未看收益寻参，仅审查固定政策、数据因果性、费用及证据闸门；Stage037 上游历史选择偏差和静态规格偏差仍存在，未来结果不能直接称样本外 alpha。
- 开始及结束的继续价值判断：**是**，固定一手、全市场、关闭AI/放开空头是可证伪整体政策实验；当前最有价值动作是明确代理边界和补证据，继续跑不完整严格回放没有价值。
- TODO：等用户分钟口径；明确供需缺失的接受/恢复路径；可见HTML披露；冻结最终代码身份；再运行一次已批准口径，随后另派独立结果审查并验证HTML。
