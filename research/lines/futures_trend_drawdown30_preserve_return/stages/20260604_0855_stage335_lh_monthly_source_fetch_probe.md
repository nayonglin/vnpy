# Stage335 lh 官方月度源 fetch probe

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 08:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：低单笔风险扩池 watch 线 `lh.DCE` 官方月度基本面源 raw-hash/PIT 抓取探针
- 是否重要突破：否；只是 source 可执行性前进，不是策略晋级
- 是否触发A/B：否；没有策略版本进入正式候选、paper 或交易白名单

## 外部调研与判断

- 参考资料：
  - 农业农村部生猪产品月度数据：`https://www.moa.gov.cn/ztzl/szcpxx/jdsj/2025/202501/`
  - 全国畜牧总站 2026 年 4 月畜产品和饲料价格月报：`https://www.nahs.org.cn/jcyj/scxs/202605/t20260519_472251.htm`
  - 全国畜牧总站畜禽生产价格页面：`https://www.nahs.org.cn/jchsjcm/xqsc/`
  - GitHub fushare 中国商品期货基本面监控项目：`https://github.com/LowinLi/fushare`
- 我的判断：
  - MOA 生猪产品月度数据能直接提供能繁母猪、定点屠宰、生猪出场价、猪粮比等月度口径，比静态产业文章更适合作为 point-in-time source。
  - NAHS 月度畜产品和饲料价格月报提供生猪、猪肉、仔猪、猪粮比等价格口径，能与 MOA 供需口径互补。
  - GitHub/fushare 证明中国商品期货基本面数据做定时抓取、落本地 CSV 是常见工程形态，但它不能替代生猪官方月报的 raw-hash 证据；本阶段必须自己抓官方源并记录 `received_at/source_url/final_url/raw_sha256/status`。
  - 本阶段仍然只是 source probe，不允许历史回填 selector，也不允许 paper、A/B 或白名单。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage635_lh_monthly_source_fetch_probe.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - active fetch targets：`2`
  - MOA target：`monthly_supply_demand_release`，release period `2025-01`
  - NAHS target：`monthly_price_release`，release period `2026-04`
  - fetch validated 条件：`HTTP 200`、`response_bytes >= 500`、`raw_sha256` 非空、关键词命中 `>=2`、预期字段解析 `>=2`
  - selector PIT 阈值：`20` 个 received_at 日期
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：本阶段不做收益回测；只抓取 `2026-06-04 08:55 CST` 时点的两个官方页面
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：
  - 输入为 Stage334/634 的 `lh.DCE` 月度官方 source contract
  - 沙箱内首次运行 DNS 失败：`URLError(gaierror(8, 'nodename nor servname provided, or not known'))`
  - 按权限规则用外部网络重跑成功；沙箱 DNS 失败不计作官方源失败
- 策略/归因口径：
  - 不重放策略、不看收益、不改交易规则、不追加 master PIT ledger、不生成 selector/paper/交易白名单、不连接 CTP
  - 只写 stage-scoped fetch ledger、product status、field matrix、gates、report 和 chart

## 结果

- 期末权益：不适用；本阶段不是收益回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`lh_monthly_source_fetch_validated_stage_scoped_selector_locked`
  - monthly source targets：`2`
  - active fetch validated rows：`2`
  - raw hash rows：`2`
  - extracted field rows：`8`
  - PIT dates now：`1`
  - selector rows：`0`
  - paper/whitelist rows：`0`
  - hard gates：`9/9`
  - MOA response bytes：`76618`
  - MOA raw sha256：`d7a00c5c3bf1e1af81b350e2bbb4e9dcd1144d327e29f5af26643c834335e89f`
  - NAHS response bytes：`411744`
  - NAHS raw sha256：`29c3547e1c89dbb084868597a68c5dd4390fe839573455e9454685e9bfcd7a59`
