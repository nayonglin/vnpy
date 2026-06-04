# Stage344 贵金属官方源合同决策板

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 10:37 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：承接低单笔风险扩池路线，对 `precious_metals/ag.SHFE` 与 `au.SHFE` 做官方外生源 source contract 审计；不做收益回测
- 是否重要突破：否；CFTC source 被验证可执行，但 selector 继续锁定
- 是否触发A/B：否；没有新增策略候选、paper、白名单或交易版本

## 外部调研与判断

- 参考资料：
  - CFTC Commitments of Traders：`https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm`
  - CFTC Historical Compressed：`https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm`
  - LBMA Silver Price：`https://www.lbma.org.uk/prices-and-data/lbma-silver-price`
  - CME NYMEX/COMEX Delivery Notices & Stocks：`https://www.cmegroup.com/solutions/clearing/operations-and-deliveries/nymex-delivery-notices.html`
  - GitHub CFTC COT ETL：`https://github.com/Mcamin/cftc-cot`
- 我的判断：
  - `CFTC COT` 是当前贵金属最强的官方机器源：公开、周频、可点时化、可压缩包缓存，外部网络探针确认 `2026` 年 zip 为 HTTP `200`。
  - 但它不能直接解锁交易，因为 Stage014 已经验证过 COT 外生质量分在 test 段不单调：低分桶 20 日 R `2.7677`，高分桶 `-0.7065`。
  - `CME Silver_stocks.xls` 有官方页面和仓库库存语义，理论上比 COT 更接近白银供需事件，但本次直接 payload 探针超时，不能写入 PIT。
  - `LBMA` 数据权威但偏价格基准/授权数据，不是当前免费、机器可控、可直接形成 selector 的供需事件源。
  - 因此贵金属方向可以保留为 P2 forward monitor/source 累计，不应晋级 selector、paper 或白名单。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage644_precious_metals_official_source_contract_board.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - CFTC silver/gold 市场映射：`SILVER - COMMODITY EXCHANGE INC.`、`GOLD - COMMODITY EXCHANGE INC.`
  - gate：`official_source_exists`
  - gate：`cftc_machine_readable_public`
  - gate：`cftc_current_probe_ok`
  - gate：`cme_payload_validated`
  - gate：`ag_event_seed_ready`
  - gate：`pit_dates_reach_20`
  - gate：`episodes_reach_3`
  - gate：`prior_cot_quality_not_failed`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不新增策略回测；只读 Stage313、Stage629、Stage631、Stage633 输出和本地 `external_cftc_cot_cache` 的 `2020-2026` CFTC 压缩包
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：
  - CFTC：仅 `SILVER - COMMODITY EXCHANGE INC.` 与 `GOLD - COMMODITY EXCHANGE INC.`
  - P2 monitor：`ag.SHFE`
  - 相关性地图：`ag.SHFE`、`au.SHFE`
- 策略/归因口径：
  - 不重放策略，不改变交易规则，不扫参数
  - 不追加 master PIT ledger
  - 不生成 selector、paper、A/B 或交易白名单
  - 不连接 CTP，不调用订单 API

## 结果

