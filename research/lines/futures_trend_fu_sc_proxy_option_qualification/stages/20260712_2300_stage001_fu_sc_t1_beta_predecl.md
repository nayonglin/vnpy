# Stage001 FU-SC 严格 T-1 beta 与期权链资格预声明

- line_id：`futures_trend_fu_sc_proxy_option_qualification`
- 当前模式：`day`
- 预声明时间：`2026-07-12 23:00 CST`
- 阶段性质：跨品种基差与数据资格；不是策略回测
- 是否重要突破：待定
- 是否触发 A/B：否

## 冻结问题

在 SC 期权上市后，SC 原油能否在不使用同日 OI、主连跳变、未来收益或事件删样的前提下，对 C9 全部 FU 入场事件提供稳定、同号且足够强的 T-1 价格风险代理？

## 冻结输入

- Stage131 query events 路径与 SHA 沿用上一数据线：`365` 行，SHA256 `7abf7a0414238517349e383a6ef7282b5f8d16921686ddc1edb6f2e70e5cc77a`。
- 样本只按 `product_vt_symbol == fu.SHFE && entry_date >= 2021-06-21` 机械过滤。
- 核心窗口 `2022-03-09 -> 2022-06-29` 预期 FU events `6`；不是唯一样本。
- 数据库：`.vntrader/database.db` 的实际合约日线；运行前后记录文件 hash、表行数与查询边界。

## T-1 选约与收益合同

- 对每个产品和日期 `d`，候选是 `d-1` 有合法 close/OI 的未到期实际合约。
- 选择 `d-1` OI 最大合约；并列按合约代码升序，保存候选数、top OI 和选择理由。
- 返回 `d` 必须使用被选合约自身 `close[d] / close[d-1] - 1`；任一端缺失则该日无效。
- 禁止 `continuous_symbol` 价格直接 pct_change，禁止 `d` 同日 OI，禁止用 entry-day close。
- 每事件只取 `< entry_date` 的最后 `126` 个 FU/SC 共同有效日；早/晚半窗各固定 `63` 日。

## 统计合同

- 三个窗口分别计算 Pearson corr 与带截距 OLS `fu_ret ~ sc_ret` beta。
- 不 winsorize、不删除极端日、不按方向翻转、不使用期权价格。
- per-event pass：三窗 `beta>0 && corr>=0.50`，且 126 个日期严格递增、全部早于 entry_date。
- 全部事件按 event 一票，不按风险金额加权来绕过失败；风险金额只作材料性汇总。

## 硬门与顺序

1. 输入 SHA、行数、FU 过滤和核心 `6` 事件一致。
2. return panel 无重复键、无未来日期、无同日 OI、无跨合约收益。
3. 核心完整历史 `6/6`，全体完整历史率 `>=90%`。
4. 核心三窗 beta/corr pass `6/6`，全体 pass rate `>=90%`。
5. 仅在 1-4 全通过后查询 SC 历史期权链；核心 coverage `6/6`、全体 `>=90%`。

## 决策

- 1-4 任一失败：`CLOSE_LINE_BASIS_RISK_INELIGIBLE`。
- 1-4 通过、5失败：`CLOSE_LINE_OPTION_CHAIN_INELIGIBLE`。
- 1-5 全过：`ALLOW_STAGE002_EXECUTION_DATA_PREDECL_ONLY`，不允许收益回测。

## 计划产物

- `contract_selection_ledger.csv.gz`
- `product_return_panel.csv.gz`
- `fu_event_beta_ledger.csv`
- `coverage_summary.csv`
- `gate_matrix.csv`
- `decision.json`
- `lineage.json`
- `report.md`

## 回测结果占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：N/A。

## 过拟合反思

- 运行前判断：中低；有 2022 后验动机，但参数、pair、全集分母和门在数据前冻结。
- 失败后禁止改代理、窗口、阈值或样本救参。

## 继续价值反思

- 运行前判断：有；只验证一个最直接经济 pair，成本低且能及时关闭整个代理思路的第一步。