- 解析字段：
  - MOA：`sow_inventory=4062`、`slaughter_volume=3816`、`hog_exit_price=16.41`、`pig_grain_ratio=7.81`
  - NAHS：`hog_market_price=10.07`、`pork_market_price=20.37`、`piglet_price=23.50`、`pig_grain_ratio=4.03`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage635_lh_monthly_source_fetch_probe_report_stage635_lh_monthly_source_fetch_probe_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage635_lh_monthly_source_fetch_probe_decision_stage635_lh_monthly_source_fetch_probe_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage635_lh_monthly_source_fetch_probe_fetch_ledger_stage635_lh_monthly_source_fetch_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage635_lh_monthly_source_fetch_probe_product_status_stage635_lh_monthly_source_fetch_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage635_lh_monthly_source_fetch_probe_field_matrix_stage635_lh_monthly_source_fetch_probe_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage635_lh_monthly_source_fetch_probe_gates_stage635_lh_monthly_source_fetch_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage635_lh_monthly_source_fetch_probe_chart_stage635_lh_monthly_source_fetch_probe_v1.png`

## 图表视觉复盘

- 左上图：
  - MOA 和 NAHS 两条源的 `http_ok/bytes_ok/raw_sha256_present/keyword_ok/field_ok` 都为 `1`。
  - 说明这不是网页人工可看而脚本不可抓的状态，当前脚本已能自动化拿到 raw hash 和字段探针。
- 右上图：
  - 字段矩阵显示两个源互补：MOA 覆盖 `sow_inventory/slaughter_volume/hog_exit_price`，NAHS 覆盖 `hog_market_price/piglet_price/pork_market_price`。
  - `pig_grain_ratio` 两边都有，是后续做一致性审计的自然锚点。
- 左下图：
  - `active_fetch_validated_rows=2`、`raw_hash_rows=2`，但 `pit_received_dates=1`，离红线 `20` 个 PIT 日期还很远。
  - `history_selector_rows=0`、`paper_or_whitelist_rows=0`，说明 fetch 成功没有越权变成交易信号。
- 右下图：
  - hard gates 全绿，但其中包含 `pit_dates_still_below_selector_threshold`、`selector_rows_zero`、`paper_whitelist_zero` 和 `master_append_zero_stage_scoped`。
  - 因此绿色代表源验证和锁定纪律同时成立，不代表 `lh.DCE` 晋级。

## 结论

- 本阶段结论：
  - `lh.DCE` 官方月度基本面源从“合同存在”前进到“stage-scoped active fetch validated”。
  - 这证明 `lh` 相比 `CJ` 更值得继续沿 forward monitor 推进，但还不是 alpha 结论。
  - 当前只有一个 `received_at` 日期，没有独立 episode、预测力审计、live TCA 或真实执行链路；selector、paper、A/B、白名单继续为 `0`。
- 是否进入下一步：进入下一步，但仍只做 source pipeline。
- 下一步：
  - 为 `lh.DCE` 建立 master PIT append gate：只允许幂等追加 `received_at/source_url/final_url/raw_sha256/status/field_json`，并拒绝 duplicate/hash 缺失/字段 schema 缺失行。
  - 至少累计 `20` 个 received_at 日期、`12` 个月跨度和 `3` 个独立趋势 episode 后，才允许做预测力审计。
  - 在此之前禁止把 MOA/NAHS 字段历史回填成 selector，也禁止 paper、A/B 和交易白名单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有看收益、没有调策略参数、没有根据历史表现选品种。
  - 只验证官方公开源是否能在当前时点自动抓取、hash、解析和 fail-closed。
  - 成功结果仍然把 selector/paper/白名单锁为 `0`。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但必须保持 source-first。
- 原因：
  - `lh.DCE` 已具备官方月度 source 的可执行证据，是低单笔风险扩池路线里少数可以继续推进的 watch 产品。
  - 继续价值不在马上回测收益，而在把 source 证据做成可累计、可复验、不可历史偷看的 master PIT ledger。
  - 若后续无法积累 PIT 样本或 TCA，则该路线仍应停止在 monitor 层。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage335 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式候选、路线废弃、跨线合并或重大突破。
