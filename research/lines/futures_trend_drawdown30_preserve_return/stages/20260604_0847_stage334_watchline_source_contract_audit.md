# Stage334 watch 线产品源合同审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 08:47 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：低单笔风险扩池 watch 线产品的 source contract 与晋级闸门审计
- 是否重要突破：否；没有新增可部署风险槽、paper 或交易白名单
- 是否触发A/B：否；没有策略版本进入正式候选、paper 或交易白名单

## 外部调研与判断

- 参考资料：
  - AQR 趋势跟随长期分散研究：`https://research.cbs.dk/en/publications/a-century-of-evidence-on-trend-following-investing-executive-summ`
  - Trend following / risk parity / commodity futures：`https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2201829_code1055219.pdf?abstractid=2126813&mirid=1&type=2`
  - Optimal allocation of trend following strategies：`https://www.sciencedirect.com/science/article/pii/S0378437115003404`
  - Man Group trend following market mix：`https://www.man.com/insights/trend-following-optimal-market-mix`
  - CZCE dried jujube contract overview：`https://english.zce.cn/en/index.htm`
  - CZCE dried jujube detailed rules：`https://english.czce.com.cn/en/Rulebook/DetailedRules/webinfo/2025/08/1750864479605262.htm`
  - 国家林草局新疆红枣产业资料：`https://www.forestry.gov.cn/lyj/1/slgs/20241023/593126.html`
  - 农业农村部生猪产品月度数据示例：`https://www.moa.gov.cn/ztzl/szcpxx/jdsj/2025/202501/`
  - 全国畜牧总站畜产品和饲料价格月报示例：`https://www.nahs.org.cn/jcyj/scxs/202601/t20260115_469255.htm`
  - DCE 生猪合约与交割材料：`https://www.dce.com.cn/dceg/file/2025-05-25/1748165285051ff8080819701ddb3518019706c554bb21f7.pdf`
- 我的判断：
  - 用户提出的“减少单笔风险、扩大品种池、每年抓部分品种趋势收益、避免高相关”方向成立，但第一性原理不是增加品种数量，而是增加可交易、低相关、有独立经济驱动、source 和 TCA 可闭合的有效风险槽。
  - Stage333 找到 `CJ.CZCE/lh.DCE` 位于 watch corr 附近，但 watch corr 只说明它们值得 source 可执行性复核，不代表能直接做收益回测或选品晋级。
  - `lh.DCE` 的公开官方月度源更强，农业农村部和全国畜牧总站有月度生猪供需、价格、猪粮比等稳定口径；`CJ.CZCE` 当前主要是交易所合约/交割规则和红枣产业背景，缺少稳定、月度、可自动化的官方基本面 release。
  - 因此本阶段只做 source contract 审计，不做 selector、paper、A/B、白名单或 CTP。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage634_watchline_source_contract_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - watch 产品：`CJ.CZCE/lh.DCE`
  - 输入产品图：Stage633 `product_map`
  - 晋级硬闸门：price/liquidity/watch corr 通过、source contract 存在、`lh` 月度官方源 `>=2`、`CJ` 月度官方源缺口被记录、fetch/hash/PIT 未验证时 fail-closed、paper/whitelist 为 `0`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：本阶段不做收益回测；只读 Stage633 产品代理与本阶段 source contract
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：
  - `CJ.CZCE`：Stage633 中 `tradable_rows=1511`、`last_tradable_date=2026-03-13`、`recent_median_volume=1713.5`
  - `lh.DCE`：Stage633 中 `tradable_rows=1261`、`last_tradable_date=2026-03-26`、`recent_median_volume=35296.5`
- 策略/归因口径：
  - 不重放策略、不看策略收益、不改交易规则、不生成 selector/paper/交易白名单、不连接 CTP
  - 只审计 source contract 是否足以进入下一步 raw-hash/PIT fetch probe

## 结果

