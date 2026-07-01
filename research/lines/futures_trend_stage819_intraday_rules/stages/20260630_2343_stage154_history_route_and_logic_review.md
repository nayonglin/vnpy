# Stage154 历史正式版路线复盘与当前重建版逻辑审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-30 23:43 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：按用户要求，从 `memory.md`、`back_log.md`、相关研究线 `LINE.md` 和当前代码出发，复盘旧正式版达到当时水平的关键版本链，提炼当前重建版可继承的优化路线，并做一次逻辑 bug 审计。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本轮按用户此前“不要搜索”的约束不做外网/GitHub搜索；只使用仓库本地历史账本、研究线记录和当前代码。
- 我的判断：当前最有价值的不是重新扫参数，而是先把旧正式版的有效结构拆出来，明确哪些路线已经被反证，哪些 bug 类需要回归验证，然后围绕当前重建版的新基线做低自由度、可解释的优化。

## 历史正式版怎么走到当时水平

### 1. Stage78/78-1：早期正式趋势骨架

- `78-1` 固化为 `official_stage78_1_defensive_50w_no_sizing_cap`，50万、关闭 sizing cap，参考结果为期末权益 `25,542,885`、总收益 `5,008.5770%`、最大回撤 `-40.0607%`、Sharpe `1.1295`。
- 这个阶段的长期经验不是“资金越大越好”，而是 cap 会显著压制复利效率，但执行容量和滑点压力也同步放大。
- 对当前的继承价值：保留它作为历史趋势家族和复利/容量对照，不要把它直接当当前实盘信号源；当前 live policy 已明确不得自动 fallback 到 Stage78。

### 2. Stage526 -> Stage372：20万正式实盘默认防守骨架

- Stage526/Stage653 一度是高收益 all-in 路线：20万、`r080_pc25_maxpos4`、保证金强制减仓 `95% -> 80%`。
- Stage372 在此基础上把“受限恢复仓 sleeve”固化为正式口径，最终成为 `official_live_stage372_20w_recovery_sleeve`。典型全周期参考：`8,728,285 / 4264.1425% / -38.6713% / Sharpe 1.6279`。
- Stage421 all-cases recovery 是当时最强的简单风控线索，全周期能把回撤降到 `-28.6384%`，但多起点失败，尤其近期窗口和季度冷启动不过关，所以只保留为 paper/forward watch，不接正式版。
- 对当前的继承价值：Stage372 是“低于 C9 进攻口径”的稳健参照物；以后评价当前重建版，至少要保留 Stage372/C4/C9 三臂对照，不能只看当前 C9 单臂。

### 3. AI 选品：不是可有可无，也不是随便重排

- Stage404 在 Stage372 上关闭 AI 后，交易从 `633` 增到 `853`，但期末权益降到 `827,790`，收益保留仅 `7.3613%`；结论是 AI 过滤的是大量低质量机会，不是简单减少机会。
- Stage784 在 Stage777 上关闭 AI，同样收益和回撤全部输给 AI-on；AI-off 年度起点 DD40/DD50 失败严重。
- Stage280/281 修过一个非常关键的 PIT bug：AI `eval_date` 必须用 `side="left"`，exact eval_date 当天仍使用上一期快照。修复前控制组相对旧权威差 `1,229,815`，日度 PnL 差异 `503` 天；修复后逐日完全一致。
- Stage405-407 证明“加一个品种再 full-market AI 重排 topN”会破坏旧核心右尾；原 AI 池不变时鸡蛋有价值，但进入共享主账户排序后会挤占 `jm/oi/fu` 等核心赢家。
- 对当前的继承价值：AI 必须保留，但要严格 point-in-time；新增品种/新 AI 池应该先做只读归因和不挤占核心右尾验证，不能从“特征在、菜谱在”直接推导为“新池一定等价旧池”。

### 4. Stage777/813/819：高收益高回撤候选链

