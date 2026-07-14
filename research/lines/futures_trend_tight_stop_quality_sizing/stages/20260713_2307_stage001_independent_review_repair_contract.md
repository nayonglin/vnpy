# Stage001 独立审计否决与修复合同

- line_id：`futures_trend_tight_stop_quality_sizing`
- 时间：`2026-07-13 23:07 CST`
- 阶段性质：Stage001 影响结果问题修复；不新增规则、不改主策略
- 独立审计 agent：`019f5bf8-8f2a-7d02-8463-ccbb1bd089a7`
- 审计结论：baseline 会计通过；技术归因 `FAIL`；Stage002 禁止
- 是否重要突破：否

## 审计发现

1. 技术特征错误读取 Stage719 静态 CSV 目录，而不是预声明冻结的当前项目数据库。29 个所谓缺失合约在 `.vntrader/database.db` 均有逐合约日线；当前覆盖率和全部规则结果作废。
2. 327 个 closed lots 只把 294 个标记为 `flat_entry` 的 lots 纳入事件，遗漏 stop retry、7 个候选到实际开仓匹配失败的普通开仓和 rollover reopen。当前机会 PnL、R、年度贡献和资格门作废。
3. ATR14 第一根 true range 错误使用 `high-low`，比 TA-Lib/Wilder 标准提前一根。ATR、ADX、stop/ATR 和阈值均需重算。

## 冻结修复口径

### 日线和指标

- 唯一主源改为仓库项目级 `.vntrader/database.db`，SQLite 使用 `mode=ro` 只读连接，按实际合约、交易所、`interval='d'` 精确读取。
- input audit 必须记录数据库路径、字节数、SHA256、逐合约 bar 数和首末日期；数据库运行前后 SHA256 必须一致。
- true range 第一行固定为缺失；ATR14、DI14 和 ADX14 必须逐值与本环境 TA-Lib `0.6.8` 对照通过。
- 特征仍严格使用 `feature_date < entry_date`；核心覆盖门保持 `>=90%`。

### 开仓谱系和机会收益

- 每个真实 flat-entry open 是一个机会父事件。风险/候选源与实际 open 按同合约、方向、时间顺序一对一匹配；优先实际风险诊断，候选 `opened` 只用于补足诊断缺失。
- 候选到实际 open 只允许向后匹配首个未占用 open，最大 `15` 个日历日且不得跨过同组下一候选；这是为春节等休市保留的执行窗口，不允许按回测结果变化。
- `order_id` 含 `.stage847_c9.2` 的真实 retry open 必须通过根 order 关联到原始 open，再递归关联到机会父事件。
- rollover reopen 必须通过同日旧合约 close 关联到已有机会父事件。它是持仓延续，不新建机会。
- 机会 realized PnL 包含初始开仓、retry 和 rollover 延续的全部已平仓 PnL，必须与全体 closed lots gross PnL 完全一致，不允许 orphan。
- 机会 R 分母为原始 flat-entry 风险加所有 retry 新尝试风险；rollover 只是原持仓迁移，不重复增加风险预算。retry 风险按其父尝试的逐手计划风险乘实际 retry volume 计算。
- 同时输出 initial/retry/rollover 三类 PnL、风险、lot 数和映射来源，避免再次把生命周期损益隐藏在汇总中。

## 重跑要求

- 端到端重新运行当前 official Stage847 C9/15万 `2020-01-01 -> 2026-06-30`，不可复用第一次的特征、阈值、规则或 decision。
- baseline、trades、entry risk、entry candidates、trade events、closed lots、机会事件、图表、input audit、manifest 和 decision 必须来自同一次完整运行。
- 修复后重新拉一个全新的独立 agent；如果仍有影响结果问题，继续 fail-close，不得进入 Stage002。

## 反思

- 过拟合：修复数据和会计口径本身不是过拟合；不得借修复修改规则、阈值或资格门。
- 继续价值：有。三个问题都直接影响候选选择，修复是继续任何优化前的必要条件。