- 期末权益：不适用；本阶段不是收益回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`watchline_source_contract_ready_fetch_probe_required_no_promotion`
  - watch products：`2`
  - source contract rows：`6`
  - `lh` monthly official source rows：`2`
  - `CJ` monthly official source rows：`0`
  - active fetch validated rows：`0`
  - raw hash rows：`0`
  - PIT dates now：`0`
  - promotion rows：`0`
  - paper/whitelist rows：`0`
  - hard gates：`9/9`
  - `lh.DCE` readiness score：`0.72`
  - `CJ.CZCE` readiness score：`0.68`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage634_watchline_source_contract_audit_report_stage634_watchline_source_contract_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage634_watchline_source_contract_audit_decision_stage634_watchline_source_contract_audit_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage634_watchline_source_contract_audit_source_contract_stage634_watchline_source_contract_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage634_watchline_source_contract_audit_product_summary_stage634_watchline_source_contract_audit_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage634_watchline_source_contract_audit_gates_stage634_watchline_source_contract_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage634_watchline_source_contract_audit_chart_stage634_watchline_source_contract_audit_v1.png`

## 图表视觉复盘

- 左上图：
  - `lh.DCE/CJ.CZCE` 的 data、liquidity、watch corr 基础层均为 `1`，说明它们不是价格覆盖或流动性层面的立即淘汰对象。
  - `lh.DCE` 的 source contract 层高于 `CJ.CZCE`，原因是 `lh` 有月度官方供需/价格源，`CJ` 当前主要是静态合约/交割/产业资料。
  - fetch 与 raw hash 均为 `0`，说明两者都不能进入 selector。
- 右上图：
  - `lh.DCE` 独有 `monthly_supply_demand_release` 和 `monthly_price_release` 两类源。
  - `CJ.CZCE` 只有 `contract_spec_reference`、`delivery_rule_reference` 和 `spot_industry_reference`，没有稳定月度官方基本面 release。
- 左下图：
  - 两个产品的 monitor status 都是 `contract_only_fetch_probe_required`，橙色柱不是机会强弱，而是提醒“只有合同，尚未抓取验证”。
- 右下图：
  - hard gates 全绿，但绿色包含 `fetch_not_validated_fail_closed`、`no_paper_or_whitelist`、`selector_requirements_unmet_fail_closed`。
  - 因此绿色代表纪律锁定成功，不代表晋级。

## 结论

- 本阶段结论：
  - `lh.DCE` 比 `CJ.CZCE` 更适合进入下一步 watchline source fetch probe，因为它有两个更稳定的官方月度源候选。
  - `CJ.CZCE` 仍需先补产品族定义，并验证 CZCE/红枣公开源是否能稳定自动化抓取；当前只能观察。
  - 两个产品都没有 raw hash、PIT 日期、独立 episode、selector 预测力或 live TCA，因此都不能 paper、A/B、白名单或实盘。
- 是否进入下一步：进入下一步 source fetch probe，但只对 `lh.DCE` 优先，`CJ.CZCE` 降级为分类和源发现。
- 下一步：
  - 优先为 `lh.DCE` 建立 MOA/NAHS 月度源 raw-hash fetch probe，字段至少包含 `received_at/source_url/final_url/published_at/raw_hash/status/product_vt_symbol/source_class`。
  - `CJ.CZCE` 先做产品族分类和稳定源发现；若 CZCE 路由继续受阻，不允许用静态产业文章构造 selector。
  - 未累计 PIT 样本、独立 episode 和 TCA 前，继续禁止 selector、paper、A/B 和交易白名单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有用收益结果筛品种，也没有调交易规则或阈值。
  - 只是把 Stage333 的 watch 产品推进到 source contract 层，审计可执行数据源是否存在。
  - 所有晋级相关字段保持为 `0`，且 fetch/hash/PIT 不存在时明确 fail-closed。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但优先级应收窄。
- 原因：
  - `lh.DCE` 具备低相关观察资格、较好流动性和官方月度源候选，适合做小步 source fetch probe。
  - `CJ.CZCE` 的低相关观察资格不足以抵消 source 弱点，继续价值在源发现和产品族分类，而不是收益回测。
  - 整体方向继续服务于“降低单笔风险、增加独立风险槽”，但当前仍没有新增可部署槽。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage334 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是重要突破、路线废弃、正式候选或跨线合并。
