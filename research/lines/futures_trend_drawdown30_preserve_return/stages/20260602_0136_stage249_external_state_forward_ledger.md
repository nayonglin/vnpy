# Stage249 外生状态 Forward 账本初始化

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 01:36 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：实盘可执行数据账本初始化；不做收益回测，不生成交易候选。
- 是否重要突破：否；但把外生状态路线从“近期能取数”推进到“带真实接收时间戳的 forward 监控账本”。
- 是否触发A/B：否。没有形成可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - AKShare 期货数据文档与 GitHub：用于 basis、库存、会员持仓排名、交易所仓单等接口可用性判断。
  - Tushare 期货持仓接口文档：作为会员/持仓数据替代源方向，但当前本地 token 冒烟仍失败。
  - AQR 趋势跟踪长期证据：多市场趋势分散有长期先验，但不能代替点时化风险预算和真实数据链路。
  - `pysystemtrade`：趋势组合应按风险预算、相关性、市场分散来设计，不应按样本内赢家直接选品。
- 我的判断：你提出的“降低单笔风险、扩大品种池、每年抓部分品种趋势收益、同时避免高相关”方向仍然成立，但关键不在继续扫风险小数，而在能否事前识别“哪类品种当时有趋势土壤”。现阶段外生状态还只能进入 forward paper 账本，不能回填 2022-2026 做历史 selector。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage549_external_state_forward_ledger.py`
- 修改脚本：同一脚本内追加执行降级逻辑，避免外部接口阻断账本：
  - 将单接口超时控制为 `6` 秒。
  - 大表只保留必要尾部记录，避免 multiprocessing 队列传输大表卡住。
  - 对 DCE/CZCE 会员与交易所仓单等慢源限制尝试次数。
- 删除脚本：无。
- 新增参数：
  - `SOURCE_TIMEOUT_SECONDS=6`
  - `LOOKBACK_DAYS=5`
  - `MAX_RECORDS_PER_PROBE=600`
  - `MAX_DICT_ITEM_RECORDS=300`
  - `MEMBER_ATTEMPTS_BY_EXCHANGE={"SHFE":4,"INE":4,"DCE":1,"CZCE":2}`
  - `WAREHOUSE_ATTEMPTS_BY_EXCHANGE={"SHFE":2,"DCE":1,"CZCE":1,"GFEX":1}`
  - forward 可用最大延迟：basis/inventory/member/warehouse 均为 `7` 天。
- 修改参数：从初版 `20` 秒超时、`10` 天回看降为上述可控执行口径。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不做收益回测；采集 `2026-06-02 01:33:58 CST` 当时可收到的外生状态。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：读取 Stage548 product source matrix，剔除金融期货后 applicable 产品 `37` 个；Oracle6 产品 `6` 个。
- 策略/归因口径：只记录 `received_at_local/received_at_utc/source_date/source_function/raw_sha256` 与可用性；`usable_for_history_selector` 全部置 `0`，防止历史回填误用。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`forward_external_ledger_initialized_not_selector_ready`
  - snapshot rows：`148`
  - master ledger：`external_state_forward_ledger.csv`
  - route summary：
    - basis：`28/37` ok，forward ready `28/37`；Oracle6 `4/6` ready。
    - inventory：`24/37` ok，forward ready `24/37`；Oracle6 `6/6` ready。
    - member_detail：`0/37` ok；本轮 SHFE/INE 返回但未匹配产品，DCE 报 `BadZipFile`，CZCE 多数超时。
    - warehouse：`0/37` ok；SHFE/DCE 多数 `JSONDecodeError`，CZCE `ValueError`，INE 当前路径不适用。
  - Oracle6 forward-ready routes：
    - `al.SHFE`：`2`
    - `c.DCE`：`2`
    - `v.DCE`：`2`
    - `y.DCE`：`2`
    - `ao.SHFE`：`1`
    - `lu.INE`：`1`
  - history selector ready：`0/37`，Oracle6 `0/6`。
  - 图表视觉复盘：
    - Oracle6 热力图中 `inventory` 全绿，说明库存可以先作为 forward 监控层。
    - `basis` 对 `al/c/v/y` 为绿，但 `ao/lu` 为红，覆盖不完整。
    - `member_detail` 与 `warehouse` 两列全红，说明这两类源当前不能作为实盘快速决策依赖，更不能直接历史回填。
    - 产品分布图显示 `20` 个产品有 `2` 条 forward-ready route，`12` 个产品只有 `1` 条，`5` 个产品为 `0`；外生状态覆盖仍不均匀。

## 输出文件

- snapshot：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage549_external_state_forward_ledger_snapshot_stage549_external_state_forward_ledger_v1.csv`
- master ledger：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/external_state_forward_ledger/external_state_forward_ledger.csv`
- route summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage549_external_state_forward_ledger_route_summary_stage549_external_state_forward_ledger_v1.csv`
- product summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage549_external_state_forward_ledger_product_summary_stage549_external_state_forward_ledger_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage549_external_state_forward_ledger_decision_stage549_external_state_forward_ledger_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage549_external_state_forward_ledger_report_stage549_external_state_forward_ledger_v1.md`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage549_external_state_forward_ledger_chart_stage549_external_state_forward_ledger_v1.png`

## 结论

- 本阶段结论：外生状态 forward 账本已初始化，但还没有 selector-ready。库存和部分 basis 可以开始做 paper 监控；会员持仓和仓单在当前 AKShare 路线下仍不稳定，不能用于选品回测或交易候选。
- 对“降低单笔风险 + 扩大品种池 + 避免高相关”的判断：方向仍对，但下一步不能靠历史赢家或样本内 Oracle6 直接选品。正确路径应是“核心仓不被替换 + 新品种低风险 sleeve + 产品族/相关性预算 + 点时化外生状态监控”，先积累 forward 证据，再做预测力审计。
- 是否进入下一步：不进入交易候选；进入 forward paper 数据积累。只有账本积累出足够多 `received_at` 样本后，才允许验证库存/basis/会员/舆情是否能事前解释品种趋势土壤。

## 过拟合反思

- 运行前判断：不是过拟合。它只建立真实接收时间戳账本，不看未来收益、不调策略规则。
- 运行后判断：不是过拟合，且进一步降低了过拟合风险。
- 原因：本阶段把所有外生状态都标记为 history selector 不可用，避免用 2026 年可取到的数据去回填解释 2022-2026 的收益。

## 继续价值反思

- 运行前判断：有价值，因为 Stage241/242 证明选对非核心品种有上限空间，但 Stage243-247 证明现有事前特征不足。
- 运行后判断：仍有价值，但短期价值在 paper 监控和数据工程，不在策略回测调参。
- 原因：库存/basis 已能覆盖相当一部分产品，足以积累 forward 证据；会员/仓单不稳定则提示不要把这些源设计成盘中硬依赖。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`。
