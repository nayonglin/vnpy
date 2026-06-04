# Stage311 独立风险槽准入协议审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 05:01 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读协议化审计；不重放交易引擎、不修改策略、不生成交易白名单。
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage611_risk_slot_admission_protocol.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage611_risk_slot_admission_protocol_report_stage611_risk_slot_admission_protocol_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage611_risk_slot_admission_protocol_chart_stage611_risk_slot_admission_protocol_v1.png`
- 决策：`risk_slot_admission_protocol_ready_new_budget_zero_not_deployable`
- 是否重要突破：否。它把扩池方向从判断升级成准入协议，但没有形成可部署候选。
- 是否触发 A/B：否。当前新增风险预算为 `0%`，没有 paper selector、没有交易白名单。
- 是否新增回测：否。
- 是否修改策略：否。
- 是否连接 CTP/SimNow：否。
- 是否调用 `send_order`：否。

## 开始前反思

- 是否过拟合：否。本阶段不按历史收益挑品种，也不扫 `TopN/risk/corr/family cap` 小数，只把 Stage604/609/610 冻结证据转成准入规则。
- 是否有价值继续：有。用户提出“减少单笔风险、扩大品种池、每年抓部分趋势、避免高相关、选对品种”，核心需要的是准入协议，而不是再跑宽池收益榜。

## 外部调研判断

- Man Group 趋势组合资料强调市场集合、相关、波动、流动性和成本共同决定趋势组合质量。
- `pysystemtrade` 把 instrument diversification、risk target 和相关性估计放在组合构造核心，支持“按独立风险源扩展”而不是“按品种数量扩展”。
- PyPortfolioOpt / skfolio 的 HRP、risk budgeting、maximum diversification 说明聚类和风险贡献是有用工具，但本仓库不能直接套黑箱优化器；必须先满足 point-in-time source、容量、真实成交和 TCA。
- 本阶段判断：扩池方向成立，但正确表达是“准入独立风险槽”，不是“多加历史赢家品种”。

参考：

- Man Group Trend Following Market Mix: https://www.man.com/insights/trend-following-optimal-market-mix
- Rob Carver pysystemtrade: https://github.com/robcarver17/pysystemtrade
- PyPortfolioOpt HRP: https://github.com/PyPortfolio/PyPortfolioOpt
- skfolio risk budgeting / HRP: https://github.com/skfolio/skfolio

## 本阶段做了什么

- 读取 Stage604 风险槽 allocator、Stage609 下一路径队列、Stage610 SimNow wrapper dry-run 冻结输出。
- 新增 Stage611 脚本，生成：
  - family admission 表；
  - contract rules 表；
  - hard gates 表；
  - decision JSON；
  - markdown report；
  - 可视化图表。
- 明确当前新增风险预算为 `0%`：source/TCA/live context 未闭合前，任何新产品族只能观察，不能 paper、不能 A/B、不能交易白名单。
- 首轮图表视觉检查发现失败闸门红条不可见、行动队列标签过碎；已修正并重跑。

## 新增/修改/删除

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage611_risk_slot_admission_protocol.py`
- 修改脚本：无既有策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `TARGET_EFFECTIVE_SLOTS = 7`
  - `CURRENT_EFFECTIVE_SLOTS = 4`
  - `IF_BLACK_FERROUS_RESOLVED_SLOTS = 5`
  - `PREFERRED_SINGLE_SLOT_RISK_PCT = 15.0`
  - `HARD_SINGLE_SLOT_RISK_PCT = 20.0`
  - `MAX_CORE_CORR_PREFERRED = 0.10`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测结果

本阶段没有新增交易回测，因此以下字段不适用：

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 核心结果

- 当前有效独立风险槽：`4`
- 目标有效独立风险槽：`7`
- 当前单槽风险代理：`25.00%`
- 目标单槽风险代理：`14.29%`
- 如果 `black_ferrous(j/i)` source/TCA 全部解决：`5` 槽，单槽风险 `20.00%`
- 当前新增风险预算：`0.00%`
- 当前可部署 selector 槽：`0`
- 当前 paper allowed rows：`0`
- 当前 trading whitelist rows：`0`
- hard gates：`6/10`
- Stage610 状态：`connect_requested=false`、`tick_rows=0`

## 准入协议

| 规则 | 含义 |
| --- | --- |
| `risk_slot_not_product_count` | 新增的是独立经济驱动族，不是单纯新增品种数量。 |
| `family_top1_same_direction` | 同一产品族同方向最多一个产品获得风险预算；`y/c`、`j/i` 不能算两个独立槽。 |
| `no_budget_before_source_tca_execution` | source、forward 样本、live context、TCA 任一未闭合，新增槽预算为 `0%`。 |
| `high_core_corr_reject` | 核心相关高于观察线的历史赢家不得作为分散槽。 |
| `target_slot_width` | 最小偏好结构是 `7` 槽左右，而不是当前 `4` 或 `j/i` 后的 `5`。 |
| `forward_monitor_not_backfit` | `soft_agri/precious_metals` 只能点时化观察，不能回头拟合历史白名单。 |
| `execution_no_bias_first` | 扩池晋级前先证明真实快照、真实成交、`vt_orderid` 和 tick/TCA 闭合。 |

## 图表视觉复盘

- 左上：`4 -> 5 -> 7` 的槽数缺口非常直观；`j/i` 解决后也只是 `20%/slot`，仍不是低单槽风险偏好结构。
- 右上：多数候选在低相关/source/capacity 上有局部绿灯，但 `TCA/live/deploy` 三列全红，说明当前不能给资金。
- 左下：失败闸门显式红色，主要卡在有效槽不足、单槽风险过高、3/6个月左尾未改善、live tick 未闭合。
- 右下：行动队列仍是执行/TCA 第一、`j/i` source/TCA 第二、source-rich monitor 第三、拒绝高相关赢家继续保持。

## 结论

- 用户的方向继续成立：每年确实存在部分品种/产品族趋势机会，降低单槽风险是比继续改 079 小参数更本质的方向。
- 但当前不能晋级：新增风险预算必须保持 `0%`。
- `black_ferrous(j/i)` 是唯一当前 P1 新独立槽 worklist，但不能独自解决目标；即便成功也只有 `5/7` 槽。
- `soft_agri/precious_metals` 只做 forward monitor，不做 paper。
- `rubber/br` 这类高相关历史赢家继续拒绝。

## 结束后反思

- 是否过拟合：否。脚本明确把历史有收益但高相关的族拒绝，把低相关但缺 TCA/live 的族预算设为 `0%`，没有用历史赢家救结果。
- 是否有价值继续：有，但要沿证据链继续。下一步不是宽池收益回测，而是闭合执行无偏差、`j/i` source/TCA、以及寻找两个真正新独立驱动。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage611_risk_slot_admission_protocol.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage611_risk_slot_admission_protocol.py`：通过。
- 图表视觉检查：第一轮发现失败闸门和标签问题，修正后第二轮通过。
- 输出文件存在：通过。

## TODO

- 执行侧：继续按 Stage310 下一步，用户确认测试环境和 read-only 动作后，用 Stage608 wrapper 捕获 live ticks，保持 `send_order=0`。
- 扩池侧：继续补 `j/i` DCE 官方源或授权替代源，以及每品种真实/独立分钟 TCA。
- 观察侧：为 `soft_agri/precious_metals` 建 point-in-time monitor ledger，只记录，不回测救援。
- 搜索侧：寻找 `2` 个非 DCE、低相关、source 可执行、容量合格的新独立经济驱动。
