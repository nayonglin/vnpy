# Stage062 会员持仓 DCE 替代路径可修复性审计

## 基本信息

- 时间：2026-06-20 06:21 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 当前工作模式：`day`
- 当前官方正式版：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
- 阶段性质：外生会员持仓数据源可修复性审计，不是真实组合引擎，不新增交易规则，不触发 A/B，不改正式配置，不连接 CTP，不调用订单 API。
- 是否重要突破版本：否。它不是收益突破；但它是会员持仓路线的负向边界版本，证明在当前 AKShare 1.18.55 和本地缓存条件下不能继续用低覆盖样本调策略。
- 决策：`stage062_dce_alternative_routes_blocked_no_strategy_rule`

## 外部调研和判断

- GitHub 调研：AKShare issue #7002 在 2026-01-26 报告 `futures_dce_position_rank` 出现 `BadZipFile('File is not a zip file')`，与本阶段 DCE smoke 结果一致。
- 官方文档调研：AKShare 期货文档说明各交易所公布会员排名口径不同，DCE 只公布品种总持仓排名，SHFE/CFFEX 是合约排名后聚合，CZCE 同时有合约和品种原始数据；因此跨交易所口径必须先点时化和标准化，不能直接用一个统一 score 交易化。
- 版本调研：AKShare changelog 显示 `futures_dce_position_rank` 和 `get_rank_table_czce` 近版本多次修复/改名，说明该数据源本身具有接口稳定性风险。
- 我的判断：会员持仓作为供需结构信息有理论价值，但当前问题是数据工程和口径问题，不是策略参数问题。继续扫 TopN、rolling、level/flow 权重是在低覆盖、右尾缺失样本上过拟合。

参考：
- https://github.com/akfamily/akshare/issues/7002
- https://akshare.akfamily.xyz/data/futures/futures.html
- https://akshare.akfamily.xyz/changelog.html

## 本阶段改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage062_member_rank_dce_alt_route_audit.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage062_member_rank_dce_alt_route_audit/`
- 新增参数：
  - `timeout_seconds=12`，用于 DCE/CZCE/SHFE/GFEX endpoint smoke。
  - 固定 DCE probe 日期：`20240603` 和 `20210301`。
  - 固定 DCE target：`JM`，同时用 `JM|I|LH|J` 检查旧网页补充路径命中。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无真实交易回测；本阶段只复用官方曲线、Stage028 会员持仓特征和覆盖缺口做审计。
- 修改回测结果：无。
- 删除回测结果：无。

## 输入和输出

- 输入 official closed lots：`399`
- Stage028 member-ready：`69/399 = 17.2932%`
- member missing：`330`
- member missing net PnL：`+22,263,004.00`
- `2020-2022` missing count：`212`
- `2020-2022` missing net PnL：`+9,241,635.60`
- DCE alternative route target hit：`False`
- positive control ok count：`3`，CZCE/SHFE/GFEX 当日 smoke 均能命中目标品种。

