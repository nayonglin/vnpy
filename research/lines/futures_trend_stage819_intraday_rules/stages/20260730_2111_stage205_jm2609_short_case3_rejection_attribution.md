# Stage205 jm2609 short_case3 拒绝归因

- line_id：`futures_trend_stage819_intraday_rules`
- 记录时间：`2026-07-30 21:11 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 生产权威根：`/Users/bytedance/Desktop/person/vnpy_production_live`
- 阶段性质：官方 C9/15万 Stage901 候选的只读信号归因
- 是否重要突破：否
- 是否触发 A/B：否

## 外部调研与判断

- vn.py 官方 CTA 文档和 GitHub 仓库说明框架只提供信号生成、委托管理和行情组件；仓库检索未发现 `short_signal_rejected`，该语义属于本项目自定义策略门禁。
- 判断：不能把 vn.py 框架能力或一般“趋势策略可多可空”的原则，当成放开本项目 `short_case2/3` 的依据；应以冻结生产代码和已有账户级 A/C 证据解释。

## 本次变更

- 策略、配置、AI 池、生产状态、CTP 与订单：均未修改。
- 仅新增本只读归因记录。
- 未运行新回测；以下历史 A/C 数字来自既有 Stage400/Stage687 记录。

## 2026-07-30 jm2609 原始信号

- exact ArrayManager：`AM41`，窗口为 `2026-06-03` 至 `2026-07-30`。
- `2026-07-29 -> 2026-07-30`：
  - MA5：`1266.7 -> 1254.6`
  - MA10：`1266.8 -> 1263.4`
  - MA20：`1269.35 -> 1267.325`
  - MA40：`1298.5625 -> 1294.7`
- 当日 `MA5 < MA10 < MA20 < MA40`，`bearish_alignment=1`。
- 三组均线当日都没有新死叉：
  - `death_5_10=0`
  - `death_10_20=0`
  - `death_20_40=0`
- AM41 MACD：
  - 前一日 DIF/DEA/HIST：`-12.948851 / -14.479656 / +3.061610`
  - 当日 DIF/DEA/HIST：`-15.078289 / -14.599382 / -0.957813`
  - DIF 从 DEA 上方跌到下方，`macd_death=1`。
- 当日收盘 `1227` 低于前 20 日最低价 `1229`，`breakout_down=1`。
- 因此代码在“无均线新交叉”的分支中，将它分类为 `short_case3`。

## 直接拒绝链

- 基础策略 `_can_open_short_signal()` 只返回 `signal == "short_case1a"`。
- `short_case3` 因此在 flat-entry candidate plan 中被设置为 `skip_reason=short_signal_rejected`。
- 其他层不是拒绝原因：
  - `passed_initial_filter=1`
  - `selected_volume=1`
  - `ai_product_pool_allowed=1`，rank=`7`，top_n=`9`
  - `risk_mode=regular`
  - 当前影子持仓与 active positions 均为 `0`
  - `bearish_alignment=1`、`breakout=1`
- OI 从 `429403` 降至 `410525`，所以 `oi_price_confirm_passed=0`、没有获得 2 倍 OI 风险恢复；但它仍保留 1 手 sizing，这不是拒绝原因。

## 底层设计依据

- 从信号结构看：
  - `short_case1a` 是 MA5 当日下穿 MA10 且完整空头排列，属于被正式版认可的“新鲜快速趋势转空”。
  - `short_case2` 是较慢 MA10/20 或 MA20/40 当日死叉。
  - `short_case3` 是没有均线新死叉时的 MACD 死叉确认；本次 jm 即属于这一类。
- 既有 Stage400/Stage687 曾仅把 Stage372/20万的 short 白名单由 case1a 放宽到 case1a/2/3：
  - 交易次数 `633 -> 805`
  - 期末权益 `8,728,285 -> 1,652,090`
  - 总收益 `4264.1425% -> 726.0450%`
  - Sharpe `1.6279 -> 1.1027`
  - 强制减仓次数 `6 -> 16`
  - 最大回撤改善约 `3.03pp`
- 历史归因是 case2/3 提前占用风险槽并改变复利路径，压制原有右尾，因此保留“只允许 case1a”。
- 边界：Stage400 是旧 Stage372/20万账户级证据，不是当前 C9/15万的直接 A/B；它解释白名单的历史风险依据，但不能证明本次 jm 单笔未来一定亏损。

## 回测字段

- 期末权益：本次未回测
- 总收益：本次未回测
- 最大回撤：本次未回测
- Sharpe：本次未回测
- 总滑点：本次未回测
- 总交易次数：本次未回测
- 胜率：本次未回测

## 独立复核

- 三路只读复核均确认：直接拒绝原因是本地 short-case 白名单，不是 AI、资金、风险、OI 或 CTP。
- 当前 JM 直接代码归因置信度：`99%`。
- “旧 Stage400 账户路径原因可直接迁移到当前 C9/15万”的置信度仅约 `75%`；未找到当前 exact C9/15万只切换 short-case 白名单的直接 A/B。
- 因此历史证据足以解释为何现行规则保持保守，但不足以宣称该规则在当前 profile 下已重新证明全局最优。

## 结论与下一步

- 直接原因：`jm2609.DCE` 是 `short_case3`，不在生产 fresh-short 白名单。
- 底层原因：生产策略只把“MA5 新死叉 + 完整空头排列”的 `short_case1a` 视为足够可靠的新开空触发；历史账户级放宽 case2/3 明显损害复利与 Sharpe。
- 这不是 AI、资金不足、并发槽、RSI 或 OI 风险层把它拒绝。
- 不因一笔 jm 候选修改白名单。若要判断当前 C9/15万是否应该放开，必须另做预注册、隔离的全样本 A/B，不能只回看本次 jm。

## 反思

- 过拟合：否。本次只解释冻结生产规则和既有证据，没有调参或按单笔结果反推规则。
- 继续价值：有，但到“解释为何拒绝”已经闭环；继续做单品种、单日期救参没有价值。
