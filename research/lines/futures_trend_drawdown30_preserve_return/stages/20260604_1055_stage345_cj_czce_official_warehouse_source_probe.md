# Stage345 CJ.CZCE 官方仓单源 active fetch 探针

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 10:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：低单笔风险扩池路线的单品种 source/选品审计；不做收益回测、不改交易规则、不连接 CTP、不生成 selector/paper/A/B/交易白名单。
- 是否重要突破：否。属于数据源层小突破，不是策略突破。
- 是否触发A/B：否。当前 selector/paper/whitelist 全部为 `0`，不满足 A/B 条件。

## 外部调研与判断

- 参考资料：
  - 趋势跟踪分散化研究：`A Century of Evidence on Trend-Following Investing`，Hurst/Ooi/Pedersen，SSRN：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026`
  - CZCE 仓单日报：`https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm`
  - AKShare `futures_warehouse_receipt_czce` 文档入口：`https://akshare.akfamily.xyz/changelog.html`
  - AKShare GitHub：`https://github.com/akfamily/akshare`
  - 国家林草局新疆红枣资料：`https://www.forestry.gov.cn/lyj/1/slgs/20241023/593126.html`
  - ShinnyTech 红枣业务规则资料：`https://www.shinnytech.com/articles/business-rules/products/czce.cj`
- 我的判断：
  - 用户提出的“降低单笔风险、扩大品种池、每年抓部分趋势、避免高相关风险”方向是正确的第一性原理：趋势策略靠广义机会覆盖和低相关风险源活下来，而不是押一个品种或一个经济驱动。
  - 但扩池不能等同于加品种数。真正可晋级的品种必须同时满足低相关、流动性、外生/官方源可事前抓取、PIT 样本、独立 episode、outcome audit 和真实 TCA。
  - `CJ.CZCE` 的本地相关性较低，是一个比 `base_metals`/贵金属更像“新增独立槽”的侦察对象；但它目前只有 CZCE 仓单日报这条稳定官方日频源，缺少稳定月度基本面源，不能直接做 selector。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage645_cj_czce_official_warehouse_source_probe.py`
- 修改脚本：无既有策略脚本修改；仅本阶段脚本内修正 raw hash 空值处理，并补充 `trading_whitelist_allowed_now` 显式字段。
- 删除脚本：无。
- 新增参数：
  - `probe_dates = [20250613, 20260421, 20260427, 20260529, 20260602, 20260603]`
  - `strict_corr_threshold = 0.15`
  - `watch_corr_threshold = 0.20`
  - `min_pit_dates_for_selector = 20`
  - `min_independent_episodes = 3`
  - `min_live_tca_samples = 3`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：非收益回测；source 探针日期为 `2025-06-13`、`2026-04-21`、`2026-04-27`、`2026-05-29`、`2026-06-02`、`2026-06-03`。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：仅审计 `CJ.CZCE`，并复用 Stage633 相关性/流动性证据与 Stage634 source contract 证据。
- 策略/归因口径：只读 CZCE/AKShare 仓单源 active fetch、raw hash、PIT 日期、selector 闸门；不看未来收益，不做交易回放。

## 结果

- 期末权益：不适用，非回测。
- 总收益：不适用，非回测。
- 最大回撤：不适用，非回测。
- Sharpe：不适用，非回测。
- 总滑点：不适用，非回测。
- 总交易次数：不适用，非回测。
- 胜率：不适用，非回测。
- 其他关键指标：
  - decision：`cj_czce_official_warehouse_source_validated_monitor_only_selector_locked`
  - fetch dates：`6`
  - fetch ok dates：`6`
  - raw hash rows：`6`
  - PIT dates：`6`
  - latest probe date：`20260603`
  - latest total receipts：`7769`
  - latest effective forecast：`336`
  - max abs corr to P0：`0.1089`
  - tail abs corr to P0 composite：`0.1751`
  - rolling abs corr p75 to P0：`0.1955`
  - recent median volume：`1713.5`
  - recent median OI：`6167`
  - trend year rate：`100%`
  - trend signal median：`1.9655`
  - hard gates：`7/13`
  - selector/paper/whitelist：`0/0/0`

## 图表视觉复盘

- 左上：CJ 仓单与有效预报量不是静态死数据。仓单从 `2026-04-21` 的 `5838`、`2026-04-27` 的 `6278`，上升到 `2026-05-29/06-02/06-03` 的约 `7769-7770`；有效预报量在 4 月高位 `1427/1274` 后回落到 `227/336`。
- 右上：fetch/raw/PIT 均为 `6`，明显低于 selector 所需 `20` PIT 日期；monthly source、episodes、selector rows 均为 `0`。
- 左下：`CJ.CZCE` 的 `max_abs_corr_to_p0 = 0.1089`，位于严格 `0.15` 相关线左侧；趋势代理约 `1.965`，具备 watch 价值。
- 右下：通过项集中在“本地加载、低相关/观察相关、流动性、官方日仓单抓取、raw hash、当前日期、fail closed”；失败项集中在“月度基本面源、20 PIT、3 episode、3 live TCA、selector、paper/whitelist”。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage645_cj_czce_official_warehouse_source_probe_report_stage645_cj_czce_official_warehouse_source_probe_v1.md`
- summary/decision：脚本 stdout JSON；主结论写入 report。
- fetch ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage645_cj_czce_official_warehouse_source_probe_fetch_ledger_stage645_cj_czce_official_warehouse_source_probe_v1.csv`
- product evidence：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage645_cj_czce_official_warehouse_source_probe_product_evidence_stage645_cj_czce_official_warehouse_source_probe_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage645_cj_czce_official_warehouse_source_probe_gates_stage645_cj_czce_official_warehouse_source_probe_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage645_cj_czce_official_warehouse_source_probe_chart_stage645_cj_czce_official_warehouse_source_probe_v1.png`
- orders/daily/quality：不适用，非交易回测。

## 结论

- 本阶段结论：`CJ.CZCE` 从 Stage634 的 `source contract weak` 升级为“官方交易所仓单源 active-fetch validated 的 forward monitor 候选”。这支持低单笔风险扩池路线中“寻找非 DCE、低相关、独立经济驱动”的方向。
- 但它不是交易候选：CZCE 仓单是一个日频供应侧状态，不是已证明的趋势 selector；目前只有 `6` 个 PIT 日期、`0` 个独立 episode、`0` 个 live TCA，且缺少稳定月度官方基本面源。
- 是否进入下一步：进入 source/PIT monitor 下一步；不进入 selector/paper/A/B/交易白名单。
- 下一步：
  - 写 CJ 仓单 master PIT append gate，只允许新自然日追加，禁止同日重复膨胀样本。
  - 累计至少 `20` 个 PIT 日期后，固定跑 `20/63/126` outcome schedule。
  - 继续寻找稳定官方/授权的季节性产量、质量、出货或库存补充源；如果找不到，CJ 只能保持 warehouse-only monitor。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：本阶段没有看收益曲线、没有调策略参数、没有筛未来表现，只验证外部官方源是否能被事前抓取、hash 留痕和进入 fail-closed 闸门；抓取成功后仍锁定 selector/paper/whitelist，说明没有用数据源成功直接包装成交易结论。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值停留在 monitor/source 层。
- 原因：CJ 满足低相关和可抓官方日频源，是扩池路线里少数从“想法”推进到“可前向积累证据”的非 DCE 候选；但离交易仍差 PIT 深度、episode、outcome 和 TCA。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage345 当前状态。
- 是否更新 `research/registry.md`：是，更新本线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破、路线废弃或跨线合并。