## 官方基准指标

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6339`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- closed-lot 胜率：`36.0902%`

## DCE 路径审计结果

| probe | 函数 | 日期 | 结果 | 说明 |
| --- | --- | --- | --- | --- |
| `dce_batch_zip_jm_20240603` | `futures_dce_position_rank` | `20240603` | error | `BadZipFile: File is not a zip file` |
| `dce_batch_zip_jm_20210301` | `futures_dce_position_rank` | `20210301` | error | `BadZipFile: File is not a zip file` |
| `dce_rank_table_jm_20240603` | `get_dce_rank_table` | `20240603` | timeout | `>12s` |
| `dce_rank_table_jm_20210301` | `get_dce_rank_table` | `20210301` | timeout | `>12s` |
| `dce_position_rank_other_20240603` | `futures_dce_position_rank_other` | `20240603` | error | `IndexError: list index out of range` |
| `dce_position_rank_other_20210301` | `futures_dce_position_rank_other` | `20210301` | error | `IndexError: list index out of range` |

## 交易所缺口

| 交易所 | closed lots | ready | missing | ready rate | missing 2020-2022 | missing net PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| CZCE | 182 | 42 | 140 | 23.0769% | 93 | `+2,554,628.90` |
| SHFE | 161 | 27 | 134 | 16.7702% | 86 | `+4,594,648.90` |
| DCE | 50 | 0 | 50 | 0.0000% | 33 | `+14,851,026.20` |
| GFEX | 6 | 0 | 6 | 0.0000% | 0 | `+262,700.00` |

## 视觉分析

- `path_coverage_chart`：官方权益的主复利台阶集中在 `2020-2022` 阴影区，但底部 coverage 图在这段大量是灰色 missing，而不是绿色 ready。说明当前会员持仓覆盖缺口正好覆盖关键右尾与回撤区，不能用 ready 样本代表全路径。
- `missing_exchange_contribution_chart`：DCE missing 红线在 `2025` 后出现明显跃升，DCE 缺口本身是大额正贡献，不是可以保守跳过的坏样本。
- `dce_route_status_chart`：DCE 三类替代路径 call ok 与 target hit 全部为 `0`，没有灰色中间状态，结论是当前本地 AKShare 路径不可用。
- `product_gap_chart`：`jm.DCE` 缺失笔数和缺失净贡献同时最高，`hc/rb/OI/CF/MA` 等也有大缺口；缺失不是单一产品小瑕疵，而是跨交易所、跨品种的数据结构问题。

## 反过拟合反思

- 开始前判断：否。这个阶段不是为了从历史亏损桶找阈值，而是验证会员持仓路线的数据覆盖和 endpoint 是否足以支持后续研究；这是减少伪发现的前置审计。
- 完成后判断：否。结果直接关停当前会员持仓参数研究，没有把 `17.2932%` ready 样本继续拆 TopN/rolling/level-flow，也没有把 DCE missing 当作可交易信号。

## 是否仍有价值继续

- 开始前判断：有。会员持仓是比产品总 OI 更细的供需结构信息，理论上更接近“高质量信号用最小风险”的外生确认源。
- 完成后判断：有条件有价值。作为策略研究暂时不值得继续；作为数据工程仍值得，但必须先修 DCE/CZCE/SHFE/GFEX 历史回填和口径一致性。补齐前不能进入 true engine、A/B 或参数研究。

## 结论和 TODO

- 结论：当前会员持仓路线不产生候选，不触发 A/B。DCE 替代路径被 `BadZipFile`、timeout 和旧网页 `IndexError` 阻断；CZCE/SHFE/GFEX 正向 smoke 只能证明接口可调用，不能证明历史覆盖足以交易化。
- TODO：
  - 停止会员持仓 TopN、rolling window、level/flow 权重、阈值和交易所/产品切片研究。
  - 若继续会员持仓，只能先做独立数据工程：DCE parser 修复、官方源落盘、跨交易所品种/合约口径统一、点时化回填。
  - 策略研究下一步应换到其他真正外生、入场前可见、覆盖完整的数据源，或基于 Stage045 已同步的 timestamp-ready replay 子集提出新的第一性分钟候选。

## 产物

- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage062_member_rank_dce_alt_route_audit/qmt_roll_stage062_c9_minrisk_member_rank_dce_alt_route_audit_decision_stage062_member_rank_dce_alt_route_audit_v1.json`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage062_member_rank_dce_alt_route_audit/qmt_roll_stage062_c9_minrisk_member_rank_dce_alt_route_audit_summary_stage062_member_rank_dce_alt_route_audit_v1.csv`
- endpoint smoke：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage062_member_rank_dce_alt_route_audit/qmt_roll_stage062_c9_minrisk_member_rank_dce_alt_route_audit_endpoint_smoke_stage062_member_rank_dce_alt_route_audit_v1.csv`
- exchange gap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage062_member_rank_dce_alt_route_audit/qmt_roll_stage062_c9_minrisk_member_rank_dce_alt_route_audit_exchange_gap_summary_stage062_member_rank_dce_alt_route_audit_v1.csv`
- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage062_member_rank_dce_alt_route_audit/qmt_roll_stage062_c9_minrisk_member_rank_dce_alt_route_audit_report_stage062_member_rank_dce_alt_route_audit_v1.md`
- 图像：
  - `qmt_roll_stage062_c9_minrisk_member_rank_dce_alt_route_audit_path_coverage_chart_stage062_member_rank_dce_alt_route_audit_v1.png`
  - `qmt_roll_stage062_c9_minrisk_member_rank_dce_alt_route_audit_missing_exchange_contribution_chart_stage062_member_rank_dce_alt_route_audit_v1.png`
  - `qmt_roll_stage062_c9_minrisk_member_rank_dce_alt_route_audit_dce_route_status_chart_stage062_member_rank_dce_alt_route_audit_v1.png`
  - `qmt_roll_stage062_c9_minrisk_member_rank_dce_alt_route_audit_product_gap_chart_stage062_member_rank_dce_alt_route_audit_v1.png`
