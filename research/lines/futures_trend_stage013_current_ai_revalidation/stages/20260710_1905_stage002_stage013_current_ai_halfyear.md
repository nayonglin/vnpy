# Stage002 Stage013 当前 AI 逐半年真实引擎验证

- line_id：`futures_trend_stage013_current_ai_revalidation`
- 当前模式：`day`
- 记录时间：`2026-07-10 20:08:32 CST`
- 是否重要突破：是，当前原冻结 AI 政策下通过多起点门槛；进入成本与执行验收
- 新增参数：无
- 修改参数：仅将冷启动起点扩展为 2020-01 至 2026-01 逐半年，统一终点 2026-06-30
- 删除参数：无
- 策略参数：冻结 Stage013 `回撤>=30% / 活跃持仓<=1 / flat_entry降为1手`

## 回测口径

- A：当前官方 AI + 当前 C9/15w。
- C：A + 冻结 Stage013 account-state pilot。
- 13 个起点均独立以 `150,000` 初始化，不继承资金、持仓或运行状态。
- 成熟样本：交易日 `>=252`；全部门槛运行前已写入 `LINE.md`，本轮不救参。

## 2020-01 完整路径

- A：期末权益 `5,996,631.00`，总收益 `3897.7540%`，最大回撤 `-55.3701%`，Sharpe `1.3967`，总滑点 `759,970.00`，交易次数 `641`，非零日胜率 `52.8302%`，逐笔胜率 `45.8716%`。
- C：期末权益 `5,984,961.70`，总收益 `3889.9745%`，最大回撤 `-38.1717%`，Sharpe `1.4585`，总滑点 `489,650.00`，交易次数 `639`，非零日胜率 `53.0516%`，逐笔胜率 `45.5385%`。

## 多起点结果

- 样本/成熟样本：`13` / `11`。
- 成熟 C 正收益：`11/11`。
- 成熟回撤改善或持平：`11/11`，比例 `1.0000`。
- 成熟起点回撤恶化超过 3pp：`0`。
- A 正收益成熟起点 C/A 收益保留中位/最小：`1.0813` / `0.9562`。
- 跨起点最差回撤 A/C：`-55.3701%` / `-43.7940%`，改善 `11.5761pp`。
- 跨起点 broker10 峰值 A/C：`88.3398%` / `81.5638%`。
- Pilot 触发总数：`470`。

## AI 政策与月历审计

- A/C eligibility 归一化完全相同，当前文件 `504` 行/`55` 个 eval_date。
- 原模型 walk-forward 为 `720/180/180` 天，首个 OOS 预测 `2022-01-28`；2020-2021 明确使用 static18 pre-AI 边界，不是缺月。
- 2022-01 至 2026-06 月度 AI 预期/存在 `54/54`，缺失 `0`；原始 50 个 OOS 日期完整，2026-03 至 05 为 membership-only 恢复，2026-06 为 live inference。
- Stage003 把后来的 `>=12月` live inference 提前到 2021，属于反事实 early activation，不是修复；其失败不否定本阶段。
- Stage002 未保存每起点候选级 entry-candidate 明细，是产物 P2；本轮已由 Stage001 明细及两个独立新进程复跑交叉确认，后续验收必须保存。

## 最终结论

- 决策：`stage002_pass_original_ai_policy_continue_cost_execution_validation`。
- 回测独立 review：`P0=0/P1=0/P2=3`，数值置信度 `97%`；边界法证 `P0=0/P1=2/P2=3`，置信度 `98%`。
- AI 月历阻塞已撤销；但尚未直接切正式，下一步是成本敏感、执行一致性和 shadow 验收，`promotion_ready=false`。
- 独立复算确认 summary 最大误差 `<1e-12`、新进程复跑一致、无缓存/日期泄漏；470 条路径事件按日期+品种去重为 77 个市场事件观测。
- 新增回测结果：见 `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage002_stage013_current_ai_halfyear/stage013_current_ai_stage002_stage013_current_ai_halfyear_pair_summary_stage002_stage013_current_ai_halfyear_v1.csv` 和 `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage002_stage013_current_ai_halfyear/stage013_current_ai_stage002_stage013_current_ai_halfyear_summary_stage002_stage013_current_ai_halfyear_v1.csv`；未修改或删除历史回测结果。

## 过拟合反思

- 运行前：低。参数、样本起点和判定门槛均预先冻结，没有搜索最优阈值。
- 运行后：低到中等。规则未调参且多起点结果一致；但 13 条路径共享市场时段，不是 13 个统计独立样本。

## 继续价值反思

- 运行前：有。Stage001 的单起点改善需要通过独立冷启动路径反证。
- 运行后：有。下一步做成本敏感、执行一致性和 shadow；不补 2021 月池、不继续调 Stage013 参数。

## 输出

- 报告：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage002_stage013_current_ai_halfyear/stage013_current_ai_stage002_stage013_current_ai_halfyear_report_stage002_stage013_current_ai_halfyear_v1.md`
- 配对结果：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage002_stage013_current_ai_halfyear/stage013_current_ai_stage002_stage013_current_ai_halfyear_pair_summary_stage002_stage013_current_ai_halfyear_v1.csv`
- 净值网格：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage002_stage013_current_ai_halfyear/stage013_current_ai_stage002_stage013_current_ai_halfyear_nav_grid_stage002_stage013_current_ai_halfyear_v1.png`
- 汇总图：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage002_stage013_current_ai_halfyear/stage013_current_ai_stage002_stage013_current_ai_halfyear_summary_chart_stage002_stage013_current_ai_halfyear_v1.png`
