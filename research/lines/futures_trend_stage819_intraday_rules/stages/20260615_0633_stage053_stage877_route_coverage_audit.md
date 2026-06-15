# Stage053 Stage877 分钟规则路线覆盖审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 06:33 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：研究线覆盖审计与路线收束；不新增交易规则、不改官方正式版、不改官方候选配置、不接真实引擎、不连接 CTP、不调用下单。
- 是否重要突破：否；这是阶段性收束，不是新 alpha。
- 是否触发A/B：否；没有形成可推广的新策略版本。

## 外部调研与判断

- 参考资料：
  - Turtle 规则支持固定突破、固定止损和 whipsaw 后重入，但核心是用少数规则承受右尾，不是不断按失败样本调参：https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf
  - Opening Range Breakout 可提供自然的日内结构尺度，但 OR 长度和突破倍数极易拟合压力年份；Stage876 已验证固定 `OR15/1xOR` 不够稳。
  - Rob Carver 对动态止损的讨论强调，趋势系统中过多路径依赖止损容易削弱右尾和 Sharpe：https://qoppac.blogspot.com/2020/02/what-is-right-way-to-set-stop-losses.html
  - vn.py CTA engine 参考说明任何候选最终必须落到 runtime 逐事件可执行语义：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/engine.py
- 我的判断：
  - 公开资料只能给原则：低自由度、实时、少数规则、右尾保留。
  - 当前线已经覆盖了常见分钟级入场/出场形状；继续在同一信息集里找规则，大概率会从研究变成救参。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 目标覆盖审计

| 目标要求 | 当前证据 | 状态 | 判断 |
| --- | --- | --- | --- |
| 基于候选版本起独立研究线 | `research/lines/futures_trend_stage819_intraday_rules/LINE.md` 已存在，定位为 Stage819 候选分钟级规则研究线 | 已完成 | 研究线与正式 Stage372/20w 隔离 |
| 全周期逐笔分析 | Stage861 summary：entry lots `341`、entry-day coverage `341/341=100%`；Stage862 基准 lot PnL `28,171,880` | 已完成入场日逐笔层 | 持仓全路径全图谱没有为每笔全部绘制，但 entry-day 和压力日期已覆盖 |
| K线视觉分析 | Stage861 entry atlas `57` 页，pressure atlas `3` 页；Stage876 追加 OR extension atlas `5` 页 | 已完成主要视觉证据 | 已足够支持入场日/压力段规则归纳和反证 |
| 规则类、非 AI | 全线所有新增规则为 OR、R、止损、重试、锁盈、账户风险等确定性规则 | 已完成 | 未引入 AI/ML |
| 日内错误实时止损，不死扛 | Stage847/C9 骨架：`0.5R` 实时止损 + 原入场价 reclaim 后一次重试；Stage863 全量分钟K重算 | 部分完成 | C9 是唯一正贡献骨架，但仍有 broker10 风险 |
| 可以多次尝试 | Stage847/C9 验证一次重试；Stage874 二次重试只读审计被反证 | 已审计 | 多次尝试不能机械增加次数 |
| 找到能提高收益的分钟规则 | Stage863 C9 相对 C4：期末权益 `+4,621,339.6`、Sharpe `+0.0316`、最大回撤改善 `+4.5602pp` | 有一个骨架线索 | 但 max broker10 从 C4 `111.4255%` 升至 C9 `114.3987%`，不能推广 |
| 找到可进入正式候选/A-B 的稳定版本 | Stage867-876 连续反证高热、收盘确认、cooldown、progress-confirm、利润锁定、二次重试、EOD 退出、OR追价过滤 | 未完成 | 当前没有可推广版本 |

## 已覆盖规则族

- 入场确认/OR：
  - Stage862 反证 OR15 block 与 60m 1R fast confirm。
  - Stage876 反证固定 `OR15/1xOR` 追价过滤。
- 日内快速止损/重试：
  - Stage847/C9 是唯一有正价值的骨架：`0.5R stop + reclaim retry once`。
  - Stage868 反证 close-confirm next-open retry。
  - Stage874 反证同日二次重试。
  - Stage875 反证重试后未进展 EOD 退出。