- Stage777 采用旧正式 AI 老师、`AM41`、基础等效风险 `0.40`、命中 `OI上升 + 价格沿方向` 恢复到 `0.80`。Stage792 把它登记为官方候选，但明确不是 live default。
- Stage793 Monte Carlo 显示它右尾强，但 DD50 概率显著高于 Stage372；坏块前置后回撤可扩大到 `-57.4836%` 甚至 `-78.4958%`。
- Stage813/819 继续在这个家族上做多头更紧初始止损、RSI95半平、30万资金等工程化，但 Stage824 证明 Stage819 虽收益更高，却有 DD40 失败，不替代 Stage372 live default。
- 对当前的继承价值：这是进攻型候选材料，不是防守替代材料。当前 C9 live default 继承了这条高进攻家族，所以优化目标应优先控制风险尾，而不是继续追求右尾放大。

### 5. Stage847/C9：0.5R 实时止损 + 一次重试

- Stage023 首次验证 C9：`C4 + 0.5R 实时止损 + 原入场价重回后允许一次重试`，收益和 Sharpe 更高，broker10 峰值下降，但当时最大回撤相对 C4 恶化。
- Stage036/037 补齐全周期分钟K覆盖，Stage039/863 在 full minute 口径下 C9 相对 C4 表现改善，但 broker10 可超过 `114%`。
- Stage898/899 解决数据 P0 后仍显示 C9 有高风险尾：月度起点 worst DD 近 `-58%`，Stage896 有 DD40/DD50/broker100 风险尾。
- Stage056 明确反证禁止跨时段重试：跨时段重试原始 matched PnL `+1,138,795`，same-session-only 代理会少赚。
- Stage057-064 反证加仓/sleeve 继续放大右尾的路线，broker10 和回撤失控；Stage065-067 反证继续沿 `0.5R/1R/OR/first60/OI/volume/session` 小变体救参。
- 对当前的继承价值：C9 的实时止损重试是唯一正价值日内骨架，当前要保留；但继续优化不能再救 R 倍数、重试次数、时段边界、利润锁、小分钟形态或加仓 sleeve，应转到账户/持仓层生存线、全市场连续分钟面板或外生低自由度信息源。

## 已经被反证或不建议重来的路线

- 关闭 AI：Stage404/784 已经强反证。
- 用 `2018-2019` 判断 AI 好坏：首个 AI eval_date 为 `2019-12-31`，且 exact eval date 当天不生效，该区间 AI-on/off 可完全一致。
- 放慢 AI 月更或强行保留旧池：历史记录显示更像掩盖漂移，不是提升泛化；正确方向是做池内外只读归因和新增品种质量审计。
- full-market AI 重排替换旧正式池排序：Stage405/407 已显示会破坏核心右尾。
- 继续扫 `topN/maxpos/风险倍率/恢复仓冷却/RSI阈值/回撤阈值`：多数已经有明确反证，容易变成窗口补丁。
- 禁空头、空头固定砍半、固定加单品种、直接关闭 maxpos4：都在 Stage400-404、Stage383 等阶段被反证，不能作为当前主线。
- C9 的小参数救援：禁止跨时段重试、二次重试、EOD 未进展退出、OR 追价过滤、利润锁、pyramiding/sleeve、volume/OI 小阈值均已反证或风险失控。

## 当前重建版逻辑审计

### 已验证通过

- AI PIT 语义仍正确：`qmt_roll_portfolio_strategy.py` 当前 `_ai_product_pool_snapshot()` 对 eval_date 使用 `searchsorted(..., side="left") - 1`；注释也明确 exact eval_date 当天使用上一期快照，新快照从后续交易日才可交易。
- `ai_product_pool_use_next_trade_date_for_entry` 默认值为 `False`，当前 live override 没有显式设置时不会产生隐藏的下一交易日平移；入口会记录 `ai_product_pool_entry_effective_date`。
- 当前正式 live override 指向 Stage182 combined eligibility 文件，并把 `account_capital/c3_capital` 覆盖到 `150,000`。
- C9 0.5R 止损重试开关仍在：`enable_stage847_half_r_stop_retry=True`、`stage847_stop_retry_r=0.5`、`stage847_max_retries=1`。
- 本轮 `py_compile` 通过：`run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py`、`qmt_roll_portfolio_strategy.py`、`qmt_roll_official_live_config.py`、`analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py` 均无语法破损。
- Stage935 最新 summary 显示 `2026-06-30 21:19:12` check 模式下，当前 eval_date `2026-05-29` 等于 expected eval_date，AI池最新品种为 `SA/MA/OI/si/AP/FG/SM/jm/fu`，`order_api_called_count=0`。

