# Stage054 Stage878 早段价格/OI参与度审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 06:42 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读参与度审计 + K线视觉复核；不改官方正式版、不改官方候选配置、不接真实引擎、不连接 CTP、不调用下单。
- 是否重要突破：否；这是新信息维度线索，不是可推广版本。
- 是否触发A/B：否；尚未形成真实引擎版本。

## 外部调研与判断

- CME 对 open interest 的定义强调它反映未平仓合约数量，可作为价格趋势背后参与度/力量的辅助信息。
- Turtle/趋势跟随资料强调右尾来自持续持有，止损纪律要低自由度；频繁按失败样本救参会破坏右尾复利。
- Rob Carver 对动态止损的讨论提醒：止损若只为了回测左尾好看，容易牺牲真正的趋势跟随收益分布。
- vn.py CTA/组合策略框架适合把规则落成可复现引擎验证，而不是停留在事后代理。
- 我的判断：Stage877 已说明同一组 OR/R/重试/确认/锁盈价格派生特征继续价值低；Stage878 换到 OI/成交量参与度，属于新信息维度。固定 `60` 根，不扫描 `30/60/90/120`。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage878_stage861_early_oi_participation_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE = "Stage878"`
  - `MODEL_TAG = "stage878_stage861_early_oi_participation_audit_v1"`
  - `EARLY_BARS = 60`
  - `MIN_EARLY_BARS = 15`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage861 全量分钟K覆盖与 Stage819 候选 entry lots。
- 账户规模：未新增；本阶段不是组合回测。
- 成本口径：只读 exit/skip 代理，读取既有 realized PnL；不重算资金联动、滑点节省或释放保证金后的后续交易。
- 样本过滤：Stage861 entry lots `341`；有效早段状态样本 `339`；missing `2`；每笔取入场日最早 `60` 根1分钟K，计算 `early_price_dir_return_pct` / `early_oi_change_pct`。
- 分桶口径：按信号方向价格顺/逆向与 OI 增/减，固定分为 `favorable_price_oi_up`、`favorable_price_oi_down`、`adverse_price_oi_up`、`adverse_price_oi_down`。
- 代理口径：
  - `P1_exit_adverse_price_oi_up`
  - `P2_exit_adverse_price_any_oi`
  - `P3_exit_non_favorable_price_oi_up`

## 结果

- 期末权益：未新增；不是组合回测。
- 总收益：未新增；不是组合回测。
- 最大回撤：未新增；不是组合回测。
- Sharpe：未新增；不是组合回测。
- 总滑点：未新增；不是组合回测。
- 总交易次数：未新增；不是组合回测。
- 胜率：未新增组合胜率；分桶胜率见下。

### 状态分桶

- `favorable_price_oi_up`：`122` 笔，占比 `35.7771%`，PnL `+30,581,100`，胜率 `57.3770%`，median R `0.7156`，big winner `22`，winner PnL `+38,966,475`，loser PnL `-8,385,375`。
- `favorable_price_oi_down`：`65` 笔，PnL `+4,782,150`，胜率 `49.2308%`，median R `-0.0975`，big winner `4`。
- `adverse_price_oi_up`：`70` 笔，PnL `-1,991,820`，胜率 `41.4286%`，median R `-0.5000`，big winner `3`。
- `adverse_price_oi_down`：`82` 笔，PnL `-5,577,190`，胜率 `29.2683%`，median R `-0.6245`，big winner `2`。
- `missing`：`2` 笔，PnL `+377,640`。

### 退出/过滤代理

- `P1_exit_adverse_price_oi_up`：affected `70`，gross proxy delta `+1,991,820`，winner_cut `-7,284,525`，loser_saved `+9,276,345`，big_winner_cut `-1,520,420`，正收益年份 `5`，负收益年份 `4`。
- `P2_exit_adverse_price_any_oi`：affected `152`，gross proxy delta `+7,569,010`，winner_cut `-12,102,545`，loser_saved `+19,671,555`，big_winner_cut `-2,111,510`，正收益年份 `7`，负收益年份 `2`。
- `P3_exit_non_favorable_price_oi_up`：affected `219`，gross proxy delta `+2,409,220`，winner_cut `-21,694,425`，loser_saved `+24,103,645`，big_winner_cut `-3,971,420`，正收益年份 `5`，负收益年份 `4`。

## 视觉复核

- summary chart 显示 `favorable_price_oi_up` 明显集中右尾，adverse 状态整体偏弱；但代理退出虽然表面为正，右尾代价很大。
- atlas page001 显示 `adverse_price_oi_up` 同时包含 `SH607/lc2505/AP210` 这类左尾，也包含 `OI201` 这类早段逆向后修复成大赢家的样本。
- atlas page004 显示 `favorable_price_oi_up` 包含多笔大右尾，但也有 `SM209/OI505/lc2401` 这类早段强参与后失败样本。
- 视觉判断：早段价格/OI状态是解释标签，不是错误充分条件；直接 60m adverse 退出会复活 Stage016 类 fail-fast 误伤问题。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage878_stage861_early_oi_participation_audit_report_stage878_stage861_early_oi_participation_audit_v1.md`
- features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage878_stage861_early_oi_participation_audit_features_stage878_stage861_early_oi_participation_audit_v1.csv`
- state_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage878_stage861_early_oi_participation_audit_state_summary_stage878_stage861_early_oi_participation_audit_v1.csv`
- proxy_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage878_stage861_early_oi_participation_audit_proxy_summary_stage878_stage861_early_oi_participation_audit_v1.csv`
- yearly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage878_stage861_early_oi_participation_audit_yearly_stage878_stage861_early_oi_participation_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage878_stage861_early_oi_participation_audit_decision_stage878_stage861_early_oi_participation_audit_v1.json`
- summary chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage878_stage861_early_oi_participation_audit_summary_chart_stage878_stage861_early_oi_participation_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage878_stage861_early_oi_participation_audit_atlas_page001_stage878_stage861_early_oi_participation_audit_v1.png` 至 `page006`

## 结论

- 本阶段结论：`stage878_early_oi_participation_has_signal_no_engine_yet`
- 是否进入下一步：有条件进入一次冻结真实引擎设计审计，但不能直接推广。
- 下一步：只允许一次冻结语义；早段价格/OI状态只能作为状态标签，真实引擎必须显式保护右尾，并验证资金路径、滑点和 broker10。不得扫描 `30/60/90/120`、OI阈值、成交量阈值、品种、方向或年份。

## 过拟合反思

- 运行前判断：否。Stage878 不是从局部亏损样本反推小数阈值，而是换到价格之外的一阶参与度信息，并固定 `60` 根分钟K。
- 运行后判断：当前审计本身不是过拟合；若下一步扫描窗口、OI小数阈值、成交量阈值、品种或方向，就会过拟合。
- 原因：结果显示参与度信息有分布差异，但同时明确揭示右尾误伤代价，不能直接拿代理 delta 写规则。

## 继续价值反思

- 运行前判断：有价值。Stage877 已证明同一组价格派生规则继续救参价值低，需要新信息维度。
- 运行后判断：有有限价值。`favorable_price_oi_up` 右尾集中足够清晰，值得一次冻结真实引擎审计；但不能扩展为筛选器或参数搜索。
- 原因：最有价值的是把 OI 作为参与度状态，检验能否在不砍右尾的情况下约束早段错误；不是继续做 fail-fast 或追价过滤。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage878 最新线索与边界。
- 是否更新 `research/registry.md`：否，未形成正式候选或重大突破。
- 是否追加根目录 `memory.md/back_log.md`：否，未形成正式候选、跨线合并或重要突破。
