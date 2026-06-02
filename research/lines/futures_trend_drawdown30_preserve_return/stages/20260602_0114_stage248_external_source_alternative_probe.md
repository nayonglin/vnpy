# Stage248 外生状态替代源探针

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 01:14 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据源可执行性与历史深度审计；不做收益回测，不生成交易候选。
- 是否重要突破：否；但把外生状态方向从“理论上可用”收窄为“近期实盘可监控、历史回测仍不够”。
- 是否触发A/B：否。没有形成可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - AKShare 期货数据文档与 GitHub：`futures_inventory_em`、`futures_spot_price`、交易所仓单、会员排名明细接口。
  - Tushare `fut_holding` 与期货基础资料接口文档。
  - AQR 趋势跟踪长期证据：多市场趋势分散有先验，但不能替代真实风险预算与可执行数据。
  - `pysystemtrade`：分散期货、风险预算、相关性控制是趋势策略工程常识，但品种选择仍需避免样本内赢家筛选。
- 我的判断：降低单笔风险、扩大品种池、避免高相关的方向仍然成立；但外生状态必须同时满足“实盘可获取”和“历史点时化可回测”。本阶段找到一批近期可监控数据源，却没有找到能支撑 2022-2026 历史 selector 的完整外生状态。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage548_external_source_alternative_probe.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 探针日期：`20260417`
  - 库存源：`futures_inventory_em`
  - 会员明细源：`get_shfe_rank_table`、`get_dce_rank_table`、`futures_dce_position_rank`、`get_rank_table_czce`、`futures_gfex_position_rank`
  - 仓单源：`futures_shfe_warehouse_receipt`、`futures_warehouse_receipt_dce`、`futures_warehouse_receipt_czce`、`futures_gfex_warehouse_receipt`、`get_receipt`
  - 库存 asof 最大允许延迟：`7` 天
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不做收益回测；只检查 Stage543 非核心产品池、Stage547 basis 覆盖与 `20260417` 外生源探针。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：Stage543 非核心产品，剔除不适用外生商品状态的金融指数后 applicable 产品 `37` 个；Oracle6 产品 `6` 个。
- 策略/归因口径：只做数据源 readiness 和历史深度审计，不调权重、不筛选收益、不生成订单。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`alternative_sources_partial_live_ready_not_backtest_ready`
  - Oracle6：
    - basis 历史 ready：`4/6`
    - `futures_inventory_em` 近期库存 ready：`6/6`
    - 库存覆盖探针日：`6/6`
    - 库存历史回测深度 ready：`0/6`
    - 会员明细 live ready：`3/6`，主要是 SHFE/INE 的 `AL/AO/LU`
    - 交易所仓单 live ready：`0/6`
    - all core external state ready：`0/6`
  - 全 applicable 产品：
    - basis 历史 ready：`25/37`，`67.5676%`
    - 库存近期 ready：`24/37`，`64.8649%`
    - 库存探针日 ready：`23/37`，`62.1622%`
    - 库存历史回测深度 ready：`0/37`
    - 会员明细 live ready：`21/37`，`56.7568%`
    - 交易所仓单 live ready：`8/37`，`21.6216%`
    - 任一 live 外生状态 ready：`33/37`，`89.1892%`
  - Tushare：已安装、`TUSHARE_TOKEN` 存在，但冒烟状态 `failed_Exception`，当前不能作为 live pipeline 依赖。
  - 图表视觉复盘：
    - Oracle6 热力图中 `inventory recent` 与 `inventory asof` 全绿，但 `inventory 2022+` 全红，说明库存只适合近期实盘监控，不适合直接历史回测。
    - `member` 只在 `AL/AO/LU` 为绿，`C/V/Y` 为红，DCE 是会员数据的关键缺口。
    - `warehouse` Oracle6 全红，交易所仓单不能支撑当前选品。
    - 右下角交易所图显示 SHFE/CZCE 明细通道较好，DCE 为 `0/14`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage548_external_source_alternative_probe_report_stage548_external_source_alternative_probe_v1.md`
- product source matrix：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage548_external_source_alternative_probe_product_source_matrix_stage548_external_source_alternative_probe_v1.csv`
- route summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage548_external_source_alternative_probe_route_summary_stage548_external_source_alternative_probe_v1.csv`
- probe detail：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage548_external_source_alternative_probe_probe_detail_stage548_external_source_alternative_probe_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage548_external_source_alternative_probe_decision_stage548_external_source_alternative_probe_v1.json`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage548_external_source_alternative_probe_chart_stage548_external_source_alternative_probe_v1.png`

## 结论

- 本阶段结论：找到了一条可实盘监控的外生状态路径，但还没有找到可回测、可晋级的历史 selector 数据路径。`futures_inventory_em` 对 Oracle6 全覆盖，但历史仅从 `2026-02-24` 到 `2026-06-01`；`get_shfe_rank_table` 可以绕过汇总会员接口的 BadZipFile，但只覆盖 SHFE/INE，DCE 仍失败；交易所仓单对 Oracle6 仍不可用。
- 是否进入下一步：不进入交易候选；可以进入两条分支，一是做 live/paper 外生状态监控账本，二是继续修复 DCE 会员和历史库存/仓单源。
- 下一步：不要用 `inventory_em` 直接做 2022-2026 历史 selector；不要调外生状态权重。若继续选品，优先补 DCE 会员和库存/仓单历史深度，或者把外生状态降级为 forward paper 监控。

## 过拟合反思

- 运行前判断：不是过拟合。它只审计数据源是否可用、是否有历史深度，不看收益。
- 运行后判断：不是过拟合，且主动阻止了新的过拟合风险。
- 原因：如果把 2026 年才有的库存数据拿去解释 2022-2026 的 Oracle6，就会形成后验解释和历史不可复验；本阶段明确禁止这样做。

## 继续价值反思

- 运行前判断：有价值，因为 Stage246/247 说明 basis 单因子不够，需要更本质外生状态。
- 运行后判断：仍有价值，但应从“历史回测 selector”转为“外生状态 forward 监控/数据工程修复”。
- 原因：近期 live 覆盖已经足够做 paper 监控，说明实盘链路有希望；但历史深度不足，不能作为当前回测晋级依据。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`。