### 风险与待修点

- P1：当前重建版仍不能宣称等同删除前旧正式版。Stage153 年度起点回测只证明当前重建版能跑且 9/9 正收益，但它仍使用当前重建的 Stage182/相关输入；旧 Stage53/Stage67/Stage149 输入链和当时中间快照未完全 1:1 复原。
- P2：当前 live default 是 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，属于 operator override 的高风险 C9，而不是 Stage372 的低回撤替代。Stage153 显示早期年度起点最大回撤仍可超过 `-54%`，所以后续优化必须以风险尾治理为优先。
- P2：Stage901 C9 live runner 为了复用旧 profile，会临时修改 Stage660/Stage847 全局状态再在 `finally` 恢复。当前代码有恢复保护，但这是脆弱工程边界；后续应加 manifest/回归检查，确认 live profile、capital、AI path、minute source 在每次 run 后没有状态泄漏。
- P2：Stage935 lock 文件当前残留旧 pid 文本，虽然 `fcntl` 文件锁本身不因 stale 文件阻塞，但它会误导人工排查。建议后续把 lock 状态、pid 存活和 stale 提示写进 summary/report，不建议现在直接删除实盘相关证据文件。
- P3：当前多数关键口径靠阶段记录和散落 JSON/CSV 支撑，缺少一个“正式 live profile manifest hash”集中校验。重建后应补一个只读 healthcheck：AI池路径、eval_date、top products、capital、C9 flags、minute source、Stage901 output path、no order API 全部落到一个机器可比对 JSON。

## 延续原思路的优化建议

1. 先做当前重建版三臂基准：Stage372 live legacy、Stage819/C4、Stage847/C9，用同一终点、同一资金归一口径、同一 AI pool source 跑年度/三年滚动/月度起点。目标不是挑赢家，而是确认“C9 多赚来自哪里，风险尾来自哪里”。
2. 做当前重建版 AI ON/OFF 消融，但只作为质量审计，不作为关 AI 候选。重点看被 AI 拦截的候选在当前数据下是否仍然是低质量机会，以及最新池与旧池差异是否来自输入漂移、训练样本漂移还是标签源变化。
3. 保留 C9 stop/retry，不再救小参数。下一步只做账户/持仓层生存线：broker10 压力、权益分母压缩、同产品同方向压力簇、强制减仓前兆、回撤后恢复参与条件。
4. 若继续“选对品种”，不要用历史后验 topN；只能做 point-in-time 外生状态账本或全市场连续分钟面板。Stage252/256 说明年度 top6 有弱结构价值但材料性不足，方向可借鉴，旧规则不直接复用。
5. 补实盘工程健康检查，而不是改策略：Stage901 global mutation 审计、Stage935 stale lock 提示、official live manifest hash、邮件/影子盘 latest summary 的 no-order-api 证明。

## 当前结论

- 旧正式版达到当时水平靠的是多条结构共同作用：AI PIT 选品、Stage372 受限恢复仓和保证金治理、以及后续 C9 的入场日实时止损重试骨架；不是单个参数或单个品种贡献。
- 当前重建版可以继续优化，但不能把“当前能跑通”误解成“旧版已 1:1 复原”。现在应该把 Stage153 结果当成当前基线，把旧正式版当成路线参考和对照物。
- 本次 review 未发现 AI PIT 同日生效回归、C9 开关丢失、live capital 未覆盖、月更脚本语法破损这类 P0/P1 代码 bug。
- 发现的主要风险是口径与工程边界：C9 live default 高风险属性、Stage901 全局状态复用脆弱、Stage935 lock 证据易误导，以及旧中间输入链未完全 1:1 复原。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有改策略参数、没有根据新回测结果筛窗口，只从长期历史记录和当前代码做结构复盘与 bug 审计。它是在降低后续过拟合概率，而不是增加拟合自由度。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：旧历史已经明确告诉我们哪些路线有结构价值、哪些路线会变成窗口补丁。继续价值集中在当前重建版三臂基准、AI质量审计、账户/持仓层风险尾治理和实盘工程健康检查；继续扫 C9 小参数或 AI topN 没有价值。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；等当前重建版三臂基准和 AI ON/OFF 审计补完后统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是复盘审计，不是重要突破或正式候选变更。