- 期末权益：不适用；本阶段不是策略回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`precious_metals_official_cftc_source_validated_monitor_only_selector_locked`
  - source options：`6`
  - official / authorized sources：`5`
  - machine readable sources：`3`
  - active probe ready sources：`3`
  - CFTC silver local rows：`333`
  - CFTC silver last report date：`2026-05-19`
  - CFTC 2026 zip 外部探针：HTTP `200`，`application/zip`
  - CME `Silver_stocks.xls` 外部探针：`timeout/internal_error`，payload 未验证
  - `ag.SHFE` PIT dates：`1`
  - `ag.SHFE` event seed rows：`0`
  - selector / paper / whitelist：`0 / 0 / 0`
  - hard gates：`7/14`
  - Stage014 COT test 低分桶 20 日 R：`2.7677`
  - Stage014 COT test 高分桶 20 日 R：`-0.7065`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage644_precious_metals_official_source_contract_board_report_stage644_precious_metals_official_source_contract_board_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage644_precious_metals_official_source_contract_board_decision_stage644_precious_metals_official_source_contract_board_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage644_precious_metals_official_source_contract_board_source_options_stage644_precious_metals_official_source_contract_board_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage644_precious_metals_official_source_contract_board_product_evidence_stage644_precious_metals_official_source_contract_board_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage644_precious_metals_official_source_contract_board_gates_stage644_precious_metals_official_source_contract_board_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage644_precious_metals_official_source_contract_board_chart_stage644_precious_metals_official_source_contract_board_v1.png`

## 图表视觉复盘

- 左上图：`CFTC Silver/Gold` ready component 最多，但左侧红块提示 prior alpha failed；这说明官方可得性不能等同于交易预测力。`SHFE Daily Data` 具备 official/public/PIT/local/active 证据，但缺 machine-readable payload 和 event seed。`CME` 有官方/公开/机器形态但 active probe 为 `0`，不能进入 PIT。
- 右上图：`ag.SHFE` 趋势代理高且流动性大，但最大相关 `0.1779` 已在严格 `0.15` 线右侧，只能算 watch 级，不是严格低相关独立槽；`au.SHFE` 相关性更低，但属于已有核心/诊断资产，不是新增白名单答案。
- 左下图：`ag.SHFE` 的 CFTC rows 为 `333`，但真正 forward PIT 只有 `1`，event seed、episode、selector 都是 `0`。这张图直接解释了为什么“有历史数据”不能晋级“可交易 selector”。
- 右下图：失败项集中在 `cme_payload_validated`、`ag_event_seed_ready`、`pit_dates_reach_20`、`episodes_reach_3`、`prior_cot_quality_not_failed`、`selector_allowed_now`、`paper_or_whitelist_allowed_now`。这和报告结论一致。
- 视觉质量：第一版右下失败 gate 因数值 `0` 不显示红条，已修成 PASS/FAIL 全宽色块；最终图无关键遮挡，`ag.SHFE` 标注接近右上边界但仍可读。

## 结论

- 本阶段结论：
  - 贵金属方向仍有研究价值，但只能做 monitor/source 累计，不能晋级交易。
  - `CFTC COT Silver` 是可执行官方源，但 Stage014 已反证其作为开仓质量因子的样本外排序能力；当前只能作为外盘资金温度计。
  - `CME Silver_stocks.xls` 可能更接近白银库存/交割供需，但本次 payload 未验证；在验证前不能进入 PIT，也不能驱动 selector。
  - `ag.SHFE` 的最大相关 `0.1779` 高于严格低相关线 `0.15`，只能算 watch 级分散，不能解决“新增独立风险槽”。
- 是否进入下一步：继续，但只允许 source/PIT 累计，不做交易回测救援。
- 下一步：
  1. 如果继续贵金属分支，只做 `CFTC ag/au weekly monitor append gate`，写 context-only PIT 账本，不生成 selector。
  2. `CME Silver_stocks.xls` 需要用 browser/session 或官方数据通道单独做 payload parser probe；验证失败则停止 CME 库存路线。
  3. 贵金属 selector 必须等 `20` 个 PIT 日期、`3` 个独立 episode、预测力审计、真实 TCA 后再谈。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段没有做收益回测、没有调整交易规则、没有用历史赢家生成白名单。
  - CFTC source 虽然可得，但因为 Stage014 样本外失败，仍被锁在 monitor-only。
  - 对 CME/LBMA 没有因为语义好听而放宽 payload/source 闸门。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值但优先级受限。
- 原因：
  - 贵金属确实具备官方源和相对分散属性，适合长期观察。
  - 但它当前不能解决目标的核心问题：新增可部署独立风险槽仍为 `0`。
  - 继续价值在 source/PIT/TCA 基建，不在贵金属交易参数优化。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage344 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式候选、路线废弃、跨线合并或重大突破。