- 二次失败/冷却：
  - Stage867 反证高热 stop-first no-retry。
  - Stage869 反证 retry_failed 后续同产品同方向 cooldown。
  - Stage870 反证 progress-confirm recovery。
- 结构破坏：
  - Stage862 反证 S1-S4 结构破坏规则，尤其 Stage842 子集线索在完整覆盖下转负。
- 盈利保护/出场：
  - Stage872 反证固定止盈。
  - Stage873 反证 `+2R 后锁 +1R` 真实引擎。
- 账户/风险：
  - Stage865 反证简单账户热度 sizing brake。
  - Stage864/871 说明 broker10 恶化多来自权益分母和路径联动，不是单个当下持仓分子可简单缩手解决。

## 关键保留事实

- C9 骨架仍是唯一值得保留的“经验模块”：
  - 期末权益 `50,637,144.6`
  - 总收益 `16,779.0482%`
  - 最大回撤 `-42.6313%`
  - Sharpe `1.631178`
  - 总滑点 `3,607,030`
  - 总交易次数 `786`
  - 胜率 `53.529937%`
  - 相对 C4 期末权益 `+4,621,339.6`
  - 相对 C4 Sharpe `+0.031584`
- 但 C9 不能作为当前正式候选：
  - max broker10 `114.398733%`，高于 C4 `111.425481%`
  - days over 100pct `7`，C4 为 `4`
  - 后续 C10、C11、C12、C13、C14 和只读派生审计均未解决这个矛盾

## 结果

- 期末权益：未新增；本阶段不是组合回测。保留 C9 `50,637,144.6` 作为线内最强骨架结果。
- 总收益：未新增；保留 C9 `16,779.0482%`。
- 最大回撤：未新增；保留 C9 `-42.6313%`。
- Sharpe：未新增；保留 C9 `1.631178`。
- 总滑点：未新增；保留 C9 `3,607,030`。
- 总交易次数：未新增；保留 C9 `786`。
- 胜率：未新增；保留 C9 `53.529937%`。
- 其他关键指标：
  - Stage861 full minute bars：`1,479,592`
  - symbols：`216`
  - entry-day coverage：`341/341=100%`
  - pressure key date coverage：`19/19=100%`
  - entry atlas pages：`57`
  - pressure atlas pages：`3`

## 结论

- 本阶段结论：`stage877_intraday_rule_route_covered_no_promotable_rule_yet`。
- 是否进入下一步：暂不继续在同一组分钟K派生特征上写新入场/出场规则。
- 下一步：
  - 若继续本线，只能换到“账户/持仓层生存线”或“外生低自由度信息源”，而不是继续对 OR、R 倍数、重试次数、确认窗口、锁盈阈值做小变体。
  - 若目标严格要求“分钟K入场/出场规则必须直接提高收益且可推广”，当前证据还没有证明完成。

## 过拟合反思

- 运行前判断：否。Stage877 是覆盖审计，不产生新参数或新规则。
- 运行后判断：否；但继续在同一信息集里找小变体会过拟合。
- 原因：
  - 已覆盖的失败分支横跨 OR、fast confirm、stop/retry、cooldown、progress-confirm、fixed takeprofit、profit lock、second retry、EOD exit、OR extension。
  - 每个分支失败的共同原因是右尾误伤、资金路径联动或 broker10/权益分母风险，而不是某个阈值没扫对。

## 继续价值反思

- 运行前判断：有价值。需要判断研究线是否仍应继续生成新分钟规则，还是该收束。
- 运行后判断：同一组分钟K派生特征继续价值低；换方向仍有价值。
- 原因：
  - C9 证明“实时止损 + 一次重试”这个默会经验方向是对的，但所有直接补丁都没有解决 broker10 风险。
  - 真正矛盾已经从“这一根分钟K是否更好”转到“右尾和压力段共享同一进攻状态，如何不砍右尾地承载风险”。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage053 收束判断。
- 是否更新 `research/registry.md`：否，本线没有路线级合入。
- 是否追加根目录 `memory.md/back_log.md`：否，暂不属于正式候选、重要突破或路线废弃；只是线内阶段收束。
