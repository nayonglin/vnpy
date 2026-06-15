# Stage034 Stage858 Stage857后覆盖偏差审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 01:39 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据覆盖偏差审计，不是策略回测
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk DataDownloader 官方文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html`
  - vn.py 的 TqSdk 数据服务接口 GitHub：`https://github.com/vnpy/vnpy_tqsdk`
- 我的判断：
  - TqSdk 官方文档明确 DataDownloader 是历史行情下载工具且属于专业版能力；Stage856 的 `您的账户不支持下载历史数据功能` 属于权限阻断，不是继续重跑脚本可以解决的问题。
  - vnpy_tqsdk 只能作为 vn.py 接入 TqSdk 的数据服务通路，不能绕过上游账号历史下载权限。
  - 本阶段的第一性问题不是“哪个日内规则更好”，而是“当前分钟K样本是否有资格代表全周期”。如果缺失集中在早期年份、右尾和压力段，继续用 covered subset 产生全周期规则会形成选择偏差。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage858_stage857_coverage_bias_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage825/Stage855 的 Stage819 closed lots 全周期样本，`341` 笔 closed lots。
- 账户规模：不适用，本阶段不跑组合回测。
- 成本口径：不适用，本阶段只读既有 closed lot PnL 和覆盖标记。
- 样本过滤：不新增交易样本；按 `after_patch_entry_day_covered` 将 Stage855 后样本分为 covered / missing。
- 策略/归因口径：
  - `Stage855` 后 entry-day minute coverage。
  - `Stage856` remaining gap requests。
  - `Stage857` patch entry lots。
  - `Stage849` pressure key dates 与 paired lots。

## 结果

- 期末权益：不适用，本阶段不是回测。
- 总收益：不适用，本阶段不是回测。
- 最大回撤：不适用，本阶段不是回测。
- Sharpe：不适用，本阶段不是回测。
- 总滑点：不适用，本阶段不是回测。
- 总交易次数：不适用，本阶段不是回测。
- 胜率：covered `48.6056%`，missing `38.8889%`，仅作覆盖偏差描述，不作策略优劣证据。
- 其他关键指标：
  - Stage855 后入场日分钟K覆盖：`251/341 = 73.6070%`。
  - 原始覆盖：`227` 笔；Stage855 本地 raw patch 新增覆盖：`24` 笔。
  - 未覆盖：`90` 笔。
  - 未覆盖绝对 PnL：`6,087,275`，占全样本绝对 PnL `6.5349%`。
  - 未覆盖净 PnL：`1,548,975`。
  - big winner：总 `31` 笔，covered `25` 笔，missing `6` 笔。
  - 2018 年：`0/25` 覆盖；2019 年：`0/45` 覆盖。
  - Stage849 pressure key dates：`12/19 = 63.1579%` 覆盖，仍缺 `7` 个。
  - pressure paired lots：总 `8` 笔，covered `5` 笔，missing `3` 笔。
  - Stage856 remaining gap requests：`97` 个，priority abs PnL `6,434,115`，含 `6` 个 big-winner requests、`17` 个产品、`65` 个合约。
  - 偏差红旗数：`4`，判定 `severe_bias=True`。
  - 决策：`stage858_coverage_bias_severe_no_rule`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage858_stage857_coverage_bias_audit_report_stage858_stage857_coverage_bias_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage858_stage857_coverage_bias_audit_summary_stage858_stage857_coverage_bias_audit_v1.csv`
- orders：不适用。
- daily：不适用。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage858_stage857_coverage_bias_audit_coverage_by_year_stage858_stage857_coverage_bias_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage858_stage857_coverage_bias_audit_coverage_by_product_stage858_stage857_coverage_bias_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage858_stage857_coverage_bias_audit_coverage_by_direction_stage858_stage857_coverage_bias_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage858_stage857_coverage_bias_audit_coverage_by_outcome_stage858_stage857_coverage_bias_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage858_stage857_coverage_bias_audit_pnl_distribution_stage858_stage857_coverage_bias_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage858_stage857_coverage_bias_audit_top_missing_lots_stage858_stage857_coverage_bias_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage858_stage857_coverage_bias_audit_pressure_coverage_bias_stage858_stage857_coverage_bias_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage858_stage857_coverage_bias_audit_bias_chart_stage858_stage857_coverage_bias_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage858_stage857_coverage_bias_audit_decision_stage858_stage857_coverage_bias_audit_v1.json`

## 结论

- 本阶段结论：
  - 覆盖偏差严重，不能基于当前 covered subset 生成新的全周期分钟级入场/出场规则。
  - 2018/2019 完全无 entry-day 分钟K，是系统性时间偏差；不是随机缺失。
  - 未覆盖样本仍包含 `6/31` 个 big winner、`3/8` 个 pressure paired lots 和 `7/19` 个 pressure key dates，说明右尾和压力段都没有被完整视觉化。
  - 这次审计没有否定分钟级路线本身，只否定“在当前数据覆盖下继续写全周期规则”的资格。
- 是否进入下一步：进入，但下一步仍是数据/证据层，不是策略规则层。
- 下一步：
  - 优先寻找替代分钟源或开通历史下载权限，补 `FG209/fu2205/fu2209/rb2210/FG601/AP210/lc2401` 等高影响缺口。
  - 如果短期无法补数，下一阶段只能做 `2020+ covered subset` 的局部假设审计，并明确不能声称全周期成立。
  - 不做 `R` 倍数、开盘区间、重试次数、品种/方向阈值救参。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段不使用未来收益去调参数，也没有新增交易规则；它只检查覆盖样本是否系统偏斜。相反，本阶段的作用是阻止我们在缺数和选择偏差下过早提炼规则。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但价值集中在补数据和限定证据边界。
- 原因：Stage858 明确了当前最大风险不是规则没想出来，而是分钟K证据不具备全周期代表性。继续补数有价值；在补完前继续做规则救参没有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破、正式候选或路线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不属于正式候选、重要突破或跨线迁移。
